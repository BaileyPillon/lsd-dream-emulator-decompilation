"""Inspect reachable objects and NPC registration in a recorded dream checkpoint.

This reads an existing cold-start capture. It never controls an emulator or
executes a game callback. Registration and loaded objects are not execution
coverage, visibility, an encounter, or whole-game acceptance.
"""

import argparse
from collections import Counter, deque
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import configure
from tools.compare_cold_start import OBSERVER_SHA256, TRACE_FIELDS, physical, read_tsv, validate_ram
from tools.inventory_entities import audit_entities, verify_layout
from tools.inventory_vtables import parse_symbols
from tools.psx_image import ORIGINAL_SHA1, executable_offset
from tools.runtime_inputs import load_verified_manifest, record_file

ENTITY_VTABLE = 0x80089AD4
MAX_OBJECTS = 8192
MAX_LIST_NODES = 65536


def require(condition, message):
    if not condition:
        raise ValueError(message)


def word(raw, offset):
    require(type(offset) is int and offset % 4 == 0 and 0 <= offset <= len(raw) - 4,
            'Unaligned or truncated native word.')
    return struct.unpack_from('<I', raw, offset)[0]


def linked_values(raw, head):
    """Read one native list; object-graph cycles are separate and permitted."""
    values, seen = [], set()
    while head:
        node = physical(head, 8)
        require(node not in seen, 'A native linked list contains a cycle.')
        require(len(seen) < MAX_LIST_NODES, 'Native list exceeds the inspection bound.')
        seen.add(node)
        value = word(raw, node + 4)
        physical(value, 12)
        values.append(value)
        head = word(raw, node)
    return values


def walk_objects(raw, roots, executable):
    require(len(raw) == 0x200000, 'The checkpoint must contain complete MainRAM.')
    require(roots, 'At least one owner-qualified graph root is required.')
    pending, objects = deque(roots.values()), {}
    while pending:
        address = pending.popleft()
        if address in objects:
            continue
        require(len(objects) < MAX_OBJECTS, 'Object graph exceeds the inspection bound.')
        offset = physical(address, 12)
        vtable = word(raw, offset)
        table_offset = physical(vtable, 16)
        original_offset = executable_offset(executable, vtable, 16)
        require(raw[table_offset:table_offset + 16] == executable[original_offset:original_offset + 16],
                'A reachable object has a changed native vtable prefix.')
        children = linked_values(raw, word(raw, offset + 4))
        parents = linked_values(raw, word(raw, offset + 8))
        objects[address] = dict(address=address, vtable=vtable, children=children, parents=parents)
        pending.extend(children)
    edges = 0
    for parent, record in objects.items():
        for child, count in Counter(record['children']).items():
            require(objects[child]['parents'].count(parent) == count,
                    'A child edge lacks its reciprocal parent entry.')
            edges += count
    return dict(roots=roots, objects=list(objects.values()), object_count=len(objects),
                child_edges_checked=edges,
                vtable_prefix_bytes_checked_per_object=16,
                vtable_counts={f'0x{key:08X}': count for key, count in
                               sorted(Counter(record['vtable'] for record in objects.values()).items())})


def inspect_entities(raw, graph, dream_address, entity_audit, executable):
    table = entity_audit['table']
    table_address = int(table['address'], 16)
    table_offset = physical(table_address, table['bytes'])
    original_offset = executable_offset(executable, table_address, table['bytes'])
    require(raw[table_offset:table_offset + table['bytes']] ==
            executable[original_offset:original_offset + table['bytes']],
            'The recorded entity property table differs from the original.')
    records, entities = entity_audit['records'], []
    for node in graph['objects']:
        if node['vtable'] != ENTITY_VTABLE:
            continue
        address = node['address']
        offset = physical(address, 0x108)
        entity_id = word(raw, offset + 0x98)
        require(entity_id < len(records), 'A reachable entity has an invalid original ID.')
        require(word(raw, offset + 0x94) == dream_address, 'A reachable entity has a different dream owner.')
        prop = records[entity_id]
        state = struct.unpack_from('<i', raw, offset + 0x9C)[0]
        active = word(raw, offset + 0xF8)
        require(active in (0, 1), 'An entity has an unsupported behavior-active value.')
        context = None
        if state > 0:
            require(state == entity_id + 1, 'An enabled context has a different entity ID.')
            require(word(raw, offset + 0xA4) == address, 'An enabled context has a different entity owner.')
            callback = word(raw, offset + 0xA8)
            expected = int(prop['callback_address'], 16)
            context = dict(state=state, tick=word(raw, offset + 0xA0), owner=address,
                           callback=callback, matches_original_binding=callback == expected,
                           callback_cleared=callback == 0)
        entities.append(dict(address=address, entity_id=entity_id, dream_owner=dream_address,
            declared_callback=prop['callback_function'], declared_callback_address=prop['callback_address'],
            behavior_active=bool(active), context_state=state, context_enabled=state > 0, registered_context=context,
            model_binding=word(raw, offset + 0x5C)))
    return dict(entities=entities, loaded_entity_objects=len(entities),
                distinct_entity_ids=sorted({row['entity_id'] for row in entities}),
                enabled_contexts=sum(row['context_enabled'] for row in entities),
                behavior_active_objects=sum(row['behavior_active'] for row in entities),
                instruction_entries_observed=0, whole_NPC_encounters_accepted=0)


