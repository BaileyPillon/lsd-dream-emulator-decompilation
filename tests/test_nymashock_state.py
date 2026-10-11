"""Keep unused host-string storage separate from changed state and invalid graphs."""

from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import inspect_nymashock_state as state


GAME = 0x36F0029A850
GAME_POINTER = 0x36F0029A9F0
LAYOUT = 0x36F0080F980
NAME = 0x36F0080FC00
OTHER_STATE = 0x36F00300000


def fixture(extra_invisible_dirty=False, missing_name=False):
    # Independent synthetic bytes with a native pointer/vector/string graph.
    # No game, firmware, emulator binary or captured state is included.
    pages = {GAME // 4096: bytearray(4096), LAYOUT // 4096: bytearray(4096),
             OTHER_STATE // 4096: bytearray(4096)}
    def write(address, value):
        page, offset = divmod(address, 4096)
        pages[page][offset:offset + len(value)] = value
    write(GAME_POINTER, struct.pack('<Q', GAME))
    write(GAME + 344, struct.pack('<Q', LAYOUT))
    write(LAYOUT + 24, struct.pack('<QQQ', NAME, NAME + 24, NAME + 24))
    write(NAME, b'\x04CD\0' + b'\0' * 20)
    if missing_name:
        del pages[NAME // 4096]
    count = 0xD80A000 // 4096
    statuses, dirty = bytearray([6] * count), bytearray(count)
    for page in pages:
        index = page - 0x36F00000000 // 4096
        statuses[index], dirty[index] = 2, 1
    if extra_invisible_dirty:
        for address in (0x36F00296000, 0x36F0060A000, 0x36F0070A000, 0x36F0480A000):
            index = (address - 0x36F00000000) // 4096
            statuses[index], dirty[index] = 2, 1
    header = (b'ActivatedWaterboxHost_v1' + b'ActivatedMemoryBlock' + b'\0' * 32
              + struct.pack('<QQ', 0x36F00000000, 0xD80A000))
    tail = b'GuestThreadSet' + 'ʇsoHxoqɹǝʇɐMpǝʇɐʌᴉʇɔ∀'.encode() + b'fixture trailer'
    return header + statuses + dirty + b''.join(pages[p] for p in sorted(pages)) + tail


def change(data, address, value):
    result = bytearray(data)
    for offset, byte in zip(state.MemoryView(data).offsets(address, len(value)), value):
        result[offset] = byte
    return bytes(result)


class NymashockStateTests(unittest.TestCase):
    def test_unused_label_storage_remains_a_full_byte_difference(self):
        original = fixture()
        rebuilt = change(original, NAME + 16, b'01234567')
        report = state.compare_decoded(original, rebuilt)
        self.assertFalse(report['whole_decoded_bytes_equal'])
        self.assertEqual(report['different_bytes'], 8)
        self.assertEqual(report['identified_unused_label_storage_difference_bytes'], 8)
        self.assertEqual(report['unclassified_difference_bytes'], 0)
        self.assertEqual(report['state_bytes_masked'], 0)
        self.assertEqual(report['whole_feature_groups_accepted'], 0)
        self.assertEqual(original, fixture())

    def test_other_state_change_is_retained_alongside_unused_storage(self):
        original = fixture()
        rebuilt = change(change(original, NAME + 16, b'01234567'), OTHER_STATE + 3, b'X')
        report = state.compare_decoded(original, rebuilt)
        self.assertEqual(report['different_bytes'], 9)
        self.assertEqual(report['identified_unused_label_storage_difference_bytes'], 8)
        self.assertEqual(report['unclassified_difference_bytes'], 1)
        self.assertFalse(report['whole_decoded_bytes_equal'])

    def test_changed_active_label_is_rejected(self):
        original = fixture()
        with self.assertRaisesRegex(ValueError, 'short CD label'):
            state.compare_decoded(original, change(original, NAME + 1, b'X'))

    def test_changed_string_size_or_long_flag_is_rejected(self):
        original = fixture()
        for marker in (b'\x06', b'\x05'):
            with self.subTest(marker=marker), self.assertRaisesRegex(ValueError, 'short CD label'):
                state.compare_decoded(original, change(original, NAME, marker))

    def test_game_symbol_root_must_agree(self):
        original = fixture()
        with self.assertRaisesRegex(ValueError, 'core symbol'):
            state.compare_decoded(original, change(original, GAME_POINTER, struct.pack('<Q', GAME + 8)))

    def test_media_type_vector_extent_is_checked(self):
        original = fixture()
        with self.assertRaisesRegex(ValueError, 'media-type record'):
            state.compare_decoded(original, change(original, LAYOUT + 32, struct.pack('<Q', NAME)))

    def test_vector_cannot_alias_unrelated_state_outside_the_heap(self):
        original = fixture()
        rebuilt = change(original, LAYOUT + 24, struct.pack('<QQQ', OTHER_STATE, OTHER_STATE + 24, OTHER_STATE + 24))
        with self.assertRaisesRegex(ValueError, 'media-type record'):
            state.compare_decoded(original, rebuilt)

    def test_invisible_dirty_pages_do_not_shift_saved_virtual_addresses(self):
        core = fixture(extra_invisible_dirty=True)
        view = state.MemoryView(core)
        self.assertEqual(view.read(NAME, 4), b'\x04CD\0')
        self.assertEqual(state.media_type(view)['media_type_name'], hex(NAME))
        with self.assertRaisesRegex(ValueError, 'not saved'):
            view.read(0x36F0060A000, 1)

    def test_missing_page_is_not_reconstructed_from_assumed_zero_bytes(self):
        with self.assertRaisesRegex(ValueError, 'not saved'):
            state.media_type(state.MemoryView(fixture(missing_name=True)))

    def test_truncated_page_payload_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'truncated|profile differs'):
            state.MemoryView(fixture()[:-4096])

    def test_wrong_memory_layout_is_rejected(self):
        data = bytearray(fixture())
        offset = data.index(b'ActivatedMemoryBlock') + 20 + 32
        struct.pack_into('<Q', data, offset, 0x36F00001000)
        with self.assertRaisesRegex(ValueError, 'Memory layout'):
            state.MemoryView(bytes(data))

    def test_unknown_core_binary_is_rejected_before_reading_states(self):
        with tempfile.TemporaryDirectory() as folder:
            core = Path(folder) / 'shock.wbx.zst'
            core.write_bytes(b'synthetic different core')
            with self.assertRaisesRegex(ValueError, 'outside the checked'):
                state.inspect(Path(folder) / 'missing-a.State', Path(folder) / 'missing-b.State', core)


if __name__ == '__main__':
    unittest.main()
