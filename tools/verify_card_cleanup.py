"""Check the original card cleanup call order with one explicit allocator stub.

This executes the original machine code against guarded synthetic buffers.
Allocator side effects are test contracts, not observations of the PS1 heap.
Source matching, physical memory cards and complete feature acceptance are
separate gates. Reports and optional candidate images stay in .decomp-lab.
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

FUNCTION = {'function': 'func_8004F810', 'address': '0x8004F810', 'bytes': 148,
            'sha256': '32814b4159a6e0b553ca1dfc0b665501ddcd75f5dd8c1f3de0dee675ec3c79e0'}
BASES = {'object': 0x100000, 'table_a': 0x101000, 'table_b': 0x102000}
LENGTHS = {'object': 0x100, 'table_a': 0x100, 'table_b': 0x100}
OFFSET = 0x40
MAX_ENTRIES = 8
BASE_CASE = dict(count=2, present=True, segment=0, seed=0, pattern='distinct',
                 buffer_null=False, mutations=())


def put_word(data, offset, value):
    struct.pack_into('<I', data, offset, value & 0xFFFFFFFF)


def get_count(buffers):
    return struct.unpack_from('<i', buffers['object'], OFFSET + 0x2C)[0]


def pointers(case):
    return {name: (address + OFFSET) | case['segment'] for name, address in BASES.items()}


def validate_case(case):
    if (case['segment'] not in (0, 0x80000000, 0xA0000000)
            or not -(1 << 31) <= case['count'] <= MAX_ENTRIES
            or case['seed'] not in (0, 1)
            or case['pattern'] not in ('distinct', 'nulls', 'duplicates', 'mixed')):
        raise ValueError('Cleanup case exceeds the bounded fixture.')
    for call, field, value in case['mutations']:
        if (not 1 <= call <= MAX_ENTRIES + 2
                or field not in ('count', 'table', 'table_a_1', 'table_b_1')
                or field == 'count' and not -1 <= value <= MAX_ENTRIES
                or field == 'table' and value not in ('table_a', 'table_b')
                or field.endswith('_1') and not isinstance(value, int)):
            raise ValueError('Cleanup mutation exceeds its explicit contract.')


def fixtures(case):
    validate_case(case)
    buffers = {name: bytearray((i * 37 + case['seed'] * 73 + 0xD7) & 255
                              for i in range(length)) for name, length in LENGTHS.items()}
    ptrs = pointers(case)
    put_word(buffers['object'], OFFSET + 0x2C, case['count'])
    put_word(buffers['object'], OFFSET + 0x38, ptrs['table_a'] if case['present'] else 0)
    put_word(buffers['object'], OFFSET + 0x3C,
             0 if case['buffer_null'] else 0x109040 | case['segment'])
    for name, address in (('table_a', 0x108000), ('table_b', 0x10A000)):
        for index in range(MAX_ENTRIES):
            value = (address + index * 0x20) | case['segment']
            if case['pattern'] == 'nulls' or case['pattern'] == 'mixed' and index % 3 == 0:
                value = 0
            elif case['pattern'] == 'duplicates' or case['pattern'] == 'mixed' and index % 3 == 1:
                value = (address + 0x40) | case['segment']
            put_word(buffers[name], OFFSET + index * 4, value)
    return buffers


def contract_writes(case, call):
    """Return only the allocator stub's declared writes after a numbered call."""
    ptrs = pointers(case)
    writes = []
    for after, field, value in case['mutations']:
        if after != call:
            continue
        if field == 'count':
            writes.append(('object', OFFSET + 0x2C, value))
        elif field == 'table':
            writes.append(('object', OFFSET + 0x38, ptrs[value]))
        else:
            writes.append((field[:-2], OFFSET + 4, value))
    return writes


