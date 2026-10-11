"""Byte-check original NPC properties and callback bindings against matching C.

This reads the canonical PS1 executable and the current entity initializer.
It exports original game data for human/AI analysis; it makes no model calls,
changes no game inputs and does not claim runtime coverage of callback branches.
"""

import argparse
from collections import Counter
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
from tools.feature_inventory import locate_functions, mask_comments
from tools.inventory_vtables import initializer_value, parse_symbols, split_initializer
from tools.progress import check_build_current, fallback_functions
from tools.psx_image import ORIGINAL_SHA1, executable_offset

SOURCE = "src/scene/entity.c"
HEADER = "src/scene/entity.h"
TABLE = "g_ENTITY_TABLE"
RECORD_BYTES = 16
PROPERTY_NAMES = ("mood_x", "mood_y", "unlock", "behaviour", "interaction_type",
                  "interaction_range", "interaction_angle", "link_stage",
                  "event_video_id", "interaction_param", "proximity", "link_flag")


def signed_byte_literal(expression):
    """Accept native s8 literals, including C octal, without executing C."""
    if not re.fullmatch(r'-?(?:0[xX][0-9a-fA-F]+|0[0-7]*|[1-9][0-9]*)', expression):
        raise ValueError("Unsupported signed-byte property: " + expression)
    unsigned = expression.lstrip('-')
    radix = 16 if unsigned.lower().startswith('0x') else 8 if unsigned.startswith('0') else 10
    value = int(expression, radix)
    if not -128 <= value <= 127:
        raise ValueError("Property is outside the declared s8 range: " + expression)
    return value


def entity_initializers(source, symbols):
    text = mask_comments(source)
    matches = list(re.finditer(r'\bentity_prop_t\s+g_ENTITY_TABLE\s*\[\s*(\d+)\s*\]\s*=\s*\{(.*?)\}\s*;', text, re.S))
    if len(matches) != 1:
        raise ValueError("Expected exactly one explicit entity property-table initializer.")
    count = int(matches[0][1])
    if not 1 <= count <= 65536:
        raise ValueError("Entity table capacity is outside the audit bound.")
    entries = split_initializer(matches[0][2])
    if len(entries) != count:
        raise ValueError("Entity initializer count does not equal its declared capacity.")
    records = []
    for index, expression in enumerate(entries):
        if not expression.startswith('{') or not expression.endswith('}'):
            raise ValueError("Entity initializer must use explicit record braces.")
        fields = split_initializer(expression[1:-1])
        if len(fields) != 12 or not fields[0].startswith('{') or not fields[0].endswith('}'):
            raise ValueError("Entity record needs a mood pair, ten s8 fields and one callback.")
        mood = split_initializer(fields[0][1:-1])
        if len(mood) != 2:
            raise ValueError("Entity mood needs exactly two signed axes.")
        properties = [signed_byte_literal(field) for field in mood + fields[1:11]]
        callback = fields[11]
        if not re.fullmatch(r'NULL|0|[A-Za-z_]\w*', callback):
            raise ValueError("Entity callback must be a named symbol or a null literal.")
        address = initializer_value(callback, symbols)
        if address and (address % 4 or not callback.startswith('entity_')):
            raise ValueError("Entity callback is not an aligned named entity function.")
        records.append({"index": index, "properties": dict(zip(PROPERTY_NAMES, properties)),
                        "callback_function": callback if address else None,
                        "callback_address": address,
                        "bytes": struct.pack('<12bI', *properties, address)})
    return records


def verify_layout(header):
    matches = list(re.finditer(r'typedef\s+struct\s*\{([^{}]+)\}\s*entity_prop_t\s*;', mask_comments(header), re.S))
    expected = ('s8mood_effect[2];s8unlock;s8behaviour;s8interaction_type;'
                's8interaction_range;s8interaction_angle;s8link_stage;'
                's8event_video_id;s8interaction_param;s8proximity;s8link_flag;'
                'void(*behaviour_fn)(entity_t*This,s32*arg1);')
    if len(matches) != 1 or re.sub(r'\s+', '', matches[0][1]) != expected:
        raise ValueError("Unsupported entity_prop_t layout; review the native 16-byte record first.")


