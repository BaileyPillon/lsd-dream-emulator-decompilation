"""Capture a neutral original/rebuilt startup-movie pair in fresh Windows profiles."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.play_game import ORIGINAL_SHA1, read_root_file
from tools.runtime_inputs import pin_inputs


def write_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def capture_pair(workspace, original_cue, rebuilt_cue, emulator_root, bios_root, state, frames=9000):
    workspace = Path(workspace).resolve()
    if workspace.exists():
        raise ValueError('Choose a new workspace; existing captures are never replaced.')
    if workspace.is_relative_to(ROOT) and not workspace.is_relative_to(ROOT / '.decomp-lab'):
        raise ValueError('Keep captures outside the checkout or inside .decomp-lab.')
    if sys.platform != 'win32':
        raise ValueError('This capture launcher requires Windows and BizHawk 2.11.1.')
    if not 1 <= frames <= 12000:
        raise ValueError('Choose 1 to 12000 emulator frames.')
    runtime, bios, start = [Path(path).resolve(strict=True) for path in (emulator_root, bios_root, state)]
    cues = [Path(path).resolve(strict=True) for path in (original_cue, rebuilt_cue)]
    built = (ROOT / 'build/SLPS015.56').read_bytes()
    if len(built) != 505856 or hashlib.sha1(built).hexdigest() != ORIGINAL_SHA1:
        raise ValueError('Build the canonical executable with ninja check first.')
    for cue in cues:
        if read_root_file(cue)[0] != built:
            raise ValueError('A selected disc executable differs from the canonical build.')
    for name in ('scph5500.bin', 'scph5501.BIN', 'scph5502.BIN'):
        if not (bios / name).is_file():
            raise ValueError('Supply the three BIOS inputs required by runtime input pinning: ' + name)
    script = ROOT / 'research/movie_playback/observe.lua'
    if not (runtime / 'EmuHawk.exe').is_file() or not script.is_file():
        raise ValueError('Missing emulator or movie observer.')
    workspace.mkdir(parents=True, exist_ok=False)
    shared = workspace / 'isolated-save-data'
    for name in ('SaveRAM', 'State', 'Screenshots'):
        (shared / 'PSX' / name).mkdir(parents=True, exist_ok=True)
    save_root = (shared / 'PSX/SaveRAM').resolve()
    config = {
        'LastWrittenFrom': '2.11.1', 'FirstBoot': False, 'SkipSuperuserPrivsCheck': True,
        'UpdateAutoCheckEnabled': False, 'SoundEnabled': False, 'SoundEnabledNormal': False,
        'SoundEnabledRWFF': False, 'PreferredCores': {'PSX': 'Nymashock'},
        'FirmwareUserSpecifications': {'PSX+J': str(bios / 'scph5500.bin'),
                                       'PSX+U': str(bios / 'scph5501.BIN'),
                                       'PSX+E': str(bios / 'scph5502.BIN')},
        'PathEntries': {'Paths': [
            {'Type': 'Base', 'Path': str(shared), 'System': 'Global_NULL'},
            {'Type': 'Base', 'Path': str(shared / 'PSX'), 'System': 'PSX'},
            {'Type': 'Save RAM', 'Path': str(save_root), 'System': 'PSX'},
            {'Type': 'Savestates', 'Path': str(shared / 'PSX/State'), 'System': 'PSX'},
            {'Type': 'Screenshots', 'Path': str(shared / 'PSX/Screenshots'), 'System': 'PSX'}]}}
    for label, cue in zip(('original', 'rebuilt'), cues):
        if any(path.is_file() for path in save_root.rglob('*')):
            raise ValueError('Owned QA SaveRAM must be empty before each run.')
        folder = workspace / label
        folder.mkdir(exist_ok=False)
        write_json(folder / 'external-save-inputs.json', {'files': [], 'initial_save_ram_empty': True})
        for name in ('config.json', 'config-input.json'):
            write_json(folder / name, config)
        run_script, run_state = folder / 'runtime_smoke.lua', folder / 'start.State'
        shutil.copyfile(script, run_script)
        shutil.copyfile(start, run_state)
        inputs = pin_inputs(cue, bios, runtime, folder / 'config-input.json', run_script,
                            'boot', frames, run_state, capture_audio=True)
        write_json(folder / 'inputs.json', inputs)
        command = [str(runtime / 'EmuHawk.exe'), '--config', str(folder / 'config.json'),
                   '--lua', str(run_script), '--chromeless', '--gdi', '--load-state', str(run_state),
                   '--dump-type', 'wave', '--dump-name', str(folder / 'audio.wav'),
                   '--audiosync', 'true', '--dump-length', str(frames), str(cue)]
        environment = dict(os.environ, LSD_QA_OUTPUT=str(folder), LSD_QA_SCENARIO='boot', LSD_QA_FRAMES=str(frames))
        startup = subprocess.STARTUPINFO()
        startup.dwFlags, startup.wShowWindow = subprocess.STARTF_USESHOWWINDOW, 0
        with (folder / 'emulator.out.log').open('xb') as stdout, (folder / 'emulator.err.log').open('xb') as stderr:
            process = subprocess.Popen(command, cwd=runtime, env=environment, stdout=stdout, stderr=stderr,
                                       startupinfo=startup, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        write_json(folder / 'process.json', {'pid': process.pid, 'command': command,
                   'started_utc': datetime.now(timezone.utc).isoformat(), 'priority': 'BelowNormal'})
        print(json.dumps({'state': 'started_owned_movie_capture', 'label': label, 'pid': process.pid, 'output': str(folder)}), flush=True)
        code = process.wait()
        write_json(folder / 'exit.json', {'pid': process.pid, 'exit_code': code,
                   'observed_utc': datetime.now(timezone.utc).isoformat()})
        saved = []
        for path in sorted(save_root.rglob('*')):
            if not path.is_file():
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(save_root):
                raise ValueError('An owned save path leaves its configured directory.')
            destination = (folder / 'exit-save-ram' / resolved.relative_to(save_root)).resolve()
            if not destination.is_relative_to(folder.resolve()) or destination.exists():
                raise ValueError('Refusing to replace or move a save outside its capture folder.')
            destination.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
            shutil.move(str(resolved), str(destination))
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise ValueError('Moved owned save failed its hash check.')
            saved.append({'relative_path': str(destination.relative_to(folder)), 'sha256': digest})
        write_json(folder / 'exit-save-records.json', {'files_preserved': saved,
                   'shared_save_ram_empty': not any(p.is_file() for p in save_root.rglob('*'))})
        if code != 0 or not (folder / 'completed.txt').is_file() or (folder / 'failed.txt').exists():
            raise ValueError('Owned movie capture failed; preserved diagnostics are in ' + str(folder))
        print(json.dumps({'state': 'completed_owned_movie_capture', 'label': label, 'pid': process.pid, 'exit_code': code}), flush=True)
    return workspace


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'original-cue', 'rebuilt-cue', 'emulator-root', 'bios-root', 'state'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--frames', type=int, default=9000)
    args = parser.parse_args(argv)
    try:
        capture_pair(args.workspace, args.original_cue, args.rebuilt_cue, args.emulator_root,
                     args.bios_root, args.state, args.frames)
        return 0
    except (OSError, ValueError) as error:
        print('[!] ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
