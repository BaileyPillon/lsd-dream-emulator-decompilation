"""Keep native save reports private and preserve existing evidence."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import verify_card_save


class CardSaveOutputTests(unittest.TestCase):
    def test_existing_private_report_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / '.decomp-lab' / 'report.json'
            report.parent.mkdir()
            report.write_bytes(b'preserved save evidence')
            with patch.object(verify_card_save, 'ROOT', root), \
                    patch.object(verify_card_save, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(verify_card_save.main(['--output', str(report)]), 2)
                verify.assert_not_called()
            self.assertEqual(report.read_bytes(), b'preserved save evidence')

    def test_escape_is_rejected_before_loading_game_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / '.decomp-lab' / '..' / 'public' / 'report.json'
            with patch.object(verify_card_save, 'ROOT', root), \
                    patch.object(verify_card_save, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(verify_card_save.main(['--output', str(report)]), 2)
                verify.assert_not_called()
            self.assertFalse((root / 'public').exists())
            self.assertFalse((root / '.decomp-lab').exists())


if __name__ == '__main__':
    unittest.main()
