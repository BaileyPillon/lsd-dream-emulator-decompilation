"""Execute original new-game/reset bodies against complete initialized buffers.

No output stubs or replacement game routines are used. This bounded native VM
profile is distinct from natural controller/ending reachability and PS1 hardware
timing. The matching compiler/build and isolated Unicorn 2.1.2 are required.
"""
import argparse
from collections import Counter
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import configure
from tools import new_game_state as model
from tools.compile_c import run_stages
from tools.decomp_workbench import candidate_commands, diagnostic_image, new_output_directory
from tools.export_npc_catalogue import nm_functions
from tools.inventory_vtables import parse_symbols
from tools.progress import build_manifest, check_build_current
from tools.verify_card_heap import backend_identity
from research.screen_lifecycle.verify import owned_record

MASK, OBJECT, AUX, STACK, END, GP = 0x1FFFFFFF, 0x110040, 0x120000, 0x1E0000, 0x1F0000, 0x8008A808
TABLE = 0x80087BDC
NAV_GLOBAL, COUNT_GLOBAL, MAGIC_GLOBAL = 0x8ACB4, 0x8ACB8, 0x8ABE0
SEGMENTS = (0, 0x80000000, 0xA0000000)
FUNCTIONS = ('dream_sys_init_new_game','init_nav_challenges_array','dream_sys_end_day',
    'dream_sys_clear_new_game','dream_sys_is_new_game','dream_sys_get_save_data','dream_sys_get_set_flag','memset')
CANONICAL = '282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f'
sha = lambda data: hashlib.sha256(data).hexdigest()
require = model.require


def cases():
    for segment,pattern in itertools.product(SEGMENTS,range(4)):
        base=dict(segment=segment,pattern=pattern)
        yield dict(base,kind='reset')
        for flashback,day in itertools.product((0,1,0x80000000,0xFFFFFFFF),(0,364)):
            yield dict(base,kind='end',mode=2,flashback=flashback,stored_day=day)
            for mode in (1,3,0xFFFFFFFF,0x80000000):
                yield dict(base,kind='end',mode=mode,flashback=flashback,stored_day=day)
            if flashback:
                yield dict(base,kind='end',mode=0,flashback=flashback,stored_day=day)
        for flag in (0,1,0x80000000,0xFFFFFFFF):
            yield dict(base,kind='clear',flag=flag)
            yield dict(base,kind='query',flag=flag)
        for size_alias in (None,*SEGMENTS):
            yield dict(base,kind='save_view',size_alias=size_alias)
        for old,value in itertools.product((0,0x7FFFFFFF,0xFFFFFFFF),(0,1,0x7FFFFFFF,0x80000000,0xFFFFFFFF)):
            yield dict(base,kind='flag',old=old,value=value)
    for segment,other_segment,pattern,alignment in itertools.product(SEGMENTS,SEGMENTS,range(4),range(4)):
        yield dict(kind='navigation',segment=segment,other_segment=other_segment,pattern=pattern,alignment=alignment)


def validate(case):
    require(type(case['segment']) is int and case['segment'] in SEGMENTS and type(case['pattern']) is int and 0 <= case['pattern'] < 4,
            'Unknown initialized pattern or RAM alias.')
    allowed={'reset':set(),'end':{'mode','flashback','stored_day'},'clear':{'flag'},'query':{'flag'},
             'save_view':{'size_alias'},'flag':{'old','value'},'navigation':{'other_segment','alignment'}}
    require(case.get('kind') in allowed and set(case)=={'kind','segment','pattern'}|allowed[case['kind']],
            'Incomplete or unknown reset profile.')
    if case['kind']=='end':
        require(case['flashback'] in (0,1,0x80000000,0xFFFFFFFF) and case['stored_day'] in (0,364)
                and case['mode'] in (0,1,2,3,0xFFFFFFFF,0x80000000)
                and (case['mode'] != 0 or case['flashback'] != 0),
                'Normal score/chart completion is outside the reset profile.')
    elif case['kind'] in ('clear','query'):
        require(case['flag'] in (0,1,0x80000000,0xFFFFFFFF),'Unknown new-game flag.')
    elif case['kind']=='save_view':
        require(case['size_alias'] in (None,*SEGMENTS),'Unknown optional size pointer alias.')
    elif case['kind']=='flag':
        require(case['old'] in (0,0x7FFFFFFF,0xFFFFFFFF) and case['value'] in (0,1,0x7FFFFFFF,0x80000000,0xFFFFFFFF),
                'Unknown flag exchange boundary.')
    elif case['kind']=='navigation':
        require(case['other_segment'] in SEGMENTS and type(case['alignment']) is int and case['alignment'] in range(4),
                'Unknown byte alignment or navigation counter alias.')


