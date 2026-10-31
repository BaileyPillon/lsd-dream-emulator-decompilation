"""Compare original complete TMD draw calls on constructed packets.

Actual original vertex loading, projection, shading and OT submission execute.
Optional recursive fixtures execute all eight subdivision families. Matrix
replacement, GPU pixels and natural scenes remain separate acceptance gates.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
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
    GLOBALS,FORMATS,GPU_BYTES,case_fixture,expected_draw,packet_specs)
from tools.tmd_recursive_model import FUNCTIONS,RETURNS
from tools.verify_model_packets import backend_identity

START,END=0x80018464,0x8001CA90
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
RECURSIVE_FAULTS=(
    dict(name='recursive-midpoint-x-store',address=0x8001A6C0,original=0xA4EF0000,replacement=0xA4EF0002,
        case=dict(mode=0x21,flags=1)),
    dict(name='recursive-red-average',address=0x8001AF50,original=0x000F7842,replacement=0x000F7882,
        case=dict(mode=0x31,flags=1)),
    dict(name='recursive-quad-center-average',address=0x8001B310,original=0x00031883,replacement=0x00031843,
        case=dict(mode=0x39,flags=1,vertices=((-1022,-1024,1024),(1026,-1024,1024),
            (-1022,1024,1024),(1026,1024,1024)))),
    dict(name='recursive-packet-length',address=0x8001A8B8,original=0x3C0E0400,replacement=0x3C0E0500,
        case=dict(mode=0x21,flags=1)),
    dict(name='recursive-near-threshold',address=0x8001A588,original=0x0019C043,replacement=0x0019C083,
        case=dict(mode=0x21,flags=1,vertices=((-256,-256,96),(256,-256,96),
            (-256,256,96),(256,256,96)))),
)
RUN_FAULTS=(
    dict(name='primitive-output-cursor',address=0x80018A70,original=0x00408021,replacement=0x02008021,
        case=dict(packets=[dict(mode=0x21,flags=1)]*2)),
    dict(name='primitive-loop-condition',address=0x80018A78,original=0x1680FFE6,replacement=0x1280FFE6,
        case=dict(packets=[dict(mode=0x21,flags=1)]*2)),
    dict(name='textured-run-RGB-reinitialization',address=0x80018B68,original=0x1680FFD0,replacement=0x1680FFCD,
        case=dict(packets=[dict(mode=0x24,flags=0)]*2)),
)


class DrawMachine(projection.Machine):
    def __init__(self,executable,bridge,fault=None):
        super().__init__(executable,bridge)
        at=executable_offset(executable,START,PARENT_BYTES)
        require(projection.sha(executable[at:at+PARENT_BYTES])==PARENT_SHA,'Original complete drawer differs.')
        for kind,(entry,body,leaf) in FUNCTIONS.items():
            for return_address,target in [(RETURNS[kind][0],entry)]+[(r,body) for r in RETURNS[kind][1]]:
                at=executable_offset(executable,return_address-8,4)
                word=struct.unpack_from('<I',executable,at)[0]
                require(word>>26==3 and (0x80000000|(word&0x3FFFFFF)<<2)==target,
                    'Recursive control-flow metadata differs: '+kind)
        index=json.loads((ROOT/'research/original-functions.json').read_bytes())['functions']
        by_address={int(row['address'],16):row for row in index}
        self.recursive_ranges=[]
        self.recursive_cull_at={}
        self.recursive_body_at={body&MASK:kind for kind,(_,body,_) in FUNCTIONS.items()}
        self.recursive_leaf_at={leaf&MASK:kind for kind,(_,_,leaf) in FUNCTIONS.items()}
        self.recursive_root_at={entry&MASK:kind for kind,(entry,_,_) in FUNCTIONS.items()}
        self.mode_run_at=0x18760
        self.primitive_at={0x193C0,0x194A4}
        for address,word in ((0x80018760,0x96620002),(0x800193C0,0x27BDFFE0),(0x800194A4,0x27BDFFD8)):
            require(struct.unpack_from('<I',executable,executable_offset(executable,address,4))[0]==word,
                'Original mode/primitive entry metadata differs.')
        for kind,addresses in FUNCTIONS.items():
            for address in addresses:
                row=by_address[address]
                at=executable_offset(executable,address,row['bytes'])
                raw=executable[at:at+row['bytes']]
                require(projection.sha(raw)==row['sha256'],'Original recursive function range differs.')
                self.recursive_ranges.append(row)
                if address==addresses[1]:
                    words=struct.unpack('<'+'I'*(len(raw)//4),raw)
                    exits=[address+4*i for i in range(len(words)-1)
                        if words[i]==0x00801021 and words[i+1]==0x03E00008]
                    require(len(exits)==6,'Original recursive cull/return shape differs: '+kind)
                    self.recursive_cull_at.update({at&MASK:(kind,reason) for at,reason in
                        zip(exits[:5],('near','right','left','bottom','top'))})
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
        for at,length in ((ORDER,4096),(GPU,GPU_BYTES),(projection.STACK-0x800,4096),
                (0x8A000,8192),(0x8E000,4096),(0x90000,4096)):
            self.cpu.mem_protect(at,length,self.u.UC_PROT_READ|self.u.UC_PROT_WRITE)
        global_spans=[(at,at+length) for at,length in GLOBALS]
        self.read_ranges=[(BUFFER,BUFFER+4096),(ORDER,ORDER+4096),(GPU,GPU+GPU_BYTES),
            (CONTEXT,CONTEXT+0xB4),(projection.STACK-0xC0,projection.STACK+0x20),
            (0x8A824,0x8A838),(0x902E0,0x902E4),*global_spans]
        self.write_ranges=[(GPU,GPU+GPU_BYTES),(ORDER,ORDER+4096),(CONTEXT,CONTEXT+0xB4),
            (projection.STACK-0xC0,projection.STACK),*global_spans]
        self.lower,self.upper=START&MASK,END&MASK
        self.access_counts=Counter()
        self.recursive_entries,self.recursive_packets,self.recursive_culls=Counter(),Counter(),Counter()
        self.recursive_roots=Counter()
        self.mode_runs=self.primitive_calls=0

    def instruction(self,cpu,address,size,unused):
        physical=address&MASK
        if physical==self.mode_run_at:self.mode_runs+=1
        if physical in self.primitive_at:self.primitive_calls+=1
        kind=self.recursive_root_at.get(physical)
        if kind:self.recursive_roots[kind]+=1
        kind=self.recursive_body_at.get(physical)
        if kind:self.recursive_entries[kind]+=1
        kind=self.recursive_leaf_at.get(physical)
        if kind:self.recursive_packets[kind]+=1
        cull=self.recursive_cull_at.get(physical)
        if cull:self.recursive_culls[cull]+=1
        super().instruction(cpu,address,size,unused)

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
        self.recursive_entries,self.recursive_packets,self.recursive_culls=Counter(),Counter(),Counter()
        self.recursive_roots=Counter()
        self.mode_runs=self.primitive_calls=0
        steps_before=self.steps
        self.label=json.dumps(case,sort_keys=True)
        try:cpu.emu_start(START,projection.STOP|alias,count=1000000)
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
        recursion=getattr(state,'recursive_stats',{})
        draw_stats=state.draw_stats
        recursive_equal=(dict(self.recursive_entries)==draw_stats['recursive_entries'] and
            dict(self.recursive_packets)==draw_stats['recursive_packets'] and
            dict(self.recursive_roots)==draw_stats['recursive_roots'] and
            dict(self.recursive_culls)=={(kind,reason):count for kind,reasons in draw_stats['recursive_culls'].items()
                for reason,count in reasons.items()})
        run_equal=self.mode_runs==draw_stats['mode_runs'] and self.primitive_calls==draw_stats['primitive_calls']
        result=dict(outcome=outcome,equal=not differences and state_equal and command_equal and counters_equal and recursive_equal and run_equal,
            differences=differences,GTE_state_equal=state_equal,commands_equal=command_equal,
            native_counters_equal=counters_equal,complete_buffer_sha256=hashes,
            recursive_calls_and_packets_equal=recursive_equal,recursive_stats=recursion,
            mode_runs_and_primitive_calls_equal=run_equal,draw_stats=draw_stats,
            instructions=self.steps-steps_before,native_commands=observed['native_commands']-before_gte['native_commands'],
            command_words=[hex(v) for v in self.command_words],saved_ABI_and_immutable_VM_preserved=True)
        if not allow_mismatch:require(result['equal'],'Original full draw differs: '+json.dumps(result))
        return result


def recursive_cases():
    large=((-1024,-1024,1024),(1024,-1024,1024),(-1024,1024,1024),(1024,1024,1024))
    odd=((-1025,-1023,1025),(1024,-1022,1024),(-1024,1024,1025),(1025,1023,1024))
    for mode,flags in FORMATS:
        for depth in (1,2,3):
            for alias in (0,0x80000000):
                for semi in (0,2):
                    yield dict(mode=mode|semi,flags=flags,attributes=depth<<9,vertices=large,
                        alias=alias,ordering_head=0x00FFFFFF)
        yield dict(mode=mode,flags=flags,attributes=0x640,vertices=odd,ordering_head=0xA1FFFFFF,fog=2047)
        yield dict(mode=mode,flags=flags,attributes=0x40,vertices=large,division_override=2,ordering_head=0x00FFFFFF)
        for axis,delta in ((0,3072),(0,-3072),(1,3072),(1,-3072)):
            vertices=tuple(tuple(value+(delta if i==axis else 0) for i,value in enumerate(point)) for point in large)
            yield dict(mode=mode,flags=flags,attributes=0x200,vertices=vertices,ordering_head=0x00FFFFFF)
        yield dict(mode=mode,flags=flags,attributes=0x200,
            vertices=((-256,-256,64),(256,-256,64),(-256,256,64),(256,256,64)),ordering_head=0x00FFFFFF)
    for mode,flags in ((0x21,1),(0x29,1),(0x31,1),(0x39,1),(0x25,1),(0x2D,1),(0x35,1),(0x3D,1)):
        for depth in (4,5):
            yield dict(mode=mode,flags=flags,attributes=depth<<9,vertices=large,ordering_head=0x00FFFFFF)


def cases(include_recursive=False):
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
    if include_recursive:yield from recursive_cases()


def primitive_run_cases():
    """Linked runs with shared state, valid indices and bounded output arenas."""
    rng=random.Random(0x4C534452)
    normals=((256,768,4096),(-768,256,2048))
    def packet(mode,flags,index=0,indices=None):
        result=dict(mode=mode,flags=flags,normal_index=index%2,
            colors=[rng.getrandbits(32) for _ in range(4)],uv=[rng.getrandbits(32) for _ in range(4)],
            ignored_count=rng.randrange(65536))
        if indices is not None:result['indices']=indices
        return result
    for mode,flags in FORMATS:
        for count in (2,3,7):
            for alias in (0,0x80000000):
                for attrs in (0,0x48):
                    yield dict(packets=[packet(mode,flags,i) for i in range(count)],normals=normals,
                        alias=alias,attributes=attrs,ordering_head=0x00FFFFFF)
        count=4 if mode&8 else 3
        valid=tuple(range(count))
        back=(0,2,1,3) if count==4 else (0,2,1)
        for order in ((back,valid,valid),(valid,back,valid),(valid,valid,back),
                ((0,)*count,valid,(0,)*count)):
            yield dict(packets=[packet(mode,flags,i,indices) for i,indices in enumerate(order)],normals=normals)
        yield dict(packets=[packet(mode,flags,i) for i in range(3)],normals=normals,fog=4096)
        yield dict(packets=[packet(mode,flags,i) for i in range(3)],normals=normals,attributes=0x80000000)
        # Exact mode-byte transitions split a linked run, including semi-transparency.
        yield dict(packets=[packet(mode|semi,flags,i) for i,semi in enumerate((0,2,2,0))],normals=normals)
    # Separate the two 0x20 flag variants with another mode: the SDK linker
    # groups by mode byte, not flags. Unsupported same-mode flag mixtures fail validation.
    mixed=(FORMATS[0],FORMATS[2],FORMATS[1],*FORMATS[3:])
    for formats in (mixed,tuple(reversed(mixed))):
        for alias in (0,0x80000000):
            for attrs,light,fog in ((0,0,0),(0x40,0,2047),(0x20,1,4095),(0x48,0,0)):
                yield dict(packets=[packet(mode,flags,i) for i,(mode,flags) in enumerate(formats)],
                    normals=normals,alias=alias,attributes=attrs,light_mode=light,fog=fog)
    # One run spans submitted, backface/degenerate and recursive-cull paths.
    vertices=((-128,-128,4096),(128,-128,4096),(-128,128,4096),(128,128,4096),
        (-1024,-1024,1024),(1024,-1024,1024),(-1024,1024,1024),(1024,1024,1024),
        (-256,-256,64),(256,-256,64),(-256,256,64),(256,256,64))
    for mode,flags in FORMATS:
        count=4 if mode&8 else 3
        groups=(tuple(range(count)),tuple(range(4,4+count)),tuple(range(8,8+count)),
            (0,)*count,tuple(range(count)))
        for alias in (0,0x80000000):
            for depth in (1,2):
                yield dict(packets=[packet(mode,flags,i,indices) for i,indices in enumerate(groups)],
                    vertices=vertices,normals=normals,attributes=depth<<9,alias=alias,ordering_head=0x00FFFFFF)
    large=vertices[4:8]
    for formats in (mixed,tuple(reversed(mixed))):
        for depth in (1,2):
            for alias in (0,0x80000000):
                yield dict(packets=[packet(mode,flags,i) for i,(mode,flags) in enumerate(formats)],
                    vertices=large,normals=normals,attributes=depth<<9,alias=alias,ordering_head=0x00FFFFFF)
    for _ in range(48):
        specs=[]
        for index in range(rng.randrange(2,25)):
            mode,flags=rng.choice(FORMATS)
            mode|=rng.choice((0,2))
            if specs and mode==specs[-1]['mode']:flags=specs[-1]['flags']
            count=4 if mode&8 else 3
            indices=tuple(range(count)) if rng.randrange(4) else (0,2,1,3)[:count]
            specs.append(packet(mode,flags,index,indices))
        yield dict(packets=specs,normals=normals,alias=rng.choice((0,0x80000000)),
            attributes=rng.choice((0,0x40,0x48)),fog=rng.choice((0,2047,4095)),ordering_head=0x00FFFFFF)
    for alias in (0,0x80000000):
        yield dict(packets=[packet(0x21,1,i) for i in range(64)],normals=normals,alias=alias)
    yield dict(packets=[])


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


def verify(executable_path,bridge_path,runtime,destination,include_recursive=False,include_runs=False):
    require(not (include_recursive and include_runs),'Choose one bounded profile per output directory.')
    require(not destination.exists() and destination.parent.is_dir(),'Choose a fresh existing-parent destination.')
    executable=executable_path.read_bytes()
    require(hashlib.sha1(executable).hexdigest()==ORIGINAL_SHA1,'Canonical original executable differs.')
    sources=('tools/verify_tmd_renderer.py','tools/tmd_renderer_model.py','tools/verify_tmd_projection.py',
        'tools/gte_state_model.py','tools/gte_state_bridge.py','tools/nymashock_gte_state_bridge.cs',
        'tools/tmd_packets.py','tools/verify_gte_state.py','tools/verify_model_packets.py','tools/psx_image.py',
        'tools/tmd_recursive_model.py','research/original-functions.json')
    before={name:file_sha(ROOT/name) for name in sources}
    destination.mkdir()
    started=time.monotonic()
    partial_checks=partial_transfer_checks()
    bridge=NativeStateBridge(bridge_path,runtime,destination/'native-errors.log')
    totals,outcomes,formats=Counter(),Counter(),Counter()
    recursive_families,recursive_depths,recursive_culls=Counter(),Counter(),Counter()
    member_outcomes,run_lengths=Counter(),Counter()
    journal=destination/'cases.jsonl'
    try:
        machine=DrawMachine(executable,bridge)
        with journal.open('x',encoding='utf-8',newline='\n') as stream:
            selected_cases=primitive_run_cases() if include_runs else cases(include_recursive)
            for ordinal,case in enumerate(selected_cases):
                require(time.monotonic()-started<900,'Draw profile exceeded 15 minutes.')
                result=machine.draw(case,allow_mismatch=True)
                if not result['equal']:
                    with (destination/'failure.json').open('x') as failure:json.dump(dict(case=case,result=result),failure,indent=2)
                    raise ValueError('Independent full draw mismatch at case '+str(ordinal)+': '+json.dumps(result))
                stream.write(json.dumps(dict(ordinal=ordinal,case=case,observed=result),separators=(',',':'))+'\n')
                require(stream.tell()<2*1024**2,'Draw journal exceeds 2 MiB.')
                totals.update(calls=1,instructions=result['instructions'],native_commands=result['native_commands'])
                stats=result['draw_stats']
                totals.update(mode_runs=stats['mode_runs'],primitive_calls=stats['primitive_calls'],
                    recursive_nodes=sum(stats['recursive_entries'].values()),
                    subdivided_packets=sum(stats['recursive_packets'].values()))
                recursive_families.update(stats['recursive_roots'])
                recursive_depths.update(stats['recursive_limits'])
                for reasons in stats['recursive_culls'].values():recursive_culls.update(reasons)
                member_outcomes.update(stats['outcomes'])
                outcomes[result['outcome']]+=1
                if include_runs:
                    specs=packet_specs(case)
                    run_lengths[str(len(specs))]+=1
                    for spec in specs:formats[f"0x{spec['mode']:02x}/0x{spec['flags']:02x}"]+=1
                else:formats[f"0x{case['mode']:02x}/0x{case['flags']:02x}"]+=1
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
        recursive_controls=[]
        if include_recursive:
            for fault in RECURSIVE_FAULTS:
                case={**dict(attributes=0x200,ordering_head=0x00FFFFFF,
                    vertices=((-1024,-1024,1024),(1024,-1024,1024),(-1024,1024,1024),(1024,1024,1024))),
                    **fault['case']}
                control=DrawMachine(executable,bridge,fault)
                result=control.draw(case,allow_mismatch=True)
                require(not result['equal'] and result['differences'] and control.fault_hits>0,
                    'Recursive original-code control was not detected: '+fault['name'])
                recursive_controls.append(dict(name=fault['name'],fault_hits=control.fault_hits,detected=True,
                    clean_original_return=True,saved_ABI_and_immutable_VM_preserved=True,
                    differences=result['differences'],GTE_state_equal=result['GTE_state_equal'],
                    original_command_sequence_equal=result['commands_equal'],native_commands=result['native_commands']))
        run_controls=[]
        if include_runs:
            for fault in RUN_FAULTS:
                control=DrawMachine(executable,bridge,fault)
                result=control.draw(fault['case'],allow_mismatch=True)
                require(not result['equal'] and control.fault_hits>0,
                    'Original primitive-run control was not detected: '+fault['name'])
                run_controls.append(dict(name=fault['name'],fault_hits=control.fault_hits,detected=True,
                    clean_original_return=True,saved_ABI_and_immutable_VM_preserved=True,
                    differences=result['differences'],GTE_state_equal=result['GTE_state_equal'],
                    original_command_sequence_equal=result['commands_equal'],
                    native_counters_equal=result['native_counters_equal'],
                    mode_runs_and_primitive_calls_equal=result['mode_runs_and_primitive_calls_equal']))
    finally:bridge.close()
    require(before=={name:file_sha(ROOT/name) for name in sources},'Executed renderer sources changed.')
    report=dict(schema_version=1,status='constructed_original_full_draw_matches',
        generated_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-started,
        original_executable_sha1=ORIGINAL_SHA1,function=dict(address=hex(START),bytes=PARENT_BYTES,sha256=PARENT_SHA),
        backend=backend_identity(),totals=dict(totals),outcomes=dict(outcomes),formats=dict(formats),
        primitive_outcomes=dict(member_outcomes),supplied_primitive_counts=dict(run_lengths),
        recursive_families=dict(recursive_families),recursive_depths=dict(recursive_depths),
        observed_recursive_culling_returns=dict(recursive_culls),recursive_function_ranges=machine.recursive_ranges,
        recursive_original_code_controls=recursive_controls,
        primitive_run_original_code_controls=run_controls,
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
        bounded_recursive_profile_requested=include_recursive,
        bounded_primitive_run_profile_requested=include_runs,
        original_mode_primitive_and_recursive_entry_counts_compared=True,
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
    profiles=parser.add_mutually_exclusive_group()
    profiles.add_argument('--recursive',action='store_true',help='Add the bounded recursive subdivision fixtures.')
    profiles.add_argument('--primitive-runs',action='store_true',help='Use the separate bounded primitive/mode-run profile.')
    args=parser.parse_args(argv)
    try:
        result=verify(args.executable,args.bridge,args.runtime,args.output,args.recursive,args.primitive_runs)
        print(json.dumps({k:result[k] for k in ('status','totals','outcomes')}))
        return 0
    except (OSError,ValueError,KeyError) as error:
        print(json.dumps(dict(status='invalid_original_draw_profile',error=str(error))),file=sys.stderr)
        return 2


if __name__=='__main__':raise SystemExit(main())
