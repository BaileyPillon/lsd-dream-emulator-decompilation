"""Check typed Run callers against original return-producing screen methods.

Graphics initialization is one explicit output contract. This verifies callback
arguments and return ownership, not actual graphics setup or natural screens.
"""
from collections import Counter
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import configure
from tools import verify_native_ai as n
from tools.compile_c import run_stages
from tools.decomp_workbench import candidate_commands
from tools.verify_scripted_ai import backend_identity
from research.compiler.compare_function import elf_function

FUNCTIONS = [
    dict(function='func_8003C1DC', address='0x8003c1dc', bytes=92,
         sha256='f203459fa2735cf984809aeb5243d874c54c14711e5de4b22ef779f9bcc37431'),
    dict(function='func_80058390', address='0x80058390', bytes=116,
         sha256='3d199adb45140134173d8a6aeb5775f38ffeea4f4a374805cc885ddced7ec105'),
    dict(function='timer_get_vtable', address='0x8003e5c8', bytes=16,
         sha256='d238fa5daeb891fd90dea2848259a29f0a9430e25a55d881feaa6fe21a19fea4'),
    dict(function='func_8003DFBC', address='0x8003dfbc', bytes=16,
         sha256='8a93f3c1cad0692ba38e1b86f054de0165974eb7aebff4cea42d988cfd2b098b'),
]
INITIALIZER = dict(function='func_8003E10C', address='0x8003e10c', bytes=372,
    sha256='511d8d2c031c5905ef4852f4d428929181499d3da8f70423994ea68695b40fed')
TABLES = {
    'ui': (0x8006E730, 'func_8003C1DC', '914a1a084ed7c13dc2045bafc3f11823ef296c38ddd5ee2bc02ecdf9953fd6a6'),
    'main': (0x80086B60, 'func_8003C1DC', '0c6ca11f3389f78f05b63ee4e4f0be3dfeebd9810b44c058f88948445f3fb8c2'),
    'chart': (0x80087AAC, 'func_80058390', 'b934f562f72a63e92c2ab08c70973ce671ee10b81634e7ce8ef5f662503f9979'),
}
CONSUMERS = ('screen_run_ui', 'screen_run_main', 'screen_run_chart')
CODE, BASE, BYTES, OBJECT = 0x180000, 0x110000, 0x280, 0x110020
GP = 0x8008A808
digest = lambda data: hashlib.sha256(data).hexdigest()


def compile_consumers(output):
    source = output / 'callers.c'
    source.write_text('#include "' + str(ROOT / 'research/screen_run/consumer.c') + '"\n'
                      '#include "' + str(ROOT / 'research/screen_run/abi_checks.h') + '"\n')
    obj, elf, binary = [output / part for part in ('callers.o', 'callers.elf', 'callers.bin')]
    commands = candidate_commands('src/menu/ui_screen.c', source, obj)
    commands[1].append('-Werror')
    with (output / 'compiler.log').open('xb') as log:
        saved = os.dup(2)
        try:
            os.dup2(log.fileno(), 2)
            run_stages(commands)
        finally:
            os.dup2(saved, 2)
            os.close(saved)
        linker = output / 'callers.ld'
        linker.write_text('SECTIONS { .text ' + hex(CODE) + ' : SUBALIGN(4) { *(.text) } '
            '/DISCARD/ : { *(.reginfo) *(.MIPS.abiflags) *(.pdr) *(.gnu.attributes) } }\n')
        subprocess.run([configure.CROSS + 'ld', '-EL', '-nostdlib', '-T', str(linker), '-o', str(elf), str(obj)],
                       check=True, stdout=log, stderr=log)
        subprocess.run([configure.CROSS + 'objcopy', '-O', 'binary', '--only-section=.text', str(elf), str(binary)], check=True)
    symbols = [line.split() for line in subprocess.check_output(
        [configure.CROSS + 'nm', '-S', '--defined-only', str(elf)], text=True).splitlines()]
    records = []
    for name in CONSUMERS:
        matches = [row for row in symbols if len(row) == 4 and row[-1] == name]
        if len(matches) != 1:
            raise ValueError('Require each complete sized screen caller.')
        address, size = int(matches[0][0], 16), int(matches[0][1], 16)
        code, ownership = elf_function(elf.read_bytes(), name, address)
        if len(code) != size or code != binary.read_bytes()[address - CODE:address - CODE + size]:
            raise ValueError('The linked caller does not cover its complete symbol.')
        records.append(dict(function=name, address=hex(address), bytes=size, sha256=digest(code)))
    cursor = CODE
    for record in sorted(records, key=lambda row: int(row['address'], 16)):
        if int(record['address'], 16) != cursor:
            raise ValueError('The three analysis callers must occupy contiguous complete text.')
        cursor += record['bytes']
    if cursor - CODE != len(binary.read_bytes()):
        raise ValueError('Unexpected code outside the three typed screen callers.')
    return binary.read_bytes(), records, commands


