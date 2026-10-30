"""Use actual filesystem links to keep shared runtime data outside capture bounds."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.capture_storage import owned_output_bytes


class CaptureStorageTests(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='lsd-capture-size-')
        self.addCleanup(area.cleanup)
        self.area = Path(area.name)
        self.root = self.area/'capture'
        self.root.mkdir()
        (self.root/'small').write_bytes(b'abc')
        (self.root/'nested').mkdir()
        (self.root/'nested/log').write_bytes(b'hello')
        self.external = self.area/'shared-runtime'
        self.external.mkdir()
        (self.external/'library').write_bytes(b'external payload that must remain outside the capture bound')

    def test_nested_outputs_are_counted(self):
        self.assertEqual(owned_output_bytes(self.root), 8)
        self.assertGreater(owned_output_bytes(self.area), 8)

    def test_directory_symlink_is_not_followed(self):
        link = self.root/'runtime'
        try:
            link.symlink_to(self.external, target_is_directory=True)
        except OSError as error:
            self.skipTest('Directory symlinks are unavailable: '+str(error))
        self.assertEqual(owned_output_bytes(self.root), 8)
        self.assertTrue((self.external/'library').is_file())

    def test_file_symlink_is_not_counted(self):
        link = self.root/'library'
        try:
            link.symlink_to(self.external/'library')
        except OSError as error:
            self.skipTest('File symlinks are unavailable: '+str(error))
        self.assertEqual(owned_output_bytes(self.root), 8)

    @unittest.skipUnless(os.name == 'nt', 'NTFS junction regression requires Windows.')
    def test_ntfs_runtime_junction_is_not_followed(self):
        link = self.root/'dll'
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(self.external)],
                                capture_output=True, text=True, timeout=10,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertTrue(link.lstat().st_file_attributes & 0x400)
        try:
            self.assertEqual(owned_output_bytes(self.root), 8)
            self.assertTrue((self.external/'library').is_file())
        finally:
            self.assertEqual(link.parent.resolve(), self.root.resolve())
            os.rmdir(link)  # Remove this exact junction, preserving its external target.

    def test_missing_or_non_directory_root_is_rejected(self):
        with self.assertRaises(FileNotFoundError):
            owned_output_bytes(self.area/'absent')
        with self.assertRaises(NotADirectoryError):
            owned_output_bytes(self.root/'small')


if __name__ == '__main__':
    unittest.main()
