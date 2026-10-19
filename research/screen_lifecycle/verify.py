"""Verify original screen factory/run/destructor composition and pool release.

Constructors, graphics initialization and cleanup are explicit output contracts.
The original factories, Run methods, destructor and pool allocator execute.
This does not accept natural screen setup/cleanup, PS1 faults or whole features.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gc
import hashlib
import itertools
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import configure
from research.compiler.compare_function import CANONICAL_SHA256, elf_function
from research.screen_run import verify as screen_run
from tools import verify_card_heap as heap
from tools import verify_native_ai as native
from tools.decomp_workbench import diagnostic_image, new_output_directory
from tools.export_npc_catalogue import nm_functions
from tools.progress import build_manifest, check_build_current
from tools.replay_cold_start_headless import require

TABLES = {'main': 0x80086B60, 'chart': 0x80087AAC}
TABLE_PREFIXES = (*TABLES.values(), 0x8006E730, 0x8006E878)
SIZES = {'main': 0xC4, 'chart': 0x244}
EXTRA = {'run_screen': 0x80026518, 'main_menu_create': 0x8004D518,
         'graph_screen_create': 0x80057F68, 'base_class_destructor': 0x80017EB0,
         'main_menu_get_vtable': 0x8004E2D0, 'func_80058764': 0x80058764}
RESULTS = (0, 1, 2, 3, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF)
SEGMENTS = (0, 0x80000000, 0xA0000000)
FAULTS = {
    'discard_Run_result': (0x8002656C, 0x00408021, 0x00008021),
    'skip_Destroy': (0x80026568, 0x0060F809, 0),
    'change_Run_mode': (0x80026554, 0x00003021, 0x24060001),
}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def file_record(path):
    return {'bytes': path.stat().st_size, 'sha256': digest(path.read_bytes())}

def validate_case(case):
    require(set(case) == {'kind', 'pool_size', 'segment', 'seed', 'create_arg', 'graphics', 'result', 'flag'},
            'A case needs the complete bounded input profile.')
    require(case['kind'] in SIZES and case['segment'] in SEGMENTS and case['seed'] in (0, 1),
            'Unknown screen, address segment or initial byte pattern.')
    size = SIZES[case['kind']]
    require(case['pool_size'] in (size, size + 4, size + 12, size + 20, 0x1000),
            'Use an undersized, exact, absorbed-tail, minimum-split or roomy pool.')
    require(case['create_arg'] in tuple(0x108040 | segment for segment in SEGMENTS)
            and case['graphics'] in tuple(0x108080 | segment for segment in SEGMENTS),
            'Only initialized opaque argument buffers and their RAM aliases are in scope.')
    require(type(case['result']) is int and case['result'] in RESULTS
            and case['flag'] in ((0,) if case['kind'] == 'main' else (0, 1, 0x80000000)),
            'Unsupported result or chart flag.')

def cases():
    # Nine pointer profiles cover every pair of object/create/graphics aliases.
    for kind, a, b, seed in itertools.product(TABLES, range(3), range(3), (0, 1)):
        common = dict(kind=kind, segment=SEGMENTS[a], seed=seed,
                      create_arg=0x108040 | SEGMENTS[b], graphics=0x108080 | SEGMENTS[(a + b) % 3])
        yield dict(common, pool_size=SIZES[kind], result=0, flag=0)
        flags = (0,) if kind == 'main' else (0, 1, 0x80000000)
        for pool, result, flag in itertools.product(
                (SIZES[kind] + 4, SIZES[kind] + 12, SIZES[kind] + 20, 0x1000), RESULTS, flags):
            yield dict(common, pool_size=pool, result=result, flag=flag)

def predicted(case):
    """Predict final bytes before any original instructions or hooks execute."""
    validate_case(case)
    model = heap.initial_model(case['pool_size'], case['segment'], case['seed'])
    model.setup()
    pointer = model.allocate(SIZES[case['kind']])
    if pointer:
        offset = (pointer & native.MASK) - heap.BASES['pool']
        model.put('pool', offset, TABLES[case['kind']])
        model.put('pool', offset + 0x38, case['result'] ^ 0xFFFFFFFF)
        if case['kind'] == 'chart':
            model.put('pool', offset + 0x238, case['flag'])
        model.free(pointer)
    return model, pointer

def expected_trace(case, success):
    factory = 'main_menu_create' if case['kind'] == 'main' else 'graph_screen_create'
    trace = ['run_screen', factory, 'memory_allocate_mem', 'memory_set_lock', 'memory_set_lock']
    if not success:
        return trace
    trace += ['main_menu_get_vtable' if case['kind'] == 'main' else 'func_80058764', 'construct:contract']
    if case['kind'] == 'chart':
        trace += ['func_80058390', 'func_8003DFBC']
    return trace + ['func_8003C1DC', 'timer_get_vtable', 'graphics_init:contract',
                    'base_class_destructor', 'cleanup:contract', 'memory_free_mem',
                    'memory_set_lock', 'memory_set_lock']

def observe_target_entry(pending, pc, arguments):
    """Keep pre-delay registers distinct from the actual callee arguments."""
    if pending is None:
        return None
    if pc & native.MASK == int(pending['target'], 16) & native.MASK:
        pending['target_entry_pc'] = f'0x{pc:08X}'
        pending['entry_arguments'] = list(arguments)
        return None
    require(pc & native.MASK == (int(pending['pc'], 16) + 4) & native.MASK,
            'An indirect transfer did not reach its recorded target after the delay slot.')
    return pending

class Machine(heap.Machine):
    def __init__(self, case, rows, fault=None):
        validate_case(case)
        self.case, self.events, self.null_reads = case, [], []
        self.final_model, self.object = predicted(case)
        self.setup_model = heap.initial_model(case['pool_size'], case['segment'], case['seed'])
        initial = self.setup_model.snapshot()
        self.setup_model.setup()
        self.table = TABLES[case['kind']]
        self.ctor = int.from_bytes(native.h.target(self.table + 8, 4), 'little') & native.MASK
        self.cleanup = int.from_bytes(native.h.target(self.table + 12, 4), 'little') & native.MASK
        self.fault_hits = 0
        self.fault_pc = FAULTS[fault][0] & native.MASK if fault else None
        super().__init__(heap.global_addresses(native.h))
        self.native_entries = {int(row['address'], 16) & native.MASK: row['function'] for row in rows}
        self.ranges = [(int(row['address'], 16) & native.MASK,
                        (int(row['address'], 16) & native.MASK) + row['bytes']) for row in rows]
        self.table_ranges = [(table & native.MASK, (table & native.MASK) + 0x48) for table in TABLE_PREFIXES]
        self.indirect_calls, self.table_reads = [], []
        self.pending_edge = None
        for name, data in initial.items():
            self.cpu.mem_write(heap.BASES[name], data)
        for address in self.globals.values():
            self.cpu.mem_write(address, bytes(4))
        if fault:
            pc, old, new = FAULTS[fault]
            require(native.h.target(pc, 4) == struct.pack('<I', old), 'Fault control lost its exact original word.')
            self.cpu.mem_write(pc & native.MASK, struct.pack('<I', new))

    def write_object(self, offset, value):
        self.cpu.mem_write((self.object & native.MASK) + offset, struct.pack('<I', value))

    def contract_return(self, marker):
        target = self.cpu.reg_read(native.reg.UC_MIPS_REG_RA)
        for index, register in enumerate(native.VOLATILE):
            self.cpu.reg_write(register, native.u32(0xBC000000 + index * 0x10203))
        self.cpu.reg_write(native.reg.UC_MIPS_REG_V0, marker)
        self.cpu.reg_write(native.reg.UC_MIPS_REG_PC, target)

    def hook(self, cpu, address, size, unused):
        pc = address & native.MASK
        args = [cpu.reg_read(getattr(native.reg, 'UC_MIPS_REG_A' + str(i))) for i in range(4)]
        self.pending_edge = observe_target_entry(self.pending_edge, address, args[:3])
        self.fault_hits += int(pc == self.fault_pc)
        if pc == self.ctor:
            require(self.object and args[:2] == [self.object, self.case['create_arg']], 'Constructor argument mismatch.')
            self.events.append('construct:contract')
            self.write_object(0, self.table)
            self.write_object(0x38, 0x76543210)
            if self.case['kind'] == 'chart':
                self.write_object(0x238, self.case['flag'] ^ 0x80000001)
            self.contract_return(0xDEAD0001)
            return
        if pc == int(screen_run.INITIALIZER['address'], 16) & native.MASK:
            require(args[:3] == [self.object, self.case['graphics'], 0], 'Run argument mismatch.')
            self.events.append('graphics_init:contract')
            self.write_object(0x38, self.case['result'])
            if self.case['kind'] == 'chart':
                self.write_object(0x238, self.case['flag'])
            self.contract_return(0xDEAD0002)
            return
        if pc == self.cleanup:
            require(self.object and args[0] == self.object, 'Cleanup receiver mismatch.')
            self.events.append('cleanup:contract')
            self.write_object(0x38, self.case['result'] ^ 0xFFFFFFFF)
            self.contract_return(0xDEAD0003)
            return
        name = self.native_entries.get(pc)
        if name:
            self.events.append(name)
            if name == 'memory_allocate_mem':
                require(args[0] == SIZES[self.case['kind']], 'Factory allocation size mismatch.')
            elif name == 'memory_free_mem':
                require(args[0] == self.object, 'Destructor freed a different receiver.')
        require(any(lo <= pc < hi for lo, hi in self.ranges), 'Execution escaped its complete owned ranges.')
        word = int.from_bytes(cpu.mem_read(pc, 4), 'little')
        if word & 0xFC1FFFFF == 0x0000F809:
            register = word >> 21 & 31
            edge = dict(pc=f'0x{address:08X}',
                target=f'0x{cpu.reg_read(native.reg.UC_MIPS_REG_0 + register):08X}', pre_delay_arguments=args[:3])
            self.indirect_calls.append(edge)
            self.pending_edge = edge
        super().hook(cpu, address, size, unused)

    def memory_hook(self, cpu, access, address, size, value, unused):
        physical = address & native.MASK
        if access == native.unicorn.UC_MEM_READ and physical == 0 and self.object == 0:
            pc = cpu.reg_read(native.reg.UC_MIPS_REG_PC) & native.MASK
            require(pc == 0x26540 and size == 4, 'Unexpected allocation-failure read.')
            self.null_reads.append(dict(pc=f'0x{pc | 0x80000000:08X}', address=f'0x{address:08X}', bytes=size))
            cpu.emu_stop()
            return
        if access == native.unicorn.UC_MEM_READ and any(lo <= physical and physical + size <= hi for lo, hi in self.table_ranges):
            self.table_reads.append(dict(pc=f'0x{(cpu.reg_read(native.reg.UC_MIPS_REG_PC) & native.MASK) | 0x80000000:08X}',
                address=f'0x{physical | 0x80000000:08X}', value=f'0x{int.from_bytes(cpu.mem_read(physical, size), "little"):08X}'))
            return
        super().memory_hook(cpu, access, address, size, value, unused)

    def execute(self):
        self.call('memory_set_manager', self.setup_model.manager_pointer)
        self.call('memory_setup_manager', self.setup_model.manager_pointer)
        self.compare(self.setup_model, True, 'setup')
        factory = 'main_menu_create' if self.case['kind'] == 'main' else 'graph_screen_create'
        if not self.object:
            require(self.call(factory, self.case['create_arg']) == 0, 'Exhausted original factory did not return zero.')
            self.compare(self.setup_model, True, 'standalone exhausted factory')
        self.events, self.indirect_calls, self.table_reads = [], [], []
        try:
            value = self.call('run_screen', native.h.symbols[factory], self.case['create_arg'], self.case['graphics'])
        except ValueError:
            if not self.null_reads or self.cpu.reg_read(native.reg.UC_MIPS_REG_PC) & native.MASK != 0x26540:
                raise
            value = None
        self.compare(self.final_model, True, 'complete lifetime')
        require(self.pending_edge is None and all('entry_arguments' in edge for edge in self.indirect_calls),
                'An indirect target entry is missing.')
        require(self.events == expected_trace(self.case, bool(self.object)), 'Native lifetime call order mismatch.')
        if self.object:
            expected = 2 if self.case['kind'] == 'chart' and self.case['flag'] else self.case['result']
            require(not self.null_reads and value == expected, 'Run result did not survive destruction.')
            require(self.free_trace == [self.object] and self.lock_trace == [1, 0, 1, 0], 'Free/lock protocol mismatch.')
        else:
            require(value is None and len(self.null_reads) == 1 and not self.free_trace and self.lock_trace == [1, 0],
                    'Allocation-failure profile changed.')
        snapshots = {name: digest(data) for name, data in self.final_model.snapshot().items()}
        return dict(case=self.case, returned=value, null_receiver_reads=self.null_reads,
                    trace=self.events, indirect_calls=self.indirect_calls, table_reads=self.table_reads,
                    complete_buffer_sha256=snapshots)

def owned_record(original, elf_data, gnu, name, address):
    code, _extent = elf_function(elf_data, name, address)
    require(gnu.get(name) == [(address, len(code))], 'GNU/ELF function extent mismatch: ' + name)
    load = struct.unpack_from('<I', original, 0x18)[0]
    at = 0x800 + address - load
    require(at >= 0x800 and at + len(code) <= len(original)
            and code == original[at:at + len(code)], 'Complete original function mismatch: ' + name)
    return dict(function=name, address=f'0x{address:08X}', bytes=len(code), sha256=digest(code))

def qualify_functions(output):
    require(check_build_current(ROOT) is True, 'Require a current matching build.')
    original = (ROOT / configure.ROM).read_bytes()
    require(digest(original) == CANONICAL_SHA256 and (ROOT / configure.EXE).read_bytes() == original,
            'Original and built executables must be canonical.')
    objects = [Path(configure.BUILD_DIR) / (name + '.o') for name, _kind in build_manifest()]
    with (output / 'link.log').open('xb') as log:
        elf, image = diagnostic_image(output, Path(configure.LD_SCRIPT), objects, ROOT / configure.EXE, log)
    elf_data = elf.read_bytes()
    text = subprocess.check_output([configure.CROSS + 'nm', '-S', '--defined-only', str(elf)], text=True)
    (output / 'GNU-symbols.txt').write_text(text)
    gnu = nm_functions(text)
    addresses = {r['function']: int(r['address'], 16) for r in heap.FUNCTIONS[:5] + screen_run.FUNCTIONS}
    addresses.update(EXTRA)
    # Contract bodies are pinned as original owned functions but never executed.
    contracts = {}
    for kind, table in TABLES.items():
        for label, offset in (('construct', 8), ('cleanup', 12)):
            at = 0x800 + table + offset - 0x80010000
            address = int.from_bytes(original[at:at + 4], 'little')
            owners = [(name, span) for name, spans in gnu.items() for span in spans if span[0] == address]
            require(len(owners) == 1, 'A contract needs one complete original function owner.')
            name, _span = owners[0]
            contracts[kind + '_' + label] = name
            addresses[name] = address
    addresses[screen_run.INITIALIZER['function']] = int(screen_run.INITIALIZER['address'], 16)
    records = []
    for name, address in addresses.items():
        records.append(owned_record(original, elf_data, gnu, name, address))
    contracted_names = {*contracts.values(), screen_run.INITIALIZER['function']}
    return [row for row in records if row['function'] not in contracted_names], [row for row in records if row['function'] in contracted_names], image

def verify(destination):
    require(sys.platform == 'linux' and Path.cwd().resolve() == ROOT, 'Run from the repository root in Linux/WSL.')
    paths = {Path(__file__), ROOT / 'tools/verify_native_ai.py', ROOT / 'tools/verify_card_heap.py',
             ROOT / 'tools/heap_model.py', ROOT / 'research/screen_run/verify.py',
             ROOT / 'PROJECT_OBJECTIVE.md', ROOT / 'configure.py', ROOT / 'requirements-card-heap.txt',
             ROOT / 'tools/decomp_workbench.py', ROOT / 'tools/progress.py', ROOT / 'tools/psx_image.py',
             ROOT / 'tools/inventory_vtables.py', ROOT / 'tools/export_npc_catalogue.py',
             ROOT / 'research/compiler/compare_function.py',
             ROOT / configure.ROM, ROOT / configure.EXE, ROOT / configure.LD_SCRIPT,
             ROOT / configure.MAP_FILE, ROOT / configure.UNDEF_FUNCS, ROOT / configure.UNDEF_SYMS}
    paths.update(ROOT / name for name, _kind in build_manifest())
    paths.update((ROOT / 'src').rglob('*.h'))
    paths.update(Path(configure.BUILD_DIR) / (name + '.o') for name, _kind in build_manifest())
    before = {str(path): file_record(path) for path in sorted(paths)}
    output = new_output_directory(destination)
    rows, contracts, image = qualify_functions(output)
    native.initialize_backend(native.load_program(rows + contracts))
    backend = heap.backend_identity()
    identities, groups, native_counts, witnesses = set(), Counter(), Counter(), {}
    aggregate = hashlib.sha256()
    with (output / 'cases.jsonl').open('x') as stream:
        for index, case in enumerate(cases()):
            encoded = json.dumps(case, sort_keys=True).encode()
            require(digest(encoded) not in identities, 'Duplicate initialized/contract input profile.')
            identities.add(digest(encoded))
            machine = Machine(case, rows)
            observed = machine.execute()
            group = case['kind'] + ('_returned' if machine.object else '_exhausted')
            groups[group] += 1
            native_counts.update(machine.entries)
            witnesses.setdefault(group, observed)
            line = json.dumps(observed, sort_keys=True, separators=(',', ':'))
            stream.write(line + '\n')
            aggregate.update((line + '\n').encode())
            if (index + 1) % 128 == 0:
                print(json.dumps(dict(completed=index + 1)), flush=True)
            if (index + 1) % 16 == 0:
                gc.collect()
    require(set(native_counts) == {row['function'] for row in rows}, 'Not every reviewed native body executed.')
    controls = []
    witness_case = dict(kind='chart', pool_size=0x1000, segment=0x80000000, seed=1,
                        create_arg=0xA0108040, graphics=0x108080, result=3, flag=1)
    for fault in FAULTS:
        Machine(witness_case, rows).execute()
        machine = Machine(witness_case, rows, fault)
        try:
            machine.execute()
        except (ValueError, AssertionError) as error:
            require(machine.fault_hits == 1, 'A negative control was not executed exactly once.')
            controls.append(dict(fault=fault, executed_instruction=f'0x{FAULTS[fault][0]:08X}',
                                 executed_hits=machine.fault_hits, rejection=str(error)))
        else:
            raise ValueError('An executed instruction fault was not rejected: ' + fault)
    require(all(file_record(Path(path)) == record for path, record in before.items())
            and check_build_current(ROOT) is True, 'A protected input or complete build changed.')
    table_records = [dict(address=f'0x{table:08X}', bytes=0x48, sha256=digest(native.h.target(table, 0x48)))
                     for table in TABLE_PREFIXES]
    report = dict(schema_version=1, timestamp_utc=datetime.now(timezone.utc).isoformat(),
        status='qualified_bounded_original_screen_lifecycle', input_profiles=len(identities), groups=dict(groups),
        native_functions_executed=rows, original_function_entry_counts=dict(native_counts),
        dependency_output_contracts=contracts, contract_types=['construct', 'graphics_initialize', 'cleanup'],
        original_contract_bodies_executed=False, full_guarded_buffers=['manager', 'pool', 'opaque_arguments'],
        prediction='Final interval/free-queue model and retained payload bytes computed before guest execution.',
        table_prefixes=table_records, witnesses=witnesses, executed_instruction_faults=controls,
        positive_fault_witnesses=len(controls), observed_campaign_sha256=aggregate.hexdigest(),
        cases_file=file_record(output / 'cases.jsonl'), backend=backend, symbolic_link=image,
        input_sha256=before, producer_sha256=digest(Path(__file__).read_bytes()),
        canonical_executable_sha256=CANONICAL_SHA256, new_game_function_C_bytes=0,
        original_behavior_modified=False, model_API_calls=0, whole_feature_groups_accepted=0,
        source_inventory_scope_U003_resolved=False, native_PS1_fault_behavior_accepted=False,
        scope='Original create/run/destroy and pool allocation/free with five pinned output-contract bodies. '
              'Exhaustion stops at the observed zero-address receiver load. Natural constructors, resource cleanup, '
              'graphics, hardware timing, full failure continuation and whole-screen acceptance remain open.')
    with (output / 'report.json').open('x') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(dict(input_profiles=len(identities), groups=dict(groups), native_functions=len(rows),
                          executed_faults=len(controls), report=str(output / 'report.json'))), flush=True)
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        verify(args.output)
    except (OSError, ValueError, AssertionError, RuntimeError, subprocess.SubprocessError) as error:
        print('[!] ' + str(error), file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    sys.exit(main())
