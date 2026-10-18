"""Check sampled natural primitive returns against captured original geometry.

The samples contain architectural registers and complete main RAM at entry and
return. They do not serialize opaque CPU/GTE state, observe every instruction,
establish allocation ownership, or attribute every RAM change to the callee.
"""
import argparse
from collections import Counter
import hashlib
import json
import mmap
from pathlib import Path, PureWindowsPath
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import inspect_dispatch_history as history
from tools.collision_calls import EVENT_BYTES, FIELDS, FRAME_BYTES, FUNCTION_BYTES, PC, RAM_BYTES, selection
from tools.dispatch_returns import _instruction, _jump_return, sequence
from tools.inspect_sdk_reads import _stack_after_delay
from tools.psx_image import executable_offset
from tools.replay_cold_start_headless import require, write_json
from tools.verify_collision import LAYOUTS, primitive_model, signed


def sha(data):
    return hashlib.sha256(data).hexdigest()


def ram_offset(address, size, alignment=1):
    """Accept bounded physical RAM and its ordinary KSEG0/KSEG1 aliases."""
    require(type(address) is int and 0 <= address <= 0xFFFFFFFF
            and address & 0xE0000000 in (0, 0x80000000, 0xA0000000)
            and type(size) is int and 0 < size <= RAM_BYTES
            and address % alignment == 0,
            'Unsupported collision RAM address, extent or alignment.')
    at = address & 0x1FFFFFFF
    require(at + size <= RAM_BYTES, 'Collision range extends outside captured main RAM.')
    return at


def ram(data, address, size, alignment=1):
    at = ram_offset(address, size, alignment)
    require(len(data) == RAM_BYTES, 'Require one complete main-RAM snapshot.')
    return data[at:at + size]


def word(data, address):
    return struct.unpack('<I', ram(data, address, 4, 4))[0]


def point(data, address):
    return struct.unpack('<3h', ram(data, address, 6, 2))


def decode_geometry(data, model):
    geometry = word(data, model + 16)
    vertices, vertex_count, normals, normal_count, primitives, count = struct.unpack(
        '<6I', ram(data, geometry, 24, 4))
    require(vertex_count <= RAM_BYTES // 8 and count <= RAM_BYTES // 16,
            'Geometry counts exceed a complete main-RAM buffer.')
    ranges = [('model_geometry_pointer', model + 16, 4), ('geometry_header', geometry, 24)]
    if vertex_count:
        ram(data, vertices, vertex_count * 8, 2)
        ranges.append(('vertices', vertices, vertex_count * 8))
    cursor, polygons, modes = primitives, [], Counter()
    for _ in range(count):
        header = ram(data, cursor, 4)
        flag, mode = header[2], header[3]
        layout = LAYOUTS.get((mode, flag & 4), LAYOUTS.get((mode, 0)))
        require(layout is not None, 'Unsupported original primitive code has no qualified packet extent.')
        length, offsets = layout
        packet = ram(data, cursor, length)
        indices = tuple(struct.unpack_from('<H', packet, at)[0] for at in offsets)
        require(all(index < vertex_count for index in indices),
                'Primitive references a vertex outside the captured declared array.')
        polygons.append(tuple(point(data, vertices + index * 8) for index in indices))
        modes[f'0x{mode:02X}'] += 1
        cursor += length
    if count:
        ranges.append(('primitive_packets', primitives, cursor - primitives))
    return dict(polygons=tuple(polygons), ranges=ranges,
                model_address=model, geometry_address=geometry, vertices_address=vertices,
                vertex_count=vertex_count, normals_address=normals, normal_count=normal_count,
                primitives_address=primitives, primitive_count=count, primitive_bytes=cursor - primitives,
                packet_mode_counts=dict(sorted(modes.items())))


