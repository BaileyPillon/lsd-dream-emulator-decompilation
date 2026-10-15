"""Synthetic guards for complete-function comparison and private evidence paths."""
from pathlib import Path
import hashlib
import struct
import tempfile
import unittest
from unittest.mock import patch

from research.compiler import compare_function as tool
from tools import decomp_workbench as workbench


class WorkbenchFunctionDiagnosticsTests(unittest.TestCase):
    WORDS = bytes.fromhex('0800e00300000000')

    def entry(self):
        return {'function': 'example', 'address': '0x80010000', 'file_offset': 0,
                'bytes': len(self.WORDS), 'sha256': hashlib.sha256(self.WORDS).hexdigest()}

    def run_diagnostic(self, folder, emitted=None, executable=None, entry=None):
        root = Path(folder)
        binary = root / 'candidate.exe'
        image = self.WORDS + b'owned data'
        binary.write_bytes(image)
        calls = []

        def run(command, **kwargs):
            self.assertTrue(kwargs['check'])
            calls.append(command)
            if command[0].endswith('objcopy'):
                Path(command[-1]).write_bytes(image if executable is None else executable)
            else:
                Path(command[command.index('-o') + 1]).write_bytes(
                    fixture(self.WORDS) if emitted is None else emitted)

        objects = [Path('build/src/retained.c.o'), root / 'candidate.o']
        with patch.object(workbench.subprocess, 'run', side_effect=run):
            result = workbench.diagnostic_function(
                self.entry() if entry is None else entry, self.WORDS, root,
                root / 'candidate.ld', objects, binary)
        return result, calls

    def test_actual_symbols_require_complete_candidate_image_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            before = list(workbench.configure.LD_FLAGS)
            result, calls = self.run_diagnostic(folder)
        self.assertTrue(result['selected_function_bytes_equal'])
        self.assertTrue(result['diagnostic_image_matches_candidate'])
        self.assertEqual(result['candidate_executable_sha256'], result['diagnostic_executable_sha256'])
        self.assertFalse(result['complete_executable_verified'])
        self.assertFalse(result['source_promoted'])
        self.assertEqual(workbench.configure.LD_FLAGS, before)
        self.assertEqual(result['diagnostic_link_flags'], [flag for flag in before if flag != '-s'])
        self.assertNotIn('-s', calls[0])
        self.assertEqual(calls[0][-2], str(Path('build/src/retained.c.o')))
        self.assertEqual(calls[0][-1], str(Path(folder) / 'candidate.o'))

    def test_matching_symbol_cannot_hide_changed_or_appended_executable_bytes(self):
        for image in (self.WORDS + b'wrong data', self.WORDS + b'owned data!'):
            with self.subTest(image=image), tempfile.TemporaryDirectory() as folder:
                with self.assertRaisesRegex(ValueError, 'complete candidate image'):
                    self.run_diagnostic(folder, executable=image)

    def test_actual_function_extent_cannot_be_replaced_by_reference_length(self):
        with tempfile.TemporaryDirectory() as folder:
            result, _ = self.run_diagnostic(folder, emitted=fixture(self.WORDS + b'\0' * 4))
        self.assertEqual(result['candidate_bytes'], 12)
        self.assertEqual(result['length_difference'], 4)
        self.assertFalse(result['selected_function_bytes_equal'])

    def test_missing_symbol_table_has_no_fabricated_boundary_fallback(self):
        data = bytearray(fixture(self.WORDS))
        section_table = struct.unpack_from('<I', data, 32)[0]
        struct.pack_into('<I', data, section_table + 2 * 40 + 4, 0)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                self.run_diagnostic(folder, emitted=bytes(data))

    def test_changed_reference_evidence_is_rejected_before_linking(self):
        entry = self.entry()
        entry['sha256'] = '0' * 64
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'Original function evidence'):
                self.run_diagnostic(folder, entry=entry)
            self.assertFalse((Path(folder) / 'candidate-symbols.elf').exists())

    def test_unexpected_strip_configuration_is_rejected(self):
        for flags in (['-nostdlib'], ['-s', '--strip-all']):
            with self.subTest(flags=flags), tempfile.TemporaryDirectory() as folder:
                with patch.object(workbench.configure, 'LD_FLAGS', flags):
                    with self.assertRaisesRegex(ValueError, 'exactly one symbol-strip'):
                        self.run_diagnostic(folder)


