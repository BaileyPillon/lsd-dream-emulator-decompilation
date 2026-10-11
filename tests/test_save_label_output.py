"""Protect private native evidence before the optional backend is initialized."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import verify_save_label


class SaveLabelOutputTests(unittest.TestCase):
    def test_existing_report_is_preserved_without_loading_game_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / '.decomp-lab' / 'evidence.json'
            report.parent.mkdir()
            content = b'{"preserved":true}\n'
            report.write_bytes(content)
            with patch.object(verify_save_label, 'ROOT', root), \
                    patch.object(verify_save_label, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(verify_save_label.main(['--output', str(report)]), 2)
                verify.assert_not_called()
            self.assertEqual(report.read_bytes(), content)

    def test_public_output_is_rejected_without_creating_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / 'public' / 'evidence.json'
            with patch.object(verify_save_label, 'ROOT', root), \
                    patch.object(verify_save_label, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(verify_save_label.main(['--output', str(report)]), 2)
                verify.assert_not_called()
            self.assertFalse(report.parent.exists())


if __name__ == '__main__':
    unittest.main()
