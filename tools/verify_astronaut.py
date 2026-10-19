"""Bounded original Astronaut script with native mood, proximity and movement.

Constructed meshless poses, injected script ticks and command timers; no full
engine stepping, natural encounter, rendering/audio or PS1 timing acceptance.
No model API, original-game modification or dependency-output substitution.
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
from tools import verify_locomotive_scripts as locomotive
from tools import verify_render_gte as g
from tools import verify_render_rotation as rotation
from tools.verify_gunman_scripts import store_span

CALLBACK = 'entity_astronaut'
RANGE_FILE = ROOT / 'docs/astronaut-function-ranges.json'
FUNCTIONS = json.loads(RANGE_FILE.read_bytes())
DATA = {
    'g_MoveUp64Back64': struct.pack('<iii', 0, 64, -64),
    'g_RotateYawNeg120': struct.pack('<6h', 0, 1, -120, 1, 0, 1),
    'g_Rotate5050Neg12030': struct.pack('<6h', 50, 1, -120, 1, 30, 1),
    'g_DreamColorTable': bytes.fromhex('060702040701030005000000'),
}
pairs = None


def base_case(binding):
    case = proximity.base_case(CALLBACK, binding['index'], binding['proximity'])
    case.update(chunk_mood=(0, 0, 0, 0, 0), instance_mood=(0, 0, 0, 0, 0))
    return case


def validate_case(case):
    proximity.validate_case(case)
    if not case['has_dream']:
        raise ValueError('This profile requires the Astronaut dream context.')
    for field in ('tick', 'timer', 'frame', 'state'):
        if not -0x80000000 <= case[field] <= 0x7fffffff:
            raise ValueError('Use signed native callback words.')
    if not 0 <= case['seed'] <= 0xffffffff:
        raise ValueError('Use an unsigned native RNG seed.')
    for field in ('chunk_mood', 'instance_mood'):
        mood = case[field]
        if (not isinstance(mood, (tuple, list)) or len(mood) != 5
                or any(type(value) is not int for value in mood)
                or any(not -128 <= value <= 127 for value in mood[:2])
                or any(not -0x80000000 <= value <= 0x7fffffff for value in mood[2:])):
            raise ValueError('Use signed mood-axis bytes, word sums and count.')
        if mood[4] == -1 and -0x80000000 in mood[2:4]:
            raise ValueError('Signed-division trap inputs are outside this normal-return profile.')


def fixtures(case):
    validate_case(case)
    buffers = proximity.fixtures(case)
    entity, dream = buffers['entity'][1], buffers['dream'][1]
    # No collision/link target is installed; the retained child buffer is inert.
    n.word(entity, 0x4c, 0)
    for offset, key in ((0x144, 'chunk_mood'), (0x154, 'instance_mood')):
        dynamic, upper, total_dynamic, total_upper, count = case[key]
        struct.pack_into('<bb', dream, offset, dynamic, upper)
        struct.pack_into('<iii', dream, offset + 4, total_dynamic, total_upper, count)
    return buffers


def input_key(case):
    initialized = [(name, address, bytes(data).hex())
                   for name, (address, data) in sorted(fixtures(case).items())]
    return json.dumps([initialized, case['seed']], separators=(',', ':')).encode()


def expected(case, previous=None):
    """Predict buffers and native GTE requests without reading executed output."""
    validate_case(case)
    initialized = fixtures(case)
    buffers = {name: bytearray(data if previous is None else previous[name])
               for name, (_address, data) in initialized.items()}
    entity, dream, context = (buffers[name] for name in ('entity', 'dream', 'context'))
    coordinate, pose = buffers['coordinate'], buffers['pose']
    if previous is not None:
        n.word(entity, 0xfc, case['tick'])
        n.word(context, 4, case['timer'])
    trace, commands = [], []

    def command(index, value):
        n.word(context, index * 4, value)

    def translate(vector):
        for index, value in enumerate(vector):
            offset = 0x18 + index * 4
            old = struct.unpack_from('<i', coordinate, offset)[0]
            n.word(coordinate, offset, old + value)
        n.word(coordinate, 0, 0)

    def forward(amount):
        trace.append(['forward', n.ENTITY, n.u32(amount), 0])
        struct.pack_into('<h', entity, 0x48, proximity.s16(amount))
        matrix = struct.unpack('<9h', rotation.rotation_bytes(struct.unpack_from('<3h', pose, 0x10), pairs))
        vector = (0, 0, proximity.s16(amount))
        moved, results = g.apply_model(matrix, vector)
        for word, part, result in zip(g.COMMANDS, g.split_vector(vector), results):
            commands.append({'inputs': {'cr': g.matrix_words(matrix), 'ir': list(part), 'command': word},
                             'output': result})
        trace.append(['movement_translation', n.ENTITY, struct.pack('<3i', *moved).hex()])
        translate(moved)

    def rotate(symbol):
        data = DATA[symbol]
        trace.append(['rotation', n.ENTITY, 1, n.h.symbols[symbol], data.hex()])
        for index in range(3):
            numerator, denominator = struct.unpack_from('<hh', data, index * 4)
            value = proximity.div(numerator, denominator) * 4096
            value += proximity.div(scripts.signed_remainder(numerator, denominator) * 4096, denominator)
            struct.pack_into('<h', pose, 0x10 + index * 2, proximity.s16(proximity.div(value, 360)))
        n.word(coordinate, 0, 0)

    state = struct.unpack_from('<i', entity, 0x44)[0]
    tick, timer = case['tick'], case['timer']
    if timer == 0:
        trace.append(['read_dream_color', n.DREAM])
        chunk, instance = locomotive.mood_average(dream, 0x144), locomotive.mood_average(dream, 0x154)
        trace.extend([['chunk_average', *chunk], ['instance_average', *instance]])
        if struct.unpack_from('<i', dream, 0x160)[0] == 0:
            instance = chunk
        average = tuple(proximity.div(a + b, 2) for a, b in zip(chunk, instance))
        bins = [2 if value >= 4 else 0 if value < -3 else 1 for value in average]
        color = DATA['g_DreamColorTable'][bins[0] * 3 + bins[1]]
        trace.append(['dream_color', color])
        if color == 5:
            state = 100
            n.word(entity, 0x44, state)
    position = struct.unpack_from('<3i', coordinate, 0x18)
    player_position = struct.unpack_from('<3i', buffers['player_coordinate'], 0x38)
    ratio = proximity.trigger_ratio(position, player_position, case['proximity'], case['proximity_scale'])
    trace.extend([['read_trigger_ratio', n.ENTITY], ['trigger_ratio', n.u32(ratio)]])
    command(4, ratio)
    if state == 0:
        if scripts.signed_remainder(timer, 10) == 0:
            command(7, 5)
            command(8, -2)
        if tick == 2400:
            n.word(entity, 0xfc, -1)
        else:
            forward(50 if tick < 1200 else -50)
    elif tick < 250:
        if scripts.signed_remainder(timer, 10) == 0:
            command(7, 5)
            command(8, -2)
        if tick < 100:
            forward(50)
        else:
            trace.append(['translation', n.ENTITY, n.h.symbols['g_MoveUp64Back64'],
                          DATA['g_MoveUp64Back64'].hex()])
            translate((0, 64, -64))
    elif tick == 250:
        trace.append(['animation_stop', n.ENTITY])
        n.word(entity, 0x90, 0)
        command(7, -2)
    elif n.u32(tick - 261) < 307:
        forward(-50)
        rotate('g_RotateYawNeg120')
    elif tick >= 569:
        rotate('g_Rotate5050Neg12030')
    result = {name: bytes(data) for name, data in buffers.items()}
    result.update(rng_seed=case['seed'] if previous is None else previous['rng_seed'],
                  trace=trace, motion_scratch=bytes(8))
    return result, commands


class Machine(proximity.Machine):
    def __init__(self, bridge, patches=None, *, callback=CALLBACK, native_functions=FUNCTIONS,
                 fixture_factory=fixtures, case_validator=validate_case, context_address=n.CONTEXT):
        self.case_validator, self.context_address = case_validator, context_address
        super().__init__(callback, bridge, patches, native_functions=native_functions, fixture_factory=fixture_factory)
        self.changed_addresses.update(address & n.MASK for address in (patches or {}))
        self.observed = {
            'dream_sys_get_dream_color': ('read_dream_color', 1),
            'entity_get_trigger_ratio': ('read_trigger_ratio', 1),
            'func_8005748C': ('forward', 3), 'func_8001CEB4': ('rotation', 3),
            'func_800573A8': ('translation', 2), 'func_800662B4': ('animation_stop', 1),
        }

    def arguments(self, count):
        return [self.cpu.reg_read(getattr(n.reg, 'UC_MIPS_REG_A' + str(index))) for index in range(count)]

    def check_store(self, cpu, word, instruction, observed_at, link=None):
        number = word >> 21 & 31
        base = cpu.reg_read(getattr(n.reg, 'UC_MIPS_REG_' + str(number)))
        if word >> 26 == 58:  # SWC2, before the COP2 adapter handles it.
            immediate = ((word & 0xffff) ^ 0x8000) - 0x8000
            span = ((base + immediate) & n.MASK, 4)
        else:
            span = store_span(word, base)
        if span is None:
            return
        if number == link:
            raise ValueError('A delay-slot store based on the changed link register needs review.')
        address, size = span
        regions = [(start, start + len(data)) for start, data in self.initial.values()]
        regions.extend(((n.RNG, n.RNG + 4), (n.STACK - 0x800, n.STACK + 0x100),
                        (n.h.symbols['D_8008ABA4'] & n.MASK, (n.h.symbols['D_8008ABA4'] & n.MASK) + 8)))
        if not any(start <= address and address + size <= end for start, end in regions):
            self.rejected_store = dict(instruction=instruction, observed_at=observed_at, address=address, bytes=size)
            raise ValueError('Native write escaped declared buffers: ' + hex(address))

    def hook(self, cpu, address, size, unused):
        pc = address & n.MASK
        returned = self.pending_returns.pop(pc, None)
        if returned is not None:
            label, destination = returned
            values = ([cpu.reg_read(n.reg.UC_MIPS_REG_V0)] if destination is None
                      else list(struct.unpack('<bb', cpu.mem_read(destination, 2))))
            self.trace.append([label, *values])
        name = self.native_entries.get(pc)
        if name in self.observed:
            label, count = self.observed[name]
            event = [label, *self.arguments(count)]
            if label in ('rotation', 'translation'):
                event.append(bytes(cpu.mem_read(event[-1] & n.MASK, 12)).hex())
            if label == 'translation' and event[2] != n.h.symbols['g_MoveUp64Back64']:
                vector_address = event[2] & n.MASK
                if vector_address % 4 or not n.STACK - 0x800 <= vector_address < vector_address + 12 <= n.STACK:
                    raise ValueError('Expected the native movement vector inside the guarded stack.')
                event = ['movement_translation', event[1], event[3]]
            self.trace.append(event)
        if name in ('dream_sys_get_dream_color', 'dream_sys_get_mood_average', 'entity_get_trigger_ratio'):
            target = cpu.reg_read(n.reg.UC_MIPS_REG_RA) & n.MASK
            if target in self.pending_returns:
                raise ValueError('Unexpected nested observed return site.')
            if name == 'dream_sys_get_mood_average':
                _, source, destination = self.arguments(3)
                if source not in (n.DREAM + 0x144, n.DREAM + 0x154):
                    raise ValueError('Unexpected mood contribution pointer.')
                label = 'chunk_average' if source == n.DREAM + 0x144 else 'instance_average'
                self.pending_returns[target] = (label, destination & n.MASK)
            else:
                self.pending_returns[target] = ('dream_color' if name == 'dream_sys_get_dream_color' else 'trigger_ratio', None)
        word = struct.unpack('<I', cpu.mem_read(pc, 4))[0]
        opcode = word >> 26
        branch = opcode in (1, 2, 3, 4, 5, 6, 7) or opcode == 0 and word & 63 in (8, 9)
        if branch:
            delay = struct.unpack('<I', cpu.mem_read(pc + 4, 4))[0]
            link = (31 if opcode == 3 or opcode == 1 and word >> 16 & 31 in (16, 17)
                    else word >> 11 & 31 if opcode == 0 and word & 63 == 9 else None)
            self.check_store(cpu, delay, pc + 4, pc, link)
        self.check_store(cpu, word, pc, pc)
        super().hook(cpu, address, size, unused)

    def run(self, case, reset=True):
        self.case_validator(case)
        self.initial = self.fixture_factory(case)
        self.trace, self.pending_returns, self.rng_trace, self.events = [], {}, [], []
        self.hits.clear()
        self.rejected_store = None
        self.adapter.reset()
        cpu = self.cpu
        if reset:
            for address, data in self.initial.values():
                cpu.mem_write(address, bytes(data))
            cpu.mem_write(n.RNG, struct.pack('<I', case['seed']))
            cpu.mem_write(n.h.symbols['D_8008ABA4'] & n.MASK, bytes(8))
        else:
            cpu.mem_write(n.ENTITY + 0xfc, struct.pack('<I', n.u32(case['tick'])))
            cpu.mem_write(self.context_address + 4, struct.pack('<I', n.u32(case['timer'])))
        cpu.mem_write(n.STACK - 0x800, bytes([0xcc]) * 0x900)
        saved = [n.u32(0xab000000 + index * 0x10203) for index in range(len(n.SAVED))]
        for register, value in zip(n.SAVED, saved):
            cpu.reg_write(register, value)
        for index, register in enumerate(n.VOLATILE):
            cpu.reg_write(register, n.u32(0xda000000 + index * 0x10203))
        for register, value in ((n.reg.UC_MIPS_REG_SP, n.STACK), (n.reg.UC_MIPS_REG_GP, 0x8008a808),
                (n.reg.UC_MIPS_REG_RA, n.END), (n.reg.UC_MIPS_REG_A0, n.ENTITY), (n.reg.UC_MIPS_REG_A1, self.context_address)):
            cpu.reg_write(register, value)
        cpu.emu_start(self.start, n.END, count=100000)
        if (cpu.reg_read(n.reg.UC_MIPS_REG_PC) != n.END or cpu.reg_read(n.reg.UC_MIPS_REG_SP) != n.STACK
                or cpu.reg_read(n.reg.UC_MIPS_REG_GP) != 0x8008a808 or cpu.reg_read(n.reg.UC_MIPS_REG_RA) != n.END
                or [cpu.reg_read(register) for register in n.SAVED] != saved or self.pending_returns
                or bytes(cpu.mem_read(n.STACK - 0x800, 64)) != bytes([0xcc]) * 64
                or bytes(cpu.mem_read(n.STACK + 0x40, 64)) != bytes([0xcc]) * 64):
            raise ValueError('Original callback violated return/ABI/stack guards.')
        return {**{name: bytes(cpu.mem_read(address, len(data))) for name, (address, data) in self.initial.items()},
                'rng_seed': struct.unpack('<I', cpu.mem_read(n.RNG, 4))[0], 'trace': self.trace,
                'motion_scratch': bytes(cpu.mem_read(n.h.symbols['D_8008ABA4'] & n.MASK, 8))}


def bindings():
    table = n.h.target(n.h.symbols['g_ENTITY_TABLE'], 130 * 16)
    found = []
    for index in range(130):
        raw = table[index * 16:index * 16 + 16]
        if struct.unpack_from('<I', raw, 12)[0] == n.h.symbols[CALLBACK]:
            found.append(dict(index=index, proximity=struct.unpack_from('<b', raw, 10)[0],
                              record_sha256=hashlib.sha256(raw).hexdigest()))
    if not found or any(row['proximity'] <= 0 for row in found):
        raise ValueError('Original Astronaut property binding changed.')
    return found, hashlib.sha256(table).hexdigest()


def cases(binding):
    base = base_case(binding)
    ticks = (-0x80000000, -1, 0, 1, 99, 100, 101, 249, 250, 251, 260, 261, 262,
             567, 568, 569, 570, 1199, 1200, 1201, 2399, 2400, 2401, 0x7fffffff)
    timers = (-0x80000000, -21, -20, -11, -10, -9, -1, 0, 1, 9, 10, 11, 20, 0x7fffffff)
    for state, tick, timer in itertools.product((-0x80000000, -1, 0, 1, 100, 0x7fffffff), ticks, timers):
        yield 'state_tick_and_signed_timer_boundaries', dict(base, state=state, tick=tick, timer=timer)
    for dynamic, upper, state, tick in itertools.product((-9, -4, -3, 0, 3, 4, 9), (-9, -4, -3, 0, 3, 4, 9), (0, 1), (0, 100, 250, 261, 569)):
        yield 'native_mood_color_boundaries', dict(base, state=state, tick=tick, timer=0,
                                                  chunk_mood=(dynamic, upper, 0, 0, 0))
    moods = ((-128, 127, 0, 0, 0), (127, -128, 0, 0, 0), (1, -1, 9, -9, 2),
             (-1, 1, -9, 9, -2), (4, 4, 0x7fffffff, -0x80000000, 1),
             (0, 0, -0x80000000, 0x7fffffff, 3))
    for chunk, instance in itertools.product(moods, moods):
        yield 'signed_mood_averages_and_contributions', dict(base, timer=0, tick=261,
                                                          chunk_mood=chunk, instance_mood=instance)
    radius = binding['proximity'] << 11
    positions = ((0, 777, radius - 1), (0, 777, radius), (0, 777, radius + 1),
                 (0x7fffffff, 0, -1), (-0x80000000, 0, 1), (1000, 2000, 3000))
    for position, euler, tick, state in itertools.product(positions,
            ((0, 0, 0), (123, 456, -789), (-32768, 32767, -1)), (1, 100, 250, 261, 568, 569), (0, 1)):
        yield 'proximity_before_motion_and_rotated_word_wrap', dict(base, position=position,
                    player_position=(0, -9000, 0), euler=euler, tick=tick, state=state)


def histories(binding):
    base = base_case(binding)
    yield 'normal_direction_and_tick_reset', [dict(base, state=0, tick=tick, timer=timer)
        for tick, timer in ((1199, 9), (1200, 10), (2399, 11), (2400, 20), (-1, 21), (0, 22))]
    yield 'pink_activation_through_exit_rotation', [dict(base, tick=tick, timer=timer,
        chunk_mood=(4, 4, 0, 0, 0)) for tick, timer in ((0, 0), (99, 9), (100, 10), (249, 19),
                                                     (250, 20), (260, 21), (261, 22),
                                                     (567, 23), (568, 24), (569, 25), (570, 30))]


def controls(bridge, binding):
    base = base_case(binding)
    # Complete original words are checked before changing private emulator memory.
    specifications = (
        ('wrong_normal_command_destination', 'entity_astronaut', 0xb0, 0xae22001c, 0xae220020,
         dict(base, tick=1, timer=10)),
        ('normal_direction_one_tick_late', 'entity_astronaut', 0xc8, 0x286204b0, 0x286204b1,
         dict(base, tick=1200)),
        ('early_motion_one_tick_late', 'entity_astronaut', 0x160, 0x28620064, 0x28620065,
         dict(base, state=1, tick=100)),
        ('late_motion_window_one_tick_long', 'entity_astronaut', 0x1e0, 0x2c420133, 0x2c420134,
         dict(base, state=1, tick=568)),
        ('exit_rotation_one_tick_early', 'entity_astronaut', 0x224, 0x28620239, 0x28620238,
         dict(base, state=1, tick=568)),
        ('missing_animation_stop', 'func_800662B4', 4, 0xac800090, 0xac800094,
         dict(base, state=1, tick=250)),
    )
    results = []
    for name, function, offset, old, changed, case in specifications:
        row = next(row for row in FUNCTIONS if row['function'] == function)
        address = int(row['address'], 16) + offset
        if struct.unpack('<I', n.h.target(address, 4))[0] != old:
            raise ValueError('Reviewed fault word changed: ' + name)
        faulty = Machine(bridge, {address: struct.pack('<I', changed)})
        model, _commands = expected(case)
        actual = faulty.run(case)
        differences = [key for key in model if actual[key] != model[key]]
        if not differences or not faulty.hits[address & n.MASK]:
            raise ValueError('The fault must execute and alter checked output: ' + name)
        results.append(dict(kind=name, function=function, function_offset=offset,
            address=hex(address), original_word=hex(old), changed_word=hex(changed),
            changed_instruction_executions=faulty.hits[address & n.MASK], changed_checked_fields=differences))
    apply = next(row for row in FUNCTIONS if row['function'] == 'ApplyMatrixLV')
    start = int(apply['address'], 16)
    raw = n.h.target(start, apply['bytes'])
    offsets = [offset for offset in range(0, len(raw), 4)
               if struct.unpack_from('<I', raw, offset)[0] == g.COMMANDS[1]]
    if len(offsets) != 1:
        raise ValueError('Expected exactly one original low-part GTE command.')
    address = start + offsets[0]
    faulty = Machine(bridge, {address: struct.pack('<I', g.COMMANDS[0])})
    model, _ = expected(base)
    actual = faulty.run(base)
    differences = [key for key in model if actual[key] != model[key]]
    if not differences or not faulty.hits[address & n.MASK]:
        raise ValueError('The GTE fault must execute and alter the motion result.')
    results.append(dict(kind='wrong_native_GTE_shift', function='ApplyMatrixLV',
        address=hex(address), original_word=hex(g.COMMANDS[1]), changed_word=hex(g.COMMANDS[0]),
        changed_instruction_executions=faulty.hits[address & n.MASK], changed_checked_fields=differences))
    return results


def bounds_control(bridge, binding):
    start = n.h.symbols[CALLBACK]
    address, old, changed = start + 0xb0, 0xae22001c, 0xae220060
    if struct.unpack('<I', n.h.target(address, 4))[0] != old:
        raise ValueError('Reviewed write-boundary word changed.')
    case = dict(base_case(binding), timer=10)
    faulty = Machine(bridge, {address: struct.pack('<I', changed)})
    rejected = False
    try:
        faulty.run(case)
    except ValueError as error:
        if 'escaped declared buffers' not in str(error):
            raise
        rejected = True
    destination = n.CONTEXT + 0x60
    if (not rejected or faulty.rejected_store is None or faulty.rejected_store['address'] != destination
            or bytes(faulty.cpu.mem_read(destination, 4)) != bytes(4)):
        raise ValueError('An escaped store must be rejected before its destination changes.')
    return dict(kind='out_of_profile_command_store', address=hex(address), original_word=hex(old),
        attempted_word=hex(changed), attempted_destination=hex(destination), rejected_before_store=True,
        destination_bytes_preserved=True, distinct_from_completed_behavior_faults=True,
        instruction_execution_observations=faulty.hits[address & n.MASK])


def verify(output, executable, runtime):
    global pairs
    output = Path(output).resolve()
    if not output.is_relative_to((ROOT / '.decomp-lab').resolve()) or output.exists():
        raise ValueError('Choose a fresh private Astronaut evidence directory inside .decomp-lab.')
    dependencies = n.evidence_dependencies('tools/verify_astronaut.py', 'docs/astronaut-function-ranges.json',
        'tools/verify_npc_proximity.py', 'tools/verify_npc_spatial.py', 'tools/verify_scripted_ai.py',
        'tools/verify_locomotive_scripts.py', 'tools/verify_gunman_scripts.py',
        'tools/verify_render_gte.py', 'tools/verify_render_rotation.py', 'tools/nymashock_gte_bridge.cs')
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    n.initialize_backend(n.load_program(FUNCTIONS))
    for name, raw in DATA.items():
        if n.h.target(n.h.symbols[name], len(raw)) != raw:
            raise ValueError('Original data bytes changed: ' + name)
    pairs = rotation.table_pairs(n.h)
    bound, table_hash = bindings()
    backend = scripts.backend_identity()
    executable = Path(executable).resolve(strict=True)
    bridge_sha = hashlib.sha256(executable.read_bytes()).hexdigest()
    output.mkdir(exist_ok=False)
    (output / 'source-snapshot.py').write_bytes(Path(__file__).read_bytes())
    (output / 'preflight.json').write_text(json.dumps({str(path): value for path, value in before.items()}, indent=2) + '\n')
    bridge = g.NativeGteBridge(executable, runtime, output / 'gte.log')
    machine = Machine(bridge)
    seen, groups, histories_report = set(), Counter(), []
    inputs, outputs = hashlib.sha256(), hashlib.sha256()
    started = time.monotonic()
    try:
        for binding in bound:
            for group, case in cases(binding):
                key = input_key(case)
                if key in seen:
                    continue
                seen.add(key)
                model, commands = expected(case)
                actual = machine.run(case)
                if actual != model or machine.adapter.commands != commands:
                    (output / 'failure.json').write_text(json.dumps(dict(group=group, case=case,
                        native=repr(actual), model=repr(model), native_commands=machine.adapter.commands,
                        model_commands=commands), indent=2) + '\n')
                    raise ValueError('Original Astronaut differs from independent buffer/GTE rules.')
                inputs.update(key)
                outputs.update(repr(actual).encode())
                groups[group] += 1
        for name, sequence in histories(bound[0]):
            previous = None
            for index, case in enumerate(sequence):
                model, commands = expected(case, previous)
                actual = machine.run(case, reset=index == 0)
                if actual != model or machine.adapter.commands != commands:
                    (output / 'history-failure.json').write_text(json.dumps(dict(name=name, step=index, case=case,
                        native=repr(actual), model=repr(model)), indent=2) + '\n')
                    raise ValueError('Original Astronaut history differs from independent rules.')
                previous = model
                outputs.update(repr(actual).encode())
            histories_report.append(dict(name=name, script_invocations=len(sequence), input_sequence=sequence))
        positive_GTE_commands = bridge.count
        faults = controls(bridge, bound[0])
        bounds = bounds_control(bridge, bound[0])
    finally:
        bridge.close()
    if (scripts.backend_identity() != backend or n.check_build_current(ROOT) is not True
            or (ROOT / n.configure.ROM).read_bytes() != n.h.ROM or (ROOT / n.configure.EXE).read_bytes() != n.h.ROM
            or any(hashlib.sha256(path.read_bytes()).hexdigest() != value for path, value in before.items())):
        raise ValueError('Original inputs, producers, backend or matching build changed.')
    if {row['function'] for row in FUNCTIONS} != set(machine.entries):
        raise ValueError('Every claimed original function must enter in the positive campaign.')
    report = dict(status='passed_bounded_original_astronaut', callback=CALLBACK, native_cases=sum(groups.values()),
        case_groups=dict(groups), histories=histories_report, native_functions=FUNCTIONS,
        actual_native_entry_counts=dict(machine.entries), qualified_but_unentered=sorted(
            {row['function'] for row in FUNCTIONS} - machine.entries.keys()),
        callback_bindings=bound, property_table_sha256=table_hash,
        original_data=[dict(symbol=name, address=hex(n.h.symbols[name]), bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest()) for name, raw in DATA.items()],
        native_gte_commands=positive_GTE_commands, negative_control_GTE_commands=bridge.count - positive_GTE_commands,
        negative_controls_detected=faults, write_bounds_control=bounds,
        store_guard='Original integer/SWC2 store spans; branch delay slots checked before the branch. No memory-write hook.',
        backend_identity=backend, bridge_sha256=bridge_sha,
        source_dependencies=[dict(path=path.resolve().relative_to(ROOT).as_posix(), sha256=value) for path, value in before.items()],
        input_digest_sha256=inputs.hexdigest(), output_digest_sha256=outputs.hexdigest(),
        dependency_output_stubs=0, new_C_bytes=0, whole_NPC_encounters_accepted=0,
        whole_feature_groups_accepted=0, model_API_calls=0, original_game_modified=False,
        user_game_controlled=False, elapsed_seconds=round(time.monotonic() - started, 3),
        scope='Constructed meshless poses, original mood/proximity/transform/RNG-preservation checks and injected script histories. All executed code uses the original image and native GTE backend. No natural encounters, complete animation playback, rendering, audio, full-engine scheduling or original-hardware timing acceptance.')
    with (output / 'report.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bridge', type=Path, required=True)
    parser.add_argument('--runtime', required=True)
    args = parser.parse_args(argv)
    result = verify(args.output, args.bridge, args.runtime)
    print(json.dumps({key: result[key] for key in ('status', 'native_cases', 'native_gte_commands', 'new_C_bytes')}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
