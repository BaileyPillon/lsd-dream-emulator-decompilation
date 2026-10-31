"""Compare original complete TMD draw calls on constructed unclipped packets.

Actual original vertex loading, projection, shading and OT submission execute.
The profile excludes recursive clipping, matrix replacement, GPU pixels and
natural scenes; passing cases do not accept a whole rendering feature.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import verify_tmd_projection as projection
from tools.gte_state_bridge import NativeStateBridge
from tools.gte_state_model import require,unsigned,signed
from tools.inventory_model_packets import file_sha
from tools.psx_image import ORIGINAL_SHA1,executable_offset
from tools.tmd_renderer_model import (BUFFER,OBJECT,OT,ORDER,GPU,CONTEXT,TRI,QUAD,OUT,
    GLOBALS,FORMATS,case_fixture,expected_draw)
from tools.verify_model_packets import backend_identity

START,END=0x80018464,0x8001A564
PARENT_BYTES=3816
PARENT_SHA='c6ff654e26c849115619693a6b1e84a8c68edfda4a0b5a5c8cd18f66aab18337'
MASK=0x1FFFFFFF
FAULTS=(
    dict(name='packet-length',address=0x800189FC,original=0x34020004,replacement=0x34020005,
        case=dict(mode=0x21,flags=1)),
    dict(name='raw-texture-flag',address=0x80019394,original=0x34420001,replacement=0x34420000,
        case=dict(mode=0x25,flags=1,attributes=0x40)),
    dict(name='bbox-final-vertex-endpoint',address=0x8001A2A0,original=0x24A5005C,replacement=0x24A50060,
        case=dict(mode=0x21,flags=1)),
    dict(name='ordering-table-link-mask',address=0x800197F0,original=0x3484FFFF,replacement=0x3484FFF0,
        case=dict(mode=0x21,flags=1)),
)


class DrawMachine(projection.Machine):
    def __init__(self,executable,bridge,fault=None):
        super().__init__(executable,bridge)
        at=executable_offset(executable,START,PARENT_BYTES)
        require(projection.sha(executable[at:at+PARENT_BYTES])==PARENT_SHA,'Original complete drawer differs.')
        # Do not lower the already transported projection helper a second time.
        self.lower_cop2(START&MASK,projection.FUNCTION-START)
        tail=projection.FUNCTION+projection.FUNCTION_BYTES
        self.lower_cop2(tail&MASK,END-tail)
        if fault:
            at=fault['address']&MASK
            require(struct.unpack('<I',self.cpu.mem_read(at,4))[0]==fault['original'],
                'Fault instruction differs: '+fault['name'])
            require(at not in self.cop2_words,'Use an ordinary-instruction fault.')
            self.cpu.mem_write(at,struct.pack('<I',fault['replacement']))
        self.fault=fault
        self.cpu.mem_map(CONTEXT,4096,self.u.UC_PROT_READ|self.u.UC_PROT_WRITE)
        for at,length in ((ORDER,4096),(GPU,4096),(projection.STACK-0x800,4096),
                (0x8A000,4096),(0x8E000,4096),(0x90000,4096)):
            self.cpu.mem_protect(at,length,self.u.UC_PROT_READ|self.u.UC_PROT_WRITE)
        global_spans=[(at,at+length) for at,length in GLOBALS]
        self.read_ranges=[(BUFFER,BUFFER+4096),(ORDER,ORDER+4096),(GPU,GPU+4096),
            (CONTEXT,CONTEXT+0xB4),(projection.STACK-0xC0,projection.STACK+0x20),
            (0x8A82C,0x8A830),(0x902E0,0x902E4),*global_spans]
        self.write_ranges=[(GPU,GPU+128),(ORDER,ORDER+4096),(CONTEXT,CONTEXT+0xB4),
            (projection.STACK-0xC0,projection.STACK),*global_spans]
        self.lower,self.upper=START&MASK,END&MASK
        self.access_counts=Counter()

    def access(self,cpu,access,address,size,value,unused):
        address &= MASK
        spans=self.write_ranges if access==self.u.UC_MEM_WRITE else self.read_ranges
        require(any(a<=address and address+size<=b for a,b in spans),
            'Draw access left declared spans: '+hex(address)+' size '+str(size))
        self.access_counts['write' if access==self.u.UC_MEM_WRITE else 'read']+=1

    def guard_integer_memory(self,word):
        op=word>>26
        if op in (0x22,0x26,0x2A,0x2E):
            base=self.cpu.reg_read(getattr(self.r,'UC_MIPS_REG_'+str(word>>21&31)))
            at=unsigned(base+signed(word,16))&~3
            # Conservatively guard the complete aligned word for partial
            # transfers, including possible backend read/modify/write traffic.
            self.access(self.cpu,self.u.UC_MEM_WRITE if op in (0x2A,0x2E) else self.u.UC_MEM_READ,at,4,0,None)
            return
        super().guard_integer_memory(word)

    def immutable_hash(self):
        data=bytearray(self.cpu.mem_read(0,projection.RAM_BYTES))
        for start,end in self.write_ranges:
            if start<projection.RAM_BYTES:data[start:end]=bytes(end-start)
        return projection.sha(data)

    def draw(self,case,allow_mismatch=False):
        cpu,reg=self.cpu,self.r
        initial,values,writes=case_fixture(case)
        predicted,state,commands,outcome=expected_draw(case)
        cpu.mem_write(BUFFER,initial)
        for at,value in values.items():cpu.mem_write(at,value)
        cpu.mem_write(0x8A82C,bytes((17,34,51,68)))
        cpu.mem_write(0x902E0,struct.pack('<I',case.get('light_mode',0)))
        cpu.mem_write(projection.STACK-0x800,bytes([0xC9])*4096)
        before_gte=self.adapter.reset(writes)
        saved_values=[0xAD000000+i*0x10203 for i in range(len(self.saved))]
        for register,value in zip(self.saved,saved_values):cpu.reg_write(register,value)
        alias=case.get('alias',0)
        settings={4:OBJECT|alias,5:OT|alias,6:case.get('shift',4),7:CONTEXT|alias,
            28:0x8008A808,29:projection.STACK|alias,31:projection.STOP|alias,
            1:0xACDC0123,26:0xCAFE0026}
        for number,value in settings.items():cpu.reg_write(getattr(reg,'UC_MIPS_REG_'+str(number)),unsigned(value))
        immutable=self.immutable_hash()
        self.command_words=[]
        steps_before=self.steps
        self.label=json.dumps(case,sort_keys=True)
        try:cpu.emu_start(START,projection.STOP|alias,count=50000)
        except self.u.UcError as error:
            raise ValueError('Original draw failed at '+hex(cpu.reg_read(reg.UC_MIPS_REG_PC))+
                ': '+repr(getattr(cpu,'_hook_exception',None))+': '+repr(list(self.history))) from error
        self.restore_temp()
        require(cpu.reg_read(reg.UC_MIPS_REG_PC)==projection.STOP|alias,'Draw did not return within its bound.')
        require(cpu.reg_read(reg.UC_MIPS_REG_SP)==projection.STACK|alias
            and cpu.reg_read(reg.UC_MIPS_REG_GP)==0x8008A808
            and cpu.reg_read(reg.UC_MIPS_REG_RA)==projection.STOP|alias
            and [cpu.reg_read(r) for r in self.saved]==saved_values,'Draw return ABI differs.')
        require(self.immutable_hash()==immutable,'Immutable VM bytes changed.')
        observed=self.adapter.flush()
        differences={}
        hashes={}
        for at,wanted in predicted.items():
            actual=bytes(cpu.mem_read(at,len(wanted)))
            hashes[hex(at)]=projection.sha(actual)
            if actual!=wanted:
                differences[hex(at)]=[dict(offset=hex(i),expected=hex(struct.unpack_from('<I',wanted,i)[0]),
                    observed=hex(struct.unpack_from('<I',actual,i)[0])) for i in range(0,len(wanted),4)
                    if actual[i:i+4]!=wanted[i:i+4]][:24]
        state_equal=observed['cr']==state.control() and observed['dr']==state.data()
        command_equal=self.command_words==commands
        counters_equal=observed['native_commands']-before_gte['native_commands']==state.commands and (
            observed['native_data_writes']-before_gte['native_data_writes']==state.data_writes)
        result=dict(outcome=outcome,equal=not differences and state_equal and command_equal and counters_equal,
            differences=differences,GTE_state_equal=state_equal,commands_equal=command_equal,
            native_counters_equal=counters_equal,complete_buffer_sha256=hashes,
            instructions=self.steps-steps_before,native_commands=observed['native_commands']-before_gte['native_commands'],
            command_words=[hex(v) for v in self.command_words],saved_ABI_and_immutable_VM_preserved=True)
        if not allow_mismatch:require(result['equal'],'Original full draw differs: '+json.dumps(result))
        return result


def cases():
    for mode,flags in FORMATS:
        for semi in (0,2):
            for alias in (0,0x80000000):
                for attrs,light in ((0,0),(0x40,0),(0x20,1),(0x48,0)):
                    for fog in (0,2047,4095,4096):
                        yield dict(mode=mode|semi,flags=flags,alias=alias,attributes=attrs,light_mode=light,fog=fog)
        for vertices in (((0,0,4096),)*4,
                ((-128,-128,4096),(-128,128,4096),(128,-128,4096),(128,128,4096))):
            yield dict(mode=mode,flags=flags,vertices=vertices)
        yield dict(mode=mode,flags=flags,attributes=0x80000000)
        yield dict(mode=mode,flags=flags,primitives=0)


def partial_transfer_checks():
    """Game-free literal little-endian merge and forbidden-access controls."""
    import unicorn
    from unicorn import mips_const as reg
    loads={0x22:(0x11B2C3D4,0x2211C3D4,0x332211D4,0x44332211),
        0x26:(0x44332211,0xA1443322,0xA1B24433,0xA1B2C344)}
    stores={0x2A:(0x443322A1,0x4433A1B2,0x44A1B2C3,0xA1B2C3D4),
        0x2E:(0xA1B2C3D4,0xB2C3D411,0xC3D42211,0xD4332211)}
    counts=Counter()
    for op in (0x22,0x26,0x2A,0x2E):
        for offset in range(4):
            for delay in (False,True):
                for reject in (False,True):
                    machine=DrawMachine.__new__(DrawMachine)
                    machine.u,machine.r=unicorn,reg
                    cpu=machine.cpu=unicorn.Uc(unicorn.UC_ARCH_MIPS,
                        unicorn.UC_MODE_MIPS32|unicorn.UC_MODE_LITTLE_ENDIAN)
                    cpu.mem_map(0,projection.RAM_BYTES,unicorn.UC_PROT_READ|unicorn.UC_PROT_EXEC)
                    cpu.mem_protect(BUFFER,4096,unicorn.UC_PROT_READ|unicorn.UC_PROT_WRITE)
                    slot=op<<26|5<<21|3<<16|offset
                    words=(0x080065B3,slot,0x34020001,0x03E00008,0) if delay else (slot,0x03E00008,0)
                    cpu.mem_write(0x196C0,struct.pack('<'+'I'*len(words),*words))
                    cpu.mem_write(BUFFER+0x100,struct.pack('<I',0x44332211))
                    cpu.reg_write(reg.UC_MIPS_REG_A1,BUFFER+0x100)
                    cpu.reg_write(reg.UC_MIPS_REG_V1,0xA1B2C3D4)
                    cpu.reg_write(reg.UC_MIPS_REG_RA,projection.STOP)
                    span=(BUFFER+0x104,BUFFER+0x108) if reject else (BUFFER+0x100,BUFFER+0x104)
                    machine.read_ranges=machine.write_ranges=[span]
                    machine.access_counts=Counter()
                    machine.lower,machine.upper,machine.cop2_words=0x196C0,0x196C0+4*len(words),{}
                    def hook(c,address,size,unused):
                        word=struct.unpack('<I',c.mem_read(address&MASK,4))[0]
                        machine.guard_integer_memory(word)
                        machine.guard_branch_delay(word,address)
                    cpu.hook_add(unicorn.UC_HOOK_CODE,hook)
                    before=bytearray(cpu.mem_read(0,projection.RAM_BYTES))
                    if reject:
                        rejected=False
                        try:cpu.emu_start(0x800196C0,projection.STOP,count=20)
                        except ValueError as error:
                            require('left declared spans' in str(error),'Unexpected guard control failure.')
                            rejected=True
                        require(rejected,'Forbidden partial transfer was accepted.')
                        require(bytes(cpu.mem_read(0,projection.RAM_BYTES))==before,'Rejected transfer changed VM memory.')
                        counts['forbidden_partial_transfers_rejected_without_memory_change']+=1
                    else:
                        cpu.emu_start(0x800196C0,projection.STOP,count=20)
                        require(cpu.reg_read(reg.UC_MIPS_REG_PC)==projection.STOP,'Partial transfer program did not return.')
                        value=loads[op][offset] if op in loads else 0xA1B2C3D4
                        require(cpu.reg_read(reg.UC_MIPS_REG_V1)==value,'Partial transfer register differs from literal.')
                        if op in stores:struct.pack_into('<I',before,BUFFER+0x100,stores[op][offset])
                        require(bytes(cpu.mem_read(0,projection.RAM_BYTES))==before,'Partial transfer VM differs from literal.')
                        counts['literal_partial_transfer_programs_passed']+=1
    return dict(counts)


def verify(executable_path,bridge_path,runtime,destination):
    require(not destination.exists() and destination.parent.is_dir(),'Choose a fresh existing-parent destination.')
    executable=executable_path.read_bytes()
    require(hashlib.sha1(executable).hexdigest()==ORIGINAL_SHA1,'Canonical original executable differs.')
    sources=('tools/verify_tmd_renderer.py','tools/tmd_renderer_model.py','tools/verify_tmd_projection.py',
        'tools/gte_state_model.py','tools/gte_state_bridge.py','tools/nymashock_gte_state_bridge.cs',
        'tools/tmd_packets.py','tools/verify_gte_state.py','tools/verify_model_packets.py','tools/psx_image.py')
    before={name:file_sha(ROOT/name) for name in sources}
    destination.mkdir()
    started=time.monotonic()
    partial_checks=partial_transfer_checks()
    bridge=NativeStateBridge(bridge_path,runtime,destination/'native-errors.log')
    totals,outcomes,formats=Counter(),Counter(),Counter()
    journal=destination/'cases.jsonl'
    try:
        machine=DrawMachine(executable,bridge)
        with journal.open('x',encoding='utf-8',newline='\n') as stream:
            for ordinal,case in enumerate(cases()):
                require(time.monotonic()-started<900,'Draw profile exceeded 15 minutes.')
                result=machine.draw(case,allow_mismatch=True)
                if not result['equal']:
                    with (destination/'failure.json').open('x') as failure:json.dump(dict(case=case,result=result),failure,indent=2)
                    raise ValueError('Independent full draw mismatch at case '+str(ordinal)+': '+json.dumps(result))
                stream.write(json.dumps(dict(ordinal=ordinal,case=case,observed=result),separators=(',',':'))+'\n')
                require(stream.tell()<2*1024**2,'Draw journal exceeds 2 MiB.')
                totals.update(calls=1,instructions=result['instructions'],native_commands=result['native_commands'])
                outcomes[result['outcome']]+=1
                formats[f"0x{case['mode']:02x}/0x{case['flags']:02x}"]+=1
        controls=[]
        for fault in FAULTS:
            control=DrawMachine(executable,bridge,fault)
            result=control.draw(fault['case'],allow_mismatch=True)
            require(not result['equal'] and result['differences'] and control.fault_hits>0,
                'Original-code control was not detected: '+fault['name'])
            require(result['GTE_state_equal'] and result['commands_equal'] and result['native_counters_equal'],
                'Control changed more than the declared output interpretation.')
            controls.append(dict(name=fault['name'],fault_hits=control.fault_hits,detected=True,
                clean_original_return=True,saved_ABI_and_immutable_VM_preserved=True,
                differences=result['differences'],native_commands=result['native_commands']))
    finally:bridge.close()
    require(before=={name:file_sha(ROOT/name) for name in sources},'Executed renderer sources changed.')
    report=dict(schema_version=1,status='constructed_original_full_draw_matches',
        generated_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-started,
        original_executable_sha1=ORIGINAL_SHA1,function=dict(address=hex(START),bytes=PARENT_BYTES,sha256=PARENT_SHA),
        backend=backend_identity(),totals=dict(totals),outcomes=dict(outcomes),formats=dict(formats),
        compiled_bridge_sha256=file_sha(bridge_path),source_sha256=before,
        partial_transfer_checks=partial_checks,original_code_controls=controls,
        journal=dict(file=journal.name,bytes=journal.stat().st_size,sha256=file_sha(journal)),
        complete_GPU_OT_context_and_global_buffers_compared=True,
        original_vertex_loading_projection_colors_UVs_and_OT_linking_executed=True,
        saved_ABI_and_all_VM_bytes_outside_declared_mutable_spans_checked=True,
        callee_stack_temporary_bytes_not_independently_predicted=True,
        scratchpad_physical_and_KSEG0_aliases_used=True,no_function_results_stubbed=True,
        original_executable_and_assets_unmodified=True,natural_scene_coverage_verified=False,
        recursive_clipping_and_replacement_matrix_branch_verified=False,
        GPU_rasterization_and_PS1_hardware_timing_verified=False,
        new_matching_C_bytes=0,whole_feature_groups_accepted=0)
    with (destination/'comparison.json').open('x') as stream:json.dump(report,stream,indent=2)
    require(sum(p.stat().st_size for p in destination.iterdir())<2*1024**2,'Profile exceeds retained byte limit.')
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable',type=Path,required=True)
    parser.add_argument('--bridge',type=Path,required=True)
    parser.add_argument('--runtime',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        result=verify(args.executable,args.bridge,args.runtime,args.output)
        print(json.dumps({k:result[k] for k in ('status','totals','outcomes')}))
        return 0
    except (OSError,ValueError,KeyError) as error:
        print(json.dumps(dict(status='invalid_original_draw_profile',error=str(error))),file=sys.stderr)
        return 2


if __name__=='__main__':raise SystemExit(main())
