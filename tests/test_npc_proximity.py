"""Independent semantic/domain guards for original proximity composition."""
from collections import defaultdict
import unittest

from tools import verify_npc_proximity as npc


class NPCProximityTests(unittest.TestCase):
    def test_distance_uses_x_and_z_and_preserves_word_wrap(self):
        self.assertEqual(npc.distance((100, -90000, -500), (0, 90000, 0)), 600)
        self.assertEqual(npc.distance((0x7fffffff, 1, 0), (-0x80000000, -1, 0)), 1)
        self.assertEqual(npc.distance((-0x80000000, 0, 0), (0, 1, 0)), -0x80000000)

    def test_ratio_keeps_two_stage_rounding_and_inclusive_threshold(self):
        self.assertEqual(npc.trigger_ratio((20480, 0, 0), (0, 77, 0), 10, 1000), 1024)
        self.assertEqual(npc.trigger_ratio((20481, 0, 0), (0, 77, 0), 10, 1000), -1)
        self.assertEqual(npc.trigger_ratio((600, 0, 0), (0, 77, 0), 10, 1000), 30)
        self.assertEqual(npc.trigger_ratio((0, 0, 0), (0, 77, 0), 10, 1000, False), -1)

    def test_zero_division_and_invalid_constructed_properties_are_rejected(self):
        with self.assertRaises(ValueError):
            npc.trigger_ratio((0, 0, 0), (0, 0, 0), 0, 1000)
        base = npc.base_case('entity_bear', 43, 10)
        for changes in ({'entity_id': 130}, {'proximity_scale': 0}, {'proximity': 0},
                        {'has_dream': 1}, {'position': (True, 0, 0)}, {'euler': (32768, 0, 0)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                npc.validate_case(dict(base, **changes))

    def test_seed_profile_covers_all_initialization_and_motion_choices(self):
        residues, choices = set(), set()
        for seed in npc.representative_seeds():
            first = (seed * 0x41c64e6d + 0x3039) & 0xffffffff
            second = (first * 0x41c64e6d + 0x3039) & 0xffffffff
            a, b = (first >> 16) & 0x7fff, (second >> 16) & 0x7fff
            residues.add(a % 10)
            choices.add((a & 1, b & 3))
        self.assertEqual(residues, set(range(10)))
        self.assertEqual(choices, {(a, b) for a in (0, 1) for b in range(4)})

    def test_period_profiles_cover_every_nonnegative_phase_and_signed_edges(self):
        for callback, period, binding in [('entity_acrobats', 30, {'index': 66, 'proximity': 20}),
                                          ('entity_ship', 300, {'index': 64, 'proximity': 40})]:
            timers = {case['timer'] for group, case in npc.cases(callback, binding) if group == 'complete_timer_phases'}
            self.assertTrue(set(range(period)) <= timers)
            self.assertTrue({-period, -1, 0x7fffffff, -0x80000000} <= timers)

    def test_profiles_include_post_translation_radius_crossings_and_pose_edges(self):
        groups = defaultdict(list)
        for group, case in npc.cases('entity_rabbit', {'index': 44, 'proximity': 10}):
            npc.validate_case(case)
            groups[group].append(case)
        crossings = groups['ratio_after_common_translation']
        self.assertEqual({case['tick'] for case in crossings}, {200, 201, 321, 340})
        self.assertEqual({case['position'][2] for case in crossings}, {20480 + 128, -20480 + 128})
        self.assertIn((-32768, -1, 32767), {case['euler'] for case in groups['spatial_boundaries']})
        self.assertEqual({case['has_dream'] for case in groups['native_proximity_boundaries']}, {False, True})


if __name__ == '__main__':
    unittest.main()
