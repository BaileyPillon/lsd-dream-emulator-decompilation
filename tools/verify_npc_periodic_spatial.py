"""Original Bird/Minotaur/Giant Minotaur with real proximity and movement.

Only constructed meshless, childless graphs are covered. This developer check
does not add game behavior, invoke an AI model, or accept whole encounters.
The original callbacks and helpers execute without dependency-output stubs.
"""
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import itertools
import json
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import verify_native_ai as n
from tools import verify_scripted_ai as scripts
from tools import verify_npc_proximity as proximity
from tools import verify_render_gte as g
from tools import verify_render_rotation as rotation

CALLBACKS = ('entity_bird', 'entity_minotaur', 'entity_giant_minotaur')
FUNCTIONS = json.loads((ROOT / 'docs/npc-periodic-spatial-function-ranges.json').read_bytes())
pairs = None


def half_duration(duration):
    word = n.u32(duration)
    return proximity.s32(n.u32(word + (word >> 31))) >> 1


def validate_case(callback, case):
    if callback not in CALLBACKS:
        raise ValueError('Unsupported original periodic callback.')
    proximity.validate_case(case)
    if type(case['duration']) is not int or not -0x80000000 <= case['duration'] <= 0xffffffff:
        raise ValueError('Duration must fit an original word.')
    for field in ('tick', 'timer', 'frame', 'state'):
        if not -0x80000000 <= case[field] <= 0x7fffffff:
            raise ValueError('Callback state must fit a signed word.')
    if not 0 <= case['seed'] <= 0xffffffff:
        raise ValueError('RNG seed must fit an unsigned word.')
    if callback == 'entity_minotaur':
        half = half_duration(case['duration'])
        if not half or (case['timer'] == -0x80000000 and half == -1):
            raise ValueError('Original zero-divisor and signed-overflow BREAK paths remain unverified.')


def fixtures(case):
    buffers = proximity.fixtures(case)
    n.word(buffers['entity'][1], 0x80, case['duration'])
    return buffers


def expected(callback, case):
    validate_case(callback, case)
    buffers = fixtures(case)
    entity, context = buffers['entity'][1], buffers['context'][1]
    coordinate, pose = buffers['coordinate'][1], buffers['pose'][1]
    commands = []

    def command(index, value):
        n.word(context, index * 4, value)

    timer = case['timer']
    if callback == 'entity_minotaur' or (callback == 'entity_bird' and scripts.signed_remainder(timer, 15) == 0):
        command(4, proximity.trigger_ratio(case['position'], case['player_position'],
                  case['proximity'], case['proximity_scale'], case['has_dream']))
    if callback == 'entity_bird':
        if scripts.signed_remainder(timer, 15) == 0:
            command(7, 7)
            command(8, -2)
        for index in range(3):
            n.word(pose, index * 4, 8192)  # Original g_OffsetTwo: 2/1 on all axes.
        old_yaw = struct.unpack_from('<h', pose, 0x12)[0]
        # Original 2 degrees, converted by the fixed-point fraction helper.
        delta = (2 * 4096) // 360
        for index in range(3):
            offset = 0x10 + index * 2
            old = old_yaw if index == 1 else struct.unpack_from('<h', pose, offset)[0]
            value = scripts.signed_remainder(old + (delta if index == 1 else 0), 4096)
            struct.pack_into('<h', pose, offset, proximity.s16(value))
        amount = -512
    elif callback == 'entity_minotaur':
        if scripts.signed_remainder(timer, half_duration(case['duration'])) == 0:
            command(7, 10)
        amount = -30
    else:
        command(4, 0)
        if timer == 0:
            for index in (7, 12, 17):
                command(index, 11)
        amount = -30
    struct.pack_into('<h', entity, 0x48, amount)
    matrix = struct.unpack('<9h', rotation.rotation_bytes(struct.unpack_from('<3h', pose, 0x10), pairs))
    vector = (0, 0, amount)
    moved, outputs = g.apply_model(matrix, vector)
    for word, part, output in zip(g.COMMANDS, g.split_vector(vector), outputs):
        commands.append({'inputs': {'cr': g.matrix_words(matrix), 'ir': list(part), 'command': word},
                         'output': output})
    for index, value in enumerate(moved):
        n.word(coordinate, 0x18 + index * 4, case['position'][index] + value)
    n.word(coordinate, 0, 0)
    return {**{name: bytes(data) for name, (address, data) in buffers.items()},
            'rng_seed': case['seed'], 'rng_trace': [], 'events': [], 'motion_scratch': bytes(8)}, commands


