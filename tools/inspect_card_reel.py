"""Compare cold recordings of the constructed-card, history-triggered reel route.

The supplied card is an external test input, not naturally earned history. SDK
queue headers are observations, not evidence that every concatenated film was
decoded. The reader keeps one bounded native row at a time.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import compare_movie_playback as playback
from tools.inspect_movie_windows import FIELDS as MOVIE_FIELDS, bounded_file, controller_schema
from tools.inspect_opening_attract import uint, validate_windows
from tools.inspect_progression_history import document, digest, integer, png_rgb, require

SCENE_FIELDS = (
    'flow', 'dream', 'year', 'day', 'stored_day', 'new_game', 'dream_timer', 'dream_limit', 'dream_paused',
    'main', 'main_selection', 'main_state', 'card', 'card_operation', 'card_state',
    'graph', 'graph_timer', 'graph_state', 'graph_result', 'graph_reel_ready', 'graph_event_index',
    'history_flag', 'four_cells_found', 'payload_sha256', 'main_seen', 'load_seen', 'load_returned', 'dream_started',
    'reel_seen', 'reel_cleared', 'movie_player', 'player_path', 'player_threshold', 'player_length', 'player_result', 'player_done',
    'sdk_next_index', 'sdk_header_base', 'sdk_data_index', 'sdk_header_00', 'sdk_header_04', 'sdk_header_08',
    'sdk_header_0c', 'sdk_header_10', 'sdk_header_14', 'sdk_header_18', 'sdk_header_1c',
)
FIELDS = MOVIE_FIELDS + SCENE_FIELDS
STICKY = ('main_seen', 'load_seen', 'load_returned', 'dream_started', 'reel_seen', 'reel_cleared')
ADDRESSES = ('flow', 'dream', 'main', 'card', 'graph', 'movie_player')
SIGNED = ('main_selection', 'sdk_next_index', 'sdk_data_index')
REEL_PATH = '/CDI/FILM/SPDAY01A.STR'
REEL_CUTOFF = 0xffffffff
REEL_LENGTH = 10110
MAX_FRAMES = 80001
LINE_LIMIT = 4096
RAW_LIMIT = 96 * 1024**2
GZIP_LIMIT = 1310720
IMAGES = ('load-return.png', 'reel-start.png', 'reel-plus-600.png', 'final.png')
REPORT_FIELDS = {
    'schema_version', 'status', 'mode', 'frames_advanced', 'last_frame', 'total_PCM_sample_frames', 'raw_native_bytes',
    'load_seen', 'load_returned', 'load_returned_frame', 'dream_started', 'reel_seen', 'first_reel_frame',
    'reel_cleared_frame', 'post_reel_frames', 'input_card_sha256', 'final_SaveRAM_sha256', 'final_SaveRAM_matches_stored',
    'expected_payload_sha256', 'prepared_external_card_loaded_using_ISaveRam', 'replayed_inputs', 'cold_start',
    'restored_state', 'main_RAM_or_instruction_writes', 'player_UI_or_saves_accessed', 'hardware_timing_verified',
    'whole_feature_groups_accepted', 'controller_buttons', 'controller_neutral_axes', 'elapsed_ms',
}
STORE_FIELDS = {
    'core_frame', 'initial_SaveRAM_bytes', 'initial_SaveRAM_sha256', 'input_card_sha256', 'stored_SaveRAM_sha256',
    'expected_payload_sha256', 'MainRAM_before_sha256', 'MainRAM_after_sha256', 'GPURAM_before_sha256',
    'GPURAM_after_sha256', 'prepared_external_card_loaded_using_ISaveRam', 'main_RAM_or_instruction_writes',
    'restored_state', 'user_player_saves_accessed',
}


def catalog():
    data = document((ROOT / 'docs/movie-inventory-checks.json').read_bytes())
    wanted = set(playback.STARTUP_PATHS.values()) | {REEL_PATH}
    result = {}
    for item in data['movies']:
        if item['path'] in wanted:
            require(item['path'] not in result, 'Duplicate movie extent.')
            sectors = integer(item['sectors'], 1, 1000000, 'movie sectors')
            require(item['bytes'] == sectors * 2336, 'Wrong audited raw movie bytes.')
            result[item['path']] = dict(filename=item['path'].rsplit('/', 1)[1] + ';1',
                lba=integer(item['lba'], 0, 0x7fffffff, 'movie LBA'), logical_bytes=sectors * 2048, sectors=sectors)
    require(set(result) == wanted, 'Missing movie extent.')
    return result


def validate_report(report):
    require(isinstance(report, dict) and set(report) == REPORT_FIELDS, 'Wrong card-reel report fields.')
    require(type(report['schema_version']) is int and report['schema_version'] == 3
            and report['status'] == 'card_reel_cleared_and_post_window_completed'
            and report['mode'] == 'card-reel', 'Card-reel recording is incomplete or unsupported.')
    for key in ('cold_start', 'prepared_external_card_loaded_using_ISaveRam', 'load_seen', 'load_returned',
                'dream_started', 'reel_seen', 'final_SaveRAM_matches_stored'):
        require(report[key] is True, 'Missing required card-reel scope: ' + key)
    for key in ('restored_state', 'main_RAM_or_instruction_writes', 'player_UI_or_saves_accessed', 'hardware_timing_verified'):
        require(report[key] is False, 'Unsupported mutation/player/hardware claim.')
    integer(report['whole_feature_groups_accepted'], 0, 0, 'whole feature acceptance')
    frames = integer(report['frames_advanced'], 1, MAX_FRAMES, 'advanced frames')
    integer(report['last_frame'], frames - 1, frames - 1, 'last frame')
    load = integer(report['load_returned_frame'], 1, frames - 1, 'card load return frame')
    first = integer(report['first_reel_frame'], load + 1, frames - 1, 'first reel frame')
    cleared = integer(report['reel_cleared_frame'], first + 601, frames - 1, 'reel clear frame')
    integer(report['post_reel_frames'], 180, 180, 'post-reel frames')
    require(frames - 1 == cleared + 180, 'Wrong post-reel interval.')
    integer(report['total_PCM_sample_frames'], 0, frames * 5000, 'PCM sample frames')
    integer(report['raw_native_bytes'], 1, RAW_LIMIT, 'raw native bytes')
    integer(report['elapsed_ms'], 0, 1800000, 'elapsed milliseconds')
    require(type(report['replayed_inputs']) is bool, 'Invalid exact-input replay role.')
    for key in ('input_card_sha256', 'final_SaveRAM_sha256', 'expected_payload_sha256'):
        digest(report[key], key)
    require(report['input_card_sha256'] == report['final_SaveRAM_sha256'], 'Recorded final card differs from the stored input.')
    controller_schema(report)
    return frames


def validate_store(store, report):
    require(isinstance(store, dict) and set(store) == STORE_FIELDS, 'Wrong cold-card store fields.')
    integer(store['core_frame'], 0, 0, 'card store core frame')
    integer(store['initial_SaveRAM_bytes'], 131072, 131072, 'qualified SaveRAM layout')
    require(store['prepared_external_card_loaded_using_ISaveRam'] is True
            and all(store[key] is False for key in ('main_RAM_or_instruction_writes', 'restored_state', 'user_player_saves_accessed')),
            'Invalid external card input/mutation scope.')
    for key in STORE_FIELDS:
        if key.endswith('_sha256'):
            digest(store[key], key)
    require(store['input_card_sha256'] == store['stored_SaveRAM_sha256'] == report['input_card_sha256']
            and store['expected_payload_sha256'] == report['expected_payload_sha256'], 'Stored card/payload identity differs.')
    for name in ('MainRAM', 'GPURAM'):
        require(store[name + '_before_sha256'] == store[name + '_after_sha256'], 'External card store changed ' + name + '.')


def input_changes(raw, frames):
    require(raw.endswith(b'\n') and b'\r' not in raw and len(raw) <= 65536, 'Invalid input journal size/newlines.')
    lines = raw.decode('ascii').splitlines()
    require(lines and lines[0] == 'frame\tmask', 'Wrong input journal header.')
    result = []
    for line in lines[1:]:
        values = line.split('\t')
        require(len(values) == 2, 'Wrong input journal columns.')
        frame, mask = map(uint, values)
        require(frame < frames and mask in (0, 1, 2, 4), 'Unsupported controller input.')
        require(not result or (frame > result[-1][0] and mask != result[-1][1]), 'Redundant/out-of-order input changes.')
        result.append((frame, mask))
    require(result and result[0] == (0, 0), 'Require neutral initial input.')
    return result


def controller_policy(frame, previous):
    """Recompute the recorder's UI-only policy from the preceding observation."""
    if frame % 120 < 60 or frame % 120 >= 72 or (previous and previous['reel_seen'] == '1'):
        return 0
    if previous is None or previous['main_seen'] == '0':
        return 1
    if previous['main'] == '0':
        return 0
    selection = int(previous['main_selection'])
    if previous['load_returned'] == '0':
        # The host's Scene.operation stays at zero before its card object exists.
        if previous['card_operation'] not in ('0', '-') or previous['load_seen'] == '1':
            return 1
        if selection < 3:
            return 4
        if 3 < selection < 6:
            return 2
        return int(selection == 3)
    if previous['dream_started'] == '0':
        return 2 if 0 < selection < 6 else int(selection == 0)
    return 0