def fixture(words, name='example', extra=b''):
    names = b'\0.text\0.symtab\0.strtab\0.shstrtab\0'
    symbols = b'\0' * 16 + struct.pack('<IIIBBH', 1, 0x80010000, len(words), 0x12, 0, 1)
    strings = b'\0' + name.encode() + b'\0'
    data = bytearray(52)
    data[:7] = b'\x7fELF\x01\x01\x01'
    struct.pack_into('<HHI', data, 16, 2, 8, 1)
    payloads = [words + extra, symbols, strings, names]
    offsets = []
    for payload in payloads:
        offsets.append(len(data))
        data.extend(payload)
    shoff = len(data)
    struct.pack_into('<I', data, 32, shoff)
    struct.pack_into('<6H', data, 40, 52, 0, 0, 40, 5, 4)
    rows = [(0,) * 10,
            (1, 1, 6, 0x80010000, offsets[0], len(payloads[0]), 0, 0, 4, 0),
            (7, 2, 0, 0, offsets[1], len(symbols), 3, 1, 4, 16),
            (15, 3, 0, 0, offsets[2], len(strings), 0, 0, 1, 0),
            (23, 3, 0, 0, offsets[3], len(names), 0, 0, 1, 0)]
    for row in rows:
        data.extend(struct.pack('<10I', *row))
    return bytes(data)


