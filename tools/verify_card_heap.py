"""Check original card cleanup composed with its original pool allocator.

All seven scoped functions execute their original instructions, without output
stubs. An interval/free-queue model predicts complete manager, pool and object
buffers. Valid owned pointers, bounded requests and supplied managers are an
explicit synthetic profile; physical cards, OS allocation, CPU timing and
whole-game acceptance remain separate. Use requirements-card-heap.txt in an
isolated environment. Reports and optional candidates stay in .decomp-lab.
"""
import argparse
from collections import Counter
import gc
import hashlib
import importlib
import itertools
import json
from pathlib import Path
import random
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import verify_native_ai as native
from tools.heap_model import PoolModel
from tools import verify_card_cleanup as cleanup

FUNCTIONS = [
    dict(function='memory_set_manager', address='0x80017A9C', bytes=12,
         sha256='31e1fb7ee27c6d0a7e8bce6222ebe7d15d003b63a0bcdffc60e62cb98dc28ade'),
    dict(function='memory_setup_manager', address='0x80017AC8', bytes=108,
         sha256='22d9cb67eacb97f1f65887bec8fd406a6d25dd69511540ee811296e9445987ba'),
    dict(function='memory_allocate_mem', address='0x80017B34', bytes=456,
         sha256='a55ec79ff9c1252fd41968bf5abca2a74f3658b6c400df80289d51d943fc5ef9'),
    dict(function='memory_free_mem', address='0x80017CFC', bytes=428,
         sha256='590fb6e594883e9fcaa7105de18de7b9a9c0df2322e07feb5e081f66da15a052'),
    dict(function='memory_set_lock', address='0x8001844C', bytes=12,
         sha256='d8fd53b2b7699e2b6135872ecc381394dea73cd963daff560ff6aa8342f3e80e'),
    dict(function='memory_is_locked', address='0x80018458', bytes=12,
         sha256='ccd77ee20801e94fafaa175ed036e3b88a7735f444013a5945fa78cd06106f7e'),
    dict(cleanup.FUNCTION),
]
BY_NAME = {record['function']: record for record in FUNCTIONS}
GP = 0x8008A808
BASES = dict(manager=0x100000, pool=0x110000, object=0x108000)
LENGTHS = dict(manager=0x100, pool=0x2080, object=0x100)
OFFSET = 0x40
MAX_ENTRIES = 8
SEGMENTS = (0, 0x80000000, 0xA0000000)
QUALIFIED_BACKEND = '2.1.2'
BASE_CASE = dict(count=2, present=True, buffer_null=False, buffer_size=68,
                 pattern='distinct', table_order='first', fragmented=False,
                 pooled_object=False, segment=0, seed=0, pool_size=0x1000)


def private_path(value, existing=False):
    root = ROOT.resolve()
    path = Path(value)
    path = (path if path.is_absolute() else root / path).resolve()
    if not path.is_relative_to((root / '.decomp-lab').resolve()):
        raise ValueError('Reports and candidates must remain inside .decomp-lab.')
    if not existing and path.exists():
        raise ValueError('Choose a fresh report path; existing evidence is preserved.')
    return path


def global_addresses(program):
    result = {}
    for name in ('memory_set_manager', 'memory_set_lock'):
        record = BY_NAME[name]
        words = struct.unpack('<III', program.target(int(record['address'], 16), record['bytes']))
        stores = [word for word in words if word >> 26 == 0x2B
                  and (word >> 21) & 31 == 28 and (word >> 16) & 31 == 4]
        if len(stores) != 1:
            raise ValueError('Pinned setter does not identify one a0 store through gp.')
        displacement = struct.unpack('<h', struct.pack('<H', stores[0] & 0xFFFF))[0]
        result[name] = (GP + displacement) & native.MASK
    if result != dict(memory_set_manager=0x8A818, memory_set_lock=0x8A820):
        raise ValueError('Native allocator globals disagree with their pinned addresses.')
    return result


