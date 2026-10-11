"""Check rotation rounding, aliasing and report preservation without game data."""
import contextlib
import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import verify_render_rotation as rotation


def synthetic_pairs():
    # Deliberately asymmetric fixture values, not the game's lookup table.
    pairs = [(0, 4096)] * 4096
    pairs[1] = (17, 4094)
    pairs[1024] = (4096, 0)
    pairs[4095] = (-2, 4095)
    return pairs


class RenderRotationTests(unittest.TestCase):
    def test_negative_angle_reflects_the_absolute_index(self):
        pairs = synthetic_pairs()
        self.assertEqual(rotation.sine_cosine(-1, pairs), (-17, 4094))
        self.assertEqual(rotation.sine_cosine(4095, pairs), (-2, 4095))
        self.assertNotEqual(rotation.sine_cosine(-1, pairs), rotation.sine_cosine(4095, pairs))

    def test_equivalent_halfword_encodings_have_one_case_identity(self):
        signed = rotation.standalone_case((-1, -32768, 1))
        encoded = rotation.standalone_case((65535, 32768, 65537))
        self.assertEqual(signed, encoded)

    def test_zero_rotation_is_fixed_point_identity(self):
        matrix = struct.unpack('<9h', rotation.rotation_bytes((0, 0, 0), synthetic_pairs()))
        self.assertEqual(matrix, (4096, 0, 0, 0, 4096, 0, 0, 0, 4096))

    def test_quarter_turns_preserve_axis_orientation(self):
        cases = [((1024, 0, 0), (4096, 0, 0, 0, 0, -4096, 0, 4096, 0)),
                 ((0, 1024, 0), (0, 0, 4096, 0, 4096, 0, -4096, 0, 0)),
                 ((0, 0, 1024), (0, -4096, 0, 4096, 0, 0, 0, 0, 4096))]
        for euler, expected in cases:
            with self.subTest(euler=euler):
                self.assertEqual(struct.unpack('<9h', rotation.rotation_bytes(euler, synthetic_pairs())), expected)

    def test_negative_product_is_rounded_after_negation(self):
        matrix = struct.unpack('<9h', rotation.rotation_bytes((1, 1, 0), synthetic_pairs()))
        self.assertEqual(matrix[5], -17)
        self.assertNotEqual(matrix[5], -(4094 * 17 >> 12))

    def test_intermediate_rounding_is_retained_in_mixed_rotation(self):
        matrix = struct.unpack('<9h', rotation.rotation_bytes((1, 1, 1), synthetic_pairs()))
        self.assertEqual(matrix, (4092, -17, 17, 17, 4091, -17, -17, 17, 4092))
        self.assertEqual(matrix[4], 4091)  # A single final rounding would give 4092.

    def test_overlapping_input_is_snapshotted_before_matrix_writes(self):
        case = rotation.standalone_case((1, -1, 1024), angle_offset=0x22, matrix_offset=0x20)
        before, pointers = rotation.standalone_fixture(case)
        actual, result = rotation.standalone_expected(case, synthetic_pairs())
        self.assertEqual(actual[0x20:0x32], rotation.rotation_bytes((1, -1, 1024), synthetic_pairs()))
        self.assertEqual(actual[:0x20], bytes(before[:0x20]))
        self.assertEqual(actual[0x32:], bytes(before[0x32:]))
        self.assertEqual(result, pointers[1])

    def test_separate_input_and_output_padding_are_preserved(self):
        case = rotation.standalone_case((1, 1024, -1), segment=0xA0000000)
        before, pointers = rotation.standalone_fixture(case)
        actual, result = rotation.standalone_expected(case, synthetic_pairs())
        self.assertEqual(actual[:0x60], bytes(before[:0x60]))
        self.assertEqual(actual[0x72:], bytes(before[0x72:]))
        self.assertEqual(result, pointers[1])

    def test_fixture_rejects_unaligned_or_unguarded_outputs(self):
        for changes in [dict(angle_offset=0x21), dict(matrix_offset=0x0E), dict(matrix_offset=0xC0)]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                rotation.standalone_fixture(rotation.standalone_case(**changes))

    def test_composition_passes_the_real_coefficients_to_apply_and_builder(self):
        case = dict(rotation.position.base_case(angle=1024), euler=(1, 1024, -1))
        model, _, _ = rotation.composition_expected(case, synthetic_pairs())
        coefficients = rotation.rotation_bytes(case['euler'], synthetic_pairs())
        self.assertEqual(model[0]['angles'][0x30:0x36], struct.pack('<3h', 1, 1024, -1))
        self.assertEqual(model[4][:18], coefficients)
        apply = next(entry for entry in model[1] if entry[0] == 'apply')
        self.assertEqual(apply[4][:18], coefficients)
        for entry in model[1]:
            if entry[0] == 'build':
                self.assertEqual(entry[3][:18], coefficients)

    def test_composition_rejects_a_different_grid_and_rotation_yaw(self):
        case = dict(rotation.position.base_case(angle=1024), euler=(0, 0, 0))
        with self.assertRaisesRegex(ValueError, 'yaw must agree'):
            rotation.composition_fixture(case)

    def test_previous_private_report_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = root / '.decomp-lab' / 'report.json'
            report.parent.mkdir()
            report.write_bytes(b'preserved original rotation evidence')
            with patch.object(rotation, 'ROOT', root), patch.object(rotation, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(rotation.main(['--output', str(report)]), 2)
                verify.assert_not_called()
            self.assertEqual(report.read_bytes(), b'preserved original rotation evidence')

    def test_public_escape_is_rejected_before_loading_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(rotation, 'ROOT', root), patch.object(rotation, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(rotation.main(['--output', str(root / 'public' / 'report.json')]), 2)
                verify.assert_not_called()
            self.assertFalse((root / 'public').exists())


if __name__ == '__main__':
    unittest.main()