def _disjoint(writes, reads):
    physical_writes = [(label, ram_offset(address, size), size) for label, address, size in writes]
    physical_reads = [(label, ram_offset(address, size), size) for label, address, size in reads]
    for index, (name, at, size) in enumerate(physical_writes):
        for other, start, length in physical_writes[index + 1:] + physical_reads:
            require(at + size <= start or start + length <= at,
                    f'Unqualified collision output alias: {name} / {other}.')


def verify_geometry_result(row, before, after):
    args = [row[f'entry_cpu_gpr_{n}'] for n in (4, 5, 6, 7)]
    model, nearest, output, height = args
    stack = row['entry_cpu_gpr_29']
    start_address, end_address = word(before, stack + 16), word(before, stack + 20)
    start, end = point(before, start_address), point(before, end_address)
    geometry = decode_geometry(before, model)
    writes = [('nearest', nearest, 4), ('contact', output, 6)]
    if height:
        ram(before, height, 4, 4)
        writes.append(('height', height, 4))
    ram(before, nearest, 4, 4)
    ram(before, output, 6, 2)
    reads = geometry['ranges'] + [('stack_arguments', stack + 16, 8),
                                 ('segment_start', start_address, 6), ('segment_end', end_address, 6),
                                 ('callee_code', PC, FUNCTION_BYTES)]
    _disjoint(writes, reads)
    for label, address, size in reads:
        require(ram(before, address, size) == ram(after, address, size),
                f'Captured collision input changed across this call: {label}.')
    result, distance, contact, elevation = primitive_model(
        geometry['polygons'], start, end,
        lambda address: struct.unpack('<H', ram(before, address, 2, 2))[0])
    require(row['cpu_gpr_2'] == result and signed(word(after, nearest)) == distance,
            'Original collision return or nearest distance differs from the algebraic model.')
    if contact is None:
        require(ram(after, output, 6) == ram(before, output, 6)
                and (not height or ram(after, height, 4) == ram(before, height, 4)),
                'A no-contact collision call changed its contact or optional height output.')
    else:
        require(point(after, output) == contact and
                (not height or signed(word(after, height)) == elevation),
                'Original collision contact or height differs from the algebraic model.')
    return dict(**{key: value for key, value in geometry.items() if key not in ('polygons', 'ranges')},
                start_address=start_address, end_address=end_address, start=list(start), end=list(end),
                nearest_address=nearest, contact_address=output, height_address=height,
                result=result, nearest=distance, contact=list(contact) if contact is not None else None,
                height=elevation if height else None,
                decoded_polygons_sha256=sha(json.dumps(geometry['polygons'], separators=(',', ':')).encode()),
                source_ranges=[dict(role=label, address=address, bytes=size,
                                    sha256=sha(ram(before, address, size)))
                               for label, address, size in geometry['ranges']])


def verify_boundary(row, base, executable, before, after):
    entry_sp, entry_ra = row['entry_cpu_gpr_29'], row['entry_cpu_gpr_31']
    require(row['entry_pc'] == base['pc'] == PC
            and (row['entry_frame'], row['entry_timestamp']) == (base['relative_frame'], base['timestamp'])
            and [row[f'entry_cpu_gpr_{n}'] for n in (4, 5, 6, 7, 29, 31)] ==
                [base[name] for name in ('a0', 'a1', 'a2', 'a3', 'sp', 'ra')]
            and (row['entry_jump_pc'], row['entry_delay_pc']) == (base['transfer_pc'], base['delay_pc'])
            and (row['entry_jump_ram'], row['entry_delay_ram']) == (base['transfer_word'], base['delay_word'])
            and base['transfer_classification']['kind'] == 'observed_direct_JAL',
            'Sample entry does not identify its complete original primitive entry.')
    require(row['entry_cpu_gpr_0'] == row['cpu_gpr_0'] == 0
            and not (row['entry_cpu_sr'] | row['cpu_sr']) & 0x10000
            and row['return_pc'] == entry_ra
            and all(row[f'entry_cpu_gpr_{n}'] == row[f'cpu_gpr_{n}'] for n in (*range(16, 24), 28, 29, 30, 31)),
            'Original collision return lost its caller, stack, callee-saved register or RAM context.')
    for prefix, snapshot in (('entry_', before), ('', after)):
        for part in ('jump', 'delay'):
            key = prefix + part + '_'
            _instruction(executable, *(row[key + name] for name in ('pc', 'ram', 'fetch', 'flags', 'sr')))
            require(word(snapshot, row[key + 'pc']) == row[key + 'ram'],
                    'Captured transfer RAM word disagrees with its complete snapshot.')
        _stack_after_delay(row, prefix, entry_sp)
    call = row['entry_jump_fetch']
    require(call >> 26 == 3 and
            (((row['entry_jump_pc'] + 4) & 0xF0000000) | ((call & 0x03FFFFFF) << 2)) == PC
            and entry_ra == row['entry_jump_pc'] + 8,
            'Sample does not observe the original direct primitive call and link.')
    _jump_return(row, executable, target=entry_ra, span=(PC, FUNCTION_BYTES))
    at = executable_offset(executable, PC, FUNCTION_BYTES)
    require(ram(before, PC, FUNCTION_BYTES) == ram(after, PC, FUNCTION_BYTES) == executable[at:at + FUNCTION_BYTES],
            'Complete primitive code changed at the captured entry or return.')


