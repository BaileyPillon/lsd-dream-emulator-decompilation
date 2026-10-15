"""Synthetic sparse-state and media-label guards; no emulator or game files."""
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
import warnings
import zipfile

from research.emulator_state import BLOCK_MAGIC, HOST_END, PAGE, CoreImage, Layout, Snapshot, classify, media_label, short_label
from tools.inspect_nymashock_state import inspect_native, main

LAYOUT = Layout(0x10000, PAGE * 4, PAGE, ((0x12000, PAGE),))
CORE = SimpleNamespace(symbol=lambda name: {'_ZN8Mednafen12MDFNGameInfoE': (0x10000, 8, name),
                                           'EmulatedPSX': (0x10080, 416, name)}[name])


def payload(pages=None, dirty=(1, 0, 1, 1)):
    if pages is None:
        pages = {0x10000: bytes(PAGE), 0x13000: bytes(PAGE)}
    result = b'ActivatedWaterboxHost_v1' + BLOCK_MAGIC + bytes(32)
    result += struct.pack('<QQ', LAYOUT.start, LAYOUT.size) + bytes([2] * 4) + bytes(dirty)
    for index, changed in enumerate(dirty):
        address = LAYOUT.start + index * PAGE
        if changed and address != 0x12000:
            result += pages[address]
    return result + b'thread-state-fixture' + HOST_END + struct.pack('<IIBQIIQI', 1, 0, 0, 0, 320, 240, 0, 0)


def graph_snapshot():
    page = bytearray(PAGE)

    def word(address, value):
        struct.pack_into('<Q', page, address - 0x10000, value)

    word(0x10000, 0x10080)
    word(0x101d8, 0x10400)
    for address, value in ((0x10400, 0x10800), (0x10408, 0x10850), (0x10410, 0x10850),
                           (0x10418, 0x10900), (0x10420, 0x10918), (0x10428, 0x10918)):
        word(address, value)
    page[0x800:0x812] = bytes([32]) + b'Virtual CD Drive\0'
    page[0x900:0x904] = b'\x04CD\0'
    return Snapshot(payload({0x10000: page, 0x13000: bytes(PAGE)}), LAYOUT)


def changed(snapshot, address, data):
    raw = bytearray(snapshot.payload)
    offset = snapshot.page_lookup[address & -PAGE] + address % PAGE
    raw[offset:offset + len(data)] = data
    return Snapshot(bytes(raw), LAYOUT)


class SparseStateTests(unittest.TestCase):
    def test_invisible_dirty_page_has_no_serialized_bytes(self):
        snapshot = Snapshot(payload(), LAYOUT)
        self.assertEqual([address for address, _ in snapshot.pages], [0x10000, 0x13000])
        self.assertEqual(snapshot.frame, 1)
        with self.assertRaisesRegex(ValueError, 'absent'):
            snapshot.read(0x12000, 1)

    def test_each_saved_page_maps_back_to_its_address(self):
        snapshot = Snapshot(payload(), LAYOUT)
        for address, offset in snapshot.pages:
            self.assertEqual(snapshot.guest_address(offset), address)
            self.assertEqual(snapshot.guest_address(offset + PAGE - 1), address + PAGE - 1)
        self.assertIsNone(snapshot.guest_address(0))
        self.assertIsNone(snapshot.guest_address(len(snapshot.payload) - 1))

    def test_read_across_adjacent_captured_pages(self):
        data = payload({0x10000: b'a' * PAGE, 0x11000: b'b' * PAGE}, dirty=(1, 1, 1, 0))
        snapshot = Snapshot(data, LAYOUT)
        self.assertEqual(snapshot.read(0x10ffe, 4), b'aabb')

    def test_read_cannot_skip_an_absent_page(self):
        snapshot = Snapshot(payload(), LAYOUT)
        with self.assertRaisesRegex(ValueError, 'absent'):
            snapshot.read(0x10fff, 2)

    def test_wrong_layout_is_rejected(self):
        wrong = Layout(LAYOUT.start, PAGE * 3, PAGE, LAYOUT.invisible)
        with self.assertRaisesRegex(ValueError, 'layout'):
            Snapshot(payload(), wrong)

    def test_unknown_page_status_and_dirty_flag_are_rejected(self):
        for offset in (0, 4):
            raw = bytearray(payload())
            at = raw.index(BLOCK_MAGIC) + len(BLOCK_MAGIC) + 32 + 16
            raw[at + offset] = 255
            with self.subTest(field=offset), self.assertRaisesRegex(ValueError, 'status or dirty'):
                Snapshot(bytes(raw), LAYOUT)

    def test_missing_or_duplicate_memory_marker_is_rejected(self):
        for data in (payload().replace(BLOCK_MAGIC, b'?' * len(BLOCK_MAGIC), 1), payload() + BLOCK_MAGIC):
            with self.subTest(length=len(data)), self.assertRaisesRegex(ValueError, 'memory block'):
                Snapshot(data, LAYOUT)

    def test_missing_end_marker_and_truncated_tail_are_rejected(self):
        for data in (payload().replace(HOST_END, b'?' * len(HOST_END), 1), payload()[:-1]):
            with self.subTest(length=len(data)), self.assertRaisesRegex(ValueError, 'end marker|managed state'):
                Snapshot(data, LAYOUT)

    def test_unaligned_pointer_read_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unaligned'):
            graph_snapshot().word(0x10001)


