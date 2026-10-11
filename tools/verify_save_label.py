"""Verify original save-slot title formatting with native SDK conversion code.

These local synthetic fixtures do not accept complete save/card behavior.
No game behavior is changed and no model API is called.
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
    {'function': 'func_800507F8', 'address': '0x800507F8', 'bytes': 240,
     'sha256': '6366aabaf1ea68aa189955760ed29e676f237ce8bbebead10131cdb91d15a5cd'},
    {'function': 'atoi', 'address': '0x80050948', 'bytes': 316,
     'sha256': 'a823b16bda0e8cac5381286349138b63812eba1890372f86ecd43b4cb2e7fa28'},
    {'function': 'todigit', 'address': '0x80050AA4', 'bytes': 100,
     'sha256': '220af54c96c04ac31fdc7b66008b2d898427b0929719514df3023ca8a5f4ace4'},
]
TITLE, NAME, TEMPLATE = 0x110000, 0x111000, 0x112000
TEMPLATE_POINTER = 0x8AAC4


def fixtures(case):
    title = bytearray([0xD7] * 0x100)
    name = bytearray([0xC5] * 0x80)
    template = bytearray((i * 29 + case['seed'] * 73) & 255 for i in range(0x180))
    title_offset = 0x40 + case['title_alignment']
    name_offset = 0x20 + case['name_alignment']
    template_offset = 0x40 + case['template_alignment']
    filename = ('BISLPS-01556' + f"{case['slot']:03d}").encode() + b'\0'
    name[name_offset:name_offset + len(filename)] = filename
    return (title, name, template), (title_offset, name_offset, template_offset)


def expected(case):
    buffers, (title_offset, _, template_offset) = fixtures(case)
    title, _, template = buffers
    suffix = template[template_offset + 0x1E:template_offset + 0x2A]
    if case['clear']:
        title[title_offset + 6:title_offset + 12] = suffix[:6]
    else:
        title[title_offset + 0x18:title_offset + 0x1A] = suffix[:2]
        title[title_offset + 6:title_offset + 18] = suffix
        slot_offset = template_offset + 2 * (case['slot'] - 1)
        title[title_offset + 8:title_offset + 10] = template[slot_offset:slot_offset + 2]
    return tuple(map(bytes, buffers))


class Machine(native.Machine):
    def __init__(self, code=None):
        self.entry_counts = Counter()
        super().__init__(code=code, start=0x507F8, native_functions=FUNCTIONS)

    def hook(self, cpu, address, size, unused):
        name = self.native_entries.get(address & native.MASK)
        if name:
            self.entry_counts[name] += 1
            self.executed_native_functions.add(name)

    def run(self, case):
        buffers, offsets = fixtures(case)
        cpu = self.cpu
        for address, data in zip((TITLE, NAME, TEMPLATE), buffers):
            cpu.mem_write(address, bytes(data))
        pointer = TEMPLATE + offsets[2]
        cpu.mem_write(TEMPLATE_POINTER, struct.pack('<I', pointer))
        cpu.mem_write(native.STACK - 0x200, bytes([0xCC]) * 0x400)
        saved = [native.u32(0xAB000000 + 0x10203 * i) for i in range(len(native.SAVED))]
        for register, value in zip(native.SAVED, saved):
            cpu.reg_write(register, value)
        for register, value in (
                (native.reg.UC_MIPS_REG_SP, native.STACK),
                (native.reg.UC_MIPS_REG_GP, 0x8008A808),
                (native.reg.UC_MIPS_REG_RA, native.END),
                (native.reg.UC_MIPS_REG_A0, TITLE + offsets[0]),
                (native.reg.UC_MIPS_REG_A1, 0 if case['clear'] else NAME + offsets[1]),
                (native.reg.UC_MIPS_REG_A2, 0xAC123456),
                (native.reg.UC_MIPS_REG_A3, 0xBC654321)):
            cpu.reg_write(register, value)
        cpu.emu_start(self.start, native.END, count=20000)
        if (cpu.reg_read(native.reg.UC_MIPS_REG_PC) != native.END or
                cpu.reg_read(native.reg.UC_MIPS_REG_SP) != native.STACK or
                cpu.reg_read(native.reg.UC_MIPS_REG_GP) != 0x8008A808 or
                [cpu.reg_read(register) for register in native.SAVED] != saved or
                bytes(cpu.mem_read(TEMPLATE_POINTER, 4)) != struct.pack('<I', pointer)):
            raise ValueError('Native save-label ABI/global-pointer expectations failed.')
        return tuple(bytes(cpu.mem_read(address, len(data)))
                     for address, data in zip((TITLE, NAME, TEMPLATE), buffers))


def verify(destination):
    dependencies = native.evidence_dependencies(
        'tools/verify_save_label.py', 'src/menu/card/save_label.c', 'src/menu/card/save_label.h',
        'src/menu/card/memory_card.c', 'src/psyq/card/file_io.c', 'config/SLPS01556.yaml',
        'src/psyq/libc/atoi.c', 'src/psyq/libc/todigit.c',
        'asm/nonmatchings/psyq/libc/atoi/atoi.s',
        'asm/nonmatchings/psyq/libc/todigit/todigit.s')
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    native.initialize_backend(native.load_program(FUNCTIONS))
    started = time.monotonic()
    machine = Machine()
    count = 0
    for slot, title_alignment, name_alignment, template_alignment, seed in itertools.product(
            range(1, 16), range(4), range(4), range(4), range(2)):
        case = dict(slot=slot, title_alignment=title_alignment, name_alignment=name_alignment,
                    template_alignment=template_alignment, seed=seed, clear=False)
        if machine.run(case) != expected(case):
            raise ValueError('Original save-label/model disagreement: ' + repr(case))
        count += 1
    for title_alignment, template_alignment, seed in itertools.product(range(4), range(4), range(2)):
        case = dict(slot=1, title_alignment=title_alignment, name_alignment=0,
                    template_alignment=template_alignment, seed=seed, clear=True)
        if machine.run(case) != expected(case):
            raise ValueError('Original save-label reset/model disagreement: ' + repr(case))
        count += 1
    controls = []
    base = dict(slot=1, title_alignment=0, name_alignment=0,
                template_alignment=0, seed=0, clear=False)
    original = native.h.target(0x800507F8, 240)
    for name, address, old, new, case in (
            ('wrong_8_9_conversion_offset', 0x80050828, 0x3408000E, 0x3408000D, {**base, 'slot': 8}),
            ('wrong_slot_index', 0x80050884, 0x2442FFFF, 0x2442FFFE, base),
            ('wrong_reset_copy_destination', 0x800508C4, 0xAA030009, 0xAA03000B, {**base, 'clear': True})):
        code = bytearray(original)
        offset = address - 0x800507F8
        if struct.unpack_from('<I', code, offset)[0] != old:
            raise ValueError('Native instruction-control evidence changed: ' + name)
        struct.pack_into('<I', code, offset, new)
        if Machine(bytes(code)).run(case) == expected(case):
            raise ValueError('Save-label negative control was not detected: ' + name)
        controls.append({'name': name, 'address': hex(address), 'expected_word': hex(old),
                         'changed_word': hex(new), 'fixture': case, 'detected': True,
                         'scope': 'Private Unicorn memory only.'})
    if ((ROOT / native.configure.ROM).read_bytes() != native.h.ROM or
            (ROOT / native.configure.EXE).read_bytes() != native.h.ROM or
            native.check_build_current(ROOT) is not True or
            any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path, digest in before.items())):
        raise ValueError('Source or canonical build changed during save-label verification.')
    report = {'status': 'passed_bounded_original_save_label',
        'canonical_executable_sha1': hashlib.sha1(native.h.ROM).hexdigest(),
        'original_and_current_build_equal': True, 'original_behavior_modified': False,
        'model_api_calls': 0, 'backend': 'Unicorn ' + native.unicorn.__version__,
        'native_cases': count, 'slot_cases': 1920, 'reset_cases': 32,
        'native_functions': FUNCTIONS, 'executed_native_entry_counts': dict(machine.entry_counts),
        'explicit_stubs': 0, 'negative_controls_detected': controls,
        'producer_dependencies': [{'path': path.resolve().relative_to(ROOT).as_posix(), 'sha256': digest}
                                  for path, digest in before.items()],
        'original_feature_groups_accepted': 0,
        'scope': 'Original save-title formatter and actual SDK atoi/todigit versus independent '
                 'slot/template byte rules. All valid slots 1-15, null-filename reset, all four '
                 'input/output/template alignments, two template contents, entire guarded buffers, '
                 'global pointer, return, GP, stack and saved registers. Synthetic independent '
                 'nonoverlapping buffers; does not establish natural template construction, '
                 'malformed filenames, overlapping inputs, physical card I/O, retry/error screens, '
                 'title rendering, save persistence or PS1 instruction/cycle timing.',
        'elapsed_seconds': round(time.monotonic() - started, 3)}
    with destination.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'report': str(destination), 'native_cases': count,
                      'negative_controls': len(controls), 'explicit_stubs': 0, 'passed': True}))


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