def verify_policy(rows, entries, settings, summary):
    selected = {row['base_ordinal']: row for row in rows}
    counts, reasons, started, last_frame, pending = Counter(), Counter(), 0, None, None
    for ordinal, entry in enumerate(entries, 1):
        if entry['pc'] != PC:
            continue
        now = entry['relative_frame'], entry['timestamp']
        if pending and (pending['frame'], pending['timestamp']) <= now:
            pending = None
        key = entry['transfer_pc'], entry['a0']
        if pending:
            reason = 'nested_skips'
        elif started == settings['max_samples']:
            reason = 'sample_limit_skips'
        elif counts[key] == settings['per_key']:
            reason = 'duplicate_key_skips'
        elif last_frame == entry['relative_frame']:
            reason = 'frame_budget_skips'
        else:
            require(ordinal in selected, 'A required caller/model collision sample is missing.')
            pending = selected[ordinal]
            counts[key] += 1
            started += 1
            last_frame = entry['relative_frame']
            continue
        reasons[reason] += 1
        require(ordinal not in selected, 'Collision sample contradicts its actual bounded selection policy.')
    require(started == len(rows) and sum(reasons.values()) + started == summary['eligible_entries']
            and all(reasons[name] == summary[name] for name in
                    ('nested_skips', 'sample_limit_skips', 'duplicate_key_skips', 'frame_budget_skips')),
            'Collision sample counters disagree with the complete primitive entry history.')
    return dict(selected_calls=started, eligible_entries=summary['eligible_entries'],
                distinct_observed_caller_model_address_keys=len(counts),
                **{name: reasons[name] for name in
                   ('nested_skips', 'sample_limit_skips', 'duplicate_key_skips', 'frame_budget_skips')})


