"""Compare the recorded cold-start path, retaining every raw state difference."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.compare_card_roundtrip import require
from tools.compare_runtime import byte_comparison, compare_audio, compare_state
from tools.runtime_inputs import compare_inputs, load_verified_manifest

FRAMES = 6000
OBSERVER_SHA256 = 'ec61b5804771bc54ad0859195107d89371c86ac10a72b979fe7376298a394ffe'
TRACE_FIELDS = ('relative_frame', 'core_frame', 'screen_kind', 'menu', 'menu_index', 'session', 'session_state',
                'map_scene', 'flow', 'dream', 'timer', 'input_locked', 'map', 'stored_day', 'new_game',
                'coordinate', 'pose', 'x', 'y', 'z', 'yaw', 'pad', 'pad_held', 'pad_released', 'pad_pressed', 'gpu_sha256')


def read_tsv(path, expected_header=None):
    with Path(path).open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        header, rows = tuple(reader.fieldnames or ()), list(reader)
    require(header and len(header) == len(set(header)), 'Missing or duplicate table columns.')
    require(expected_header is None or header == tuple(expected_header), 'Unsupported observation columns.')
    require(all(None not in row and None not in row.values() for row in rows), 'An observation row is truncated.')
    return header, rows


def physical(value, size):
    require(0x80010000 <= value <= 0x80200000 - size and value % 4 == 0, 'Invalid native pointer.')
    return value & 0x1fffffff


def validate_ram(raw, row):
    """Re-read the logged owners, pose and native values from a full checkpoint."""
    require(len(raw) == 0x200000, 'A checkpoint must contain complete MainRAM.')
    require(row['screen_kind'] in ('startup', 'main', 'dream_session', 'unlocked_dream'), 'Unknown screen observation.')
    if row['screen_kind'] != 'startup':
        require(all(row[key] != '-' for key in ('flow', 'dream', 'pad')), 'An active screen requires its native owner chain.')
    if row['screen_kind'] == 'main':
        require(row['menu'] != '-', 'The main screen requires its menu object.')
    if row['screen_kind'] in ('dream_session', 'unlocked_dream'):
        require(row['session'] != '-', 'A dream screen requires its session object.')
    if row['screen_kind'] == 'unlocked_dream':
        require(row['session_state'] == '2' and row['input_locked'] == '0'
                and all(row[key] != '-' for key in ('session', 'map_scene', 'coordinate', 'pose')),
                'An unlocked dream requires its native session, map, transform and unlocked input.')
    def word(offset):
        require(0 <= offset <= len(raw) - 4 and offset % 4 == 0, 'Native field lies outside aligned MainRAM storage.')
        return struct.unpack_from('<I', raw, offset)[0]
    def equal(name, value):
        require(int(row[name]) == value, 'Checkpoint field disagrees with MainRAM: ' + name)
    if row['flow'] == '-':
        candidate = word(0x8ac20)
        valid = 0x80010000 <= candidate <= 0x801fffd4 and candidate % 4 == 0
        require(not valid or word(candidate & 0x1fffffff) != 0x8006d3c8, 'A live game flow was omitted.')
        return
    flow = physical(word(0x8ac20), 0x2c)
    equal('flow', flow)
    require(word(flow) == 0x8006d3c8, 'Wrong game-flow type.')
    if row['dream'] == '-':
        return
    dream = physical(word(flow + 0x28), 0x928)
    equal('dream', dream)
    require(word(dream) == 0x80087bdc, 'Wrong dream-system type.')
    graphics = physical(word(flow + 0x1c), 0x14)
    pad = physical(word(graphics + 4), 0x20)
    equal('pad', pad)
    require(word(pad) == 0x8006d370, 'Wrong native pad type.')
    for name, offset in (('timer', 0x24), ('input_locked', 0x70), ('stored_day', 0x180), ('new_game', 0x878)):
        equal(name, word(dream + offset))
    equal('map', struct.unpack_from('<i', raw, dream + 0x164)[0])
    for name, offset in (('pad_held', 0x10), ('pad_released', 0x14), ('pad_pressed', 0x18)):
        equal(name, word(pad + offset))
    if row['menu'] != '-':
        menu = int(row['menu'])
        require(word(menu) == 0x80086b60 and word(menu + 0xc) == word(flow + 0x1c)
                and word(menu + 0xa4) == 0x80000000 + dream, 'Wrong main-menu ownership.')
        equal('menu_index', word(menu + 0x58))
    if row['session'] != '-':
        session = int(row['session'])
        require(word(session) == 0x800865c8 and word(session + 0xc) == word(flow + 0x1c)
                and word(session + 0x38) == 0x80000000 + dream, 'Wrong dream-session ownership.')
        equal('session_state', word(session + 0x3c))
        if row['map_scene'] != '-':
            scene = physical(word(session + 0x4c), 4)
            equal('map_scene', scene)
            require(word(scene) == 0x80087034, 'Wrong map-scene type.')
    if row['coordinate'] != '-':
        coordinate = physical(word(dream + 0x14), 0x50)
        equal('coordinate', coordinate)
        for name, offset in (('x', 0x18), ('y', 0x1c), ('z', 0x20)):
            equal(name, struct.unpack_from('<i', raw, coordinate + offset)[0])
        if row['pose'] != '-':
            pose = physical(word(coordinate + 0x44), 0x28)
            equal('pose', pose)
            equal('yaw', struct.unpack_from('<h', raw, pose + 0x12)[0])


def validate_submissions(header, definitions, submitted, observations, frames=FRAMES):
    controls = {row['name']: row for row in definitions}
    require(len(controls) == len(definitions) == 26, 'Incomplete controller definition.')
    boolean = {key for key, value in controls.items() if value['type'] == 'boolean'}
    numeric = {key for key, value in controls.items() if value['type'] == 'number'}
    require(len(boolean) == 21 and len(numeric) == 5 and boolean | numeric == set(controls), 'Unexpected controller types.')
    require(all(controls[key]['neutral_value'] == 'false' for key in boolean), 'Digital controls were not neutralized.')
    require(tuple(header) == ('relative_frame', 'core_frame', 'phase', 'buttons', *sorted(controls)), 'Wrong controller columns.')
    require(len(submitted) == frames and [int(row['relative_frame']) for row in submitted] == list(range(1, frames + 1)),
            'Submitted controls must contain every advanced frame.')
    phases = {}
    for row in submitted:
        frame = int(row['relative_frame'])
        require(int(row['core_frame']) == int(observations[frame - 1]['core_frame']), 'Wrong pre-frame controller boundary.')
        require(all(row[key] in ('true', 'false') for key in boolean), 'Invalid Boolean controller value.')
        require(all(row[key] == controls[key]['neutral_value'] for key in numeric), 'Unexpected analog or disc input.')
        requested = row['buttons'].split(',') if row['buttons'] else []
        require(len(requested) == len(set(requested)) and set(requested) == {key for key in boolean if row[key] == 'true'},
                'Submitted controls differ from the declared buttons.')
        phases.setdefault(row['phase'], []).append(observations[frame])
    return phases


def inspect_run(folder):
    folder = Path(folder)
    require((folder / 'completed.txt').is_file() and not (folder / 'failed.txt').exists(), 'Incomplete recorder.')
    require(json.loads((folder / 'exit.json').read_text())['exit_code'] == 0, 'Owned emulator did not exit normally.')
    command = json.loads((folder / 'process.json').read_text())['command']
    require('--load-state' not in command, 'This profile requires cold boot without a saved state.')
    manifest = load_verified_manifest(folder)
    require(manifest['start_state'] is None and manifest['start_kind'] == 'cold_boot', 'Wrong starting-state identity.')
    script = (folder / 'runtime_smoke.lua').read_bytes()
    require(hashlib.sha256(script).hexdigest() == OBSERVER_SHA256, 'Wrong executed cold-start observer.')
    external = json.loads((folder / 'external-save-inputs.json').read_text())
    require(external['initial_external_save_ram_empty'] and external['files'] == [], 'Unexpected initial external saves.')
    _, rows = read_tsv(folder / 'cold-start.tsv', TRACE_FIELDS)
    require(len(rows) == FRAMES + 1 and [int(row['relative_frame']) for row in rows] == list(range(FRAMES + 1)),
            'Native observations must include every boundary.')
    first_core = int(rows[0]['core_frame'])
    require([int(row['core_frame']) for row in rows] == list(range(first_core, first_core + FRAMES + 1)),
            'Native emulator frames are not consecutive.')
    require(all(re.fullmatch('[0-9a-f]{64}', row['gpu_sha256']) for row in rows), 'Invalid full GPU-memory hash.')
    _, definitions = read_tsv(folder / 'input-definition.tsv', ('name', 'type', 'initial_value', 'neutral_value'))
    header, submitted = read_tsv(folder / 'submitted.tsv')
    phases = validate_submissions(header, definitions, submitted, rows)
    firsts = {}
    for row in rows:
        firsts.setdefault(row['screen_kind'], int(row['relative_frame']))
    require(firsts.get('startup') == 0 and 0 < firsts.get('main', -1) < firsts.get('dream_session', -1)
            < firsts.get('unlocked_dream', -1), 'The recorded path did not reach an unlocked dream through the main menu.')
    summary = {}
    for phase, values in phases.items():
        ranges = {}
        for field in ('x', 'y', 'z', 'yaw', 'timer', 'input_locked', 'pad_held', 'pad_released', 'pad_pressed'):
            numbers = [int(row[field]) for row in values if row[field] != '-']
            if numbers:
                ranges[field] = [min(numbers), max(numbers)]
        summary[phase] = {'frames': len(values), 'value_ranges': ranges}
    for phase in ('turn_left', 'turn_right'):
        limits = summary.get(phase, {}).get('value_ranges', {}).get('yaw', [0, 0])
        require(limits[0] < limits[1], 'Turning did not change the native yaw: ' + phase)
    for phase in ('walk_forward', 'walk_backwards'):
        limits = summary.get(phase, {}).get('value_ranges', {})
        require(any(limits.get(field, [0, 0])[0] != limits.get(field, [0, 0])[1] for field in ('x', 'z')),
                'Walking did not change the native position: ' + phase)
    _, captures = read_tsv(folder / 'captures.tsv', ('relative_frame', 'core_frame', 'reason'))
    selected = [int(row['relative_frame']) for row in captures]
    require(selected == sorted(set(selected)) and all(0 <= frame <= FRAMES for frame in selected)
            and set(range(0, FRAMES + 1, 600)) <= set(selected) and firsts['unlocked_dream'] in selected,
            'Required checkpoint boundaries are missing.')
    for capture in captures:
        frame = int(capture['relative_frame'])
        require(int(capture['core_frame']) == int(rows[frame]['core_frame']), 'Wrong checkpoint boundary.')
        validate_ram((folder / f'mainram-{frame}.bin').read_bytes(), rows[frame])
        gpu = (folder / f'gpu-{frame}.bin').read_bytes()
        require(len(gpu) == 0x100000 and hashlib.sha256(gpu).hexdigest() == rows[frame]['gpu_sha256'],
                'Checkpoint GPU memory differs from the recorded full hash.')
        require((folder / f'frame-{frame}.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n'), 'Invalid checkpoint PNG.')
    return {'observations': len(rows), 'submitted_frames': len(submitted), 'controller_fields': len(definitions),
            'first_core_frame': first_core, 'last_core_frame': int(rows[-1]['core_frame']),
            'first_observed_relative_frames': firsts, 'phases': summary, 'checkpoint_frames': selected,
            'all_checkpoint_fields_reread_from_full_mainram': True}


def compare_pair(original, rebuilt):
    folders = [Path(original), Path(rebuilt)]
    identity = compare_inputs(*folders, 'boot', FRAMES)
    require(identity['inputs_verified'], 'Require identical schema-2 launch identities.')
    summaries = [inspect_run(folder) for folder in folders]
    require(summaries[0]['checkpoint_frames'] == summaries[1]['checkpoint_frames'], 'Checkpoint schedules differ.')
    files = {name: byte_comparison(*[(folder / name).read_bytes() for folder in folders])
             for name in ('input-definition.tsv', 'submitted.tsv', 'cold-start.tsv', 'captures.tsv')}
    checkpoints = []
    for frame in summaries[0]['checkpoint_frames']:
        item = {'relative_frame': frame}
        for label, name in (('mainram', f'mainram-{frame}.bin'), ('gpu', f'gpu-{frame}.bin'), ('png', f'frame-{frame}.png')):
            item[label] = byte_comparison(*[(folder / name).read_bytes() for folder in folders])
        item['state'] = compare_state(*(folder / f'frame-{frame}.State' for folder in folders))
        checkpoints.append(item)
    audio = compare_audio(*(folder / 'audio.wav' for folder in folders))
    outputs_equal = (all(value['equal'] for value in files.values())
                     and all(item[key]['equal'] for item in checkpoints for key in ('mainram', 'gpu', 'png'))
                     and audio['equal_pcm_output'] and audio['wav_file_bytes']['equal'])
    state_equal = all(item['state']['member_contents_equal'] for item in checkpoints)
    return {'status': 'passed_bounded_cold_start_comparison' if outputs_equal and state_equal else 'recorded_cold_start_differences',
            'recorded_utc': datetime.now(timezone.utc).isoformat(), 'frames_advanced_per_image': FRAMES,
            'input_identity': identity, 'summaries': summaries, 'files': files, 'checkpoints': checkpoints, 'audio': audio,
            'controller_native_RAM_GPU_PNG_audio_outputs_equal': outputs_equal, 'all_state_member_payloads_equal': state_equal,
            'state_bytes_masked': 0, 'new_c_bytes': 0, 'whole_feature_groups_accepted': 0,
            'producer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'One controller-only cold-boot menu/dream/movement history per image, starting at the recorded core frame. '
                     'Native fields are sampled at emulator boundaries. Direct instruction entries, all displayed frames, '
                     'all content, complete NPC encounters, original hardware timing and whole-feature acceptance remain open.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('original', 'rebuilt', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        require(not args.output.exists(), 'Choose a new report path; previous evidence is preserved.')
        report = compare_pair(args.original, args.rebuilt)
        with args.output.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')
        print(json.dumps({key: report[key] for key in ('status', 'controller_native_RAM_GPU_PNG_audio_outputs_equal',
                                                      'all_state_member_payloads_equal', 'state_bytes_masked')}))
        return 0 if report['status'] == 'passed_bounded_cold_start_comparison' else 2
    except (OSError, ValueError, KeyError, TypeError, IndexError, struct.error) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
