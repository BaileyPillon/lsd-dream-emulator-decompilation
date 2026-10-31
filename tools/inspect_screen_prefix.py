"""Qualify the shared runnable-screen view without inventing concrete tables.

This is a declaration and complete-code-byte audit, not a gameplay replay.
The four screen-specific callback addresses deliberately have no common callable
signature. Previously ELF/GNU-qualified target extents are reused and every byte
is compared with the canonical executable again.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import configure
from tools.inventory_vtables import collect, table_words

TYPE = 'game_flow_screen_vtable_t'
FIELDS = ('type_id', 'Destroy', 'ConstructAddress', 'CleanupAddress', 'Attach',
          'Detach', 'DetachAll', 'IterChildren', 'AddParent', 'RemoveParent',
          'ClearParents', 'IterParents', 'Notify', 'Nop', 'OnNotifyAddress',
          'Reserved_3C', 'InitializeAddress', 'Run')
SHARED = {4: ('Destroy', 'base_class_destructor', 0x80017EB0),
          0x10: ('Attach', 'base_class_attach', 0x80017F98),
          0x14: ('Detach', 'base_class_detach', 0x80017FF0),
          0x18: ('DetachAll', 'base_class_detach_all', 0x80018040),
          0x1C: ('IterChildren', 'base_class_iter_children', 0x800180BC),
          0x20: ('AddParent', 'base_class_add_parent', 0x800180FC),
          0x24: ('RemoveParent', 'base_class_remove_parent', 0x8001811C),
          0x28: ('ClearParents', 'base_class_clear_parents', 0x8001813C),
          0x2C: ('IterParents', 'base_class_iter_parents', 0x8001816C),
          0x30: ('Notify', 'base_class_notify', 0x800182CC),
          0x34: ('Nop', 'base_class_nop', 0x80018350)}
FAMILY_SPECIFIC = (8, 12, 0x38, 0x40)
TABLES = {
    'g_MAIN_MENU_VTABLE': dict(address=0x80086B60, type_id=0x1F130,
        specific=(0x8004D578, 0x8004D704, 0x8004D788, 0x8004D814), run=0x8003C1DC),
    'D_80087AAC': dict(address=0x80087AAC, type_id=0x2F130,
        specific=(0x80057FC8, 0x8003C008, 0x8003E030, 0x80058078), run=0x80058390)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique(items, key, description):
    result = {}
    for item in items:
        identity = item[key]
        require(identity not in result, 'Duplicate ' + description + ': ' + str(identity))
        result[identity] = item
    return result


def inspect(executable, inventory, catalogue):
    """Pure checker; synthetic tests do not need game files or a compiler."""
    views = unique(inventory['unbound_type_views'], 'type', 'unbound type')
    require(TYPE in views, 'The common screen view is missing or bound as a concrete table.')
    require(not any(row['type'] == TYPE for row in inventory['unsupported_types']),
            'The common view cannot be supported and unsupported at once.')
    view = views[TYPE]
    require(view['header'] == 'src/game/game_flow.h' and view['bytes'] == 0x48
            and view['concrete_table_binding_claimed'] is False,
            'Wrong common-view owner, extent or binding claim.')
    slots = view['slots']
    callable_offsets = set(SHARED) | {0x44}
    require(len(slots) == len(FIELDS), 'Incomplete common screen layout.')
    for index, (slot, name) in enumerate(zip(slots, FIELDS)):
        require(slot['offset'] == index * 4 and slot['field'] == name
                and type(slot['declared_function_pointer']) is bool
                and slot['declared_function_pointer'] == (index * 4 in callable_offsets),
                'Wrong common screen slot, field or callable classification.')
    tables = unique(inventory['tables'], 'name', 'concrete table')
    require(not any(row['type'] == TYPE for row in tables.values()),
            'An unbound view must not add a concrete table.')
    require('g_BASE_CLASS_VTABLE' in tables, 'Missing original base-class table.')
    base_table = tables['g_BASE_CLASS_VTABLE']
    require(int(base_table['address'], 16) == 0x8006B58C, 'Wrong original base table address.')
    base_words = table_words(executable, 0x8006B58C, 16)
    base = unique(base_table['slots'], 'offset', 'base slot')
    for offset, (field, _function, address) in SHARED.items():
        require(offset in base and base[offset]['field'] == field
                and base[offset]['declared_function_pointer'] is True
                and int(base[offset]['value'], 16) == address == base_words[offset // 4],
                'Shared base declaration or binding differs.')
    targets = unique(catalogue['targets'], 'pc', 'complete target')
    load = struct.unpack_from('<I', executable, 0x18)[0]
    qualified, observed = {}, []
    for name, spec in TABLES.items():
        require(name in tables, 'Missing concrete screen table: ' + name)
        table = tables[name]
        require(int(table['address'], 16) == spec['address'] and table['bytes'] >= 0x48,
                'Wrong original screen table address or extent.')
        concrete = unique(table['slots'], 'offset', 'screen slot')
        words = table_words(executable, spec['address'], len(FIELDS))
        expected = {0:spec['type_id'], 0x3C:0, 0x44:spec['run'],
                    **{offset:row[2] for offset,row in SHARED.items()},
                    **dict(zip(FAMILY_SPECIFIC, spec['specific']))}
        bindings = []
        for index, value in enumerate(words):
            offset = index * 4
            require(offset in concrete and value == expected[offset]
                    and int(concrete[offset]['value'], 16) == value,
                    'Original screen word or concrete declaration differs at ' + name + '+' + hex(offset))
            if offset in SHARED:
                require(concrete[offset]['field'] == SHARED[offset][0], 'Shared field name differs.')
            if offset == 0x44:
                require(concrete[offset]['field'] == 'Run', 'Wrong original Run slot name.')
            if offset in (0, 0x3C):
                continue
            require(concrete[offset]['declared_function_pointer'] is True,
                    'A concrete callback is not classified as callable.')
            pc = f'0x{value:08X}'
            require(pc in targets, 'Missing complete original target: ' + pc)
            target = targets[pc]
            size = target['function_bytes']
            start = 0x800 + value - load
            require(type(size) is int and size > 0 and size % 4 == 0
                    and start >= 0x800 and start + size <= len(executable),
                    'Invalid complete target extent.')
            body = executable[start:start+size]
            require(hashlib.sha256(body).hexdigest() == target['function_sha256'],
                    'A complete original target body differs: ' + target['function'])
            binding = dict(table=name, slot=f'0x{offset:03X}', field=concrete[offset]['field'])
            require(target['bindings'].count(binding) == 1, 'Missing or repeated original target binding.')
            if offset in SHARED:
                require(target['function'] == SHARED[offset][1], 'Wrong shared original function owner.')
            qualified[pc] = dict(function=target['function'], pc=pc, bytes=size,
                                 sha256=target['function_sha256'])
            bindings.append(dict(offset=offset, common_field=FIELDS[index],
                concrete_field=concrete[offset]['field'], target=pc,
                callable_through_common_view=offset in callable_offsets,
                family_specific_signature_retained=offset in FAMILY_SPECIFIC))
        observed.append(dict(table=name, address=f"0x{spec['address']:08X}",
            prefix_bytes=0x48, prefix_sha256=hashlib.sha256(struct.pack('<18I', *words)).hexdigest(),
            bindings=bindings, reserved_3C_is_null=True))
    return dict(schema_version=1, status='qualified_common_screen_prefix',
        common_type=TYPE, view_bytes=0x48, shared_inherited_callbacks=len(SHARED),
        newly_exposed_shared_callbacks=len(SHARED)-1, callable_common_slots=len(callable_offsets),
        screen_specific_address_slots=len(FAMILY_SPECIFIC), concrete_prefixes=observed,
        concrete_callback_bindings=sum(len(row['bindings']) for row in observed),
        complete_target_functions=len(qualified), complete_target_bytes=sum(row['bytes'] for row in qualified.values()),
        complete_targets=sorted(qualified.values(), key=lambda row:row['pc']),
        declared_tables=inventory['declared_tables_audited'],
        declared_function_slots=inventory['declared_function_slots'],
        unsupported_type_views=inventory['unsupported_types'],
        target_extent_provenance='Existing independently ELF/GNU-qualified catalogue; every scoped complete body rechecked against original bytes.',
        new_concrete_tables=0, new_C_bytes=0, model_API_calls=0, native_calls_observed=0,
        new_gameplay_features=0, whole_feature_groups_accepted=0,
        all_dynamic_dispatch_resolved=False, screen_specific_signature_review_complete=False,
        scope='Known main-menu/chart prefixes and shared base callbacks only. Native execution, all other receiver families, factory signatures, family-specific signatures and whole-game parity remain separate.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='New JSON file; existing evidence is preserved.')
    args = parser.parse_args()
    try:
        require(not args.output.exists(), 'Refusing to replace an existing audit.')
        inventory = collect()
        original = (ROOT/configure.ROM).read_bytes()
        catalogue_path = ROOT/'research/dispatch/target-catalogue.json'
        catalogue_bytes = catalogue_path.read_bytes()
        report = inspect(original, inventory, json.loads(catalogue_bytes))
        report.update(canonical_executable_sha256=hashlib.sha256(original).hexdigest(),
            build_evidence_sha256=inventory['evidence_sha256'],
            source_sha256={name:inventory['source_sha256'][name] for name in
                ('src/game/game_flow.h','src/base/base.h','src/menu/main_menu.h','src/menu/graph_screen.h')},
            inspector_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            inventory_producer_sha256=inventory['producer_sha256'],
            target_catalogue_sha256=hashlib.sha256(catalogue_bytes).hexdigest())
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')
        print(json.dumps({key:report[key] for key in ('status','declared_tables','newly_exposed_shared_callbacks',
            'concrete_callback_bindings','complete_target_functions','complete_target_bytes','new_C_bytes')}))
        return 0
    except (OSError, ValueError, KeyError, struct.error) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
