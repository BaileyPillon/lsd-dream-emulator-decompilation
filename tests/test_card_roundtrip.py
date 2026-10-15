"""Synthetic card corruption and input-route guards; no game or BIOS required."""
from functools import reduce
from operator import xor
import struct
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tools.compare_card_roundtrip import expected_action, fields, lsd_payload, parse_card, validate_checkpoint
from tools.capture_card_roundtrip import capture_pair, preserve_saves


def checksum(card, frame):
    start = frame * 128
    card[start + 127] = reduce(xor, card[start:start + 127], 0)


def blank_card():
    card = bytearray(131072)
    card[:2] = b'MC'
    checksum(card, 0)
    for frame in range(1, 16):
        struct.pack_into('<I', card, frame * 128, 0xa0)
        struct.pack_into('<H', card, frame * 128 + 8, 0xffff)
        checksum(card, frame)
    return card


def install(card, block=1, name=b'BISLPS-01556-01'):
    offset = block * 128
    struct.pack_into('<IIH', card, offset, 0x51, 8192, 0xffff)
    card[offset + 10:offset + 10 + len(name) + 1] = name + b'\0'
    checksum(card, block)
    start = block * 8192
    card[start:start + 4] = b'SC\x13\x01'
    card[start + 512:start + 516] = b'J01\0'
    struct.pack_into('<I', card, start + 520, 1)
    return card


