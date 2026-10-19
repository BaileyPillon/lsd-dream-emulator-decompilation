"""Synthetic guards for interpreting compiler phase evidence, without game data."""
import unittest

from research.render_grid import inspect_compiler_phases as phases


class GridCompilerPhaseTests(unittest.TestCase):
    def test_selected_function_is_exact_and_duplicates_are_rejected(self):
        dump = ';; Function another\nignored\n;; Function func_8004C6A8\nselected\n;; Function later\ntail\n'
        self.assertEqual(phases.function_section(dump), 'selected\n')
        for text in (dump.replace('func_8004C6A8', 'func_8004C6A8_extra'), dump + dump):
            with self.assertRaises(ValueError):
                phases.function_section(text)

    def test_register_copy_respects_function_marker_and_stops_at_first_call(self):
        text = ('(insn 8 0 9 (set (reg/v:SI 73) (reg:SI 6 a2)))\n\n'
                '(note 9 8 17 "" NOTE_INSN_FUNCTION_BEG)\n\n'
                '(insn 17 9 40 (set (reg/v:SI 75) (reg/v:SI 73)))\n\n'
                '(call_insn 40 17 45 (call (mem:SI (reg:SI 2 v0))))\n\n'
                '(insn 45 40 0 (set (reg:SI 3 v1) (reg:SI 6 a2)))\n')
        moves = [event for event in phases.prefix_events(text) if event['kind'] == 'register_copy']
        self.assertEqual([(e['uid'], e['after_function_begin_note']) for e in moves], [(8, False), (17, True)])

    def test_stack_address_and_save_are_distinct_and_keep_native_order(self):
        text = ('(note 9 0 36 "" NOTE_INSN_FUNCTION_BEG)\n\n'
                '(insn:QI 36 9 402 (set (reg:SI 5 a1) (plus:SI (reg:SI 29 sp) (const_int 16))))\n\n'
                '(insn 402 36 0 (set (mem:SI (plus:SI (reg:SI 29 sp) (const_int 144))) (reg:SI 30 $fp)))\n')
        events = phases.prefix_events(text)
        self.assertEqual([event['kind'] for event in events],
                         ['function_begin_note', 'lookup_buffer_address', 'save_incoming_fp'])
        self.assertEqual(events[-1]['displacement'], 144)

    def test_missing_rtl_or_function_boundary_is_rejected(self):
        for text in ('', '(insn 8 0 0 (set (reg:SI 30) (reg:SI 6 a2)))\n'):
            with self.assertRaises(ValueError):
                phases.prefix_events(text)

    def test_inline_forms_keep_their_own_instruction_ids(self):
        text = ('(note/i 1 0 2 "" NOTE_INSN_FUNCTION_BEG)\n\n'
                '(insn/i 2 1 3 (set (reg:SI 72) (reg:SI 4 a0)))\n\n'
                '(insn/i 3 2 4 (set (reg:SI 73) (reg:SI 5 a1)))\n\n'
                '(note/i 4 3 0 "" NOTE_INSN_DELETED)\n')
        events = phases.prefix_events(text)
        self.assertEqual([(e['uid'], e['kind']) for e in events],
                         [(1, 'function_begin_note'), (2, 'register_copy'),
                          (3, 'register_copy'), (4, 'deleted_note')])

    def test_inline_call_ends_the_prefix_before_later_copies(self):
        text = ('(note 1 0 2 "" NOTE_INSN_FUNCTION_BEG)\n\n'
                '(insn/i 2 1 3 (set (reg:SI 72) (reg:SI 4 a0)))\n\n'
                '(call_insn/i 3 2 4 (call (mem:SI (reg:SI 2 v0))))\n\n'
                '(insn 4 3 0 (set (reg:SI 73) (reg:SI 5 a1)))\n')
        moves = [e for e in phases.prefix_events(text) if e['kind'] == 'register_copy']
        self.assertEqual([(e['uid'], e['destination']) for e in moves], [(2, 72)])

    def test_mixed_inline_and_ordinary_notes_do_not_relabel_events(self):
        text = ('(note 1 0 2 "" NOTE_INSN_FUNCTION_BEG)\n\n'
                '(insn 2 1 3 (set (reg:SI 72) (reg:SI 4 a0)))\n\n'
                '(note/i 3 2 4 "" NOTE_INSN_DELETED)\n\n'
                '(insn/i 4 3 0 (set (reg:SI 73) (reg:SI 5 a1)))\n')
        events = phases.prefix_events(text)
        self.assertEqual([(e['uid'], e['kind']) for e in events],
                         [(1, 'function_begin_note'), (2, 'register_copy'),
                          (3, 'deleted_note'), (4, 'register_copy')])

    def test_inline_attributes_and_modes_preserve_stack_event_order(self):
        text = ('(note/i 1 0 2 "" NOTE_INSN_FUNCTION_BEG)\n\n'
                '(insn/i:QI 2 1 3 (set (reg:SI 5 a1) (plus:SI (reg:SI 29 sp) (const_int 16))))\n\n'
                '(insn/s/i:QI 3 2 0 (set (mem:SI (plus:SI (reg:SI 29 sp) (const_int 144))) (reg:SI 30 $fp)))\n')
        events = phases.prefix_events(text)
        self.assertEqual([e['kind'] for e in events],
                         ['function_begin_note', 'lookup_buffer_address', 'save_incoming_fp'])
        self.assertEqual([e['uid'] for e in events], [1, 2, 3])

    def test_unsized_and_zero_size_compiler_labels_are_not_functions(self):
        text = ('00000000 00000294 T func_8004C6A8\n00000000 t gcc2_compiled.\n'
                '00000000 00000000 t __gnu_compiled_c\n00000294 00000010 t real_helper\n')
        self.assertEqual(phases.sized_function_symbols(text),
                         [{'function': 'func_8004C6A8', 'offset': 0, 'bytes': 660},
                          {'function': 'real_helper', 'offset': 660, 'bytes': 16}])


if __name__ == '__main__':
    unittest.main()
