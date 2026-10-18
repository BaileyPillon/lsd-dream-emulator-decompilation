"""Source-only fixtures for compiler census parsing and evidence guards."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import audit_unused_locals as tool


class UnusedLocalDiagnosticTests(unittest.TestCase):
    def test_canonical_backtick_diagnostic_preserves_function_file_line_and_name(self):
        text="src/file.c: In function `read_file':\nsrc/file.c:12: warning: unused variable `sector'\n"
        self.assertEqual(tool.parse_diagnostics(text),[dict(function='read_file',source='src/file.c',line=12,variable='sector')])

    def test_context_changes_without_counting_unrelated_warnings(self):
        text="a.c: In function 'first':\na.c:2: warning: unused variable 'buffer'\n"
        text+="a.c:3: warning: control reaches end of non-void function\na.c: In function `second':\na.c:9: warning: unused variable `pointer'\n"
        self.assertEqual([(r['function'],r['variable']) for r in tool.parse_diagnostics(text)],
                         [('first','buffer'),('second','pointer')])

    def test_source_path_with_spaces_and_a_drive_colon_is_not_split(self):
        text="C:/Private Project/file.c: In function `read_file':\nC:/Private Project/file.c:25: warning: unused variable `buffer'"
        self.assertEqual(tool.parse_diagnostics(text)[0]['source'],'C:/Private Project/file.c')

    def test_unsupported_warning_syntax_cannot_silently_reduce_the_count(self):
        for line in ("a.c:2: warning: unused variable sector", "a.c:0: warning: unused variable `sector'",
                     "a.c:2: unused variable `sector'", "a.c:2: warning: unused variable `sector' unexpected"):
            with self.subTest(line=line),self.assertRaises(ValueError):
                tool.parse_diagnostics("a.c: In function `read_file':\n"+line)

    def test_unowned_warning_is_rejected(self):
        with self.assertRaises(ValueError):tool.parse_diagnostics("a.c:2: warning: unused variable `buffer'")

    def test_repeated_diagnostics_remain_visible_as_emitted_warnings(self):
        line="a.c:2: warning: unused variable `buffer'\n"
        self.assertEqual(len(tool.parse_diagnostics("a.c: In function `read_file':\n"+line*2)),2)

    def test_parameter_and_function_warnings_are_outside_the_local_variable_census(self):
        self.assertEqual(tool.parse_diagnostics("a.c:2: warning: unused parameter `receiver'\n"
                                               "a.c:3: warning: `helper' defined but not used\n"),[])

    def test_output_must_be_a_new_private_child_and_existing_evidence_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);lab=root/'.decomp-lab';lab.mkdir();old=lab/'old';old.mkdir()
            (old/'evidence.txt').write_text('retained')
            self.assertEqual(tool.private_output(lab/'new',root),(lab/'new').resolve())
            for target in (lab,old,root/'elsewhere',lab/'..'/'elsewhere'):
                with self.subTest(target=target),self.assertRaises(ValueError):tool.private_output(target,root)
            self.assertEqual((old/'evidence.txt').read_text(),'retained')

    def test_wrong_compiler_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            fake=Path(folder)/'cc1';fake.write_bytes(b'owned wrong compiler fixture')
            with self.assertRaisesRegex(ValueError,'exact bundled'):tool.compiler_identity(fake)

    def test_unsupported_host_does_not_load_game_inputs_or_create_output(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'.decomp-lab'/'new'
            with patch.object(tool,'private_output',return_value=output),patch.object(tool.sys,'platform','win32'),\
                 patch.object(tool,'collect_progress',side_effect=AssertionError('must not load inputs')):
                with self.assertRaisesRegex(ValueError,'Linux/WSL'):tool.audit(output)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