def validate_row(row, frame, previous):
    require(row['relative_frame'] == str(frame) and row['core_frame'] == str(frame + 1), 'Wrong native frame schedule.')
    require(row['native_tables_ready'] in ('0', '1'), 'Invalid native table guard.')
    require(not previous or previous['native_tables_ready'] != '1' or row['native_tables_ready'] == '1', 'Native tables unloaded.')
    address = uint(row['active_movie'])
    if row['native_tables_ready'] == '1':
        uint(row['rng']); uint(row['watchdog_counter'])
    else:
        require(address == 0 and row['rng'] == row['watchdog_counter'] == '-', 'Premature native data.')
    if address:
        require(row['native_tables_ready'] == '1' and playback.aligned_pointer(address, 0x6c), 'Invalid movie pointer.')
        for key in MOVIE_FIELDS[6:]:
            uint(row[key])
        require(row['movie_00'] == str(0x8006f614) and row['stream_00'] == str(0x800817e0)
                and playback.aligned_pointer(int(row['movie_60']), 0x5c), 'Invalid movie/stream vtable chain.')
        require((row['movie_24'], row['movie_28']) == ('320', '240')
                and row['movie_44'] in ('0', '1') and row['movie_48'] in ('0', '1'), 'Invalid movie viewport/flags.')
    else:
        require(all(row[key] == '-' for key in MOVIE_FIELDS[6:]), 'Inactive movie words must be absent.')
    for key in SCENE_FIELDS:
        value = row[key]
        if key == 'payload_sha256':
            if value != '-':
                digest(value, key)
        elif key == 'player_path':
            require(value == '-' or value in ('FILM\\SPDAY01A.STR', 'ETC\\ASMK.STR',
                    *('ETC\\OPENING' + letter + '.STR' for letter in 'ABCDEFG')), 'Unsupported player path.')
        elif key in SIGNED and value == '-1':
            pass
        elif value != '-':
            uint(value)
        if key in ADDRESSES:
            address_value = uint(value)
            require(address_value == 0 or (0x10000 <= address_value <= 0x1fff00 and address_value % 4 == 0),
                    'Invalid physical scene address.')
        if key in STICKY:
            require(value in ('0', '1') and (not previous or previous[key] != '1' or value == '1'), 'Regressed native route flag.')
    require((row['flow'] == '0') == (row['dream'] == '0'), 'Incomplete flow/dream binding.')
    if row['dream'] != '0':
        require(row['payload_sha256'] != '-' and uint(row['year']) == 0 and uint(row['day']) in (0, 4, 5)
                and row['history_flag'] in ('0', '1') and uint(row['four_cells_found']) <= 4, 'Invalid prepared-history scene.')


