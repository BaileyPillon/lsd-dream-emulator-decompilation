"""Owned ELF/PS-X fixtures for complete original-callback catalogue boundaries."""
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import decomp_workbench, export_npc_catalogue as tool


WORDS = bytes.fromhex('0800e0030000000021104000')


def executable(words=WORDS):
    data = bytearray(0x800)
    data[:8] = b'PS-X EXE'
    struct.pack_into('<II', data, 0x18, 0x80010000, len(words))
    return bytes(data) + words


def elf(words=WORDS, functions=(('entity_alpha', 0, 8),)):
    section_names = b'\0.text\0.symtab\0.strtab\0.shstrtab\0'
    strings, symbols = bytearray(b'\0'), bytearray(16)
    for name, offset, size in functions:
        name_offset = len(strings)
        strings.extend(name.encode() + b'\0')
        symbols.extend(struct.pack('<IIIBBH', name_offset, 0x80010000 + offset, size, 0x12, 0, 1))
    data = bytearray(52)
    data[:7] = b'\x7fELF\x01\x01\x01'
    struct.pack_into('<HHI', data, 16, 2, 8, 1)
    payloads = (words, symbols, strings, section_names)
    offsets = []
    for payload in payloads:
        offsets.append(len(data))
        data.extend(payload)
    shoff = len(data)
    struct.pack_into('<I', data, 32, shoff)
    struct.pack_into('<6H', data, 40, 52, 0, 0, 40, 5, 4)
    sections = ((0,) * 10,
        (1, 1, 6, 0x80010000, offsets[0], len(words), 0, 0, 4, 0),
        (7, 2, 0, 0, offsets[1], len(symbols), 3, 1, 4, 16),
        (15, 3, 0, 0, offsets[2], len(strings), 0, 0, 1, 0),
        (23, 3, 0, 0, offsets[3], len(section_names), 0, 0, 1, 0))
    for section in sections:
        data.extend(struct.pack('<10I', *section))
    return bytes(data)


def binding(index=0, name='entity_alpha', pc='0x80010000'):
    return dict(index=index, callback_function=name, callback_address=pc)


class NpcCatalogueTests(unittest.TestCase):
    def ranges(self, records=None, image=None, linked=None, symbols=None):
        return tool.callback_ranges(executable() if image is None else image,
            elf() if linked is None else linked, [binding()] if records is None else records,
            tool.nm_functions('80010000 00000008 T entity_alpha\n') if symbols is None else symbols)

    def test_complete_span_and_shared_binding_ids_are_retained(self):
        rows = self.ranges([binding(7), binding(2), binding(3, None, '0x00000000')])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['entity_ids'], [2, 7])
        self.assertEqual(rows[0]['function_bytes'], 8)
        self.assertEqual(rows[0]['function_sha256'], hashlib.sha256(WORDS[:8]).hexdigest())
        self.assertEqual(rows[0]['entry_instruction_sha256'], hashlib.sha256(WORDS[:4]).hexdigest())

    def test_changed_tail_is_rejected_even_when_entry_instruction_agrees(self):
        changed = WORDS[:4] + b'FAIL' + WORDS[8:]
        with self.assertRaisesRegex(ValueError, 'complete callback differs'):
            self.ranges(image=executable(changed))

    def test_GNU_extent_must_agree_with_sized_ELF(self):
        for symbols in ({'entity_alpha': [(0x80010000, 4)]},
                        {'entity_alpha': [(0x80010004, 8)]}):
            with self.subTest(symbols=symbols), self.assertRaisesRegex(ValueError, 'GNU and ELF'):
                self.ranges(symbols=symbols)

    def test_missing_and_duplicate_GNU_symbols_are_rejected(self):
        for symbols in ({}, {'entity_alpha': [(0x80010000, 8)] * 2}):
            with self.subTest(symbols=symbols), self.assertRaisesRegex(ValueError, 'GNU and ELF'):
                self.ranges(symbols=symbols)

    def test_stripped_ELF_has_no_guessed_extent_fallback(self):
        data = bytearray(elf())
        shoff = struct.unpack_from('<I', data, 32)[0]
        struct.pack_into('<I', data, shoff + 2 * 40 + 4, 0)
        with self.assertRaisesRegex(ValueError, 'static symbol table'):
            self.ranges(linked=bytes(data))

    def test_callback_address_must_match_the_actual_ELF_symbol(self):
        for pc in ('0x80010002', '0x80010004', '80010000', '0x800100000'):
            with self.subTest(pc=pc), self.assertRaises(ValueError):
                self.ranges([binding(pc=pc)])

    def test_duplicate_and_invalid_entity_ids_are_rejected(self):
        for records in ([binding(), binding()], [binding(-1)], [binding(True)], [binding(65536)]):
            with self.subTest(records=records), self.assertRaisesRegex(ValueError, 'Entity IDs'):
                self.ranges(records)

    def test_two_source_names_cannot_share_one_watched_PC(self):
        with self.assertRaisesRegex(ValueError, 'ambiguous source names'):
            self.ranges([binding(), binding(1, 'entity_alias')])

    def test_overlapping_complete_function_ranges_are_rejected(self):
        functions = (('entity_alpha', 0, 8), ('entity_beta', 4, 8))
        symbols = tool.nm_functions('80010000 00000008 T entity_alpha\n80010004 00000008 T entity_beta\n')
        with self.assertRaisesRegex(ValueError, 'ranges overlap'):
            self.ranges([binding(), binding(1, 'entity_beta', '0x80010004')],
                        linked=elf(functions=functions), symbols=symbols)

    def test_null_binding_and_nonempty_catalogue_are_required(self):
        for records in ([], [binding(0, 'entity_alpha', '0x00000000')],
                        [binding(0, None, '0x00000000')], [binding(0, None)]):
            with self.subTest(records=records), self.assertRaises(ValueError):
                self.ranges(records)

    def test_executable_payload_extent_cannot_be_extended_by_appended_data(self):
        image = bytearray(executable())
        struct.pack_into('<I', image, 0x1C, 4)
        with self.assertRaisesRegex(ValueError, 'outside the executable payload'):
            self.ranges(image=bytes(image))

    def test_symbolic_link_preserves_existing_diagnostic_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / 'candidate-symbols.elf'
            path.write_bytes(b'earlier evidence')
            with patch.object(decomp_workbench.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'Existing symbol diagnostics'):
                    decomp_workbench.diagnostic_image(root, root / 'source.ld', [], root / 'game.exe')
            run.assert_not_called()
            self.assertEqual(path.read_bytes(), b'earlier evidence')

    def test_public_output_is_rejected_before_build_or_game_inspection(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / 'public-export'
            with patch.object(tool.sys, 'platform', 'linux'), patch.object(tool.Path, 'cwd', return_value=tool.ROOT), \
                    patch.object(tool, 'check_build_current') as current:
                with self.assertRaisesRegex(ValueError, 'fresh private directory'):
                    tool.export(destination)
            current.assert_not_called()
            self.assertFalse(destination.exists())
