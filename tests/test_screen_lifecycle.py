"""Source-only adversarial checks for bounded native screen lifetime evidence."""
from copy import deepcopy
import itertools
import unittest

from research.screen_lifecycle import verify as tool
from tests.test_npc_catalogue import elf, executable

class ScreenLifecycleTests(unittest.TestCase):
    def case(self, kind='chart', pool=0x1000):
        return dict(kind=kind, pool_size=pool, segment=0x80000000, seed=1,
                    create_arg=0x108040, graphics=0xA0108080, result=3,
                    flag=0x80000000 if kind == 'chart' else 0)

    def test_every_pair_of_ram_aliases_is_exercised(self):
        profiles = list(tool.cases())
        keys = ('segment', 'create_arg', 'graphics')
        choices = (tool.SEGMENTS, tuple(0x108040 | s for s in tool.SEGMENTS),
                   tuple(0x108080 | s for s in tool.SEGMENTS))
        for first, second in itertools.combinations(range(3), 2):
            self.assertEqual({(c[keys[first]], c[keys[second]]) for c in profiles},
                             set(itertools.product(choices[first], choices[second])))

    def test_exhaustion_does_not_multiply_unexecuted_result_or_flag_values(self):
        exhausted = [c for c in tool.cases() if c['pool_size'] == tool.SIZES[c['kind']]]
        self.assertEqual(len(exhausted), 36)
        self.assertEqual({(c['result'], c['flag']) for c in exhausted}, {(0, 0)})
        self.assertEqual(len({tuple(c.values()) for c in tool.cases()}), 2052)

    def test_prediction_is_complete_before_any_original_execution(self):
        for kind in tool.SIZES:
            for delta in (4, 12, 20):
                case = self.case(kind, tool.SIZES[kind] + delta)
                untouched = deepcopy(case)
                model, pointer = tool.predicted(case)
                self.assertNotEqual(pointer, 0)
                self.assertEqual(case, untouched)
                self.assertEqual(len(model.blocks), 1)
                self.assertTrue(model.blocks[0].free)
                self.assertEqual(model.blocks[0].size, case['pool_size'])
                self.assertEqual(set(model.snapshot()), {'manager', 'pool', 'object'})

    def test_too_small_pool_predicts_no_receiver(self):
        for kind, size in tool.SIZES.items():
            model, pointer = tool.predicted(self.case(kind, size))
            self.assertEqual(pointer, 0)
            self.assertEqual(model.queue, [0])

    def test_unsupported_or_uninitialized_inputs_are_rejected(self):
        for field, value in (('pool_size', 0x1004), ('segment', 0x40000000),
                             ('graphics', 0xDEADBEEF), ('create_arg', 0), ('kind', 'ui')):
            case = self.case()
            case[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                tool.validate_case(case)

    def test_complete_function_tail_must_match(self):
        code = b'\x00' * 12 + b'ABCD'
        linked = elf(code, (('method', 0, len(code)),))
        with self.assertRaisesRegex(ValueError, 'Complete original function mismatch'):
            tool.owned_record(executable(code[:-4] + b'FAIL'), linked,
                              {'method': [(0x80010000, 16)]}, 'method', 0x80010000)

    def test_ambiguous_or_different_gnu_ownership_is_rejected(self):
        code = bytes(16)
        for spans in ([(0x80010000, 12)], [(0x80010000, 16), (0x80010000, 16)]):
            with self.subTest(spans=spans), self.assertRaisesRegex(ValueError, 'GNU/ELF function extent mismatch'):
                tool.owned_record(executable(code), elf(code, (('method', 0, 16),)),
                                  {'method': spans}, 'method', 0x80010000)

    def test_destroy_and_release_follow_run_in_the_required_protocol(self):
        trace = tool.expected_trace(self.case(), True)
        self.assertLess(trace.index('graphics_init:contract'), trace.index('base_class_destructor'))
        self.assertLess(trace.index('cleanup:contract'), trace.index('memory_free_mem'))
        self.assertNotIn('construct:contract', tool.expected_trace(self.case(), False))

    def test_delay_slot_registers_are_not_reported_as_callee_arguments(self):
        edge = dict(pc='0x80026550', target='0x8003C1DC', pre_delay_arguments=[7, 8, 0xBAD])
        self.assertIs(tool.observe_target_entry(edge, 0x80026554, [7, 8, 0xBAD]), edge)
        self.assertNotIn('entry_arguments', edge)
        self.assertIsNone(tool.observe_target_entry(edge, 0x8003C1DC, [7, 8, 0]))
        self.assertEqual(edge['entry_arguments'], [7, 8, 0])
        self.assertEqual(edge['pre_delay_arguments'], [7, 8, 0xBAD])

    def test_an_unobserved_target_cannot_complete_the_call(self):
        edge = dict(pc='0x80026550', target='0x8003C1DC', pre_delay_arguments=[7, 8, 0xBAD])
        with self.assertRaisesRegex(ValueError, 'did not reach its recorded target'):
            tool.observe_target_entry(edge, 0x8003C1E0, [7, 8, 0])

    def test_no_pending_transfer_does_not_create_an_entry(self):
        self.assertIsNone(tool.observe_target_entry(None, 0x8003C1DC, [7, 8, 0]))

if __name__ == '__main__':
    unittest.main()