def backend_identity():
    try:
        import unicorn
    except ImportError as error:
        raise ValueError('Install requirements-card-heap.txt in a separate analysis environment.') from error
    if unicorn.__version__ != QUALIFIED_BACKEND:
        raise ValueError('This graph is qualified with isolated Unicorn 2.1.2. '
                         'Install requirements-card-heap.txt separately; do not change the main analysis environment.')
    module = importlib.import_module(unicorn.Uc.__module__)
    library = Path(module.uclib._name).resolve()
    entry = Path(unicorn.__file__).resolve()
    binding_sources = [(path.relative_to(entry.parent).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
                       for path in sorted(entry.parent.rglob('*.py'))]
    return dict(package_version=unicorn.__version__, library_api=list(unicorn.uc_version()),
                loaded_library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),
                binding_entry_sha256=hashlib.sha256(entry.read_bytes()).hexdigest(),
                binding_sources_sha256=hashlib.sha256(json.dumps(binding_sources).encode()).hexdigest(),
                binding_source_count=len(binding_sources),
                execution_hook='UC_HOOK_CODE', fresh_cpu_per_host_call=True,
                all_emulated_ram_preserved_between_host_calls=True,
                uninterrupted_cpu_within_guest_cleanup_graph=True)


def validate_case(case):
    if (case['segment'] not in SEGMENTS or case['seed'] not in (0, 1)
            or not -(1 << 31) <= case['count'] <= MAX_ENTRIES
            or case['pattern'] not in ('distinct', 'mixed', 'nulls')
            or case['table_order'] not in ('first', 'last')
            or not 16 <= case['pool_size'] <= 0x2000 or case['pool_size'] % 4
            or not 1 <= case['buffer_size'] <= 128
            or case['pooled_object'] and case['pool_size'] < 512):
        raise ValueError('Cleanup case exceeds its valid-ownership fixture profile.')


def initial_model(pool_size, segment, seed=0):
    buffers = {name: bytearray((i * 37 + seed * 73 + 0xD7) & 255 for i in range(length))
               for name, length in LENGTHS.items()}
    struct.pack_into('<II', buffers['manager'], OFFSET,
                     (BASES['pool'] + OFFSET) | segment, pool_size)
    return PoolModel(buffers, BASES, OFFSET, OFFSET, pool_size, segment)


