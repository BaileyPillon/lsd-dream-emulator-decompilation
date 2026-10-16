"""Compare populated actor child-flag dispatch through original native methods.

The analysis caller uses the corrected actor API. Original actor/entity and
scene-node tables, the fan-out, the leaf method and the bit setter execute.
This does not run an NPC encounter or resolve inherited unused local storage.
"""
import argparse
from collections import Counter
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
from tools import verify_native_ai as n
from tools.decomp_workbench import candidate_commands, configure
from tools.compile_c import run_stages
from tools.verify_scripted_ai import backend_identity
from research.compiler.compare_function import elf_function

FUNCTIONS = [
    dict(function='func_80065A5C', address='0x80065a5c', bytes=132,
         sha256='278028b4201f68dc536800ede29a45e5905ef7ed8e5929059a19709f705d1f23'),
    dict(function='func_8001D344', address='0x8001d344', bytes=48,
         sha256='ff5d0290554c6476f831e69e135c146bc2efe1921f80df09eb4d8b262011d661'),
    dict(function='func_8001EDAC', address='0x8001edac', bytes=88,
         sha256='685cff5de3228050301baf2343de332f6b5d8f6e3792817177b649ff16605923')]
TABLES = [
    dict(symbol='g_ACTOR_VTABLE', address='0x8008a6c4', bytes=0x144,
         sha256='00907856ef17e7189c9749a820ebf11a7f2eb8c2aa71440573bf6a00d1458fc8'),
    dict(symbol='g_ENTITY_VTABLE', address='0x80089ad4', bytes=0x14C,
         sha256='d2f1f7eee6c466a8dfa12bb5746e93e071eecbe26ba1ee09d13663ef170e62de'),
    dict(symbol='D_800878D4', address='0x800878d4', bytes=0xF0,
         sha256='74ba4f812269d36e971368efa639a6cb725213972f6958caed2bdf3c42a15388')]
ARENA, ARENA_BYTES, CODE = 0x110000, 0xC00, 0x180000
ROOT_OFFSET, LIST_OFFSET = 0x20, 0xA00
FLAGS = (-2147483648, -1, 0, 1, 2, 256, 2147483647)
WORDS = (0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF, 0x12345678, 0xABCDEF01, 0x40000000)
SEGMENTS = (0, 0x80000000, 0xA0000000)
HISTORY = (0, 1, 1, 0, -1)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def node_offset(index):
    return 0x210 + index * 0x80


def indices(layout):
    return (tuple(range(9)), tuple(reversed(range(9))),
            (0, 1, 0, 2, 1, 3, 0, 4, 8), (2, 4, 6, 8, 1, 3, 5, 7, 0))[layout]


def fixture(case):
    data = bytearray((i * 37 + case['pattern'] * 91 + 3) & 255 for i in range(ARENA_BYTES))
    table = TABLES[1 if case['kind'] == 'virtual-entity' else 0]
    pointer = lambda offset: (ARENA + offset) | case['segment']
    n.word(data, ROOT_OFFSET, int(table['address'], 16))
    n.word(data, ROOT_OFFSET + 0x6C, case['count'])
    n.word(data, ROOT_OFFSET + 0x70, pointer(LIST_OFFSET))
    for i in range(9):
        n.word(data, node_offset(i), int(TABLES[2]['address'], 16))
        n.word(data, node_offset(i) + 0x10, case['word'] ^ (i * 0x10203))
    for i, index in enumerate(indices(case['layout'])):
        n.word(data, LIST_OFFSET + i * 4, pointer(node_offset(index)))
    return data


def entry(case):
    if case['kind'] == 'direct-node':
        return int(FUNCTIONS[1]['address'], 16) & n.MASK
    return int(FUNCTIONS[0]['address'], 16) & n.MASK if case['kind'] == 'direct-actor' else CODE


def receiver(case):
    offset = node_offset(0) if case['kind'] == 'direct-node' else ROOT_OFFSET
    return (ARENA + offset) | case['segment']


