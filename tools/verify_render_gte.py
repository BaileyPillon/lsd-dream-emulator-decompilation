"""Execute ApplyMatrixLV using original MIPS and a checked native GTE bridge.

The bridge invokes the pinned Nymashock MVMVA implementation. Reviewed COP2
register transfers connect it to Unicorn; no original function is skipped.
This verifies arithmetic and composition, not PS1 CPU load delays or scenes.
"""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import verify_native_ai as native
from tools import verify_render_rotation as rotation

grid, position = rotation.grid, rotation.position
APPLY = {'function': 'ApplyMatrixLV', 'address': '0x80015618', 'bytes': 352,
         'sha256': 'b5cca44ff50bf0ca0e5996e8f5cf1b954740710e6773d57827b764a47fee082e'}
FUNCTIONS = rotation.FUNCTIONS + [APPLY]
COMMANDS = (0x4A41E012, 0x4A49E012)
BUFFER, BUFFER_BYTES = 0x120000, 0x180
CORE_SHA256 = '5c6fe90fadd670318ca74993911b171e15b167c7f2e1e88bf66de4661fc24126'


def matrix_words(matrix):
    if len(matrix) != 9:
        raise ValueError('Nine signed-halfword matrix coefficients are required.')
    return list(struct.unpack('<5I', struct.pack('<10h', *(position.signed(v, 16) for v in matrix), 0)))


def command_model(cr, ir, command):
    """Independent dot products, signed MAC narrowing and IR limit flags.

    With signed 16-bit coefficients/vectors and null translation, no partial
    sum approaches the 44-bit accumulator limits. MAC still narrows to 32 bits
    before the IR clamp, including positive sums wrapping to negative MAC.
    """
    if len(cr) != 5 or len(ir) != 3 or command not in COMMANDS:
        raise ValueError('Only the two reviewed MVMVA commands are supported.')
    coefficients = struct.unpack('<10h', struct.pack('<5I', *(native.u32(v) for v in cr)))[:9]
    vector = [position.signed(v, 16) for v in ir]
    shift = 12 if command == COMMANDS[1] else 0
    mac = [position.signed(sum(coefficients[row * 3 + col] * vector[col] for col in range(3)) >> shift)
           for row in range(3)]
    flags, saturated = 0, []
    for index, value in enumerate(mac):
        if not -32768 <= value <= 32767:
            flags |= 1 << (24 - index)
        saturated.append(max(-32768, min(32767, value)))
    if flags & 0x7F87E000:
        flags |= 1 << 31
    return {'mac': mac, 'ir': saturated, 'flags': flags, 'command_cycles_minus_one': 7}


def split_vector(vector):
    """Split signed long inputs, retaining INT_MIN negation and IR truncation."""
    high, low = [], []
    for value in map(position.signed, vector):
        magnitude = position.signed(-value) if value < 0 else value
        hi, lo = magnitude >> 15, magnitude & 32767
        if value < 0:
            hi, lo = -hi, -lo
        high.append(position.signed(hi, 16))
        low.append(position.signed(lo, 16))
    return high, low


def apply_model(matrix, vector):
    cr = matrix_words(matrix)
    high, low = split_vector(vector)
    commands = [command_model(cr, high, COMMANDS[0]), command_model(cr, low, COMMANDS[1])]
    result = [position.signed(hi * 8 + lo) for hi, lo in zip(commands[0]['mac'], commands[1]['mac'])]
    return result, commands


