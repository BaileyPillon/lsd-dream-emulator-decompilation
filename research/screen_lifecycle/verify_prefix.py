"""Compile and exercise shared-prefix callers up to original method entry.

Original callback bodies do NOT execute. This checks target/argument forwarding,
target layout and noncallable family-specific words, not gameplay or returns.
Use the existing isolated Unicorn 2.1.2 environment with the pinned build Ninja
on PATH; no disc, emulator clone or game-content extraction is created.
"""
import argparse
import gc
import gzip
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
from research.compiler.compare_function import elf_function
from tools.compile_c import run_stages
from tools.decomp_workbench import candidate_commands, new_output_directory
from tools import inspect_screen_prefix as prefix
from tools.verify_card_heap import backend_identity

CODE, OBJECT, STACK, END, MASK = 0x180000, 0x110000, 0x1E0000, 0x1F0000, 0x1FFFFFFF
CALLERS = dict(zip(('attach','detach','detach_all','iter_children','add_parent',
                   'remove_parent','clear_parents','iter_parents','notify','nop'), range(0x10,0x38,4)))
SEGMENTS = (0, 0x80000000, 0xA0000000)
sha = lambda data: hashlib.sha256(data).hexdigest()
require = prefix.require


def compile_callers(output):
    source = ROOT/'research/screen_lifecycle/prefix_consumer.c'
    obj, elf = output/'prefix.o', output/'prefix.elf'
    commands = candidate_commands('src/game/game_flow.c', source, obj)
    commands[1].append('-Werror')
    linker = output/'prefix.ld'
    linker.write_text('SECTIONS { .text '+hex(CODE)+' : SUBALIGN(4) { *(.text) } '
        '/DISCARD/ : { *(.reginfo) *(.MIPS.abiflags) *(.pdr) *(.gnu.attributes) } }\n', encoding='utf-8')
    with (output/'compiler.log').open('xb') as log:
        saved = os.dup(2)
        try:
            os.dup2(log.fileno(), 2)
            require(run_stages(commands) == b'', 'Unexpected compiler output.')
        finally:
            os.dup2(saved, 2); os.close(saved)
        subprocess.run([configure.CROSS+'ld', '-EL', '-nostdlib', '-T', str(linker),
            *(f'--defsym={function}={hex(address)}' for _field,function,address in prefix.SHARED.values()),
            '-o', str(elf), str(obj)], check=True, stdout=log, stderr=log)
    nm = subprocess.check_output([configure.CROSS+'nm','-S','--defined-only',str(elf)], text=True)
    code = subprocess.check_output([configure.CROSS+'objcopy','-O','binary','-j','.text',str(elf),'/dev/stdout'])
    rows = []
    for name in [*('screen_prefix_'+name for name in CALLERS), 'screen_prefix_typecheck']:
        matches = [line.split() for line in nm.splitlines() if len(line.split()) == 4 and line.split()[-1] == name]
        require(len(matches) == 1, 'Missing complete sized caller: '+name)
        address, size = int(matches[0][0],16), int(matches[0][1],16)
        body,_ = elf_function(elf.read_bytes(), name, address)
        require(len(body) == size and body == code[address-CODE:address-CODE+size], 'ELF/GNU caller extent mismatch.')
        rows.append(dict(function=name, address=address, bytes=size, sha256=sha(body)))
    ordered = sorted(rows, key=lambda row:row['address'])
    cursor = CODE
    for row in ordered:
        require(row['address'] == cursor, 'Unexpected caller extent gap.')
        cursor += row['bytes']
    require(cursor-CODE == len(code), 'Unowned code in analysis text.')
    rejected = []
    for field in ('ConstructAddress','CleanupAddress','OnNotifyAddress','InitializeAddress'):
        bad = output/('not-callable-'+field+'.c')
        bad.write_text('#include "game/game_flow.h"\nvoid invalid(game_flow_screen_t *s) { s->vtable->'+field+'(s); }\n', encoding='utf-8')
        bad_commands = candidate_commands('src/game/game_flow.c', bad, output/'must-not-build.o')
        with (output/('not-callable-'+field+'.log')).open('xb') as log:
            saved = os.dup(2)
            try:
                os.dup2(log.fileno(),2)
                try:
                    run_stages(bad_commands)
                except subprocess.CalledProcessError as error:
                    require(error.cmd[0] == configure.CC, 'Wrong failing compiler stage.')
                    rejected.append(field)
                else:
                    raise ValueError('A family-specific address compiled as callable.')
            finally:
                os.dup2(saved,2); os.close(saved)
        diagnostic = (output/('not-callable-'+field+'.log')).read_text(encoding='utf-8')
        require('called object' in diagnostic and 'function' in diagnostic, 'Noncallable rejection lacks its expected diagnostic.')
    return code, rows, commands, rejected