def expected(case, data, flag):
    """Model the bit and list contract without executing or decoding MIPS."""
    result = bytearray(data)
    trace = []
    pointer = lambda offset: (ARENA + offset) | case['segment']
    argument = flag & 0xFFFFFFFF
    if case['kind'] != 'direct-node':
        if case['kind'].startswith('virtual-'):
            trace.append(['actor_children_set_flag', receiver(case), argument])
        trace.append(['func_80065A5C', receiver(case), argument])
    selected = (0,) if case['kind'] == 'direct-node' else indices(case['layout'])[:max(0, case['count'])]
    returned = None
    for index in selected:
        offset = node_offset(index) + 0x10
        old = struct.unpack_from('<I', result, offset)[0]
        # A false argument sets bit 31. Other bits survive, and the leaf
        # reports whether bit 31 was clear before this call.
        changed = (old & 0x7FFFFFFF) + (0x80000000 if argument == 0 else 0)
        n.word(result, offset, changed)
        returned = int(old < 0x80000000)
        trace.extend([['func_8001D344', pointer(node_offset(index)), argument],
                      ['func_8001EDAC', pointer(offset), 31, 1, int(argument == 0)]])
    return bytes(result), returned if case['kind'] == 'direct-node' else None, trace


def cases():
    for kind in ('direct-actor', 'virtual-actor', 'virtual-entity'):
        for count in (-2147483648, -1, 0, 1, 2, 4, 8):
            layouts = range(4) if count > 1 else (0,)
            for layout, flag, word, segment, pattern in itertools.product(layouts, FLAGS, WORDS, SEGMENTS, (0, 1)):
                yield dict(kind=kind, count=count, layout=layout, flag=flag, word=word, segment=segment, pattern=pattern)
    for flag, word, segment, pattern in itertools.product(FLAGS, WORDS, SEGMENTS, (0, 1)):
        yield dict(kind='direct-node', count=0, layout=0, flag=flag, word=word, segment=segment, pattern=pattern)


def histories():
    for word, segment, pattern in itertools.product(WORDS, SEGMENTS, (0, 1)):
        yield dict(kind='virtual-entity', count=8, layout=2, flag=0, word=word, segment=segment, pattern=pattern)


def compile_caller(output):
    source = output / 'caller.c'
    source.write_text('#include "' + str(ROOT / 'research/actor_children/consumer.c') + '"\n'
                      '#include "' + str(ROOT / 'research/actor_children/abi_checks.h') + '"\n')
    obj, elf, binary = (output / name for name in ('caller.o', 'caller.elf', 'caller.bin'))
    with (output / 'compiler.log').open('xb') as log:
        saved = os.dup(2)
        os.dup2(log.fileno(), 2)
        try:
            run_stages(candidate_commands('src/scene/actor.c', source, obj))
        finally:
            os.dup2(saved, 2)
            os.close(saved)
        script = output / 'caller.ld'
        script.write_text('SECTIONS { .text ' + hex(CODE) + ' : SUBALIGN(4) { *(.text) } '
                          '/DISCARD/ : { *(.reginfo) *(.MIPS.abiflags) *(.pdr) *(.gnu.attributes) } }\n')
        subprocess.run([configure.CROSS + 'ld', '-EL', '-nostdlib', '-T', str(script), '-o', str(elf), str(obj)],
                       check=True, stdout=log, stderr=subprocess.STDOUT)
        subprocess.run([configure.CROSS + 'objcopy', '-O', 'binary', '-j', '.text', str(elf), str(binary)], check=True)
    code, detail = elf_function(elf.read_bytes(), 'actor_children_set_flag', CODE)
    if code != binary.read_bytes() or detail['other_sized_functions'] or not detail['function_covers_complete_section']:
        raise ValueError('Require exactly the complete compiled analysis caller.')
    return code, dict(function='actor_children_set_flag', address=hex(CODE), bytes=len(code), sha256=digest(code))


