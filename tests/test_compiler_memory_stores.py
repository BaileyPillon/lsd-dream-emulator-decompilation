"""Guard qualification of compiler observations without original game inputs."""
from pathlib import Path
import tempfile
import unittest

from research.compiler import trace_memory_stores as stores


class CompilerMemoryStoresTests(unittest.TestCase):
    def valid_trace(self):
        reg = {'code': 'reg', 'number': 30}
        mem = {'code': 'mem', 'address': reg}
        return {'target': 'test_leaf', 'compiler_exited': True, 'compiler_exit_code': 0,
                'compiler_sha256': stores.COMPILER_SHA256,
                'normal_debugger_breakpoint_machinery': True,
                'explicit_inferior_memory_writes_or_opcode_substitutions': False,
                'extra_inferior_functions_invoked': False,
                'decisions': [{'sequence': 0, 'pattern': {'code': 'set', 'left': mem},
                               'last_mem_set_before': mem, 'last_mem_set_after': mem,
                               'returned_dead': 1,
                               'equality_calls': [{'left': mem, 'right': mem, 'returned_equal': 1}]}]}

    def test_complete_observation_counts_actual_returns(self):
        result = stores.validate_observation(self.valid_trace(), b'assembly', b'assembly', 'test_leaf')
        self.assertEqual((result['memory_store_decisions'], result['address_equality_calls'], result['dead_decisions']), (1, 1, 1))

    def test_changed_complete_assembly_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'changed complete'):
            stores.validate_observation(self.valid_trace(), b'normal', b'changed', 'test_leaf')

    def test_missing_or_unfinished_returns_are_rejected(self):
        examples = [self.valid_trace() for _ in range(4)]
        examples[0]['decisions'] = []
        del examples[1]['decisions'][0]['returned_dead']
        del examples[2]['decisions'][0]['equality_calls'][0]['returned_equal']
        examples[3]['decisions'][0]['returned_dead'] = False
        for trace in examples:
            with self.subTest(trace=trace), self.assertRaises(ValueError):
                stores.validate_observation(trace, b's', b's', 'test_leaf')

    def test_observer_mutation_or_wrong_target_is_rejected(self):
        for key, value in [('target', 'other'), ('compiler_exited', False), ('compiler_exit_code', 1),
                           ('compiler_sha256', 'unsupported'),
                           ('extra_inferior_functions_invoked', True),
                           ('explicit_inferior_memory_writes_or_opcode_substitutions', True)]:
            trace = self.valid_trace()
            trace[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                stores.validate_observation(trace, b's', b's', 'test_leaf')

    def test_existing_or_nonprivate_evidence_is_preserved(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            lab = root / '.decomp-lab'
            lab.mkdir()
            existing = lab / 'retained'
            existing.mkdir()
            note = existing / 'note'
            note.write_bytes(b'keep this evidence')
            with self.assertRaises(FileExistsError):
                stores.require_output(existing, lab)
            with self.assertRaises(ValueError):
                stores.require_output(root / 'public', lab)
            self.assertEqual(note.read_bytes(), b'keep this evidence')

    def test_unsupported_compiler_is_rejected_before_observation(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / 'compiler'
            path.write_bytes(b'unsupported compiler')
            with self.assertRaisesRegex(ValueError, 'Unsupported compiler'):
                stores.require_compiler(path)


if __name__ == '__main__':
    unittest.main()
