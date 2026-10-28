"""Execute original SDK sound metadata bodies in bounded, explicit RAM contexts.

No SPU/DMA output is stubbed. Header-open fixtures stop in the original pending
state. Ready-state getters require caller-supplied, separately authenticated RAM.
These calls do not establish natural call reachability or audible playback.
"""
from collections import Counter
import hashlib
from pathlib import Path
import struct
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.compiler.compare_function import CANONICAL_SHA256, elf_function
from tools.export_npc_catalogue import nm_functions
from tools import verify_native_ai as n
from tools.inventory_sound import TONE_BASE, vab_info

API_ROOTS = ('SpuInitMalloc', 'SsVabOpenHead', 'SsUtGetVabHdr',
             'SsUtGetProgAtr', 'SsUtGetVagAtr', 'SsSeqOpen',
             'bgm_get_sequence_work', 'func_800323A8')
HEAD, ALLOC, OUT = 0x110000, 0x160000, 0x150020
USED, HEADERS, PROGRAM_TABLES, TONE_TABLES = 0x8EA2C, 0x8E80C, 0x8E7A4, 0x8E850
SPU_BASES, SPU_LENGTHS = 0x90BD4, 0x90B90
FIELDS = {'SsUtGetVabHdr': [(0, 12), (18, 28)],
          'SsUtGetProgAtr': [(0, 5), (6, 8)],
          'SsUtGetVagAtr': [(0, 14), (16, 24)]}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def qualify(elf_path, roots=API_ROOTS):
    """Use retained ELF sizes, GNU symbols and every original byte; never relink."""
    elf_path = Path(elf_path)
    elf = elf_path.read_bytes()
    rom = (ROOT / 'rom/SLPS_015.56').read_bytes()
    require(sha(rom) == CANONICAL_SHA256, 'Canonical executable changed.')
    output = subprocess.check_output(['mipsel-linux-gnu-nm', '-S', '--defined-only', str(elf_path)], text=True)
    symbols = nm_functions(output)
    owners = {}
    for name, spans in symbols.items():
        for address, size in spans:
            if size:
                owners.setdefault((address, size), []).append(name)
    pending, qualified, external = list(roots), {}, []
    while pending:
        name = pending.pop()
        require(len(symbols.get(name, [])) == 1, 'Ambiguous complete function: ' + name)
        address, size = symbols[name][0]
        if address in qualified:
            continue
        code, _ = elf_function(elf, name, address)
        offset = 0x800 + address - 0x80010000
        require(len(code) == size and code == rom[offset:offset + size], 'Noncanonical complete SDK body: ' + name)
        qualified[address] = dict(function=name, address=hex(address), bytes=size, sha256=sha(code))
        for index, (word,) in enumerate(struct.iter_unpack('<I', code)):
            pc = address + index * 4
            if word >> 26 not in (2, 3):
                continue
            target = ((pc + 4) & 0xF0000000) | ((word & 0x3FFFFFF) << 2)
            if address <= target < address + size:
                continue
            found = [(a, length, names) for (a, length), names in owners.items() if a <= target < a + length]
            if not found and not 0x80010000 <= target < 0x80010000 + len(rom) - 0x800:
                external.append(dict(caller=name, PC=hex(pc), target=hex(target)))
            else:
                require(len(found) == 1, 'Unowned original transfer at ' + hex(pc))
                pending.append(sorted(found[0][2])[0])
    rows = sorted(qualified.values(), key=lambda row: int(row['address'], 16))
    require(all(int(a['address'], 16) + a['bytes'] <= int(b['address'], 16)
                for a, b in zip(rows, rows[1:])), 'Overlapping SDK function owners.')
    n.initialize_backend(n.load_program(rows))
    return rows, dict(ELF_sha256=sha(elf), GNU_symbol_output_sha256=sha(output.encode()),
                      complete_spans_original_byte_equal=True, functions=rows,
                      unqualified_static_external_transfers=external)