class Machine(n.Machine):
    def __init__(self, code, caller, fault=None):
        self.functions = FUNCTIONS + [caller]
        self.entries = {int(row['address'], 16) & n.MASK: row['function'] for row in self.functions}
        self.ranges = [(int(row['address'], 16) & n.MASK, row['bytes']) for row in self.functions]
        self.counts = Counter()
        self.fault = None if fault is None else fault[0] & n.MASK
        self.fault_hits = 0
        super().__init__(start=CODE, native_functions=FUNCTIONS)
        self.cpu.mem_write(CODE, code)
        if fault is not None:
            self.cpu.mem_write(fault[0] & n.MASK, struct.pack('<I', fault[1]))

    def hook(self, cpu, address, size, unused):
        address &= n.MASK
        if not any(start <= address < start + length for start, length in self.ranges):
            raise ValueError('Execution escaped the reviewed original methods and compiled caller.')
        if address == self.fault:
            self.fault_hits += 1
        name = self.entries.get(address)
        if name:
            self.counts[name] += 1
            count = 4 if name == 'func_8001EDAC' else 2
            self.trace.append([name, *[cpu.reg_read(getattr(n.reg, 'UC_MIPS_REG_A' + str(i))) for i in range(count)]])

    def initialize(self, case):
        self.cpu.mem_write(ARENA, bytes(fixture(case)))

    def call(self, case, flag):
        self.trace, self.fault_hits = [], 0
        cpu = self.cpu
        guard = bytes([0xC9]) * 0x800
        cpu.mem_write(n.STACK - 0x400, guard)
        saved = [n.u32(0xAD000000 + i * 0x10203) for i in range(len(n.SAVED))]
        for register, value in zip(n.SAVED, saved):
            cpu.reg_write(register, value)
        for i, register in enumerate(n.VOLATILE):
            cpu.reg_write(register, n.u32(0xBC000000 + i * 0x10203))
        for register, value in ((n.reg.UC_MIPS_REG_SP, n.STACK), (n.reg.UC_MIPS_REG_GP, 0x8008A808),
                                (n.reg.UC_MIPS_REG_RA, n.END), (n.reg.UC_MIPS_REG_V0, 0xDEADBEEF),
                                (n.reg.UC_MIPS_REG_A0, receiver(case)), (n.reg.UC_MIPS_REG_A1, n.u32(flag))):
            cpu.reg_write(register, value)
        cpu.emu_start(entry(case), n.END, count=10000)
        checks = dict(return_pc=cpu.reg_read(n.reg.UC_MIPS_REG_PC) == n.END,
                      stack_pointer=cpu.reg_read(n.reg.UC_MIPS_REG_SP) == n.STACK,
                      global_pointer=cpu.reg_read(n.reg.UC_MIPS_REG_GP) == 0x8008A808,
                      return_address=cpu.reg_read(n.reg.UC_MIPS_REG_RA) == n.END,
                      saved_registers=[cpu.reg_read(r) for r in n.SAVED] == saved,
                      lower_stack_guard=bytes(cpu.mem_read(n.STACK - 0x400, 0x200)) == guard[:0x200],
                      upper_stack_guard=bytes(cpu.mem_read(n.STACK, 0x200)) == guard[0x400:0x600])
        if not all(checks.values()):
            raise ValueError('Child-flag ABI checks failed: ' + ', '.join(name for name, ok in checks.items() if not ok))
        result = cpu.reg_read(n.reg.UC_MIPS_REG_V0) if case['kind'] == 'direct-node' else None
        return bytes(cpu.mem_read(ARENA, ARENA_BYTES)), result, self.trace


def controls(code, caller):
    records = []
    definitions = [
        ('child_list_stride', 0x80065ABC, 0x26310004, 0x26310008, 'direct-actor', 2, 0, 0x12345678),
        ('zero_argument_gate', 0x8001D34C, 0x2CA70001, 0x2CA70000, 'virtual-entity', 1, 0, 0),
        ('wrong_flag_bit', 0x8001D354, 0x3405001F, 0x3405001E, 'virtual-actor', 1, 0, 0),
        ('wrong_leaf_return', 0x8001D360, 0x2C420001, 0x2C420002, 'direct-node', 0, 1, 0x80000000)]
    for name, address, original, changed, kind, count, flag, word in definitions:
        if struct.unpack('<I', n.h.target(address, 4))[0] != original:
            raise ValueError('Reviewed control instruction changed: ' + name)
        case = dict(kind=kind, count=count, layout=0, flag=flag, word=word, segment=0, pattern=0)
        machine = Machine(code, caller, (address, changed))
        machine.initialize(case)
        wanted = expected(case, fixture(case), flag)
        actual = machine.call(case, flag)
        wrong_buffer, wrong_return = actual[0] != wanted[0], actual[1] != wanted[1]
        if not machine.fault_hits or not (wrong_buffer or wrong_return):
            raise ValueError('Control lacks an executed changed instruction and wrong output: ' + name)
        records.append(dict(kind=name, address=hex(address), changed_instruction_hits=machine.fault_hits,
                            wrong_buffer=wrong_buffer, wrong_return_word=wrong_return, fixture=case))
    return records


