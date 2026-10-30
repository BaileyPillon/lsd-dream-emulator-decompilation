"""Owned PS-X/ELF fixtures and executed failure controls for recovered-C context."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import configure
from tools import decomp_workbench as workbench
from tools.export_function_ranges import index_ranges
from tools.original_functions import INDEX, instruction_listing, reference_entry
from tests.test_npc_catalogue import WORDS, elf, executable

GNU = {'entity_alpha': [(0x80010000, 8)], 'entity_beta': [(0x80010008, 4)]}
LISTING = '80010000: 03e00008 jr ra\n80010004: 00000000 nop\n'


def index(image=None, linked=None, symbols=None):
    return index_ranges(executable() if image is None else image,
        elf(functions=(('entity_alpha', 0, 8), ('entity_beta', 8, 4))) if linked is None else linked,
        GNU if symbols is None else symbols, 'entity_alpha', 0x80010000)


class OriginalFunctionTests(unittest.TestCase):
    def test_all_sized_ranges_use_ELF_and_GNU_extents(self):
        result = index()
        self.assertEqual(result['qualified_function_count'], 2)
        self.assertEqual([(r['function'], r['file_offset'], r['bytes']) for r in result['functions']],
                         [('entity_alpha', 0x800, 8), ('entity_beta', 0x808, 4)])
        self.assertEqual(result['functions'][0]['sha256'], hashlib.sha256(WORDS[:8]).hexdigest())
        self.assertNotIn('instructions', json.dumps(result))

    def test_changed_tail_is_rejected_despite_unchanged_entry_word(self):
        with self.assertRaisesRegex(ValueError, 'complete linked function differs'):
            index(image=executable(WORDS[:4] + b'FAIL' + WORDS[8:]))

    def test_missing_duplicate_or_incorrect_GNU_extents_fail(self):
        for values in ({}, {'entity_alpha': [(0x80010000, 4)]},
                       {'entity_alpha': [(0x80010000, 8)] * 2}):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, 'GNU and ELF'):
                index(symbols=values)

    def test_zero_sized_tail_does_not_gain_a_neighbor_inferred_extent(self):
        result = index(linked=elf(functions=(('entity_alpha', 0, 8), ('entity_beta', 8, 0))))
        self.assertEqual(result['qualified_function_count'], 1)
        with self.assertRaisesRegex(ValueError, 'unambiguous sized function'):
            reference_entry(result, 'entity_beta', executable())

    def test_duplicate_local_names_are_excluded_without_selecting_one(self):
        result = index(linked=elf(functions=(('entity_alpha', 0, 4),
            ('local_name', 4, 4), ('local_name', 8, 4))),
            symbols={'entity_alpha': [(0x80010000, 4)]})
        self.assertEqual(result['excluded_ambiguous_or_non_C_names'], ['local_name'])
        self.assertEqual(result['qualified_function_count'], 1)

    def test_foreign_executable_or_duplicate_reference_fails(self):
        result = index()
        with self.assertRaisesRegex(ValueError, 'canonical executable'):
            reference_entry(result, 'entity_alpha', executable(WORDS + b'EXTR'))
        result['functions'].append(dict(result['functions'][0]))
        with self.assertRaisesRegex(ValueError, 'unambiguous sized function'):
            reference_entry(result, 'entity_alpha', executable())

    def test_offsets_sizes_alignment_and_hashes_are_checked(self):
        for change in ({'file_offset': 0}, {'file_offset': 0x804}, {'bytes': 0},
                       {'bytes': True}, {'bytes': 7}, {'bytes': 16},
                       {'address': '0x80010002'}, {'sha256': '0' * 64}):
            result = copy.deepcopy(index())
            result['functions'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                reference_entry(result, 'entity_alpha', executable())

    def test_every_disassembled_word_is_verified_including_zeroes(self):
        entry = reference_entry(index(), 'entity_alpha', executable())
        text = instruction_listing(LISTING, entry, executable())
        self.assertEqual(workbench.assembly_evidence(text, 'entity_alpha', executable())['bytes'], 8)
        self.assertIn('00000000', text)
        for bad in (LISTING.splitlines()[0], LISTING.replace('80010004', '80010008'),
                    LISTING.replace('03e00008', '0800e003'),
                    LISTING + '80010008: 00401021 move v0,v0\n'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                instruction_listing(bad, entry, executable())


class RecoveredContextTests(unittest.TestCase):
    def fixture(self, root):
        for name in ('src', 'rom', 'config', 'research'):
            (root / name).mkdir()
        (root / 'src/example.c').write_text('#include "example.h"\nint entity_alpha(int x) { return x; }\n', encoding='utf-8')
        (root / 'src/example.h').write_text('/* déclaration */\nint entity_alpha(int);\n', encoding='utf-8')
        (root / configure.ROM).write_bytes(executable())
        (root / configure.EXE_HASH).write_text(hashlib.sha1(executable()).hexdigest() + '\n', encoding='utf-8')
        (root / INDEX).write_text(json.dumps(index()), encoding='utf-8')

    def test_fresh_checkout_with_no_ASM_or_private_catalog_exports_C_context(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            self.fixture(root)
            output = root / '.decomp-lab/fresh'
            with patch.object(workbench, 'ROOT', root), patch.object(workbench, 'build_manifest', return_value=[('src/example.c', 'C')]), \
                 patch.object(workbench, 'find_objdump', return_value='synthetic-objdump'), \
                 patch.object(workbench.subprocess, 'run', return_value=SimpleNamespace(stdout=LISTING)) as run:
                result = workbench.context_bundle('entity_alpha', output)
            self.assertEqual(result['function']['evidence_kind'], 'verified_function_index')
            self.assertEqual(result['function']['source_state'], 'recovered_C')
            self.assertFalse((root / '.decomp-lab/remaining-game-functions.json').exists())
            self.assertFalse(result['matching_proof'])
            self.assertFalse(result['gameplay_tested'])
            self.assertFalse(result['ai_model_invoked'])
            self.assertEqual((output / 'original-function.bin').read_bytes(), WORDS[:8])
            for row in result['evidence']:
                self.assertEqual(hashlib.sha256((output / row['bundle_file']).read_bytes()).hexdigest(), row['sha256'])
            prompt = (output / 'PROMPT.md').read_text(encoding='utf-8')
            self.assertIn('documented upstream compatibility storage', prompt)
            self.assertIn('whole executable byte match', ' '.join(prompt.split()))
            self.assertNotIn('Do not add padding', prompt)
            self.assertIn('-z', run.call_args.args[0])
            self.assertEqual((output / 'headers/src/example.h').read_bytes(), (root / 'src/example.h').read_bytes())

    def test_ambiguous_current_definition_fails_before_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            self.fixture(root)
            (root / 'src/other.c').write_text('int entity_alpha(int x) { return x; }\n', encoding='utf-8')
            output = root / '.decomp-lab/fresh'
            with patch.object(workbench, 'ROOT', root), patch.object(workbench, 'build_manifest', return_value=[('src/example.c', 'C'), ('src/other.c', 'C')]):
                with self.assertRaisesRegex(ValueError, 'exactly one configured definition'):
                    workbench.context_bundle('entity_alpha', output)
            self.assertFalse(output.exists())

    def test_missing_disassembler_fails_before_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            self.fixture(root)
            output = root / '.decomp-lab/fresh'
            with patch.object(workbench, 'ROOT', root), patch.object(workbench, 'build_manifest', return_value=[('src/example.c', 'C')]), \
                 patch.object(workbench, 'find_objdump', side_effect=ValueError('MIPS objdump missing')):
                with self.assertRaisesRegex(ValueError, 'MIPS objdump missing'):
                    workbench.context_bundle('entity_alpha', output)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
