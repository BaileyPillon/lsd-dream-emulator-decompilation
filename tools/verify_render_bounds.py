"""Verify the original render-context bounds predicate with local native fixtures.

The original 108-byte function still uses assembly in the matching build.
These fixtures recover signed field, boundary and short-circuit behavior;
they do not accept rendering, stage traversal or a nonmatching C candidate.
"""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import verify_native_ai as native

FUNCTIONS = [{'function': 'func_8004CD38', 'address': '0x8004CD38', 'bytes': 108,
              'sha256': '73713a1bd9a992c92c7a7fb6c5c88684a9224107fbc2b0d4d2f83b606e71d03a'}]
BOUNDS_BUFFER, POINT_BUFFER = 0x110000, 0x111000
BOUNDS, POINT, UNMAPPED = BOUNDS_BUFFER + 0x20, POINT_BUFFER + 0x20, 0x300000
LIMITS = [(0, 0, 127, 127), (-128, -128, -1, -1), (-32, -40, 32, 40),
          (-32768, -32768, 2147483647, 2147483647),
          (32767, 32767, 2147483647, 2147483647),
          (-32768, -32768, -2147483648, -2147483648),
          (12, -2, -12, -3), (-128, 127, 127, 127)]


def fixtures(case):
    buffers = [bytearray((i * 37 + case.get('seed', 0) * 91 + base) & 255
                         for i in range(0x80)) for base in (0xC7, 0xD3)]
    if case['bounds'] is not None:
        struct.pack_into('<hhii', buffers[0], 0x20, *case['bounds'])
    point_offset = case.get('point_offset', 0)
    alias = case.get('alias', False)
    buffer = buffers[0] if alias else buffers[1]
    buffer[0x20 + point_offset:0x22 + point_offset] = bytes((case['x'], case['y']))
    bounds_pointer = BOUNDS if case['bounds'] is not None else 0
    point_pointer = (BOUNDS if alias else POINT) + point_offset
    if case.get('unmapped_point', False):
        point_pointer = UNMAPPED
    return tuple(map(bytes, buffers)), bounds_pointer, point_pointer


def expected(case):
    buffers, bounds_pointer, point_pointer = fixtures(case)
    if bounds_pointer == 0:
        return buffers, 1, [], 'null_bounds'
    offset = 0x20 + case.get('point_offset', 0)
    coords = buffers[0] if case.get('alias', False) else buffers[1]
    x, y = struct.unpack_from('<bb', coords, offset)
    min_x, min_y, max_x, max_y = struct.unpack_from('<hhii', buffers[0], 0x20)
    reads = [[point_pointer, 1], [bounds_pointer, 2]]
    if x < min_x:
        return buffers, 1, reads, 'below_min_x'
    reads.append([bounds_pointer + 4, 4])
    if x > max_x:
        return buffers, 1, reads, 'above_max_x'
    reads.extend([[point_pointer + 1, 1], [bounds_pointer + 2, 2]])
    if y < min_y:
        return buffers, 1, reads, 'below_min_y'
    reads.append([bounds_pointer + 8, 4])
    return buffers, int(y > max_y), reads, 'above_max_y' if y > max_y else 'inside'


