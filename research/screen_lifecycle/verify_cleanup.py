"""Execute original screen/resource destruction on independently owned fixtures.

No constructor, callback or allocator output is substituted. The input graphs
are initialized fixtures, not claims of natural construction or hardware I/O.
"""
import argparse
from bisect import bisect_right
from collections import Counter
import gc
import hashlib
import itertools
import json
import lzma
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import configure
from research.screen_lifecycle import verify as lifecycle
from research.collision.trace_compiler_stack import new_output
from tools.heap_model import PoolModel
from tools.export_npc_catalogue import nm_functions
from tools.replay_cold_start_headless import require

native, heap = lifecycle.native, lifecycle.heap
TABLES = dict(main=0x80086B60, chart=0x80087AAC, base=0x8006B58C,
              sprite=0x8006F2C4, tile=0x8006F498, atlas=0x8006F514,
              cell=0x8006EAC0, text=0x8006EB90, glyph=0x8006EC74,
              card=0x80086DC4, tim=0x8006E558, sound=0x8006DA34)
LENGTHS = dict(manager=0x100, pool=0x20080, object=0x100)
FILE_TABLES = ('tile', 'atlas', 'tim', 'sound')
COPY_SLOTS = (16, 17, 18, 19, 20, 21, 22, 26, 27, 28, 29)
FAULTS = {
    'skip_last_chart_cell': (0x80058350, 0x2A220064, 0x2A220063, 'release order'),
    'retain_file_NoFree': (0x80026A04, 0xA6000020, 0, 'release order'),
    'skip_SPU_interval_free': (0x80038D2C, 0xACA80000, 0, 'complete-buffer mismatch in object'),
}
digest = lambda data: hashlib.sha256(data).hexdigest()


def cases():
    for kind, segment, seed, buffers, links, sound in itertools.product(
            ('main', 'chart'), lifecycle.SEGMENTS, (0, 1), (False, True), (False, True),
            ('borrowed', 'owned_no_bank', 'owned_bank')):
        yield dict(kind=kind, segment=segment, seed=seed, buffers=buffers, links=links, sound=sound)


def validate_case(case):
    require(set(case) == {'kind', 'segment', 'seed', 'buffers', 'links', 'sound'}, 'Incomplete cleanup fixture.')
    require(case['kind'] in ('main', 'chart') and case['segment'] in lifecycle.SEGMENTS
            and type(case['seed']) is int and case['seed'] in (0, 1)
            and type(case['buffers']) is bool and type(case['links']) is bool,
            'Unsupported screen cleanup fixture.')
    require(case['sound'] in ('borrowed', 'owned_no_bank', 'owned_bank'), 'Unsupported sound ownership state.')


