"""Hand-calculated semantic and domain checks; native evidence is separate."""
from types import SimpleNamespace
import struct
import unittest
from unittest.mock import patch

from tools import verify_npc_periodic_spatial as npc


class PeriodicSpatialTests(unittest.TestCase):
    def setUp(self):
        program = SimpleNamespace(symbols={'g_ENTITY_VTABLE': 0x80100, 'g_DREAM_SYS_VTABLE': 0x80200,
                                           'g_BASE_CLASS_VTABLE': 0x80300})
        self.program = patch.object(npc.n, 'h', program, create=True)
        self.program.start()
        self.rotation = patch.object(npc.rotation, 'rotation_bytes', return_value=struct.pack('<9h',
            4096, 0, 0, 0, 4096, 0, 0, 0, 4096))
        self.rotation.start()
        self.addCleanup(self.program.stop)
        self.addCleanup(self.rotation.stop)
        self.base = npc.base_case({'index': 9, 'proximity': 30})

    def test_half_duration_has_original_word_wrap_and_signed_rounding(self):
        for duration, half in [(0, 0), (1, 0), (2, 1), (3, 1), (15, 7), (-1, 0), (-2, -1),
                               (-3, -1), (-5, -2), (-0x80000000, -0x40000000),
                               (0x7fffffff, 0x3fffffff), (0xffffffff, 0)]:
            self.assertEqual(npc.half_duration(duration), half)

    def test_division_trap_paths_are_explicitly_rejected_only_where_used(self):
        for duration in (0, 1, -1, 0xffffffff):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                npc.validate_case('entity_minotaur', dict(self.base, duration=duration))
        with self.assertRaises(ValueError):
            npc.validate_case('entity_minotaur', dict(self.base, duration=-2, timer=-0x80000000))
        npc.validate_case('entity_giant_minotaur', dict(self.base, duration=0))
        for changes in ({'duration': True}, {'timer': 0x80000000}, {'seed': -1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                npc.validate_case('entity_minotaur', dict(self.base, **changes))

    def test_selected_small_positive_and_negative_periods_cover_every_phase(self):
        grouped = {}
        for group, case in npc.cases('entity_minotaur', {'index': 9, 'proximity': 30}):
            npc.validate_case('entity_minotaur', case)
            if group == 'duration_and_signed_timer_boundaries':
                grouped.setdefault(case['duration'], set()).add(case['timer'])
        for duration, timers in grouped.items():
            period = abs(npc.half_duration(duration))
            if period <= 60:
                self.assertTrue(set(range(period)) <= timers)
        self.assertTrue({-3, -5, 3, 5, 15, 120, -0x80000000, 0x7fffffff} <= set(grouped))

    def test_ratio_is_measured_before_forward_motion_crosses_radius(self):
        radius = 30 << 11
        case = dict(self.base, position=(0, 777, radius + 1), timer=0)
        for callback, amount in [('entity_bird', -512), ('entity_minotaur', -30)]:
            result, commands = npc.expected(callback, case)
            self.assertEqual(struct.unpack_from('<i', result['context'], 16)[0], -1)
            self.assertEqual(struct.unpack_from('<i', result['coordinate'], 0x20)[0], radius + 1 + amount)
            self.assertEqual(len(commands), 2)
        case = dict(case, timer=1)
        result, _ = npc.expected('entity_bird', case)
        self.assertEqual(result['context'][16:20], b'\xc4' * 4)

    def test_minotaur_odd_duration_and_giant_distinct_command_writes(self):
        for timer, triggered in [(6, False), (7, True), (-7, True), (-8, False)]:
            result, _ = npc.expected('entity_minotaur', dict(self.base, duration=15, timer=timer))
            self.assertEqual(result['context'][28:32], struct.pack('<i', 10) if triggered else b'\xc4' * 4)
        for timer in (0, 1, -1):
            result, _ = npc.expected('entity_giant_minotaur', dict(self.base, timer=timer))
            self.assertEqual(result['context'][16:20], bytes(4))
            for offset in (28, 48, 68):
                self.assertEqual(result['context'][offset:offset + 4], struct.pack('<i', 11) if timer == 0 else b'\xc4' * 4)

    def test_fixtures_retain_selected_duration_and_deduplicate_actual_memory(self):
        case = dict(self.base, duration=-3)
        buffers = npc.fixtures(case)
        self.assertEqual(struct.unpack_from('<i', buffers['entity'][1], 0x80)[0], -3)
        self.assertEqual(npc.input_key(case), npc.input_key(dict(case, duration=0xfffffffd)))
        self.assertNotEqual(npc.input_key(case), npc.input_key(dict(case, seed=42)))


if __name__ == '__main__':
    unittest.main()
