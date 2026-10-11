"""Audit the original LBD loader with local assets and native dependencies.

Requires a canonical complete build and an inventory from inventory_animations.py.
Uses a ready CD state, synthetic caller objects and the original native allocator,
constructors and SDK map/link code. No GPU rendering or whole-feature acceptance.
An optional private candidate replaces only the loader in Unicorn memory.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import verify_native_ai as native
from tools.inventory_animations import lbd_info

program, reg, functions = None, None, []
MANAGER, SLOT, STREAM, FILE = 0x90000, 0x91000, 0x91200, 0x91400
ITEMS, NODES, COORDS, STATES = 0x92000, 0x94000, 0xA0000, 0xB0000
DATA, POOL, POOL_SIZE, COUNT = 0x100000, 0x140000, 0x10000, 410
BE54, TMD_VT, FILE_VT, PRIM_VT = 0x8004BE54, 0x8006F13C, 0x8006D940, 0x8006BEA0

def w(data, offset, value):
    struct.pack_into('<I', data, offset, value & 0xFFFFFFFF)

def r(data, offset=0):
    return struct.unpack_from('<I', data, offset)[0]

def hash_bytes(data):
    return hashlib.sha256(data).hexdigest()


class Arena:
    def __init__(self):
        self.pool = bytearray([0xD3])*(POOL_SIZE+16)
        self.manager = bytearray([0xE2])*0x1C
        self.cursor = 0
        for offset,value in ((0,POOL),(4,POOL_SIZE),(8,POOL),(12,POOL),(16,1)):
            w(self.manager,offset,value)
        w(self.pool,0,POOL_SIZE|0x40000000)
        w(self.pool,4,0); w(self.pool,8,0)
        w(self.pool,POOL_SIZE-4,POOL); w(self.pool,POOL_SIZE,0x80000000)

    def allocate(self,size):
        size = max(12,(size+3)&~3)+4
        assert POOL_SIZE-self.cursor >= size+16
        offset = self.cursor
        self.cursor += size
        w(self.pool,offset,size)
        w(self.pool,self.cursor,(POOL_SIZE-self.cursor)|0x40000000)
        w(self.pool,self.cursor+4,0); w(self.pool,self.cursor+8,0)
        w(self.pool,POOL_SIZE-4,POOL+self.cursor)
        w(self.manager,8,POOL+self.cursor); w(self.manager,12,POOL+self.cursor)
        return POOL+offset+4

class Machine(native.Machine):
    def __init__(self,body=None,mutation=None):
        super().__init__(start=BE54&native.MASK, native_functions=functions)
        self.entries = Counter()
        self.instructions = 0
        self.cpu.mem_write(program.symbols['g_CdInitialized']&native.MASK,struct.pack('<I',1))
        if body is not None:
            self.cpu.mem_write(BE54&native.MASK,body)
        if mutation is not None:
            address,old,new = mutation
            assert r(self.cpu.mem_read(address&native.MASK,4)) == old
            self.cpu.mem_write(address&native.MASK,struct.pack('<I',new))
        self.invoke(program.symbols['file_driver_set_class'],0x13)
        self.initialized_entries = dict(self.entries)
        self.entries.clear()

    def hook(self,cpu,address,size,unused):
        self.instructions += 1
        address &= native.MASK
        if address in self.native_entries:
            self.entries[self.native_entries[address]] += 1

    def invoke(self,address,*arguments):
        cpu = self.cpu
        cpu.mem_write(native.STACK-0x400,bytes([0xCD])*0x800)
        saved = [native.u32(0xAA000000+i*0x10301) for i in range(len(native.SAVED))]
        for register,value in zip(native.SAVED,saved):
            cpu.reg_write(register,value)
        for register,value in ((reg.UC_MIPS_REG_SP,native.STACK),(reg.UC_MIPS_REG_GP,0x8008A808),(reg.UC_MIPS_REG_RA,native.END)):
            cpu.reg_write(register,value)
        for i in range(4):
            cpu.reg_write(getattr(reg,'UC_MIPS_REG_A'+str(i)),arguments[i] if i<len(arguments) else 0)
        cpu.emu_start(address&native.MASK,native.END,count=3000000)
        assert cpu.reg_read(reg.UC_MIPS_REG_PC) == native.END, f'Incomplete native execution at {cpu.reg_read(reg.UC_MIPS_REG_PC):x}'
        assert cpu.reg_read(reg.UC_MIPS_REG_SP) == native.STACK
        assert cpu.reg_read(reg.UC_MIPS_REG_GP) == 0x8008A808
        assert cpu.reg_read(reg.UC_MIPS_REG_RA) == native.END
        assert [cpu.reg_read(register) for register in native.SAVED] == saved
        assert bytes(cpu.mem_read(native.STACK-0x400,0x200)) == bytes([0xCD])*0x200
        assert bytes(cpu.mem_read(native.STACK+0x20,0x3E0)) == bytes([0xCD])*0x3E0
        return cpu.reg_read(reg.UC_MIPS_REG_V0)

    def run(self,file):
        raw = Path(file['source']).read_bytes()
        assert hash_bytes(raw) == file['sha256']
        info = lbd_info(raw)
        assert json.loads(json.dumps(info)) == file['LBD_analysis']
        if len(raw) > 0x10000 or info['additional_tile_records'] > 10:
            raise ValueError('LBD input exceeds the bounded loader fixture: '+file['path'])
        if info['grid_dimensions'] != [20,20] or info['tmd_mapped_flag'] != 0:
            raise ValueError('Expected an unmapped 20 by 20 LBD input: '+file['path'])
        slot,stream,fo = bytearray([0xA1])*0x1C,bytearray([0xB2])*0x1C,bytearray([0xC3])*0x34
        refs = bytearray(COUNT*4)
        nodes,coords,states = bytearray([0xA4])*COUNT*64,bytearray([0xB5])*COUNT*80,bytearray([0xC6])*COUNT*32
        for offset,value in ((4,STREAM),(8,FILE),(0x10,ITEMS)):
            w(slot,offset,value)
        w(stream,0x10,DATA)
        for offset,value in ((0,FILE_VT),(0x2C,0)):
            w(fo,offset,value)
        for i in range(COUNT):
            w(refs,i*4,NODES+i*64)
            w(nodes,i*64+0x10,0x10203040+i)
            w(nodes,i*64+0x14,COORDS+i*80)
            w(nodes,i*64+0x20,0)
            w(coords,i*80+0x44,STATES+i*32)
        arena = Arena()
        initial = [slot,stream,fo,refs,nodes,coords,states,bytearray(raw)]
        bases = (SLOT,STREAM,FILE,ITEMS,NODES,COORDS,STATES,DATA)
        self.cpu.mem_write(MANAGER,bytes([0xE2])*0x1C)
        self.cpu.mem_write(POOL,bytes([0xD3])*(POOL_SIZE+16))
        self.cpu.mem_write(MANAGER,struct.pack('<II',POOL,POOL_SIZE))
        self.invoke(program.symbols['memory_set_manager'],MANAGER)
        self.invoke(program.symbols['memory_setup_manager'],MANAGER)
        assert bytes(self.cpu.mem_read(MANAGER,0x1C)) == bytes(arena.manager)
        assert bytes(self.cpu.mem_read(POOL,POOL_SIZE+16)) == bytes(arena.pool)
        for base,buffer in zip(bases,initial):
            self.cpu.mem_write(base-32,bytes([0xED])*32)
            self.cpu.mem_write(base,bytes(buffer))
            self.cpu.mem_write(base+len(buffer),bytes([0xFE])*32)
        expected = [bytearray(value) for value in initial]
        ef,en,ec,es,asset = expected[2],expected[4],expected[5],expected[6],expected[7]
        tmd_start = info['tmd_offset']
        count = info['tmd_objects']
        model = arena.allocate(0x30)
        parts = arena.allocate((count+1)*4)
        prims = [arena.allocate(36) for _ in range(count)]
        for offset,value in ((0,TMD_VT),(4,0),(8,0),(0xC,0),(0x10,DATA+tmd_start),(0x14,0),(0x20,0),(0x24,1),(0x28,0),(0x2C,parts)):
            w(arena.pool,model-POOL+offset,value)
        for i,prim in enumerate(prims):
            descriptor = DATA+tmd_start+12+i*28
            w(arena.pool,parts-POOL+i*4,prim)
            for offset,value in ((0,PRIM_VT),(4,0),(8,0),(0xC,descriptor-12),(0x10,descriptor)):
                w(arena.pool,prim-POOL+offset,value)
        w(arena.pool,parts-POOL+count*4,0)
        w(ef,0x10,DATA+info['grid_offset']); w(ef,0x14,0); w(ef,0x2C,model)
        w(asset,tmd_start+4,1)
        for i in range(count):
            for field in (0,8,16):
                offset = tmd_start+12+i*28+field
                w(asset,offset,r(asset,offset)+DATA+tmd_start+12)
        extra,linked,empty,walked = 400,0,0,0
        strides = {0x8001F030:24,0x8001F04C:28,0x8001F054:20,0x8001F05C:16,0x8001F064:32,0x8001F06C:44,0x8001F074:36}
        for cell in range(400):
            relative = 8+cell*12
            is_extra = False
            while relative:
                record = info['grid_offset']+relative
                tag,_,model_index,kind,heading,height,next_record = struct.unpack_from('<BBHBBhI',raw,record)
                if tag:
                    index = extra if is_extra else cell
                    if is_extra:
                        extra += 1
                    descriptor = DATA+tmd_start+12+model_index*28
                    w(en,index*64+0x20,prims[model_index]); w(en,index*64+0x18,descriptor)
                    descriptor_offset = descriptor-DATA
                    cursor = r(asset,descriptor_offset+16)-DATA
                    packets = r(asset,descriptor_offset+20)
                    group_start,previous,group_count = cursor,0,0
                    for packet in range(packets):
                        assert 0 <= cursor <= len(asset)-4
                        mode,flags = asset[cursor+3],asset[cursor+2]
                        if previous and previous != mode:
                            struct.pack_into('<H',asset,group_start,group_count&65535)
                            group_start,group_count = cursor,0
                        previous = mode
                        table_index = (mode&0xFD)-0x20
                        assert 0 <= table_index < 30
                        target = int.from_bytes(program.target(0x800102DC+table_index*4,4),'little')
                        stride = (24 if flags&4 else 16) if target == 0x8001F01C else (28 if flags&4 else 20) if target == 0x8001F038 else strides[target]
                        assert cursor+stride <= len(asset)
                        cursor += stride; group_count += 1
                    struct.pack_into('<H',asset,group_start,group_count&65535)
                    walked += packets
                    for field,value in ((0x18,(cell%20)*2048+1024),(0x1C,height*2048),(0x20,(cell//20)*2048+1024),(0,0)):
                        w(ec,index*80+field,value)
                    for field,value in ((0x10,0),(0x12,(heading<<10)&65535),(0x14,0)):
                        struct.pack_into('<H',es,index*32+field,value)
                    struct.pack_into('<H',en,index*64+0x36,kind)
                    linked += 1
                else:
                    index = cell
                    w(en,index*64+0x20,0); w(en,index*64+0x18,0)
                    empty += 1
                w(en,index*64+0x10,r(en,index*64+0x10)|0x80000000)
                w(en,index*64+0x38,NODES+extra*64 if next_record else 0)
                relative,is_extra = next_record,True
        self.cpu.mem_write(POOL-32,bytes([0xE7])*32)
        self.cpu.mem_write(MANAGER-32,bytes([0xE8])*32)
        self.cpu.mem_write(MANAGER+0x1C,bytes([0xE9])*32)
        previous_instructions = self.instructions
        self.invoke(BE54,0xABCD0000,SLOT)
        for base,buffer in zip(bases,expected):
            actual = bytes(self.cpu.mem_read(base,len(buffer)))
            if actual != bytes(buffer):
                diffs = [i for i,(a,b) in enumerate(zip(actual,buffer)) if a!=b]
                raise AssertionError(f'{file["path"]}: buffer {base:x} differs at {diffs[:20]}, actual={actual[diffs[0]:diffs[0]+8].hex()}, expected={buffer[diffs[0]:diffs[0]+8].hex()}')
            assert bytes(self.cpu.mem_read(base-32,32)) == bytes([0xED])*32
            assert bytes(self.cpu.mem_read(base+len(buffer),32)) == bytes([0xFE])*32
        for base,buffer in ((MANAGER,arena.manager),(POOL,arena.pool)):
            actual = bytes(self.cpu.mem_read(base,len(buffer)))
            if actual != bytes(buffer):
                diffs = [i for i,(a,b) in enumerate(zip(actual,buffer)) if a!=b]
                raise AssertionError(f'{file["path"]}: arena {base:x} differs at {diffs[:20]}, actual={actual[diffs[0]:diffs[0]+8].hex()}, expected={buffer[diffs[0]:diffs[0]+8].hex()}')
        assert bytes(self.cpu.mem_read(POOL-32,32)) == bytes([0xE7])*32
        assert bytes(self.cpu.mem_read(MANAGER-32,32)) == bytes([0xE8])*32
        assert bytes(self.cpu.mem_read(MANAGER+0x1C,32)) == bytes([0xE9])*32
        assert hash_bytes(Path(file['source']).read_bytes()) == file['sha256']

        # Exercise the native destructor and the already-mapped reload path.
        # Native free-list bookkeeping can alter uninitialized primitive fields;
        # check defined fields independently and compare the whole reloaded arena
        # between original and candidate executions in verify().
        self.invoke(BE54,0xABCD0000,SLOT)
        for base,buffer in zip(bases,expected):
            actual = bytes(self.cpu.mem_read(base,len(buffer)))
            if actual != bytes(buffer):
                raise AssertionError(file['path']+': buffer differs after native reload at '+hex(base))
            assert bytes(self.cpu.mem_read(base-32,32)) == bytes([0xED])*32
            assert bytes(self.cpu.mem_read(base+len(buffer),32)) == bytes([0xFE])*32
        assert bytes(self.cpu.mem_read(MANAGER,0x1C)) == bytes(arena.manager)
        reloaded_pool = bytes(self.cpu.mem_read(POOL,POOL_SIZE+16))
        defined_ranges = [(model-POOL+offset,4) for offset in (0,4,8,0xC,0x10,0x14,0x20,0x24,0x28,0x2C)]
        defined_ranges += [(parts-POOL,(count+1)*4)]
        defined_ranges += [(prim-POOL+offset,4) for prim in prims for offset in (0,4,8,0xC,0x10)]
        for offset,length in defined_ranges:
            assert reloaded_pool[offset:offset+length] == bytes(arena.pool[offset:offset+length])
        for offset in [0,52,52+max(12,((count+1)*4+3)&~3)+4]+[prim-POOL-4 for prim in prims]+[arena.cursor,POOL_SIZE]:
            assert reloaded_pool[offset:offset+4] == bytes(arena.pool[offset:offset+4])
        assert bytes(self.cpu.mem_read(POOL-32,32)) == bytes([0xE7])*32
        assert bytes(self.cpu.mem_read(MANAGER-32,32)) == bytes([0xE8])*32
        assert bytes(self.cpu.mem_read(MANAGER+0x1C,32)) == bytes([0xE9])*32
        assert hash_bytes(Path(file['source']).read_bytes()) == file['sha256']
        return {'path':file['path'],'sha256':file['sha256'],'linked_records':linked,'empty_records':empty,
                'allocated_extra_nodes':extra-400,'tmd_objects':count,'primitive_packets_walked':walked,
                'native_reload_checked':True,'reloaded_arena_sha256':hash_bytes(reloaded_pool),
                'native_instructions':self.instructions-previous_instructions}


def verify(inventory_path, destination, candidate_path=None):
    global program, reg, functions
    inventory = json.loads(inventory_path.read_text())
    files = [file for file in inventory['files'] if file.get('LBD_analysis')]
    if not files:
        raise ValueError('The inventory has no bounded LBD files.')
    program = native.load_program([])
    native.initialize_backend(program)
    reg = native.reg
    for table,offset,expected in ((FILE_VT,0x78,0x8002C278),(TMD_VT,0x80,0x80043B58),
                                 (program.symbols['D_800866E8'],0x104,BE54),
                                 (TMD_VT,4,program.symbols['file_buf_destroy'])):
        if int.from_bytes(program.target(table+offset,4),'little') != expected:
            raise ValueError('The original native virtual-table binding changed.')
    candidate = candidate_path.read_bytes() if candidate_path else None
    if candidate is not None and len(candidate) != 600:
        raise ValueError('The optional loader candidate must contain exactly 600 text bytes.')
    addresses = sorted({value for value in program.symbols.values() if 0x80010000 <= value < 0x80069000})
    ends = dict(zip(addresses,addresses[1:]))
    names = {}
    for name,address in program.symbols.items():
        if address in ends and not name.startswith(('D_','jtbl_','_')):
            names.setdefault(address,name)
    functions = [{'function':name,'address':hex(address),'bytes':ends[address]-address,
                  'sha256':hash_bytes(program.target(address,ends[address]-address))}
                 for address,name in names.items()]
    native.load_program(functions)
    dependencies = [Path(__file__),ROOT/'tools/verify_native_ai.py',ROOT/'tools/inventory_animations.py',
        ROOT/'tools/inventory_vtables.py',ROOT/'tools/progress.py',ROOT/'configure.py',
        ROOT/'requirements-analysis.txt',ROOT/native.configure.MAP_FILE,
        ROOT/native.configure.UNDEF_FUNCS,ROOT/native.configure.UNDEF_SYMS,
        ROOT/'src/file/file_object.c',ROOT/'src/file/file_object.h',
        ROOT/'src/file/tmd_model.c',ROOT/'src/file/tmd_model.h',ROOT/'src/file/tmd_prim.c',
        ROOT/'src/file/tmd_prim_geom.c',ROOT/'src/base/base.c',ROOT/'src/base/base.h',
        ROOT/'src/file/file_buf.c',ROOT/'src/file/cd_file_driver.c',ROOT/'src/scene/render_context.c',
        ROOT/'asm/nonmatchings/scene/render_context/func_8004BE54.s',
        ROOT/'asm/nonmatchings/psyq/gs/objt/GsLinkObject4.s',
        ROOT/'asm/nonmatchings/psyq/gs/GsMapModelingData/GsMapModelingData.s']
    before = {path:hash_bytes(path.read_bytes()) for path in dependencies}
    inventory_hash = hash_bytes(inventory_path.read_bytes())
    candidate_hash = hash_bytes(candidate) if candidate is not None else None
    began = time.monotonic()
    original_machine = Machine()
    candidate_machine = Machine(candidate) if candidate is not None else None
    observations = []
    for index,file in enumerate(files):
        original = original_machine.run(file)
        if candidate_machine:
            proposed = candidate_machine.run(file)
            if {key:value for key,value in original.items() if key!='native_instructions'} != {
                    key:value for key,value in proposed.items() if key!='native_instructions'}:
                raise ValueError('Original and candidate level outputs differ: '+file['path'])
            original['candidate_native_instructions'] = proposed['native_instructions']
        observations.append(original)
        if (index+1)%100 == 0:
            print(json.dumps({'levels_checked':index+1,'elapsed_seconds':time.monotonic()-began}),flush=True)
    controls = []
    for label,mutation,field in (
            ('missing_empty_flag',(0x8004BF40,0xAC620010,0),'empty_records'),
            ('missing_continuation_link',(0x8004C068,0xAC620038,0xAC600038),'allocated_extra_nodes'),
            ('missing_mapping_flag',(0x80020560,0xAC820000,0),None),
            ('missing_packet_group_count',(0x8001F09C,0xA6910000,0xA6800000),'primitive_packets_walked'),
            ('missing_old_model_destruction',(0x8004BE88,0x8E64002C,0x00002021),None)):
        eligible = next((index for index,observation in enumerate(observations) if field is None or observation[field]),None)
        if eligible is None:
            controls.append({'name':label,'status':'not_run_no_qualifying_fixture'})
            continue
        try:
            Machine(mutation=mutation).run(files[eligible])
        except AssertionError as error:
            if ': buffer ' not in str(error):
                raise ValueError('Control failed outside the output oracle: '+label) from error
            controls.append({'name':label,'address':hex(mutation[0]),'path':files[eligible]['path'],
                             'output_difference_detected':True,'scope':'Private Unicorn memory only.'})
        else:
            raise ValueError('Output negative control was not detected: '+label)
    if (hash_bytes(inventory_path.read_bytes()) != inventory_hash or
            any(hash_bytes(path.read_bytes()) != digest for path,digest in before.items()) or
            (candidate_path is not None and hash_bytes(candidate_path.read_bytes()) != candidate_hash) or
            (ROOT/native.configure.ROM).read_bytes() != program.ROM or
            (ROOT/native.configure.EXE).read_bytes() != program.ROM or
            native.check_build_current(ROOT) is not True):
        raise ValueError('Inputs, source or canonical build changed during verification.')
    total_fields = ['linked_records','empty_records','allocated_extra_nodes','tmd_objects',
                    'primitive_packets_walked','native_instructions']
    if candidate_machine:
        total_fields.append('candidate_native_instructions')
    executed = set(original_machine.entries)|set(original_machine.initialized_entries)
    report = {'schema_version':1,'created_utc':datetime.now(timezone.utc).isoformat(),
        'status':'passed_bounded_native_lbd_pipeline','canonical_executable_sha1':hashlib.sha1(program.ROM).hexdigest(),
        'original_and_current_build_equal':True,'original_behavior_modified':False,'model_api_calls':0,
        'input_inventory_sha256':inventory_hash,'levels_checked':len(observations),
        'loader_invocations_per_level_and_implementation':2,
        'original_loader_runs':len(observations)*2,
        'original_and_candidate_native_runs':len(observations)*(4 if candidate_machine else 2),
        'totals':{field:sum(observation[field] for observation in observations) for field in total_fields},
        'original_executed_native_entry_counts':dict(original_machine.entries),
        'dispatch_initialization_native_entry_counts':original_machine.initialized_entries,
        'native_function_ranges':[function for function in functions if function['function'] in executed],
        'dependency_stubs':0,'input_state_contracts':[{'global':'g_CdInitialized','value':1,
            'purpose':'CD hardware has completed initialization. Execute the native ready branch; cold CD initialization is outside scope.'}],
        'caller_fixture':'410 distinct nodes, coordinate and angle buffers; complete originals and guards checked.',
        'negative_controls':controls,'source_promotions':0,'whole_original_feature_groups_accepted':0,
        'backend':'Unicorn '+native.unicorn.__version__,'observations':observations,
        'producer_dependencies':[{'path':path.resolve().relative_to(ROOT).as_posix(),'sha256':digest}
                                 for path,digest in before.items()],
        'scope':'Local LBD tiles and TMD data through original loader, decoder, constructors, SDK map/link, '
                'allocator and virtual-table initialization. Independently compare complete guarded cold-load '
                'buffers and arena. Reload through native destruction and already-mapped TMD data; check complete '
                'caller buffers and defined heap fields, and compare full reload arenas if a candidate is supplied. '
                'Preinitialized CD state; no cold hardware, GPU drawing, caller node allocation/ownership, '
                'aliasing, PS1 bus/load-delay timing or whole-game acceptance.'}
    if candidate_machine:
        report['candidate_executed_native_entry_counts'] = dict(candidate_machine.entries)
        report['candidate'] = {'bytes':len(candidate),'sha256':candidate_hash,
            'byte_differences':sum(a!=b for a,b in zip(candidate,program.target(BE54,600))),
            'matching_c_accepted':False,'source_provenance':'Supplied private text bytes; full source/build comparison required separately.'}
    with destination.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2)
        stream.write('\n')
    print(json.dumps({'report':str(destination),'levels_checked':len(observations),
                      'loader_runs':report['original_and_candidate_native_runs'],
                      'negative_controls_detected':sum(control.get('output_difference_detected',False) for control in controls),
                      'dependency_stubs':0,'passed':True}))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory',type=Path,required=True,help='Local JSON produced by inventory_animations.py.')
    parser.add_argument('--candidate',type=Path,help='Optional private 600-byte loader text for a bounded comparison.')
    parser.add_argument('--output',type=Path,required=True,help='New report inside .decomp-lab.')
    args = parser.parse_args(argv)
    try:
        destination = args.output if args.output.is_absolute() else ROOT/args.output
        destination = destination.resolve()
        if not destination.is_relative_to((ROOT/'.decomp-lab').resolve()) or destination.exists():
            raise ValueError('Choose a new report path inside the private .decomp-lab directory.')
        destination.parent.mkdir(parents=True,exist_ok=True)
        verify(args.inventory,destination,args.candidate)
        return 0
    except (OSError,ValueError) as error:
        print('[!] '+str(error),file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
