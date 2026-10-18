"""Replay a pinned cold-start capture in an isolated BizHawk PS1 core.

Requires Windows, .NET Framework 4.8 and an installed .NET SDK 8 or later.
The original emulator UI, game inputs and saves are never controlled or written.
The managed host belongs to analysis tooling; the matching game retains its
original GCC/MIPS build. No game files or emulator binaries are distributed.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.compare_cold_start import inspect_run, read_tsv, validate_frame_count
from tools.runtime_inputs import load_verified_manifest, record_file

HOST_SOURCE = ROOT / 'research/headless/ReplayColdStart.cs'
TRACE_FIELDS = ('relative_frame', 'core_frame', 'phase', 'gpu_sha256', 'gpu_equal',
                'sample_frames', 'total_sample_frames')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def select_compiler(sdk_list):
    candidates = []
    for line in sdk_list.splitlines():
        match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+) \[(.+)\]', line.strip())
        if match and int(match[1]) >= 8:
            version = tuple(int(match[index]) for index in (1, 2, 3))
            candidates.append((version, Path(match[4]) / '.'.join(map(str, version)) / 'Roslyn/bincore/csc.dll'))
    require(candidates, 'A stable installed .NET SDK 8 or later is required to build the recorder.')
    return max(candidates, key=lambda item: item[0])[1]


def audio_window(pcm, reference_wave, sample_counts, dump_frames):
    """Keep all headless audio; compare the GUI writer's declared frame window."""
    require(type(dump_frames) is int and dump_frames > 0 and len(sample_counts) == dump_frames + 1,
            'The audio comparison needs the dump window and its extra observation boundary.')
    require(all(type(value) is int and value >= 0 for value in sample_counts), 'Invalid per-frame PCM counts.')
    require(len(pcm) == sum(sample_counts) * 4, 'The complete headless PCM is truncated or has trailing bytes.')
    with wave.open(str(reference_wave), 'rb') as source:
        require((source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype()) ==
                (2, 2, 44100, 'NONE'), 'Expected complete 44,100 Hz stereo 16-bit reference PCM.')
        expected = source.readframes(source.getnframes())
    limit = sum(sample_counts[:dump_frames]) * 4
    require(len(expected) == limit, 'The complete reference WAV disagrees with its declared dump-frame window.')
    actual, tail = pcm[:limit], pcm[limit:]
    return dict(equal=actual == expected, GUI_dump_frames=dump_frames,
        GUI_dump_PCM_sample_frames=limit // 4, headless_all_PCM_sample_frames=len(pcm) // 4,
        extra_observer_frame_PCM_sample_frames=len(tail) // 4,
        reference_PCM_sha256=hashlib.sha256(expected).hexdigest(),
        headless_dump_window_PCM_sha256=hashlib.sha256(actual).hexdigest(),
        complete_headless_PCM_sha256=hashlib.sha256(pcm).hexdigest(),
        retained_extra_observer_PCM_sha256=hashlib.sha256(tail).hexdigest(),
        complete_headless_PCM_preserved=True)


def validate_trace(rows, reference, frames):
    require(len(rows) == len(reference) == frames + 1, 'Missing headless or reference observation boundaries.')
    total, counts, gpu_differences = 0, [], 0
    for frame, (row, original) in enumerate(zip(rows, reference)):
        require(int(row['relative_frame']) == int(original['relative_frame']) == frame
                and int(row['core_frame']) == int(original['core_frame']) == frame + 1,
                'Headless and reference frame boundaries differ.')
        require(re.fullmatch('[0-9a-f]{64}', row['gpu_sha256']) is not None, 'Invalid complete GPU hash.')
        equal = row['gpu_sha256'] == original['gpu_sha256']
        require(row['gpu_equal'] == str(equal), 'The GPU comparison flag disagrees with recorded hashes.')
        gpu_differences += not equal
        count = int(row['sample_frames'])
        require(count >= 0, 'A native frame has a negative PCM count.')
        total += count
        require(int(row['total_sample_frames']) == total, 'PCM frame totals are not consecutive.')
        counts.append(count)
    return counts, gpu_differences


