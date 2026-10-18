"""Constructed selection controls for complete ordinal partitions of a route."""
import copy
import struct
import unittest

from tests.test_collision_calls import fixture
from tools import inspect_collision_calls as tool
from tools.collision_calls import FIELDS, selection


class CollisionOrdinalTests(unittest.TestCase):
    def setUp(self):
        self.row, self.before, self.after, self.summary, entries, self.program, self.image = fixture()
        self.entries = [dict(entries[0], relative_frame=frame) for frame in (3, 4, 5)]
        self.row['base_ordinal'] = 3
        self.program['method_trace']['collision_calls'] = dict(max_samples=64, ordinal_first=3, ordinal_step=3)
        self.summary.update(protocol=2, settings=selection(self.program), eligible_entries=3, ordinal_skips=2)

    def verify(self):
        data = struct.pack('<247I', *(self.row[name] for name in FIELDS))
        return tool.validate_records(data, self.before + self.after, self.summary,
                                     self.entries, self.program, self.image)

    def test_ordinal_selection_reaches_a_third_invocation_of_the_same_key(self):
        report = self.verify()
        self.assertEqual(report['completed_samples'], 1)
        self.assertEqual(report['policy']['ordinal_skips'], 2)
        self.assertEqual(report['policy']['duplicate_key_skips'], 0)
        self.assertEqual(report['calls'][0]['base_ordinal'], 3)
        self.assertEqual(report['calls'][0]['result'], 1)
        self.assertFalse(report['complete_state_parity_checked'])

    def test_wrong_phase_cannot_claim_a_later_record(self):
        self.program['method_trace']['collision_calls']['ordinal_first'] = 1
        self.summary['settings'] = selection(self.program)
        with self.assertRaisesRegex(ValueError, 'required'):
            self.verify()

    def test_ordinal_skip_count_is_checked_against_every_original_entry(self):
        self.summary['ordinal_skips'] = 1
        with self.assertRaisesRegex(ValueError, 'counters disagree'):
            self.verify()

    def test_absent_boolean_or_negative_ordinal_counters_are_rejected(self):
        for value in (None, True, -1):
            with self.subTest(value=value):
                self.summary['ordinal_skips'] = value
                with self.assertRaisesRegex(ValueError, 'non-integer'):
                    self.verify()

    def test_selection_and_summary_protocol_must_agree(self):
        self.summary['protocol'] = 1
        with self.assertRaisesRegex(ValueError, 'Unqualified'):
            self.verify()

    def test_ordinal_configuration_rejects_mixed_policies_and_invalid_integers(self):
        good = copy.deepcopy(self.program)
        for first, step in ((0, 3), (4, 3), (1, 65), (True, 3), (1, False), (1, '3')):
            with self.subTest(first=first, step=step):
                self.program = copy.deepcopy(good)
                self.program['method_trace']['collision_calls'].update(ordinal_first=first, ordinal_step=step)
                with self.assertRaisesRegex(ValueError, 'Ordinal selection'):
                    selection(self.program)
        self.program = good
        self.program['method_trace']['collision_calls']['per_key'] = 2
        with self.assertRaisesRegex(ValueError, 'Ordinal selection'):
            selection(self.program)

    def test_legacy_recordings_keep_their_original_protocol_and_policy(self):
        row, before, after, summary, entries, program, image = fixture()
        data = struct.pack('<247I', *(row[name] for name in FIELDS))
        result = tool.validate_records(data, before + after, summary, entries, program, image)
        self.assertNotIn('ordinal_skips', result['policy'])
        summary['ordinal_skips'] = 0
        tool.validate_records(data, before + after, summary, entries, program, image)
        summary['ordinal_skips'] = 1
        with self.assertRaisesRegex(ValueError, 'Legacy'):
            tool.validate_records(data, before + after, summary, entries, program, image)

    def test_ordinal_mode_retains_transport_overflow_and_pending_call_guards(self):
        for field in ('native_overflow', 'pending_calls', 'nested_skips'):
            self.summary[field] = 1
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'Unqualified'):
                self.verify()
            self.summary[field] = 0


if __name__ == '__main__':
    unittest.main()
