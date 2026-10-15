"""Private output guards must run before original inputs or the optional backend."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import verify_movie_paths as tool


class MoviePathOutputTests(unittest.TestCase):
    def test_public_and_existing_output_paths_are_preserved_before_input_reads(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(tool, 'ROOT', Path(folder)):
            root = Path(folder)
            existing = root / '.decomp-lab' / 'retained.json'
            existing.parent.mkdir()
            existing.write_text('retained')
            for output in (root / 'public.json', existing):
                with patch.object(tool.native, 'load_program') as load, contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(tool.main(['--output', str(output)]), 1)
                    load.assert_not_called()
            self.assertEqual(existing.read_text(), 'retained')
            self.assertFalse((root / 'public.json').exists())


if __name__ == '__main__':
    unittest.main()