def expected(case):
    """Model ordered releases, dynamic table/count reads and the final clear."""
    buffers = fixtures(case)
    trace = []

    def pointer():
        return struct.unpack_from('<I', buffers['object'], OFFSET + 0x38)[0]

    def release(address):
        trace.append(address)
        for name, offset, value in contract_writes(case, len(trace)):
            put_word(buffers[name], offset, value)

    if pointer():
        release(struct.unpack_from('<I', buffers['object'], OFFSET + 0x3C)[0])
        index = 0
        while index < get_count(buffers):
            table = pointer() & native.MASK
            names = [name for name in ('table_a', 'table_b') if BASES[name] + OFFSET == table]
            if len(names) != 1 or index >= MAX_ENTRIES:
                raise ValueError('Model left the guarded cleanup table.')
            release(struct.unpack_from('<I', buffers[names[0]], OFFSET + index * 4)[0])
            index += 1
        release(pointer())
        put_word(buffers['object'], OFFSET + 0x38, 0)
    return trace, {name: bytes(data) for name, data in buffers.items()}


class Machine(native.Machine):
    def __init__(self, code=None):
        super().__init__(code=code, start=int(FUNCTION['address'], 16) & native.MASK,
                         native_functions=[FUNCTION])
        self.free = native.h.symbols['memory_free_mem'] & native.MASK
        self.entry_count = 0
        self.cpu.hook_add(native.unicorn.UC_HOOK_MEM_READ | native.unicorn.UC_HOOK_MEM_WRITE,
                          self.memory_hook)

    def memory_hook(self, cpu, access, address, size, value, unused):
        address &= native.MASK
        ranges = [(base, base + LENGTHS[name]) for name, base in BASES.items()]
        ranges.append((native.STACK - 0x100, native.STACK + 0x100))
        if not any(start <= address and address + size <= end for start, end in ranges):
            raise ValueError('Cleanup made an unreviewed data access.')

    def hook(self, cpu, address, size, unused):
        address &= native.MASK
        if address == self.start:
            self.entry_count += 1
            self.executed_native_functions.add(FUNCTION['function'])
        if address != self.free:
            if not self.start <= address < self.start + FUNCTION['bytes']:
                raise ValueError('Cleanup executed outside the reviewed function and allocator stub.')
            return
        self.trace.append(cpu.reg_read(native.reg.UC_MIPS_REG_A0))
        for name, offset, value in contract_writes(self.case, len(self.trace)):
            cpu.mem_write(BASES[name] + offset, struct.pack('<I', value & 0xFFFFFFFF))
        target = cpu.reg_read(native.reg.UC_MIPS_REG_RA)
        for index, register in enumerate(native.VOLATILE):
            cpu.reg_write(register, native.u32(0xBC000000 + 0x10203 * index))
        cpu.reg_write(native.reg.UC_MIPS_REG_V0, native.u32(0xC001 + len(self.trace)))
        cpu.reg_write(native.reg.UC_MIPS_REG_PC, target)

    def run(self, case):
        self.case, self.trace = case, []
        cpu = self.cpu
        for name, data in fixtures(case).items():
            cpu.mem_write(BASES[name], bytes(data))
        stack = bytes([0xCC]) * 0x500
        cpu.mem_write(native.STACK - 0x400, stack)
        saved = [native.u32(0xAB000000 + 0x10203 * i) for i in range(len(native.SAVED))]
        for register, value in zip(native.SAVED, saved):
            cpu.reg_write(register, value)
        for register, value in ((native.reg.UC_MIPS_REG_SP, native.STACK),
                                (native.reg.UC_MIPS_REG_GP, 0x8008A808),
                                (native.reg.UC_MIPS_REG_RA, native.END),
                                (native.reg.UC_MIPS_REG_A0, pointers(case)['object'])):
            cpu.reg_write(register, value)
        cpu.emu_start(self.start, native.END, count=2000)
        if (cpu.reg_read(native.reg.UC_MIPS_REG_PC) != native.END
                or cpu.reg_read(native.reg.UC_MIPS_REG_SP) != native.STACK
                or cpu.reg_read(native.reg.UC_MIPS_REG_GP) != 0x8008A808
                or cpu.reg_read(native.reg.UC_MIPS_REG_RA) != native.END
                or [cpu.reg_read(register) for register in native.SAVED] != saved
                or bytes(cpu.mem_read(native.STACK, 0x100)) != stack[0x400:]
                or bytes(cpu.mem_read(native.STACK - 0x400, 0x100)) != stack[:0x100]):
            raise ValueError('Cleanup violated guarded stack or saved-register expectations.')
        return self.trace, {name: bytes(cpu.mem_read(BASES[name], length))
                            for name, length in LENGTHS.items()}