class Machine(n.Machine):
    def __init__(self, rows, ram=None, fault=None):
        self.rows = rows
        self.spans = [(int(r['address'], 16) & n.MASK,
                       (int(r['address'], 16) & n.MASK) + r['bytes']) for r in rows]
        self.entries, self.seen, self.last_pc = Counter(), set(), None
        super().__init__(start=0x32C98, native_functions=rows)
        if ram is not None:
            require(len(ram) == 2**21, 'Use one complete 2 MiB RAM context.')
            for row in rows:
                at = int(row['address'], 16) & n.MASK
                require(sha(ram[at:at + row['bytes']]) == row['sha256'],
                        'Recorded SDK body differs: ' + row['function'])
            self.cpu.mem_write(0, ram)
        if fault:
            address, before, after = fault
            require(bytes(self.cpu.mem_read(address & n.MASK, 4)) == struct.pack('<I', before),
                    'Fault-control instruction changed.')
            self.cpu.mem_write(address & n.MASK, struct.pack('<I', after))

    def hook(self, cpu, address, size, unused):
        pc = address & n.MASK
        require(any(start <= pc < end for start, end in self.spans),
                'Unreviewed original instruction: ' + hex(address))
        self.last_pc = pc
        self.seen.add(pc)
        name = self.native_entries.get(pc)
        if name:
            self.entries[name] += 1
            self.executed_native_functions.add(name)

    def call(self, name, *args):
        matches = [r for r in self.rows if r['function'] == name]
        require(len(matches) == 1 and len(args) <= 4, 'Unsupported original entry or ABI.')
        self.saved = {reg: n.u32(0xB8000000 + i * 0x10309) for i, reg in enumerate(n.SAVED)}
        for reg, value in self.saved.items():
            self.cpu.reg_write(reg, value)
        for reg, value in [(n.reg.UC_MIPS_REG_SP, n.STACK), (n.reg.UC_MIPS_REG_GP, 0x8008A808),
                           (n.reg.UC_MIPS_REG_RA, n.END), *zip((n.reg.UC_MIPS_REG_A0, n.reg.UC_MIPS_REG_A1,
                                                             n.reg.UC_MIPS_REG_A2, n.reg.UC_MIPS_REG_A3), args)]:
            self.cpu.reg_write(reg, n.u32(value))
        self.cpu.emu_start(int(matches[0]['address'], 16) & n.MASK, n.END, count=200000)
        require(self.cpu.reg_read(n.reg.UC_MIPS_REG_PC) == n.END, 'Original call did not return within its bound.')
        require(self.cpu.reg_read(n.reg.UC_MIPS_REG_SP) == n.STACK
                and self.cpu.reg_read(n.reg.UC_MIPS_REG_GP) == 0x8008A808
                and all(self.cpu.reg_read(reg) == value for reg, value in self.saved.items()),
                'Original SDK call violated its preserved-register/stack ABI.')
        return self.cpu.reg_read(n.reg.UC_MIPS_REG_V0)


