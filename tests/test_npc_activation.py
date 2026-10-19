import copy
import hashlib
from pathlib import Path
import struct
import unittest

from tools.record_npc_activation import ENGINE_METHODS, native_targets, prefix_settings


class ActivationTargetsTests(unittest.TestCase):
    def setUp(self):
        # Owned synthetic PS-X image. No original instructions or game data.
        image = bytearray(0x1800)
        image[:8] = b'PS-X EXE'
        struct.pack_into('<II', image, 0x18, 0x80010000, 0x1000)
        self.image = bytes(image)
        digest = hashlib.sha256(self.image).hexdigest()
        code_digest = hashlib.sha256(bytes(8)).hexdigest()
        targets, records = [], []
        for index in range(107):
            name = 'entity_fixture_' + str(index)
            pc = f'0x{0x80010000 + index * 8:08X}'
            targets.append(dict(callback=name, pc=pc, function_bytes=8, function_sha256=code_digest))
            records.append(dict(callback_function=name, callback_address=pc))
        self.catalogue = dict(canonical_executable_sha256=digest, targets=targets)
        self.audit = dict(records=records)
        methods = [dict(name=name, address=0x80010800 + index * 8, bytes=8, sha256=code_digest)
                   for index, name in enumerate(sorted(ENGINE_METHODS))]
        self.engine = dict(schema_version=1, canonical_executable_sha256=digest, methods=methods)

    def test_complete_byte_checked_target_closure_keeps_engine_methods_separate(self):
        pcs = native_targets(self.image, self.catalogue, self.engine, self.audit)
        self.assertEqual(len(pcs), 115)
        self.assertEqual(len(set(pcs)), 115)
        self.assertEqual(pcs[107:], [row['address'] for row in self.engine['methods']])

    def test_changed_tail_cannot_hide_behind_a_matching_entry_instruction(self):
        catalogue = copy.deepcopy(self.catalogue)
        catalogue['targets'][0]['function_sha256'] = hashlib.sha256(bytes(4) + b'FAIL').hexdigest()
        with self.assertRaisesRegex(ValueError, 'target span differs'):
            native_targets(self.image, catalogue, self.engine, self.audit)

    def test_wrong_binding_duplicate_pc_and_unreviewed_method_are_rejected(self):
        audit = copy.deepcopy(self.audit)
        audit['records'][0]['callback_address'] = '0x80010008'
        with self.assertRaisesRegex(ValueError, 'binding closure'):
            native_targets(self.image, self.catalogue, self.engine, audit)
        engine = copy.deepcopy(self.engine)
        engine['methods'][0]['address'] = 0x80010000
        with self.assertRaisesRegex(ValueError, 'distinct'):
            native_targets(self.image, self.catalogue, engine, self.audit)
        engine = copy.deepcopy(self.engine)
        engine['methods'][0]['name'] = 'guessed_activation'
        with self.assertRaisesRegex(ValueError, 'method identity'):
            native_targets(self.image, self.catalogue, engine, self.audit)


class ActivationPrefixTests(unittest.TestCase):
    def test_prefix_uses_only_retained_boundaries_and_preserves_input_settings(self):
        original = dict(frames=30000, checkpoint_frames=[0, 6000, 30000], arm_frame=3900,
                        watched_pc=0x8005EFF4, RAM_sample_interval=6, trace_enabled=True)
        before = copy.deepcopy(original)
        result = prefix_settings(original, Path('reference'), [0x80010000], 6000, stock=True)
        self.assertEqual(original, before)
        self.assertEqual(result['checkpoint_frames'], [0, 6000])
        self.assertEqual(result['reference_frames'], 30000)
        self.assertEqual(result['arm_frame'], 3900)
        self.assertFalse(result['trace_enabled'])
        for frames in (True, 0, 5999, 30001):
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                prefix_settings(original, Path('reference'), [], frames)


if __name__ == '__main__':
    unittest.main()