class Fixture:
    """Build ownership and predict every final buffer before native execution."""
    def __init__(self, case):
        validate_case(case)
        self.case, self.allocations, self.holes, self.setup_operations = case, [], [], []
        self.record_setup = True
        buffers = {name: bytes((i * 37 + case['seed'] * 73 + 0xD7) & 255 for i in range(length))
                   for name, length in LENGTHS.items()}
        buffers['manager'] = bytearray(buffers['manager'])
        struct.pack_into('<II', buffers['manager'], heap.OFFSET,
                         (heap.BASES['pool'] + heap.OFFSET) | case['segment'], 0x20000)
        self.model = PoolModel(buffers, heap.BASES, heap.OFFSET, heap.OFFSET, 0x20000, case['segment'])
        self.model.setup()
        self.root = self.object(lifecycle.SIZES[case['kind']], case['kind'])
        self.observer = self.object(12, 'base') if case['links'] else 0
        self.borrowed_child = self.object(12, 'base') if case['links'] else 0
        self.sprite = self.transform(0x68, 'sprite')
        self.tile = self.object(0x44, 'tile')
        self.atlas = self.object(0x38, 'atlas')
        for pointer, offset in ((self.sprite, 0x78), (self.tile, 0x7C), (self.atlas, 0x80)):
            self.put(self.root, offset, pointer)
        self.tile_extra = self.alloc(36) if case['buffers'] else 0
        self.atlas_extra = [self.alloc(20), self.alloc(44)] if case['buffers'] else [0, 0]
        self.put(self.tile, 0x38, self.tile_extra)
        self.put(self.atlas, 0x34, self.atlas_extra[0])
        self.put(self.atlas, 0x2C, self.atlas_extra[1])
        self.file_payloads = {}
        for pointer in (self.tile, self.atlas):
            self.file_fixture(pointer)
        self.sound = self.object(0x64, 'sound')
        self.put(self.root, 0x48, self.sound)
        self.put(self.root, 0x44, int(case['sound'] != 'borrowed'))
        self.sound_extra = [self.alloc(n) if case['buffers'] else 0 for n in (20, 44, 28)] if case['sound'] != 'borrowed' else []
        if self.sound_extra:
            self.file_fixture(self.sound)
            for offset, pointer in zip((0x4C, 0x50, 0x5C), self.sound_extra):
                self.put(self.sound, offset, pointer)
        self.put(self.sound, 0x54, 0xFFFF if case['sound'] == 'owned_no_bank' else 5)
        self.texture = self.object(0x50, 'tim') if case['buffers'] else 0
        self.put(self.root, 0x70, 1 if self.texture else 0)
        self.put(self.root, 0x74, self.texture)
        if self.texture:
            self.file_fixture(self.texture)
        self.card, self.card_texture, self.title, self.cells = 0, 0, 0, []
        if case['kind'] == 'main':
            self.card = self.object(0xC0, 'card') if case['buffers'] else 0
            self.card_texture = self.object(0x50, 'tim') if self.card else 0
            self.put(self.root, 0xAC, self.card)
            self.put(self.root, 0xA8, self.card_texture)
            if self.card_texture:
                self.file_fixture(self.card_texture)
            self.title = self.transform(0xB8, 'text')
            self.glyphs = [self.transform(0xA8, 'glyph') for _ in range(3 + case['seed'] * 4)]
            self.glyph_table = self.alloc(4 * len(self.glyphs))
            for i, pointer in enumerate(self.glyphs):
                self.put(self.glyph_table, i * 4, pointer)
            self.put(self.title, 0xA8, len(self.glyphs) << 8)
            self.put(self.title, 0xB4, self.glyph_table)
            self.put(self.root, 0xB0, self.title)
        else:
            self.cells = [self.transform(0x6C, 'cell') for _ in range(100)]
            for i, pointer in enumerate(self.cells):
                self.put(self.root, 0xA8 + i * 4, pointer)
            self.events = self.alloc(4) if case['buffers'] else 0
            self.put(self.root, 0x240, self.events)
        self.extra_owned_objects, self.extra_retained_pointers = [], set()
        self.initialize_extra_resources()
        self.owned_objects = [self.root, self.sprite, self.tile, self.atlas]
        if case['sound'] != 'borrowed':
            self.owned_objects.append(self.sound)
        self.owned_objects += [p for p in (self.texture, self.card, self.card_texture, self.title) if p]
        self.owned_objects += self.cells + (self.glyphs if self.title else [])
        self.owned_objects += self.extra_owned_objects
        if self.observer:
            for pointer in self.owned_objects:
                self.attach(self.observer, pointer)
            self.attach(self.root, self.borrowed_child)
        for pointer in self.holes:
            self.model.free(pointer)
            self.setup_operations.append(['free_hole', pointer])
        # One allocated SPU interval, followed by its valid tail sentinel.
        # This is supplied SDK RAM, not an assertion that VAB DMA completed.
        record_pointer = (heap.BASES['object'] + heap.OFFSET) | case['segment']
        struct.pack_into('<IIII', self.model.buffers['object'], heap.OFFSET,
                         0x1010, 0x200, 0x40001210, 0x7EDF0)
        self.setup_operations.append(['object_words', heap.OFFSET, [0x1010, 0x200, 0x40001210, 0x7EDF0]])
        allocation = bytearray(64); struct.pack_into('<I', allocation, 20, 0x1010)
        self.sdk_before = {0x6E188: struct.pack('<III', 16, 1, record_pointer),
                           0x8EA2C: bytes(5) + b'\x01' + bytes(10),
                           0x90BD0: struct.pack('<H', 1), 0x90BD4: bytes(allocation),
                           0x8A8C4: struct.pack('<I', 2)}
        self.sdk_after = dict(self.sdk_before)
        if case['sound'] == 'owned_bank':
            self.sdk_after[0x6E188] = struct.pack('<III', 16, 0, record_pointer)
            self.sdk_after[0x8EA2C] = bytes(16)
            self.sdk_after[0x90BD0] = bytes(2)
        if case['sound'] != 'borrowed':
            self.sdk_after[0x8A8C4] = struct.pack('<I', 1)
        self.initial = self.model.snapshot()
        self.record_setup = False
        self.live_before = sum(not b.free for b in self.model.blocks)
        self.free_trace = []
        self.predict_cleanup()
        self.model.validate()
        expected_live = {self.observer, self.borrowed_child} - {0}
        if case['sound'] == 'borrowed':
            expected_live.add(self.sound)
        expected_live.update(self.extra_retained_pointers)
        actual_live = {self.model.block_pointer(b.offset) + 4 for b in self.model.blocks if not b.free}
        require(actual_live == expected_live, 'Cleanup oracle leaked an owned allocation.')

    def offset(self, pointer):
        return (pointer & native.MASK) - heap.BASES['pool']

    def initialize_extra_resources(self):
        """Companion profiles can supply additional owned content before setup."""

    def predict_extra_cleanup(self):
        """Predict a companion's content release before the root is released."""

    def get(self, pointer, offset=0):
        return self.model.get('pool', self.offset(pointer) + offset)

    def put(self, pointer, offset, value):
        self.model.put('pool', self.offset(pointer) + offset, value)
        if self.record_setup:
            self.setup_operations.append(['put', pointer, offset, value])

    def alloc(self, size):
        pointer = self.model.allocate(size)
        require(pointer != 0, 'Fixture exceeded its original pool capacity.')
        self.allocations.append((pointer, size))
        self.setup_operations.append(['allocate', pointer, size])
        offset = self.offset(pointer)
        self.model.buffers['pool'][offset:offset + size] = bytes(size)
        return pointer

    def object(self, size, kind):
        pointer = self.alloc(size)
        self.put(pointer, 0, TABLES[kind])
        if self.case['seed']:
            self.holes.append(self.alloc(20))
        return pointer

    def transform(self, size, kind):
        pointer = self.object(size, kind)
        coordinate, rotation = self.alloc(0x50), self.alloc(0x28)
        self.put(pointer, 0x14, coordinate)
        self.put(coordinate, 0x44, rotation)
        return pointer

    def file_fixture(self, pointer):
        payload = self.alloc(52) if self.case['buffers'] else 0
        self.file_payloads[pointer] = payload
        self.put(pointer, 0x0C, 1)  # Opaque nonzero file state, retained by cleanup.
        self.put(pointer, 0x10, payload)
        self.put(pointer, 0x14, 52 if payload else 0)
        self.put(pointer, 0x20, 1)  # Destroy overrides NoFree; no queued requests.

    def attach(self, parent, child):
        node = self.alloc(8)
        self.put(node, 0, self.get(parent, 4)); self.put(node, 4, child)
        self.put(parent, 4, node)
        node = self.alloc(8)
        self.put(node, 0, self.get(child, 8)); self.put(node, 4, parent)
        self.put(child, 8, node)

    def free(self, pointer):
        self.free_trace.append(pointer)
        self.model.free(pointer)

    def remove(self, owner, field, value):
        current, previous = self.get(owner, field), 0
        while current:
            following = self.get(current)
            if self.get(current, 4) == value:
                self.put(previous or owner, 0 if previous else field, following)
                self.free(current)
                return
            previous, current = current, following
        raise ValueError('Ownership oracle could not remove a declared edge.')

    def base_cleanup(self, pointer):
        parents = []
        node = self.get(pointer, 8)
        while node:
            parents.append(self.get(node, 4)); node = self.get(node)
        for parent in parents:
            self.remove(parent, 4, pointer)
            self.remove(pointer, 8, parent)
        children = []
        node = self.get(pointer, 4)
        while node:
            children.append(self.get(node, 4)); node = self.get(node)
        for child in children:
            self.remove(pointer, 4, child)
            self.remove(child, 8, pointer)
        self.put(pointer, 8, 0)

    def destroy_transform(self, pointer):
        coordinate = self.get(pointer, 0x14)
        self.free(self.get(coordinate, 0x44))
        self.free(coordinate)
        self.put(pointer, 0x18, 0); self.put(pointer, 0x20, 0)
        self.base_cleanup(pointer)
        self.free(pointer)

    def destroy_file(self, pointer, extra=()):
        self.put(pointer, 0x20, self.get(pointer, 0x20) & 0xFFFF0000)
        for item in extra:
            self.free(item)
        payload = self.file_payloads[pointer]
        if payload:
            self.free(payload); self.put(pointer, 0x10, 0)
        self.base_cleanup(pointer)
        self.free(pointer)

    def predict_cleanup(self):
        if self.card:
            self.base_cleanup(self.card); self.free(self.card)
            self.destroy_file(self.card_texture)
        self.destroy_transform(self.sprite)
        self.destroy_file(self.tile, [self.tile_extra])
        self.destroy_file(self.atlas, self.atlas_extra)
        if self.case['sound'] != 'borrowed':
            self.destroy_file(self.sound, self.sound_extra)
            if self.case['sound'] == 'owned_bank':
                struct.pack_into('<II', self.model.buffers['object'], heap.OFFSET, 0x40001010, 0x7EFF0)
        if self.texture:
            self.destroy_file(self.texture)
        if self.title:
            for index, pointer in enumerate(self.glyphs):
                self.destroy_transform(pointer)
                self.put(self.glyph_table, index * 4, 0)
            self.free(self.glyph_table); self.put(self.title, 0xB4, 0)
            self.destroy_transform(self.title)
        else:
            self.free(self.events)
            for pointer in self.cells:
                self.destroy_transform(pointer)
        self.predict_extra_cleanup()
        self.base_cleanup(self.root)
        self.free(self.root)


