"""Check typed callback installation and original CD tick guard paths.

Uses owned initialized objects, complete canonical function ranges and compiled
C callers. No VSync, disc I/O, original display loop or natural timing is run.
"""
import argparse
from collections import Counter
import hashlib
import importlib
import itertools
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import configure
from research.compiler.compare_function import elf_function,CANONICAL_SHA256
from research.file_driver.verify import compiler_stages
from tools.decomp_workbench import candidate_commands,candidate_link_command
from tools.verify_actor_children import build_inputs,output_directory,require_ninja
from tools.progress import build_manifest,check_build_current
from tools.replay_cold_start_headless import require

FUNCTIONS=('display_set_vsync_callback','display_set_sync_mode','display_do_vsync_internal',
           'cd_file_driver_tick','memory_is_locked')
CALLERS=('install_cd_word_callback','invoke_display_word_callback','clear_display_word_callback')
GLOBALS=('g_CdLocked','g_MEMORY_LOCKED','g_CdFrameMode','g_CdReadPhase','g_CdCallbackActive')
DEPENDENCIES=('research/display_callback/verify.py','research/display_callback/consumer.c',
 'research/display_callback/abi_checks.h','src/graphics/display.h','src/graphics/display.c',
 'src/file/cd_file_driver.c','research/compiler/compare_function.py','research/file_driver/verify.py',
 'tools/decomp_workbench.py','tools/verify_actor_children.py','tools/compile_c.py','tools/progress.py',
 'configure.py','requirements.txt','requirements-card-heap.txt')
CODE,BASE,OBJECT,TABLE_BASE,TABLE=0x180000,0x110000,0x110020,0x112000,0x112020
STACK,END,MASK,GP=0x1E0000,0x1F0000,0x1FFFFFFF,0x8008A808
WORDS=(0,1,0x7FFFFFFF,0x80000000,0xFFFFFFFF)
sha=lambda data:hashlib.sha256(data).hexdigest()

def backend():
 import unicorn
 module=importlib.import_module('unicorn.unicorn_py3.unicorn')
 require(unicorn.__version__=='2.1.2','Use the isolated requirements-card-heap.txt environment.')
 return dict(version=unicorn.__version__,library_sha256=sha(Path(module.uclib._name).read_bytes()),
             binding_sha256=sha(Path(module.__file__).read_bytes()))

def qualified_original(output,rom):
 objects=[Path(configure.BUILD_DIR)/(name+'.o') for name,_ in build_manifest()]
 require(len(objects)==306 and all(p.is_file() for p in objects),'Require all canonical objects.')
 flags=[flag for flag in configure.LD_FLAGS if flag!='-s']
 require(len(flags)+1==len(configure.LD_FLAGS),'Require the normal single strip flag.')
 elf,binary=output/'canonical-symbols.elf',output/'canonical-symbols.exe'
 with (output/'link.log').open('xb') as log:
  subprocess.run(candidate_link_command(elf,output/'canonical-symbols.map',Path(configure.LD_SCRIPT),objects,flags),stdout=log,stderr=log,check=True)
  subprocess.run([configure.CROSS+'objcopy','-O','binary',str(elf),str(binary)],stdout=log,stderr=log,check=True)
 require(binary.read_bytes()==rom,'The complete symbolic executable differs from original.')
 rows=[l.split() for l in subprocess.check_output([configure.CROSS+'nm','-S','--defined-only',str(elf)],text=True).splitlines()]
 symbols={}
 for name in (*FUNCTIONS,*GLOBALS,'g_DISPLAY_VTABLE'):
  matches=[r for r in rows if r[-1]==name]
  require(len(matches)==1,'Missing/ambiguous original symbol: '+name)
  symbols[name]=int(matches[0][0],16)
 records=[]
 for name in FUNCTIONS:
  row=next(r for r in rows if r[-1]==name);require(len(row)==4 and row[2] in ('T','t'),'Require an actual GNU-sized function.')
  pc,size=int(row[0],16),int(row[1],16);code,_=elf_function(elf.read_bytes(),name,pc)
  at=pc-0x80010000+0x800
  require(size==len(code) and code==rom[at:at+size],'Canonical complete ELF/GNU function extent differs: '+name)
  records.append(dict(function=name,address=hex(pc),bytes=size,sha256=sha(code)))
 return symbols,records,dict(complete_canonical_image_equal=True,independent_ELF_GNU_extents_equal=True,
  objects=306,elf_sha256=sha(elf.read_bytes()),executable_sha256=sha(rom))

