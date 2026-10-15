"""Semantic and custody checks for additional original callback models."""
import math
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import verify_scripted_ai as scripts


class AdditionalScriptedCallbackTests(unittest.TestCase):
    def setUp(self):
        self.symbols = {name: 0x80010000 + 16 * index for index, name in enumerate((
            'g_ENTITY_VTABLE', 'g_DREAM_SYS_VTABLE', 'g_OffsetTwo', 'g_OffsetHalf',
            'g_OffsetSix', 'g_MoveDown64Then32', 'g_MoveUp64', 'g_RotateYawNegHalf',
            'func_8001EACC', 'sound_entity_stop', 'entity_fish'))}
        self.program = patch.object(scripts.native, 'h', SimpleNamespace(symbols=self.symbols), create=True)
        self.program.start()
        self.addCleanup(self.program.stop)

    def case(self, **updates):
        case = dict(timer=1, tick=1, frame=1, duration=15, state=0, variant=0,
                    action=0, seed=0, ratio=99, nudge=-19)
        case.update(updates)
        return case

    def test_bell_zero_timer_increments_before_rng_and_takes_reset_priority(self):
        result = scripts.expected('entity_bell_striker', self.case(timer=0, duration=1, state=35))
        self.assertEqual(struct.unpack_from('<i', result['entity'], 0x44)[0], 36)
        self.assertEqual(struct.unpack_from('<i', result['context'], 4)[0], 0)
        self.assertEqual(struct.unpack_from('<i', result['context'], 28)[0], 12)
        self.assertEqual(result['trace'], [
            ['trigger_ratio', scripts.native.ENTITY], ['rand', 0],
            ['notification', scripts.native.ENTITY, 11]])

    def test_bell_leaving_state_36_does_not_consume_rng(self):
        result = scripts.expected('entity_bell_striker', self.case(timer=0, state=36, seed=42))
        self.assertEqual(struct.unpack_from('<i', result['entity'], 0x44)[0], 37)
        self.assertEqual(result['rng_seed'], 42)
        self.assertEqual(result['trace'], [['trigger_ratio', scripts.native.ENTITY]])

    def test_bell_timer_resets_at_duration_minus_one(self):
        before = scripts.expected('entity_bell_striker', self.case(timer=13, duration=15))
        boundary = scripts.expected('entity_bell_striker', self.case(timer=14, duration=15))
        self.assertEqual(struct.unpack_from('<i', before['context'], 4)[0], 13)
        self.assertEqual(struct.unpack_from('<i', boundary['context'], 4)[0], -1)
        self.assertEqual(struct.unpack_from('<i', boundary['context'], 28)[0],
                         struct.unpack_from('<i', scripts.fixtures(self.case())[2], 28)[0])

    def test_bell_rng_is_checked_on_nonzero_timers_in_state_36(self):
        for seed, notification in ((0, True), (1, False), (42, False)):
            with self.subTest(seed=seed):
                result = scripts.expected('entity_bell_striker', self.case(timer=1, state=36, seed=seed))
                self.assertEqual(result['trace'][:2], [['trigger_ratio', scripts.native.ENTITY], ['rand', seed]])
                self.assertEqual(result['trace'][2:], [['notification', scripts.native.ENTITY, 11]] if notification else [])

    def test_bell_state_increment_uses_original_word_wrap(self):
        result = scripts.expected('entity_bell_striker', self.case(timer=0, state=0x7fffffff))
        self.assertEqual(struct.unpack_from('<i', result['entity'], 0x44)[0], -0x80000000)
        self.assertEqual(result['trace'], [['trigger_ratio', scripts.native.ENTITY]])

    def test_bell_duration_subtraction_wraps_before_signed_comparison(self):
        before = scripts.expected('entity_bell_striker', self.case(timer=0x7ffffffe, duration=-0x80000000))
        boundary = scripts.expected('entity_bell_striker', self.case(timer=0x7fffffff, duration=-0x80000000))
        self.assertEqual(struct.unpack_from('<i', before['context'], 4)[0], 0x7ffffffe)
        self.assertEqual(struct.unpack_from('<i', boundary['context'], 4)[0], -1)

    def test_opera_period_accepts_negative_and_zero_multiples(self):
        for timer in (-240, -120, 0, 120, 240):
            with self.subTest(timer=timer):
                case = self.case(timer=timer, ratio=-1, seed=42)
                result = scripts.expected('entity_opera_singer', case)
                self.assertEqual(result['trace'], [['trigger_ratio', scripts.native.ENTITY]])
                self.assertEqual(struct.unpack_from('<i', result['context'], 16)[0], -1)
                self.assertEqual(struct.unpack_from('<i', result['context'], 28)[0], 1)
                self.assertEqual(result['rng_seed'], 42)
                self.assertEqual(result['entity'], bytes(scripts.fixtures(case)[0]))

    def test_opera_other_timers_preserve_context_and_rng(self):
        for timer in (-0x80000000, -121, -119, -1, 1, 119, 121, 0x7fffffff):
            with self.subTest(timer=timer):
                case = self.case(timer=timer, seed=42)
                result = scripts.expected('entity_opera_singer', case)
                self.assertEqual(result['trace'], [])
                self.assertEqual(result['context'], bytes(scripts.fixtures(case)[2]))
                self.assertEqual(result['rng_seed'], 42)

    def test_bell_fixtures_include_wrap_and_all_rng_remainders(self):
        cases = scripts.cases_by_callback()['entity_bell_striker']
        self.assertEqual({case['seed'] for case in cases}, {0, 1, 2, 42, 0xffffffff})
        for timer in (0, 0x7ffffffe, 0x7fffffff, -0x80000000):
            self.assertTrue(any(case['duration'] == -0x80000000 and case['timer'] == timer for case in cases))
        self.assertTrue(any(case['state'] == 0x7fffffff and case['timer'] == 0 for case in cases))

    def test_fish_fixtures_cover_every_nonnegative_joint_period(self):
        period = math.lcm(6, 12, 64, 500)
        cases = scripts.cases_by_callback()['entity_fish']
        ticks = [case['tick'] for case in cases]
        self.assertEqual(period, 24000)
        self.assertEqual(ticks[:period], list(range(period)))
        self.assertIn(-0x80000000, ticks)
        self.assertIn(-1, ticks)
        self.assertIn(0x7fffffff, ticks)

    def test_negative_fish_tick_uses_c_remainders(self):
        result = scripts.expected('entity_fish', self.case(tick=-1))
        self.assertEqual(result['trace'], [
            ['vertical', scripts.native.ENTITY, scripts.native.u32(-64), 0],
            ['axis_c8', scripts.native.ENTITY, scripts.native.u32(-64), 0],
            ['forward', scripts.native.ENTITY, scripts.native.u32(-128), 0],
            ['translation', scripts.native.ENTITY, self.symbols['g_MoveDown64Then32']],
        ])

    def test_fish_translation_boundaries_and_forward_reversal(self):
        a = scripts.expected('entity_fish', self.case(tick=31))['trace']
        b = scripts.expected('entity_fish', self.case(tick=32))['trace']
        c = scripts.expected('entity_fish', self.case(tick=63))['trace']
        d = scripts.expected('entity_fish', self.case(tick=64))['trace']
        self.assertEqual(a[2][2], scripts.native.u32(-128))
        self.assertEqual(b[2][2], 128)
        self.assertEqual(a[-1][2], self.symbols['g_MoveDown64Then32'])
        self.assertEqual(b[-1][2], self.symbols['g_MoveUp64'])
        self.assertEqual(c[-1][2], self.symbols['g_MoveUp64'])
        self.assertEqual(len(d), 3)

    def test_airship_state_change_requires_the_zero_rng_remainder(self):
        case = self.case(tick=700, seed=0)
        result = scripts.expected('entity_airship', case)
        self.assertEqual(struct.unpack_from('<i', result['entity'], 0x44)[0], 11)
        self.assertEqual(result['trace'][0], ['rand', 0])
        self.assertEqual([call[0] for call in result['trace']], ['rand', 'rotation', 'vertical', 'forward'])
        other = scripts.expected('entity_airship', self.case(tick=700, seed=1))
        self.assertEqual(struct.unpack_from('<i', other['entity'], 0x44)[0], 0)
        self.assertEqual([call[0] for call in other['trace']], ['rand', 'forward'])

    def test_airship_link_notification_and_rotation_cutoff(self):
        result = scripts.expected('entity_airship', self.case(tick=930, state=11))
        self.assertIn(['notification', scripts.native.ENTITY, 10], result['trace'])
        cutoff = scripts.expected('entity_airship', self.case(tick=1020, state=11))
        self.assertEqual(cutoff['trace'], [['forward', scripts.native.ENTITY, scripts.native.u32(-30), 0]])

    def test_airship_blends_the_linked_child_not_the_parent(self):
        case = self.case(tick=100, seed=0)
        result = scripts.expected('entity_airship', case)
        self.assertIn(['motion_blend', scripts.CHILD, 4, 0], result['trace'])
        self.assertEqual(result['child'], bytes(scripts.child_fixture()))
        self.assertEqual(result['entity'], bytes(scripts.fixtures(case)[0]))

    def test_elephant_variants_and_giant_fish_keep_original_scale_requests(self):
        for callback, symbol, tail in (
                ('entity_elephant', 'g_OffsetTwo', ['translation', scripts.native.ENTITY, self.symbols['g_MoveDown64Then32']]),
                ('entity_elephant_small', 'g_OffsetHalf', ['forward', scripts.native.ENTITY, scripts.native.u32(-10), 0]),
                ('entity_fish_giant', 'g_OffsetSix', None)):
            with self.subTest(callback=callback):
                case = self.case()
                result = scripts.expected(callback, case)
                self.assertEqual(result['trace'][0], ['scale', scripts.native.ENTITY, 1, self.symbols[symbol]])
                self.assertEqual(result['trace'][1:], [tail] if tail else [])
                self.assertEqual(result['entity'], bytes(scripts.fixtures(case)[0]))
                self.assertEqual(result['context'], bytes(scripts.fixtures(case)[2]))

    def test_a_contract_cannot_bypass_a_claimed_native_callback(self):
        native_address = int(scripts.SCRIPT_FUNCTIONS[0]['address'], 16)
        def slot(table, offset):
            return native_address if offset == 0xC8 else 0x80020000 + offset
        with patch.object(scripts.native, 'slot', side_effect=slot):
            with self.assertRaisesRegex(ValueError, 'bypass a claimed native function'):
                scripts.Machine('entity_fish')

    def test_same_version_cannot_hide_changed_backend_library_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            library, binding = Path(folder) / 'backend.bin', Path(folder) / 'binding.py'
            library.write_bytes(b'first native backend')
            binding.write_bytes(b'first Python binding')
            module = SimpleNamespace(uclib=SimpleNamespace(_name=str(library)), __file__=str(binding))
            with patch.object(scripts.native, 'unicorn', SimpleNamespace(__version__='same-version'), create=True):
                with patch.object(scripts.importlib, 'import_module', return_value=module):
                    before = scripts.backend_identity()
                    library.write_bytes(b'changed native backend')
                    after = scripts.backend_identity()
            self.assertEqual(before['package_version'], after['package_version'])
            self.assertNotEqual(before['loaded_library_sha256'], after['loaded_library_sha256'])
            self.assertEqual(before['binding_sha256'], after['binding_sha256'])

    def test_changed_python_binding_is_distinct_from_unchanged_native_library(self):
        with tempfile.TemporaryDirectory() as folder:
            library, binding = Path(folder) / 'backend.bin', Path(folder) / 'binding.py'
            library.write_bytes(b'same native backend')
            binding.write_bytes(b'first binding')
            module = SimpleNamespace(uclib=SimpleNamespace(_name=str(library)), __file__=str(binding))
            with patch.object(scripts.native, 'unicorn', SimpleNamespace(__version__='same-version'), create=True):
                with patch.object(scripts.importlib, 'import_module', return_value=module):
                    before = scripts.backend_identity()
                    binding.write_bytes(b'changed binding')
                    after = scripts.backend_identity()
            self.assertEqual(before['loaded_library_sha256'], after['loaded_library_sha256'])
            self.assertNotEqual(before['binding_sha256'], after['binding_sha256'])


if __name__ == '__main__':
    unittest.main()
