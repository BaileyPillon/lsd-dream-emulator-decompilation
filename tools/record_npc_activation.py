"""Observe original NPC engine entries against an existing verified history.

Windows-only optional analysis. Runtime libraries are shared through directory
junctions. The compact host compares every declared output against the reference
without saving duplicate audio, screenshots or raw RAM/GPU buffers. Reference
paths and all actual observations remain private. No game RAM is injected.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.compare_npc_history import inspect_run
import configure
from tools.inventory_entities import audit_entities, verify_layout
from tools.inventory_vtables import parse_symbols
from tools.psx_image import executable_offset
from tools.record_npc_history import STOCK_RUNTIME, load_observer_profile
from tools.replay_cold_start_headless import require, select_compiler, write_json
from tools.runtime_inputs import disc_inputs, record_file

COMPACT = ROOT / 'research/headless/compact/RecordNpcHistory.cs'
METHODS = ROOT / 'research/headless/entity-lifecycle-methods.json'
CATALOGUE = ROOT / 'research/headless/npc-callback-catalogue.json'
HOST_SOURCES = [COMPACT, *(ROOT / 'research/headless' / name for name in
                ('ReplayColdStart.cs', 'NpcInstructionTrace.cs', 'NpcCatalogueTrace.cs', 'RecordNpcCatalogue.cs'))]
ENGINE_METHODS = {'entity_tick', 'entity_check_interaction', 'entity_check_interaction_range',
                  'entity_check_link_trigger', 'entity_enable_link', 'entity_disable_link',
                  'entity_start_behaviour', 'entity_stop_behaviour'}


def original_entity_audit():
    """Pin original bytes and source bindings on Windows, without Linux stamps.

    Matching-C build freshness is a separate supported-build check. This
    recorder accepts no new C source and attributes no C coverage to a replay.
    """
    names = [configure.ROM, configure.EXE, configure.MAP_FILE, configure.UNDEF_FUNCS,
             configure.UNDEF_SYMS, configure.SYMBOLS, 'src/scene/entity.c', 'src/scene/entity.h',
             'tools/inventory_entities.py', 'tools/inventory_vtables.py', 'tools/psx_image.py']
    pins = {name: record_file(ROOT / name) for name in names}
    original = (ROOT / configure.ROM).read_bytes()
    require(hashlib.sha256(original).hexdigest() == '282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f'
            and (ROOT / configure.EXE).read_bytes() == original, 'The original and built complete images must remain canonical.')
    verify_layout((ROOT / 'src/scene/entity.h').read_text())
    symbols = parse_symbols((ROOT / configure.MAP_FILE).read_text(),
                            [(ROOT / name).read_text() for name in (configure.UNDEF_FUNCS, configure.UNDEF_SYMS, configure.SYMBOLS)])
    audit = audit_entities(original, (ROOT / 'src/scene/entity.c').read_text(), symbols)
    require(all(record_file(ROOT / name) == pin for name, pin in pins.items()), 'Original input evidence changed during inspection.')
    audit['evidence_sha256'] = {name: row['sha256'] for name, row in pins.items()}
    return audit


def native_targets(executable, catalogue, engine, audit):
    """Validate entire spans and exact NPC/property binding closure."""
    digest = hashlib.sha256(executable).hexdigest()
    require(catalogue.get('canonical_executable_sha256') == digest == engine.get('canonical_executable_sha256'),
            'Target catalogues require the canonical complete executable.')
    require(engine.get('schema_version') == 1 and len(engine.get('methods', [])) == 8,
            'Use the reviewed eight-method lifecycle catalogue.')
    require({row.get('name') for row in engine['methods']} == ENGINE_METHODS,
            'The lifecycle catalogue has an unreviewed method identity.')
    expected = {(row['callback_function'], row['callback_address']) for row in audit['records'] if row['callback_function']}
    actual = {(row['callback'], row['pc']) for row in catalogue['targets']}
    require(actual == expected and len(actual) == 107, 'The original NPC binding closure differs.')
    rows = [dict(name=row['callback'], address=int(row['pc'], 0), bytes=row['function_bytes'],
                 sha256=row['function_sha256']) for row in catalogue['targets']] + engine['methods']
    pcs = []
    for row in rows:
        address, size = row['address'], row['bytes']
        require(type(address) is int and type(size) is int and address % 4 == 0 and size > 0 and size % 4 == 0,
                'Each target needs an aligned complete original extent.')
        offset = executable_offset(executable, address, size)
        require(hashlib.sha256(executable[offset:offset + size]).hexdigest() == row['sha256'],
                'An original target span differs: ' + row['name'])
        pcs.append(address)
    require(len(pcs) == len(set(pcs)) == 115, 'Target PCs must be distinct and fit the native observer.')
    return pcs


def prefix_settings(reference_settings, reference_folder, targets, frames, stock=False):
    total = reference_settings['frames']
    require(type(frames) is int and 1 <= frames <= total <= 30000, 'Invalid reference prefix length.')
    require(frames in reference_settings['checkpoint_frames'], 'The prefix must end at a retained raw checkpoint.')
    settings = dict(reference_settings)
    settings.update(frames=frames, checkpoint_frames=[f for f in settings['checkpoint_frames'] if f <= frames],
                    reference=str(Path(reference_folder) / 'observations'), reference_frames=total,
                    catalogue_pcs=targets, trace_enabled=not stock)
    return settings


def junction(link, target):
    require(not os.path.lexists(link) and target.is_dir(), 'Use a new runtime link and an existing input directory.')
    require(not target.lstat().st_file_attributes & 0x400, 'Supply the direct retained runtime directory.')
    # Paths are JSON data on stdin, never interpolated into PowerShell code.
    script = ('$p=[Console]::In.ReadToEnd()|ConvertFrom-Json; '
              'New-Item -ItemType Junction -Path $p.link -Target $p.target -ErrorAction Stop|Out-Null')
    subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                   input=json.dumps(dict(link=str(link), target=str(target))), text=True,
                   capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    require(link.resolve() == target, 'Runtime junction does not resolve to its verified input.')


def output_bytes(folder):
    return sum(path.stat().st_size for path in folder.iterdir() if path.is_file()) if folder.exists() else 0


def record(reference, runtime, workspace, *, observer_profile=None, stock=False, frames=None, cue=None, dotnet=None):
    require(os.name == 'nt' and sys.maxsize > 2**32, 'Use the supported 64-bit Windows environment.')
    require(stock == (observer_profile is None), 'Select stock control or an explicit catalogue observer profile.')
    reference, runtime = Path(reference).resolve(strict=True), Path(runtime).resolve(strict=True)
    workspace = Path(workspace).absolute()
    require(not os.path.lexists(workspace) and workspace != Path(workspace.anchor), 'Choose a fresh private workspace.')
    require(not workspace.is_relative_to(reference) and not workspace.is_relative_to(runtime),
            'Keep output outside the reference and supplied runtime.')
    for ancestor in workspace.parents:
        if (ancestor / '.git').exists():
            require(ancestor == ROOT and workspace.is_relative_to(ROOT / '.decomp-lab'),
                    'Keep recordings outside worktrees or under this checkout\'s private .decomp-lab.')
    executable = (ROOT / 'rom/SLPS_015.56').read_bytes()
    inspect_run(reference, executable)
    audit = original_entity_audit()
    targets = native_targets(executable, json.loads(CATALOGUE.read_text()), json.loads(METHODS.read_text(encoding='utf-8-sig')), audit)
    source_inputs = json.loads((reference / 'run-inputs.json').read_text())
    source_settings = json.loads((reference / 'settings.json').read_text())
    frames = source_settings['frames'] if frames is None else frames
    settings = prefix_settings(source_settings, reference, targets, frames, stock)
    supplied = disc_inputs(cue or source_inputs['command'][2])
    expected = source_inputs['source_manifest']['disc']
    require(supplied['layout'] == expected['layout'] and
            [(r['bytes'], r['sha256']) for r in supplied['tracks']] ==
            [(r['bytes'], r['sha256']) for r in expected['tracks']],
            'The alternate disc must retain the complete verified track bytes and layout.')
    profile, profile_files = (None, []) if stock else load_observer_profile(observer_profile, catalogue=True)
    require(all(record_file(runtime / name)['sha256'] == value for name, value in STOCK_RUNTIME.items()
                if name != 'dll/shock.wbx.zst'), 'Use the qualified 2.11.1 managed adapter and Waterbox host.')
    if stock:
        require(all(record_file(runtime / name)['sha256'] == value for name, value in STOCK_RUNTIME.items()),
                'The stock control requires the qualified distributed core and adapter.')
    else:
        require(record_file(runtime / 'dll/shock.wbx.zst')['sha256'] == profile['compressed_core']['sha256'],
                'The supplied runtime does not contain the profiled catalogue core.')
    runtime_files = [p for name in ('dll', 'gamedb') for p in sorted((runtime / name).rglob('*')) if p.is_file()]
    require(runtime_files and (runtime / 'gamedb/gamedb.txt').is_file(), 'The retained runtime and game database are required.')
    reference_files = [p for p in sorted((reference / 'observations').iterdir()) if p.is_file()]
    configuration = Path(source_inputs['host_configuration']['path'])
    paths = [Path(__file__), *HOST_SOURCES, METHODS, CATALOGUE, configuration,
             *(ROOT / p for p in audit['evidence_sha256']),
             reference / 'run-inputs.json', reference / 'submitted.tsv', reference / 'settings.json',
             *runtime_files, *reference_files, *profile_files]
    paths += [Path(row['path']) for row in [supplied['cue'], *supplied['tracks']]]
    paths += [Path(p) for p in source_inputs['command'][3:6]]
    pins = [record_file(p) for p in paths]
    dotnet = str(dotnet or Path(os.environ['ProgramFiles']) / 'dotnet/dotnet.exe')
    compiler = select_compiler(subprocess.check_output([dotnet, '--list-sdks'], text=True))
    framework = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319'
    references = [framework / name for name in ('mscorlib.dll', 'System.dll', 'System.Core.dll',
                  'System.Web.Extensions.dll', 'System.Drawing.dll', 'netstandard.dll')]
    references += [runtime / 'dll' / name for name in ('BizHawk.Common.dll', 'BizHawk.BizInvoke.dll',
                   'BizHawk.Emulation.Common.dll', 'BizHawk.Emulation.Cores.dll', 'BizHawk.Emulation.DiscSystem.dll', 'System.ValueTuple.dll')]
    require(all(p.is_file() for p in references), 'Required framework/core references are absent.')
    pins += [record_file(p) for p in [compiler, *references]]
    workspace.mkdir(parents=True, exist_ok=False)
    host = workspace / 'host'; host.mkdir()
    junction(host / 'dll', runtime / 'dll'); junction(host / 'gamedb', runtime / 'gamedb')
    binary = host / 'CompactNpcActivation.exe'
    (host / 'CompactNpcActivation.exe.config').write_bytes(configuration.read_bytes())
    command = [dotnet, 'exec', str(compiler), '/nologo', '/target:exe', '/platform:x64', '/langversion:12',
               '/main:Lsd.Research.Headless.RecordNpcCatalogue', '/nostdlib+', '/deterministic+',
               *('/reference:' + str(p) for p in references), '/out:' + str(binary), *(str(p) for p in HOST_SOURCES)]
    write_json(workspace / 'compile-command.json', command)
    with (workspace / 'compiler.log').open('xb') as log:
        built = subprocess.run(command, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
    require(built.returncode == 0, 'Compact host compilation failed; see its private compiler.log.')
    write_json(workspace / 'settings.json', settings)
    launch = [str(binary), str(host), supplied['cue']['path'], *source_inputs['command'][3:6],
              str(reference / 'submitted.tsv'), str(workspace / 'settings.json'), str(workspace / 'observations')]
    pins += [record_file(binary), record_file(binary.with_suffix('.exe.config')), record_file(workspace / 'settings.json')]
    write_json(workspace / 'run-inputs.json', dict(schema_version=1, kind='compact_engine_entry_observation',
        reference=str(reference), frames=frames, stock_control=stock, command=launch, inputs=pins,
        target_NPC_callbacks=107, target_engine_methods=8, original_NPC_behavior_modified=False,
        runtime_libraries_copied=False, restored_state=False, game_RAM_injected=False, model_api_calls=0,
        matching_C_build_freshness_checked=False))
    with (workspace / 'stdout.log').open('xb') as stdout, (workspace / 'stderr.log').open('xb') as stderr:
        process = subprocess.Popen(launch, cwd=host, stdout=stdout, stderr=stderr,
                                  creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        write_json(workspace / 'process.json', dict(pid=process.pid, command=launch))
        print(json.dumps(dict(status='recording_compact_engine_history', pid=process.pid, frames=frames)), flush=True)
        try:
            while process.poll() is None:
                if output_bytes(workspace / 'observations') > 64 * 1024**2:
                    process.terminate()
                    process.wait()
                    raise ValueError('Owned compact output exceeded its 64 MiB review threshold; partial evidence is retained.')
                time.sleep(0.1)
            code = process.returncode
        finally:
            if process.poll() is None:
                process.terminate(); process.wait()
    require(all(record_file(row['path']) == row for row in pins), 'A frozen source, reference or runtime input changed.')
    result = dict(exit_code=code, reference=str(reference), frames=frames, stock_control=stock,
                  supplied_inputs_preserved=True, runtime_libraries_copied=False, new_C_bytes=0,
                  new_bounded_NPC_callbacks=0, whole_NPC_encounters_accepted=0,
                  whole_feature_groups_accepted=0, recorded_utc=datetime.now(timezone.utc).isoformat())
    if code == 0:
        result['native'] = json.loads((workspace / 'observations/report.json').read_text())
    write_json(workspace / 'result.json', result)
    require(code == 0, 'Compact recording rejected a reference difference or native failure; inspect retained stderr.')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'runtime', 'workspace'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--observer-profile', type=Path)
    parser.add_argument('--stock', action='store_true')
    parser.add_argument('--frames', type=int)
    parser.add_argument('--cue', type=Path)
    args = parser.parse_args(argv)
    result = record(args.reference, args.runtime, args.workspace, observer_profile=args.observer_profile,
                    stock=args.stock, frames=args.frames, cue=args.cue)
    print(json.dumps(dict(status='completed_compact_engine_history', exit_code=result['exit_code'])))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
