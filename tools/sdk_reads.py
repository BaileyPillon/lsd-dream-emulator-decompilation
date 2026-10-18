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
TARGETS=(('func_80029274',0x80029274,128,1),('CdReadSync',0x80029254,32,2),
         ('CdControl',0x80028DF0,328,3),('CdControlF',0x80028F38,316,3),
         ('CdControlB',0x80029074,340,3),('CdSync',0x80028D68,32,4))
sha=lambda data:hashlib.sha256(data).hexdigest()

def export_ranges(output):
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
    for name,pc,length,kind in TARGETS:
        code,_=elf_function(elf.read_bytes(),name,pc)
        offset=pc-0x80010000+0x800
        require(symbols.get(name)==(pc,length) and len(code)==length and code==original[offset:offset+length],
                'Complete SDK ELF/GNU range qualification failed: '+name)
        rows.append(dict(function=name,pc=hex(pc),bytes=length,kind=kind,sha256=sha(code)))
    report=dict(schema_version=1,kind='original_LSD_SDK_read_boundaries',
        canonical_executable_sha256=CANONICAL_SHA256,rows=rows,
        object_count=len(objects),canonical_symbolic_elf_sha256=sha(elf.read_bytes()),
        GNU_symbol_table_sha256=sha(gnu),independent_GNU_sized_function_extents_equal=True,
        complete_canonical_image_equal=True,diagnostic=diagnostic,
        producer_sha256=sha(Path(__file__).read_bytes()))
    write_json(output/'function-ranges.json',report)
    return report

def verified_sdk_selection(program,executable,manifest):
    enabled=program['method_trace'].get('sdk_reads',False)
    require(type(enabled) is bool,'SDK read observation must be a boolean selection.')
    if not enabled:return None
    require(program['method_trace'].get('return_trace') is not None,
            'SDK reads require the original return/caller-flow observer.')
    require(sha(executable)==CANONICAL_SHA256 and manifest.get('schema_version')==1
            and manifest.get('kind')=='original_LSD_SDK_read_boundaries'
            and manifest.get('canonical_executable_sha256')==CANONICAL_SHA256
            and manifest.get('object_count')==306 and manifest.get('complete_canonical_image_equal') is True
            and manifest.get('independent_GNU_sized_function_extents_equal') is True,
            'Require complete canonical SDK function-range qualification.')
    rows=manifest.get('rows',[])
    require(len(rows)==len(TARGETS),'Incomplete SDK boundary selection.')
    selected=[]
    for row,(name,pc,length,kind) in zip(rows,TARGETS):
        offset=pc-0x80010000+0x800
        require((row.get('function'),row.get('pc'),row.get('bytes'),row.get('kind'))==(name,hex(pc),length,kind)
                and sha(executable[offset:offset+length])==row.get('sha256'),
                'SDK boundary identity or complete range changed: '+name)
        selected.append(dict(pc=pc,bytes=length,kind=kind))
    return selected

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export-ranges',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        report=export_ranges(args.export_ranges)
        print(json.dumps(dict(status='qualified_original_SDK_ranges',functions=len(report['rows']),
                              complete_canonical_image_equal=True)))
        return 0
    except (OSError,ValueError,subprocess.CalledProcessError) as error:
        print(str(error),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
