"""Inspect bounded controller-only progression histories and sealed journals.

This checks recorded evidence, not original-hardware or whole-feature parity.
Complete-state hashes are compared only where an actual observation exists.
"""
import argparse
from bisect import bisect_right
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import sys
import tarfile
import zlib

MAX_FRAMES = 8_000_000
STREAM_LIMIT = 16 * 2**20
PNG_LIMIT = 4 * 2**20
JOURNALS = ('checkpoints.jsonl', 'days.jsonl', 'audio.tsv', 'ending.jsonl')
CHECK_FIELDS = {'frame', 'core_frame', 'state', 'MainRAM_sha256', 'GPURAM_sha256',
                'RGB_sha256', 'serialized_state_sha256', 'PCM_sample_frames'}
STATE_FIELDS = {'address', 'year', 'day', 'timer', 'limit', 'paused', 'flashback',
                'link', 'stored_day', 'menu', 'selection', 'found', 'AbsoluteDay'}
SCOPE_FIELDS = ('restored_state', 'game_RAM_injected', 'emulator_UI_controlled',
                'original_hardware_timing_verified', 'complete_feature_parity_accepted')
ENDING_IMAGES = (0, 120, 600, 1800, 3600, 11999)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def integer(value, low, high, label):
    require(type(value) is int and low <= value <= high, 'Invalid ' + label + '.')
    return value


def digest(value, label):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value),
            'Invalid ' + label + ' digest.')
    return value


def decimal(value, label):
    require(isinstance(value, str) and re.fullmatch('0|[1-9][0-9]*', value),
            'Invalid decimal ' + label + '.')
    return int(value)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON field: ' + key)
        result[key] = value
    return result


def document(data):
    def invalid(value):
        raise ValueError('Non-finite JSON value: ' + value)
    return json.loads(data.decode('utf-8-sig'), object_pairs_hook=_pairs,
                      parse_constant=invalid)


def rows(data, columns):
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig')), delimiter='\t')
    require(tuple(reader.fieldnames or ()) == columns, 'Wrong journal columns.')
    result = list(reader)
    require(all(None not in row and None not in row.values() for row in result),
            'Truncated or extra journal columns.')
    return result


class RecordingFiles:
    """Read the four exact sealed members without expanding them to disk."""

    def __init__(self, folder):
        self.folder = Path(folder).resolve(strict=True)
        require(self.folder.is_dir(), 'Recording must be a directory.')
        self.loaded = {}
        self.sealed = None
        self.archive = None
        index = self.folder / 'retained-journals.json'
        if index.exists():
            self.sealed = document(self._raw(index, STREAM_LIMIT))
            require(isinstance(self.sealed, dict), 'Journal index must be an object.')
            require(self.sealed.get('archive') == 'retained-journals.tar.xz',
                    'Unsupported journal archive name.')
            entries = self.sealed.get('files')
            require(isinstance(entries, list) and len(entries) == len(JOURNALS)
                    and all(isinstance(r, dict) for r in entries)
                    and {r.get('name') for r in entries} == set(JOURNALS),
                    'Sealed journal index is incomplete or duplicated.')
            require(self.sealed.get('all_members_full_sha256_verified') is True
                    and self.sealed.get('restore_readback_test_passed') is True,
                    'Journal sealing/restore checks are absent.')
            self.archive = self._raw(self.folder / self.sealed['archive'], STREAM_LIMIT)
            require(sha(self.archive) == digest(self.sealed.get('archive_sha256'), 'archive'),
                    'Sealed archive changed.')
            total = 0
            observed = set()
            with tarfile.open(fileobj=io.BytesIO(self.archive), mode='r|xz') as tar:
                for member in tar:
                    require(member.name in JOURNALS and member.name not in observed
                            and member.isfile(), 'Unexpected archive member.')
                    observed.add(member.name)
                    entry = next(r for r in entries if r['name'] == member.name)
                    size = integer(entry.get('bytes'), 0, STREAM_LIMIT, 'journal size')
                    total += size
                    require(member.size == size and total <= STREAM_LIMIT,
                            'Sealed journals exceed their declared capture bound.')
                    with tar.extractfile(member) as stream:
                        value = stream.read(STREAM_LIMIT + 1)
                    require(len(value) == size and sha(value) == digest(entry.get('sha256'), 'member'),
                            'Sealed journal content changed: ' + member.name)
                    self.loaded[member.name] = value
            require(observed == set(JOURNALS), 'Sealed journal archive is incomplete.')

    def _raw(self, path, limit):
        require(path.resolve(strict=True).parent == self.folder,
                'A retained file escapes its recording.')
        require(path.is_file() and path.stat().st_size <= limit, 'Oversized retained file.')
        with path.open('rb') as stream:
            value = stream.read(limit + 1)
        require(len(value) <= limit, 'Retained file grew beyond its bound.')
        return value

    def read(self, name, limit=STREAM_LIMIT):
        require(Path(name).name == name and '/' not in name and '\\' not in name,
                'Expected one exact retained basename.')
        path = self.folder / name
        if name in self.loaded:
            value = self.loaded[name]
            if path.exists():
                require(self._raw(path, limit) == value, 'Restored journal differs from its sealed copy.')
            return value
        return self._raw(path, limit)


