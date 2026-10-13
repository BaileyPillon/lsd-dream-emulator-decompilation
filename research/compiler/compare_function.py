"""Compare a complete linked MIPS function with the canonical game privately."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
CANONICAL_SHA256 = '282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def elf_function(data, function, address):
    """Require an unstripped linked ELF32 LE MIPS function with its full extent."""
    if len(data) < 52 or data[:7] != b'\x7fELF\x01\x01\x01':
        raise ValueError('Require ELF32 little-endian version 1.')
    kind, machine, version = struct.unpack_from('<HHI', data, 16)
    if (kind, machine, version) != (2, 8, 1):
        raise ValueError('Require a linked MIPS executable, not a relocatable object.')
    shoff = struct.unpack_from('<I', data, 32)[0]
    header_size, _, _, entry_size, count, names_index = struct.unpack_from('<6H', data, 40)
    if header_size != 52 or entry_size != 40 or not 0 < names_index < count:
        raise ValueError('Invalid or unsupported ELF section table.')
    if shoff < 52 or shoff + entry_size * count > len(data):
        raise ValueError('Truncated ELF section table.')
    sections = [struct.unpack_from('<10I', data, shoff + index * 40) for index in range(count)]

    def contents(index):
        if not 0 <= index < count:
            raise ValueError('Section index outside ELF table.')
        section = sections[index]
        if section[1] == 8 or section[4] + section[5] > len(data):
            raise ValueError('Section payload absent or truncated.')
        return data[section[4]:section[4] + section[5]]

    def string(strings, offset):
        if not 0 <= offset < len(strings):
            raise ValueError('ELF string offset outside its table.')
        end = strings.find(b'\0', offset)
        if end < 0:
            raise ValueError('Unterminated ELF string.')
        try:
            return strings[offset:end].decode('ascii')
        except UnicodeDecodeError as error:
            raise ValueError('Unsupported non-ASCII ELF name.') from error

    if sections[names_index][1] != 3:
        raise ValueError('Invalid section-name string table.')
    section_names = contents(names_index)
    symbol_tables = [index for index, section in enumerate(sections) if section[1] == 2]
    if len(symbol_tables) != 1:
        raise ValueError('Require exactly one static symbol table; stripped ELF is insufficient.')
    table = sections[symbol_tables[0]]
    if table[9] != 16 or table[5] % 16:
        raise ValueError('Invalid ELF symbol-table extent.')
    if not 0 <= table[6] < count or sections[table[6]][1] != 3:
        raise ValueError('Invalid symbol-name string table.')
    symbols, names = contents(symbol_tables[0]), contents(table[6])
    selected, functions = [], []
    for offset in range(0, len(symbols), 16):
        name_offset, value, size, info, _, section_index = struct.unpack_from('<IIIBBH', symbols, offset)
        name = string(names, name_offset)
        if name == function:
            selected.append((value, size, info & 15, section_index))
        if info & 15 == 2 and size and 0 < section_index < count:
            functions.append({'function': name, 'address': f'0x{value:08X}', 'bytes': size,
                              'section_index': section_index})
    if len(selected) != 1:
        raise ValueError('Selected function must have exactly one symbol.')
    value, size, symbol_kind, section_index = selected[0]
    if symbol_kind != 2 or not size or size % 4 or value != address or value % 4:
        raise ValueError('Require a sized, aligned function at the requested address.')
    if not 0 < section_index < count:
        raise ValueError('Selected function is undefined or lacks a file-backed section.')
    section = sections[section_index]
    if section[1] != 1 or section[2] & 6 != 6:
        raise ValueError('Selected function must reside in allocated executable program bytes.')
    start = value - section[3]
    if start < 0 or start + size > section[5]:
        raise ValueError('Complete function extent lies outside its text section.')
    text = contents(section_index)
    return text[start:start + size], {
        'section': string(section_names, section[0]), 'section_index': section_index,
        'section_address': f'0x{section[3]:08X}', 'section_bytes': len(text),
        'function_offset_in_section': start, 'function_bytes': size,
        'function_covers_complete_section': start == 0 and size == len(text),
        'other_sized_functions': [item for item in functions if item['function'] != function],
    }


def word_fields(word):
    value = int.from_bytes(word, 'little')
    return {'opcode': value >> 26, 'rs': value >> 21 & 31, 'rt': value >> 16 & 31,
            'rd': value >> 11 & 31, 'shift': value >> 6 & 31, 'function': value & 63,
            'immediate': value & 0xffff}


def difference_kind(original, candidate):
    left, right = word_fields(original), word_fields(candidate)
    if (left['opcode'] == right['opcode'] == 0 and
            left['function'] == right['function'] and left['function'] in (0x21, 0x24, 0x25, 0x26) and
            left['rd'] == right['rd'] and left['shift'] == right['shift'] == 0 and
            (left['rs'], left['rt']) == (right['rt'], right['rs'])):
        return 'commutative_register_operands_swapped'
    if left['opcode'] != right['opcode']:
        return 'opcode_changed'
    if left['opcode'] != 0 and (left['rs'], left['rt']) == (right['rs'], right['rt']):
        return 'immediate_or_target_bits_changed'
    return 'instruction_fields_changed'


def compare(elf, original, function, address):
    if not original or len(original) % 4:
        raise ValueError('Original function must have a nonzero whole-instruction extent.')
    candidate, qualification = elf_function(elf, function, address)
    different = []
    for offset in range(0, max(len(original), len(candidate)), 4):
        left, right = original[offset:offset + 4], candidate[offset:offset + 4]
        if left == right:
            continue
        different.append({'offset': offset, 'address': f'0x{address + offset:08X}',
                          'original_word_le': left.hex() if left else None,
                          'candidate_word_le': right.hex() if right else None,
                          'kind': difference_kind(left, right) if left and right else 'function_extent_changed'})
    runs = []
    for item in different:
        if runs and item['offset'] == runs[-1][-1]['offset'] + 4:
            runs[-1].append(item)
        else:
            runs.append([item])
    reordered = []
    for run in runs:
        if len(run) > 1 and all(item['original_word_le'] and item['candidate_word_le'] for item in run):
            if sorted(item['original_word_le'] for item in run) == sorted(item['candidate_word_le'] for item in run):
                reordered.append({'offset': run[0]['offset'], 'words': len(run)})
    return {'function': function, 'address': f'0x{address:08X}',
            'elf_sha256': digest(elf), 'original_function_sha256': digest(original),
            'candidate_function_sha256': digest(candidate), 'original_bytes': len(original),
            'candidate_bytes': len(candidate), 'length_difference': len(candidate) - len(original),
            'original_extent_supplied_by_caller': True,
            'differing_bytes': sum(a != b for a, b in zip(original, candidate)) + abs(len(original) - len(candidate)),
            'selected_function_bytes_equal': original == candidate,
            'elf_qualification': qualification, 'changed_words': different,
            'contiguous_runs_with_same_instruction_multiset': reordered,
            'source_promoted': False, 'complete_executable_verified': False,
            'scope': 'Complete linked candidate function versus the supplied original span. Original symbol/extent authority must be checked separately. Instruction reordering is not a semantic or timing acceptance. Full image equality and source ownership remain required.'}


def require_output(path, lab):
    path, lab = Path(path).resolve(), Path(lab).resolve()
    if path == lab or not path.is_relative_to(lab) or path.suffix.lower() != '.json':
        raise ValueError('Use a fresh .json report inside .decomp-lab; raw words must remain private.')
    if path.exists():
        raise FileExistsError('Existing evidence cannot be overwritten.')
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', required=True, type=Path)
    parser.add_argument('--function', required=True)
    parser.add_argument('--address', required=True, type=lambda value: int(value, 0))
    parser.add_argument('--bytes', required=True, type=lambda value: int(value, 0))
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    # Reject public paths and overwrites before accessing the game or candidate.
    output = require_output(args.output, ROOT / '.decomp-lab')
    if not 0 <= args.address <= 0xffffffff or not 0 < args.bytes <= 505856 or args.bytes % 4:
        raise ValueError('Invalid original address or instruction extent.')
    rom = (ROOT / 'rom/SLPS_015.56').read_bytes()
    if len(rom) != 505856 or digest(rom) != CANONICAL_SHA256 or rom[:8] != b'PS-X EXE':
        raise ValueError('The original executable is not the canonical LSD reference.')
    load_address = struct.unpack_from('<I', rom, 0x18)[0]
    offset = 0x800 + args.address - load_address
    if offset < 0x800 or offset + args.bytes > len(rom):
        raise ValueError('Original function extent lies outside the executable payload.')
    elf = args.elf.read_bytes()
    report = compare(elf, rom[offset:offset + args.bytes], args.function, args.address)
    report.update(original_executable_sha256=digest(rom), original_file_offset=offset,
                  producer_sha256=digest(Path(__file__).read_bytes()), model_api_calls=0)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({key: report[key] for key in ('function', 'original_bytes', 'candidate_bytes',
        'differing_bytes', 'selected_function_bytes_equal', 'source_promoted', 'complete_executable_verified')}))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, struct.error) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
