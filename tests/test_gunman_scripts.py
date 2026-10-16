"""Independent phase, word-boundary and output-guard tests without game files."""
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import verify_gunman_scripts as gun


class GunmanScriptTests(unittest.TestCase):
    def setUp(self):
        symbols = {name: 0x80010000 + 0x100 * index for index, name in enumerate((
            'g_ENTITY_VTABLE', 'g_DREAM_SYS_VTABLE', 'g_EFFECT_VTABLE', 'D_8008AC14', 'D_8008AC0C',
            'g_RotateYawNine', 'g_RotateRollOne', 'g_RotateYawHalfTurn', 'g_RotateRollNegNine', 'D_8006EA90', 'D_8006EAA8'))}
        self.symbols = symbols
        def target(address, size):
            for name, bias in (('D_8006EA90', 0), ('D_8006EAA8', 100)):
                if symbols[name] <= address and address + size <= symbols[name] + 24:
                    offset = address - symbols[name]
                    return bytes(range(bias + offset, bias + offset + size))
            raise AssertionError('Unexpected synthetic palette read.')
        self.program = patch.object(gun.n, 'h', SimpleNamespace(symbols=symbols, target=target), create=True)
        self.program.start()
        self.addCleanup(self.program.stop)

    def result(self, **updates):
        return gun.expected('entity_gunman', gun.base_case(**updates))

    def test_initial_completion_does_not_fall_through_to_the_action_phase(self):
        result = self.result(frame=5, tick=5, duration=5, action=1)
        self.assertEqual([call[0] for call in result['trace']], ['aim_pose', 'animation_stop'])
        self.assertEqual(gun.read_word(result['entity'], 0x44), 10)
        self.assertEqual(gun.read_word(result['entity'], 0xFC), -1)

    def test_action_window_is_strict_and_uses_the_full_input_word(self):
        for action in (1, -1, 0x10000):
            before = self.result(state=10, tick=9, action=action)
            self.assertEqual(gun.read_word(before['entity'], 0x44), 12)
            at_boundary = self.result(state=10, tick=10, action=action, move_mode=2)
            self.assertEqual(gun.read_word(at_boundary['entity'], 0x44), 11)
            self.assertNotIn('read_action', [call[0] for call in at_boundary['trace']])
            self.assertEqual(at_boundary['dream'][0xC4:0xCC], bytes(8))
        zero = self.result(state=10, tick=9, action=0)
        self.assertEqual(gun.read_word(zero['entity'], 0x44), 10)

    def test_failed_allocation_still_advances_the_script_and_preserves_effect_memory(self):
        case = gun.base_case(state=11, tick=30, effect_mode='fail')
        result = gun.expected('entity_gunman', case)
        self.assertEqual(gun.read_word(result['entity'], 0x44), 13)
        self.assertEqual(gun.read_word(result['entity'], 0xFC), -1)
        self.assertEqual(result['effect'], bytes(gun.fixtures(case)['effect']))
        self.assertNotIn('activate_effect', [call[0] for call in result['trace']])

    def test_fast_activation_preserves_alpha_and_lower_flag_bits(self):
        result = self.result(state=11, tick=30)
        effect = result['effect']
        self.assertEqual(gun.read_word(effect, 0x74), -30)
        self.assertEqual(gun.read_word(effect, 0x80), 8)
        self.assertEqual(gun.read_word(effect, 0x84), 31)
        self.assertEqual(struct.unpack_from('<I', effect, 0x58)[0], 0x59ABCDEF)
        self.assertEqual(effect[0x64:0x68], bytes((21, 22, 23, 0xF3)))

    def test_attached_activation_has_distinct_life_channels_and_color_table(self):
        result = self.result(state=13, tick=30)
        effect = result['effect']
        self.assertEqual(gun.read_word(effect, 0x6C), 2)
        self.assertEqual(gun.read_word(effect, 0x74), 10)
        self.assertEqual(gun.read_word(effect, 0x78), 15)
        self.assertEqual(gun.read_word(effect, 0x80), 25)
        self.assertEqual(effect[0x64:0x68], bytes((100, 101, 102, 0xF3)))

    def test_existing_active_effect_does_not_restart_its_color_phase(self):
        case = gun.base_case(state=11, tick=30, effect_state=1)
        result = gun.expected('entity_gunman', case)
        self.assertNotIn('activate_effect', [call[0] for call in result['trace']])
        self.assertEqual(result['effect'][0x64:0x68], bytes(gun.fixtures(case)['effect'][0x64:0x68]))
        self.assertEqual(gun.read_word(result['effect'], 0x74), 30)

    def test_rng_domain_has_every_first_result_and_both_notification_classes(self):
        seeds = [gun.first_result_seed(value) for value in range(32768)]
        results = [((seed * 0x41C64E6D + 0x3039) & 0xFFFFFFFF) >> 16 & 0x7FFF for seed in seeds]
        self.assertEqual(results, list(range(32768)))
        for value, event in ((0, 12), (1, 10), (5, 12), (32767, 10)):
            result = self.result(state=13, tick=90, seed=gun.first_result_seed(value))
            self.assertEqual(result['trace'][-1], ['notification', gun.n.ENTITY, event])
            self.assertEqual(gun.read_word(result['entity'], 0x44), 14)

    def test_victim_completion_uses_native_wrapped_addition(self):
        duration = 0x7FFFFFFF
        tick = -0x7FFFFFF7
        result = gun.expected('entity_gunman_victim', gun.base_case(duration=duration, tick=tick, frame=10))
        self.assertEqual(gun.read_word(result['entity'], 0x44), 1)
        self.assertEqual(result['entity'][0x8C:0x94], bytes(8))
        self.assertIn('fall_pose', [call[0] for call in result['trace']])

    def test_little_endian_store_spans_cover_partial_word_edges(self):
        self.assertEqual(gun.store_span(43 << 26 | 0xFFF0, 0x100080), (0x100070, 4))
        self.assertEqual(gun.store_span(42 << 26 | 3, 0x100000), (0x100000, 4))
        self.assertEqual(gun.store_span(42 << 26 | 4, 0x100000), (0x100004, 1))
        self.assertEqual(gun.store_span(46 << 26 | 1, 0x100000), (0x100001, 3))
        with self.assertRaises(ValueError):
            gun.store_span(61 << 26, 0)

    def test_output_guards_precede_any_game_input_load(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(gun, 'ROOT', Path(directory)), patch.object(gun.n, 'load_program', side_effect=AssertionError('Game input loaded.')):
                with self.assertRaises(ValueError):
                    gun.verify(Path(directory) / 'outside')
                existing = Path(directory) / '.decomp-lab' / 'existing'
                existing.mkdir(parents=True)
                with self.assertRaises(ValueError):
                    gun.verify(existing)

    def test_invalid_fresh_effect_state_and_boolean_inputs_are_rejected(self):
        for updates in (dict(effect_mode='allocate', effect_state=1), dict(state=True), dict(effect_state=False)):
            with self.assertRaises(ValueError):
                gun.validate_case(gun.base_case(**updates))
        with self.assertRaises(ValueError):
            gun.first_result_seed(32768)


if __name__ == '__main__':
    unittest.main()