class FunctionComparisonTests(unittest.TestCase):
    def test_exact_complete_function_is_not_full_image_acceptance(self):
        words = bytes.fromhex('0800e00300000000')
        result = tool.compare(fixture(words), words, 'example', 0x80010000)
        self.assertTrue(result['selected_function_bytes_equal'])
        self.assertTrue(result['elf_qualification']['function_covers_complete_section'])
        self.assertFalse(result['source_promoted'])
        self.assertFalse(result['complete_executable_verified'])

    def test_prefix_match_does_not_hide_extra_function_words(self):
        words = bytes.fromhex('0800e00300000000')
        result = tool.compare(fixture(words + b'\0' * 4), words, 'example', 0x80010000)
        self.assertFalse(result['selected_function_bytes_equal'])
        self.assertEqual(result['differing_bytes'], 4)
        self.assertEqual(result['changed_words'][0]['kind'], 'function_extent_changed')

    def test_other_section_bytes_are_reported_outside_function_scope(self):
        words = bytes.fromhex('0800e00300000000')
        result = tool.compare(fixture(words, extra=b'\xff' * 4), words, 'example', 0x80010000)
        self.assertTrue(result['selected_function_bytes_equal'])
        self.assertFalse(result['elf_qualification']['function_covers_complete_section'])
        self.assertEqual(result['elf_qualification']['section_bytes'], 12)

    def test_reordered_words_remain_nonmatching(self):
        original = struct.pack('<3I', 0x27bdfff0, 0xafbf000c, 0x00808021)
        candidate = original[4:] + original[:4]
        result = tool.compare(fixture(candidate), original, 'example', 0x80010000)
        self.assertFalse(result['selected_function_bytes_equal'])
        self.assertEqual(result['contiguous_runs_with_same_instruction_multiset'], [{'offset': 0, 'words': 3}])

    def test_commutative_swap_is_reported_without_accepting_bytes(self):
        left = struct.pack('<I', (9 << 21) | (4 << 16) | (2 << 11) | 0x21)
        right = struct.pack('<I', (4 << 21) | (9 << 16) | (2 << 11) | 0x21)
        result = tool.compare(fixture(right), left, 'example', 0x80010000)
        self.assertEqual(result['changed_words'][0]['kind'], 'commutative_register_operands_swapped')
        self.assertFalse(result['selected_function_bytes_equal'])

    def test_relocatable_wrong_architecture_and_big_endian_rejected(self):
        original = fixture(b'\0' * 4)
        for offset, value in ((16, 1), (18, 3), (5, 2)):
            with self.subTest(offset=offset):
                data = bytearray(original)
                if offset == 5:
                    data[offset] = value
                else:
                    struct.pack_into('<H', data, offset, value)
                with self.assertRaises(ValueError):
                    tool.elf_function(bytes(data), 'example', 0x80010000)

    def test_unsized_or_out_of_section_function_rejected(self):
        original = fixture(b'\0' * 4)
        shoff = struct.unpack_from('<I', original, 32)[0]
        symbol_offset = struct.unpack_from('<I', original, shoff + 2 * 40 + 16)[0]
        for size in (0, 3, 8):
            with self.subTest(size=size):
                data = bytearray(original)
                struct.pack_into('<I', data, symbol_offset + 16 + 8, size)
                with self.assertRaises(ValueError):
                    tool.elf_function(bytes(data), 'example', 0x80010000)

    def test_missing_function_and_address_mismatch_rejected(self):
        data = fixture(b'\0' * 4)
        for name, address in (('absent', 0x80010000), ('example', 0x80010004)):
            with self.subTest(name=name, address=address):
                with self.assertRaises(ValueError):
                    tool.elf_function(data, name, address)

    def test_truncated_sections_and_names_rejected(self):
        data = fixture(b'\0' * 4)
        for truncated in (data[:20], data[:-1]):
            with self.assertRaises(ValueError):
                tool.elf_function(truncated, 'example', 0x80010000)

    def test_public_path_rejected_before_input_read(self):
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('input read too early')):
            with self.assertRaises(ValueError):
                tool.main(['--elf', 'absent.elf', '--function', 'example', '--address', '0x80010000',
                           '--bytes', '4', '--output', str(tool.ROOT / 'docs/unsafe.json')])

    def test_existing_report_and_traversal_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            lab = Path(tmp) / 'lab'
            lab.mkdir()
            existing = lab / 'existing.json'
            existing.write_text('retained')
            with self.assertRaises(FileExistsError):
                tool.require_output(existing, lab)
            self.assertEqual(existing.read_text(), 'retained')
            with self.assertRaises(ValueError):
                tool.require_output(lab / '../outside.json', lab)
            with self.assertRaises(ValueError):
                tool.require_output(lab / 'report.c', lab)

    def test_cli_retains_inputs_and_writes_only_fresh_private_report(self):
        words = bytes.fromhex('0800e00300000000')
        rom = bytearray(505856)
        rom[:8] = b'PS-X EXE'
        struct.pack_into('<I', rom, 0x18, 0x80010000)
        rom[0x800:0x800 + len(words)] = words
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'rom').mkdir()
            original = root / 'rom/SLPS_015.56'
            original.write_bytes(rom)
            candidate = root / 'candidate.elf'
            candidate.write_bytes(fixture(words))
            output = root / '.decomp-lab/report.json'
            arguments = ['--elf', str(candidate), '--function', 'example', '--address', '0x80010000',
                         '--bytes', str(len(words)), '--output', str(output)]
            with patch.object(tool, 'ROOT', root), patch.object(tool, 'CANONICAL_SHA256', tool.digest(rom)), patch('builtins.print'):
                self.assertEqual(tool.main(arguments), 0)
                self.assertTrue(output.exists())
                self.assertEqual(original.read_bytes(), rom)
                self.assertEqual(candidate.read_bytes(), fixture(words))
                with self.assertRaises(FileExistsError):
                    tool.main(arguments)

    def test_noncanonical_game_rejected_without_creating_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'rom').mkdir()
            (root / 'rom/SLPS_015.56').write_bytes(b'wrong reference')
            output = root / '.decomp-lab/report.json'
            with patch.object(tool, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'canonical'):
                    tool.main(['--elf', str(root / 'absent.elf'), '--function', 'example',
                               '--address', '0x80010000', '--bytes', '4', '--output', str(output)])
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
