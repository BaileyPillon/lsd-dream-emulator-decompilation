"""Owned RAM graphs distinguish disabled, detached and reused object storage."""
from pathlib import Path
import struct
import tempfile
import unittest

from tools import inspect_npc_lifetime as lifetime


class NpcLifetimeTests(unittest.TestCase):
    def setUp(self):
        self.raw = bytearray(0x200000)
        self.executable = bytearray(0x800 + 0x7B000)
        self.executable[:8] = b'PS-X EXE'
        struct.pack_into('<II', self.executable, 0x18, 0x80010000, 0x7B000)
        payload = (bytes(range(256)) * (0x7B000 // 256))
        self.executable[0x800:] = payload
        self.raw[0x10000:0x8B000] = payload
        self.flow, self.dream, self.entity = 0x80010000, 0x80010400, 0x80011000
        for address in (self.flow, self.dream, self.entity):
            self.raw[address & 0x1FFFFFFF:(address & 0x1FFFFFFF) + 0x108] = bytes(0x108)
        self.put(0x8008AC20, self.flow)
        self.put(self.flow, 0x8006D3C8)
        self.put(self.flow + 0x28, self.dream)
        self.put(self.dream, 0x80087BDC)
        self.put(self.dream + 4, 0x80012000)
        self.put(0x80012000, 0)
        self.put(0x80012004, self.entity)
        self.put(0x80012010, 0)
        self.put(0x80012014, self.dream)
        self.put(self.entity, 0x80089AD4)
        self.put(self.entity + 8, 0x80012010)
        self.put(self.entity + 0x94, self.dream)
        self.raw[0x110A0:0x110F0] = b'\xDD' * 0x50
        self.audit = dict(table=dict(address='0x80089200', bytes=32), records=[
            dict(callback_function='entity_example', callback_address='0x80050100'),
            dict(callback_function='entity_other', callback_address='0x80050200')])

    def put(self, address, value):
        struct.pack_into('<I', self.raw, address & 0x1FFFFFFF, value)

    def inspect(self):
        return lifetime.inspect_checkpoint(self.raw, self.executable, self.audit, self.entity, 0)

    def enable(self):
        self.put(self.entity + 0x9C, 1)
        self.put(self.entity + 0xA0, 7)
        self.put(self.entity + 0xA4, self.entity)
        self.put(self.entity + 0xA8, 0x80050100)
        self.put(self.entity + 0xF8, 1)

    def test_disabled_payload_is_uninterpreted_and_inputs_are_unchanged(self):
        before = bytes(self.raw), bytes(self.executable)
        report = self.inspect()
        self.assertEqual(report['state'], 'disabled')
        self.assertIsNone(report['target']['registered_context'])
        self.assertEqual((self.raw, self.executable), before)

    def test_negative_native_state_is_disabled(self):
        self.put(self.entity + 0x9C, 0xFFFFFFFF)
        self.assertEqual(self.inspect()['state'], 'disabled')

    def test_enabled_context_has_its_original_owner_and_binding(self):
        self.enable()
        report = self.inspect()
        self.assertEqual(report['state'], 'enabled')
        self.assertTrue(report['target']['registered_context']['matches_original_binding'])

    def test_nonzero_entity_id_uses_its_own_state_and_callback(self):
        self.enable()
        self.put(self.entity + 0x98, 1)
        self.put(self.entity + 0x9C, 2)
        self.put(self.entity + 0xA8, 0x80050200)
        report = lifetime.inspect_checkpoint(self.raw, self.executable, self.audit, self.entity, 1)
        self.assertEqual(report['state'], 'enabled')
        self.assertTrue(report['target']['registered_context']['matches_original_binding'])

    def test_wrong_context_owner_is_rejected(self):
        self.enable()
        self.put(self.entity + 0xA4, self.dream)
        with self.assertRaisesRegex(ValueError, 'different entity owner'):
            self.inspect()

    def test_wrong_context_id_is_rejected(self):
        self.enable()
        self.put(self.entity + 0x9C, 2)
        with self.assertRaisesRegex(ValueError, 'different entity ID'):
            self.inspect()

    def test_unreachable_former_storage_is_never_interpreted(self):
        self.put(self.dream + 4, 0)
        self.raw[0x11000:0x11108] = b'\xFF' * 0x108
        report = self.inspect()
        self.assertEqual(report['state'], 'not_reachable')
        self.assertIsNone(report['target'])

    def test_another_entity_at_the_old_address_is_distinct(self):
        self.put(self.entity + 0x98, 1)
        report = self.inspect()
        self.assertEqual(report['state'], 'different_object_at_address')
        self.assertIsNone(report['target'])

    def test_another_object_at_the_old_address_is_distinct(self):
        self.put(self.entity, 0x80089000)
        self.put(self.entity + 0x98, 0xFFFFFFFF)
        self.assertEqual(self.inspect()['state'], 'different_object_at_address')

    def test_bad_global_root_pointer_is_rejected(self):
        for value in (0, 0x80010001, 0x80200000):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'Invalid native pointer'):
                self.put(0x8008AC20, value)
                self.inspect()

    def test_wrong_root_type_is_rejected(self):
        self.put(self.flow, 0x80089000)
        with self.assertRaisesRegex(ValueError, 'game-flow type'):
            self.inspect()

    def test_wrong_dream_owner_type_is_rejected(self):
        self.put(self.dream, 0x80089000)
        with self.assertRaisesRegex(ValueError, 'dream-system type'):
            self.inspect()

    def test_nonreciprocal_edge_is_rejected(self):
        self.put(self.entity + 8, 0)
        with self.assertRaisesRegex(ValueError, 'reciprocal parent'):
            self.inspect()

    def test_changed_original_property_table_is_rejected(self):
        self.raw[0x89200] ^= 1
        with self.assertRaisesRegex(ValueError, 'property table'):
            self.inspect()

    def test_transition_windows_keep_sampled_and_consecutive_boundaries_distinct(self):
        rows = [dict(relative_frame=frame, state=state) for frame, state in
                ((10, 'enabled'), (20, 'disabled'), (21, 'not_reachable'))]
        windows = lifetime.transition_windows(rows)
        self.assertEqual((windows[0]['after_relative_frame'], windows[0]['through_relative_frame']), (10, 20))
        self.assertFalse(windows[0]['consecutive_core_advances'])
        self.assertTrue(windows[1]['consecutive_core_advances'])

    def test_repeated_or_reordered_checkpoint_boundaries_are_rejected(self):
        for frames in ((1, 1), (2, 1), (-1, 1), (True, 2)):
            with self.subTest(frames=frames), self.assertRaisesRegex(ValueError, 'unique and increasing'):
                lifetime.transition_windows([dict(relative_frame=frame, state='disabled') for frame in frames])

    def test_cli_preserves_an_existing_report(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'report.json'
            path.write_text('retained evidence', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'new report path'):
                lifetime.main(['--recording', folder, '--output', str(path)])
            self.assertEqual(path.read_text(encoding='utf-8'), 'retained evidence')


if __name__ == '__main__':
    unittest.main()