def cases():
    results = (-0x80000000, -1, 0, 1, 2, 3, 0x7FFFFFFF)
    modes = (-0x80000000, -1, 0, 1, 2, 0x7FFFFFFF)
    for kind in TABLES:
        flags = (0, 1, 0x80000000) if kind == 'chart' else (0,)
        for result, flag, segment, graphics, mode in itertools.product(results, flags,
                (0, 0x80000000, 0xA0000000), (0x118020, 0x80118020, 0xA0118020), modes):
            yield dict(kind=kind, result=n.u32(result), video_flag=flag,
                       segment=segment, graphics=graphics, mode=n.u32(mode))


def fixture(case):
    data = bytearray((i * 37 + 91) & 255 for i in range(BYTES))
    struct.pack_into('<I', data, 0x20, TABLES[case['kind']][0])
    struct.pack_into('<I', data, 0x58, 0x76543210)
    if case['kind'] == 'chart':
        struct.pack_into('<I', data, 0x258, case['video_flag'] ^ 0x80000001)
    return data


def expected(case):
    data = fixture(case)
    struct.pack_into('<I', data, 0x58, case['result'])
    if case['kind'] == 'chart':
        struct.pack_into('<I', data, 0x258, case['video_flag'])
    result = 2 if case['kind'] == 'chart' and case['video_flag'] else case['result']
    return bytes(data), result


class Machine(n.Machine):
    def __init__(self, code, consumers, tracked=()):
        self.records = FUNCTIONS + consumers
        self.ranges = [(int(row['address'], 16) & n.MASK, row['bytes']) for row in self.records]
        self.entries = {int(row['address'], 16) & n.MASK: row['function'] for row in self.records}
        self.counts = Counter()
        self.tracked = tuple(address & n.MASK for address in tracked)
        self.hits = Counter()
        self.initializer_entries = 0
        self.starts = {name.removeprefix('screen_run_'): int(row['address'], 16)
                       for name, row in zip(CONSUMERS, consumers)}
        super().__init__(start=CODE, native_functions=FUNCTIONS)
        self.cpu.mem_write(CODE, code)

    def hook(self, cpu, address, size, unused):
        physical = address & n.MASK
        if physical in self.tracked:
            self.hits[physical] += 1
        if physical == int(INITIALIZER['address'], 16) & n.MASK:
            self.initializer_entries += 1
            args = tuple(cpu.reg_read(register) for register in
                         (n.reg.UC_MIPS_REG_A0, n.reg.UC_MIPS_REG_A1, n.reg.UC_MIPS_REG_A2))
            if args != self.arguments:
                raise ValueError('A Run caller changed a graphics-initializer argument.')
            self.trace.append(INITIALIZER['function'] + ':contract')
            cpu.mem_write(OBJECT + 0x38, struct.pack('<I', self.case['result']))
            if self.case['kind'] == 'chart':
                cpu.mem_write(OBJECT + 0x238, struct.pack('<I', self.case['video_flag']))
            target = cpu.reg_read(n.reg.UC_MIPS_REG_RA)
            for index, register in enumerate(n.VOLATILE):
                cpu.reg_write(register, n.u32(0xBC000000 + index * 0x10203))
            cpu.reg_write(n.reg.UC_MIPS_REG_V0, 0xDEADBEEF)
            cpu.reg_write(n.reg.UC_MIPS_REG_PC, target)
            return
        if not any(start <= physical < start + length for start, length in self.ranges):
            raise ValueError('Execution escaped the declared methods, callers and initializer contract.')
        name = self.entries.get(physical)
        if name:
            self.counts[name] += 1
            self.trace.append(name)
            if name in ('func_8003C1DC', 'func_80058390'):
                args = tuple(cpu.reg_read(register) for register in
                             (n.reg.UC_MIPS_REG_A0, n.reg.UC_MIPS_REG_A1, n.reg.UC_MIPS_REG_A2))
                if args != self.arguments:
                    raise ValueError('The typed screen caller changed an argument.')
        word = struct.unpack('<I', bytes(cpu.mem_read(physical, 4)))[0]
        opcode = word >> 26
        if opcode in (0x28, 0x29, 0x2A, 0x2B, 0x2E, 0x38):
            base = cpu.reg_read(n.reg.UC_MIPS_REG_0 + ((word >> 21) & 31))
            displacement = ((word & 65535) ^ 32768) - 32768
            destination = (base + displacement) & n.MASK
            if opcode != 0x2B or not n.STACK - 0x100 <= destination <= n.STACK - 4:
                raise ValueError('A method attempted a store outside its owned stack frame.')

    def run(self, case, typed):
        self.case, self.trace, self.hits = case, [], Counter()
        self.arguments = (OBJECT | case['segment'], case['graphics'], case['mode'])
        cpu = self.cpu
        cpu.mem_write(BASE, bytes(fixture(case)))
        guard = bytes([0xC9]) * 0x500
        cpu.mem_write(n.STACK - 0x400, guard)
        saved = [n.u32(0xAD000000 + index * 0x10203) for index in range(len(n.SAVED))]
        for register, value in zip(n.SAVED, saved):
            cpu.reg_write(register, value)
        for register, value in ((n.reg.UC_MIPS_REG_SP, n.STACK), (n.reg.UC_MIPS_REG_GP, GP),
                (n.reg.UC_MIPS_REG_RA, n.END), (n.reg.UC_MIPS_REG_A0, self.arguments[0]),
                (n.reg.UC_MIPS_REG_A1, self.arguments[1]), (n.reg.UC_MIPS_REG_A2, self.arguments[2]),
                (n.reg.UC_MIPS_REG_A3, 0xBACD5678), (n.reg.UC_MIPS_REG_V0, 0x12345678)):
            cpu.reg_write(register, value)
        start = self.starts[case['kind']] if typed else n.h.symbols[TABLES[case['kind']][1]] & n.MASK
        cpu.emu_start(start, n.END, count=1000)
        if (cpu.reg_read(n.reg.UC_MIPS_REG_PC) != n.END
                or cpu.reg_read(n.reg.UC_MIPS_REG_SP) != n.STACK
                or cpu.reg_read(n.reg.UC_MIPS_REG_GP) != GP
                or cpu.reg_read(n.reg.UC_MIPS_REG_RA) != n.END
                or [cpu.reg_read(register) for register in n.SAVED] != saved
                or bytes(cpu.mem_read(n.STACK - 0x400, 0x300)) != guard[:0x300]
                or bytes(cpu.mem_read(n.STACK, 0x100)) != guard[0x400:]):
            raise ValueError('Screen return violated guarded stack or saved ABI.')
        wanted_trace = ['func_8003C1DC', 'timer_get_vtable', INITIALIZER['function'] + ':contract']
        if case['kind'] == 'chart':
            wanted_trace = ['func_80058390', 'func_8003DFBC'] + wanted_trace
        if typed:
            wanted_trace.insert(0, 'screen_run_' + case['kind'])
        if self.trace != wanted_trace:
            raise ValueError('Unexpected original screen dispatch order.')
        return bytes(cpu.mem_read(BASE, BYTES)), cpu.reg_read(n.reg.UC_MIPS_REG_V0)


