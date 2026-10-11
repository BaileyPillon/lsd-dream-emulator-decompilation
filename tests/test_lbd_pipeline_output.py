"""Native level evidence must remain private and existing reports intact."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import verify_lbd_pipeline


class LBDPipelineOutputTests(unittest.TestCase):
    def test_existing_private_report_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / '.decomp-lab' / 'report.json'
            report.parent.mkdir()
            report.write_bytes(b'preserved original level evidence')
            with patch.object(verify_lbd_pipeline, 'ROOT', root), \
                    patch.object(verify_lbd_pipeline, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(verify_lbd_pipeline.main([
                    '--inventory', 'unused.json', '--output', str(report)]), 2)
            verify.assert_not_called()
            self.assertEqual(report.read_bytes(), b'preserved original level evidence')

    def test_public_report_is_rejected_before_assets_are_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / 'docs' / 'report.json'
            with patch.object(verify_lbd_pipeline, 'ROOT', root), \
                    patch.object(verify_lbd_pipeline, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(verify_lbd_pipeline.main([
                    '--inventory', 'unused.json', '--output', str(report)]), 2)
            verify.assert_not_called()
            self.assertFalse(report.exists())
            self.assertFalse(report.parent.exists())


if __name__ == '__main__':
    unittest.main()
