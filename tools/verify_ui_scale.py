"""Check the original sprite scaling leaf, including overlapping input records.

The 560-byte function remains assembly. This local native audit checks signed
fixed-point arithmetic, read/store order and incoming-register behavior; it
does not accept menu rendering, a C candidate or any whole feature group.
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

FUNCTIONS = [{'function': 'func_8004441C', 'address': '0x8004441C', 'bytes': 560,
              'sha256': 'da711212afcc5d37cc0dc8f15ad0493cbfee5bda9f6fd5d3deffe3b6c6db729c'}]
OBJECT_BUFFER, INPUT_BUFFER = 0x110000, 0x111000
OBJECT, INPUT = OBJECT_BUFFER + 0x20, INPUT_BUFFER + 0x20
BUFFER_SIZE = 0xC0
SHORTS = (-32768, -32767, -30000, -4096, -2, -1, 0, 1, 2, 4096, 29999, 30000, 30001, 32767)
INCOMING = ((0, 0), (4096, 4096), (0x7FFF, 0x8000),
            (0x7FFFFFFF, 0x80000000), (0xFFFFFFFF, 0xFFFF))


def signed16(value):
    value &= 0xFFFF
    return value if value < 0x8000 else value - 0x10000


def trunc_div(numerator, denominator):
    result = abs(numerator) // abs(denominator)
    return result if (numerator < 0) == (denominator < 0) else -result


def fixtures(case):
    seed = case.get('seed', 0)
    buffers = [bytearray((i * 37 + seed * 91 + base) & 255 for i in range(BUFFER_SIZE))
               for base in (0xC7, 0xD3)]
    struct.pack_into('<hh', buffers[0], 0x20 + 0x60, *case['old'])
    alias = case.get('alias_offset')
    pointer = INPUT if alias is None else OBJECT + alias
    target = buffers[1] if alias is None else buffers[0]
    struct.pack_into('<hhhh', target, 0x20 if alias is None else 0x20 + alias,
                     *case['fractions'])
    return tuple(map(bytes, buffers)), pointer


def expected(case, snapshot_y_denominator=False):
    initial, pointer = fixtures(case)
    buffers = list(map(bytearray, initial))
    events, paths = [], []

    def read(address):
        events.append(['read', address, 2])
        base, data = (OBJECT_BUFFER, buffers[0]) if OBJECT_BUFFER <= address < OBJECT_BUFFER + BUFFER_SIZE else (INPUT_BUFFER, buffers[1])
        return struct.unpack_from('<h', data, address - base)[0]

    def write(address, value):
        events.append(['write', address, 2])
        struct.pack_into('<h', buffers[0], address - OBJECT_BUFFER, signed16(value))

    negative_x = read(pointer) < 0 or read(pointer + 2) < 0
    negative_y = read(pointer + 4) < 0 or read(pointer + 6) < 0
    ratios = list(case.get('incoming', INCOMING[0]))
    denominators = []
    for axis in range(2):
        denominator = read(pointer + axis * 4 + 2)
        denominators.append(denominator)
        if denominator:
            numerator = read(pointer + axis * 4)
            quotient = trunc_div(numerator, denominator)
            remainder = numerator - quotient * denominator
            ratios[axis] = (quotient << 12) + trunc_div(remainder << 12, denominator)

    if case['mode']:
        for axis in range(2):
            denominator = denominators[axis]
            if axis == 1:
                reread = read(pointer + 6)
                if not snapshot_y_denominator:
                    denominator = reread
            if denominator == 0:
                value, path = 4096, 'replace_zero_denominator'
            else:
                value = signed16(ratios[axis])
                path = 'replace_upper_clamp' if value >= 30001 else 'replace_ratio'
                value = min(value, 30000)
            write(OBJECT + 0x60 + axis * 2, value)
            paths.append(path)
    else:
        for axis, negative in enumerate((negative_x, negative_y)):
            old = read(OBJECT + 0x60 + axis * 2)
            if old + signed16(ratios[axis]) < 30001:
                value, path = old + ratios[axis], 'increment_sum'
            else:
                value = 1 if negative else 30000
                path = 'increment_negative_fallback' if negative else 'increment_upper_clamp'
            write(OBJECT + 0x60 + axis * 2, value)
            paths.append(path)
    return tuple(map(bytes, buffers)), events, paths


def cases():
    for value in range(65536):
        numerator = signed16(value)
        for mode in (0, 1):
            yield 'complete_numerator_word_sweep', {
                'old': (4096, -8192), 'mode': mode,
                'fractions': (numerator, 7, signed16(~value), -13)}
        yield 'complete_denominator_word_sweep', {
            'old': (29999, -32768), 'mode': value & 1,
            'fractions': (32767, numerator, -32768, signed16(-numerator)),
            'incoming': INCOMING[3]}
    for numerator, denominator, old, mode in itertools.product(
            SHORTS, SHORTS, ((0, 0), (-32768, 32767), (4096, 4096),
                             (29999, 30000), (30000, 30001)), (0, 1, -1)):
        for incoming in (INCOMING if numerator == 0 or denominator == 0 else INCOMING[:1]):
            yield 'signed_edges_and_incoming_registers', {
                'old': old, 'mode': mode, 'fractions': (numerator, denominator, denominator, numerator),
                'incoming': incoming}
    fractions = ((1, 1, 7, 0), (0, 1, 7, 4096), (7, 0, 0, 7),
                 (-1, -1, -32768, 1), (30001, 4096, 32767, -1),
                 (0, 0, 0, 0), (1, 7, -1, 13), (32767, 1, -32768, -1))
    for alias, values, mode, incoming, seed, segment in itertools.product(
            (-2, 0, 0x54, 0x56, 0x58, 0x5A, 0x5C, 0x5E, 0x60, 0x62, 0x64, 0x66),
            fractions, (0, 1, -1), (INCOMING[1], INCOMING[3]), range(2), (0, 0x80000000)):
        yield 'overlapping_inputs_and_segment_aliases', {
            'old': (-32768, 30000), 'mode': mode, 'fractions': values,
            'incoming': incoming, 'seed': seed, 'segment': segment, 'alias_offset': alias}


class Machine(native.Machine):
    def __init__(self, code=None):
        self.entry_counts, self.events = Counter(), []
        self.pending_store = None
        super().__init__(code=code, start=0x4441C, native_functions=FUNCTIONS)
        body = native.h.target(0x8004441C, 560) if code is None else code
        self.memory_instructions = {}
        for offset in range(0, len(body), 4):
            word = struct.unpack_from('<I', body, offset)[0]
            if word >> 26 in (0x21, 0x29):
                immediate = signed16(word)
                self.memory_instructions[self.start + offset] = (
                    word >> 26, getattr(native.reg, 'UC_MIPS_REG_' + str((word >> 21) & 31)),
                    getattr(native.reg, 'UC_MIPS_REG_' + str((word >> 16) & 31)), immediate)

    def hook(self, cpu, address, size, unused):
        if self.pending_store is not None:
            location, value = self.pending_store
            if int.from_bytes(cpu.mem_read(location, 2), 'little') != value:
                raise ValueError('Observed UI halfword store did not commit.')
            self.pending_store = None
        address &= native.MASK
        name = self.native_entries.get(address)
        if name:
            self.entry_counts[name] += 1
            self.executed_native_functions.add(name)
        instruction = self.memory_instructions.get(address)
        if instruction is not None:
            operation, base, source, immediate = instruction
            location = (cpu.reg_read(base) + immediate) & native.MASK
            self.events.append(['read' if operation == 0x21 else 'write', location, 2])
            if operation == 0x29:
                self.pending_store = location, cpu.reg_read(source) & 0xFFFF

    def run(self, case):
        buffers, pointer = fixtures(case)
        cpu = self.cpu
        for address, data in zip((OBJECT_BUFFER, INPUT_BUFFER), buffers):
            cpu.mem_write(address, data)
        stack = bytes((i * 73 + 0x91) & 255 for i in range(0x80))
        cpu.mem_write(native.STACK - 0x40, stack)
        for index in range(1, 32):
            cpu.reg_write(getattr(native.reg, 'UC_MIPS_REG_' + str(index)),
                          native.u32(0xCD000000 + index * 0x10403))
        saved = [cpu.reg_read(register) for register in native.SAVED]
        segment = case.get('segment', 0)
        incoming = case.get('incoming', INCOMING[0])
        for register, value in ((native.reg.UC_MIPS_REG_SP, native.STACK),
                (native.reg.UC_MIPS_REG_GP, 0x8008A808), (native.reg.UC_MIPS_REG_RA, native.END),
                (native.reg.UC_MIPS_REG_A0, OBJECT | segment),
                (native.reg.UC_MIPS_REG_A1, native.u32(case['mode'])),
                (native.reg.UC_MIPS_REG_A2, pointer | segment),
                (native.reg.UC_MIPS_REG_T1, native.u32(incoming[0])),
                (native.reg.UC_MIPS_REG_T2, native.u32(incoming[1]))):
            cpu.reg_write(register, value)
        self.events, self.pending_store = [], None
        cpu.emu_start(self.start, native.END, count=250)
        if (cpu.reg_read(native.reg.UC_MIPS_REG_PC) != native.END or
                cpu.reg_read(native.reg.UC_MIPS_REG_SP) != native.STACK or
                cpu.reg_read(native.reg.UC_MIPS_REG_GP) != 0x8008A808 or
                cpu.reg_read(native.reg.UC_MIPS_REG_RA) != native.END or
                [cpu.reg_read(register) for register in native.SAVED] != saved or
                bytes(cpu.mem_read(native.STACK - 0x40, len(stack))) != stack or
                self.pending_store is not None):
            raise ValueError('Original UI scale ABI/unused stack contract failed: ' + repr({
                'fixture': case, 'pc': hex(cpu.reg_read(native.reg.UC_MIPS_REG_PC)),
                'sp': hex(cpu.reg_read(native.reg.UC_MIPS_REG_SP)),
                'gp': hex(cpu.reg_read(native.reg.UC_MIPS_REG_GP)),
                'ra': hex(cpu.reg_read(native.reg.UC_MIPS_REG_RA)),
                'saved_before': saved,
                'saved_after': [cpu.reg_read(register) for register in native.SAVED],
                'stack_changed': bytes(cpu.mem_read(native.STACK - 0x40, len(stack))) != stack}))
        return tuple(bytes(cpu.mem_read(address, len(data)))
                     for address, data in zip((OBJECT_BUFFER, INPUT_BUFFER), buffers)), self.events


def verify(destination):
    dependencies = native.evidence_dependencies('tools/verify_ui_scale.py',
        'src/menu/ui_sprite.c', 'src/menu/ui_sprite.h', 'config/symbols.txt',
        'asm/nonmatchings/menu/ui_sprite/func_8004441C.s')
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    native.initialize_backend(native.load_program(FUNCTIONS))
    if int.from_bytes(native.h.target(0x8006F30C, 4), 'little') != 0x8004441C:
        raise ValueError('Original UI sprite vtable scale slot changed.')
    machine, groups, paths = Machine(), Counter(), Counter()
    alias_changes, witness = 0, None
    for group, case in cases():
        reference = expected(case)
        if machine.run(case) != reference[:2]:
            raise ValueError('Original scale/reference disagreement: ' + repr(case))
        groups[group] += 1
        paths.update(reference[2])
        if case.get('alias_offset') is not None and case['mode'] and reference[0] != expected(case, True)[0]:
            alias_changes += 1
            if witness is None:
                witness = {'fixture': case,
                    'original_scales': list(struct.unpack_from('<hh', reference[0][0], 0x80)),
                    'snapshot_scales': list(struct.unpack_from('<hh', expected(case, True)[0][0], 0x80))}
        if sum(groups.values()) % 32768 == 0:
            print(json.dumps({'native_cases_checked': sum(groups.values())}), flush=True)
    if witness is None:
        raise ValueError('Aliased denominator observation was not exercised.')
    original = native.h.target(0x8004441C, 560)
    controls = []
    for name, address, old, new, case in (
        ('cached_y_denominator', 0x800445A0, 0x84C20006, 0x00801021,
         {'old': (0, 0), 'mode': 1, 'fractions': (1, 1, 7, 0),
          'incoming': (0, 0x1234), 'alias_offset': 0x5A}),
        ('incoming_x_ratio_zeroed', 0x8004442C, 0, 0x00004821,
         {'old': (100, 100), 'mode': 0, 'fractions': (1, 0, 1, 1), 'incoming': (7, 0)}),
        ('accepted_x_addition_subtracted', 0x80044600, 0x01241021, 0x01241023,
         {'old': (100, 100), 'mode': 0, 'fractions': (1, 1, 1, 1)}),
        ('maximum_replace_clamp_incremented', 0x80044598, 0x34037530, 0x34037531,
         {'old': (0, 0), 'mode': 1, 'fractions': (30001, 4096, 1, 1)})):
        code = bytearray(original)
        offset = address - 0x8004441C
        if struct.unpack_from('<I', code, offset)[0] != old:
            raise ValueError('UI control instruction changed: ' + name)
        struct.pack_into('<I', code, offset, new)
        result = Machine(bytes(code)).run(case)
        reference = expected(case)
        if result[0] == reference[0]:
            raise ValueError('UI output negative control was not detected: ' + name)
        controls.append({'name': name, 'address': hex(address), 'fixture': case,
                         'output_difference_detected': True, 'scope': 'Private Unicorn memory only.'})
    if ((ROOT / native.configure.ROM).read_bytes() != native.h.ROM or
            (ROOT / native.configure.EXE).read_bytes() != native.h.ROM or
            native.check_build_current(ROOT) is not True or
            any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path, digest in before.items())):
        raise ValueError('Source or canonical build changed during UI verification.')
    report = {'status': 'passed_bounded_original_ui_scale',
        'canonical_executable_sha1': hashlib.sha1(native.h.ROM).hexdigest(),
        'original_and_current_build_equal': True, 'original_behavior_modified': False,
        'model_api_calls': 0, 'backend': 'Unicorn ' + native.unicorn.__version__,
        'native_cases': sum(groups.values()), 'case_groups': dict(groups),
        'decision_paths': dict(paths), 'native_functions': FUNCTIONS,
        'executed_native_entry_counts': dict(machine.entry_counts), 'explicit_stubs': 0,
        'observation_method': 'Decode executed LH/SH instructions; check each SH by readback at the next instruction. No Unicorn memory-write hook.',
        'overlapping_cases_changed_by_caching_y_denominator': alias_changes,
        'overlapping_denominator_witness': witness,
        'negative_controls_detected': controls, 'source_promotions': 0,
        'producer_dependencies': [{'path': path.resolve().relative_to(ROOT).as_posix(),
                                   'sha256': digest} for path, digest in before.items()],
        'original_feature_groups_accepted': 0,
        'scope': 'Complete 16-bit numerator sweeps for both axes in both modes; complete '
                 'denominator words with one mode per word; signed edges, incoming T1/T2 '
                 'values for skipped divisions, overlapping inputs and KSEG0 aliases. '
                 'Compare ordered halfword reads/stores, complete guarded buffers, unused '
                 'stack, GP, RA and saved registers. No stubs. This is a MIPS32 functional '
                 'audit, not PS1 load-delay, bus, interrupt, GPU or whole-menu acceptance.'}
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'report': str(destination), 'native_cases': report['native_cases'],
                      'negative_controls': len(controls), 'overlapping_differences': alias_changes,
                      'explicit_stubs': 0, 'passed': True}))


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