def cases():
    """Distinct inputs: complete byte sweeps, edge pairs, aliases and nulls."""
    seen = set()

    def add(group, case):
        key = json.dumps(case, sort_keys=True)
        if key not in seen:
            seen.add(key)
            return group, case

    def middle(low, high):
        low, high = max(-128, low), min(127, high)
        return (low + high) // 2 if low <= high else 0

    edge_bytes = (0x80, 0x81, 0xFF, 0, 1, 0x7E, 0x7F)
    for limits in LIMITS:
        center_x = middle(limits[0], limits[2]) & 255
        center_y = middle(limits[1], limits[3]) & 255
        for x in range(256):
            row = add('complete_x_byte_sweep', {'bounds': limits, 'x': x, 'y': center_y})
            if row:
                yield row
        for y in range(256):
            row = add('complete_y_byte_sweep', {'bounds': limits, 'x': center_x, 'y': y})
            if row:
                yield row
        for x, y in itertools.product(edge_bytes, repeat=2):
            row = add('cross_axis_edges', {'bounds': limits, 'x': x, 'y': y})
            if row:
                yield row
    for alias_offset, x, y, seed in itertools.product(
            (0, 1, 2, 3, 4, 5, 8, 9), (0x80, 0, 0x7F), (0xFF, 0, 1), range(2)):
        yield 'aliased_input_fields', {'bounds': (-32, -40, 32, 40), 'x': x, 'y': y,
                                     'alias': True, 'point_offset': alias_offset, 'seed': seed}
    for x, y, segment in itertools.product(edge_bytes, edge_bytes, (0, 0x80000000)):
        yield 'unaligned_and_segment_alias', {'bounds': (-32, -40, 32, 40), 'x': x,
                                             'y': y, 'point_offset': 1, 'segment': segment}
    for x, y in itertools.product((0, 0x80), (0, 0xFF)):
        yield 'null_bounds_unmapped_point', {'bounds': None, 'x': x, 'y': y,
                                            'unmapped_point': True}


class Machine(native.Machine):
    def __init__(self, code=None):
        self.entry_counts = Counter()
        self.reads, self.writes = [], []
        super().__init__(code=code, start=0x4CD38, native_functions=FUNCTIONS)
        self.cpu.hook_add(native.unicorn.UC_HOOK_MEM_READ, self.memory_read)
        self.cpu.hook_add(native.unicorn.UC_HOOK_MEM_WRITE, self.memory_write)

    def hook(self, cpu, address, size, unused):
        name = self.native_entries.get(address & native.MASK)
        if name:
            self.entry_counts[name] += 1
            self.executed_native_functions.add(name)

    def memory_read(self, cpu, access, address, size, value, unused):
        self.reads.append([address & native.MASK, size])

    def memory_write(self, cpu, access, address, size, value, unused):
        self.writes.append([address & native.MASK, size])

    def run(self, case):
        buffers, bounds_pointer, point_pointer = fixtures(case)
        cpu = self.cpu
        for address, data in zip((BOUNDS_BUFFER, POINT_BUFFER), buffers):
            cpu.mem_write(address, data)
        saved = [native.u32(0xCD000000 + 0x10403 * i) for i in range(len(native.SAVED))]
        for register, value in zip(native.SAVED, saved):
            cpu.reg_write(register, value)
        segment = case.get('segment', 0)
        for register, value in ((native.reg.UC_MIPS_REG_SP, native.STACK),
                (native.reg.UC_MIPS_REG_GP, 0x8008A808),
                (native.reg.UC_MIPS_REG_RA, native.END),
                (native.reg.UC_MIPS_REG_A0, bounds_pointer | segment if bounds_pointer else 0),
                (native.reg.UC_MIPS_REG_A1, point_pointer | segment),
                (native.reg.UC_MIPS_REG_A2, 0xAB123456),
                (native.reg.UC_MIPS_REG_A3, 0xAB765432)):
            cpu.reg_write(register, value)
        self.reads, self.writes = [], []
        cpu.emu_start(self.start, native.END, count=200)
        if (cpu.reg_read(native.reg.UC_MIPS_REG_PC) != native.END or self.writes or
                cpu.reg_read(native.reg.UC_MIPS_REG_SP) != native.STACK or
                cpu.reg_read(native.reg.UC_MIPS_REG_GP) != 0x8008A808 or
                cpu.reg_read(native.reg.UC_MIPS_REG_RA) != native.END or
                [cpu.reg_read(register) for register in native.SAVED] != saved):
            raise ValueError('Original bounds ABI or read-only contract failed.')
        return (tuple(bytes(cpu.mem_read(address, len(data)))
                      for address, data in zip((BOUNDS_BUFFER, POINT_BUFFER), buffers)),
                cpu.reg_read(native.reg.UC_MIPS_REG_V0), self.reads)