def validate_records(data, payload, summary, entries, program, executable):
    settings = selection(program)
    require(settings is not None, 'No primitive call snapshots were selected.')
    numeric = ('protocol', 'event_bytes', 'returns', 'native_returns', 'native_started', 'eligible_entries',
               'native_overflow', 'pending_calls', 'payload_bytes', 'duplicate_key_skips', 'frame_budget_skips',
               'sample_limit_skips', 'nested_skips', 'frame_payload_limit', 'ram_snapshot_bytes',
               'CPU_register_words', 'GTE_architectural_register_words')
    require(isinstance(summary, dict) and all(type(summary.get(key)) is int and summary[key] >= 0 for key in numeric),
            'Collision sample summary has missing or non-integer counters.')
    require(summary['protocol'] == 1 and summary['event_bytes'] == EVENT_BYTES
            and summary.get('settings') == settings
            and all(type(value) is int for value in summary['settings'].values())
            and summary['native_overflow'] == summary['pending_calls'] == summary['nested_skips'] == 0
            and summary['frame_payload_limit'] == FRAME_BYTES and summary['ram_snapshot_bytes'] == RAM_BYTES
            and summary['CPU_register_words'] == 37 and summary['GTE_architectural_register_words'] == 64
            and all(summary.get(key) is False for key in
                    ('original_game_RAM_injected', 'original_CPU_source_modified', 'observer_writes_GTE_registers',
                     'complete_state_parity_checked', 'opaque_internal_GTE_state_serialized')),
            'Unqualified collision sampler protocol, overflow, pending call or state claim.')
    count = len(data) // EVENT_BYTES
    require(len(data) % EVENT_BYTES == 0 and 1 <= count <= settings['max_samples']
            and count == summary['returns'] == summary['native_returns'] == summary['native_started']
            and len(payload) == summary['payload_bytes'] == count * RAM_BYTES * 2,
            'Incomplete collision call records or complete-RAM payload.')
    rows = [dict(zip(FIELDS, values)) for values in struct.iter_unpack('<247I', data)]
    calls, modes, callers, results = [], Counter(), Counter(), Counter()
    previous_base, previous_sequence = 0, 0
    for index, row in enumerate(rows):
        for field in ('entry_timestamp', 'timestamp'):
            row[field] = signed(row[field])
        require(row['ordinal'] == row['entry_id'] == index + 1
                and previous_base < row['base_ordinal'] <= len(entries)
                and program['method_trace']['arm_frame'] <= row['entry_frame'] <= row['frame'] <= program['frames']
                and 0 <= row['entry_timestamp'] and 0 <= row['timestamp']
                and (row['entry_frame'], row['entry_timestamp']) < (row['frame'], row['timestamp'])
                and previous_sequence < sequence(row, 'entry_') < sequence(row)
                and row['ram_bytes'] == RAM_BYTES and row['payload_status'] == 1
                and row['before_offset'] == index * RAM_BYTES * 2
                and row['after_offset'] == row['before_offset'] + RAM_BYTES,
                'Collision call ordinal, boundary order, sequence or RAM extent differs.')
        previous_base, previous_sequence = row['base_ordinal'], sequence(row)
        before = payload[row['before_offset']:row['before_offset'] + RAM_BYTES]
        after = payload[row['after_offset']:row['after_offset'] + RAM_BYTES]
        base = entries[row['base_ordinal'] - 1]
        verify_boundary(row, base, executable, before, after)
        geometry = verify_geometry_result(row, before, after)
        modes.update(geometry['packet_mode_counts'])
        callers[f"0x{row['entry_jump_pc']:08X}"] += 1
        results[str(geometry['result'])] += 1
        calls.append(dict(ordinal=row['ordinal'], base_ordinal=row['base_ordinal'],
                          entry_frame=row['entry_frame'], return_frame=row['frame'],
                          entry_timestamp=row['entry_timestamp'], return_timestamp=row['timestamp'],
                          entry_instruction_sequence=sequence(row, 'entry_'), return_instruction_sequence=sequence(row),
                          caller=f"0x{row['entry_jump_pc']:08X}", stack_address=row['entry_cpu_gpr_29'],
                          before_RAM_sha256=sha(before), after_RAM_sha256=sha(after), **geometry))
    require(summary['eligible_entries'] == sum(row['pc'] == PC for row in entries),
            'Sampler eligible count differs from the complete original entry stream.')
    policy = verify_policy(rows, entries, settings, summary)
    return dict(status='verified_bounded_natural_primitive_calls', completed_samples=count,
                policy=policy, caller_counts=dict(sorted(callers.items())), result_counts=dict(sorted(results.items())),
                sampled_polygon_visits=sum(call['primitive_count'] for call in calls),
                packet_mode_counts=dict(sorted(modes.items())),
                distinct_sampled_model_addresses=len({call['model_address'] for call in calls}),
                distinct_sampled_geometry_addresses=len({call['geometry_address'] for call in calls}),
                calls_crossing_a_frame=sum(call['entry_frame'] != call['return_frame'] for call in calls),
                binary_records_sha256=sha(data), complete_RAM_payload_sha256=sha(payload), calls=calls,
                architectural_CPU_words_per_boundary=37, architectural_GTE_words_per_boundary=64,
                complete_state_parity_checked=False, opaque_internal_GTE_state_serialized=False,
                every_RAM_change_attributed_to_callee=False, full_instruction_paths_accepted=False,
                geometry_allocation_ownership_accepted=False, whole_feature_groups_accepted=0, new_C_bytes=0,
                scope='Sampled original call/return boundaries, complete main RAM, declared geometry buffers, '
                      'and algebraic hit/distance/contact/optional-height agreement in this one input history. '
                      'Caller/model addresses are observations, not allocation generations or asset identities. '
                      'Interrupt and frame activity can change other RAM during a call. Unselected calls, '
                      'hull returns, opaque CPU/GTE state and whole collision-feature parity remain unaccepted.')