def callback_load(body, start, offset):
    """Select the callback load, excluding a same-offset stack restore."""
    words = [word for word, in struct.iter_unpack('<I',body)]
    registers = {word>>21&31 for word in words if word&0xFC1FFFFF == 0x0000F809}
    require(len(registers) == 1, 'Wrong-slot control needs one indirect target register.')
    loads = [start+i*4 for i,word in enumerate(words)
             if word>>26 == 0x23 and word&0xFFFF == offset and word>>16&31 in registers]
    require(len(loads) == 1, 'Wrong-slot control needs one reviewed callback load.')
    return loads[0]


def run_entry(executable, code, row, offset, table, object_index, table_index, fault=False):
    import unicorn
    from unicorn import mips_const as reg
    cpu = unicorn.Uc(unicorn.UC_ARCH_MIPS, unicorn.UC_MODE_MIPS32 | unicorn.UC_MODE_LITTLE_ENDIAN)
    cpu.mem_map(0,0x200000)
    load = struct.unpack_from('<I',executable,0x18)[0] & MASK
    cpu.mem_write(load,bytes(executable[0x800:]))
    cpu.mem_write(CODE,code)
    guarded = bytearray([0xC7])*0x100
    struct.pack_into('<I',guarded,0,(table & MASK)|SEGMENTS[table_index])
    cpu.mem_write(OBJECT,bytes(guarded))
    cpu.mem_write(STACK-0x400,b'\xCC'*0x500)
    receiver = OBJECT|SEGMENTS[object_index]
    other = (OBJECT+0x40)|SEGMENTS[(object_index+table_index)%3]
    argc = 3 if offset in (0x1C,0x2C) else 1 if offset in (0x18,0x28,0x34) else 2
    arguments = [receiver, (0x80000000 if table_index%2 else 0x7FFFFFFF) if offset == 0x30 else other, other+4]
    for i in range(4):
        cpu.reg_write(getattr(reg,'UC_MIPS_REG_A'+str(i)), arguments[i] if i < argc else 0xBA000000+i)
    cpu.reg_write(reg.UC_MIPS_REG_SP, STACK)
    cpu.reg_write(reg.UC_MIPS_REG_RA, END)
    expected = prefix.SHARED[offset][2]
    start, size = row['address'], row['bytes']
    fault_pc, fault_hits = None, 0
    if fault:
        body = code[start-CODE:start-CODE+size]
        fault_pc = callback_load(body,start,offset)
        word = int.from_bytes(cpu.mem_read(fault_pc,4),'little')
        replacement = 0x10 if offset == 0x34 else 0x34
        cpu.mem_write(fault_pc,struct.pack('<I',(word&0xFFFF0000)|replacement))
    observed, instructions = [], []
    def hook(machine,address,size,unused):
        nonlocal fault_hits
        pc = address&MASK
        fault_hits += int(pc == fault_pc)
        if not start <= pc < start+row['bytes']:
            observed.append(dict(pc=f'0x{address:08X}', arguments=[machine.reg_read(getattr(reg,'UC_MIPS_REG_A'+str(i))) for i in range(argc)]))
            machine.emu_stop()
            return
        instructions.append(pc)
    cpu.hook_add(unicorn.UC_HOOK_CODE,hook)
    cpu.emu_start(start,END,count=100)
    require(len(observed) == 1 and instructions, 'A compiled caller did not reach one target entry.')
    require(bytes(cpu.mem_read(OBJECT,len(guarded))) == bytes(guarded), 'Analysis caller changed the receiver or argument buffers.')
    require(bytes(cpu.mem_read(table&MASK,0x48)) == bytes(executable[0x800+(table&MASK)-load:0x800+(table&MASK)-load+0x48]), 'Original table bytes changed.')
    actual = observed[0]
    accepted = (int(actual['pc'],16)&MASK == expected&MASK and actual['arguments'] == arguments[:argc])
    return dict(caller=row['function'], receiver=hex(receiver), table=hex(table),
        table_pointer=hex((table&MASK)|SEGMENTS[table_index]), slot=hex(offset), expected_target=hex(expected),
        observed_entry=actual, expected_arguments=arguments[:argc], accepted=accepted,
        caller_instructions=len(instructions), changed_slot_load_hits=fault_hits,
        original_method_body_instructions_executed=0)