class Machine(native.Machine):
    def __init__(self, globals_, code=None, patches=None):
        self.entries = Counter()
        self.data_accesses = Counter()
        self.globals = globals_
        self.host_calls = 0
        self.instructions = []
        self.free_trace = []
        self.lock_trace = []
        super().__init__(code=code, start=int(cleanup.FUNCTION['address'], 16) & native.MASK,
                         native_functions=FUNCTIONS)
        self.ranges = [(int(record['address'], 16) & native.MASK,
                        (int(record['address'], 16) & native.MASK) + record['bytes']) for record in FUNCTIONS]
        for name, replacement in (patches or {}).items():
            record = BY_NAME[name]
            if len(replacement) != record['bytes']:
                raise ValueError('Private fault copy exceeds its pinned function span.')
            self.cpu.mem_write(int(record['address'], 16) & native.MASK, replacement)

    def memory_hook(self, cpu, access, address, size, value, unused):
        address &= native.MASK
        ranges = [(base, base + LENGTHS[name]) for name, base in BASES.items()]
        ranges += [(start, start + 4) for start in self.globals.values()]
        ranges.append((native.STACK - 0x100, native.STACK + 0x100))
        if not any(start <= address and address + size <= end for start, end in ranges):
            raise ValueError('Native heap graph made an unreviewed data access at ' + hex(address))
        self.data_accesses['write' if access == native.unicorn.UC_MEM_WRITE else 'read'] += 1

    def hook(self, cpu, address, size, unused):
        address &= native.MASK
        self.instructions.append(address)
        if not any(start <= address and address + size <= end for start, end in self.ranges):
            raise ValueError('Native heap graph executed outside its seven reviewed ranges.')
        if address in self.native_entries:
            name = self.native_entries[address]
            self.entries[name] += 1
            self.executed_native_functions.add(name)
            if name == 'memory_free_mem':
                self.free_trace.append(cpu.reg_read(native.reg.UC_MIPS_REG_A0))
            elif name == 'memory_set_lock':
                self.lock_trace.append(cpu.reg_read(native.reg.UC_MIPS_REG_A0))

    def call(self, name, *arguments):
        previous = bytes(self.cpu.mem_read(0, 0x200000))
        cpu = native.Uc(native.UC_ARCH_MIPS, native.UC_MODE_MIPS32 | native.UC_MODE_LITTLE_ENDIAN)
        cpu.mem_map(0, 0x200000)
        cpu.mem_write(0, previous)
        if bytes(cpu.mem_read(0, 0x200000)) != previous:
            raise ValueError('Fresh host-call CPU failed to preserve the entire native RAM image.')
        cpu.hook_add(native.UC_HOOK_CODE, self.hook)
        cpu.hook_add(native.unicorn.UC_HOOK_MEM_READ | native.unicorn.UC_HOOK_MEM_WRITE, self.memory_hook)
        self.cpu = cpu
        self.instructions, self.free_trace, self.lock_trace = [], [], []
        cpu.mem_write(native.STACK - 0x400, bytes([0xCC]) * 0x500)
        saved = [native.u32(0xAB000000 + 0x10203 * i) for i in range(len(native.SAVED))]
        for register, value in zip(native.SAVED, saved):
            cpu.reg_write(register, value)
        for register, value in ((native.reg.UC_MIPS_REG_SP, native.STACK),
                                (native.reg.UC_MIPS_REG_GP, GP), (native.reg.UC_MIPS_REG_RA, native.END)):
            cpu.reg_write(register, value)
        for i in range(4):
            cpu.reg_write(getattr(native.reg, 'UC_MIPS_REG_A' + str(i)),
                          arguments[i] if i < len(arguments) else 0xBA000000 + i)
        try:
            cpu.emu_start(native.h.symbols[name] & native.MASK, native.END, count=20000)
        except native.unicorn.UcError as error:
            raise ValueError('Native backend failed in ' + name + ': ' + str(error)
                             + '; last PCs=' + repr([hex(pc) for pc in self.instructions[-12:]])) from error
        if (cpu.reg_read(native.reg.UC_MIPS_REG_PC) != native.END
                or cpu.reg_read(native.reg.UC_MIPS_REG_SP) != native.STACK
                or cpu.reg_read(native.reg.UC_MIPS_REG_GP) != GP
                or cpu.reg_read(native.reg.UC_MIPS_REG_RA) != native.END
                or [cpu.reg_read(register) for register in native.SAVED] != saved
                or bytes(cpu.mem_read(native.STACK, 0x100)) != bytes([0xCC]) * 0x100
                or bytes(cpu.mem_read(native.STACK - 0x400, 0x100)) != bytes([0xCC]) * 0x100):
            raise ValueError('Native heap graph violated its return, stack, saved-register or red-zone checks.')
        self.host_calls += 1
        if self.host_calls % 16 == 0:
            gc.collect()
        return cpu.reg_read(native.reg.UC_MIPS_REG_V0)

    def compare(self, model, registered, operation):
        for name, expected in model.snapshot().items():
            actual = bytes(self.cpu.mem_read(BASES[name], len(expected)))
            if actual != expected:
                differences = [i for i, (a, b) in enumerate(zip(actual, expected)) if a != b]
                raise ValueError(operation + ' complete-buffer mismatch in ' + name
                                 + ' at offsets ' + repr(differences[:12]))
        expected_manager = model.manager_pointer if registered else 0
        actual_manager = struct.unpack('<I', self.cpu.mem_read(self.globals['memory_set_manager'], 4))[0]
        actual_lock = struct.unpack('<I', self.cpu.mem_read(self.globals['memory_set_lock'], 4))[0]
        if actual_manager != expected_manager or actual_lock != 0:
            raise ValueError('Native allocator global manager or lock disagrees with its fixture.')


