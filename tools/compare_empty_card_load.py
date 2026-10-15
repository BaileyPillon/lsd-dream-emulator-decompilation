"""Verify the fixed controller-only cold Load of a formatted empty PS1 card."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.compare_card_roundtrip import (
    CARD_NAME, CANONICAL_SHA256, SCRIPT_HASHES, digest, parse_card, require,
    table, validate_checkpoint, validate_trace,
)
from tools.compare_runtime import byte_comparison, compare_state
from tools.runtime_inputs import compare_inputs

FRAMES = 6000


def validate_empty_card(card):
    require(not parse_card(card), 'Require an empty card with no allocated files.')
    require(all(struct.unpack_from('<I', card, block * 128)[0] == 0xa0
                and struct.unpack_from('<H', card, block * 128 + 8)[0] == 0xffff
                for block in range(1, 16)), 'Require fifteen free, unlinked card blocks.')


def validate_card_transition(seed, card, backup):
    validate_empty_card(seed)
    validate_empty_card(card)
    require(backup == seed, 'The backup does not preserve the input card.')
    # This fixed BIOS/core profile writes its header into block 0, frame 63.
    # Verify the complete resulting image, then compare both runs without masking.
    expected = seed[:63 * 128] + seed[:128] + seed[64 * 128:]
    require(card == expected, 'Unexpected card transition outside the header write-test copy.')
    return {'input_sha256': digest(seed), 'exit_sha256': digest(card),
            'backup_sha256': digest(backup), 'complete_expected_exit_verified': True,
            'changes': [{'offset': index, 'before': before, 'after': after}
                        for index, (before, after) in enumerate(zip(seed, card)) if before != after]}


def validate_empty_route(observed, first_returned):
    present = [row for row in observed if row['card_24'] != '-']
    transitions = []
    for row in present:
        state = (int(row['card_24']), int(row['card_28']))
        if not transitions or transitions[-1] != state:
            transitions.append(state)
    require(transitions == [(1, 0), (1, 13), (0, 0)], 'Not the fixed empty-card Load route.')
    require(all((row['stored_day'], row['new_game']) == ('0', '1')
                for row in observed if row['dream'] != '-'), 'Empty-card Load changed day/new-game state.')
    require(all(row['comment_00'] == row['select_00'] == '-' for row in observed),
            'Empty-card Load unexpectedly constructed a comment or save-selection menu.')
    registered = next(int(row['relative_frame']) for row in present if row['card_28'] == '13')
    require(registered < first_returned and observed[first_returned]['screen_kind'] == 'main',
            'Missing not-found dialog or return to the main screen.')
    return {'not_found_state': 13, 'first_not_found_frame': registered,
            'first_returned_frame': first_returned, 'stored_day': 0, 'new_game': 1}


def not_found_resource(image):
    require(digest(image) == CANONICAL_SHA256, 'Require the canonical executable.')
    load = struct.unpack_from('<I', image, 0x18)[0]

    def offset(address, size=1):
        start = 0x800 + address - load
        require(0x800 <= start <= len(image) - size, 'Resource address outside executable.')
        return start

    def text(address):
        start = offset(address)
        end = image.find(b'\0', start, start + 80)
        require(end >= start, 'Unterminated card resource string.')
        return image[start:end].decode('ascii')

    pointer = struct.unpack_from('<I', image, offset(0x80086e80 + 13 * 4, 4))[0]
    name = text(0x8008aab4) + text(pointer) + text(0x8008aabc)
    require(name == 'CARD\\NOTFOUND.TIM', 'Unexpected not-found resource binding.')
    return {'state': 13, 'table_address': '0x80086e80', 'resource': name}


def compare_empty_load(original, rebuilt):
    folders = [Path(original), Path(rebuilt)]
    script = ROOT / 'research/card_roundtrip/load.lua'
    require(digest(script.read_bytes()) == SCRIPT_HASHES['load'], 'Supported observer bytes changed.')
    inputs = compare_inputs(*folders, 'play', FRAMES)
    require(inputs['inputs_verified'] and inputs['declared_inputs_identical']
            and inputs['identity']['start_kind'] == 'cold_boot', 'Require identical cold-boot inputs.')
    summaries, routes, seeds, transitions, exit_cards = [], [], [], [], []
    for folder in folders:
        require(json.loads((folder / 'exit.json').read_text(encoding='utf-8'))['exit_code'] == 0,
                'Owned QA process did not exit successfully.')
        require((folder / 'completed.txt').read_text(encoding='utf-8').startswith(f'{FRAMES} frames;')
                and not (folder / 'failed.txt').exists(), 'Incomplete recorder.')
        require((folder / 'runtime_smoke.lua').read_bytes() == script.read_bytes(), 'Wrong executed observer.')
        summary = validate_trace(folder, 'load', FRAMES)
        summaries.append(summary)
        routes.append(validate_empty_route(summary['observed'], summary['first_returned_frame']))
        seed = (folder / 'input-card.SaveRAM').read_bytes()
        validate_empty_card(seed)
        seeds.append(seed)
        external = json.loads((folder / 'external-save-inputs.json').read_text(encoding='utf-8'))
        require(external['source_card_sha256'] == digest(seed) and len(external['files']) == 1
                and external['files'][0]['sha256'] == digest(seed)
                and external['files'][0]['bytes'] == len(seed), 'Wrong cold-boot card provenance.')
        records = json.loads((folder / 'exit-save-records.json').read_text(encoding='utf-8'))
        expected = {f'exit-save-ram/{CARD_NAME}', f'exit-save-ram/{CARD_NAME}.bak'}
        actual = set()
        require(records['shared_save_ram_empty'], 'Owned saves were not preserved.')
        for record in records['files_preserved']:
            relative = record['relative_path'].replace('\\', '/')
            require(relative in expected and relative not in actual, 'Unexpected or duplicate exit-save record.')
            actual.add(relative)
            card = (folder / relative).read_bytes()
            require(record['bytes'] == len(card) and record['sha256'] == digest(card),
                    'Changed persisted card or backup record.')
        require(actual == expected, 'Missing persisted empty card or backup.')
        card = (folder / 'exit-save-ram' / CARD_NAME).read_bytes()
        backup = (folder / 'exit-save-ram' / (CARD_NAME + '.bak')).read_bytes()
        transitions.append(validate_card_transition(seed, card, backup))
        exit_cards.append(card)
    require(seeds[0] == seeds[1], 'Initial empty cards differ.')
    files = {name: byte_comparison((folders[0] / name).read_bytes(), (folders[1] / name).read_bytes())
             for name in ('card.tsv', 'submitted.tsv', 'input-definition.tsv', 'captures.tsv', 'completed.txt',
                          'external-save-inputs.json', 'exit-save-records.json')}
    names, captures = table(folders[0] / 'captures.tsv')
    other_names, other_captures = table(folders[1] / 'captures.tsv')
    require(names == other_names == ['relative_frame', 'core_frame', 'reason'] and captures == other_captures,
            'Wrong or differing checkpoint schedules.')
    frames = [int(row['relative_frame']) for row in captures]
    require(all(0 <= frame <= FRAMES for frame in frames) and len(set(frames)) == len(frames)
            and set(range(0, FRAMES + 1, 600)) <= set(frames)
            and {route[key] for route in routes for key in ('first_not_found_frame', 'first_returned_frame')} <= set(frames),
            'Required empty-card checkpoints are missing.')
    checkpoints = []
    for capture in captures:
        frame = int(capture['relative_frame'])
        require(all(capture['core_frame'] == summary['observed'][frame]['core_frame'] for summary in summaries),
                'Checkpoint/core alignment differs.')
        item = {'relative_frame': frame}
        for key, name, size in (('mainram', f'mainram-{frame}.bin', 0x200000),
                                ('gpu', f'gpu-{frame}.bin', 0x100000), ('image', f'frame-{frame}.png', None)):
            data = [(folder / name).read_bytes() for folder in folders]
            require(all(data) and (size is None or all(len(value) == size for value in data)), 'Wrong checkpoint extent.')
            item[key] = byte_comparison(*data)
            for index in (0, 1):
                if key == 'mainram':
                    validate_checkpoint(data[index], summaries[index]['observed'][frame])
                if key == 'gpu':
                    require(digest(data[index]) == summaries[index]['observed'][frame]['gpu_sha256'],
                            'GPU dump disagrees with its per-frame hash.')
        item['state'] = compare_state(*(folder / f'frame-{frame}.State' for folder in folders))
        checkpoints.append(item)
    game_equal = (all(item['equal'] for item in files.values()) and exit_cards[0] == exit_cards[1]
                  and all(all(item[key]['equal'] for key in ('mainram', 'gpu', 'image')) for item in checkpoints))
    states_equal = all(item['state']['member_contents_equal'] for item in checkpoints)
    equal = game_equal and states_equal
    return {'status': 'equal_recorded_empty_card_load' if equal else 'different_recorded_empty_card_load',
            'recorded_utc': datetime.now(timezone.utc).isoformat(), 'inputs': inputs, 'files': files,
            'routes': routes, 'checkpoints': checkpoints, 'frames_each': FRAMES,
            'recorded_game_buffers_and_inputs_equal': game_equal,
            'complete_state_members_equal': states_equal,
            'complete_recorded_outputs_equal': equal,
            'trace_rows_each': FRAMES + 1, 'trace_columns': len(summaries[0]['observed'][0]),
            'paired_initial_cards_equal': True, 'paired_exit_cards': byte_comparison(*exit_cards),
            'card_transitions': transitions, 'input_card_sha256': digest(seeds[0]),
            'observer_sha256': digest(script.read_bytes()), 'state_bytes_masked': 0,
            'audio_captured': False, 'new_c_bytes': 0, 'whole_feature_groups_accepted': 0,
            'producer_sha256': digest(Path(__file__).read_bytes()),
            'scope': 'One Japanese cold-boot Load with a formatted card and no files. Disconnected, unformatted, full, corrupt, overwrite/cancel, all slots, audio and hardware timing remain open.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('original', 'rebuilt', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    require(output.suffix.lower() == '.json' and output.is_relative_to(ROOT / '.decomp-lab')
            and not output.exists(), 'Use a new JSON output under .decomp-lab.')
    binding = not_found_resource((ROOT / 'build/SLPS015.56').read_bytes())
    report = compare_empty_load(args.original, args.rebuilt)
    report['native_resource_binding'] = binding
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({key: report[key] for key in ('status', 'frames_each', 'trace_rows_each', 'new_c_bytes')}))
    return int(report['status'] != 'equal_recorded_empty_card_load')


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, struct.error) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