class NativeGteBridge:
    def __init__(self, executable, runtime, log):
        self.executable = Path(executable).resolve()
        if not self.executable.is_file():
            raise ValueError('Compile a new local native GTE bridge first.')
        self.log = Path(log)
        self.id, self.count = 0, 0
        self.output = self.log.open('x', encoding='utf-8', newline='\n')
        self.errors = self.log.with_name(self.log.stem + '-stderr.log').open('x', encoding='utf-8', newline='\n')
        self.process = subprocess.Popen([str(self.executable), runtime], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.errors, text=True, bufsize=1)
        try:
            self.ready = self.read('GTE_READY ')
            if self.ready != dict(command_model(matrix_words((4096, 0, 0, 0, 4096, 0, 0, 0, 4096)),
                                               (0, 0, 12345), COMMANDS[1]), id=0):
                raise ValueError('Native bridge self-check differs.')
        except BaseException:
            self.close()
            raise

    def read(self, prefix):
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise ValueError('Native GTE bridge ended before its response; inspect its private logs.')
            self.output.write(line)
            self.output.flush()
            if line.startswith(prefix):
                return json.loads(line[len(prefix):])

    def execute(self, cr, ir, command):
        self.id += 1
        request = dict(id=self.id, cr=list(cr), ir=list(ir), command=command)
        self.output.write('GTE_REQUEST ' + json.dumps(request, separators=(',', ':')) + '\n')
        self.process.stdin.write(json.dumps(request, separators=(',', ':')) + '\n')
        self.process.stdin.flush()
        observed = self.read('GTE_RESULT ')
        if observed.pop('id', None) != self.id:
            raise ValueError('Native GTE response id differs.')
        self.count += 1
        return observed

    def close(self):
        if self.process.stdin and not self.process.stdin.closed:
            self.process.stdin.close()
        code = self.process.wait(timeout=30)
        self.process.stdout.close()
        self.output.close()
        self.errors.close()
        if code:
            raise ValueError('Native GTE bridge exited with code ' + str(code) + '; private logs retained.')


def decode_cop2(word):
    if word >> 26 != 0x12:
        return None
    rs, rt, rd = (word >> 21) & 31, (word >> 16) & 31, (word >> 11) & 31
    if word in COMMANDS:
        return 'command', word, None
    if word & 0x7FF:
        raise ValueError('Unreviewed COP2 instruction encoding.')
    if rs == 6 and rd in range(5):
        return 'ctc2', rt, rd
    if rs == 4 and rd in (9, 10, 11):
        return 'mtc2', rt, rd
    if rs == 0 and rd in (25, 26, 27):
        return 'mfc2', rt, rd
    raise ValueError('Unreviewed COP2 operation or register.')


class Cop2Adapter:
    def __init__(self, bridge):
        self.bridge = bridge
        self.counts = Counter()
        self.reset()

    def reset(self):
        self.cr, self.ir, self.mac = [0] * 5, [0] * 3, [0] * 3
        self.commands = []

    def step(self, word, get_register, set_register):
        decoded = decode_cop2(word)
        if decoded is None:
            return False
        kind, register, cop_register = decoded
        self.counts[kind] += 1
        if kind == 'ctc2':
            self.cr[cop_register] = native.u32(get_register(register)) & (0xFFFF if cop_register == 4 else 0xFFFFFFFF)
        elif kind == 'mtc2':
            self.ir[cop_register - 9] = position.signed(get_register(register), 16)
        elif kind == 'mfc2':
            set_register(register, native.u32(self.mac[cop_register - 25]))
        else:
            inputs = {'cr': self.cr[:], 'ir': self.ir[:], 'command': register}
            observed = self.bridge.execute(**inputs)
            expected = command_model(**inputs)
            if observed != expected:
                raise ValueError('Native MVMVA disagrees with independent arithmetic: ' + repr((inputs, observed, expected)))
            self.commands.append({'inputs': inputs, 'output': observed})
            self.mac, self.ir = observed['mac'][:], observed['ir'][:]
        return True


def handle_cop2(adapter, cpu, address):
    word = int.from_bytes(cpu.mem_read(address, 4), 'little')
    handled = adapter.step(word, lambda number: cpu.reg_read(getattr(native.reg, 'UC_MIPS_REG_' + str(number))),
                          lambda number, value: cpu.reg_write(getattr(native.reg, 'UC_MIPS_REG_' + str(number)), value))
    if handled:
        # No original instruction bytes are rewritten. Reviewed COP2 transfers
        # and command results advance the PC; ordinary MIPS code still executes.
        cpu.reg_write(native.reg.UC_MIPS_REG_PC, address + 4)
    return handled


def standalone_case(matrix=(4096, 0, 0, 0, 4096, 0, 0, 0, 4096), vector=(0, 0, 0), **changes):
    return dict(dict(matrix=tuple(position.signed(v, 16) for v in matrix), vector=tuple(map(position.signed, vector)),
                     matrix_offset=0x30, vector_offset=0x80, output_offset=0xC0, segment=0, seed=0), **changes)


