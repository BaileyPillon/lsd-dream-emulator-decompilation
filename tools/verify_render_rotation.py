"""Execute the original SDK rotation helper and the world-to-stream chain.

RotMatrix is ordinary MIPS code using the canonical packed sine/cosine table.
It executes without stubs. The ten-function composition retains only the
ApplyMatrixLV hardware contract; GTE, scene ownership and timing are separate.
Reports require a new private path and do not distribute the original table.
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
from tools import verify_render_grid as grid
from tools import verify_render_position as position

ROTATION = {'function': 'RotMatrix', 'address': '0x800160B0', 'bytes': 652,
            'sha256': 'cab8838ded03b3b2a50a32cc279811d7fb6a1ee23cfe640c1ac4d7c1d9eee443'}
FUNCTIONS = position.ALL_FUNCTIONS + [ROTATION]
TABLE = {'symbol': 'D_80066BE0', 'address': '0x80066BE0', 'bytes': 16384,
         'records': 4096, 'record_bytes': 4,
         'sha256': 'b106234165685d79392c926192d1b2f9e30125307abde6040747e401a35d0e87'}
BUFFER = 0x120000
BUFFER_BYTES = 0xE0


def table_pairs(program):
    if program.symbols.get(TABLE['symbol']) != int(TABLE['address'], 16):
        raise ValueError('Canonical rotation table symbol changed.')
    data = program.target(int(TABLE['address'], 16), TABLE['bytes'])
    if hashlib.sha256(data).hexdigest() != TABLE['sha256']:
        raise ValueError('Canonical packed sine/cosine table changed.')
    pairs = tuple(struct.iter_unpack('<hh', data))
    if any(abs(value) > 4096 for pair in pairs for value in pair):
        raise ValueError('Rotation table exceeds the reviewed fixed-point range.')
    return pairs


def sine_cosine(angle, pairs):
    """Retain the native signed-angle branch, rather than periodic remapping."""
    angle = position.signed(angle, 16)
    sine, cosine = pairs[abs(angle) & 0xFFF]
    return (-sine if angle < 0 else sine), cosine


def rotation_bytes(euler, pairs):
    """Independent Euler products with each native fixed-point rounding stage."""
    sx, cx = sine_cosine(euler[0], pairs)
    sy, cy = sine_cosine(euler[1], pairs)
    sz, cz = sine_cosine(euler[2], pairs)

    def fixed(value):
        return position.signed(value) >> 12

    cycz, cysz = fixed(cy * cz), fixed(-cy * sz)
    xz = fixed(-sy * cz)
    yz = fixed(-sy * sz)
    values = (cycz, cysz, sy,
              fixed(sz * cx) - fixed(xz * sx),
              fixed(cz * cx) + fixed(yz * sx), fixed(-cy * sx),
              fixed(xz * cx) + fixed(sz * sx),
              fixed(cz * sx) - fixed(yz * cx), fixed(cy * cx))
    return struct.pack('<9h', *(position.signed(value, 16) for value in values))


def standalone_case(euler=(0, 0, 0), **changes):
    return dict(dict(euler=tuple(position.signed(value, 16) for value in euler), segment=0, seed=0,
                     angle_offset=0x20, matrix_offset=0x60), **changes)


def standalone_fixture(case):
    offsets = (case['angle_offset'], case['matrix_offset'])
    if any(offset < 0x10 or offset & 1 for offset in offsets):
        raise ValueError('Rotation fixture pointers must be guarded and halfword aligned.')
    if offsets[0] + 6 > BUFFER_BYTES - 0x10 or offsets[1] + 32 > BUFFER_BYTES - 0x10:
        raise ValueError('Rotation fixture output exceeds its guarded buffer.')
    data = bytearray((index * 37 + case['seed'] * 91 + 13) & 255
                     for index in range(BUFFER_BYTES))
    struct.pack_into('<3h', data, offsets[0], *(position.signed(v, 16) for v in case['euler']))
    pointers = tuple((BUFFER + offset) | case['segment'] for offset in offsets)
    return data, pointers


def standalone_expected(case, pairs):
    data, pointers = standalone_fixture(case)
    offset = case['matrix_offset']
    data[offset:offset + 18] = rotation_bytes(case['euler'], pairs)
    return bytes(data), native.u32(pointers[1])


class RotationMachine(native.Machine):
    def __init__(self, patches=None):
        self.entry_count = 0
        super().__init__(start=int(ROTATION['address'], 16) & native.MASK,
                         native_functions=[ROTATION])
        for address, data in (patches or {}).items():
            self.cpu.mem_write(address & native.MASK, data)

    def hook(self, cpu, address, size, unused):
        address &= native.MASK
        if address == self.start:
            self.entry_count += 1
        if not self.start <= address < self.start + ROTATION['bytes']:
            raise ValueError('Execution escaped the reviewed original rotation helper.')

    def run(self, case):
        initial, pointers = standalone_fixture(case)
        cpu = self.cpu
        cpu.mem_write(BUFFER, bytes(initial))
        guard = bytes([0xC9]) * 0x80
        cpu.mem_write(native.STACK - 0x40, guard)
        saved = [native.u32(0xAD000000 + i * 0x10203) for i in range(len(native.SAVED))]
        for register, value in zip(native.SAVED, saved):
            cpu.reg_write(register, value)
        for register, value in ((native.reg.UC_MIPS_REG_SP, native.STACK),
                (native.reg.UC_MIPS_REG_GP, 0x8008A808), (native.reg.UC_MIPS_REG_RA, native.END),
                (native.reg.UC_MIPS_REG_A0, pointers[0]), (native.reg.UC_MIPS_REG_A1, pointers[1])):
            cpu.reg_write(register, value)
        cpu.emu_start(self.start, native.END, count=400)
        if (cpu.reg_read(native.reg.UC_MIPS_REG_PC) != native.END or
                cpu.reg_read(native.reg.UC_MIPS_REG_SP) != native.STACK or
                cpu.reg_read(native.reg.UC_MIPS_REG_GP) != 0x8008A808 or
                cpu.reg_read(native.reg.UC_MIPS_REG_RA) != native.END or
                [cpu.reg_read(r) for r in native.SAVED] != saved or
                bytes(cpu.mem_read(native.STACK - 0x40, len(guard))) != guard):
            raise ValueError('Rotation helper violated guarded stack or saved ABI.')
        return bytes(cpu.mem_read(BUFFER, BUFFER_BYTES)), cpu.reg_read(native.reg.UC_MIPS_REG_V0)


def standalone_cases():
    # Each halfword domain is exhausted with the other two axes fixed to a
    # nonzero mixed rotation. This is not the full three-angle Cartesian domain.
    for axis in range(3):
        for word in range(65536):
            euler = [137, -821, 1603]
            euler[axis] = word
            yield 'axis_' + str(axis) + '_complete_word_sweep', standalone_case(euler)
    edges = (-32768, -4097, -4096, -4095, -1024, -1, 0, 1, 1024, 4095, 4096, 4097, 32767)
    for euler, segment in itertools.product(itertools.product(edges, repeat=3),
                                           (0, 0x80000000, 0xA0000000)):
        yield 'mixed_sign_and_period_edges', standalone_case(euler, segment=segment, seed=1)
    for euler, offsets, segment in itertools.product(
            ((0, 0, 0), (1, -1, 1023), (-1025, 513, -32768), (32767, -4095, 4097)),
            ((0x20, 0x20), (0x22, 0x20), (0x20, 0x22), (0x20, 0x24), (0x30, 0x20)),
            (0, 0x80000000, 0xA0000000)):
        yield 'overlapping_input_output', standalone_case(euler, angle_offset=offsets[0],
            matrix_offset=offsets[1], segment=segment, seed=2)


def composition_cases():
    for case in position.composition_cases():
        # Pitch and roll vary across the real lookup's seven labels while yaw
        # retains the earlier angular/rectangle coverage and projection contract.
        label = position.selected_label(case)
        euler = ((0, 1, -1, 513, -1025, 4095, -32768)[label], case['angle'],
                 (0, -513, 1025, -4095, 32767, -1, 1)[label])
        yield dict(case, euler=euler)


def composition_fixture(case):
    if (len(case['euler']) != 3 or
            position.signed(case['euler'][1], 16) != position.signed(case['angle'], 16)):
        raise ValueError('Composition yaw must agree with the grid decision angle.')
    buffers, pointers, template, rotation = position.fixture(case)
    struct.pack_into('<3h', buffers['angles'], 0x30,
                     *(position.signed(value, 16) for value in case['euler']))
    return buffers, pointers, template, rotation


def composition_expected(case, pairs):
    model, axis, rectangles = position.composition_expected(case)
    buffers, trace, template, info, matrix = model
    buffers = dict(buffers)
    buffers['angles'] = bytes(composition_fixture(case)[0]['angles'])
    coefficients = rotation_bytes(case['euler'], pairs)
    matrix = coefficients + matrix[18:]
    updated = []
    for entry in trace:
        if entry[0] == 'rotate':
            entry = (*entry[:3], struct.pack('<3h', *(position.signed(v, 16) for v in case['euler'])), entry[4])
        elif entry[0] == 'apply':
            entry = (*entry[:4], coefficients + entry[4][18:])
        elif entry[0] == 'build':
            entry = (*entry[:3], coefficients + entry[3][18:])
        updated.append(entry)
    return (buffers, updated, template, info, matrix), axis, rectangles


class CompositionMachine(position.CompositionMachine):
    def __init__(self, patches=None):
        super().__init__(patches=patches)
        del self.stubs[int(ROTATION['address'], 16) & native.MASK]
        self.native_entries = {int(f['address'], 16) & native.MASK: f['function'] for f in FUNCTIONS}
        self.ranges = [(int(f['address'], 16) & native.MASK, f['bytes']) for f in FUNCTIONS]
        if len(self.stubs) != 1:
            raise ValueError('Expected only the ApplyMatrixLV hardware contract.')

    def hook(self, cpu, address, size, unused):
        address &= native.MASK
        if address == int(ROTATION['address'], 16) & native.MASK:
            self.entry_counts['RotMatrix'] += 1
            a0, a1 = (cpu.reg_read(register) for register in (native.reg.UC_MIPS_REG_A0, native.reg.UC_MIPS_REG_A1))
            if [a0, a1] != [self.pointers['angles'] + 0x10, grid.MATRIX]:
                raise ValueError('Original rotation call has unexpected arguments.')
            self.trace.append(('rotate', a0, a1, self.read(a0, 6), self.read(a1, 32)))
            return
        super().hook(cpu, address, size, unused)

    def run(self, case):
        self.case, self.trace = case, []
        self.buffers, self.pointers, template, self.rotation = composition_fixture(case)
        cpu = self.cpu
        for name, data in self.buffers.items():
            cpu.mem_write(position.BASES[name], bytes(data))
        cpu.mem_write(grid.TEMPLATE, template)
        guard = bytes([0xC9]) * 0x400
        cpu.mem_write(native.STACK - 0x300, guard)
        saved = [native.u32(0xAD000000 + i * 0x10203) for i in range(len(native.SAVED))]
        for register, value in zip(native.SAVED, saved):
            cpu.reg_write(register, value)
        for register, value in ((native.reg.UC_MIPS_REG_SP, native.STACK),
                (native.reg.UC_MIPS_REG_GP, 0x8008A808), (native.reg.UC_MIPS_REG_RA, native.END),
                (native.reg.UC_MIPS_REG_A0, self.pointers['context']),
                (native.reg.UC_MIPS_REG_A1, native.u32(case['width'])),
                (native.reg.UC_MIPS_REG_A2, native.u32(case['height'])),
                (native.reg.UC_MIPS_REG_A3, 0xBEADC0DE)):
            cpu.reg_write(register, value)
        cpu.emu_start(self.start, native.END, count=12000)
        if (cpu.reg_read(native.reg.UC_MIPS_REG_PC) != native.END or
                cpu.reg_read(native.reg.UC_MIPS_REG_SP) != native.STACK or
                cpu.reg_read(native.reg.UC_MIPS_REG_GP) != 0x8008A808 or
                cpu.reg_read(native.reg.UC_MIPS_REG_RA) != native.END or
                [cpu.reg_read(r) for r in native.SAVED] != saved or
                self.read(native.STACK - 0x300, 0x100) != guard[:0x100] or
                self.read(native.STACK, 0x100) != guard[0x300:]):
            raise ValueError('Rotation/position/render composition violated guarded stack or saved ABI.')
        return ({name: self.read(position.BASES[name], len(data)) for name, data in self.buffers.items()},
                self.trace, self.read(grid.TEMPLATE, 32), self.read(grid.INFO, 44), self.read(grid.MATRIX, 32))


def negative_controls(pairs):
    records = []
    specs = [('wrong_fractional_shift', 0x80016220, 0x000F7303, 0x000F7343,
              standalone_case((137, -821, 1603))),
             ('skip_negative_pitch_reflection', 0x800160E8, 0x00185823, 0x00185821,
              standalone_case((-137, -821, 1603)))]
    for name, address, original, modified, case in specs:
        if int.from_bytes(native.h.target(address, 4), 'little') != original:
            raise ValueError('Original rotation control instruction changed: ' + name)
        observed = RotationMachine({address: struct.pack('<I', modified)}).run(case)
        if observed == standalone_expected(case, pairs):
            raise ValueError('Rotation fault was not detected: ' + name)
        records.append({'name': name, 'address': hex(address), 'detected': True,
                        'scope': 'Private Unicorn memory only.'})
    address = int(TABLE['address'], 16) + 4
    case = standalone_case((1, 0, 0))
    word = int.from_bytes(native.h.target(address, 4), 'little')
    observed = RotationMachine({address: struct.pack('<I', word ^ 1)}).run(case)
    if observed == standalone_expected(case, pairs):
        raise ValueError('Packed table fault was not detected.')
    records.append({'name': 'packed_sine_table_bit', 'address': hex(address), 'detected': True,
                    'scope': 'Private Unicorn memory only; canonical input remains unchanged.'})
    case = next(c for c in composition_cases() if c['euler'][0] < 0)
    observed = CompositionMachine({0x800160E8: struct.pack('<I', 0x00185821)}).run(case)
    if observed == composition_expected(case, pairs)[0]:
        raise ValueError('Composed original rotation fault was not detected.')
    records.append({'name': 'composed_negative_pitch_reflection', 'address': '0x800160e8',
                    'detected': True, 'scope': 'Private Unicorn memory only.'})
    return records


def verify(destination):
    dependencies = native.evidence_dependencies('tools/verify_render_rotation.py',
        'tools/verify_render_grid.py', 'tools/verify_render_stream.py', 'tools/verify_render_position.py',
        'src/scene/render_context.c', 'src/scene/render_context.h', 'src/psyq/gte/fgo01.c',
        'asm/nonmatchings/psyq/gte/fgo01/RotMatrix.s')
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in dependencies}
    native.initialize_backend(native.load_program(FUNCTIONS))
    pairs = table_pairs(native.h)
    position.canonical_bindings(native.h)
    machine = RotationMachine()
    groups, unique = Counter(), set()
    previous = None
    for group, case in standalone_cases():
        if group != previous:
            if previous:
                print(previous, groups[previous], 'passed', flush=True)
            previous = group
        key = json.dumps(case, sort_keys=True)
        unique.add(key)
        observed = machine.run(case)
        if observed != standalone_expected(case, pairs):
            failure = destination.with_name(destination.stem + '-rotation-failure.json')
            with failure.open('x', encoding='utf-8') as f:
                json.dump({'group': group, 'case': case, 'observed_return': observed[1],
                           'different_byte_offsets': [i for i, (a, b) in enumerate(zip(
                               observed[0], standalone_expected(case, pairs)[0])) if a != b]}, f, indent=2)
            raise ValueError('Original rotation/model disagreement; see ' + failure.name)
        groups[group] += 1
    print(previous, groups[previous], 'passed', flush=True)
    composition = CompositionMachine()
    composed_unique, axes, rectangles = set(), Counter(), Counter()
    for case in composition_cases():
        composed_unique.add(json.dumps(case, sort_keys=True))
        model, axis, count = composition_expected(case, pairs)
        observed = composition.run(case)
        if observed != model:
            failure = destination.with_name(destination.stem + '-composition-failure.json')
            with failure.open('x', encoding='utf-8') as f:
                json.dump({'case': case, 'expected_trace': model[1], 'observed_trace': observed[1],
                           'different_buffers': [name for name in model[0] if observed[0][name] != model[0][name]],
                           'template_equal': model[2] == observed[2], 'info_equal': model[3] == observed[3],
                           'matrix_equal': model[4] == observed[4]}, f, indent=2,
                          default=lambda value: {'bytes_hex': value.hex()})
            raise ValueError('Original rotation composition/model disagreement; see ' + failure.name)
        axes[axis] += 1
        rectangles[count] += 1
    composed_count = sum(axes.values())
    if len(composed_unique) != composed_count:
        raise ValueError('Repeated composed inputs must be classified before publication.')
    print('native_rotation_world_to_stream', composed_count, 'passed', flush=True)
    table_data = native.h.target(int(TABLE['address'], 16), TABLE['bytes'])
    for runner in (machine, composition):
        if bytes(runner.cpu.mem_read(int(TABLE['address'], 16) & native.MASK, TABLE['bytes'])) != table_data:
            raise ValueError('Original execution changed the canonical packed table.')
    controls = negative_controls(pairs)
    if any(hashlib.sha256(p.read_bytes()).hexdigest() != value for p, value in before.items()):
        raise ValueError('Evidence dependency changed during rotation checks.')
    if (ROOT / native.configure.EXE).read_bytes() != native.h.ROM or native.check_build_current(ROOT) is not True:
        raise ValueError('Canonical build changed during rotation checks.')
    report = {'status': 'passed_bounded_original_render_rotation',
        'canonical_executable_sha1': hashlib.sha1(native.h.ROM).hexdigest(),
        'original_and_current_build_equal': True, 'original_behavior_modified': False, 'model_api_calls': 0,
        'backend': 'Unicorn ' + native.unicorn.__version__, 'native_function': ROTATION,
        'packed_trigonometric_table': TABLE, 'table_bytes_distributed': False,
        'native_cases': len(unique), 'native_runs': sum(groups.values()),
        'repeated_input_runs': sum(groups.values()) - len(unique), 'case_groups': dict(groups),
        'case_group_count_scope': 'Native invocations; distinct inputs counted separately.',
        'executed_rotation_entries': machine.entry_count, 'explicit_stubs': 0,
        'complete_axis_word_domains_checked': 3, 'complete_three_angle_cartesian_domain_checked': False,
        'table_cosine_quarter_shift_mismatches': sum(c != pairs[(i + 1024) & 4095][0]
                                                    for i, (_, c) in enumerate(pairs)),
        'table_odd_sine_reflection_mismatches': sum(pairs[(-i) & 4095][0] != -s for i, (s, _) in enumerate(pairs)),
        'composition': {'native_cases': composed_count, 'native_functions': FUNCTIONS,
            'executed_native_entry_counts': dict(composition.entry_counts),
            'decision_axes': dict(axes), 'emitted_rectangle_counts': dict(rectangles),
            'explicit_stubs': 1, 'stub_contracts': ['ApplyMatrixLV']},
        'negative_controls_detected': controls, 'source_promotions': 0, 'original_feature_groups_accepted': 0,
        'producer_dependencies': [{'path': p.resolve().relative_to(ROOT).as_posix(), 'sha256': value}
                                  for p, value in before.items()],
        'scope': 'The original 652-byte SDK RotMatrix and its canonical packed table execute without stubs. '
                 'Individual complete signed-halfword domains, mixed sign/period edges, buffer overlaps and aliases '
                 'are checked against independent staged Euler products. This is not the full three-angle domain. '
                 'Ten original game/SDK functions compose real lookup, rotation, grid generation and streaming '
                 'with only ApplyMatrixLV under its existing argument/output contract. Actual GTE, natural graph '
                 'ownership, scenes, framebuffer and PS1 load-delay/cycle timing remain separate.'}
    with destination.open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print(json.dumps({'report': str(destination), 'native_cases': len(unique),
                      'native_runs': sum(groups.values()), 'composition_cases': composed_count,
                      'negative_controls': len(controls), 'composition_stubs': 1}), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        destination = (ROOT / args.output).resolve()
        if not destination.is_relative_to((ROOT / '.decomp-lab').resolve()) or destination.exists():
            raise ValueError('Choose a new report path inside private .decomp-lab.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        verify(destination)
        return 0
    except (OSError, ValueError) as error:
        print('[!] ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
