"""Check the recovered Open/Read ABI on bounded original driver paths.

Requires a current matching WSL build and requirements-card-heap.txt. Original
CD guard paths, debug methods and slot copying execute without output stubs.
No disc/SDK I/O, destination writes, natural histories or timing are accepted.
"""
import argparse
from collections import Counter
import hashlib
import importlib
import itertools
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import configure
from research.compiler.compare_function import elf_function
from tools import verify_native_ai as native
from tools.decomp_workbench import candidate_commands
from tools.verify_actor_children import build_inputs, output_directory, symbol_diagnostic

CODE, BASE, OBJECT, TABLE_BASE, TABLE = 0x180000, 0x110000, 0x110020, 0x112000, 0x112020
STACK, END, MASK, GP = 0x1E0000, 0x1F0000, 0x1FFFFFFF, 0x8008A808
WORDS = (0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF)
COPIED_SLOTS = (16, 17, 18, 19, 20, 21, 22, 26, 27, 28, 29)
CONSUMERS = ('file_open_common', 'file_read_common', 'file_open_debug', 'file_read_debug')
SLOTS = {'open': 0x44, 'read': 0x54}
TABLE_NAMES = {'cd': 'g_CD_FILE_DRIVER_VTABLE', 'debug': 'g_DEBUG_FILE_DRIVER_VTABLE'}
GLOBALS = ('g_CdFrameActive', 'g_CdFrameParam', 'g_CdReadBusy', 'g_CdLocked')
DEPENDENCIES = ('research/file_driver/verify.py', 'research/file_driver/consumer.c',
    'research/file_driver/abi_checks.h', 'research/file_driver/function-ranges.json',
    'research/compiler/compare_function.py', 'tools/decomp_workbench.py',
    'tools/verify_native_ai.py', 'tools/verify_actor_children.py', 'tools/compile_c.py',
    'tools/inventory_vtables.py', 'tools/progress.py', 'configure.py',
    'requirements.txt', 'requirements-card-heap.txt')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def cases():
    for method in SLOTS:
        for view, driver, state in (('common', 'cd', 'busy'), ('common', 'cd', 'state'),
                                    ('common', 'debug', 'empty'), ('debug', 'debug', 'empty')):
            for arguments in itertools.product(WORDS, repeat=3 if method == 'open' else 2):
                yield dict(method=method, view=view, driver=driver, state=state, arguments=arguments)


def expected_trace(case, typed):
    result = [case['driver'] + '_file_driver_' + case['method']]
    if case['driver'] == 'cd':
        result += ['cd_file_driver_lock', 'cd_file_driver_unlock']
    return (['file_' + case['method'] + '_' + case['view']] if typed else []) + result


def validate_observation(case, typed, actual):
    """Reject argument/return, ordering, ownership and preserved-ABI failures."""
    if actual['arguments'] != (OBJECT | 0x80000000, *case['arguments']):
        raise ValueError('Driver entry arguments changed.')
    if actual['trace'] != expected_trace(case, typed):
        raise ValueError('Unexpected original driver dispatch order.')
    if case['method'] == 'read' and actual['result'] != 0:
        raise ValueError('Read result word differs from the scoped original path.')
    if actual['locks'] != ([1, 0] if case['driver'] == 'cd' else []):
        raise ValueError('Original lock transition changed.')
    for key in ('object_equal', 'table_equal', 'globals_equal', 'saved_abi', 'stack_guards'):
        if actual[key] is not True:
            raise ValueError('Guard or ownership check failed: ' + key)


