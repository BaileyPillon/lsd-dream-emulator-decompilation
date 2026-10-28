"""Check typed Destroy callers against the original destructor and pool release.

Construction and resource cleanup are explicit contracts. This tests the C
callback interface and bounded initialized objects, not natural screen setup.
"""
import argparse
from collections import Counter
import gc
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
from research.collision.trace_compiler_stack import new_output
from research.compiler.compare_function import elf_function
from research.screen_lifecycle import verify as lifecycle
from tools.compile_c import run_stages
from tools.decomp_workbench import candidate_commands
from tools.replay_cold_start_headless import require

native, heap = lifecycle.native, lifecycle.heap
CODE = 0x180000
CALLERS = ('screen_destroy_common', 'screen_destroy_main', 'screen_destroy_chart')
digest = lambda data: hashlib.sha256(data).hexdigest()


def compile_callers(output):
    source = ROOT/'research/screen_lifecycle/destroy_consumer.c'
    obj, elf = output/'destroy-callers.o', output/'destroy-callers.elf'
    commands = candidate_commands('src/game/game_flow.c', source, obj)
    commands[1].append('-Werror')
    with (output/'consumer-compiler.log').open('xb') as log:
        saved = os.dup(2)
        try:
            os.dup2(log.fileno(), 2)
            require(run_stages(commands) == b'', 'Unexpected compiler pipeline output.')
        finally:
            os.dup2(saved, 2)
            os.close(saved)
        linker = output/'destroy-callers.ld'
        linker.write_text('SECTIONS { .text '+hex(CODE)+' : SUBALIGN(4) { *(.text) } '
            '/DISCARD/ : { *(.reginfo) *(.MIPS.abiflags) *(.pdr) *(.gnu.attributes) } }\n')
        subprocess.run([configure.CROSS+'ld', '-EL', '-nostdlib', '-T', str(linker), '-o', str(elf), str(obj)],
                       check=True, stdout=log, stderr=log)
    nm = subprocess.check_output([configure.CROSS+'nm', '-S', '--defined-only', str(elf)], text=True)
    binary = subprocess.check_output([configure.CROSS+'objcopy', '-O', 'binary', '-j', '.text', str(elf), '/dev/stdout'])
    rows = []
    for name in CALLERS:
        matches = [s.split() for s in nm.splitlines() if len(s.split()) == 4 and s.split()[-1] == name]
        require(len(matches) == 1, 'Require one complete sized analysis caller: '+name)
        address, size = int(matches[0][0], 16), int(matches[0][1], 16)
        code, _ = elf_function(elf.read_bytes(), name, address)
        require(len(code) == size and code == binary[address-CODE:address-CODE+size], 'GNU/ELF caller extent mismatch.')
        rows.append(dict(function=name, address=hex(address), bytes=size, sha256=digest(code)))
    cursor = CODE
    for row in sorted(rows, key=lambda r: int(r['address'], 16)):
        require(int(row['address'], 16) == cursor, 'Unexpected gap between analysis callers.')
        cursor += row['bytes']
    require(cursor-CODE == len(binary), 'Unexpected code outside the three analysis callers.')
    return binary, rows, commands


def cases():
    for view, kind, segment, seed, shape in itertools.product(CALLERS, lifecycle.TABLES,
            lifecycle.SEGMENTS, (0, 1), (4, 12, 20, 0x1000)):
        if view != 'screen_destroy_common' and view != 'screen_destroy_'+kind:
            continue
        size = lifecycle.SIZES[kind]
        yield view, dict(kind=kind, segment=segment, seed=seed, pool_size=shape if shape == 0x1000 else size+shape,
                         create_arg=0x108040 | segment, graphics=0x108080 | segment,
                         result=0x80000000 if seed else 0x7FFFFFFF, flag=0x80000000 if kind == 'chart' else 0)


