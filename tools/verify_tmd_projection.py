"""Execute LSD's original TMD projection/culling prepass with the native GTE.

The supplied camera/vertex state is a bounded fixture, not a natural scene.
The original MIPS helper, native GTE commands, complete outputs/state, memory
and saved ABI are compared with independent predictions. No function output
is stubbed. Texture assembly, rasterization and hardware timing are separate.
"""
import argparse
from collections import Counter, deque
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.gte_state_bridge import Cop2StateAdapter, NativeStateBridge
from tools.gte_state_model import GteState, command_word, require, signed, unsigned
from tools.inventory_model_packets import file_sha
from tools.psx_image import ORIGINAL_SHA1, executable_offset
from tools.verify_gte_state import IDENTITY, matrix
from tools.verify_model_packets import backend_identity

FUNCTION, FUNCTION_BYTES = 0x800195EC, 232
FUNCTION_SHA = '6e59588417cf13084d066a4c87d527c6f5f8e647092c956b07fdf34017fc8680'
RAM_BYTES, MASK = 0x200000, 0x1FFFFFFF
BUFFER, BUFFER_BYTES, STACK, STOP = 0x120000, 4096, 0x1B0800, 0x1FF000
CONTEXT, PACKET, INPUT, OUTPUT = BUFFER+0x100, BUFFER+0x400, BUFFER+0x800, BUFFER+0x900
CODE = 0x80001000
RTPT, NCLIP, AVSZ3 = 0x4A280030, 0x4B400006, 0x4B58002D
FAULTS = (
    dict(name='packet-length-source', address=0x800195FC, original=0x90A20014, replacement=0x90A20015),
    dict(name='fog-rejection-threshold', address=0x8001966C, original=0x28421000, replacement=0x28420800),
    dict(name='ordering-depth-shift', address=0x800196B0, original=0x00831807, replacement=0x00831804),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def writes_for(case):
    writes = matrix(0, case.get('matrix', IDENTITY))
    writes += [(0, 5+i, unsigned(value)) for i, value in enumerate(case.get('translation', (0, 0, 0)))]
    writes += [(0, 24, unsigned(case.get('ofx', 0))), (0, 25, unsigned(case.get('ofy', 0))),
        (0, 26, case.get('h', 256)), (0, 27, unsigned(case.get('dqa', 0))),
        (0, 28, unsigned(case.get('dqb', 0))), (0, 29, unsigned(case.get('zsf', 1365)))]
    for index, (x, y, z) in enumerate(case['vertices']):
        writes += [(1, index*2, (x & 0xFFFF) | (y & 0xFFFF) << 16), (1, index*2+1, z & 0xFFFF)]
    return writes


def fixture(case):
    data = bytearray((i*37+case.get('seed', 0)*19+13) & 255 for i in range(BUFFER_BYTES))
    struct.pack_into('<II', data, CONTEXT-BUFFER, (0x150000 | case.get('alias', 0)), unsigned(case.get('shift', 4)))
    data[CONTEXT-BUFFER+0x14] = case.get('length', 4)
    data[CONTEXT-BUFFER+0x15] = 0x2C
    return data


def expected(case):
    data, state, commands = fixture(case), GteState(), []
    state.request(True, writes_for(case))
    context = CONTEXT-BUFFER
    def word(offset, value):
        struct.pack_into('<I', data, context+offset, unsigned(value))
    word(0x78, 0)
    state.execute(RTPT)
    commands.append(RTPT)
    data[PACKET-BUFFER+3] = data[context+0x14]
    flag = state.cr[31] & 0x40000
    word(0x5C, flag)
    if flag:
        word(0x78, 1)
    state.execute(NCLIP)
    commands.append(NCLIP)
    area = state.dr[24]
    word(0x28, area)
    outcome = 'backface_or_degenerate'
    if signed(area) <= 0:
        return bytes(data), 1, state, commands, outcome
    depth = state.dr[8]
    word(0x24, depth)
    if signed(depth) >= 4096:
        return bytes(data), 1, state, commands, 'depth_cue_rejected'
    state.execute(AVSZ3)
    commands.append(AVSZ3)
    word(0x20, state.dr[7])
    for i in range(3):
        word(0x60+4*i, state.dr[12+i])
    base, shift = struct.unpack_from('<II', data, context)
    word(0x30, base+((signed(state.dr[7]) >> (shift & 31)) << 2))
    return bytes(data), 0, state, commands, 'projected_with_clip_flag' if flag else 'projected'


class Machine:
    def __init__(self, executable, bridge, fault=None, cpu_model=None):
        import unicorn
        from unicorn import mips_const as reg
        self.u, self.r, self.fault = unicorn, reg, fault
        self.cpu = unicorn.Uc(unicorn.UC_ARCH_MIPS, unicorn.UC_MODE_MIPS32 | unicorn.UC_MODE_LITTLE_ENDIAN)
        if cpu_model is not None:
            self.cpu.ctl_set_cpu_model(cpu_model)
        self.cpu.mem_map(0, RAM_BYTES, unicorn.UC_PROT_READ | unicorn.UC_PROT_EXEC)
        load, size = struct.unpack_from('<II', executable, 0x18)
        require(len(executable) == size+0x800 and (load & MASK)+size < BUFFER, 'Canonical image extent differs.')
        self.cpu.mem_write(load & MASK, executable[0x800:])
        at = executable_offset(executable, FUNCTION, FUNCTION_BYTES)
        require(sha(executable[at:at+FUNCTION_BYTES]) == FUNCTION_SHA, 'Original projection helper range differs.')
        if fault:
            at = fault['address'] & MASK
            require(struct.unpack('<I', self.cpu.mem_read(at, 4))[0] == fault['original'], 'Fault instruction differs.')
            self.cpu.mem_write(at, struct.pack('<I', fault['replacement']))
        self.cop2_words, self.transports, self.pending_temp = {}, {}, None
        self.lower_cop2(FUNCTION & MASK, FUNCTION_BYTES)
        self.cpu.mem_protect(BUFFER, BUFFER_BYTES, unicorn.UC_PROT_READ | unicorn.UC_PROT_WRITE)
        self.adapter = Cop2StateAdapter(bridge, self.read_word, self.stage_word_store)
        self.saved = [getattr(reg, 'UC_MIPS_REG_S'+str(i)) for i in range(8)]+[reg.UC_MIPS_REG_FP]
        self.steps, self.fault_hits, self.calls = 0, 0, 0
        self.history, self.label = deque(maxlen=8), 'unlabeled'
        self.cpu.hook_add(unicorn.UC_HOOK_CODE, self.instruction)

    def lower_cop2(self, start, length):
        # Unicorn's unsupported COP2 delay-slot opcodes raise CPU exceptions.
        # Preserve every guest word in a side map, execute its real semantics
        # in the checked GTE adapter, and let a NOP transport that side effect
        # through Unicorn's original integer branch/delay-slot execution.
        for at in range(start, start+length, 4):
            self.cop2_words.pop(at, None)
            self.transports.pop(at, None)
            word = struct.unpack('<I', self.cpu.mem_read(at, 4))[0]
            if word >> 26 in (0x12, 0x32, 0x3A):
                self.cop2_words[at] = word
                transport = 0
                if word >> 26 == 0x3A:
                    base = word >> 21 & 31
                    temp = 1 if base != 1 else 26
                    transport = 0xAC000000 | base << 21 | temp << 16 | (word & 0xFFFF)
                self.transports[at] = transport
                self.cpu.mem_write(at, struct.pack('<I', transport))

    def access(self, cpu, access, address, size, value, unused):
        address &= MASK
        spans = self.write_ranges if access == self.u.UC_MEM_WRITE else [(BUFFER, BUFFER+BUFFER_BYTES)]
        require(any(a <= address and address+size <= b for a, b in spans), 'Projection data access left guarded spans: '+hex(address))

    def guard_integer_memory(self, word):
        # Unicorn 2.1.4 memory hooks corrupt a branch-to-JR delay-slot tail
        # when its delay slot performs that hooked load/store. Check each
        # original effective address before execution instead. Whole-VM and
        # complete output-buffer comparisons still guard the resulting writes.
        op = word >> 26
        sizes = {0x20:1, 0x21:2, 0x23:4, 0x24:1, 0x25:2, 0x28:1, 0x29:2, 0x2B:4}
        if op < 0x20:
            return
        require(op in sizes, 'Unreviewed integer memory instruction: '+hex(word))
        size = sizes[op]
        base = self.cpu.reg_read(getattr(self.r, 'UC_MIPS_REG_'+str(word >> 21 & 31)))
        at = unsigned(base+signed(word, 16))
        require(at % size == 0, 'Unaligned integer memory transfer.')
        self.access(self.cpu, self.u.UC_MEM_WRITE if op in (0x28,0x29,0x2B) else self.u.UC_MEM_READ,
            at, size, 0, None)

    def guard_branch_delay(self, word, address):
        get = lambda number:self.cpu.reg_read(getattr(self.r, 'UC_MIPS_REG_'+str(number)))
        if Cop2StateAdapter.branch_target(word, address, get) is None:
            return
        physical = (address+4) & MASK
        require(self.lower <= physical and physical+4 <= self.upper,
                'Branch delay slot left its qualified function/program.')
        slot = self.cop2_words.get(physical, struct.unpack('<I',self.cpu.mem_read(physical,4))[0])
        op,base = slot >> 26,slot >> 21 & 31
        # Link-register address bases need a separately qualified after-link
        # value. Reject this unneeded encoding rather than checking stale GPRs.
        link = 31 if word >> 26 == 3 or word >> 26 == 1 and (word >> 16 & 31) in (16,17) else None
        if word >> 26 == 0 and word & 63 == 9:
            link = word >> 11 & 31
        require(not (op >= 0x20 and link not in (None,0) and base == link),
                'Unreviewed link-register memory base in delay slot.')
        if op in (0x32,0x3A):
            at = unsigned(get(base)+signed(slot,16))
            require(at % 4 == 0, 'Unaligned COP2 memory transfer.')
            self.access(self.cpu,self.u.UC_MEM_WRITE if op == 0x3A else self.u.UC_MEM_READ,
                at,4,0,None)
        elif op != 0x12:
            self.guard_integer_memory(slot)

    def read_word(self, address):
        self.access(self.cpu, self.u.UC_MEM_READ, address, 4, 0, None)
        return struct.unpack('<I', self.cpu.mem_read(address & MASK, 4))[0]

    def stage_word_store(self, address, value):
        self.access(self.cpu, self.u.UC_MEM_WRITE, address, 4, value, None)
        temp = self.current_transport >> 16 & 31
        register = getattr(self.r, 'UC_MIPS_REG_'+str(temp))
        require(self.pending_temp is None, 'Previous COP2 transport register was not restored.')
        self.pending_temp = (register, self.cpu.reg_read(register))
        self.cpu.reg_write(register, unsigned(value))

    def restore_temp(self):
        if self.pending_temp is not None:
            register, value = self.pending_temp
            self.cpu.reg_write(register, value)
            self.pending_temp = None

    def instruction(self, cpu, address, size, unused):
        self.restore_temp()
        physical = address & MASK
        require(self.lower <= physical and physical+size <= self.upper, 'Execution left its qualified function/program.')
        self.steps += 1
        if self.fault and physical == self.fault['address'] & MASK:
            self.fault_hits += 1
        transport = struct.unpack('<I', cpu.mem_read(physical, 4))[0]
        word = self.cop2_words.get(physical, transport)
        self.history.append((hex(address), hex(word), hex(cpu.reg_read(self.r.UC_MIPS_REG_RA))))
        require(physical not in self.cop2_words or transport == self.transports[physical], 'COP2 transport instruction changed.')
        self.current_transport = transport
        if word >> 26 == 0x12 and word >> 21 & 31 >= 16:
            self.command_words.append(word)
        if physical not in self.cop2_words:
            self.guard_integer_memory(word)
            self.guard_branch_delay(word,address)
        self.adapter.step(word, address,
            lambda number:cpu.reg_read(getattr(self.r, 'UC_MIPS_REG_'+str(number))),
            lambda number, value:cpu.reg_write(getattr(self.r, 'UC_MIPS_REG_'+str(number)), value),
            lambda value:None)  # The original integer branch executes the NOP transport.

    def immutable(self):
        memory = bytearray(self.cpu.mem_read(0, RAM_BYTES))
        memory[BUFFER:BUFFER+BUFFER_BYTES] = bytes(BUFFER_BYTES)
        return sha(memory)

    def invoke(self, initial, writes, expected_data, expected_return, expected_state, expected_commands,
               alias=0, registers=None, program=None, allow_mismatch=False):
        require(alias in (0, 0x80000000), 'Unsupported analysis alias.')
        cpu, reg = self.cpu, self.r
        if program is not None:
            body = struct.pack('<'+'I'*len(program), *program)
            require(len(body) <= 4096, 'Synthetic program exceeds its code page.')
            cpu.mem_write(CODE & MASK, body)
            self.lower_cop2(CODE & MASK, len(body))
            cpu.ctl_remove_cache(CODE, CODE+4096)
            start, self.lower, self.upper = CODE, CODE & MASK, (CODE & MASK)+len(body)
            self.write_ranges = [(OUTPUT, OUTPUT+128)]
        else:
            start, self.lower, self.upper = FUNCTION, FUNCTION & MASK, (FUNCTION & MASK)+FUNCTION_BYTES
            self.write_ranges = [(PACKET+3, PACKET+4)]+[(CONTEXT+i, CONTEXT+i+4)
                for i in (0x78, 0x5C, 0x28, 0x24, 0x20, 0x60, 0x64, 0x68, 0x30)]
        cpu.mem_write(BUFFER, bytes(initial))
        cpu.mem_write(STACK-0x800, b'\xc9'*4096)
        before_gte = self.adapter.reset(writes)
        initial_oracle = GteState().request(True, writes)
        require(all(before_gte[key] == initial_oracle[key] for key in ('cr','dr')), 'Initial GTE input transfer differs.')
        values = [0xAD000000+i*0x10203 for i in range(len(self.saved))]
        for register, value in zip(self.saved, values):
            cpu.reg_write(register, value)
        settings = {4:(PACKET if program is None else INPUT) | alias,
                    5:(CONTEXT if program is None else OUTPUT) | alias, 6:0xA6000006, 7:0xA7000007,
                    1:0xACDC0123, 26:0xCAFE0026,
                    24:STOP | alias, 28:0x8008A808, 29:STACK | alias, 31:STOP | alias}
        settings.update(registers or {})
        for number, value in settings.items():
            cpu.reg_write(getattr(reg, 'UC_MIPS_REG_'+str(number)), unsigned(value))
        before = self.immutable()
        self.command_words, steps_before = [], self.steps
        try:
            cpu.emu_start(start, STOP | alias, count=4096)
        except self.u.UcError as error:
            raise ValueError('MIPS execution failed in '+self.label+' at '+hex(cpu.reg_read(reg.UC_MIPS_REG_PC))
                +' after '+str(self.steps-steps_before)+' instructions; hook error: '
                +repr(getattr(cpu, '_hook_exception', None))+': '+repr(list(self.history))) from error
        self.restore_temp()
        require(cpu.reg_read(reg.UC_MIPS_REG_PC) == STOP | alias and cpu.reg_read(reg.UC_MIPS_REG_SP) == STACK | alias
                and cpu.reg_read(reg.UC_MIPS_REG_GP) == 0x8008A808 and cpu.reg_read(reg.UC_MIPS_REG_RA) == STOP | alias
                and cpu.reg_read(reg.UC_MIPS_REG_AT) == 0xACDC0123 and cpu.reg_read(reg.UC_MIPS_REG_K0) == 0xCAFE0026
                and [cpu.reg_read(r) for r in self.saved] == values, 'Projection/program return or saved-register ABI differs.')
        require(self.immutable() == before, 'Full VM code/input/stack outside compared buffer changed.')
        observed_gte = self.adapter.flush()
        actual = bytes(cpu.mem_read(BUFFER, BUFFER_BYTES))
        observed_return = cpu.reg_read(reg.UC_MIPS_REG_V0)
        equal = actual == expected_data and (expected_return is None or observed_return == expected_return)
        state_equal = observed_gte['cr'] == expected_state.control() and observed_gte['dr'] == expected_state.data()
        commands_equal = self.command_words == expected_commands
        if not allow_mismatch:
            require(equal and state_equal and commands_equal, 'Original projection/program disagrees with independent complete output/state.')
            require(observed_gte['native_commands']-before_gte['native_commands'] == expected_state.commands,
                    'Original command count differs.')
            require(observed_gte['native_data_writes']-before_gte['native_data_writes']
                    == expected_state.data_writes-initial_oracle['native_data_writes'], 'Original data transfer count differs.')
        self.calls += 1
        return dict(equal=equal, state_equal=state_equal, command_words_equal=commands_equal,
            clean_return=True, full_VM_and_ABI_guards_intact=True, output_sha256=sha(actual),
            return_value=observed_return, instructions=self.steps-steps_before,
            native_commands=observed_gte['native_commands']-before_gte['native_commands'])


def projection_cases():
    front = ((0,0,4096), (256,0,4096), (0,256,4096))
    for alias in (0, 0x80000000):
        for vertices in (front, (front[0],front[2],front[1]), (front[0],)*3):
            for fog in (0, 2047, 2048, 3072, 4095, 4096):
                for shift in (0, 4, 31, 36, -1):
                    yield dict(vertices=vertices, dqb=fog << 12, alias=alias, shift=shift,
                               length=4, seed=fog+shift)
        yield dict(vertices=((0,0,1), (8192,0,1), (0,8192,1)), translation=(0,0,65536), alias=alias)
    rng = random.Random(0x195EC)
    for index in range(256):
        yield dict(vertices=tuple(tuple(rng.randrange(-32768,32768) for _ in range(3)) for _ in range(3)),
            matrix=tuple(rng.randrange(-32768,32768) for _ in range(9)),
            translation=tuple(rng.randrange(-65536,65536) for _ in range(3)),
            ofx=rng.getrandbits(32), ofy=rng.getrandbits(32), h=rng.randrange(65536),
            dqa=rng.randrange(-32768,32768), dqb=rng.getrandbits(32), zsf=rng.randrange(-32768,32768),
            alias=0x80000000 if index & 1 else 0, shift=rng.getrandbits(32), length=index, seed=index)


def transfer_program(kind):
    words = []
    for i in range(32):
        if kind == 'memory':
            words.append(0xC8000000 | 4 << 21 | i << 16 | i*4)
        else:
            words += [0x8C000000 | 4 << 21 | 8 << 16 | i*4, 0,
                0x48000000 | (6 if kind == 'control' else 4) << 21 | 8 << 16 | i << 11]
    for i in range(32):
        if kind == 'memory':
            words.append(0xE8000000 | 5 << 21 | i << 16 | i*4)
        else:
            words += [0x48000000 | (2 if kind == 'control' else 0) << 21 | 8 << 16 | i << 11,
                      0, 0xAC000000 | 5 << 21 | 8 << 16 | i*4]
    return words+[0x03E00008, 0]


def synthetic_checks(machine):
    counts = Counter()
    for alias in (0, 0x80000000):
        for kind in ('memory', 'control', 'data'):
            machine.label = 'transfer '+kind+' '+hex(alias)
            raw = bytearray(b'\xa7'*BUFFER_BYTES)
            values = [unsigned(0xB3018000+i*0x13579) for i in range(32)]
            struct.pack_into('<32I', raw, INPUT-BUFFER, *values)
            expected_data = bytearray(raw)
            state = GteState()
            state.request(True, [])
            for i, value in enumerate(values):
                state.write(0 if kind == 'control' else 1, i, value)
            struct.pack_into('<32I', expected_data, OUTPUT-BUFFER, *(state.control() if kind == 'control' else state.data()))
            machine.invoke(raw, [], bytes(expected_data), None, state, [], alias=alias, program=transfer_program(kind))
            counts['all_register_transfer_programs'] += 1
    ops = {
        'cfc2': 0x48000000 | 2 << 21 | 9 << 16 | 24 << 11,
        'mfc2': 0x48000000 | 9 << 16 | 9 << 11,
        'ctc2': 0x48000000 | 6 << 21 | 9 << 16 | 24 << 11,
        'mtc2': 0x48000000 | 4 << 21 | 9 << 16 | 9 << 11,
        'lwc2': 0xC8000000 | 4 << 21 | 9 << 16,
        'swc2': 0xE8000000 | 5 << 21 | 9 << 16,
        'command': command_word(0x12),
        'integer-sw': 0xAC000000 | 5 << 21 | 9 << 16,
        'integer-lw': 0x8C000000 | 4 << 21 | 9 << 16,
    }
    for branch in ('beq','bne','blez','bgtz','bltz','bgez','j','jal','jr','jalr'):
        for taken in ((True,False) if branch not in ('j','jal','jr','jalr') else (True,)):
            for name, operation in ops.items():
                machine.label = 'delay '+branch+' '+str(taken)+' '+name
                raw = bytearray(b'\xa7'*BUFFER_BYTES)
                struct.pack_into('<I', raw, INPUT-BUFFER, 0x12348001)
                expected_data = bytearray(raw)
                writes = matrix(0)+[(0,24,0x12340000), (1,0,2 << 16 | 1), (1,1,3), (1,9,0x8000)]
                state = GteState()
                state.request(True, writes)
                a, b = 1, 2
                if branch == 'beq': a,b = (1,1) if taken else (1,2)
                if branch == 'bne': a,b = (1,2) if taken else (1,1)
                if branch == 'blez': a = 0 if taken else 1
                if branch == 'bgtz': a = 1 if taken else 0
                if branch == 'bltz': a = 0xFFFFFFFF if taken else 0
                if branch == 'bgez': a = 0 if taken else 0xFFFFFFFF
                if name == 'ctc2': state.write(0,24,a)
                if name == 'mtc2': state.write(1,9,a)
                if name == 'lwc2': state.write(1,9,0x12348001)
                if name == 'swc2': struct.pack_into('<I', expected_data, OUTPUT-BUFFER, state.data()[9])
                if name == 'integer-sw': struct.pack_into('<I', expected_data, OUTPUT-BUFFER, a)
                command_list = []
                if name == 'command': state.execute(operation); command_list=[operation]
                if branch in ('beq','bne'):
                    branch_word = (4 if branch == 'beq' else 5) << 26 | 9 << 21 | 10 << 16 | 4
                elif branch in ('blez','bgtz'):
                    branch_word = (6 if branch == 'blez' else 7) << 26 | 9 << 21 | 4
                elif branch in ('bltz','bgez'):
                    branch_word = 1 << 26 | 9 << 21 | (1 if branch == 'bgez' else 0) << 16 | 4
                elif branch in ('j','jal'):
                    branch_word = (2 if branch == 'j' else 3) << 26 | ((CODE+20) >> 2 & 0x3FFFFFF)
                else:
                    branch_word = 8 << 21 | (31 << 11 if branch == 'jalr' else 0) | (9 if branch == 'jalr' else 8)
                program = [branch_word, operation, 0x24021111,
                    2 << 26 | ((CODE+24) >> 2 & 0x3FFFFFF), 0, 0x24022222,
                    24 << 21 | 31 << 11 | 0x21, 0x03E00008, 0]
                machine.invoke(raw, writes, bytes(expected_data), 0x2222 if taken else 0x1111, state, command_list,
                    registers={8:CODE+20, 9:a, 10:b}, program=program)
                counts['integer_branch_delay_slot_programs'] += 1
                counts['ordinary_memory_delay_slot_programs' if name.startswith('integer-')
                       else 'COP2_delay_slot_programs'] += 1
    return dict(counts)


def guard_controls(machine):
    """Reject actual synthetic memory instructions before their guest effects."""
    controls = []
    fixtures = (
        ('outside-buffer-read', 0x8C820000, {4:BUFFER-4}, 'left guarded spans'),
        ('outside-write-slots', 0xACA90080, {}, 'left guarded spans'),
        ('unaligned-store', 0xACA90001, {}, 'Unaligned integer memory'),
        ('unreviewed-partial-load', 0x88820000, {}, 'Unreviewed integer memory'),
    )
    for delay in (False,True):
        for name, word, registers, message in fixtures:
            raw = bytes([0xA7])*BUFFER_BYTES
            state = GteState()
            state.request(True, [])
            machine.label = name+(' delay slot' if delay else '')
            program = [2 << 26 | ((CODE+12) >> 2 & 0x3FFFFFF),word,0,0x03E00008,0] if delay else [word,0x03E00008,0]
            try:
                machine.invoke(raw, [], raw, None, state, [], registers=registers,program=program)
            except ValueError as error:
                require(message in str(error), 'Memory guard control failed for an unrelated reason.')
            else:
                raise ValueError('Memory guard did not reject '+name)
            require(bytes(machine.cpu.mem_read(BUFFER,BUFFER_BYTES)) == raw,
                    'Rejected memory instruction changed the complete buffer.')
            controls.append(dict(name=name,instruction=hex(word),delay_slot=delay,guard_rejected=True,
                complete_buffer_unchanged=True))
    return controls


def verify(executable_path, bridge_path, runtime, destination):
    started = time.monotonic()
    require(not destination.exists() and destination.parent.is_dir(), 'Choose a fresh bounded output directory.')
    executable = executable_path.read_bytes()
    require(hashlib.sha1(executable).hexdigest() == ORIGINAL_SHA1, 'Use the canonical Japanese executable.')
    destination.mkdir()
    backend = backend_identity()
    bridge = NativeStateBridge(bridge_path, runtime, destination/'native-stderr.log')
    machine, outcomes, journal_hash = Machine(executable, bridge), Counter(), hashlib.sha256()
    try:
        synthetic = synthetic_checks(machine)
        memory_guard_controls = guard_controls(machine)
        synthetic_calls = machine.calls
        with (destination/'cases.jsonl').open('x', encoding='utf-8') as journal:
            for index, case in enumerate(projection_cases()):
                machine.label = 'original projection '+str(index)
                require(time.monotonic()-started < 900, 'Projection profile exceeded its 15-minute bound.')
                data, returned, state, commands, outcome = expected(case)
                observed = machine.invoke(fixture(case), writes_for(case), data, returned, state, commands, alias=case.get('alias',0))
                outcomes[outcome] += 1
                line = json.dumps(dict(case=index, outcome=outcome, **observed), separators=(',', ':'))+'\n'
                journal.write(line)
                journal_hash.update(line.encode())
        controls = []
        for fault in FAULTS:
            control = Machine(executable, bridge, fault=fault)
            case = dict(vertices=((0,0,4096),(256,0,4096),(0,256,4096)), dqb=3072 << 12, shift=4)
            data, returned, state, commands, outcome = expected(case)
            observed = control.invoke(fixture(case), writes_for(case), data, returned, state, commands, allow_mismatch=True)
            require(control.fault_hits > 0 and not observed['equal'] and observed['clean_return']
                    and observed['full_VM_and_ABI_guards_intact'] and observed['native_commands'] > 0,
                    'Executed clean-return original-code control was not detected.')
            controls.append(dict(**fault, instruction_executions=control.fault_hits, output_disagreement_detected=True,
                returned_with_ABI_and_full_VM_guards_intact=True, native_commands=observed['native_commands'], crash_count=0))
    finally:
        bridge.close()
    dependencies = ('tools/verify_tmd_projection.py','tools/verify_gte_state.py','tools/gte_state_model.py',
        'tools/gte_state_bridge.py','tools/nymashock_gte_state_bridge.cs','tools/verify_model_packets.py',
        'tools/psx_image.py','tools/inventory_model_packets.py','tools/disc_files.py','requirements-analysis.txt')
    report = dict(schema_version=1, status='original_tmd_projection_matches',
        generated_at=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic()-started,
        original_executable_sha1=ORIGINAL_SHA1, function=dict(address=hex(FUNCTION), bytes=FUNCTION_BYTES, sha256=FUNCTION_SHA),
        backend=backend, synthetic=synthetic, synthetic_MIPS_program_calls=synthetic_calls,
        original_projection_calls=machine.calls-synthetic_calls, outcomes=dict(outcomes),
        original_and_synthetic_MIPS_instructions=machine.steps, COP2_transfers=dict(machine.adapter.counts),
        data_memory_guards='Effective addresses checked in instruction hooks; native COP2 transfers checked in the adapter; complete buffer and full VM compared.',
        Unicorn_delay_slot_memory_hooks_avoided=True,
        controls=controls, journal=dict(file='cases.jsonl',sha256=journal_hash.hexdigest()),
        memory_guard_controls=memory_guard_controls,
        compiled_bridge_sha256=file_sha(bridge_path), source_sha256={name:file_sha(ROOT/name) for name in dependencies},
        complete_output_return_GTE_registers_ABI_and_full_VM_equal=True,
        original_executable_unmodified=True, COP2_lowered_to_NOP_or_guarded_SW_transport_only_in_analysis_VM=True,
        original_COP2_words_retained_and_native_semantics_executed=True,
        ordinary_MIPS_bytes_unchanged_except_private_fault_controls=True, no_function_output_stubs=True,
        fixture_camera_and_vertex_state_supplied=True, natural_scene_coverage_verified=False,
        normal_UV_material_packet_assembly_and_GPU_rasterization_verified=False,
        PS1_CPU_load_delays_and_hardware_timing_verified=False, whole_feature_groups_accepted=0,
        new_matching_C_bytes=0, scope='Original 232-byte TMD projection/culling/depth prepass with native GTE commands; full draw composition remains separate.')
    with (destination/'comparison.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    require(sum(path.stat().st_size for path in destination.iterdir()) < 4*1024**2, 'Projection output exceeds 4 MiB.')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--bridge', type=Path, required=True)
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = verify(args.executable, args.bridge, args.runtime, args.output)
        print(json.dumps({key:result[key] for key in ('status','original_projection_calls','synthetic','outcomes')}))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps(dict(status='invalid_tmd_projection_profile', error=str(error))), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
