"""Inspect NPC activation and scene reachability in a verified recording.

Reads retained RAM and instruction observations only. A disabled context's
payload and an unreachable object's former storage are never interpreted.
Snapshot transitions do not establish heap allocation lifetime, visibility,
complete emulator state, hardware timing or a whole NPC encounter.
"""
import argparse
from bisect import bisect_right
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import configure
from tools.compare_npc_history import inspect_run
from tools.inventory_entities import audit_entities, verify_layout
from tools.inventory_runtime_scene import inspect_entities, physical, walk_objects, word
from tools.inventory_vtables import parse_symbols
from tools.psx_image import ORIGINAL_SHA1
from tools.runtime_inputs import record_file


def require(condition, message):
    if not condition:
        raise ValueError(message)


def graph_roots(raw):
    """Follow the original game-flow global and its actual dream member."""
    require(len(raw) == 0x200000, 'A checkpoint must contain complete MainRAM.')
    flow = word(raw, 0x8AC20)
    offset = physical(flow, 0x2C)
    require(word(raw, offset) == 0x8006D3C8, 'The recorded game-flow type differs.')
    dream = word(raw, offset + 0x28)
    require(word(raw, physical(dream, 0x928)) == 0x80087BDC,
            'The recorded dream-system type differs.')
    return dict(flow=flow, dream=dream)


def inspect_checkpoint(raw, executable, entity_audit, target_address, entity_id):
    roots = graph_roots(raw)
    graph = walk_objects(raw, roots, executable)
    inventory = inspect_entities(raw, graph, roots['dream'], entity_audit, executable)
    at_address = [node for node in graph['objects'] if node['address'] == target_address]
    candidates = [row for row in inventory['entities'] if row['address'] == target_address]
    require(len(candidates) <= 1, 'Repeated target entity in the reachable graph.')
    target = candidates[0] if candidates else None
    if target is not None and target['entity_id'] == entity_id:
        state = 'enabled' if target['context_enabled'] else 'disabled'
    elif at_address:
        state = 'different_object_at_address'
        target = None
    else:
        state = 'not_reachable'
        target = None
    return dict(state=state, target=target, roots=roots,
                reachable_objects=graph['object_count'], child_edges_checked=graph['child_edges_checked'],
                loaded_entity_objects=inventory['loaded_entity_objects'])


def transition_windows(rows):
    """State changes are bounded by adjacent checked snapshots, not guesses."""
    require(all(type(row.get('relative_frame')) is int and row['relative_frame'] >= 0 for row in rows)
            and all(left['relative_frame'] < right['relative_frame'] for left, right in zip(rows, rows[1:])),
            'Checkpoint boundaries must be unique and increasing.')
    return [dict(from_state=left['state'], to_state=right['state'],
                 after_relative_frame=left['relative_frame'], through_relative_frame=right['relative_frame'],
                 consecutive_core_advances=right['relative_frame'] == left['relative_frame'] + 1)
            for left, right in zip(rows, rows[1:]) if left['state'] != right['state']]


