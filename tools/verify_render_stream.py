"""Check original grid generation through native row splitting and slot lookup.

Four original MIPS functions execute. Position lookup, RotMatrix and
ApplyMatrixLV retain explicit contracts; GTE/framebuffer parity is separate.
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
from tools import verify_render_grid as grid
from tools import verify_native_ai as native

FUNCTIONS = grid.FUNCTIONS + [
    {'function': 'func_8004C93C', 'address': '0x8004C93C', 'bytes': 436,
     'sha256': 'b2ae8adf614d7d9cbbc54f0c421116d413b0d1ec83b589ef627f68bf496807e9'},
    {'function': 'func_8004CAF0', 'address': '0x8004CAF0', 'bytes': 388,
     'sha256': 'db0aef3b0fd26e35a931cc0a7becce405b0e7cf3269a275448f8f39b4bdc5497'},
    {'function': 'func_8004C588', 'address': '0x8004C588', 'bytes': 72,
     'sha256': 'e180bd8b0901df8378e5dd68e131ebae4d12ce6693f3ff82923f4a4b9d8fbdac'},
]
BASES = {**grid.BASES, **{'chunk' + str(index): 0x115000 + index * 0x1000 for index in range(7)}}
LENGTHS = {**grid.LENGTHS, **{'chunk' + str(index): 0x80 for index in range(7)}}
SLOT_FUNCTION = 0x8004C588
VTABLE_ADDRESS = 0x800866E8
SLOT_OFFSET = 0x120


def canonical_slot(program):
    """Reject a synthetic slot binding that disagrees with the original table."""
    slot_bytes = program.target(VTABLE_ADDRESS + SLOT_OFFSET, 4)
    if (program.symbols.get('D_800866E8') != VTABLE_ADDRESS or
            int.from_bytes(slot_bytes, 'little') != SLOT_FUNCTION):
        raise ValueError('Original render-context slot 0x120 no longer targets func_8004C588.')
    return {'table_symbol': 'D_800866E8', 'table_address': hex(VTABLE_ADDRESS),
            'slot_offset': hex(SLOT_OFFSET), 'slot_address': hex(VTABLE_ADDRESS + SLOT_OFFSET),
            'target_function': 'func_8004C588', 'target_address': hex(SLOT_FUNCTION),
            'slot_sha256': hashlib.sha256(slot_bytes).hexdigest(), 'verified': True}


def bind_slots(buffers, case):
    segment, seed = case.get('segment', 0), case.get('seed', 0)
    labels = case.get('labels', tuple(range(7)))
    if len(labels) != 7:
        raise ValueError('Exactly seven streaming object labels are required.')
    for index, label in enumerate(labels):
        name = 'chunk' + str(index)
        data = bytearray((offset * 37 + seed * 91 + BASES[name]) & 255 for offset in range(0x80))
        struct.pack_into('<h', data, 0x20 + 0x32, label)
        buffers[name] = data
        native.word(buffers['context'], 0x20 + 0xEC + index * 0x1C + 4,
                    (BASES[name] + 0x20) | segment)
    native.word(buffers['vtable'], 0x20 + 0x120, SLOT_FUNCTION | segment)


def fixture(case):
    buffers, pointers, template, info, rotation = grid.fixture(case)
    bind_slots(buffers, case)
    return buffers, pointers, template, info, rotation


def expected(case):
    """Build staggered tile intersections in native emission order."""
    buffers, trace, template, info, matrix, axis = grid.expected(case)
    buffers = {name: bytearray(data) for name, data in buffers.items()}
    bind_slots(buffers, case)
    context = buffers['context']
    pointer = (BASES['context'] + 0x20) | case.get('segment', 0)
    trace = list(trace[:3]) + [('build', pointer, bytes(context), matrix)]
    x, y = struct.unpack_from('<hh', context, 0x20 + 0x7C)
    width, height = struct.unpack_from('<ii', context, 0x20 + 0x80)
    # Map the origin to the upper tile of the staggered seven-slot layout.
    if y < 0:
        y += 20
        if x < 0:
            x += 10
            mode = 0
        elif x < 10:
            x += 10
            mode = 0
        else:
            x -= 10
            mode = 1
    elif x < 0:
        x += 20
        mode = 2
    else:
        mode = 3
    labels = case.get('labels', tuple(range(7)))
    def selected(mode):
        trace.append(('selector', pointer, native.u32(mode)))
        return next((index for index, label in enumerate(labels) if label == mode), 0)
    upper_index = selected(mode)
    upper_width = min(width, 20 - x)
    upper_height = min(height, 20 - y)
    rectangles = [(upper_index, max(x, 0), y, upper_width, upper_height)]
    trace.append(('row', pointer, pointer + 0x8C, 0, native.u32(mode),
                  native.u32(x), native.u32(y), native.u32(width), native.u32(height)))
    if height > 20 - y:
        lower_mode, lower_x = (mode + 2, x + 10) if x < 10 else (mode + 3, x - 10)
        lower_index = selected(lower_mode)
        lower_height = height - (20 - y)
        rectangles.append((lower_index, lower_x, 0, min(width, 20 - lower_x), lower_height))
        if width > 20 - lower_x:
            rectangles.append((selected(lower_mode + 1), 0, 0,
                               width - (20 - lower_x), lower_height))
    if width > 20 - x:
        rectangles.append((selected(mode + 1), 0, y, width - (20 - x), upper_height))
    native.word(context, 0x20 + 0x88, len(rectangles))
    for index, rectangle in enumerate(rectangles):
        slot, cell_x, cell_y, extent_x, extent_y = rectangle
        struct.pack_into('<Ihhhh', context, 0x20 + 0x8C + index * 12, native.u32(slot),
                         grid.signed(cell_x, 16), grid.signed(cell_y, 16),
                         grid.signed(extent_x, 16), grid.signed(extent_y, 16))
    return ({name: bytes(data) for name, data in buffers.items()}, trace, template, info,
            matrix, axis, len(rectangles))


class Machine(grid.Machine):
    def __init__(self, code=None):
        super().__init__(code=code)
        del self.stubs[native.h.symbols['func_8004C93C'] & native.MASK]
        self.entries = {int(row['address'], 16) & native.MASK: row['function'] for row in FUNCTIONS}
        self.ranges = [(address, address + row['bytes'])
                       for address, row in zip(self.entries, FUNCTIONS)]

    def hook(self, cpu, address, size, unused):
        address &= native.MASK
        name = self.entries.get(address)
        if name:
            self.entry_counts[name] += 1
            args = [cpu.reg_read(getattr(native.reg, 'UC_MIPS_REG_A' + str(index))) for index in range(4)]
            if name == 'func_8004C93C':
                self.trace.append(('build', args[0], self.read(BASES['context'], LENGTHS['context']),
                                   self.read(grid.MATRIX, 32)))
            elif name == 'func_8004CAF0':
                stack = cpu.reg_read(native.reg.UC_MIPS_REG_SP) & native.MASK
                args += list(struct.unpack('<IIII', self.read(stack + 16, 16)))
                self.trace.append(('row', *args))
            elif name == 'func_8004C588':
                self.trace.append(('selector', *args[:2]))
        if address in self.stubs:
            # Legacy contract logic handles the same three inputs and ABI.
            return super().hook(cpu, address, size, unused)
        if not any(start <= address < end for start, end in self.ranges):
            raise ValueError('Unexpected execution outside reviewed renderer/stream functions.')

    def run(self, case):
        self.case, self.trace = case, []
        buffers, self.pointers, template, self.info, self.rotation = fixture(case)
        cpu = self.cpu
        for name, data in buffers.items():
            cpu.mem_write(BASES[name], bytes(data))
        cpu.mem_write(grid.TEMPLATE, template)
        stack = bytes([0xC9]) * 0x400
        cpu.mem_write(native.STACK - 0x300, stack)
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
        cpu.emu_start(self.start, native.END, count=5000)
        if (cpu.reg_read(native.reg.UC_MIPS_REG_PC) != native.END or
                cpu.reg_read(native.reg.UC_MIPS_REG_SP) != native.STACK or
                cpu.reg_read(native.reg.UC_MIPS_REG_GP) != 0x8008A808 or
                cpu.reg_read(native.reg.UC_MIPS_REG_RA) != native.END or
                [cpu.reg_read(register) for register in native.SAVED] != saved or
                self.read(native.STACK - 0x300, 0x100) != stack[:0x100] or
                self.read(native.STACK, 0x100) != stack[0x300:]):
            raise ValueError('Native streaming composition violated guarded stack or ABI.')
        return ({name: self.read(BASES[name], LENGTHS[name]) for name in BASES}, self.trace,
                self.read(grid.TEMPLATE, 32), self.read(grid.INFO, 44), self.read(grid.MATRIX, 32))


def cases():
    base = dict(angle=0x200, x=0, z=0, radius=4, width=8, height=6,
                distance=12345, projected_x=12289, projected_y=-3456, projected_z=-12289)
    for x, z, radius, height, angle, direction in itertools.product(
            range(20), range(20), (1, 4, 9), (1, 6, 18),
            (0, 0x200, 0x600, 0xA00), (-1, 0, 1)):
        yield 'complete_cell_grid', dict(base, x=x, z=z, radius=radius, width=radius * 2,
            height=height, angle=angle, projected_x=direction * 12289, projected_z=-direction * 12289)
    corners = ((0, 0), (0, 19), (19, 0), (19, 19))
    angles = (0, 0x1FF, 0x200, 0x5FF, 0x600, 0x9FF, 0xA00, 0xDFF,
              0xE00, 0xFFFF, 0x8000, 0xF7FF, 0xF800, 0xF9FF, 0xFA00, 0xFDFF)
    for point, angle, direction in itertools.product(corners, angles, (-1, 0, 1)):
        yield 'angle_edges_and_corner_wraps', dict(base, x=point[0], z=point[1], angle=angle,
            radius=9, width=18, height=18, projected_x=direction * 12289, projected_z=-direction * 12289)
    layouts = (tuple(range(7)), tuple(reversed(range(7))), (1, 1, 2, 3, 4, 5, 6),
               (0, 1, 2, 3, 4, 5, 5), (-1,) * 7, (6, 5, 6, 5, 0, -1, 1),
               (7, -32768, 32767, 0, 4, 3, 2))
    for labels, point, angle, direction, segment, seed in itertools.product(layouts, corners,
            (0, 0x200, 0x600, 0xA00), (-1, 0, 1), (0, 0x80000000, 0xA0000000), (0, 1)):
        yield 'slot_order_missing_duplicate_and_segment', dict(base, labels=labels,
            x=point[0], z=point[1], angle=angle, radius=9, width=18, height=18,
            projected_x=direction * 12289, projected_z=-direction * 12289, segment=segment, seed=seed)


def verify(destination):
    dependencies = native.evidence_dependencies('tools/verify_render_stream.py',
        'tools/verify_render_grid.py', 'src/scene/render_context.c',
        'src/scene/render_context.h', 'config/symbols.txt')
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    program = native.load_program(FUNCTIONS)
    slot_link = canonical_slot(program)
    native.initialize_backend(program)
    machine, groups, rectangle_counts, axes = Machine(), Counter(), Counter(), Counter()
    last = None
    for group, case in cases():
        if last is not None and last != group:
            print(last, groups[last], 'passed', flush=True)
        last = group
        model, actual = expected(case), machine.run(case)
        if actual != model[:5]:
            failure = destination.with_name(destination.stem + '-failure-' + str(time.time_ns()) + '.json')
            with failure.open('x', encoding='utf-8') as stream:
                json.dump({'group': group, 'case': case, 'native': repr(actual), 'model': repr(model[:5])}, stream, indent=2)
            raise ValueError('Native streamed grid/model disagreement; see ' + failure.name)
        groups[group] += 1
        axes[model[5]] += 1
        rectangle_counts[model[6]] += 1
    print(last, groups[last], 'passed', flush=True)
    controls = []
    # Each witness uses the actual builder, row helper and object-slot scanner.
    witnesses = list(case for _, case in cases())
    for name, address, old, new in (
            ('row_height_wrap_threshold', 0x8004CB34, 0x28620015, 0x28620014),
            ('row_width_wrap_threshold', 0x8004CBD0, 0x2A620015, 0x2A620014),
            ('slot_label_field', 0x8004C5A0, 0x84420032, 0x84420030),
            ('row_height_written_to_width', 0x8004CB48, 0xA602000A, 0xA6020008)):
        original = native.h.target(address, 4)
        if int.from_bytes(original, 'little') != old:
            raise ValueError('Streaming control instruction changed: ' + name)
        wrong = Machine()
        wrong.cpu.mem_write(address & native.MASK, struct.pack('<I', new))
        for case in witnesses:
            try:
                detected = wrong.run(case) != expected(case)[:5]
            except ValueError:
                detected = True
            if detected:
                controls.append({'name': name, 'address': hex(address), 'fixture': case,
                                 'detected': True, 'scope': 'Private Unicorn memory only.'})
                break
        else:
            raise ValueError('Streaming negative control was not detected: ' + name)
    if ((ROOT / native.configure.ROM).read_bytes() != native.h.ROM or
            (ROOT / native.configure.EXE).read_bytes() != native.h.ROM or
            native.check_build_current(ROOT) is not True or
            any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path, digest in before.items())):
        raise ValueError('Source or canonical build changed during stream verification.')
    report = {'status': 'passed_bounded_original_render_stream',
        'canonical_executable_sha1': hashlib.sha1(native.h.ROM).hexdigest(),
        'original_and_current_build_equal': True, 'original_behavior_modified': False,
        'model_api_calls': 0, 'backend': 'Unicorn ' + native.unicorn.__version__,
        'native_cases': sum(groups.values()), 'case_groups': dict(groups), 'decision_axes': dict(axes),
        'rectangle_counts': dict(rectangle_counts), 'native_functions': FUNCTIONS,
        'original_virtual_slot': slot_link,
        'executed_native_entry_counts': dict(machine.entry_counts), 'explicit_stubs': 3,
        'stub_contracts': ['position lookup', 'RotMatrix', 'ApplyMatrixLV'],
        'negative_controls_detected': controls, 'source_promotions': 0, 'original_feature_groups_accepted': 0,
        'producer_dependencies': [{'path': path.resolve().relative_to(ROOT).as_posix(), 'sha256': digest}
                                  for path, digest in before.items()],
        'scope': 'All 400 cell positions for bounded window sizes, orientations and vector signs; '
                 'angle/corner boundaries; reordered, missing and duplicate signed slot labels; '
                 'cached/uncached segment aliases and initial contents. Original grid builder, '
                 'row splitting and seven-object slot scanner execute. Compare emitted rectangle '
                 'records/counts/order, whole guarded objects, native/helper calls and eight row '
                 'arguments, matrices/info buffers, stack guards, GP, RA and saved registers. '
                 'Real position lookup, GTE, textures, scene lifetime, framebuffer and PS1 timing '
                 'remain outside these three contracts and are not accepted.'}
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'report': str(destination), 'native_cases': report['native_cases'],
                      'negative_controls': len(controls), 'explicit_stubs': 3, 'passed': True}), flush=True)


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
