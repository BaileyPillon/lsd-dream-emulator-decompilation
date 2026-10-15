"""Execute original movie path/cutoff helpers in bounded manual MIPS fixtures."""
from collections import Counter
import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import verify_native_ai as native
from tools.inventory_movies import reference_tables, PATH_ADDRESS, PATH_WIDTH, CUTOFF_ADDRESS

MASK = 0x1fffffff
BUFFER, OUTPUT, STACK, END = 0x100000, 0x100008, 0x1f0000, 0x1ff000
FUNCTIONS = ('get_logo_asmk_path', 'get_opening_movie_path', 'get_random_opening_movie_path',
             'get_ending_movie_path', 'get_ending_movie_path_2', 'get_event1_movie_path',
             'get_event_movie_path', 'get_special_movie_path', 'get_special_day_movie',
             'get_special_reel_movie_path', 'get_movie_duration_maybe', 'get_path_table',
             'get_seeded_random', 'rand', 'srand')


NATIVE_FUNCTIONS = [
    {
        "function": "get_logo_asmk_path",
        "address": "0x800490F4",
        "bytes": 28,
        "sha256": "fc5e45ee46447aa5ee5fa1758740259e6d67addc3a7c048cd520cf445f19c98f"
    },
    {
        "function": "get_opening_movie_path",
        "address": "0x80049110",
        "bytes": 44,
        "sha256": "8554dd5ae3540fe750e33afc4cc11323f4a15e63e03084998a243f5a7db391e0"
    },
    {
        "function": "get_random_opening_movie_path",
        "address": "0x8004913C",
        "bytes": 144,
        "sha256": "01dfa2133ac1575131024ed32e888b00457bd79df8c978456872bf044eebd857"
    },
    {
        "function": "get_ending_movie_path",
        "address": "0x800491CC",
        "bytes": 48,
        "sha256": "ffcba2d93fead9998f204935b0ee90ff58751f0bdc8362806a4673863e668b34"
    },
    {
        "function": "get_ending_movie_path_2",
        "address": "0x800491FC",
        "bytes": 68,
        "sha256": "bd65bf43f8fb4cddd69c6af3ea8f9e71024cbb682568ee4716cdd28316e0812b"
    },
    {
        "function": "get_event1_movie_path",
        "address": "0x80049240",
        "bytes": 48,
        "sha256": "e26dbbfa99879113b2eca393ea28346305298f8e24aeebc4bbde8c3ee1509aca"
    },
    {
        "function": "get_event_movie_path",
        "address": "0x80049270",
        "bytes": 96,
        "sha256": "3bc389a50989cf7323b35915a09a7e6bbb073e9f4c4776ba5fc35208d0f11b80"
    },
    {
        "function": "get_special_movie_path",
        "address": "0x800492D0",
        "bytes": 100,
        "sha256": "22d6aca4e55190ba28740500ef4f1d35cac9e099d2c2e535bc9bf34a0ed2f364"
    },
    {
        "function": "get_special_day_movie",
        "address": "0x80049334",
        "bytes": 148,
        "sha256": "cd69dbb12c6277685d047f6dc4e35d7bba3ecac22d5cf2b8ca5a92c23037335e"
    },
    {
        "function": "get_special_reel_movie_path",
        "address": "0x800493E4",
        "bytes": 156,
        "sha256": "6848d728a3907f4ad85cc344d133ef6446a6adc7a49bc7fac202cf378ccde884"
    },
    {
        "function": "get_movie_duration_maybe",
        "address": "0x800493C8",
        "bytes": 28,
        "sha256": "2627ea962effea99af77268773e25af9f43b38e074b2305565ec384ed2f45513"
    },
    {
        "function": "get_path_table",
        "address": "0x80048D48",
        "bytes": 28,
        "sha256": "daf17bc0c637610f5ecc894afa83dbaba43df82e2f000c003c1d70c0fdfb777d"
    },
    {
        "function": "get_seeded_random",
        "address": "0x80048CFC",
        "bytes": 44,
        "sha256": "d6a663de736ac83d8fe70a47d4746484004b201fe4cb02c18939cc0e022d418d"
    },
    {
        "function": "rand",
        "address": "0x80049480",
        "bytes": 40,
        "sha256": "4c54a1210ed147afe9b02657c9b12bdec5bb62c5584a2a9fef212567d0e04c0c"
    },
    {
        "function": "srand",
        "address": "0x800494A8",
        "bytes": 12,
        "sha256": "41e2537527158d69ebbd13e2205b03816cf27c981266d1f3683a978930beb94a"
    }
]