def compile_callers(output,symbols):
 source=output/'callers.c';source.write_text('#include "'+str(ROOT/'research/display_callback/consumer.c')+'"\n#include "'+str(ROOT/'research/display_callback/abi_checks.h')+'"\n')
 obj,elf,binary=output/'callers.o',output/'callers.elf',output/'callers.bin'
 commands=candidate_commands('src/graphics/display.c',source,obj);commands[1].append('-Werror')
 with (output/'compiler.log').open('xb') as log:
  status,error=compiler_stages(commands,log);require(status==0,'Typed C callers failed: '+error)
  ld=output/'callers.ld';ld.write_text('PROVIDE(cd_file_driver_tick = '+hex(symbols['cd_file_driver_tick'])+');\nSECTIONS { .text '+hex(CODE)+' : SUBALIGN(4) { *(.text) } /DISCARD/ : { *(.reginfo) *(.MIPS.abiflags) *(.pdr) *(.gnu.attributes) } }\n')
  subprocess.run([configure.CROSS+'ld','-EL','-nostdlib','-T',str(ld),'-o',str(elf),str(obj)],stdout=log,stderr=log,check=True)
  subprocess.run([configure.CROSS+'objcopy','-O','binary','--only-section=.text',str(elf),str(binary)],stdout=log,stderr=log,check=True)
 rows=[r.split() for r in subprocess.check_output([configure.CROSS+'nm','-S','--defined-only',str(elf)],text=True).splitlines()]
 code=binary.read_bytes();records=[]
 for name in CALLERS:
  matches=[r for r in rows if r[-1]==name];require(len(matches)==1 and len(matches[0])==4,'Missing complete C caller: '+name)
  row=matches[0];pc,size=int(row[0],16),int(row[1],16);body,_=elf_function(elf.read_bytes(),name,pc)
  require(len(body)==size and body==code[pc-CODE:pc-CODE+size],'Owned caller extent differs.')
  records.append(dict(function=name,address=hex(pc),bytes=size,sha256=sha(body)))
 cursor=CODE
 for row in sorted(records,key=lambda r:int(r['address'],16)):
  require(int(row['address'],16)==cursor,'Unexpected helper or gap in owned C callers.');cursor+=row['bytes']
 require(cursor-CODE==len(code),'Additional code outside owned callers.')
 return code,records,commands

def static_original_flow(rom,symbols,functions):
 row=next(r for r in functions if r['function']=='display_do_vsync_internal');pc=int(row['address'],16)
 at=pc-0x80010000+0x800;words=[w for (w,) in struct.iter_unpack('<I',rom[at:at+row['bytes']])]
 matches=[i for i,w in enumerate(words) if w==0x8E020030]
 require(len(matches)==1,'Require the original owner-relative callback field load.')
 index=matches[0]
 require(words[index+4:index+7]==[0x0040F809,0,0x8E020000],
  'The original callback JALR/delay or immediate overwrite of its result differs.')
 table=symbols['g_DISPLAY_VTABLE']-0x80010000+0x800
 require(struct.unpack_from('<I',rom,table+0x84)[0]==symbols['display_set_vsync_callback'],'Original setter binding differs.')
 return dict(callback_field_load=hex(pc+4*index),callback_field_offset='0x30',setter_slot='0x84',
  original_callback_call=hex(pc+4*(index+4)),return_word_overwritten_before_use=True,static_only=True)

