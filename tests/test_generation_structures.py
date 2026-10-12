"""Bounded graph and candidate guards use synthetic buffers, without game data."""
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import verify_generation_structures as generation


class GenerationStructureTests(unittest.TestCase):
    def setUp(self):
        self.symbols = {'D_800876FC': 0x80001000, 'D_800879C4': 0x80002000,
                        'D_8008788C': 0x80003000}
        self.program = patch.object(generation.n, 'h', SimpleNamespace(
            symbols=self.symbols, target=lambda address, size: struct.pack('<4h', 1, 16, 7, 1)[:size]),
            create=True)
        self.program.start()
        self.addCleanup(self.program.stop)

    def test_negative_type_and_nonpositive_count_leave_every_graph_buffer_untouched(self):
        for changes in ({'type': -1, 'count': 17}, {'count': -1}, {'count': 0}):
            case = generation.base_case(**changes)
            result = generation.model(case)
            self.assertEqual(result['trace'], [])
            self.assertEqual(result['rng_seed'], 0)
            for name, value in generation.fixtures(case).items():
                self.assertEqual(result[name], bytes(value))

    def test_live_list_updates_successive_objects_and_preserves_later_records(self):
        case = generation.base_case(count=2)
        result = generation.model(case)
        self.assertEqual([item[:2] for item in result['trace'] if item[0] == 'update'],
                         [['update', generation.OBJECTS], ['update', generation.OBJECTS + 0x100]])
        self.assertEqual(struct.unpack_from('<3i', result['coordinates'], 0x18), (800, 2230, 3000))
        self.assertEqual(struct.unpack_from('<3i', result['coordinates'], 0x118), (900, 2229, 2950))
        before = generation.fixtures(case)
        self.assertEqual(result['objects'][0x200:], bytes(before['objects'][0x200:]))
        self.assertEqual(result['coordinates'][0x200:], bytes(before['coordinates'][0x200:]))
        self.assertEqual(result['player'], bytes(before['player']))
        self.assertEqual(result['listing'], bytes(before['listing']))

    def test_position_and_tick_wrap_at_native_word_width(self):
        result = generation.model(generation.base_case(
            tick=0x7FFFFFFF, position=(-0x80000000, 0x7FFFFFFF, 0)))
        self.assertEqual(struct.unpack_from('<i', result['objects'], 0x24)[0], -0x80000000)
        self.assertEqual(struct.unpack_from('<3i', result['coordinates'], 0x18),
                         (0x7FFFFF38, -0x7FFFFF1B, 0))

    def test_sprite_relative_scale_uses_wrapped_low_product_before_signed_shift(self):
        result = generation.model(generation.base_case(mode=3, scale_mode=1, scale_value=0x7FFFFFFF))
        # 0x7FFFFFFF * 256 has low word 0xFFFFFF00, whose signed >>12 is -1.
        self.assertEqual(struct.unpack_from('<i', result['sprites'], 0x15C)[0], -1)
        self.assertEqual(len([item for item in result['trace'] if item[0] == 'rand']), 8)
        self.assertEqual(len([item for item in result['trace'] if item[0] == 'sprite_scale']), 4)

    def test_unsafe_mode_zero_variant_and_oversized_list_are_rejected_before_execution(self):
        for changes in ({'variant': 3, 'enabled': 1}, {'count': 18}, {'mode': 4},
                        {'seed': -1}, {'position': (0, 1)}, {'tick': True}):
            with self.assertRaises(ValueError):
                generation.fixtures(generation.base_case(**changes))

    def test_fixture_groups_include_guard_and_signed_scale_boundaries(self):
        cases = list(generation.cases())
        self.assertEqual(len(cases), 1116)
        self.assertTrue(any(case['count'] == 17 and case['mode'] == 3 for group, case in cases))
        self.assertTrue(any(case['tick'] == 0x7FFFFFFF for group, case in cases))
        self.assertTrue(any(case['scale_mode'] == -1 for group, case in cases))
        self.assertTrue(all(case['variant'] in (0, 1, 2) for group, case in cases))

    def candidate_program(self):
        return SimpleNamespace(LOAD=int(generation.FUNCTIONS[0]['address'], 16),
                               ROM=bytes(0x800 + 136 + 8))

    def test_candidate_changes_inside_function_remain_unaccepted(self):
        program = self.candidate_program()
        data = bytearray(program.ROM)
        data[0x800] = 1
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'candidate.exe'
            path.write_bytes(data)
            observed, identity = generation.candidate_identity(program, path)
        self.assertEqual(observed, bytes(data))
        self.assertEqual(identity['changed_bytes'], 1)
        self.assertFalse(identity['complete_image_equal'])
        self.assertFalse(identity['source_promoted'])

    def test_candidate_header_truncation_and_other_function_changes_are_rejected(self):
        program = self.candidate_program()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'candidate.exe'
            for offset in (0, 0x800 + 136):
                data = bytearray(program.ROM)
                data[offset] = 1
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    generation.candidate_identity(program, path)
            path.write_bytes(program.ROM[:-1])
            with self.assertRaises(ValueError):
                generation.candidate_identity(program, path)


if __name__ == '__main__':
    unittest.main()
