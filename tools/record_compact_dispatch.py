"""Record bounded original-method histories using an existing runtime in place.

No runtime, disc or asset tree is copied. The optional historical observer is
accepted only with the published CD-error profile and its retained producer;
the normal current-producer observer loader remains unchanged.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import record_dispatch_history as legacy
from tools.build_dispatch_observer import OBSERVER, FLOW_OBSERVER, RETURN_OBSERVER, SDK_OBSERVER
from tools.build_dispatch_observer import EXPORTS, FLOW_EXPORTS, RETURN_EXPORTS, SDK_EXPORTS
from tools.build_npc_observer import UPSTREAM, MEDNAFEN, SOURCE_SHA256
from tools.compact_dispatch import CAPTURE_LIMIT, archive_payloads, validate_outputs
from tools.compact_dispatch_inputs import selection_paths, context
from tools.dispatch_trace import validate_program, expand_program
from tools.record_npc_activation import junction
from tools.record_npc_history import STOCK_RUNTIME
from tools.replay_cold_start_headless import require, select_compiler, write_json
from tools.runtime_inputs import load_verified_manifest, record_file

DEFAULT_PROGRAM = ROOT / 'research/headless/blocking-cd-retry-route.json'
QUALIFICATION = ROOT / 'docs/cd-error-reset-checks.json'

def runtime_files(runtime):
    return {str(p.relative_to(runtime)).replace('\\', '/'): record_file(p)
            for directory in ('dll', 'gamedb') for p in sorted((runtime / directory).rglob('*')) if p.is_file()}

def qualify_reused_profile(profile, qualification, headers, producer):
    require(profile.get('schema_version') == 1 and profile.get('status') == 'built_separate_dispatch_observer_core'
            and profile.get('upstream_commit') == UPSTREAM and profile.get('mednafen_commit') == MEDNAFEN
            and profile.get('original_adapter_sha256') == SOURCE_SHA256['shock.cpp']
            and profile.get('existing_CPU_source_modified') is False and profile.get('input_files_preserved') is True
            and profile.get('original_game_RAM_written_by_observer') is False
            and profile.get('observer_mode') == 'method_entries', 'Unqualified reused observer source or CPU provenance.')
    require(profile.get('compressed_core') == qualification['native_profile']['compressed_core']
            and profile.get('producer_sha256') == qualification['source_file_SHA256']['tools/build_dispatch_observer.py']
            == producer['sha256'], 'The historical observer body/producer differs from the published CD-error qualification.')
    require(profile.get('observer_header_sha256') == headers['entry']['sha256']
            and profile.get('flow_header_sha256') == headers['flow']['sha256']
            and profile.get('return_header_sha256') == headers['return']['sha256']
            and profile.get('sdk_read_header_sha256') == headers['sdk']['sha256'], 'Historical observer interfaces differ.')
    require(profile.get('flow_protocol') == profile.get('return_protocol') == profile.get('sdk_read_protocol') == 1
            and profile.get('flow_event_bytes') == 664 and profile.get('flow_history_instructions') == 16
            and profile.get('return_event_bytes') == 600 and profile.get('return_frame_payload_bytes') == 8 * 2**20
            and profile.get('sdk_read_event_bytes') == 464 and profile.get('sdk_read_frame_payload_bytes') == 32 * 2**20
            and (set(EXPORTS) | set(FLOW_EXPORTS) | set(RETURN_EXPORTS) | set(SDK_EXPORTS)) <= set(profile.get('exported_functions', []))
            and 'collision_call_protocol' not in profile, 'Unsupported reused native observer transport.')

def reusable_observer(folder):
    folder = Path(folder).resolve(strict=True)
    manifest_path = folder / 'run-inputs.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    profile = manifest['observer_profile']
    found = [r for r in manifest['source_snapshots'] if Path(r['original']['path']).name == 'build_dispatch_observer.py']
    require(len(found) == 1, 'Historical observer must retain exactly one producer snapshot.')
    producer = (folder / found[0]['file']).resolve(strict=True)
    require(producer.is_relative_to(folder), 'Historical native producer escapes its capture.')
    headers = {k: record_file(p) for k, p in {'entry': OBSERVER, 'flow': FLOW_OBSERVER,
                                            'return': RETURN_OBSERVER, 'sdk': SDK_OBSERVER}.items()}
    qualify_reused_profile(profile, json.loads(QUALIFICATION.read_text()), headers, record_file(producer))
    require(record_file(producer)['sha256'] == found[0]['original']['sha256'] == found[0]['sha256'],
            'Retained historical producer differs from its original capture pin.')
    runtime = folder / 'host'
    core = runtime / 'dll/shock.wbx.zst'
    require(record_file(core)['sha256'] == profile['compressed_core']['sha256']
            and core.stat().st_size == profile['compressed_core']['bytes'], 'Reused native compressed core differs.')
    unpacked = runtime / 'dll/shock.wbx'
    if unpacked.exists():
        require(record_file(unpacked)['sha256'] == profile['core']['sha256']
                and unpacked.stat().st_size == profile['core']['bytes'], 'An unpacked core shadows the qualified body.')
    return runtime, profile, dict(historical_manifest=manifest_path, historical_native_producer=producer,
                                  qualification=QUALIFICATION, entry_header=OBSERVER, flow_header=FLOW_OBSERVER,
                                  return_header=RETURN_OBSERVER, sdk_header=SDK_OBSERVER)

def record(capture_folder, workspace, program_file=DEFAULT_PROGRAM, observer_capture=None, frames=None, dotnet=None):
    require(os.name == 'nt' and sys.maxsize > 2**32, 'Compact native recording requires 64-bit Windows.')
    workspace, capture = Path(workspace).resolve(), Path(capture_folder).resolve(strict=True)
    require(not workspace.exists(), 'Choose a new workspace; preserve existing evidence.')
    program_file = Path(program_file).resolve(strict=True)
    program = validate_program(json.loads(program_file.read_text(encoding='utf-8-sig')))
    frames = program['frames'] if frames is None else frames
    submitted = expand_program(program, frames)
    require(type(frames) is int and program['method_trace']['arm_frame'] <= frames <= program['frames'],
            'Compact capture must include its declared observer arm boundary.')
    paths = selection_paths(program)
    selected = context(program, {k: p.read_bytes() for k, p in paths.items()})
    manifest = load_verified_manifest(capture)
    require(manifest and manifest['schema_version'] == 2 and manifest['selected_core'] == 'Nymashock'
            and manifest['scenario'] == 'boot' and manifest['start_kind'] == 'cold_boot' and manifest['start_state'] is None
            and len(manifest['disc']['tracks']) == 1 and manifest['disc']['tracks'][0]['sha256'] == program['disc_track_sha256'],
            'Use the verified default-core cold-boot disc/BIOS inputs for this controller program.')
    stock = Path(manifest['emulator_files']['EmuHawk.exe']['path']).parent.resolve(strict=True)
    require(all(record_file(stock / k)['sha256'] == v for k, v in STOCK_RUNTIME.items())
            and not (stock / 'dll/shock.wbx').exists(), 'Use the qualified distributed runtime without an unpacked core shadow.')
    configuration = json.loads(Path(manifest['configuration']['path']).read_text(encoding='utf-8-sig'))
    require(all(not any('Nymashock' in n and v for n, v in configuration.get(section, {}).items())
                for section in ('CoreSettings', 'CoreSyncSettings')), 'Require default Nymashock settings.')
    runtime, profile, extra = stock, None, {}
    if observer_capture is not None:
        runtime, profile, extra = reusable_observer(observer_capture)
    require(not workspace.is_relative_to(capture) and not workspace.is_relative_to(runtime), 'Keep outputs outside retained inputs/runtime.')
    runtime_pins = runtime_files(runtime)
    stock_pins = runtime_files(stock)
    ordinary = {k: v for k, v in runtime_pins.items() if k not in ('dll/shock.wbx', 'dll/shock.wbx.zst')}
    require(set(ordinary) == set(stock_pins) - {'dll/shock.wbx.zst'}
            and all((v['bytes'], v['sha256']) == (stock_pins[k]['bytes'], stock_pins[k]['sha256']) for k, v in ordinary.items()),
            'Reused managed libraries/game database differ from the distributed runtime.')
    checkpoints = sorted({v for v in program['checkpoint_frames'] if v <= frames} | {0, frames})
    require(len(checkpoints) <= 4, 'Compact capture retains at most four PNG checkpoints.')
    settings = dict(frames=frames, checkpoint_frames=checkpoints, RAM_sample_interval=program['RAM_sample_interval'],
                    trace_enabled=profile is not None, arm_frame=program['method_trace']['arm_frame'],
                    dispatch_targets=selected['dispatch_targets'], dispatch_words=selected['dispatch_words'],
                    flow_sites=selected['flow_sites'], return_trace=selected['return_trace'],
                    collision_calls=None, serialized_state=False, compact_capture=True)
    framework = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319'
    dotnet = str(dotnet or shutil.which('dotnet') or Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'dotnet/dotnet.exe')
    compiler = select_compiler(subprocess.check_output([dotnet, '--list-sdks'], text=True))
    source_paths = dict(paths)
    source_paths.update({'host_' + p.stem: p for p in legacy.HOST_SOURCES})
    source_paths.update(extra)
    for name in ('record_compact_dispatch', 'compact_dispatch', 'compact_dispatch_inputs', 'dispatch_trace', 'dispatch_returns',
                 'dispatch_flow', 'inspect_dispatch_history', 'inspect_sdk_reads', 'sdk_reads', 'runtime_inputs', 'psx_image'):
        source_paths['tool_' + name] = ROOT / 'tools' / (name + '.py')
    source_paths['program'] = program_file
    source_pins = {k: record_file(p) for k, p in source_paths.items()}
    workspace.mkdir(parents=True)
    host, snapshots = workspace / 'host', workspace / 'sources'
    host.mkdir(); snapshots.mkdir()
    for name in ('dll', 'gamedb'):
        junction(host / name, (runtime / name).resolve(strict=True))
    executable = host / 'RecordDispatchHistory.exe'
    shutil.copyfile(stock / 'EmuHawk.exe.config', executable.with_suffix('.exe.config'))
    saved = {}
    for index, (key, path) in enumerate(source_paths.items()):
        target = snapshots / (f'{index:02d}-' + path.name)
        shutil.copyfile(path, target)
        copied = record_file(target)
        require((copied['bytes'], copied['sha256']) == (source_pins[key]['bytes'], source_pins[key]['sha256']), 'Source snapshot differs.')
        saved[key] = dict(file=target.relative_to(workspace).as_posix(), **copied)
    (workspace / 'submitted.tsv').write_bytes(submitted)
    shutil.copyfile(program_file, workspace / 'program.json')
    write_json(workspace / 'settings.json', settings)
    references = [framework / name for name in ('mscorlib.dll', 'System.dll', 'System.Core.dll', 'System.Web.Extensions.dll', 'System.Drawing.dll', 'netstandard.dll')]
    references += [host / 'dll' / name for name in ('BizHawk.Common.dll', 'BizHawk.BizInvoke.dll', 'BizHawk.Emulation.Common.dll',
                    'BizHawk.Emulation.Cores.dll', 'BizHawk.Emulation.DiscSystem.dll', 'System.ValueTuple.dll')]
    compiler_pins = [record_file(compiler)] + [record_file(p) for p in references]
    command = [dotnet, 'exec', str(compiler), '/nologo', '/target:exe', '/platform:x64', '/langversion:12',
               '/main:Lsd.Research.Headless.RecordDispatchHistory', '/nostdlib+', '/deterministic+', '/warnaserror+',
               *('/reference:' + str(p) for p in references), '/out:' + str(executable),
               *str_paths(workspace, saved)]
    write_json(workspace / 'compile-command.json', command)
    with (workspace / 'compiler.log').open('xb') as log:
        built = subprocess.run(command, cwd=host, stdout=log, stderr=subprocess.STDOUT)
    require(built.returncode == 0, 'Compact host build failed; preserve compiler.log.')
    launch = [str(executable), str(host), manifest['disc']['cue']['path'], *(manifest['bios'][k]['path'] for k in ('J', 'U', 'E')),
              str(workspace / 'submitted.tsv'), str(workspace / 'settings.json'), str(workspace / 'observations')]
    run = dict(schema_version=1, kind='compact_original_method_history', source_capture=str(capture), source_manifest=manifest,
               source_capture_manifest=record_file(capture / 'inputs.json'), source_pins=source_pins, source_snapshots=saved,
               runtime=str(runtime.resolve()), runtime_files=runtime_pins, observer_profile=profile,
               compiler_inputs=compiler_pins, settings=settings, program_file=record_file(workspace / 'program.json'),
               settings_file=record_file(workspace / 'settings.json'), submitted=record_file(workspace / 'submitted.tsv'),
               host_binary=record_file(executable), host_configuration=record_file(executable.with_suffix('.exe.config')),
               compile_command=record_file(workspace / 'compile-command.json'), command=launch,
               runtime_copies=0, disc_copies=0, asset_tree_copies=0, game_RAM_injected=False, restored_state=False, emulator_UI_controlled=False)
    write_json(workspace / 'run-inputs.json', run)
    with (workspace / 'host.out.log').open('xb') as stdout, (workspace / 'host.err.log').open('xb') as stderr:
        child = subprocess.Popen(launch, cwd=host, stdout=stdout, stderr=stderr,
                                 creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        write_json(workspace / 'process.json', dict(pid=child.pid, command=launch))
        print(json.dumps(dict(status='recording_compact_dispatch', pid=child.pid, frames=frames)), flush=True)
        try:
            code = child.wait()
        except BaseException:
            child.terminate(); child.wait()
            raise
    write_json(workspace / 'exit.json', dict(pid=child.pid, exit_code=code))
    require(code == 0, 'Owned compact host failed; preserve host.err.log.')
    require(source_pins == {k: record_file(p) for k, p in source_paths.items()} and runtime_files(runtime) == runtime_pins
            and load_verified_manifest(capture) == manifest and compiler_pins == [record_file(compiler)] + [record_file(p) for p in references],
            'A compact producer, compiler, shared runtime or original input changed.')
    require(sum(p.stat().st_size for p in (workspace / 'observations').iterdir() if p.is_file()) < CAPTURE_LIMIT, 'Capture exceeded 128 MiB.')
    archives = archive_payloads(workspace / 'observations')
    native = validate_outputs(workspace, settings, program)
    result = dict(status='recorded_compact_dispatch_history', frames=native['frames_advanced'], payload_archives=len(archives),
                  runtime_copies=0, disc_copies=0, asset_tree_copies=0, comparison_performed=False, new_C_bytes=0,
                  whole_feature_groups_accepted=0, complete_state_parity_checked=False, workspace=str(workspace))
    write_json(workspace / 'result.json', result)
    return result

def str_paths(workspace, saved):
    return [str(workspace / saved['host_' + p.stem]['file']) for p in legacy.HOST_SOURCES]

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture_folder', type=Path)
    parser.add_argument('workspace', type=Path)
    parser.add_argument('--program', type=Path, default=DEFAULT_PROGRAM)
    parser.add_argument('--observer-capture', type=Path, help='Existing published CD-error observer capture; omit for stock.')
    parser.add_argument('--frames', type=int)
    parser.add_argument('--dotnet')
    args = parser.parse_args(argv)
    try:
        result = record(args.capture_folder, args.workspace, args.program, args.observer_capture, args.frames, args.dotnet)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(json.dumps(dict(status='failed', error=str(error))), file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