class Machine(heap.Machine):
    INSTRUCTION_LIMIT = 500000

    def __init__(self, fixture, rows, fault=None):
        self.fixture, self.events, self.pending_edge, self.indirect_calls = fixture, [], None, []
        self.rows, self.fault, self.fault_hits, self.last_return = rows, fault, 0, None
        super().__init__(heap.global_addresses(native.h))
        self.native_entries = {int(r['address'], 16) & native.MASK: r['function'] for r in rows}
        self.ranges = sorted((int(r['address'], 16) & native.MASK,
                              (int(r['address'], 16) & native.MASK) + r['bytes']) for r in rows)
        self.starts = [lo for lo, _ in self.ranges]
        self.tables = {TABLES[k]: bytearray(native.h.target(TABLES[k], 0x7C)) for k in FILE_TABLES}
        source = native.h.target(native.h.symbols['g_CD_FILE_DRIVER_VTABLE'], 0x7C)
        for data in self.tables.values():
            for slot in COPY_SLOTS:
                data[slot * 4:slot * 4 + 4] = source[slot * 4:slot * 4 + 4]
        for name, data in fixture.initial.items():
            self.cpu.mem_write(heap.BASES[name], data)
        for address in self.globals.values():
            self.cpu.mem_write(address, bytes(4))
        for address, data in fixture.sdk_before.items():
            self.cpu.mem_write(address, data)
        if fault:
            pc, old, new, _reason = FAULTS[fault]
            require(native.h.target(pc, 4) == struct.pack('<I', old), 'Fault lost its original instruction.')
            self.cpu.mem_write(pc & native.MASK, struct.pack('<I', new))

    def hook(self, cpu, address, size, unused):
        pc = address & native.MASK
        if self.fault and pc == FAULTS[self.fault][0] & native.MASK:
            self.fault_hits += 1
        args = [cpu.reg_read(getattr(native.reg, 'UC_MIPS_REG_A' + str(i))) for i in range(3)]
        self.pending_edge = lifecycle.observe_target_entry(self.pending_edge, address, args)
        index = bisect_right(self.starts, pc) - 1
        require(index >= 0 and self.ranges[index][0] <= pc < self.ranges[index][1],
                'Execution escaped a complete original function: ' + hex(address))
        self.instructions.append(pc)
        name = self.native_entries.get(pc)
        if name:
            self.events.append([name, *args]); self.entries[name] += 1
            self.executed_native_functions.add(name)
            if name == 'memory_free_mem': self.free_trace.append(args[0])
            elif name == 'memory_set_lock': self.lock_trace.append(args[0])
        word = int.from_bytes(cpu.mem_read(pc, 4), 'little')
        if word & 0xFC1FFFFF == 0x0000F809:
            register = word >> 21 & 31
            edge = dict(pc=hex(address), target=hex(cpu.reg_read(native.reg.UC_MIPS_REG_0 + register)),
                        pre_delay_arguments=args)
            self.indirect_calls.append(edge); self.pending_edge = edge

    def memory_hook(self, cpu, access, address, size, value, unused):
        physical = address & native.MASK
        data = [(heap.BASES[n], heap.BASES[n] + length) for n, length in LENGTHS.items()]
        data += [(a, a + 4) for a in self.globals.values()]
        data += [(a, a + len(b)) for a, b in self.fixture.sdk_before.items()]
        data += [(0x8A88C, 0x8A890)]  # Original CD lock, acquired and released.
        if access == native.unicorn.UC_MEM_READ:
            # Original initialized CD-driver selection and synchronous state.
            data += [(a, a + 4) for a in (0x8A84C, 0x8A85C, 0x8A860, 0x8A894)]
        data += [(native.STACK - 0x300, native.STACK + 0x100)]
        table_ranges = [(TABLES[k] & native.MASK, (TABLES[k] & native.MASK) +
                         (0x124 if k in ('main', 'chart') else 0xD4)) for k in TABLES]
        table_ranges += [(0x6E730, 0x6E854), (0x6E878, 0x6E878 + 0x68),
                         (native.h.symbols['g_CD_FILE_DRIVER_VTABLE'] & native.MASK,
                          (native.h.symbols['g_CD_FILE_DRIVER_VTABLE'] & native.MASK) + 0x7C)]
        if access == native.unicorn.UC_MEM_READ:
            data += table_ranges
        else:
            data += [(table & native.MASK, (table & native.MASK) + len(buf)) for table, buf in self.tables.items()]
        require(any(lo <= physical and physical + size <= hi for lo, hi in data),
                'Unreviewed cleanup data access: ' + hex(address))
        self.data_accesses['write' if access == native.unicorn.UC_MEM_WRITE else 'read'] += 1

    def execute(self):
        self.call('memory_set_manager', self.fixture.model.manager_pointer)
        for table in self.tables:
            self.call('file_driver_copy_vtable_slots', table, native.h.symbols['g_CD_FILE_DRIVER_VTABLE'])
            require(bytes(self.cpu.mem_read(table & native.MASK, 0x7C)) == self.tables[table],
                    'Original driver-slot copy differs from its independent model.')
        self.events, self.indirect_calls = [], []
        value = self.call('base_class_destructor', self.fixture.root)
        self.last_return = value
        require(value == 0 and self.pending_edge is None, 'Destroy did not return NULL through its completed call graph.')
        require(self.free_trace == self.fixture.free_trace, 'Original cleanup release order differs from the ownership model.')
        require(self.lock_trace == [state for _p in self.free_trace for state in (1, 0)],
                'Each original release, including NULL, must acquire and release the heap lock.')
        self.compare(self.fixture.model, True, 'screen cleanup')
        for address, expected in self.fixture.sdk_after.items():
            require(bytes(self.cpu.mem_read(address, len(expected))) == expected,
                    'Complete SDK state mismatch: ' + hex(address))
        require(int.from_bytes(self.cpu.mem_read(0x8A88C, 4), 'little') == 0, 'CD lock was not released.')
        for table, expected in self.tables.items():
            require(bytes(self.cpu.mem_read(table & native.MASK, len(expected))) == expected,
                    'Cleanup changed a driver table.')
        for row in self.rows:
            address, size = int(row['address'], 16), row['bytes']
            require(bytes(self.cpu.mem_read(address & native.MASK, size)) == native.h.target(address, size),
                    'Cleanup changed original code: ' + row['function'])
        return dict(input=self.fixture.case, returned=value, release_trace=self.free_trace,
                    setup_operations=self.fixture.setup_operations, root=self.fixture.root,
                    initial_buffer_hashes={n: digest(b) for n, b in self.fixture.initial.items()},
                    SDK_before={hex(a): b.hex() for a, b in self.fixture.sdk_before.items()},
                    SDK_after={hex(a): bytes(self.cpu.mem_read(a, len(b))).hex() for a, b in self.fixture.sdk_after.items()},
                    live_allocations_before=self.fixture.live_before,
                    live_allocations_after=sum(not b.free for b in self.fixture.model.blocks),
                    buffer_hashes={n: digest(bytes(self.cpu.mem_read(heap.BASES[n], len(b))))
                                   for n, b in self.fixture.model.snapshot().items()},
                    original_entries=dict(self.entries), indirect_calls=self.indirect_calls,
                    instructions=len(self.instructions))


