"""Evidence and compiler-mode safeguards without copyrighted game inputs."""

from pathlib import Path
import sys
import tempfile
import re
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import configure
from tools import decomp_workbench as workbench


class WorkbenchTests(unittest.TestCase):
    def test_length_difference_cannot_pass_as_a_match(self):
        result = workbench.compare_bytes(b"abcd", b"abcdX")
        self.assertFalse(result["exact_match"])
        self.assertEqual(result["changed_bytes_in_common_range"], 0)
        self.assertEqual(result["length_difference"], 1)

    def test_evidence_excludes_neighboring_function_bytes(self):
        assembly = """glabel earlier
/* 0 80010000 01020304 */ nop
endlabel earlier
glabel target
/* 4 80010004 05060708 */ nop
/* 8 80010008 090A0B0C */ nop
endlabel target
glabel later
/* C 8001000C 0D0E0F10 */ nop
endlabel later
"""
        result = workbench.assembly_evidence(assembly, "target", bytes(range(1, 17)))
        self.assertEqual((result["file_offset"], result["bytes"], result["instructions"]), (4, 8, 2))

    def test_noncontiguous_and_disagreeing_evidence_is_rejected(self):
        template = "glabel target\n/* 0 80010000 01020304 */ nop\n/* {} 80010004 05060708 */ nop\nendlabel target\n"
        with self.assertRaisesRegex(ValueError, "Non-contiguous"):
            workbench.assembly_evidence(template.format("8"), "target", bytes(range(1, 9)))
        with self.assertRaisesRegex(ValueError, "disagree"):
            workbench.assembly_evidence(template.format("4"), "target", b"wrongROM")

    def test_explicit_end_boundary_is_required(self):
        with self.assertRaisesRegex(ValueError, "boundaries"):
            workbench.assembly_evidence("glabel target\n/* 0 80010000 01020304 */ nop", "target", b"\1\2\3\4")

    def test_candidate_uses_each_configured_compiler_mode(self):
        palette = workbench.candidate_commands("src/dream/dream_generation_palette.c", "candidate.c", "candidate.o")
        normal = workbench.candidate_commands("src/dream/dream_generation.c", "candidate.c", "candidate.o")
        self.assertIn("-G0", palette[1])
        self.assertNotIn("-DCCG8", palette[0])
        self.assertIn("-G8", normal[1])
        self.assertIn("-DCCG8", normal[0])
        with tempfile.TemporaryDirectory() as folder:
            graph = Path(folder) / "build.ninja"
            configure.generate_build(graph)
            content = re.sub(r'\$\n\s*', '', graph.read_text())
            self.assertTrue("dream_generation_palette.c.o: cc src/dream/dream_generation_palette.c" in content,
                            "The standard graph must compile the palette unit with the G0 rule.")

    def test_existing_and_outside_output_directories_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            lab = root / ".decomp-lab"
            lab.mkdir()
            existing = lab / "existing"
            existing.mkdir()
            sentinel = existing / "proof.json"
            sentinel.write_text("retained")
            with patch.object(workbench, "ROOT", root):
                with self.assertRaises(FileExistsError):
                    workbench.new_output_directory(existing)
                with self.assertRaisesRegex(ValueError, "inside"):
                    workbench.new_output_directory(root / "outside")
                with self.assertRaisesRegex(ValueError, "inside"):
                    workbench.new_output_directory(lab)
            self.assertEqual(sentinel.read_text(), "retained")
            self.assertFalse((root / "outside").exists())


if __name__ == "__main__":
    unittest.main()