def validate_case(view, case):
    lifecycle.validate_case(case)
    require(view in CALLERS and (view == 'screen_destroy_common' or view == 'screen_destroy_'+case['kind']),
            'The concrete C screen view does not match the receiver family.')
    require(case['pool_size'] > lifecycle.SIZES[case['kind']], 'Destroy needs an allocated receiver.')


def run_case(view, case, rows, code, callers, fault=False):
    """Predict before execution, allocate through the original factory, destroy once."""
    validate_case(view, case)
    machine = lifecycle.Machine(case, rows)
    machine.cpu.mem_write(CODE, code)
    for row in callers:
        address = int(row['address'], 16)
        machine.ranges.append((address, address+row['bytes']))
        machine.native_entries[address] = row['function']
    machine.call('memory_set_manager', machine.setup_model.manager_pointer)
    machine.call('memory_setup_manager', machine.setup_model.manager_pointer)
    machine.compare(machine.setup_model, True, 'setup')
    factory = 'main_menu_create' if case['kind'] == 'main' else 'graph_screen_create'
    require(machine.call(factory, case['create_arg']) == machine.object != 0, 'Original factory allocation mismatch.')
    # These are bounded initialized fixtures; the constructor is still a contract.
    machine.write_object(0x38, case['result'])
    if case['kind'] == 'chart':
        machine.write_object(0x238, case['flag'])
    machine.events, machine.indirect_calls, machine.table_reads = [], [], []
    selected = next(r for r in callers if r['function'] == view)
    start, size = int(selected['address'], 16), selected['bytes']
    if fault:
        # Replace the compiled caller's reviewed Destroy load with Cleanup.
        words = list(struct.iter_unpack('<I', code[start-CODE:start-CODE+size]))
        offsets = [i*4 for i, (w,) in enumerate(words) if w>>26 == 0x23 and w & 0xffff == 4]
        require(len(offsets) == 1, 'Fault must select exactly one compiled Destroy-slot load.')
        pc = start+offsets[0]
        old = int.from_bytes(machine.cpu.mem_read(pc, 4), 'little')
        machine.cpu.mem_write(pc, struct.pack('<I', (old & 0xffff0000) | 12))
        machine.fault_pc = pc
    value = machine.call(view, machine.object)
    if fault:
        require(machine.fault_hits > 0, 'The changed slot-load instruction was not executed.')
        return dict(changed_instruction_hits=machine.fault_hits, returned=value,
                    release_trace=machine.free_trace, events=machine.events,
                    rejected=value != 0 and machine.free_trace != [machine.object])
    require(value == 0, 'The original destructor must return NULL, regardless of Cleanup V0.')
    require(machine.events == [view, 'base_class_destructor', 'cleanup:contract', 'memory_free_mem',
                               'memory_set_lock', 'memory_set_lock'], 'Destroy dispatch or release order mismatch.')
    # call() resets protocol counters for each host invocation. Allocation
    # completed in the preceding host call; this one contains only free.
    require(machine.free_trace == [machine.object] and machine.lock_trace == [1, 0], 'Receiver/free/lock mismatch.')
    machine.compare(machine.final_model, True, 'complete original destruction')
    require(machine.pending_edge is None and all('entry_arguments' in e for e in machine.indirect_calls),
            'Missing actual indirect target entry.')
    require(any(int(r['address'], 16) == lifecycle.TABLES[case['kind']]+4
                and int(r['value'], 16) == lifecycle.EXTRA['base_class_destructor'] for r in machine.table_reads),
            'The caller did not read the original Destroy word.')
    for row in callers:
        require(digest(bytes(machine.cpu.mem_read(int(row['address'], 16), row['bytes']))) == row['sha256'],
                'A positive analysis caller changed.')
    return dict(view=view, case=case, returned=value, events=machine.events,
                indirect_calls=machine.indirect_calls, table_reads=machine.table_reads,
                complete_buffer_sha256={name:digest(data) for name,data in machine.final_model.snapshot().items()},
                native_entries={name:count for name,count in machine.entries.items() if name not in CALLERS})


