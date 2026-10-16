"""Check bounded generation structure dispatch with original native routines.

All four modes execute their actual update paths, including mode 0's eight
rate variants and four active child layouts. These valid manual
object graphs do not establish construction, rendering, lifetime or encounter
acceptance. This analysis tool changes no original behavior and calls no model.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import verify_native_ai as n
from tools.verify_scripted_ai import backend_identity

OBJECTS, COORDS, SPRITES, PLAYER, WORLD = 0x100000, 0x110000, 0x120000, 0x130000, 0x131000
COUNT = 17
POSES, CHILD_NODES, CHILD_COORDS, CHILD_POSES, SIZE_KEYS = 0x140000, 0x150000, 0x160000, 0x170000, 0x180000
RATE_WORDS = (0, 0, 0, -1, -2, -4, -16, -256)
FUNCTIONS = [
    {
        "function": "dream_generation_update_structure_entities",
        "address": "0x80054C74",
        "bytes": 136,
        "sha256": "8e76e15aa6bb2308176a4a72b32eb3b71f3adc0e5d2b88c3c229f2d6335e54a5"
    },
    {
        "function": "func_800564F4",
        "address": "0x800564F4",
        "bytes": 44,
        "sha256": "fab2c1f0323e006fa234e024d1b4fd571ea09e24ce4c3c7dbf9c9fe0f3ee11a3"
    },
    {
        "function": "func_80056640",
        "address": "0x80056640",
        "bytes": 216,
        "sha256": "3cc6def140e06a9bd9e7b2c106751e0124171436e49a4e6bbb86fcb414d31066"
    },
    {
        "function": "func_80056794",
        "address": "0x80056794",
        "bytes": 64,
        "sha256": "491f5cc3d82c61bde594eb5804a4ed3ab1588587adfeaeb3e393d3aa05fdf7e7"
    },
    {
        "function": "func_800569A8",
        "address": "0x800569A8",
        "bytes": 484,
        "sha256": "118a8fd70514047175034b75986589933f746cb62ed4c9378122177ff098e826"
    },
    {
        "function": "func_80056DF0",
        "address": "0x80056DF0",
        "bytes": 8,
        "sha256": "6d64edf91449c1b17746c1ef18afa2eb25c70bdf1322ab3df5a2630993b7e2f1"
    },
    {
        "function": "func_80056E44",
        "address": "0x80056E44",
        "bytes": 228,
        "sha256": "a66d08b7b2426dba486e08913830f6bd56cb3c1f01a512fb8739206bf0b05386"
    },
    {
        "function": "func_80057384",
        "address": "0x80057384",
        "bytes": 36,
        "sha256": "209c4d51b9f0747d871ce8d9e5dde8a14d4e0235eeed3191c3723dfa3c7e2bba"
    },
    {
        "function": "func_800573CC",
        "address": "0x800573CC",
        "bytes": 120,
        "sha256": "c1a99e64390fec4e8dcf12a0a17942c6c30f55d6703dc08a78cd5e1111b8ad19"
    },
    {
        "function": "func_80057DF4",
        "address": "0x80057DF4",
        "bytes": 324,
        "sha256": "399a7dc526a1823315f40f5be164b6635b61bb36bddfb31d737c0c3cbb8fc54e"
    },
    {
        "function": "rand",
        "address": "0x80049480",
        "bytes": 40,
        "sha256": "4c54a1210ed147afe9b02657c9b12bdec5bb62c5584a2a9fef212567d0e04c0c"
    },
    {
        "function": "func_8001CEB4",
        "address": "0x8001CEB4",
        "bytes": 340,
        "sha256": "722d79cf1f8c109300d4a56aa1d421442a2b5c424a7f3f1e16ad27d281432217"
    },
    {
        "function": "func_8001EC84",
        "address": "0x8001EC84",
        "bytes": 120,
        "sha256": "7c14d23868ee93933886ecd2477e4e60c6200bef1982963f671e2d76e6d7caaf"
    },
    {
        "function": "func_80056858",
        "address": "0x80056858",
        "bytes": 336,
        "sha256": "7a884633b9d0163a2987efdc1a6545f4ddf0ccbc0af3968291f154532bd2aed8"
    },
    {
        "function": "func_800573A8",
        "address": "0x800573A8",
        "bytes": 36,
        "sha256": "cb98f20f55e4915c70de0cd5ec85346bad6f0c06c72aa4c2ff968b5327149cda"
    }
]

TABLES = [
    {
        "symbol": "D_800876FC",
        "address": "0x800876FC",
        "bytes": 240,
        "sha256": "ea50c46e67e855f2a98796a6a7a490f146ed485761ececdc3555a834f28d3cc7"
    },
    {
        "symbol": "D_800879C4",
        "address": "0x800879C4",
        "bytes": 200,
        "sha256": "5b88043978c8bc3b061d49f9f28dd604e09d5d62d6b02c47ebc3e673cba381bc"
    },
    {
        "symbol": "D_8008788C",
        "address": "0x8008788C",
        "bytes": 72,
        "sha256": "403231f56003ebf51b01f5b53feaa6b94a001c57e31082bf27c6f65f7cd8e477"
    },
    {
        "symbol": "D_8008780C",
        "address": "0x8008780C",
        "bytes": 32,
        "sha256": "ab02dcd6068e498f46dc68c6b5e37f373cdb2fb8a80a4e3225d348fa882e7080"
    },
    {
        "symbol": "D_800878D4",
        "address": "0x800878D4",
        "bytes": 240,
        "sha256": "74ba4f812269d36e971368efa639a6cb725213972f6958caed2bdf3c42a15388"
    },
    {
        "symbol": "D_800877EC",
        "address": "0x800877EC",
        "bytes": 12,
        "sha256": "15ec7bf0b50732b49f8228e07d24365338f9e3ab994b00af08e5a3bffe55fd8b"
    },
    {
        "symbol": "D_800877F8",
        "address": "0x800877F8",
        "bytes": 20,
        "sha256": "ce6e22474801b381f8536532d43fb6a13e69925d8bb54734161672d8bf826726"
    },
    {
        "symbol": "D_8008782C",
        "address": "0x8008782C",
        "bytes": 12,
        "sha256": "15ec7bf0b50732b49f8228e07d24365338f9e3ab994b00af08e5a3bffe55fd8b"
    },
    {
        "symbol": "D_80087838",
        "address": "0x80087838",
        "bytes": 12,
        "sha256": "204c385cce9a7336c400ab87845785f6ca52fe18047d8c29cd77f724c2cf57e0"
    }
]


def validate_case(case):
    for name in ('type', 'count', 'mode', 'tick', 'enabled', 'variant', 'height',
                 'baseline_height', 'scale_mode', 'scale_value'):
        value = case.get(name)
        if type(value) is not int or not -0x80000000 <= value <= 0x7FFFFFFF:
            raise ValueError('Expected a native signed word: ' + name)
    if (case['count'] > COUNT or case['mode'] not in (0, 1, 2, 3)
            or case['enabled'] not in range(5) or case['variant'] not in range(8)):
        raise ValueError('Fixture lies outside the bounded generation object graph.')
    if type(case.get('seed')) is not int or not 0 <= case['seed'] <= 0xFFFFFFFF:
        raise ValueError('Expected an unsigned native RNG seed.')
    position = case.get('position')
    if (not isinstance(position, (tuple, list)) or len(position) != 3
            or any(type(value) is not int or not -0x80000000 <= value <= 0x7FFFFFFF
                   for value in position)):
        raise ValueError('Expected three signed player position words.')
    euler = case.get('euler', (0, 0, 0))
    key = case.get('size_key', 1)
    if (not isinstance(euler, (tuple, list)) or len(euler) != 3
            or any(type(value) is not int or not -0x8000 <= value <= 0x7FFF for value in euler)
            or type(key) is not int or not -0x8000 <= key <= 0x7FFF):
        raise ValueError('Expected signed halfwords for Euler angles and size key.')


def s32(value):
    return (value + 0x80000000) % 0x100000000 - 0x80000000


def sh(value):
    return (value + 0x8000) % 0x10000 - 0x8000


def div(left, right):
    return (-1 if (left < 0) != (right < 0) else 1) * (abs(left) // abs(right))


def fixtures(case):
    validate_case(case)
    objects = bytearray([0x9D]) * (COUNT * 0x100)
    coords = bytearray([0xBE]) * (COUNT * 0x100)
    sprites = bytearray([0xA7]) * (COUNT * 4 * 0x100)
    poses = bytearray([0xAF]) * (COUNT * 0x100)
    child_nodes = bytearray([0xBD]) * (COUNT * 2 * 0x100)
    child_coords = bytearray([0xCD]) * (COUNT * 2 * 0x100)
    child_poses = bytearray([0xDA]) * (COUNT * 2 * 0x100)
    keys = bytearray([0x9B]) * (COUNT * 0x10)
    player = struct.pack('<3i', *case['position'])
    world = bytearray([0xCB]) * 0x30
    n.word(world, 0x18, case['height'])
    for i in range(COUNT):
        off = i * 0x100
        for offset, value in ((0, n.h.symbols['D_800876FC']), (0x14, COORDS + off),
                              (0x24, case['tick']), (0x54, case['mode']),
                              (0x68, SIZE_KEYS + i * 0x10),
                              (0x6C, case['enabled']), (0x70, case['variant'])):
            n.word(objects, off + offset, value)
        for axis, value in enumerate((100 * i - 200, 30 - i, -50 * i)):
            n.word(objects, off + 0x58 + axis * 4, value)
        n.word(coords, off, 1)
        n.word(coords, off + 0x44, POSES + off)
        struct.pack_into('<3h', poses, off + 0x10, *case.get('euler', (0, 0, 0)))
        struct.pack_into('<h', keys, i * 0x10, case.get('size_key', 1))
        for child in range(2):
            child_off = (i * 2 + child) * 0x100
            n.word(objects, off + 0x7C + child * 4, CHILD_NODES + child_off)
            n.word(child_nodes, child_off, n.h.symbols['D_800878D4'])
            n.word(child_nodes, child_off + 0x14, CHILD_COORDS + child_off)
            n.word(child_coords, child_off, 1)
            n.word(child_coords, child_off + 0x44, CHILD_POSES + child_off)
            for axis, value in enumerate((111 + child, 222 + i, 333 - child)):
                n.word(child_coords, child_off + 0x18 + axis * 4, value)
            struct.pack_into('<3h', child_poses, child_off + 0x10, *case.get('euler', (0, 0, 0)))
        for child in range(4):
            spoff = (i * 4 + child) * 0x100
            n.word(objects, off + 0x88 + child * 4, SPRITES + spoff)
            for offset, value in ((0, n.h.symbols['D_800879C4']), (0x58, case['scale_mode']),
                                  (0x5C, case['scale_value']), (0x60, case['scale_value'] - 1)):
                n.word(sprites, spoff + offset, value)
    listing = b''.join(struct.pack('<I', OBJECTS + i * 0x100) for i in range(COUNT))
    return dict(objects=objects, coordinates=coords, sprites=sprites,
                player=player, world=world, listing=listing, poses=poses,
                child_nodes=child_nodes, child_coordinates=child_coords,
                child_poses=child_poses, size_keys=keys)


def rotate_model(buffers, name, offset, source, trace, obj):
    data = n.h.target(source, 12)
    delta = []
    for numerator, denominator in struct.iter_unpack('<hh', data):
        quotient = div(numerator, denominator)
        fixed = (quotient << 12) + div((numerator - quotient * denominator) << 12, denominator)
        delta.append(div(fixed, 360))
    trace.append(['rotation', obj, 0, source])
    for axis, value in enumerate(delta):
        old = struct.unpack_from('<h', buffers[name], offset + 0x10 + axis * 2)[0]
        value = old + value
        value = value - div(value, 4096) * 4096
        struct.pack_into('<h', buffers[name], offset + 0x10 + axis * 2, sh(value))


def model(case, previous=None):
    if previous is None:
        buffers, trace, seed = fixtures(case), [], n.u32(case['seed'])
    else:
        validate_case(case)
        buffers = {name: bytearray(data) for name, data in previous.items() if name not in ('trace', 'rng_seed')}
        buffers['player'] = struct.pack('<3i', *case['position'])
        n.word(buffers['world'], 0x18, case['height'])
        trace, seed = [], previous['rng_seed']
    if case['type'] >= 0 and case['count'] > 0:
        for i in range(case['count']):
            off, obj = i * 0x100, OBJECTS + i * 0x100
            trace.append(['update', obj, PLAYER])
            tick = n.u32(struct.unpack_from('<I', buffers['objects'], off + 0x24)[0] + 1)
            n.word(buffers['objects'], off + 0x24, tick)
            result = [s32(case['position'][axis] + value)
                      for axis, value in enumerate((100 * i - 200, 30 - i, -50 * i))]
            result[1] = s32(result[1] + s32(case['height'] - case['baseline_height']))
            trace.append(['position_set', obj, result])
            for axis, value in enumerate(result):
                n.word(buffers['coordinates'], off + 0x18 + axis * 4, value)
            n.word(buffers['coordinates'], off, 0)
            mode = struct.unpack_from('<i', buffers['objects'], off + 0x54)[0]
            enabled = struct.unpack_from('<i', buffers['objects'], off + 0x6C)[0]
            variant = struct.unpack_from('<i', buffers['objects'], off + 0x70)[0]
            if mode == 0:
                rate = struct.unpack('<i', n.h.target(n.h.symbols['D_8008780C'] + variant * 4, 4))[0]
                if enabled and rate and tick >= 501:
                    rotation = n.h.symbols['D_80087838']
                    rotate_model(buffers, 'poses', off, rotation, trace, obj)
                    base = list(struct.unpack('<3i', n.h.target(n.h.symbols['D_8008782C'], 12)))
                    for child in range(2):
                        child_off = (i * 2 + child) * 0x100
                        child_obj = CHILD_NODES + child_off
                        vector = list(base)
                        vector[2] = s32(vector[2] + child * 3 + rate)
                        trace.append(['position_add', child_obj, vector])
                        for axis, value in enumerate(vector):
                            offset = child_off + 0x18 + axis * 4
                            old = struct.unpack_from('<i', buffers['child_coordinates'], offset)[0]
                            n.word(buffers['child_coordinates'], offset, old + value)
                        rotate_model(buffers, 'child_poses', child_off, rotation, trace, child_obj)
                        n.word(buffers['child_coordinates'], child_off, 0)
                    period = abs(div(0x5FB4, rate))
                    if tick % period == 0:
                        local = list(struct.unpack('<3i', n.h.target(n.h.symbols['D_800877EC'], 12)))
                        scale = struct.unpack('<i', n.h.target(n.h.symbols['D_800877F8'] + enabled * 4, 4))[0]
                        for child in range(2):
                            child_off = (i * 2 + child) * 0x100
                            if enabled < 3:
                                key = struct.unpack_from('<h', buffers['size_keys'], i * 0x10)[0]
                                local[0] = s32(local[0] + key * scale)
                            else:
                                local[1] = s32(local[1] + scale)
                            trace.append(['position_set', CHILD_NODES + child_off, list(local)])
                            for axis, value in enumerate(local):
                                n.word(buffers['child_coordinates'], child_off + 0x18 + axis * 4, value)
                            n.word(buffers['child_coordinates'], child_off, 0)
            elif mode == 3:
                for child in range(4):
                    spoff = (i * 4 + child) * 0x100
                    trace.append(['rand', seed])
                    seed = (seed * 0x41C64E6D + 0x3039) & 0xFFFFFFFF
                    table = n.h.symbols['D_8008788C'] + 12 * (((seed >> 16) & 0x7FFF) % 6)
                    values = []
                    for numerator, denominator in struct.iter_unpack('<hh', n.h.target(table, 8)):
                        quotient = div(numerator, denominator)
                        values.append(sh((quotient << 12) + div((numerator - quotient * denominator) << 12, denominator)))
                    trace.append(['sprite_scale', SPRITES + spoff, 1, table])
                    if case['scale_mode']:
                        for offset, value in zip((0x5C, 0x60), values):
                            old = struct.unpack_from('<i', buffers['sprites'], spoff + offset)[0]
                            n.word(buffers['sprites'], spoff + offset, s32(old * value) >> 12)
                    else:
                        struct.pack_into('<2h', buffers['sprites'], spoff + 0x80, *values)
                    trace.append(['rand', seed])
                    seed = (seed * 0x41C64E6D + 0x3039) & 0xFFFFFFFF
                    n.word(buffers['sprites'], spoff + 0x84, (((seed >> 16) & 0x7FFF) % 360) << 12)
    return dict({name: bytes(data) for name, data in buffers.items()}, trace=trace, rng_seed=seed)


class Machine:
    def __init__(self, patch=None, image=None):
        self.cpu = n.Uc(n.UC_ARCH_MIPS, n.UC_MODE_MIPS32 | n.UC_MODE_LITTLE_ENDIAN)
        self.cpu.mem_map(0, 0x200000)
        self.cpu.mem_write(n.h.LOAD & n.MASK, (n.h.ROM if image is None else image)[0x800:])
        for address, data in (patch or {}).items():
            self.cpu.mem_write(address & n.MASK, data)
        self.entries = {int(row['address'], 16) & n.MASK: row['function'] for row in FUNCTIONS}
        self.counts = Counter()
        self.control_address = None
        self.control_hits = 0
        self.cpu.hook_add(n.UC_HOOK_CODE, self.hook)

    def hook(self, cpu, address, size, unused):
        if (address & n.MASK) == self.control_address:
            self.control_hits += 1
        name = self.entries.get(address & n.MASK)
        if name:
            self.counts[name] += 1
        args = [cpu.reg_read(getattr(n.reg, 'UC_MIPS_REG_A' + str(i))) for i in range(4)]
        if name == 'func_800564F4':
            self.trace.append(['update', args[0], args[1]])
        elif name == 'func_80057384':
            vector = list(struct.unpack('<3i', cpu.mem_read(args[1] & n.MASK, 12)))
            self.trace.append(['position_set', args[0], vector])
        elif name == 'func_800573A8':
            vector = list(struct.unpack('<3i', cpu.mem_read(args[1] & n.MASK, 12)))
            self.trace.append(['position_add', args[0], vector])
        elif name == 'func_8001CEB4':
            self.trace.append(['rotation', *args[:3]])
        elif name == 'rand':
            self.trace.append(['rand', int.from_bytes(cpu.mem_read(n.RNG, 4), 'little')])
        elif name == 'func_80057DF4':
            self.trace.append(['sprite_scale', *args[:3]])

    def run(self, case, reset=True):
        self.trace = []
        buffers, cpu = fixtures(case), self.cpu
        addresses = {'objects': OBJECTS, 'coordinates': COORDS, 'sprites': SPRITES,
                     'player': PLAYER, 'world': WORLD,
                     'listing': n.h.symbols['g_GenerationStructures'] & n.MASK,
                     'poses': POSES, 'child_nodes': CHILD_NODES, 'child_coordinates': CHILD_COORDS,
                     'child_poses': CHILD_POSES, 'size_keys': SIZE_KEYS}
        for name, data in buffers.items():
            if reset or name in ('player', 'world'):
                cpu.mem_write(addresses[name], bytes(data))
        for name, value in (('g_GenerationType', case['type']), ('g_GenerationStructureCount', case['count']),
                            ('D_8008ACAC', WORLD), ('D_8008ACB0', case['baseline_height'])):
            cpu.mem_write(n.h.symbols[name] & n.MASK, struct.pack('<I', n.u32(value)))
        if reset:
            cpu.mem_write(n.RNG, struct.pack('<I', n.u32(case['seed'])))
        cpu.mem_write(n.STACK - 0x400, bytes([0xCC]) * 0x800)
        saved = [n.u32(0xAB000000 + 0x10203 * i) for i in range(len(n.SAVED))]
        for register, value in zip(n.SAVED, saved):
            cpu.reg_write(register, value)
        for register, value in ((n.reg.UC_MIPS_REG_SP, n.STACK), (n.reg.UC_MIPS_REG_GP, 0x8008A808),
                                (n.reg.UC_MIPS_REG_RA, n.END), (n.reg.UC_MIPS_REG_A0, PLAYER)):
            cpu.reg_write(register, value)
        cpu.emu_start(n.h.symbols['dream_generation_update_structure_entities'] & n.MASK, n.END, count=200000)
        if (cpu.reg_read(n.reg.UC_MIPS_REG_PC) != n.END or cpu.reg_read(n.reg.UC_MIPS_REG_SP) != n.STACK
                or [cpu.reg_read(register) for register in n.SAVED] != saved):
            raise ValueError('ABI preservation failed')
        return dict({name: bytes(cpu.mem_read(addresses[name], len(data))) for name, data in buffers.items()},
                    trace=self.trace, rng_seed=int.from_bytes(cpu.mem_read(n.RNG, 4), 'little'))


def base_case(**changes):
    case = dict(type=0, count=1, mode=0, tick=0, enabled=0, variant=0,
                position=(1000, 2000, 3000), height=400, baseline_height=200,
                seed=0, scale_mode=0, scale_value=4096)
    case.update(changes)
    return case


def cases():
    for kind, count, mode, tick in itertools.product(
            (-0x80000000, -1, 0, 1, 2, 3, 0x7FFFFFFF),
            (-1, 0, 1, 2, 17), (0, 1, 2, 3), (-1, 0, 499, 500, 501, 0x7FFFFFFF)):
        yield 'guards_modes_and_ticks', base_case(type=kind, count=count, mode=mode, tick=tick)
    for count, position, seed, scale_mode, scale_value in itertools.product(
            (1, 2, 17), ((1000, 2000, 3000), (0x7FFFFFFF, -0x80000000, 0)),
            (0, 1, 42, 0xFFFFFFFF), (0, 1, -1), (4096, -4096, 0x7FFFFFFF)):
        yield 'sprite_rng_and_word_width', base_case(type=1, count=count, mode=3,
            position=position, seed=seed, scale_mode=scale_mode, scale_value=scale_value)
    for enabled, variant, tick, count in itertools.product(
            (0, 1), (0, 1, 2), (499, 500, 501, -1, 0x7FFFFFFF), (1, 17)):
        yield 'mode_zero_zero_rate_variants', base_case(
            enabled=enabled, variant=variant, tick=tick, count=count)
    for enabled, variant, tick, count in itertools.product(
            range(5), range(8), (-1, 0, 499, 500, 501, 0x7FFFFFFE, 0x7FFFFFFF), (1, 17)):
        yield 'all_mode_zero_variants', base_case(enabled=enabled, variant=variant, tick=tick, count=count)
    for variant, enabled, count, key, euler in itertools.product(
            range(3, 8), range(1, 5), (1, 2), (-32768, -1, 32767),
            ((0, 0, 0), (-32768, -1, 32767))):
        period = abs(div(24500, RATE_WORDS[variant]))
        first = ((501 + period - 1) // period) * period
        for tick in (499, 500, first - 2, first - 1, first, 2 * first - 1):
            yield 'period_and_coordinate_reset', base_case(enabled=enabled, variant=variant,
                tick=tick, count=count, size_key=key, euler=euler)


def histories():
    for enabled, variant in itertools.product(range(1, 5), range(3, 8)):
        period = abs(div(24500, RATE_WORDS[variant]))
        first = ((501 + period - 1) // period) * period
        for kind, start_tick in (('late_activation', 498), ('first_period_reset', first - 3)):
            sequence = [base_case(enabled=enabled, variant=variant, tick=start_tick, count=2,
                size_key=-3, euler=(-32768, -1, 32767),
                position=(1000 + 11 * step, 2000 - 17 * step, 3000 + step), height=400 + 13 * step)
                for step in range(12)]
            yield kind, sequence


def qualify_tables(program):
    for record in TABLES:
        address = int(record['address'], 16)
        if (program.symbols.get(record['symbol']) != address
                or hashlib.sha256(program.target(address, record['bytes'])).hexdigest() != record['sha256']):
            raise ValueError('Canonical generation table changed: ' + record['symbol'])
    if (struct.unpack('<8i', program.target(program.symbols['D_8008780C'], 32)) != RATE_WORDS
            or program.symbols['g_GenerationEffects'] - program.symbols['g_GenerationStructures'] != COUNT * 4):
        raise ValueError('Generation rate fixtures or structure array boundary changed.')
    bindings = [
        ('D_800876FC', 0xEC, 'func_800564F4'),
        ('D_800876FC', 0xB8, 'func_80057384'),
        ('D_800879C4', 0x48, 'func_80057DF4'),
        ('D_800876FC', 0x44, 'func_8001CEB4'),
        ('D_800878D4', 0x44, 'func_8001CEB4'),
        ('D_800878D4', 0xB8, 'func_80057384'),
        ('D_800878D4', 0xBC, 'func_800573A8'),
    ]
    for table, offset, function in bindings:
        slot = struct.unpack('<I', program.target(program.symbols[table] + offset, 4))[0]
        if slot != program.symbols[function]:
            raise ValueError('Generation virtual dispatch no longer binds the expected native method.')
    return [{'table': table, 'offset': offset, 'function': function}
            for table, offset, function in bindings]


def candidate_identity(program, candidate):
    data = Path(candidate).read_bytes()
    function = FUNCTIONS[0]
    start = 0x800 + int(function['address'], 16) - program.LOAD
    end = start + function['bytes']
    if (len(data) != len(program.ROM) or data[:start] != program.ROM[:start]
            or data[end:] != program.ROM[end:]):
        raise ValueError('Candidate must be a complete image differing only inside the selected 136-byte function.')
    return data, {'path': str(Path(candidate).resolve()), 'bytes': len(data),
                  'sha256': hashlib.sha256(data).hexdigest(),
                  'function_sha256': hashlib.sha256(data[start:end]).hexdigest(),
                  'complete_image_equal': data == program.ROM,
                  'changed_bytes': sum(left != right for left, right in zip(data, program.ROM)),
                  'function_bytes': function['bytes'], 'source_promoted': False}


def negative_controls():
    controls = [
        ('wrong_generation_guard', FUNCTIONS[0]['function'], 24, 0x04400014, 0x04410014,
         base_case(type=-1)),
        ('repeated_structure_instead_of_next', FUNCTIONS[0]['function'], 68, 0x26310004, 0x26310000,
         base_case(count=2)),
        ('additive_instead_of_absolute_position', 'func_80057384', 16, 0x34050001, 0x34050000,
         base_case()),
        ('wrong_sprite_scale_destination', 'func_80057DF4', 308, 0xA5040080, 0xA5040082,
         base_case(mode=3, seed=42)),
        ('wrong_rng_increment', 'rand', 20, 0x24423039, 0x2442303A,
         base_case(mode=3, seed=42)),
        ('wrong_late_activation_tick', 'func_800569A8', 88, 0x2C4201F5, 0x2C4201F6,
         base_case(enabled=1, variant=3, tick=500)),
        ('wrong_second_child_offset', 'func_800569A8', 220, 0x26310003, 0x26310002,
         base_case(enabled=1, variant=3, tick=500)),
        ('wrong_reposition_period', 'func_800569A8', 288, 0x34025FB4, 0x34025FB5,
         base_case(enabled=1, variant=3, tick=24499)),
        ('wrong_rotation_axis_destination', 'func_8001CEB4', 280, 0xA4820000, 0xA4820002,
         base_case(enabled=1, variant=3, tick=500)),
    ]
    detected = []
    for kind, function, offset, expected_word, changed_word, case in controls:
        record = next(row for row in FUNCTIONS if row['function'] == function)
        address = int(record['address'], 16)
        original = bytearray(n.h.target(address, record['bytes']))
        if struct.unpack_from('<I', original, offset)[0] != expected_word:
            raise ValueError('Control does not identify its pinned original instruction: ' + kind)
        struct.pack_into('<I', original, offset, changed_word)
        machine = Machine(patch={address: bytes(original)})
        machine.control_address = (address + offset) & n.MASK
        if machine.run(case) == model(case) or machine.control_hits == 0:
            raise ValueError('Control was not detected: ' + kind)
        detected.append({'kind': kind, 'function': function, 'function_offset': offset,
                         'expected_word': f'0x{expected_word:08X}', 'changed_word': f'0x{changed_word:08X}',
                         'changed_instruction_executions': machine.control_hits,
                         'fixture': case, 'scope': 'Private Unicorn memory only.'})
    return detected


def new_destination(value):
    path = Path(value).resolve()
    if (path.suffix != '.json' or not path.is_relative_to((n.ROOT / '.decomp-lab').resolve())
            or path.exists()):
        raise ValueError('Choose a new private JSON report inside .decomp-lab.')
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def verify(destination, candidate=None):
    destination = new_destination(destination)
    dependencies = n.evidence_dependencies('tools/verify_generation_structures.py',
        'tools/verify_scripted_ai.py', 'src/dream/dream_generation.c',
        'src/dream/dream_generation_post.c', 'src/dream/generation_structure.c',
        'src/dream/generation_structure.h', 'src/dream/generation_sprite.c',
        'src/dream/generation_sprite.h', 'src/scene/scene_node.c', 'src/scene/scene_node.h',
        'asm/data/77EFC.data.s')
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    n.initialize_backend(n.load_program(FUNCTIONS))
    bindings = qualify_tables(n.h)
    backend = backend_identity()
    candidate_data, candidate_record = (None, None) if candidate is None else candidate_identity(n.h, candidate)
    profiles = [('original', Machine())]
    if candidate_data is not None:
        profiles.append(('unaccepted_complete_c_candidate', Machine(image=candidate_data)))
    started = time.monotonic()
    observations = {}
    for profile, machine in profiles:
        groups = Counter()
        for index, (group, case) in enumerate(cases()):
            actual, expected = machine.run(case), model(case)
            if actual != expected:
                failure = destination.with_name(destination.stem + '-failure-' + str(time.time_ns()) + '.json')
                with failure.open('x') as handle:
                    json.dump({'profile': profile, 'index': index, 'case': case,
                               'actual': repr(actual), 'expected': repr(expected)}, handle, indent=2)
                raise ValueError('Generation structure disagreement; private evidence: ' + str(failure))
            groups[group] += 1
        history_groups, history_count = Counter(), 0
        for kind, sequence in histories():
            previous = None
            history_count += 1
            for step, case in enumerate(sequence):
                actual, expected = machine.run(case, reset=step == 0), model(case, previous)
                if actual != expected:
                    failure = destination.with_name(destination.stem + '-history-failure-' + str(time.time_ns()) + '.json')
                    with failure.open('x') as handle:
                        json.dump({'profile': profile, 'history': kind, 'step': step, 'case': case,
                                   'actual': repr(actual), 'expected': repr(expected)}, handle, indent=2)
                    raise ValueError('Generation history disagreement; private evidence: ' + str(failure))
                previous = expected
                history_groups[kind] += 1
        observations[profile] = {'native_cases': sum(groups.values()), 'case_groups': dict(groups),
                                 'consecutive_update_histories': history_count,
                                 'history_frames': sum(history_groups.values()), 'history_frame_groups': dict(history_groups),
                                 'actual_native_entry_counts': dict(sorted(machine.counts.items()))}
        print(profile, sum(groups.values()), 'passed', flush=True)
    controls = negative_controls()
    if (backend_identity() != backend or (n.ROOT / n.configure.ROM).read_bytes() != n.h.ROM
            or (n.ROOT / n.configure.EXE).read_bytes() != n.h.ROM
            or n.check_build_current(n.ROOT) is not True
            or any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path, digest in before.items())
            or (candidate is not None and Path(candidate).read_bytes() != candidate_data)):
        raise ValueError('Generation source, backend or preserved executable evidence changed.')
    report = {
        'status': 'passed_bounded_original_generation_structure_composition',
        'canonical_executable_sha1': hashlib.sha1(n.h.ROM).hexdigest(),
        'canonical_original_and_build_equal': True, 'backend_identity': backend,
        'profiles': observations, 'native_functions': FUNCTIONS, 'native_tables': TABLES,
        'virtual_method_bindings': bindings, 'negative_controls_detected': controls,
        'candidate': candidate_record, 'dependency_contracts': [],
        'original_behavior_modified': False, 'model_api_calls': 0,
        'source_functions_promoted': 0, 'whole_feature_groups_accepted': 0,
        'producer_dependencies': [{'path': path.resolve().relative_to(n.ROOT).as_posix(), 'sha256': digest}
                                  for path, digest in before.items()],
        'scope': 'Fifteen original routines execute in manually assembled valid structure/coordinate/sprite/child graphs. '
                 'Full graph buffers, player/world/list preservation, ordered updates/position sets/scales/RNG, '
                 'native 32-bit arithmetic and ABI. All four generation modes, all eight mode-0 rate variants, '
                 'four active child layouts, late activation and periodic position reset with consecutive-update histories. '
                 'Excludes construction, parameter-table selection provenance, dynamic list/count mutations during callbacks, '
                 'null player vectors with live structures, rendering/audio, natural encounters/lifetimes and PS1 CPU timing.',
        'elapsed_seconds': round(time.monotonic() - started, 3),
    }
    with destination.open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='New private JSON report inside .decomp-lab.')
    parser.add_argument('--candidate', type=Path, help='Optional unaccepted complete candidate image.')
    args = parser.parse_args(argv)
    try:
        import os
        os.chdir(n.ROOT)
        report = verify(args.output, args.candidate)
        print(json.dumps({'status': report['status'], 'profiles': report['profiles'],
                          'controls': len(report['negative_controls_detected'])}))
        return 0
    except (OSError, ValueError, AssertionError) as error:
        print('error: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
