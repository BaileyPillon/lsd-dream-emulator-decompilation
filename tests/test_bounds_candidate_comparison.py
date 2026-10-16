"""Candidate image confinement and measured-fault guards without game files."""
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from research.render_bounds import compare_candidate as bounds


class BoundsCandidateComparisonTests(unittest.TestCase):
    def images(self):
        original = bytes(512)
        code = bytes([17]) * bounds.LENGTH
        image = original[:128] + code + original[128 + bounds.LENGTH:]
        return original, image, code

    def test_complete_confined_function_is_accepted(self):
        original, image, code = self.images()
        changed = bounds.validate_image(original, image, code, 128)
        self.assertEqual(changed, set(range(bounds.ADDRESS, bounds.ADDRESS + bounds.LENGTH, 4)))
        self.assertEqual(bounds.validate_image(original, original, bytes(bounds.LENGTH), 128), set())

    def test_extent_and_image_length_cannot_be_changed(self):
        original, image, code = self.images()
        for body, offset in ((code[:-4], 128), (code + bytes(4), 128), (code, -1), (code, len(original))):
            with self.subTest(size=len(body), offset=offset), self.assertRaisesRegex(ValueError, 'complete original'):
                bounds.validate_image(original, image, body, offset)
        for changed in (image[:-1], image + b'x'):
            with self.subTest(size=len(changed)), self.assertRaisesRegex(ValueError, 'outside the bounds'):
                bounds.validate_image(original, changed, code, 128)

    def test_no_byte_outside_the_selected_function_can_change(self):
        original, image, code = self.images()
        for offset in (0, 127, 128 + bounds.LENGTH, len(image) - 1):
            changed = bytearray(image)
            changed[offset] = 1
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, 'outside the bounds'):
                bounds.validate_image(original, changed, code, 128)
        with self.assertRaisesRegex(ValueError, 'Sized ELF'):
            bounds.validate_image(original, image, bytes(bounds.LENGTH), 128)

    def test_output_guards_preserve_evidence_before_loading_game_inputs(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(bounds, 'ROOT', Path(folder)):
            root = Path(folder)
            prior = root / '.decomp-lab' / 'retained'
            prior.mkdir(parents=True)
            sentinel = prior / 'evidence.json'
            sentinel.write_bytes(b'retained evidence')
            for output in (root / 'public', root / '.decomp-lab', prior, root / '.decomp-lab' / '..' / 'escaped'):
                with self.subTest(output=output), patch.object(bounds.n, 'evidence_dependencies') as dependencies, \
                        patch.object(bounds.n, 'load_program') as load:
                    with self.assertRaisesRegex(ValueError, 'fresh private output'):
                        bounds.verify(output, root / 'missing.exe', root / 'missing.elf')
                    dependencies.assert_not_called()
                    load.assert_not_called()
            self.assertEqual(sentinel.read_bytes(), b'retained evidence')

    def test_faults_change_one_reviewed_field_without_mutating_input(self):
        words = [0] * 27
        for index in range(4):
            words[index] = (24 << 6) | 3
        words[4], words[5] = 33 << 26, (35 << 26) | 8
        for index in range(6, 10):
            words[index] = 42
        code = struct.pack('<27I', *words)
        faults = bounds.fault_specifications(code)
        self.assertEqual(len(faults), 4)
        self.assertEqual(len({index for _, index, _ in faults}), 4)
        self.assertTrue(all(words[index] != replacement for _, index, replacement in faults))
        self.assertEqual(struct.unpack('<27I', code), tuple(words))
        self.assertEqual([word for _, _, word in faults], [(24 << 6) | 2, 37 << 26, (35 << 26) | 4, 43])

    def test_changed_fault_layout_requires_review(self):
        for code in (bytes(bounds.LENGTH), bytes(bounds.LENGTH - 4)):
            with self.subTest(size=len(code)), self.assertRaisesRegex(ValueError, 'Review controls'):
                bounds.fault_specifications(code)


if __name__ == '__main__':
    unittest.main()