def cases():
    for present, count, segment, seed in itertools.product((False, True),
            (-(1 << 31), -1, 0, 1, 2, 3, 7, 8), (0, 0x80000000, 0xA0000000), (0, 1)):
        yield 'count_and_null_table', dict(BASE_CASE, present=present, count=count, segment=segment, seed=seed)
    for pattern, count, segment, buffer_null, seed in itertools.product(
            ('distinct', 'nulls', 'duplicates', 'mixed'), (1, 2, 5, 8),
            (0, 0x80000000, 0xA0000000), (False, True), (0, 1)):
        yield 'opaque_release_arguments', dict(BASE_CASE, pattern=pattern, count=count,
                                               segment=segment, buffer_null=buffer_null, seed=seed)
    for count, new_count, segment in itertools.product((0, 1, 2, 8), (-1, 0, 1, 2, 8),
                                                      (0, 0x80000000, 0xA0000000)):
        yield 'count_reload_after_buffer', dict(BASE_CASE, count=count, segment=segment,
                                                mutations=((1, 'count', new_count),))
    for count, new_count, call, segment in itertools.product((2, 5, 8), (-1, 0, 1, 3, 8),
                                                            (2, 3), (0, 0x80000000, 0xA0000000)):
        yield 'count_reload_after_entry', dict(BASE_CASE, count=count, segment=segment,
                                               mutations=((call, 'count', new_count),))
    for count, call, segment, seed in itertools.product((2, 5, 8), (1, 2, 3),
                                                       (0, 0x80000000, 0xA0000000), (0, 1)):
        yield 'table_reload', dict(BASE_CASE, count=count, segment=segment, seed=seed,
                                   mutations=((call, 'table', 'table_b'),))
    for segment, field in itertools.product((0, 0x80000000, 0xA0000000), ('table_a_1', 'table_b_1')):
        yield 'entry_reload', dict(BASE_CASE, segment=segment,
                                  mutations=((1, 'table', field[:-2]), (2, field, 0x10D040 | segment)))
    for segment in (0, 0x80000000, 0xA0000000):
        yield 'clear_after_final_release', dict(BASE_CASE, segment=segment,
                                                mutations=((4, 'table', 'table_b'),))


def private_path(value, *, existing=False):
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve(strict=existing)
    lab = (ROOT / '.decomp-lab').resolve()
    if path == lab or not path.is_relative_to(lab):
        raise ValueError('Reports and candidates must remain inside .decomp-lab.')
    if not existing and path.exists():
        raise ValueError('Choose a fresh report path; existing evidence is preserved.')
    return path


def candidate_code(path, program):
    """Accept only a private complete image changing the reviewed function span."""
    path = private_path(path, existing=True)
    image = path.read_bytes()
    offset = 0x800 + int(FUNCTION['address'], 16) - program.LOAD
    end = offset + FUNCTION['bytes']
    if (len(image) != len(program.ROM) or image[:offset] != program.ROM[:offset]
            or image[end:] != program.ROM[end:]):
        raise ValueError('Candidate must change only the fixed 148-byte cleanup span.')
    code = image[offset:end]
    reference = program.ROM[offset:end]
    return code, {'path': path.relative_to(ROOT.resolve()).as_posix(),
                  'executable_sha256': hashlib.sha256(image).hexdigest(),
                  'function_sha256': hashlib.sha256(code).hexdigest(),
                  'whole_executable_byte_differences': sum(a != b for a, b in zip(image, program.ROM)),
                  'complete_executable_equal': image == program.ROM, 'source_promoted': False}