def controls(code, consumers):
    faults = []
    specifications = (
        ('func_8003C1DC', 'ui', 'wrong_result_field', 0x8E420038, 0x8E420034),
        ('func_80058390', 'chart', 'inverted_video_flag', 0x14400002, 0x10400002),
        ('func_80058390', 'chart', 'wrong_chart_result_field', 0x8E430038, 0x8E430034),
    )
    for function, kind, reason, original, replacement in specifications:
        record = next(row for row in FUNCTIONS if row['function'] == function)
        start = int(record['address'], 16)
        body = n.h.target(start, record['bytes'])
        offsets = [index * 4 for index, (word,) in enumerate(struct.iter_unpack('<I', body)) if word == original]
        if len(offsets) != 1:
            raise ValueError('A reviewed screen fault must select one complete instruction.')
        address = start + offsets[0]
        machine = Machine(code, consumers, (address,))
        machine.cpu.mem_write(address & n.MASK, struct.pack('<I', replacement))
        for case in cases():
            if case['kind'] != kind:
                continue
            actual = machine.run(case, True)
            if actual != expected(case):
                if not machine.hits[address & n.MASK]:
                    raise ValueError('A fault was rejected without executing its changed instruction.')
                faults.append(dict(kind=reason, function=function, function_offset=offsets[0],
                    fixture=case, changed_instruction_hits=machine.hits[address & n.MASK],
                    wrong_return_word=actual[1] != expected(case)[1], wrong_buffer=actual[0] != expected(case)[0]))
                break
        else:
            raise ValueError('A screen return fault was not detected.')
    return faults