def verify(destination, lab_root=None):
    require(sys.platform == 'linux' and Path.cwd().resolve() == ROOT, 'Run from the repository root in Linux/WSL.')
    output = new_output(destination, lab_root)
    dependencies = native.evidence_dependencies('research/screen_lifecycle/verify_destroy.py',
        'research/screen_lifecycle/destroy_consumer.c', 'research/screen_lifecycle/verify.py',
        'src/game/game_flow.c', 'src/game/game_flow.h', 'src/base/base.c', 'src/base/base.h',
        'src/menu/main_menu.h', 'src/menu/graph_screen.h', 'tools/verify_card_heap.py',
        'tools/heap_model.py', 'tools/compile_c.py', 'tools/decomp_workbench.py',
        'research/compiler/compare_function.py', 'tools/gcc263/cc1')
    before = {p:digest(p.read_bytes()) for p in dependencies}
    rows, contracts, image = lifecycle.qualify_functions(output)
    native.initialize_backend(native.load_program(rows+contracts))
    backend = heap.backend_identity()
    code, callers, commands = compile_callers(output)
    saved_symbols = dict(native.h.symbols)
    native.h.symbols.update({r['function']:int(r['address'], 16) for r in callers})
    counts, identities, aggregate = Counter(), set(), hashlib.sha256()
    faults = []
    try:
        with (output/'destroy-cases.jsonl').open('x') as journal:
            for i, (view, case) in enumerate(cases()):
                identity = digest(json.dumps([view, case], sort_keys=True).encode())
                require(identity not in identities, 'Repeated destruction input.')
                identities.add(identity)
                observed = run_case(view, case, rows, code, callers)
                line = json.dumps(observed, sort_keys=True, separators=(',', ':'))+'\n'
                journal.write(line)
                aggregate.update(line.encode())
                counts.update(observed['native_entries'])
                if (i+1) % 24 == 0:
                    gc.collect()
            for view in CALLERS:
                case = next(case for name,case in cases() if name == view)
                witness = run_case(view, case, rows, code, callers, fault=True)
                require(witness['rejected'], 'Wrong-slot fault was not rejected.')
                faults.append(dict(view=view, case=case, **witness))
    finally:
        native.h.symbols.clear()
        native.h.symbols.update(saved_symbols)
    require(all(digest(p.read_bytes()) == checksum for p,checksum in before.items()), 'An evidence dependency changed.')
    require(heap.backend_identity() == backend, 'Execution backend changed.')
    require((ROOT/configure.EXE).read_bytes() == native.h.ROM, 'Canonical build changed.')
    report = dict(status='passed_bounded_destroy_interfaces', initialized_interface_cases=len(identities),
        compiled_analysis_callers=callers, target_layout_assertions=4, warnings_are_errors=True,
        Destroy_slot='0x04', original_Destroy_destination=hex(lifecycle.EXTRA['base_class_destructor']),
        original_complete_functions_qualified=rows, contracted_complete_functions_qualified=contracts,
        original_native_entry_counts=dict(counts), input_output_sha256=aggregate.hexdigest(),
        negative_controls=faults, compiler_commands=commands, canonical_image=image,
        producer_dependencies=[dict(path=p.relative_to(ROOT).as_posix(), sha256=h) for p,h in before.items()],
        backend_identity=backend, dependency_output_contracts=['main/chart constructor', 'main/chart cleanup'],
        contract_limit='Constructor and cleanup bodies do not execute. Graphics initialization is not reached.',
        new_game_C_bytes=0, new_original_features_accepted=0, model_api_calls=0,
        scope='Typed common/main/chart callers consume the real base destructor NULL return and free one valid '
              'receiver through the original pool. Full expected manager/pool/argument buffers, saved ABI and '
              'stack guards are checked. Natural screen construction/resource cleanup and whole-feature acceptance remain open.')
    (output/'destroy-report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','initialized_interface_cases','new_game_C_bytes')}))
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--lab-root', type=Path)
    args=parser.parse_args()
    verify(args.output, args.lab_root)
