"""Executable-free regression checks for reviewed original script decisions."""
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import verify_locomotive_scripts as loco


class LocomotiveScriptTests(unittest.TestCase):
    def setUp(self):
        program = SimpleNamespace(symbols={'g_ENTITY_VTABLE': 0x80010000, 'g_DREAM_SYS_VTABLE': 0x80010200})
        replacement = patch.object(loco.n, 'h', program, create=True)
        replacement.start()
        self.addCleanup(replacement.stop)

    def result(self, callback, **updates):
        return loco.expected(callback, loco.base_case(**updates))

    def calls(self, result):
        return [event[0] for event in result['trace']]

    def test_factory_initial_draw_overwrites_state_and_still_moves_at_tick_zero(self):
        for draw, state in ((0, 10), (3, 13), (4, 14), (5, 10), (32767, 12)):
            result = self.result(loco.CALLBACKS[0], tick=0, state=-1, seed=loco.first_result_seed(draw))
            self.assertEqual(loco.read_word(result['entity'], 0x44), state)
            self.assertEqual(self.calls(result), ['rand', 'common', 'forward'])

    def test_factory_scale_starts_at_320_and_requires_exact_state_fourteen(self):
        before = self.result(loco.CALLBACKS[0], state=14, tick=319)
        boundary = self.result(loco.CALLBACKS[0], state=14, tick=320)
        later_state = self.result(loco.CALLBACKS[0], state=15, tick=320)
        self.assertEqual(self.calls(before), ['common', 'forward'])
        self.assertEqual(self.calls(boundary), ['rand', 'scale'])
        self.assertEqual(self.calls(later_state), [])
        self.assertEqual(self.calls(self.result(loco.CALLBACKS[0], state=14, tick=321)), [])

    def test_factory_negative_tick_uses_signed_early_motion_branch(self):
        result = self.result(loco.CALLBACKS[0], state=15, tick=-1)
        self.assertEqual(self.calls(result), ['common', 'forward'])

    def test_scale_write_preserves_the_entire_array_and_changes_separate_halfword(self):
        case = loco.base_case(state=14, tick=320, denominator=23, seed=loco.first_result_seed(31))
        initial = loco.fixtures(case)
        result = loco.expected(loco.CALLBACKS[0], case)
        self.assertEqual(result['scratch'], initial['scratch'])
        self.assertEqual(result['denominator'], struct.pack('<h', 32))
        scale = result['trace'][-1]
        self.assertEqual(scale[1:4], [loco.n.ENTITY, 1, loco.DATA['scratch'][1] + 12])
        self.assertEqual(bytes.fromhex(scale[4]), bytes(initial['scratch'][12:]) + struct.pack('<h', 32))

    def test_factory_turn_windows_include_both_ends(self):
        for first, last in ((3000, 3091), (3341, 3433), (3698, 3791)):
            for tick, turns in ((first - 1, False), (first, True), (last, True), (last + 1, False)):
                result = self.result(loco.CALLBACKS[0], state=13, tick=tick)
                self.assertEqual('rotation' in self.calls(result), turns, tick)

    def test_common_completion_disables_link_and_behavior_and_preserves_tick(self):
        result = self.result(loco.CALLBACKS[0], state=13, tick=500, mode=6)
        self.assertEqual(loco.read_word(result['entity'], 0x44), 1)
        self.assertEqual(loco.read_word(result['entity'], 0xFC), 500)
        for offset in (0x8C, 0x90, 0xF0, 0xF4, 0xF8):
            self.assertEqual(loco.read_word(result['entity'], offset), 0)
        self.assertEqual([loco.read_word(result['context'], index * 4) for index in (4, 7, 12, 17)], [0, 4, 4, 4])
        self.assertEqual(self.calls(result)[-7:], ['disable_link', 'child_link_flag', 'stop_behaviour',
            'sound_stop', 'animation_stop', 'model_unload', 'set_triggered'])

    def test_factory_scale_variant_does_not_take_common_completion_at_500(self):
        result = self.result(loco.CALLBACKS[0], state=14, tick=500)
        self.assertEqual(self.calls(result), ['rand', 'scale'])
        self.assertEqual(loco.read_word(result['entity'], 0xF0), 1)
        self.assertEqual(loco.read_word(result['entity'], 0x44), 14)

    def test_kyoto_trigger_initialization_returns_to_motion_without_action_fallthrough(self):
        result = self.result(loco.CALLBACKS[1], state=0, tick=10, action=0x10000, mode=6)
        self.assertEqual(loco.read_word(result['entity'], 0x44), 10)
        self.assertEqual(loco.read_word(result['entity'], 0xFC), 0)
        self.assertEqual(self.calls(result), ['forward'])

    def test_kyoto_excludes_only_tick_ten_from_action_checks(self):
        for tick in (-1, 0, 9, 11, 100, 0x7FFFFFFF):
            result = self.result(loco.CALLBACKS[1], state=10, tick=tick, action=0x10000)
            self.assertEqual(loco.read_word(result['entity'], 0x44), 11)
            self.assertIn('clear_callbacks', self.calls(result))
        at_ten = self.result(loco.CALLBACKS[1], state=10, tick=10, action=0x10000)
        self.assertEqual(self.calls(at_ten), ['notification', 'forward'])
        self.assertEqual(loco.read_word(at_ten['entity'], 0x44), 10)

    def test_kyoto_zero_trigger_suppresses_state_logic_and_retains_motion(self):
        result = self.result(loco.CALLBACKS[1], state=10, tick=9, triggered=0, action=1)
        self.assertEqual(self.calls(result), ['forward'])
        self.assertEqual(loco.read_word(result['entity'], 0x44), 10)

    def test_kyoto_link_uses_full_active_word_and_original_transform_offset(self):
        for active, pointer in ((0, 0), (1, loco.TRANSFORM + 0x38), (0x10000, loco.TRANSFORM + 0x38)):
            result = self.result(loco.CALLBACKS[1], state=10, tick=9, action=0x10000, active=active)
            self.assertEqual(result['trace'][1], ['link_pose', loco.n.DREAM, pointer])

    def test_kyoto_clears_movement_and_keeps_view_callback(self):
        for move_mode in range(4):
            result = self.result(loco.CALLBACKS[1], state=10, tick=9, action=1, move_mode=move_mode)
            self.assertEqual(result['dream'][0x80:0x88], struct.pack('<II', 0xABCD1000, 3))
            self.assertEqual(result['dream'][0x98:0xA0], bytes(8))
            expected_view_flags = bytes(8) if move_mode == 2 else struct.pack('<II', 1, 1)
            self.assertEqual(result['dream'][0xC4:0xCC], expected_view_flags)
            self.assertEqual('set_view_mode' in self.calls(result), move_mode == 2)

    def test_kyoto_state_eleven_notifies_at_exactly_100_after_link_pose(self):
        result = self.result(loco.CALLBACKS[1], state=11, tick=100)
        self.assertEqual(self.calls(result), ['link_pose', 'notification', 'forward'])
        self.assertEqual(result['trace'][1], ['notification', loco.n.ENTITY, 10])
        self.assertEqual(self.calls(self.result(loco.CALLBACKS[1], state=11, tick=101)), ['link_pose', 'forward'])

    def test_natural_pink_initialization_preserves_existing_state_for_other_colors(self):
        pink = self.result(loco.CALLBACKS[2], state=0, tick=0, chunk_mood=(4, 4, 0, 0, 0))
        neutral = self.result(loco.CALLBACKS[2], state=1, tick=0)
        self.assertEqual(loco.read_word(pink['entity'], 0x44), 11)
        self.assertIn(['dream_color', 5], pink['trace'])
        self.assertEqual(loco.read_word(neutral['entity'], 0x44), 1)
        self.assertIn(['dream_color', 7], neutral['trace'])

    def test_zero_instance_count_uses_chunk_average_even_with_other_instance_bytes(self):
        result = self.result(loco.CALLBACKS[2], tick=0, instance_mood=(9, 9, 0, 0, 0))
        self.assertIn(['instance_average', 9, 9], result['trace'])
        self.assertIn(['dream_color', 7], result['trace'])
        self.assertEqual(loco.read_word(result['entity'], 0x44), 0)

    def test_counted_instance_contribution_can_make_pink(self):
        result = self.result(loco.CALLBACKS[2], tick=0, instance_mood=(0, 0, 8, 8, 1))
        self.assertIn(['instance_average', 8, 8], result['trace'])
        self.assertIn(['dream_color', 5], result['trace'])
        self.assertEqual(loco.read_word(result['entity'], 0x44), 11)

    def test_mood_signed_division_truncates_toward_zero(self):
        dream = loco.fixtures(loco.base_case(chunk_mood=(-4, 4, -5, 5, 2)))['dream']
        self.assertEqual(loco.mood_average(dream, 0x144), (-3, 3))

    def test_mood_axis_wrap_has_asymmetric_exact_boundaries(self):
        for total, expected in ((9, 9), (10, -9), (-9, -9), (-10, 9)):
            dream = loco.fixtures(loco.base_case(chunk_mood=(0, 0, total, total, 1)))['dream']
            self.assertEqual(loco.mood_average(dream, 0x144), (expected, expected))

    def test_mood_combination_uses_wrapped_native_word_addition(self):
        dream = loco.fixtures(loco.base_case(chunk_mood=(127, -128, 0x7FFFFFFF, -0x80000000, 1)))['dream']
        self.assertEqual(loco.mood_average(dream, 0x144), (9, -9))

    def test_natural_pause_applies_to_every_nonzero_state(self):
        for state in (-1, 1, 11):
            result = self.result(loco.CALLBACKS[2], state=state, tick=2160)
            self.assertEqual(self.calls(result), ['animation_stop'])
            self.assertEqual(loco.read_word(result['entity'], 0x90), 0)
            self.assertEqual([loco.read_word(result['context'], index * 4) for index in (7, 12, 17)], [-2, -2, -2])
            self.assertEqual(loco.read_word(result['context'], 16), 12345)
        zero = self.result(loco.CALLBACKS[2], state=0, tick=2160)
        self.assertEqual(self.calls(zero), ['common', 'forward'])

    def test_natural_late_pose_window_has_ten_ticks_then_animation_resumes(self):
        for tick in (2550, 2559):
            result = self.result(loco.CALLBACKS[2], state=11, tick=tick)
            self.assertEqual(self.calls(result), [])
            self.assertEqual(loco.read_word(result['context'], 28), 5)
            self.assertEqual(loco.read_word(result['context'], 32), -2)
        resumed = self.result(loco.CALLBACKS[2], state=11, tick=2560, mode=6)
        self.assertEqual(self.calls(resumed), ['animation_play'])
        self.assertEqual(loco.read_word(resumed['context'], 4), 1)

    def test_natural_two_tick_gap_precedes_movement_resume(self):
        for tick in (2561, 2562):
            self.assertEqual(self.calls(self.result(loco.CALLBACKS[2], state=11, tick=tick)), [])
        self.assertEqual(self.calls(self.result(loco.CALLBACKS[2], state=11, tick=2563)), ['common', 'forward'])

    def test_natural_vertical_motion_precedes_shared_forward_motion_from_2801(self):
        result = self.result(loco.CALLBACKS[2], state=11, tick=2801)
        self.assertEqual(self.calls(result), ['vertical', 'common', 'forward'])
        self.assertEqual(result['trace'][0], ['vertical', loco.n.ENTITY, loco.n.u32(-32), 0])
        self.assertEqual(self.calls(self.result(loco.CALLBACKS[2], state=11, tick=2800)), ['common', 'forward'])

    def test_nonpink_completion_changes_the_next_scheduled_pause_branch(self):
        case = loco.base_case(state=0, tick=2180)
        first = loco.expected(loco.CALLBACKS[2], case)
        second = loco.expected(loco.CALLBACKS[2], dict(case, tick=2181), first)
        self.assertEqual(loco.read_word(first['entity'], 0x44), 1)
        self.assertEqual(self.calls(second), [])
        self.assertEqual(loco.read_word(second['entity'], 0xF4), 0)
        self.assertEqual(loco.read_word(second['entity'], 0x90), 0)

    def test_first_rng_seed_domain_contains_every_fifteen_bit_result(self):
        seeds = [loco.first_result_seed(value) for value in range(32768)]
        results = [((seed * 0x41C64E6D + 0x3039) & 0xFFFFFFFF) >> 16 & 0x7FFF for seed in seeds]
        self.assertEqual(results, list(range(32768)))
        self.assertEqual(len(set(seeds)), 32768)

    def test_invalid_native_words_and_division_traps_are_rejected(self):
        for updates in ({'tick': 0x80000000}, {'seed': -1}, {'active': True}, {'denominator': 32768},
                        {'move_mode': 4}, {'chunk_mood': (128, 0, 0, 0, 0)},
                        {'instance_mood': (0, 0, -0x80000000, 0, -1)}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                loco.validate_case(loco.base_case(**updates))
        for value in (-1, 32768, True):
            with self.assertRaises(ValueError):
                loco.first_result_seed(value)

    def test_output_boundary_is_validated_before_game_inputs_are_read(self):
        outside = loco.ROOT / 'docs' / 'must-not-be-created-by-a-test'
        with patch.object(loco.n, 'load_program') as load:
            with self.assertRaisesRegex(ValueError, 'fresh private output'):
                loco.verify(outside)
            load.assert_not_called()
        self.assertFalse(outside.exists())


if __name__ == '__main__':
    unittest.main()