def base_case(binding):
    return dict(proximity.base_case('', binding['index'], binding['proximity']), duration=15)


def cases(callback, binding):
    base = base_case(binding)
    if callback == 'entity_minotaur':
        durations = (2, 3, 4, 5, 15, 30, 59, 60, 61, 120, -2, -3, -4, -5, -59, -60, -61,
                     -0x80000000, 0x7fffffff)
        for duration in durations:
            half = half_duration(duration)
            timers = set(range(min(abs(half), 60)))
            timers.update((-0x80000000, -1, 0, 1, 0x7fffffff))
            timers.update(k * half + edge for k in (-2, -1, 1, 2) for edge in (-1, 0, 1))
            for timer in sorted(timers):
                if not -0x80000000 <= timer <= 0x7fffffff or (timer == -0x80000000 and half == -1):
                    continue
                yield 'duration_and_signed_timer_boundaries', dict(base, duration=duration, timer=timer)
    else:
        timers = list(range(45)) if callback == 'entity_bird' else []
        for timer in sorted(set(timers + [-0x80000000, -31, -30, -16, -15, -14, -1, 0, 1, 15, 45, 46, 0x7fffffff])):
            yield 'periodic_or_zero_timer_branches', dict(base, timer=timer)
    if callback != 'entity_giant_minotaur':
        radius = binding['proximity'] << 11
        distances = (0, 1, radius // 2, radius - 1, radius, radius + 1, radius + 30, radius + 511)
        for measured, axis, scale, dream, timer in itertools.product(distances, range(5), (1, 100, 1000), (False, True), (-15, 0, 1)):
            points = ((measured, 12345, 0), (-measured, -23456, 0), (0, 0x7fffffff, measured),
                      (0, -0x80000000, -measured), (measured // 2, 17, measured - measured // 2))
            yield 'ratio_before_motion_and_radius_boundaries', dict(base, timer=timer, position=points[axis],
                  proximity_scale=scale, has_dream=dream)
    for euler, position, scale, timer in itertools.product(
            ((0, 0, 0), (0, 1024, 0), (0, -1024, 0), (128, 777, -256), (1023, 2048, 2049),
             (-32768, -1, 32767), (4095, -4095, 4096)),
            ((1000, 2000, 3000), (0x7fffffff, -2000, -0x80000000), (-0x80000000, 17, 0x7fffffff)),
            ((4096, 4096, 4096), (-4096, 8192, 2048)), (-15, 0, 1, 15)):
        yield 'pose_word_wrap_and_preserved_buffers', dict(base, euler=euler, position=position, scale=scale,
                                                         timer=timer, seed=0xffffffff if timer < 0 else 42)


def bindings():
    table = n.h.target(n.h.symbols['g_ENTITY_TABLE'], 130 * 16)
    found = {}
    for callback in CALLBACKS:
        rows = []
        for index in range(130):
            data = table[index * 16:index * 16 + 16]
            if struct.unpack_from('<I', data, 12)[0] == n.h.symbols[callback]:
                rows.append({'index': index, 'proximity': struct.unpack_from('<b', data, 10)[0],
                             'record_sha256': hashlib.sha256(data).hexdigest()})
        if not rows or any(row['proximity'] <= 0 for row in rows):
            raise ValueError('Original callback/property bindings changed.')
        found[callback] = rows
    return found, hashlib.sha256(table).hexdigest()


def input_key(case):
    # Deduplicate initialized memory and RNG, including fields the callback ignores.
    initialized = [(name, address, bytes(data).hex()) for name, (address, data) in sorted(fixtures(case).items())]
    return json.dumps([initialized, case['seed']], separators=(',', ':')).encode()


def machine(callback, bridge, patches=None):
    return proximity.Machine(callback, bridge, patches, native_functions=FUNCTIONS, fixture_factory=fixtures)


def controls(bridge, bound):
    specifications = [
        ('entity_bird', 'entity_bird', 43, 28, 32, 'bird_wrong_command_destination'),
        ('entity_minotaur', 'entity_minotaur', 43, 28, 32, 'minotaur_wrong_command_destination'),
        ('entity_giant_minotaur', 'entity_giant_minotaur', 43, 48, 52, 'giant_missing_second_command'),
        ('entity_get_distance', 'entity_minotaur', 35, 32, 28, 'distance_wrong_z_field'),
        ('entity_get_trigger_ratio', 'entity_bird', 32, None, None, 'ratio_wrong_property_byte'),
        ('func_80057534', 'entity_minotaur', 41, 72, 74, 'motion_wrong_nudge_halfword'),
    ]
    results = []
    for function, callback, opcode, immediate, changed, name in specifications:
        record = next(row for row in FUNCTIONS if row['function'] == function)
        address = int(record['address'], 16)
        code = n.h.target(address, record['bytes'])
        offsets = [offset for offset in range(0, len(code), 4) if
                   (word := struct.unpack_from('<I', code, offset)[0]) >> 26 == opcode
                   and (word >> 21) & 31 != 29 and (immediate is None or word & 0xffff == immediate)]
        if not offsets:
            raise ValueError('No reviewed fault instruction: ' + function)
        offset = offsets[0]
        original = struct.unpack_from('<I', code, offset)[0]
        replacement = (original & 0xffff0000) | (changed if changed is not None else (original + 1) & 0xffff)
        case = dict(base_case(bound[callback][0]), timer=0)
        model, commands = expected(callback, case)
        faulty = machine(callback, bridge, {address + offset: struct.pack('<I', replacement)})
        faulty.changed_addresses.add((address + offset) & n.MASK)
        actual = faulty.run(case)
        differences = [key for key in model if actual[key] != model[key]]
        hits = faulty.hits[(address + offset) & n.MASK]
        if not differences or not hits:
            raise ValueError('Fault must execute and change a checked buffer: ' + name)
        results.append(dict(kind=name, function=function, callback=callback, address=hex(address + offset),
                            expected_word=hex(original), changed_word=hex(replacement),
                            changed_instruction_executions=hits, changed_checked_fields=differences))
    record = next(row for row in FUNCTIONS if row['function'] == 'ApplyMatrixLV')
    address = int(record['address'], 16)
    code = n.h.target(address, record['bytes'])
    offsets = [i for i in range(0, len(code), 4) if struct.unpack_from('<I', code, i)[0] == g.COMMANDS[1]]
    if len(offsets) != 1:
        raise ValueError('Original low-part GTE command is not unique.')
    pc = address + offsets[0]
    callback = 'entity_minotaur'
    case = base_case(bound[callback][0])
    model, _ = expected(callback, case)
    faulty = machine(callback, bridge, {pc: struct.pack('<I', g.COMMANDS[0])})
    faulty.changed_addresses.add(pc & n.MASK)
    actual = faulty.run(case)
    differences = [key for key in model if actual[key] != model[key]]
    hits = faulty.hits[pc & n.MASK]
    if not differences or not hits:
        raise ValueError('Changed GTE shift must execute and change a checked buffer.')
    results.append(dict(kind='wrong_native_gte_shift', function='ApplyMatrixLV', callback=callback,
        address=hex(pc), expected_word=hex(g.COMMANDS[1]), changed_word=hex(g.COMMANDS[0]),
        changed_instruction_executions=hits, changed_checked_fields=differences))
    return results


def verify(output, executable, runtime):
    global pairs
    output = Path(output).resolve()
    if not output.is_relative_to((ROOT / '.decomp-lab').resolve()) or output.exists():
        raise ValueError('Choose a fresh private evidence directory inside .decomp-lab.')
    dependencies = n.evidence_dependencies('tools/verify_npc_periodic_spatial.py', 'tools/verify_npc_proximity.py',
        'tools/verify_scripted_ai.py', 'tools/verify_npc_spatial.py', 'tools/verify_render_gte.py',
        'tools/verify_render_rotation.py', 'tools/nymashock_gte_bridge.cs',
        'docs/npc-periodic-spatial-function-ranges.json', 'docs/npc-proximity-function-ranges.json',
        'src/scene/scene_node.c', 'src/base/object_math.c')
    preserved = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    n.initialize_backend(n.load_program(FUNCTIONS))
    pairs = rotation.table_pairs(n.h)
    bound, table_hash = bindings()
    backend = scripts.backend_identity()
    executable = Path(executable).resolve(strict=True)
    bridge_hash = hashlib.sha256(executable.read_bytes()).hexdigest()
    output.mkdir(parents=True, exist_ok=False)
    bridge = g.NativeGteBridge(executable, runtime, output / 'gte.log')
    counts, entries, duplicates, started = Counter(), Counter(), 0, time.monotonic()
    input_digest, output_digest = hashlib.sha256(), hashlib.sha256()
    try:
        for callback in CALLBACKS:
            original = machine(callback, bridge)
            seen = set()
            for binding in bound[callback]:
                for group, case in cases(callback, binding):
                    validate_case(callback, case)
                    key = input_key(case)
                    if key in seen:
                        duplicates += 1
                        continue
                    seen.add(key)
                    model, commands = expected(callback, case)
                    actual = original.run(case)
                    if actual != model or original.adapter.commands != commands:
                        (output / 'failure.json').write_text(json.dumps(dict(callback=callback, case=case,
                            actual=repr(actual), expected=repr(model), native_commands=original.adapter.commands,
                            model_commands=commands), indent=2) + '\n')
                        raise ValueError('Original callback differs from full-buffer/GTE rules: ' + callback)
                    input_digest.update(callback.encode() + b'\0' + len(key).to_bytes(4, 'little') + key)
                    output_digest.update(repr(actual).encode())
                    counts[(callback, group)] += 1
            entries.update(original.entries)
            print(callback, len(seen), 'distinct initialized inputs passed', flush=True)
        commands_before_controls = bridge.count
        faults = controls(bridge, bound)
    finally:
        bridge.close()
    if (scripts.backend_identity() != backend or hashlib.sha256(executable.read_bytes()).hexdigest() != bridge_hash
            or (ROOT / n.configure.ROM).read_bytes() != n.h.ROM or (ROOT / n.configure.EXE).read_bytes() != n.h.ROM
            or n.check_build_current(ROOT) is not True
            or any(hashlib.sha256(path.read_bytes()).hexdigest() != value for path, value in preserved.items())):
        raise ValueError('Source/build/backend inputs changed during callback verification.')
    report = dict(status='passed_bounded_original_periodic_npc_spatial_composition', callbacks=list(CALLBACKS),
        native_cases=sum(counts.values()), duplicate_initialized_inputs_skipped=duplicates,
        cases_by_group=[dict(callback=cb, group=group, cases=count) for (cb, group), count in sorted(counts.items())],
        property_bindings=bound, property_table_sha256=table_hash, native_functions=FUNCTIONS,
        executed_native_entry_counts=dict(entries), native_gte_commands=commands_before_controls,
        native_gte_control_commands=bridge.count - commands_before_controls, dependency_output_stubs=0,
        initialized_inputs_sha256=input_digest.hexdigest(), checked_buffers_sha256=output_digest.hexdigest(),
        negative_controls_detected=faults, backend_identity=backend, bridge_executable_sha256=bridge_hash,
        nymashock_compressed_core_sha256=g.CORE_SHA256,
        preserved_dependencies=[dict(path=path.relative_to(ROOT).as_posix(), sha256=value) for path, value in preserved.items()],
        canonical_original_and_build_equal=True, source_promoted=False, new_bounded_callbacks=2,
        whole_callback_acceptances=0, whole_feature_groups_accepted=0, model_api_calls=0,
        original_game_behavior_modified=False, elapsed_seconds=round(time.monotonic() - started, 3),
        scope='Three original callbacks and real proximity/transform/SDK/GTE. Bird ratio is read before movement; '
              'Minotaur uses signed half-duration periods; Giant Minotaur has its own zero-timer commands. '
              'Constructed meshless graphs, no actor children. Full buffers, ordered GTE, ABI, signed/word boundaries. '
              'Excludes natural construction/encounters, lifecycle histories, zero-divisor/overflow BREAK paths, '
              'drawing/audio and PS1 scheduling/timing. No whole-NPC or whole-feature acceptance.')
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--bridge', required=True, type=Path)
    parser.add_argument('--runtime', required=True)
    args = parser.parse_args()
    report = verify(args.output, args.bridge, args.runtime)
    print(json.dumps({key: report[key] for key in ('status', 'native_cases', 'native_gte_commands')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
