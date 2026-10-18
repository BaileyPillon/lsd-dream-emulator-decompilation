"""Source-only rejection tests; native driver runs require a private game dump."""
from copy import deepcopy
import unittest

from research.file_driver import verify as driver


class FileInterfaceObservationTests(unittest.TestCase):
    def setUp(self):
        self.case = dict(method='read', view='common', driver='cd', state='busy',
                         arguments=(0x80000000, 0xFFFFFFFF))
        self.observation = dict(arguments=(driver.OBJECT | 0x80000000, 0x80000000, 0xFFFFFFFF),
            trace=['file_read_common', 'cd_file_driver_read', 'cd_file_driver_lock', 'cd_file_driver_unlock'],
            result=0, locks=[1, 0], object_equal=True, table_equal=True,
            globals_equal=True, saved_abi=True, stack_guards=True)

    def check(self, **changes):
        observed = deepcopy(self.observation)
        observed.update(changes)
        driver.validate_observation(self.case, True, observed)

    def test_complete_boundary_word_observation(self):
        self.check()

    def test_nonzero_read_result_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Read result'):
            self.check(result=1)

    def test_signed_length_reinterpretation_rejected(self):
        with self.assertRaisesRegex(ValueError, 'entry arguments'):
            self.check(arguments=(driver.OBJECT | 0x80000000, 0x80000000, -1))

    def test_receiver_alias_changed_rejected(self):
        with self.assertRaisesRegex(ValueError, 'entry arguments'):
            self.check(arguments=(driver.OBJECT, 0x80000000, 0xFFFFFFFF))

    def test_omitted_native_unlock_rejected(self):
        with self.assertRaisesRegex(ValueError, 'dispatch order'):
            self.check(trace=self.observation['trace'][:-1])

    def test_lock_left_held_rejected(self):
        with self.assertRaisesRegex(ValueError, 'lock transition'):
            self.check(locks=[1])

    def test_each_ownership_and_abi_failure_rejected(self):
        for key in ('object_equal', 'table_equal', 'globals_equal', 'saved_abi', 'stack_guards'):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, key):
                self.check(**{key: False})

    def test_void_open_does_not_claim_a_result_word(self):
        self.case.update(method='open', arguments=(0xFFFFFFFF, 0x80000000, 1))
        self.observation.update(arguments=(driver.OBJECT | 0x80000000, 0xFFFFFFFF, 0x80000000, 1),
            trace=['file_open_common', 'cd_file_driver_open', 'cd_file_driver_lock', 'cd_file_driver_unlock'])
        self.check(result=0xDEADBEEF)

    def test_debug_method_must_not_claim_a_cd_lock(self):
        self.case.update(driver='debug')
        self.observation.update(trace=['file_read_common', 'debug_file_driver_read'])
        self.check(locks=[])
        with self.assertRaisesRegex(ValueError, 'lock transition'):
            self.check()


if __name__ == '__main__':
    unittest.main()