class Machine:
 def __init__(self,rom,symbols,functions,code,callers,fault=None):
  import unicorn as u
  from unicorn import mips_const as r
  self.u,self.r,self.symbols,self.rom=u,r,symbols,rom
  self.cpu=u.Uc(u.UC_ARCH_MIPS,u.UC_MODE_MIPS32|u.UC_MODE_LITTLE_ENDIAN);self.cpu.mem_map(0,0x200000)
  self.cpu.mem_write(0x10000,rom[0x800:]);self.cpu.mem_write(CODE,code)
  self.records=functions+callers;self.starts={x['function']:int(x['address'],16)&MASK for x in self.records}
  self.ranges=[(self.starts[x['function']],self.starts[x['function']]+x['bytes']) for x in self.records]
  self.counts=Counter();self.fault=fault;self.fault_hits=0
  self.saved=[getattr(r,'UC_MIPS_REG_S'+str(i)) for i in range(8)]+[r.UC_MIPS_REG_FP]
  if fault:
   pc,old,new=fault;require(struct.unpack('<I',self.cpu.mem_read(pc&MASK,4))[0]==old,'Fault original word differs.')
   self.cpu.mem_write(pc&MASK,struct.pack('<I',new))
  self.cpu.hook_add(u.UC_HOOK_CODE,self.hook);self.cpu.hook_add(u.UC_HOOK_MEM_WRITE,self.write_hook)
 def hook(self,cpu,address,size,unused):
  pc=address&MASK
  if self.fault and pc==(self.fault[0]&MASK):self.fault_hits+=1
  require(any(a<=pc<b for a,b in self.ranges),'Execution escaped the original/owned closure.')
  for name,start in self.starts.items():
   if start==pc:self.trace.append(name);self.counts[name]+=1
  if pc==self.starts['display_set_vsync_callback']:
   self.setter_args.append((cpu.reg_read(self.r.UC_MIPS_REG_A0),cpu.reg_read(self.r.UC_MIPS_REG_A1)))
 def write_hook(self,cpu,access,address,size,value,unused):
  pc=address&MASK
  require(size==4 and (STACK-0x200<=pc<STACK or pc==OBJECT+0x30),'A native write escaped the owned stack/callback word.')
 def invoke(self,name):
  cpu,r=self.cpu,self.r;self.trace=[];self.setter_args=[]
  cpu.mem_write(STACK-0x300,b'\xC9'*0x380)
  saved=[0xAD000000+i*0x10203 for i in range(len(self.saved))]
  for reg,value in zip(self.saved,saved):cpu.reg_write(reg,value)
  for reg,value in ((r.UC_MIPS_REG_SP,STACK),(r.UC_MIPS_REG_GP,GP),(r.UC_MIPS_REG_RA,END),
   (r.UC_MIPS_REG_V0,0x12345678),(r.UC_MIPS_REG_A0,OBJECT|0x80000000)):cpu.reg_write(reg,value)
  cpu.emu_start(self.starts[name],END,count=2000)
  require(cpu.reg_read(r.UC_MIPS_REG_PC)==END and cpu.reg_read(r.UC_MIPS_REG_SP)==STACK
   and cpu.reg_read(r.UC_MIPS_REG_RA)==END and cpu.reg_read(r.UC_MIPS_REG_GP)==GP
   and [cpu.reg_read(reg) for reg in self.saved]==saved,'Preserved native ABI or return failed.')
  require(bytes(cpu.mem_read(STACK-0x300,0x100))==b'\xC9'*0x100 and bytes(cpu.mem_read(STACK,0x80))==b'\xC9'*0x80,'Native stack guards changed.')
  return cpu.reg_read(r.UC_MIPS_REG_V0)
 def run(self,locked,memory_locked):
  cpu,s=self.cpu,self.symbols
  original=bytearray((37*i+91)&255 for i in range(0x20+0x34+0x20))
  struct.pack_into('<I',original,0x20,TABLE|0x80000000);struct.pack_into('<I',original,0x50,s['memory_is_locked'])
  cpu.mem_write(BASE,bytes(original));at=s['g_DISPLAY_VTABLE']-0x80010000+0x800
  table=b'\xA7'*0x20+self.rom[at:at+0x88]+b'\xD3'*0x20;cpu.mem_write(TABLE_BASE,table)
  values=(locked,memory_locked,0,0,0)
  for name,value in zip(GLOBALS,values):cpu.mem_write(s[name]&MASK,struct.pack('<I',value))
  self.invoke(CALLERS[0]);expected=bytearray(original);struct.pack_into('<I',expected,0x50,s['cd_file_driver_tick'])
  require(bytes(cpu.mem_read(BASE,len(original)))==bytes(expected),'Callback installation or object guards differ.')
  require(self.setter_args==[(OBJECT|0x80000000,s['cd_file_driver_tick'])] and self.trace==[CALLERS[0],'display_set_vsync_callback'],'Setter pointer arguments/order differ.')
  result=self.invoke(CALLERS[1]);trace=[CALLERS[1],'cd_file_driver_tick']+(['memory_is_locked'] if locked==0 else [])
  require(result==0 and self.trace==trace,'Typed callback status word or original tick guard differs.')
  require(bytes(cpu.mem_read(BASE,len(original)))==bytes(expected),'Callback unexpectedly changed the display object.')
  self.invoke(CALLERS[2]);struct.pack_into('<I',expected,0x50,0)
  require(bytes(cpu.mem_read(BASE,len(original)))==bytes(expected),'Callback clearing or object guards differ.')
  require(self.setter_args==[(OBJECT|0x80000000,0)] and self.trace==[CALLERS[2],'display_set_vsync_callback'],'Clear callback arguments/order differ.')
  require(bytes(cpu.mem_read(TABLE_BASE,len(table)))==table,'Original copied display table changed.')
  require([struct.unpack('<I',cpu.mem_read(s[n]&MASK,4))[0] for n in GLOBALS]==list(values),'Native CD guard globals changed.')
  return dict(locked=locked,memory_locked=memory_locked,callback_result=result,object_table_globals_and_ABI_equal=True)

