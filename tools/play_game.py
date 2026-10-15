"""Prepare or launch an isolated BizHawk profile for the matching LSD build."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

try:
    from .psx_image import ORIGINAL_SHA1, read_root_file
    from .runtime_inputs import EMULATOR_FILES, disc_inputs, record_file
except ImportError:
    from psx_image import ORIGINAL_SHA1, read_root_file
    from runtime_inputs import EMULATOR_FILES, disc_inputs, record_file

ROOT = Path(__file__).resolve().parents[1]


def build_in_wsl(distro):
    if sys.platform != 'win32':
        raise ValueError('--distro is for the Windows WSL build helper.')
    linux_root = subprocess.check_output(
        ['wsl.exe', '-d', distro, '--exec', 'wslpath', '-a', '-u', str(ROOT)], text=True).strip()
    script = '''set -eu
lsdPython=python3
if [ -x .venv/bin/python ]; then
    export PATH="$PWD/.venv/bin:$PATH"
    lsdPython=python
elif [ -x /opt/lsd-decomp-venv/bin/python ]; then
    export PATH=/opt/lsd-decomp-venv/bin:$PATH
    lsdPython=python
fi
"$lsdPython" configure.py
ninja check -j2
'''
    subprocess.run(['wsl.exe', '-d', distro, '--cd', linux_root, '--exec', 'sh', '-c', script],
                   cwd=ROOT, check=True)


def fingerprint(path):
    return record_file(path)


def write_json(path, data):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, indent=2, ensure_ascii=True)
        stream.write('\n')


def prepare(cue, emulator_root, bios_root, profile):
    cue = Path(cue).resolve(strict=True)
    if cue.suffix.lower() != '.cue':
        raise ValueError('Supply the CUE for your original or rebuilt disc.')
    emulator_root = Path(emulator_root).resolve(strict=True)
    bios_root = Path(bios_root).resolve(strict=True)
    profile = Path(profile).resolve()
    if profile.exists():
        raise ValueError('Choose a new profile directory; existing profiles are never replaced.')
    executable = ROOT / 'build/SLPS015.56'
    built = executable.read_bytes()
    packed, lba = read_root_file(cue)
    if len(built) != 505856 or hashlib.sha1(built).hexdigest() != ORIGINAL_SHA1:
        raise ValueError('Build the canonical executable with ninja check before preparing play.')
    if packed != built:
        raise ValueError('The selected disc executable differs from the matching build.')
    bios = bios_root / 'scph5500.bin'
    if bios.stat().st_size != 524288:
        raise ValueError('Expected a 512 KiB Japanese PlayStation BIOS: scph5500.bin.')
    disc = disc_inputs(cue)
    inputs = {'cue': disc['cue'], 'disc': disc['tracks'][0],
              'additional_disc_tracks': disc['tracks'][1:], 'disc_layout': disc['layout'],
              'built_executable': fingerprint(executable), 'bios': fingerprint(bios),
              'emulator': [fingerprint(emulator_root / name) for name in EMULATOR_FILES]}
    controls = {
        'P1 D-Pad Up': 'Up, X1 DpadUp', 'P1 D-Pad Down': 'Down, X1 DpadDown',
        'P1 D-Pad Left': 'Left, X1 DpadLeft', 'P1 D-Pad Right': 'Right, X1 DpadRight',
        'P1 Start': 'Enter, X1 Start', 'P1 Select': 'Space, X1 Back',
        'P1 \u25cb': 'X, X1 B', 'P1 X': 'Z, X1 A',
        'P1 \u25a1': 'A, X1 X', 'P1 \u25b3': 'S, X1 Y',
        'P1 L1': 'Q, X1 LeftShoulder', 'P1 R1': 'W, X1 RightShoulder',
        'P1 L2': 'E, X1 LeftTrigger', 'P1 R2': 'R, X1 RightTrigger',
    }
    config = {
        'LastWrittenFrom': '2.11.1', 'FirstBoot': False, 'SkipSuperuserPrivsCheck': True,
        'UpdateAutoCheckEnabled': False, 'PreferredCores': {'PSX': 'Nymashock'},
        'FirmwareUserSpecifications': {'PSX+J': str(bios)},
        'PathEntries': {'Paths': [
            {'Type': 'Base', 'Path': str(profile), 'System': 'Global_NULL'},
            {'Type': 'Base', 'Path': str(profile / 'PSX'), 'System': 'PSX'},
            {'Type': 'Save RAM', 'Path': str(profile / 'PSX/SaveRAM'), 'System': 'PSX'},
            {'Type': 'Savestates', 'Path': str(profile / 'PSX/State'), 'System': 'PSX'},
            {'Type': 'Screenshots', 'Path': str(profile / 'PSX/Screenshots'), 'System': 'PSX'},
        ]},
        'AllTrollers': {'PSX Front Panel': controls},
        'SoundEnabled': True, 'SoundEnabledNormal': True, 'SoundEnabledRWFF': False,
        'SpeedPercent': 100, 'ClockThrottle': True, 'StartPaused': False,
        'AcceptBackgroundInput': False, 'SaveWindowPosition': True,
        'MainWindowSize': '960, 745',
    }
    profile.mkdir(parents=True, exist_ok=False)
    for name in ('SaveRAM', 'State', 'Screenshots'):
        (profile / 'PSX' / name).mkdir(parents=True)
    write_json(profile / 'config.json', config)
    write_json(profile / 'config-input.json', config)
    manifest = {
        'schema_version': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'prepared_matching_play_profile', 'inputs': inputs,
        'config_input': fingerprint(profile / 'config-input.json'),
        'disc_executable_equals_build': True, 'executable_lba': lba,
        'canonical_sha1': ORIGINAL_SHA1, 'emulator_core': 'Nymashock',
        'controls': controls, 'runtime_observed': False,
        'whole_game_parity_accepted': False,
    }
    write_json(profile / 'play.json', manifest)
    return manifest


def launch(profile):
    if sys.platform != 'win32':
        raise ValueError('Interactive launch requires Windows and BizHawk; use --prepare-only elsewhere.')
    profile = Path(profile).resolve(strict=True)
    manifest = json.loads((profile / 'play.json').read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 1 or manifest.get('canonical_sha1') != ORIGINAL_SHA1:
        raise ValueError('Unsupported play profile.')
    inputs = manifest['inputs']
    for entry in [inputs['cue'], inputs['disc'], *inputs.get('additional_disc_tracks', []),
                  inputs['bios'], *inputs['emulator']]:
        if fingerprint(entry['path']) != entry:
            raise ValueError('A pinned game, BIOS, or emulator input changed; prepare a new profile.')
    expected = inputs['built_executable']
    packed, lba = read_root_file(inputs['cue']['path'])
    if (len(packed) != expected['bytes'] or hashlib.sha256(packed).hexdigest() != expected['sha256']
            or hashlib.sha1(packed).hexdigest() != ORIGINAL_SHA1 or lba != manifest['executable_lba']):
        raise ValueError('Disc read-back no longer matches the prepared build.')
    if fingerprint(profile / 'config-input.json') != manifest['config_input']:
        raise ValueError('The frozen initial profile changed; prepare a new profile.')
    run = profile / ('session-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    run.mkdir(exist_ok=False)
    executable = inputs['emulator'][0]['path']
    command = [executable, '--config', str(profile / 'config.json'), '--gdi', inputs['cue']['path']]
    with (run / 'stdout.log').open('xb') as stdout, (run / 'stderr.log').open('xb') as stderr:
        process = subprocess.Popen(command, cwd=str(Path(executable).parent), stdout=stdout, stderr=stderr)
    report = {'status': 'started_play_process', 'pid': process.pid, 'command': command,
              'started_utc': datetime.now(timezone.utc).isoformat(),
              'runtime_observed': False, 'whole_game_parity_accepted': False}
    write_json(run / 'session.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cue', type=Path)
    parser.add_argument('--emulator-root', type=Path)
    parser.add_argument('--bios-root', type=Path)
    parser.add_argument('--profile', required=True, type=Path)
    parser.add_argument('--distro', help='Build in this WSL distribution before preparing play.')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--resume', action='store_true', help='Launch an existing verified profile.')
    args = parser.parse_args(argv)
    try:
        if args.resume:
            if args.prepare_only or any((args.cue, args.emulator_root, args.bios_root, args.distro)):
                raise ValueError('--resume only takes --profile.')
        else:
            if not all((args.cue, args.emulator_root, args.bios_root)):
                raise ValueError('Preparing play requires --cue, --emulator-root and --bios-root.')
            if args.distro:
                build_in_wsl(args.distro)
            prepare(args.cue, args.emulator_root, args.bios_root, args.profile)
            print('Verified matching executable in supplied disc; prepared profile: ' + str(args.profile.resolve()))
        if not args.prepare_only:
            report = launch(args.profile)
            print('Started matching game, PID ' + str(report['pid']))
        print('Keyboard: arrows move/turn, Enter Start, X Circle/confirm, Z Cross, Q/W L1/R1.')
        print('Process launch alone does not verify gameplay or whole-game parity.')
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print('[!] ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