def inspect_capture(folder, frame):
    folder = Path(folder).resolve(strict=True)
    require(type(frame) is int and 0 <= frame <= 30000, 'Choose a recorded cold-start frame.')
    source_paths = [ROOT / configure.ROM, ROOT / configure.MAP_FILE, ROOT / configure.UNDEF_FUNCS,
                    ROOT / configure.UNDEF_SYMS, ROOT / configure.SYMBOLS,
                    ROOT / 'src/scene/entity.c', ROOT / 'src/scene/entity.h', Path(__file__)]
    source_paths += [ROOT / path for path in ('tools/compare_cold_start.py', 'tools/inventory_entities.py',
        'tools/inventory_vtables.py', 'tools/feature_inventory.py', 'tools/progress.py',
        'tools/psx_image.py', 'tools/runtime_inputs.py')]
    capture_paths = [folder / 'inputs.json', folder / 'cold-start.tsv', folder / 'captures.tsv',
                     folder / f'mainram-{frame}.bin']
    before = [record_file(path) for path in source_paths + capture_paths]
    manifest = load_verified_manifest(folder)
    require(manifest is not None and manifest.get('schema_version') == 2
            and manifest.get('scenario') == 'boot' and manifest.get('start_kind') == 'cold_boot'
            and manifest['script']['sha256'] == OBSERVER_SHA256,
            'A pinned capture from the supported cold-start observer is required.')
    executable = source_paths[0].read_bytes()
    require(hashlib.sha1(executable).hexdigest() == ORIGINAL_SHA1, 'Use the canonical local executable.')
    symbols = parse_symbols(source_paths[1].read_text(), [path.read_text() for path in source_paths[2:5]])
    verify_layout(source_paths[6].read_text())
    entity_audit = audit_entities(executable, source_paths[5].read_text(), symbols)
    _, observations = read_tsv(folder / 'cold-start.tsv', TRACE_FIELDS)
    selected = [row for row in observations if int(row['relative_frame']) == frame]
    require(len(selected) == 1, 'The checkpoint needs exactly one matching native observation.')
    row = selected[0]
    _, captures = read_tsv(folder / 'captures.tsv', ('relative_frame', 'core_frame', 'reason'))
    selected_captures = [item for item in captures if int(item['relative_frame']) == frame]
    require(len(selected_captures) == 1 and selected_captures[0]['core_frame'] == row['core_frame'],
            'The complete RAM capture needs its matching recorded boundary.')
    raw = (folder / f'mainram-{frame}.bin').read_bytes()
    validate_ram(raw, row)
    require(row['screen_kind'] == 'unlocked_dream', 'Select an owner-qualified unlocked dream checkpoint.')
    roots = {name: 0x80000000 + int(row[name]) for name in ('dream', 'session', 'map_scene')}
    graph = walk_objects(raw, roots, executable)
    inventory = inspect_entities(raw, graph, roots['dream'], entity_audit, executable)
    require([record_file(path) for path in source_paths + capture_paths] == before,
            'Source or capture evidence changed during inspection.')
    return dict(schema_version=1, status='inspected_recorded_dream_scene',
        recorded_utc=datetime.now(timezone.utc).isoformat(), relative_frame=frame,
        core_frame=int(row['core_frame']), graph=graph, **inventory, evidence=before,
        game_RAM_modified=False, emulator_controlled=False, game_functions_executed=0,
        new_C_bytes=0, whole_feature_groups_accepted=0,
        scope='Reachable object links, immutable vtable prefixes, original entity properties and current '
              'registration at one recorded boundary. Disabled context payload is not interpreted. '
              'No callback execution, visibility, encounter, frame continuity or complete replay acceptance.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-folder', type=Path, required=True)
    parser.add_argument('--frame', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New private JSON report; existing files are preserved.')
    args = parser.parse_args(argv)
    require(not args.output.exists(), 'Choose a new output path.')
    report = inspect_capture(args.capture_folder, args.frame)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({key: report[key] for key in
        ('status', 'relative_frame', 'loaded_entity_objects', 'distinct_entity_ids', 'enabled_contexts')}))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