def png_rgb(data):
    """Decode the producer's bounded 8-bit RGB PNGs, including all five filters."""
    require(len(data) <= PNG_LIMIT and data.startswith(b'\x89PNG\r\n\x1a\n'), 'Invalid PNG.')
    offset, header, payload, ended = 8, None, bytearray(), False
    while offset < len(data):
        require(offset + 12 <= len(data), 'Truncated PNG chunk.')
        length = struct.unpack_from('>I', data, offset)[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + length
        require(end <= len(data), 'Truncated PNG payload.')
        body = data[offset + 8:end - 4]
        require(zlib.crc32(kind + body) & 0xffffffff == struct.unpack_from('>I', data, end - 4)[0],
                'PNG checksum differs.')
        if header is None:
            require(kind == b'IHDR' and length == 13, 'PNG must start with IHDR.')
            header = struct.unpack('>IIBBBBB', body)
            width, height = header[:2]
            require(1 <= width <= 1024 and 1 <= height <= 1024
                    and header[2:] == (8, 2, 0, 0, 0), 'Unsupported producer PNG format.')
        elif kind == b'IHDR':
            raise ValueError('Repeated PNG header.')
        elif kind == b'IDAT':
            payload.extend(body)
        elif kind == b'IEND':
            require(length == 0 and end == len(data), 'PNG end/trailing bytes differ.')
            ended = True
        else:
            require(kind[0] & 32 and kind != b'tRNS', 'Unsupported critical/transparency PNG chunk.')
        offset = end
    require(header is not None and ended and payload, 'Incomplete PNG.')
    stride = width * 3
    expected = (stride + 1) * height
    decoder = zlib.decompressobj()
    raw = decoder.decompress(bytes(payload), expected + 1)
    require(len(raw) == expected and decoder.eof and not decoder.unused_data
            and not decoder.unconsumed_tail, 'Invalid or oversized decoded PNG.')
    pixels, previous = bytearray(), bytearray(stride)
    for row in range(height):
        at = row * (stride + 1)
        mode = raw[at]
        require(mode <= 4, 'Unknown PNG row filter.')
        line = bytearray(raw[at + 1:at + 1 + stride])
        for x in range(stride):
            left = line[x - 3] if x >= 3 else 0
            up = previous[x]
            corner = previous[x - 3] if x >= 3 else 0
            if mode == 1:
                predictor = left
            elif mode == 2:
                predictor = up
            elif mode == 3:
                predictor = (left + up) // 2
            elif mode == 4:
                p = left + up - corner
                distances = (abs(p - left), abs(p - up), abs(p - corner))
                predictor = (left, up, corner)[distances.index(min(distances))]
            else:
                predictor = 0
            line[x] = (line[x] + predictor) & 255
        pixels.extend(line)
        previous = line
    return dict(width=width, height=height, RGB_sha256=sha(pixels), PNG_sha256=sha(data))


def load_recording(folder):
    files = RecordingFiles(folder)
    data = {'report': document(files.read('report.json'))}
    require(isinstance(data['report'], dict), 'Native report must be an object.')
    extended = 'year_boundary_frame' in data['report']
    payloads, retained = {}, 0
    for name in ('days.jsonl', 'checkpoints.jsonl', 'audio.tsv', 'inputs.tsv',
                 *(['ending.jsonl'] if extended else [])):
        payloads[name] = files.read(name)
        retained += len(payloads[name])
        require(retained <= STREAM_LIMIT, 'Actual retained streams exceed the capture bound.')
    data['actual_retained_stream_bytes'] = retained
    for name in ('days', 'checkpoints'):
        data[name] = [document(line) for line in payloads[name + '.jsonl'].splitlines()]
    data['audio'] = rows(payloads['audio.tsv'], ('first_frame', 'last_frame', 'sample_frames', 'PCM_sha256'))
    data['inputs'] = rows(payloads['inputs.tsv'], ('frame', 'mask'))
    data['ending'] = ([document(line) for line in payloads['ending.jsonl'].splitlines()]
                      if extended else [])
    names = ['final.png'] + sorted(p.name for p in files.folder.glob('ending-*.png'))
    require(len(names) <= 1 + len(ENDING_IMAGES), 'Too many ending images.')
    data['images'] = {name: png_rgb(files.read(name, PNG_LIMIT)) for name in names}
    return data


def state(value):
    require(isinstance(value, dict) and set(value) == STATE_FIELDS, 'Wrong native state fields.')
    require(type(value['found']) is bool, 'Invalid object-location flag.')
    integer(value['year'], 0, 1, 'native year')
    integer(value['day'], 0, 364, 'native day')
    for key in ('timer', 'limit', 'paused', 'flashback', 'link', 'stored_day', 'selection'):
        integer(value[key], -(2**31), 2**31 - 1, 'native ' + key)
    address = integer(value['address'], 0, 0x1effff, 'dream address')
    integer(value['menu'], 0, 0x1effff, 'menu address')
    require((value['found'] and address >= 0x90000) or (not value['found'] and address == 0),
            'Object-location flag and address disagree.')
    absolute = value['year'] * 365 + value['day']
    require(type(value['AbsoluteDay']) is int and value['AbsoluteDay'] == absolute,
            'Native absolute-day accounting differs.')
    return absolute


def _boundary(row, previous, last):
    at = integer(row.get('frame'), 0, last, 'observation frame')
    require(at > previous and type(row.get('core_frame')) is int and row['core_frame'] == at + 1,
            'Observation frame chronology differs.')
    state(row.get('state'))
    return at


def validate(data):
    require(isinstance(data, dict) and isinstance(data.get('report'), dict),
            'Native recording/report must be objects.')
    require(all(isinstance(data.get(k), list) and all(isinstance(r, dict) for r in data[k])
                for k in ('days', 'checkpoints', 'inputs', 'audio', 'ending')),
            'Observation journals must contain objects.')
    require(isinstance(data.get('images'), dict), 'Image observations must be an object.')
    report = data['report']
    require(report.get('status') in ('completed_requested_natural_days', 'frame_ceiling_reached',
            'native_day_watchdog_reached', 'owned_host_stop_requested',
            'completed_natural_year_and_ending_objects', 'completed_natural_year_missing_ending_evidence'),
            'Unsupported native recording outcome.')
    last = integer(report.get('last_frame'), 1, MAX_FRAMES, 'last frame')
    require(type(report.get('frames_advanced')) is int and report['frames_advanced'] == last + 1,
            'Native frame total differs.')
    require(all(report.get(name) is False for name in SCOPE_FIELDS), 'Unsupported mutation/parity scope.')
    retained = integer(report.get('retained_stream_bytes'), 0, STREAM_LIMIT, 'retained streams')
    require(type(report.get('retained_stream_limit')) is int and report['retained_stream_limit'] == STREAM_LIMIT
            and retained <= report['retained_stream_limit'], 'Retained-output bound differs.')
    if 'actual_retained_stream_bytes' in data:
        actual = integer(data['actual_retained_stream_bytes'], 0, STREAM_LIMIT, 'actual stream bytes')
        require(actual == retained, 'Declared retained stream bytes differ from actual journals.')
    require(data['days'], 'No native day observations.')
    previous, frame = -1, -1
    day_frames = set()
    object_address = None
    for ordinal, row in enumerate(data['days']):
        require(set(row) == {'frame', 'core_frame', 'state', 'completed_days'}, 'Wrong day fields.')
        frame = _boundary(row, frame, last)
        absolute = state(row['state'])
        require(row['state']['found'] is True and row['state']['flashback'] == 0
                and absolute == previous + 1, 'Native day skipped, regressed, or wrapped early.')
        require(type(row['completed_days']) is int and row['completed_days'] == ordinal,
                'Completed-day count differs.')
        if object_address is None:
            object_address = row['state']['address']
        require(row['state']['address'] == object_address, 'Pinned dream object changed identity.')
        previous = absolute
        day_frames.add(frame)
    completed = integer(report.get('completed_days'), 0, 365, 'completed days')
    require(completed == len(data['days']) - 1 and state(report.get('final_state')) == previous,
            'Final report disagrees with observed day transitions.')
    extended = 'year_boundary_frame' in report
    wrap = next((r['frame'] for r in data['days'] if r['state']['AbsoluteDay'] == 365), -1)
    ending_frames, pending, terminal = set(), {}, set()
    pre_pending_raw_flags = 0
    last_ending = -1
    for row in data['ending']:
        require(extended and set(row) == {'frame', 'core_frame', 'state', 'movies'}, 'Wrong ending fields.')
        last_ending = _boundary(row, last_ending, last)
        require(wrap >= 0 and last_ending >= wrap and last_ending % 30 == 0
                and state(row['state']) == 365, 'Ending observation is outside its natural year boundary.')
        require(isinstance(row['movies'], list), 'Ending movie observations must be an array.')
        ending_frames.add(last_ending)
        addresses = set()
        for movie in row['movies']:
            address = integer(movie.get('address'), 0x90000, 0x1effff, 'movie address')
            require(address not in addresses, 'Repeated ending object in one observation.')
            addresses.add(address)
            integer(movie.get('path_pointer'), 0x80000000, 0x801fff80, 'movie path pointer')
            require(movie.get('path') == 'ETC\\ENDING.STR'
                    and type(movie.get('encoded_frame_threshold')) is int
                    and movie['encoded_frame_threshold'] == 474
                    and type(movie.get('play_flags')) is int and movie['play_flags'] == 1,
                    'Ending path/threshold/flags contract differs.')
            flag = integer(movie.get('completion_flag'), -(2**31), 2**31 - 1, 'ending completion flag')
            result = integer(movie.get('decoder_result'), -(2**31), 2**31 - 1, 'decoder result')
            # movie_screen_construct does not initialize +0xd8. Event 5 writes
            # zero and event 7 writes one (func_8003BC14). Retain raw pre-start
            # observations, but never count them as pending or completion.
            if flag not in (0, 1):
                require(address not in pending, 'Nonboolean ending completion flag after pending.')
                pre_pending_raw_flags += 1
            if flag == 0:
                pending.setdefault(address, last_ending)
            if flag == 1 and result != 0 and address in pending and pending[address] < last_ending:
                terminal.add(address)
    require(extended or not data['ending'], 'Legacy pilot cannot contain year-ending observations.')
    if extended:
        require(type(report['year_boundary_frame']) is int and report['year_boundary_frame'] == wrap,
                'Reported year boundary differs.')
        observed = 0 if wrap < 0 else last - wrap
        require(type(report.get('post_year_frames_observed')) is int
                and report['post_year_frames_observed'] == observed, 'Post-year window differs.')
        require(type(report.get('ending_path_pending_observed')) is bool
                and report['ending_path_pending_observed'] == bool(pending), 'Reported pending ending differs.')
        require(type(report.get('ending_completion_after_pending_observed')) is bool
                and report['ending_completion_after_pending_observed'] == bool(terminal),
                'Reported ending terminal transition differs.')
        require(type(report.get('ending_object_observations')) is int
                and report['ending_object_observations'] == len(data['ending']), 'Ending journal count differs.')
    checks = data['checkpoints']
    expected = set(range(0, last + 1, 600)) | day_frames | ending_frames | {last}
    require([r.get('frame') for r in checks] == sorted(expected), 'Missing, duplicated or extra checkpoint.')
    required_states = day_frames | ending_frames | {last}
    day_order = sorted(day_frames)
    state_hashes, last_samples = 0, -1
    for row in checks:
        require(set(row) == CHECK_FIELDS, 'Wrong checkpoint fields.')
        _boundary(row, -1, last)
        ordinal = bisect_right(day_order, row['frame']) - 1
        require((ordinal < 0 and row['state']['found'] is False and state(row['state']) == 0)
                or (ordinal >= 0 and row['state']['found'] is True
                    and row['state']['address'] == object_address
                    and state(row['state']) == ordinal), 'Checkpoint day disagrees with the native day journal.')
        for name in ('MainRAM_sha256', 'GPURAM_sha256', 'RGB_sha256'):
            digest(row[name], name)
        value = row['serialized_state_sha256']
        if value is not None:
            digest(value, 'complete serialized state')
            state_hashes += 1
        require((value is not None) == (row['frame'] in required_states),
                'Complete-state observation is absent or outside the declared schedule.')
        samples = integer(row['PCM_sample_frames'], 0, 2**63 - 1, 'checkpoint PCM samples')
        require(samples >= last_samples, 'PCM sample counter regressed.')
        last_samples = samples
    next_frame, total_samples = 0, 0
    audio_ends = {}
    for row in data['audio']:
        first, end, count = [decimal(row[k], k) for k in ('first_frame', 'last_frame', 'sample_frames')]
        require(first == next_frame and first <= end <= last, 'Missing or overlapping PCM window.')
        require(end == (0 if first == 0 else min(((first - 1) // 600 + 1) * 600, last)),
                'PCM window boundary differs from the declared schedule.')
        digest(row['PCM_sha256'], 'complete PCM')
        next_frame = end + 1
        total_samples += count
        audio_ends[end] = total_samples
    require(next_frame == last + 1 and type(report.get('total_PCM_sample_frames')) is int
            and total_samples == report['total_PCM_sample_frames'], 'Incomplete returned-PCM coverage.')
    require(all(r['PCM_sample_frames'] == audio_ends[r['frame']]
                for r in checks if r['frame'] in audio_ends), 'Checkpoint/window PCM counters disagree.')
    changes = data['inputs']
    require(changes and changes[0] == {'frame': '0', 'mask': '0'}, 'Missing initial neutral input.')
    previous_frame, previous_mask = -1, -1
    first_post_year_mask = 0
    for row in changes:
        at, mask = decimal(row['frame'], 'input frame'), decimal(row['mask'], 'input mask')
        require(previous_frame < at <= last and mask in (0, 1, 2) and mask != previous_mask,
                'Nonmonotonic, redundant or unsupported controller change.')
        if wrap >= 0:
            require(at <= wrap or mask == 0, 'Post-year input must stay neutral.')
            if at <= wrap + 1:
                first_post_year_mask = mask
        previous_frame, previous_mask = at, mask
    require(changes[-1] and (wrap < 0 or previous_mask == 0), 'Ending window has held input.')
    require(wrap < 0 or first_post_year_mask == 0, 'First post-year frame has held input.')
    require('final.png' in data['images']
            and data['images']['final.png']['RGB_sha256'] == checks[-1]['RGB_sha256'],
            'Final decoded PNG differs from native RGB.')
    image_names = {'final.png'}
    if wrap >= 0:
        image_names |= {'ending-' + str(n) + '.png' for n in ENDING_IMAGES if wrap + n <= last}
    require(set(data['images']) == image_names, 'Ending PNG coverage differs.')
    year_complete = (extended and completed == 365 and last - wrap == 12000
                     and bool(terminal) and report.get('ending_completion_after_pending_observed') is True
                     and report.get('status') == 'completed_natural_year_and_ending_objects')
    return dict(frames=last + 1, completed_days=completed, checkpoints=len(checks),
                complete_state_observations=state_hashes, PCM_windows=len(data['audio']),
                PCM_stereo_sample_frames=total_samples, controller_changes=len(changes),
                year_boundary_frame=wrap, ending_pending_objects=len(pending),
                ending_terminal_objects=len(terminal), year_route_observed=year_complete,
                ending_pre_pending_raw_flag_observations=pre_pending_raw_flags,
                retained_stream_byte_count_verified='actual_retained_stream_bytes' in data,
                complete_ending_decode_verified=False, whole_feature_groups_accepted=0,
                original_hardware_timing_verified=False)


def compare_data(original, rebuilt, require_year=False):
    before, after = validate(original), validate(rebuilt)
    differences = {}
    for name in ('days', 'inputs', 'audio', 'ending'):
        if original[name] != rebuilt[name]:
            differences[name] = {'equal': False}
    fields = ('state', 'MainRAM_sha256', 'GPURAM_sha256', 'RGB_sha256', 'PCM_sample_frames')
    counts = {name: {'compared': 0, 'different': 0, 'first_different_frames': []} for name in fields}
    counts['serialized_state_sha256'] = {'compared': 0, 'different': 0, 'first_different_frames': []}
    left = {r['frame']: r for r in original['checkpoints']}
    right = {r['frame']: r for r in rebuilt['checkpoints']}
    if set(left) != set(right):
        differences['checkpoint_frames'] = {'original_only': sorted(set(left) - set(right)),
                                            'rebuilt_only': sorted(set(right) - set(left))}
    for frame in sorted(set(left) & set(right)):
        for name in (*fields, 'serialized_state_sha256'):
            a, b = left[frame][name], right[frame][name]
            if name == 'serialized_state_sha256' and a is None and b is None:
                continue
            count = counts[name]
            count['compared'] += 1
            if a != b:
                count['different'] += 1
                if len(count['first_different_frames']) < 20:
                    count['first_different_frames'].append(frame)
    if any(c['different'] for c in counts.values()):
        differences['checkpoint_fields'] = [name for name, c in counts.items() if c['different']]
    images_equal = ({k: {n: v[n] for n in ('width', 'height', 'RGB_sha256')} for k, v in original['images'].items()}
                    == {k: {n: v[n] for n in ('width', 'height', 'RGB_sha256')} for k, v in rebuilt['images'].items()})
    if not images_equal:
        differences['decoded_PNGs'] = {'equal': False}
    dimensions_equal = before == after
    if not dimensions_equal:
        differences['recording_dimensions'] = {'original': before, 'rebuilt': after}
    year_ok = before['year_route_observed'] and after['year_route_observed']
    passed = not differences and (not require_year or year_ok)
    return dict(schema_version=1, status='equal_for_recorded_scope' if passed else 'recorded_differences_or_unmet_year_gate',
                passed=passed, requested_year_gate=require_year, year_gate_observed=year_ok,
                original=before, rebuilt=after, checkpoint_comparisons=counts,
                decoded_PNGs_equal=images_equal, differences=differences,
                whole_feature_groups_accepted=0, original_hardware_timing_verified=False,
                complete_emulator_or_game_parity_accepted=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    inspect = commands.add_parser('inspect')
    inspect.add_argument('recording', type=Path)
    compare = commands.add_parser('compare')
    compare.add_argument('original', type=Path)
    compare.add_argument('rebuilt', type=Path)
    compare.add_argument('--require-year-ending', action='store_true')
    for command in (inspect, compare):
        command.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'inspect':
            result = validate(load_recording(args.recording))
            code = 0
        else:
            result = compare_data(load_recording(args.original), load_recording(args.rebuilt), args.require_year_ending)
            code = 0 if result['passed'] else 1
        result['scope'] = 'Saved observations only; producer/runtime provenance must be checked separately; no live process is controlled.'
        if args.output:
            with args.output.open('x', encoding='utf-8') as stream:
                json.dump(result, stream, indent=2)
                stream.write('\n')
        print(json.dumps(result, indent=2))
        return code
    except (OSError, ValueError, KeyError, TypeError, struct.error, zlib.error, tarfile.TarError) as error:
        print(json.dumps({'status': 'invalid_recording', 'error': str(error)}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
