"""Check the original renderer's grid-window decisions with local native fixtures.

The 660-byte function executes in Unicorn. Position lookup, RotMatrix,
ApplyMatrixLV and the downstream grid builder have explicit contracts.
This checks the surrounding scalar behavior, not GTE or framebuffer parity.
"""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import verify_native_ai as native

FUNCTIONS = [{'function': 'func_8004C6A8', 'address': '0x8004C6A8', 'bytes': 660,
              'sha256': 'a50855f634d69c3ce7a04cc5db9fafd9a2d88edfeab167f9e351c7791bdb46d9'}]
BASES = {'context': 0x110000, 'owner': 0x111000, 'inner': 0x112000,
         'angles': 0x113000, 'vtable': 0x114000}
LENGTHS = {'context': 0x300, 'owner': 0x80, 'inner': 0x100,
           'angles': 0x80, 'vtable': 0x160}
LOOKUP = 0x180000
TEMPLATE = 0x8E98C
MATRIX = native.STACK - 0x98 + 0x40
VECTOR = MATRIX + 0x14
INFO = native.STACK - 0x98 + 0x10


def signed(value, bits=32):
    value &= (1 << bits) - 1
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def fixture(case):
    seed, segment = case.get('seed', 0), case.get('segment', 0)
    buffers = {name: bytearray((index * 37 + seed * 91 + base) & 255
                               for index in range(LENGTHS[name]))
               for name, base in BASES.items()}
    pointers = {name: (base + 0x20) | segment for name, base in BASES.items()}
    native.word(buffers['context'], 0x20, pointers['vtable'])
    native.word(buffers['context'], 0x20 + 0x6C, pointers['owner'])
    native.word(buffers['context'], 0x20 + 0x74, case['distance'])
    struct.pack_into('<h', buffers['context'], 0x20 + 0x78, case['radius'])
    native.word(buffers['owner'], 0x20 + 0x14, pointers['inner'])
    native.word(buffers['inner'], 0x20 + 0x44, pointers['angles'])
    struct.pack_into('<h', buffers['angles'], 0x20 + 0x12, signed(case['angle'], 16))
    native.word(buffers['vtable'], 0x20 + 0x10C, LOOKUP | segment)
    template = bytes((index * 13 + seed * 31 + 7) & 255 for index in range(32))
    info = bytearray((index * 19 + seed * 11 + 5) & 255 for index in range(44))
    info[2], info[3] = case['x'] & 255, case['z'] & 255
    rotation = bytes((index * 17 + seed * 23 + 3) & 255 for index in range(18))
    return buffers, pointers, template, bytes(info), rotation


def expected(case):
    """Independent angular intervals and native integer/store rules."""
    buffers, pointers, template, info, rotation = fixture(case)
    context, angles = buffers['context'], buffers['angles']
    radius = case.get('callback_radius', case['radius'])
    distance = case.get('callback_distance', case['distance'])
    angle = signed(case.get('callback_angle', case['angle']), 16)
    native.word(context, 0x20 + 0x74, distance)
    struct.pack_into('<h', context, 0x20 + 0x78, radius)
    struct.pack_into('<h', angles, 0x20 + 0x12, angle)
    normalized = (angle + 0x1000 if angle < 0 else angle) & 0xFFFF
    transverse = 0x200 <= normalized < 0x600 or 0xA00 <= normalized < 0xE00
    x, z = signed(case['x'], 8), signed(case['z'], 8)
    px, pz = signed(case['projected_x']), signed(case['projected_z'])
    width, height = signed(case['width']), signed(case['height'])
    half = radius & 0xFFFF
    if transverse:
        rows, columns = height, width
        origin_x = x if px > 0 else x - width + 1
        origin_z = z - half - (1 if pz > 0 else -1)
        correction = pz >> 11
    else:
        rows, columns = width, height
        origin_x = x - half - (1 if px > 0 else -1)
        origin_z = z if pz > 0 else z - height + 1
        correction = px >> 11
    if correction >= radius:
        correction = radius - 1
    if correction <= -radius:
        correction = -radius + 1
    if transverse:
        origin_z += correction
    else:
        origin_x += correction
    struct.pack_into('<hh', context, 0x20 + 0x7C, signed(origin_x, 16), signed(origin_z, 16))
    native.word(context, 0x20 + 0x80, rows)
    native.word(context, 0x20 + 0x84, columns)
    matrix = bytearray(template)
    struct.pack_into('<iii', matrix, 0x14, 0, 0, signed(distance))
    rotation_input = bytes(angles[0x30:0x36])
    trace = [('lookup', pointers['context'], INFO, 0),
             ('rotate', pointers['angles'] + 0x10, MATRIX, rotation_input, bytes(matrix))]
    matrix[:18] = rotation
    trace.append(('apply', MATRIX, VECTOR, VECTOR, bytes(matrix)))
    struct.pack_into('<iii', matrix, 0x14, px, signed(case['projected_y']), pz)
    trace.append(('build', pointers['context'], bytes(context), bytes(matrix)))
    return ({name: bytes(data) for name, data in buffers.items()}, trace,
            template, info, bytes(matrix), 'transverse' if transverse else 'longitudinal')


