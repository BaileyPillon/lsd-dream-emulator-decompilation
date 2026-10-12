"""Private candidate preparation and complete-image isolation use synthetic data."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.collision import prepare_overlap_candidate as prepare
from research.collision import compare_overlap_candidate as compare


class OverlapCandidateTests(unittest.TestCase):
    def source(self):
        return ('prefix\n' + prepare.MARKER + '\n'
                'typedef struct func_8001E2E8_pt { short x,y,z; } func_8001E2E8_pt_t;\n'
                'typedef struct box { short limits[6]; } func_8001E2E8_box_t;\n'
                'void func_8001E2E8(void);\n'
                '\ns32 func_8001E110(void) { return 7; }\nsuffix\n')

    def test_prepare_preserves_unrelated_code_and_moves_declarations_once(self):
        source = self.source()
        composed = prepare.compose(source, 'CANDIDATE\n')
        self.assertTrue(composed.startswith('prefix\n'))
        self.assertTrue(composed.endswith('s32 func_8001E110(void) { return 7; }\nsuffix\n'))
        self.assertEqual(composed.count(prepare.TYPE_START), 1)
        self.assertLess(composed.index(prepare.TYPE_START), composed.index('CANDIDATE'))
        self.assertNotIn(prepare.MARKER, composed)

    def test_duplicate_inclusions_and_incomplete_declarations_are_rejected(self):
        for source in (self.source() + prepare.MARKER,
                       self.source().replace('void func_8001E2E8(void);', ''),
                       self.source().replace(prepare.TYPE_START, 'typedef struct different {')):
            with self.assertRaises(ValueError):
                prepare.compose(source, 'CANDIDATE')

    def test_existing_or_external_evidence_directory_is_rejected_before_source_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / '.decomp-lab' / 'retained'
            existing.mkdir(parents=True)
            with patch.object(prepare, 'ROOT', root), patch.object(Path, 'read_bytes') as reads:
                for output in (existing, root / 'outside-private'):
                    with self.subTest(output=output), self.assertRaises(ValueError):
                        prepare.prepare(output)
                reads.assert_not_called()

    def reference(self):
        return bytes(0x800 + compare.FUNCTION_BYTES + 16)

    def test_selected_function_changes_are_isolated_but_not_promoted(self):
        reference = self.reference()
        candidate = bytearray(reference)
        candidate[0x804] = 1
        observed = compare.candidate_patch(reference, bytes(candidate), compare.ADDRESS)
        self.assertEqual(len(observed), compare.FUNCTION_BYTES)
        self.assertEqual(observed[4], 1)

    def test_header_other_function_and_image_length_changes_are_rejected(self):
        reference = self.reference()
        for offset in (0, 0x800 + compare.FUNCTION_BYTES):
            candidate = bytearray(reference)
            candidate[offset] = 1
            with self.assertRaises(ValueError):
                compare.candidate_patch(reference, bytes(candidate), compare.ADDRESS)
        with self.assertRaises(ValueError):
            compare.candidate_patch(reference, reference[:-1], compare.ADDRESS)


if __name__ == '__main__':
    unittest.main()