def compiler_stages(commands, log):
    data = None
    for command in commands:
        result = subprocess.run(command, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        log.write(result.stderr)
        if result.returncode:
            return result.returncode, result.stderr.decode(errors='replace')
        data = result.stdout
    return 0, ''


def compile_consumers(output):
    source = output / 'callers.c'
    source.write_text('#include "' + str(ROOT / 'research/file_driver/consumer.c') + '"\n'
        '#include "' + str(ROOT / 'research/file_driver/abi_checks.h') + '"\n')
    obj, elf, binary = (output / name for name in ('callers.o', 'callers.elf', 'callers.bin'))
    commands = candidate_commands('src/file/file_buf.c', source, obj)
    commands[1].append('-Werror')
    with (output / 'compiler.log').open('xb') as log:
        status, error = compiler_stages(commands, log)
        if status:
            raise ValueError('Owned typed callers did not compile: ' + error)
        linker = output / 'callers.ld'
        linker.write_text('SECTIONS { .text ' + hex(CODE) + ' : SUBALIGN(4) { *(.text) } '
            '/DISCARD/ : { *(.reginfo) *(.MIPS.abiflags) *(.pdr) *(.gnu.attributes) } }\n')
        subprocess.run([configure.CROSS + 'ld', '-EL', '-nostdlib', '-T', str(linker), '-o', str(elf), str(obj)],
                       stdout=log, stderr=log, check=True)
        subprocess.run([configure.CROSS + 'objcopy', '-O', 'binary', '--only-section=.text', str(elf), str(binary)], check=True)
    symbols = [line.split() for line in subprocess.check_output(
        [configure.CROSS + 'nm', '-S', '--defined-only', str(elf)], text=True).splitlines()]
    code, records = binary.read_bytes(), []
    for name in CONSUMERS:
        matches = [row for row in symbols if len(row) == 4 and row[-1] == name]
        if len(matches) != 1:
            raise ValueError('Require each complete sized owned caller: ' + name)
        address, size = int(matches[0][0], 16), int(matches[0][1], 16)
        body, _ = elf_function(elf.read_bytes(), name, address)
        if len(body) != size or body != code[address - CODE:address - CODE + size]:
            raise ValueError('Incomplete caller symbol: ' + name)
        records.append(dict(function=name, address=hex(address), bytes=size, sha256=sha(body)))
    cursor = CODE
    for record in sorted(records, key=lambda row: int(row['address'], 16)):
        if int(record['address'], 16) != cursor:
            raise ValueError('Owned callers must fill contiguous complete text.')
        cursor += record['bytes']
    if cursor - CODE != len(code):
        raise ValueError('Unexpected helper code outside the four owned callers.')
    return code, records, commands


def compiler_controls(output):
    specs = (
        ('common_read_void', 'file_buf.h', 's32 (*Read)', 'void (*Read)', 'void'),
        ('debug_read_void', 'debug_file_driver.h', 's32 (*debug_file_driver_read)',
         'void (*debug_file_driver_read)', 'void'),
        ('debug_open_receiver_only', 'debug_file_driver.h',
         '(*debug_file_driver_open)(struct file_buf *, s32, s32, s32)',
         '(*debug_file_driver_open)(struct file_buf *)', 'arguments'),
    )
    results = []
    for name, header, old, new, diagnostic in specs:
        folder = output / name
        (folder / 'file').mkdir(parents=True)
        for original in ('file_buf.h', 'debug_file_driver.h'):
            text = (ROOT / 'src/file' / original).read_text()
            if original == header:
                if text.count(old) != 1:
                    raise ValueError('Ambiguous negative header substitution.')
                text = text.replace(old, new)
            (folder / 'file' / original).write_text(text)
        source = folder / 'callers.c'
        source.write_text('#include "' + str(ROOT / 'research/file_driver/consumer.c') + '"\n')
        commands = candidate_commands('src/file/file_buf.c', source, folder / 'callers.o')
        commands[0].insert(1, '-I' + str(folder))
        commands[1].append('-Werror')
        with (folder / 'compiler.log').open('xb') as log:
            status, error = compiler_stages(commands, log)
        if not status or diagnostic not in error:
            raise ValueError('Negative interface compiler control was not specifically rejected: ' + name)
        results.append(dict(name=name, rejected=True, diagnostic_contains=diagnostic,
                            diagnostic_sha256=sha(error.encode())))
    return results


def backend_identity():
    import unicorn
    module = importlib.import_module('unicorn.unicorn_py3.unicorn')
    if unicorn.__version__ != '2.1.2':
        raise ValueError('Use the isolated pinned requirements-card-heap.txt backend.')
    return dict(package_version=unicorn.__version__,
        loaded_library_sha256=sha(Path(module.uclib._name).read_bytes()),
        binding_sha256=sha(Path(module.__file__).read_bytes()))


class Machine:
    """Closed original instruction graph with observed writes; no native stubs."""
    def __init__(self, program, ranges, code, consumers, fault=None):
        import unicorn as u
        from unicorn import mips_const as r
        self.u, self.r, self.program, self.records = u, r, program, consumers
        self.cpu = u.Uc(u.UC_ARCH_MIPS, u.UC_MODE_MIPS32 | u.UC_MODE_LITTLE_ENDIAN)
        self.cpu.mem_map(0, 0x200000)
        self.cpu.mem_write(program.LOAD & MASK, program.ROM[0x800:])
        self.cpu.mem_write(CODE, code)
        self.ranges = ranges + [(int(row['address'], 16), int(row['address'], 16) + row['bytes'], row['function'])
                                for row in consumers]
        self.entries = {start: name for start, _, name in self.ranges}
        self.starts = {name: start for start, _, name in self.ranges}
        self.saved = [getattr(r, 'UC_MIPS_REG_S' + str(i)) for i in range(8)] + [r.UC_MIPS_REG_FP]
        self.argregs = [getattr(r, 'UC_MIPS_REG_A' + str(i)) for i in range(4)]
        self.counts, self.fault, self.fault_hits = Counter(), fault, 0
        if fault:
            address, old, new = fault
            if struct.unpack('<I', self.cpu.mem_read(address & MASK, 4))[0] != old:
                raise ValueError('A fault must match the reviewed qualified instruction.')
            self.cpu.mem_write(address & MASK, struct.pack('<I', new))
        self.cpu.hook_add(u.UC_HOOK_CODE, self.hook)
        self.cpu.hook_add(u.UC_HOOK_MEM_WRITE, self.write_hook)

    def hook(self, cpu, address, size, unused):
        pc = address & MASK
        if self.fault and pc == (self.fault[0] & MASK):
            self.fault_hits += 1
        if not any(start <= pc < end for start, end, _ in self.ranges):
            raise ValueError('Execution escaped the qualified original graph and owned callers.')
        name = self.entries.get(pc)
        if name:
            self.counts[name] += 1
            self.trace.append(name)
            if name in ('cd_file_driver_open', 'cd_file_driver_read',
                        'debug_file_driver_open', 'debug_file_driver_read'):
                self.observed_args = tuple(cpu.reg_read(reg) for reg in self.argregs[:len(self.arguments)])

    def write_hook(self, cpu, access, address, size, value, unused):
        physical = address & MASK
        if size == 4 and STACK - 0x200 <= physical <= STACK - 4:
            return
        if (self.phase == 'copy' and size == 4 and physical - TABLE in [4 * i for i in COPIED_SLOTS]):
            return
        if (self.phase == 'method' and self.case['driver'] == 'cd' and size == 4
                and physical == (self.program.symbols['g_CdLocked'] & MASK)):
            self.locks.append(value)
            return
        raise ValueError('Forbidden native write outside the owned stack, copied slots and CD lock.')

    def invoke(self, start, arguments):
        cpu, r = self.cpu, self.r
        self.trace, self.locks, self.observed_args = [], [], None
        self.arguments = arguments
        guard = b'\xC9' * 0x380
        cpu.mem_write(STACK - 0x300, guard)
        saved = [0xAD000000 + i * 0x10203 for i in range(len(self.saved))]
        for register, value in zip(self.saved, saved):
            cpu.reg_write(register, value)
        for register, value in ((r.UC_MIPS_REG_SP, STACK), (r.UC_MIPS_REG_GP, GP),
                               (r.UC_MIPS_REG_RA, END), (r.UC_MIPS_REG_V0, 0x12345678)):
            cpu.reg_write(register, value)
        for index, reg in enumerate(self.argregs):
            cpu.reg_write(reg, arguments[index] if index < len(arguments) else 0xBACD5678)
        cpu.emu_start(start & MASK, END, count=2000)
        return dict(result=cpu.reg_read(r.UC_MIPS_REG_V0), trace=list(self.trace),
            arguments=self.observed_args, locks=list(self.locks),
            saved_abi=(cpu.reg_read(r.UC_MIPS_REG_PC) == END
                and cpu.reg_read(r.UC_MIPS_REG_SP) == STACK and cpu.reg_read(r.UC_MIPS_REG_GP) == GP
                and cpu.reg_read(r.UC_MIPS_REG_RA) == END
                and [cpu.reg_read(register) for register in self.saved] == saved),
            stack_guards=(bytes(cpu.mem_read(STACK - 0x300, 0x100)) == guard[:0x100]
                          and bytes(cpu.mem_read(STACK, 0x80)) == guard[-0x80:]))

    def run(self, case, typed):
        self.case = case
        p, cpu = self.program, self.cpu
        obj = bytearray((37 * i + 91) & 255 for i in range(0x20 + 0x2C + 0x20))
        source = p.symbols[TABLE_NAMES[case['driver']]]
        struct.pack_into('<I', obj, 0x20, TABLE | 0x80000000 if case['view'] == 'common' else source)
        opened = int(case['method'] == 'open') if case['state'] == 'state' else 1
        struct.pack_into('<I', obj, 0x20 + 0x0C, opened)
        struct.pack_into('<H', obj, 0x20 + 0x28, 1)
        cpu.mem_write(BASE, bytes(obj))
        table = bytearray(b'\xA7' * 0x20 + p.target(p.symbols['g_FILE_BUF_VTABLE'], 0x7C) + b'\xD3' * 0x20)
        cpu.mem_write(TABLE_BASE, bytes(table))
        if case['view'] == 'common':
            self.phase = 'copy'
            observation = self.invoke(self.starts['file_driver_copy_vtable_slots'],
                                      (TABLE | 0x80000000, source))
            for slot in COPIED_SLOTS:
                table[0x20 + 4 * slot:0x24 + 4 * slot] = p.target(source + 4 * slot, 4)
            if (observation['trace'] != ['file_driver_copy_vtable_slots']
                    or not observation['saved_abi'] or not observation['stack_guards']
                    or bytes(cpu.mem_read(TABLE_BASE, len(table))) != table):
                raise ValueError('Original slot copier changed a slot, guard or preserved ABI.')
        global_values = (1, 0, int(case['state'] == 'busy'), 0)
        for name, value in zip(GLOBALS, global_values):
            cpu.mem_write(p.symbols[name] & MASK, struct.pack('<I', value))
        self.phase = 'method'
        name = ('file_' + case['method'] + '_' + case['view'] if typed
                else case['driver'] + '_file_driver_' + case['method'])
        observation = self.invoke(self.starts[name], (OBJECT | 0x80000000, *case['arguments']))
        observation.update(object_equal=bytes(cpu.mem_read(BASE, len(obj))) == obj,
            table_equal=bytes(cpu.mem_read(TABLE_BASE, len(table))) == table,
            globals_equal=all(struct.unpack('<I', cpu.mem_read(p.symbols[name] & MASK, 4))[0] == value
                              for name, value in zip(GLOBALS, global_values)))
        validate_observation(case, typed, observation)
        return observation


def negative_controls(program, ranges, code, consumers):
    by_name = {row['function']: row for row in consumers}
    specifications = [('native_read_result', int(program.symbols['debug_file_driver_read']) + 4,
                       0x00001021, 0x34020001, 'read', 'debug')]
    record = by_name['file_read_common']
    address, length = int(record['address'], 16), record['bytes']
    body = code[address - CODE:address - CODE + length]
    loads = [(address + i * 4, word) for i, (word,) in enumerate(struct.iter_unpack('<I', body))
             if word >> 26 == 0x23 and word & 0xFFFF == 0x54]
    if len(loads) != 1:
        raise ValueError('Require one qualified common Read slot load.')
    pc, word = loads[0]
    specifications.append(('wrong_read_slot', pc, word, (word & 0xFFFF0000) | 0x50, 'read', 'common'))
    for method, argument, replacement in (('read', 2, 0x00003021), ('open', 3, 0x00003821)):
        row = by_name['file_' + method + '_common']
        start, length = int(row['address'], 16), row['bytes']
        words = list(struct.iter_unpack('<I', code[start - CODE:start - CODE + length]))
        delays = [(start + 4 * (i + 1), words[i + 1][0]) for i, (word,) in enumerate(words[:-1])
                  if word & 0xFC00003F == 9]
        if len(delays) != 1 or delays[0][1] != 0:
            raise ValueError('Require the reviewed unfilled indirect-call delay slot.')
        specifications.append(('lost_argument_' + str(argument), delays[0][0], 0, replacement, method, 'common'))
    copier = next(row for start, end, row in ranges if row == 'file_driver_copy_vtable_slots')
    start = program.symbols[copier]
    length = next(end - begin for begin, end, name in ranges if name == copier)
    stores = [(start + 4 * i, word) for i, (word,) in enumerate(struct.iter_unpack('<I', program.target(start, length)))
              if word >> 26 == 0x2B and (word >> 21) & 31 == 4 and word & 0xFFFF == 0x54]
    if len(stores) != 1:
        raise ValueError('Require one original copied Read slot store.')
    specifications.append(('omitted_copied_read_slot', stores[0][0], stores[0][1], 0, 'read', 'common'))
    faults = []
    for name, address, old, new, method, view in specifications:
        machine = Machine(program, ranges, code, consumers, (address, old, new))
        witness = dict(method=method, view=view, driver='debug', state='empty',
                       arguments=(0x80000000, 0xFFFFFFFF, 1) if method == 'open' else (0x80000000, 0xFFFFFFFF))
        try:
            machine.run(witness, True)
        except ValueError as error:
            if not machine.fault_hits:
                raise ValueError('Rejected fault was not executed: ' + name) from error
            faults.append(dict(name=name, address=hex(address), executed=machine.fault_hits,
                               rejected=True, reason=str(error)))
        else:
            raise ValueError('Native fault escaped detection: ' + name)
    return faults


def verify(output):
    before = build_inputs()
    dependencies = {path: sha((ROOT / path).read_bytes()) for path in DEPENDENCIES}
    functions = json.loads((ROOT / 'research/file_driver/function-ranges.json').read_text())
    program = native.load_program(functions)
    ranges, diagnostic = symbol_diagnostic(program, output, functions)
    symbols = [line.split() for line in subprocess.check_output(
        [configure.CROSS + 'nm', '-S', '--defined-only', str(output / 'canonical-symbols.elf')],
        text=True).splitlines()]
    for record in functions:
        rows = [row for row in symbols if len(row) == 4 and row[-1] == record['function']]
        if (len(rows) != 1 or int(rows[0][0], 16) != int(record['address'], 16)
                or int(rows[0][1], 16) != record['bytes']):
            raise ValueError('Independent GNU function extent disagrees: ' + record['function'])
    diagnostic['independent_GNU_sized_function_extents_equal'] = True
    backend = backend_identity()
    code, consumers, commands = compile_consumers(output)
    bindings = []
    for driver, table_name in TABLE_NAMES.items():
        for method, slot in SLOTS.items():
            table, function = program.symbols[table_name], driver + '_file_driver_' + method
            target = struct.unpack('<I', program.target(table + slot, 4))[0]
            if target != program.symbols[function]:
                raise ValueError('Canonical original table binding differs: ' + function)
            bindings.append(dict(table=table_name, slot=hex(slot), function=function, address=hex(target)))
    machine = Machine(program, ranges, code, consumers)
    identities, snapshots, groups = set(), hashlib.sha256(), Counter()
    for case in cases():
        identity = sha(json.dumps(case, sort_keys=True).encode())
        if identity in identities:
            raise ValueError('Repeated initialized interface case.')
        identities.add(identity)
        for typed in (False, True):
            observation = machine.run(case, typed)
            snapshots.update(json.dumps(dict(case=case, typed=typed, observation=observation), sort_keys=True).encode())
        groups['/'.join(case[key] for key in ('view', 'driver', 'method', 'state'))] += 1
    faults = negative_controls(program, ranges, code, consumers)
    compiler_faults = compiler_controls(output)
    for row in functions + consumers:
        if sha(bytes(machine.cpu.mem_read(int(row['address'], 16) & MASK, row['bytes']))) != row['sha256']:
            raise ValueError('Positive original or owned code changed.')
    if (before != build_inputs() or dependencies != {path: sha((ROOT / path).read_bytes()) for path in dependencies}
            or backend_identity() != backend or native.load_program(functions).ROM != program.ROM):
        raise ValueError('Build inputs, producer, backend or canonical executable changed.')
    report = dict(status='passed_bounded_file_driver_interfaces', initialized_interface_cases=len(identities),
        positive_method_runs=2 * len(identities), actual_entry_counts=dict(machine.counts), case_groups=dict(groups),
        original_functions=functions, compiled_analysis_callers=consumers, target_ABI_assertions=10,
        original_slot_bindings=bindings, copied_slot_indices=COPIED_SLOTS, original_symbol_diagnostic=diagnostic,
        dependency_output_stubs=0, negative_controls=faults, negative_compiler_controls=compiler_faults,
        observations_sha256=snapshots.hexdigest(), backend_identity=backend,
        compiler_commands=commands, analysis_caller_warnings_are_errors=True,
        build_input_hashes=before, producer_dependencies=dependencies,
        canonical_executable_sha256=sha(program.ROM), original_and_current_build_equal=True,
        new_game_function_C_bytes=0, original_behavior_modified=False, whole_feature_groups_accepted=0,
        scope='Boundary-word arguments, result words, guarded objects/tables, copied slots, CD lock transitions '
              'and preserved ABI on original debug methods and two CD guard paths per method. No dependency '
              'output stubs, actual disc/SDK I/O, destination writes, natural history, CPU timing, complete file '
              'behavior or whole-feature acceptance. The two inherited empty debug frames remain unexplained.')
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('status', 'initialized_interface_cases', 'positive_method_runs',
                     'actual_entry_counts', 'new_game_function_C_bytes')}, indent=2), flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if sys.platform == 'win32':
            raise ValueError('Use the matching WSL compiler and isolated pinned analysis environment.')
        output = output_directory(args.output)
        output.mkdir(parents=True)
        verify(output)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('[!] ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
