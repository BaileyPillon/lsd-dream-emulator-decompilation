"""Check the original SDK voice-volume getter and its pointer/status ABI.

These bounded native fixtures use no stubs and do not accept audible playback,
automatic volume ramps or the entire sound feature group. No model API is used.
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

FUNCTIONS = [{'function': 'SsUtGetDetVVol', 'address': '0x80031C98', 'bytes': 88,
              'sha256': '83424bcc8015302705d84878cb4b3bbc566bb28968c1ec6db82878ad0926f132'}]
TABLE, LEFT, RIGHT, POINTER = 0x110000, 0x112000, 0x113000, 0x6DAD4
VOICES = [*range(24), -1, 24, 25, 0x7FFF, -0x8000, 0x10000, 0x10017, 0x10018]


def fixtures(case):
    table = bytearray((i * 37 + case['seed'] * 91) & 255 for i in range(0x200))
    for voice in range(32):
        struct.pack_into('<HH', table, voice * 16,
                         (0x1043 + voice * 0x91 + case['seed'] * 0x1F11) & 65535,
                         (0x9051 + voice * 0x121 + case['seed'] * 0x12F1) & 65535)
    left, right = bytearray([0xC7] * 0x80), bytearray([0xD3] * 0x80)
    left_offset, right_offset = 0x20 + case['left_alignment'], 0x20 + case['right_alignment']
    return (table, left, right), (left_offset, right_offset)


def expected(case):
    buffers, (left_offset, right_offset) = fixtures(case)
    table, left, right = buffers
    voice = case['voice'] & 65535
    result = native.u32(-1)
    if voice < 24:
        left[left_offset:left_offset + 2] = table[voice * 16:voice * 16 + 2]
        output, offset = (left, left_offset) if case['alias'] else (right, right_offset)
        output[offset:offset + 2] = table[voice * 16 + 2:voice * 16 + 4]
        result = 0
    return tuple(map(bytes, buffers)), result


class Machine(native.Machine):
    def __init__(self, code=None):
        self.entry_counts = Counter()
        super().__init__(code=code, start=0x31C98, native_functions=FUNCTIONS)

    def hook(self, cpu, address, size, unused):
        name = self.native_entries.get(address & native.MASK)
        if name:
            self.entry_counts[name] += 1
            self.executed_native_functions.add(name)

    def run(self, case):
        buffers, (left_offset, right_offset) = fixtures(case)
        cpu = self.cpu
        for address, data in zip((TABLE, LEFT, RIGHT), buffers):
            cpu.mem_write(address, bytes(data))
        cpu.mem_write(POINTER, struct.pack('<I', TABLE))
        saved = [native.u32(0xCD000000 + 0x10403 * i) for i in range(len(native.SAVED))]
        for register, value in zip(native.SAVED, saved):
            cpu.reg_write(register, value)
        for register, value in (
                (native.reg.UC_MIPS_REG_SP, native.STACK),
                (native.reg.UC_MIPS_REG_GP, 0x8008A808),
                (native.reg.UC_MIPS_REG_RA, native.END),
                (native.reg.UC_MIPS_REG_A0, native.u32(case['voice'])),
                (native.reg.UC_MIPS_REG_A1, LEFT + left_offset),
                (native.reg.UC_MIPS_REG_A2, LEFT + left_offset if case['alias'] else RIGHT + right_offset),
                (native.reg.UC_MIPS_REG_A3, 0xAB123456)):
            cpu.reg_write(register, value)
        cpu.emu_start(self.start, native.END, count=2000)
        if (cpu.reg_read(native.reg.UC_MIPS_REG_PC) != native.END or
                cpu.reg_read(native.reg.UC_MIPS_REG_SP) != native.STACK or
                cpu.reg_read(native.reg.UC_MIPS_REG_GP) != 0x8008A808 or
                [cpu.reg_read(register) for register in native.SAVED] != saved or
                bytes(cpu.mem_read(POINTER, 4)) != struct.pack('<I', TABLE)):
            raise ValueError('Original voice-volume ABI/global-pointer expectations failed.')
        return (tuple(bytes(cpu.mem_read(address, len(data)))
                      for address, data in zip((TABLE, LEFT, RIGHT), buffers)),
                cpu.reg_read(native.reg.UC_MIPS_REG_V0))


def verify(destination):
    dependencies = native.evidence_dependencies('tools/verify_sound_volume.py',
        'src/sound/sound.c', 'include/psx/libsnd.h', 'config/symbols.txt', 'asm/22244.s')
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    native.initialize_backend(native.load_program(FUNCTIONS))
    machine, count = Machine(), 0
    destinations = [(False, left, right) for left, right in itertools.product((0, 2), repeat=2)]
    destinations += [(True, alignment, 0) for alignment in (0, 2)]
    for voice, seed, (alias, left, right) in itertools.product(VOICES, range(2), destinations):
        case = {'voice': voice, 'seed': seed, 'alias': alias,
                'left_alignment': left, 'right_alignment': right}
        if machine.run(case) != expected(case):
            raise ValueError('Original voice-volume/reference disagreement: ' + repr(case))
        count += 1
    base = {'voice': 7, 'seed': 0, 'alias': False, 'left_alignment': 0, 'right_alignment': 0}
    controls, original = [], native.h.target(0x80031C98, 88)
    for name, address, old, new, case in (
            ('wrong_voice_bound', 0x80031C9C, 0x2C420018, 0x2C420019, {**base, 'voice': 24}),
            ('wrong_voice_stride', 0x80031CB8, 0x00031B03, 0x00031B43, base),
            ('wrong_right_channel', 0x80031CDC, 0x94630002, 0x94630004, base)):
        code = bytearray(original)
        offset = address - 0x80031C98
        if struct.unpack_from('<I', code, offset)[0] != old:
            raise ValueError('Voice-volume control instruction evidence changed: ' + name)
        struct.pack_into('<I', code, offset, new)
        if Machine(bytes(code)).run(case) == expected(case):
            raise ValueError('Voice-volume negative control was not detected: ' + name)
        controls.append({'name': name, 'address': hex(address), 'expected_word': hex(old),
                         'changed_word': hex(new), 'fixture': case, 'detected': True,
                         'scope': 'Private Unicorn memory only.'})
    if ((ROOT / native.configure.ROM).read_bytes() != native.h.ROM or
            (ROOT / native.configure.EXE).read_bytes() != native.h.ROM or
            native.check_build_current(ROOT) is not True or
            any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path, digest in before.items())):
        raise ValueError('Source or canonical build changed during voice-volume verification.')
    report = {'status': 'passed_bounded_original_sdk_voice_volume',
        'canonical_executable_sha1': hashlib.sha1(native.h.ROM).hexdigest(),
        'original_and_current_build_equal': True, 'original_behavior_modified': False,
        'model_api_calls': 0, 'backend': 'Unicorn ' + native.unicorn.__version__,
        'native_cases': count, 'native_functions': FUNCTIONS,
        'executed_native_entry_counts': dict(machine.entry_counts), 'explicit_stubs': 0,
        'negative_controls_detected': controls,
        'producer_dependencies': [{'path': path.resolve().relative_to(ROOT).as_posix(), 'sha256': digest}
                                  for path, digest in before.items()],
        'original_feature_groups_accepted': 0,
        'scope': 'The actual SDK getter compares 32 voice inputs (all 24 valid voices, invalid bounds '
                 'and 16-bit truncation), two opaque channel contents and six aligned pointer/alias '
                 'layouts: whole guarded buffers, return status, source data/global pointer, GP, stack '
                 'and saved registers. No stubs. This does not establish automatic volume/pan ramps, '
                 'natural voice allocation, audible playback, SPU timing or entire sound-group acceptance.'}
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'report': str(destination), 'native_cases': count,
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