def inspect_native(stream, frames, windows, extents, changes, report):
    header = ('\t'.join(FIELDS) + '\n').encode('ascii')
    require(stream.readline(LINE_LIMIT + 1) == header, 'Wrong card-reel native header.')
    whole = hashlib.sha256(header)
    native_hash, control_hash = hashlib.sha256(), hashlib.sha256()
    window_index = window_bytes = raw_bytes = change_index = mask = 0
    previous = active = None
    lifetimes, events = [], {}
    graph_indices = set()
    reel_streaming_samples = 0
    post_main = None
    for frame in range(frames):
        line = stream.readline(LINE_LIMIT + 1)
        require(0 < len(line) <= LINE_LIMIT and line.endswith(b'\n') and b'\r' not in line, 'Missing/oversized native line or wrong newline.')
        values = line[:-1].decode('ascii').split('\t')
        require(len(values) == len(FIELDS), 'Missing/extra native columns.')
        row = dict(zip(FIELDS, values))
        validate_row(row, frame, previous)
        if change_index < len(changes) and changes[change_index][0] == frame:
            mask = changes[change_index][1]
            change_index += 1
        require(mask == controller_policy(frame, previous), 'Submitted controls differ from the UI-only policy.')
        for key in STICKY:
            if row[key] == '1' and (previous is None or previous[key] == '0'):
                events[key] = frame
                if key == 'main_seen':
                    require(row['main'] != '0', 'Main-seen flag lacks a native main object.')
                elif key == 'load_seen':
                    require(row['card'] != '0' and row['card_operation'] == '1'
                            and uint(row['card_state']) != 0, 'Load-seen flag lacks a native card load.')
        if row['load_returned'] == '1' and (previous is None or previous['load_returned'] == '0'):
            require(row['load_seen'] == '1' and row['main'] != '0' and row['card'] != '0'
                    and row['card_operation'] == row['card_state'] == '0'
                    and row['payload_sha256'] == report['expected_payload_sha256']
                    and row['year'] == '0' and row['day'] == '4' and row['history_flag'] == '0'
                    and row['four_cells_found'] == '4', 'Load did not return the complete prepared card payload/history.')
        if row['dream_started'] == '1' and (previous is None or previous['dream_started'] == '0'):
            require(row['load_returned'] == '1' and uint(row['dream_timer']) > 0 and row['dream_paused'] == '0'
                    and row['day'] == '4', 'Dream did not start after the native card load.')
        if row['history_flag'] == '1' and (previous is None or previous['history_flag'] != '1'):
            require(row['dream_started'] == '1' and row['day'] == '5' and row['four_cells_found'] == '4'
                    and row['graph'] != '0' and row['graph_reel_ready'] == '1', 'Missing native four-cell graph trigger.')
            events['history_consumed'] = frame
        if 'history_consumed' in events:
            require(row['history_flag'] == '1' and row['four_cells_found'] == '4' and row['day'] == '5', 'Consumed prepared history changed.')
            if row['graph'] != '0' and row['graph_reel_ready'] == '1':
                index = uint(row['graph_event_index'])
                require(index <= 4, 'Invalid graph flash index.')
                graph_indices.add(index)
        address = uint(row['active_movie'])
        if address:
            cutoff, state = uint(row['movie_5c']), uint(row['stream_2c'])
            path = REEL_PATH if cutoff == REEL_CUTOFF else playback.STARTUP_PATHS.get(cutoff)
            require(path in extents, 'Unsupported routed movie request.')
            identity = playback.native_file_identity(row)
            require(identity == extents[path], 'Native disc filename/LBA/size differs from the audited movie.')
            if active is None:
                require(len(lifetimes) < 3 and ((len(lifetimes) == 0 and cutoff == 90)
                        or (len(lifetimes) == 1 and cutoff in set(playback.STARTUP_PATHS) - {90})
                        or (len(lifetimes) == 2 and cutoff == REEL_CUTOFF)), 'Wrong startup/reel lifetime order.')
                require(state == 1, 'Movie lifetime lacks setup.')
                if cutoff == REEL_CUTOFF:
                    require(events.get('reel_seen') == frame, 'Reel-seen event differs from the first native reel request.')
                active = dict(path=path, requested_threshold=cutoff, first_active_frame=frame,
                    movie=address, stream=uint(row['movie_60']), state=1, streaming_samples=0, maximum_id=-1,
                    file_identity=identity, closed_frame=None)
            require(address == active['movie'] and uint(row['movie_60']) == active['stream']
                    and path == active['path'], 'Movie/stream identity changed within a lifetime.')
            old_state = active['state']
            require(state == old_state or (old_state, state) in ((1, 2), (2, 0)), 'Invalid setup/streaming/closed lifecycle.')
            if cutoff == REEL_CUTOFF:
                require('history_consumed' in events and row['load_returned'] == row['dream_started'] == '1'
                        and row['reel_seen'] == '1' and row['movie_player'] != '0'
                        and row['player_path'] == 'FILM\\SPDAY01A.STR'
                        and row['player_threshold'] == str(REEL_CUTOFF) and row['player_length'] == str(REEL_LENGTH)
                        and state in (1, 2) and row['movie_44'] == row['movie_48'] == '0', 'Invalid history-triggered reel request.')
                if state == 2:
                    require(row['stream_40'] == str(REEL_CUTOFF) and row['stream_58'] == '0', 'Reel bypass counter/threshold differs.')
                    reel_streaming_samples += 1
            elif state == 2:
                counter = uint(row['stream_58'])
                require(row['stream_40'] == str(cutoff) and counter < cutoff
                        and counter in (active['maximum_id'], active['maximum_id'] + 1), 'Startup accepted IDs are not contiguous.')
                active['maximum_id'] = counter
            elif state == 0:
                require(old_state == 2 and mask == 1 and row['movie_44'] == row['movie_48'] == '1'
                        and row['movie_54'] == '0' and uint(row['stream_58']) == active['maximum_id'], 'Closed startup lacks the controller skip lifecycle.')
                active['closed_frame'] = frame
            if state == 2:
                active['streaming_samples'] += 1
            active['state'] = state
        elif active is not None:
            require(active['streaming_samples'] > 0, 'Movie lifetime lacks streaming observations.')
            if active['requested_threshold'] == REEL_CUTOFF:
                require(active['state'] == 2 and events.get('reel_cleared') == frame and mask == 0,
                        'Missing neutral reel pointer removal.')
                active['termination_scope'] = 'configured player interval and active-pointer removal; no sampled MDEC EOF flags'
            else:
                require(active['state'] == 0 and active['closed_frame'] == frame - 1, 'Startup pointer removal lacks its preceding skip.')
                active['termination_scope'] = 'controller skip'
            active['first_inactive_frame_after'] = frame
            lifetimes.append(active)
            active = None
        if 'reel_cleared' in events and row['main'] != '0' and post_main is None:
            post_main = frame
        whole.update(line)
        raw_bytes += len(line)
        require(raw_bytes <= RAW_LIMIT, 'Raw native journal exceeds its bound.')
        native_hash.update(struct.pack('<iii', frame, frame + 1, len(line))); native_hash.update(line)
        control_hash.update(struct.pack('<iiii', frame, frame + 1, 4, mask))
        window_bytes += len(line)
        if frame == windows[window_index]['last_frame']:
            window = windows[window_index]
            require(window['payload_bytes']['native'] == window_bytes
                    and window['framed_sha256']['native'] == native_hash.hexdigest()
                    and window['framed_sha256']['controller'] == control_hash.hexdigest(), 'Independent native/controller framed hash differs.')
            window_index += 1
            window_bytes = 0
            native_hash, control_hash = hashlib.sha256(), hashlib.sha256()
        previous = row
    require(stream.readline(LINE_LIMIT + 1) == b'', 'Extra native rows/trailing bytes.')
    require(window_index == len(windows) and change_index == len(changes), 'Unconsumed hash windows/inputs.')
    require(active is None and len(lifetimes) == 3 and set(events) == set(STICKY) | {'history_consumed'}
            and graph_indices == {0, 1, 2, 3, 4} and post_main is not None, 'Incomplete card/dream/graph/reel/return route.')
    require(events['main_seen'] < events['load_seen'] < events['load_returned'] < events['dream_started']
            < events['history_consumed'] < events['reel_seen'] < events['reel_cleared'] <= post_main
            and events['reel_cleared'] + 180 == frames - 1, 'Wrong native route order/post interval.')
    require(report['load_returned_frame'] == events['load_returned'] and report['first_reel_frame'] == events['reel_seen']
            and report['reel_cleared_frame'] == events['reel_cleared'] and report['raw_native_bytes'] == raw_bytes,
            'Report disagrees with independently read native events/bytes.')
    return dict(complete_card_reel_scope=True, events=events, graph_flash_indices=sorted(graph_indices),
        first_post_reel_main_object_frame=post_main, lifetimes=lifetimes, reel_streaming_samples=reel_streaming_samples,
        raw_native_bytes=raw_bytes, journal_sha256=whole.hexdigest(), concatenated_movie_payloads_consumed_not_claimed=True,
        native_and_controller_hashes_independently_recomputed=True, per_frame_rows_retained_in_reader=False)


