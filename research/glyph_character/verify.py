"""Compile typed character callers and execute original glyph methods privately.

This checks character/UV buffers, byte conversion, virtual binding and ABI.
It does not resolve the getter's inherited unused local or accept rendering.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools import verify_native_ai as n
from tools.decomp_workbench import candidate_commands, configure
from tools.compile_c import run_stages
from tools.verify_scripted_ai import backend_identity
from research.compiler.compare_function import elf_function

FUNCTIONS = [
    dict(function='glyph_set_char',address='0x80041bdc',bytes=76,sha256='aa64ff97d3400f436d4dbed22f1687c3c6d68ab6f575284650f2cc5402c1323c'),
    dict(function='glyph_get_char',address='0x80041c28',bytes=20,sha256='5b6b699c5a61336764d09934ffb8183244e3da097dc542b0b1bb15357856b728'),
    dict(function='func_80041C4C',address='0x80041c4c',bytes=80,sha256='79f4b67714427f714cff33464a3ba3728d8c2b29709947b2eaef1f7133bc332e')]
CONSUMERS = ('glyph_character_read','glyph_character_write_read')
CODE, BASE, BYTES = 0x180000, 0x110000, 0xEC
TABLE_SHA256 = '858e5f11a66c2911f636f15bda8bc61ede508196c60443d3fb311bc899a57b50'
TEMPLATE_SHA256 = '12437a1a61b8d61a91a18278e4506bedaaf0eafc643b162f914a02ff738326b9'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def compile_consumers(output):
    source = output/'callers.c'
    source.write_text('#include "'+str(ROOT/'research/glyph_character/consumer.c')+'"\n'
                      '#include "'+str(ROOT/'research/glyph_character/abi_checks.h')+'"\n')
    obj,elf,binary = (output/name for name in ('callers.o','callers.elf','callers.bin'))
    commands = candidate_commands('src/menu/glyph.c',source,obj)
    import os
    with (output/'compile.log').open('xb') as log:
        saved = os.dup(2)
        os.dup2(log.fileno(),2)
        try:
            run_stages(commands)
        finally:
            os.dup2(saved,2)
            os.close(saved)
        script = output/'callers.ld'
        script.write_text('SECTIONS { .text '+hex(CODE)+' : { *(.text) } '
                          '/DISCARD/ : { *(.reginfo) *(.MIPS.abiflags) *(.pdr) *(.gnu.attributes) } }\n')
        subprocess.run([configure.CROSS+'ld','-EL','-nostdlib','-T',str(script),'-o',str(elf),str(obj)],
                       check=True,stdout=log,stderr=subprocess.STDOUT)
        subprocess.run([configure.CROSS+'objcopy','-O','binary','-j','.text',str(elf),str(binary)],check=True)
    symbols = subprocess.check_output([configure.CROSS+'nm','-S','--defined-only',str(elf)],text=True).splitlines()
    functions = []
    for name in CONSUMERS:
        rows = [line.split() for line in symbols if line.split()[-1:] == [name]]
        if len(rows) != 1 or len(rows[0]) != 4:
            raise ValueError('Require both complete sized caller symbols.')
        address,length = int(rows[0][0],16),int(rows[0][1],16)
        code,_ = elf_function(elf.read_bytes(),name,address)
        if len(code) != length or code != binary.read_bytes()[address-CODE:address-CODE+length]:
            raise ValueError('Complete caller bytes disagree with the linked text image.')
        functions.append(dict(function=name,address=hex(address),bytes=length,sha256=digest(code)))
    if sorted((int(row['address'],16),row['bytes']) for row in functions) != [(CODE,functions[0]['bytes']),
            (CODE+functions[0]['bytes'],functions[1]['bytes'])] or sum(row['bytes'] for row in functions) != len(binary.read_bytes()):
        raise ValueError('Require exactly the two contiguous complete analysis callers.')
    return binary.read_bytes(),functions


def fixture(case,table):
    data = bytearray((i*37+case['seed']*91+3) & 255 for i in range(BYTES))
    struct.pack_into('<I',data,0x20,(table & n.MASK) | case['segment'])
    data[0x20+0xA8] = case['character']
    return data


def expected(case,table,template):
    data = fixture(case,table)
    value = case['character']
    if case['kind'] == 'virtual-set-get':
        value = case['code'] & 255
        u,v = struct.unpack_from('<HH',template)
        data[0x20+0xA8] = value
        data[0x20+0x72] = (u+(value & 31)*8) & 255
        data[0x20+0x73] = (v+(value >> 5)*8) & 255
    return bytes(data),value


def cases():
    for kind in ('direct-getter','virtual-getter'):
        for character in range(256):
            for segment in (0,0x80000000,0xA0000000):
                for seed in (0,1):
                    yield dict(kind=kind,character=character,segment=segment,seed=seed,code=0)
    for code in tuple(range(256))+(-2147483648,-65537,-1,256,257,65535,65536,2147483647):
        for segment in (0,0x80000000,0xA0000000):
            for seed in (0,1):
                yield dict(kind='virtual-set-get',character=31+seed*127,segment=segment,seed=seed,code=code)


class Machine(n.Machine):
    def __init__(self,code,consumers,tracked=()):
        self.functions = FUNCTIONS+consumers
        self.entries = {int(row['address'],16) & n.MASK:row['function'] for row in self.functions}
        self.ranges = [(int(row['address'],16) & n.MASK,row['bytes']) for row in self.functions]
        self.counts = Counter()
        self.hits = Counter({address & n.MASK:0 for address in tracked})
        super().__init__(start=CODE,native_functions=FUNCTIONS)
        self.cpu.mem_write(CODE,code)
        self.starts = {'direct-getter':n.h.symbols['glyph_get_char'] & n.MASK,
                       'virtual-getter':int(consumers[0]['address'],16),
                       'virtual-set-get':int(consumers[1]['address'],16)}

    def hook(self,cpu,address,size,unused):
        address &= n.MASK
        if address in self.hits:
            self.hits[address] += 1
        if not any(start <= address < start+length for start,length in self.ranges):
            raise ValueError('Execution escaped the original methods and compiled callers.')
        name = self.entries.get(address)
        if name:
            self.counts[name] += 1
            self.trace.append(name)
            if name in ('glyph_set_char','glyph_get_char') and cpu.reg_read(n.reg.UC_MIPS_REG_A0) != self.pointer:
                raise ValueError('Character method received a different object pointer.')
            if name == 'glyph_set_char' and cpu.reg_read(n.reg.UC_MIPS_REG_A1) != self.case['code'] & 255:
                raise ValueError('The typed caller did not narrow its character argument.')

    def run(self,case,table):
        self.case,self.trace = case,[]
        self.hits = Counter({address:0 for address in self.hits})
        self.pointer = (BASE+0x20) | case['segment']
        cpu = self.cpu
        cpu.mem_write(BASE,bytes(fixture(case,table)))
        guard = bytes([0xC9])*0x500
        cpu.mem_write(n.STACK-0x400,guard)
        saved = [n.u32(0xAD000000+i*0x10203) for i in range(len(n.SAVED))]
        for register,value in zip(n.SAVED,saved):
            cpu.reg_write(register,value)
        for register,value in ((n.reg.UC_MIPS_REG_SP,n.STACK),(n.reg.UC_MIPS_REG_GP,0x8008A808),
            (n.reg.UC_MIPS_REG_RA,n.END),(n.reg.UC_MIPS_REG_A0,self.pointer),
            (n.reg.UC_MIPS_REG_A1,n.u32(case['code'])),(n.reg.UC_MIPS_REG_A2,0xBCAD1234),(n.reg.UC_MIPS_REG_A3,0xBCAD5678)):
            cpu.reg_write(register,value)
        cpu.emu_start(self.starts[case['kind']],n.END,count=1000)
        if (cpu.reg_read(n.reg.UC_MIPS_REG_PC) != n.END or cpu.reg_read(n.reg.UC_MIPS_REG_SP) != n.STACK
            or cpu.reg_read(n.reg.UC_MIPS_REG_GP) != 0x8008A808 or [cpu.reg_read(r) for r in n.SAVED] != saved
            or bytes(cpu.mem_read(n.STACK-0x400,0x100)) != guard[:0x100]
            or bytes(cpu.mem_read(n.STACK,0x100)) != guard[0x400:]):
            raise ValueError('Character methods violated guarded stack or saved ABI.')
        return bytes(cpu.mem_read(BASE,BYTES)),cpu.reg_read(n.reg.UC_MIPS_REG_V0)


def controls(code,consumers,table,template):
    records = []
    for function,opcode,immediate,changed_opcode,changed_immediate,kind,reason in (
        ('glyph_get_char',0x24,0xA8,0x20,0xA8,'direct-getter','signed_character_return'),
        ('glyph_set_char',0x28,0xA8,0x28,0xA9,'virtual-set-get','wrong_character_destination'),
        ('func_80041C4C',0x0C,0xFF,0x0C,0x7F,'virtual-set-get','wrong_character_row_mask')):
        record = next(row for row in FUNCTIONS if row['function'] == function)
        start = int(record['address'],16)
        original = n.h.target(start,record['bytes'])
        matches = [(i,word) for i,(word,) in enumerate(struct.iter_unpack('<I',original))
                   if word >> 26 == opcode and word & 0xffff == immediate]
        if len(matches) != 1:
            raise ValueError('Reviewed glyph control must identify exactly one word: '+reason)
        index,word = matches[0]
        address = start+index*4
        altered = (word & 0x03FF0000) | (changed_opcode << 26) | changed_immediate
        machine = Machine(code,consumers,(address,))
        machine.cpu.mem_write(address & n.MASK,struct.pack('<I',altered))
        for case in cases():
            if case['kind'] != kind:
                continue
            wanted = expected(case,table,template)
            actual = machine.run(case,table)
            if actual != wanted:
                hits = machine.hits[address & n.MASK]
                if not hits:
                    raise ValueError('A glyph fault was detected without executing its changed word.')
                records.append(dict(kind=reason,function=function,function_offset=index*4,fixture=case,
                    changed_instruction_hits=hits,wrong_buffer=actual[0] != wanted[0],wrong_return_word=actual[1] != wanted[1]))
                break
        else:
            raise ValueError('Glyph control was not detected: '+reason)
    return records


def verify(output):
    dependencies = n.evidence_dependencies('research/glyph_character/consumer.c','research/glyph_character/abi_checks.h',
        'research/glyph_character/verify.py','src/menu/glyph.c','src/menu/glyph.h',
        'tools/decomp_workbench.py','tools/verify_scripted_ai.py','research/compiler/compare_function.py','tools/gcc263/cc1')
    before = {path:digest(path.read_bytes()) for path in dependencies}
    n.initialize_backend(n.load_program(FUNCTIONS))
    backend = backend_identity()
    code,consumers = compile_consumers(output)
    table_address = n.h.symbols['g_GLYPH_VTABLE']
    table = n.h.target(table_address,0xCC)
    template_address = n.h.symbols['D_8006ED40']
    template = n.h.target(template_address,12)
    if (digest(table) != TABLE_SHA256 or digest(template) != TEMPLATE_SHA256
        or struct.unpack_from('<II',table,0xC4) != (n.h.symbols['glyph_set_char'],n.h.symbols['glyph_get_char'])):
        raise ValueError('Original character bindings or region template changed.')
    machine = Machine(code,consumers)
    groups,identities = Counter(),set()
    snapshots = hashlib.sha256()
    for case in cases():
        identity = digest(bytes(fixture(case,table_address))+struct.pack('<II',n.u32(case['code']),machine.starts[case['kind']]))
        if identity in identities:
            raise ValueError('Repeated initialized character/API input requires classification.')
        identities.add(identity)
        actual = machine.run(case,table_address)
        if actual != expected(case,table_address,template):
            raise ValueError('Original glyph methods disagree with the byte/UV model: '+repr(case))
        wanted_trace = {'direct-getter':['glyph_get_char'],'virtual-getter':['glyph_character_read','glyph_get_char'],
            'virtual-set-get':['glyph_character_write_read','glyph_set_char','func_80041C4C','glyph_get_char']}[case['kind']]
        if machine.trace != wanted_trace:
            raise ValueError('Original character call order differs.')
        groups[case['kind']] += 1
        snapshots.update(bytes.fromhex(identity)+actual[0]+struct.pack('<I',actual[1]))
    faults = controls(code,consumers,table_address,template)
    for row in FUNCTIONS+consumers:
        address = int(row['address'],16)
        if digest(bytes(machine.cpu.mem_read(address & n.MASK,row['bytes']))) != row['sha256']:
            raise ValueError('Positive method/caller bytes changed during verification.')
    if (bytes(machine.cpu.mem_read(table_address & n.MASK,0xCC)) != table
        or bytes(machine.cpu.mem_read(template_address & n.MASK,12)) != template
        or backend_identity() != backend or n.load_program(FUNCTIONS).ROM != n.h.ROM
        or any(digest(path.read_bytes()) != value for path,value in before.items())):
        raise ValueError('An original input, source, backend or canonical build changed.')
    report = dict(status='passed_bounded_original_glyph_character_API',native_cases=len(identities),case_groups=dict(groups),
        original_functions=FUNCTIONS,compiled_analysis_callers=consumers,actual_entry_counts=dict(machine.counts),
        dependency_output_contracts=[],target_ABI_assertions=8,original_virtual_slots={'setter':'0xC4','getter':'0xC8'},
        original_vtable_sha256=TABLE_SHA256,original_region_template_sha256=TEMPLATE_SHA256,
        input_and_output_sha256=snapshots.hexdigest(),negative_controls=faults,backend_identity=backend,
        original_and_current_build_equal=True,canonical_executable_sha256=digest(n.h.ROM),
        producer_dependencies=[dict(path=path.relative_to(ROOT).as_posix(),sha256=value) for path,value in before.items()],
        new_game_function_C_bytes=0,original_behavior_modified=False,model_api_calls=0,whole_feature_groups_accepted=0,
        scope='Compiled C callers exercise the original getter, setter and region helper with no function-output stubs. '
              'Full guarded glyph buffers, character/UV bytes, return words, method order and saved ABI are compared. '
              'This does not explain the getter padding, render pixels, establish natural UI histories or verify PS1 CPU timing.')
    with (output/'report.json').open('x') as stream:
        json.dump(report,stream,indent=2)
        stream.write('\n')
    print(json.dumps(dict(report=str(output/'report.json'),native_cases=len(identities),negative_controls=len(faults))),flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path,help='Fresh private directory inside .decomp-lab.')
    args = parser.parse_args(argv)
    try:
        output = (ROOT/args.output).resolve()
        lab = (ROOT/'.decomp-lab').resolve()
        if output == lab or not output.is_relative_to(lab) or output.exists():
            raise ValueError('Choose a fresh private output directory; prior evidence is preserved.')
        if sys.platform == 'win32':
            raise ValueError('Use the matching WSL/Linux compiler and optional analysis dependencies.')
        output.mkdir(parents=True,exist_ok=False)
        verify(output)
        return 0
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        print('[!] '+str(error),file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
