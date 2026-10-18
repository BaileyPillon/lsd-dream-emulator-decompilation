"""Validate optional catalogue observations without accepting whole NPC behavior."""
from bisect import bisect_right
import csv
import hashlib
import json
from pathlib import Path
import re
import struct

from tools.psx_image import executable_offset
from tools.replay_cold_start_headless import require

PRIMARY_FIELDS = ('relative_frame', 'pc', 'entity', 'ra', 'sp', 'timestamp', 'instruction', 'context_tick')
CATALOGUE_FIELDS = PRIMARY_FIELDS + ('entity_vtable', 'entity_id', 'context_state', 'context_owner', 'context_callback')
HEX_FIELDS = set(CATALOGUE_FIELDS) - {'relative_frame', 'timestamp', 'context_tick'}
DISPATCH_RETURN = 0x8002CD88


def sha(data):
    return hashlib.sha256(data).hexdigest()


def catalogue_targets(value, executable):
    require(isinstance(value, dict) and value.get('schema_version') == 1
            and value.get('kind') == 'original_LSD_NPC_callback_catalogue', 'Unsupported NPC catalogue.')
    require(value.get('canonical_executable_sha256') == sha(executable), 'Catalogue executable identity differs.')
    count = value.get('property_records')
    require(type(count) is int and 1 <= count <= 65536, 'Invalid original entity-table count.')
    table = value.get('original_entity_table', {})
    require(table.get('record_bytes') == 16 and table.get('bytes') == 16 * count,
            'Unsupported original entity record layout.')
    try:
        address = int(table['address'], 0)
    except (KeyError, ValueError, TypeError):
        raise ValueError('Invalid original entity-table address.') from None
    at = executable_offset(executable, address, count * 16)
    raw = executable[at:at + count * 16]
    require(sha(raw) == table.get('sha256'), 'Original entity-table bytes differ.')
    bindings, nulls = {}, 0
    for index in range(count):
        pc = struct.unpack_from('<I', raw, index * 16 + 12)[0]
        if pc:
            bindings.setdefault(pc, []).append(index)
        else:
            nulls += 1
    rows = value.get('targets')
    require(isinstance(rows, list) and 1 <= len(rows) <= 128, 'Invalid catalogue target count.')
    targets, end, total = {}, 0, 0
    for row in rows:
        require(isinstance(row, dict) and isinstance(row.get('pc'), str)
                and re.fullmatch(r'0x[0-9A-F]{8}', row['pc']) is not None, 'Invalid catalogue PC.')
        pc, size = int(row['pc'], 16), row.get('function_bytes')
        require(pc not in targets and pc % 4 == 0 and pc >= end and type(size) is int
                and size > 0 and size % 4 == 0, 'Repeated, unsized or overlapping catalogue target.')
        require(row.get('entity_ids') == bindings.get(pc) and bool(bindings.get(pc)),
                'Catalogue entity IDs differ from the original table.')
        require(isinstance(row.get('callback'), str) and re.fullmatch(r'entity_[A-Za-z0-9_]+', row['callback']),
                'Catalogue callback name is not a recovered entity label.')
        offset = executable_offset(executable, pc, size)
        code = executable[offset:offset + size]
        require(sha(code) == row.get('function_sha256') and sha(code[:4]) == row.get('entry_instruction_sha256'),
                'Catalogue code bytes differ from the original.')
        targets[pc] = dict(row, entry_word=struct.unpack_from('<I', code)[0])
        end, total = pc + size, total + size
    require(set(targets) == set(bindings) and len(targets) == value.get('distinct_callback_functions')
            and total == value.get('total_callback_function_bytes')
            and nulls == value.get('null_callback_slots')
            and sum(map(len, bindings.values())) == value.get('nonnull_callback_slots'),
            'Catalogue omits or miscounts original bindings.')
    return targets


def verified_catalogue(value, provenance, raw, executable):
    require(provenance.get('status') == 'verified_original_NPC_callback_catalogue'
            and provenance.get('source_sha256', {}).get('research/headless/npc-callback-catalogue.json') == sha(raw),
            'Catalogue does not match its published complete-symbol verification.')
    require(json.loads(raw) == value, 'Frozen catalogue data differs from its source bytes.')
    targets = catalogue_targets(value, executable)
    require(len(targets) == 107 and value['property_records'] == 130
            and value['nonnull_callback_slots'] == 111 and value['null_callback_slots'] == 19
            and value['total_callback_function_bytes'] == 29232, 'Use the complete original LSD catalogue.')
    return targets