class CardImageTests(unittest.TestCase):
    def test_blank_card(self):
        self.assertEqual(parse_card(blank_card()), [])

    def test_complete_payload(self):
        card = install(blank_card())
        card[8192 + 512 + 1791] = 0xab
        payload = lsd_payload(card)
        self.assertEqual(len(payload), 1792)
        self.assertEqual(payload[-1], 0xab)
        self.assertEqual(parse_card(card)[0]['blocks'], [1])

    def test_fragmented_two_block_chain(self):
        card = install(blank_card())
        struct.pack_into('<IH', card, 128 + 4, 16384, 2)
        checksum(card, 1)
        struct.pack_into('<IIH', card, 3 * 128, 0x53, 0, 0xffff)
        checksum(card, 3)
        card[3 * 8192:4 * 8192] = bytes([0xa5]) * 8192
        saved = parse_card(card)[0]
        self.assertEqual(saved['blocks'], [1, 3])
        self.assertEqual(saved['data'][8192:], bytes([0xa5]) * 8192)

    def test_checksum_corruption(self):
        card = install(blank_card())
        card[128 + 10] ^= 1
        with self.assertRaisesRegex(ValueError, 'checksum'):
            parse_card(card)

    def test_card_extent_and_signature(self):
        for card in (b'', bytes(131072), blank_card()[:-1], blank_card() + b'\0'):
            with self.subTest(length=len(card)), self.assertRaisesRegex(ValueError, 'raw 128 KiB'):
                parse_card(card)

    def test_unknown_allocation_state(self):
        card = blank_card()
        struct.pack_into('<I', card, 128, 0x99)
        checksum(card, 1)
        with self.assertRaisesRegex(ValueError, 'allocation state'):
            parse_card(card)

    def test_allocation_cycle(self):
        card = install(blank_card())
        struct.pack_into('<H', card, 128 + 8, 0)
        checksum(card, 1)
        with self.assertRaisesRegex(ValueError, 'cyclic'):
            parse_card(card)

    def test_out_of_range_next_block(self):
        card = install(blank_card())
        struct.pack_into('<H', card, 128 + 8, 15)
        checksum(card, 1)
        with self.assertRaisesRegex(ValueError, 'Invalid'):
            parse_card(card)

    def test_orphaned_continuation(self):
        card = blank_card()
        struct.pack_into('<I', card, 128, 0x53)
        checksum(card, 1)
        with self.assertRaisesRegex(ValueError, 'Orphaned'):
            parse_card(card)

    def test_file_size_corruption(self):
        card = install(blank_card())
        struct.pack_into('<I', card, 128 + 4, 16384)
        checksum(card, 1)
        with self.assertRaisesRegex(ValueError, 'File size'):
            parse_card(card)

    def test_duplicate_filename(self):
        card = install(install(blank_card()), block=2)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            parse_card(card)

    def test_filename_encoding_and_termination(self):
        for name in (b'X' * 21, bytes([0x80]) + b'\0' * 20):
            card = install(blank_card())
            card[138:159] = name
            checksum(card, 1)
            with self.subTest(name=name), self.assertRaises(ValueError):
                parse_card(card)

    def test_wrong_lsd_header_and_payload(self):
        for offset in (8192, 8192 + 2, 8192 + 512, 8192 + 520):
            card = install(blank_card())
            card[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                lsd_payload(card)

    def test_multiple_files_are_outside_fixed_profile(self):
        card = install(install(blank_card()), block=2, name=b'OTHER')
        self.assertEqual(len(parse_card(card)), 2)
        with self.assertRaisesRegex(ValueError, 'only LSD slot'):
            lsd_payload(card)


class InputRouteTests(unittest.TestCase):
    def row(self, phase='save', **changes):
        row = {f'{phase}_returned': '0', f'{phase}_seen': '0', 'screen_kind': 'main',
               'screen_58': '2', 'card_24': '-', 'comment_00': '-'}
        row.update(changes)
        return row

    def test_completed_operation_is_neutral(self):
        row = self.row(save_returned='1', card_24='2')
        self.assertEqual(expected_action(row, 'save', True), ('neutral_after_card_return', ''))

    def test_cold_start_uses_circle(self):
        row = self.row('load', screen_kind='none')
        self.assertEqual(expected_action(row, 'load', False), ('skip_startup_with_circle', 'P1 \u25cb'))
        self.assertEqual(expected_action(row, 'load', True), ('wait_for_main', ''))

    def test_menu_targets_are_distinct(self):
        self.assertEqual(expected_action(self.row(), 'save', True), ('open_save', 'P1 \u25cb'))
        self.assertEqual(expected_action(self.row('load'), 'load', True), ('select_load_down', 'P1 D-Pad Down'))

    def test_comment_and_card_routes(self):
        self.assertEqual(expected_action(self.row(card_24='2'), 'save', True), ('confirm_card_dialog', 'P1 \u25cb'))
        self.assertEqual(expected_action(self.row(card_24='2', comment_00='1'), 'save', True), ('accept_comment', 'P1 \u25cb'))

    def test_phase_columns_preserve_native_offsets(self):
        for phase in ('save', 'load'):
            names = fields(phase)
            self.assertEqual(len(names), 135)
            self.assertEqual(len(set(names)), 135)
            self.assertIn('card_24', names)
            self.assertIn('card_28', names)
            self.assertIn(f'{phase}_returned', names)


class CheckpointTests(unittest.TestCase):
    def fixture(self):
        raw = bytearray(0x200000)
        flow, dream, graphics, pad, screen, card = (0x90000, 0x91000, 0x92000, 0x93000, 0x94000, 0x95000)
        def write(address, value):
            struct.pack_into('<I', raw, address, value)
        for address, value in ((0x8ac20, flow + 0x80000000), (flow, 0x8006d3c8),
                               (flow + 0x28, dream + 0x80000000), (flow + 0x1c, graphics + 0x80000000),
                               (dream, 0x80087bdc), (graphics + 4, pad + 0x80000000), (pad, 0x8006d370),
                               (screen, 0x80086b60), (screen + 0xc, graphics + 0x80000000),
                               (screen + 0xa4, dream + 0x80000000), (screen + 0xac, card + 0x80000000),
                               (card, 0x80086dc4), (card + 0x24, 2), (card + 0x28, 17)):
            write(address, value)
        row = dict.fromkeys(fields('save'), '-')
        row.update(screen=str(screen), dream=str(dream), screen_kind='main', stored_day='0', new_game='0',
                   pad_held='0', pad_released='0', pad_pressed='0')
        for prefix, base, last in (('screen', screen, 0xc0), ('card', card, 0x80)):
            for offset in range(0, last + 1, 4):
                row[f'{prefix}_{offset:02x}'] = str(struct.unpack_from('<I', raw, base + offset)[0])
        return raw, row, card, dream

    def test_complete_native_words_agree(self):
        raw, row, _, _ = self.fixture()
        validate_checkpoint(raw, row)

    def test_swapped_mode_offset_is_detected(self):
        raw, row, card, _ = self.fixture()
        struct.pack_into('<I', raw, card + 0x24, 1)
        with self.assertRaisesRegex(ValueError, 'card word 0x24'):
            validate_checkpoint(raw, row)

    def test_changed_day_is_detected(self):
        raw, row, _, dream = self.fixture()
        struct.pack_into('<I', raw, dream + 0x180, 1)
        with self.assertRaisesRegex(ValueError, 'stored_day'):
            validate_checkpoint(raw, row)


class CaptureOwnershipTests(unittest.TestCase):
    def test_exit_save_preserved_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            saves, folder = root / 'isolated', root / 'capture'
            saves.mkdir()
            folder.mkdir()
            data = bytes(range(256)) * 512
            (saves / 'owned.SaveRAM').write_bytes(data)
            result = preserve_saves(saves, folder)
            self.assertTrue(result['shared_save_ram_empty'])
            self.assertEqual((folder / 'exit-save-ram/owned.SaveRAM').read_bytes(), data)
            self.assertEqual(result['files_preserved'][0]['bytes'], 131072)

    def test_existing_exit_save_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            saves, folder = root / 'isolated', root / 'capture'
            saves.mkdir()
            (folder / 'exit-save-ram').mkdir(parents=True)
            source, target = saves / 'owned.SaveRAM', folder / 'exit-save-ram/owned.SaveRAM'
            source.write_bytes(b'new')
            target.write_bytes(b'preserved')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                preserve_saves(saves, folder)
            self.assertEqual(source.read_bytes(), b'new')
            self.assertEqual(target.read_bytes(), b'preserved')

    def test_existing_capture_workspace_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary, patch('tools.capture_card_roundtrip.sys', SimpleNamespace(platform='win32')):
            root = Path(temporary)
            marker = root / 'keep.txt'
            marker.write_text('keep', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'new workspace'):
                capture_pair(root, None, None, None, None, 'save', state='unused')
            self.assertEqual(marker.read_text(encoding='utf-8'), 'keep')

    def test_cold_load_refuses_a_saved_state(self):
        with tempfile.TemporaryDirectory() as temporary, patch('tools.capture_card_roundtrip.sys', SimpleNamespace(platform='win32')):
            target = Path(temporary) / 'new'
            with self.assertRaisesRegex(ValueError, 'cold Load'):
                capture_pair(target, None, None, None, None, 'load', state='wrong', card='unused')
            self.assertFalse(target.exists())

    def test_save_refuses_an_external_seed_card(self):
        with tempfile.TemporaryDirectory() as temporary, patch('tools.capture_card_roundtrip.sys', SimpleNamespace(platform='win32')):
            target = Path(temporary) / 'new'
            with self.assertRaisesRegex(ValueError, 'Save requires'):
                capture_pair(target, None, None, None, None, 'save', state='unused', card='wrong')
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