def verify(destination):
    require(sys.platform == 'linux' and Path.cwd().resolve() == ROOT, 'Run from the repository root in the supported WSL/Linux environment.')
    backend = backend_identity()
    inventory = prefix.collect()
    original = (ROOT/configure.ROM).read_bytes()
    catalogue = (ROOT/'research/dispatch/target-catalogue.json').read_bytes()
    audit = prefix.inspect(original,inventory,json.loads(catalogue))
    dependencies = [Path(__file__), ROOT/'research/screen_lifecycle/prefix_consumer.c',
        ROOT/'tools/inspect_screen_prefix.py', ROOT/'tools/inventory_vtables.py',
        ROOT/'tools/compile_c.py', ROOT/'tools/decomp_workbench.py',
        ROOT/'research/compiler/compare_function.py', ROOT/'tools/verify_card_heap.py',
        ROOT/configure.ROM, ROOT/configure.EXE,
        *(ROOT/name for name in inventory['source_sha256'])]
    before = {str(p):sha(p.read_bytes()) for p in dependencies}
    output = new_output_directory(destination)
    code, callers, commands, rejected = compile_callers(output)
    rows = {row['function']:row for row in callers}
    aggregate = hashlib.sha256(); count = 0; faults = []
    with (output/'entry-cases.jsonl.gz').open('xb') as raw, gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as journal:
        for name,table,a,b in itertools.product(CALLERS,prefix.TABLES.values(),range(3),range(3)):
            observed = run_entry(original,code,rows['screen_prefix_'+name],CALLERS[name],table['address'],a,b)
            require(observed['accepted'], 'Wrong original target entry or forwarded argument.')
            line = (json.dumps(observed,sort_keys=True,separators=(',',':'))+'\n').encode()
            journal.write(line); aggregate.update(line); count += 1
            if count%18 == 0: gc.collect()
    table = next(iter(prefix.TABLES.values()))['address']
    for name,offset in CALLERS.items():
        witness = run_entry(original,code,rows['screen_prefix_'+name],offset,table,0,0,True)
        require(not witness['accepted'] and witness['changed_slot_load_hits'] > 0, 'An executed wrong-slot control was accepted.')
        faults.append(witness)
    require({str(p):sha(p.read_bytes()) for p in dependencies} == before, 'A qualified source, original input or producer changed.')
    require(prefix.collect()['evidence_sha256'] == inventory['evidence_sha256'], 'Matching build evidence changed.')
    report = dict(schema_version=1,status='passed_common_screen_prefix_entry_check',
        target_layout_assertions=44, compiler_warnings_are_errors=True,
        analysis_callers=callers, compiler_commands=commands,
        noncallable_address_compile_rejections=rejected,
        original_table_entry_profiles=count, entry_journal_raw_sha256=aggregate.hexdigest(),
        wrong_slot_controls=faults, backend={key:backend[key] for key in
            ('package_version','library_api','loaded_library_sha256','binding_entry_sha256','binding_sources_sha256')},
        complete_prefix_audit=audit, source_sha256={str(p.relative_to(ROOT)):before[str(p)] for p in dependencies if p.is_relative_to(ROOT)},
        target_catalogue_sha256=sha(catalogue), original_method_body_instructions_executed=0,
        original_method_returns_verified=False, native_gameplay_runs=0, new_C_bytes=0,
        model_API_calls=0, whole_feature_groups_accepted=0,
        scope='Ten compiled shared-method consumers reach original main/chart targets with expected arguments. All receiver/table RAM-alias pairs use one defined third-argument alias pattern. Callee bodies, returns and natural screen/gameplay behavior do not execute.')
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:report[key] for key in ('status','target_layout_assertions','original_table_entry_profiles','original_method_body_instructions_executed')}))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args = parser.parse_args()
    try:
        verify(args.output)
        return 0
    except (OSError,ValueError,subprocess.CalledProcessError) as error:
        print(str(error),file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