def standalone_fixture(case):
    offsets = tuple(case[key] for key in ('matrix_offset', 'vector_offset', 'output_offset'))
    if any(offset < 0x10 or offset & 3 or offset + length > BUFFER_BYTES - 0x10
           for offset, length in zip(offsets, (20, 12, 12))):
        raise ValueError('Matrix/vector pointers must be word aligned and guarded.')
    data = bytearray((index * 37 + case['seed'] * 91 + 13) & 255 for index in range(BUFFER_BYTES))
    struct.pack_into('<9h', data, offsets[0], *case['matrix'])
    struct.pack_into('<3i', data, offsets[1], *case['vector'])
    pointers = tuple((BUFFER + offset) | case['segment'] for offset in offsets)
    return data, pointers


def standalone_expected(case):
    data, pointers = standalone_fixture(case)
    matrix = struct.unpack_from('<9h', data, case['matrix_offset'])
    vector = struct.unpack_from('<3i', data, case['vector_offset'])
    result, commands = apply_model(matrix, vector)
    struct.pack_into('<3i', data, case['output_offset'], *result)
    return (bytes(data), native.u32(pointers[2])), commands


class ApplyMachine(native.Machine):
    def __init__(self, bridge, patches=None):
        self.adapter, self.entries = Cop2Adapter(bridge), 0
        super().__init__(start=int(APPLY['address'], 16) & native.MASK, native_functions=[APPLY])
        for address, data in (patches or {}).items():
            self.cpu.mem_write(address & native.MASK, data)

    def hook(self, cpu, address, size, unused):
        address &= native.MASK
        if address == self.start:
            self.entries += 1
        if not self.start <= address < self.start + APPLY['bytes']:
            raise ValueError('Execution escaped original ApplyMatrixLV.')
        handle_cop2(self.adapter, cpu, address)

    def run(self, case):
        self.adapter.reset()
        initial, pointers = standalone_fixture(case)
        cpu = self.cpu
        cpu.mem_write(BUFFER, bytes(initial))
        guard = bytes([0xC9]) * 0x80
        cpu.mem_write(native.STACK - 0x40, guard)
        saved = [native.u32(0xAD000000 + i * 0x10203) for i in range(len(native.SAVED))]
        for register, value in zip(native.SAVED, saved):
            cpu.reg_write(register, value)
        for register, value in ((native.reg.UC_MIPS_REG_SP, native.STACK), (native.reg.UC_MIPS_REG_GP, 0x8008A808),
                (native.reg.UC_MIPS_REG_RA, native.END), (native.reg.UC_MIPS_REG_A0, pointers[0]),
                (native.reg.UC_MIPS_REG_A1, pointers[1]), (native.reg.UC_MIPS_REG_A2, pointers[2])):
            cpu.reg_write(register, value)
        cpu.emu_start(self.start, native.END, count=400)
        if (cpu.reg_read(native.reg.UC_MIPS_REG_PC) != native.END or
                cpu.reg_read(native.reg.UC_MIPS_REG_SP) != native.STACK or cpu.reg_read(native.reg.UC_MIPS_REG_RA) != native.END or
                cpu.reg_read(native.reg.UC_MIPS_REG_GP) != 0x8008A808 or [cpu.reg_read(r) for r in native.SAVED] != saved or
                bytes(cpu.mem_read(native.STACK - 0x40, len(guard))) != guard):
            raise ValueError('ApplyMatrixLV violated guarded stack or saved ABI.')
        return bytes(cpu.mem_read(BUFFER, BUFFER_BYTES)), cpu.reg_read(native.reg.UC_MIPS_REG_V0)


def standalone_cases():
    matrices = ((4096, 0, 0, 0, 4096, 0, 0, 0, 4096), (0,) * 9,
                (0, 0, 4096, 0, 4096, 0, -4096, 0, 0),
                (4093, -17, 23, -1024, 3585, -2001, 177, 801, 3123),
                (-32768,) * 9, (32767,) * 9,
                (-32768, 32767, -1, 1, -4096, 4095, 32767, -32768, 13))
    edges = (-2147483648, -2147483647, -1073741825, -1073741824, -1073741823,
             -65537, -65536, -32769, -32768, -32767, -4097, -4096, -1, 0, 1,
             4095, 4096, 32767, 32768, 32769, 65535, 65536, 1073741823, 1073741824, 2147483647)
    for matrix, vector in itertools.product(matrices, itertools.product(edges, repeat=3)):
        yield 'signed_long_split_and_matrix_edges', standalone_case(matrix, vector)
    for matrix, offsets, segment in itertools.product(matrices,
            ((0x30, 0x80, 0x80), (0x30, 0x80, 0x84), (0x30, 0x80, 0x7C),
             (0x30, 0x80, 0x30), (0x30, 0x80, 0x34), (0x30, 0x30, 0x30)),
            (0, 0x80000000, 0xA0000000)):
        yield 'overlapping_inputs_outputs_and_aliases', standalone_case(matrix, (65537, -32769, 12345),
            matrix_offset=offsets[0], vector_offset=offsets[1], output_offset=offsets[2], segment=segment, seed=1)