class Machine(native.Machine):
    def __init__(self, code=None):
        self.entry_counts = Counter()
        super().__init__(code=code, start=0x4C6A8, native_functions=FUNCTIONS)
        self.stubs = {LOOKUP: 'lookup', native.h.symbols['RotMatrix'] & native.MASK: 'rotate',
                      native.h.symbols['ApplyMatrixLV'] & native.MASK: 'apply',
                      native.h.symbols['func_8004C93C'] & native.MASK: 'build'}
        if len(self.stubs) != 4 or native.h.symbols['D_8008E98C'] & native.MASK != TEMPLATE:
            raise ValueError('Grid dependency addresses changed.')

    def read(self, address, size):
        return bytes(self.cpu.mem_read(address & native.MASK, size))

    def hook(self, cpu, address, size, unused):
        address &= native.MASK
        if address == self.start:
            self.entry_counts['func_8004C6A8'] += 1
        name = self.stubs.get(address)
        if name is None:
            if not self.start <= address < self.start + 660:
                raise ValueError('Unexpected execution outside the reviewed grid function.')
            return
        args = [cpu.reg_read(getattr(native.reg, 'UC_MIPS_REG_A' + str(index))) for index in range(3)]
        result = self.case.get('lookup_result', 1) if name == 'lookup' else 0
        if name == 'lookup':
            self.trace.append((name, *args))
            if (args[0] != self.pointers['context'] or args[1] != INFO or args[2] != 0):
                raise ValueError('Position lookup argument contract failed.')
            cpu.mem_write(INFO, self.info)
            cpu.mem_write((self.pointers['context'] & native.MASK) + 0x74,
                         struct.pack('<I', native.u32(self.case.get('callback_distance', self.case['distance']))))
            cpu.mem_write((self.pointers['context'] & native.MASK) + 0x78,
                         struct.pack('<h', self.case.get('callback_radius', self.case['radius'])))
            cpu.mem_write((self.pointers['angles'] & native.MASK) + 0x12,
                         struct.pack('<h', signed(self.case.get('callback_angle', self.case['angle']), 16)))
        elif name == 'rotate':
            self.trace.append((name, args[0], args[1], self.read(args[0], 6), self.read(args[1], 32)))
            if args[:2] != [self.pointers['angles'] + 0x10, MATRIX]:
                raise ValueError('Rotation argument contract failed.')
            cpu.mem_write(MATRIX, self.rotation)
        elif name == 'apply':
            self.trace.append((name, *args, self.read(args[0], 32)))
            if args != [MATRIX, VECTOR, VECTOR]:
                raise ValueError('In-place vector application contract failed.')
            cpu.mem_write(VECTOR, struct.pack('<iii', signed(self.case['projected_x']),
                                            signed(self.case['projected_y']), signed(self.case['projected_z'])))
        else:
            self.trace.append((name, args[0], self.read(BASES['context'], LENGTHS['context']), self.read(MATRIX, 32)))
            if args[0] != self.pointers['context']:
                raise ValueError('Grid builder argument contract failed.')
        target = cpu.reg_read(native.reg.UC_MIPS_REG_RA)
        for index, register in enumerate(native.VOLATILE):
            cpu.reg_write(register, native.u32(0xBC000000 + index * 0x10203))
        cpu.reg_write(native.reg.UC_MIPS_REG_V0, native.u32(result))
        cpu.reg_write(native.reg.UC_MIPS_REG_PC, target)

    def run(self, case):
        self.case, self.trace = case, []
        buffers, self.pointers, template, self.info, self.rotation = fixture(case)
        cpu = self.cpu
        for name, data in buffers.items():
            cpu.mem_write(BASES[name], bytes(data))
        cpu.mem_write(TEMPLATE, template)
        stack = bytes([0xC9]) * 0x300
        cpu.mem_write(native.STACK - 0x200, stack)
        saved = [native.u32(0xAB000000 + index * 0x10305) for index in range(len(native.SAVED))]
        for register, value in zip(native.SAVED, saved):
            cpu.reg_write(register, value)
        for register, value in ((native.reg.UC_MIPS_REG_SP, native.STACK),
                (native.reg.UC_MIPS_REG_GP, 0x8008A808), (native.reg.UC_MIPS_REG_RA, native.END),
                (native.reg.UC_MIPS_REG_A0, self.pointers['context']),
                (native.reg.UC_MIPS_REG_A1, native.u32(case['width'])),
                (native.reg.UC_MIPS_REG_A2, native.u32(case['height'])),
                (native.reg.UC_MIPS_REG_A3, 0xBEADC0DE)):
            cpu.reg_write(register, value)
        cpu.emu_start(self.start, native.END, count=2000)
        if (cpu.reg_read(native.reg.UC_MIPS_REG_PC) != native.END or
                cpu.reg_read(native.reg.UC_MIPS_REG_SP) != native.STACK or
                cpu.reg_read(native.reg.UC_MIPS_REG_GP) != 0x8008A808 or
                cpu.reg_read(native.reg.UC_MIPS_REG_RA) != native.END or
                [cpu.reg_read(register) for register in native.SAVED] != saved or
                self.read(native.STACK - 0x200, 0x168) != stack[:0x168] or
                self.read(native.STACK, 0x100) != stack[0x200:]):
            raise ValueError('Grid function violated stack guards or its ABI.')
        return ({name: self.read(BASES[name], LENGTHS[name]) for name in BASES}, self.trace,
                self.read(TEMPLATE, 32), self.read(INFO, 44), self.read(MATRIX, 32))


