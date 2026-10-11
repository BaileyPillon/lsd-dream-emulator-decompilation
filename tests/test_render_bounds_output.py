"""Reject unsafe report destinations before loading game or native backends."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import verify_render_bounds


class RenderBoundsOutputTests(unittest.TestCase):
    def test_existing_private_evidence_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / '.decomp-lab' / 'report.json'
            report.parent.mkdir()
            report.write_bytes(b'preserved native evidence')
            with patch.object(verify_render_bounds, 'ROOT', root), \
                    patch.object(verify_render_bounds, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(verify_render_bounds.main(['--output', str(report)]), 2)
                verify.assert_not_called()
            self.assertEqual(report.read_bytes(), b'preserved native evidence')

    def test_path_escape_is_rejected_without_creating_public_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / '.decomp-lab' / '..' / 'public' / 'report.json'
            with patch.object(verify_render_bounds, 'ROOT', root), \
                    patch.object(verify_render_bounds, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(verify_render_bounds.main(['--output', str(report)]), 2)
                verify.assert_not_called()
            self.assertFalse((root / 'public').exists())
            self.assertFalse((root / '.decomp-lab').exists())


if __name__ == '__main__':
    unittest.main()