def composition_cases(pairs):
    # Earlier cases varied synthetic projection independently of the real
    # vector. Replace it with actual rotated (0,0,distance), without repeats.
    distances = (-65537, -32769, -1, 0, 1, 12345, 65537)
    for label, cell_x, cell_z, yaw, distance, labels, segment in itertools.product(range(7), (0, 9, 19), (0, 9, 19),
            (0, 0x200, 0x600, 0xA00, 0xE00), distances,
            (tuple(range(7)), (6, 2, 5, 1, 4, 0, 3)), (0, 0x80000000, 0xA0000000)):
        euler = ((0, 1, -1, 513, -1025, 4095, -32768)[label], yaw,
                 (0, -513, 1025, -4095, 32767, -1, 1)[label])
        matrix = struct.unpack('<9h', rotation.rotation_bytes(euler, pairs))
        projected, _ = apply_model(matrix, (0, 0, distance))
        yield dict(position.base_case(position=(label * 40960 + cell_x * 2048 + 1024,
                        -label * 2048, cell_z * 2048 + 1024), angle=yaw,
                        distance=distance, projected_x=projected[0], projected_y=projected[1], projected_z=projected[2],
                        labels=labels, segment=segment, mode=label % 2, seed=label, auxiliary_present=False), euler=euler)


class CompositionMachine(rotation.CompositionMachine):
    def __init__(self, bridge, patches=None):
        self.adapter = Cop2Adapter(bridge)
        super().__init__(patches=patches)
        del self.stubs[int(APPLY['address'], 16) & native.MASK]
        self.native_entries = {int(f['address'], 16) & native.MASK: f['function'] for f in FUNCTIONS}
        self.ranges = [(int(f['address'], 16) & native.MASK, f['bytes']) for f in FUNCTIONS]
        if self.stubs:
            raise ValueError('Original world-to-stream functions must have zero stubs.')

    def hook(self, cpu, address, size, unused):
        address &= native.MASK
        if address == int(APPLY['address'], 16) & native.MASK:
            self.entry_counts['ApplyMatrixLV'] += 1
            self.adapter.reset()
            args = [cpu.reg_read(getattr(native.reg, 'UC_MIPS_REG_A' + str(i))) for i in range(3)]
            if args != [grid.MATRIX, grid.VECTOR, grid.VECTOR]:
                raise ValueError('Original in-place vector arguments differ.')
            self.trace.append(('apply', *args, self.read(args[0], 32)))
        if (int(APPLY['address'], 16) & native.MASK) <= address < (int(APPLY['address'], 16) & native.MASK) + APPLY['bytes']:
            handle_cop2(self.adapter, cpu, address)
            return
        super().hook(cpu, address, size, unused)


