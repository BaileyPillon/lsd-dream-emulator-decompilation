"""Synthetic guards for native menu domains, object rules and candidate custody."""
import json
import unittest

from tools import verify_menu_layout as menu


class MenuLayoutTests(unittest.TestCase):
    def case(self, **changes):
        result = dict(count=2, old=0, selected=1, mode=2, show=1, glyphs=4,
                      start=1, length=2, gap=2, spacing=-8, repeats=1, xy=(31, 51))
        result.update(changes)
        return result

    def test_profile_is_unique_and_within_owned_graph_bounds(self):
        cases = list(menu.cases())
        self.assertEqual(len(cases), 864)
        self.assertEqual(len({json.dumps(case, sort_keys=True) for case in cases}), 864)
        for case in cases:
            menu.validate_case(case)

    def test_invalid_selection_windows_or_word_values_are_rejected(self):
        for changes in ({'count': 0}, {'selected': 2}, {'start': 3, 'length': 2},
                        {'glyphs': True}, {'xy': (0x80000000, 0)}, {'repeats': 3}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                menu.validate_case(self.case(**changes))

    def test_gap_and_window_attachment_differ_from_later_full_index_reset(self):
        case = self.case()
        before = menu.expected_objects(case, False)['lines'][0]['glyphs']
        after = menu.expected_objects(case, True)['lines'][0]['glyphs']
        self.assertEqual([before[i]['position'][0] for i in (1, 2)], [31, 39])
        self.assertEqual([after[i]['position'][0] for i in (1, 2)], [23, 15])
        self.assertEqual([after[i]['position'] for i in (0, 3)], [[0, 0], [0, 0]])

    def test_only_mode_two_commits_selection_color_and_timer_changes(self):
        for mode in (0, 1, 3):
            case = self.case(mode=mode)
            self.assertEqual(menu.expected_objects(case, True), menu.expected_objects(case, False))
        result = menu.expected_objects(self.case(), True)
        self.assertEqual((result['mode'], result['stored_selection'], result['ticks'], result['timer_mode']), (1, 1, 0, 5))
        self.assertEqual(result['lines'][1]['glyphs'][1]['color'], [0x23, 0xA4, 0x7F])
        self.assertEqual(result['lines'][1]['glyphs'][0]['color'], [7, 11, 13])

    def test_native_word_wrap_and_hidden_effect_dimensions_are_preserved(self):
        case = self.case(xy=(0x7fffffff, -0x80000000), spacing=8, start=0, gap=0, length=4)
        result = menu.expected_objects(case, True)
        self.assertEqual(result['lines'][0]['position'][1], 0x7ffffff6)
        self.assertEqual(result['lines'][0]['glyphs'][1]['position'][0], -0x7ffffff9)
        hidden = menu.expected_objects(self.case(show=0), True)
        self.assertEqual(hidden['effect_dimensions'], [71, -83])
        self.assertEqual(hidden['effect_parent'], 0)

    def test_complete_candidate_is_restricted_to_the_two_native_spans(self):
        load = menu.SOURCE_FUNCTIONS['func_8003D73C'][0]
        end = 0x800 + menu.SOURCE_FUNCTIONS['func_8003DAD4'][0] - load + 472
        reference = bytes(end + 16)
        candidate = bytearray(reference)
        candidate[0x800] = 1
        self.assertEqual(set(menu.candidate_patches(reference, bytes(candidate), load)), {'func_8003D73C'})
        for changed in (bytes(candidate)[:-1], bytes([1]) + reference[1:], reference[:-1] + bytes([1])):
            with self.assertRaises(ValueError):
                menu.candidate_patches(reference, changed, load)


if __name__ == '__main__':
    unittest.main()
