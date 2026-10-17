"""Keep original grid evidence private and preserve prior reports."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import verify_render_grid, verify_render_stream


class RenderGridOutputTests(unittest.TestCase):
    def test_recovered_grid_without_generated_assembly_reaches_program_checks(self):
        class ReachedProgramQualification(Exception):
            pass

        for verifier in (verify_render_grid, verify_render_stream):
            with self.subTest(verifier=verifier.__name__), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for name in ('tools/verify_render_grid.py', 'tools/verify_render_stream.py',
                             'src/scene/render_context.c', 'src/scene/render_context.h',
                             'config/symbols.txt'):
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b'synthetic recovered-C checkout input\n')

                def dependencies(*names):
                    return [root / name for name in names]

                # Stop at the existing canonical image checks. No game file,
                # generated grid assembly or VM backend is needed for preflight.
                with patch.object(verifier, 'ROOT', root), \
                        patch.object(verifier.native, 'evidence_dependencies', side_effect=dependencies), \
                        patch.object(verifier.native, 'load_program', side_effect=ReachedProgramQualification) as load:
                    with self.assertRaises(ReachedProgramQualification):
                        verifier.verify(root / '.decomp-lab' / 'report.json')
                    load.assert_called_once()
                self.assertFalse((root / 'asm').exists())

    def test_existing_private_report_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / '.decomp-lab' / 'report.json'
            report.parent.mkdir()
            report.write_bytes(b'preserved original renderer evidence')
            with patch.object(verify_render_grid, 'ROOT', root), \
                    patch.object(verify_render_grid, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(verify_render_grid.main(['--output', str(report)]), 2)
                verify.assert_not_called()
            self.assertEqual(report.read_bytes(), b'preserved original renderer evidence')

    def test_escape_is_rejected_before_loading_game_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = root / '.decomp-lab' / '..' / 'public' / 'report.json'
            with patch.object(verify_render_grid, 'ROOT', root), \
                    patch.object(verify_render_grid, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(verify_render_grid.main(['--output', str(report)]), 2)
                verify.assert_not_called()
            self.assertFalse((root / 'public').exists())
            self.assertFalse((root / '.decomp-lab').exists())


if __name__ == '__main__':
    unittest.main()
