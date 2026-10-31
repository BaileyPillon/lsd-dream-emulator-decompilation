"""Owned state patterns catch reset over-clearing and signed-word mistakes."""
import unittest

from tools import new_game_state as model


class OriginalNewGameStateTests(unittest.TestCase):
    def context(self):
        data = bytearray((index*37+0x53)&255 for index in range(model.OBJECT_BYTES))
        model.put(data, model.IS_NEW_GAME, 0xAABBCCDD)
        model.put(data, model.IS_FLASHBACK, 0)
        model.put(data, model.STORED_DAY, 364)
        return data

    def test_reset_footprint_preserves_inactive_history_and_every_unwritten_byte(self):
        before = self.context()
        after = model.reset(before, 0xA1B2C3D4)
        written = model.reset_write_offsets()
        self.assertEqual(len(written), 576)
        self.assertEqual(model.SAVE_BYTES-len(written), 1216)
        self.assertTrue(all(after[i] == before[i] for i in range(len(before)) if i not in written))
        self.assertEqual(after[0x190:0x46C], before[0x190:0x46C])
        self.assertEqual(after[0x470:0x5D8], before[0x470:0x5D8])
        self.assertEqual(after[0x5D9:0x5DF], before[0x5D9:0x5DF])
        self.assertEqual(after[0x5FE:0x600], before[0x5FE:0x600])
        self.assertEqual(after[0x604:0x678], before[0x604:0x678])
        self.assertEqual(model.word(after, model.IS_NEW_GAME), 0xAABBCCDD)

    def test_marker_is_copied_as_a_full_native_word_and_shake_is_enabled(self):
        for marker in (0, 0x31304A, 0xFFFFFFFF, 0x80000000):
            with self.subTest(marker=marker):
                out = model.reset(self.context(), marker)
                self.assertEqual(model.word(out, model.SAVE_OFFSET), marker)
                self.assertEqual(model.word(out, 0x678), 1)
                self.assertEqual(out[0x684:0x878], bytes(500))

    def test_end_mode_two_resets_both_normal_and_flashback_sessions(self):
        for flashback in (0, 1, 0x80000000, 0xFFFFFFFF):
            before = self.context(); model.put(before, model.IS_FLASHBACK, flashback)
            out, returned = model.end_day(before, 2, 0x31304A)
            self.assertEqual(returned, flashback)
            self.assertEqual(model.word(out, 0x180), 0)
            self.assertEqual(model.word(out, model.IS_NEW_GAME), 1)
            self.assertEqual(out[0x190:0x46C], before[0x190:0x46C])

    def test_other_end_modes_restore_stored_day_without_resetting(self):
        before = self.context()
        for mode in (1, 3, 0xFFFFFFFF, 0x80000000):
            out, returned = model.end_day(before, mode, 0x31304A)
            expected = bytearray(before); model.put(expected, 0x180, 364)
            self.assertEqual(out, bytes(expected))
            self.assertEqual(returned, 0)

    def test_flashback_zero_mode_does_not_take_normal_score_chart_branch(self):
        before = self.context(); model.put(before, model.IS_FLASHBACK, 1)
        out, returned = model.end_day(before, 0, 0x31304A)
        self.assertEqual(model.word(out, 0x180), 364)
        self.assertEqual(returned, 1)
        with self.assertRaisesRegex(ValueError, 'score/chart'):
            model.end_day(self.context(), 0, 0x31304A)

    def test_clearing_new_game_changes_only_the_four_byte_flag_outside_save_data(self):
        before = self.context(); out = model.clear_new_game(before)
        self.assertEqual(out[0x178:0x878], before[0x178:0x878])
        expected = bytearray(before); model.put(expected, model.IS_NEW_GAME, 0)
        self.assertEqual(out, bytes(expected))

    def test_negative_flag_inputs_query_and_nonnegative_inputs_exchange(self):
        before = self.context(); old = model.word(before, model.FLAG)
        for value in (0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF):
            out, returned = model.get_set_flag(before, value)
            self.assertEqual(returned, old)
            self.assertEqual(model.word(out, model.FLAG), value if value < 0x80000000 else old)
            self.assertEqual(out[:model.FLAG], before[:model.FLAG])

    def test_navigation_flags_support_byte_offsets_with_guarded_word_count(self):
        before = bytes((i*13+7)&255 for i in range(128))
        for alignment in range(4):
            start = 16+alignment
            out = model.nav_reset(before, start, 80)
            expected = bytearray(before); expected[start:start+30] = bytes(30); expected[80:84] = bytes(4)
            self.assertEqual(out, bytes(expected))
            self.assertEqual(out[start-1], before[start-1])
            self.assertEqual(out[start+30], before[start+30])

    def test_truncation_overlap_and_unaligned_word_are_explicitly_outside_profile(self):
        for invalid in (b'', bytes(model.SAVE_BYTES), bytes(model.OBJECT_BYTES-1)):
            with self.assertRaises(ValueError): model.reset(invalid, 0)
        for flags, count in ((-1, 80), (110, 80), (16, 17), (16, 20)):
            with self.assertRaises(ValueError): model.nav_reset(bytes(128), flags, count)

    def test_non_native_values_are_not_silently_truncated(self):
        for value in (-1, 1<<32, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                model.reset(self.context(), value)


if __name__ == '__main__':
    unittest.main()
