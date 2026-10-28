"""Reject typed-interface claims outside the supplied receiver contract."""
from copy import deepcopy
import unittest

from research.screen_lifecycle import verify_destroy as tool


class ScreenDestroyInputs(unittest.TestCase):
    def setUp(self):
        self.case = next(case for view, case in tool.cases() if view == 'screen_destroy_main')

    def test_supported_view_uses_the_actual_receiver_family(self):
        for view in ('screen_destroy_main', 'screen_destroy_common'):
            tool.validate_case(view, self.case)

    def test_identical_machine_prefix_does_not_authorize_wrong_concrete_type(self):
        with self.assertRaisesRegex(ValueError, 'receiver family'):
            tool.validate_case('screen_destroy_chart', self.case)

    def test_unknown_view_is_not_silently_treated_as_common(self):
        with self.assertRaisesRegex(ValueError, 'receiver family'):
            tool.validate_case('screen_destroy_unknown', self.case)

    def test_exhausted_factory_cannot_supply_a_destructor_receiver(self):
        self.case['pool_size'] = tool.lifecycle.SIZES['main']
        with self.assertRaisesRegex(ValueError, 'allocated receiver'):
            tool.validate_case('screen_destroy_common', self.case)

    def test_uninitialized_argument_or_unknown_alias_rejected(self):
        for key, value in (('create_arg', 0), ('graphics', 0xDEADBEEF), ('segment', 0x40000000)):
            case = deepcopy(self.case)
            case[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                tool.validate_case('screen_destroy_common', case)


if __name__ == '__main__':
    unittest.main()
