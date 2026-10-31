"""Execute original mapping, linking and drawing on the complete local TMD corpus.

Original asset pools, indices and packet bytes stay intact. Two explicitly
supplied inspection cameras are not natural game scenes. Complete outputs,
GTE state/counters, native dispatch counts, ABI and immutable VM are compared.
Unsupported original dispatch formats retain their real early-return behavior.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import lzma
from pathlib import Path,PurePosixPath
import struct
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.disc_files import Mode2Disc
from tools.gte_state_bridge import NativeStateBridge
from tools.gte_state_model import require,unsigned
from tools.inventory_model_packets import file_sha
from tools.psx_image import EXECUTABLE_NAME,ORIGINAL_SHA1,executable_offset
from tools.tmd_corpus_model import camera_for,raw_specs
from tools.tmd_packets import geometries,model_ranges
from tools.tmd_renderer_model import BUFFER,MODEL,OBJECT,case_fixture,packet_specs
from tools.tmd_sdk_model import map_tmd,link_tmd
from tools.verify_model_packets import backend_identity,write_json
from tools.verify_tmd_renderer import DrawMachine,MASK,START,END,projection
from tools.verify_tmd_sdk import FUNCTIONS,JUMP_TABLE,JUMP_BYTES

CORPUS_FAULTS=(
    dict(name='unsupported-mode-routed-to-unlit-shader',address=0x80018804,
        original=0x34023101,replacement=0x34023000,case=dict(mode=0x30,flags=0)),
    dict(name='normal-pool-replaced-with-vertex-pool',address=0x800188BC,
        original=0x8E430010,replacement=0x8E43000C,case=dict(mode=0x20,flags=0)),
)


class CorpusMachine(DrawMachine):
    """Compose the actual SDK producer calls before each guarded draw."""
    def __init__(self,executable,bridge,fault=None):
        super().__init__(executable,bridge,fault)
        for function in FUNCTIONS.values():
            at=executable_offset(executable,function['address'],function['bytes'])
            require(hashlib.sha256(executable[at:at+function['bytes']]).hexdigest()==function['sha256'],
                'Original SDK preparation function differs.')
        self.jump_sha256=projection.sha(bytes(self.cpu.mem_read(JUMP_TABLE,JUMP_BYTES)))

    def prepare_fixture(self,case,initial):
        if 'raw_tmd' not in case:return super().prepare_fixture(case,initial)
        raw,alias=case['raw_tmd'],case.get('alias',0)
        source=bytearray(initial)
        source[MODEL-BUFFER:MODEL-BUFFER+len(raw)]=raw
        struct.pack_into('<I',source,OBJECT-BUFFER+8,0)
        self.cpu.mem_write(BUFFER,bytes(source))
        self.cpu.mem_write(projection.STACK-0x800,bytes([0xC9])*4096)
        old_read,old_write,old_lower,old_upper=self.read_ranges,self.write_ranges,self.lower,self.upper
        self.read_ranges=[(BUFFER,BUFFER+len(initial)),(projection.STACK-56,projection.STACK),
            (JUMP_TABLE,JUMP_TABLE+JUMP_BYTES)]
        self.write_ranges=[(BUFFER,BUFFER+len(initial)),(projection.STACK-56,projection.STACK)]
        immutable=self.immutable_hash()
        self.command_words=[]
        steps=self.steps
        mapped=map_tmd(raw,MODEL|alias)
        mapped_buffer=bytearray(source)
        mapped_buffer[MODEL-BUFFER:MODEL-BUFFER+len(mapped)]=mapped
        try:
            for operation,args,wanted in (
                    ('map',(MODEL+4|alias,0xDEAD0020,0xDEAD0030,0xDEAD0040),bytes(mapped_buffer)),
                    ('link',(MODEL+12|alias,OBJECT|alias,case['geometry_index'],0xDEAD0040),initial)):
                function=FUNCTIONS[operation]
                self.lower=function['address']&MASK
                self.upper=self.lower+function['bytes']
                values=[0xA7000000+i*0x10301 for i in range(len(self.saved))]
                for register,value in zip(self.saved,values):self.cpu.reg_write(register,value)
                for i,value in enumerate(args):self.cpu.reg_write(getattr(self.r,'UC_MIPS_REG_A'+str(i)),value)
                for register,value in ((self.r.UC_MIPS_REG_SP,projection.STACK|alias),
                        (self.r.UC_MIPS_REG_GP,0x8008A808),(self.r.UC_MIPS_REG_RA,projection.STOP|alias)):
                    self.cpu.reg_write(register,value)
                self.cpu.emu_start(function['address'],projection.STOP|alias,count=1000000)
                self.restore_temp()
                require(self.cpu.reg_read(self.r.UC_MIPS_REG_PC)==projection.STOP|alias and
                    self.cpu.reg_read(self.r.UC_MIPS_REG_SP)==projection.STACK|alias and
                    self.cpu.reg_read(self.r.UC_MIPS_REG_GP)==0x8008A808 and
                    self.cpu.reg_read(self.r.UC_MIPS_REG_RA)==projection.STOP|alias and
                    [self.cpu.reg_read(r) for r in self.saved]==values,'Original SDK preparation ABI differs.')
                require(self.immutable_hash()==immutable,'Original SDK preparation changed immutable VM.')
                require(bytes(self.cpu.mem_read(BUFFER,len(initial)))==wanted,
                    'Original SDK preparation differs from complete scalar input: '+operation)
                require(not self.command_words,'SDK preparation unexpectedly used GTE commands.')
        finally:self.read_ranges,self.write_ranges,self.lower,self.upper=old_read,old_write,old_lower,old_upper
        return dict(native_mapper_calls=1,native_linker_calls=1,original_instructions=self.steps-steps,
            complete_prepared_buffer_sha256=projection.sha(initial),full_input_ABI_and_immutable_VM_equal=True)


def early_return_checks(executable,bridge):
    machine=CorpusMachine(executable,bridge)
    calls=0
    for mode in (0x30,0x34,0x38,0x3C):
        for semi in (0,2):
            for alias in (0,0x80000000):
                for prefix in ([],[dict(mode=0x21,flags=1)]):
                    case=dict(packets=[*prefix,dict(mode=mode|semi,flags=0),dict(mode=0x21,flags=1)],alias=alias)
                    result=machine.draw(case)
                    require(result['outcome']=='unsupported_mode_return','Original unsupported-run return differs.')
                    calls+=1
    controls=[]
    for fault in CORPUS_FAULTS:
        control=CorpusMachine(executable,bridge,fault)
        result=control.draw(fault['case'],allow_mismatch=True)
        require(not result['equal'] and control.fault_hits>0,'Original corpus control was not detected.')
        controls.append(dict(name=fault['name'],instruction_executions=control.fault_hits,detected=True,
            clean_original_return=True,saved_ABI_and_immutable_VM_preserved=True,
            differences=result['differences'],GTE_state_equal=result['GTE_state_equal'],
            native_counters_equal=result['native_counters_equal'],
            mode_and_primitive_counts_equal=result['mode_runs_and_primitive_calls_equal']))
    return dict(constructed_unsupported_run_calls=calls,original_code_controls=controls)


def verify(disc_path,inventory_path,bridge_path,runtime,destination):
    require(not destination.exists() and destination.parent.is_dir(),'Choose a fresh existing-parent output.')
    inventory=json.loads(inventory_path.read_bytes())
    require(inventory.get('status')=='model_vertex_references_verified' and inventory.get('unresolved')==[],
        'Use the complete existing static model inventory.')
    for name,digest in inventory['source_dependencies'].items():
        path=(ROOT/name.replace('\\','/')).resolve()
        require(path.is_relative_to(ROOT) and file_sha(path)==digest,'Static source pin differs: '+name)
    names=('tools/verify_tmd_corpus.py','tools/tmd_corpus_model.py','tools/verify_tmd_renderer.py',
        'tools/tmd_renderer_model.py','tools/tmd_recursive_model.py','tools/verify_tmd_projection.py',
        'tools/tmd_sdk_model.py','tools/verify_tmd_sdk.py','tools/gte_state_model.py','tools/gte_state_bridge.py',
        'tools/nymashock_gte_state_bridge.cs','tools/tmd_packets.py','tools/verify_gte_state.py',
        'tools/verify_model_packets.py','tools/inventory_model_packets.py','tools/disc_files.py',
        'tools/inventory_animations.py','tools/psx_image.py','research/original-functions.json')
    sources={name:file_sha(ROOT/name) for name in names}
    destination.mkdir()
    started=time.monotonic()
    bridge=NativeStateBridge(bridge_path,runtime,destination/'native-errors.log')
    totals,outcomes,formats=Counter(),Counter(),Counter()
    aborts=[]
    decoded_hash=hashlib.sha256()
    decoded_bytes=0
    journal=destination/'files.jsonl.xz'
    try:
        with Mode2Disc(disc_path) as disc:
            before=disc.path.stat()
            require(file_sha(disc.path)==inventory['raw_disc_sha256'],'Original disc hash differs.')
            files=disc.files()
            selected={name:record for name,record in files.items()
                if PurePosixPath(name).suffix in ('.LBD','.MOM','.TMD')}
            require(set(selected)=={row['path'] for row in inventory['rows']},'Original model file set differs.')
            executable=disc.read_file(files['/'+EXECUTABLE_NAME])
            require(hashlib.sha1(executable).hexdigest()==ORIGINAL_SHA1,'Canonical executable differs.')
            synthetic=early_return_checks(executable,bridge)
            machine=CorpusMachine(executable,bridge)
            with lzma.open(journal,'xb',preset=6) as stream:
                for ordinal,row in enumerate(inventory['rows'],1):
                    require(time.monotonic()-started<3600,'Original corpus profile exceeded one hour.')
                    raw=disc.read_file(selected[row['path']])
                    require(len(raw)==row['bytes'] and projection.sha(raw)==row['sha256'],'Original model bytes differ.')
                    counts,call_hash=Counter(),hashlib.sha256()
                    ranges=model_ranges(raw,PurePosixPath(row['path']).suffix)
                    require(len(ranges)==len(row['models']),'Original TMD table set differs.')
                    for model,static in zip(ranges,row['models']):
                        require(all(model[key]==static[key] for key in model),'Original TMD bounds differ.')
                        tmd=raw[model['tmd']:model['limit']]
                        geometry_rows=geometries(tmd)
                        require(len(geometry_rows)==static['counts']['objects'],'Original descriptor count differs.')
                        for geometry in geometry_rows:
                            base=dict(raw_tmd=tmd,geometry_index=geometry.index,ordering_head=0x00FFFFFF,
                                attributes=0x200,source_path=row['path'],source_tmd=model['tmd'])
                            specs=raw_specs(base)
                            for spec in specs:formats[f"0x{spec['mode']:02x}/0x{spec['flags']:02x}"]+=1
                            counts.update(objects=1,source_packets=len(specs))
                            for view in (0,1):
                                case={**base,**camera_for(tmd,geometry,bool(view)),
                                    'alias':0x80000000 if view else 0,'view':view}
                                result=machine.draw(case,allow_mismatch=True)
                                if not result['equal']:
                                    write_json(destination/'failure.json',dict(path=row['path'],tmd=model['tmd'],
                                        object=geometry.index,view=view,result=result))
                                    raise ValueError('Original model draw differs: '+row['path']+' object '+str(geometry.index))
                                stats=result['draw_stats']
                                prep=result['input_preparation']
                                counts.update(draw_calls=1,mode_runs=stats['mode_runs'],primitive_calls=stats['primitive_calls'],
                                    drawer_instructions=result['instructions'],SDK_instructions=prep['original_instructions'],
                                    native_commands=result['native_commands'],native_mapper_calls=1,native_linker_calls=1,
                                    unvisited_supplied_packets=len(specs)-stats['primitive_calls'])
                                outcomes.update(stats['outcomes'])
                                if stats['unsupported_run_returns']:
                                    stopped=specs[stats['primitive_calls']]
                                    counts['unsupported_run_returns']+=1
                                    aborts.append(dict(path=row['path'],tmd=model['tmd'],object=geometry.index,view=view,
                                        stopped_mode=hex(stopped['mode']),stopped_flags=stopped['flags'],
                                        primitive_calls=stats['primitive_calls'],supplied_packets=len(specs)))
                                require(not stats['recursive_roots'],'Inspection fit unexpectedly entered subdivision.')
                                call_hash.update((json.dumps(result,sort_keys=True,separators=(',',':'))+'\n').encode())
                        counts['TMD_tables']+=1
                    evidence=dict(path=row['path'],source_sha256=row['sha256'],counts=dict(counts),
                        complete_call_comparison_stream_sha256=call_hash.hexdigest(),
                        both_views_full_outputs_GTE_dispatch_ABI_and_immutable_VM_equal=True)
                    encoded=(json.dumps(evidence,separators=(',',':'))+'\n').encode()
                    decoded_bytes+=len(encoded)
                    require(decoded_bytes<1024**2,'Decoded per-file journal exceeds 1 MiB.')
                    decoded_hash.update(encoded)
                    stream.write(encoded)
                    totals.update(counts)
                    require(journal.stat().st_size<1024**2,'Compressed per-file journal exceeds 1 MiB.')
                    print(json.dumps(dict(completed_files=ordinal,total_files=len(inventory['rows']),
                        draw_calls=totals['draw_calls'],source_packets=totals['source_packets'])),flush=True)
            for key,expected in (('objects',13627),('TMD_tables',531),('source_packets',119458),('draw_calls',27254)):
                require(totals[key]==expected,'Complete corpus count differs: '+key)
            after=disc.path.stat()
            require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
                (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) and
                file_sha(disc.path)==inventory['raw_disc_sha256'],'Original disc changed during the profile.')
    finally:bridge.close()
    require(sources=={name:file_sha(ROOT/name) for name in names},'Executed corpus sources changed.')
    report=dict(schema_version=1,status='original_TMD_corpus_draw_calls_match',
        generated_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-started,
        raw_disc_sha256=inventory['raw_disc_sha256'],inventory_sha256=file_sha(inventory_path),
        original_executable_sha1=ORIGINAL_SHA1,backend=backend_identity(),source_sha256=sources,
        compiled_bridge_sha256=file_sha(bridge_path),model_files=len(inventory['rows']),totals=dict(totals),
        primitive_outcomes=dict(outcomes),source_formats=dict(formats),original_unsupported_run_returns=aborts,
        synthetic=synthetic,
        native_preparation_functions=FUNCTIONS,linker_jump_table_sha256=machine.jump_sha256,
        journal=dict(file=journal.name,bytes=journal.stat().st_size,sha256=file_sha(journal),
            decoded_bytes=decoded_bytes,decoded_sha256=decoded_hash.hexdigest()),
        complete_prepared_input_and_draw_output_buffers_compared=True,all_64_GTE_words_commands_and_native_counters_compared=True,
        original_mapper_linker_and_drawer_executed_without_output_stubs=True,
        saved_ABI_and_full_VM_outside_declared_mutable_spans_compared=True,
        raw_original_pools_indices_and_packet_payloads_preserved=True,only_original_SDK_mapping_and_link_headers_mutated=True,
        camera_policy='two fitted opposite oblique views, scaled integer rotation, supplied translation and H=512',
        camera_is_recovered_game_state=False,lit_Gouraud_formats_preserve_original_drawer_early_return=True,
        other_in_game_draw_routes_for_those_formats_verified=False,natural_scenes_GPU_pixels_and_hardware_timing_verified=False,
        corpus_subdivision_paths_verified=False,stack_temporary_bytes_independently_predicted=False,
        no_asset_payloads_written=True,original_assets_player_and_year_replay_unchanged=True,
        new_matching_C_bytes=0,new_gameplay_features=0,whole_feature_groups_accepted=0,whole_NPC_encounters_accepted=0)
    write_json(destination/'comparison.json',report)
    require(sum(path.stat().st_size for path in destination.iterdir())<2*1024**2,'Corpus outputs exceed 2 MiB.')
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disc',type=Path,required=True)
    parser.add_argument('--inventory',type=Path,required=True)
    parser.add_argument('--bridge',type=Path,required=True)
    parser.add_argument('--runtime',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        result=verify(args.disc,args.inventory,args.bridge,args.runtime,args.output)
        print(json.dumps({key:result[key] for key in ('status','model_files','totals','primitive_outcomes')}))
        return 0
    except (OSError,ValueError,KeyError) as error:
        print(json.dumps(dict(status='invalid_original_TMD_draw_profile',error=str(error))),file=sys.stderr)
        return 2


if __name__=='__main__':raise SystemExit(main())
