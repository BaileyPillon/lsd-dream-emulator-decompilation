"""Execute the original world-position lookup and compose it with grid streaming.

Five original position functions execute without stubs. The nine-function
composition retains two explicit GTE contracts; rendering and timing remain
separate. Reports contain metadata and require a new private output path.
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
from tools import verify_render_stream as stream

FUNCTIONS = [
    {'function': 'func_8004C158', 'address': '0x8004C158', 'bytes': 104,
     'sha256': 'ed0e88573bebaabe7193558da0ca5155fc928339b799e7ac05147d79ab2ec3ea'},
    {'function': 'func_8004C1C0', 'address': '0x8004C1C0', 'bytes': 424,
     'sha256': 'd82d26562f1a91a9ae77988cfedcf3e0e41b69c558344850c56a6a1d8712933c'},
    {'function': 'func_8004C368', 'address': '0x8004C368', 'bytes': 136,
     'sha256': 'fde21abc879fe53caac48f67490e480a5b4f00661f006583abfdd99a5b9bf25a'},
    {'function': 'func_8004C434', 'address': '0x8004C434', 'bytes': 60,
     'sha256': '20dc014764c03db33c736936d39697ca0578fea09351941f97b1eaf2cce96596'},
    {'function': 'func_8004C470', 'address': '0x8004C470', 'bytes': 280,
     'sha256': '1e8050abf24ead47a7e6009565ee0db7086026203b62b555771812c7343a368a'},
]
ALL_FUNCTIONS = FUNCTIONS + stream.FUNCTIONS
BINDINGS = {0x10C: 0x8004C158, 0x110: 0x8004C1C0,
            0x118: 0x8004C434, 0x11C: 0x8004C470, 0x120: 0x8004C588}
BASES = {**stream.BASES, 'layout': 0x11C000, 'output': 0x11D000, 'auxiliary': 0x11E000}
TRACE_NAMES = {'func_8004C158': ('lookup', 3), 'func_8004C1C0': ('resolve', 3),
               'func_8004C368': ('partition', 3), 'func_8004C434': ('label', 2),
               'func_8004C470': ('world', 2)}
ORIGINS = tuple((index * 0xA000, index * 257 - 700, 0) for index in range(7))
MARKERS = (-32768, -1, 0, 127, 128, 256, 32767)


def signed(value, bits=32):
    return grid.signed(value, bits)


def quotient(value, divisor):
    if divisor == 0:
        raise ValueError('Zero divisor is a separate native trap observation.')
    result = abs(value) // abs(divisor)
    return -result if (value < 0) != (divisor < 0) else result


def base_case(**changes):
    return dict(dict(angle=0x200, x=0, z=0, radius=4, width=8, height=6,
                     distance=12345, projected_x=12289, projected_y=-3456,
                     projected_z=-12289, position=(1024, 0, 1024),
                     labels=tuple(range(7)), origins=ORIGINS, markers=MARKERS,
                     divisor=20, mode=0, segment=0, seed=0,
                     entry='lookup', output_present=True, auxiliary_present=True), **changes)


def canonical_bindings(program):
    records = []
    for offset, address in BINDINGS.items():
        data = program.target(0x800866E8 + offset, 4)
        if int.from_bytes(data, 'little') != address:
            raise ValueError('Original position/grid virtual binding changed: ' + hex(offset))
        records.append({'slot_offset': hex(offset), 'target': hex(address),
                        'slot_sha256': hashlib.sha256(data).hexdigest()})
    return records


def fixture(case):
    if sorted(case['labels']) != list(range(7)):
        raise ValueError('Position fixtures require one native slot per label 0 through 6.')
    if len(case['origins']) != 7 or len(case['markers']) != 7:
        raise ValueError('Seven coordinate records and marker values are required.')
    buffers, pointers, template, _, rotation = stream.fixture(case)
    segment, seed = case['segment'], case['seed']
    for name in ('layout', 'output', 'auxiliary'):
        buffers[name] = bytearray((i * 37 + seed * 91 + BASES[name]) & 255 for i in range(0x80))
        pointers[name] = (BASES[name] + 0x20) | segment
    pointers['position'] = pointers['inner'] + 0x18
    struct.pack_into('<iii', buffers['inner'], 0x38, *map(signed, case['position']))
    native.word(buffers['context'], 0x20 + 0x68, pointers['layout'])
    struct.pack_into('<h', buffers['layout'], 0x20, signed(case['divisor'], 16))
    native.word(buffers['layout'], 0x24, case['mode'])
    for offset, address in BINDINGS.items():
        native.word(buffers['vtable'], 0x20 + offset, address)
    for index, label in enumerate(case['labels']):
        name, base = 'chunk' + str(index), BASES['chunk' + str(index)]
        data = bytearray((i * 37 + seed * 91 + base) & 255 for i in range(0x180))
        struct.pack_into('<hh', data, 0x50, signed(case['markers'][label], 16), label)
        native.word(data, 0x94, (base + 0xC0) | segment)
        struct.pack_into('<iii', data, 0xD8, *map(signed, case['origins'][label]))
        buffers[name] = data
        native.word(buffers['context'], 0x20 + 0xEC + index * 0x1C + 4, (base + 0x20) | segment)
        native.word(buffers['context'], 0x20 + 0xEC + index * 0x1C + 0xC, (base + 0x80) | segment)
    return buffers, pointers, template, rotation


def selected_label(case):
    """Independent half-open horizontal rectangles and ordered height layers."""
    x, y, z = map(signed, case['position'])
    for label, origin in enumerate(case['origins']):
        ox, _, oz = map(signed, origin)
        horizontal = ox <= x < signed(ox + 40960) and oz <= z < signed(oz + 40960)
        upper = -2048 * label
        vertical = not case['mode'] or upper - 2048 < y <= upper
        if horizontal and vertical:
            return label
    return None


def label_pointer(case, pointers, label):
    try:
        index = case['labels'].index(label)
    except ValueError:
        return 0
    return pointers['context'] + 0xEC + index * 0x1C


def resolved_info(case, initial):
    label = selected_label(case)
    if label is None:
        return bytes(initial), 1, None
    x, y, z = map(signed, case['position'])
    ox, oy, oz = map(signed, case['origins'][label])
    value, divisor = signed(case['markers'][label], 16), signed(case['divisor'], 16)
    part = quotient(value, divisor)
    cell_x, cell_z = quotient(signed(x - ox), 2048), quotient(signed(z - oz), 2048)
    result = bytearray(initial)
    struct.pack_into('<bbbb', result, 0, signed(value - part * divisor, 8),
                     signed(part, 8), signed(cell_x, 8), signed(cell_z, 8))
    struct.pack_into('<hhh', result, 4, signed(x - ox - cell_x * 2048 - 1024, 16),
                     signed(y, 16), signed(z - oz - cell_z * 2048 - 1024, 16))
    vx, vz = signed(ox + 20480), signed(oz + 20480)
    struct.pack_into('<iiiiii', result, 12, vx, oy, vz, signed(x - vx), y, signed(z - vz))
    slot = (BASES['context'] + 0x20) | case['segment']
    struct.pack_into('<Ii', result, 36, native.u32(label_pointer(case, {'context': slot}, label)), value)
    return bytes(result), 0, label


def lookup_trace(case, pointers, output, auxiliary):
    trace = [('lookup', pointers['context'], output, auxiliary)]
    if not output:
        return trace
    trace += [('resolve', pointers['context'], output, pointers['position']),
              ('world', pointers['context'], pointers['position'])]
    selected = selected_label(case)
    for label in range(7 if selected is None else selected + 1):
        trace.append(('label', pointers['context'], label))
    if selected is not None:
        trace += [('partition', pointers['context'], output,
                   native.u32(signed(case['markers'][selected], 16))),
                  ('label', pointers['context'], selected)]
    return trace


def expected(case):
    buffers, pointers, _, _ = fixture(case)
    out = pointers['output'] if case['output_present'] else 0
    aux = pointers['auxiliary'] if case['auxiliary_present'] else 0
    entry = case['entry']
    if entry == 'lookup':
        trace = lookup_trace(case, pointers, out, aux)
        if aux:
            native.word(buffers['auxiliary'], 0x20, pointers['position'])
        result = pointers['context'] + 0xBC
        if out:
            data, status, _ = resolved_info(case, buffers['output'][0x20:0x4C])
            buffers['output'][0x20:0x4C] = data
            if status:
                result = 0
    elif entry == 'partition':
        value, divisor = signed(case['value'], 16), signed(case['divisor'], 16)
        part = quotient(value, divisor)
        buffers['output'][0x20:0x22] = bytes((value - part * divisor & 255, part & 255))
        result = native.u32(divisor)
        trace = [('partition', pointers['context'], out, native.u32(value))]
    elif entry == 'label':
        result = label_pointer(case, pointers, signed(case['wanted_label']))
        trace = [('label', pointers['context'], native.u32(case['wanted_label']))]
    else:
        raise ValueError('Unknown position fixture entry.')
    return {name: bytes(data) for name, data in buffers.items()}, native.u32(result), trace


class Machine(native.Machine):
    def __init__(self, entry='lookup', patches=None):
        address = {'lookup': 0x4C158, 'partition': 0x4C368, 'label': 0x4C434}[entry]
        self.entry = entry
        self.entry_counts = Counter()
        self.last_executed_address = None
        super().__init__(start=address, native_functions=FUNCTIONS)
        self.ranges = [(int(f['address'], 16) & native.MASK, f['bytes']) for f in FUNCTIONS]
        for address, data in (patches or {}).items():
            self.cpu.mem_write(address & native.MASK, data)

    def hook(self, cpu, address, size, unused):
        address &= native.MASK
        self.last_executed_address = address
        name = self.native_entries.get(address)
        if name:
            self.entry_counts[name] += 1
            label, count = TRACE_NAMES[name]
            args = [cpu.reg_read(getattr(native.reg, 'UC_MIPS_REG_A' + str(i))) for i in range(count)]
            self.trace.append((label, *args))
        if not any(start <= address < start + size for start, size in self.ranges):
            raise ValueError('Execution escaped the five reviewed position functions.')

    def run(self, case):
        if case['entry'] != self.entry:
            raise ValueError('Fixture and native entry differ.')
        buffers, pointers, _, _ = fixture(case)
        cpu, self.trace, self.last_executed_address = self.cpu, [], None
        for name, data in buffers.items():
            cpu.mem_write(BASES[name], bytes(data))
        guard = bytes([0xC9]) * 0x400
        cpu.mem_write(native.STACK - 0x300, guard)
        saved = [native.u32(0xAD000000 + i * 0x10203) for i in range(len(native.SAVED))]
        for register, value in zip(native.SAVED, saved):
            cpu.reg_write(register, value)
        out = pointers['output'] if case['output_present'] else 0
        auxiliary = pointers['auxiliary'] if case['auxiliary_present'] else 0
        a1 = native.u32(case['wanted_label']) if self.entry == 'label' else out
        a2 = native.u32(signed(case['value'], 16)) if self.entry == 'partition' else auxiliary
        for register, value in ((native.reg.UC_MIPS_REG_SP, native.STACK),
                (native.reg.UC_MIPS_REG_GP, 0x8008A808), (native.reg.UC_MIPS_REG_RA, native.END),
                (native.reg.UC_MIPS_REG_A0, pointers['context']),
                (native.reg.UC_MIPS_REG_A1, a1), (native.reg.UC_MIPS_REG_A2, a2)):
            cpu.reg_write(register, value)
        cpu.emu_start(self.start, native.END, count=12000)
        if (cpu.reg_read(native.reg.UC_MIPS_REG_PC) != native.END or
                cpu.reg_read(native.reg.UC_MIPS_REG_SP) != native.STACK or
                cpu.reg_read(native.reg.UC_MIPS_REG_GP) != 0x8008A808 or
                cpu.reg_read(native.reg.UC_MIPS_REG_RA) != native.END or
                [cpu.reg_read(r) for r in native.SAVED] != saved or
                bytes(cpu.mem_read(native.STACK - 0x300, 0x100)) != guard[:0x100] or
                bytes(cpu.mem_read(native.STACK, 0x100)) != guard[0x300:]):
            raise ValueError('Position lookup violated guarded stack or saved ABI.')
        return ({name: bytes(cpu.mem_read(BASES[name], len(data))) for name, data in buffers.items()},
                cpu.reg_read(native.reg.UC_MIPS_REG_V0), self.trace)


def cases():
    permutations = (tuple(range(7)), (6, 2, 5, 1, 4, 0, 3))
    segments = (0, 0x80000000, 0xA0000000)
    for slot, dx, dz, mode, labels, segment in itertools.product(range(7),
            (-1, 0, 1, 1023, 1024, 2047, 2048, 40959, 40960),
            (-1, 0, 1, 1023, 40959, 40960), (0, 1), permutations, segments):
        yield 'horizontal_boundaries', base_case(position=(slot * 40960 + dx, -slot * 2048, dz),
                                                mode=mode, labels=labels, segment=segment)
    for slot, delta, mode, overlap, labels, segment in itertools.product(range(7),
            (1, 0, -1, -2047, -2048, -2049), (0, 1), (False, True), permutations, segments):
        origins = tuple((0, i * 257 - 700, 0) for i in range(7)) if overlap else ORIGINS
        yield 'height_layers_and_overlap', base_case(position=(origins[slot][0] + 1024, -slot * 2048 + delta, 1024),
                                                    origins=origins, mode=mode, labels=labels, segment=segment)
    for present, auxiliary, position, segment in itertools.product((False, True), (False, True),
            ((1024, 0, 1024), (-1, 0, -1), (1024, -2147483648, 1024)), segments):
        yield 'cached_and_missing_lookup', base_case(output_present=present, auxiliary_present=auxiliary,
                                                   position=position, segment=segment)
    for value, divisor, segment in itertools.product(
            (-32768, -32767, -129, -128, -127, -1, 0, 1, 127, 128, 129, 32766, 32767),
            (-32768, -32767, -129, -128, -7, -1, 1, 7, 127, 128, 32767), segments):
        yield 'signed_partition', base_case(entry='partition', value=value, divisor=divisor, segment=segment)
    for wanted, labels, segment in itertools.product(
            (-32769, -32768, -1, *range(9), 32767, 65536, 2147483647, -2147483648), permutations, segments):
        yield 'label_scan_and_miss', base_case(entry='label', wanted_label=wanted, labels=labels, segment=segment)
    for origin, delta, segment in itertools.product((-2147483648, 2147442688, 2147483647),
            (0, 1, 40959, 40960), segments):
        origins = ((origin, -700, origin),) + ORIGINS[1:]
        yield 'signed_world_wrap', base_case(origins=origins,
            position=(signed(origin + delta), 0, signed(origin + delta)), segment=segment)


def composition_cases():
    for label, cell_x, cell_z, angle, projection, labels, segment in itertools.product(
            range(7), (0, 9, 19), (0, 9, 19), (0, 0x200, 0x600, 0xA00, 0xE00),
            ((-12289, 12289), (0, 0), (12289, -12289)),
            (tuple(range(7)), (6, 2, 5, 1, 4, 0, 3)), (0, 0x80000000, 0xA0000000)):
        yield base_case(position=(label * 40960 + cell_x * 2048 + 1024,
                                 -label * 2048, cell_z * 2048 + 1024),
                        angle=angle, projected_x=projection[0], projected_z=projection[1],
                        labels=labels, segment=segment, mode=label % 2, seed=label,
                        auxiliary_present=False)


def composition_expected(case):
    buffers, pointers, template, _ = fixture(case)
    info, status, _ = resolved_info(case, bytes([0xC9]) * 44)
    if status:
        raise ValueError('The composition fixtures require a resolved world slot.')
    derived = dict(case, x=signed(info[2], 8), z=signed(info[3], 8))
    model = stream.expected(derived)
    # Reuse independent scalar/rectangle models only for fields these functions
    # write. The original lookup's complete fixture graph remains guarded.
    context = buffers['context']
    context[0x9C:0xDC] = model[0]['context'][0x9C:0xDC]
    trace = lookup_trace(case, pointers, grid.INFO, 0)
    for entry in model[1][1:]:
        if entry[0] == 'build':
            before_build = bytearray(fixture(case)[0]['context'])
            before_build[0x9C:0xA8] = entry[2][0x9C:0xA8]
            entry = ('build', entry[1], bytes(before_build), entry[3])
        trace.append(entry)
    return ({name: bytes(data) for name, data in buffers.items()}, trace,
            template, info, model[4]), model[5], model[6]


class CompositionMachine(grid.Machine):
    def __init__(self, patches=None):
        super().__init__()
        del self.stubs[grid.LOOKUP]
        del self.stubs[native.h.symbols['func_8004C93C'] & native.MASK]
        self.native_entries = {int(f['address'], 16) & native.MASK: f['function'] for f in ALL_FUNCTIONS}
        self.ranges = [(int(f['address'], 16) & native.MASK, f['bytes']) for f in ALL_FUNCTIONS]
        for address, data in (patches or {}).items():
            self.cpu.mem_write(address & native.MASK, data)

    def hook(self, cpu, address, size, unused):
        address &= native.MASK
        name = self.native_entries.get(address)
        if name:
            self.entry_counts[name] += 1
            args = [cpu.reg_read(getattr(native.reg, 'UC_MIPS_REG_A' + str(i))) for i in range(4)]
            if name in TRACE_NAMES:
                label, count = TRACE_NAMES[name]
                self.trace.append((label, *args[:count]))
            elif name == 'func_8004C93C':
                self.trace.append(('build', args[0], self.read(BASES['context'], len(self.buffers['context'])),
                                   self.read(grid.MATRIX, 32)))
            elif name == 'func_8004CAF0':
                stack = cpu.reg_read(native.reg.UC_MIPS_REG_SP) & native.MASK
                self.trace.append(('row', *args, *struct.unpack('<IIII', self.read(stack + 16, 16))))
            elif name == 'func_8004C588':
                self.trace.append(('selector', *args[:2]))
        if address in self.stubs:
            return super().hook(cpu, address, size, unused)
        if not any(start <= address < start + length for start, length in self.ranges):
            raise ValueError('Execution escaped the nine reviewed renderer/position functions.')

    def run(self, case):
        self.case, self.trace = case, []
        self.buffers, self.pointers, template, self.rotation = fixture(case)
        cpu = self.cpu
        for name, data in self.buffers.items():
            cpu.mem_write(BASES[name], bytes(data))
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
            raise ValueError('Position/render composition violated guarded stack or saved ABI.')
        return ({name: self.read(BASES[name], len(data)) for name, data in self.buffers.items()},
                self.trace, self.read(grid.TEMPLATE, 32), self.read(grid.INFO, 44), self.read(grid.MATRIX, 32))


def control_instruction(function, predicate, last=False):
    record = next(f for f in FUNCTIONS if f['function'] == function)
    address = int(record['address'], 16)
    data = native.h.target(address, record['bytes'])
    matches = [(address + offset, struct.unpack_from('<I', data, offset)[0])
               for offset in range(0, len(data), 4) if predicate(struct.unpack_from('<I', data, offset)[0])]
    if not matches:
        raise ValueError('Native control instruction not found: ' + function)
    return matches[-1 if last else 0]


def negative_controls():
    specs = [
        ('unsigned_partition', 'func_8004C368', lambda w: w & 0xFC00003F == 0x1A,
         lambda w: w + 1, base_case(entry='partition', value=-32768, divisor=7), False),
        ('wrong_local_cell_bias', 'func_8004C1C0', lambda w: w >> 26 == 9 and w & 0xFFFF == 0xFC00,
         lambda w: w + 1, base_case(), False),
        ('inclusive_horizontal_upper_bound', 'func_8004C470', lambda w: w >> 26 == 13 and w & 0xFFFF == 0xA000,
         lambda w: w + 1, base_case(position=(40960, 0, 1024)), False),
        ('wrong_slot_stride', 'func_8004C434', lambda w: w >> 26 == 9 and w & 0xFFFF == 0x1C,
         lambda w: w - 4, base_case(entry='label', wanted_label=6), False),
        ('reverse_lookup_result', 'func_8004C158', lambda w: w >> 26 in (4, 5) and w >> 21 & 31 == 2 and w >> 16 & 31 == 0,
         lambda w: w ^ (1 << 26), base_case(), True),
    ]
    records = []
    for name, function, predicate, change, case, last in specs:
        address, original = control_instruction(function, predicate, last)
        modified = change(original)
        fault = None
        try:
            observed = Machine(case['entry'], {address: struct.pack('<I', modified)}).run(case)
            detected = observed != expected(case)
        except (ValueError, native.unicorn.UcError) as error:
            detected, fault = True, str(error)
        if not detected:
            raise ValueError('Native position negative control was not detected: ' + name)
        records.append({'name': name, 'address': hex(address), 'original_word': hex(original),
                        'modified_word': hex(modified), 'case': case, 'detected': True,
                        'execution_fault': fault, 'scope': 'Private Unicorn memory only.'})
    # One original lookup mutation must also be caught through the full pipeline.
    address, original = control_instruction('func_8004C1C0', lambda w: w >> 26 == 9 and w & 0xFFFF == 0xFC00)
    case = next(composition_cases())
    observed = CompositionMachine({address: struct.pack('<I', original + 1)}).run(case)
    if observed == composition_expected(case)[0]:
        raise ValueError('Composed lookup/output control was not detected.')
    records.append({'name': 'composed_local_cell_bias', 'address': hex(address),
                    'original_word': hex(original), 'modified_word': hex(original + 1),
                    'detected': True, 'scope': 'Private Unicorn memory only.'})
    return records


def division_traps():
    records = []
    for value in (0, -32768, 32767):
        machine = Machine('partition')
        try:
            machine.run(base_case(entry='partition', value=value, divisor=0))
        except native.unicorn.UcError as error:
            reported_pc = machine.cpu.reg_read(native.reg.UC_MIPS_REG_PC)
            # Unicorn reports PC zero after the exception. The instruction hook
            # identifies the actual original BREAK reached before that reset.
            address = machine.last_executed_address
            if address is None:
                raise ValueError('No executed instruction was recorded before the exception.') from error
            instruction = int.from_bytes(machine.cpu.mem_read(address, 4), 'little')
            if (error.errno != native.unicorn.UC_ERR_EXCEPTION or
                    address != 0x4C384 or instruction != 0x0007000D):
                raise ValueError('Zero division did not reach the native BREAK instruction.') from error
            records.append({'value': value, 'divisor': 0, 'native_break_address': hex(address),
                            'instruction': hex(instruction), 'reported_pc_after_exception': hex(reported_pc),
                            'observation': 'Original BREAK 7 reached in the pre-execution instruction hook.',
                            'observed_exception': str(error)})
        else:
            raise ValueError('Expected original division-by-zero trap was absent.')
    return records


def verify(destination):
    dependencies = native.evidence_dependencies('tools/verify_render_position.py',
        'tools/verify_render_grid.py', 'tools/verify_render_stream.py',
        'src/scene/render_context.c', 'src/scene/render_context.h')
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in dependencies}
    native.initialize_backend(native.load_program(ALL_FUNCTIONS))
    bindings = canonical_bindings(native.h)
    machines = {entry: Machine(entry) for entry in ('lookup', 'partition', 'label')}
    groups, outcomes = Counter(), Counter()
    unique_inputs = set()
    previous = None
    for group, case in cases():
        unique_inputs.add(json.dumps(case, sort_keys=True))
        if group != previous:
            if previous:
                print(previous, groups[previous], 'passed', flush=True)
            previous = group
        model = expected(case)
        observed = machines[case['entry']].run(case)
        if observed != model:
            failure = destination.with_name(destination.stem + '-failure.json')
            with failure.open('x', encoding='utf-8') as f:
                json.dump({'case': case, 'expected_result': model[1], 'observed_result': observed[1],
                           'expected_trace': model[2], 'observed_trace': observed[2],
                           'different_buffers': [name for name in model[0] if observed[0][name] != model[0][name]]}, f, indent=2,
                          default=lambda value: {'bytes_hex': value.hex()})
            raise ValueError('Original position/model disagreement; see ' + failure.name)
        groups[group] += 1
        if case['entry'] == 'lookup':
            outcomes['cached_without_output' if not case['output_present'] else
                     'no_world_slot' if selected_label(case) is None else 'resolved'] += 1
    print(previous, groups[previous], 'passed', flush=True)
    composition = CompositionMachine()
    composed_cases, axes, rectangles = 0, Counter(), Counter()
    for case in composition_cases():
        model, axis, count = composition_expected(case)
        observed = composition.run(case)
        if observed != model:
            failure = destination.with_name(destination.stem + '-composition-failure.json')
            with failure.open('x', encoding='utf-8') as f:
                json.dump({'case': case, 'expected_trace': model[1], 'observed_trace': observed[1],
                           'different_buffers': [name for name in model[0] if observed[0][name] != model[0][name]],
                           'template_equal': model[2] == observed[2], 'info_equal': model[3] == observed[3],
                           'matrix_equal': model[4] == observed[4]}, f, indent=2,
                          default=lambda value: {'bytes_hex': value.hex()})
            raise ValueError('Original composition/model disagreement; see ' + failure.name)
        composed_cases += 1
        axes[axis] += 1
        rectangles[count] += 1
    print('world_to_stream_composition', composed_cases, 'passed', flush=True)
    controls = negative_controls()
    traps = division_traps()
    if any(hashlib.sha256(p.read_bytes()).hexdigest() != value for p, value in before.items()):
        raise ValueError('Evidence dependency changed during position checks.')
    if (ROOT / native.configure.EXE).read_bytes() != native.h.ROM or native.check_build_current(ROOT) is not True:
        raise ValueError('Canonical build changed during position checks.')
    counts = Counter()
    for machine in machines.values():
        counts.update(machine.entry_counts)
    report = {'status': 'passed_bounded_original_render_position',
        'canonical_executable_sha1': hashlib.sha1(native.h.ROM).hexdigest(),
        'original_and_current_build_equal': True, 'original_behavior_modified': False,
        'model_api_calls': 0, 'backend': 'Unicorn ' + native.unicorn.__version__,
        'native_cases': len(unique_inputs), 'native_runs': sum(groups.values()),
        'repeated_input_runs': sum(groups.values()) - len(unique_inputs),
        'case_groups': dict(groups), 'case_group_count_scope': 'Native invocations, including repeated inputs.',
        'lookup_outcomes': dict(outcomes),
        'native_functions': FUNCTIONS, 'executed_native_entry_counts': dict(counts),
        'canonical_virtual_bindings': bindings, 'explicit_stubs': 0,
        'composition': {'native_cases': composed_cases, 'native_functions': ALL_FUNCTIONS,
                        'executed_native_entry_counts': dict(composition.entry_counts),
                        'decision_axes': dict(axes), 'emitted_rectangle_counts': dict(rectangles),
                        'explicit_stubs': 2, 'stub_contracts': ['RotMatrix', 'ApplyMatrixLV']},
        'negative_controls_detected': controls, 'original_division_by_zero_observations': traps,
        'source_promotions': 0, 'original_feature_groups_accepted': 0,
        'producer_dependencies': [{'path': p.resolve().relative_to(ROOT).as_posix(), 'sha256': value}
                                  for p, value in before.items()],
        'scope': 'Five original position functions with zero stubs, fixture-owned valid seven-slot records, '
                 'horizontal and height-layer boundaries, overlap priority, cache/missing paths, '
                 'signed partition, label misses and address aliases. Whole guarded buffers, return values, '
                 'native call order/arguments and saved ABI are compared. Natural level ownership, '
                 'invalid object graphs, GTE, framebuffer and PS1 timing remain separate. '
                 'The nine-function world-to-stream composition executes real position lookup with '
                 'two GTE contracts. Complete matrix/info/template outputs, native call traces and '
                 'guarded inputs are checked against the independent scalar and rectangle models.'}
    with destination.open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print(json.dumps({'report': str(destination), 'native_cases': report['native_cases'],
                      'native_runs': report['native_runs'],
                      'composition_cases': composed_cases, 'negative_controls': len(controls),
                      'original_division_traps': len(traps), 'lookup_stubs': 0, 'composition_stubs': 2}), flush=True)


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
