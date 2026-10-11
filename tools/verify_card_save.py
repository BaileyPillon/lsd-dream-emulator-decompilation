"""Check the original save wrapper, file writer and native string/label helpers.

File I/O, allocation and diagnostic output use explicit deterministic stubs.
This local proof does not accept physical memory-card I/O or an entire feature.
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

FUNCTIONS = [
    {'function': 'memory_card_write_file', 'address': '0x8004EEA0', 'bytes': 204,
     'sha256': '4f275a5b9579eabc43e95de70bc41214ae0734de5ed7ea5c273b819ac791a313'},
    {'function': 'func_8004EF6C', 'address': '0x8004EF6C', 'bytes': 960,
     'sha256': 'a24ccbb37789695a86a6bf46e624aea68a667ed5cac934704edf7e6677349092'},
    {'function': 'memory_card_build_path', 'address': '0x8004F32C', 'bytes': 104,
     'sha256': '004e28b1c8b5fa55f4d5c2a1754dca403787deada36d63b701e30d9790e0027b'},
    {'function': 'func_800507F8', 'address': '0x800507F8', 'bytes': 240,
     'sha256': '6366aabaf1ea68aa189955760ed29e676f237ce8bbebead10131cdb91d15a5cd'},
    {'function': 'atoi', 'address': '0x80050948', 'bytes': 316,
     'sha256': 'a823b16bda0e8cac5381286349138b63812eba1890372f86ecd43b4cb2e7fa28'},
    {'function': 'todigit', 'address': '0x80050AA4', 'bytes': 100,
     'sha256': '220af54c96c04ac31fdc7b66008b2d898427b0929719514df3023ca8a5f4ace4'},
    {'function': 'strcpy', 'address': '0x80028B78', 'bytes': 68,
     'sha256': '83f1261096a02f2dc5770b577c92ace41c327074183dfadcb9fbd23ab14c3a89'},
    {'function': 'strcat', 'address': '0x80027130', 'bytes': 168,
     'sha256': 'fab4183efed2bac3c1324c0331f603fc24f453b862bc47b08b8b318684673662'},
    {'function': 'strlen', 'address': '0x80013348', 'bytes': 48,
     'sha256': '687b44978ea1acc29ad6ef4a72daa81c0db610cf13febf8030f3203e01478b3e'},
]
STUB_NAMES = ('delete', 'open', 'close', 'write', 'printf',
              'memory_allocate_mem', 'memory_free_mem')
BASES = {'object': 0x100000, 'name': 0x101000, 'title': 0x102000,
         'texture': 0x103000, 'image': 0x104000, 'payload': 0x108000,
         'header': 0x118000, 'template': 0x119000}
LENGTHS = {'object': 0x80, 'name': 0x80, 'title': 0x100, 'texture': 0x80,
           'image': 0x400, 'payload': 0x6000, 'header': 0x400, 'template': 0x180}
TEMPLATE_POINTER = 0x8AAC4
BASE_CASE = dict(port=0, slot=1, icons=3, size=8193, alignment=0, seed=0,
                 segment=0, failure_stage='create', failed_attempts=0,
                 delete_result=-1, close_result=0, write_result=None,
                 failed_write=0)


def fixtures(case):
    buffers = {name: bytearray((i * 37 + case['seed'] * 73 + 0xD7) & 255
                              for i in range(length))
               for name, length in LENGTHS.items()}
    offsets = {name: 0x40 for name in BASES}
    for index, name in enumerate(('name', 'title', 'image', 'header', 'template')):
        offsets[name] += (case['alignment'] + index) % 4
    pointers = {name: (BASES[name] + offsets[name]) | case['segment'] for name in BASES}
    struct.pack_into('<I', buffers['object'], offsets['object'] + 12, native.u32(case['port']))
    struct.pack_into('<I', buffers['texture'], offsets['texture'] + 16, pointers['image'])
    filename = ('BISLPS-01556' + f"{case['slot']:03d}").encode()
    buffers['name'][offsets['name']:offsets['name'] + len(filename) + 1] = filename + b'\0'
    title = b'LSD DREAM EMULATOR SLOT TEST DATA'
    buffers['title'][offsets['title']:offsets['title'] + len(title) + 1] = title + b'\0'
    # Opaque byte pairs: fixtures exercise the native copies, not glyph rendering.
    template = bytes(itertools.chain.from_iterable((0x82, 0x4F + i) for i in range(15)))
    template += bytes((0x83, 0x68, 0x83, 0x8A, 0x81, 0x5B, 0x83, 0x80, 0x20, 0x20, 0x20, 0x20))
    buffers['template'][offsets['template']:offsets['template'] + len(template)] = template
    return buffers, offsets, pointers, filename


def format_title(buffers, offsets, slot, clear=False):
    title, template = buffers['title'], buffers['template']
    destination, source = offsets['title'], offsets['template']
    suffix = template[source + 30:source + 42]
    if clear:
        title[destination + 6:destination + 12] = suffix[:6]
    else:
        title[destination + 24:destination + 26] = suffix[:2]
        title[destination + 6:destination + 18] = suffix
        title[destination + 8:destination + 10] = template[source + 2 * (slot - 1):source + 2 * slot]


def expected(case):
    buffers, offsets, pointers, filename = fixtures(case)
    format_title(buffers, offsets, case['slot'])
    path = (b'bu00:' if case['port'] == 0 else b'bu10:') + filename
    flags = (((case['size'] + 0x21FF) >> 13) << 16) | 0x200
    trace = []
    result = 0
    attempts = min(case['failed_attempts'] + 1, 11)
    for attempt in range(1, attempts + 1):
        create_fd, output_fd = 10 + 2 * attempt, 11 + 2 * attempt
        failing = attempt <= case['failed_attempts']
        trace.append(('writer_call', pointers['object'], pointers['name'], pointers['title'],
                      case['icons'] & 255, pointers['texture'], pointers['payload'], case['size']))
        trace.append(('delete', path))
        create_failed = failing and case['failure_stage'] == 'create'
        trace.append(('open', path, flags, native.u32(-1 if create_failed else create_fd)))
        if create_failed:
            trace.append(('printf', native.h.symbols['D_80011530']))
            continue
        trace.append(('close', create_fd))
        reopen_failed = failing and case['failure_stage'] == 'reopen'
        trace.append(('open', path, 2, native.u32(-1 if reopen_failed else output_fd)))
        if reopen_failed:
            continue
        header, start = buffers['header'], offsets['header']
        icons = case['icons'] & 255
        header[start:start + 4] = bytes((0x53, 0x43, (icons + 16) & 255,
                                      ((case['size'] + 0x1FFF) >> 13) & 255))
        title_start = offsets['title']
        title_end = buffers['title'].index(0, title_start) + 1
        title = buffers['title'][title_start:title_end]
        header[start + 4:start + 4 + len(title)] = title
        image, image_start = buffers['image'], offsets['image']
        header[start + 0x60:start + 0x80] = image[image_start + 0x14:image_start + 0x34]
        for index in range(3):
            begin = start + 0x80 + 128 * index
            image_begin = image_start + 0x40 + 128 * index
            header[begin:begin + 128] = image[image_begin:image_begin + 128]
        trace.append(('memory_allocate_mem', 0x200))
        header_size = (icons + 1) * 128
        trace.append(('write', output_fd, pointers['header'], header_size,
                      bytes(header[start:start + header_size])))
        trace.append(('memory_free_mem', pointers['header']))
        payload_size = ((case['size'] + 127) // 128) * 128
        payload_start = offsets['payload']
        trace.append(('write', output_fd, pointers['payload'], payload_size,
                      bytes(buffers['payload'][payload_start:payload_start + payload_size])))
        trace.append(('close', output_fd))
        result = 1
        break
    if result == 0:
        format_title(buffers, offsets, case['slot'], clear=True)
    return result, trace, {name: bytes(data) for name, data in buffers.items()}, attempts


class Machine(native.Machine):
    def __init__(self, patches=()):
        self.entry_counts = Counter()
        super().__init__(start=0x4EEA0, native_functions=FUNCTIONS)
        self.stubs = {native.h.symbols[name] & native.MASK: name for name in STUB_NAMES}
        self.ranges = [(int(record['address'], 16) & native.MASK,
                        (int(record['address'], 16) & native.MASK) + record['bytes'])
                       for record in FUNCTIONS]
        for address, data in patches:
            self.cpu.mem_write(address & native.MASK, data)

    def cstring(self, address):
        data = bytes(self.cpu.mem_read(address & native.MASK, 128))
        return data[:data.index(0)]

    def hook(self, cpu, address, size, unused):
        address &= native.MASK
        name = self.native_entries.get(address)
        if name:
            self.entry_counts[name] += 1
            self.executed_native_functions.add(name)
            if name == 'func_8004EF6C':
                args = [cpu.reg_read(getattr(native.reg, 'UC_MIPS_REG_A' + str(i))) for i in range(4)]
                stack = cpu.reg_read(native.reg.UC_MIPS_REG_SP) & native.MASK
                args += list(struct.unpack('<III', bytes(cpu.mem_read(stack + 16, 12))))
                self.trace.append(('writer_call', *args))
        stub = self.stubs.get(address)
        if stub is None:
            if not any(start <= address < end for start, end in self.ranges):
                raise ValueError('Unexpected native execution outside the reviewed save call graph.')
            return
        args = [cpu.reg_read(getattr(native.reg, 'UC_MIPS_REG_A' + str(i))) for i in range(3)]
        result = 0
        if stub == 'delete':
            self.trace.append((stub, self.cstring(args[0])))
            result = self.case['delete_result']
        elif stub == 'open':
            if args[1] & 0x200:
                self.attempts += 1
                stage, result = 'create', 10 + 2 * self.attempts
            elif args[1] == 2:
                stage, result = 'reopen', 11 + 2 * self.attempts
            else:
                raise ValueError('Unexpected file-open mode.')
            if stage == self.case['failure_stage'] and self.attempts <= self.case['failed_attempts']:
                result = -1
            self.trace.append((stub, self.cstring(args[0]), args[1], native.u32(result)))
        elif stub == 'close':
            self.trace.append((stub, args[0]))
            result = self.case['close_result']
        elif stub == 'printf':
            self.trace.append((stub, args[0]))
        elif stub == 'memory_allocate_mem':
            self.trace.append((stub, args[0]))
            result = self.pointers['header']
        elif stub == 'memory_free_mem':
            self.trace.append((stub, args[0]))
        elif stub == 'write':
            self.writes += 1
            if args[2] > LENGTHS['payload']:
                raise ValueError('Write exceeds the guarded synthetic fixture.')
            data = bytes(cpu.mem_read(args[1] & native.MASK, args[2]))
            self.trace.append((stub, *args, data))
            result = args[2]
            if self.case['failed_write'] in (self.writes, 3):
                result = self.case['write_result']
        target = cpu.reg_read(native.reg.UC_MIPS_REG_RA)
        for index, register in enumerate(native.VOLATILE):
            cpu.reg_write(register, native.u32(0xBC000000 + 0x10203 * index))
        cpu.reg_write(native.reg.UC_MIPS_REG_V0, native.u32(result))
        cpu.reg_write(native.reg.UC_MIPS_REG_PC, target)

    def run(self, case):
        self.case, self.trace, self.attempts, self.writes = case, [], 0, 0
        buffers, _, self.pointers, _ = fixtures(case)
        cpu = self.cpu
        for name, data in buffers.items():
            cpu.mem_write(BASES[name], bytes(data))
        pointer = struct.pack('<I', self.pointers['template'])
        cpu.mem_write(TEMPLATE_POINTER, pointer)
        stack = bytearray([0xCC] * 0x500)
        for offset, value in ((16, self.pointers['texture']), (20, self.pointers['payload']),
                              (24, case['size'])):
            struct.pack_into('<I', stack, 0x400 + offset, native.u32(value))
        cpu.mem_write(native.STACK - 0x400, bytes(stack))
        saved = [native.u32(0xAB000000 + 0x10203 * i) for i in range(len(native.SAVED))]
        for register, value in zip(native.SAVED, saved):
            cpu.reg_write(register, value)
        for register, value in ((native.reg.UC_MIPS_REG_SP, native.STACK),
                                (native.reg.UC_MIPS_REG_GP, 0x8008A808),
                                (native.reg.UC_MIPS_REG_RA, native.END),
                                (native.reg.UC_MIPS_REG_A0, self.pointers['object']),
                                (native.reg.UC_MIPS_REG_A1, self.pointers['name']),
                                (native.reg.UC_MIPS_REG_A2, self.pointers['title']),
                                (native.reg.UC_MIPS_REG_A3, native.u32(case['icons']))):
            cpu.reg_write(register, value)
        cpu.emu_start(self.start, native.END, count=200000)
        if (cpu.reg_read(native.reg.UC_MIPS_REG_PC) != native.END or
                cpu.reg_read(native.reg.UC_MIPS_REG_SP) != native.STACK or
                cpu.reg_read(native.reg.UC_MIPS_REG_GP) != 0x8008A808 or
                cpu.reg_read(native.reg.UC_MIPS_REG_RA) != native.END or
                [cpu.reg_read(register) for register in native.SAVED] != saved or
                bytes(cpu.mem_read(TEMPLATE_POINTER, 4)) != pointer or
                bytes(cpu.mem_read(native.STACK, 0x100)) != bytes(stack[0x400:]) or
                bytes(cpu.mem_read(native.STACK - 0x400, 0x100)) != bytes(stack[:0x100])):
            raise ValueError('Native save workflow violated guarded memory or ABI expectations.')
        return (cpu.reg_read(native.reg.UC_MIPS_REG_V0), self.trace,
                {name: bytes(cpu.mem_read(BASES[name], length)) for name, length in LENGTHS.items()},
                self.attempts)


def cases():
    for port, slot, icons, size, alignment, seed in itertools.product(
            (0, 1, -1, 0x7FFFFFFF), range(1, 16), (1, 2, 3),
            (0, 1, 127, 128, 129, 8191, 8192, 8193), range(4), range(2)):
        yield 'successful_saves', dict(BASE_CASE, port=port, slot=slot, icons=icons,
                                       size=size, alignment=alignment, seed=seed)
    for stage, failures, port, slot, icons, alignment in itertools.product(
            ('create', 'reopen'), range(1, 13), (0, 1), (1, 8, 15), (1, 3), range(4)):
        yield 'retry_and_cleanup', dict(BASE_CASE, failure_stage=stage, failed_attempts=failures,
                                        port=port, slot=slot, icons=icons, alignment=alignment)
    for call, value, icons, seed in itertools.product(('delete', 'close', 'write'),
                                                    (-1, 0, 1, 127), range(4), range(2)):
        case = dict(BASE_CASE, icons=icons, seed=seed)
        case[call + '_result'] = value
        if call == 'write':
            case['failed_write'] = 3
        yield 'ignored_io_results', case
    for segment, port, icons, slot, alignment in itertools.product(
            (0x80000000, 0xA0000000), (0, 1), (1, 2, 3), (1, 15), (0, 3)):
        yield 'segment_aliases', dict(BASE_CASE, segment=segment, port=port, icons=icons,
                                     slot=slot, alignment=alignment)
    for icons, stage, failures, segment, alignment in itertools.product(
            (0x100, 0x101, 0x102, 0x103, 0xFFFFFF00, 0xFFFFFF01, 0xFFFFFF02, 0xFFFFFF03),
            ('create', 'reopen'), (0, 11), (0, 0x80000000), range(4)):
        yield 'wrapper_icon_byte', dict(BASE_CASE, icons=icons, failure_stage=stage,
                                       failed_attempts=failures, segment=segment, alignment=alignment)
    for size, port, icons, alignment in itertools.product((16383, 16384, 16385),
                                                        (0, 1), (1, 2, 3), range(4)):
        yield 'additional_block_boundary', dict(BASE_CASE, size=size, port=port,
                                                icons=icons, alignment=alignment)
    for failed_write, value in itertools.product((1, 2), (-1, 0, 1, 127)):
        yield 'individual_write_results', dict(BASE_CASE, failed_write=failed_write, write_result=value)


def verify(destination):
    dependencies = native.evidence_dependencies(
        'tools/verify_card_save.py', 'src/menu/card/memory_card.c', 'src/menu/card/memory_card.h',
        'src/menu/card/save_label.c', 'src/menu/card/save_label.h', 'config/SLPS01556.yaml',
        'asm/nonmatchings/menu/card/memory_card/func_8004EF6C.s',
        'src/psyq/libc/strcpy.c', 'src/psyq/libc/strcat.c', 'src/psyq/libc/strlen.c',
        'src/psyq/libc/atoi.c', 'src/psyq/libc/todigit.c',
        'asm/nonmatchings/psyq/libc/strcpy/strcpy.s',
        'asm/nonmatchings/psyq/libc/strcat/strcat.s',
        'asm/nonmatchings/psyq/libc/strlen/strlen.s',
        'asm/nonmatchings/psyq/libc/atoi/atoi.s', 'asm/nonmatchings/psyq/libc/todigit/todigit.s')
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    native.initialize_backend(native.load_program(FUNCTIONS))
    started = time.monotonic()
    machine = Machine()
    groups, results, attempts = Counter(), Counter(), Counter()
    for group, case in cases():
        actual, model = machine.run(case), expected(case)
        if actual != model:
            raise ValueError('Original save workflow/model disagreement: ' + repr(case))
        groups[group] += 1
        results['success' if actual[0] else 'failure'] += 1
        attempts[str(actual[3])] += 1
        count = sum(groups.values())
        if count % 1024 == 0:
            print(json.dumps({'native_cases_checked': count}), flush=True)
    if machine.executed_native_functions != {record['function'] for record in FUNCTIONS}:
        raise ValueError('The native save call graph was not fully exercised.')
    controls = []
    for name, address, immediate, case in (
            ('shortened_retry_limit', 0x8004EEC8, 9, dict(BASE_CASE, failed_attempts=10)),
            ('incorrect_create_flags', 0x8004EFE0, 0x400, BASE_CASE),
            ('incorrect_header_write_length', 0x8004F2C8, 127, BASE_CASE),
            ('incorrect_payload_padding', 0x8004F2DC, 126, BASE_CASE),
            ('wrong_icon_argument_width', 0x8004EF00, 0xFFFF, dict(BASE_CASE, icons=0x101)),
            ('incorrect_palette_source', 0x8004F070, 0x1B, BASE_CASE)):
        original = native.h.target(address, 4)
        patched = original[2:]
        data = struct.pack('<H', immediate) + patched
        try:
            observed = Machine(((address, data),)).run(case)
            detected = observed != expected(case)
        except ValueError:
            detected = True
        if not detected:
            raise ValueError('Save workflow mutation control was not detected: ' + name)
        controls.append({'name': name, 'address': f'0x{address:08X}', 'detected': True})
    case = dict(BASE_CASE, failed_attempts=11)
    observed = Machine(((0x8004EF2C, bytes(4)),)).run(case)
    if observed == expected(case):
        raise ValueError('Missing failure-label reset control was not detected.')
    controls.append({'name': 'missing_failure_label_reset', 'address': '0x8004EF2C', 'detected': True})
    if ((ROOT / native.configure.ROM).read_bytes() != native.h.ROM or
            (ROOT / native.configure.EXE).read_bytes() != native.h.ROM or
            native.check_build_current(ROOT) is not True or
            any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path, digest in before.items())):
        raise ValueError('Source or canonical build changed during save workflow verification.')
    report = {'status': 'passed_bounded_original_save_workflow',
        'canonical_executable_sha1': hashlib.sha1(native.h.ROM).hexdigest(),
        'original_and_current_build_equal': True, 'original_behavior_modified': False,
        'model_api_calls': 0, 'backend': 'Unicorn ' + native.unicorn.__version__,
        'native_cases': sum(groups.values()), 'case_groups': dict(groups),
        'case_results': dict(results), 'attempt_counts': dict(attempts),
        'native_functions': FUNCTIONS, 'executed_native_entry_counts': dict(machine.entry_counts),
        'explicit_stub_count': len(STUB_NAMES), 'explicit_stubs': list(STUB_NAMES),
        'negative_controls_detected': controls,
        'producer_dependencies': [{'path': path.resolve().relative_to(ROOT).as_posix(), 'sha256': digest}
                                  for path, digest in before.items()],
        'original_feature_groups_accepted': 0,
        'scope': 'Original save wrapper, writer, path builder, title formatter and actual SDK '
                 'atoi/todigit/strcpy/strcat/strlen versus independent guarded byte and I/O rules. '
                 'Valid slots 1-15, aligned/unaligned nonoverlapping buffers, byte-masked icon '
                 'argument, up to 11 attempts, create/reopen failures, reset after exhaustion, '
                 '128-byte padding, 8 KiB allocation boundaries, both device prefixes, segment '
                 'aliases, ignored delete/close/write results, entire fixture buffers, call graph, '
                 'global pointer, stack and saved registers. Seven explicit stubs cover file I/O, '
                 'allocation and printf. Does not establish physical card I/O, allocator failure, '
                 'invalid filenames, oversized icons, overlapping buffers, UI/error rendering, '
                 'save persistence, complete dream-state round trips or PS1 timing.',
        'elapsed_seconds': round(time.monotonic() - started, 3)}
    with destination.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'report': str(destination), 'native_cases': report['native_cases'],
                      'negative_controls': len(controls), 'explicit_stubs': len(STUB_NAMES), 'passed': True}))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='New JSON report within .decomp-lab.')
    args = parser.parse_args(argv)
    try:
        destination = Path(args.output)
        if not destination.is_absolute():
            destination = ROOT / destination
        destination = destination.resolve()
        if not destination.is_relative_to((ROOT / '.decomp-lab').resolve()):
            raise ValueError('Reports must remain inside the private .decomp-lab directory.')
        if destination.exists():
            raise ValueError('Choose a new report path; existing evidence is preserved.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        verify(destination)
        return 0
    except (OSError, ValueError) as error:
        print('[!] ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
