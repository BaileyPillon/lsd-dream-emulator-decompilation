"""Capture one Save or cold-Load pair in a fresh, isolated Windows QA workspace."""
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
from tools.compare_card_roundtrip import CARD_NAME, CANONICAL_SHA256, SCRIPT_HASHES, lsd_payload
from tools.play_game import read_root_file
from tools.runtime_inputs import pin_inputs


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def preserve_saves(save_root, folder):
    save_root, folder = Path(save_root).resolve(), Path(folder).resolve()
    records = []
    for path in sorted(save_root.rglob('*')):
        if not path.is_file():
            continue
        resolved = path.resolve()
        if not resolved.is_relative_to(save_root):
            raise ValueError('Owned save path resolves outside its isolated directory.')
        destination = (folder / 'exit-save-ram' / resolved.relative_to(save_root)).resolve()
        if not destination.is_relative_to(folder) or destination.exists():
            raise ValueError('Exit-save destination is outside this capture or already exists.')
        data = resolved.read_bytes()
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(resolved), str(destination))
        if destination.read_bytes() != data:
            raise ValueError('Preserved save bytes differ.')
        records.append({'relative_path': str(destination.relative_to(folder)), 'bytes': len(data),
                        'sha256': hashlib.sha256(data).hexdigest()})
    return {'files_preserved': records, 'shared_save_ram_empty': not any(p.is_file() for p in save_root.rglob('*'))}


def capture_pair(workspace, original_cue, rebuilt_cue, emulator_root, bios_root, phase, state=None, card=None):
    if sys.platform != 'win32':
        raise ValueError('This capture launcher requires Windows and BizHawk 2.11.1.')
    workspace = Path(workspace).resolve()
    if workspace.exists() or (workspace.is_relative_to(ROOT) and not workspace.is_relative_to(ROOT / '.decomp-lab')):
        raise ValueError('Use a new workspace outside the checkout or under .decomp-lab.')
    if phase not in ('save', 'load') or (phase == 'save' and (state is None or card is not None)) or (
            phase == 'load' and (card is None or state is not None)):
        raise ValueError('Save requires --state; cold Load requires --card and no state.')
    runtime, bios = [Path(p).resolve(strict=True) for p in (emulator_root, bios_root)]
    cues = [Path(p).resolve(strict=True) for p in (original_cue, rebuilt_cue)]
    state = Path(state).resolve(strict=True) if state is not None else None
    card = Path(card).resolve(strict=True) if card is not None else None
    script = ROOT / 'research/card_roundtrip' / f'{phase}.lua'
    if hashlib.sha256(script.read_bytes()).hexdigest() != SCRIPT_HASHES[phase]:
        raise ValueError('Supported observer bytes changed.')
    built = (ROOT / 'build/SLPS015.56').read_bytes()
    if hashlib.sha256(built).hexdigest() != CANONICAL_SHA256:
        raise ValueError('Build the canonical executable with ninja check first.')
    if any(read_root_file(cue)[0] != built for cue in cues):
        raise ValueError('A disc executable differs from the canonical build.')
    seed = card.read_bytes() if card else None
    if seed is not None:
        lsd_payload(seed)
    for path in (runtime / 'EmuHawk.exe', *(bios / name for name in ('scph5500.bin', 'scph5501.BIN', 'scph5502.BIN'))):
        if not path.is_file():
            raise ValueError('Missing capture input: ' + str(path))
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
    frames = 2400 if phase == 'save' else 6000
    for label, cue in zip(('original', 'rebuilt'), cues):
        if any(path.is_file() for path in save_root.rglob('*')):
            raise ValueError('Owned QA SaveRAM must be empty before staging this run.')
        folder = workspace / label
        folder.mkdir(exist_ok=False)
        external = {'files': [], 'initial_external_save_ram_empty': True,
                    'embedded_card_state': 'Retained in the pinned warm state; external absence alone does not prove blank embedded cards.'}
        if seed is not None:
            (save_root / CARD_NAME).write_bytes(seed)
            (folder / 'input-card.SaveRAM').write_bytes(seed)
            digest = hashlib.sha256(seed).hexdigest()
            external = {'files': [{'relative_path': str((save_root / CARD_NAME).relative_to(shared)),
                                   'bytes': len(seed), 'sha256': digest}],
                        'source_card_sha256': digest, 'load_kind': 'cold_boot_without_saved_state'}
        write_json(folder / 'external-save-inputs.json', external)
        for name in ('config.json', 'config-input.json'):
            write_json(folder / name, config)
        run_script = folder / 'runtime_smoke.lua'
        shutil.copyfile(script, run_script)
        run_state = folder / 'start.State' if state else None
        if state:
            shutil.copyfile(state, run_state)
        write_json(folder / 'inputs.json', pin_inputs(cue, bios, runtime, folder / 'config-input.json',
                   run_script, 'play', frames, run_state, capture_audio=False))
        command = [str(runtime / 'EmuHawk.exe'), '--config', str(folder / 'config.json'), '--lua',
                   str(run_script), '--chromeless', '--gdi']
        if run_state:
            command += ['--load-state', str(run_state)]
        command.append(str(cue))
        environment = dict(os.environ, LSD_QA_OUTPUT=str(folder), LSD_QA_SCENARIO='play', LSD_QA_FRAMES=str(frames))
        startup = subprocess.STARTUPINFO()
        startup.dwFlags, startup.wShowWindow = subprocess.STARTF_USESHOWWINDOW, 0
        with (folder / 'emulator.out.log').open('xb') as stdout, (folder / 'emulator.err.log').open('xb') as stderr:
            process = subprocess.Popen(command, cwd=runtime, env=environment, stdout=stdout, stderr=stderr,
                                       startupinfo=startup, creationflags=subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        write_json(folder / 'process.json', {'pid': process.pid, 'command': command,
                   'started_utc': datetime.now(timezone.utc).isoformat()})
        print(json.dumps({'state': 'started_owned_card_capture', 'phase': phase, 'label': label, 'pid': process.pid}), flush=True)
        code = process.wait()
        write_json(folder / 'exit.json', {'pid': process.pid, 'exit_code': code,
                   'observed_utc': datetime.now(timezone.utc).isoformat()})
        write_json(folder / 'exit-save-records.json', preserve_saves(save_root, folder))
        if code != 0 or not (folder / 'completed.txt').is_file() or (folder / 'failed.txt').exists():
            raise ValueError('Owned capture did not complete; its logs and saves are preserved.')
        if card and card.read_bytes() != seed:
            raise ValueError('Source card changed during capture.')
        print(json.dumps({'state': 'completed_owned_card_capture', 'phase': phase, 'label': label, 'pid': process.pid}), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('workspace', 'original-cue', 'rebuilt-cue', 'emulator-root', 'bios-root'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--phase', choices=('save', 'load'), required=True)
    parser.add_argument('--state', type=Path)
    parser.add_argument('--card', type=Path)
    args = parser.parse_args(argv)
    capture_pair(args.workspace, args.original_cue, args.rebuilt_cue, args.emulator_root, args.bios_root,
                 args.phase, args.state, args.card)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
