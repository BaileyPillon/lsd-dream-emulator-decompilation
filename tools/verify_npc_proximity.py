"""Original Bear/Rabbit/Acrobats/Ship with real proximity and spatial methods.

Constructed coordinate/pose graphs with no collider or actor children.
No dependency output stubs; original GTE commands use the checked local bridge.
Natural construction, animation/render/audio and whole encounters remain open.
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
from tools import verify_npc_spatial as spatial
from tools import verify_render_gte as g
from tools import verify_render_rotation as rotation

CALLBACKS = ('entity_bear', 'entity_rabbit', 'entity_acrobats', 'entity_ship')
COORD, POSE = spatial.COORD, spatial.POSE
PLAYER_COORD, PLAYER_ROOT = 0x111000, 0x112000
FUNCTIONS = json.loads((ROOT / 'docs/npc-proximity-function-ranges.json').read_bytes())
pairs = None


def s32(value):
    return (value + 0x80000000) % 0x100000000 - 0x80000000


def s16(value):
    return (value + 0x8000) % 0x10000 - 0x8000


def div(value, divisor):
    if not divisor:
        raise ValueError('Zero-scale/quotient traps are outside normal constructed graphs.')
    return (-1 if (value < 0) != (divisor < 0) else 1) * (abs(value) // abs(divisor))


def distance(position, player):
    dx, dz = s32(position[0] - player[0]), s32(position[2] - player[2])
    dx = s32(-dx) if dx < 0 else dx
    return s32(dx + dz) if dz >= 0 else s32(dx - dz)


def trigger_ratio(position, player, proximity, scale, has_dream=True):
    if not has_dream:
        return -1
    measured = distance(position, player)
    threshold = s32(proximity << 11)
    return div(measured, div(threshold, scale)) if measured <= threshold else -1


def validate_case(case):
    for name in ('tick', 'timer', 'frame', 'state', 'seed', 'entity_id', 'proximity', 'proximity_scale'):
        if type(case[name]) is not int:
            raise ValueError('Use integer state/property fields.')
    if (not 0 <= case['entity_id'] < 130 or not 1 <= case['proximity'] <= 127
            or not 1 <= case['proximity_scale'] <= 1000 or type(case['has_dream']) is not bool):
        raise ValueError('Invalid constructed property/proximity context.')
    for name in ('position', 'player_position', 'scale'):
        if len(case[name]) != 3 or any(type(v) is not int or not -0x80000000 <= v <= 0x7fffffff for v in case[name]):
            raise ValueError('Use three signed-word coordinates/scales.')
    if len(case['euler']) != 3 or any(type(v) is not int or not -32768 <= v <= 32767 for v in case['euler']):
        raise ValueError('Use three signed-halfword angles.')


def fixtures(case):
    validate_case(case)
    base = dict(case, duration=15, variant=0, action=0, ratio=0, nudge=-19)
    entity, dream, context = scripts.fixtures(base)
    n.word(entity, 0x14, COORD)
    n.word(entity, 0x20, 0)  # Valid meshless node: collision processing is inactive.
    n.word(entity, 0x94, n.DREAM if case['has_dream'] else 0)
    n.word(entity, 0x98, case['entity_id'])
    n.word(entity, 0xb0, case['proximity_scale'])
    n.word(dream, 0x0c, PLAYER_ROOT)
    n.word(dream, 0x14, PLAYER_COORD)
    coordinate, pose = spatial.fixtures(case)
    player = bytearray([0x93] * 0x60)
    root = bytearray(0x40)
    n.word(root, 0, n.h.symbols['g_BASE_CLASS_VTABLE'])
    for index, value in enumerate(case['player_position']):
        n.word(player, 0x38 + index * 4, value)
    return {'entity': (n.ENTITY, entity), 'dream': (n.DREAM, dream),
            'context': (n.CONTEXT, context), 'coordinate': (COORD, coordinate),
            'pose': (POSE, pose), 'player_coordinate': (PLAYER_COORD, player),
            'player_root': (PLAYER_ROOT, root), 'linked_child': (scripts.CHILD, scripts.child_fixture())}


def expected(callback, case):
    buffers = fixtures(case)
    entity, context = buffers['entity'][1], buffers['context'][1]
    coordinate, pose = buffers['coordinate'][1], buffers['pose'][1]
    seed, trace, commands, events = n.u32(case['seed']), [], [], []

    def command(index, value):
        n.word(context, index * 4, value)

    def random():
        nonlocal seed
        trace.append(['rand', seed])
        seed = n.u32(seed * 0x41c64e6d + 0x3039)
        return (seed >> 16) & 0x7fff

    def position():
        return struct.unpack_from('<3i', coordinate, 0x18)

    def translate(vector):
        for index, value in enumerate(vector):
            old = struct.unpack_from('<i', coordinate, 0x18 + index * 4)[0]
            n.word(coordinate, 0x18 + index * 4, old + value)
        n.word(coordinate, 0, 0)

    def motion(axis, amount, flag=0):
        amount = s16(amount)
        struct.pack_into('<h', entity, 0x48, amount)
        vector = [0, 0, 0]
        vector[axis] = amount
        matrix = struct.unpack('<9h', rotation.rotation_bytes(struct.unpack_from('<3h', pose, 0x10), pairs))
        moved, sequence = g.apply_model(matrix, vector)
        for command, part, output in zip(g.COMMANDS, g.split_vector(vector), sequence):
            commands.append({'inputs': {'cr': g.matrix_words(matrix), 'ir': list(part), 'command': command},
                             'output': output})
        translate(moved)
        if flag:
            events.append(['func_800571F8', n.ENTITY, {0: 7, 1: 8, 2: 6}[axis]])

    def fractional(symbol, kind):
        source = n.h.target(n.h.symbols[symbol], 12)
        for index in range(3):
            numerator, denominator = struct.unpack_from('<hh', source, index * 4)
            value = div(numerator, denominator) * 4096 + div((numerator - div(numerator, denominator) * denominator) * 4096, denominator)
            if kind == 'scale':
                n.word(pose, index * 4, s16(value))
            else:
                old = struct.unpack_from('<h', pose, 0x10 + index * 2)[0]
                struct.pack_into('<h', pose, 0x10 + index * 2, s16(scripts.signed_remainder(old + div(value, 360), 4096)))
        n.word(coordinate, 0, 0)

    state, tick, frame, timer = case['state'], case['tick'], case['frame'], case['timer']
    if callback in ('entity_bear', 'entity_rabbit'):
        if tick == 0:
            choice = random() % 10
            if choice >= 8:
                fractional('g_EntityOffsetScratch', 'scale')
            elif choice >= 5:
                state = 10
                n.word(entity, 0x44, state)
        if state == 10 and tick >= 201:
            translate(struct.unpack('<3i', n.h.target(n.h.symbols['g_MoveBack256'], 12)))
    command(4, trigger_ratio(position(), case['player_position'], case['proximity'], case['proximity_scale'], case['has_dream']))
    if callback == 'entity_bear':
        if frame in (0, 15):
            command(7, 18)
            command(12, 18)
        if tick >= 321:
            motion(0, -60 if random() & 1 else 60)
            fractional('g_RotateYawNegNine' if random() & 3 else 'g_RotateYawNine', 'rotation')
    elif callback == 'entity_rabbit':
        if frame in (7, 22):
            command(7, 3)
        if n.u32(tick - 300) < 20:
            motion(2, -60)
        elif n.u32(tick - 321) < 19:
            fractional('g_RotateYawNegNine', 'rotation')
        elif tick >= 321:
            motion(0, 128 if random() & 1 else -128, 1)
            fractional('g_RotateYawNegNine' if random() & 3 else 'g_RotateYawNine', 'rotation')
    elif callback == 'entity_acrobats':
        if scripts.signed_remainder(timer, 30) == 0:
            command(7, 13)
    elif callback == 'entity_ship':
        remainder = scripts.signed_remainder(timer, 300)
        if remainder < 20:
            command(7, 5)
            command(8, -2)
        elif remainder == 22:
            command(7, -2)
        motion(2, -10)
    else:
        raise ValueError('Unsupported original callback.')
    return {**{name: bytes(data) for name, (address, data) in buffers.items()},
            'rng_seed': seed, 'rng_trace': trace, 'events': events, 'motion_scratch': bytes(8)}, commands


class Machine(n.Machine):
    def __init__(self, callback, bridge, patches=None, *, native_functions=None, fixture_factory=None):
        functions = FUNCTIONS if native_functions is None else native_functions
        self.fixture_factory = fixtures if fixture_factory is None else fixture_factory
        self.entries, self.hits = Counter(), Counter()
        self.changed_addresses = set()
        self.ranges = [(int(row['address'], 16) & n.MASK, (int(row['address'], 16) & n.MASK) + row['bytes']) for row in functions]
        self.adapter = g.Cop2Adapter(bridge)
        super().__init__(start=n.h.symbols[callback] & n.MASK, native_functions=functions)
        for address, data in (patches or {}).items():
            self.cpu.mem_write(address & n.MASK, data)

    def hook(self, cpu, address, size, unused):
        pc = address & n.MASK
        if not any(start <= pc < end for start, end in self.ranges):
            raise ValueError('Execution left reviewed native ranges: ' + hex(pc))
        if pc in self.native_entries:
            self.entries[self.native_entries[pc]] += 1
        if pc in self.changed_addresses:
            self.hits[pc] += 1
        if pc == n.h.symbols['rand'] & n.MASK:
            self.rng_trace.append(['rand', int.from_bytes(cpu.mem_read(n.RNG, 4), 'little')])
        if pc == n.h.symbols['func_800571F8'] & n.MASK:
            self.events.append(['func_800571F8', cpu.reg_read(n.reg.UC_MIPS_REG_A0), cpu.reg_read(n.reg.UC_MIPS_REG_A1)])
        g.handle_cop2(self.adapter, cpu, pc)

    def run(self, case):
        self.rng_trace, self.events = [], []
        self.adapter.reset()
        buffers = self.fixture_factory(case)
        cpu = self.cpu
        for address, data in buffers.values():
            cpu.mem_write(address, bytes(data))
        cpu.mem_write(n.RNG, struct.pack('<I', n.u32(case['seed'])))
        cpu.mem_write(n.STACK - 0x800, bytes([0xcc]) * 0x900)
        saved = [n.u32(0xab000000 + index * 0x10203) for index in range(len(n.SAVED))]
        for register, value in zip(n.SAVED, saved):
            cpu.reg_write(register, value)
        for register, value in [(n.reg.UC_MIPS_REG_SP, n.STACK), (n.reg.UC_MIPS_REG_GP, 0x8008a808),
                                (n.reg.UC_MIPS_REG_RA, n.END), (n.reg.UC_MIPS_REG_A0, n.ENTITY), (n.reg.UC_MIPS_REG_A1, n.CONTEXT)]:
            cpu.reg_write(register, value)
        cpu.emu_start(self.start, n.END, count=100000)
        if (cpu.reg_read(n.reg.UC_MIPS_REG_PC) != n.END or cpu.reg_read(n.reg.UC_MIPS_REG_SP) != n.STACK
                or cpu.reg_read(n.reg.UC_MIPS_REG_GP) != 0x8008a808
                or [cpu.reg_read(register) for register in n.SAVED] != saved
                or bytes(cpu.mem_read(n.STACK, 0x100)) != bytes([0xcc]) * 0x100
                or bytes(cpu.mem_read(n.STACK - 0x800, 0x100)) != bytes([0xcc]) * 0x100):
            raise ValueError('Original callback violated its return/ABI/stack guards.')
        return {**{name: bytes(cpu.mem_read(address, len(data))) for name, (address, data) in buffers.items()},
                'rng_seed': int.from_bytes(cpu.mem_read(n.RNG, 4), 'little'), 'rng_trace': self.rng_trace,
                'events': self.events, 'motion_scratch': bytes(cpu.mem_read(n.h.symbols['D_8008ABA4'] & n.MASK, 8))}


def base_case(callback, entity_id, proximity):
    return dict(tick=1, timer=1, frame=1, state=0, seed=0, entity_id=entity_id, proximity=proximity,
                proximity_scale=1000, has_dream=True, position=(1000, 2000, 3000), player_position=(0, 9000, 0),
                scale=(4096, 4096, 4096), euler=(0, 0, 0))


def representative_seeds():
    initial, motions = {}, {}
    for seed in range(65536):
        first = n.u32(seed * 0x41c64e6d + 0x3039)
        second = n.u32(first * 0x41c64e6d + 0x3039)
        a, b = (first >> 16) & 0x7fff, (second >> 16) & 0x7fff
        initial.setdefault(a % 10, seed)
        motions.setdefault((a & 1, b & 3), seed)
        if len(initial) == 10 and len(motions) == 8:
            break
    if len(initial) != 10 or len(motions) != 8:
        raise ValueError('Seed profile did not cover initialization and two-draw branches.')
    return sorted(set(initial.values()) | set(motions.values()) | {0, 42, 0xffffffff})


def cases(callback, binding):
    base = base_case(callback, binding['index'], binding['proximity'])
    seeds = representative_seeds()
    if callback in ('entity_bear', 'entity_rabbit'):
        ticks = (-1, 0, 1, 200, 201, 299, 300, 319, 320, 321, 322, 339, 340, 341)
        frames = (-1, 0, 1, 14, 15, 16) if callback == 'entity_bear' else (-1, 6, 7, 8, 21, 22, 23)
        for tick, frame, state, seed in itertools.product(ticks, frames, (0, 10, 11), seeds):
            yield 'behavior_boundaries', dict(base, tick=tick, frame=frame, state=state, seed=seed)
        for tick, state, seed, angles in itertools.product(
                (0, 201, 300, 319, 320, 321, 339, 340, 341), (0, 10), seeds[:8],
                ((0, 1024, 0), (0, -1024, 0), (128, 777, -256), (1023, 2048, 2049), (-32768, -1, 32767))):
            yield 'spatial_boundaries', dict(base, tick=tick, state=state, seed=seed, euler=angles,
                position=(0x7fffffff, -2000, -0x80000000), scale=(-4096, 8192, 2048))
        radius = binding['proximity'] << 11
        for z, tick in itertools.product((radius + 128, -radius + 128), (200, 201, 321, 340)):
            yield 'ratio_after_common_translation', dict(base, state=10, tick=tick, position=(0, 777, z))
    else:
        period = 30 if callback == 'entity_acrobats' else 300
        timers = tuple(range(period)) + (-0x80000000, -period * 2 - 1, -period * 2,
                                        -period - 1, -period, -1, period, period + 1, 0x7fffffff)
        for timer in timers:
            yield 'complete_timer_phases', dict(base, timer=timer)
    radius = binding['proximity'] << 11
    distances = sorted({0, 1, radius // 2 - 1, radius // 2, radius // 2 + 1,
                        radius - 1, radius, radius + 1})
    for distance_value, scale, has_dream, axis in itertools.product(distances, (1, 100, 1000), (False, True), range(5)):
        points = ((distance_value, 12345, 0), (-distance_value, -23456, 0),
                  (0, 0x7fffffff, distance_value), (0, -0x80000000, -distance_value),
                  (distance_value // 2, 17, distance_value - distance_value // 2))
        yield 'native_proximity_boundaries', dict(base, position=points[axis], proximity_scale=scale,
                                                 has_dream=has_dream)


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
            raise ValueError('Callback binding does not fit the positive-radius profile.')
        found[callback] = rows
    return found, hashlib.sha256(table).hexdigest()


def controls(bridge, bound):
    patches = []
    for callback in CALLBACKS:
        record = next(row for row in FUNCTIONS if row['function'] == callback)
        address, length = int(record['address'], 16), record['bytes']
        code = n.h.target(address, length)
        offset = next(i for i in range(0, len(code), 4) if
                      (word := struct.unpack_from('<I', code, i)[0]) >> 26 == 43
                      and (word >> 21) & 31 != 29 and word & 0xffff == 28)
        word, = struct.unpack_from('<I', code, offset)
        case = dict(base_case(callback, bound[callback][0]['index'], bound[callback][0]['proximity']),
                    frame=7 if callback == 'entity_rabbit' else 0, timer=0)
        patches.append((callback + '_wrong_command_slot', callback, address + offset,
                        word, (word & 0xffff0000) | 32, case))
    for function, opcode, immediate, changed, callback in [
            ('entity_get_distance', 35, 32, 28, 'entity_acrobats'),
            ('entity_get_trigger_ratio', 32, None, None, 'entity_acrobats')]:
        record = next(row for row in FUNCTIONS if row['function'] == function)
        address = int(record['address'], 16)
        code = n.h.target(address, record['bytes'])
        matches = [i for i in range(0, len(code), 4) if
                   (word := struct.unpack_from('<I', code, i)[0]) >> 26 == opcode
                   and (word >> 21) & 31 != 29 and (immediate is None or word & 0xffff == immediate)]
        if not matches:
            raise ValueError('No reviewed dependency fault instruction: ' + function)
        offset = matches[0]
        word, = struct.unpack_from('<I', code, offset)
        replacement = (word & 0xffff0000) | (changed if changed is not None else (word + 1) & 0xffff)
        case = base_case(callback, bound[callback][0]['index'], bound[callback][0]['proximity'])
        patches.append((function + '_wrong_field', callback, address + offset, word, replacement, case))
    record = next(row for row in FUNCTIONS if row['function'] == 'func_80057534')
    address = int(record['address'], 16)
    code = n.h.target(address, record['bytes'])
    offset = max(i for i in range(0, len(code), 4) if struct.unpack_from('<I', code, i)[0] & 0xfc00003f == 9)
    word, = struct.unpack_from('<I', code, offset)
    callback = 'entity_rabbit'
    case = dict(base_case(callback, bound[callback][0]['index'], bound[callback][0]['proximity']), tick=340)
    patches.append(('omit_flagged_movement_event', callback, address + offset, word, 0, case))
    results = []
    for name, callback, pc, original, changed, case in patches:
        actual_word, = struct.unpack('<I', n.h.target(pc, 4))
        if actual_word != original:
            raise ValueError('Fault address no longer identifies its original instruction.')
        machine = Machine(callback, bridge, {pc: struct.pack('<I', changed)})
        machine.changed_addresses.add(pc & n.MASK)
        model, commands = expected(callback, case)
        observed = machine.run(case)
        if observed == model and machine.adapter.commands == commands:
            raise ValueError('Undetected original-code fault: ' + name)
        hits = machine.hits[pc & n.MASK]
        if not hits:
            raise ValueError('Fault fixture never executed the changed instruction.')
        results.append({'kind': name, 'callback': callback, 'address': hex(pc),
                        'expected_word': hex(original), 'changed_word': hex(changed),
                        'changed_instruction_executions': hits,
                        'scope': 'Private original-code emulator memory only; original inputs unchanged.'})
    return results


def verify(output, executable, runtime):
    global pairs
    output = Path(output).resolve()
    if not output.is_relative_to((ROOT / '.decomp-lab').resolve()) or output.exists():
        raise ValueError('Choose a fresh private evidence directory inside .decomp-lab.')
    dependencies = n.evidence_dependencies('tools/verify_npc_proximity.py', 'tools/verify_scripted_ai.py',
        'tools/verify_npc_spatial.py', 'tools/verify_render_gte.py', 'tools/verify_render_rotation.py',
        'docs/npc-proximity-function-ranges.json', 'src/scene/scene_node.c', 'src/base/object_math.c')
    preserved = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    n.initialize_backend(n.load_program(FUNCTIONS))
    pairs = rotation.table_pairs(n.h)
    bound, table_hash = bindings()
    backend = scripts.backend_identity()
    executable = Path(executable).resolve(strict=True)
    bridge_hash = hashlib.sha256(executable.read_bytes()).hexdigest()
    output.mkdir(parents=True, exist_ok=False)
    bridge = g.NativeGteBridge(executable, runtime, output / 'gte.log')
    counts, entries, total, started = Counter(), Counter(), 0, time.monotonic()
    digest = hashlib.sha256()
    try:
        for callback in CALLBACKS:
            machine = Machine(callback, bridge)
            for binding in bound[callback]:
                seen = set()
                for group, case in cases(callback, binding):
                    key = json.dumps(case, sort_keys=True)
                    if key in seen:
                        continue
                    seen.add(key)
                    model, commands = expected(callback, case)
                    observed = machine.run(case)
                    if observed != model or machine.adapter.commands != commands:
                        (output / 'failure.json').write_bytes((json.dumps({'callback': callback, 'case': case,
                            'native': repr(observed), 'model': repr(model), 'native_commands': machine.adapter.commands,
                            'model_commands': commands}, indent=2) + '\n').encode())
                        raise ValueError('Original callback differs from independent full-buffer/GTE rules.')
                    digest.update(repr(observed).encode())
                    counts[(callback, group)] += 1
                    total += 1
                    if total % 500 == 0:
                        print('NPC proximity cases', total, 'passed', flush=True)
            entries.update(machine.entries)
            print(callback, 'passed', flush=True)
        faults = controls(bridge, bound)
    finally:
        bridge.close()
    if (scripts.backend_identity() != backend or hashlib.sha256(executable.read_bytes()).hexdigest() != bridge_hash
            or n.check_build_current(ROOT) is not True
            or any(hashlib.sha256(path.read_bytes()).hexdigest() != expected for path, expected in preserved.items())):
        raise ValueError('Source/build/backend inputs changed during callback verification.')
    report = {'status': 'passed_bounded_original_npc_proximity_composition', 'callbacks': list(CALLBACKS),
              'native_cases': total, 'cases_by_group': [{'callback': cb, 'group': group, 'cases': count}
                                                       for (cb, group), count in sorted(counts.items())],
              'property_bindings': bound, 'property_table_sha256': table_hash,
              'executed_native_entry_counts': dict(entries), 'native_gte_commands': bridge.count,
              'dependency_output_stubs': 0, 'checked_buffers_sha256': digest.hexdigest(),
              'negative_controls_detected': faults, 'backend_identity': backend,
              'bridge_executable_sha256': bridge_hash,
              'preserved_dependencies': [{'path': str(path), 'sha256': value} for path, value in preserved.items()],
              'source_promoted': False, 'whole_callback_acceptances': 0, 'whole_feature_groups_accepted': 0,
              'model_api_calls': 0, 'elapsed_seconds': round(time.monotonic() - started, 3),
              'scope': 'Four original callbacks, real RNG/distance/ratio, spatial/pose helpers and checked native GTE. '
                       'Valid constructed graphs have no collider or actor children. Full buffers, ordered GTE/flagged events, '
                       'ABI and original property bindings are checked. Excludes natural construction/encounters, '
                       'zero-scale/quotient traps, animation/render/audio output and PS1 scheduling/timing.'}
    (output / 'report.json').write_bytes((json.dumps(report, indent=2) + '\n').encode())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--bridge', required=True, type=Path)
    parser.add_argument('--runtime', required=True)
    args = parser.parse_args()
    report = verify(args.output, args.bridge, args.runtime)
    print(json.dumps({'status': report['status'], 'native_cases': report['native_cases'],
                      'native_gte_commands': report['native_gte_commands']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