def verify(destination):
    dependencies = native.evidence_dependencies('tools/verify_render_bounds.py',
        'src/scene/render_context.c', 'src/scene/render_context.h', 'config/symbols.txt',
        'asm/nonmatchings/scene/render_context/func_8004CD38.s')
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    native.initialize_backend(native.load_program(FUNCTIONS))
    machine, groups, paths = Machine(), Counter(), Counter()
    for group, case in cases():
        model = expected(case)
        if machine.run(case) != model[:3]:
            raise ValueError('Original bounds/reference disagreement: ' + repr(case))
        groups[group] += 1
        paths[model[3]] += 1
    original = native.h.target(0x8004CD38, 108)
    controls = []
    for name, address, old, new, case in (
            ('unsigned_x_sign_extension', 0x8004CD50, 0x00071E03, 0x00071E02,
             {'bounds': (0, 0, 10, 10), 'x': 0xFF, 'y': 0}),
            ('unsigned_minimum_x', 0x8004CD48, 0x84C40000, 0x94C40000,
             {'bounds': (-1, 0, 10, 10), 'x': 0, 'y': 0}),
            ('wrong_maximum_y_field', 0x8004CD90, 0x8CC30008, 0x8CC30004,
             {'bounds': (0, 0, 1, 8), 'x': 0, 'y': 5}),
            ('unsigned_maximum_x', 0x8004CD68, 0x0064182A, 0x0064182B,
             {'bounds': (-128, -128, -1, 127), 'x': 0, 'y': 0})):
        code = bytearray(original)
        offset = address - 0x8004CD38
        if struct.unpack_from('<I', code, offset)[0] != old:
            raise ValueError('Bounds control instruction evidence changed: ' + name)
        struct.pack_into('<I', code, offset, new)
        if Machine(bytes(code)).run(case) == expected(case)[:3]:
            raise ValueError('Bounds negative control was not detected: ' + name)
        controls.append({'name': name, 'address': hex(address), 'fixture': case,
                         'detected': True, 'scope': 'Private Unicorn memory only.'})
    if ((ROOT / native.configure.ROM).read_bytes() != native.h.ROM or
            (ROOT / native.configure.EXE).read_bytes() != native.h.ROM or
            native.check_build_current(ROOT) is not True or
            any(hashlib.sha256(path.read_bytes()).hexdigest() != digest
                for path, digest in before.items())):
        raise ValueError('Source or canonical build changed during bounds verification.')
    report = {'status': 'passed_bounded_original_render_bounds',
        'canonical_executable_sha1': hashlib.sha1(native.h.ROM).hexdigest(),
        'original_and_current_build_equal': True, 'original_behavior_modified': False,
        'model_api_calls': 0, 'backend': 'Unicorn ' + native.unicorn.__version__,
        'native_cases': sum(groups.values()), 'case_groups': dict(groups),
        'decision_paths': dict(paths), 'native_functions': FUNCTIONS,
        'executed_native_entry_counts': dict(machine.entry_counts), 'explicit_stubs': 0,
        'negative_controls_detected': controls, 'source_promotions': 0,
        'producer_dependencies': [{'path': path.resolve().relative_to(ROOT).as_posix(),
                                   'sha256': digest} for path, digest in before.items()],
        'original_feature_groups_accepted': 0,
        'scope': 'Both complete byte-coordinate sweeps across eight signed bound layouts, '
                 'cross-axis edges, aliased record/coordinate inputs, unaligned byte pointers, '
                 'cached-segment aliases and null bounds with an unmapped coordinate pointer. '
                 'Compare return status, exact data-read order/widths, whole guarded input buffers, '
                 'zero native writes, GP, stack and saved registers. No stubs. The original '
                 'function remains assembly. No C candidate, renderer, stage, framebuffer '
                 'or PS1 timing acceptance is claimed.'}
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'report': str(destination), 'native_cases': report['native_cases'],
                      'negative_controls': len(controls), 'explicit_stubs': 0, 'passed': True}))


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
