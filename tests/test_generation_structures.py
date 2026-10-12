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
        self.symbols = {name: 0x80001000 + i * 0x100 for i, name in enumerate(
            ('D_800876FC', 'D_800879C4', 'D_8008788C', 'D_800878D4',
             'D_8008780C', 'D_80087838', 'D_8008782C', 'D_800877EC', 'D_800877F8'))}
        data = {
            self.symbols['D_8008780C']: struct.pack('<8i', *generation.RATE_WORDS),
            self.symbols['D_80087838']: struct.pack('<6h', 0, 1, 1, 10, 0, 1),
            self.symbols['D_8008782C']: bytes(12), self.symbols['D_800877EC']: bytes(12),
            self.symbols['D_800877F8']: struct.pack('<5i', 0, -128, 128, -256, 64),
        }

        def target(address, size):
            for start, block in data.items():
                if start <= address < start + len(block):
                    return block[address - start:address - start + size]
            return struct.pack('<4h', 1, 16, 7, 1)[:size]

        self.program = patch.object(generation.n, 'h', SimpleNamespace(
            symbols=self.symbols, target=target),
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
        for changes in ({'variant': 8, 'enabled': 1}, {'enabled': 5}, {'count': 18}, {'mode': 4},
                        {'seed': -1}, {'position': (0, 1)}, {'tick': True},
                        {'euler': (0, 0, 32768)}, {'size_key': True}):
            with self.assertRaises(ValueError):
                generation.fixtures(generation.base_case(**changes))

    def test_fixture_groups_include_guard_and_signed_scale_boundaries(self):
        cases = list(generation.cases())
        self.assertEqual(len(cases), 3116)
        self.assertTrue(any(case['count'] == 17 and case['mode'] == 3 for group, case in cases))
        self.assertTrue(any(case['tick'] == 0x7FFFFFFF for group, case in cases))
        self.assertTrue(any(case['scale_mode'] == -1 for group, case in cases))
        self.assertEqual({case['variant'] for group, case in cases}, set(range(8)))

    def test_late_effects_activate_after_tick_500_and_preserve_signed_remainders(self):
        case = generation.base_case(enabled=1, variant=7, tick=499, euler=(-32768, -1, 32767))
        before = generation.fixtures(case)
        inactive = generation.model(case)
        self.assertEqual(inactive['child_coordinates'], bytes(before['child_coordinates']))
        active = generation.model(dict(case, tick=500))
        self.assertEqual(struct.unpack_from('<3h', active['poses'], 0x10), (0, 0, 4095))
        self.assertEqual(struct.unpack_from('<i', active['child_coordinates'], 0x20)[0], 77)
        self.assertEqual(struct.unpack_from('<i', active['child_coordinates'], 0x120)[0], 79)

    def test_periodic_reset_overwrites_the_preceding_child_z_addition(self):
        result = generation.model(generation.base_case(enabled=1, variant=7, tick=569, size_key=-3))
        self.assertEqual(struct.unpack_from('<3i', result['child_coordinates'], 0x18), (384, 0, 0))
        self.assertEqual(struct.unpack_from('<3i', result['child_coordinates'], 0x118), (768, 0, 0))
        names = [item[0] for item in result['trace']]
        self.assertEqual(names[-2:], ['position_set', 'position_set'])
        self.assertEqual(names.count('position_add'), 2)

    def test_vertical_layout_uses_two_successive_absolute_offsets(self):
        result = generation.model(generation.base_case(enabled=3, variant=7, tick=569, size_key=-32768))
        self.assertEqual(struct.unpack_from('<3i', result['child_coordinates'], 0x18), (0, -256, 0))
        self.assertEqual(struct.unpack_from('<3i', result['child_coordinates'], 0x118), (0, -512, 0))

    def test_consecutive_updates_keep_ticks_and_child_motion_from_the_prior_state(self):
        first = generation.base_case(enabled=1, variant=3, tick=500)
        previous = generation.model(first)
        result = generation.model(dict(first, position=(0, 0, 0)), previous)
        self.assertEqual(struct.unpack_from('<I', result['objects'], 0x24)[0], 502)
        self.assertEqual(struct.unpack_from('<i', result['child_coordinates'], 0x20)[0], 331)
        self.assertEqual(struct.unpack_from('<3i', result['coordinates'], 0x18), (-200, 230, 0))

    def test_all_five_nonzero_variant_periods_use_truncating_division(self):
        self.assertEqual([abs(generation.div(24500, rate)) for rate in generation.RATE_WORDS[3:]],
                         [24500, 12250, 6125, 1531, 95])

    def test_histories_cover_each_active_layout_and_rate_with_unreset_graphs(self):
        histories = list(generation.histories())
        self.assertEqual(len(histories), 40)
        self.assertEqual(sum(len(sequence) for kind, sequence in histories), 480)
        self.assertEqual({kind for kind, sequence in histories}, {'late_activation', 'first_period_reset'})
        self.assertTrue(all(len(sequence) == 12 for kind, sequence in histories))

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
