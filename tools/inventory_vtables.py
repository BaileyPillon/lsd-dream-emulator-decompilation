"""Audit declared native PS1 virtual tables against canonical executable words.

This inventories declarations, not every possible dynamic dispatch. It resolves
the original table bindings and checks explicit C initializers without treating
guessed field names or pointer signatures as verified semantics.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import configure
from tools.feature_inventory import mask_comments
from tools.progress import build_manifest, check_build_current


def fields_for_type(body):
    """Accept only four-byte scalar/pointer members of a PS1 vtable."""
    fields = []
    for declaration in body.split(';'):
        declaration = declaration.strip()
        if not declaration:
            continue
        function = re.search(r'\(\s*\*\s*(\w+)\s*\)', declaration)
        if function:
            fields.append({"name": function[1], "function_pointer": True})
            continue
        scalar = re.fullmatch(r'(?:u32|s32|int|unsigned\s+int|long|unsigned\s+long)\s+(\w+)', declaration)
        pointer = re.fullmatch(r'[\w\s]+\*\s*(\w+)', declaration)
        if not (scalar or pointer):
            raise ValueError("Unsupported native table member: " + declaration)
        fields.append({"name": (scalar or pointer)[1], "function_pointer": False})
    if not fields:
        raise ValueError("A native table needs declared members.")
    return fields


def split_initializer(body):
    entries, start, depth = [], 0, 0
    for index, char in enumerate(body):
        if char in '([{':
            depth += 1
        elif char in ')]}':
            depth -= 1
            if depth < 0:
                raise ValueError("Unbalanced table initializer.")
        elif char == ',' and depth == 0:
            entries.append(body[start:index].strip())
            start = index + 1
    tail = body[start:].strip()
    if tail:
        entries.append(tail)
    if depth or any(not entry for entry in entries):
        raise ValueError("Unbalanced or empty table initializer.")
    return entries


def initializer_value(expression, symbols):
    """Resolve literals and symbol pointers; never evaluate arbitrary C."""
    if expression in ('NULL', '0'):
        return 0
    if re.fullmatch(r'-?(?:0[xX][0-9a-fA-F]+|0[0-7]*|[1-9][0-9]*)[uUlL]*', expression):
        number = re.sub(r'[uUlL]+$', '', expression)
        unsigned = number.lstrip('-')
        radix = 16 if unsigned.lower().startswith('0x') else 8 if unsigned.startswith('0') else 10
        value = int(number, radix)
        if not -(1 << 31) <= value < (1 << 32):
            raise ValueError("Initializer is outside a native 32-bit word.")
        return value & 0xFFFFFFFF
    symbol = re.search(r'([A-Za-z_]\w*)\s*$', expression)
    # A function-pointer cast may contain commas and stars but no initializer
    # operators. The final identifier is the pointer's link-time symbol.
    if symbol and not re.search(r'[+\-/{}=]', expression):
        name = symbol[1]
        if expression[:symbol.start()].strip() in ('', '&') or expression.lstrip().startswith('('):
            if name == 'NULL':
                return 0
            if name in symbols:
                return symbols[name]
    raise ValueError("Unresolved C initializer: " + expression)


def indexed_initializers(expressions, fields):
    indexed, index = {}, 0
    for expression in expressions:
        designated = re.fullmatch(r'\.(\w+)\s*=\s*(.*)', expression, re.S)
        if designated:
            candidates = [number for number, field in enumerate(fields) if field['name'] == designated[1]]
            if len(candidates) != 1:
                raise ValueError("Unknown designated table member: " + designated[1])
            index = candidates[0]
            expression = designated[2]
        if index >= len(fields) or index in indexed:
            raise ValueError("Duplicate or out-of-bounds table initializer.")
        indexed[index] = expression
        index += 1
    return indexed


def parse_symbols(map_text, definition_texts=()):
    symbols = {}
    for address, name in re.findall(r'(?m)^\s*(0x[0-9a-fA-F]+)\s+([A-Za-z_]\w*)\s*$', map_text):
        value = int(address, 16)
        if name in symbols and symbols[name] != value:
            raise ValueError("Ambiguous linker symbol: " + name)
        symbols[name] = value
    for text in definition_texts:
        for name, address in re.findall(r'([A-Za-z_]\w*)\s*=\s*(0x[0-9a-fA-F]+)', text):
            value = int(address, 16)
            if name in symbols and symbols[name] != value:
                raise ValueError("Conflicting linker symbol: " + name)
            symbols[name] = value
    return symbols


def table_words(executable, address, count):
    if len(executable) < 0x800 or executable[:8] != b'PS-X EXE':
        raise ValueError("Expected a complete PS-X executable.")
    load = struct.unpack_from('<I', executable, 0x18)[0]
    offset = 0x800 + address - load
    if count < 1 or offset < 0x800 or offset + count * 4 > len(executable):
        raise ValueError("Table extent is outside the canonical executable.")
    return list(struct.unpack_from('<' + str(count) + 'I', executable, offset))


def assembly_table_extents(executable, assemblies, symbols):
    """Measure byte-checked assembly labels, which can include adjacent data."""
    extents = {}
    for path, content in assemblies.items():
        for match in re.finditer(r'(?m)^dlabel\s+(\w+)\s*\n(.*?)^enddlabel\s+\1\s*$', content, re.S):
            name, body = match[1], match[2]
            if name not in symbols:
                continue
            words = re.findall(r'/\*\s+[0-9A-Fa-f]+\s+([0-9A-Fa-f]+)\s+([0-9A-Fa-f]{8})\s*\*/\s*\.word', body)
            if not words:
                continue
            addresses = [int(address, 16) for address, _raw in words]
            start = symbols[name]
            # Splat may encode the type ID as a four-byte padded ASCII string.
            # All remaining table entries must be contiguous native words.
            if addresses[0] not in (start, start + 4) or any(right != left + 4 for left, right in zip(addresses, addresses[1:])):
                continue
            for address, raw in words:
                native = table_words(executable, int(address, 16), 1)[0].to_bytes(4, 'little')
                if native != bytes.fromhex(raw):
                    raise ValueError("Assembly data record disagrees with the original executable: " + name)
            size = addresses[-1] + 4 - start
            if name in extents and extents[name]['bytes'] != size:
                raise ValueError("Conflicting native table extents: " + name)
            extents[name] = {'bytes': size, 'assembly': path}
    return extents


def audit_tables(executable, sources, headers, symbols, native_extents=None):
    types, unsupported, declarations, definitions = {}, [], {}, {}
    pattern = re.compile(r'typedef\s+struct(?:\s+\w+)?\s*\{([^{}]*)\}\s*(\w*vtable\w*)\s*;', re.I)
    for path, content in headers.items():
        masked = mask_comments(content)
        matches = [(match[2], match[1]) for match in pattern.finditer(masked)]
        aliases = {tag: alias for tag, alias in re.findall(r'\btypedef\s+struct\s+(\w+)\s+(\w*vtable\w*)\s*;', masked, re.I)}
        for tag, body in re.findall(r'\bstruct\s+(\w*vtable\w*)\s*\{([^{}]*)\}\s*;', masked, re.I):
            matches.append((aliases.get(tag, tag), body))
        for type_name, body in matches:
            try:
                fields = fields_for_type(body)
                if type_name in types and types[type_name][1] != fields:
                    raise ValueError("Conflicting table type: " + type_name)
                types[type_name] = (path, fields)
            except ValueError as error:
                unsupported.append({"header": path, "type": type_name, "reason": str(error)})
    declaration_pattern = re.compile(r'\bextern\s+(\w*vtable\w*)\s+(\w+)\s*;', re.I)
    definition_pattern = re.compile(r'\b(\w*vtable\w*)\s+(\w+)\s*=\s*\{([^{}]*)\}\s*;', re.I | re.S)
    for path, content in {**headers, **sources}.items():
        masked = mask_comments(content)
        for match in declaration_pattern.finditer(masked):
            declarations.setdefault(match[2], set()).add((match[1], path))
        if path in sources:
            for match in definition_pattern.finditer(masked):
                declarations.setdefault(match[2], set()).add((match[1], path))
                if match[2] in definitions:
                    raise ValueError("Duplicate C table definition: " + match[2])
                definitions[match[2]] = (path, split_initializer(match[3]))
    names_by_address = {}
    for name, address in symbols.items():
        names_by_address.setdefault(address, []).append(name)
    tables, unresolved, layout_issues, extent_notes = [], [], [], []
    for name, refs in sorted(declarations.items()):
        names = {entry[0] for entry in refs}
        if len(names) != 1:
            raise ValueError("Conflicting table declarations: " + name)
        type_name = next(iter(names))
        if type_name not in types or name not in symbols:
            unresolved.append({"name": name, "type": type_name,
                               "reason": "No supported type or canonical linker symbol."})
            continue
        header, fields = types[type_name]
        declared_bytes = len(fields) * 4
        extent = (native_extents or {}).get(name)
        if extent and declared_bytes > extent['bytes']:
            layout_issues.append({'name': name, 'type': type_name, 'header': header,
                                  'declared_bytes': declared_bytes, 'native_bytes': extent['bytes'],
                                  'assembly': extent['assembly']})
            fields = fields[:extent['bytes'] // 4]
        elif extent and declared_bytes < extent['bytes']:
            # Reconstructed assembly labels are not original C type metadata.
            # For STR, the label also encloses four non-callback words. Never
            # invent callback members from the remaining label span.
            extra = table_words(executable, symbols[name] + declared_bytes,
                                (extent['bytes'] - declared_bytes) // 4)
            extent_notes.append({'name': name, 'header': header,
                                 'declared_bytes': declared_bytes,
                                 'assembly_label_bytes': extent['bytes'],
                                 'assembly': extent['assembly'],
                                 'words_after_declared_layout': [f'0x{word:08X}' for word in extra],
                                 'reason': 'Assembly label includes data beyond the declared layout; it does not prove additional callbacks.'})
        words = table_words(executable, symbols[name], len(fields))
        source, expressions = definitions.get(name, (None, None))
        if expressions is not None and len(expressions) > len(fields):
            raise ValueError("Initializer exceeds declared table: " + name)
        indexed = indexed_initializers(expressions, fields) if expressions is not None else None
        slots = []
        for index, (field, word) in enumerate(zip(fields, words)):
            slot = {"offset": index * 4, "field": field["name"],
                    "declared_function_pointer": field["function_pointer"],
                    "value": f"0x{word:08X}",
                    "linker_symbols": sorted(names_by_address.get(word, [])) if word else []}
            if expressions is not None:
                expression = indexed.get(index, '0')
                expected = initializer_value(expression, symbols)
                if expected != word:
                    raise ValueError(f"C/native binding mismatch: {name}+0x{index:X} ({expression}).")
                slot.update(c_initializer=expression, initializer_matches_native=True)
            slots.append(slot)
        tables.append({"name": name, "type": type_name, "address": f"0x{symbols[name]:08X}",
                       "header": header, "declarations": sorted({entry[1] for entry in refs}),
                       "c_source": source, "bytes": len(words) * 4, "slots": slots,
                       "header_declared_bytes": declared_bytes,
                       "observed_assembly_label_extent": extent,
                       "c_initializer_verified": expressions is not None})
    callbacks = [slot for table in tables for slot in table['slots']
                 if slot['declared_function_pointer'] and slot['value'] != '0x00000000']
    bound_types = {type_name for refs in declarations.values() for type_name, _ in refs}
    unbound = [{"type": type_name, "header": header, "bytes": len(fields) * 4,
                "slots": [{"offset": index * 4, "field": field['name'],
                           "declared_function_pointer": field['function_pointer']}
                          for index, field in enumerate(fields)],
                "concrete_table_binding_claimed": False}
               for type_name, (header, fields) in sorted(types.items())
               if type_name not in bound_types]
    return {"tables": tables, "unsupported_types": unsupported, "unresolved_declarations": unresolved,
            "unbound_type_views": unbound,
            "header_layout_issues": layout_issues,
            "assembly_extent_notes": extent_notes,
            "declared_tables_audited": len(tables),
            "explicit_c_initializers_verified": sum(table["c_initializer_verified"] for table in tables),
            "declared_function_slots": sum(slot["declared_function_pointer"] for table in tables for slot in table["slots"]),
            "nonnull_declared_function_slots": len(callbacks),
            "unique_declared_function_addresses": len({slot['value'] for slot in callbacks}),
            "unnamed_declared_function_addresses": sorted({slot['value'] for slot in callbacks if not slot['linker_symbols']}),
            "all_dynamic_dispatch_resolved": False, "game_feature_total": None,
            "scope": "Declared four-byte PS1 table members; header names and signatures require semantic review."}


def collect():
    if check_build_current(ROOT) is not True:
        raise ValueError('A current matching build is required; run configure.py and ninja check first.')
    paths = [ROOT / configure.ROM, ROOT / configure.EXE, ROOT / configure.MAP_FILE,
             ROOT / configure.UNDEF_FUNCS, ROOT / configure.UNDEF_SYMS, ROOT / configure.SYMBOLS]
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    original = paths[0].read_bytes()
    expected = (ROOT / configure.EXE_HASH).read_text().split()[0].lower()
    if hashlib.sha1(original).hexdigest() != expected or paths[1].read_bytes() != original:
        raise ValueError("Original and built executable must match the canonical SHA-1.")
    sources = {name: (ROOT / name).read_text() for name, kind in build_manifest() if kind == 'C'}
    headers = {path.relative_to(ROOT).as_posix(): path.read_text()
               for path in (ROOT / 'src').rglob('*.h') if 'psyq' not in path.parts}
    assemblies = {name: (ROOT / name).read_text() for name, kind in build_manifest() if kind == 'data'}
    source_hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in {**sources, **headers, **assemblies}}
    symbols = parse_symbols(paths[2].read_text(), [path.read_text() for path in paths[3:]])
    extents = assembly_table_extents(original, assemblies, symbols)
    report = audit_tables(original, sources, headers, symbols, extents)
    if any(hashlib.sha256(path.read_bytes()).hexdigest() != value for path, value in ((Path(key), val) for key, val in before.items())):
        raise ValueError("Executable or linker evidence changed during the audit.")
    if any(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != value for name, value in source_hashes.items()):
        raise ValueError("Source declarations changed during the audit; retry on a stable snapshot.")
    if check_build_current(ROOT) is not True:
        raise ValueError('Build inputs changed during the audit; refresh and retry.')
    report.update(timestamp_utc=datetime.now(timezone.utc).isoformat(), canonical_sha1=expected,
                  source_sha256=source_hashes,
                  evidence_sha256={Path(path).relative_to(ROOT).as_posix(): value for path, value in before.items()},
                  producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  canonical_runtime_changed=False, model_api_calls=0)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='New JSON file; existing files are preserved.')
    args = parser.parse_args()
    try:
        report = collect()
        with Path(args.output).open('x', encoding='utf-8') as output:
            json.dump(report, output, indent=2)
            output.write('\n')
        print(f"{report['declared_tables_audited']} declared tables; "
              f"{report['explicit_c_initializers_verified']} C initializers verified; "
              f"{len(report['header_layout_issues'])} header layout issues; "
              f"{len(report['unresolved_declarations'])} unresolved declarations.")
        return 0
    except (OSError, ValueError) as error:
        print('[!] ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