def cases():
    base = dict(angle=0x200, x=-32, z=40, radius=4, width=8, height=6,
                distance=12345, projected_x=12289, projected_y=-3456, projected_z=-12287)
    for angle in range(65536):
        yield 'complete_angle_word_sweep', dict(base, angle=angle)
    angles = (0, 0x1FF, 0x200, 0x5FF, 0x600, 0x9FF, 0xA00, 0xDFF,
              0xE00, 0xFFFF, 0x8000, 0xF7FF, 0xF800, 0xF9FF, 0xFA00, 0xFDFF)
    for angle, radius in itertools.product(angles, (-32768, -1, 0, 1, 2, 4, 127, 32767)):
        values = (radius * 2048 - 1, radius * 2048, radius * 2048 + 1,
                  -radius * 2048 - 1, -radius * 2048, -radius * 2048 + 1, 0)
        for value in values:
            yield 'projection_clamp_boundaries', dict(base, angle=angle, radius=radius,
                                                      projected_x=value, projected_z=-value)
    sizes = ((8, 6), (0, 0), (-3, 4), (1, -2), (1, 1),
             (2147483647, -2147483648), (-2147483648, 2147483647))
    for x, z, angle, dimensions, direction in itertools.product(
            (-128, -127, -1, 0, 1, 126, 127), (-128, -127, -1, 0, 1, 126, 127),
            (0, 0x200, 0x600, 0xA00, 0xE00, 0xFFFF, 0x8000, 0xF800), sizes, (-1, 0, 1)):
        yield 'coordinate_and_dimension_edges', dict(base, x=x, z=z, angle=angle,
            width=dimensions[0], height=dimensions[1], projected_x=direction * 2147483647,
            projected_z=-direction * 2147483647)
    for angle, replacement, radius, result, seed in itertools.product(
            (0, 0x200), (0x600, 0xFFFF), (-1, 0, 7), (0, 1, -1), (0, 1)):
        yield 'callback_mutation_order', dict(base, angle=angle, callback_angle=replacement,
            callback_distance=-7654321, callback_radius=radius, lookup_result=result, seed=seed)
    for segment, angle, seed in itertools.product((0, 0x80000000, 0xA0000000), angles, (0, 1)):
        yield 'segment_aliases_and_template_contents', dict(base, angle=angle, segment=segment, seed=seed)