def verify(destination, candidate=None):
    dependencies = native.evidence_dependencies('tools/verify_card_cleanup.py',
                                                'src/menu/card/memory_card.c', 'src/menu/card/memory_card.h')
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    program = native.load_program([FUNCTION])
    code, candidate_record = candidate_code(candidate, program) if candidate else (None, None)
    native.initialize_backend(program)
    started = time.monotonic()
    machines = [('original', Machine())]
    if candidate_record:
        machines.append(('candidate', Machine(code)))
    groups = Counter()
    for group, case in cases():
        model = expected(case)
        for name, machine in machines:
            if machine.run(case) != model:
                raise ValueError(name + ' cleanup disagrees with the guarded release model: ' + repr(case))
        groups[group] += 1
    controls = []
    for name, offset, word, replacement in (
            ('skipped_entry', 0x54, 0x26100001, 0x26100002),
            ('wrong_final_field_clear', 0x78, 0xAE200038, 0xAE20003C),
            ('saved_owner_not_restored', 0x80, 0x8FB1001C, 0x8FB10018)):
        changed = bytearray(program.target(int(FUNCTION['address'], 16), FUNCTION['bytes']))
        if struct.unpack_from('<I', changed, offset)[0] != word:
            raise ValueError('Cleanup negative control no longer identifies its pinned word.')
        struct.pack_into('<I', changed, offset, replacement)
        try:
            detected = Machine(bytes(changed)).run(BASE_CASE) != expected(BASE_CASE)
        except ValueError:
            detected = True
        if not detected:
            raise ValueError('Cleanup negative control was not detected: ' + name)
        controls.append({'name': name, 'function_offset': offset, 'detected': True,
                         'scope': 'Private emulated copy; canonical inputs are preserved.'})
    if ((ROOT / native.configure.ROM).read_bytes() != program.ROM
            or (ROOT / native.configure.EXE).read_bytes() != program.ROM
            or native.check_build_current(ROOT) is not True
            or any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path, digest in before.items())):
        raise ValueError('Canonical build or a producer dependency changed during cleanup verification.')
    if candidate_record:
        candidate_digest = hashlib.sha256((ROOT / candidate_record['path']).read_bytes()).hexdigest()
        if candidate_digest != candidate_record['executable_sha256']:
            raise ValueError('Candidate image changed during verification.')
    report = {'status': 'passed_bounded_original_card_cleanup',
              'canonical_executable_sha1': hashlib.sha1(program.ROM).hexdigest(),
              'original_and_current_build_equal': True, 'original_behavior_modified': False,
              'model_api_calls': 0, 'backend': 'Unicorn ' + native.unicorn.__version__,
              'native_cases': sum(groups.values()), 'case_groups': dict(groups),
              'executed_native_entry_counts': {name: machine.entry_count for name, machine in machines},
              'native_functions': [FUNCTION], 'explicit_stub_count': 1,
              'explicit_stubs': ['memory_free_mem'], 'candidate': candidate_record,
              'negative_controls_detected': controls,
              'producer_dependencies': [{'path': path.resolve().relative_to(ROOT).as_posix(), 'sha256': digest}
                                        for path, digest in before.items()],
              'source_promotions': 0, 'original_feature_groups_accepted': 0,
              'scope': 'Original cleanup machine code: ordered opaque releases, signed count boundaries, '
                       'null table, null/duplicate arguments, KSEG aliases, dynamic count/table/entry reloads, '
                       'final table clear, all guarded fixture bytes, data-access boundaries, stack and saved registers. '
                       'One allocator stub poisons volatile registers and performs explicitly scheduled writes. '
                       'These writes are adversarial contracts, not claims about the native allocator. '
                       'Does not establish real heap coalescing, valid duplicate frees, card hardware, '
                       'natural cleanup reachability, source-layout recovery, PS1 timing or whole-feature parity.',
              'elapsed_seconds': round(time.monotonic() - started, 3)}
    with destination.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'passed': True, 'native_cases_per_image': report['native_cases'],
                      'images_checked': len(machines), 'negative_controls': len(controls), 'explicit_stubs': 1}))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='Fresh JSON report within .decomp-lab.')
    parser.add_argument('--candidate', help='Private complete candidate image changing only this function.')
    args = parser.parse_args(argv)
    try:
        destination = private_path(args.output)
        candidate = private_path(args.candidate, existing=True) if args.candidate else None
        destination.parent.mkdir(parents=True, exist_ok=True)
        verify(destination, candidate)
        return 0
    except (OSError, ValueError) as error:
        print('[!] ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