def qualify(output, diagnostic=None):
    require(lifecycle.check_build_current(ROOT) is True, 'Require the current complete matching build.')
    original = (ROOT / configure.ROM).read_bytes()
    require(digest(original) == lifecycle.CANONICAL_SHA256 and (ROOT / configure.EXE).read_bytes() == original,
            'The complete original and current build must be canonical.')
    if diagnostic is None:
        lifecycle.qualify_functions(output)
        diagnostic = output
    diagnostic = Path(diagnostic)
    elf_path = diagnostic / 'candidate-symbols.elf'
    elf = elf_path.read_bytes()
    image = subprocess.check_output([configure.CROSS + 'objcopy', '-O', 'binary', str(elf_path), '/dev/stdout'])
    require(image == original, 'Diagnostic complete image differs from retail.')
    text = subprocess.check_output([configure.CROSS + 'nm', '-S', '--defined-only', str(elf_path)], text=True)
    gnu = nm_functions(text)
    pins = json.loads((ROOT / 'research/screen_lifecycle/cleanup-functions.json').read_text())
    rows = [lifecycle.owned_record(original, elf, gnu, r['function'], int(r['address'], 16)) for r in pins]
    require(rows == pins, 'A complete original function differs from the published pins.')
    return rows, dict(complete_image_equal=True, canonical_sha256=digest(image),
                      diagnostic_elf_sha256=digest(elf), GNU_symbol_output_sha256=digest(text.encode()))