def verify(output):
    dependencies = n.evidence_dependencies('research/actor_children/consumer.c', 'research/actor_children/abi_checks.h',
        'research/actor_children/verify.py', 'src/scene/actor.h', 'src/scene/scene_node.c', 'src/scene/scene_node.h',
        'src/base/object_math.c', 'tools/decomp_workbench.py', 'tools/verify_scripted_ai.py',
        'research/compiler/compare_function.py', 'tools/gcc263/cc1')
    before = {path: digest(path.read_bytes()) for path in dependencies}
    n.initialize_backend(n.load_program(FUNCTIONS))
    backend = backend_identity()
    for table in TABLES:
        address = int(table['address'], 16)
        method = FUNCTIONS[1 if table['symbol'] == 'D_800878D4' else 0]
        if (n.h.symbols[table['symbol']] != address or digest(n.h.target(address, table['bytes'])) != table['sha256']
                or struct.unpack('<I', n.h.target(address + 0x60, 4))[0] != int(method['address'], 16)):
            raise ValueError('Original child-flag binding changed: ' + table['symbol'])
    code, caller = compile_caller(output)
    machine = Machine(code, caller)
    identities, groups, snapshots = set(), Counter(), hashlib.sha256()
    steps = 0
    for case, commands in itertools.chain(((case, (case['flag'],)) for case in cases()),
                                          ((case, HISTORY) for case in histories())):
        data = bytes(fixture(case))
        identity = digest(data + struct.pack('<II', entry(case), receiver(case))
                          + b''.join(struct.pack('<I', n.u32(value)) for value in commands))
        if identity in identities:
            raise ValueError('Repeated actual initialized graph and command input.')
        identities.add(identity)
        machine.initialize(case)
        for flag in commands:
            wanted = expected(case, data, flag)
            actual = machine.call(case, flag)
            if actual != wanted:
                raise ValueError('Original child-flag dispatch disagrees with its model: ' + repr(case))
            data = wanted[0]
            snapshots.update(bytes.fromhex(identity) + data + bytes([255 if actual[1] is None else actual[1]]))
            steps += 1
        groups['five_call_history' if len(commands) > 1 else case['kind']] += 1
    faults = controls(code, caller)
    for row in FUNCTIONS + [caller] + TABLES:
        address = int(row['address'], 16) & n.MASK
        if digest(bytes(machine.cpu.mem_read(address, row['bytes']))) != row['sha256']:
            raise ValueError('Positive function, analysis caller or table changed.')
    if (backend_identity() != backend or n.load_program(FUNCTIONS).ROM != n.h.ROM
            or any(digest(path.read_bytes()) != value for path, value in before.items())):
        raise ValueError('A source, original input, backend or canonical build changed.')
    report = dict(status='passed_bounded_original_actor_child_flags', native_case_inputs=len(identities),
        positive_native_invocations=steps, case_groups=dict(groups), actual_entry_counts=dict(machine.counts),
        original_functions=FUNCTIONS, original_tables=TABLES, compiled_analysis_caller=caller,
        target_ABI_assertions=8, dependency_output_contracts=[], negative_controls=faults,
        input_and_output_sha256=snapshots.hexdigest(), backend_identity=backend,
        canonical_original_and_build_equal=True, canonical_executable_sha256=digest(n.h.ROM),
        producer_dependencies=[dict(path=p.relative_to(ROOT).as_posix(), sha256=h) for p, h in before.items()],
        original_behavior_modified=False, new_game_function_C_bytes=0, model_API_calls=0,
        new_bounded_NPC_callbacks=0, new_whole_NPC_encounters=0, whole_feature_groups_accepted=0,
        scope='Original actor/entity table dispatch to populated disjoint scene-node lists, including duplicate entries, '
              'signed empty counts, full-word flags and repeated flag changes. The real fan-out, leaf and bit setter run '
              'without output contracts. Full guarded graph, ordered call arguments, leaf return word and saved ABI agree. '
              'Excludes natural construction/NPC encounters, recursion, call-time count changes, rendering/audio and PS1 timing; '
              'the bit setter inherited unused local remains unresolved.')
    with (output / 'report.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(report=str(output / 'report.json'), native_case_inputs=len(identities),
                          native_invocations=steps, negative_controls=len(faults))), flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='Fresh private directory inside .decomp-lab.')
    args = parser.parse_args(argv)
    try:
        output = (ROOT / args.output).resolve()
        lab = (ROOT / '.decomp-lab').resolve()
        if output == lab or not output.is_relative_to(lab) or output.exists():
            raise ValueError('Choose a fresh private output directory; prior evidence is preserved.')
        if sys.platform == 'win32':
            raise ValueError('Use the matching WSL/Linux compiler and optional analysis dependencies.')
        output.mkdir(parents=True, exist_ok=False)
        verify(output)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print('[!] ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
