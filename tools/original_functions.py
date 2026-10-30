"""Validate original function metadata and complete GNU instruction listings."""
import hashlib
import json
from pathlib import Path
import re

from tools.psx_image import executable_offset

INDEX = 'research/original-functions.json'
IDENTIFIER = re.compile(r'[A-Za-z_]\w*', re.ASCII)
WORD = re.compile(r'^\s*([0-9a-fA-F]+):\s+([0-9a-fA-F]{8})\s+(.+?)\s*$', re.M)


def reference_entry(index, function, original):
    """A selected range must belong to the exact executable and PS-X mapping."""
    if not IDENTIFIER.fullmatch(function):
        raise ValueError('Select a C function identifier.')
    if (index.get('schema_version') != 1 or
            index.get('kind') != 'original_LSD_function_ranges' or
            index.get('canonical_executable_sha256') != hashlib.sha256(original).hexdigest()):
        raise ValueError('The function index does not identify this canonical executable.')
    matches = [row for row in index.get('functions', []) if row.get('function') == function]
    if len(matches) != 1:
        raise ValueError('The original function index needs one unambiguous sized function: ' + function)
    entry = dict(matches[0])
    address, size, offset = (entry.get(key) for key in ('address', 'bytes', 'file_offset'))
    if (not isinstance(address, str) or re.fullmatch(r'0x[0-9A-Fa-f]{8}', address) is None or
            type(size) is not int or size <= 0 or size % 4 or
            type(offset) is not int or offset < 0 or int(address, 16) % 4):
        raise ValueError('The original function needs a positive aligned complete extent.')
    if executable_offset(original, int(address, 16), size) != offset:
        raise ValueError('Function file offset and PS-X load address disagree.')
    if hashlib.sha256(original[offset:offset + size]).hexdigest() != entry.get('sha256'):
        raise ValueError('The function index disagrees with the original function bytes.')
    entry['instructions'] = size // 4
    entry['evidence_kind'] = 'verified_function_index'
    return entry


def read_reference(path, function, original):
    return reference_entry(json.loads(Path(path).read_text(encoding='utf-8')), function, original)


def instruction_listing(text, entry, original):
    """Reject omitted, reordered, truncated or wrong-endian disassembler words."""
    address, offset = int(entry['address'], 16), entry['file_offset']
    data = original[offset:offset + entry['bytes']]
    rows = WORD.findall(text)
    if len(rows) != entry['bytes'] // 4:
        raise ValueError('GNU disassembly must list every original instruction, including zero words.')
    lines = [f"# Verified original range; GNU mnemonics are analysis, not original C.\nglabel {entry['function']}"]
    for index, (pc, word, mnemonic) in enumerate(rows):
        encoded = int(word, 16).to_bytes(4, 'little')
        if int(pc, 16) != address + 4 * index or encoded != data[4 * index:4 * index + 4]:
            raise ValueError('GNU instruction address or bytes disagree with the original range.')
        lines.append(f'    /* {offset + 4 * index:X} {address + 4 * index:08X} {encoded.hex().upper()} */ {mnemonic}')
    lines.append(f"endlabel {entry['function']}\n")
    return '\n'.join(lines)
