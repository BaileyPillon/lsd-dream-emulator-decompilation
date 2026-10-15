"""Capture a saved-state replay with restoration before the first Lua observation."""
import argparse
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
from tools.compare_card_roundtrip import CANONICAL_SHA256
from tools.play_game import read_root_file
from tools.runtime_inputs import pin_inputs

RESTORE_PREFIX = b'''-- Restore synchronously before the appended observer reads game state.
do
    local directory = assert(os.getenv("LSD_QA_OUTPUT"))
    assert(emu.getsystemid() == "PSX")
    savestate.load(directory .. "/start.State")
end
'''


def compose_observer(observer):
    """Keep the self-contained observer bytes intact after the scoped loader."""
    if not isinstance(observer, bytes) or not observer.strip():
        raise ValueError('Supply a nonempty Lua observer as bytes.')
    if observer.startswith(b'\xef\xbb\xbf'):
        raise ValueError('A byte-order mark cannot appear after the restore prefix.')
    observer.decode('utf-8')
    return RESTORE_PREFIX + observer


def capture_pair(workspace, original_cue, rebuilt_cue, emulator_root, bios_root, observer, state, frames):
    if sys.platform != 'win32':
        raise ValueError('This launcher requires Windows and BizHawk 2.11.1.')
    if type(frames) is not int or not 1 <= frames <= 30000:
        raise ValueError('Use between 1 and 30000 recorded frames.')
    workspace = Path(workspace).resolve()
    if workspace.exists() or (workspace.is_relative_to(ROOT) and not workspace.is_relative_to(ROOT / '.decomp-lab')):
        raise ValueError('Use a fresh workspace outside the checkout or under .decomp-lab.')
    runtime, bios, observer, state = [Path(p).resolve(strict=True) for p in
                                     (emulator_root, bios_root, observer, state)]
    cues = [Path(p).resolve(strict=True) for p in (original_cue, rebuilt_cue)]
    observer_bytes, state_bytes = observer.read_bytes(), state.read_bytes()
    script_bytes = compose_observer(observer_bytes)
    built = (ROOT / 'build/SLPS015.56').read_bytes()
    if hashlib.sha256(built).hexdigest() != CANONICAL_SHA256:
        raise ValueError('Build the canonical executable with ninja check first.')
    if any(read_root_file(cue)[0] != built for cue in cues):
        raise ValueError('A supplied disc executable differs from the canonical build.')
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
                                       'PSX+U': str(bios / 'scph5501.BIN'), 'PSX+E': str(bios / 'scph5502.BIN')},
        'PathEntries': {'Paths': [
            {'Type': 'Base', 'Path': str(shared), 'System': 'Global_NULL'},
            {'Type': 'Base', 'Path': str(shared / 'PSX'), 'System': 'PSX'},
            {'Type': 'Save RAM', 'Path': str(save_root), 'System': 'PSX'},
            {'Type': 'Savestates', 'Path': str(shared / 'PSX/State'), 'System': 'PSX'},
            {'Type': 'Screenshots', 'Path': str(shared / 'PSX/Screenshots'), 'System': 'PSX'}]},
    }
    for label, cue in zip(('original', 'rebuilt'), cues):
        if any(path.is_file() for path in save_root.rglob('*')):
            raise ValueError('Owned QA SaveRAM must be empty before each run.')
        folder = workspace / label
        folder.mkdir(exist_ok=False)
        write_json(folder / 'external-save-inputs.json', {
            'files': [], 'initial_save_ram_empty': True,
            'embedded_cards': 'Retained in the pinned state; external absence does not prove empty cards.'})
        for name in ('config.json', 'config-input.json'):
            write_json(folder / name, config)
        run_script, run_state = folder / 'runtime_smoke.lua', folder / 'start.State'
        run_script.write_bytes(script_bytes)
        run_state.write_bytes(state_bytes)
        write_json(folder / 'preparation.json', {
            'restore_mode': 'synchronous_lua_before_observer',
            'observer_sha256': hashlib.sha256(observer_bytes).hexdigest(),
            'generated_script_sha256': hashlib.sha256(script_bytes).hexdigest(),
            'source_state_sha256': hashlib.sha256(state_bytes).hexdigest(),
            'producer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
        write_json(folder / 'inputs.json', pin_inputs(cue, bios, runtime, folder / 'config-input.json',
                   run_script, 'play', frames, run_state, capture_audio=False))
        command = [str(runtime / 'EmuHawk.exe'), '--config', str(folder / 'config.json'), '--lua',
                   str(run_script), '--chromeless', '--gdi', str(cue)]
        environment = dict(os.environ, LSD_QA_OUTPUT=str(folder), LSD_QA_SCENARIO='play', LSD_QA_FRAMES=str(frames))
        startup = subprocess.STARTUPINFO()
        startup.dwFlags, startup.wShowWindow = subprocess.STARTF_USESHOWWINDOW, 0
        with (folder / 'emulator.out.log').open('xb') as stdout, (folder / 'emulator.err.log').open('xb') as stderr:
            process = subprocess.Popen(command, cwd=runtime, env=environment, stdout=stdout, stderr=stderr,
                                       startupinfo=startup, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        write_json(folder / 'process.json', {'pid': process.pid, 'command': command,
                   'started_utc': datetime.now(timezone.utc).isoformat()})
        print(json.dumps({'state': 'started_owned_state_replay', 'label': label, 'pid': process.pid}), flush=True)
        code = process.wait()
        write_json(folder / 'exit.json', {'pid': process.pid, 'exit_code': code,
                   'observed_utc': datetime.now(timezone.utc).isoformat()})
        write_json(folder / 'exit-save-records.json', preserve_saves(save_root, folder))
        if code != 0 or not (folder / 'completed.txt').is_file() or (folder / 'failed.txt').exists():
            raise ValueError('Owned replay did not complete; its logs and saves are preserved.')
        if observer.read_bytes() != observer_bytes or state.read_bytes() != state_bytes:
            raise ValueError('A source observer or saved state changed during capture.')
        print(json.dumps({'state': 'completed_owned_state_replay', 'label': label, 'pid': process.pid}), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'original-cue', 'rebuilt-cue', 'emulator-root', 'bios-root', 'observer', 'state'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--frames', type=int, required=True)
    args = parser.parse_args(argv)
    try:
        capture_pair(args.workspace, args.original_cue, args.rebuilt_cue, args.emulator_root,
                     args.bios_root, args.observer, args.state, args.frames)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
