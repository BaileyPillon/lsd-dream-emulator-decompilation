"""Check independent position-model edges and preservation without game inputs."""
import contextlib
import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import verify_render_position as position


class RenderPositionTests(unittest.TestCase):
    def test_horizontal_upper_edge_selects_the_next_label(self):
        case = position.base_case(position=(40960, 0, 1024))
        self.assertEqual(position.selected_label(case), 1)
        data, status, label = position.resolved_info(case, bytes([0xC9]) * 44)
        self.assertEqual((status, label, data[:4]), (0, 1, b'\xff\0\0\0'))

    def test_height_layers_exclude_lower_and_include_upper_edges(self):
        origins = tuple((0, 0, 0) for _ in range(7))
        for y, wanted in ((1, None), (0, 0), (-2047, 0), (-2048, 1),
                          (-12288, 6), (-14335, 6), (-14336, None)):
            with self.subTest(y=y):
                case = position.base_case(origins=origins, position=(1024, y, 1024), mode=1)
                self.assertEqual(position.selected_label(case), wanted)

    def test_flat_mode_ignores_world_height(self):
        case = position.base_case(position=(1024, -2147483648, 1024), mode=0)
        self.assertEqual(position.selected_label(case), 0)

    def test_record_order_preserves_label_priority_and_changes_object_pointer(self):
        labels = (6, 2, 5, 1, 4, 0, 3)
        case = position.base_case(origins=tuple((0, 0, 0) for _ in range(7)), labels=labels)
        data, _, selected = position.resolved_info(case, bytes([0xC9]) * 44)
        self.assertEqual(selected, 0)
        pointer = struct.unpack_from('<I', data, 36)[0]
        self.assertEqual(pointer, 0x110020 + 0xEC + 5 * 0x1C)

    def test_signed_partition_uses_truncation_toward_zero(self):
        case = position.base_case(entry='partition', value=-129, divisor=7)
        buffers, result, _ = position.expected(case)
        self.assertEqual(buffers['output'][0x20:0x22], b'\xfd\xee')
        self.assertEqual(result, 7)
        self.assertEqual(position.quotient(-32768, -32768), 1)
        with self.assertRaises(ValueError):
            position.quotient(1, 0)

    def test_cell_residue_crosses_the_half_tile_and_tile_edges(self):
        for x, cell, residue in ((1023, 0, -1), (1024, 0, 0),
                                 (2047, 0, 1023), (2048, 1, -1024)):
            with self.subTest(x=x):
                data, status, _ = position.resolved_info(
                    position.base_case(position=(x, 0, 1024)), bytes([0xC9]) * 44)
                self.assertEqual(status, 0)
                self.assertEqual(data[2], cell)
                self.assertEqual(struct.unpack_from('<h', data, 4)[0], residue)
                self.assertEqual(data[10:12], b'\xc9\xc9')

    def test_missing_world_slot_retains_the_entire_output(self):
        case = position.base_case(position=(-1, 0, -1))
        initial = position.fixture(case)[0]
        buffers, result, trace = position.expected(case)
        self.assertEqual(result, 0)
        self.assertEqual(buffers['output'], bytes(initial['output']))
        self.assertEqual(sum(entry[0] == 'label' for entry in trace), 7)

    def test_cached_lookup_skips_resolution_even_with_zero_divisor(self):
        case = position.base_case(output_present=False, divisor=0)
        initial, pointers, _, _ = position.fixture(case)
        buffers, result, trace = position.expected(case)
        self.assertEqual(result, 0x110020 + 0xBC)
        self.assertEqual(buffers['output'], bytes(initial['output']))
        self.assertEqual(struct.unpack_from('<I', buffers['auxiliary'], 0x20)[0], pointers['position'])
        self.assertEqual(len(trace), 1)

    def test_signed_world_wrap_keeps_native_interval_direction(self):
        case = position.base_case(origins=((2147442688, 0, 2147442688),) + position.ORIGINS[1:],
                                  position=(2147442688, 0, 2147442688))
        self.assertIsNone(position.selected_label(case))
        case = position.base_case(origins=((-2147483648, 0, -2147483648),) + position.ORIGINS[1:],
                                  position=(-2147482624, 0, -2147482624))
        self.assertEqual(position.selected_label(case), 0)

    def test_composition_retains_actual_lookup_chain_and_resolved_info(self):
        case = position.base_case(auxiliary_present=False)
        model, _, _ = position.composition_expected(case)
        self.assertEqual([entry[0] for entry in model[1][:3]], ['lookup', 'resolve', 'world'])
        self.assertEqual(model[3][0:4], b'\xf8\x9a\0\0')
        self.assertTrue(any(entry[0] == 'row' for entry in model[1]))

    def test_incomplete_slot_labels_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'one native slot'):
            position.fixture(position.base_case(labels=(0, 1, 2, 3, 4, 5, 5)))

    def test_previous_private_report_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = root / '.decomp-lab' / 'report.json'
            report.parent.mkdir()
            report.write_bytes(b'preserved original position evidence')
            with patch.object(position, 'ROOT', root), patch.object(position, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(position.main(['--output', str(report)]), 2)
                verify.assert_not_called()
            self.assertEqual(report.read_bytes(), b'preserved original position evidence')

    def test_public_escape_is_rejected_before_loading_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(position, 'ROOT', root), patch.object(position, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(position.main(['--output', str(root / 'public' / 'report.json')]), 2)
                verify.assert_not_called()
            self.assertFalse((root / 'public').exists())


if __name__ == '__main__':
    unittest.main()