def prepare(machine, model, registered=True):
    for name, data in model.snapshot().items():
        machine.cpu.mem_write(BASES[name], data)
    machine.call('memory_set_manager', model.manager_pointer if registered else 0)
    machine.call('memory_set_lock', 0)
    model.setup()
    machine.call('memory_setup_manager', 0 if registered else model.manager_pointer)
    machine.compare(model, registered, 'setup')


def allocation(machine, model, size, registered=True):
    expected = model.allocate(size)
    actual = machine.call('memory_allocate_mem', size, 0 if registered else model.manager_pointer)
    if actual != expected or machine.lock_trace != [1, 0]:
        raise ValueError('Native allocation pointer or lock transition disagrees with the model.')
    machine.compare(model, registered, 'allocate ' + str(size))
    if machine.call('memory_is_locked') != 0:
        raise ValueError('Original getter did not observe the released allocation lock.')
    machine.compare(model, registered, 'allocation lock getter')
    return actual


def release(machine, model, pointer, registered=True):
    model.free(pointer)
    result = machine.call('memory_free_mem', pointer, 0 if registered else model.manager_pointer)
    if result != 0 or machine.lock_trace != [1, 0] or machine.free_trace != [pointer]:
        raise ValueError('Native free return, argument or lock transition disagrees with the model.')
    machine.compare(model, registered, 'free ' + hex(pointer))
    if machine.call('memory_is_locked') != 0:
        raise ValueError('Original getter did not observe the released free lock.')
    machine.compare(model, registered, 'free lock getter')


def components(machine, group, case):
    model = initial_model(case['pool_size'], case['segment'], case['seed'])
    registered = case['registered']
    prepare(machine, model, registered)
    live = []
    if group == 'fragmented_first_fit':
        live = [allocation(machine, model, size, registered) for size in (60, 124, 60, 252, 60)]
        for index in (3, 0):
            release(machine, model, live[index], registered)
        live = [live[index] for index in (1, 2, 4)]
        live += [allocation(machine, model, size, registered) for size in (200, 60)]
    elif group == 'generated_owned_sequences':
        rng = random.Random(case['random_seed'])
        for _ in range(32):
            if live and rng.randrange(3) == 0:
                pointer = live.pop(rng.randrange(len(live)))
                release(machine, model, pointer, registered)
            else:
                size = rng.choice((0, 1, 11, 12, 13, 15, 16, 17, 31, 32, 33, 63, 64, 65, 127, 128, 129, 513, 1024))
                pointer = allocation(machine, model, size, registered)
                if pointer:
                    live.append(pointer)
    else:
        for size in case['requests']:
            pointer = allocation(machine, model, size, registered)
            if pointer:
                live.append(pointer)
    release(machine, model, 0, registered)
    for pointer in live[::2] + live[1::2]:
        release(machine, model, pointer, registered)
    if [(b.offset, b.size, b.free) for b in model.blocks] != [(0, model.pool_size, True)]:
        raise ValueError('Component teardown did not restore one coalesced free interval.')


def component_cases():
    for segment, registered in itertools.product(SEGMENTS, (True, False)):
        for seed, size in itertools.product((0, 1), (16, 32, 64, 1024)):
            yield 'alignment_capacity_and_coalescing', dict(segment=segment, registered=registered,
                 seed=seed, pool_size=size, requests=(0, 1, 12, 13, 31, 128, size, size + 4))
        for request in (108, 112, 124):
            yield 'split_threshold', dict(segment=segment, registered=registered, seed=0,
                                          pool_size=128, requests=(request,))
        yield 'fragmented_first_fit', dict(segment=segment, registered=registered, seed=1, pool_size=1024)
        for seed in range(4):
            yield 'generated_owned_sequences', dict(segment=segment, registered=registered,
                                                    seed=seed % 2, random_seed=seed, pool_size=1024)


