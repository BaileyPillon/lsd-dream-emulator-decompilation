"""Owned fixture and evidence-boundary checks; original execution is optional."""
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import verify_model_enumeration as enumeration


class ModelEnumerationTests(unittest.TestCase):
    def fixture(self, count=260, selector=42, output=True, index=True, segment=0):
        return enumeration.fixture('object_model', count, selector, output, index, segment)

    def test_full_output_survives_byte_count_wrap(self):
        for count in (0, 255, 256, 257, 260):
            _, before, expected, _, result = self.fixture(count=count)
            self.assertEqual(result, count & 255)
            self.assertEqual(expected[4][32:32 + count], bytes(i & 255 for i in range(count)))
            self.assertEqual(expected[4][:32], before[4][:32])
            self.assertEqual(expected[4][32 + count:], before[4][32 + count:])

    def test_selector_and_result_use_full_signed_word(self):
        for selector, expected_index in ((42, 3), (65536, 0), (-1, 0)):
            _, before, expected, _, _ = self.fixture(selector=selector)
            self.assertEqual(struct.unpack_from('<i', expected[5], 32)[0], expected_index)
            self.assertEqual(expected[5][36:], before[5][36:])
            self.assertEqual(expected[5][:32], before[5][:32])

    def test_null_output_counts_index_records(self):
        _, before, expected, arguments, _ = self.fixture(output=False)
        self.assertEqual(arguments[1], 0)
        self.assertEqual(expected[4], before[4])
        self.assertEqual(struct.unpack_from('<i', expected[5], 32)[0], 3)

    def test_null_index_preserves_the_complete_record(self):
        _, before, expected, arguments, _ = self.fixture(index=False)
        self.assertEqual(arguments[2], 0)
        self.assertEqual(expected[5], before[5])

    def test_aliases_retain_physical_receiver_and_output_locations(self):
        _, _, _, low, result = self.fixture()
        _, _, _, cached, cached_result = self.fixture(segment=0x80000000)
        self.assertEqual(tuple(value & 0x1fffffff for value in cached), low)
        self.assertEqual(cached_result, result)

    def test_private_report_guards_run_before_loading_original_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            lab = root / '.decomp-lab'
            lab.mkdir()
            retained = lab / 'retained.json'
            retained.write_text('keep this evidence\n')
            with patch.object(enumeration, 'ROOT', root), patch.object(enumeration, 'collect_progress') as inputs:
                for path in (root / 'public.json', lab / 'wrong.txt', retained):
                    with self.assertRaises(ValueError):
                        enumeration.verify(path)
                inputs.assert_not_called()
            self.assertEqual(retained.read_text(), 'keep this evidence\n')


if __name__ == '__main__':
    unittest.main()