def runtime_header(header, spu_base):
    """Compute all original OpenHead bookkeeping writes, without discarding bytes."""
    expected = bytearray(header)
    active = 0
    for program in range(128):
        offset = 32 + program * 16
        struct.pack_into('<I', expected, offset + 8, active)
        if expected[offset]:
            active += 1
    samples = struct.unpack_from('<H', header, 22)[0]
    sizes_at = 2080 + struct.unpack_from('<H', header, 18)[0] * 512
    cumulative = 0
    for index in range(samples + 1):
        cumulative += struct.unpack_from('<H', header, sizes_at + index * 2)[0] * 8
        struct.pack_into('<H', expected, 32 + (index // 2) * 16 + 12 + 2 * (index & 1),
                         ((spu_base + cumulative) >> 3) & 0xffff)
    return bytes(expected)


def pending_bank(rows, header, body):
    info = vab_info(header, body)
    machine = Machine(rows)
    cpu = machine.cpu
    cpu.mem_write(HEAD - 32, b'\x9b' * 32 + header + b'\x4d' * 32)
    cpu.mem_write(ALLOC - 32, b'\x7d' * 32 + bytes(128) + b'\x38' * 32)
    require(machine.call('SpuInitMalloc', 16, ALLOC) == 16, 'Original SPU allocator did not initialize.')
    bank = machine.call('SsVabOpenHead', HEAD, -1)
    require(bank == 0 and cpu.mem_read(USED, 1) == b'\x02', 'Original header-open pending state differs.')
    base = struct.unpack('<I', cpu.mem_read(SPU_BASES, 4))[0]
    length = struct.unpack('<I', cpu.mem_read(SPU_LENGTHS, 4))[0]
    require(base == 0x1010 and length == len(body), 'Original sample allocation differs.')
    require(bytes(cpu.mem_read(HEAD, len(header))) == runtime_header(header, base),
            'Complete original header normalization differs from its byte model.')
    require(bytes(cpu.mem_read(HEAD - 32, 32)) == b'\x9b' * 32
            and bytes(cpu.mem_read(HEAD + len(header), 32)) == b'\x4d' * 32
            and bytes(cpu.mem_read(ALLOC - 32, 32)) == b'\x7d' * 32
            and bytes(cpu.mem_read(ALLOC + 128, 32)) == b'\x38' * 32, 'Original loader crossed a caller guard.')
    for name, args in [('SsUtGetVabHdr', (bank, OUT)), ('SsUtGetProgAtr', (bank, 0, OUT)),
                       ('SsUtGetVagAtr', (bank, 0, 0, OUT))]:
        cpu.mem_write(OUT - 32, b'\xa5' * 96)
        require(machine.call(name, *args) == 0xffffffff and cpu.mem_read(OUT - 32, 96) == b'\xa5' * 96,
                'Pending metadata was incorrectly exposed by ' + name)
    return dict(programs=info['declared_programs'], tones=info['declared_tones'], samples=info['declared_samples'],
                pending_flag=2, allocated_SPU_address=base, allocated_SPU_bytes=length,
                complete_mutated_VH_sha256=sha(runtime_header(header, base)),
                all_header_bytes_and_guards_equal=True, pending_getter_rejections=3,
                entered_original_functions=dict(machine.entries), native_output_stubs=0,
                SPU_transfer_executed=False, audible_playback_verified=False)


def ready_bindings(ram, banks):
    """Identify exact complete original VH bytes including all runtime writes."""
    require(len(ram) == 2**21, 'Use complete recorded RAM.')
    found = []
    for bank, flag in enumerate(ram[USED:USED + 16]):
        if flag != 1:
            continue
        address = struct.unpack_from('<I', ram, HEADERS + bank * 4)[0]
        at = address & n.MASK
        base = struct.unpack_from('<I', ram, SPU_BASES + bank * 4)[0]
        matches = [(name, head, body) for name, (head, body) in banks.items()
                   if at + len(head) <= len(ram) and ram[at:at + len(head)] == runtime_header(head, base)]
        require(len(matches) == 1, 'Ready bank lacks one exact complete VH owner: ' + str(bank))
        name, head, body = matches[0]
        require(struct.unpack_from('<I', ram, PROGRAM_TABLES + bank * 4)[0] == address + 32
                and struct.unpack_from('<I', ram, TONE_TABLES + bank * 4)[0] == address + TONE_BASE,
                'Ready registry pointers differ from their original VH layout.')
        require(struct.unpack_from('<I', ram, SPU_LENGTHS + bank * 4)[0] == len(body),
                'Ready registered waveform length differs from its original VB.')
        found.append(dict(bank_id=bank, path=name, header_address=address, SPU_address=base,
                          header=head, info=vab_info(head, body)))
    require(found, 'No exact original ready bank was observed.')
    return found


def getter_case(machine, binding, name, program=0, tone=0):
    """Compare all 2 MiB, including exact stack stores and SDK cached fields."""
    cpu = machine.cpu
    bank, head = binding['bank_id'], binding['header_address']
    info = binding['info']
    if name == 'SsUtGetVabHdr':
        source = binding['header'][:32]
        args = (bank, OUT)
    elif name == 'SsUtGetProgAtr':
        source = binding['header'][32 + program * 16:48 + program * 16]
        args = (bank, program, OUT)
    else:
        owner = next(r for r in info['programs'] if r['native_id'] == program)
        where = TONE_BASE + owner['dense_tone_block'] * 512 + tone * 32
        source = binding['header'][where:where + 32]
        args = (bank, program, tone, OUT)
    cpu.mem_write(OUT - 32, b'\xa5' * 96)
    cpu.mem_write(n.STACK - 128, b'\x6c' * 160)
    before = bytes(cpu.mem_read(0, 2**21))
    result = machine.call(name, *args)
    expected = bytearray(before)
    for start, end in FIELDS[name]:
        expected[OUT + start:OUT + end] = source[start:end]
    struct.pack_into('<I', expected, 0x8E970, head)
    if name != 'SsUtGetVabHdr':
        program_table, tone_table = head + 32, head + TONE_BASE
        struct.pack_into('<I', expected, 0x8E968, program_table)
        struct.pack_into('<I', expected, 0x8E978, tone_table)
        expected[0x8EA0D] = bank
        expected[0x8EA12] = program
        expected[0x8EA13] = struct.unpack_from('<I', before, (program_table & n.MASK) + program * 16 + 8)[0]
        for offset, value in ((-16, machine.saved[n.reg.UC_MIPS_REG_S0]),
                              (-12, machine.saved[n.reg.UC_MIPS_REG_S1]), (-8, n.END)):
            struct.pack_into('<I', expected, n.STACK + offset, value)
    after = bytes(cpu.mem_read(0, 2**21))
    different = [] if expected == after else [i for i, (a, b) in enumerate(zip(expected, after)) if a != b][:16]
    require(result == 0 and not different,
            'Original metadata/reference disagreement: ' + repr((name, bank, program, tone, result, different)))
    return sha(after)


def ready_queries(rows, ram, banks):
    bindings = ready_bindings(ram, banks)
    machine = Machine(rows, ram)
    digest, count, summaries = hashlib.sha256(), 0, []
    for binding in bindings:
        digest.update(bytes.fromhex(getter_case(machine, binding, 'SsUtGetVabHdr')))
        count += 1
        for program in binding['info']['programs']:
            native_id = program['native_id']
            digest.update(bytes.fromhex(getter_case(machine, binding, 'SsUtGetProgAtr', native_id)))
            count += 1
            for tone in program['tones']:
                digest.update(bytes.fromhex(getter_case(machine, binding, 'SsUtGetVagAtr', native_id, tone['index'])))
                count += 1
        summaries.append(dict(bank_id=binding['bank_id'], path=binding['path'],
                              header_address=hex(binding['header_address']), SPU_address=hex(binding['SPU_address']),
                              programs=binding['info']['declared_programs'], tones=binding['info']['declared_tones']))
    return dict(ready_banks=summaries, complete_RAM_comparisons=count, complete_RAM_bytes_per_comparison=2**21,
                result_chain_sha256=digest.hexdigest(), entered_original_functions=dict(machine.entries),
                original_output_stubs=0, source_RAM_digest=sha(ram),
                natural_method_entry_trace=False, SPU_transfer_completion_verified=False,
                audible_playback_verified=False)


def sequence_open(rows, ram, sequence, bank):
    """Observe original initializer return/trap; do not emulate BIOS or SPU I/O."""
    machine = Machine(rows, ram)
    work = machine.call('bgm_get_sequence_work')
    machine.call('func_800323A8', work, 2, 1)
    address = 0x140000
    require(len(sequence) < 0x10000, 'Oversized sequence-call fixture.')
    machine.cpu.mem_write(address - 32, b'\x2e' * 32 + sequence + b'\x53' * 32)
    try:
        result = machine.call('SsSeqOpen', address, bank)
        outcome = dict(returned=True, result=result)
    except n.unicorn.UcError as error:
        outcome = dict(returned=False, Unicorn_exception=str(error), last_PC=hex(machine.last_pc),
                       last_instruction=bytes(machine.cpu.mem_read(machine.last_pc, 4)).hex(),
                       architectural_PC=hex(machine.cpu.reg_read(n.reg.UC_MIPS_REG_PC)))
    require(bytes(machine.cpu.mem_read(address - 32, 32)) == b'\x2e' * 32
            and bytes(machine.cpu.mem_read(address, len(sequence))) == sequence
            and bytes(machine.cpu.mem_read(address + len(sequence), 32)) == b'\x53' * 32,
            'Original initializer changed sequence bytes or caller guards.')
    return dict(**outcome, entered_original_functions=dict(machine.entries), source_sequence_sha256=sha(sequence),
                original_output_stubs=0, natural_file_reachability_verified=False,
                BIOS_exception_handling_verified=False, audible_playback_verified=False)


def read_ram(path, expected_sha256, member=None, archive_sha256=None):
    """Read one exact RAM payload in memory; capture provenance is separate."""
    path = Path(path)
    if member is None:
        require(path.stat().st_size == 2**21, 'Use one complete 2 MiB RAM file.')
        ram = path.read_bytes()
    else:
        require(archive_sha256 is not None and path.stat().st_size <= 64 * 2**20,
                'Supply a bounded archive and its full hash.')
        with path.open('rb') as stream:
            digest = hashlib.sha256()
            for block in iter(lambda: stream.read(2**20), b''):
                digest.update(block)
            require(digest.hexdigest() == archive_sha256,
                    'RAM archive content differs.')
        ram, total, count = None, 0, 0
        with tarfile.open(path, 'r|*') as stream:
            for item in stream:
                total += item.size
                count += 1
                require(total <= 256 * 2**20 and count <= 4096, 'Unbounded RAM archive members.')
                if item.name == member:
                    require(ram is None and item.isfile() and item.size == 2**21,
                            'RAM member is repeated, not regular, or incomplete.')
                    with stream.extractfile(item) as payload:
                        ram = payload.read(2**21 + 1)
        require(ram is not None, 'Exact RAM member is absent.')
    require(len(ram) == 2**21 and sha(ram) == expected_sha256, 'Complete RAM payload hash differs.')
    return ram


def fault_controls(rows, ram, banks):
    bindings = ready_bindings(ram, banks)
    normal = next(b for b in bindings if any(p['native_id'] == 1 for p in b['info']['programs']))
    controls = [
        ('header_population_from_tone_count', 'SsUtGetVabHdr', 0x800331DC, 0x94620012, 0x94620014, 0),
        ('wrong_dense_program_byte', 'SsUtGetVagAtr', 0x80032204, 0x90430008, 0x90430009, 1),
        ('tone_sample_store_to_owner_field', 'SsUtGetVagAtr', 0x80033484, 0xA6030016, 0xA6030014, 0),
    ]
    observations = []
    for label, name, pc, before, after, program in controls:
        machine = Machine(rows, ram, (pc, before, after))
        detected = False
        try:
            getter_case(machine, normal, name, program, 0)
        except ValueError as error:
            require(str(error).startswith('Original metadata/reference disagreement:'),
                    'Fault control stopped for an unrelated reason: ' + str(error))
            detected = True
        require(detected and (pc & n.MASK) in machine.seen, 'Fault instruction was not executed and rejected.')
        observations.append(dict(name=label, PC=hex(pc), original_word=hex(before), changed_word=hex(after),
                                 instruction_executed=True, full_RAM_disagreement_detected=True))
    return observations