def verify_replay(capture, output, summary, frames, host_exit_code):
    capture, output = Path(capture), Path(output)
    native = json.loads((output / 'report.json').read_text())
    require(native['status'] in ('passed_isolated_recorded_cold_replay', 'recorded_headless_replay_differences'),
            'The native recorder did not complete a supported replay.')
    require(native['frames_advanced'] == frames + 1 and native['submitted_frames_replayed'] == frames,
            'The native recorder completed a different frame window.')
    require(not native['restored_state'] and not native['game_RAM_injected'] and not native['emulator_UI_controlled'],
            'This comparison requires controller-only cold boot with no emulator UI control.')
    _, rows = read_tsv(output / 'headless.tsv', TRACE_FIELDS)
    _, reference = read_tsv(capture / 'cold-start.tsv')
    counts, gpu_differences = validate_trace(rows, reference, frames)
    checkpoints = native['rows']
    require([row['relative_frame'] for row in checkpoints] == summary['checkpoint_frames'],
            'Native checkpoint boundaries differ from the reference capture.')
    checked, ram_differences, rgb_differences, png_differences = [], 0, 0, 0
    for row in checkpoints:
        frame = row['relative_frame']
        raw = (output / f'mainram-{frame}.bin').read_bytes()
        expected = (capture / f'mainram-{frame}.bin').read_bytes()
        require(len(raw) == len(expected) == 0x200000, 'A checkpoint needs complete MainRAM.')
        different = sum(a != b for a, b in zip(raw, expected))
        require(different == row['differing_RAM_bytes'] and hashlib.sha256(raw).hexdigest() == row['RAM_sha256'],
                'The native RAM report disagrees with its complete bytes.')
        gpu = (output / f'gpu-{frame}.bin').read_bytes()
        expected_gpu = (capture / f'gpu-{frame}.bin').read_bytes()
        require(len(gpu) == len(expected_gpu) == 0x100000
                and hashlib.sha256(gpu).hexdigest() == rows[frame]['gpu_sha256'],
                'Checkpoint GPU bytes disagree with their complete observation hash.')
        png_equal = (output / f'frame-{frame}.png').read_bytes() == (capture / f'frame-{frame}.png').read_bytes()
        require(png_equal == row['PNG_file_byte_equal'] and type(row['differing_RGB_pixels']) is int
                and row['differing_RGB_pixels'] >= 0, 'The native image report is inconsistent.')
        ram_differences += different
        rgb_differences += row['differing_RGB_pixels']
        png_differences += not png_equal
        checked.append(dict(relative_frame=frame, MainRAM_equal=different == 0, GPU_equal=gpu == expected_gpu,
            RGB_pixels_equal=row['differing_RGB_pixels'] == 0, PNG_file_bytes_equal=png_equal))
    require((gpu_differences, ram_differences, rgb_differences, png_differences) ==
            (native['differing_GPU_observations'], native['differing_MainRAM_bytes'],
             native['differing_RGB_pixels'], native['differing_PNG_files']),
            'Native aggregate output counts disagree with individual observations.')
    pcm = (output / 'audio.pcm').read_bytes()
    audio = audio_window(pcm, capture / 'audio.wav', counts, frames)
    require(native['all_PCM_sample_frames'] == sum(counts), 'Native PCM total differs from complete audio.')
    passed = (host_exit_code == 0 and not gpu_differences and not ram_differences and not rgb_differences
              and all(row['GPU_equal'] for row in checked) and audio['equal'])
    return dict(status='passed_headless_game_output_comparison' if passed else 'recorded_headless_game_output_differences',
        submitted_frames=frames, native_observations=len(rows), checkpoint_comparisons=checked,
        differing_GPU_observations=gpu_differences, differing_MainRAM_bytes=ram_differences,
        differing_RGB_pixels=rgb_differences, differing_PNG_containers=png_differences, audio=audio,
        host_exit_code=host_exit_code, PNG_container_identity_required=False, complete_state_parity_checked=False,
        new_C_bytes=0, new_bounded_NPC_callbacks=0, whole_NPC_encounters_accepted=0, whole_feature_groups_accepted=0,
        scope='Cold-start controller replay, complete selected RAM/GPU, every recorded full GPU hash, '
              'native RGB comparison and the complete declared GUI PCM window. PNG file differences and '
              'all extra-observer audio are retained. No callback-entry trace, complete state or whole-feature acceptance.')