def negative_controls(bridge, pairs):
    controls = []
    for name, address, original, modified, vector in (
            ('wrong_high_part_scale', 0x80015710, 0x000B58C0, 0x000B5880, (65537, 1, 0)),
            ('skip_negative_high_reflection', 0x80015660, 0x000B5823, 0x000B5821, (-65537, 1, 0))):
        if int.from_bytes(native.h.target(address, 4), 'little') != original:
            raise ValueError('Canonical negative-control word changed: ' + name)
        case = standalone_case(vector=vector)
        actual = ApplyMachine(bridge, {address: struct.pack('<I', modified)}).run(case)
        if actual == standalone_expected(case)[0]:
            raise ValueError('Original instruction fault was not detected: ' + name)
        controls.append({'name': name, 'address': hex(address), 'detected': True, 'scope': 'Private Unicorn memory only.'})
    # Change the original command's sf bit; actual native core arithmetic must
    # still pass its own command model, while the whole helper detects the fault.
    case = standalone_case(matrix=(4093, -17, 23, -1024, 3585, -2001, 177, 801, 3123), vector=(65537, -32769, 12345))
    address = 0x800156F4
    if int.from_bytes(native.h.target(address, 4), 'little') != COMMANDS[1]:
        raise ValueError('Canonical low-part command changed.')
    actual = ApplyMachine(bridge, {address: struct.pack('<I', COMMANDS[0])}).run(case)
    if actual == standalone_expected(case)[0]:
        raise ValueError('Wrong native command shift was not detected.')
    controls.append({'name': 'wrong_low_part_mvmva_shift', 'address': hex(address), 'detected': True,
                     'scope': 'Private Unicorn command word; checked native core is unchanged.'})
    case = next(c for c in composition_cases(pairs) if c['distance'] == 65537 and c['angle'] == 0)
    address = 0x80015748
    if int.from_bytes(native.h.target(address, 4), 'little') != 0x000D68C0:
        raise ValueError('Canonical composed high-part instruction changed.')
    actual = CompositionMachine(bridge, {address: struct.pack('<I', 0x000D6880)}).run(case)
    if actual == rotation.composition_expected(case, pairs)[0]:
        raise ValueError('Composed high-part fault was not detected.')
    controls.append({'name': 'composed_wrong_high_z_scale', 'address': hex(address), 'detected': True,
                     'scope': 'Private Unicorn memory through eleven original functions.'})
    return controls


