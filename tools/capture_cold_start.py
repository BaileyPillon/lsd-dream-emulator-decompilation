"""Record a controller-only cold boot into a dream in isolated Windows profiles."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.capture_card_roundtrip import preserve_saves, write_json
from tools.compare_card_roundtrip import CANONICAL_SHA256, require
from tools.compare_cold_start import FRAMES, OBSERVER_SHA256, validate_frame_count
from tools.play_game import read_root_file
from tools.runtime_inputs import load_verified_manifest, pin_inputs


def capture_pair(workspace, original_cue, rebuilt_cue, emulator_root, bios_root, frames=FRAMES):
    validate_frame_count(frames)
    require(sys.platform == 'win32', 'This recorder requires Windows and BizHawk 2.11.1.')
    workspace = Path(workspace).resolve()
    require(not workspace.exists(), 'Choose a new capture directory; existing files are preserved.')
    require(not workspace.is_relative_to(ROOT) or workspace.is_relative_to(ROOT / '.decomp-lab'),
            'Keep private captures outside the checkout or under .decomp-lab.')
    tasks = subprocess.check_output(['tasklist', '/FI', 'IMAGENAME eq EmuHawk.exe', '/FO', 'CSV', '/NH'], text=True)
    require(not any(row and row[0].lower() == 'emuhawk.exe' for row in csv.reader(tasks.splitlines())),
            'An emulator is already running. Preserve that session and run this capture after it exits.')
    runtime, bios = [Path(p).resolve(strict=True) for p in (emulator_root, bios_root)]
    cues = [Path(p).resolve(strict=True) for p in (original_cue, rebuilt_cue)]
    built = (ROOT / 'build/SLPS015.56').read_bytes()
    require(len(built) == 505856 and hashlib.sha256(built).hexdigest() == CANONICAL_SHA256,
            'Run ninja check to produce the canonical executable before capturing.')
    require(all(read_root_file(cue)[0] == built for cue in cues), 'A disc executable differs from the matching build.')
    observer = ROOT / 'research/cold_start/observe.lua'
    observer_bytes = observer.read_bytes()
    require(hashlib.sha256(observer_bytes).hexdigest() == OBSERVER_SHA256, 'Supported observer bytes changed.')
    workspace.mkdir(parents=True, exist_ok=False)
    shared = workspace / 'isolated-save-data'
    for name in ('SaveRAM', 'State', 'Screenshots'):
        (shared / 'PSX' / name).mkdir(parents=True, exist_ok=False)
    save_root = shared / 'PSX/SaveRAM'
    config = {
        'LastWrittenFrom': '2.11.1', 'FirstBoot': False, 'SkipSuperuserPrivsCheck': True,
        'UpdateAutoCheckEnabled': False, 'SoundEnabled': False, 'SoundEnabledNormal': False,
        'SoundEnabledRWFF': False, 'PreferredCores': {'PSX': 'Nymashock'},
        'FirmwareUserSpecifications': {'PSX+J': str(bios / 'scph5500.bin'),
                                       'PSX+U': str(bios / 'scph5501.BIN'), 'PSX+E': str(bios / 'scph5502.BIN')},
        'PathEntries': {'Paths': [
            {'Type': 'Base', 'Path': str(shared), 'System': 'Global_NULL'},
            {'Type': 'Base', 'Path': str(shared / 'PSX'), 'System': 'PSX'},
            {'Type': 'Save RAM', 'Path': str(save_root), 'System': 'PSX'},
            {'Type': 'Savestates', 'Path': str(shared / 'PSX/State'), 'System': 'PSX'},
            {'Type': 'Screenshots', 'Path': str(shared / 'PSX/Screenshots'), 'System': 'PSX'}]},
    }
    producer_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for label, cue in zip(('original', 'rebuilt'), cues):
        require(not any(p.is_file() for p in save_root.rglob('*')), 'Owned SaveRAM must be empty before each cold boot.')
        folder = workspace / label
        folder.mkdir(exist_ok=False)
        write_json(folder / 'external-save-inputs.json', {'files': [], 'initial_external_save_ram_empty': True})
        write_json(folder / 'preparation.json', {'producer_sha256': producer_hash, 'observer_sha256': OBSERVER_SHA256,
                   'canonical_executable_sha256': CANONICAL_SHA256, 'start_kind': 'cold_boot_without_saved_state'})
        for name in ('config.json', 'config-input.json'):
            write_json(folder / name, config)
        script = folder / 'runtime_smoke.lua'
        script.write_bytes(observer_bytes)
        write_json(folder / 'inputs.json', pin_inputs(cue, bios, runtime, folder / 'config-input.json', script,
                   'boot', frames, None, capture_audio=True))
        command = [str(runtime / 'EmuHawk.exe'), '--config', str(folder / 'config.json'), '--lua', str(script),
                   '--chromeless', '--gdi', '--dump-type', 'wave', '--dump-name', str(folder / 'audio.wav'),
                   '--audiosync', 'true', '--dump-length', str(frames), str(cue)]
        environment = dict(os.environ, LSD_QA_OUTPUT=str(folder), LSD_QA_SCENARIO='boot', LSD_QA_FRAMES=str(frames))
        startup = subprocess.STARTUPINFO()
        startup.dwFlags, startup.wShowWindow = subprocess.STARTF_USESHOWWINDOW, 0
        with (folder / 'emulator.out.log').open('xb') as out, (folder / 'emulator.err.log').open('xb') as err:
            process = subprocess.Popen(command, cwd=runtime, env=environment, stdout=out, stderr=err,
                                       startupinfo=startup, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        write_json(folder / 'process.json', {'pid': process.pid, 'command': command,
                   'started_utc': datetime.now(timezone.utc).isoformat()})
        print(json.dumps({'state': 'started_owned_cold_start', 'label': label, 'pid': process.pid}), flush=True)
        code = process.wait()
        write_json(folder / 'exit.json', {'pid': process.pid, 'exit_code': code,
                   'observed_utc': datetime.now(timezone.utc).isoformat()})
        write_json(folder / 'exit-save-records.json', preserve_saves(save_root, folder))
        require(code == 0 and (folder / 'completed.txt').is_file() and not (folder / 'failed.txt').exists(),
                'Cold-start capture failed; its logs and owned saves are retained in ' + str(folder))
        require(observer.read_bytes() == observer_bytes, 'The source observer changed during capture.')
        load_verified_manifest(folder)
        print(json.dumps({'state': 'completed_owned_cold_start', 'label': label, 'pid': process.pid}), flush=True)
    return workspace


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'original-cue', 'rebuilt-cue', 'emulator-root', 'bios-root'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--frames', type=int, default=FRAMES,
                        help='Advanced frames per disc, from 6000 through 30000 (default: 6000).')
    args = parser.parse_args(argv)
    try:
        capture_pair(args.workspace, args.original_cue, args.rebuilt_cue, args.emulator_root, args.bios_root,
                     frames=args.frames)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