def read_catalogue_rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        require(tuple(reader.fieldnames or ()) == CATALOGUE_FIELDS, 'Unexpected catalogue observation columns.')
        rows = list(reader)
    require(all(None not in row and None not in row.values() for row in rows), 'Truncated catalogue observation.')
    return rows


def classify_entry(row, targets, executable):
    pc = row['pc']
    if row['entity_vtable'] != 0x80089AD4:
        return 'non_entity_function_entry'
    entity_id = row['entity_id']
    if row['context_state'] & 0x80000000 or row['context_state'] == 0:
        return 'disabled_context_function_entry'
    registered = targets.get(row['context_callback'])
    if (registered is None or row['context_state'] != entity_id + 1
            or row['context_owner'] != row['entity'] or entity_id not in registered['entity_ids']):
        return 'unregistered_function_entry'
    if row['context_callback'] == pc and entity_id in targets[pc]['entity_ids'] and row['ra'] == DISPATCH_RETURN:
        return 'registered_dispatch'
    # Only an actual original JAL to this PC establishes a direct nested call.
    callsite = row['ra'] - 8
    try:
        at = executable_offset(executable, callsite, 4)
    except ValueError:
        return 'non_dispatch_function_entry'
    word = struct.unpack_from('<I', executable, at)[0]
    destination = ((callsite + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
    if word >> 26 == 3 and destination == pc and row['context_callback'] != pc:
        return 'nested_callback_function_entry'
    return 'non_dispatch_function_entry'


def validate_catalogue_rows(rows, targets, executable, arm, frames):
    entries, last, seen = [], arm, set()
    for raw in rows:
        require(set(raw) == set(CATALOGUE_FIELDS), 'Incomplete catalogue event fields.')
        require(all(isinstance(raw[key], str) and re.fullmatch(r'[0-9A-F]{8}', raw[key])
                    for key in HEX_FIELDS), 'Invalid catalogue register word.')
        try:
            row = {key: int(value, 16) if key in HEX_FIELDS else int(value) for key, value in raw.items()}
        except (ValueError, TypeError):
            raise ValueError('Invalid catalogue numeric field.') from None
        pc, frame = row['pc'], row['relative_frame']
        require(pc in targets and row['instruction'] == targets[pc]['entry_word'], 'Wrong original catalogue entry instruction.')
        require(last <= frame <= frames and frame >= arm and row['timestamp'] >= 0
                and 0 <= row['context_tick'] <= 0xFFFFFFFF, 'Invalid catalogue observation boundary.')
        require(row['entity'] % 4 == 0 and 0x80010000 <= row['entity'] <= 0x80200000 - 0x108
                and row['sp'] % 4 == 0 and 0x80010000 <= row['sp'] < 0x80200000
                and row['ra'] % 4 == 0 and 0x80010000 <= row['ra'] < 0x80200000,
                'Invalid catalogue entity, stack pointer or return address.')
        identity = tuple(row[key] for key in CATALOGUE_FIELDS)
        require(identity not in seen, 'Repeated catalogue event.')
        seen.add(identity)
        last = frame
        row['classification'] = classify_entry(row, targets, executable)
        entries.append(row)
    return entries


def dispatch_clock_models(entries):
    """Keep unknown resets unresolved instead of inventing activation epochs."""
    dispatches = {}
    for row in entries:
        if row['classification'] == 'registered_dispatch':
            dispatches.setdefault((row['entity'], row['pc'], row['entity_id']), []).append(row)
    clocks = {}
    for key, observed in dispatches.items():
        ticks = [row['context_tick'] for row in observed]
        clocks[key] = dict(first_observed_tick=ticks[0], entries=len(observed),
            consecutive_entry_ticks=ticks == list(range(ticks[0], ticks[0] + len(ticks))),
            rooted_RAM_clock_checks=0)
    return dispatches, clocks


def inspect_catalogue_log(run, executable):
    """Validate a second log; unknown clocks remain explicitly unqualified."""
    from tools.inspect_npc_lifetime import graph_roots
    from tools.inventory_runtime_scene import walk_objects, inspect_entities
    from tools.inventory_entities import audit_entities
    from tools.inventory_vtables import parse_symbols
    from tools.runtime_inputs import record_file
    import configure
    root = Path(__file__).resolve().parents[1]
    source_paths = [Path(__file__).resolve(), *(root / name for name in (
        'tools/inspect_npc_lifetime.py', 'tools/inventory_runtime_scene.py',
        'tools/inventory_entities.py', 'tools/inventory_vtables.py',
        'src/scene/entity.c', 'src/scene/entity.h', 'src/game/game_flow.h', 'src/dream/dream_sys.h',
        configure.MAP_FILE, configure.UNDEF_FUNCS, configure.UNDEF_SYMS, configure.SYMBOLS))]
    source_pins = [record_file(path) for path in source_paths]
    descriptor = run['inputs']['catalogue']
    value = descriptor['value']
    targets = catalogue_targets(value, executable)
    folder = run['folder']
    rows = read_catalogue_rows(folder / 'observations/npc-catalogue-instructions.tsv')
    entries = validate_catalogue_rows(rows, targets, executable, run['settings']['arm_frame'], run['settings']['frames'])
    selected = [{key: row[key] for key in PRIMARY_FIELDS} for row in entries if row['pc'] == run['settings']['watched_pc']]
    require(selected == run['entries'], 'Catalogue projection differs from the independent selected-PC trace.')
    summary = json.loads((folder / 'observations/npc-catalogue-summary.json').read_text())
    require(summary.get('watched_pcs') == sorted(targets) and summary.get('event_words') == 13
            and summary.get('per_frame_capacity') == 1024
            and summary.get('original_instruction_entries') == len(entries)
            and summary.get('hook_enabled_relative_frame') == run['settings']['arm_frame']
            and summary.get('hook_enabled') == (run['settings']['frames'] >= run['settings']['arm_frame'])
            and summary.get('first_observed_entry_frame') == (entries[0]['relative_frame'] if entries else -1)
            and summary.get('last_observed_entry_frame') == (entries[-1]['relative_frame'] if entries else -1)
            and summary.get('game_RAM_injected') is False, 'Catalogue summary differs from its complete log.')
    dispatches, clocks = dispatch_clock_models(entries)
    symbols = parse_symbols((root / configure.MAP_FILE).read_text(),
        [(root / name).read_text() for name in (configure.UNDEF_FUNCS, configure.UNDEF_SYMS, configure.SYMBOLS)])
    audit = audit_entities(executable, (root / 'src/scene/entity.c').read_text(), symbols)
    unrooted = []
    for frame, paths in run['raw_checkpoints'].items():
        if frame < run['settings']['arm_frame']:
            continue
        raw = paths['RAM'].read_bytes()
        for pc, target in targets.items():
            at = executable_offset(executable, pc, target['function_bytes'])
            require(raw[pc & 0x1FFFFFFF:(pc & 0x1FFFFFFF) + target['function_bytes']] == executable[at:at + target['function_bytes']],
                    'A loaded catalogue callback span differs from the original.')
        try:
            roots = graph_roots(raw)
        except ValueError as error:
            unrooted.append(dict(frame=frame, reason=str(error)))
            continue  # A non-dream boundary supplies no rooted NPC evidence.
        graph = walk_objects(raw, roots, executable)
        inventory = inspect_entities(raw, graph, roots['dream'], audit, executable)
        entities = {row['address']: row for row in inventory['entities']}
        for key, observed in dispatches.items():
            owner, pc, entity_id = key
            clock = clocks[key]
            entity = entities.get(owner)
            if not clock['consecutive_entry_ticks'] or entity is None or entity['entity_id'] != entity_id:
                continue
            context = entity['registered_context']
            if context is None or context['callback'] != pc:
                continue
            count = bisect_right([row['relative_frame'] for row in observed], frame)
            if count == 0:
                continue
            require(context['tick'] == clock['first_observed_tick'] + count,
                    'A rooted catalogue context clock differs from its registered dispatches.')
            clock['rooted_RAM_clock_checks'] += 1
    counts = {}
    for row in entries:
        counts[row['classification']] = counts.get(row['classification'], 0) + 1
    require([record_file(path) for path in source_paths] == source_pins,
            'Catalogue inspection source changed during validation.')
    return dict(entries=entries, classifications=counts, source_pins=source_pins,
        unrooted_checkpoint_boundaries=unrooted,
        observed_function_PCs=sorted({row['pc'] for row in entries}),
        observed_registered_callback_PCs=sorted({row['pc'] for row in entries if row['classification'] == 'registered_dispatch'}),
        instances=[dict(entity=f'0x{key[0]:08X}', PC=f'0x{key[1]:08X}', entity_id=key[2], **clock)
                   for key, clock in sorted(clocks.items())],
        whole_NPC_encounters_accepted=0, whole_feature_groups_accepted=0)
