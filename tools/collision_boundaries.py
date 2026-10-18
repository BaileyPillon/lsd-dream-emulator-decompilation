"""Qualify both remaining collision functions for optional natural entry traces."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import configure
from research.compiler.compare_function import CANONICAL_SHA256,elf_function
from tools.decomp_workbench import diagnostic_image
from tools.progress import build_manifest,check_build_current
from tools.replay_cold_start_headless import require,write_json

TARGETS=(('func_8001DDF4',0x8001DDF4,796),('func_8001F8B8',0x8001F8B8,1944))
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def export_ranges(output):
    output=Path(output).resolve()
    require(output.is_relative_to(ROOT/'.decomp-lab') and not output.exists(),
            'Choose a fresh private collision-range diagnostic directory.')
    require(check_build_current(ROOT) is True,'Require the current canonical game build.')
    original=(ROOT/configure.ROM).read_bytes()
    require(sha(original)==CANONICAL_SHA256 and original==(ROOT/configure.EXE).read_bytes(),
            'Require the complete original canonical executable.')
    output.mkdir()
    objects=[Path(configure.BUILD_DIR)/(source+'.o') for source,_ in build_manifest()]
    with (output/'link.log').open('xb') as log:
        elf,diagnostic=diagnostic_image(output,Path(configure.LD_SCRIPT),objects,ROOT/configure.EXE,log)
    gnu=subprocess.check_output([configure.CROSS+'nm','-S','--defined-only',str(elf)])
    (output/'gnu-symbols.txt').write_bytes(gnu)
    symbols={words[3]:(int(words[0],16),int(words[1],16)) for line in gnu.decode().splitlines()
             if len(words:=line.split())==4 and words[2] in ('T','t')}
    rows=[]
    for name,pc,length in TARGETS:
        code,_=elf_function(elf.read_bytes(),name,pc)
        offset=pc-0x80010000+0x800
        require(symbols.get(name)==(pc,length) and len(code)==length and code==original[offset:offset+length],
                'Complete original collision ELF/GNU range qualification failed: '+name)
        rows.append(dict(function=name,address=hex(pc),bytes=length,sha256=sha(code)))
    write_json(output/'function-ranges.json',rows)
    proof=dict(schema_version=1,status='verified_complete_original_collision_boundaries',
        canonical_executable_sha256=CANONICAL_SHA256,original_function_range_count=len(rows),object_count=len(objects),
        original_symbol_diagnostic=dict(complete_canonical_image_equal=True,
            independent_GNU_sized_function_extents_equal=True,canonical_symbolic_elf_sha256=sha(elf.read_bytes()),
            GNU_symbol_table_sha256=sha(gnu),diagnostic=diagnostic),
        producer_dependencies={'research/collision/function-ranges.json':sha((output/'function-ranges.json').read_bytes()),
            'tools/collision_boundaries.py':sha(Path(__file__).read_bytes())},
        original_slot_bindings=[],range_selection_supplies_runtime_execution_evidence=False,
        original_declared_dispatch_catalogue_modified=False,new_C_bytes=0,whole_feature_groups_accepted=0)
    write_json(output/'range-provenance.json',proof)
    return proof


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        report=export_ranges(args.output)
        print(json.dumps(dict(status=report['status'],functions=report['original_function_range_count'])));return 0
    except (OSError,ValueError,subprocess.CalledProcessError) as error:print(str(error),file=sys.stderr);return 2


if __name__=='__main__':sys.exit(main())
