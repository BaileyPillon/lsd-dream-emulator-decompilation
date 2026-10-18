"""Interleaved original contexts require separate clocks and complete ownership."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests import test_npc_entry_trace as fixtures
from tools import compare_npc_history as comparison
from tools.record_npc_history import STOCK_RUNTIME, validate_program


class MultiInstanceHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.program, self.executable = fixtures.fixture_program()
        self.owners = (0x80011000, 0x80011200)
        self.program['trace']['expected_entries'] = 4
        self.program['trace']['expected_instances'] = [dict(
            entity_address=f'0x{owner:08X}', expected_entries=2,
            expected_first_frame=1, expected_last_frame=3) for owner in self.owners]
        hashes = {name: fixtures.digest(name.encode()) for name in STOCK_RUNTIME}
        patch = mock.patch('tools.compare_npc_history.STOCK_RUNTIME', hashes)
        patch.start()
        self.addCleanup(patch.stop)
        self.left, self.right = self.root / 'original', self.root / 'rebuilt'
        self.entries = fixtures.fixture_run(self.left, self.program, self.executable, owners=self.owners)
        fixtures.fixture_run(self.right, self.program, self.executable, owners=self.owners)

    def validate(self, rows, program=None, frames=3):
        return comparison.validate_entries(rows, self.program if program is None else program, frames, self.executable)

    def test_interleaved_instances_have_independent_clocks_and_complete_outputs(self):
        exe = self.root / 'owned.exe'
        exe.write_bytes(self.executable)
        report = comparison.compare(self.left, self.right, exe)
        self.assertEqual(report['status'], 'passed_NPC_history_output_comparison')
        self.assertEqual(report['original_entities_per_run'], [2, 2])
        self.assertEqual(report['original_instruction_entries_per_run'], [4, 4])
        self.assertEqual(report['original_clock_checkpoint_checks'], [2, 2])
        self.assertEqual(report['original_clock_checks_by_entity'][0],
                         {'0x80011000': 1, '0x80011200': 1})

    def test_existing_single_instance_profiles_do_not_implicitly_accept_multiple_owners(self):
        program = copy.deepcopy(self.program)
        del program['trace']['expected_instances']
        with self.assertRaisesRegex(ValueError, 'single original entity'):
            self.validate(self.entries, program)

    def test_an_undeclared_instance_is_rejected(self):
        rows = copy.deepcopy(self.entries)
        rows[-1]['entity'] = '80011400'
        with self.assertRaisesRegex(ValueError, 'undeclared'):
            self.validate(rows)

    def test_missing_instance_entries_are_rejected(self):
        rows = [row for row in self.entries if row['entity'] == '80011000']
        with self.assertRaises(ValueError):
            self.validate(rows)

    def test_second_instance_tick_fault_is_rejected(self):
        rows = copy.deepcopy(self.entries)
        rows[-1]['context_tick'] = 7
        with self.assertRaisesRegex(ValueError, 'instance.*ticks'):
            self.validate(rows)

    def test_a_repeated_tick_in_one_instance_is_rejected(self):
        rows = copy.deepcopy(self.entries)
        rows[-1]['context_tick'] = 0
        with self.assertRaisesRegex(ValueError, 'instance.*ticks'):
            self.validate(rows)

    def test_each_instance_requires_its_declared_first_boundary(self):
        rows = copy.deepcopy(self.entries)
        rows[1]['relative_frame'] = 2
        with self.assertRaisesRegex(ValueError, 'incorrect first entry'):
            self.validate(rows)

    def test_a_prefix_before_a_later_instance_does_not_require_that_future_instance(self):
        program = copy.deepcopy(self.program)
        program['trace']['expected_instances'][1]['expected_first_frame'] = 2
        self.assertEqual(len(self.validate([self.entries[0]], program, frames=1)), 1)

    def test_a_prefix_cannot_omit_an_instance_whose_first_entry_is_already_due(self):
        with self.assertRaisesRegex(ValueError, 'missing or incorrect first entry'):
            self.validate([self.entries[0]], frames=2)

    def test_a_prefix_cannot_exceed_an_instances_complete_entry_count(self):
        rows = copy.deepcopy(self.entries[:2])
        for tick in (1, 2):
            row = copy.deepcopy(self.entries[2])
            row.update(relative_frame=2, context_tick=tick, timestamp=9 + tick)
            rows.append(row)
        with self.assertRaisesRegex(ValueError, 'prefix exceeds'):
            self.validate(rows, frames=2)

    def test_a_prefix_cannot_finish_an_instance_before_its_declared_last_entry(self):
        rows = copy.deepcopy(self.entries[:3])
        rows[-1]['relative_frame'] = 2
        with self.assertRaisesRegex(ValueError, 'completes before'):
            self.validate(rows, frames=2)

    def test_a_clock_guard_cannot_hide_a_missing_second_context(self):
        with self.assertRaisesRegex(ValueError, 'every observed instance'):
            comparison.inspect_run(self.left, self.executable,
                context_clock_guard=lambda raw, address, entity_id, frame: address == self.owners[0])

    def test_a_second_instance_clock_fault_cannot_hide_behind_the_first_clock(self):
        folder = self.root / 'bad-second-clock'
        fixtures.fixture_run(folder, self.program, self.executable, owners=self.owners,
                             clock_offsets={self.owners[1]: 1})
        with self.assertRaisesRegex(ValueError, 'initialized tick history'):
            comparison.inspect_run(folder, self.executable)

    def test_malformed_per_instance_metadata_is_rejected(self):
        for mutate in (
            lambda rows: rows.append(copy.deepcopy(rows[0])),
            lambda rows: rows[0].update(entity_address='0x80011001'),
            lambda rows: rows[0].update(entity_address='0x80200000'),
            lambda rows: rows[0].update(entity_address='80011000'),
            lambda rows: rows[0].update(expected_entries=0),
            lambda rows: rows[0].update(expected_entries=True),
            lambda rows: rows[0].update(expected_first_frame=3, expected_last_frame=1),
            lambda rows: rows[0].update(expected_first_frame=0),
            lambda rows: rows[0].update(extra_field=1),
            lambda rows: rows.clear(),
        ):
            program = copy.deepcopy(self.program)
            mutate(program['trace']['expected_instances'])
            with self.subTest(instances=program['trace']['expected_instances']), self.assertRaises(ValueError):
                validate_program(program)


if __name__ == '__main__':
    unittest.main()
