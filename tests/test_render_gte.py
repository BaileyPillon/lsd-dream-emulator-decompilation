"""Check GTE narrowing and COP2 boundaries using synthetic inputs only."""
import contextlib
import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import verify_render_gte as gte


IDENTITY = (4096, 0, 0, 0, 4096, 0, 0, 0, 4096)


class RenderGteTests(unittest.TestCase):
    def test_identity_retains_split_signs_and_low_remainders(self):
        for vector in ((65537, -32769, 12345), (-1, 0, 1), (1073741823, -1073741823, 32768)):
            with self.subTest(vector=vector):
                self.assertEqual(gte.apply_model(IDENTITY, vector)[0], list(vector))

    def test_ir_high_part_truncation_preserves_original_large_vector_limit(self):
        self.assertEqual(gte.split_vector((-2147483648, 1073741824, -1073741824)),
                         ([0, -32768, -32768], [0, 0, 0]))
        self.assertEqual(gte.apply_model(IDENTITY, (-2147483648, 1073741824, -1073741824))[0],
                         [0, -1073741824, -1073741824])

    def test_negative_fixed_product_rounds_toward_negative_infinity(self):
        matrix = (1, 0, 0, 0, 1, 0, 0, 0, 1)
        result = gte.command_model(gte.matrix_words(matrix), (-1, 1, -4096), gte.COMMANDS[1])
        self.assertEqual(result['mac'], [-1, 0, -1])

    def test_unshifted_positive_sum_wraps_before_ir_saturation(self):
        result = gte.command_model(gte.matrix_words((-32768,) * 9), (-32768,) * 3, gte.COMMANDS[0])
        self.assertEqual(result['mac'], [-1073741824] * 3)
        self.assertEqual(result['ir'], [-32768] * 3)
        self.assertEqual(result['flags'], 0x81C00000)

    def test_ir3_limit_flag_alone_does_not_set_summary_bit(self):
        cr = gte.matrix_words((0, 0, 0, 0, 0, 0, 0, 0, 4096))
        result = gte.command_model(cr, (0, 0, 9), gte.COMMANDS[0])
        self.assertEqual(result['mac'], [0, 0, 36864])
        self.assertEqual(result['ir'], [0, 0, 32767])
        self.assertEqual(result['flags'], 0x00400000)

    def test_commands_do_not_use_matrix_padding_as_a_coefficient(self):
        cr = gte.matrix_words(IDENTITY)
        cr[4] |= 0xABCD0000
        self.assertEqual(gte.command_model(cr, (1, -2, 3), gte.COMMANDS[1])['mac'], [1, -2, 3])

    def test_unreviewed_mvmva_fields_are_rejected(self):
        for command in (gte.COMMANDS[0] ^ 0x2000, gte.COMMANDS[1] | 0x400, 0x4A000001):
            with self.subTest(command=command), self.assertRaises(ValueError):
                gte.command_model(gte.matrix_words(IDENTITY), (1, 2, 3), command)
            with self.assertRaises(ValueError):
                gte.decode_cop2(command)

    def test_only_reviewed_transfer_registers_are_accepted(self):
        self.assertEqual(gte.decode_cop2(0x48C80000), ('ctc2', 8, 0))
        self.assertEqual(gte.decode_cop2(0x488B4800), ('mtc2', 11, 9))
        self.assertEqual(gte.decode_cop2(0x480BC800), ('mfc2', 11, 25))
        self.assertIsNone(gte.decode_cop2(0))
        for word in (0x48C82800, 0x488B4000, 0x480BB800, 0x48C80001):
            with self.subTest(word=word), self.assertRaises(ValueError):
                gte.decode_cop2(word)

    def test_adapter_masks_cr4_and_narrows_signed_ir_input(self):
        adapter = gte.Cop2Adapter(None)
        adapter.step(0x48CC2000, lambda number: 0xABCDFFFF, lambda number, value: None)
        adapter.step(0x488B4800, lambda number: 0xFFFF8000, lambda number, value: None)
        self.assertEqual(adapter.cr[4], 65535)
        self.assertEqual(adapter.ir[0], -32768)

    def test_adapter_detects_incorrect_native_output_before_register_read(self):
        class FaultyBridge:
            def execute(self, **inputs):
                result = gte.command_model(**inputs)
                result['mac'][0] += 1
                return result
        adapter = gte.Cop2Adapter(FaultyBridge())
        with self.assertRaisesRegex(ValueError, 'disagrees'):
            adapter.step(gte.COMMANDS[1], lambda number: 0, lambda number, value: None)
        self.assertEqual(adapter.commands, [])

    def test_aliasing_uses_actual_overwritten_matrix_and_vector_inputs(self):
        case = gte.standalone_case(IDENTITY, (65537, -32769, 12345),
                                  matrix_offset=0x30, vector_offset=0x30, output_offset=0x34)
        before, pointers = gte.standalone_fixture(case)
        matrix = struct.unpack_from('<9h', before, 0x30)
        vector = struct.unpack_from('<3i', before, 0x30)
        result, _ = gte.apply_model(matrix, vector)
        after, _ = gte.standalone_expected(case)
        self.assertEqual(struct.unpack_from('<3i', after[0], 0x34), tuple(result))
        self.assertEqual(after[0][:0x34], before[:0x34])
        self.assertEqual(after[0][0x40:], before[0x40:])
        self.assertEqual(after[1], pointers[2])

    def test_unaligned_and_unguarded_vectors_are_rejected(self):
        for changes in (dict(matrix_offset=0x32), dict(vector_offset=8), dict(output_offset=0x170)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                gte.standalone_fixture(gte.standalone_case(**changes))

    def test_existing_report_and_logs_are_preserved_before_input_loading(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = root / '.decomp-lab' / 'report.json'
            report.parent.mkdir()
            for path in (report, report.with_suffix('.log'), report.with_name('report-stderr.log')):
                path.write_bytes(b'prior evidence')
                with patch.object(gte, 'ROOT', root), patch.object(gte, 'verify') as verify, \
                        contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(gte.main(['--output', str(report), '--bridge', 'unused.exe', '--runtime', 'unused']), 2)
                    verify.assert_not_called()
                self.assertEqual(path.read_bytes(), b'prior evidence')
                path.unlink()

    def test_public_report_is_rejected_before_input_loading(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(gte, 'ROOT', Path(folder)), \
                patch.object(gte, 'verify') as verify, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(gte.main(['--output', 'public.json', '--bridge', 'unused.exe', '--runtime', 'unused']), 2)
            verify.assert_not_called()


if __name__ == '__main__':
    unittest.main()
