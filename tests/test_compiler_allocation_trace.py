import copy
from pathlib import Path
import tempfile
import unittest

from research.compiler import trace_allocation as trace


class AllocationQualificationTests(unittest.TestCase):
    def setUp(self):
        self.normal = b'leaf:\n\tjr $31\n'
        self.dump = ';; Function leaf\n;; Register dispositions:\n71 in 4 72 in 5\n;; Hard regs used: 4 5\n'
        item = {'allocno': 0, 'pseudo': 72, 'references': 2, 'live_length': 2,
                'size': 1, 'hard_register_after': 5, 'alternate_class': 0, 'retrying': 0}
        left, right = dict(item), dict(item, allocno=1)
        self.observation = {'target': 'leaf', 'compiler_exited': True, 'compiler_exit_code': 0,
            'normal_debugger_breakpoint_machinery': True,
            'explicit_inferior_memory_writes_or_opcode_substitutions': False,
            'extra_inferior_functions_invoked': False,
            'local_events': [{'before': {}, 'after': {'71': {'hard_register': 4}}}],
            'equivalence_events': [{'before': {}, 'after': {}}],
            'allocation_events': [item],
            'comparison_events': [{'left': left, 'right': right, 'returned_comparison': -1}]}

    def qualify(self, observation=None, normal=None, observed=None, diagnostic=None, dump=None):
        return trace.validate_observation(observation or self.observation,
            self.normal if normal is None else normal,
            self.normal if observed is None else observed,
            self.normal if diagnostic is None else diagnostic,
            self.dump if dump is None else dump, 'leaf')

    def test_option_comments_do_not_hide_instruction_changes(self):
        self.qualify(diagnostic=b'# -da\n' + self.normal)
        with self.assertRaisesRegex(ValueError, 'instructions'):
            self.qualify(diagnostic=b'# -da\nleaf:\n\tnop\n')

    def test_observation_must_preserve_complete_assembly(self):
        with self.assertRaisesRegex(ValueError, 'complete compiler assembly'):
            self.qualify(observed=self.normal + b'\tnop\n')

    def test_incomplete_or_missing_local_observation_is_rejected(self):
        for events in ([], [{'before': {}}]):
            bad = copy.deepcopy(self.observation)
            bad['local_events'] = events
            with self.subTest(events=events), self.assertRaisesRegex(ValueError, 'incomplete local'):
                self.qualify(bad)

    def test_unfinished_global_allocation_is_rejected(self):
        bad = copy.deepcopy(self.observation)
        del bad['allocation_events'][0]['hard_register_after']
        with self.assertRaisesRegex(ValueError, 'never returned'):
            self.qualify(bad)

    def test_wrong_function_or_exit_is_rejected(self):
        for key, value in (('target', 'other'), ('compiler_exited', False), ('compiler_exit_code', 1)):
            bad = copy.deepcopy(self.observation)
            bad[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'finish successfully'):
                self.qualify(bad)

    def test_extra_inferior_execution_or_mutation_is_rejected(self):
        for key in ('extra_inferior_functions_invoked', 'explicit_inferior_memory_writes_or_opcode_substitutions'):
            bad = copy.deepcopy(self.observation)
            bad[key] = True
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'mutation or invocation'):
                self.qualify(bad)

    def test_local_and_global_disposition_changes_are_rejected(self):
        for path in ('local', 'global'):
            bad = copy.deepcopy(self.observation)
            if path == 'local':
                bad['local_events'][0]['after']['71']['hard_register'] = 6
            else:
                bad['allocation_events'][0]['hard_register_after'] = 6
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'disagrees'):
                self.qualify(bad)

    def test_reference_priority_and_tie_break_are_checked(self):
        good = self.qualify()
        self.assertEqual(good['priority_comparisons'], 1)
        bad = copy.deepcopy(self.observation)
        bad['comparison_events'][0]['returned_comparison'] = 1
        with self.assertRaisesRegex(ValueError, 'reference priority'):
            self.qualify(bad)
        self.assertEqual(trace.allocation_priority({'references': 2, 'live_length': 33, 'size': 1}), 606)
        with self.assertRaisesRegex(ValueError, 'operands'):
            trace.allocation_priority({'references': 0, 'live_length': 33, 'size': 1})

    def test_duplicate_and_missing_function_dumps_are_rejected(self):
        for dump in (self.dump + self.dump, self.dump.replace('leaf', 'other')):
            with self.subTest(dump=dump), self.assertRaisesRegex(ValueError, 'exactly once'):
                self.qualify(dump=dump)

    def test_zero_global_events_are_reported_explicitly(self):
        observation = copy.deepcopy(self.observation)
        observation['allocation_events'] = []
        observation['comparison_events'] = []
        report = self.qualify(observation)
        self.assertEqual((report['global_allocations'], report['priority_comparisons']), (0, 0))

    def test_spilled_register_is_omitted_but_an_assigned_register_cannot_be(self):
        observation = copy.deepcopy(self.observation)
        observation['allocation_events'][0]['hard_register_after'] = -1
        no_assignment = self.dump.replace(' 72 in 5', '')
        self.qualify(observation, dump=no_assignment)
        with self.assertRaisesRegex(ValueError, 'Global allocation disagrees'):
            self.qualify(dump=no_assignment)
        with self.assertRaisesRegex(ValueError, 'Global allocation disagrees'):
            self.qualify(observation)


class AllocationCustodyTests(unittest.TestCase):
    def test_compiler_identity_must_match_before_decoding(self):
        with tempfile.TemporaryDirectory() as directory:
            compiler = Path(directory) / 'different-compiler'
            compiler.write_bytes(b'unsupported compiler identity')
            with self.assertRaisesRegex(ValueError, 'Unsupported compiler'):
                trace.require_compiler(compiler)

    def test_output_must_be_fresh_and_inside_private_lab(self):
        with tempfile.TemporaryDirectory() as directory:
            lab = Path(directory) / '.decomp-lab'
            lab.mkdir()
            existing = lab / 'existing'
            existing.mkdir()
            evidence = existing / 'retained.json'
            evidence.write_bytes(b'original evidence')
            with self.assertRaises(FileExistsError):
                trace.require_output(existing, lab)
            self.assertEqual(evidence.read_bytes(), b'original evidence')
            for output in (lab, lab.parent / 'outside'):
                with self.subTest(output=output), self.assertRaises(ValueError):
                    trace.require_output(output, lab)
            self.assertEqual(trace.require_output(lab / 'fresh', lab), (lab / 'fresh').resolve())


if __name__ == '__main__':
    unittest.main()
