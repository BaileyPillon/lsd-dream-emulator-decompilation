"""Owned STR packets and table fixtures; no original game files are required."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import inventory_movies as tool


def video(number=1, chunk=0, chunks=1, size=8, width=320, version=2):
    prefix = struct.pack('<IHH', 0x38000020, 2, version)
    header = struct.pack('<IHHIIHHIHHI', 0x80010160, chunk, chunks, number,
                         size, width, 240, 0x38000020, 2, version, 0)
    payload = prefix.ljust(2016, b'\0') if chunk == 0 else b'\0' * 2016
    return b'\x01\x01\x48\0' * 2 + header + payload + b'\0' * 280


def reference_fixture():
    paths = [f'FILE{index:04}.BIN' for index in range(tool.PATH_COUNT)]
    cutoffs = [-10] + list(range(1, tool.CUTOFF_COUNT))
    offset = lambda address: 0x800 + address - 0x80010000
    image = bytearray(offset(tool.CUTOFF_ADDRESS) + 100)
    image[:8] = b'PS-X EXE'
    struct.pack_into('<I', image, 0x18, 0x80010000)
    packed = b''.join(path.encode().ljust(28, b'\0') for path in paths)
    image[offset(tool.PATH_ADDRESS):offset(tool.PATH_ADDRESS) + len(packed)] = packed
    image[offset(tool.CUTOFF_ADDRESS):] = struct.pack('<50h', *cutoffs)
    source = ('static char g_STRING_TABLE[LSD_PATH_COUNT][LSD_PATH_LEN] = {' +
              ','.join(json.dumps(path) for path in paths) + '};')
    timing = 'static s16 g_MovieDurations[] = {' + ','.join(map(str, cutoffs)) + '};'
    return bytes(image), source, timing, paths, cutoffs


class MovieInventoryTests(unittest.TestCase):
    def scan(self, data):
        return tool.scan_stream(io.BytesIO(data))

    def test_complete_chunks_with_interleaved_audio_and_filler(self):
        # Audio data may resemble a video marker; XA submode remains authoritative.
        audio = b'\x01\x01\x64\x01' * 2 + struct.pack('<I', 0x80010160) + b'\0' * 2324
        filler = b'\x01\0\0\0' * 2 + b'\0' * 2328
        data = video(chunks=2) + audio + video(chunk=1, chunks=2) + video(number=2) + filler
        result = self.scan(data)
        self.assertEqual(result['sector_kinds'], {'video': 3, 'xa_audio': 1, 'zero_data_filler': 1})
        self.assertEqual(result['frame_count'], 2)
        self.assertEqual(result['frames'][0]['chunks'], 2)
        self.assertEqual(result['sha256'], hashlib.sha256(data).hexdigest())
        self.assertEqual(result['bytes'], len(data))

    def test_partial_sector_and_disagreeing_subheaders_are_rejected(self):
        damaged = bytearray(video())
        damaged[4] ^= 1
        for data in (video()[:-1], bytes(damaged)):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                self.scan(data)

    def test_missing_duplicate_reordered_and_skipped_chunks_are_rejected(self):
        for data in (video(chunks=2), video(chunks=2) + video(chunks=2),
                     video(chunk=1, chunks=2), video() + video(number=3),
                     video(chunks=2) + video(chunk=1, chunks=2, width=160)):
            with self.subTest(data_bytes=len(data)), self.assertRaises(ValueError):
                self.scan(data)

    def test_invalid_bounds_versions_and_mdec_prefix_are_rejected(self):
        bad_prefix = bytearray(video())
        bad_prefix[40] ^= 1
        for data in (video(size=2020), video(size=9), video(width=0),
                     video(version=3), bytes(bad_prefix)):
            with self.subTest(first_bytes=data[:40]), self.assertRaises(ValueError):
                self.scan(data)

    def test_wrong_sector_form_and_nonzero_unknown_data_are_not_hidden_as_padding(self):
        for flags in (4, 0x28, 0x10):
            data = bytearray(video())
            data[2] = data[6] = flags
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                self.scan(bytes(data))
        filler = bytearray(b'\x01\0\0\0' * 2 + b'\0' * 2328)
        filler[100] = 1
        with self.assertRaisesRegex(ValueError, 'Unclassified'):
            self.scan(video() + filler)

    def test_native_tables_require_exact_initializer_bytes_and_signed_cutoffs(self):
        image, source, timing, paths, cutoffs = reference_fixture()
        with patch.object(tool, 'CANONICAL_SHA256', hashlib.sha256(image).hexdigest()):
            actual_paths, actual_cutoffs, hashes = tool.reference_tables(image, source, timing)
        self.assertEqual(actual_paths, paths)
        self.assertEqual(actual_cutoffs, cutoffs)
        self.assertEqual(actual_cutoffs[0], -10)
        self.assertEqual(len(hashes), 2)

    def test_altered_initializer_values_and_noncanonical_executable_are_rejected(self):
        image, source, timing, _, _ = reference_fixture()
        with self.assertRaisesRegex(ValueError, 'not canonical'):
            tool.reference_tables(image, source, timing)
        with patch.object(tool, 'CANONICAL_SHA256', hashlib.sha256(image).hexdigest()):
            with self.assertRaisesRegex(ValueError, 'path-table bytes'):
                tool.reference_tables(image, source.replace('FILE0000', 'ELIF0000'), timing)
            with self.assertRaisesRegex(ValueError, 'cutoff bytes'):
                tool.reference_tables(image, source, timing.replace('{-10,', '{-9,'))
            with self.assertRaisesRegex(ValueError, 'plain string'):
                tool.reference_tables(image, source.replace('"FILE0000.BIN"', 'unknown()'), timing)

    def test_routes_preserve_native_cutoffs_without_deriving_a_fixed_tail_margin(self):
        _, _, _, paths, cutoffs = reference_fixture()
        routes = tool.movie_routes(paths, cutoffs)
        self.assertEqual(len(routes), 39)
        self.assertEqual(routes[0]['frame_cutoff'], -10)
        self.assertEqual(routes[-1]['cutoff_index'], 49)
        self.assertEqual(cutoffs[0], -10)
        self.assertEqual({row['cutoff_index'] for row in routes}, set(range(38)) | {49})

    def test_unavailable_or_stale_build_is_rejected_before_reading_inputs(self):
        for current in (None, False):
            with self.subTest(current=current), patch.object(tool, 'check_build_current', return_value=current):
                with self.assertRaisesRegex(ValueError, 'current build'):
                    tool.collect('missing-layout.xml')

    def test_current_but_nonmatching_build_is_rejected_before_asset_inspection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, data in ((tool.configure.ROM, b'owned reference'),
                               (tool.configure.EXE, b'changed build')):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            with patch.object(tool, 'ROOT', root), patch.object(tool, 'check_build_current', return_value=True):
                with self.assertRaisesRegex(ValueError, 'does not match'):
                    tool.collect('missing-layout.xml')

    def test_public_or_existing_output_is_preserved_before_loading_inputs(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(tool, 'ROOT', Path(folder)):
            root = Path(folder)
            existing = root / '.decomp-lab' / 'retained.json'
            existing.parent.mkdir()
            existing.write_text('retained')
            for output in (root / 'public.json', existing):
                with patch.object(tool, 'collect') as collect, contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(tool.main(['--layout', 'unused', '--output', str(output)]), 1)
                    collect.assert_not_called()
            self.assertEqual(existing.read_text(), 'retained')
            self.assertFalse((root / 'public.json').exists())


if __name__ == '__main__':
    unittest.main()