def inspect_history(folder):
    folder = Path(folder).resolve(strict=True)
    source_paths = [ROOT / path for path in (
        configure.ROM, configure.MAP_FILE, configure.UNDEF_FUNCS, configure.UNDEF_SYMS, configure.SYMBOLS,
        'src/scene/entity.c', 'src/scene/entity.h', 'src/game/game_flow.h', 'src/dream/dream_sys.h',
        'tools/inspect_npc_lifetime.py', 'tools/compare_npc_history.py', 'tools/inventory_runtime_scene.py',
        'tools/inventory_entities.py', 'tools/inventory_vtables.py', 'tools/psx_image.py',
        'tools/runtime_inputs.py')]
    before = [record_file(path) for path in source_paths]
    recording_pin = record_file(folder / 'run-inputs.json')
    executable = source_paths[0].read_bytes()
    require(hashlib.sha1(executable).hexdigest() == ORIGINAL_SHA1, 'Use the canonical original executable.')
    symbols = parse_symbols(source_paths[1].read_text(), [path.read_text() for path in source_paths[2:5]])
    verify_layout(source_paths[6].read_text())
    audit = audit_entities(executable, source_paths[5].read_text(), symbols)
    rooted_snapshots = {}

    def context_clock_guard(raw, address, entity_id, frame):
        snapshot = inspect_checkpoint(raw, executable, audit, address, entity_id)
        rooted_snapshots[frame] = snapshot
        return snapshot['target'] is not None

    run = inspect_run(folder, executable, context_clock_guard=context_clock_guard)
    require(run['entries'], 'This recording has no qualified original instruction entries.')
    profile = run['program']['trace']
    entity_id = profile['entity_id']
    require(entity_id < len(audit['records']), 'The watched entity ID is outside the original property table.')
    require(int(audit['records'][entity_id]['callback_address'], 16) == int(profile['watched_pc'], 0),
            'The watched instruction does not match this original entity binding.')
    target_address = run['entries'][0]['entity']
    event_frames = [row['relative_frame'] for row in run['entries']]
    expected_RAM = {row['relative_frame']: row['RAM_sha256'] for row in run['native']['checkpoints']}
    rows, checkpoints = [], []
    for frame, paths in sorted(run['raw_checkpoints'].items()):
        if frame < profile['arm_frame']:
            continue
        path = paths['RAM']
        pin = record_file(path)
        require(pin['sha256'] == expected_RAM[frame], 'A RAM checkpoint differs from its verified native observation.')
        row = rooted_snapshots.get(frame)
        if row is None:
            row = inspect_checkpoint(path.read_bytes(), executable, audit, target_address, entity_id)
        if row['target'] is not None and row['target']['registered_context'] is not None:
            context = row['target']['registered_context']
            if context['matches_original_binding']:
                require(context['tick'] == bisect_right(event_frames, frame),
                        'An enabled original context clock differs from the observed instruction entries.')
        require(record_file(path) == pin, 'A complete RAM checkpoint changed during inspection.')
        checkpoints.append(pin)
        rows.append(dict(relative_frame=frame, instruction_entries_through_frame=bisect_right(event_frames, frame), **row))
    require(rows, 'No complete checkpoints lie in the armed observation window.')
    require([record_file(path) for path in source_paths] == before, 'An inspected source changed.')
    require(record_file(folder / 'run-inputs.json') == recording_pin, 'The recording manifest changed.')
    return dict(schema_version=1, status='inspected_recorded_NPC_lifetime',
                recorded_utc=datetime.now(timezone.utc).isoformat(), recording=str(folder),
                run_inputs=recording_pin, sources=before, checkpoints=checkpoints,
                target_address=target_address, entity_id=entity_id, callback=profile['callback'],
                instruction_entries=len(run['entries']), checked_snapshots=len(rows), rows=rows,
                transition_windows=transition_windows(rows),
                game_RAM_modified=False, emulator_controlled=False, new_native_game_runs=0,
                new_C_bytes=0, whole_NPC_encounters_accepted=0, whole_feature_groups_accepted=0,
                complete_state_parity_checked=False, original_hardware_timing_verified=False,
                scope='Recorded context states and reachability from the original game-flow global and its '
                      'dream owner. Every followed child edge has a reciprocal parent entry. Disabled context '
                      'payload and unreachable former storage are uninterpreted. Snapshot intervals do not '
                      'prove allocation lifetime, visibility, arbitrary intervening states or whole encounters.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recording', type=Path, required=True, help='Completed observer recording from record_npc_history.py.')
    parser.add_argument('--output', type=Path, required=True, help='New private JSON report; existing files are preserved.')
    args = parser.parse_args(argv)
    require(not args.output.exists(), 'Choose a new report path.')
    report = inspect_history(args.recording)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({key: report[key] for key in
                     ('status', 'checked_snapshots', 'instruction_entries', 'transition_windows', 'new_C_bytes')}))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
