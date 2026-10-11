"""Research CLI guards must fail before optional emulation or public output writes."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from research.collision import compare_candidate, verify_midpoint


class CollisionResearchGuards(unittest.TestCase):
    def setUp(self):
        self.previous_cwd = Path.cwd()

    def tearDown(self):
        os.chdir(self.previous_cwd)

    def test_help_needs_no_game_or_optional_emulator(self):
        for module in (compare_candidate, verify_midpoint):
            with self.subTest(module=module.__name__):
                with patch.object(module.n, 'load_program', side_effect=AssertionError('unexpected game read')):
                    with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as result:
                        module.main(['--help'])
                    self.assertEqual(result.exception.code, 0)

    def test_both_checkers_refuse_public_output_locations(self):
        with tempfile.TemporaryDirectory() as folder:
            outside = Path(folder) / 'new-proof'
            for module in (compare_candidate, verify_midpoint):
                with self.subTest(module=module.__name__):
                    with patch.object(module.n, 'load_program', side_effect=AssertionError('unexpected game read')):
                        with self.assertRaisesRegex(ValueError, 'fresh private output'):
                            module.verify(SimpleNamespace(output=outside))
                    self.assertFalse(outside.exists())

    def test_existing_private_evidence_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            output = root / '.decomp-lab' / 'retained'
            output.mkdir(parents=True)
            sentinel = output / 'evidence.json'
            sentinel.write_text('retained', encoding='utf-8')
            try:
                for module in (compare_candidate, verify_midpoint):
                    with self.subTest(module=module.__name__):
                        with patch.object(module, 'ROOT', root), patch.object(module.n, 'load_program') as load:
                            with self.assertRaises(FileExistsError):
                                module.verify(SimpleNamespace(output=output))
                            load.assert_not_called()
                        self.assertEqual(sentinel.read_text(encoding='utf-8'), 'retained')
            finally:
                os.chdir(self.previous_cwd)

    def check_rejected_candidate(self, changed, expected_message):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            (root / 'docs').mkdir()
            (root / 'docs/collision-function-ranges.json').write_text('[]', encoding='utf-8')
            reference = bytes(4096)
            candidate = root / 'candidate.exe'
            candidate.write_bytes(changed)
            program = SimpleNamespace(ROM=reference, LOAD=0x8001F8B8)
            arguments = SimpleNamespace(output=root / '.decomp-lab' / 'new', candidate=candidate)
            try:
                with patch.object(compare_candidate, 'ROOT', root):
                    with patch.object(compare_candidate.n, 'load_program', return_value=program):
                        with patch.object(compare_candidate.n, 'initialize_backend'), patch.object(compare_candidate.n, 'h', program, create=True):
                            with patch.object(compare_candidate.c, 'CollisionBridge', side_effect=AssertionError('unexpected bridge')):
                                with self.assertRaisesRegex(ValueError, expected_message):
                                    compare_candidate.verify(arguments)
            finally:
                os.chdir(self.previous_cwd)

    def test_candidate_cannot_change_another_function(self):
        data = bytearray(4096)
        data[0x100] = 1
        self.check_rejected_candidate(bytes(data), 'outside the original primitive')

    def test_candidate_cannot_change_the_image_length(self):
        self.check_rejected_candidate(bytes(4097), 'outside the original primitive')


if __name__ == '__main__':
    unittest.main()