def replay(capture, workspace, dotnet=None):
    workspace = Path(workspace).resolve()
    require(not workspace.exists(), 'Choose a new workspace; existing evidence is preserved.')
    require(os.name == 'nt' and sys.maxsize > 2**32, 'The qualified headless recorder requires 64-bit Windows.')
    capture = Path(capture).resolve(strict=True)
    manifest = load_verified_manifest(capture)
    require(manifest is not None and manifest['schema_version'] == 2 and manifest['selected_core'] == 'Nymashock'
            and manifest['scenario'] == 'boot' and manifest.get('audio_output_requested') is True,
            'Use a complete pinned Nymashock cold-start capture with audio.')
    frames = manifest['frames']
    validate_frame_count(frames)
    summary = inspect_run(capture, frames=frames)
    require(summary['first_core_frame'] == 1, 'The qualified cold recorder starts at emulator frame one.')
    runtime = Path(manifest['emulator_files']['EmuHawk.exe']['path']).parent.resolve(strict=True)
    require(not workspace.is_relative_to(capture) and not workspace.is_relative_to(runtime),
            'Keep the new workspace outside the reference capture and emulator runtime.')
    config = json.loads(Path(manifest['configuration']['path']).read_text(encoding='utf-8-sig'))
    for section in ('CoreSettings', 'CoreSyncSettings'):
        require(not any('Nymashock' in name and value for name, value in config.get(section, {}).items()),
                'Only the capture recorder\'s default Nymashock settings are qualified.')
    dotnet = str(dotnet or shutil.which('dotnet') or Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'dotnet/dotnet.exe')
    sdk_list = subprocess.check_output([dotnet, '--list-sdks'], text=True)
    compiler = select_compiler(sdk_list)
    framework = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319'
    source_paths = [HOST_SOURCE, Path(__file__).resolve(), ROOT / 'tools/compare_cold_start.py',
                    ROOT / 'tools/runtime_inputs.py', ROOT / 'tools/compare_runtime.py', compiler]
    source_pins = [record_file(path) for path in source_paths]
    capture_paths = [capture / name for name in ('inputs.json', 'cold-start.tsv', 'submitted.tsv',
        'input-definition.tsv', 'captures.tsv', 'audio.wav')]
    for frame in summary['checkpoint_frames']:
        capture_paths += [capture / f'{kind}-{frame}.{suffix}' for kind, suffix in
                          (('mainram', 'bin'), ('gpu', 'bin'), ('frame', 'png'))]
    capture_pins = [record_file(path) for path in capture_paths]
    runtime_paths = [path for folder in (runtime / 'dll', runtime / 'gamedb') for path in sorted(folder.rglob('*')) if path.is_file()]
    require(runtime_paths and (runtime / 'gamedb/gamedb.txt').is_file(), 'The complete runtime and game database are required.')
    runtime_pins = [record_file(path) for path in runtime_paths]
    workspace.mkdir(parents=True, exist_ok=False)
    host = workspace / 'host'
    host.mkdir()
    for folder in ('dll', 'gamedb'):
        shutil.copytree(runtime / folder, host / folder)
    executable = host / 'ReplayColdStart.exe'
    shutil.copyfile(runtime / 'EmuHawk.exe.config', executable.with_suffix('.exe.config'))
    shutil.copyfile(HOST_SOURCE, host / 'ReplayColdStart.cs')
    references = [framework / name for name in ('mscorlib.dll', 'System.dll', 'System.Core.dll',
        'System.Web.Extensions.dll', 'System.Drawing.dll', 'netstandard.dll')]
    references += [host / 'dll' / name for name in ('BizHawk.Common.dll', 'BizHawk.Emulation.Common.dll',
        'BizHawk.Emulation.Cores.dll', 'BizHawk.Emulation.DiscSystem.dll', 'System.ValueTuple.dll')]
    require(all(path.is_file() for path in references), 'Required framework/core reference assemblies are absent.')
    compile_command = [dotnet, 'exec', str(compiler), '/nologo', '/target:exe', '/platform:x64', '/langversion:12',
        '/nostdlib+', '/deterministic+', *('/reference:' + str(path) for path in references),
        '/out:' + str(executable), str(host / 'ReplayColdStart.cs')]
    write_json(workspace / 'compile-command.json', compile_command)
    with (workspace / 'compiler.log').open('xb') as log:
        built = subprocess.run(compile_command, stdout=log, stderr=log)
    require(built.returncode == 0, 'The owned recorder build failed; see compiler.log.')
    output = workspace / 'observations'
    command = [str(executable), str(host), manifest['disc']['cue']['path'],
               *(manifest['bios'][key]['path'] for key in ('J', 'U', 'E')), str(capture), str(output), str(frames)]
    write_json(workspace / 'launch.json', dict(command=command, source_pins=source_pins,
        capture_pins=capture_pins, runtime_pins=runtime_pins, host_binary=record_file(executable),
        restored_state=False, game_RAM_injected=False, emulator_UI_controlled=False))
    with (workspace / 'host.out.log').open('xb') as out, (workspace / 'host.err.log').open('xb') as err:
        process = subprocess.Popen(command, cwd=host, stdout=out, stderr=err,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        write_json(workspace / 'process.json', dict(pid=process.pid, executable=str(executable), command=command))
        try:
            exit_code = process.wait()
        except BaseException:
            process.terminate()
            process.wait()
            raise
    write_json(workspace / 'exit.json', dict(pid=process.pid, exit_code=exit_code))
    require([record_file(path) for path in source_paths] == source_pins
            and [record_file(path) for path in capture_paths] == capture_pins
            and [record_file(path) for path in runtime_paths] == runtime_pins,
            'Source, reference capture or original runtime changed during replay.')
    require(load_verified_manifest(capture) == manifest, 'Pinned original launch inputs changed during replay.')
    result = verify_replay(capture, output, summary, frames, exit_code)
    result.update(source_pins=source_pins, reference_manifest=record_file(capture / 'inputs.json'),
                  host_binary=record_file(executable), workspace=str(workspace))
    write_json(workspace / 'comparison.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-folder', type=Path, required=True)
    parser.add_argument('--workspace', type=Path, required=True, help='New owned workspace outside the capture/runtime.')
    parser.add_argument('--dotnet', type=Path, help='Optional dotnet executable.')
    args = parser.parse_args(argv)
    result = replay(args.capture_folder, args.workspace, args.dotnet)
    print(json.dumps({key: result[key] for key in ('status', 'submitted_frames', 'native_observations',
        'differing_GPU_observations', 'differing_MainRAM_bytes', 'differing_RGB_pixels', 'differing_PNG_containers')}))
    return 0 if result['status'] == 'passed_headless_game_output_comparison' else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.CalledProcessError, wave.Error) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