def compiler_controls(output):
 original=(ROOT/'src/graphics/display.h').read_text();results=[]
 changes=(('void_callback','typedef s32 (*display_vsync_callback_t)(void);','typedef void (*display_vsync_callback_t)(void);','void'),
  ('callback_requires_argument','typedef s32 (*display_vsync_callback_t)(void);','typedef s32 (*display_vsync_callback_t)(s32);','arguments'),
  ('void_setter_parameter','void (*display_set_vsync_callback)(display_t *, display_vsync_callback_t Callback);',
   'void (*display_set_vsync_callback)(display_t *, void (*Callback)(void));','incompatible'))
 for name,old,new,diagnostic in changes:
  folder=output/name;(folder/'graphics').mkdir(parents=True);require(original.count(old)==1,'Ambiguous callback compiler control.')
  (folder/'graphics/display.h').write_text(original.replace(old,new,1));source=folder/'callers.c'
  source.write_text('#include "'+str(ROOT/'research/display_callback/consumer.c')+'"\n#include "'+str(ROOT/'research/display_callback/abi_checks.h')+'"\n')
  commands=candidate_commands('src/graphics/display.c',source,folder/'callers.o');commands[0].insert(1,'-I'+str(folder));commands[1].append('-Werror')
  with (folder/'compiler.log').open('xb') as log:status,error=compiler_stages(commands,log)
  require(status!=0 and diagnostic in error,'Incorrect callback interface was not specifically rejected: '+name)
  results.append(dict(name=name,rejected=True,diagnostic_contains=diagnostic,diagnostic_sha256=sha(error.encode())))
 return results

