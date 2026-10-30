"""Export compact original function ranges from a complete matching symbolic link.

Only names, extents and hashes belong in the public index. ELF, instructions,
maps and full input receipts remain in a fresh private .decomp-lab directory.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import configure
from research.compiler.compare_function import CANONICAL_SHA256, elf_function
from tools.decomp_workbench import diagnostic_image, new_output_directory
from tools.export_npc_catalogue import nm_functions
from tools.original_functions import IDENTIFIER, reference_entry
from tools.progress import build_manifest, check_build_current
from tools.psx_image import executable_offset
from tools.runtime_inputs import record_file


def index_ranges(original, elf, gnu_symbols, seed='func_80020050', address=0x80020050):
    code, qualification = elf_function(elf, seed, address)
    functions = [dict(function=seed, address=f'0x{address:08X}', bytes=len(code)),
                 *qualification['other_sized_functions']]
    counts = Counter(row['function'] for row in functions)
    excluded = sorted(name for name, count in counts.items() if count != 1 or not IDENTIFIER.fullmatch(name))
    entries = []
    for row in sorted(functions, key=lambda row: (int(row['address'], 16), row['function'])):
        name, pc, size = row['function'], int(row['address'], 16), row['bytes']
        if name in excluded:
            continue
        if gnu_symbols.get(name) != [(pc, size)]:
            raise ValueError('GNU and ELF function extents disagree: ' + name)
        code, extent = elf_function(elf, name, pc)
        offset = executable_offset(original, pc, size)
        if code != original[offset:offset + size] or extent['function_bytes'] != size:
            raise ValueError('The complete linked function differs from the canonical executable: ' + name)
        entries.append(dict(function=name, address=f'0x{pc:08X}', file_offset=offset,
                            bytes=size, sha256=hashlib.sha256(code).hexdigest()))
    if not entries:
        raise ValueError('No independently sized original functions were qualified.')
    index = dict(schema_version=1, kind='original_LSD_function_ranges',
                 canonical_executable_sha256=hashlib.sha256(original).hexdigest(),
                 canonical_executable_sha1=hashlib.sha1(original).hexdigest(),
                 qualified_function_count=len(entries),
                 excluded_ambiguous_or_non_C_names=excluded,
                 scope='Unique sized text symbols, including SDK functions. These are metadata, not C coverage, source declarations, game features or runtime acceptance. No neighboring-symbol size inference is used.',
                 functions=entries)
    for row in entries:
        reference_entry(index, row['function'], original)
    return index


def export(output):
    if sys.platform != 'linux' or Path.cwd().resolve() != ROOT:
        raise ValueError('Export from the repository root in its supported Linux/WSL build environment.')
    if check_build_current(ROOT) is not True:
        raise ValueError('A current complete matching build is required.')
    original = (ROOT / configure.ROM).read_bytes()
    if (hashlib.sha256(original).hexdigest() != CANONICAL_SHA256 or
            (ROOT / configure.EXE).read_bytes() != original):
        raise ValueError('The complete built executable must equal the canonical executable.')
    gnu = {name: shutil.which(configure.CROSS + name) for name in ('nm', 'ld', 'objcopy')}
    if not all(gnu.values()):
        raise ValueError('GNU MIPS nm, ld and objcopy are required.')
    objects = [Path(configure.BUILD_DIR) / (source + '.o') for source, _ in build_manifest()]
    if not objects or any(not path.is_file() for path in objects):
        raise ValueError('The configured object set is incomplete.')
    paths = {ROOT / source for source, _ in build_manifest()}
    for folder in (ROOT / 'src', ROOT / 'include'):
        paths.update(folder.rglob('*.h'))
        paths.update(folder.rglob('*.inc'))
    paths.update(Path(path).resolve() for path in objects)
    paths.update(ROOT / name for name in ('configure.py', configure.LD_SCRIPT, configure.UNDEF_SYMS,
                 configure.UNDEF_FUNCS, configure.SYMBOLS, configure.SPLAT_CONFIG, configure.ROM, configure.EXE,
                 'tools/export_function_ranges.py', 'tools/original_functions.py',
                 'tools/decomp_workbench.py', 'research/compiler/compare_function.py'))
    paths.update(Path(path) for path in gnu.values())
    before = [record_file(path) for path in sorted(paths)]
    output = new_output_directory(output)
    with (output / 'diagnostic-link.log').open('xb') as log:
        elf_path, image = diagnostic_image(output, ROOT / configure.LD_SCRIPT, objects, ROOT / configure.EXE, log=log)
        symbols = subprocess.check_output([gnu['nm'], '-S', '--defined-only', str(elf_path)], stderr=log)
    (output / 'GNU-symbols.txt').write_bytes(symbols)
    elf = elf_path.read_bytes()
    index = index_ranges(original, elf, nm_functions(symbols.decode('ascii')))
    index['qualification'] = dict(complete_executable_equal=True, GNU_and_ELF_extents_agree=True,
        diagnostic_elf_sha256=hashlib.sha256(elf).hexdigest(), GNU_symbols_sha256=hashlib.sha256(symbols).hexdigest(),
        source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip())
    if [record_file(path) for path in sorted(paths)] != before or check_build_current(ROOT) is not True:
        raise ValueError('A source, object, tool or executable changed during range export.')
    index_path = output / 'original-functions.json'
    index_path.write_text(json.dumps(index, indent=2) + '\n', encoding='utf-8')
    report = dict(schema_version=1, status='verified_original_function_ranges',
        recorded_utc=datetime.now(timezone.utc).isoformat(), **image,
        complete_canonical_image_verified=True, source_inputs_preserved=True,
        original_function_ranges=len(index['functions']), excluded_names=index['excluded_ambiguous_or_non_C_names'],
        inputs=before, index=record_file(index_path), game_C_bytes_added=0,
        new_original_features=0, whole_feature_acceptances=0, whole_NPC_acceptances=0,
        model_API_calls=0, native_game_runs=0)
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Fresh private directory inside .decomp-lab.')
    args = parser.parse_args(argv)
    report = export(args.output)
    print(json.dumps({key: report[key] for key in ('status', 'original_function_ranges', 'excluded_names', 'game_C_bytes_added')}))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