def verify(destination):
    dependencies = native.evidence_dependencies('tools/verify_render_grid.py',
        'src/scene/render_context.c', 'src/scene/render_context.h', 'config/symbols.txt',
        'asm/nonmatchings/scene/render_context/func_8004C6A8.s')
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    native.initialize_backend(native.load_program(FUNCTIONS))
    machine, groups, axes = Machine(), Counter(), Counter()
    last_group = None
    for group, case in cases():
        if last_group is not None and group != last_group:
            print(last_group, groups[last_group], 'passed', flush=True)
        last_group = group
        model = expected(case)
        actual = machine.run(case)
        if actual != model[:5]:
            failure = destination.with_name(destination.stem + '-failure-' + str(time.time_ns()) + '.json')
            with failure.open('x', encoding='utf-8') as stream:
                json.dump({'group': group, 'case': case, 'native': repr(actual), 'model': repr(model[:5])}, stream, indent=2)
            raise ValueError('Original grid/model disagreement; see private failure report ' + failure.name)
        groups[group] += 1
        axes[model[5]] += 1
    print(last_group, groups[last_group], 'passed', flush=True)
    original = native.h.target(0x8004C6A8, 660)
    base = dict(angle=0x200, x=-32, z=40, radius=4, width=8, height=6,
                distance=12345, projected_x=-4096, projected_y=-3456, projected_z=-4096)
    controls = []
    for name, address, old, new, case in (
            ('first_angle_interval_width', 0x8004C79C, 0x2C620400, 0x2C6203FF, dict(base, angle=0x5FF)),
            ('unsigned_grid_z', 0x8004C704, 0x83B60013, 0x93B60013, dict(base, z=-1)),
            ('wrong_row_extent', 0x8004C83C, 0xAE370080, 0xAE3E0080, dict(base, angle=0x600)),
            ('negative_origin_boundary', 0x8004C7D8, 0x24420001, 0x24420000, base),
            ('unsigned_radius_read', 0x8004C8A0, 0x86230078, 0x96230078, dict(base, radius=-1)),
            ('logical_projection_shift', 0x8004C8A4, 0x00139AC3, 0x00139AC2, base),
            ('unsigned_upper_clamp', 0x8004C8A8, 0x0263102A, 0x0263102B, base),
            ('wrong_correction_axis', 0x8004C898, 0x34070001, 0x34070000, dict(base, angle=0x600))):
        code = bytearray(original)
        offset = address - 0x8004C6A8
        if struct.unpack_from('<I', code, offset)[0] != old:
            raise ValueError('Grid control instruction evidence changed: ' + name)
        struct.pack_into('<I', code, offset, new)
        try:
            detected = Machine(bytes(code)).run(case) != expected(case)[:5]
        except ValueError:
            detected = True
        if not detected:
            raise ValueError('Grid negative control was not detected: ' + name)
        controls.append({'name': name, 'address': hex(address), 'fixture': case,
                         'detected': True, 'scope': 'Private Unicorn memory only.'})
    if ((ROOT / native.configure.ROM).read_bytes() != native.h.ROM or
            (ROOT / native.configure.EXE).read_bytes() != native.h.ROM or
            native.check_build_current(ROOT) is not True or
            any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path, digest in before.items())):
        raise ValueError('Source or canonical build changed during grid verification.')
    report = {'status': 'passed_bounded_original_render_grid',
        'canonical_executable_sha1': hashlib.sha1(native.h.ROM).hexdigest(),
        'original_and_current_build_equal': True, 'original_behavior_modified': False,
        'model_api_calls': 0, 'backend': 'Unicorn ' + native.unicorn.__version__,
        'native_cases': sum(groups.values()), 'case_groups': dict(groups), 'decision_axes': dict(axes),
        'native_functions': FUNCTIONS, 'executed_native_entry_counts': dict(machine.entry_counts),
        'explicit_stubs': 4, 'stub_contracts': ['position lookup', 'RotMatrix', 'ApplyMatrixLV', 'grid builder'],
        'negative_controls_detected': controls, 'source_promotions': 0, 'original_feature_groups_accepted': 0,
        'producer_dependencies': [{'path': path.resolve().relative_to(ROOT).as_posix(), 'sha256': digest}
                                  for path, digest in before.items()],
        'scope': 'All 65536 input angle words plus scalar clamp, signed coordinate, dimension, '
                 'callback mutation, segment alias and template fixtures. Compare whole guarded '
                 'objects, exact call order/arguments, rotation inputs, intermediate matrices, final '
                 'grid fields, matrix/info buffers, stack guards, GP, RA and saved registers. '
                 'The four explicit contracts do not execute GTE transforms, position resolution '
                 'or the downstream grid builder. The original function remains assembly; '
                 'full rendering, natural scene lifetime and PS1 timing remain unaccepted.'}
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'report': str(destination), 'native_cases': report['native_cases'],
                      'negative_controls': len(controls), 'explicit_stubs': 4, 'passed': True}), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New JSON report inside .decomp-lab.')
    args = parser.parse_args(argv)
    try:
        destination = args.output if args.output.is_absolute() else ROOT / args.output
        destination = destination.resolve()
        if not destination.is_relative_to((ROOT / '.decomp-lab').resolve()) or destination.exists():
            raise ValueError('Choose a new report path inside the private .decomp-lab directory.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        verify(destination)
        return 0
    except (OSError, ValueError) as error:
        print('[!] ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
