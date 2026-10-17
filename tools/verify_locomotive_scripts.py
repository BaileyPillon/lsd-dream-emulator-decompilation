"""Bounded original locomotive script, RNG, mood and callback checks.

Geometry, sound and notification are explicit contracts. This developer tool
executes no model API, changes no original game behavior and accepts no whole
NPC encounter. Script histories inject tick and action inputs between calls.
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
from tools.verify_gunman_scripts import store_span

CALLBACKS = ('entity_locomotive_factory', 'entity_locomotive_kyoto', 'entity_locomotive_natural')
RANGE_FILE = ROOT / 'docs/locomotive-function-ranges.json'
FUNCTIONS = json.loads(RANGE_FILE.read_bytes())
TRANSFORM = 0x105000
SIZES = dict(entity=0x108, dream=0xA00, context=0x60, transform=0x80,
             scratch=22, denominator=2, yaw_one=12, yaw_quarter=12, color_table=12)
DATA = {
    'scratch': ('g_EntityOffsetScratch', 0x80089E8C, '03000100010001000100010001000100010001000100'),
    'denominator': ('g_EntityOffsetScratchDenom', 0x80089EA2, '0100'),
    'yaw_one': ('g_RotateYawOne', 0x80089D18, '000001000100010000000100'),
    'yaw_quarter': ('g_RotateYawNegQuarter', 0x80089C94, '00000100a6ff010000000100'),
    'color_table': ('g_DreamColorTable', 0x80087E14, '060702040701030005000000'),
}
MOOD_ZERO = (0, 0, 0, 0, 0)


def locations():
    return dict(entity=n.ENTITY, dream=n.DREAM, context=n.CONTEXT, transform=TRANSFORM,
                **{key: address & n.MASK for key, (_name, address, _hex) in DATA.items()})


def base_case(**updates):
    case = dict(state=0, tick=1, triggered=1, active=1, mode=1, command_timer=12345,
                action=0, seed=0, move_mode=1, denominator=1, property_index=0,
                chunk_mood=MOOD_ZERO, instance_mood=MOOD_ZERO)
    case.update(updates)
    return case


def validate_case(case):
    for name in ('state', 'tick', 'triggered', 'active', 'mode', 'command_timer', 'action'):
        if type(case.get(name)) is not int or not -0x80000000 <= case[name] <= 0x7FFFFFFF:
            raise ValueError('Use a signed native word for ' + name)
    if type(case.get('seed')) is not int or not 0 <= case['seed'] <= 0xFFFFFFFF:
        raise ValueError('Use an unsigned native RNG seed.')
    if type(case.get('denominator')) is not int or not -32768 <= case['denominator'] <= 32767:
        raise ValueError('Use one original signed halfword denominator.')
    if type(case.get('move_mode')) is not int or case['move_mode'] not in range(4):
        raise ValueError('Use a reviewed callback mode.')
    if type(case.get('property_index')) is not int or not 0 <= case['property_index'] < 130:
        raise ValueError('Use an original entity property index.')
    for name in ('chunk_mood', 'instance_mood'):
        value = case.get(name)
        if (not isinstance(value, (tuple, list)) or len(value) != 5
                or any(type(part) is not int for part in value)
                or any(not -128 <= part <= 127 for part in value[:2])
                or any(not -0x80000000 <= part <= 0x7FFFFFFF for part in value[2:])):
            raise ValueError('Use two mood-axis bytes, two signed sums and a signed count.')
        if value[4] == -1 and -0x80000000 in value[2:4]:
            raise ValueError('The original signed division trap is outside this fixture domain.')


def read_word(data, offset):
    return struct.unpack_from('<i', data, offset)[0]


def quotient(value, divisor):
    if not divisor or value == -0x80000000 and divisor == -1:
        raise ValueError('Original division-trap input.')
    magnitude = abs(value) // abs(divisor)
    return -magnitude if (value < 0) != (divisor < 0) else magnitude


def fixtures(case):
    validate_case(case)
    buffers = {key: bytearray([fill]) * SIZES[key]
               for key, fill in (('entity', 0xD7), ('dream', 0xA6), ('context', 0xC4), ('transform', 0xB3))}
    for key, (_name, _address, raw) in DATA.items():
        buffers[key] = bytearray.fromhex(raw)
    entity, dream, context = (buffers[key] for key in ('entity', 'dream', 'context'))
    for offset, value in ((0, n.h.symbols['g_ENTITY_VTABLE']), (0xC, case['active']), (0x14, TRANSFORM),
            (0x44, case['state']), (0x58, n.SOUND), (0x6C, 0), (0x70, 0), (0x8C, 1), (0x90, 1),
            (0x94, n.DREAM), (0x98, case['property_index']), (0xF0, 1), (0xF4, case['triggered']),
            (0xF8, 1), (0xFC, case['tick'])):
        n.word(entity, offset, value)
    for offset, value in ((0, n.h.symbols['g_DREAM_SYS_VTABLE']), (0x74, case['action']),
            (0x80, 0xABCD1000), (0x84, 3), (0x98, 0xABCD2000), (0x9C, case['move_mode']),
            (0xC4, 1), (0xC8, 1)):
        n.word(dream, offset, value)
    for offset, field in ((0x144, 'chunk_mood'), (0x154, 'instance_mood')):
        last_dynamic, last_upper, sum_dynamic, sum_upper, count = case[field]
        struct.pack_into('<bb', dream, offset, last_dynamic, last_upper)
        struct.pack_into('<iii', dream, offset + 4, sum_dynamic, sum_upper, count)
    n.word(context, 4, case['mode'])
    n.word(context, 16, case['command_timer'])
    struct.pack_into('<h', buffers['denominator'], 0, case['denominator'])
    return buffers


def next_inputs(buffers, case):
    n.word(buffers['entity'], 0xFC, case['tick'])
    n.word(buffers['dream'], 0x74, case['action'])


def mood_average(dream, offset):
    last = struct.unpack_from('<bb', dream, offset)
    sums_and_count = struct.unpack_from('<iii', dream, offset + 4)
    count = sums_and_count[2]
    if count == 0:
        return last
    result = []
    for previous, total in zip(last, sums_and_count[:2]):
        combined = scripts.signed_word(quotient(total, count) + quotient(previous, 3))
        result.append(-9 if combined >= 10 else 9 if combined < -9 else combined)
    return tuple(result)


def expected(callback, case, previous=None):
    if callback not in CALLBACKS:
        raise ValueError('Unsupported original locomotive callback.')
    validate_case(case)
    buffers = fixtures(case) if previous is None else {key: bytearray(previous[key]) for key in SIZES}
    if previous is not None:
        next_inputs(buffers, case)
    entity, dream, context = (buffers[key] for key in ('entity', 'dream', 'context'))
    trace, seed = [], case['seed'] if previous is None else previous['rng_seed']

    def call(name, *args):
        trace.append([name, *map(n.u32, args)])

    def command(index, value):
        n.word(context, index * 4, value)

    def random():
        nonlocal seed
        call('rand', seed)
        seed = n.u32(seed * 0x41C64E6D + 0x3039)
        return seed >> 16 & 0x7FFF

    def rotation(who, mode, key):
        call('rotation', who, mode, DATA[key][1])
        trace[-1].append(bytes(buffers[key]).hex())

    def animation(playing):
        call('animation_play' if playing else 'animation_stop', n.ENTITY)
        n.word(entity, 0x90, int(playing))

    def disable():
        call('disable_link', n.ENTITY)
        call('child_link_flag', n.ENTITY, 0)
        call('stop_behaviour', n.ENTITY)
        call('sound_stop', n.SOUND, n.ENTITY + 0x9C)
        animation(False)
        call('model_unload', n.ENTITY)
        n.word(entity, 0x8C, 0)
        n.word(entity, 0xF8, 0)
        call('set_triggered', n.ENTITY, 0)
        n.word(entity, 0xF4, 0)
        n.word(entity, 0xF0, 0)

    def common(turn_start, end_tick, speed):
        call('common', n.ENTITY, n.CONTEXT, turn_start, end_tick, speed)
        command(4, 0)
        if read_word(context, 4) == 6:
            for index in (7, 12, 17):
                command(index, 4)
        tick = read_word(entity, 0xFC)
        windows = ((turn_start, turn_start + 91), (turn_start + 341, turn_start + 433),
                   (turn_start + 698, turn_start + 791))
        if any(first <= tick <= last for first, last in windows):
            rotation(n.ENTITY, 0, 'yaw_one')
        call('forward', n.ENTITY, speed, 0)
        if tick == end_tick:
            disable()
            n.word(entity, 0x44, 1)

    tick, state = read_word(entity, 0xFC), read_word(entity, 0x44)
    if callback == 'entity_locomotive_factory':
        if tick == 0:
            state = random() % 5 + 10
            n.word(entity, 0x44, state)
        if state < 14 or tick < 320:
            common(3000, 500, -256)
        elif state == 14 and tick & 3 == 0:
            struct.pack_into('<h', buffers['denominator'], 0, random() % 32 + 1)
            call('scale', n.ENTITY, 1, DATA['scratch'][1] + 12)
            trace[-1].append(bytes(buffers['scratch'][12:] + buffers['denominator']).hex())
    elif callback == 'entity_locomotive_kyoto':
        if read_word(context, 4) == 6:
            for index, value in ((4, 0), (7, 4), (12, 4), (17, 4)):
                command(index, value)
        if read_word(entity, 0xF4) != 0:
            if state == 0:
                n.word(entity, 0x44, 10)
                n.word(entity, 0xFC, 0)
            elif state == 10:
                if tick == 10:
                    call('notification', n.ENTITY, 10)
                else:
                    call('read_action', n.DREAM)
                    if read_word(dream, 0x74) != 0:
                        call('link_pose', n.DREAM, TRANSFORM + 0x38 if read_word(entity, 0xC) else 0)
                        rotation(n.DREAM, 1, 'yaw_quarter')
                        call('clear_callbacks', n.DREAM, 0)
                        call('set_move_callback', n.DREAM, 0)
                        if read_word(dream, 0x9C) == 2:
                            call('set_view_mode', n.DREAM, 0)
                            n.word(dream, 0xC4, 0)
                            n.word(dream, 0xC8, 0)
                        n.word(dream, 0x9C, 0)
                        n.word(dream, 0x98, 0)
                        n.word(entity, 0xFC, 0)
                        n.word(entity, 0x44, 11)
            elif state == 11:
                call('link_pose', n.DREAM, TRANSFORM + 0x38 if read_word(entity, 0xC) else 0)
                if tick == 100:
                    call('notification', n.ENTITY, 10)
        call('forward', n.ENTITY, -256, 0)
    else:
        if tick == 0:
            call('read_dream_color', n.DREAM)
            chunk, instance = mood_average(dream, 0x144), mood_average(dream, 0x154)
            trace.append(['chunk_average', *chunk])
            trace.append(['instance_average', *instance])
            if read_word(dream, 0x160) == 0:
                instance = chunk
            average = tuple(quotient(a + b, 2) for a, b in zip(chunk, instance))
            bins = [2 if value >= 4 else 0 if value < -3 else 1 for value in average]
            color = buffers['color_table'][bins[0] * 3 + bins[1]]
            trace.append(['dream_color', color])
            if color == 5:
                state = 11
                n.word(entity, 0x44, state)
        if state != 0 and tick >= 2160:
            if n.u32(tick - 2160) < 401:
                if tick == 2160:
                    animation(False)
                    for index in (7, 12, 17):
                        command(index, -2)
                elif n.u32(tick - 2550) < 10:
                    command(7, 5)
                    command(8, -2)
                elif tick == 2560:
                    animation(True)
                    command(1, 1)
            elif tick >= 2563:
                if tick >= 2801:
                    call('vertical', n.ENTITY, -32, 0)
                common(481, 4000, -60)
        else:
            common(481, 2180, -60)
    return {**{key: bytes(buffers[key]) for key in SIZES}, 'rng_seed': seed, 'trace': trace}


def first_result_seed(result):
    if type(result) is not int or not 0 <= result < 32768:
        raise ValueError('Use a fifteen-bit original RNG result.')
    return ((result << 16) - 0x3039) * pow(0x41C64E6D, -1, 1 << 32) & 0xFFFFFFFF


def slot(table, offset):
    return struct.unpack('<I', n.h.target(n.h.symbols[table] + offset, 4))[0] & n.MASK


class Machine(n.Machine):
    def __init__(self, callback, patches=None):
        if callback not in CALLBACKS:
            raise ValueError('Unsupported original locomotive callback.')
        self.callback, self.entry_counts, self.hits = callback, Counter(), Counter()
        self.contract_counts = Counter()
        self.changed_addresses, self.rejected_store = set(), None
        self.contracts = {
            slot('g_ENTITY_VTABLE', 0x44): ('rotation', 3),
            slot('g_ENTITY_VTABLE', 0x48): ('scale', 3),
            slot('g_ENTITY_VTABLE', 0xC4): ('forward', 3),
            slot('g_ENTITY_VTABLE', 0xCC): ('vertical', 3),
            slot('g_ENTITY_VTABLE', 0x30): ('notification', 2),
            slot('g_DREAM_SYS_VTABLE', 0xB8): ('link_pose', 2),
            n.h.symbols['sound_entity_stop'] & n.MASK: ('sound_stop', 2),
        }
        if len(self.contracts) != 7 or slot('g_ENTITY_VTABLE', 0x44) != slot('g_DREAM_SYS_VTABLE', 0x44):
            raise ValueError('Reviewed geometry/notification/sound bindings changed.')
        self.events = {
            'entity_locomotive_common': ('common', 5), 'entity_disable_link': ('disable_link', 1),
            'func_80065A5C': ('child_link_flag', 2), 'entity_stop_behaviour': ('stop_behaviour', 1),
            'entity_set_triggered': ('set_triggered', 2), 'func_800662A8': ('animation_play', 1),
            'func_800662B4': ('animation_stop', 1), 'func_80066148': ('model_unload', 1),
            'dream_sys_get_action_pressed': ('read_action', 1),
            'dream_sys_clear_callbacks': ('clear_callbacks', 2),
            'dream_sys_set_move_callback': ('set_move_callback', 2),
            'dream_sys_set_view_mode': ('set_view_mode', 2),
            'dream_sys_get_dream_color': ('read_dream_color', 1),
        }
        self.ranges = [(int(row['address'], 16) & n.MASK,
                        (int(row['address'], 16) & n.MASK) + row['bytes']) for row in FUNCTIONS]
        if {address for address, _end in self.ranges}.intersection(self.contracts):
            raise ValueError('A contract would bypass a claimed original native function.')
        super().__init__(start=n.h.symbols[callback] & n.MASK, native_functions=FUNCTIONS)
        for address, data in (patches or {}).items():
            self.cpu.mem_write(address & n.MASK, data)
            self.changed_addresses.add(address & n.MASK)

    def arguments(self, count):
        args = [self.cpu.reg_read(getattr(n.reg, 'UC_MIPS_REG_A' + str(index))) for index in range(min(count, 4))]
        if count == 5:
            args.append(struct.unpack('<I', self.cpu.mem_read(self.cpu.reg_read(n.reg.UC_MIPS_REG_SP) + 16, 4))[0])
        return args

    def hook(self, cpu, address, size, unused):
        pc = address & n.MASK
        if pc in self.changed_addresses:
            self.hits[pc] += 1
        returned = self.pending_returns.pop(pc, None)
        if returned is not None:
            label, destination = returned
            values = [cpu.reg_read(n.reg.UC_MIPS_REG_V0)] if destination is None else list(struct.unpack('<bb', cpu.mem_read(destination, 2)))
            self.trace.append([label, *values])
        if pc in self.native_entries:
            name = self.native_entries[pc]
            self.entry_counts[name] += 1
            if name == 'rand':
                self.trace.append(['rand', struct.unpack('<I', cpu.mem_read(n.RNG, 4))[0]])
            elif name in self.events:
                label, count = self.events[name]
                self.trace.append([label, *self.arguments(count)])
            if name in ('dream_sys_get_dream_color', 'dream_sys_get_mood_average'):
                target = cpu.reg_read(n.reg.UC_MIPS_REG_RA) & n.MASK
                if target in self.pending_returns:
                    raise ValueError('Unexpected nested mood return site.')
                if name == 'dream_sys_get_dream_color':
                    self.pending_returns[target] = ('dream_color', None)
                else:
                    _this, source, destination = self.arguments(3)
                    if source not in (n.DREAM + 0x144, n.DREAM + 0x154):
                        raise ValueError('Unexpected original mood contribution object.')
                    label = 'chunk_average' if source == n.DREAM + 0x144 else 'instance_average'
                    self.pending_returns[target] = (label, destination & n.MASK)
        contract = self.contracts.get(pc)
        if contract is not None:
            label, count = contract
            self.contract_counts[label] += 1
            args = self.arguments(count)
            event = [label, *args]
            if label in ('rotation', 'scale'):
                event.append(bytes(cpu.mem_read(args[2] & n.MASK, 12)).hex())
            self.trace.append(event)
            target = cpu.reg_read(n.reg.UC_MIPS_REG_RA)
            for index, register in enumerate(n.VOLATILE):
                cpu.reg_write(register, n.u32(0xBC000000 + 0x10203 * index))
            cpu.reg_write(n.reg.UC_MIPS_REG_V0, 0)
            cpu.reg_write(n.reg.UC_MIPS_REG_HI, 0xD13579BF)
            cpu.reg_write(n.reg.UC_MIPS_REG_LO, 0xE2468ACE)
            cpu.reg_write(n.reg.UC_MIPS_REG_PC, target)
        elif not any(start <= pc < end for start, end in self.ranges):
            raise ValueError('Execution escaped reviewed native/contract ranges: ' + hex(pc))
        else:
            word = struct.unpack('<I', cpu.mem_read(pc, 4))[0]
            opcode = word >> 26
            branch = opcode in (1, 2, 3, 4, 5, 6, 7) or opcode == 0 and word & 63 in (8, 9)
            if branch:
                delay = struct.unpack('<I', cpu.mem_read(pc + 4, 4))[0]
                link = 31 if opcode == 3 or opcode == 1 and word >> 16 & 31 in (16, 17) else (
                    word >> 11 & 31 if opcode == 0 and word & 63 == 9 else None)
                self.check_store(cpu, delay, pc + 4, pc, link)
            self.check_store(cpu, word, pc, pc)

    def check_store(self, cpu, word, instruction, observed_at, link=None):
        number = word >> 21 & 31
        span = store_span(word, cpu.reg_read(getattr(n.reg, 'UC_MIPS_REG_' + str(number))))
        if span is None:
            return
        if link is not None and number == link:
            raise ValueError('A delay store based on the changed link register needs separate review.')
        address, size = span
        current = locations()
        writable = ('entity', 'dream', 'context', 'transform', 'scratch', 'denominator')
        regions = [(current[key], current[key] + SIZES[key]) for key in writable]
        regions.extend(((n.RNG, n.RNG + 4), (n.STACK - 0x400, n.STACK + 0x100)))
        if not any(start <= address and address + size <= end for start, end in regions):
            self.rejected_store = dict(instruction=instruction, observed_at=observed_at, address=address, bytes=size)
            self.cpu.emu_stop()
            raise ValueError('Native write escaped declared buffers: ' + hex(address))

    def run(self, case, reset=True):
        validate_case(case)
        self.case, self.trace, self.pending_returns = case, [], {}
        self.hits.clear()
        self.rejected_store = None
        cpu = self.cpu
        if reset:
            for key, data in fixtures(case).items():
                cpu.mem_write(locations()[key], bytes(data))
            cpu.mem_write(n.RNG, struct.pack('<I', case['seed']))
        else:
            cpu.mem_write(n.ENTITY + 0xFC, struct.pack('<I', n.u32(case['tick'])))
            cpu.mem_write(n.DREAM + 0x74, struct.pack('<I', n.u32(case['action'])))
        cpu.mem_write(n.STACK - 0x400, bytes([0xCC]) * 0x500)
        saved = [n.u32(0xAB000000 + 0x10203 * index) for index in range(len(n.SAVED))]
        for register, value in zip(n.SAVED, saved):
            cpu.reg_write(register, value)
        for index, register in enumerate(n.VOLATILE):
            cpu.reg_write(register, n.u32(0xDA000000 + 0x10203 * index))
        for register, value in ((n.reg.UC_MIPS_REG_SP, n.STACK), (n.reg.UC_MIPS_REG_GP, 0x8008A808),
                (n.reg.UC_MIPS_REG_RA, n.END), (n.reg.UC_MIPS_REG_A0, n.ENTITY), (n.reg.UC_MIPS_REG_A1, n.CONTEXT)):
            cpu.reg_write(register, value)
        try:
            cpu.emu_start(self.start, n.END, count=30000)
        except n.unicorn.UcError as error:
            raise ValueError('Native execution failed at ' + hex(cpu.reg_read(n.reg.UC_MIPS_REG_PC)) + ': ' + str(error)) from error
        if (cpu.reg_read(n.reg.UC_MIPS_REG_PC) != n.END or cpu.reg_read(n.reg.UC_MIPS_REG_SP) != n.STACK
                or cpu.reg_read(n.reg.UC_MIPS_REG_GP) != 0x8008A808 or cpu.reg_read(n.reg.UC_MIPS_REG_RA) != n.END
                or [cpu.reg_read(register) for register in n.SAVED] != saved or self.pending_returns
                or bytes(cpu.mem_read(n.STACK - 0x400, 64)) != bytes([0xCC]) * 64
                or bytes(cpu.mem_read(n.STACK + 0x40, 64)) != bytes([0xCC]) * 64):
            raise ValueError('Original callback violated ABI, return, mood-return or stack guards.')
        return {**{key: bytes(cpu.mem_read(locations()[key], length)) for key, length in SIZES.items()},
                'rng_seed': struct.unpack('<I', cpu.mem_read(n.RNG, 4))[0], 'trace': self.trace}


def bindings():
    table = n.h.target(n.h.symbols['g_ENTITY_TABLE'], 130 * 16)
    result = {}
    for callback in CALLBACKS:
        found = [dict(index=index, record_sha256=hashlib.sha256(table[index * 16:index * 16 + 16]).hexdigest())
                 for index in range(130) if struct.unpack_from('<I', table, index * 16 + 12)[0] == n.h.symbols[callback]]
        if not found:
            raise ValueError('Missing original callback property binding: ' + callback)
        result[callback] = found
    return result, hashlib.sha256(table).hexdigest()


def cases(callback, property_index, exhaust_rng=True):
    base = base_case(property_index=property_index)
    if callback == CALLBACKS[0]:
        ticks = (-0x80000000, -1, 0, 1, 319, 320, 321, 323, 324, 499, 500, 501, 0x7FFFFFFF)
        for state, tick, mode in itertools.product((-0x80000000, -1, 0, 10, 13, 14, 15, 0x7FFFFFFF), ticks, (-1, 1, 6, 7)):
            yield 'factory_branch_boundaries', dict(base, state=state, tick=tick, mode=mode)
        for first, last in ((3000, 3091), (3341, 3433), (3698, 3791)):
            for tick, mode in itertools.product((first - 1, first, first + 1, last - 1, last, last + 1), (1, 6)):
                yield 'factory_inclusive_turn_windows', dict(base, state=13, tick=tick, mode=mode)
        for value in (-32768, -1, 0, 1, 32767):
            for result in (0, 1, 30, 31, 32, 32767):
                yield 'separate_adjacent_denominator', dict(base, state=14, tick=320, denominator=value, seed=first_result_seed(result))
        if exhaust_rng:
            for result in range(32768):
                yield 'all_initial_rng_results', dict(base, tick=0, seed=first_result_seed(result))
                yield 'all_scale_rng_results', dict(base, state=14, tick=320, seed=first_result_seed(result))
    elif callback == CALLBACKS[1]:
        for state, tick, action, triggered, active, mode in itertools.product((-1, 0, 1, 10, 11, 12),
                (-0x80000000, -1, 0, 1, 9, 10, 11, 99, 100, 101, 0x7FFFFFFF),
                (0, 1, -1, 0x10000), (0, 1, -1), (0, 1), (1, 6)):
            yield 'kyoto_state_action_and_link_boundaries', dict(base, state=state, tick=tick, action=action,
                triggered=triggered, active=active, mode=mode)
        for move_mode, active in itertools.product(range(4), (0, 1, -1, 0x10000)):
            yield 'kyoto_callback_reset_modes', dict(base, state=10, tick=9, action=0x10000, move_mode=move_mode, active=active)
    elif callback == CALLBACKS[2]:
        ticks = (-0x80000000, -1, 0, 1, 2159, 2160, 2161, 2179, 2180, 2181, 2549, 2550,
                 2551, 2558, 2559, 2560, 2561, 2562, 2563, 2564, 2800, 2801, 2802, 3999, 4000, 4001, 0x7FFFFFFF)
        for state, tick, mode in itertools.product((-0x80000000, -1, 0, 1, 10, 11, 0x7FFFFFFF), ticks, (-1, 1, 6, 7)):
            yield 'natural_pause_and_restart_boundaries', dict(base, state=state, tick=tick, mode=mode)
        for first, last in ((481, 572), (822, 914), (1179, 1272)):
            for tick, mode in itertools.product((first - 1, first, first + 1, last - 1, last, last + 1), (1, 6)):
                yield 'natural_inclusive_turn_windows', dict(base, tick=tick, mode=mode)
        axes = (-128, -10, -4, -3, 0, 3, 4, 9, 127)
        for dynamic, upper, state in itertools.product(axes, axes, (0, 1, 11)):
            yield 'all_color_bins_and_axis_byte_edges', dict(base, tick=0, state=state,
                chunk_mood=(dynamic, upper, 0, 0, 0))
        moods = [(-9, 9, -40, 40, 4), (9, -9, 40, -40, 4), (4, 4, 0, 0, 0),
                 (0, 0, 9, 10, 1), (0, 0, -9, -10, 1), (0, 0, -11, 11, 1),
                 (-128, 127, -0x80000000, 0x7FFFFFFF, 1), (127, -128, 0x7FFFFFFF, -0x80000000, 1),
                 (-9, 9, -11, 11, -3), (9, -9, 11, -11, 3), MOOD_ZERO]
        for chunk, instance in itertools.product(moods, repeat=2):
            yield 'counted_mood_wrap_and_contribution_combination', dict(base, tick=0, chunk_mood=chunk, instance_mood=instance)
    else:
        raise ValueError('Unsupported callback fixture domain.')


def histories(callback, index):
    if callback == CALLBACKS[0]:
        for result in (0, 4):
            base = base_case(property_index=index, mode=6, tick=0, seed=first_result_seed(result))
            yield 'factory-roll-' + str(result), [dict(base, tick=tick) for tick in
                (0, 1, 319, 320, 321, 324, 499, 500, 501, 3000, 3091, 3092, 3341, 3433, 3698, 3791)]
    elif callback == CALLBACKS[1]:
        for active, move_mode in itertools.product((0, 1), (0, 1, 2, 3)):
            base = base_case(property_index=index, active=active, move_mode=move_mode, mode=6)
            yield 'kyoto-link-' + str(active) + '-move-' + str(move_mode), [dict(base, tick=tick, action=action)
                for tick, action in ((0, 0), (1, 0), (9, 0), (10, 0x10000), (11, 0x10000), (1, 0), (99, 0), (100, 0))]
    else:
        for state, mood in itertools.product((0, 1), (MOOD_ZERO, (9, 9, 0, 0, 0))):
            base = base_case(property_index=index, state=state, chunk_mood=mood, mode=6)
            yield 'natural-state-' + str(state) + '-pink-' + str(mood != MOOD_ZERO), [dict(base, tick=tick) for tick in
                (0, 481, 572, 822, 914, 1179, 1272, 2159, 2160, 2161, 2180, 2181, 2549, 2550,
                 2559, 2560, 2561, 2562, 2563, 2800, 2801, 3999, 4000, 4001)]


def input_key(case):
    digest = hashlib.sha256()
    for key, data in sorted(fixtures(case).items()):
        digest.update(key.encode() + b'\0' + bytes(data))
    digest.update(struct.pack('<I', case['seed']))
    return digest.digest()


def fault_instruction(function, expected_word, offset=None):
    record = next(row for row in FUNCTIONS if row['function'] == function)
    start = int(record['address'], 16)
    if offset is None:
        code = n.h.target(start, record['bytes'])
        found = [index for index in range(0, len(code), 4)
                 if struct.unpack_from('<I', code, index)[0] == expected_word]
        if len(found) != 1:
            raise ValueError('Expected one reviewed fault instruction in ' + function)
        offset = found[0]
    if (offset % 4 or not 0 <= offset <= record['bytes'] - 4
            or struct.unpack('<I', n.h.target(start + offset, 4))[0] != expected_word):
        raise ValueError('Reviewed fault instruction changed in ' + function)
    return start + offset, offset


def controls():
    factory, kyoto, natural = CALLBACKS
    specifications = [
        ('wrong_initial_state_offset', factory, factory, 0x2442000A, 0x2442000B,
         dict(tick=0, seed=first_result_seed(0)), None),
        ('wrong_factory_scale_boundary', factory, factory, 0x28620140, 0x28620141,
         dict(state=14, tick=320), None),
        ('scale_write_corrupts_array_instead_of_denominator', factory, factory, 0xA4C20000, 0xA4C2FFFE,
         dict(state=14, tick=320, denominator=23, seed=first_result_seed(31)), None),
        ('wrong_scale_fraction_pointer', factory, factory, 0x24C6FFF6, 0x24C6FFF4,
         dict(state=14, tick=320), None),
        ('wrong_first_inclusive_turn_end', 'entity_locomotive_common', factory, 0x24C2005B, 0x24C2005A,
         dict(state=13, tick=3091), None),
        ('wrong_second_inclusive_turn_end', 'entity_locomotive_common', factory, 0x24C201B1, 0x24C201B0,
         dict(state=13, tick=3433), None),
        ('wrong_third_inclusive_turn_end', 'entity_locomotive_common', factory, 0x24C20317, 0x24C20316,
         dict(state=13, tick=3791), None),
        ('truncated_action_word', 'dream_sys_get_action_pressed', kyoto, 0x8C820074, 0x94820074,
         dict(state=10, tick=9, action=0x10000, move_mode=2), None),
        ('wrong_kyoto_action_exclusion', kyoto, kyoto, 0x10430041, 0x14430041,
         dict(state=10, tick=9, action=1), None),
        ('wrong_kyoto_notification_tick', kyoto, kyoto, 0x34020064, 0x34020065,
         dict(state=11, tick=100), None),
        ('wrong_link_transform_offset', kyoto, kyoto, 0x24450038, 0x2445003C,
         dict(state=10, tick=9, action=1, active=1), 0xB8),
        ('truncated_link_active_word', kyoto, kyoto, 0x8E03000C, 0x9603000C,
         dict(state=10, tick=9, action=1, active=0x10000), 0xA0),
        ('wrong_view_reset_destination', 'dream_sys_set_view_mode', kyoto, 0xAC4000C4, 0xAC4000C0,
         dict(state=10, tick=9, action=1, move_mode=2), None),
        ('wrong_pause_start', natural, natural, 0x28620870, 0x28620871,
         dict(state=11, tick=2160), None),
        ('wrong_inclusive_animation_resume', natural, natural, 0x2C420191, 0x2C420190,
         dict(state=11, tick=2560, mode=6), None),
        ('wrong_movement_resume', natural, natural, 0x28620A03, 0x28620A04,
         dict(state=11, tick=2563), None),
        ('wrong_vertical_start', natural, natural, 0x28620AF1, 0x28620AF2,
         dict(state=11, tick=2801), None),
        ('wrong_mood_axis_wrap', 'calc_mood_axis', natural, 0x28A2000A, 0x28A2000B,
         dict(tick=0, chunk_mood=(0, 0, 10, 0, 1)), None),
        ('wrong_positive_color_bin', 'calc_dream_color', natural, 0x28620004, 0x28620005,
         dict(tick=0, chunk_mood=(4, 4, 0, 0, 0)), None),
        ('wrong_negative_color_bin', 'calc_dream_color', natural, 0x2862FFFD, 0x2862FFFE,
         dict(tick=0, chunk_mood=(-3, -3, 0, 0, 0)), None),
        ('wrong_rng_multiplier', 'rand', factory, 0x34634E6D, 0x34634E6E,
         dict(tick=0, seed=1), None),
    ]
    bound, _table_hash = bindings()
    results = []
    for label, function, callback, old, changed, updates, offset in specifications:
        address, offset = fault_instruction(function, old, offset)
        case = base_case(property_index=bound[callback][0]['index'], **updates)
        machine = Machine(callback, {address: struct.pack('<I', changed)})
        actual, model = machine.run(case), expected(callback, case)
        differences = [key for key in model if actual[key] != model[key]]
        hits = machine.hits[address & n.MASK]
        if not hits or not differences:
            raise ValueError('A completed fault must execute and change checked results: ' + label)
        results.append(dict(kind=label, function=function, callback=callback, function_offset=offset,
            address=hex(address), expected_word=hex(old), changed_word=hex(changed),
            changed_instruction_executions=hits, changed_checked_fields=differences,
            scope='Separate private Unicorn memory; no source or canonical image modification.'))
    return results


def write_bounds_controls():
    specifications = [
        ('out_of_profile_halfword_store', CALLBACKS[0], CALLBACKS[0], 0xA4C20000, 0xA4C20002,
         DATA['denominator'][1] + 2, 2, dict(state=14, tick=320)),
        ('out_of_profile_delay_slot_store', 'entity_locomotive_common', CALLBACKS[0], 0xACA00010, 0xACA00100,
         n.CONTEXT + 0x100, 4, dict(state=13, tick=1, mode=6)),
    ]
    results = []
    for label, function, callback, old, changed, destination, size, updates in specifications:
        address, offset = fault_instruction(function, old)
        machine = Machine(callback, {address: struct.pack('<I', changed)})
        before = bytes(machine.cpu.mem_read(destination & n.MASK, size))
        try:
            machine.run(base_case(**updates))
        except ValueError as error:
            rejected = machine.rejected_store
            if ('Native write escaped declared buffers' not in str(error) or rejected is None
                    or rejected['instruction'] != address & n.MASK
                    or rejected['address'] != destination & n.MASK or rejected['bytes'] != size):
                raise
        else:
            raise ValueError('An escaped write was not rejected before execution.')
        if bytes(machine.cpu.mem_read(destination & n.MASK, size)) != before:
            raise ValueError('The write guard must preserve the rejected destination bytes.')
        results.append(dict(kind=label, function=function, function_offset=offset,
            address=hex(address), expected_word=hex(old), attempted_word=hex(changed),
            attempted_destination=hex(destination), bytes=size,
            decoded_from_instruction=hex(machine.rejected_store['observed_at']),
            changed_instruction_execution_observations=machine.hits[address & n.MASK],
            rejected_before_store=True, destination_bytes_preserved=True,
            distinct_from_completed_behavior_faults=True))
    return results


def verify(destination, exhaust_rng=True):
    destination = Path(destination).resolve()
    lab = (ROOT / '.decomp-lab').resolve()
    if not destination.is_relative_to(lab) or destination == lab or destination.exists():
        raise ValueError('Choose a fresh private output directory under .decomp-lab.')
    dependencies = n.evidence_dependencies('tools/verify_scripted_ai.py', 'tools/verify_gunman_scripts.py',
        'docs/gunman-function-ranges.json', 'asm/data/783DC.data.s') + [Path(__file__), RANGE_FILE]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    n.initialize_backend(n.load_program(FUNCTIONS))
    for key, (name, address, raw) in DATA.items():
        if n.h.symbols.get(name) != address or n.h.target(address, SIZES[key]) != bytes.fromhex(raw):
            raise ValueError('Original data identity changed: ' + name)
    bound, table_hash = bindings()
    backend = scripts.backend_identity()
    destination.mkdir(exist_ok=False)
    (destination / 'source-snapshot.py').write_bytes(Path(__file__).read_bytes())
    (destination / 'preflight.json').write_text(json.dumps({str(path): digest for path, digest in before.items()}, indent=2) + '\n')
    started = time.monotonic()
    profiles, entries, contract_counts, history_observations = {}, Counter(), Counter(), []
    input_digest, output_digest = hashlib.sha256(), hashlib.sha256()
    for callback in CALLBACKS:
        machine, seen, groups, states = Machine(callback), set(), Counter(), Counter()
        for binding in bound[callback]:
            for group, case in cases(callback, binding['index'], exhaust_rng):
                key = input_key(case)
                if key in seen:
                    continue
                seen.add(key)
                actual, model = None, None
                try:
                    actual, model = machine.run(case), expected(callback, case)
                    if actual != model:
                        raise ValueError('Native/model output mismatch: ' + repr([key for key in model if actual[key] != model[key]]))
                except Exception as error:
                    failure = dict(callback=callback, group=group, case=case, error=str(error))
                    if actual is not None and model is not None:
                        failure.update(native=repr(actual), model=repr(model))
                    (destination / 'failure.json').write_text(json.dumps(failure, indent=2) + '\n')
                    raise
                groups[group] += 1
                states[read_word(actual['entity'], 0x44)] += 1
                input_digest.update(callback.encode() + b'\0' + key)
                output_digest.update(repr(actual).encode())
        profiles[callback] = dict(native_cases=sum(groups.values()), groups=dict(groups),
            resulting_states=dict(states), actual_native_entry_counts=dict(machine.entry_counts),
            actual_dependency_contract_counts=dict(machine.contract_counts))
        entries.update(machine.entry_counts)
        contract_counts.update(machine.contract_counts)
        print(callback, sum(groups.values()), 'native cases passed', flush=True)
        for name, sequence in histories(callback, bound[callback][0]['index']):
            history_machine, previous = Machine(callback), None
            for step, case in enumerate(sequence):
                actual, model = history_machine.run(case, reset=step == 0), expected(callback, case, previous)
                if actual != model:
                    (destination / 'history-failure.json').write_text(json.dumps(dict(callback=callback, name=name,
                        step=step, case=case, native=repr(actual), model=repr(model)), indent=2) + '\n')
                    raise ValueError('A scheduled locomotive script history differs.')
                previous = model
                output_digest.update(repr(actual).encode())
            history_observations.append(dict(callback=callback, name=name, script_invocations=len(sequence),
                submitted_inputs=sequence, final_state=read_word(previous['entity'], 0x44),
                actual_native_entry_counts=dict(history_machine.entry_counts)))
            entries.update(history_machine.entry_counts)
            contract_counts.update(history_machine.contract_counts)
    faults = controls()
    bounds = write_bounds_controls()
    if (scripts.backend_identity() != backend or (ROOT / n.configure.ROM).read_bytes() != n.h.ROM
            or (ROOT / n.configure.EXE).read_bytes() != n.h.ROM or n.check_build_current(ROOT) is not True
            or any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path, digest in before.items())):
        raise ValueError('Original sources, backend or canonical build changed during verification.')
    missing = {row['function'] for row in FUNCTIONS} - entries.keys()
    if missing:
        raise ValueError('A claimed native function did not execute: ' + repr(sorted(missing)))
    declared_contracts = {name for name, _count in Machine(CALLBACKS[0]).contracts.values()}
    if declared_contracts != set(contract_counts):
        raise ValueError('An explicit dependency contract was not exercised by positive fixtures.')
    report = dict(status='passed_bounded_original_locomotive_scripts',
        profiles=profiles, native_functions=FUNCTIONS, actual_native_entry_counts=dict(entries),
        callback_bindings=bound, property_table_sha256=table_hash, backend_identity=backend,
        exhaustive_first_rng_results_per_site=32768 if exhaust_rng else 0,
        histories=history_observations, history_invocations=sum(row['script_invocations'] for row in history_observations),
        original_data_objects=[dict(symbol=name, address=hex(address), bytes=SIZES[key],
            sha256=hashlib.sha256(bytes.fromhex(raw)).hexdigest()) for key, (name, address, raw) in DATA.items()],
        dependency_contracts=sorted(declared_contracts), actual_dependency_contract_counts=dict(contract_counts),
        negative_controls_detected=faults, write_bounds_controls=bounds,
        store_guard='Instruction-level R3000 integer-store spans; branch delay slots checked before the branch; no memory-write hook.',
        canonical_executable_sha1=hashlib.sha1(n.h.ROM).hexdigest(), canonical_original_and_build_equal=True,
        input_digest_sha256=input_digest.hexdigest(), output_digest_sha256=output_digest.hexdigest(),
        input_digest_scope='Deduplicated standalone initialized buffers and RNG seed, with callback identity. Histories separately record their submitted input sequences.',
        producer_dependencies=[dict(path=path.resolve().relative_to(ROOT).as_posix(), sha256=digest) for path, digest in before.items()],
        original_behavior_modified=False, source_functions_promoted=0, whole_feature_groups_accepted=0,
        whole_NPC_encounters_accepted=0, model_api_calls=0, negative_controls_executed=True,
        scope='Constructed locomotive script states, actual RNG, link-disable helpers with no child nodes, animation flags, player callback clear and complete mood-to-color chain. Seven explicit contracts cover rotation, scale, forward/vertical motion, link pose, notification and sound. Histories preserve buffers/RNG and inject tick/action inputs. This is not complete engine stepping, natural encounter acceptance, geometry, audio or PS1 timing. No C recovered.',
        elapsed_seconds=round(time.monotonic() - started, 3))
    with (destination / 'report.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--smoke', action='store_true', help='Omit the two exhaustive RNG domains; retain all boundary fixtures.')
    args = parser.parse_args(argv)
    report = verify(args.output, exhaust_rng=not args.smoke)
    print(json.dumps(dict(status=report['status'], native_cases=sum(row['native_cases'] for row in report['profiles'].values()),
        native_functions_executed=len(report['actual_native_entry_counts']), history_invocations=report['history_invocations'],
        completed_behavior_faults=len(report['negative_controls_detected']),
        rejected_store_controls=len(report['write_bounds_controls']), new_C_bytes=0), indent=2), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
