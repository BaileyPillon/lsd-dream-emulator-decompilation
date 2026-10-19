"""Inspect compact histories or compare their exact bounded output windows."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import record_dispatch_history as legacy
from tools.compact_dispatch import validate_outputs, compare_outputs, read_payload, rows, sha
from tools.compact_dispatch_inputs import context, selection_paths
from tools.dispatch_trace import validate_program, expand_program
from tools.inspect_dispatch_history import validate_entries, validate_native_summary, ENTRY_FIELDS
from tools.dispatch_flow import validate_flow
from tools.dispatch_returns import validate_returns
from tools.inspect_sdk_reads import validate_records
from tools.record_compact_dispatch import runtime_files, qualify_reused_profile
from tools.record_npc_history import STOCK_RUNTIME
from tools.replay_cold_start_headless import require, write_json
from tools.runtime_inputs import record_file, load_verified_manifest

def qualify_host_sources(captured, current, published=None):
    require(captured == current or (isinstance(published, dict) and captured == published),
            'Compact host source set is neither current nor a published qualified version.')

def verify(path, expected):
    actual = record_file(path)
    require(actual == expected, 'Retained compact input differs: ' + str(path))
    return actual

def inspect_details(folder):
    folder = Path(folder).resolve(strict=True)
    run = json.loads((folder / 'run-inputs.json').read_text(encoding='utf-8-sig'))
    require(run.get('schema_version') == 1 and run.get('kind') == 'compact_original_method_history'
            and all(run.get(k) == 0 for k in ('runtime_copies', 'disc_copies', 'asset_tree_copies'))
            and all(run.get(k) is False for k in ('game_RAM_injected', 'restored_state', 'emulator_UI_controlled')),
            'Unsupported compact source or execution mode.')
    process = json.loads((folder / 'process.json').read_text())
    exit_info = json.loads((folder / 'exit.json').read_text())
    require(exit_info.get('exit_code') == 0 and exit_info.get('pid') == process.get('pid')
            and process.get('command') == run['command'], 'Owned compact process did not complete its recorded command.')
    snapshots = {}
    require(set(run['source_snapshots']) == set(run['source_pins']), 'Incomplete compact source snapshot roles.')
    for key, row in run['source_snapshots'].items():
        path = (folder / row['file']).resolve(strict=True)
        require(path.parent == folder / 'sources' and row['file'].startswith('sources/'), 'Snapshot escapes its source directory.')
        actual = verify(path, {k: row[k] for k in ('path', 'bytes', 'sha256')})
        original = run['source_pins'][key]
        require((actual['bytes'], actual['sha256']) == (original['bytes'], original['sha256']), 'Frozen source differs from its producer pin.')
        snapshots[key] = path.read_bytes()
    captured_host = {p.name: run['source_pins']['host_' + p.stem]['sha256'] for p in legacy.HOST_SOURCES}
    current_host = {p.name: record_file(p)['sha256'] for p in legacy.HOST_SOURCES}
    proof = ROOT / 'docs/blocking-cd-retry-checks.json'
    published_host = json.loads(proof.read_text()).get('captured_host_source_SHA256') if proof.is_file() else None
    qualify_host_sources(captured_host, current_host, published_host)
    for name, key in (('program.json', 'program_file'), ('settings.json', 'settings_file'), ('submitted.tsv', 'submitted'),
                      ('host/RecordDispatchHistory.exe', 'host_binary'), ('host/RecordDispatchHistory.exe.config', 'host_configuration'),
                      ('compile-command.json', 'compile_command')):
        verify(folder / name, run[key])
    require(run['program_file']['sha256'] == run['source_pins']['program']['sha256'], 'Program source/snapshot identity differs.')
    program = validate_program(json.loads((folder / 'program.json').read_text()))
    settings = json.loads((folder / 'settings.json').read_text())
    require(settings == run['settings'] and settings['compact_capture'] is True, 'Compact settings differ from retained inputs.')
    require(set(selection_paths(program)) <= set(snapshots), 'Canonical selection snapshots are incomplete.')
    selected = context(program, snapshots)
    expected_settings = dict(frames=settings['frames'], checkpoint_frames=sorted(
        {v for v in program['checkpoint_frames'] if v <= settings['frames']} | {0, settings['frames']}),
        RAM_sample_interval=program['RAM_sample_interval'], trace_enabled=run['observer_profile'] is not None,
        arm_frame=program['method_trace']['arm_frame'], dispatch_targets=selected['dispatch_targets'],
        dispatch_words=selected['dispatch_words'], flow_sites=selected['flow_sites'], return_trace=selected['return_trace'],
        collision_calls=None, serialized_state=False, compact_capture=True)
    require(settings == expected_settings and settings['frames'] >= settings['arm_frame'], 'Compact selection or observation window differs.')
    capture = Path(run['source_capture'])
    verify(capture / 'inputs.json', run['source_capture_manifest'])
    require(load_verified_manifest(capture) == run['source_manifest'], 'Original disc/BIOS/cold-boot inputs changed.')
    source = run['source_manifest']
    require(source['start_kind'] == 'cold_boot' and source['start_state'] is None and source['selected_core'] == 'Nymashock'
            and len(source['disc']['tracks']) == 1 and source['disc']['tracks'][0]['sha256'] == program['disc_track_sha256'],
            'Unsupported compact original disc or starting condition.')
    runtime = Path(run['runtime']).resolve(strict=True)
    for name in ('dll', 'gamedb'):
        require((folder / 'host' / name).resolve(strict=True) == (runtime / name).resolve(strict=True), 'Shared runtime junction changed.')
    require(runtime_files(runtime) == run['runtime_files'], 'Shared runtime gained, lost or changed a file.')
    stock = Path(source['emulator_files']['EmuHawk.exe']['path']).parent.resolve(strict=True)
    distributed = runtime_files(stock)
    ordinary = {k: v for k, v in run['runtime_files'].items() if k not in ('dll/shock.wbx', 'dll/shock.wbx.zst')}
    require(set(ordinary) == set(distributed) - {'dll/shock.wbx.zst'}
            and all((v['bytes'], v['sha256']) == (distributed[k]['bytes'], distributed[k]['sha256']) for k, v in ordinary.items()),
            'Compact managed libraries or game database differ from the distributed runtime.')
    profile = run['observer_profile']
    if profile is not None:
        header_pins = {k: run['source_pins'][k + '_header'] for k in ('entry', 'flow', 'return', 'sdk')}
        qualify_reused_profile(profile, json.loads(snapshots['qualification']), header_pins, run['source_pins']['historical_native_producer'])
        historical = json.loads(snapshots['historical_manifest'])
        require(historical['observer_profile'] == profile, 'Historical native profile changed in transit.')
        require(run['runtime_files']['dll/shock.wbx.zst']['sha256'] == profile['compressed_core']['sha256'], 'Native core differs from qualification.')
        if 'dll/shock.wbx' in run['runtime_files']:
            require(run['runtime_files']['dll/shock.wbx']['sha256'] == profile['core']['sha256'], 'Unpacked observer core shadows a different body.')
    else:
        require('dll/shock.wbx' not in run['runtime_files']
                and run['runtime_files']['dll/shock.wbx.zst']['sha256'] == STOCK_RUNTIME['dll/shock.wbx.zst'], 'Distributed core differs.')
    for item in run['compiler_inputs']:
        verify(item['path'], item)
    command = json.loads((folder / 'compile-command.json').read_text())
    required_flags = ['/nologo', '/target:exe', '/platform:x64', '/langversion:12', '/main:Lsd.Research.Headless.RecordDispatchHistory',
                      '/nostdlib+', '/deterministic+', '/warnaserror+']
    require(command[1] == 'exec' and str(Path(command[2]).resolve()) == run['compiler_inputs'][0]['path']
            and [v for v in command[3:] if v.startswith('/') and not v.startswith(('/reference:', '/out:'))] == required_flags
            and [str(Path(v[len('/reference:'):]).resolve()) for v in command if v.startswith('/reference:')]
                == [p['path'] for p in run['compiler_inputs'][1:]]
            and [v for v in command if v.startswith('/out:')] == ['/out:' + run['host_binary']['path']]
            and [v for v in command if v.lower().endswith('.cs')]
                == [run['source_snapshots']['host_' + p.stem]['path'] for p in legacy.HOST_SOURCES],
            'Unqualified compiler, reference, source or output selection.')
    expected_command = [run['host_binary']['path'], str(folder / 'host'), source['disc']['cue']['path'],
                        *(source['bios'][k]['path'] for k in ('J', 'U', 'E')), str(folder / 'submitted.tsv'),
                        str(folder / 'settings.json'), str(folder / 'observations')]
    require(run['command'] == expected_command, 'Recorded launch arguments differ from their complete pinned inputs.')
    native = validate_outputs(folder, settings, program)
    output = folder / 'observations'
    entries, entry_report, flow_report, return_report, sdk_report = [], {}, {}, {}, {}
    returns, sdk, return_payload, sdk_payload = [], [], b'', b''
    if profile is not None:
        game = snapshots['executable']
        entries, entry_report = validate_entries(rows(output / 'method-instructions.tsv', ENTRY_FIELDS), program,
                                                 selected['selected'], read_payload(output, 'method-code.bin'), game)
        validate_native_summary(json.loads((output / 'method-trace-summary.json').read_text()), native, settings, entries)
        flow_report, _ = validate_flow(read_payload(output, 'method-flow.bin'), json.loads((output / 'method-flow-summary.json').read_text()),
                                       entries, program, game)
        return_payload = read_payload(output, 'method-return-data.bin')
        return_report, returns = validate_returns(read_payload(output, 'method-returns.bin'), return_payload,
            json.loads((output / 'method-return-summary.json').read_text()), entries, selected['return_trace'], selected['selected'], game, program)
        sdk_payload = read_payload(output, 'sdk-read-data.bin')
        sdk_summary = json.loads((output / 'sdk-read-summary.json').read_text())
        sdk_report, sdk = validate_records(read_payload(output, 'sdk-reads.bin'), sdk_payload, sdk_summary,
                                           selected['return_trace']['sdk_targets'], game, program)
        require(all(r['frame'] <= settings['frames'] for r in sdk + returns), 'Native trace extends beyond the actual compact window.')
    else:
        require(native['instruction_entries'] == 0 and not any((output / name).exists() for name in
            ('method-instructions.tsv', 'method-returns.bin', 'sdk-reads.bin', 'method-flow.bin')), 'A stock capture claims native observation.')
        sdk_summary = None
    report = dict(status='qualified_compact_method_history', frames=native['frames_advanced'], RAM_samples=native['RAM_samples'],
                  PNG_checkpoints=len(native['checkpoints']), complete_PCM_bytes=native['complete_PCM_bytes'],
                  complete_PCM_sha256=native['complete_PCM_sha256'], observing=profile is not None,
                  method_entries=entry_report, caller_flow=flow_report, original_returns=return_report, SDK=sdk_report,
                  runtime_copies=0, disc_copies=0, asset_tree_copies=0, new_C_bytes=0, whole_feature_groups_accepted=0,
                  complete_state_parity_checked=False, original_hardware_timing_verified=False)
    return dict(report=report, folder=folder, native=native, program=program, settings=settings, run=run,
                entries=entries, returns=returns, return_payload=return_payload, sdk=sdk, sdk_payload=sdk_payload,
                sdk_summary=sdk_summary, executable=snapshots['executable'])

def inspect(folder):
    return inspect_details(folder)['report']

def compare(reference, candidate, mode):
    left, right = inspect_details(reference), inspect_details(candidate)
    require(mode in ('original-rebuilt', 'observer-stock') and left['report']['observing']
            and right['report']['observing'] == (mode == 'original-rebuilt'), 'Unsupported compact comparison roles.')
    require(left['program'] == right['program'], 'Compact comparison controller profiles differ.')
    report = compare_outputs(left['folder'], right['folder'], left['native'], right['native'])
    if mode == 'original-rebuilt':
        for name in ('method-code.bin', 'method-instructions.tsv', 'method-flow.bin', 'method-returns.bin',
                     'method-return-data.bin', 'sdk-reads.bin', 'sdk-read-data.bin'):
            require(read_payload(left['folder'] / 'observations', name) == read_payload(right['folder'] / 'observations', name),
                    'Original/rebuilt native stream bytes differ: ' + name)
    return dict(status='compact_output_windows_equal', comparison=mode, **report, new_C_bytes=0, whole_feature_groups_accepted=0)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='operation', required=True)
    one = sub.add_parser('inspect'); one.add_argument('folder', type=Path)
    pair = sub.add_parser('compare'); pair.add_argument('reference', type=Path); pair.add_argument('candidate', type=Path)
    pair.add_argument('--mode', choices=('original-rebuilt', 'observer-stock'), required=True)
    for item in (one, pair): item.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        report = inspect(args.folder) if args.operation == 'inspect' else compare(args.reference, args.candidate, args.mode)
        if args.output is not None: write_json(args.output, report)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps(dict(status='rejected', error=str(error))), file=sys.stderr)
        return 1
    print(json.dumps(report))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
