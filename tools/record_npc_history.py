"""Record a static PS1 controller history, optionally with an NPC entry observer.

The supplied emulator, capture, game and BIOS remain inputs. Every run builds
and launches its own hidden host, records its actual runtime identities, and
keeps complete audio and selected raw buffers. Comparison is a separate step.
"""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_npc_observer import OBSERVER, SOURCE_SHA256, UPSTREAM, MEDNAFEN
from tools.replay_cold_start_headless import require, select_compiler, write_json
from tools.runtime_inputs import load_verified_manifest, record_file

DEFAULT_PROGRAM = ROOT / 'research/headless/buddha-timed-route.json'
HOST_SOURCES = tuple(ROOT / 'research/headless' / name for name in
                     ('ReplayColdStart.cs', 'RecordNpcHistory.cs', 'NpcInstructionTrace.cs'))
STOCK_RUNTIME = {
    'dll/shock.wbx.zst': '5c6fe90fadd670318ca74993911b171e15b167c7f2e1e88bf66de4661fc24126',
    'dll/BizHawk.Common.dll': '15ebdf860bc1d8d9efcaabefe1df69de0b24f31d431b558621df353882f386b9',
    'dll/BizHawk.BizInvoke.dll': '36784436af64e6547a1e6155071eab104ca09d9b2d5fe1d73c7282cee500bffb',
    'dll/BizHawk.Emulation.Common.dll': 'f557d94912b12bde18413b60d25b3e61332b7bbfc7184349d1289d6ba9f350ee',
    'dll/BizHawk.Emulation.Cores.dll': '444bc157418e9b5df5d07e987fc7ad1d2d1c6993676f5b864368027cb4f054d5',
    'dll/waterboxhost.dll': 'e8e47426941a710c7ceea98fb0833b8387de1952f54ca0fa40001cd494507cee',
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def digest_text(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def clean_name(value):
    return isinstance(value, str) and bool(value) and not any(char in value for char in '\t\r\n')


def validate_program(program):
    require(isinstance(program, dict) and program.get('schema_version') == 1, 'Unsupported controller program schema.')
    frames = program.get('frames')
    require(type(frames) is int and 1 <= frames <= 30000, 'The controller program supports 1 through 30000 input frames.')
    require(digest_text(program.get('executable_sha256')) and digest_text(program.get('disc_track_sha256')),
            'The program must identify its canonical executable and complete disc track.')
    controller = program.get('controller', {})
    buttons, axes, order = (controller.get(name) for name in ('buttons', 'axes', 'column_order'))
    require(isinstance(buttons, list) and buttons and all(clean_name(name) for name in buttons)
            and len(buttons) == len(set(buttons)), 'Button names must be unique nonempty TSV fields.')
    require(isinstance(axes, dict) and all(clean_name(name) and type(value) is int and -(2**31) <= value < 2**31
                                         for name, value in axes.items()), 'Invalid neutral controller axes.')
    require(not set(buttons) & set(axes) and isinstance(order, list) and all(clean_name(name) for name in order)
            and len(order) == len(set(order)) and set(order) == set(buttons) | set(axes),
            'Controller columns must name each button and axis exactly once.')
    segments = program.get('segments')
    require(isinstance(segments, list) and segments, 'The controller program needs contiguous input segments.')
    previous = 0
    for segment in segments:
        require(isinstance(segment, dict), 'Invalid controller segment.')
        until, phase, pressed = (segment.get(name) for name in ('until', 'phase', 'pressed'))
        require(type(until) is int and previous < until <= frames and clean_name(phase),
                'Input segments must advance consecutively to the declared final frame.')
        require(isinstance(pressed, list) and all(isinstance(name, str) for name in pressed)
                and len(pressed) == len(set(pressed)) and set(pressed) <= set(buttons),
                'A segment contains an unknown or repeated button.')
        previous = until
    require(previous == frames, 'Input segments do not cover the complete program.')
    checkpoints = program.get('checkpoint_frames')
    require(isinstance(checkpoints, list) and 2 <= len(checkpoints) <= 256
            and all(type(frame) is int and 0 <= frame <= frames for frame in checkpoints)
            and checkpoints == sorted(set(checkpoints)) and checkpoints[0] == 0 and checkpoints[-1] == frames,
            'Use sorted unique checkpoint frames, including zero and the final frame, with at most 256 captures.')
    interval = program.get('RAM_sample_interval')
    require(type(interval) is int and 1 <= interval <= frames, 'Invalid RAM observation interval.')
    trace = program.get('trace', {})
    try:
        pc = int(trace['watched_pc'], 0)
    except (KeyError, TypeError, ValueError):
        raise ValueError('The program needs a hexadecimal watched instruction address.') from None
    require(pc % 4 == 0 and 0x80010000 <= pc < 0x80200000, 'The watched PC must be a word-aligned game RAM address.')
    require(type(trace.get('arm_frame')) is int and 0 <= trace['arm_frame'] <= frames,
            'The observer arm frame lies outside the controller program.')
    require(type(trace.get('function_bytes')) is int and trace['function_bytes'] > 0
            and trace['function_bytes'] % 4 == 0 and digest_text(trace.get('function_sha256')),
            'Identify the complete original function containing the watched entry.')
    require(trace.get('context_tick_offset') == 0xA0, 'This observer reads the original entity tick at offset 0xA0.')
    require(type(trace.get('expected_entries')) is int and trace['expected_entries'] >= 0,
            'Declare the expected entry count for this complete recorded profile.')
    first, last = trace.get('expected_first_frame'), trace.get('expected_last_frame')
    require(type(first) is int and type(last) is int and
            ((0 <= first <= last <= frames) if trace['expected_entries'] else first == last == -1),
            'Invalid expected entry observation window.')
    require(type(trace.get('entity_id')) is int and 0 <= trace['entity_id'] < 2**31,
            'Identify the original entity ID for this single-entity history.')
    if 'expanded_submitted_sha256' in program:
        require(digest_text(program['expanded_submitted_sha256']), 'Invalid expanded-input checksum.')
    return program


def expand_program(program, frames=None):
    program = validate_program(program)
    frames = program['frames'] if frames is None else frames
    require(type(frames) is int and 1 <= frames <= program['frames'], 'Choose an input window within the controller program.')
    controller = program['controller']
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
    writer.writerow(('relative_frame', 'core_frame', 'phase', 'buttons', *controller['column_order']))
    segment_index = 0
    for frame in range(1, frames + 1):
        while frame > program['segments'][segment_index]['until']:
            segment_index += 1
        segment = program['segments'][segment_index]
        pressed = set(segment['pressed'])
        summary = ';'.join(name for name in controller['buttons'] if name in pressed)
        values = [('true' if name in pressed else 'false') if name in controller['buttons'] else str(controller['axes'][name])
                  for name in controller['column_order']]
        writer.writerow((frame, frame, segment['phase'], summary, *values))
    data = stream.getvalue().encode('utf-8')
    if frames == program['frames'] and 'expanded_submitted_sha256' in program:
        require(sha256(data) == program['expanded_submitted_sha256'], 'Expanded controller inputs differ from the recorded program checksum.')
    return data


def load_observer_profile(path):
    path = Path(path).resolve(strict=True)
    profile = json.loads(path.read_text(encoding='utf-8-sig'))
    require(profile.get('schema_version') == 1 and profile.get('status') == 'built_separate_NPC_observer_core',
            'Use a profile generated by tools/build_npc_observer.py.')
    require(profile.get('upstream_commit') == UPSTREAM and profile.get('mednafen_commit') == MEDNAFEN
            and profile.get('original_adapter_sha256') == SOURCE_SHA256['shock.cpp']
            and profile.get('existing_CPU_source_modified') is False and profile.get('input_files_preserved') is True,
            'The observer profile has an unsupported source or CPU provenance.')
    require(profile.get('observer_header_sha256') == record_file(OBSERVER)['sha256']
            and profile.get('producer_sha256') == record_file(ROOT / 'tools/build_npc_observer.py')['sha256'],
            'Rebuild the observer profile with the current published source.')
    files = []
    for key, filename in (('core', 'shock.wbx'), ('compressed_core', 'shock.wbx.zst')):
        item = profile.get(key, {})
        require(item.get('file') == filename and type(item.get('bytes')) is int and digest_text(item.get('sha256')),
                'The observer profile omits a complete core artifact identity.')
        candidate = (path.parent / filename).resolve(strict=True)
        require(candidate.parent == path.parent, 'Keep observer core artifacts inside their profile directory.')
        actual = record_file(candidate)
        require((actual['bytes'], actual['sha256']) == (item['bytes'], item['sha256']),
                'An observer core artifact differs from its build profile.')
        files.append(candidate)
    return profile, files


def record(capture_folder, workspace, program_file=DEFAULT_PROGRAM, observer_profile=None, frames=None, dotnet=None):
    workspace = Path(workspace).resolve()
    require(not workspace.exists(), 'Choose a new workspace; existing evidence is preserved.')
    require(os.name == 'nt' and sys.maxsize > 2**32, 'The qualified recorder requires 64-bit Windows.')
    program_file = Path(program_file).resolve(strict=True)
    program = validate_program(json.loads(program_file.read_text(encoding='utf-8-sig')))
    submitted = expand_program(program, frames)
    frames = program['frames'] if frames is None else frames
    capture = Path(capture_folder).resolve(strict=True)
    manifest = load_verified_manifest(capture)
    require(manifest is not None and manifest['schema_version'] == 2 and manifest['selected_core'] == 'Nymashock'
            and manifest['scenario'] == 'boot' and manifest['start_kind'] == 'cold_boot' and manifest['start_state'] is None,
            'Use a verified default-core cold-boot capture as the source of local launch inputs.')
    require(len(manifest['disc']['tracks']) == 1 and manifest['disc']['tracks'][0]['sha256'] == program['disc_track_sha256'],
            'The complete disc track does not match this recorded controller profile.')
    runtime = Path(manifest['emulator_files']['EmuHawk.exe']['path']).parent.resolve(strict=True)
    require(not workspace.is_relative_to(capture) and not workspace.is_relative_to(runtime),
            'Keep recording output outside the source capture and supplied emulator.')
    configuration = json.loads(Path(manifest['configuration']['path']).read_text(encoding='utf-8-sig'))
    for section in ('CoreSettings', 'CoreSyncSettings'):
        require(not any('Nymashock' in name and value for name, value in configuration.get(section, {}).items()),
                'Only default Nymashock settings are qualified.')
    require(all(record_file(runtime / name)['sha256'] == expected for name, expected in STOCK_RUNTIME.items()),
            'Use the qualified distributed BizHawk 2.11.1 runtime; observer cores are supplied separately.')
    require(not (runtime / 'dll/shock.wbx').exists(),
            'The distributed runtime must contain only its compressed shock.wbx.zst; an unpacked core could shadow it.')
    profile, core_files = None, []
    if observer_profile is not None:
        observer_profile = Path(observer_profile).resolve(strict=True)
        require(not workspace.is_relative_to(observer_profile.parent), 'Keep recording output outside the observer build.')
        profile, core_files = load_observer_profile(observer_profile)
    dotnet = str(dotnet or shutil.which('dotnet') or Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'dotnet/dotnet.exe')
    compiler = select_compiler(subprocess.check_output([dotnet, '--list-sdks'], text=True))
    framework = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319'
    source_paths = [*HOST_SOURCES, OBSERVER, program_file, Path(__file__).resolve(), ROOT / 'tools/build_npc_observer.py',
                    ROOT / 'tools/replay_cold_start_headless.py', ROOT / 'tools/runtime_inputs.py', compiler,
                    *(core_files + [observer_profile] if observer_profile else [])]
    source_pins = [record_file(path) for path in source_paths]
    runtime_paths = [path for name in ('dll', 'gamedb') for path in sorted((runtime / name).rglob('*')) if path.is_file()]
    runtime_paths.append(runtime / 'EmuHawk.exe.config')
    runtime_pins = [record_file(path) for path in runtime_paths]
    workspace.mkdir(parents=True, exist_ok=False)
    host = workspace / 'host'
    host.mkdir()
    for name in ('dll', 'gamedb'):
        shutil.copytree(runtime / name, host / name)
    for path in core_files:
        shutil.copyfile(path, host / 'dll' / path.name)
    executable = host / 'RecordNpcHistory.exe'
    shutil.copyfile(runtime / 'EmuHawk.exe.config', executable.with_suffix('.exe.config'))
    for path in HOST_SOURCES:
        shutil.copyfile(path, host / path.name)
    copied_host_sources = {path.name: record_file(host / path.name) for path in HOST_SOURCES}
    sources = workspace / 'sources'
    sources.mkdir()
    source_snapshots = []
    for index, (path, expected) in enumerate(zip(source_paths, source_pins)):
        target = sources / (str(index).zfill(2) + '-' + path.name)
        shutil.copyfile(path, target)
        actual = record_file(target)
        require((actual['bytes'], actual['sha256']) == (expected['bytes'], expected['sha256']),
                'A retained source copy differs from its input.')
        source_snapshots.append(dict(original=expected, file=str(target.relative_to(workspace)).replace('\\', '/'),
                                     bytes=actual['bytes'], sha256=actual['sha256']))
    (workspace / 'submitted.tsv').open('xb').write(submitted)
    shutil.copyfile(program_file, workspace / 'program.json')
    checkpoint_frames = sorted({value for value in program['checkpoint_frames'] if value <= frames} | {0, frames})
    settings = dict(frames=frames, checkpoint_frames=checkpoint_frames,
        RAM_sample_interval=program['RAM_sample_interval'], trace_enabled=profile is not None,
        watched_pc=int(program['trace']['watched_pc'], 0), arm_frame=program['trace']['arm_frame'])
    write_json(workspace / 'settings.json', settings)
    references = [framework / name for name in ('mscorlib.dll', 'System.dll', 'System.Core.dll',
        'System.Web.Extensions.dll', 'System.Drawing.dll', 'netstandard.dll')]
    references += [host / 'dll' / name for name in ('BizHawk.Common.dll', 'BizHawk.BizInvoke.dll',
        'BizHawk.Emulation.Common.dll', 'BizHawk.Emulation.Cores.dll', 'BizHawk.Emulation.DiscSystem.dll', 'System.ValueTuple.dll')]
    require(all(path.is_file() for path in references), 'Required framework/core reference assemblies are absent.')
    command = [dotnet, 'exec', str(compiler), '/nologo', '/target:exe', '/platform:x64', '/langversion:12',
        '/main:Lsd.Research.Headless.RecordNpcHistory', '/nostdlib+', '/deterministic+',
        *('/reference:' + str(path) for path in references), '/out:' + str(executable),
        *(str(host / path.name) for path in HOST_SOURCES)]
    write_json(workspace / 'compile-command.json', command)
    with (workspace / 'compiler.log').open('xb') as log:
        built = subprocess.run(command, stdout=log, stderr=log)
    require(built.returncode == 0, 'The owned recorder build failed; see compiler.log.')
    actual_runtime = {str(path.relative_to(host)).replace('\\', '/'): record_file(path)
        for name in ('dll', 'gamedb') for path in sorted((host / name).rglob('*')) if path.is_file()}
    output = workspace / 'observations'
    launch = [str(executable), str(host), manifest['disc']['cue']['path'],
        *(manifest['bios'][key]['path'] for key in ('J', 'U', 'E')),
        str(workspace / 'submitted.tsv'), str(workspace / 'settings.json'), str(output)]
    run_inputs = dict(schema_version=1, source_manifest=manifest, source_capture=str(capture),
        source_capture_manifest=record_file(capture / 'inputs.json'), source_pins=source_pins,
        source_snapshots=source_snapshots, copied_host_sources=copied_host_sources,
        supplied_runtime_pins=runtime_pins, actual_runtime_files=actual_runtime,
        program=program, program_file=record_file(workspace / 'program.json'),
        submitted=record_file(workspace / 'submitted.tsv'), settings=settings,
        settings_file=record_file(workspace / 'settings.json'), host_binary=record_file(executable),
        host_configuration=record_file(executable.with_suffix('.exe.config')),
        observer_profile=profile, runtime_kind='npc_observer' if profile else 'distributed',
        command=launch, game_RAM_injected=False, restored_state=False, emulator_UI_controlled=False)
    write_json(workspace / 'run-inputs.json', run_inputs)
    with (workspace / 'host.out.log').open('xb') as stdout, (workspace / 'host.err.log').open('xb') as stderr:
        process = subprocess.Popen(launch, cwd=host, stdout=stdout, stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        write_json(workspace / 'process.json', dict(pid=process.pid, executable=str(executable), command=launch))
        print(json.dumps(dict(status='recording_owned_NPC_history', pid=process.pid,
                              runtime_kind=run_inputs['runtime_kind'], input_frames=frames)), flush=True)
        try:
            code = process.wait()
        except BaseException:
            process.terminate()
            process.wait()
            raise
    write_json(workspace / 'exit.json', dict(pid=process.pid, exit_code=code))
    require([record_file(path) for path in source_paths] == source_pins
            and [record_file(path) for path in runtime_paths] == runtime_pins,
            'A source, provided runtime or observer build input changed during recording.')
    require(load_verified_manifest(capture) == manifest, 'Pinned original disc, BIOS or launch inputs changed.')
    require({name: record_file(value['path']) for name, value in actual_runtime.items()} == actual_runtime,
            'An owned runtime file changed during recording.')
    require({str(path.relative_to(host)).replace('\\', '/') for name in ('dll', 'gamedb')
             for path in (host / name).rglob('*') if path.is_file()} == set(actual_runtime),
            'The owned runtime gained or lost a file during recording.')
    require({name: record_file(value['path']) for name, value in copied_host_sources.items()} == copied_host_sources
            and record_file(executable) == run_inputs['host_binary']
            and record_file(executable.with_suffix('.exe.config')) == run_inputs['host_configuration'],
            'A compiled host input or binary changed during recording.')
    for item in source_snapshots:
        actual = record_file(workspace / item['file'])
        require((actual['bytes'], actual['sha256']) == (item['bytes'], item['sha256']),
                'A retained source snapshot changed during recording.')
    require(record_file(workspace / 'submitted.tsv') == run_inputs['submitted']
            and record_file(workspace / 'settings.json') == run_inputs['settings_file']
            and record_file(workspace / 'program.json') == run_inputs['program_file'],
            'Owned controller/settings inputs changed.')
    require(code == 0, 'The owned recorder failed; retain and inspect host.err.log.')
    native = json.loads((output / 'report.json').read_text(encoding='utf-8-sig'))
    require(native['status'] == 'recorded_static_NPC_history' and native['frames_advanced'] == frames + 1,
            'The recorder did not complete its declared observation window.')
    result = dict(status='recorded_pinned_NPC_history', runtime_kind=run_inputs['runtime_kind'],
        input_frames=frames, native_observations=frames + 1, instruction_entries=native['instruction_entries'],
        checkpoint_observations=len(native['checkpoints']), input_files_preserved=True,
        comparison_performed=False, new_C_bytes=0, whole_NPC_encounters_accepted=0, whole_feature_groups_accepted=0,
        complete_state_parity_checked=False, workspace=str(workspace))
    write_json(workspace / 'result.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-folder', type=Path, required=True, help='Existing verified cold-boot launch inputs.')
    parser.add_argument('--workspace', type=Path, required=True, help='New isolated recording directory.')
    parser.add_argument('--program', type=Path, default=DEFAULT_PROGRAM)
    parser.add_argument('--observer-profile', type=Path, help='Optional profile.json from the separate native observer build.')
    parser.add_argument('--frames', type=int, help='Optional prefix of the static program.')
    parser.add_argument('--dotnet', type=Path)
    args = parser.parse_args(argv)
    result = record(args.capture_folder, args.workspace, args.program, args.observer_profile, args.frames, args.dotnet)
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