def cleanup_cases():
    for segment, count, present, buffer_null in itertools.product(
            SEGMENTS, (-(1 << 31), -1, 0, 1, 2, 8), (True, False), (True, False)):
        yield 'signed_count_and_table_guard', dict(BASE_CASE, segment=segment, count=count,
                                                  present=present, buffer_null=buffer_null)
    for segment, count, order, pooled, pattern in itertools.product(
            SEGMENTS, (2, 8), ('first', 'last'), (True, False), ('mixed', 'nulls')):
        yield 'owned_null_patterns_and_object_locations', dict(BASE_CASE, segment=segment, count=count,
             table_order=order, pooled_object=pooled, pattern=pattern, seed=1)
    for segment, order, pooled, pattern in itertools.product(
            SEGMENTS, ('first', 'last'), (True, False), ('distinct', 'mixed', 'nulls')):
        yield 'fragmented_cleanup', dict(BASE_CASE, segment=segment, count=8, table_order=order,
                                        pooled_object=pooled, pattern=pattern, fragmented=True)
    for segment, size, order in itertools.product(SEGMENTS, (16, 32, 64, 128), ('first', 'last')):
        yield 'bounded_allocation_failures', dict(BASE_CASE, segment=segment, count=8, pool_size=size,
                                                 table_order=order, buffer_size=28, pattern='distinct')


def owner_location(model, pointer):
    if (not isinstance(pointer, int) or not 0 <= pointer <= 0xFFFFFFFF
            or (pointer & ~native.MASK) != model.segment):
        raise ValueError('Owner pointer exceeds the consistent 32-bit alias profile.')
    physical = pointer & native.MASK
    for name in ('pool', 'object'):
        if BASES[name] <= physical and physical + 0x40 <= BASES[name] + LENGTHS[name]:
            if name == 'pool' and model.owned_block(pointer).size - 4 < 0x40:
                raise ValueError('Pooled owner fields exceed their live allocation.')
            return name, physical - BASES[name]
    raise ValueError('Owner fields exceed their supplied fixture buffer.')


def expected_cleanup(model, owner):
    name, offset = owner_location(model, owner)
    get = lambda field: model.get(name, offset + field)
    trace = []
    if get(0x38):
        trace.append(get(0x3C))
        model.free(trace[-1])
        index = 0
        while index < struct.unpack('<i', struct.pack('<I', get(0x2C)))[0]:
            if index >= MAX_ENTRIES:
                raise ValueError('Cleanup model exceeded its bounded entry table.')
            table = get(0x38)
            model.owned_block(table)
            trace.append(model.get('pool', (table & native.MASK) - BASES['pool'] + index * 4))
            model.free(trace[-1])
            index += 1
        trace.append(get(0x38))
        model.free(trace[-1])
        model.put(name, offset + 0x38, 0)
    return trace


def cleanup_fixture(machine, case):
    validate_case(case)
    model = initial_model(case['pool_size'], case['segment'], case['seed'])
    prepare(machine, model)
    owner = allocation(machine, model, 128) if case['pooled_object'] else (BASES['object'] + OFFSET) | case['segment']
    if not owner:
        raise ValueError('The supplied owner must remain a valid live object.')
    table = allocation(machine, model, MAX_ENTRIES * 4) if case['present'] and case['table_order'] == 'first' else 0
    buffer = 0 if case['buffer_null'] else allocation(machine, model, case['buffer_size'])
    entries, holes = [], []
    for index in range(MAX_ENTRIES):
        present = (case['present'] and index < max(0, case['count']) and case['pattern'] != 'nulls'
                   and not (case['pattern'] == 'mixed' and index % 3 == 0))
        entries.append(allocation(machine, model, (12, 13, 31)[index % 3]) if present else 0)
        if present and case['fragmented']:
            holes.append(allocation(machine, model, 24))
    if case['present'] and case['table_order'] == 'last':
        table = allocation(machine, model, MAX_ENTRIES * 4)
    for pointer in holes:
        if pointer:
            release(machine, model, pointer)
    if table:
        data = struct.pack('<' + 'I' * MAX_ENTRIES, *entries)
        model.write_payload(table, data)
        machine.cpu.mem_write(table & native.MASK, data)
    name, offset = owner_location(model, owner)
    if case['pooled_object']:
        model.owned_block(owner)
    for field, value in ((0x2C, case['count']), (0x38, table), (0x3C, buffer)):
        model.put(name, offset + field, value)
        machine.cpu.mem_write((owner & native.MASK) + field, struct.pack('<I', value & 0xFFFFFFFF))
    machine.compare(model, True, 'supplied cleanup fields')
    return model, owner


