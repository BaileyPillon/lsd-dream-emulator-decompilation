"""Qualify original entity-engine entries from retained native observations.

Use byte-checked method ranges and the verified NPC catalogue. A checked engine
entry is not a registered callback dispatch or whole encounter acceptance.
Disabled context payload is never returned as a meaningful clock or binding.
"""
import hashlib
import struct

from tools.npc_catalogue_trace import CATALOGUE_FIELDS
from tools.psx_image import executable_offset
from tools.replay_cold_start_headless import require

CALLER_METHODS = {'entity_init', 'entity_start', 'entity_stop', 'entity_update'}


def method_ranges(value, executable, expected_names):
    """Validate complete ranges; names require separately reviewed symbols."""
    require(isinstance(value, dict) and value.get('schema_version') == 1 and
            value.get('canonical_executable_sha256') == hashlib.sha256(executable).hexdigest(),
            'Method catalogue executable identity differs.')
    rows = value.get('methods')
    require(isinstance(rows, list) and all(isinstance(row, dict) for row in rows) and len(rows) == len(expected_names) and
            {row.get('name') for row in rows} == set(expected_names),
            'Method catalogue identities differ from the reviewed set.')
    result = {}
    for row in rows:
        address, size = row.get('address'), row.get('bytes')
        require(type(address) is int and type(size) is int and address % 4 == size % 4 == 0 and size > 0,
                'Each method needs an aligned complete function range.')
        at = executable_offset(executable, address, size)
        require(hashlib.sha256(executable[at:at + size]).hexdigest() == row.get('sha256'),
                'A complete original method span differs: ' + row['name'])
        require(address not in result, 'Repeated original method PC.')
        result[address] = dict(row)
    ordered = sorted(result.values(), key=lambda row: row['address'])
    require(all(left['address'] + left['bytes'] <= right['address'] for left, right in zip(ordered, ordered[1:])),
            'Original method ranges overlap.')
    return result


def qualify_engine_entry(row, executable, methods, callers, targets):
    """Check one parsed native row for an entity with a verified callback.

    `methods` and `callers` come from method_ranges; `targets` comes from
    catalogue_targets. The saved return address identifies a checked original
    call instruction. Unreviewed caller names stay unknown. This function does
    not validate a recording's complete outputs, event ordering or rooted RAM.
    """
    require(set(row) == set(CATALOGUE_FIELDS) and all(type(v) is int for v in row.values()),
            'A complete parsed native engine row is required.')
    require(0 <= row['relative_frame'] <= 30000 and 0 <= row['timestamp'] < 2**63 and
            all(0 <= row[key] < 2**32 for key in CATALOGUE_FIELDS if key not in ('relative_frame', 'timestamp')),
            'Native engine values are outside their recorded widths.')
    pc = row['pc']
    require(pc in methods, 'The entry is not a reviewed engine target.')
    at = executable_offset(executable, pc, 4)
    require(struct.unpack_from('<I', executable, at)[0] == row['instruction'],
            'Original engine entry instruction differs.')
    require(row['entity_vtable'] == 0x80089AD4 and row['entity'] % 4 == 0 and
            0x80010000 <= row['entity'] <= 0x80200000 - 0x108,
            'Unsupported original entity type or owner address.')
    require(row['sp'] % 4 == 0 and 0x80010000 <= row['sp'] < 0x80200000,
            'Invalid original engine stack pointer.')
    bindings = [address for address, target in targets.items() if row['entity_id'] in target['entity_ids']]
    require(len(bindings) == 1, 'The entity has no unique verified original callback binding.')
    # sound_entity_update executes only when the original signed state is > 0.
    enabled = 0 < row['context_state'] < 0x80000000
    if enabled:
        require(row['context_state'] == row['entity_id'] + 1 and
                row['context_owner'] == row['entity'] and row['context_callback'] == bindings[0],
                'Enabled context differs from its original owner or callback binding.')

    require(row['ra'] % 4 == 0 and row['ra'] >= 8, 'Invalid saved return address.')
    site = row['ra'] - 8
    call = struct.unpack_from('<I', executable, executable_offset(executable, site, 4))[0]
    if call >> 26 == 3:
        destination = ((site + 4) & 0xf0000000) | ((call & 0x3ffffff) << 2)
        require(destination == pc, 'The original direct call targets another function.')
        call_kind = 'JAL'
    else:
        require(call >> 26 == 0 and call & 63 == 9 and (call >> 11) & 31 == 31 and
                (call >> 16) & 31 == 0 and (call >> 6) & 31 == 0,
                'The saved return address has no supported original call instruction.')
        call_kind = 'JALR'
    require(not set(methods) & set(callers), 'Engine and caller catalogues repeat a method PC.')
    ranges = sorted([*methods.values(), *callers.values()], key=lambda r: r['address'])
    require(all(a['address'] + a['bytes'] <= b['address'] for a, b in zip(ranges, ranges[1:])),
            'Engine and caller method ranges overlap.')
    owner = next((r['name'] for r in ranges if r['address'] <= site < r['address'] + r['bytes']), None)
    return dict(relative_frame=row['relative_frame'], timestamp=row['timestamp'],
                method=methods[pc]['name'], entity=row['entity'], entity_id=row['entity_id'],
                original_callsite=site, call_kind=call_kind, reviewed_caller=owner,
                context_enabled=enabled, disabled_payload_ignored=not enabled,
                context_tick=row['context_tick'] if enabled else None,
                context_owner=row['context_owner'] if enabled else None,
                context_callback=row['context_callback'] if enabled else None,
                registered_callback_dispatch=False, whole_encounter_accepted=False)
