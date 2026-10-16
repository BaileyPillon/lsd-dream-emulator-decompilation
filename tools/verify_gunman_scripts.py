"""Compare original Gunman scripts and effect arithmetic on bounded fixtures.

Allocation, attachment, geometry, notification and sound use explicit contracts.
Natural encounter construction, rendering, audio and timing remain unaccepted.
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

CALLBACKS = ('entity_gunman', 'entity_gunman_victim')
FUNCTIONS = json.loads((ROOT / 'docs/gunman-function-ranges.json').read_bytes())
EFFECT, PARENT = 0x105000, 0x106000
BUFFER_SIZES = {'entity': 0x108, 'dream': 0xA00, 'context': 0x60, 'effect': 0xA0, 'parent': 0x80}
ADDRESSES = {'entity': n.ENTITY, 'dream': n.DREAM, 'context': n.CONTEXT, 'effect': EFFECT, 'parent': PARENT}


def base_case(**updates):
    case = dict(state=0, tick=0, frame=0, duration=15, action=0, seed=0,
                effect_mode='existing', effect_state=0, effect_mask=255,
                effect_flags=0x89ABCDEF, move_mode=1, property_index=85)
    case.update(updates)
    return case


def validate_case(case):
    for name in ('state', 'tick', 'frame', 'duration', 'action', 'effect_mask'):
        if type(case.get(name)) is not int or not -0x80000000 <= case[name] <= 0x7FFFFFFF:
            raise ValueError('Script input must be a signed native word: ' + name)
    for name in ('seed', 'effect_flags'):
        if type(case.get(name)) is not int or not 0 <= case[name] <= 0xFFFFFFFF:
            raise ValueError('Script input must be an unsigned native word: ' + name)
    if (case.get('effect_mode') not in ('existing', 'allocate', 'fail')
            or type(case.get('effect_state')) is not int or case['effect_state'] not in (0, 1, 2)
            or case['effect_mode'] != 'existing' and case['effect_state'] != 0):
        raise ValueError('Use an existing valid effect or a fresh state-zero allocation contract.')
    if type(case.get('move_mode')) is not int or case['move_mode'] not in (0, 1, 2, 3):
        raise ValueError('Use a reviewed original move mode.')
    if type(case.get('property_index')) is not int or not 0 <= case['property_index'] < 130:
        raise ValueError('Use an original property-table index.')


def read_word(data, offset):
    return struct.unpack_from('<i', data, offset)[0]


def fixtures(case):
    validate_case(case)
    buffers = {name: bytearray([fill]) * BUFFER_SIZES[name]
               for name, fill in (('entity', 0xD7), ('dream', 0xA6), ('context', 0xC4), ('effect', 0xE2), ('parent', 0xB3))}
    entity, dream, effect = buffers['entity'], buffers['dream'], buffers['effect']
    for offset, value in ((0, n.h.symbols['g_ENTITY_VTABLE']), (0x44, case['state']),
            (0x50, PARENT), (0x58, n.SOUND), (0x6C, 0), (0x70, 0),
            (0x80, case['duration']), (0x84, case['frame']), (0x8C, 1), (0x90, 1),
            (0x94, n.DREAM), (0x98, case['property_index']), (0xF8, 1), (0xFC, case['tick']),
            (0x100, EFFECT if case['effect_mode'] == 'existing' else 0)):
        n.word(entity, offset, value)
    for offset, value in ((0, n.h.symbols['g_DREAM_SYS_VTABLE']), (0x74, case['action']),
            (0x80, 0xABCD1000), (0x84, 3), (0x98, 0xABCD2000), (0x9C, case['move_mode']),
            (0xC4, 1), (0xC8, 1)):
        n.word(dream, offset, value)
    for offset, value in ((0, n.h.symbols['g_EFFECT_VTABLE']), (0xC, 0),
            (0x58, case['effect_flags']), (0x64, 0xF355AA11), (0x68, case['effect_mask']),
            (0x6C, case['effect_state']), (0x70, 3), (0x74, 10), (0x78, 0),
            (0x7C, 9), (0x80, 50), (0x98, 0), (0x9C, 1)):
        n.word(effect, offset, value)
    return buffers


def next_inputs(buffers, case):
    for offset, name in ((0xFC, 'tick'), (0x84, 'frame'), (0x80, 'duration')):
        n.word(buffers['entity'], offset, case[name])
    n.word(buffers['dream'], 0x74, case['action'])


def expected(callback, case, previous=None):
    if callback not in CALLBACKS:
        raise ValueError('Unsupported original Gunman callback.')
    validate_case(case)
    buffers = fixtures(case) if previous is None else {name: bytearray(previous[name]) for name in BUFFER_SIZES}
    if previous is not None:
        next_inputs(buffers, case)
    entity, dream, context, effect = [buffers[name] for name in ('entity', 'dream', 'context', 'effect')]
    trace = []
    seed = case['seed'] if previous is None else previous['rng_seed']

    def call(name, *arguments):
        trace.append([name, *map(n.u32, arguments)])

    def command(index, value):
        n.word(context, index * 4, value)

    def aim():
        call('aim_pose', n.CONTEXT)
        for index, value in ((4, 0), (7, 7), (8, -2), (12, 7), (13, -2), (17, 7), (18, -2)):
            command(index, value)

    def fall():
        call('fall_pose', n.CONTEXT)
        for index, value in ((7, 18), (4, 0), (12, 3), (17, 3)):
            command(index, value)

    def stop():
        call('stop_behaviour', n.ENTITY)
        call('sound_stop', n.SOUND, n.ENTITY + 0x9C)
        call('animation_stop', n.ENTITY)
        n.word(entity, 0x90, 0)
        call('model_unload', n.ENTITY)
        n.word(entity, 0x8C, 0)
        n.word(entity, 0xF8, 0)

    def change_state(value, reset_tick=False):
        n.word(entity, 0x44, value)
        if reset_tick:
            n.word(entity, 0xFC, -1)

    def color_effect(step, attached):
        call('create_effect', n.ENTITY, 0, 0, step, 0)
        if read_word(entity, 0x100) == 0:
            call('allocate_effect', n.h.symbols['D_8008AC14'], 0, 0)
            if case['effect_mode'] == 'fail':
                return
            n.word(entity, 0x100, EFFECT)
        call('effect_detach_empty', EFFECT)
        call('effect_bind', EFFECT, n.ENTITY, n.h.symbols['D_8008AC0C'])
        call('color_step', EFFECT, step)
        n.word(effect, 0x74, step)
        variant = 0 if attached else 7
        call('start_effect_attached' if attached else 'start_effect', EFFECT, PARENT, variant, 0)
        if read_word(effect, 0x6C) != 0:
            return
        call('activate_effect', EFFECT, PARENT, variant, 0)
        n.word(effect, 0x70, variant)
        n.word(effect, 0x78, variant if variant else 15)
        life = 256 // step
        n.word(effect, 0x7C, 0)
        n.word(effect, 0x80, life)
        mask = read_word(effect, 0x68)
        quotient = abs(mask) // life
        n.word(effect, 0x84, -quotient if mask < 0 else quotient)
        call('effect_attach', EFFECT, PARENT)
        call('effect_flag24', EFFECT, 1)
        flags = struct.unpack_from('<I', effect, 0x58)[0] | 0x40000000
        activation_state = 2 if not variant else 1
        call('effect_flag25', EFFECT, activation_state)
        flags = (flags & ~0x30000000) | activation_state << 28
        call('effect_flag23', EFFECT, 1)
        n.word(effect, 0x58, flags & ~0x80000000)
        palette = n.h.symbols['D_8006EAA8' if attached else 'D_8006EA90'] + variant * 3
        call('write_color', EFFECT, 1, palette)
        effect[0x64:0x67] = n.h.target(palette, 3)
        n.word(effect, 0x6C, 2 if attached else 1)
        if not attached:
            n.word(effect, 0x74, -step)

    state = read_word(entity, 0x44)
    tick, frame, duration = (read_word(entity, offset) for offset in (0xFC, 0x84, 0x80))
    if callback == 'entity_gunman_victim':
        if tick < 10:
            call('animation_stop', n.ENTITY)
            n.word(entity, 0x90, 0)
        elif tick == 10:
            call('animation_play', n.ENTITY)
            n.word(entity, 0x90, 1)
        if frame == 10:
            fall()
        if tick == scripts.signed_word(duration + 10):
            stop()
            change_state(1)
    elif state == 0:
        if frame == 5:
            aim()
        if tick == duration:
            call('animation_stop', n.ENTITY)
            n.word(entity, 0x90, 0)
            change_state(10, True)
    elif state == 10:
        if tick < 10:
            call('rotation', n.ENTITY, 0, n.h.symbols['g_RotateYawNine'])
            call('read_action', n.DREAM)
            if read_word(dream, 0x74) != 0:
                aim()
                change_state(12, True)
        else:
            call('clear_callbacks', n.DREAM, 1)
            call('set_move_callback', n.DREAM, 0)
            if read_word(dream, 0x9C) == 2:
                call('set_view_mode', n.DREAM, 0)
                n.word(dream, 0xC4, 0)
                n.word(dream, 0xC8, 0)
            n.word(dream, 0x9C, 0)
            n.word(dream, 0x98, 0)
            call('set_view_callback', n.DREAM, 0)
            n.word(dream, 0x84, 0)
            n.word(dream, 0x80, 0)
            change_state(11, True)
    elif state == 11:
        call('orientation', n.ENTITY, n.DREAM, 1, 0, 0)
        if tick < 30:
            call('forward', n.ENTITY, -10, 0)
        else:
            aim()
            color_effect(30, False)
            change_state(13, True)
    elif state == 13:
        if tick < 90:
            if tick == 30:
                color_effect(10, True)
            call('rotation', n.DREAM, 0, n.h.symbols['g_RotateRollOne'])
        else:
            fall()
            call('rotation', n.DREAM, 1, n.h.symbols['g_RotateYawHalfTurn'])
            call('rand', seed)
            seed = n.u32(seed * 0x41C64E6D + 0x3039)
            result = seed >> 16 & 0x7FFF
            call('notification', n.ENTITY, 10 if result % 5 else 12)
            change_state(14)
    elif state == 12:
        if tick < 10:
            call('rotation', n.ENTITY, 0, n.h.symbols['g_RotateRollNegNine'])
        else:
            fall()
            stop()
            change_state(1)
    return {**{name: bytes(data) for name, data in buffers.items()}, 'rng_seed': seed, 'trace': trace}


def first_result_seed(result):
    if type(result) is not int or not 0 <= result < 32768:
        raise ValueError('Use one original fifteen-bit RNG result.')
    return ((result << 16) - 0x3039) * pow(0x41C64E6D, -1, 1 << 32) & 0xFFFFFFFF


def cases(callback, property_index):
    base = base_case(property_index=property_index)
    ticks = (-0x80000000, -1, 0, 4, 5, 9, 10, 11, 29, 30, 31, 89, 90, 91, 0x7FFFFFFF)
    if callback == 'entity_gunman':
        for state, tick, action, frame in itertools.product((-1, 0, 1, 10, 11, 12, 13, 14), ticks, (0, 1, -1, 0x10000), (4, 5, 10)):
            yield 'state_input_and_phase_boundaries', dict(base, state=state, tick=tick, action=action, frame=frame)
        for duration in (-0x80000000, -1, 0, 5, 10, 30, 0x7FFFFFFF):
            for edge, frame in itertools.product((-1, 0, 1), (4, 5, 6)):
                tick = scripts.signed_word(duration + edge)
                yield 'initial_animation_and_completion', dict(base, duration=duration, tick=tick, frame=frame)
        for move_mode, tick, action in itertools.product(range(4), (9, 10, 11), (0, 1, 0x10000)):
            yield 'player_callback_clear_modes', dict(base, state=10, tick=tick, action=action, move_mode=move_mode)
        effect_modes = [('existing', value) for value in (0, 1, 2)] + [('allocate', 0), ('fail', 0)]
        for state, tick, (mode, effect_state), mask, flags in itertools.product((11, 13), (29, 30, 31), effect_modes,
                (-0x80000000, -1, 0, 1, 255, 0x7FFFFFFF), (0, 0xFFFFFFFF, 0x89ABCDEF)):
            yield 'native_effect_factory_activation_and_words', dict(base, state=state, tick=tick,
                effect_mode=mode, effect_state=effect_state, effect_mask=mask, effect_flags=flags)
        for result in range(32768):
            yield 'all_first_rng_results', dict(base, state=13, tick=90, seed=first_result_seed(result))
    elif callback == 'entity_gunman_victim':
        for duration, tick, frame, state in itertools.product((-0x80000000, -10, -1, 0, 5, 10, 30, 0x7FFFFFFF),
                ticks, (9, 10, 11), (0, 1, 10, 14)):
            yield 'victim_animation_and_phase_boundaries', dict(base, duration=duration, tick=tick, frame=frame, state=state)
        for duration, edge, frame in itertools.product((-0x80000000, -11, -10, -1, 0, 1, 10, 0x7FFFFFFF), (-1, 0, 1), (9, 10, 11)):
            yield 'victim_wrapped_duration_completion', dict(base, duration=duration,
                tick=scripts.signed_word(duration + 10 + edge), frame=frame)
    else:
        raise ValueError('Unsupported callback fixture domain.')


def input_key(case):
    initialized = [(name, ADDRESSES[name], bytes(data).hex()) for name, data in sorted(fixtures(case).items())]
    return json.dumps([initialized, case['seed'], case['effect_mode'] == 'fail'], separators=(',', ':')).encode()


def slot(table, offset):
    return struct.unpack('<I', n.h.target(n.h.symbols[table] + offset, 4))[0] & n.MASK


def store_span(word, base):
    """Return the physical byte span of a reviewed little-endian MIPS store."""
    opcode = word >> 26
    if opcode in (44, 45, 56, 57, 58, 59, 60, 61, 62, 63):
        raise ValueError('Unreviewed store class in this integer-only R3000 profile.')
    if opcode not in (40, 41, 42, 43, 46):
        return None
    offset = ((word & 0xFFFF) ^ 0x8000) - 0x8000
    address = n.u32(base + offset) & n.MASK
    if opcode == 42:  # SWL writes from the aligned word start through this byte.
        return address & ~3, (address & 3) + 1
    if opcode == 46:  # SWR writes from this byte through the aligned word end.
        return address, 4 - (address & 3)
    return address, {40: 1, 41: 2, 43: 4}[opcode]


class Machine(n.Machine):
    def __init__(self, callback, patches=None):
        if callback not in CALLBACKS:
            raise ValueError('Unsupported native callback.')
        self.callback = callback
        self.entry_counts, self.hits = Counter(), Counter()
        self.changed_addresses = set()
        self.rejected_store = None
        self.contracts = {
            n.h.symbols['func_8001EACC'] & n.MASK: ('orientation', 5),
            n.h.symbols['sound_entity_stop'] & n.MASK: ('sound_stop', 2),
            n.h.symbols['effect_create'] & n.MASK: ('allocate_effect', 3),
            slot('g_ENTITY_VTABLE', 0x44): ('rotation', 3),
            slot('g_ENTITY_VTABLE', 0xC4): ('forward', 3),
            slot('g_ENTITY_VTABLE', 0x30): ('notification', 2),
            slot('g_EFFECT_VTABLE', 0x4C): ('effect_bind', 3),
            slot('g_EFFECT_VTABLE', 0x10): ('effect_attach', 2),
        }
        if slot('g_DREAM_SYS_VTABLE', 0x44) != slot('g_ENTITY_VTABLE', 0x44):
            raise ValueError('The reviewed shared rotation binding changed.')
        self.native_events = {
            'entity_set_aim_pose': ('aim_pose', 1), 'entity_set_fall_pose': ('fall_pose', 1),
            'func_800662A8': ('animation_play', 1), 'func_800662B4': ('animation_stop', 1),
            'func_80066148': ('model_unload', 1), 'entity_stop_behaviour': ('stop_behaviour', 1),
            'dream_sys_get_action_pressed': ('read_action', 1), 'dream_sys_clear_callbacks': ('clear_callbacks', 2),
            'dream_sys_set_move_callback': ('set_move_callback', 2), 'dream_sys_set_view_callback': ('set_view_callback', 2),
            'dream_sys_set_view_mode': ('set_view_mode', 2), 'entity_create_effect': ('create_effect', 5),
            'func_8001D1A4': ('effect_detach_empty', 1), 'effect_set_color_step': ('color_step', 2),
            'effect_start': ('start_effect', 4), 'effect_start_attached': ('start_effect_attached', 4),
            'effect_activate': ('activate_effect', 4), 'func_80040714': ('effect_flag24', 2),
            'func_80040740': ('effect_flag25', 2), 'func_800406E4': ('effect_flag23', 2),
            'func_8004076C': ('write_color', 3),
        }
        self.ranges = [(int(row['address'], 16) & n.MASK, (int(row['address'], 16) & n.MASK) + row['bytes']) for row in FUNCTIONS]
        if {address for address, _end in self.ranges}.intersection(self.contracts):
            raise ValueError('A contract would bypass a claimed native function.')
        super().__init__(start=n.h.symbols[callback] & n.MASK, native_functions=FUNCTIONS)
        for address, data in (patches or {}).items():
            self.cpu.mem_write(address & n.MASK, data)
            self.changed_addresses.add(address & n.MASK)

    def arguments(self, count):
        values = [self.cpu.reg_read(getattr(n.reg, 'UC_MIPS_REG_A' + str(i))) for i in range(min(count, 4))]
        if count == 5:
            values.append(struct.unpack('<I', self.cpu.mem_read(self.cpu.reg_read(n.reg.UC_MIPS_REG_SP) + 16, 4))[0])
        return values

    def hook(self, cpu, address, size, unused):
        pc = address & n.MASK
        if pc in self.changed_addresses:
            self.hits[pc] += 1
        if pc in self.native_entries:
            name = self.native_entries[pc]
            self.entry_counts[name] += 1
            if name == 'rand':
                self.trace.append(['rand', struct.unpack('<I', cpu.mem_read(n.RNG, 4))[0]])
            elif name in self.native_events:
                event, count = self.native_events[name]
                self.trace.append([event, *self.arguments(count)])
        contract = self.contracts.get(pc)
        if contract is not None:
            name, count = contract
            self.trace.append([name, *self.arguments(count)])
            result = EFFECT if name == 'allocate_effect' and self.case['effect_mode'] != 'fail' else 0
            target = cpu.reg_read(n.reg.UC_MIPS_REG_RA)
            for index, register in enumerate(n.VOLATILE):
                cpu.reg_write(register, n.u32(0xBC000000 + 0x10203 * index))
            cpu.reg_write(n.reg.UC_MIPS_REG_HI, 0xD13579BF)
            cpu.reg_write(n.reg.UC_MIPS_REG_LO, 0xE2468ACE)
            cpu.reg_write(n.reg.UC_MIPS_REG_V0, result)
            cpu.reg_write(n.reg.UC_MIPS_REG_PC, target)
        elif not any(start <= pc < end for start, end in self.ranges):
            raise ValueError('Execution escaped the reviewed native/contract ranges: ' + hex(pc))
        else:
            word = struct.unpack('<I', cpu.mem_read(pc, 4))[0]
            opcode = word >> 26
            is_branch = opcode in (1, 2, 3, 4, 5, 6, 7) or opcode == 0 and word & 63 in (8, 9)
            if is_branch:
                # Stop before the branch: stopping from a delay-slot hook can
                # still allow that slot's store to complete in this backend.
                delay = struct.unpack('<I', cpu.mem_read(pc + 4, 4))[0]
                link = 31 if opcode == 3 or opcode == 1 and word >> 16 & 31 in (16, 17) else (
                    word >> 11 & 31 if opcode == 0 and word & 63 == 9 else None)
                self.check_store(cpu, delay, pc + 4, pc, link)
            self.check_store(cpu, word, pc, pc)

    def check_store(self, cpu, word, instruction, observed_at, link=None):
        base_number = word >> 21 & 31
        base_register = getattr(n.reg, 'UC_MIPS_REG_' + str(base_number))
        span = store_span(word, cpu.reg_read(base_register))
        if span is None:
            return
        if link is not None and base_number == link:
            raise ValueError('A delay store using the changed link register requires separate review.')
        self.write_guard(*span, instruction, observed_at)

    def write_guard(self, address, size, instruction, observed_at):
        regions = [(ADDRESSES[name], ADDRESSES[name] + length) for name, length in BUFFER_SIZES.items()]
        regions.extend(((n.RNG, n.RNG + 4), (n.STACK - 0x400, n.STACK + 0x100)))
        if not any(start <= address and address + size <= end for start, end in regions):
            self.rejected_store = dict(instruction=instruction, observed_at=observed_at, address=address, bytes=size)
            self.cpu.emu_stop()
            raise ValueError('Native write escaped the declared buffers: ' + hex(address))

    def run(self, case, reset=True):
        validate_case(case)
        self.case, self.trace = case, []
        self.hits.clear()
        self.rejected_store = None
        cpu = self.cpu
        if reset:
            for name, data in fixtures(case).items():
                cpu.mem_write(ADDRESSES[name], bytes(data))
            cpu.mem_write(n.RNG, struct.pack('<I', case['seed']))
        else:
            for offset, name in ((0xFC, 'tick'), (0x84, 'frame'), (0x80, 'duration')):
                cpu.mem_write(n.ENTITY + offset, struct.pack('<I', n.u32(case[name])))
            cpu.mem_write(n.DREAM + 0x74, struct.pack('<I', n.u32(case['action'])))
        cpu.mem_write(n.STACK - 0x400, bytes([0xCC]) * 0x500)
        saved = [n.u32(0xAB000000 + 0x10203 * i) for i in range(len(n.SAVED))]
        for register, value in zip(n.SAVED, saved):
            cpu.reg_write(register, value)
        for register, value in ((n.reg.UC_MIPS_REG_SP, n.STACK), (n.reg.UC_MIPS_REG_GP, 0x8008A808),
                (n.reg.UC_MIPS_REG_RA, n.END), (n.reg.UC_MIPS_REG_A0, n.ENTITY), (n.reg.UC_MIPS_REG_A1, n.CONTEXT)):
            cpu.reg_write(register, value)
        try:
            cpu.emu_start(self.start, n.END, count=30000)
        except n.unicorn.UcError as error:
            raise ValueError('Native execution failed at ' + hex(cpu.reg_read(n.reg.UC_MIPS_REG_PC)) + ': ' + str(error)) from error
        if (cpu.reg_read(n.reg.UC_MIPS_REG_PC) != n.END or cpu.reg_read(n.reg.UC_MIPS_REG_SP) != n.STACK
                or cpu.reg_read(n.reg.UC_MIPS_REG_GP) != 0x8008A808 or cpu.reg_read(n.reg.UC_MIPS_REG_RA) != n.END
                or [cpu.reg_read(register) for register in n.SAVED] != saved
                or bytes(cpu.mem_read(n.STACK - 0x400, 64)) != bytes([0xCC]) * 64
                or bytes(cpu.mem_read(n.STACK + 0x40, 64)) != bytes([0xCC]) * 64):
            raise ValueError('Original callback violated return, saved-register, GP or stack guards.')
        return {**{name: bytes(cpu.mem_read(ADDRESSES[name], length)) for name, length in BUFFER_SIZES.items()},
                'rng_seed': struct.unpack('<I', cpu.mem_read(n.RNG, 4))[0], 'trace': self.trace}


def new_output(value):
    destination = Path(value).resolve()
    lab = (ROOT / '.decomp-lab').resolve()
    if not destination.is_relative_to(lab) or destination == lab or destination.exists():
        raise ValueError('Choose a fresh private directory inside .decomp-lab.')
    return destination


def bindings():
    table = n.h.target(n.h.symbols['g_ENTITY_TABLE'], 130 * 16)
    result = {}
    for callback in CALLBACKS:
        found = [dict(index=index, record_sha256=hashlib.sha256(table[index * 16:index * 16 + 16]).hexdigest())
            for index in range(130) if struct.unpack_from('<I', table, index * 16 + 12)[0] == n.h.symbols[callback]]
        if not found:
            raise ValueError('The callback lacks an original property-table binding.')
        result[callback] = found
    return result, hashlib.sha256(table).hexdigest()


def histories(callback, property_index):
    """Scheduled script invocations; tick/frame/action are explicit inputs."""
    if callback == 'entity_gunman':
        for seed in (0, 42, 0xFFFFFFFF):
            base = base_case(property_index=property_index, seed=seed, duration=5)
            yield 'action_taken-' + str(seed), [dict(base, tick=tick, frame=frame, action=action)
                for tick, frame, action in ((5, 5, 0), (0, 6, 1), (9, 9, 0), (10, 10, 0))]
            for mode in ('existing', 'allocate', 'fail'):
                base = base_case(property_index=property_index, seed=seed, duration=5, move_mode=2, effect_mode=mode)
                yield 'timeout-' + mode + '-' + str(seed), [dict(base, tick=tick, frame=frame, action=0)
                    for tick, frame in ((5, 5), (9, 6), (10, 7), (0, 8), (29, 9), (30, 10),
                                       (0, 11), (30, 12), (89, 13), (90, 14), (91, 15))]
    else:
        for duration in (15, 30, 60):
            base = base_case(property_index=property_index, duration=duration)
            yield 'victim-duration-' + str(duration), [dict(base, tick=tick, frame=frame)
                for tick, frame in ((0, 0), (9, 9), (10, 10), (duration + 9, 11), (duration + 10, 12))]


def controls():
    specifications = [
        ('wrong_initial_duration_field', 'entity_gunman', 'entity_gunman', 64, 0x8E020080, 0x8E020084,
         dict(state=0, tick=15, frame=4)),
        ('wrong_action_window', 'entity_gunman', 'entity_gunman', 132, 0x2842000A, 0x2842000B,
         dict(state=10, tick=10, action=1, move_mode=2)),
        ('wrong_fall_boundary', 'entity_gunman', 'entity_gunman', 460, 0x2862005A, 0x2862005B,
         dict(state=13, tick=90, seed=1)),
        ('wrong_aim_command_destination', 'entity_set_aim_pose', 'entity_gunman', 12, 0xAC83001C, 0xAC830020,
         dict(state=0, frame=5, tick=4)),
        ('wrong_victim_completion', 'entity_gunman_victim', 'entity_gunman_victim', 128, 0x2442000A, 0x2442000B,
         dict(tick=25, frame=9)),
        ('wrong_victim_frame_field', 'entity_gunman_victim', 'entity_gunman_victim', 96, 0x8E030084, 0x8E030080,
         dict(tick=11, frame=10)),
        ('wrong_effect_step_destination', 'effect_set_color_step', 'entity_gunman', 4, 0xAC850074, 0xAC850078,
         dict(state=11, tick=30)),
        ('wrong_effect_flag_destination', 'func_8001EDAC', 'entity_gunman', 72, 0xAD230000, 0xAD230004,
         dict(state=11, tick=30)),
        ('wrong_rng_multiplier', 'rand', 'entity_gunman', 8, 0x34634E6D, 0x34634E6E,
         dict(state=13, tick=90, seed=1)),
        ('wrong_view_reset_destination', 'dream_sys_set_view_mode', 'entity_gunman', 12, 0xAC4000C4, 0xAC4000C0,
         dict(state=10, tick=10, move_mode=2)),
    ]
    records = {row['function']: row for row in FUNCTIONS}
    action = records['dream_sys_get_action_pressed']
    code = n.h.target(int(action['address'], 16), action['bytes'])
    offsets = [offset for offset in range(0, len(code), 4) if struct.unpack_from('<I', code, offset)[0] == 0x8C820074]
    if len(offsets) != 1:
        raise ValueError('Expected the reviewed full-word action load.')
    specifications.append(('truncated_action_word', 'dream_sys_get_action_pressed', 'entity_gunman', offsets[0],
                           0x8C820074, 0x94820074, dict(state=10, tick=9, action=0x10000)))
    bound, _table_hash = bindings()
    results = []
    for name, function, callback, offset, old, changed, updates in specifications:
        address = int(records[function]['address'], 16) + offset
        if struct.unpack('<I', n.h.target(address, 4))[0] != old:
            raise ValueError('Fault no longer identifies its reviewed original instruction: ' + name)
        case = base_case(property_index=bound[callback][0]['index'], **updates)
        machine = Machine(callback, {address: struct.pack('<I', changed)})
        actual, model = machine.run(case), expected(callback, case)
        differences = [key for key in model if actual[key] != model[key]]
        hits = machine.hits[address & n.MASK]
        if not differences or not hits:
            raise ValueError('A fault must execute and change a checked result: ' + name)
        results.append(dict(kind=name, function=function, callback=callback, function_offset=offset,
            address=hex(address), expected_word=hex(old), changed_word=hex(changed),
            changed_instruction_executions=hits, changed_checked_fields=differences,
            scope='Separate private Unicorn memory only.'))
    return results


def write_bounds_control():
    record = next(row for row in FUNCTIONS if row['function'] == 'effect_set_color_step')
    address = int(record['address'], 16) + 4
    machine = Machine('entity_gunman', {address: struct.pack('<I', 0xAC850700)})
    case = base_case(state=11, tick=30)
    try:
        machine.run(case)
    except ValueError as error:
        if ('Native write escaped the declared buffers' not in str(error) or machine.rejected_store is None
                or machine.rejected_store['instruction'] != address & n.MASK):
            raise
    else:
        raise ValueError('The instruction-level bounds guard failed to reject an escaped write.')
    if bytes(machine.cpu.mem_read(EFFECT + 0x700, 4)) != bytes(4):
        raise ValueError('The guard must reject the store before it writes.')
    return dict(kind='out_of_profile_store_rejected_before_execution', address=hex(address),
        expected_word='0xAC850074', attempted_word='0xAC850700', attempted_destination=hex(EFFECT + 0x700),
        decoded_from_instruction=hex(machine.rejected_store['observed_at']),
        changed_instruction_execution_observations=machine.hits[address & n.MASK], store_completed=False,
        distinct_from_completed_behavior_faults=True)


def verify(destination):
    destination = new_output(destination)
    dependencies = n.evidence_dependencies('tools/verify_gunman_scripts.py', 'tools/verify_scripted_ai.py',
        'docs/gunman-function-ranges.json', 'src/graphics/effect.c', 'src/graphics/effect.h',
        'src/graphics/effect_base.c', 'src/graphics/effect_base.h', 'src/base/object_math.c')
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    n.initialize_backend(n.load_program(FUNCTIONS))
    backend = scripts.backend_identity()
    bound, table_hash = bindings()
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'source-snapshot.py').write_bytes(Path(__file__).read_bytes())
    (destination / 'preflight.json').write_text(json.dumps({str(path): digest for path, digest in before.items()}, indent=2) + '\n')
    observations, entries, contracts_seen = {}, Counter(), set()
    history_observations = []
    input_digest, output_digest = hashlib.sha256(), hashlib.sha256()
    started = time.monotonic()
    for callback in CALLBACKS:
        machine = Machine(callback)
        groups, states, seen = Counter(), Counter(), set()
        for binding in bound[callback]:
            for group, case in cases(callback, binding['index']):
                key = input_key(case)
                if key in seen:
                    continue
                seen.add(key)
                actual, model = machine.run(case), expected(callback, case)
                if actual != model:
                    (destination / 'failure.json').write_text(json.dumps(dict(callback=callback, case=case,
                        native=repr(actual), model=repr(model)), indent=2) + '\n')
                    raise ValueError('Original Gunman code differs from the declared model.')
                groups[group] += 1
                states[read_word(actual['entity'], 0x44)] += 1
                input_digest.update(callback.encode() + b'\0' + key)
                output_digest.update(repr(actual).encode())
        observations[callback] = dict(native_cases=sum(groups.values()), groups=dict(groups),
            resulting_states=dict(states), actual_native_entry_counts=dict(machine.entry_counts))
        entries.update(machine.entry_counts)
        contracts_seen.update(name for name, count in machine.contracts.values())
        print(callback, sum(groups.values()), 'native cases passed', flush=True)
        for history_name, sequence in histories(callback, bound[callback][0]['index']):
            history_machine, previous = Machine(callback), None
            for index, case in enumerate(sequence):
                model = expected(callback, case, previous)
                actual = history_machine.run(case, reset=index == 0)
                if actual != model:
                    (destination / 'history-failure.json').write_text(json.dumps(dict(callback=callback,
                        history=history_name, step=index, case=case, native=repr(actual), model=repr(model)), indent=2) + '\n')
                    raise ValueError('A consecutive Gunman script history differs from its model.')
                previous = model
                output_digest.update(repr(actual).encode())
            history_observations.append(dict(callback=callback, name=history_name, script_invocations=len(sequence),
                submitted_inputs=sequence, final_state=read_word(previous['entity'], 0x44),
                actual_native_entry_counts=dict(history_machine.entry_counts)))
            entries.update(history_machine.entry_counts)
    faults = controls()
    bounds_control = write_bounds_control()
    if (scripts.backend_identity() != backend or (ROOT / n.configure.ROM).read_bytes() != n.h.ROM
            or (ROOT / n.configure.EXE).read_bytes() != n.h.ROM or n.check_build_current(ROOT) is not True
            or any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path, digest in before.items())):
        raise ValueError('Native source, backend or canonical build changed during verification.')
    report = dict(status='passed_bounded_original_gunman_scripts', profiles=observations,
        native_functions=FUNCTIONS, actual_native_entry_counts=dict(entries),
        dependency_contracts=sorted(contracts_seen), callback_bindings=bound, property_table_sha256=table_hash,
        backend_identity=backend, negative_controls_detected=faults,
        histories=history_observations, history_invocations=sum(row['script_invocations'] for row in history_observations),
        write_bounds_control=bounds_control, store_guard='Instruction-level integer-store spans; no memory-write hook.',
        palette_identities=[dict(symbol=name, bytes=24, sha256=hashlib.sha256(n.h.target(n.h.symbols[name], 24)).hexdigest())
            for name in ('D_8006EA90', 'D_8006EAA8')],
        canonical_executable_sha1=hashlib.sha1(n.h.ROM).hexdigest(), canonical_original_and_build_equal=True,
        input_digest_sha256=input_digest.hexdigest(), output_digest_sha256=output_digest.hexdigest(),
        producer_dependencies=[dict(path=path.resolve().relative_to(ROOT).as_posix(), sha256=digest) for path, digest in before.items()],
        original_behavior_modified=False, source_functions_promoted=0, whole_feature_groups_accepted=0,
        whole_NPC_encounters_accepted=0, model_api_calls=0,
        scope='Constructed Gunman/victim script states and real pose, animation, callback-clear, RNG, effect-factory and effect-color arithmetic. Allocation, empty attachment, orientation, rotation, movement, notification and sound use explicit contracts. Histories retain buffers/RNG and explicitly inject tick/frame/action inputs; they do not run a complete engine frame or tick the effects. Excludes natural construction, populated attachment graphs, linked-effect mode, effect ticking/rendering, audio and PS1 CPU timing.',
        elapsed_seconds=round(time.monotonic() - started, 3))
    with (destination / 'report.json').open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        report = verify(args.output)
        print(json.dumps(dict(status=report['status'], profiles=report['profiles'])))
        return 0
    except (OSError, ValueError, NotImplementedError) as error:
        print('error: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
