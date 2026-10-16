"""Source preparation uses synthetic files and preserves every original input."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from research.render_bounds.prepare_candidate import prepare


class BoundsSourceRecipeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'src/scene/render_context.c'
        self.fragment = self.root / 'research/render_bounds/bounds_candidate.c'
        self.source.parent.mkdir(parents=True)
        self.fragment.parent.mkdir(parents=True)
        self.source.write_text('''#include "scene/render_context.h"
s32 func_8004CD38(const render_context_cell_bounds_t *bounds, const u8 *point);
void caller(void) { func_8004CD38(This->m_NextSlotExclusionBounds, point); }
INCLUDE_ASM("asm/nonmatchings/scene/render_context", func_8004CD38);
void successor(void) { }
''', encoding='utf-8')
        self.fragment.write_text('s32 func_8004CD38(s32 address, const u8 *point) { return address == 0; }\n', encoding='utf-8')

    def test_complete_candidate_and_manifest_preserve_inputs(self):
        before = {path: path.read_bytes() for path in (self.source, self.fragment)}
        destination = self.root / '.decomp-lab/attempt'
        report = prepare(destination, root=self.root)
        candidate = (destination / 'render_context.c').read_text(encoding='utf-8')
        self.assertIn('s32 func_8004CD38(s32, const u8 *);', candidate)
        self.assertIn('func_8004CD38((s32) This->m_NextSlotExclusionBounds, point)', candidate)
        self.assertIn(self.fragment.read_text(encoding='utf-8').strip(), candidate)
        self.assertNotIn('INCLUDE_ASM(', candidate)
        self.assertTrue(candidate.endswith('void successor(void) { }\n'))
        self.assertEqual(json.loads((destination / 'recipe.json').read_text()), report)
        self.assertEqual(report['candidate_sha256'], hashlib.sha256(candidate.encode()).hexdigest())
        self.assertFalse(report['matching_verified'])
        self.assertFalse(report['native_behavior_verified'])
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_existing_destination_and_inputs_are_untouched(self):
        destination = self.root / '.decomp-lab/attempt'
        destination.mkdir(parents=True)
        sentinel = destination / 'render_context.c'
        sentinel.write_bytes(b'keep prior research\x00')
        before = {path: path.read_bytes() for path in (self.source, self.fragment, sentinel)}
        with self.assertRaises(ValueError):
            prepare(destination, root=self.root)
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_public_and_lab_root_destinations_are_rejected(self):
        for destination in (self.root / 'public-attempt', self.root / '.decomp-lab'):
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                prepare(destination, root=self.root)
            self.assertFalse(destination.exists())

    def test_changed_source_contract_is_rejected_before_writes(self):
        baseline = self.source.read_text(encoding='utf-8')
        for old, replacement in (
                ('s32 func_8004CD38(', 'u32 renamed_bounds('),
                ('INCLUDE_ASM(', 'REMOVED_ASSEMBLY('),
                ('This->m_NextSlotExclusionBounds', 'This->changed_bounds')):
            with self.subTest(contract=old):
                self.source.write_text(baseline.replace(old, replacement, 1), encoding='utf-8')
                destination = self.root / '.decomp-lab/attempt'
                with self.assertRaises(ValueError):
                    prepare(destination, root=self.root)
                self.assertFalse(destination.exists())
        self.source.write_text(baseline + baseline, encoding='utf-8')
        with self.assertRaises(ValueError):
            prepare(self.root / '.decomp-lab/attempt', root=self.root)
        self.assertFalse((self.root / '.decomp-lab/attempt').exists())

    def test_wrong_or_assembly_fragment_is_rejected(self):
        for fragment in ('s32 different_function(void) { return 1; }\n',
                         's32 func_8004CD38(s32 a, const u8 *b) { return 1; }\nINCLUDE_ASM("x", other);\n'):
            with self.subTest(fragment=fragment):
                self.fragment.write_text(fragment, encoding='utf-8')
                with self.assertRaises(ValueError):
                    prepare(self.root / '.decomp-lab/attempt', root=self.root)
                self.assertFalse((self.root / '.decomp-lab/attempt').exists())


if __name__ == '__main__':
    unittest.main()