def negative_controls(rom,symbols,functions,code,callers):
 specs=[];row=next(r for r in functions if r['function']=='display_set_vsync_callback');pc=int(row['address'],16)
 at=pc-0x80010000+0x800;words=[w for (w,) in struct.iter_unpack('<I',rom[at:at+row['bytes']])]
 stores=[(pc+4*i,w) for i,w in enumerate(words) if w>>26==0x2B and w&65535==0x30]
 require(len(stores)==1,'Require one original callback-word store.')
 address,word=stores[0];specs.append(('lost_callback_argument',address,word,(word&~0x1F0000)|(4<<16)))
 for name,offset,replacement in ((CALLERS[0],0x84,0x80),(CALLERS[1],0x30,0x2C)):
  row=next(r for r in callers if r['function']==name);pc=int(row['address'],16)
  words=[w for (w,) in struct.iter_unpack('<I',code[pc-CODE:pc-CODE+row['bytes']])]
  loads=[(pc+4*i,w) for i,w in enumerate(words) if w>>26==0x23 and w&65535==offset]
  require(len(loads)==1,'Require one reviewed callback/slot load.')
  address,word=loads[0];specs.append(('wrong_'+hex(offset),address,word,(word&0xFFFF0000)|replacement))
 results=[]
 for name,pc,old,new in specs:
  machine=Machine(rom,symbols,functions,code,callers,(pc,old,new))
  try:machine.run(1,0)
  except (ValueError,machine.u.UcError) as error:
   require(machine.fault_hits>0,'The rejected callback fault never executed.')
   results.append(dict(name=name,rejected=True,executed=machine.fault_hits,reason=str(error)))
  else:raise ValueError('Incorrect callback word/slot was accepted: '+name)
 return results

def verify(output):
 require_ninja();require(check_build_current(ROOT) is True,'Require a current matching complete build.')
 before=build_inputs();dependencies={n:sha((ROOT/n).read_bytes()) for n in DEPENDENCIES};identity=backend()
 rom=(ROOT/configure.ROM).read_bytes();require(sha(rom)==CANONICAL_SHA256 and rom==(ROOT/configure.EXE).read_bytes(),'Require the canonical original executable.')
 symbols,functions,diagnostic=qualified_original(output,rom)
 flow=static_original_flow(rom,symbols,functions);code,callers,commands=compile_callers(output,symbols)
 machine=Machine(rom,symbols,functions,code,callers);observations=[]
 for locked,memory_locked in itertools.product(WORDS,repeat=2):observations.append(machine.run(locked,memory_locked))
 faults=negative_controls(rom,symbols,functions,code,callers);compiler_faults=compiler_controls(output)
 for row in functions+callers:
  require(sha(bytes(machine.cpu.mem_read(int(row['address'],16)&MASK,row['bytes'])))==row['sha256'],'Positive original/owned code changed.')
 require(before==build_inputs() and dependencies=={n:sha((ROOT/n).read_bytes()) for n in DEPENDENCIES}
  and identity==backend() and rom==(ROOT/configure.ROM).read_bytes(),'Build inputs, verifier, backend or original executable changed.')
 report=dict(status='passed_bounded_display_word_callback_interface',initialized_cases=len(observations),
  owned_top_level_calls=3*len(observations),actual_entry_counts=dict(machine.counts),original_functions=functions,
  compiled_C_callers=callers,ABI_assertions=7,original_static_call_site=flow,original_symbol_diagnostic=diagnostic,
  dependency_output_stubs=0,negative_controls=faults,negative_compiler_controls=compiler_faults,
  observations_sha256=sha(json.dumps(observations,sort_keys=True).encode()),backend_identity=identity,compiler_commands=commands,
  analysis_caller_warnings_are_errors=True,build_input_hashes=before,producer_dependencies=dependencies,
  canonical_executable_sha256=sha(rom),new_C_bytes=0,whole_feature_groups_accepted=0,whole_NPC_encounters_accepted=0,
  original_display_loop_executed=False,natural_callback_histories_accepted=False,SDK_or_disc_IO_accepted=False,
  scope='Typed original setter, original CD tick lock/memory-lock/idle guard paths and original memory getter on owned initialized objects. The display loop relation is static; VSync, active CD phases, SDK callbacks, real frames, asynchronous I/O and whole features remain unaccepted.')
 (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:report[k] for k in ('status','initialized_cases','owned_top_level_calls','actual_entry_counts','new_C_bytes')}),flush=True)
 return report

def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args(argv)
 try:
  require(sys.platform!='win32','Run in the matching Linux/WSL compiler and pinned Unicorn environment.')
  output=output_directory(args.output);output.mkdir(parents=True);verify(output);return 0
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
  print('[!] '+str(error),file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