def load_recording(folder):
    folder = Path(folder).resolve(strict=True)
    report_raw = bounded_file(folder, 'report.json', 65536)
    report = document(report_raw)
    frames = validate_report(report)
    require(not (folder / 'STOP').exists(), 'Stopped recording is incomplete.')
    store = document(bounded_file(folder, 'card-store.json', 65536))
    validate_store(store, report)
    inputs_raw = bounded_file(folder, 'inputs.tsv', 65536)
    changes = input_changes(inputs_raw, frames)
    windows = [document(line) for line in bounded_file(folder, 'windows.jsonl', 1024**2).splitlines()]
    validate_windows(windows, frames, report['total_PCM_sample_frames'])
    path = folder / 'native.tsv.gz'
    require(path.resolve(strict=True).parent == folder and path.is_file() and path.stat().st_size <= GZIP_LIMIT,
            'Native gzip leaves the folder or exceeds its bound.')
    with gzip.open(path, 'rb') as stream:
        native = inspect_native(stream, frames, windows, catalog(), changes, report)
    images = {name: png_rgb(bounded_file(folder, name, 4 * 1024**2)) for name in IMAGES}
    return dict(report=report, card_store=store, windows=windows, native=native, images=images,
        inputs_sha256=hashlib.sha256(inputs_raw).hexdigest(), report_sha256=hashlib.sha256(report_raw).hexdigest(),
        dimensions=dict(frames=frames, complete_state_observations=len(windows),
            PCM_stereo_sample_frames=report['total_PCM_sample_frames'], MainRAM_bytes=frames * 0x200000,
            GPURAM_bytes=frames * 0x100000, RGB_payload_bytes=sum(w['payload_bytes']['RGB'] for w in windows)))