def audit_entities(executable, source, symbols):
    records = entity_initializers(source, symbols)
    if TABLE not in symbols:
        raise ValueError("Entity property-table linker symbol is absent.")
    address = symbols[TABLE]
    if address % 4:
        raise ValueError("Entity property table must be four-byte aligned.")
    size = len(records) * RECORD_BYTES
    offset = executable_offset(executable, address, size)
    native = executable[offset:offset + size]
    index = locate_functions({SOURCE: source})
    fallbacks = fallback_functions(source)
    callbacks = {}
    serializable = []
    for record in records:
        start = record['index'] * RECORD_BYTES
        if record['bytes'] != native[start:start + RECORD_BYTES]:
            raise ValueError(f"Entity C/native property or callback mismatch at record {record['index']}.")
        name, callback_address = record['callback_function'], record['callback_address']
        if callback_address:
            executable_offset(executable, callback_address, 4)
            locations = index.get(name, [])
            if len(locations) != 1:
                raise ValueError("Callback must have one configured C or assembly definition: " + name)
            callback = callbacks.setdefault(callback_address, {
                "address": f"0x{callback_address:08X}", "names": [], "entity_indices": [],
                "source_definitions": [], "recovered_c": True,
                "runtime_validated": False,
            })
            if name not in callback['names']:
                callback['names'].append(name)
                callback['source_definitions'].append({"function": name, "source": locations[0][0], "line": locations[0][1]})
            callback['entity_indices'].append(record['index'])
            callback['recovered_c'] = callback['recovered_c'] and name not in fallbacks
        output = {key: value for key, value in record.items() if key != 'bytes'}
        output['callback_address'] = f"0x{callback_address:08X}"
        output['initializer_matches_native'] = True
        serializable.append(output)
    nonnull = sum(bool(record['callback_address']) for record in records)
    return {
        "table": {"name": TABLE, "address": f"0x{address:08X}", "file_offset": offset,
                  "record_bytes": RECORD_BYTES, "bytes": size, "sha256": hashlib.sha256(native).hexdigest(),
                  "source": SOURCE, "all_initializers_match_native": True},
        "totals": {"property_records": len(records), "nonnull_callback_slots": nonnull,
                   "null_callback_slots": len(records) - nonnull, "distinct_callback_addresses": len(callbacks),
                   "distinct_callback_names": len({record['callback_function'] for record in records if record['callback_function']}),
                   "distinct_callbacks_recovered_c": sum(callback['recovered_c'] for callback in callbacks.values()),
                   "runtime_validated_callbacks": 0},
        "property_histograms": {name: dict(sorted(Counter(record['properties'][name] for record in records).items()))
                                for name in PROPERTY_NAMES},
        "records": serializable,
        "callbacks": sorted(callbacks.values(), key=lambda record: record['address']),
        "scope": "Original entity property bytes and callback bindings. Names are recovered source labels; state/RNG/input branches need runtime review.",
        "original_behavior_modified": False, "model_api_calls": 0, "game_feature_total": None,
    }


def collect():
    if check_build_current(ROOT) is not True:
        raise ValueError("A current matching build is required; run configure.py and ninja check first.")
    paths = [ROOT / configure.ROM, ROOT / configure.EXE, ROOT / configure.MAP_FILE,
             ROOT / configure.UNDEF_FUNCS, ROOT / configure.UNDEF_SYMS, ROOT / configure.SYMBOLS,
             ROOT / SOURCE, ROOT / HEADER, Path(__file__)]
    dependencies = ["tools/inventory_vtables.py", "tools/feature_inventory.py", "tools/progress.py", "tools/psx_image.py"]
    paths += [ROOT / name for name in dependencies]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    original = paths[0].read_bytes()
    if hashlib.sha1(original).hexdigest() != ORIGINAL_SHA1 or paths[1].read_bytes() != original:
        raise ValueError("Original and built executable must equal the canonical SHA-1.")
    verify_layout((ROOT / HEADER).read_text())
    symbols = parse_symbols(paths[2].read_text(), [path.read_text() for path in paths[3:6]])
    report = audit_entities(original, (ROOT / SOURCE).read_text(), symbols)
    if any(hashlib.sha256(path.read_bytes()).hexdigest() != expected for path, expected in before.items()):
        raise ValueError("Entity source/build evidence changed during the audit; retry on a stable snapshot.")
    if check_build_current(ROOT) is not True:
        raise ValueError("Build inputs changed during the audit; refresh and retry.")
    report.update(schema_version=1, timestamp_utc=datetime.now(timezone.utc).isoformat(),
                  canonical_sha1=ORIGINAL_SHA1,
                  evidence_sha256={path.relative_to(ROOT).as_posix(): digest for path, digest in before.items()},
                  producer_sha256=before[Path(__file__)], canonical_runtime_changed=False)
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
        counts = report['totals']
        print(f"{counts['property_records']} original entity records; {counts['nonnull_callback_slots']} nonnull slots, "
              f"{counts['distinct_callback_addresses']} distinct callback addresses; "
              f"{counts['distinct_callbacks_recovered_c']} C bodies. Runtime callback acceptance remains 0.")
        return 0
    except (OSError, ValueError) as error:
        print('[!] ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
