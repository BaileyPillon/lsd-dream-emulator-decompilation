"""Reject incomplete or inconsistent compiler observations using synthetic data."""
import copy
from pathlib import Path
import tempfile
import unittest

from research.compiler import trace_inline_calls as inline

ASSEMBLY = b'\t.ent test_leaf\n test_leaf:\n\t.end test_leaf\n'


class CompilerInlineCallsTests(unittest.TestCase):
    def type_node(self, pointer='0x1000', uid=224, mode='BLK'):
        return dict(pointer=pointer, main_variant='0x1000', code='record_type', mode=mode,
                    uid=uid, alignment=32, readonly=False, volatile=False)

    def valid_trace(self, rejected=True):
        formal = self.type_node()
        actual = self.type_node('0x1004', 225) if rejected else self.type_node()
        arg = dict(name='value', formal_node='0x2000', formal_type=formal,
                   promoted_type=copy.deepcopy(formal), actual_type=actual,
                   same_type_identity=not rejected)
        gates = [dict(gate='argument_mode_or_BLK_type_identity', formal_node='0x2000',
                      formal_type=copy.deepcopy(formal), promoted_type=copy.deepcopy(formal),
                      actual_type=copy.deepcopy(actual), reason='BLK_type_identity_mismatch')] if rejected else []
        return dict(schema_version=1, compiler_sha256=inline.COMPILER_SHA256,
                    target='test_leaf', helper='sum_pair', compiler_exited=True,
                    compiler_exit_code=0, call_stack_balanced=True,
                    normal_debugger_breakpoint_machinery=True,
                    explicit_inferior_memory_writes_or_opcode_substitutions=False,
                    extra_inferior_functions_invoked=False,
                    events=[dict(sequence=0, caller='test_leaf', function='sum_pair',
                                 completed=True, return_value='0xffffffff' if rejected else '0x0',
                                 arguments=[arg], rejections=gates)])

    def validate(self, trace):
        return inline.validate_observation(trace, ASSEMBLY, ASSEMBLY, 'test_leaf', 'sum_pair')

    def test_actual_rejection_and_inline_returns_are_distinct(self):
        rejected = self.validate(self.valid_trace())
        accepted = self.validate(self.valid_trace(False))
        self.assertEqual((rejected['inline_calls'], rejected['not_inlined_calls'],
                          rejected['argument_gate_rejections']), (1, 1, 1))
        self.assertEqual((accepted['inlined_calls'], accepted['not_inlined_calls']), (1, 0))

    def test_nonvoid_rtl_return_counts_as_inlined(self):
        trace = self.valid_trace(False)
        trace['events'][0]['return_value'] = '0x5000'
        self.assertEqual(self.validate(trace)['inlined_calls'], 1)

    def test_unobserved_rejection_cause_stays_unclassified(self):
        trace = self.valid_trace()
        trace['events'][0]['rejections'] = []
        result = self.validate(trace)
        self.assertEqual(result['argument_gate_rejections'], 0)
        self.assertEqual(result['not_inlined_without_observed_argument_gate'], 1)

    def test_mode_difference_is_separate_from_block_identity(self):
        trace = self.valid_trace()
        arg = trace['events'][0]['arguments'][0]
        arg['actual_type']['mode'] = 'SI'
        gate = trace['events'][0]['rejections'][0]
        gate['actual_type'] = copy.deepcopy(arg['actual_type'])
        gate['reason'] = 'argument_mode_mismatch'
        self.assertEqual(self.validate(trace)['argument_gate_rejections'], 1)

    def test_same_main_variant_does_not_hide_distinct_block_nodes(self):
        trace = self.valid_trace()
        arg = trace['events'][0]['arguments'][0]
        self.assertEqual(arg['formal_type']['main_variant'], arg['actual_type']['main_variant'])
        self.assertEqual(self.validate(trace)['not_inlined_calls'], 1)

    def test_changed_complete_assembly_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'changed complete'):
            inline.validate_observation(self.valid_trace(), ASSEMBLY, ASSEMBLY + b'changed',
                                        'test_leaf', 'sum_pair')

    def test_absent_or_duplicate_selected_function_is_rejected(self):
        for assembly in (b'\t.ent other\n', ASSEMBLY + ASSEMBLY):
            with self.subTest(assembly=assembly), self.assertRaisesRegex(ValueError, 'emitted exactly once'):
                inline.validate_observation(self.valid_trace(), assembly, assembly, 'test_leaf', 'sum_pair')

    def test_wrong_target_helper_or_compiler_is_rejected(self):
        for key, value in [('target', 'other'), ('helper', 'other'), ('compiler_sha256', 'unsupported'),
                           ('schema_version', True), ('compiler_exited', False),
                           ('compiler_exit_code', False), ('compiler_exit_code', 1),
                           ('call_stack_balanced', False)]:
            trace = self.valid_trace()
            trace[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.validate(trace)

    def test_observer_mutations_or_extra_calls_are_rejected(self):
        for key, value in [('normal_debugger_breakpoint_machinery', False),
                           ('explicit_inferior_memory_writes_or_opcode_substitutions', True),
                           ('extra_inferior_functions_invoked', True)]:
            trace = self.valid_trace()
            trace[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(trace)

    def test_empty_unfinished_and_out_of_order_calls_are_rejected(self):
        examples = [self.valid_trace() for _ in range(6)]
        examples[0]['events'] = []
        examples[1]['events'][0]['completed'] = False
        examples[2]['events'][0]['sequence'] = True
        examples[3]['events'][0]['sequence'] = 1
        examples[4]['events'][0]['caller'] = 'other'
        examples[5]['events'][0]['function'] = 'other'
        for trace in examples:
            with self.subTest(trace=trace), self.assertRaises(ValueError):
                self.validate(trace)

    def test_return_values_require_a_complete_unsigned_word(self):
        for value in (None, 0, True, '-1', '0x100000000'):
            trace = self.valid_trace()
            trace['events'][0]['return_value'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.validate(trace)

    def test_missing_actual_is_only_consistent_with_failure(self):
        trace = self.valid_trace()
        arg = trace['events'][0]['arguments'][0]
        arg['missing_actual'] = True
        del arg['actual_type']
        trace['events'][0]['rejections'] = []
        self.assertEqual(self.validate(trace)['not_inlined_without_observed_argument_gate'], 1)
        trace['events'][0]['return_value'] = '0x0'
        with self.assertRaisesRegex(ValueError, 'missing actual'):
            self.validate(trace)

    def test_duplicate_or_unknown_formal_nodes_are_rejected(self):
        trace = self.valid_trace()
        trace['events'][0]['arguments'].append(copy.deepcopy(trace['events'][0]['arguments'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.validate(trace)
        trace = self.valid_trace()
        trace['events'][0]['rejections'][0]['formal_node'] = '0x3000'
        with self.assertRaisesRegex(ValueError, 'observed argument'):
            self.validate(trace)

    def test_type_identity_claim_is_checked_against_addresses(self):
        trace = self.valid_trace()
        trace['events'][0]['arguments'][0]['same_type_identity'] = True
        with self.assertRaisesRegex(ValueError, 'type identity'):
            self.validate(trace)

    def test_gate_types_must_match_entry_observation(self):
        trace = self.valid_trace()
        trace['events'][0]['rejections'][0]['actual_type']['uid'] += 1
        with self.assertRaisesRegex(ValueError, 'types differ'):
            self.validate(trace)

    def test_repeated_rejection_gate_cannot_inflate_call_counts(self):
        trace = self.valid_trace()
        trace['events'][0]['rejections'] *= 2
        with self.assertRaisesRegex(ValueError, 'Incomplete selected inline call'):
            self.validate(trace)

    def test_captured_gate_must_have_matching_failure_and_reason(self):
        examples = [self.valid_trace() for _ in range(3)]
        examples[0]['events'][0]['return_value'] = '0x0'
        examples[1]['events'][0]['rejections'][0]['reason'] = 'argument_mode_mismatch'
        examples[2]['events'][0]['rejections'][0]['gate'] = 'unknown'
        for trace in examples:
            with self.subTest(trace=trace), self.assertRaises(ValueError):
                self.validate(trace)

    def test_invalid_type_layouts_are_rejected(self):
        for key, value in [('pointer', '0x0'), ('main_variant', '0x100000000'), ('uid', False),
                           ('alignment', -1), ('readonly', 0), ('mode', '')]:
            trace = self.valid_trace()
            trace['events'][0]['arguments'][0]['actual_type'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(trace)

    def test_optional_helper_filter_keeps_call_ownership(self):
        trace = self.valid_trace()
        trace['helper'] = None
        result = inline.validate_observation(trace, ASSEMBLY, ASSEMBLY, 'test_leaf')
        self.assertEqual(result['inline_calls'], 1)

    def test_unsupported_compiler_is_rejected_without_running_it(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / 'compiler'
            path.write_bytes(b'unsupported compiler')
            with self.assertRaisesRegex(ValueError, 'Unsupported compiler'):
                inline.require_compiler(path)

    def test_existing_or_public_evidence_is_preserved(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            lab = root / '.decomp-lab'
            lab.mkdir()
            retained = lab / 'retained'
            retained.mkdir()
            note = retained / 'note'
            note.write_bytes(b'preserve')
            with self.assertRaises(FileExistsError):
                inline.require_output(retained, lab)
            for path in (lab, root / 'public', lab.parent / 'sibling'):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    inline.require_output(path, lab)
            self.assertEqual(note.read_bytes(), b'preserve')

    def test_invalid_function_identifiers_are_rejected(self):
        for name in ('9name', 'name;run', '', None):
            with self.subTest(name=name), self.assertRaises(ValueError):
                inline.validate_observation(self.valid_trace(), ASSEMBLY, ASSEMBLY, name)


if __name__ == '__main__':
    unittest.main()