def compare_data(original, rebuilt):
    require(original['native']['complete_card_reel_scope'] is True and rebuilt['native']['complete_card_reel_scope'] is True,
            'Incomplete route cannot pass the card-reel comparison.')
    require(original['report']['replayed_inputs'] is False and rebuilt['report']['replayed_inputs'] is True,
            'Require original-policy and exact-input rebuilt roles.')
    differences = {}
    for key in ('card_store', 'windows', 'native', 'images', 'inputs_sha256', 'dimensions'):
        if original[key] != rebuilt[key]:
            differences[key] = True
    scope = lambda value: {key: item for key, item in value['report'].items() if key not in ('elapsed_ms', 'replayed_inputs')}
    if scope(original) != scope(rebuilt):
        differences['report_scope'] = True
    return dict(schema_version=1, status='equal_for_constructed_card_reel_scope' if not differences else 'recorded_card_reel_differences',
        passed=not differences, dimensions=original['dimensions'], native=original['native'], differences=differences,
        constructed_external_history_card=True, naturally_earned_history_claimed=False,
        full_gameplay_feature_or_NPC_acceptance=False, hardware_timing_verified=False,
        complete_concatenated_movie_consumption_claimed=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=Path)
    parser.add_argument('rebuilt', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        result = compare_data(load_recording(args.original), load_recording(args.rebuilt))
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, zlib.error, EOFError) as error:
        result = dict(status='invalid_or_incomplete_card_reel_recording', passed=False, error=str(error))
        code = 2
    else:
        code = 0 if result['passed'] else 1
    rendered = json.dumps(result, indent=2) + '\n'
    if args.output:
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(rendered)
    print(rendered, end='')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
