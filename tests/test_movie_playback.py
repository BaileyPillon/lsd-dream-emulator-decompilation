"""Owned recorder fixtures distinguish setup words, playback, and complete lifetimes."""

import contextlib
import csv
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import compare_movie_playback as tool
from tools import capture_movie_playback as capture


def observations():
    rows = []
    for frame in range(95):
        row = dict.fromkeys(tool.FIELDS, '-')
        row.update(relative_frame=str(frame), core_frame=str(1000 + frame),
                   native_tables_ready=str(int(frame > 0)), active_movie='0', gpu_sha256='0' * 64)
        if frame > 0:
            row.update(rng='123', watchdog_counter='0')
        if 1 <= frame <= 93:
            row.update({field: '0' for field in tool.FIELDS[6:-1]})
            row.update(active_movie=str(0x800a0000), movie_00=str(0x8006f614),
                       movie_60=str(0x800b0000), stream_00=str(0x800817e0),
                       movie_20='640', movie_24='320', movie_28='240', movie_5c='90',
                       stream_40='90', stream_2c='2', stream_58=str(min(89, frame - 2)))
            file = bytes((0x04, 0x43, 0x45, 0)) + (1008 * 2048).to_bytes(4, 'little')
            file += b'ASMK.STR;1\0'.ljust(16, b'\0')
            for offset in range(0, 24, 4):
                row[f'stream_{0x0c + offset:02x}'] = str(int.from_bytes(file[offset:offset + 4], 'little'))
            if frame == 1:
                row.update(stream_2c='1', stream_40='100', stream_58='4096')
            if frame >= 92:
                row.update(stream_2c='4', movie_48='1')
            if frame == 93:
                row['movie_44'] = '1'
        rows.append(row)
    return rows


def write_tsv(path, fields, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter='\t')
        writer.writeheader()
        writer.writerows(rows)


class MovieObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.path = self.folder / 'movies.tsv'
        self.rows = observations()

    def read(self):
        write_tsv(self.path, tool.FIELDS, self.rows)
        return tool.read_observations(self.path, len(self.rows) - 1)

    def test_setup_stale_word_is_preserved_without_counting_it_as_playback(self):
        result = tool.summarize_lifetimes(self.read())[0]
        self.assertEqual(result['setup_raw_frame_values'], [4096])
        self.assertEqual(result['setup_thresholds'], [100])
        self.assertEqual(result['maximum_accepted_frame_id_while_streaming'], 89)
        self.assertEqual(result['nonzero_frame_ids_sampled'], 89)
        self.assertTrue(result['observed_complete_lifetime'])
        self.assertEqual(result['source_viewports_xy_width_height'], [(640, 0, 320, 240)])

    def test_stale_word_during_streaming_is_rejected(self):
        self.rows[2]['stream_58'] = '4096'
        with self.assertRaisesRegex(ValueError, 'counter'):
            self.read()

    def test_native_file_location_size_and_name_are_decoded(self):
        result = tool.native_file_identity(self.rows[2])
        self.assertEqual(result, {'filename': 'ASMK.STR;1', 'lba': 21120,
                                  'logical_bytes': 2064384, 'sectors': 1008})

    def test_invalid_bcd_and_unaligned_file_size_are_rejected(self):
        for field, value in [('stream_0c', str(0x00436a04)), ('stream_10', '2064385')]:
            with self.subTest(field=field):
                self.rows = observations()
                self.rows[2][field] = value
                with self.assertRaises(ValueError):
                    self.read()

    def test_opened_filename_must_agree_with_the_movie_request(self):
        self.rows[2]['stream_14'] = str(int.from_bytes(b'XMKS', 'little'))
        with self.assertRaises(ValueError):
            self.read()

    def test_filename_tail_after_nul_remains_in_the_recorded_words(self):
        raw = b'ASMK.STR;1\0JUNK\0'
        for offset in range(0, 16, 4):
            self.rows[2][f'stream_{0x14 + offset:02x}'] = str(int.from_bytes(raw[offset:offset + 4], 'little'))
        observed = self.read()
        self.assertEqual(tool.native_file_identity(observed[2])['filename'], 'ASMK.STR;1')
        self.assertNotEqual(observed[2]['stream_20'], observed[3]['stream_20'])

    def test_truncated_or_nonconsecutive_observations_are_rejected(self):
        self.rows.pop(40)
        write_tsv(self.path, tool.FIELDS, self.rows)
        with self.assertRaises(ValueError):
            tool.read_observations(self.path, 94)
        with self.assertRaises(ValueError):
            tool.read_observations(self.path, 93)

    def test_extra_and_duplicate_fields_are_rejected(self):
        self.read()
        self.path.write_text(self.path.read_text() + 'extra\tfield\n')
        with self.assertRaises(ValueError):
            tool.read_observations(self.path, 94)
        self.path.write_text('relative_frame\trelative_frame\n0\t0\n')
        with self.assertRaises(ValueError):
            tool.read_observations(self.path, 0)

    def test_bad_pointer_vtable_viewport_and_hash_are_rejected(self):
        cases = [('active_movie', str(0x800a0001)), ('movie_60', str(0x80200000)),
                 ('movie_00', '0'), ('stream_00', '0'), ('movie_24', '319'),
                 ('gpu_sha256', '0' * 63)]
        for field, value in cases:
            with self.subTest(field=field):
                self.rows = observations()
                self.rows[2][field] = value
                with self.assertRaises(ValueError):
                    self.read()

    def test_inactive_fields_and_readiness_regression_are_rejected(self):
        self.rows[94]['movie_00'] = '0'
        with self.assertRaises(ValueError):
            self.read()
        self.rows = observations()
        self.rows[94]['native_tables_ready'] = '0'
        with self.assertRaises(ValueError):
            self.read()

    def test_partial_repeat_is_not_a_complete_movie(self):
        self.rows = self.rows[:70]
        result = tool.summarize_lifetimes(self.read())[0]
        self.assertIsNone(result['first_inactive_frame_after'])
        self.assertFalse(result['observed_complete_lifetime'])

    def test_missing_ids_or_decode_completion_do_not_accept_a_lifetime(self):
        self.rows[40]['stream_58'] = self.rows[39]['stream_58']
        result = tool.summarize_lifetimes(self.read())[0]
        self.assertFalse(result['sampled_ids_contiguous_from_zero'])
        self.assertFalse(result['observed_complete_lifetime'])
        self.rows = observations()
        self.rows[93]['movie_44'] = '0'
        self.assertFalse(tool.summarize_lifetimes(self.read())[0]['observed_complete_lifetime'])

    def make_inputs(self):
        definitions = [{'name': name, 'type': 'boolean', 'neutral_value': 'false'} for name in tool.DIGITAL_NAMES]
        definitions += [{'name': name, 'type': 'number', 'neutral_value': str(value)}
                        for name, value in tool.NUMERIC_NEUTRAL.items()]
        definitions.sort(key=lambda row: row['name'])
        names = [row['name'] for row in definitions]
        submitted = []
        for frame in range(1, 95):
            row = {'relative_frame': str(frame), 'core_frame': str(999 + frame)}
            row.update({item['name']: item['neutral_value'] for item in definitions})
            submitted.append(row)
        write_tsv(self.folder / 'input-definition.tsv', ('name', 'type', 'neutral_value'), definitions)
        write_tsv(self.folder / 'submitted.tsv', ('relative_frame', 'core_frame', *names), submitted)
        return definitions, names, submitted

    def test_submitted_digital_edge_is_rejected(self):
        _, names, submitted = self.make_inputs()
        tool.check_inputs(self.folder, self.read(), 94)
        submitted[4]['P1 Start'] = 'true'
        write_tsv(self.folder / 'submitted.tsv', ('relative_frame', 'core_frame', *names), submitted)
        with self.assertRaises(ValueError):
            tool.check_inputs(self.folder, self.rows, 94)

    def test_wrong_analog_center_is_rejected_even_when_both_logs_agree(self):
        definitions, names, submitted = self.make_inputs()
        key = 'P1 Left Stick Left / Right'
        next(item for item in definitions if item['name'] == key)['neutral_value'] = '0'
        for row in submitted:
            row[key] = '0'
        write_tsv(self.folder / 'input-definition.tsv', ('name', 'type', 'neutral_value'), definitions)
        write_tsv(self.folder / 'submitted.tsv', ('relative_frame', 'core_frame', *names), submitted)
        with self.assertRaises(ValueError):
            tool.check_inputs(self.folder, self.read(), 94)


class MovieOutputGuards(unittest.TestCase):
    def test_public_and_existing_reports_are_preserved_before_reading_inputs(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(tool, 'ROOT', Path(directory).resolve()):
            root = Path(directory).resolve()
            existing = root / '.decomp-lab/retained.json'
            existing.parent.mkdir()
            existing.write_text('retained')
            for output in (root / 'public.json', existing):
                with patch.object(tool, 'compare_runs') as compare, contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(tool.main(['--original', 'missing', '--rebuilt', 'missing', '--output', str(output)]), 2)
                    compare.assert_not_called()
            self.assertEqual(existing.read_text(), 'retained')
            self.assertFalse((root / 'public.json').exists())

    def test_existing_and_public_capture_workspaces_are_rejected_before_input_reads(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(capture, 'ROOT', Path(directory).resolve()):
            root = Path(directory).resolve()
            for workspace in (root, root / 'public-new'):
                with patch.object(capture, 'read_root_file') as read, patch.object(capture, 'pin_inputs') as pin:
                    with self.assertRaises(ValueError):
                        capture.capture_pair(workspace, 'missing', 'missing', 'missing', 'missing', 'missing')
                    read.assert_not_called()
                    pin.assert_not_called()


if __name__ == '__main__':
    unittest.main()
