"""Compare the fixed Japanese Save/cold-Load research profile without masking bytes."""
import argparse
import csv
from datetime import datetime, timezone
from functools import reduce
import hashlib
import json
from operator import xor
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.compare_runtime import byte_comparison, compare_state
from tools.runtime_inputs import compare_inputs

CARD_NAME = 'LSD - Dream Emulator (Japan).SaveRAM'
CANONICAL_SHA256 = '282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f'
SCRIPT_HASHES = {
    'save': 'bf9d45a702e7a3380b3a90d51bd205610067315afe71f0ad6c62c323e6d3a52f',
    'load': '2d8c014521550ac3fa5431becabb59e002e7ed98e34394497ba3bec08cea9197',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def parse_card(data):
    """Read allocation chains from one raw card; never modify or repair it."""
    require(len(data) == 0x20000 and data[:2] == b'MC', 'Require a raw 128 KiB MC card.')
    entries = [data[i * 128:(i + 1) * 128] for i in range(16)]
    require(all(reduce(xor, entry, 0) == 0 for entry in entries), 'Invalid header/directory checksum.')
    states = [struct.unpack_from('<I', entry)[0] for entry in entries]
    require(all(state in (0x51, 0x52, 0x53, 0xa0, 0xa1, 0xa2, 0xa3)
                for state in states[1:]), 'Unsupported directory allocation state.')
    owned, files = set(), []
    for first in range(1, 16):
        if states[first] != 0x51:
            continue
        name = entries[first][10:31]
        require(b'\0' in name, 'Unterminated filename.')
        try:
            name = name.split(b'\0')[0].decode('ascii')
        except UnicodeDecodeError as error:
            raise ValueError('Non-ASCII card filename.') from error
        require(bool(name), 'Empty allocated filename.')
        blocks, current = [], first
        while True:
            require(1 <= current <= 15 and current not in owned,
                    'Invalid, overlapping or cyclic allocation chain.')
            owned.add(current)
            blocks.append(current)
            link = struct.unpack_from('<H', entries[current], 8)[0]
            expected = 0x51 if current == first else (0x53 if link == 0xffff else 0x52)
            require(states[current] == expected, 'Allocation state disagrees with chain position.')
            if link == 0xffff:
                break
            current = link + 1
        size = struct.unpack_from('<I', entries[first], 4)[0]
        require(size == len(blocks) * 0x2000, 'File size disagrees with allocated blocks.')
        files.append({'filename': name, 'blocks': blocks, 'allocated_bytes': size,
                      'data': b''.join(data[i * 0x2000:(i + 1) * 0x2000] for i in blocks)})
    require(owned == {i for i in range(1, 16) if states[i] in (0x51, 0x52, 0x53)},
            'Orphaned allocated block.')
    require(len({item['filename'] for item in files}) == len(files), 'Duplicate active filenames.')
    return files


def lsd_payload(card):
    files = parse_card(card)
    require(len(files) == 1 and files[0]['filename'] == 'BISLPS-01556-01',
            'This profile requires only LSD slot 01.')
    body = files[0]['data']
    require(len(body) == 8192 and body[:4] == b'SC\x13\x01', 'Unexpected LSD save header.')
    payload = body[512:512 + 1792]
    require(payload[:4] == b'J01\0', 'Unexpected LSD save-data magic.')
    require(struct.unpack_from('<I', payload, 8)[0] == 1, 'This profile requires stored day one (day two).')
    return payload


def fields(phase):
    names = ['relative_frame', 'core_frame', 'screen_kind', 'screen', 'dream',
             'stored_day', 'new_game', f'{phase}_seen', f'{phase}_returned',
             'pad_held', 'pad_released', 'pad_pressed']
    for name, last in (('screen', 0xc0), ('card', 0x80), ('comment', 0x48), ('select', 0x50)):
        names.extend(f'{name}_{offset:02x}' for offset in range(0, last + 1, 4))
    return names + ['gpu_sha256']


def table(path):
    with Path(path).open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        names, rows = reader.fieldnames, list(reader)
    require(names and len(set(names)) == len(names) and rows, 'Missing or duplicate table columns.')
    require(all(None not in row and all(value is not None for value in row.values()) for row in rows),
            'Malformed table row.')
    return names, rows


def expected_action(row, phase, main_seen):
    if row[f'{phase}_returned'] == '1':
        return 'neutral_after_card_return', ''
    if row['screen_kind'] == 'graph':
        return 'leave_chart', 'P1 \u25cb'
    if row['screen_kind'] != 'main':
        if phase == 'load' and not main_seen:
            return 'skip_startup_with_circle', 'P1 \u25cb'
        return 'wait_for_main', ''
    if row['card_24'] != '-' and (row['card_24'] != '0' or row[f'{phase}_seen'] == '1'):
        return ('accept_comment' if row['comment_00'] != '-' else 'confirm_card_dialog'), 'P1 \u25cb'
    target, index = (2 if phase == 'save' else 3), int(row['screen_58'])
    if index < target:
        return f'select_{phase}_down', 'P1 D-Pad Down'
    if target < index < 6:
        return f'select_{phase}_up', 'P1 D-Pad Up'
    if index == target:
        return f'open_{phase}', 'P1 \u25cb'
    return 'wait_for_menu', ''


def validate_trace(folder, phase, frames):
    names, observed = table(folder / 'card.tsv')
    require(names == fields(phase) and len(observed) == frames + 1, 'Wrong native trace shape.')
    _, definitions = table(folder / 'input-definition.tsv')
    keys = [row['name'] for row in definitions]
    digital = [row['name'] for row in definitions if row['type'] == 'boolean']
    analog = {row['name']: row['neutral_value'] for row in definitions if row['type'] == 'number'}
    require(len(keys) == len(set(keys)) == 26 and len(digital) == 21 and len(analog) == 5,
            'Wrong controller definition.')
    require(all(row['neutral_value'] == 'false' for row in definitions if row['type'] == 'boolean'),
            'Digital controls must be explicitly neutralized.')
    input_fields, submitted = table(folder / 'submitted.tsv')
    require(input_fields == ['relative_frame', 'core_frame', 'mode', 'button', *sorted(keys)]
            and len(submitted) == frames, 'Wrong submitted input shape.')
    seen, returned, main_seen = False, False, False
    mode, button = 'initial_neutral', ''
    first_seen = first_returned = None
    for frame, row in enumerate(observed):
        require(row['relative_frame'] == str(frame), 'Nonconsecutive native frames.')
        require(int(row['core_frame']) == int(observed[0]['core_frame']) + frame, 'Skipped core frame.')
        require(bool(re.fullmatch('[0-9a-f]{64}', row['gpu_sha256'])), 'Malformed GPU hash.')
        require(row['screen_kind'] in ('none', 'graph', 'main'), 'Unknown screen kind.')
        if row['screen_kind'] != 'none':
            expected_vtable = 0x80086b60 if row['screen_kind'] == 'main' else 0x80087aac
            require(int(row['screen_00']) == expected_vtable and int(row['screen_a4']) == int(row['dream']) + 0x80000000,
                    'Wrong screen binding.')
        if row['screen_kind'] == 'main':
            main_seen = True
        if row['card_00'] != '-':
            require(int(row['card_00']) == 0x80086dc4, 'Wrong card vtable.')
            operation, state = int(row['card_24']), int(row['card_28'])
            require(0 <= operation <= 2 and 0 <= state <= 23, 'Unsupported native card state.')
            if operation == (2 if phase == 'save' else 1) and state:
                if not seen:
                    first_seen = frame
                seen = True
            if seen and operation == state == 0:
                if not returned:
                    first_returned = frame
                returned = True
        require(row[f'{phase}_seen'] == str(int(seen)) and row[f'{phase}_returned'] == str(int(returned)),
                'Derived operation flags disagree with native fields.')
        if frame == frames:
            break
        requested_frame, request = frame + 1, submitted[frame]
        if requested_frame % 120 == 60:
            mode, button = expected_action(row, phase, main_seen)
        pressed = button if 60 <= requested_frame % 120 < 72 else ''
        require(request['relative_frame'] == str(requested_frame) and request['core_frame'] == row['core_frame'],
                'Input/core alignment differs.')
        require(request['mode'] == mode and request['button'] == pressed, 'Input route differs from the fixed observer.')
        for name in digital:
            require(request[name] == str(name == pressed).lower(), 'Unexpected submitted digital input.')
        for name, value in analog.items():
            require(float(request[name]) == float(value), 'Changed numeric controller baseline.')
    require(first_seen is not None and first_returned is not None, 'Card operation did not complete.')
    return {'rows': len(observed), 'columns': len(names), 'controller_rows': len(submitted),
            'first_registered_frame': first_seen, 'first_returned_frame': first_returned,
            'observed': observed}


def validate_checkpoint(raw, row):
    """Re-read recorded native words independently from the complete RAM dump."""
    require(len(raw) == 0x200000, 'Wrong checkpoint RAM size.')

    def word(address):
        require(0 <= address <= len(raw) - 4 and address % 4 == 0, 'Invalid native word address.')
        return struct.unpack_from('<I', raw, address)[0]

    def pointer(value):
        require(0x80010000 <= value <= 0x801ffffc and value % 4 == 0, 'Invalid native pointer.')
        return value & 0x1fffffff

    bases = {'screen': None, 'card': None, 'comment': None, 'select': None}
    if row['dream'] != '-':
        flow = pointer(word(0x8ac20))
        dream = pointer(word(flow + 0x28))
        require(word(flow) == 0x8006d3c8 and word(dream) == 0x80087bdc
                and dream == int(row['dream']), 'Wrong checkpoint game/dream binding.')
        pad = pointer(word(pointer(word(flow + 0x1c)) + 4))
        require(word(pad) == 0x8006d370, 'Wrong checkpoint pad binding.')
        for name, address in (('stored_day', dream + 0x180), ('new_game', dream + 0x878),
                              ('pad_held', pad + 0x10), ('pad_released', pad + 0x14), ('pad_pressed', pad + 0x18)):
            require(int(row[name]) == word(address), 'Checkpoint semantic field disagrees with RAM: ' + name)
    if row['screen'] != '-':
        bases['screen'] = int(row['screen'])
        if row['screen_kind'] == 'main' and word(bases['screen'] + 0xac):
            bases['card'] = pointer(word(bases['screen'] + 0xac))
            for prefix, offset in (('comment', 0x78), ('select', 0x7c)):
                if word(bases['card'] + offset):
                    bases[prefix] = pointer(word(bases['card'] + offset))
    for prefix, last in (('screen', 0xc0), ('card', 0x80), ('comment', 0x48), ('select', 0x50)):
        for offset in range(0, last + 1, 4):
            value = row[f'{prefix}_{offset:02x}']
            require(value == '-' if bases[prefix] is None else value == str(word(bases[prefix] + offset)),
                    f'Checkpoint {prefix} word {offset:#x} disagrees with RAM.')


def compare_pair(original, rebuilt, phase, frames):
    original, rebuilt = Path(original), Path(rebuilt)
    script = ROOT / 'research/card_roundtrip' / f'{phase}.lua'
    require(digest(script.read_bytes()) == SCRIPT_HASHES[phase], 'Supported observer bytes changed.')
    identity = compare_inputs(original, rebuilt, 'play', frames)
    require(identity['inputs_verified'] and identity['declared_inputs_identical'], 'Unverified/different launch inputs.')
    require(identity['identity']['start_kind'] == ('saved_state' if phase == 'save' else 'cold_boot'),
            'Wrong start kind for this operation.')
    summaries = []
    cards = []
    for folder in (original, rebuilt):
        require(json.loads((folder / 'exit.json').read_text(encoding='utf-8'))['exit_code'] == 0,
                'Owned QA process did not exit successfully.')
        require((folder / 'completed.txt').read_text(encoding='utf-8').startswith(f'{frames} frames;')
                and not (folder / 'failed.txt').exists(), 'Incomplete recorder.')
        require((folder / 'runtime_smoke.lua').read_bytes() == script.read_bytes(), 'Wrong executed observer.')
        summaries.append(validate_trace(folder, phase, frames))
        records = json.loads((folder / 'exit-save-records.json').read_text(encoding='utf-8'))
        require(records['shared_save_ram_empty'], 'Owned exit saves were not preserved.')
        expected_paths = {f'exit-save-ram/{CARD_NAME}', *([f'exit-save-ram/{CARD_NAME}.bak'] if phase == 'load' else [])}
        actual_paths = set()
        for record in records['files_preserved']:
            relative = record['relative_path'].replace('\\', '/')
            require(relative in expected_paths and relative not in actual_paths, 'Unexpected exit-save record.')
            actual_paths.add(relative)
            require(digest((folder / relative).read_bytes()) == record['sha256'], 'Changed persisted save.')
        require(actual_paths == expected_paths, 'Missing persisted card or backup.')
        cards.append((folder / 'exit-save-ram' / CARD_NAME).read_bytes())
        lsd_payload(cards[-1])
        if phase == 'load':
            seed = (folder / 'input-card.SaveRAM').read_bytes()
            lsd_payload(seed)
            external = json.loads((folder / 'external-save-inputs.json').read_text(encoding='utf-8'))
            require(external['source_card_sha256'] == digest(seed) and len(external['files']) == 1
                    and external['files'][0]['sha256'] == digest(seed), 'Wrong cold-boot card provenance.')
            require(seed == cards[-1] == (folder / 'exit-save-ram' / (CARD_NAME + '.bak')).read_bytes(),
                    'Load changed the persisted card.')
        for frame in (summaries[-1]['first_returned_frame'], frames):
            raw = (folder / f'mainram-{frame}.bin').read_bytes()
            require(len(raw) == 0x200000, 'Wrong checkpoint main RAM size.')
            dream = int(summaries[-1]['observed'][frame]['dream'])
            require(raw[dream + 0x178:dream + 0x878] == lsd_payload(cards[-1]), 'Save payload differs from native data.')
        if phase == 'load':
            present = [r for r in summaries[-1]['observed'] if r['stored_day'] != '-']
            require((present[0]['stored_day'], present[0]['new_game']) == ('0', '1'), 'Not a fresh game before Load.')
            returned_row = summaries[-1]['observed'][summaries[-1]['first_returned_frame']]
            require((returned_row['stored_day'], returned_row['new_game']) == ('1', '0'), 'Day/new-game state was not restored.')
    files = {name: byte_comparison((original / name).read_bytes(), (rebuilt / name).read_bytes())
             for name in ('card.tsv', 'submitted.tsv', 'input-definition.tsv', 'captures.tsv', 'completed.txt',
                          'external-save-inputs.json', 'exit-save-records.json')}
    capture_names, captures = table(original / 'captures.tsv')
    other_names, other_captures = table(rebuilt / 'captures.tsv')
    require(capture_names == other_names == ['relative_frame', 'core_frame', 'reason'], 'Wrong checkpoint columns.')
    require(captures == other_captures, 'Checkpoint schedules differ.')
    checkpoint_frames = [int(row['relative_frame']) for row in captures]
    require(all(0 <= frame <= frames for frame in checkpoint_frames)
            and len(set(checkpoint_frames)) == len(checkpoint_frames)
            and set(range(0, frames + 1, 600)) <= set(checkpoint_frames)
            and {frames, summaries[0]['first_returned_frame'], summaries[1]['first_returned_frame']} <= set(checkpoint_frames),
            'Required checkpoints are missing.')
    checkpoints = []
    for frame in checkpoint_frames:
        item = {'relative_frame': frame}
        capture = next(row for row in captures if int(row['relative_frame']) == frame)
        require(capture['core_frame'] == summaries[0]['observed'][frame]['core_frame']
                == summaries[1]['observed'][frame]['core_frame'], 'Checkpoint/core alignment differs.')
        for key, name, size in (('mainram', f'mainram-{frame}.bin', 0x200000),
                                ('gpu', f'gpu-{frame}.bin', 0x100000), ('image', f'frame-{frame}.png', None)):
            data = [(folder / name).read_bytes() for folder in (original, rebuilt)]
            require(all(data) and (size is None or all(len(value) == size for value in data)), 'Invalid checkpoint extent.')
            item[key] = byte_comparison(*data)
            if key == 'mainram':
                for index in (0, 1):
                    validate_checkpoint(data[index], summaries[index]['observed'][frame])
            if key == 'gpu':
                require(all(digest(data[index]) == summaries[index]['observed'][frame]['gpu_sha256'] for index in (0, 1)),
                        'GPU dump disagrees with its per-frame hash.')
        item['state'] = compare_state(original / f'frame-{frame}.State', rebuilt / f'frame-{frame}.State')
        checkpoints.append(item)
    equal = (all(item['equal'] for item in files.values()) and cards[0] == cards[1]
             and all(all(item[key]['equal'] for key in ('mainram', 'gpu', 'image'))
                     and item['state']['member_contents_equal'] for item in checkpoints))
    return {'phase': phase, 'frames': frames, 'inputs': identity, 'files': files, 'checkpoints': checkpoints,
            'observations': [{key: value for key, value in summary.items() if key != 'observed'} for summary in summaries],
            'cards_equal': cards[0] == cards[1], 'card_sha256': [digest(card) for card in cards],
            'payload_sha256': [digest(lsd_payload(card)) for card in cards],
            'complete_recorded_outputs_equal': equal, 'observer_sha256': digest(script.read_bytes())}


def compare_roundtrip(save_original, save_rebuilt, load_original, load_rebuilt):
    save = compare_pair(save_original, save_rebuilt, 'save', 2400)
    load = compare_pair(load_original, load_rebuilt, 'load', 6000)
    seeds = [(Path(folder) / 'input-card.SaveRAM').read_bytes() for folder in (load_original, load_rebuilt)]
    require(all(digest(seed) == save['card_sha256'][index] for index, seed in enumerate(seeds)),
            'Cold Load inputs are not the cards from the paired Save runs.')
    equal = save['complete_recorded_outputs_equal'] and load['complete_recorded_outputs_equal']
    return {'status': 'equal_recorded_card_roundtrip' if equal else 'different_recorded_card_outputs',
            'recorded_utc': datetime.now(timezone.utc).isoformat(), 'save': save, 'load': load,
            'persisted_payload_bytes': 1792, 'cross_restart_payload_verified': True,
            'state_bytes_masked': 0, 'audio_captured': False, 'new_c_bytes': 0,
            'whole_feature_groups_accepted': 0, 'model_api_calls': 0,
            'producer_sha256': digest(Path(__file__).read_bytes()),
            'scope': 'One Japanese slot-01 warm-state Save and cold-boot Load history. All raw checkpoint/state payloads remain compared. Missing/full/corrupt cards, cancellation, all slots, physical cards, audio and hardware timing remain open.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('save-original', 'save-rebuilt', 'load-original', 'load-rebuilt', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    require(output.suffix.lower() == '.json' and output.is_relative_to(ROOT / '.decomp-lab')
            and not output.exists(), 'Use a new JSON output under .decomp-lab.')
    require(digest((ROOT / 'build/SLPS015.56').read_bytes()) == CANONICAL_SHA256,
            'The current build is not canonical.')
    report = compare_roundtrip(args.save_original, args.save_rebuilt, args.load_original, args.load_rebuilt)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'status': report['status'], 'cross_restart_payload_verified': True,
                      'new_c_bytes': 0, 'state_bytes_masked': 0}))
    return int(report['status'] != 'equal_recorded_card_roundtrip')


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, struct.error) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
