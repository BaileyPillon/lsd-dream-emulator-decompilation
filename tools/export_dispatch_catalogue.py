"""Export complete original ranges for declared virtual-table targets.

Requires a current canonical WSL build. Declared bindings, complete function
ownership and indirect instruction sites remain separate from observed calls,
reviewed signatures, source recovery and whole-feature acceptance.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import configure
from research.compiler.compare_function import CANONICAL_SHA256, elf_function
from tools.decomp_workbench import diagnostic_image, new_output_directory
from tools.export_npc_catalogue import nm_functions
from tools.inventory_vtables import collect
from tools.progress import build_manifest, check_build_current
from tools.psx_image import executable_offset
from tools.replay_cold_start_headless import require, write_json
from tools.runtime_inputs import record_file


def sha(data):
    return hashlib.sha256(data).hexdigest()


def address(value):
    require(isinstance(value, str) and re.fullmatch(r'0x[0-9A-F]{8}', value) is not None,
            'Require a complete uppercase original address.')
    return int(value, 16)


def indirect_sites(code, pc):
    """Describe exact JR/JALR encodings; an instruction is not a virtual call."""
    require(code and len(code) % 4 == 0 and pc % 4 == 0, 'Require complete aligned instruction words.')
    result = []
    for offset, (word,) in enumerate(struct.iter_unpack('<I', code)):
        source, target, destination, shift = word >> 21 & 31, word >> 16 & 31, word >> 11 & 31, word >> 6 & 31
        operation = word & 63
        if word >> 26 or target or shift or operation not in (8, 9):
            continue
        if operation == 8 and destination:
            continue
        if operation == 8 and source == 31:
            continue  # An ordinary return is outside this indirect-target index.
        site = pc + offset * 4
        require(offset * 4 + 8 <= len(code), 'An indirect transfer lacks its complete owned delay slot.')
        row = dict(pc=f'0x{site:08X}', instruction='JALR' if operation == 9 else 'JR',
            target_register=source, link_register=destination if operation == 9 else None,
            delay_slot_pc=f'0x{site + 4:08X}', instruction_sha256=sha(struct.pack('<I', word)),
            classification='unobserved_indirect_transfer')
        if operation == 9 and destination == 31:
            row['return_address'] = f'0x{site + 8:08X}'
        result.append(row)
    return result


def target_ranges(executable, elf, inventory, gnu):
    """Check table words and complete uniquely owned target extents independently."""
    require(isinstance(inventory, dict) and isinstance(inventory.get('tables'), list)
            and inventory['tables'], 'Require a nonempty audited table inventory.')
    grouped, tables, nulls, names, pcs = {}, [], [], set(), set()
    for table in inventory['tables']:
        name, kind, slots = table.get('name'), table.get('type'), table.get('slots')
        require(isinstance(name, str) and re.fullmatch(r'[A-Za-z_]\w*', name) is not None
                and name not in names and isinstance(kind, str) and kind,
                'Table names must be unique valid declarations.')
        pc = address(table.get('address'))
        require(pc % 4 == 0 and pc not in pcs, 'Table addresses must be unique and aligned.')
        require(isinstance(slots, list) and slots and table.get('bytes') == 4 * len(slots),
                'Every complete table word needs a declaration.')
        names.add(name)
        pcs.add(pc)
        start = executable_offset(executable, pc, table['bytes'])
        raw = executable[start:start + table['bytes']]
        callbacks, nonnull = 0, 0
        fields = set()
        for index, slot in enumerate(slots):
            field, is_function = slot.get('field'), slot.get('declared_function_pointer')
            require(type(slot.get('offset')) is int and slot['offset'] == 4 * index
                    and isinstance(field, str) and field and field not in fields
                    and type(is_function) is bool, 'Table slots must have unique ordered declared fields.')
            fields.add(field)
            value = address(slot.get('value'))
            require(struct.unpack_from('<I', raw, index * 4)[0] == value,
                    'A declared table word differs from the original executable.')
            if not is_function:
                continue
            callbacks += 1
            binding = dict(table=name, slot=f'0x{index * 4:03X}', field=field)
            if not value:
                nulls.append(binding)
                continue
            nonnull += 1
            require(value % 4 == 0, 'Original target addresses must be aligned.')
            symbols = slot.get('linker_symbols')
            require(isinstance(symbols, list) and symbols and all(isinstance(item, str) and item for item in symbols),
                    'Every nonnull target needs audited linker names.')
            item = grouped.setdefault(value, dict(bindings=[], names=set()))
            item['bindings'].append(binding)
            item['names'].update(symbols)
        tables.append(dict(table=name, type=kind, pc=table['address'], bytes=len(raw), sha256=sha(raw),
                           declared_callback_slots=callbacks, nonnull_callback_slots=nonnull))
    require(grouped, 'The declared tables contain no nonnull targets.')
    by_address = {}
    for name, rows in gnu.items():
        for pc, length in rows:
            by_address.setdefault(pc, []).append((name, length))
    targets, sites = [], []
    for pc, item in sorted(grouped.items()):
        candidates = by_address.get(pc, [])
        require(len(candidates) == 1, 'A target needs one unambiguous complete GNU function owner.')
        name, length = candidates[0]
        require(name in item['names'], 'The complete function owner disagrees with audited linker names.')
        code, extent = elf_function(elf, name, pc)
        require(gnu[name] == [(pc, len(code))] and length == len(code),
                'GNU and ELF target extents disagree.')
        at = executable_offset(executable, pc, length)
        require(code == executable[at:at + length], 'The complete target differs from the original executable.')
        if targets:
            previous = targets[-1]
            require(address(previous['pc']) + previous['function_bytes'] <= pc,
                    'Complete target function ranges overlap.')
        targets.append(dict(function=name, pc=f'0x{pc:08X}', function_bytes=length,
            function_sha256=sha(code), entry_instruction_sha256=sha(code[:4]), elf_section=extent['section'],
            bindings=sorted(item['bindings'], key=lambda row: (row['table'], row['slot']))))
        sites.extend(dict(function=name, **site) for site in indirect_sites(code, pc))
    return tables, targets, nulls, sites


def export(output):
    require(sys.platform == 'linux' and Path.cwd().resolve() == ROOT,
            'Run from the repository root in the supported Linux/WSL build environment.')
    output = Path(output).resolve()
    lab = (ROOT / '.decomp-lab').resolve()
    require(output != lab and output.is_relative_to(lab) and not output.exists(),
            'Choose a fresh private directory inside .decomp-lab; earlier evidence is preserved.')
    require(check_build_current(ROOT) is True, 'Require a current complete matching build.')
    original, built = ROOT / configure.ROM, ROOT / configure.EXE
    executable = original.read_bytes()
    require(sha(executable) == CANONICAL_SHA256 and built.read_bytes() == executable,
            'The original and complete rebuilt executable must be canonical.')
    inventory = collect()
    require(not inventory['header_layout_issues'] and not inventory['unresolved_declarations']
            and not inventory['unnamed_declared_function_addresses'], 'Unresolved table inventory cannot qualify targets.')
    objects = [Path(configure.BUILD_DIR) / (source + '.o') for source, _ in build_manifest()]
    require(objects and all(path.is_file() for path in objects), 'Require every configured original build object.')
    native_tools = {name: shutil.which(configure.CROSS + name) for name in ('nm', 'ld', 'objcopy')}
    require(all(native_tools.values()), 'GNU MIPS nm, ld and objcopy are required.')
    paths = {Path(__file__).resolve(), original, built, ROOT / 'configure.py', ROOT / configure.LD_SCRIPT,
        ROOT / configure.MAP_FILE, ROOT / configure.UNDEF_FUNCS, ROOT / configure.UNDEF_SYMS, ROOT / configure.SYMBOLS,
        *(ROOT / path for path in inventory['source_sha256']),
        *(ROOT / path for path in ('tools/decomp_workbench.py','research/compiler/compare_function.py',
            'tools/export_npc_catalogue.py','tools/inventory_vtables.py','tools/progress.py','tools/psx_image.py',
            'tools/replay_cold_start_headless.py','tools/runtime_inputs.py')),
        *(Path(path) for path in native_tools.values()), *objects}
    paths = sorted(paths, key=str)
    before = [record_file(path) for path in paths]
    output = new_output_directory(output)
    with (output / 'diagnostic-link.log').open('xb') as log:
        linked, image = diagnostic_image(output, ROOT / configure.LD_SCRIPT, objects, built, log=log)
        result = subprocess.run([native_tools['nm'], '-S', '--defined-only', str(linked)],
            stdout=subprocess.PIPE, stderr=log, check=True)
    (output / 'GNU-symbols.txt').write_bytes(result.stdout)
    tables, targets, nulls, sites = target_ranges(executable, linked.read_bytes(), inventory,
                                                nm_functions(result.stdout.decode('ascii')))
    require(len(targets) == inventory['unique_declared_function_addresses']
            and sum(len(row['bindings']) for row in targets) == inventory['nonnull_declared_function_slots']
            and len(nulls) + sum(len(row['bindings']) for row in targets) == inventory['declared_function_slots'],
            'Complete target bindings must close the entire declared callback inventory.')
    require([record_file(path) for path in paths] == before and check_build_current(ROOT) is True,
            'An original input, object, source, producer or current build changed during export.')
    catalogue = dict(schema_version=1, kind='original_LSD_declared_dispatch_targets',
        canonical_executable_sha256=CANONICAL_SHA256, declared_tables=len(tables),
        declared_callback_slots=inventory['declared_function_slots'], nonnull_callback_bindings=sum(len(row['bindings']) for row in targets),
        null_callback_bindings=len(nulls), distinct_target_functions=len(targets),
        total_target_function_bytes=sum(row['function_bytes'] for row in targets),
        indirect_transfer_sites=len(sites), tables=tables, targets=targets,
        null_bindings=nulls, sites=sites, unsupported_type_views=inventory['unsupported_types'],
        all_dynamic_dispatch_resolved=False, native_calls_observed=0, original_behavior_modified=False,
        new_C_bytes=0, whole_feature_groups_accepted=0,
        scope='Every declared nonnull vtable target has complete original ELF/GNU ownership and matching bytes. '
              'Indirect JR/JALR sites are unobserved instructions within those bodies; they are not accepted '
              'virtual calls. Other original code, non-vtable callbacks, runtime receiver/slot edges, signatures '
              'and natural behavior remain separate. No game bytes, SDK semantics or features are recovered by export.')
    write_json(output / 'catalogue.json', catalogue)
    report = dict(status='exported_verified_declared_dispatch_catalogue', recorded_utc=datetime.now(timezone.utc).isoformat(),
        **image, canonical_complete_image_verified=True, cached_objects=len(objects),
        declared_tables=len(tables), declared_callback_slots=catalogue['declared_callback_slots'],
        nonnull_callback_bindings=catalogue['nonnull_callback_bindings'], null_callback_bindings=len(nulls),
        complete_target_functions=len(targets), target_function_bytes=catalogue['total_target_function_bytes'],
        indirect_transfer_sites=len(sites), complete_ELF_and_GNU_extents_agree=True,
        all_complete_target_bytes_match=True, every_declared_callback_binding_accounted=True,
        inventory_source_sha256=inventory['source_sha256'], input_files_preserved=True, inputs=before,
        catalogue=record_file(output / 'catalogue.json'), compiler_flags_changed=False,
        game_functions_promoted=0, new_C_bytes=0, model_API_called=False, emulator_UI_controlled=False,
        whole_feature_groups_accepted=0, native_game_runs=0)
    write_json(output / 'report.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = export(args.output)
        print(json.dumps({key:report[key] for key in ('status','cached_objects','declared_tables',
            'complete_target_functions','nonnull_callback_bindings','indirect_transfer_sites','new_C_bytes')}))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
