"""Owned script boundary fixtures; native execution evidence is separate."""
from pathlib import Path
from types import SimpleNamespace
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import verify_astronaut as a


class AstronautTests(unittest.TestCase):
    def setUp(self):
        symbols = {'g_ENTITY_VTABLE': 0x80100, 'g_DREAM_SYS_VTABLE': 0x80200,
                   'g_BASE_CLASS_VTABLE': 0x80300, 'D_8008ABA4': 0x8aba4,
                   'g_MoveUp64Back64': 0x89da8, 'g_RotateYawNeg120': 0x89ce8,
                   'g_Rotate5050Neg12030': 0x89cf4}
        self.program = patch.object(a.n, 'h', SimpleNamespace(symbols=symbols), create=True)
        self.rotation = patch.object(a.rotation, 'rotation_bytes', return_value=struct.pack('<9h',
            4096, 0, 0, 0, 4096, 0, 0, 0, 4096))
        self.program.start()
        self.rotation.start()
        self.rng = patch.object(a.n, 'RNG', 0x8ae00, create=True)
        self.rng.start()
        self.addCleanup(self.program.stop)
        self.addCleanup(self.rotation.stop)
        self.addCleanup(self.rng.stop)
        self.binding = {'index': 7, 'proximity': 10}
        self.base = a.base_case(self.binding)

    def result(self, **changes):
        return a.expected(dict(self.base, **changes))[0]

    @staticmethod
    def word(result, name, offset):
        return struct.unpack_from('<i', result[name], offset)[0]

    @staticmethod
    def labels(result):
        return [event[0] for event in result['trace']]

    def test_normal_direction_switches_at_exactly_1200(self):
        for tick, delta in ((-0x80000000, 50), (-1, 50), (1199, 50), (1200, -50), (2399, -50), (2401, -50)):
            with self.subTest(tick=tick):
                result = self.result(tick=tick)
                self.assertEqual(self.word(result, 'coordinate', 0x20), 3000 + delta)
                self.assertEqual(result['trace'][-2][2], a.n.u32(delta))

    def test_tick_2400_resets_only_that_tick_and_does_not_move(self):
        result = self.result(tick=2400, timer=10)
        self.assertEqual(self.word(result, 'entity', 0xfc), -1)
        self.assertEqual(self.word(result, 'coordinate', 0x20), 3000)
        self.assertNotIn('forward', self.labels(result))
        self.assertEqual(self.word(result, 'context', 28), 5)

    def test_pink_color_changes_state_only_at_command_timer_zero(self):
        for timer in (-10, 0, 1, 10):
            result = self.result(timer=timer, chunk_mood=(4, 4, 0, 0, 0))
            self.assertEqual(self.word(result, 'entity', 0x44), 100 if timer == 0 else 0)
            self.assertEqual('read_dream_color' in self.labels(result), timer == 0)

    def test_color_thresholds_and_zero_instance_fallback(self):
        for dynamic, upper, pink in ((3, 4, False), (4, 3, False), (4, 4, True), (9, 9, True), (-4, 9, False)):
            result = self.result(timer=0, chunk_mood=(dynamic, upper, 0, 0, 0),
                                 instance_mood=(-9, -9, 9999, -9999, 0))
            self.assertEqual(self.word(result, 'entity', 0x44), 100 if pink else 0)

    def test_nonzero_instance_count_combines_its_own_average(self):
        result = self.result(timer=0, chunk_mood=(9, 9, 0, 0, 0), instance_mood=(-9, -9, 0, 0, 1))
        self.assertEqual(self.word(result, 'entity', 0x44), 0)
        self.assertIn(['instance_average', -3, -3], result['trace'])

    def test_nonzero_states_share_motion_and_direct_translation_boundaries(self):
        for state in (-0x80000000, -1, 1, 100, 0x7fffffff):
            early = self.result(state=state, tick=99)
            lift = self.result(state=state, tick=100)
            self.assertEqual(self.word(early, 'coordinate', 0x20), 3050)
            self.assertEqual(self.word(lift, 'coordinate', 0x1c), 2064)
            self.assertEqual(self.word(lift, 'coordinate', 0x20), 2936)
            self.assertNotIn('forward', self.labels(lift))
            self.assertEqual(self.word(lift, 'entity', 0x48), 0x1234ffed)

    def test_tick_250_stops_animation_and_overwrites_only_command_seven(self):
        result = self.result(state=1, tick=250, timer=10)
        self.assertEqual(self.word(result, 'entity', 0x90), 0)
        self.assertEqual(self.word(result, 'context', 28), -2)
        self.assertEqual(result['context'][32:36], bytes([0xc4]) * 4)
        self.assertEqual(self.word(result, 'coordinate', 0), 1)

    def test_idle_windows_preserve_pose_and_coordinate_validity(self):
        for tick in (251, 260, 568):
            result = self.result(state=1, tick=tick)
            self.assertEqual(self.word(result, 'coordinate', 0), 1)
            self.assertNotIn('forward', self.labels(result))
            self.assertNotIn('rotation', self.labels(result))

    def test_motion_window_ends_before_568_and_rotates_after_translation(self):
        for tick in (261, 567):
            result = self.result(state=1, tick=tick, euler=(12, 34, 56))
            self.assertEqual(self.labels(result)[-3:], ['forward', 'movement_translation', 'rotation'])
            self.assertEqual(struct.unpack_from('<3h', result['pose'], 0x10), (0, -1365, 0))
        self.assertNotIn('rotation', self.labels(self.result(state=1, tick=568)))

    def test_exit_orientation_is_absolute_and_repeated_calls_preserve_it(self):
        case = dict(self.base, state=1, tick=569, euler=(32767, -32768, 1234))
        first, _ = a.expected(case)
        self.assertEqual(struct.unpack_from('<3h', first['pose'], 0x10), (568, -1365, 341))
        second, commands = a.expected(dict(case, tick=570), first)
        self.assertEqual(second['pose'], first['pose'])
        self.assertFalse(commands)

    def test_signed_timers_issue_periodic_commands_on_negative_multiples(self):
        for timer, selected in ((-20, True), (-11, False), (-10, True), (-1, False), (10, True), (11, False)):
            result = self.result(timer=timer)
            self.assertEqual(result['context'][28:32], struct.pack('<i', 5) if selected else bytes([0xc4]) * 4)

    def test_trigger_ratio_precedes_motion_crossing_the_radius(self):
        radius = 10 << 11
        result = self.result(position=(0, 777, radius + 1), player_position=(0, 0, 0), tick=1200)
        self.assertEqual(self.word(result, 'context', 16), -1)
        self.assertEqual(self.word(result, 'coordinate', 0x20), radius - 49)
        self.assertEqual(result['trace'][0:2], [['read_trigger_ratio', a.n.ENTITY], ['trigger_ratio', 0xffffffff]])

    def test_motion_updates_keep_original_word_wrap_and_two_native_GTE_requests(self):
        result, commands = a.expected(dict(self.base, position=(0, 0, 0x7fffffff), player_position=(0, 0, 0)))
        self.assertEqual(self.word(result, 'coordinate', 0x20), -0x7fffffcf)
        self.assertEqual(len(commands), 2)
        self.assertEqual(result['motion_scratch'], bytes(8))

    def test_histories_preserve_state_pose_commands_and_rng_between_invocations(self):
        for name, sequence in a.histories(self.binding):
            previous = None
            for case in sequence:
                previous, _ = a.expected(case, previous)
            self.assertEqual(previous['rng_seed'], sequence[0]['seed'], name)
            if name.startswith('pink'):
                self.assertEqual(self.word(previous, 'entity', 0x44), 100)
                self.assertEqual(self.word(previous, 'entity', 0x90), 0)
                self.assertEqual(struct.unpack_from('<3h', previous['pose'], 0x10), (568, -1365, 341))

    def test_input_digest_covers_mood_words_and_all_initialized_bytes(self):
        self.assertNotEqual(a.input_key(self.base), a.input_key(dict(self.base, chunk_mood=(0, 0, 1, 0, 0))))
        self.assertNotEqual(a.input_key(self.base), a.input_key(dict(self.base, seed=42)))

    def test_invalid_words_missing_dream_and_division_traps_are_rejected(self):
        for changes in ({'tick': True}, {'timer': 0x80000000}, {'seed': -1}, {'has_dream': False},
                        {'chunk_mood': (0, 0, -0x80000000, 0, -1)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                a.validate_case(dict(self.base, **changes))

    def test_existing_output_is_rejected_before_loading_game_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(a.n, 'load_program') as load:
                with self.assertRaisesRegex(ValueError, 'fresh private'):
                    a.verify(Path(directory), Path('missing.exe'), 'missing runtime')
                load.assert_not_called()

    def test_nested_movement_vector_keeps_the_actual_instruction_address(self):
        pc, vector = 0x573a8, a.n.STACK - 32
        machine = a.Machine.__new__(a.Machine)
        machine.pending_returns, machine.trace = {}, []
        machine.native_entries = {pc: 'func_800573A8'}
        machine.observed = {'func_800573A8': ('translation', 2)}
        values = {4: a.n.ENTITY, 5: vector}
        cpu = SimpleNamespace(reg_read=lambda number: values.get(number, 0),
            mem_read=lambda address, size: struct.pack('<iii', 1, 2, 3) if size == 12 else bytes(size))
        machine.cpu = cpu
        registers = SimpleNamespace(UC_MIPS_REG_A0=4, UC_MIPS_REG_A1=5, UC_MIPS_REG_0=0)
        with patch.object(a.n, 'reg', registers, create=True), patch.object(a.proximity.Machine, 'hook') as parent:
            machine.hook(cpu, pc, 4, None)
            parent.assert_called_once_with(cpu, pc, 4, None)
        self.assertEqual(machine.trace, [['movement_translation', a.n.ENTITY, struct.pack('<iii', 1, 2, 3).hex()]])

    def test_SWC2_store_guard_accepts_the_last_word_and_rejects_the_next(self):
        machine = a.Machine.__new__(a.Machine)
        machine.initial = a.fixtures(self.base)
        cpu = SimpleNamespace(reg_read=lambda number: a.n.CONTEXT)
        with patch.object(a.n, 'reg', SimpleNamespace(UC_MIPS_REG_4=4), create=True):
            machine.check_store(cpu, 58 << 26 | 4 << 21 | 0x5c, 0x80000, 0x80000)
            with self.assertRaisesRegex(ValueError, 'escaped declared'):
                machine.check_store(cpu, 58 << 26 | 4 << 21 | 0x60, 0x80004, 0x80004)
        self.assertEqual(machine.rejected_store['address'], a.n.CONTEXT + 0x60)

    def test_store_guard_rejects_original_constant_data(self):
        machine = a.Machine.__new__(a.Machine)
        machine.initial = a.fixtures(self.base)
        cpu = SimpleNamespace(reg_read=lambda number: a.n.h.symbols['g_MoveUp64Back64'])
        with patch.object(a.n, 'reg', SimpleNamespace(UC_MIPS_REG_4=4), create=True):
            with self.assertRaisesRegex(ValueError, 'escaped declared'):
                machine.check_store(cpu, 43 << 26 | 4 << 21, 0x80000, 0x80000)

    def test_delay_store_based_on_a_changed_link_register_requires_review(self):
        machine = a.Machine.__new__(a.Machine)
        machine.initial = a.fixtures(self.base)
        cpu = SimpleNamespace(reg_read=lambda number: a.n.CONTEXT)
        with patch.object(a.n, 'reg', SimpleNamespace(UC_MIPS_REG_31=31), create=True):
            with self.assertRaisesRegex(ValueError, 'changed link register'):
                machine.check_store(cpu, 43 << 26 | 31 << 21, 0x80004, 0x80000, link=31)


if __name__ == '__main__':
    unittest.main()
