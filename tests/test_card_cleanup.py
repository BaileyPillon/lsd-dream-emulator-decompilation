"""Exercise cleanup oracle boundaries and private-image/report custody gates."""
import contextlib
import io
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import verify_card_cleanup as cleanup


class CleanupContractTests(unittest.TestCase):
    def test_absent_table_makes_no_release_or_fixture_change(self):
        case = dict(cleanup.BASE_CASE, present=False, count=8)
        trace, buffers = cleanup.expected(case)
        self.assertEqual(trace, [])
        self.assertEqual(buffers, {name: bytes(data) for name, data in cleanup.fixtures(case).items()})

    def test_negative_count_still_releases_buffer_and_table(self):
        case = dict(cleanup.BASE_CASE, count=-(1 << 31))
        trace, buffers = cleanup.expected(case)
        self.assertEqual(trace, [0x109040, cleanup.BASES['table_a'] + cleanup.OFFSET])
        self.assertEqual(struct.unpack_from('<i', buffers['object'], cleanup.OFFSET + 0x2C)[0], -(1 << 31))
        self.assertEqual(struct.unpack_from('<I', buffers['object'], cleanup.OFFSET + 0x3C)[0], 0x109040)

    def test_table_is_reloaded_after_each_release(self):
        case = dict(cleanup.BASE_CASE, mutations=((1, 'table', 'table_b'), (2, 'table', 'table_a')))
        trace, _ = cleanup.expected(case)
        self.assertEqual(trace, [0x109040, 0x10A000, 0x108020, 0x101040])

    def test_count_shrink_stops_before_the_next_entry(self):
        case = dict(cleanup.BASE_CASE, count=8, mutations=((2, 'count', 0),))
        trace, buffers = cleanup.expected(case)
        self.assertEqual(trace, [0x109040, 0x108000, 0x101040])
        self.assertEqual(struct.unpack_from('<i', buffers['object'], cleanup.OFFSET + 0x2C)[0], 0)

    def test_final_clear_follows_the_allocator_contract_write(self):
        case = dict(cleanup.BASE_CASE, mutations=((4, 'table', 'table_b'),))
        trace, buffers = cleanup.expected(case)
        self.assertEqual(trace[-1], 0x101040)
        self.assertEqual(struct.unpack_from('<I', buffers['object'], cleanup.OFFSET + 0x38)[0], 0)

    def test_oversized_count_or_mutation_is_rejected(self):
        for case in (dict(cleanup.BASE_CASE, count=9),
                     dict(cleanup.BASE_CASE, mutations=((1, 'count', 9),)),
                     dict(cleanup.BASE_CASE, segment=0xC0000000)):
            with self.subTest(case=case), self.assertRaises(ValueError):
                cleanup.fixtures(case)


class CleanupCustodyTests(unittest.TestCase):
    def program(self):
        return SimpleNamespace(ROM=bytes([0xA6]) * 4096,
                               LOAD=int(cleanup.FUNCTION['address'], 16))

    def test_candidate_accepts_only_the_reviewed_changed_span(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / '.decomp-lab' / 'candidate.exe'
            path.parent.mkdir()
            program = self.program()
            data = bytearray(program.ROM)
            data[0x810] ^= 1
            path.write_bytes(data)
            with patch.object(cleanup, 'ROOT', root):
                code, record = cleanup.candidate_code(path, program)
            self.assertEqual(len(code), 148)
            self.assertEqual(record['whole_executable_byte_differences'], 1)
            self.assertFalse(record['complete_executable_equal'])
            self.assertFalse(record['source_promoted'])
            self.assertEqual(path.read_bytes(), data)

    def test_candidate_rejects_header_other_function_or_length_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / '.decomp-lab' / 'candidate.exe'
            path.parent.mkdir()
            program = self.program()
            for changed_offset in (0, 0x800 + 148, None):
                data = bytearray(program.ROM)
                if changed_offset is None:
                    data.pop()
                else:
                    data[changed_offset] ^= 1
                path.write_bytes(data)
                with self.subTest(changed_offset=changed_offset), patch.object(cleanup, 'ROOT', root), \
                        self.assertRaises(ValueError):
                    cleanup.candidate_code(path, program)

    def test_candidate_outside_lab_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'public.exe'
            path.write_bytes(self.program().ROM)
            with patch.object(cleanup, 'ROOT', root), self.assertRaises(ValueError):
                cleanup.candidate_code(path, self.program())

    def test_existing_report_is_preserved_before_loading_game(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / '.decomp-lab' / 'report.json'
            path.parent.mkdir()
            path.write_bytes(b'preserved evidence')
            with patch.object(cleanup, 'ROOT', root), patch.object(cleanup, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cleanup.main(['--output', str(path)]), 2)
                verify.assert_not_called()
            self.assertEqual(path.read_bytes(), b'preserved evidence')

    def test_report_escape_is_rejected_before_loading_game(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / '.decomp-lab' / '..' / 'public' / 'report.json'
            with patch.object(cleanup, 'ROOT', root), patch.object(cleanup, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cleanup.main(['--output', str(path)]), 2)
                verify.assert_not_called()
            self.assertFalse((root / 'public').exists())


if __name__ == '__main__':
    unittest.main()