def inspect_calls(folder):
    recording, retained = history.inspect(folder)
    require(retained['manifest']['runtime_kind'] == 'dispatch_observer', 'Require the separate collision observer.')
    folder = retained['folder']
    output = folder / 'observations'
    snapshots = [item for item in retained['manifest']['source_snapshots']
                 if PureWindowsPath(item['original']['path']).name == 'SLPS_015.56']
    require(len(snapshots) == 1, 'Require the retained canonical executable.')
    executable = history.owned_file(folder, snapshots[0]['file']).read_bytes()
    data = history.owned_file(output, 'collision-calls.bin').read_bytes()
    summary = json.loads(history.owned_file(output, 'collision-call-summary.json').read_text(encoding='utf-8-sig'))
    payload_path = history.owned_file(output, 'collision-call-ram.bin')
    original = payload_path.stat()
    with payload_path.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as payload:
        calls = validate_records(data, payload, summary, retained['entries'],
                                 dict(retained['program'], frames=recording['input_frames']), executable)
    current = payload_path.stat()
    require((original.st_size, original.st_mtime_ns) == (current.st_size, current.st_mtime_ns),
            'Collision RAM payload changed during inspection.')
    sources = ('tools/inspect_collision_calls.py', 'tools/collision_calls.py', 'tools/verify_collision.py',
               'tools/inspect_dispatch_history.py', 'tools/dispatch_returns.py', 'tools/inspect_sdk_reads.py',
               'tools/psx_image.py', 'tools/replay_cold_start_headless.py')
    return dict(status='inspected_bounded_natural_primitive_calls', recording=recording,
                collision_calls=calls, verifier_sources={name: sha((ROOT / name).read_bytes()) for name in sources},
                new_C_bytes=0, whole_feature_groups_accepted=0)


def compare_calls(reference, candidate, mode='same-runtime'):
    compared = history.compare(reference, candidate, mode)
    before = inspect_calls(reference)
    if mode == 'same-runtime':
        after = inspect_calls(candidate)
        require(before['collision_calls'] == after['collision_calls'],
                'Original/rebuilt primitive snapshots or geometry results differ.')
    return dict(status='compared_bounded_natural_primitive_calls', mode=mode,
                every_recorded_game_output_equal=compared['every_recorded_game_output_equal'],
                complete_sample_records_and_RAM_equal=mode == 'same-runtime', verification=before,
                new_C_bytes=0, whole_feature_groups_accepted=0)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--mode', choices=('same-runtime', 'observer-output'), default='same-runtime')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        output = args.output.resolve()
        require(output.is_relative_to(ROOT / '.decomp-lab') and not output.exists(),
                'Choose a fresh private primitive call report.')
        report = compare_calls(args.reference, args.candidate, args.mode) if args.candidate else inspect_calls(args.reference)
        write_json(output, report)
        print(json.dumps(dict(status=report['status'], output=str(output))))
        return 0
    except (OSError, ValueError, KeyError, struct.error) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
