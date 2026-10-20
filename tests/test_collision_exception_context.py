"""Generic MIPS/CP0 evidence fixtures; no game or BIOS data."""
import struct
import unittest

from tools.collision_exception_context import (CORE_COMMIT, CPU_HEADER_SHA256, CPU_SOURCE_SHA256,
                                               ExceptionTrace, RAM_BYTES, inspect_context, qualify_core_profile)


def fixture(*, delay=False, taken=False):
    memory = bytearray(RAM_BYTES)
    struct.pack_into('<4I', memory, 0x10000, 0, 0x1440fffe, 0x24e70006, 0)
    epc = 0x80010004 if delay else 0x80010008
    row = dict(entry_cpu_epc=0x80018000, cpu_epc=epc, cpu_gpr_26=epc,
               cpu_cause=0x10000000 | (0x80000000 if delay else 0) | (0x40000000 if taken else 0))
    functions = [dict(function='synthetic', address='0x80010000', bytes=16)]
    return row, memory, functions


class ExceptionContextTests(unittest.TestCase):
    def test_core_profile_binds_the_diagnostic_to_both_pinned_CPU_sources(self):
        profile = dict(mednafen_commit=CORE_COMMIT, existing_CPU_source_modified=False,
                       inputs=[dict(path='/source/cpu.cpp', sha256=CPU_SOURCE_SHA256),
                               dict(path='C:\\source\\cpu.h', sha256=CPU_HEADER_SHA256)])
        self.assertEqual(qualify_core_profile(profile)['CPU_source_sha256'], CPU_SOURCE_SHA256)
        self.assertEqual(qualify_core_profile(profile)['CPU_header_sha256'], CPU_HEADER_SHA256)

    def test_changed_or_ambiguous_core_profile_is_rejected(self):
        def profile():
            return dict(mednafen_commit=CORE_COMMIT, existing_CPU_source_modified=False,
                        inputs=[dict(path='/source/cpu.cpp', sha256=CPU_SOURCE_SHA256),
                                dict(path='/source/cpu.h', sha256=CPU_HEADER_SHA256)])
        invalid = []
        item = profile(); item['existing_CPU_source_modified'] = True; invalid.append(item)
        item = profile(); item['mednafen_commit'] = '0'*40; invalid.append(item)
        item = profile(); item['inputs'][1]['sha256'] = '0'*64; invalid.append(item)
        item = profile(); item['inputs'].append(dict(item['inputs'][0])); invalid.append(item)
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ValueError):
                qualify_core_profile(item)

    def test_interrupt_encoding_and_instruction_derived_CE(self):
        context = inspect_context(*fixture())
        self.assertEqual(context['status'], 'consistent_interrupt_register_context')
        self.assertEqual(context['interrupted_PC'], 0x80010008)
        self.assertEqual(context['instruction_CE_bits'], 0x10000000)
        self.assertEqual(context['interrupted_function'], 'synthetic')
        self.assertFalse(context['interrupts_replayed'])

    def test_unchanged_EPC_is_only_an_absence_of_transition_evidence(self):
        row, memory, functions = fixture()
        row['entry_cpu_epc'] = row['cpu_epc']
        context = inspect_context(row, memory, functions)
        self.assertEqual(context['status'], 'no_observed_EPC_transition')
        self.assertNotIn('interrupted_PC', context)

    def test_non_interrupt_exception_codes_remain_distinct(self):
        for code in (4, 5, 8, 9, 12):
            row, memory, functions = fixture()
            row['cpu_cause'] |= code << 2
            with self.subTest(code=code):
                context = inspect_context(row, memory, functions)
                self.assertEqual(context['status'], 'other_exception_transition')
                self.assertEqual(context['exception_code'], code)

    def test_CE_contradiction_is_reported_with_both_values(self):
        row, memory, functions = fixture()
        row['cpu_cause'] ^= 0x10000000
        context = inspect_context(row, memory, functions)
        self.assertIn('CAUSE_CE_disagrees_with_pinned_core_instruction_rule', context['issues'])
        self.assertEqual((context['CAUSE_CE_bits'], context['instruction_CE_bits']), (0, 0x10000000))

    def test_K0_contradiction_is_not_an_interrupt_explanation(self):
        row, memory, functions = fixture()
        row['cpu_gpr_26'] ^= 4
        context = inspect_context(row, memory, functions)
        self.assertIn('returned_K0_does_not_equal_returned_EPC', context['issues'])
        self.assertNotEqual(context['status'], 'consistent_interrupt_register_context')

    def test_branch_delay_uses_delay_instruction_and_branch_EPC(self):
        context = inspect_context(*fixture(delay=True, taken=True))
        self.assertEqual(context['status'], 'consistent_interrupt_register_context')
        self.assertEqual(context['returned_EPC'], 0x80010004)
        self.assertEqual(context['interrupted_PC'], 0x80010008)
        self.assertEqual(context['branch']['taken_target'], 0x80010000)
        self.assertEqual(context['branch']['fallthrough'], 0x8001000c)

    def test_taken_and_untaken_paths_have_distinct_compatible_occurrences(self):
        for taken, expected in ((True, 0x80010000), (False, 0x8001000c)):
            with self.subTest(taken=taken):
                context = inspect_context(*fixture(delay=True, taken=taken))
                trace = ExceptionTrace(context)
                for i, pc in enumerate((0x80010004, 0x80010008, expected), 1):
                    trace.observe(pc, i)
                self.assertEqual(trace.report()['compatible_PC_occurrences'], 1)
                wrong = ExceptionTrace(context)
                for i, pc in enumerate((0x80010004, 0x80010008, 0x80010010), 1):
                    wrong.observe(pc, i)
                self.assertEqual(wrong.report()['compatible_PC_occurrences'], 0)

    def test_missing_preceding_branch_cannot_qualify_a_delay_slot(self):
        trace = ExceptionTrace(inspect_context(*fixture(delay=True, taken=True)))
        for i, pc in enumerate((0x80010000, 0x80010008, 0x80010000), 1):
            trace.observe(pc, i)
        self.assertEqual(trace.report()['compatible_PC_occurrences'], 0)

    def test_taken_and_fallthrough_totals_expose_timing_ambiguity_without_more_samples(self):
        trace = ExceptionTrace(inspect_context(*fixture(delay=True, taken=True)), sample_limit=0)
        for i, pc in enumerate((0x80010004, 0x80010008, 0x80010000,
                                0x80010004, 0x80010008, 0x8001000c), 1):
            trace.observe(pc, i)
        report = trace.report()
        self.assertEqual(report['branch_transfer_outcomes']['taken_target_only'], 1)
        self.assertEqual(report['branch_transfer_outcomes']['fallthrough_only'], 1)
        self.assertEqual(report['compatible_PC_occurrences'], 1)
        self.assertEqual(report['retained_PC_details'], [])
        self.assertFalse(report['interrupt_cycle_identified'])

    def test_identical_target_and_fallthrough_cannot_disambiguate_the_taken_bit(self):
        row, memory, functions = fixture(delay=True, taken=True)
        struct.pack_into('<I', memory, 0x10004, 0x14400001)
        trace = ExceptionTrace(inspect_context(row, memory, functions))
        for i, pc in enumerate((0x80010004, 0x80010008, 0x8001000c), 1):
            trace.observe(pc, i)
        report = trace.report()
        self.assertEqual(report['branch_transfer_outcomes']['indistinguishable_target_and_fallthrough'], 1)
        self.assertEqual(report['compatible_PC_occurrences'], 1)
        self.assertFalse(report['interrupt_cycle_identified'])

    def test_taken_bit_without_delay_context_is_preserved_as_contradictory(self):
        context = inspect_context(*fixture(taken=True))
        self.assertIn('taken_bit_without_branch_delay_context', context['issues'])

    def test_unreviewed_register_jump_delay_is_not_guessed(self):
        row, memory, functions = fixture(delay=True, taken=True)
        struct.pack_into('<I', memory, 0x10004, 0x03e00008)
        context = inspect_context(row, memory, functions)
        self.assertIn('branch_delay_transfer_not_reviewed', context['issues'])

    def test_EPC_and_delay_instruction_both_require_qualified_ranges(self):
        row, memory, functions = fixture(delay=True, taken=True)
        functions[0].update(address='0x80010004', bytes=4)
        context = inspect_context(row, memory, functions)
        self.assertIn('EPC_or_interrupted_PC_outside_qualified_function_ranges', context['issues'])

    def test_unmapped_or_unaligned_EPC_is_not_read(self):
        for address in (0x80010009, 0x80200000, 0xbfc00180):
            row, memory, functions = fixture()
            row['cpu_epc'] = row['cpu_gpr_26'] = address
            with self.subTest(address=address):
                context = inspect_context(row, memory, functions)
                self.assertIn('EPC_or_interrupted_PC_not_in_aligned_RAM', context['issues'])

    def test_incomplete_memory_and_non_architectural_words_are_rejected(self):
        row, memory, functions = fixture()
        with self.assertRaisesRegex(ValueError, 'complete captured'):
            inspect_context(row, memory[:-1], functions)
        for value in (-1, 2**32, True):
            row['cpu_epc'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, '32-bit word'):
                inspect_context(row, memory, functions)

    def test_PC_samples_are_bounded_without_losing_occurrence_totals(self):
        trace = ExceptionTrace(inspect_context(*fixture()), sample_limit=2)
        for i in range(10):
            trace.observe(0x80010008, i + 1)
        report = trace.report()
        self.assertEqual((report['functional_PC_occurrences'], report['completed_PC_occurrences'],
                          report['compatible_PC_occurrences'], report['unfinished_PC_occurrences']), (10, 9, 9, 1))
        self.assertEqual((len(report['retained_PC_details']), report['omitted_PC_details']), (2, 7))
        self.assertFalse(report['interrupt_cycle_identified'])
        self.assertFalse(report['interrupt_device_identified'])
        self.assertFalse(report['full_game_parity_accepted'])

    def test_an_unvisited_exception_PC_does_not_qualify(self):
        trace = ExceptionTrace(inspect_context(*fixture()))
        trace.observe(0x80010000, 1)
        self.assertEqual(trace.report()['compatible_PC_occurrences'], 0)


if __name__ == '__main__':
    unittest.main()