def verify(destination, executable, runtime):
    dependencies = native.evidence_dependencies('tools/verify_render_gte.py', 'tools/nymashock_gte_bridge.cs',
        'tools/verify_render_rotation.py', 'tools/verify_render_position.py', 'tools/verify_render_stream.py',
        'tools/verify_render_grid.py', 'src/scene/render_context.c', 'src/scene/render_context.h',
        'asm/nonmatchings/psyq/gte/mtx4/ApplyMatrixLV.s')
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in dependencies}
    native.initialize_backend(native.load_program(FUNCTIONS))
    pairs = rotation.table_pairs(native.h)
    bindings = position.canonical_bindings(native.h)
    bridge = NativeGteBridge(executable, runtime, destination.with_suffix('.log'))
    try:
        machine = ApplyMachine(bridge)
        groups, unique, saturation = Counter(), set(), Counter()
        for group, case in standalone_cases():
            initial, pointers = standalone_fixture(case)
            unique.add(hashlib.sha256(bytes(initial) + struct.pack('<3I', *pointers)).hexdigest())
            expected, commands = standalone_expected(case)
            actual = machine.run(case)
            if actual != expected or [entry['output'] for entry in machine.adapter.commands] != commands:
                raise ValueError('Original ApplyMatrixLV fixture differs: ' + repr(case))
            for entry in machine.adapter.commands:
                saturation[str(entry['output']['flags'])] += 1
            groups[group] += 1
            if sum(groups.values()) % 20000 == 0:
                print('ApplyMatrixLV', sum(groups.values()), 'passed', flush=True)
        print('ApplyMatrixLV', sum(groups.values()), 'passed', flush=True)
        composition = CompositionMachine(bridge)
        composed_unique, axes, rectangles = set(), Counter(), Counter()
        for case in composition_cases(pairs):
            buffers, pointers, template, _ = rotation.composition_fixture(case)
            identity = b''.join(name.encode() + bytes(data) for name, data in sorted(buffers.items()))
            identity += template + json.dumps(pointers, sort_keys=True).encode()
            composed_unique.add(hashlib.sha256(identity).hexdigest())
            model, axis, count = rotation.composition_expected(case, pairs)
            actual = composition.run(case)
            if actual != model:
                with destination.with_name(destination.stem + '-composition-failure.json').open('x') as f:
                    json.dump({'case': case, 'expected': model, 'actual': actual}, f, indent=2,
                              default=lambda value: {'bytes_hex': value.hex()})
                raise ValueError('Original native-GTE composition differs; private failure retained.')
            axes[axis] += 1
            rectangles[count] += 1
        composed = sum(axes.values())
        if len(composed_unique) != composed or len(unique) != sum(groups.values()):
            raise ValueError('Duplicate fixtures must be classified before publication.')
        print('native_gte_world_to_stream', composed, 'passed', flush=True)
        controls = negative_controls(bridge, pairs)
        for runner in (machine, composition):
            if bytes(runner.cpu.mem_read(int(rotation.TABLE['address'], 16) & native.MASK, rotation.TABLE['bytes'])) != native.h.target(
                    int(rotation.TABLE['address'], 16), rotation.TABLE['bytes']):
                raise ValueError('Original packed rotation table changed during execution.')
    finally:
        bridge.close()
    if any(hashlib.sha256(p.read_bytes()).hexdigest() != value for p, value in before.items()):
        raise ValueError('Evidence dependency changed during native GTE checks.')
    if (ROOT / native.configure.EXE).read_bytes() != native.h.ROM or native.check_build_current(ROOT) is not True:
        raise ValueError('Canonical build changed during native GTE checks.')
    report = {'status': 'passed_bounded_original_render_native_gte',
        'canonical_executable_sha1': hashlib.sha1(native.h.ROM).hexdigest(), 'original_and_current_build_equal': True,
        'original_behavior_modified': False, 'model_api_calls': 0, 'backend': 'Unicorn ' + native.unicorn.__version__,
        'native_function': APPLY, 'native_cases': len(unique), 'native_runs': sum(groups.values()), 'case_groups': dict(groups),
        'executed_apply_entries': machine.entries, 'explicit_function_stubs': 0,
        'cop2_operations_executed': dict(machine.adapter.counts), 'native_command_flag_counts': dict(saturation),
        'native_gte': {'implementation': 'BizHawk 2.11.1 Nymashock, checked local native Waterbox core',
            'compressed_core_sha256': CORE_SHA256, 'bridge_source_sha256': before[ROOT / 'tools/nymashock_gte_bridge.cs'],
            'compiled_bridge_sha256': hashlib.sha256(Path(executable).read_bytes()).hexdigest(),
            'command_invocations_excluding_identity_self_check': bridge.count, 'identity_self_check': bridge.ready,
            'command_words': [hex(word) for word in COMMANDS], 'inlined_transfer_adapter_registers': 'CR0..4, IR1..3, MAC1..3',
            'stdout_log_sha256': hashlib.sha256(destination.with_suffix('.log').read_bytes()).hexdigest(),
            'stderr_log_sha256': hashlib.sha256(destination.with_name(destination.stem + '-stderr.log').read_bytes()).hexdigest(),
            'full_psx_cpu_timing_checked': False},
        'composition': {'native_cases': composed, 'native_functions': FUNCTIONS,
            'native_function_bytes': sum(f['bytes'] for f in FUNCTIONS),
            'executed_native_entry_counts': dict(composition.entry_counts), 'explicit_function_stubs': 0,
            'cop2_operations_executed': dict(composition.adapter.counts),
            'decision_axes': dict(axes), 'emitted_rectangle_counts': dict(rectangles), 'canonical_virtual_bindings': bindings},
        'negative_controls_detected': controls, 'source_promotions': 0, 'original_feature_groups_accepted': 0,
        'producer_dependencies': [{'path': p.resolve().relative_to(ROOT).as_posix(), 'sha256': value} for p, value in before.items()],
        'scope': 'Original ApplyMatrixLV instructions execute, including long-vector splitting and overlapping buffers. '
                 'Reviewed COP2 transfers invoke actual pinned native MVMVA commands and compare MAC, IR and flags '
                 'with independent arithmetic. Eleven original functions compose lookup, rotation, vector application, '
                 'grid and streaming without function-output contracts. The scoped transfer adapter is explicit; '
                 'Unicorn does not execute the full PS1 CPU, hardware load delays or cycle scheduling. Natural graph '
                 'ownership, scenes, framebuffer and independently reviewed whole-feature acceptance remain open.'}
    with destination.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print(json.dumps({'report': str(destination), 'native_cases': len(unique), 'composition_cases': composed,
                      'native_gte_commands': bridge.count, 'function_stubs': 0, 'negative_controls': len(controls)}), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bridge', type=Path, required=True)
    parser.add_argument('--runtime', required=True, help='Windows path to the pinned local BizHawk 2.11.1 directory.')
    args = parser.parse_args(argv)
    try:
        destination = (ROOT / args.output).resolve()
        if not destination.is_relative_to((ROOT / '.decomp-lab').resolve()) or any(p.exists() for p in (
                destination, destination.with_suffix('.log'), destination.with_name(destination.stem + '-stderr.log'))):
            raise ValueError('Choose new private report and log paths inside .decomp-lab.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        verify(destination, args.bridge.resolve(), args.runtime)
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('[!] ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