def pattern_bytes(length, pattern):
    return bytes(0 if pattern==0 else 255 if pattern==1 else (index*37+0x53)&255
                 if pattern==2 else hashlib.sha256(struct.pack('<I',index//32)).digest()[index%32]
                 for index in range(length))


def fixture(case, marker):
    validate(case)
    initial=bytearray(pattern_bytes(model.OBJECT_BYTES,case['pattern']))
    model.put(initial,0,TABLE)
    model.put(initial,model.IS_NEW_GAME,0xAABBCCDD)
    aux=bytearray(pattern_bytes(256,(case['pattern']+1)%4))
    globals_before=struct.pack('<II',0xA0100040,0x80100100)
    expected=bytes(initial);expected_aux=bytes(aux);expected_globals=globals_before
    args=[OBJECT|case['segment']];result=None
    kind=case['kind']
    if kind=='reset':
        function='dream_sys_init_new_game';expected=model.reset(initial,marker)
        expected_globals=struct.pack('<II',args[0]+model.NAV_FLAGS,args[0]+model.DYNAMIC_LINK_COUNT)
    elif kind=='end':
        model.put(initial,model.IS_FLASHBACK,case['flashback']);model.put(initial,model.STORED_DAY,case['stored_day'])
        expected,result=model.end_day(initial,case['mode'],marker)
        function='dream_sys_end_day';args.append(case['mode'])
        if case['mode']==2:expected_globals=struct.pack('<II',args[0]+model.NAV_FLAGS,args[0]+model.DYNAMIC_LINK_COUNT)
    elif kind in ('clear','query'):
        model.put(initial,model.IS_NEW_GAME,case['flag'])
        expected=model.clear_new_game(initial) if kind=='clear' else bytes(initial)
        result=case['flag'] if kind=='query' else None
        function='dream_sys_clear_new_game' if kind=='clear' else 'dream_sys_is_new_game'
    elif kind=='save_view':
        function='dream_sys_get_save_data';result=args[0]+model.SAVE_OFFSET
        args.append(0 if case['size_alias'] is None else (AUX+0x80)|case['size_alias'])
        if args[1]:model.put(aux,0x80,model.SAVE_BYTES)
        expected_aux=bytes(aux)
    elif kind=='flag':
        model.put(initial,model.FLAG,case['old'])
        expected,result=model.get_set_flag(initial,case['value'])
        function='dream_sys_get_set_flag';args.append(case['value'])
    else:
        function='init_nav_challenges_array'
        start=0x20+case['alignment']
        args=[(AUX+start)|case['segment'],(AUX+0x80)|case['other_segment']]
        expected_aux=model.nav_reset(aux,start,0x80)
        expected_globals=struct.pack('<II',*args)
    return dict(object=bytes(initial),aux=pattern_bytes(256,(case['pattern']+1)%4),
        globals=globals_before,expected_object=expected,expected_aux=expected_aux,
        expected_globals=expected_globals,function=function,args=args,returned=result)


def qualify(output):
    require(check_build_current(ROOT) is True,'Require a current complete matching build.')
    original=(ROOT/configure.ROM).read_bytes()
    require(sha(original)==CANONICAL and (ROOT/configure.EXE).read_bytes()==original,'Complete game images must be canonical.')
    objects=[Path(configure.BUILD_DIR)/(name+'.o') for name,_ in build_manifest()]
    with (output/'link.log').open('xb') as log:
        elf,image=diagnostic_image(output,Path(configure.LD_SCRIPT),objects,ROOT/configure.EXE,log)
    gnu_text=subprocess.check_output([configure.CROSS+'nm','-S','--defined-only',str(elf)],text=True)
    gnu=nm_functions(gnu_text)
    symbols=parse_symbols((ROOT/configure.MAP_FILE).read_text(encoding='utf-8'),
        [(ROOT/name).read_text(encoding='utf-8') for name in (configure.UNDEF_FUNCS,configure.UNDEF_SYMS,configure.SYMBOLS)])
    rows=[owned_record(original,elf.read_bytes(),gnu,name,symbols[name]) for name in FUNCTIONS]
    with (output/'GNU-symbols.txt.gz').open('xb') as stream:stream.write(gzip.compress(gnu_text.encode(),mtime=0))
    obj=output/'layout.o'
    commands=candidate_commands('src/dream/dream_sys.c',ROOT/'research/new_game_reset/layout.c',obj)
    commands[1].append('-Werror')
    with (output/'layout-compiler.log').open('xb') as log:
        saved=os.dup(2)
        try:
            os.dup2(log.fileno(),2);require(run_stages(commands)==b'','Unexpected target layout compiler output.')
        finally:
            os.dup2(saved,2);os.close(saved)
    return original,rows,image,commands


class Machine:
    def __init__(self,image,rows,case,marker,fault=None):
        import unicorn
        from unicorn import mips_const as reg
        self.unicorn,self.reg=unicorn,reg
        self.cpu=unicorn.Uc(unicorn.UC_ARCH_MIPS,unicorn.UC_MODE_MIPS32|unicorn.UC_MODE_LITTLE_ENDIAN)
        self.cpu.mem_map(0,0x200000)
        load=struct.unpack_from('<I',image,0x18)[0]&MASK
        self.cpu.mem_write(load,bytes(image[0x800:]))
        self.f=fixture(case,marker);self.rows={row['function']:row for row in rows}
        self.entries=Counter();self.trace=[];self.instructions=0;self.fault_hits=0;self.fault_pc=None;self.save_writes=set()
        self.entry_names={int(row['address'],16)&MASK:row['function'] for row in rows}
        self.ranges=[(int(row['address'],16)&MASK,(int(row['address'],16)&MASK)+row['bytes']) for row in rows]
        self.expected_code={row['function']:bytes(self.cpu.mem_read(int(row['address'],16)&MASK,row['bytes'])) for row in rows}
        self.cpu.mem_write(OBJECT-0x40,b'\xC7'*0x40+self.f['object']+b'\xC7'*0x40)
        self.cpu.mem_write(AUX,self.f['aux']);self.cpu.mem_write(NAV_GLOBAL,self.f['globals'])
        self.cpu.mem_write(STACK-0x400,b'\xCC'*0x500)
        self.allowed=((OBJECT,OBJECT+model.OBJECT_BYTES),(AUX,AUX+256),(NAV_GLOBAL,COUNT_GLOBAL+4),(STACK-0x300,STACK))
        if fault:
            name,old,new=fault
            row=self.rows[name];start=int(row['address'],16)&MASK
            words=list(struct.iter_unpack('<I',self.cpu.mem_read(start,row['bytes'])))
            matches=[start+i*4 for i,(word,) in enumerate(words) if word==old]
            require(len(matches)==1,'A fault needs one exact qualified original word.')
            self.fault_pc=matches[0];self.cpu.mem_write(self.fault_pc,struct.pack('<I',new))
            expected=bytearray(self.expected_code[name]);struct.pack_into('<I',expected,self.fault_pc-start,new)
            self.expected_code[name]=bytes(expected)
        self.code_hook=self.cpu.hook_add(unicorn.UC_HOOK_CODE,self.hook)
        self.write_hook=self.cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,self.write)

    def hook(self,cpu,address,size,unused):
        pc=address&MASK
        require(any(lo<=pc<hi for lo,hi in self.ranges),'Execution escaped complete owned original functions at '+hex(address))
        self.instructions+=1;self.fault_hits+=int(pc==self.fault_pc)
        if pc in self.entry_names:
            name=self.entry_names[pc];self.entries[name]+=1
            self.trace.append(dict(function=name,pc=hex(address),args=[cpu.reg_read(getattr(self.reg,'UC_MIPS_REG_A'+str(i))) for i in range(3)]))

    def write(self,cpu,access,address,size,value,unused):
        at=address&MASK
        require(any(lo<=at and at+size<=hi for lo,hi in self.allowed),
                'Original reset wrote outside its initialized object/aux/globals/stack context: '+hex(address))
        for byte in range(at,at+size):
            if OBJECT+model.SAVE_OFFSET<=byte<OBJECT+model.SAVE_OFFSET+model.SAVE_BYTES:
                self.save_writes.add(byte-OBJECT)

    def run(self):
        cpu,reg=self.cpu,self.reg
        saved=[0xAB000000+i*0x10203 for i in range(9)]
        regs=[getattr(reg,'UC_MIPS_REG_S'+str(i)) for i in range(8)]+[reg.UC_MIPS_REG_FP]
        for register,value in zip(regs,saved):cpu.reg_write(register,value)
        for register,value in ((reg.UC_MIPS_REG_SP,STACK),(reg.UC_MIPS_REG_GP,GP),(reg.UC_MIPS_REG_RA,END)):
            cpu.reg_write(register,value)
        for i in range(4):cpu.reg_write(getattr(reg,'UC_MIPS_REG_A'+str(i)),self.f['args'][i] if i<len(self.f['args']) else 0xBA000000+i)
        cpu.emu_start(int(self.rows[self.f['function']]['address'],16)&MASK,END,count=10000)
        require(cpu.reg_read(reg.UC_MIPS_REG_PC)==END and cpu.reg_read(reg.UC_MIPS_REG_SP)==STACK
            and cpu.reg_read(reg.UC_MIPS_REG_GP)==GP and cpu.reg_read(reg.UC_MIPS_REG_RA)==END
            and [cpu.reg_read(r) for r in regs]==saved,'Native return/stack/saved-register mismatch.')
        require(bytes(cpu.mem_read(STACK,0x100))==b'\xCC'*0x100 and bytes(cpu.mem_read(STACK-0x400,0x100))==b'\xCC'*0x100,'Stack guard changed.')
        buffers=dict(object=bytes(cpu.mem_read(OBJECT,model.OBJECT_BYTES)),aux=bytes(cpu.mem_read(AUX,256)),globals=bytes(cpu.mem_read(NAV_GLOBAL,8)))
        require(bytes(cpu.mem_read(OBJECT-0x40,0x40))==b'\xC7'*0x40 and bytes(cpu.mem_read(OBJECT+model.OBJECT_BYTES,0x40))==b'\xC7'*0x40,'Object guard changed.')
        for name,data in buffers.items():require(data==self.f['expected_'+name],'Complete initialized '+name+' buffer mismatch.')
        reset_call=self.f['function']=='dream_sys_init_new_game' or self.f['function']=='dream_sys_end_day' and self.f['args'][1]==2
        expected_writes=model.reset_write_offsets() if reset_call else set(range(0x180,0x184)) if self.f['function']=='dream_sys_end_day' else set()
        require(self.save_writes==expected_writes,'Original save-block write footprint differs.')
        value=cpu.reg_read(reg.UC_MIPS_REG_V0)
        require(self.f['returned'] is None or value==self.f['returned'],'Original return bit pattern differs.')
        expected_trace=[self.f['function']]
        if self.f['function']=='dream_sys_init_new_game' or self.f['function']=='dream_sys_end_day' and self.f['args'][1]==2:
            if self.f['function']=='dream_sys_end_day':expected_trace+=['dream_sys_init_new_game']
            expected_trace+=['init_nav_challenges_array','memset']
        require([row['function'] for row in self.trace]==expected_trace,'Original reset call graph differs.')
        for row in self.rows.values():
            start=int(row['address'],16)&MASK
            require(bytes(cpu.mem_read(start,row['bytes']))==self.expected_code[row['function']],'Qualified original/control code bytes changed.')
        return dict(returned=value,checked_return=self.f['returned'] is not None,
            full_buffers_sha256={name:sha(data) for name,data in buffers.items()},
            full_save_block_sha256=sha(buffers['object'][model.SAVE_OFFSET:model.SAVE_OFFSET+model.SAVE_BYTES]),
            original_entries=dict(self.entries),original_trace=self.trace,original_instructions=self.instructions,
            save_write_footprint_bytes=len(self.save_writes),save_write_footprint_sha256=sha(b''.join(struct.pack('<I',n) for n in sorted(self.save_writes))))

    def close(self):
        self.cpu.hook_del(self.code_hook);self.cpu.hook_del(self.write_hook)


def verify(destination):
    require(sys.platform=='linux' and Path.cwd().resolve()==ROOT,'Run from the repository root in supported WSL/Linux.')
    backend=backend_identity();output=new_output_directory(destination)
    original,rows,image,commands=qualify(output)
    (output/'qualified-functions.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    marker=struct.unpack_from('<I',original,0x800+MAGIC_GLOBAL-0x10000)[0]
    paths=[Path(__file__),ROOT/'tools/new_game_state.py',ROOT/'research/new_game_reset/layout.c',
        ROOT/'src/dream/dream_sys.c',ROOT/'src/dream/dream_sys.h',ROOT/'tools/compile_c.py',
        ROOT/'tools/decomp_workbench.py',ROOT/'research/compiler/compare_function.py',
        ROOT/'research/screen_lifecycle/verify.py',ROOT/'tools/verify_card_heap.py',
        ROOT/configure.ROM,ROOT/configure.EXE]
    before={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in paths}
    (output/'inputs-before.json').write_text(json.dumps(before,indent=2)+'\n',encoding='utf-8')
    rebuilt=(ROOT/configure.EXE).read_bytes()
    aggregate=hashlib.sha256();counts=Counter();groups=Counter();identities=set()
    with (output/'cases.jsonl.gz').open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as journal:
        for number,case in enumerate(cases(),1):
            identity=sha(json.dumps(case,sort_keys=True).encode());require(identity not in identities,'Duplicate initialized profile.');identities.add(identity)
            outcomes=[]
            for executable in (original,rebuilt):
                machine=Machine(executable,rows,case,marker)
                try:outcomes.append(machine.run())
                finally:machine.close()
            require(outcomes[0]==outcomes[1],'Original/rebuilt complete native outcomes differ.')
            counts.update(outcomes[0]['original_entries']);groups[case['kind']]+=1
            line=(json.dumps(dict(case=case,original_and_rebuilt=outcomes[0]),sort_keys=True,separators=(',',':'))+'\n').encode()
            journal.write(line);aggregate.update(line)
            if number%128==0:print(json.dumps(dict(completed=number)),flush=True)
            if number%16==0:gc.collect()
    require(set(counts)==set(FUNCTIONS),'Not every qualified complete original body executed.')
    controls=[]
    by_name={row['function']:row for row in rows}
    def select(name,predicate,new_immediate):
        row=by_name[name];at=0x800+int(row['address'],16)-0x80010000
        words=[word for word, in struct.iter_unpack('<I',original[at:at+row['bytes']])]
        candidates=[word for word in words if predicate(word)]
        require(len(candidates)==1,'Control must select one original semantic instruction.')
        word=candidates[0]
        return name,word,(word&0xFFFF0000)|new_immediate
    reserved=lambda w:w>>26 in (9,13) and w>>21&31==0 and w>>16&31==6 and w&0xFFFF==500
    faults=[('short_reserved_clear',select('dream_sys_init_new_game',reserved,499),dict(kind='reset',segment=0x80000000,pattern=1)),
        ('long_reserved_clear',select('dream_sys_init_new_game',reserved,501),dict(kind='reset',segment=0x80000000,pattern=1)),
        ('missing_navigation_first_byte',select('init_nav_challenges_array',lambda w:w>>26 in (9,13) and w>>21&31==0 and w&0xFFFF==29,28),
            dict(kind='navigation',segment=0x80000000,other_segment=0xA0000000,pattern=0,alignment=3)),
        ('misplaced_new_game_flag',select('dream_sys_end_day',lambda w:w>>26==43 and w&0xFFFF==0x878,0x874),
            dict(kind='end',segment=0x80000000,pattern=1,mode=2,flashback=0,stored_day=364))]
    for name,fault,case in faults:
        machine=Machine(original,rows,case,marker,fault)
        try:
            try:machine.run()
            except ValueError as error:
                require(machine.fault_hits>0 and 'Complete initialized' in str(error),
                        'A control must execute and fail the independent data oracle, not its code hash.')
                controls.append(dict(fault=name,function=fault[0],pc=hex(machine.fault_pc|0x80000000),
                    old_word=hex(fault[1]),changed_word=hex(fault[2]),executed_hits=machine.fault_hits,rejection=str(error)))
            else:raise ValueError('Executed reset fault was accepted: '+name)
        finally:machine.close()
    require({str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in paths}==before and check_build_current(ROOT) is True,'A source, original input or current matching build changed.')
    report=dict(schema_version=1,status='passed_bounded_original_new_game_reset',
        canonical_executable_sha256=CANONICAL,matching_complete_diagnostic_image=image,
        initialized_profiles=len(identities),original_and_rebuilt_executions=2*len(identities),groups=dict(groups),
        original_functions=rows,original_entry_counts_per_image=dict(counts),save_block_bytes=1792,
        reset_write_footprint_bytes=len(model.reset_write_offsets()),preserved_save_block_bytes=1792-len(model.reset_write_offsets()),
        copied_original_marker=hex(marker),target_layout_assertions=27,layout_compiler_commands=commands,
        journal_raw_sha256=aggregate.hexdigest(),source_sha256=before,
        executed_original_instruction_controls=controls,
        backend={key:backend[key] for key in ('package_version','library_api','loaded_library_sha256','binding_entry_sha256','binding_sources_sha256')},
        output_stubs=0,new_C_bytes=0,new_gameplay_features=0,whole_feature_groups_accepted=0,
        natural_controller_reset_reachability_verified=False,normal_nonflashback_score_chart_branch_executed=False,
        original_NPC_callbacks_accepted=0,model_API_calls=0,
        scope='Complete initialized objects/save blocks, guarded auxiliary buffers, globals, original scoped calls and ABI. Natural constructor/reset endings, score/chart completion, audiovisual/card outputs and hardware timing remain separate.')
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','initialized_profiles','original_and_rebuilt_executions','reset_write_footprint_bytes','preserved_save_block_bytes')}))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    try:verify(args.output);return 0
    except (OSError,ValueError,subprocess.CalledProcessError) as error:print(str(error),file=sys.stderr);return 2


if __name__=='__main__':sys.exit(main())