def verify(output):
    dependencies = n.evidence_dependencies('research/screen_run/verify.py', 'research/screen_run/consumer.c',
        'research/screen_run/abi_checks.h', 'src/menu/ui_screen.c', 'src/menu/ui_screen.h',
        'src/menu/main_menu.c', 'src/menu/main_menu.h', 'src/menu/main_menu_post.c',
        'src/menu/graph_screen.c', 'src/menu/graph_screen.h', 'src/game/game_flow.c', 'src/game/game_flow.h',
        'tools/verify_scripted_ai.py', 'tools/compile_c.py', 'tools/decomp_workbench.py',
        'research/compiler/compare_function.py', 'tools/gcc263/cc1')
    before = {path: digest(path.read_bytes()) for path in dependencies}
    n.initialize_backend(n.load_program(FUNCTIONS + [INITIALIZER]))
    backend = backend_identity()
    code, consumers, commands = compile_consumers(output)
    for table, function, checksum in TABLES.values():
        if (digest(n.h.target(table, 0x48)) != checksum
                or struct.unpack('<I', n.h.target(table + 0x44, 4))[0] != n.h.symbols[function]):
            raise ValueError('An original Run table binding changed.')
    if struct.unpack('<I', n.h.target(0x8006E878 + 0x44, 4))[0] != n.h.symbols[INITIALIZER['function']]:
        raise ValueError('The original timer initializer slot changed.')
    machine = Machine(code, consumers)
    identities, groups, snapshots = set(), Counter(), hashlib.sha256()
    for case in cases():
        identity = digest(json.dumps(case, sort_keys=True).encode() + bytes(fixture(case)))
        if identity in identities:
            raise ValueError('Repeated initialized screen interface input requires classification.')
        identities.add(identity)
        wanted = expected(case)
        for typed in (False, True):
            actual = machine.run(case, typed)
            if actual != wanted:
                raise ValueError('Original screen method or typed caller disagrees with return ownership: ' + repr(case))
            snapshots.update(bytes.fromhex(identity) + bytes([typed]) + actual[0] + struct.pack('<I', actual[1]))
        groups[case['kind']] += 1
    faults = controls(code, consumers)
    for record in FUNCTIONS + consumers + [INITIALIZER]:
        if digest(bytes(machine.cpu.mem_read(int(record['address'], 16) & n.MASK, record['bytes']))) != record['sha256']:
            raise ValueError('Positive code or a contracted original body changed.')
    for table, _, checksum in TABLES.values():
        if digest(bytes(machine.cpu.mem_read(table & n.MASK, 0x48))) != checksum:
            raise ValueError('A positive original screen table changed.')
    if (backend_identity() != backend or n.load_program(FUNCTIONS + [INITIALIZER]).ROM != n.h.ROM
            or any(digest(path.read_bytes()) != checksum for path, checksum in before.items())):
        raise ValueError('A source, original input, backend or canonical build changed.')
    report = dict(status='passed_bounded_screen_run_interfaces', initialized_interface_cases=len(identities),
        positive_native_executions=2 * len(identities), case_groups=dict(groups), original_functions_executed=FUNCTIONS,
        compiled_analysis_callers=consumers, actual_entry_counts=dict(machine.counts),
        dependency_output_contracts=[dict(**INITIALIZER, positive_entries=machine.initializer_entries,
            original_body_executed=False, scope='Checks all three arguments, writes the supplied result and chart flag, '
                'clobbers caller-saved registers and returns a deliberately unrelated V0. Does not execute graphics initialization.')],
        target_ABI_assertions=8, Run_slot='0x44', original_Run_bindings={key: dict(table_address=hex(value[0]),
            function=value[1], prefix_bytes=0x48, prefix_sha256=value[2]) for key, value in TABLES.items()},
        input_and_output_sha256=snapshots.hexdigest(), negative_controls=faults, backend_identity=backend,
        compiler_commands=commands, warning_errors_enabled_for_analysis_callers=True,
        producer_dependencies=[dict(path=path.relative_to(ROOT).as_posix(), sha256=checksum) for path, checksum in before.items()],
        canonical_executable_sha256=digest(n.h.ROM), original_and_current_build_equal=True,
        new_game_function_C_bytes=0, original_behavior_modified=False, model_api_calls=0,
        whole_feature_groups_accepted=0, whole_NPC_encounters_accepted=0,
        scope='Three typed Run callers execute original UI/chart methods and table getters. Full guarded objects, '
            'three arguments, original call order, return words and saved ABI are checked. The graphics initializer '
            'is one explicit output contract. No real factory, graphics setup, natural screen history, whole-feature '
            'acceptance or PS1 timing claim is made.')
    with (output / 'report.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(status=report['status'], initialized_interface_cases=len(identities),
        positive_native_executions=2 * len(identities), negative_controls=len(faults),
        graphics_initializer_contracts=1, new_C_bytes=0), indent=2), flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='Fresh private directory inside .decomp-lab.')
    args = parser.parse_args(argv)
    try:
        output, lab = (ROOT / args.output).resolve(), (ROOT / '.decomp-lab').resolve()
        if output == lab or not output.is_relative_to(lab) or output.exists():
            raise ValueError('Choose a fresh private output directory; earlier evidence is preserved.')
        if sys.platform == 'win32':
            raise ValueError('Use the matching Linux/WSL compiler and optional analysis dependencies.')
        output.mkdir(parents=True, exist_ok=False)
        verify(output)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('[!] ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
