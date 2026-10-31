"""Synthetic format/fault tests; these fixtures are not native parity evidence."""
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from tools import inspect_opening_attract as attract

EXTENTS = attract.catalog()


def encode(row):
    return ('\t'.join(row[key] for key in attract.FIELDS) + '\n').encode('ascii')


def native(frame, cutoff=None, state=1, counter=0):
    row = {key: '0' for key in attract.FIELDS}
    row.update(relative_frame=str(frame), core_frame=str(frame + 1), native_tables_ready='1',
               active_movie='0' if cutoff is None else str(0x800a0000))
    if cutoff is None:
        row.update({key: '-' for key in attract.FIELDS[6:]})
        return row
    identity = EXTENTS[attract.playback.STARTUP_PATHS[cutoff]]
    minute, second = divmod((identity['lba'] + 150) // 75, 60)
    sector = (identity['lba'] + 150) % 75
    bcd = lambda value: ((value // 10) << 4) | (value % 10)
    raw = struct.pack('<4BI16s', bcd(minute), bcd(second), bcd(sector), 0,
                      identity['logical_bytes'], identity['filename'].encode())
    for offset in range(0, 24, 4):
        row[f'stream_{offset + 12:02x}'] = str(int.from_bytes(raw[offset:offset + 4], 'little'))
    row.update(movie_00=str(0x8006f614), stream_00=str(0x800817e0), movie_60=str(0x800b0000),
               movie_24='320', movie_28='240', movie_5c=str(cutoff), stream_40=str(cutoff),
               stream_58=str(counter), stream_2c=str(state), movie_44='1' if state == 4 else '0',
               movie_48='1' if state == 4 else '0')
    return row


def png():
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\x00\x12\x34\x56')) + chunk(b'IEND', b''))


def fixture():
    lines, cleared = [], []
    for cutoff in attract.playback.STARTUP_PATHS:
        lines.append(encode(native(len(lines), cutoff)))
        for counter in range(cutoff):
            lines.append(encode(native(len(lines), cutoff, 2, counter)))
        lines.append(encode(native(len(lines), cutoff, 4, cutoff - 1)))
        cleared.append(len(lines))
        lines.append(encode(native(len(lines))))
    for _ in range(180):
        lines.append(encode(native(len(lines))))
    windows = []
    for first in range(0, len(lines), 600):
        selected = lines[first:first + 600]
        count, last = len(selected), first + len(selected) - 1
        native_bytes = b''.join(struct.pack('<iii', frame, frame + 1, len(line)) + line
                               for frame, line in enumerate(selected, first))
        input_bytes = b''.join(struct.pack('<iiii', frame, frame + 1, 4, 0) for frame in range(first, last + 1))
        hashes = {key: 'a' * 64 for key in attract.CHANNELS}
        hashes.update(native=hashlib.sha256(native_bytes).hexdigest(), controller=hashlib.sha256(input_bytes).hexdigest())
        sizes = dict(MainRAM=count * 0x200000, GPURAM=count * 0x100000, RGB=count * 11,
                     PCM=count * 4, native=sum(map(len, selected)), controller=count * 4)
        windows.append(dict(first_frame=first, last_frame=last, frames=count, PCM_sample_frames=count,
            payload_bytes=sizes, framed_sha256=hashes, complete_state_sha256='b' * 64,
            final_MainRAM_sha256='c' * 64, final_GPURAM_sha256='d' * 64, final_RGB_with_dimensions_sha256='e' * 64))
    report = dict(schema_version=2, status='all_openings_cleared_and_post_window_completed', mode='neutral',
        frames_advanced=len(lines), last_frame=len(lines) - 1, total_PCM_sample_frames=len(lines),
        opening_cutoffs_completed=sorted(attract.OPENINGS), opening_lifetimes_completed=7,
        all_openings_cleared_frame=cleared[-1], post_all_openings_frames=180,
        skip_submitted_frame=-1, skip_pulse_frames=0, raw_native_bytes=sum(map(len, lines)),
        replayed_inputs=False, cold_start=True, restored_state=False, game_RAM_injected=False,
        player_UI_or_saves_accessed=False, hardware_timing_verified=False, whole_feature_groups_accepted=0,
        controller_buttons=sorted(attract.playback.DIGITAL_NAMES),
        controller_neutral_axes={key: int(value) for key, value in attract.playback.NUMERIC_NEUTRAL.items()}, elapsed_ms=1)
    return lines, windows, report


class OneLineStream(io.BytesIO):
    def read(self, *args):
        raise AssertionError('The native reader must not read the complete stream.')

    def readline(self, size=-1):
        if size != attract.LINE_LIMIT + 1:
            raise AssertionError('Every line read must have its explicit bound.')
        return super().readline(size)


class OpeningAttractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lines, cls.windows, cls.report = fixture()
        cls.header = ('\t'.join(attract.FIELDS) + '\n').encode('ascii')
        cls.raw = cls.header + b''.join(cls.lines)

    def inspect(self, raw=None, windows=None):
        return attract.inspect_native(OneLineStream(self.raw if raw is None else raw), len(self.lines),
                                      self.windows if windows is None else windows, attract.catalog())

    def test_streaming_all_seven_and_complete_logo_with_independent_hashes(self):
        attract.validate_report(self.report)
        attract.validate_windows(self.windows, len(self.lines), len(self.lines))
        value = self.inspect()
        self.assertEqual(value['journal_sha256'], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(value['raw_native_bytes'], sum(map(len, self.lines)))
        self.assertEqual(value['opening_cutoffs_completed'], sorted(attract.OPENINGS))
        self.assertEqual(value['opening_lifetimes_completed'], 7)
        self.assertEqual(len(value['lifetimes']), 8)
        self.assertEqual(value['all_openings_cleared_frame'], self.report['all_openings_cleared_frame'])
        for life in value['lifetimes']:
            self.assertEqual(life['distinct_accepted_frame_ids'], life['requested_cutoff'])

    def test_neutral_closed_skipped_regressed_and_missing_setup_are_rejected(self):
        for change in ({'stream_2c': '0'}, {'stream_2c': '2'}, {'stream_14': '1'}, {'movie_44': '2'},
                       {'active_movie': str(0x800a0001)}, {'movie_60': str(0x800b0001)}, {'rng': '00'}):
            row = native(0, 90)
            row.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.inspect(self.header + encode(row) + b''.join(self.lines[1:]))
        for counter in (2, 89):
            row = native(2, 90, 2, counter)
            with self.subTest(counter=counter), self.assertRaisesRegex(ValueError, 'contiguous'):
                self.inspect(self.header + b''.join(self.lines[:2]) + encode(row) + b''.join(self.lines[3:]))

    def test_lifetime_identity_completion_flags_and_pointer_transition_are_mandatory(self):
        for index, change in ((10, {'stream_14': '1'}), (10, {'movie_60': str(0x800b0004)}),
                              (91, {'movie_44': '0'}), (91, {'movie_48': '0'}), (91, {'stream_2c': '2'}),
                              (10, {'stream_58': '0'})):
            row = dict(zip(attract.FIELDS, self.lines[index].decode().rstrip('\n').split('\t')))
            row.update(change)
            with self.subTest(index=index, change=change), self.assertRaises(ValueError):
                self.inspect(self.header + b''.join(self.lines[:index]) + encode(row) + b''.join(self.lines[index + 1:]))

    def test_extra_truncated_oversized_nonascii_and_wrong_schedule_are_rejected(self):
        cases = (self.raw + b'\n', self.raw[:-1], self.raw.replace(b'core_frame', b'extra\tcore_frame', 1),
                 self.header + b'X' * (attract.LINE_LIMIT + 1), self.header + b'\xff\n',
                 self.header + self.lines[0].replace(b'0\t1\t', b'1\t2\t', 1) + b''.join(self.lines[1:]))
        for raw in cases:
            with self.subTest(prefix=raw[:40]), self.assertRaises((ValueError, UnicodeError)):
                self.inspect(raw)

    def test_native_and_controls_cannot_keep_old_hashes_after_changes(self):
        for channel in ('native', 'controller'):
            windows = copy.deepcopy(self.windows)
            windows[0]['framed_sha256'][channel] = 'f' * 64
            with self.subTest(channel=channel), self.assertRaisesRegex(ValueError, 'framed hash'):
                self.inspect(windows=windows)

    def test_window_gaps_missing_states_channels_and_incomplete_buffers_are_rejected(self):
        for key in ('MainRAM', 'GPURAM', 'PCM', 'controller'):
            windows = copy.deepcopy(self.windows)
            windows[0]['payload_bytes'][key] -= 1
            with self.subTest(channel=key), self.assertRaises(ValueError):
                attract.validate_windows(windows, len(self.lines), len(self.lines))
        for change in ({'first_frame': 1}, {'last_frame': 598}, {'frames': True}, {'complete_state_sha256': None}):
            windows = copy.deepcopy(self.windows)
            windows[0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                attract.validate_windows(windows, len(self.lines), len(self.lines))

    def test_incomplete_report_scope_replay_and_mutation_claims_are_rejected(self):
        for change in ({'opening_cutoffs_completed': sorted(attract.OPENINGS)[:-1]}, {'schema_version': True},
                       {'cold_start': False}, {'restored_state': True}, {'skip_submitted_frame': 20},
                       {'post_all_openings_frames': 179}, {'whole_feature_groups_accepted': True},
                       {'frames_advanced': attract.MAX_FRAMES + 1}, {'status': 'frame_ceiling_reached'},
                       {'replayed_inputs': 1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                attract.validate_report({**self.report, **change})

    def test_explicit_partial_review_cannot_be_compared_as_all_seven(self):
        partial = {**self.report, 'status': 'frame_ceiling_reached',
                   'all_openings_cleared_frame': -1, 'post_all_openings_frames': 0,
                   'opening_cutoffs_completed': sorted(attract.OPENINGS)[:-1]}
        with self.assertRaises(ValueError):
            attract.validate_report(partial)
        attract.validate_report(partial, allow_incomplete=True)
        original = {'native': {'all_seven_openings_completed': False}}
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            attract.compare_data(original, original)

    def test_recording_load_and_unmasked_state_gpu_and_image_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'report.json').write_text(json.dumps(self.report), encoding='utf-8')
            (folder / 'inputs.tsv').write_bytes(b'frame\tmask\n0\t0\n')
            (folder / 'native.tsv.gz').write_bytes(gzip.compress(self.raw, mtime=0))
            (folder / 'windows.jsonl').write_text('\n'.join(json.dumps(w) for w in self.windows), encoding='utf-8')
            (folder / 'final.png').write_bytes(png())
            original = attract.load_recording(folder)
            rebuilt = copy.deepcopy(original)
            rebuilt['report']['replayed_inputs'] = True
            rebuilt['report']['elapsed_ms'] = 2
            self.assertTrue(attract.compare_data(original, rebuilt)['passed'])
            for key in ('complete_state_sha256', 'final_GPURAM_sha256'):
                changed = copy.deepcopy(rebuilt)
                changed['windows'][0][key] = 'f' * 64
                self.assertEqual(attract.compare_data(original, changed)['differences'], {'windows': [0]})
            changed = copy.deepcopy(rebuilt)
            changed['final_image']['RGB_sha256'] = 'f' * 64
            self.assertEqual(attract.compare_data(original, changed)['differences'], {'decoded_final_PNG': True})
            with self.assertRaises(ValueError):
                attract.compare_data(original, original)
            (folder / 'inputs.tsv').write_bytes(b'frame\tmask\n0\t0\n1\t1\n')
            with self.assertRaises(ValueError):
                attract.load_recording(folder)

    def test_public_or_existing_outputs_and_same_capture_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            target = attract.ROOT / 'docs/should-not-write-attract.json'
            self.assertEqual(attract.main([directory, directory, '--output', str(target)]), 2)
            self.assertFalse(target.exists())
            target = Path(directory) / 'preserve.json'
            target.write_text('retained')
            self.assertEqual(attract.main([directory, directory, '--output', str(target)]), 2)
            self.assertEqual(target.read_text(), 'retained')
            self.assertEqual(attract.main([directory, directory]), 2)


if __name__ == '__main__':
    unittest.main()
