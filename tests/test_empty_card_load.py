"""Synthetic empty-card and not-found-route guards; no game inputs required."""
from functools import reduce
from operator import xor
from pathlib import Path
from types import SimpleNamespace
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools.capture_card_roundtrip import capture_pair
from tools.compare_empty_card_load import (
    main, validate_card_transition, validate_empty_card, validate_empty_route,
)


def checksum(card, frame):
    start = frame * 128
    card[start + 127] = reduce(xor, card[start:start + 127], 0)


def empty_card():
    card = bytearray(131072)
    card[:2] = b'MC'
    checksum(card, 0)
    for frame in range(1, 16):
        struct.pack_into('<I', card, frame * 128, 0xa0)
        struct.pack_into('<H', card, frame * 128 + 8, 0xffff)
        checksum(card, frame)
    return card


def native_route():
    rows = []
    for frame, (operation, state) in enumerate(((1, 0), (1, 13), (0, 0))):
        rows.append({'relative_frame': str(frame), 'card_24': str(operation), 'card_28': str(state),
                     'dream': '1000000', 'stored_day': '0', 'new_game': '1', 'screen_kind': 'main',
                     'comment_00': '-', 'select_00': '-'})
    return rows


class EmptyCardTests(unittest.TestCase):
    def test_formatted_empty_card(self):
        self.assertIsNone(validate_empty_card(empty_card()))

    def test_allocated_save_is_not_an_empty_card(self):
        card = empty_card()
        struct.pack_into('<IIH', card, 128, 0x51, 8192, 0xffff)
        card[138:143] = b'SAVE\0'
        checksum(card, 1)
        with self.assertRaisesRegex(ValueError, 'no allocated files'):
            validate_empty_card(card)

    def test_deleted_directory_is_outside_fixed_profile(self):
        card = empty_card()
        struct.pack_into('<I', card, 128, 0xa1)
        checksum(card, 1)
        with self.assertRaisesRegex(ValueError, 'free, unlinked'):
            validate_empty_card(card)

    def test_free_entry_with_a_link_is_rejected(self):
        card = empty_card()
        struct.pack_into('<H', card, 128 + 8, 2)
        checksum(card, 1)
        with self.assertRaisesRegex(ValueError, 'free, unlinked'):
            validate_empty_card(card)

    def test_write_test_frame_is_verified_without_masking(self):
        seed = bytes(empty_card())
        card = bytearray(seed)
        card[8064:8192] = seed[:128]
        report = validate_card_transition(seed, card, seed)
        self.assertEqual([row['offset'] for row in report['changes']], [8064, 8065, 8191])
        self.assertNotEqual(report['input_sha256'], report['exit_sha256'])

    def test_preinitialized_write_test_is_unchanged(self):
        card = empty_card()
        card[8064:8192] = card[:128]
        self.assertEqual(validate_card_transition(card, card, card)['changes'], [])

    def test_unexpected_card_data_change_is_rejected(self):
        seed = bytes(empty_card())
        for offset in (8064, 8100, 8192, 131071):
            card = bytearray(seed)
            card[8064:8192] = seed[:128]
            card[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, 'Unexpected card transition'):
                validate_card_transition(seed, card, seed)

    def test_changed_backup_is_rejected(self):
        seed = bytes(empty_card())
        card = bytearray(seed)
        card[8064:8192] = seed[:128]
        with self.assertRaisesRegex(ValueError, 'backup'):
            validate_card_transition(seed, card, card)


class EmptyRouteTests(unittest.TestCase):
    def test_not_found_and_main_screen_return(self):
        self.assertEqual(validate_empty_route(native_route(), 2)['first_not_found_frame'], 1)

    def test_other_native_error_is_not_the_not_found_profile(self):
        rows = native_route()
        rows[1]['card_28'] = '12'
        with self.assertRaisesRegex(ValueError, 'fixed empty-card'):
            validate_empty_route(rows, 2)

    def test_save_operation_is_rejected(self):
        rows = native_route()
        rows[0]['card_24'] = rows[1]['card_24'] = '2'
        with self.assertRaisesRegex(ValueError, 'fixed empty-card'):
            validate_empty_route(rows, 2)

    def test_load_must_not_restore_a_saved_day(self):
        for name, value in (('stored_day', '1'), ('new_game', '0')):
            rows = native_route()
            rows[-1][name] = value
            with self.subTest(field=name), self.assertRaisesRegex(ValueError, 'day/new-game'):
                validate_empty_route(rows, 2)

    def test_unexpected_selection_and_comment_are_rejected(self):
        for name in ('comment_00', 'select_00'):
            rows = native_route()
            rows[1][name] = '123'
            with self.subTest(field=name), self.assertRaisesRegex(ValueError, 'unexpectedly constructed'):
                validate_empty_route(rows, 2)

    def test_return_requires_the_main_screen(self):
        rows = native_route()
        rows[-1]['screen_kind'] = 'none'
        with self.assertRaisesRegex(ValueError, 'return to the main'):
            validate_empty_route(rows, 2)


class CaptureGuards(unittest.TestCase):
    def test_empty_card_profile_cannot_be_used_for_save(self):
        with tempfile.TemporaryDirectory() as temporary, patch('tools.capture_card_roundtrip.sys', SimpleNamespace(platform='win32')):
            folder = Path(temporary) / 'new'
            with self.assertRaisesRegex(ValueError, 'requires a cold Load'):
                capture_pair(folder, None, None, None, None, 'save', state='unused', card_kind='empty')
            self.assertFalse(folder.exists())

    def test_unknown_card_profile_is_rejected_before_launch(self):
        with tempfile.TemporaryDirectory() as temporary, patch('tools.capture_card_roundtrip.sys', SimpleNamespace(platform='win32')):
            folder = Path(temporary) / 'new'
            with self.assertRaisesRegex(ValueError, 'requires a cold Load'):
                capture_pair(folder, None, None, None, None, 'load', card='unused', card_kind='other')
            self.assertFalse(folder.exists())

    def test_existing_report_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary, patch('tools.compare_empty_card_load.ROOT', Path(temporary)):
            report = Path(temporary) / '.decomp-lab/existing.json'
            report.parent.mkdir()
            report.write_bytes(b'preserve')
            with self.assertRaisesRegex(ValueError, 'new JSON'):
                main(['--original', 'unused', '--rebuilt', 'unused', '--output', str(report)])
            self.assertEqual(report.read_bytes(), b'preserve')


if __name__ == '__main__':
    unittest.main()