def verify(destination, lab_root=None, diagnostic=None):
    require(sys.platform == 'linux' and Path.cwd().resolve() == ROOT, 'Run from the repository root in WSL/Linux.')
    paths = {Path(__file__), ROOT/'research/screen_lifecycle/cleanup-functions.json',
             ROOT/'tools/verify_card_heap.py', ROOT/'tools/heap_model.py', ROOT/'tools/verify_native_ai.py',
             ROOT/'research/screen_lifecycle/verify.py', ROOT/'research/collision/trace_compiler_stack.py',
             ROOT/'research/compiler/compare_function.py', ROOT/'tools/decomp_workbench.py',
             ROOT/'tools/progress.py', ROOT/'tools/compile_c.py', ROOT/'configure.py',
             ROOT/'requirements-card-heap.txt', ROOT/'PROJECT_OBJECTIVE.md',
             ROOT/configure.ROM, ROOT/configure.EXE, ROOT/configure.LD_SCRIPT}
    paths.update(ROOT/name for name, _kind in lifecycle.build_manifest())
    paths.update((ROOT/'src').rglob('*.h'))
    paths.update(ROOT/configure.BUILD_DIR/(name+'.o') for name, _kind in lifecycle.build_manifest())
    before = {str(p): lifecycle.file_record(p) for p in sorted(paths)}
    output = new_output(destination, lab_root)
    rows, image = qualify(output, diagnostic)
    native.initialize_backend(native.load_program(rows))
    backend = heap.backend_identity()
    counts, groups, seen, aggregate = Counter(), Counter(), set(), hashlib.sha256()
    witnesses, releases, instruction_counts = {}, [], []
    journal = output/'cases.jsonl.xz'
    with lzma.open(journal, 'xt', encoding='utf-8', newline='\n') as stream:
        for index, case in enumerate(cases()):
            key = json.dumps(case, sort_keys=True)
            require(key not in seen, 'Repeated cleanup input profile.'); seen.add(key)
            machine = Machine(Fixture(case), rows)
            result = machine.execute()
            counts.update(machine.entries)
            group = case['kind']+'/'+case['sound']; groups[group] += 1
            witnesses.setdefault(group, dict(input=case, instructions=result['instructions'],
                                             released=len(result['release_trace'])))
            releases.append(len(result['release_trace'])); instruction_counts.append(result['instructions'])
            line = json.dumps(result, sort_keys=True, separators=(',', ':'))+'\n'
            stream.write(line); aggregate.update(line.encode())
            if (index+1) % 12 == 0:
                print(json.dumps(dict(completed=index+1, total=144)), flush=True)
            gc.collect()
    require(set(counts) == {r['function'] for r in rows}, 'Not every qualified native body executed.')
    faults = []
    control = dict(kind='chart', segment=0x80000000, seed=1, buffers=True, links=True, sound='owned_bank')
    for fault, (pc, old, new, reason) in FAULTS.items():
        machine = Machine(Fixture(control), rows, fault)
        try:
            machine.execute()
        except ValueError as error:
            require(machine.fault_hits > 0 and machine.last_return == 0 and reason in str(error),
                    'Control did not complete through the changed instruction and its intended rejection.')
            faults.append(dict(fault=fault, pc=hex(pc), original_word=hex(old), changed_word=hex(new),
                               executed_hits=machine.fault_hits, returned=machine.last_return, rejection=str(error)))
        else:
            raise ValueError('Executed resource leak was not rejected: '+fault)
    require(all(lifecycle.file_record(Path(p)) == record for p, record in before.items()),
            'A protected source, object, image or producer changed during verification.')
    require(lifecycle.check_build_current(ROOT) is True and heap.backend_identity() == backend,
            'Build or execution backend changed.')
    report = dict(schema_version=1, status='passed_bounded_original_screen_resource_cleanup',
                  initialized_profiles=len(seen), groups=dict(groups), original_native_functions=rows,
                  original_entry_counts=dict(counts), input_output_sha256=aggregate.hexdigest(),
                  cases_journal=dict(path=journal.name, **lifecycle.file_record(journal)),
                  release_count_range=[min(releases), max(releases)],
                  instruction_count_range=[min(instruction_counts), max(instruction_counts)],
                  witnesses=witnesses, negative_controls=faults, dependency_output_contracts=[],
                  initialization='Supplied independently modeled owned graph and SDK RAM; no constructors claimed.',
                  backend=backend, complete_image=image,
                  producer_dependencies=[dict(path=Path(p).relative_to(ROOT).as_posix(), **r)
                                         for p, r in before.items() if Path(p).is_relative_to(ROOT)],
                  new_game_C_bytes=0, accepted_original_features=0, accepted_NPC_encounters=0, model_API_calls=0,
                  remaining=['natural construction and controller histories', 'populated secondary menu panels',
                             'pending CD requests and final sound-instance hardware shutdown',
                             'natural audio/video output and timing', 'whole-feature acceptance'])
    (output/'cleanup-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(status=report['status'], profiles=len(seen), functions=len(rows), controls=len(faults))), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', type=Path, help='Reuse an existing canonical diagnostic link directory.')
    parser.add_argument('--lab-root', type=Path)
    args = parser.parse_args()
    verify(args.output, args.lab_root, args.diagnostic)


if __name__ == '__main__':
    main()