class Machine:
    def __init__(self, program):
        try:
            import unicorn
            from unicorn import mips_const as reg
        except ImportError as error:
            raise ValueError('Install requirements-analysis.txt in the configured analysis environment.') from error
        if unicorn.__version__ != '2.1.4':
            raise ValueError('Use the pinned Unicorn 2.1.4 analysis environment.')
        self.reg, self.program = reg, program
        self.cpu = unicorn.Uc(unicorn.UC_ARCH_MIPS, unicorn.UC_MODE_MIPS32 | unicorn.UC_MODE_LITTLE_ENDIAN)
        self.cpu.mem_map(0, 0x200000)
        self.cpu.mem_write(program.LOAD & MASK, program.ROM[0x800:])
        self.entries = {program.symbols[name] & MASK: name for name in FUNCTIONS}
        self.counts, self.instructions = Counter(), Counter()
        self.cpu.hook_add(unicorn.UC_HOOK_CODE, self.observe)

    def observe(self, cpu, address, size, unused):
        address &= MASK
        self.instructions[address] += 1
        if address in self.entries:
            self.counts[self.entries[address]] += 1

    def call(self, name, args):
        reg, cpu = self.reg, self.cpu
        saved = [getattr(reg, 'UC_MIPS_REG_S' + str(index)) for index in range(8)] + [reg.UC_MIPS_REG_FP]
        expected = [0xab000000 + index * 0x10203 for index in range(len(saved))]
        for register, value in zip(saved, expected):
            cpu.reg_write(register, value)
        for index in range(4):
            cpu.reg_write(getattr(reg, 'UC_MIPS_REG_A' + str(index)), (args[index] if index < len(args) else 0) & 0xffffffff)
        cpu.reg_write(reg.UC_MIPS_REG_SP, STACK)
        cpu.reg_write(reg.UC_MIPS_REG_GP, 0x8008a808)
        cpu.reg_write(reg.UC_MIPS_REG_RA, END)
        cpu.emu_start(self.program.symbols[name] & MASK, END, count=10000)
        if (cpu.reg_read(reg.UC_MIPS_REG_PC) != END or cpu.reg_read(reg.UC_MIPS_REG_SP) != STACK or
                cpu.reg_read(reg.UC_MIPS_REG_GP) != 0x8008a808 or cpu.reg_read(reg.UC_MIPS_REG_RA) != END or
                [cpu.reg_read(register) for register in saved] != expected):
            raise ValueError('Native movie helper failed its return/stack/callee-saved ABI guard.')
        return cpu.reg_read(reg.UC_MIPS_REG_V0) & 0xffffffff

    def text(self, address):
        raw = bytes(self.cpu.mem_read(address & MASK, PATH_WIDTH))
        return raw.split(b'\0', 1)[0].decode('ascii')

    def rng(self):
        return int.from_bytes(self.cpu.mem_read(self.program.symbols['small__rand'] & MASK, 4), 'little')


