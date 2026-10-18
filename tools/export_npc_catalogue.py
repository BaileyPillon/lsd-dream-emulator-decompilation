"""Export original NPC callback ranges from a complete matching symbolic link.

Run in the supported Linux/WSL build environment. The output is private and
contains the complete local image. No game code, state or feature is changed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import configure
from research.compiler.compare_function import CANONICAL_SHA256, elf_function
from tools.decomp_workbench import diagnostic_image, new_output_directory
from tools.inventory_entities import audit_entities, verify_layout
from tools.inventory_vtables import parse_symbols
from tools.progress import build_manifest, check_build_current
from tools.psx_image import executable_offset
from tools.replay_cold_start_headless import require, write_json
from tools.runtime_inputs import record_file


def sha(data):
    return hashlib.sha256(data).hexdigest()


def nm_functions(text):
    """Keep all sized text symbols; selected duplicate names are ambiguous."""
    result = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) != 4 or fields[2] not in ('T', 't'):
            continue
        try:
            address, length = (int(value, 16) for value in fields[:2])
        except ValueError:
            raise ValueError('Invalid GNU text-symbol address or extent.') from None
        result.setdefault(fields[3], []).append((address, length))
    return result


def callback_ranges(executable, elf, records, gnu_symbols):
    """Resolve every nonnull binding using actual sized ELF and GNU symbols."""
    require(isinstance(records, list) and records, 'Supply the audited original entity records.')
    grouped, owners, seen = {}, {}, set()
    for row in records:
        require(isinstance(row, dict), 'Entity records must be audited field dictionaries.')
        index, name, text = (row.get(key) for key in ('index', 'callback_function', 'callback_address'))
        require(type(index) is int and 0 <= index < 65536 and index not in seen,
                'Entity IDs must be unique bounded nonnegative integers.')
        seen.add(index)
        require(isinstance(text, str) and re.fullmatch(r'0x[0-9A-F]{8}', text) is not None,
                'A callback needs its complete original hexadecimal address.')
        address = int(text, 16)
        if not address:
            require(name is None, 'A null original callback must have no function name.')
            continue
        require(isinstance(name, str) and re.fullmatch(r'entity_[A-Za-z0-9_]+', name) is not None
                and address % 4 == 0, 'Original callbacks need aligned named entity functions.')
        require(owners.get(address, name) == name, 'One callback PC has ambiguous source names.')
        owners[address] = name
        key = (address, name)
        grouped.setdefault(key, []).append(index)
    require(grouped, 'The entity records contain no original callbacks.')
    ranges = []
    for (address, name), indices in sorted(grouped.items()):
        code, extent = elf_function(elf, name, address)
        length = extent['function_bytes']
        require(gnu_symbols.get(name) == [(address, length)],
                'GNU and ELF must identify one identical complete callback extent: ' + name)
        offset = executable_offset(executable, address, length)
        original = executable[offset:offset + length]
        require(code == original, 'The complete callback differs from the canonical image: ' + name)
        if ranges:
            previous = ranges[-1]
            require(int(previous['pc'], 16) + previous['function_bytes'] <= address,
                    'Original callback function ranges overlap.')
        ranges.append(dict(callback=name, pc=f'0x{address:08X}', entity_ids=sorted(indices),
            function_bytes=length, function_sha256=sha(original),
            entry_instruction_sha256=sha(original[:4]), elf_section=extent['section']))
    return ranges


def export(output):
    require(sys.platform == 'linux', 'Export the catalogue in the supported Linux/WSL build environment.')
    require(Path.cwd().resolve() == ROOT, 'Run the exporter from the repository root.')
    destination = Path(output).resolve()
    lab = (ROOT / '.decomp-lab').resolve()
    require(destination != lab and destination.is_relative_to(lab) and not destination.exists(),
            'Choose a fresh private directory inside .decomp-lab; existing outputs are preserved.')
    require(check_build_current(ROOT) is True, 'A current complete matching build is required.')
    executable_path, built_path = ROOT / configure.ROM, ROOT / configure.EXE
    executable = executable_path.read_bytes()
    require(sha(executable) == CANONICAL_SHA256 and built_path.read_bytes() == executable,
            'The complete current executable must equal the canonical image.')
    native_tools = {name: shutil.which(configure.CROSS + name) for name in ('nm', 'ld', 'objcopy')}
    require(all(native_tools.values()), 'GNU MIPS nm, ld and objcopy are required.')
    objects = [Path(configure.BUILD_DIR) / (source + '.o') for source, _ in build_manifest()]
    require(objects and all(path.is_file() for path in objects), 'The configured object set is incomplete.')
    paths = [Path(__file__).resolve(), executable_path, built_path, ROOT / 'configure.py',
        ROOT / configure.LD_SCRIPT, ROOT / configure.MAP_FILE, ROOT / configure.UNDEF_SYMS,
        ROOT / configure.UNDEF_FUNCS, ROOT / configure.SYMBOLS,
        ROOT / 'src/scene/entity.c', ROOT / 'src/scene/entity.h',
        ROOT / 'tools/decomp_workbench.py', ROOT / 'research/compiler/compare_function.py',
        ROOT / 'tools/inventory_entities.py', ROOT / 'tools/inventory_vtables.py',
        ROOT / 'tools/feature_inventory.py', ROOT / 'tools/progress.py',
        ROOT / 'tools/psx_image.py', ROOT / 'tools/runtime_inputs.py',
        ROOT / 'tools/replay_cold_start_headless.py',
        *(Path(path) for path in native_tools.values()), *objects]
    before = [record_file(path) for path in paths]
    symbols = parse_symbols((ROOT / configure.MAP_FILE).read_text(),
        [(ROOT / name).read_text() for name in (configure.UNDEF_FUNCS, configure.UNDEF_SYMS, configure.SYMBOLS)])
    verify_layout((ROOT / 'src/scene/entity.h').read_text())
    audit = audit_entities(executable, (ROOT / 'src/scene/entity.c').read_text(), symbols)
    totals = audit['totals']
    require((totals['property_records'], totals['nonnull_callback_slots'],
             totals['null_callback_slots'], totals['distinct_callback_addresses']) == (130, 111, 19, 107),
            'The canonical original NPC table dimensions differ.')
    output = new_output_directory(destination)
    with (output / 'diagnostic-link.log').open('xb') as log:
        elf_path, image = diagnostic_image(output, ROOT / configure.LD_SCRIPT, objects, built_path, log=log)
        result = subprocess.run([native_tools['nm'], '-S', '--defined-only', str(elf_path)],
            stdout=subprocess.PIPE, stderr=log, check=True)
    (output / 'GNU-symbols.txt').write_bytes(result.stdout)
    ranges = callback_ranges(executable, elf_path.read_bytes(), audit['records'],
                             nm_functions(result.stdout.decode('ascii')))
    require(len(ranges) == 107 and sum(len(row['entity_ids']) for row in ranges) == 111,
            'The catalogue did not cover every original nonnull binding.')
    require([record_file(path) for path in paths] == before and check_build_current(ROOT) is True,
            'A source, object, executable or build input changed during export.')
    catalogue = dict(schema_version=1, kind='original_LSD_NPC_callback_catalogue',
        canonical_executable_sha256=CANONICAL_SHA256, original_entity_table=audit['table'],
        property_records=130, nonnull_callback_slots=111, null_callback_slots=19,
        distinct_callback_functions=107, total_callback_function_bytes=sum(row['function_bytes'] for row in ranges),
        targets=ranges, original_behavior_modified=False, new_C_bytes=0,
        native_callback_executions=0, whole_NPC_encounters_accepted=0, whole_feature_groups_accepted=0,
        scope='Static original bindings and complete matching code ranges for observer selection and '
              'human/AI-assisted analysis. Source names are recovered labels. This export executes no game callback.')
    write_json(output / 'catalogue.json', catalogue)
    report = dict(schema_version=1, status='exported_verified_original_NPC_catalogue',
        recorded_utc=datetime.now(timezone.utc).isoformat(), python=sys.version, **image,
        canonical_complete_image_verified=True, cached_objects=len(objects),
        original_callback_ranges=107, original_nonnull_bindings=111, original_null_bindings=19,
        complete_ELF_and_GNU_extents_agree=True, all_complete_callback_bytes_match=True,
        compiler_flags_changed=False, input_files_preserved=True, inputs=before,
        catalogue=record_file(output / 'catalogue.json'), source_promoted=False,
        new_C_bytes=0, native_game_runs=0, model_API_called=False, emulator_UI_controlled=False,
        whole_feature_groups_accepted=0, whole_NPC_encounters_accepted=0)
    write_json(output / 'report.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Fresh private directory inside .decomp-lab.')
    args = parser.parse_args(argv)
    report = export(args.output)
    print(json.dumps({key: report[key] for key in
        ('status', 'cached_objects', 'original_callback_ranges', 'canonical_complete_image_verified', 'new_C_bytes')}))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