def run_cleanup(machine, case):
    model, owner = cleanup_fixture(machine, case)
    trace = expected_cleanup(model, owner)
    machine.call(cleanup.FUNCTION['function'], owner)
    machine.compare(model, True, 'composed cleanup')
    if machine.free_trace != trace or machine.lock_trace != [value for _ in trace for value in (1, 0)]:
        raise ValueError('Composed cleanup releases or original lock transitions disagree with the model.')
    if machine.call('memory_is_locked') != 0:
        raise ValueError('Cleanup left the original allocation lock set.')
    machine.compare(model, True, 'cleanup lock getter')
    snapshot = model.snapshot()
    if expected_cleanup(model, owner) or model.snapshot() != snapshot:
        raise ValueError('Cleared or absent table should make repeated cleanup inert.')
    machine.call(cleanup.FUNCTION['function'], owner)
    machine.compare(model, True, 'repeated cleanup')
    if machine.free_trace or machine.lock_trace:
        raise ValueError('Repeated cleanup released a stale buffer or entered the allocator.')
    remaining = sum(not block.free for block in model.blocks)
    digest = hashlib.sha256(b''.join(snapshot[name] for name in sorted(snapshot))).hexdigest()
    # Teardown is the analysis caller's work, separate from observed cleanup.
    for block in list(model.blocks):
        if not block.free:
            release(machine, model, model.block_pointer(block.offset) + 4)
    if [(b.offset, b.size, b.free) for b in model.blocks] != [(0, model.pool_size, True)]:
        raise ValueError('Fixture teardown did not restore a coalesced pool.')
    return dict(releases=trace, remaining_live_after_cleanup=remaining, fixture_sha256=digest)