class MediaLabelTests(unittest.TestCase):
    def test_owner_graph_identifies_one_cd_media_type(self):
        binding = media_label(CORE, graph_snapshot())
        self.assertEqual(binding['object'], 0x10900)
        self.assertEqual(binding['length'], 2)
        self.assertEqual(binding['unused_begin'], 0x10904)

    def test_complete_equality_is_reported_separately(self):
        snapshot = graph_snapshot()
        report = classify(CORE, snapshot, snapshot)
        self.assertTrue(report['decoded_payloads_equal'])
        self.assertFalse(report['all_differences_in_unused_media_label_storage'])

    def test_unused_capacity_is_located_without_masking(self):
        original = graph_snapshot()
        other = changed(original, 0x10910, b'12345678')
        report = classify(CORE, original, other)
        self.assertEqual(report['different_decoded_bytes'], 8)
        self.assertFalse(report['decoded_payloads_equal'])
        self.assertTrue(report['all_differences_in_unused_media_label_storage'])
        self.assertEqual(report['state_bytes_masked'], 0)
        self.assertNotEqual(report['decoded_sha256'][0], report['decoded_sha256'][1])

    def test_an_extra_game_or_emulator_byte_is_not_classified_away(self):
        original = graph_snapshot()
        other = changed(changed(original, 0x10910, b'12345678'), 0x10300, b'x')
        report = classify(CORE, original, other)
        self.assertEqual(report['different_decoded_bytes'], 9)
        self.assertFalse(report['all_differences_in_unused_media_label_storage'])

    def test_changed_live_label_is_rejected(self):
        original = graph_snapshot()
        with self.assertRaisesRegex(ValueError, 'media label'):
            classify(CORE, original, changed(original, 0x10901, b'X'))

    def test_wrong_game_info_binding_is_rejected(self):
        other = changed(graph_snapshot(), 0x10000, struct.pack('<Q', 0x10088))
        with self.assertRaisesRegex(ValueError, 'game-info'):
            media_label(CORE, other)

    def test_wrong_vector_span_is_rejected(self):
        other = changed(graph_snapshot(), 0x10420, struct.pack('<Q', 0x10930))
        with self.assertRaisesRegex(ValueError, 'one media-type'):
            media_label(CORE, other)

    def test_long_string_and_missing_terminator_are_rejected(self):
        for address, value in ((0x10900, b'\x05'), (0x10903, b'x')):
            with self.subTest(address=address), self.assertRaises(ValueError):
                short_label(changed(graph_snapshot(), address, value), 0x10900)

    def test_different_frames_are_rejected(self):
        original = graph_snapshot()
        raw = bytearray(original.payload)
        at = raw.index(HOST_END) + len(HOST_END)
        struct.pack_into('<I', raw, at, 2)
        with self.assertRaisesRegex(ValueError, 'Frame'):
            classify(CORE, original, Snapshot(bytes(raw), LAYOUT))


class InputGuards(unittest.TestCase):
    def test_controls_require_explicit_accessor_execution(self):
        with self.assertRaisesRegex(ValueError, 'require --execute-accessors'):
            inspect_native(None, None, None, execute=False, controls=True)

    def test_duplicate_zip_members_are_rejected_before_decoding(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'duplicate.State'
            with zipfile.ZipFile(path, 'w') as archive, warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                archive.writestr('Core.bin.zst', b'first')
                archive.writestr('Core.bin.zst', b'second')
            with self.assertRaisesRegex(ValueError, 'duplicate core'):
                Snapshot.from_file(path, LAYOUT)

    def test_game_binary_cannot_be_used_as_emulator_core(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'game.exe'
            path.write_bytes(b'PS-X EXE' + bytes(1024))
            with self.assertRaisesRegex(ValueError, 'core identity'):
                CoreImage(path)

    def test_existing_report_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / '.decomp-lab/existing.json'
            report.parent.mkdir()
            report.write_bytes(b'keep')
            self.assertEqual(main(['--core', 'unused', '--original', 'unused', '--rebuilt', 'unused',
                                   '--execute-accessors', '--output', str(report)]), 1)
            self.assertEqual(report.read_bytes(), b'keep')


if __name__ == '__main__':
    unittest.main()
