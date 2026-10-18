"""Qualify original SDK boundary ranges for optional completed-read observation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import configure
from research.compiler.compare_function import CANONICAL_SHA256,elf_function
from tools.decomp_workbench import diagnostic_image
from tools.progress import build_manifest,check_build_current
from tools.replay_cold_start_headless import require,write_json

RANGES=ROOT/'research/sdk_reads/sdk-function-ranges.json'
HEAP_RANGES=ROOT/'research/sdk_reads/heap-function-ranges.json'
RECOVERY_RANGES=ROOT/'research/sdk_reads/recovery-function-ranges.json'
TARGETS=(('func_80029274',0x80029274,128,1),('CdReadSync',0x80029254,32,2),
         ('CdControl',0x80028DF0,328,3),('CdControlF',0x80028F38,316,3),
         ('CdControlB',0x80029074,340,3),('CdSync',0x80028D68,32,4))
HEAP_TARGETS=(('memory_allocate_mem',0x80017B34,456,5),('memory_free_mem',0x80017CFC,428,6),
              ('file_buf_construct',0x80026A50,100,7),('file_buf_destroy',0x800269F0,96,8),
              ('file_buf_release',0x80026C20,96,9),('file_buf_cleanup',0x80026AB4,84,10))
RECOVERY_TARGETS=(('CdFlush',0x80028CC0,32,11),('cd_file_driver_end_read',0x80028864,36,12),
                  ('cd_file_driver_set_read_result',0x80028888,16,13))
DRIVER_GLOBALS=(('g_CdReadBusy',0x8008A864),('g_CdReadParam',0x8008A874),
                ('g_CdReadState',0x8008A878),('g_CdReadPhase',0x8008A898),
                ('g_CdReadIdle',0x8008A870),('g_CdTimeoutCounter',0x8008A8A0),
                ('g_CdReadPos',0x8008A87C),('g_CdReadDest',0x8008A880),
                ('g_CdReadLba',0x8008A884),('g_CdRequestList',0x8008A894))
sha=lambda data:hashlib.sha256(data).hexdigest()

def export_ranges(output,*,heap_lifetime=False,cd_recovery=False):
    heap_lifetime=heap_lifetime or cd_recovery
    output=Path(output).resolve()
    require(output.is_relative_to(ROOT/'.decomp-lab') and not output.exists(),
            'Choose a fresh private SDK range diagnostic directory.')
    require(check_build_current(ROOT) is True,'Require the current canonical build.')
    original=(ROOT/configure.ROM).read_bytes()
    require(sha(original)==CANONICAL_SHA256 and original==(ROOT/configure.EXE).read_bytes(),
            'Require the complete canonical executable.')
    output.mkdir()
    objects=[Path(configure.BUILD_DIR)/(source+'.o') for source,_ in build_manifest()]
    with (output/'link.log').open('xb') as log:
        elf,diagnostic=diagnostic_image(output,Path(configure.LD_SCRIPT),objects,ROOT/configure.EXE,log)
    gnu=subprocess.check_output([configure.CROSS+'nm','-S','--defined-only',str(elf)])
    (output/'gnu-symbols.txt').write_bytes(gnu)
    symbols={words[3]:(int(words[0],16),int(words[1],16)) for line in gnu.decode().splitlines()
             if len(words:=line.split())==4 and words[2] in ('T','t')}
    rows=[]
    for name,pc,length,kind in TARGETS+(HEAP_TARGETS if heap_lifetime else ())+(RECOVERY_TARGETS if cd_recovery else ()):
        code,_=elf_function(elf.read_bytes(),name,pc)
        offset=pc-0x80010000+0x800
        require(symbols.get(name)==(pc,length) and len(code)==length and code==original[offset:offset+length],
                'Complete SDK ELF/GNU range qualification failed: '+name)
        rows.append(dict(function=name,pc=hex(pc),bytes=length,kind=kind,sha256=sha(code)))
    report=dict(schema_version=1,kind='original_LSD_CD_recovery_boundaries' if cd_recovery else
                'original_LSD_SDK_heap_boundaries' if heap_lifetime else 'original_LSD_SDK_read_boundaries',
        canonical_executable_sha256=CANONICAL_SHA256,rows=rows,
        object_count=len(objects),canonical_symbolic_elf_sha256=sha(elf.read_bytes()),
        GNU_symbol_table_sha256=sha(gnu),independent_GNU_sized_function_extents_equal=True,
        complete_canonical_image_equal=True,diagnostic=diagnostic,
        producer_sha256=sha(Path(__file__).read_bytes()))
    if cd_recovery:
        globals_=[]
        for name,address in DRIVER_GLOBALS:
            require(symbols.get(name)==(address,4),'Complete driver global ELF/GNU extent changed: '+name)
            offset=address-0x80010000+0x800
            require(0<=offset<=len(original)-4,'Driver word lies outside the complete canonical image.')
            globals_.append(dict(symbol=name,address=hex(address),bytes=4,initial_word_sha256=sha(original[offset:offset+4])))
        report['driver_globals']=globals_
    write_json(output/'function-ranges.json',report)
    return report

def verified_sdk_selection(program,executable,manifest):
    enabled=program['method_trace'].get('sdk_reads',False)
    require(type(enabled) is bool,'SDK read observation must be a boolean selection.')
    heap=program['method_trace'].get('heap_lifetime',False)
    require(type(heap) is bool and (not heap or enabled),'Heap lifetime observation requires SDK read selection.')
    recovery=program['method_trace'].get('cd_recovery',False)
    require(type(recovery) is bool and (not recovery or heap),'CD recovery observation requires heap/SDK selection.')
    if not enabled:return None
    require(program['method_trace'].get('return_trace') is not None,
            'SDK reads require the original return/caller-flow observer.')
    require(sha(executable)==CANONICAL_SHA256 and manifest.get('schema_version')==1
            and manifest.get('kind')==('original_LSD_CD_recovery_boundaries' if recovery else
                'original_LSD_SDK_heap_boundaries' if heap else 'original_LSD_SDK_read_boundaries')
            and manifest.get('canonical_executable_sha256')==CANONICAL_SHA256
            and manifest.get('object_count')==306 and manifest.get('complete_canonical_image_equal') is True
            and manifest.get('independent_GNU_sized_function_extents_equal') is True,
            'Require complete canonical SDK function-range qualification.')
    rows=manifest.get('rows',[])
    targets=TARGETS+(HEAP_TARGETS if heap else ())+(RECOVERY_TARGETS if recovery else ())
    require(len(rows)==len(targets),'Incomplete SDK boundary selection.')
    selected=[]
    for row,(name,pc,length,kind) in zip(rows,targets):
        offset=pc-0x80010000+0x800
        require((row.get('function'),row.get('pc'),row.get('bytes'),row.get('kind'))==(name,hex(pc),length,kind)
                and sha(executable[offset:offset+length])==row.get('sha256'),
                'SDK boundary identity or complete range changed: '+name)
        selected.append(dict(pc=pc,bytes=length,kind=kind))
    if recovery:
        expected=[]
        for name,address in DRIVER_GLOBALS:
            offset=address-0x80010000+0x800
            expected.append(dict(symbol=name,address=hex(address),bytes=4,initial_word_sha256=sha(executable[offset:offset+4])))
        require(manifest.get('driver_globals')==expected,'Original driver global word selection changed.')
    return selected

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export-ranges',type=Path,required=True)
    parser.add_argument('--heap-lifetime',action='store_true')
    parser.add_argument('--cd-recovery',action='store_true')
    args=parser.parse_args(argv)
    try:
        report=export_ranges(args.export_ranges,heap_lifetime=args.heap_lifetime,cd_recovery=args.cd_recovery)
        print(json.dumps(dict(status='qualified_original_SDK_ranges',functions=len(report['rows']),
                              complete_canonical_image_equal=True)))
        return 0
    except (OSError,ValueError,subprocess.CalledProcessError) as error:
        print(str(error),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