def verify(destination, candidate=None):
    backend = backend_identity()
    dependencies = native.evidence_dependencies('tools/verify_card_heap.py', 'tools/heap_model.py',
        'tools/verify_card_cleanup.py', 'requirements-card-heap.txt', 'src/base/base.c', 'src/base/base.h',
        'src/menu/card/memory_card.c', 'src/menu/card/memory_card.h')
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    program = native.load_program(FUNCTIONS)
    code, candidate_record = cleanup.candidate_code(candidate, program) if candidate else (None, None)
    globals_ = global_addresses(program)
    native.initialize_backend(program)
    started = time.monotonic()
    totals = Counter()
    accesses = Counter()
    host_calls = 0

    def collect(machine):
        nonlocal host_calls
        totals.update(machine.entries)
        accesses.update(machine.data_accesses)
        host_calls += machine.host_calls

    component_groups = Counter()
    for group, case in component_cases():
        machine = Machine(globals_)
        components(machine, group, case)
        collect(machine)
        component_groups[group] += 1
    cleanup_groups = Counter()
    remaining_counts = Counter()
    outcome_hash = hashlib.sha256()
    for group, case in cleanup_cases():
        results = []
        for label, image in [('original', None)] + ([('candidate', code)] if candidate_record else []):
            machine = Machine(globals_, image)
            result = run_cleanup(machine, case)
            collect(machine)
            results.append(result)
        if any(result != results[0] for result in results[1:]):
            raise ValueError('Original and candidate heap-cleanup outcomes differ.')
        outcome_hash.update(json.dumps(dict(case=case, result=results[0]), sort_keys=True).encode())
        remaining_counts[str(results[0]['remaining_live_after_cleanup'])] += 1
        cleanup_groups[group] += 1
    controls = []
    for name, function, offset, word, replacement in (
            ('wrong_minimum_payload', 'memory_allocate_mem', 0x58, 0x3410000C, 0x34100010),
            ('missing_free_header_flag', 'memory_free_mem', 0x16C, 0x3C034000, 0x3C030000),
            ('omitted_table_release', cleanup.FUNCTION['function'], 0x70, 0x0C005F3F, 0)):
        record = BY_NAME[function]
        changed = bytearray(program.target(int(record['address'], 16), record['bytes']))
        if struct.unpack_from('<I', changed, offset)[0] != word:
            raise ValueError('Heap fault control no longer identifies its pinned original word.')
        struct.pack_into('<I', changed, offset, replacement)
        machine = Machine(globals_, patches={function: bytes(changed)})
        try:
            if function == cleanup.FUNCTION['function']:
                run_cleanup(machine, BASE_CASE)
            else:
                components(machine, 'alignment_capacity_and_coalescing',
                           dict(segment=0, registered=True, seed=0, pool_size=128, requests=(1,)))
        except ValueError as error:
            controls.append(dict(name=name, function=function, function_offset=offset,
                                 detected=True, detection=str(error), private_copy_only=True))
        else:
            raise ValueError('Heap fault control was not detected: ' + name)
    if ((ROOT / native.configure.ROM).read_bytes() != program.ROM
            or (ROOT / native.configure.EXE).read_bytes() != program.ROM
            or native.check_build_current(ROOT) is not True
            or any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path, digest in before.items())
            or backend_identity() != backend):
        raise ValueError('Canonical inputs, producer dependencies or backend changed during heap verification.')
    if candidate_record and hashlib.sha256(candidate.read_bytes()).hexdigest() != candidate_record['executable_sha256']:
        raise ValueError('Candidate image changed during heap verification.')
    report = dict(status='passed_bounded_original_card_heap_composition',
        canonical_executable_sha1=hashlib.sha1(program.ROM).hexdigest(), original_and_current_build_equal=True,
        original_behavior_modified=False, model_api_calls=0, backend=backend,
        component_cases=sum(component_groups.values()), component_case_groups=dict(component_groups),
        cleanup_fixture_cases_per_image=sum(cleanup_groups.values()), cleanup_case_groups=dict(cleanup_groups),
        cleanup_executions_per_image=2 * sum(cleanup_groups.values()),
        images_checked=2 if candidate_record else 1, host_calls=host_calls,
        executed_native_entry_counts=dict(totals), guarded_data_access_counts=dict(accesses),
        native_functions=FUNCTIONS, global_addresses={name: hex(address) for name, address in globals_.items()},
        explicit_stub_count=0, explicit_stubs=[], candidate=candidate_record,
        cleanup_outcomes_sha256=outcome_hash.hexdigest(), remaining_live_after_cleanup=dict(remaining_counts),
        negative_controls_detected=controls,
        producer_dependencies=[dict(path=path.resolve().relative_to(ROOT).as_posix(), sha256=digest)
                               for path, digest in before.items()],
        source_promotions=0, original_feature_groups_accepted=0,
        scope='Seven original functions: supplied-manager setup, global preference and explicit fallback for '
              'direct component calls, first-fit allocation, alignment, minimum and split thresholds, valid-owned '
              'free/coalescing, NULL and failed allocations, lock stores/getter, complete guarded buffers and globals, '
              'three consistent pointer aliases, signed cleanup counts, original release order, external and pooled '
              'owners, fragmented pools, repeated cleanup, o32 saved registers, stack and red zones. '
              'The entire native cleanup/free/lock graph runs uninterrupted without output stubs. '
              'The caller teardown is separate. Invalid/duplicate frees, overflowing requests, OS allocator failure, '
              'concurrent execution, physical cards, natural error-path reachability, PS1 timing, padding-source '
              'recovery and whole-feature parity are not established.',
        elapsed_seconds=round(time.monotonic() - started, 3))
    with destination.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(passed=True, component_cases=report['component_cases'],
        cleanup_fixture_cases_per_image=report['cleanup_fixture_cases_per_image'],
        cleanup_executions_per_image=report['cleanup_executions_per_image'],
        images_checked=report['images_checked'], explicit_stubs=0, negative_controls=len(controls))))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='Fresh JSON report within .decomp-lab.')
    parser.add_argument('--candidate', help='Private complete image changing only the cleanup function.')
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
