"""Inspect the whole save block in one retained natural MainRAM checkpoint.

Matching reset-written fields is state evidence, not proof that a reset event
occurred. Object identity here is structural; allocation lifetime, natural reset
entry/return boundaries and controller reachability need separate evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import new_game_state as model
from tools.inspect_runtime_menu import read_blob
from tools.verify_new_game_reset import CANONICAL, TABLE, NAV_GLOBAL, COUNT_GLOBAL, MAGIC_GLOBAL, FUNCTIONS

sha=lambda raw:hashlib.sha256(raw).hexdigest()
require=model.require


def physical(pointer,size):
    require(type(pointer) is int and 0<=pointer<=0xFFFFFFFF and pointer&0xE0000000 in (0,0x80000000,0xA0000000),
            'Unsupported PS1 RAM pointer alias.')
    offset=pointer&0x1FFFFFFF
    require(0<=offset and offset+size<=0x200000,'Save context is outside complete MainRAM.')
    return offset


def inspect(raw):
    require(isinstance(raw,(bytes,bytearray)) and len(raw)==0x200000,'Use a complete unmasked MainRAM checkpoint.')
    flags=model.word(raw,NAV_GLOBAL);count=model.word(raw,COUNT_GLOBAL)
    base=dict(schema_version=1,mainram_sha256=sha(raw),navigation_pointer=hex(flags),dynamic_count_pointer=hex(count),
        reset_event_proved=False,object_allocation_lifetime_proved=False,new_C_bytes=0,model_API_calls=0)
    if flags==0 and count==0:
        return dict(base,status='no_bound_navigation_context',object_available=False)
    require(flags!=0 and count!=0 and flags>=model.NAV_FLAGS,'Incomplete navigation-context binding.')
    root=flags-model.NAV_FLAGS
    offset=physical(root,model.OBJECT_BYTES)
    require(count==root+model.DYNAMIC_LINK_COUNT,'Navigation globals do not describe the same dream system.')
    data=bytes(raw[offset:offset+model.OBJECT_BYTES])
    require(model.word(data,0)==TABLE,'Navigation globals do not point to a dream-system table.')
    marker=model.word(raw,MAGIC_GLOBAL)
    expected=model.reset(data,marker)
    written=model.reset_write_offsets()
    different=[n for n in sorted(written) if data[n]!=expected[n]]
    save=data[model.SAVE_OFFSET:model.SAVE_OFFSET+model.SAVE_BYTES]
    preserved=bytes(data[n] for n in range(model.SAVE_OFFSET,model.SAVE_OFFSET+model.SAVE_BYTES) if n not in written)
    return dict(base,status='inspected_structurally_bound_save_block',object_available=True,
        receiver=hex(root),object_sha256=sha(data),save_block_sha256=sha(save),save_block_bytes=len(save),
        original_marker=hex(marker),stored_marker=hex(model.word(data,model.SAVE_OFFSET)),
        year=model.word(data,0x17C),zero_based_day=model.word(data,0x180),
        new_game_flag=model.word(data,model.IS_NEW_GAME),flashback_session=model.word(data,model.IS_FLASHBACK),
        flashback_count=model.word(data,0x46C),dynamic_links=model.word(data,model.DYNAMIC_LINK_COUNT),
        screen_shake=model.word(data,0x678),
        matches_reset_written_fields=not different,reset_written_field_differences=different,
        reset_write_footprint_bytes=len(written),preserved_save_block_bytes=len(preserved),
        preserved_bytes_sha256=sha(preserved),preserved_nonzero_bytes=sum(n!=0 for n in preserved),
        mood_history_nonzero_bytes=sum(n!=0 for n in data[0x190:0x46A]),
        flashback_record_nonzero_bytes=sum(n!=0 for n in data[0x470:0x5D8]),
        source_scope='Structural snapshot of one complete object/save block. A field pattern does not establish reset execution, object lifetime, rendering/audio/card parity or a natural reset ending.')


def replay_object(data,executable,rebuilt,functions,segment):
    """Relocate a retained object into an isolated VM fixture, never a live core."""
    require(isinstance(data,bytes) and len(data)==model.OBJECT_BYTES and model.word(data,0)==TABLE,
            'Use one complete retained dream-system object with its original table.')
    require(model.word(data,model.IS_FLASHBACK) in (0,1) and model.word(data,model.STORED_DAY)<=364,
            'The retained-context extension requires an ordinary initialized day/flashback state.')
    require(segment in (0,0x80000000,0xA0000000),'Use the retained receiver RAM alias.')
    require(sha(executable)==sha(rebuilt)==CANONICAL,'Both supplied complete executables must be canonical.')
    from tools.verify_card_heap import backend_identity
    from tools.verify_new_game_reset import Machine,OBJECT
    backend=backend_identity()
    marker=struct.unpack_from('<I',executable,0x800+MAGIC_GLOBAL-0x10000)[0]
    results=[]
    for kind in ('reset','end_mode_two'):
        # The ordinary profile initializes a fresh ABI/auxiliary context first;
        # the complete retained object then replaces that synthetic object.
        case=dict(kind='reset',segment=segment,pattern=0) if kind=='reset' else \
             dict(kind='end',segment=segment,pattern=0,mode=2,flashback=0,stored_day=0)
        expected=model.reset(data,marker) if kind=='reset' else model.end_day(data,2,marker)[0]
        outcomes=[]
        for image in (executable,rebuilt):
            machine=Machine(image,functions,case,marker)
            try:
                machine.f['object']=data;machine.f['expected_object']=expected
                if kind!='reset':machine.f['returned']=model.word(data,model.IS_FLASHBACK)
                machine.cpu.mem_write(OBJECT,data)
                outcomes.append(machine.run())
            finally:machine.close()
        require(outcomes[0]==outcomes[1],'Original/rebuilt retained-object reset outcomes differ.')
        results.append(dict(kind=kind,original_and_rebuilt=outcomes[0],
            retained_object_input_sha256=sha(data),expected_complete_object_sha256=sha(expected)))
    return dict(analysis_VM_relocated_object=True,original_object_pointers_preserved_as_opaque_bytes=True,
        live_emulator_RAM_modified=False,natural_reset_event_proved=False,
        original_and_rebuilt_executions=4,results=results,
        backend={key:backend[key] for key in ('package_version','loaded_library_sha256','binding_entry_sha256')},
        scope='Original reset and end-mode-two bodies act on a copy of the complete retained object in an isolated fixture. This is not a restored emulator state or a naturally reached reset event.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ram',required=True,type=Path);parser.add_argument('--ram-member')
    parser.add_argument('--ram-sha256',required=True);parser.add_argument('--exe',required=True,type=Path)
    parser.add_argument('--functions',required=True,type=Path,help='Qualified original complete-function records.')
    parser.add_argument('--native-replay',action='store_true',help='Replay this copied object in the isolated native VM; not a natural emulator event.')
    parser.add_argument('--rebuilt-exe',type=Path,help='Required with --native-replay; separate current rebuilt executable.')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    try:
        require(not args.output.exists(),'Choose a new output path; preserve existing evidence.')
        raw=read_blob(args.ram,0x200000,args.ram_member)
        require(sha(raw)==args.ram_sha256,'Retained MainRAM does not match its checkpoint hash.')
        executable=args.exe.read_bytes();require(sha(executable)==CANONICAL,'Use the canonical executable.')
        rows=json.loads(args.functions.read_bytes());load=struct.unpack_from('<I',executable,0x18)[0]
        require(isinstance(rows,list) and len(rows)==len(FUNCTIONS)
                and {row['function'] for row in rows}==set(FUNCTIONS),'Use all eight unique qualified function records.')
        for row in rows:
            address=int(row['address'],16);size=row['bytes'];at=0x800+address-load
            require(type(size) is int and size>0 and size%4==0 and at>=0x800 and at+size<=len(executable),'Invalid complete function range.')
            body=executable[at:at+size]
            require(sha(body)==row['sha256'] and raw[physical(address,size):physical(address,size)+size]==body,
                    'A retained original function body differs: '+row['function'])
        report=inspect(raw)
        if args.native_replay:
            require(report['object_available'] and args.rebuilt_exe is not None,
                    'Native replay needs a bound object and an explicit rebuilt executable.')
            offset=physical(int(report['receiver'],16),model.OBJECT_BYTES)
            report['retained_object_native_replay']=replay_object(raw[offset:offset+model.OBJECT_BYTES],
                executable,args.rebuilt_exe.read_bytes(),rows,int(report['receiver'],16)&0xE0000000)
        else:
            require(args.rebuilt_exe is None,'Use --native-replay with --rebuilt-exe.')
        report.update(canonical_executable_sha256=CANONICAL,complete_original_functions_in_RAM_checked=len(rows),
            producer_sha256=sha(Path(__file__).read_bytes()),model_sha256=sha((ROOT/'tools/new_game_state.py').read_bytes()),
            function_records_sha256=sha(args.functions.read_bytes()),new_emulator_recording=False,
            expanded_RAM_file_written=False)
        with args.output.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
        print(json.dumps({key:report[key] for key in ('status','object_available','reset_event_proved')}))
        return 0
    except (OSError,ValueError,KeyError,struct.error) as error:print(str(error),file=sys.stderr);return 2


if __name__=='__main__':sys.exit(main())
