"""Preserve private native reports before loading optional game/backend inputs."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import verify_sound_volume


class SoundVolumeOutputTests(unittest.TestCase):
    def test_existing_report_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / '.decomp-lab' / 'report.json'
            report.parent.mkdir()
            report.write_bytes(b'preserved native evidence')
            with patch.object(verify_sound_volume, 'ROOT', root), \
                    patch.object(verify_sound_volume, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(verify_sound_volume.main(['--output', str(report)]), 2)
                verify.assert_not_called()
            self.assertEqual(report.read_bytes(), b'preserved native evidence')

    def test_public_output_is_rejected_without_creating_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / 'public' / 'report.json'
            with patch.object(verify_sound_volume, 'ROOT', root), \
                    patch.object(verify_sound_volume, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(verify_sound_volume.main(['--output', str(report)]), 2)
                verify.assert_not_called()
            self.assertFalse(report.parent.exists())


if __name__ == '__main__':
    unittest.main()