def exercise(program):
    paths, cutoffs, tables = reference_tables(program.ROM, (ROOT / 'src/utils/paths.h').read_text(),
                                             (ROOT / 'src/utils/cd_paths.c').read_text())
    machine = Machine(program)
    rows = []
    logo = b'ETC\\ASMK.STR\0'
    if program.ROM.count(logo) != 1:
        raise ValueError('Expected a unique original logo path.')
    logo_pointer = program.LOAD + program.ROM.index(logo) - 0x800

    def check(name, args, returned, out=None, path=None, rng=None, label=None, target=machine):
        guard = b'\xa5' * 32
        target.cpu.mem_write(BUFFER, guard)
        before_rng = target.rng()
        value = target.call(name, args)
        expected = bytearray(guard)
        if out is not None:
            struct.pack_into('<I', expected, OUTPUT - BUFFER, out & 0xffffffff)
        observed = bytes(target.cpu.mem_read(BUFFER, 32))
        if value != returned & 0xffffffff or observed != expected:
            raise ValueError('Native movie result/output mismatch: ' + name)
        if path is not None and target.text(value) != path:
            raise ValueError('Native returned path content mismatch: ' + name)
        if target.rng() != (before_rng if rng is None else rng):
            raise ValueError('Native RNG history mismatch: ' + name)
        row = {'function': name, 'label': label, 'args': args, 'returned': value,
               'output_value': out, 'path': path, 'rng_after': target.rng(),
               'guarded_output_sha256': hashlib.sha256(observed).hexdigest()}
        if target is machine:
            rows.append(row)
        return row

    def path_check(name, other, index, output_value, nullable=True):
        for pointer in (OUTPUT, 0) if nullable else (OUTPUT,):
            check(name, [pointer, *other], PATH_ADDRESS + index * PATH_WIDTH,
                  output_value if pointer else None, paths[index])

    for pointer in (OUTPUT, 0):
        check('get_path_table', [pointer], PATH_ADDRESS, 560 if pointer else None)
        check('get_logo_asmk_path', [pointer], logo_pointer, 49 if pointer else None, 'ETC\\ASMK.STR')
    path_check('get_opening_movie_path', [], 560, 0)
    path_check('get_ending_movie_path', [], 567, 7)
    path_check('get_event1_movie_path', [], 568, 8)
    for unused in (0, 1, -1, 0x80000000, 0x7fffffff):
        path_check('get_ending_movie_path_2', [unused], 567, 7)
    for index in range(6):
        path_check('get_event_movie_path', [index], 568 + index, 8 + index)
    for day in range(12):
        path_check('get_special_movie_path', [day], 574 + day * 6, 14 + day * 2)
        for variant in range(6):
            path_check('get_special_day_movie', [(variant << 16) | day],
                       574 + day * 6 + variant, 14 + day * 2 + variant if variant < 2 else -1)
        for count in range(13 - day):
            first = 14 + day * 2
            limit = sum(cutoffs[index] + 10 for index in range(first, first + count * 2)) - 10
            path_check('get_special_reel_movie_path', [day, count], 574 + day * 6, limit, nullable=False)
    for low in (-1, -32768):
        for event in range(6):
            path_check('get_special_day_movie', [(event << 16) | (low & 0xffff)], 568 + event, 8 + event)
    for index, value in enumerate(cutoffs):
        check('get_movie_duration_maybe', [index], value)
    seeds = [0, 1, 2, 3, 7, 31, 255, 256, 65535, 65536, 0x7fffffff, 0x80000000,
             0xfffffffe, 0xffffffff, 0x12345678, 0x87654321]
    for seed in seeds:
        machine.call('srand', [seed])
        state = seed
        for step in range(16):
            state = (state * 0x41c64e6d + 0x3039) & 0xffffffff
            index = ((state >> 16) & 0x7fff) % 7
            pointer = OUTPUT if step % 2 == 0 else 0
            check('get_random_opening_movie_path', [pointer, 0x13570000 + step],
                  PATH_ADDRESS + (560 + index) * PATH_WIDTH, index if pointer else None,
                  paths[560 + index], state, f'seed-{seed}-step-{step}')
    if set(machine.counts) != set(FUNCTIONS):
        raise ValueError('A declared original movie routine was not actually entered.')

    controls = []
    for kind in ('unsigned-cutoff-load', 'cutoff-data', 'path-data'):
        faulty = Machine(program)
        getter = program.symbols['get_movie_duration_maybe'] & MASK
        if kind == 'unsigned-cutoff-load':
            site = getter + 16
            instruction = int.from_bytes(faulty.cpu.mem_read(site, 4), 'little')
            if instruction >> 26 != 0x21:
                raise ValueError('Unexpected original signed-halfword load for negative control.')
            faulty.cpu.mem_write(site, ((instruction & 0x03ffffff) | (0x25 << 26)).to_bytes(4, 'little'))
            call = ('get_movie_duration_maybe', [48], cutoffs[48], None, None)
        elif kind == 'cutoff-data':
            site = getter + 16
            faulty.cpu.mem_write(CUTOFF_ADDRESS & MASK, struct.pack('<h', cutoffs[0] + 1))
            call = ('get_movie_duration_maybe', [0], cutoffs[0], None, None)
        else:
            site = program.symbols['get_event_movie_path'] & MASK
            address = PATH_ADDRESS + 568 * PATH_WIDTH
            faulty.cpu.mem_write(address & MASK, b'X')
            call = ('get_event_movie_path', [OUTPUT, 0], address, 8, paths[568])
        try:
            check(*call, target=faulty)
        except ValueError as error:
            if not faulty.instructions[site]:
                raise ValueError('A negative control failed before reaching its target.') from error
            controls.append({'kind': kind, 'detected': True, 'observed_target_executions': faulty.instructions[site]})
        else:
            raise ValueError('Movie negative control escaped detection: ' + kind)
    return {'fixture_count': len(rows), 'fixtures': rows, 'original_routines_entered': dict(machine.counts),
            'negative_controls': controls, 'native_tables': tables, 'rng_histories': len(seeds),
            'rng_steps_per_history': 16, 'function_output_stubs': 0,
            'scope': 'Manual valid path/table/RNG contexts; not natural movie construction, decode, audible output, or playback timing.',
            'whole_feature_groups_accepted': 0, 'new_c_bytes': 0}


def verify(output):
    output = Path(output).resolve()
    if not output.is_relative_to(ROOT / '.decomp-lab') or output.exists():
        raise ValueError('Choose a new private report path.')
    program = native.load_program(NATIVE_FUNCTIONS)
    report = exercise(program)
    import unicorn
    module = importlib.import_module('unicorn.unicorn_py3.unicorn')
    library = Path(module.uclib._name).resolve(strict=True)
    report.update(canonical_sha256=hashlib.sha256(program.ROM).hexdigest(),
                  schema_version=1, recorded_utc=datetime.now(timezone.utc).isoformat(),
                  producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  source_hashes={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                 for name in ('src/utils/paths.h', 'src/utils/cd_paths.c')},
                  source_promoted=False, movie_playback_accepted=False,
                  input_modified=False, model_api_calls=0,
                  backend={'version': unicorn.__version__, 'library_sha256': hashlib.sha256(library.read_bytes()).hexdigest(),
                           'binding_sha256': hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()})
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({'fixtures': report['fixture_count'], 'native_routines': len(report['original_routines_entered']),
                      'negative_controls': len(report['negative_controls']), 'function_output_stubs': 0}))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        verify(args.output)
        return 0
    except (OSError, ValueError, struct.error) as error:
        print('[!] ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
