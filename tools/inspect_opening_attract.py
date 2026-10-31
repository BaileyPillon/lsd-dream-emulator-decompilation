"""Stream and compare neutral cold-start recordings of all seven opening choices.

The retained native journal is read one bounded line at a time. Full-buffer
hashes and serialized states are never masked; hardware and whole-feature
acceptance are separate from this recorded scope.
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
from tools.inspect_movie_windows import CHANNELS, FIELDS, WINDOW_FIELDS, bounded_file, controller_schema
from tools.inspect_progression_history import document, digest, integer, png_rgb, require

MAX_FRAMES = 170001
RAW_LIMIT = 96 * 1024**2
GZIP_LIMIT = 2 * 1024**2
LINE_LIMIT = 4096
OPENINGS = set(playback.STARTUP_PATHS) - {90}
REPORT_FIELDS = {
    'schema_version', 'status', 'mode', 'frames_advanced', 'last_frame',
    'total_PCM_sample_frames', 'opening_cutoffs_completed', 'opening_lifetimes_completed',
    'all_openings_cleared_frame', 'post_all_openings_frames', 'skip_submitted_frame',
    'skip_pulse_frames', 'raw_native_bytes', 'replayed_inputs', 'cold_start', 'restored_state',
    'game_RAM_injected', 'player_UI_or_saves_accessed', 'hardware_timing_verified',
    'whole_feature_groups_accepted', 'controller_buttons', 'controller_neutral_axes', 'elapsed_ms',
}


def catalog():
    """Bind native CdlFILE identity to the existing audited mixed-sector inventory."""
    data = document((ROOT / 'docs/movie-inventory-checks.json').read_bytes())
    result = {}
    for item in data['movies']:
        if item['path'] in playback.STARTUP_PATHS.values():
            require(item['path'] not in result, 'Duplicate startup movie inventory path.')
            sectors = integer(item['sectors'], 1, 1000000, 'movie sector count')
            require(item['bytes'] == sectors * 2336, 'Audited movie raw-sector bytes disagree.')
            result[item['path']] = dict(filename=item['path'].rsplit('/', 1)[1] + ';1',
                lba=integer(item['lba'], 0, 0x7fffffff, 'movie LBA'),
                logical_bytes=sectors * 2048, sectors=sectors)
    require(set(result) == set(playback.STARTUP_PATHS.values()), 'Missing startup movie extent.')
    return result


def validate_report(report, allow_incomplete=False):
    require(isinstance(report, dict) and set(report) == REPORT_FIELDS, 'Wrong attract report fields.')
    complete = report['status'] == 'all_openings_cleared_and_post_window_completed'
    require(type(report['schema_version']) is int and report['schema_version'] == 2
            and (complete or (allow_incomplete and report['status'] == 'frame_ceiling_reached')),
            'The all-opening native recording did not finish.')
    require(report['mode'] == 'neutral' and report['cold_start'] is True, 'Require a neutral cold start.')
    require(all(report[key] is False for key in ('restored_state', 'game_RAM_injected',
            'player_UI_or_saves_accessed', 'hardware_timing_verified')),
            'Unsupported mutation/player/hardware scope.')
    integer(report['whole_feature_groups_accepted'], 0, 0, 'whole feature acceptance')
    frames = integer(report['frames_advanced'], 1, MAX_FRAMES, 'advanced frames')
    require(type(report['last_frame']) is int and report['last_frame'] == frames - 1,
            'Final frame disagrees with frame count.')
    integer(report['total_PCM_sample_frames'], 0, frames * 5000, 'total PCM sample frames')
    integer(report['raw_native_bytes'], 1, RAW_LIMIT, 'raw native journal bytes')
    integer(report['all_openings_cleared_frame'], 0 if complete else -1,
            frames - 1 if complete else -1, 'all openings cleared frame')
    integer(report['post_all_openings_frames'], 180 if complete else 0,
            180 if complete else 0, 'post-opening frames')
    integer(report['skip_submitted_frame'], -1, -1, 'neutral skip frame')
    integer(report['skip_pulse_frames'], 0, 0, 'neutral skip pulse')
    integer(report['opening_lifetimes_completed'], 7 if complete else 0, 127, 'opening lifetime count')
    integer(report['elapsed_ms'], 0, 1800000, 'elapsed native milliseconds')
    choices = report['opening_cutoffs_completed']
    require(isinstance(choices, list) and all(type(value) is int for value in choices)
            and choices == sorted(set(choices)) and set(choices) <= OPENINGS
            and (set(choices) == OPENINGS if complete else set(choices) != OPENINGS),
            'All seven opening choices are required for a completed report.')
    require(type(report['replayed_inputs']) is bool, 'Invalid replay role.')
    controller_schema(report)
    return frames


def validate_windows(windows, frames, total_samples):
    next_frame = samples = 0
    require(isinstance(windows, list) and 1 <= len(windows) <= (MAX_FRAMES + 599) // 600,
            'Missing or excessive hash windows.')
    for window in windows:
        require(isinstance(window, dict) and set(window) == WINDOW_FIELDS, 'Wrong window fields.')
        first = integer(window['first_frame'], 0, frames - 1, 'first window frame')
        last = integer(window['last_frame'], first, frames - 1, 'last window frame')
        require(first == next_frame and last == min(first + 599, frames - 1),
                'Missing, overlapping or nonstandard frame window.')
        count = last - first + 1
        integer(window['frames'], count, count, 'window frame count')
        sample_count = integer(window['PCM_sample_frames'], 0, count * 5000, 'window PCM samples')
        sizes, hashes = window['payload_bytes'], window['framed_sha256']
        require(isinstance(sizes, dict) and set(sizes) == CHANNELS
                and isinstance(hashes, dict) and set(hashes) == CHANNELS, 'Missing buffer hash channel.')
        for key in CHANNELS:
            integer(sizes[key], 0, 2 * 1024**3, 'channel payload bytes')
            digest(hashes[key], key)
        require(sizes['MainRAM'] == count * 0x200000 and sizes['GPURAM'] == count * 0x100000
                and sizes['controller'] == count * 4 and sizes['PCM'] == sample_count * 4,
                'Incomplete RAM/GPU/controller/PCM payload coverage.')
        require(count * 11 <= sizes['RGB'] <= count * (8 + 1024 * 1024 * 3), 'Invalid RGB payload coverage.')
        require(count * 2 <= sizes['native'] <= count * LINE_LIMIT, 'Invalid native payload coverage.')
        for key in ('complete_state_sha256', 'final_MainRAM_sha256', 'final_GPURAM_sha256',
                    'final_RGB_with_dimensions_sha256'):
            digest(window[key], key)
        next_frame = last + 1
        samples += sample_count
    require(next_frame == frames and samples == total_samples, 'Incomplete frame/PCM window coverage.')


def uint(text):
    require(text.isascii() and text.isdecimal() and len(text) <= 10, 'Invalid unsigned native word.')
    value = int(text)
    require(0 <= value <= 0xffffffff and str(value) == text, 'Noncanonical unsigned native word.')
    return value


class Lifetime:
    """Aggregate one movie without retaining its per-frame rows or an ID array."""

    def __init__(self, row, frame, sequence, extents):
        self.address = row['active_movie']
        self.stream = row['movie_60']
        self.cutoff = int(row['movie_5c'])
        self.path = playback.STARTUP_PATHS[self.cutoff]
        self.file_words = tuple(row[f'stream_{at:02x}'] for at in range(0x0c, 0x24, 4))
        self.identity = playback.native_file_identity(row)
        require(self.identity == extents[self.path], 'Native movie filename/LBA/size differs from the audited disc.')
        self.first = self.last = frame
        self.sequence = sequence
        self.state = 0
        self.maximum = -1
        self.unique_ids = 0
        self.complete_flag = self.decode_flag = False
        self.setups, self.setup_ids, self.viewports = set(), set(), set()

    def add(self, row, frame):
        require(row['active_movie'] == self.address and row['movie_60'] == self.stream
                and int(row['movie_5c']) == self.cutoff, 'Movie/stream request changed within one lifetime.')
        require(tuple(row[f'stream_{at:02x}'] for at in range(0x0c, 0x24, 4)) == self.file_words,
                'Native CD-file identity changed within one lifetime.')
        state = int(row['stream_2c'])
        require(state >= self.state and (state == self.state or (self.state, state) in ((0, 1), (1, 2), (2, 4))),
                'Invalid neutral setup/streaming/stopped transition.')
        self.state = state
        if state == 1:
            self.setups.add(int(row['stream_40']))
            self.setup_ids.add(int(row['stream_58']))
            require(len(self.setups) <= 8 and len(self.setup_ids) <= 8, 'Excessive setup values.')
        elif state == 2:
            value = int(row['stream_58'])
            require(value in (self.maximum, self.maximum + 1) and value >= 0,
                    'Accepted frame IDs must be nondecreasing and contiguous from zero.')
            if value != self.maximum:
                self.unique_ids += 1
                self.maximum = value
        else:
            require(int(row['stream_58']) == self.maximum, 'Stopped counter differs from accepted streaming ID.')
        self.complete_flag |= row['movie_48'] == '1'
        self.decode_flag |= row['movie_44'] == '1'
        xy = struct.unpack('<hh', struct.pack('<I', int(row['movie_20'])))
        self.viewports.add((*xy, int(row['movie_24']), int(row['movie_28'])))
        require(len(self.viewports) <= 8, 'Excessive source viewports.')
        self.last = frame

    def finish(self, frame):
        require(self.maximum == self.cutoff - 1 and self.unique_ids == self.cutoff
                and self.complete_flag and self.decode_flag and self.state == 4,
                'Incomplete normal movie lifetime or missing completion/stopped fields.')
        return dict(sequence=self.sequence, path=self.path, opened_file=self.identity,
            first_active_frame=self.first, last_active_frame=self.last, first_inactive_frame_after=frame,
            requested_cutoff=self.cutoff, setup_thresholds=sorted(self.setups), setup_raw_frame_values=sorted(self.setup_ids),
            maximum_accepted_frame_id_while_streaming=self.maximum, distinct_accepted_frame_ids=self.unique_ids,
            sampled_ids_contiguous_from_zero=True, movie_complete_flag_observed=self.complete_flag,
            decode_complete_flag_observed=self.decode_flag, observed_complete_lifetime=True,
            source_viewports_xy_width_height=[list(value) for value in sorted(self.viewports)])


def inspect_native(stream, frames, windows, extents, allow_incomplete=False):
    """Consume a binary (possibly gzip) stream with at most one 4 KiB line alive."""
    header = ('\t'.join(FIELDS) + '\n').encode('ascii')
    require(stream.readline(LINE_LIMIT + 1) == header, 'Wrong native journal header.')
    whole = hashlib.sha256(header)
    native_hash, control_hash = hashlib.sha256(), hashlib.sha256()
    raw_bytes = window_bytes = window_index = 0
    ready_seen = False
    active = None
    lifetimes = []
    seen = set()
    all_cleared = None
    for frame in range(frames):
        line = stream.readline(LINE_LIMIT + 1)
        require(0 < len(line) <= LINE_LIMIT and line.endswith(b'\n') and b'\r' not in line,
                'Missing/oversized native line or invalid newline.')
        raw_bytes += len(line)
        require(raw_bytes <= RAW_LIMIT, 'Raw native journal exceeds its bound.')
        whole.update(line)
        values = line[:-1].decode('ascii').split('\t')
        require(len(values) == len(FIELDS), 'Missing/extra native columns.')
        row = dict(zip(FIELDS, values))
        require(row['relative_frame'] == str(frame) and row['core_frame'] == str(frame + 1), 'Native frame schedule differs.')
        require(row['native_tables_ready'] in ('0', '1'), 'Invalid native table guard.')
        ready = row['native_tables_ready'] == '1'
        require(not ready_seen or ready, 'Native tables were unloaded.')
        ready_seen |= ready
        address = uint(row['active_movie'])
        if ready:
            uint(row['rng'])
            uint(row['watchdog_counter'])
        else:
            require(address == 0 and row['rng'] == row['watchdog_counter'] == '-', 'Premature native observations.')
        if address:
            require(ready and playback.aligned_pointer(address, 0x6c), 'Invalid movie address.')
            for key in FIELDS[6:]:
                uint(row[key])
            require(row['movie_00'] == str(0x8006f614) and row['stream_00'] == str(0x800817e0)
                    and playback.aligned_pointer(int(row['movie_60']), 0x5c), 'Invalid native vtable/pointer chain.')
            cutoff, state = int(row['movie_5c']), int(row['stream_2c'])
            require(cutoff in playback.STARTUP_PATHS and state in (1, 2, 4), 'Unsupported neutral startup movie/state.')
            require((int(row['movie_24']), int(row['movie_28'])) == (320, 240), 'Unexpected source viewport.')
            require(row['movie_44'] in ('0', '1') and row['movie_48'] in ('0', '1'), 'Invalid completion flags.')
            if state in (2, 4):
                require(int(row['stream_40']) == cutoff and 0 <= int(row['stream_58']) < cutoff,
                        'Invalid stream threshold/counter.')
            if active is None:
                require((not lifetimes and cutoff == 90) or (lifetimes and cutoff in OPENINGS),
                        'Require one initial logo followed by opening movies.')
                require(len(lifetimes) < 128, 'Excessive movie lifetimes.')
                active = Lifetime(row, frame, len(lifetimes) + 1, extents)
            active.add(row, frame)
        else:
            require(all(row[key] == '-' for key in FIELDS[6:]), 'Inactive native words must be absent.')
            if active is not None:
                life = active.finish(frame)
                lifetimes.append(life)
                if active.cutoff in OPENINGS:
                    seen.add(active.cutoff)
                    if seen == OPENINGS and all_cleared is None:
                        all_cleared = frame
                active = None
        native_hash.update(struct.pack('<iii', frame, frame + 1, len(line)))
        native_hash.update(line)
        control_hash.update(struct.pack('<iiii', frame, frame + 1, 4, 0))
        window_bytes += len(line)
        if frame == windows[window_index]['last_frame']:
            window = windows[window_index]
            require(window['payload_bytes']['native'] == window_bytes, 'Native window byte count differs.')
            require(window['framed_sha256']['native'] == native_hash.hexdigest()
                    and window['framed_sha256']['controller'] == control_hash.hexdigest(),
                    'Independent native/controller framed hash differs.')
            native_hash, control_hash = hashlib.sha256(), hashlib.sha256()
            window_bytes = 0
            window_index += 1
    require(stream.readline(LINE_LIMIT + 1) == b'', 'Extra native journal rows/trailing bytes.')
    complete = active is None and seen == OPENINGS and all_cleared is not None
    require(complete or allow_incomplete, 'All seven completed opening lifetimes are required.')
    require(window_index == len(windows), 'Unconsumed native hash windows.')
    return dict(lifetimes=lifetimes, opening_cutoffs_completed=sorted(seen),
        opening_lifetimes_completed=max(0, len(lifetimes) - 1),
        all_openings_cleared_frame=-1 if all_cleared is None else all_cleared,
        all_seven_openings_completed=complete,
        unfinished_lifetime=None if active is None else dict(path=active.path,
            first_active_frame=active.first, last_active_frame=active.last,
            maximum_accepted_frame_id_while_streaming=active.maximum,
            distinct_accepted_frame_ids=active.unique_ids, observed_complete_lifetime=False),
        raw_native_bytes=raw_bytes, journal_sha256=whole.hexdigest())


def load_recording(folder, allow_incomplete=False):
    folder = Path(folder).resolve(strict=True)
    report_raw = bounded_file(folder, 'report.json', 65536)
    report = document(report_raw)
    frames = validate_report(report, allow_incomplete=allow_incomplete)
    require(not (folder / 'STOP').exists(), 'Stopped recording is incomplete.')
    inputs = bounded_file(folder, 'inputs.tsv', 65536)
    require(inputs == b'frame\tmask\n0\t0\n', 'Neutral input record changed.')
    windows = [document(line) for line in bounded_file(folder, 'windows.jsonl', 1024**2).splitlines()]
    validate_windows(windows, frames, report['total_PCM_sample_frames'])
    path = folder / 'native.tsv.gz'
    require(path.resolve(strict=True).parent == folder and path.is_file() and path.stat().st_size <= GZIP_LIMIT,
            'Native gzip leaves the folder or exceeds its bound.')
    with gzip.open(path, 'rb') as stream:
        native = inspect_native(stream, frames, windows, catalog(), allow_incomplete=allow_incomplete)
    for key in ('opening_cutoffs_completed', 'opening_lifetimes_completed', 'all_openings_cleared_frame', 'raw_native_bytes'):
        require(report[key] == native[key], 'Report disagrees with independently read native ' + key + '.')
    if report['status'] == 'all_openings_cleared_and_post_window_completed':
        require(native['all_seven_openings_completed']
                and report['last_frame'] - native['all_openings_cleared_frame'] == 180,
                'Wrong final post-opening interval.')
    dimensions = dict(frames=frames, windows=len(windows), complete_state_observations=len(windows),
        PCM_stereo_sample_frames=report['total_PCM_sample_frames'], MainRAM_bytes=frames * 0x200000,
        GPURAM_bytes=frames * 0x100000, RGB_payload_bytes=sum(w['payload_bytes']['RGB'] for w in windows),
        native_and_controller_hashes_independently_recomputed=True,
        per_frame_native_rows_retained_in_reader=False, maximum_native_line_bytes=LINE_LIMIT)
    return dict(report=report, windows=windows, native=native, inputs_sha256=hashlib.sha256(inputs).hexdigest(),
        dimensions=dimensions, final_image=png_rgb(bounded_file(folder, 'final.png', 8 * 1024**2)),
        report_sha256=hashlib.sha256(report_raw).hexdigest())


def compare_data(original, rebuilt):
    require(original['native']['all_seven_openings_completed'] is True
            and rebuilt['native']['all_seven_openings_completed'] is True,
            'Incomplete attract data cannot pass the all-seven comparison.')
    require(original['report']['replayed_inputs'] is False and rebuilt['report']['replayed_inputs'] is True,
            'Require original-policy and exact-input rebuilt roles.')
    differences = {}
    for key in ('native', 'inputs_sha256', 'dimensions'):
        if original[key] != rebuilt[key]:
            differences[key] = True
    left = {key: value for key, value in original['report'].items() if key not in ('replayed_inputs', 'elapsed_ms')}
    right = {key: value for key, value in rebuilt['report'].items() if key not in ('replayed_inputs', 'elapsed_ms')}
    if left != right:
        differences['report_scope'] = True
    if original['windows'] != rebuilt['windows']:
        differences['windows'] = [index for index in range(max(len(original['windows']), len(rebuilt['windows'])))
            if index >= min(len(original['windows']), len(rebuilt['windows']))
            or original['windows'][index] != rebuilt['windows'][index]]
    if any(original['final_image'][key] != rebuilt['final_image'][key] for key in ('width', 'height', 'RGB_sha256')):
        differences['decoded_final_PNG'] = True
    return dict(schema_version=1, status='equal_for_all_opening_attract_scope' if not differences else 'recorded_attract_differences',
        passed=not differences, dimensions=original['dimensions'], lifetimes=original['native']['lifetimes'],
        distinct_opening_choices=7, routed_movie_payloads_observed=8, total_routed_movie_payloads=39,
        opening_lifetimes_completed=original['native']['opening_lifetimes_completed'],
        all_openings_cleared_frame=original['native']['all_openings_cleared_frame'],
        original_native_journal_sha256=original['native']['journal_sha256'],
        rebuilt_native_journal_sha256=rebuilt['native']['journal_sha256'],
        original_report_sha256=original['report_sha256'], rebuilt_report_sha256=rebuilt['report_sha256'],
        differences=differences, whole_feature_groups_accepted=0, whole_NPC_encounters_accepted=0,
        hardware_timing_verified=False, complete_all_movie_or_ending_playback_verified=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=Path)
    parser.add_argument('rebuilt', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output:
            target = args.output.resolve()
            require(not target.exists(), 'Preserve an existing analysis report.')
            require(not target.is_relative_to(ROOT) or target.is_relative_to(ROOT / '.decomp-lab'), 'Use a private output path.')
        require(args.original.resolve() != args.rebuilt.resolve(), 'Require distinct original and rebuilt folders.')
        result = compare_data(load_recording(args.original), load_recording(args.rebuilt))
        if args.output:
            with args.output.open('x', encoding='utf-8', newline='\n') as stream:
                json.dump(result, stream, indent=2)
        print(json.dumps(result))
        return 0 if result['passed'] else 1
    except (ValueError, OSError, KeyError, TypeError, IndexError, EOFError, UnicodeError, zlib.error) as error:
        print('Opening attract inspection failed: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
