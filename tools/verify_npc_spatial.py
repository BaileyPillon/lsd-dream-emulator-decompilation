"""Compose real transform helpers and original GTE with existing callback models."""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import struct
import sys
sys.path.insert(0,str(Path.cwd()))
from tools import verify_native_ai as n
from tools import verify_scripted_ai as s
from tools import verify_render_gte as g
from tools import verify_render_rotation as r

HELPERS = [
    {
        "function": "func_8001D008",
        "address": "0x8001d008",
        "bytes": 228,
        "sha256": "225abd6608917cf20ad9aca5ad59a9a7f6f43e67f64d8372e6aeb2e9fbfe7363"
    },
    {
        "function": "func_8001CEB4",
        "address": "0x8001ceb4",
        "bytes": 340,
        "sha256": "722d79cf1f8c109300d4a56aa1d421442a2b5c424a7f3f1e16ad27d281432217"
    },
    {
        "function": "func_8001EC84",
        "address": "0x8001ec84",
        "bytes": 120,
        "sha256": "7c14d23868ee93933886ecd2477e4e60c6200bef1982963f671e2d76e6d7caaf"
    },
    {
        "function": "func_8001E58C",
        "address": "0x8001e58c",
        "bytes": 116,
        "sha256": "d0f977e8df4d270bfd57647ce4d42f81641736d27383f8916fce2439796c34c2"
    },
    {
        "function": "func_8001D4DC",
        "address": "0x8001d4dc",
        "bytes": 140,
        "sha256": "66d6016ba623639a9f3c1e4d2ad39782f05a3eedaa2d4658e9aeaa0d634f950f"
    },
    {
        "function": "func_8001EE98",
        "address": "0x8001ee98",
        "bytes": 124,
        "sha256": "2569a9b916b6606e7e75e70b4397a0c3b0a4d08781d858570dd43e384b3217ab"
    },
    {
        "function": "func_800573A8",
        "address": "0x800573a8",
        "bytes": 36,
        "sha256": "cb98f20f55e4915c70de0cd5ec85346bad6f0c06c72aa4c2ff968b5327149cda"
    },
    {
        "function": "func_800573CC",
        "address": "0x800573cc",
        "bytes": 120,
        "sha256": "c1a99e64390fec4e8dcf12a0a17942c6c30f55d6703dc08a78cd5e1111b8ad19"
    },
    {
        "function": "func_80057444",
        "address": "0x80057444",
        "bytes": 72,
        "sha256": "f733da4527460b28cca35c365edb865d3612c61b47356ff8500d430a5bc7d680"
    },
    {
        "function": "func_8005748C",
        "address": "0x8005748c",
        "bytes": 56,
        "sha256": "56c4b7f4e13cde1be03d9e0f549a37ad158f8194a73c986e003153ea0acfe087"
    },
    {
        "function": "func_800574C4",
        "address": "0x800574c4",
        "bytes": 56,
        "sha256": "29303f176ed3d04daf35423bed542cbae4fafeaff90abdf8182d51eb31613f55"
    },
    {
        "function": "func_800574FC",
        "address": "0x800574fc",
        "bytes": 56,
        "sha256": "e22cf1c7265259493c587b72e18fdd9cf18a600fcf0189cc6bed5784078fef66"
    },
    {
        "function": "func_80057534",
        "address": "0x80057534",
        "bytes": 124,
        "sha256": "6bfcd219c77dc157668f2ca054b8ae40423b9bf2cc61552577216917aa6b37da"
    }
]
FUNCTIONS=s.NATIVE_FUNCTIONS+HELPERS+[r.ROTATION,g.APPLY]
CALLBACKS=('entity_elephant','entity_fish_giant','entity_elephant_small','entity_bird','entity_rocket','entity_ufo','entity_fish')
pairs=None
COORD,POSE=0x110000,0x110100
REMOVED={'scale','rotation','translation','forward','axis_c8','vertical'}
def fixtures(case):
    coord=bytearray([0xB9]*0x60);pose=bytearray([0xA9]*0x38)
    n.word(coord,0,1);n.word(coord,0x44,POSE)
    for i,value in enumerate(case.get('position',(1000,2000,3000))):n.word(coord,0x18+i*4,value)
    for i,value in enumerate(case.get('scale',(4096,4096,4096))):n.word(pose,i*4,value)
    struct.pack_into('<3h',pose,0x10,*case.get('euler',(0,0,0)))
    return coord,pose
def div(a,b):return (-1 if (a<0)!=(b<0) else 1)*(abs(a)//abs(b))
def sh(v):return (v+0x8000)%0x10000-0x8000
def model(cb,case):
    result=s.expected(cb,case)
    entity=bytearray(result['entity']);n.word(entity,0x14,COORD)
    coord,pose=fixtures(case);trace=[];commands=[]
    for item in result['trace']:
        name=item[0]
        if name not in REMOVED:trace.append(item);continue
        if name in ['scale','rotation']:
            data=n.h.target(item[3],12)
            values=[]
            for offset in [0,4,8]:
                a,b=struct.unpack_from('<hh',data,offset)
                values.append((div(a,b)<<12)+div((a-div(a,b)*b)<<12,b))
            for i,val in enumerate(values):
                if name=='scale':
                    old=struct.unpack_from('<i',pose,i*4)[0]
                    n.word(pose,i*4,sh(val) if item[2] else old+sh(val))
                else:
                    offset=0x10+i*2;old=struct.unpack_from('<h',pose,offset)[0];value=div(val,360)
                    value=value if item[2] else s.signed_remainder(old+value,4096)
                    struct.pack_into('<h',pose,offset,sh(value))
        elif name=='translation':
            vec=struct.unpack('<3i',n.h.target(item[2],12))
            for i,value in enumerate(vec):
                offset=0x18+i*4;old=struct.unpack_from('<i',coord,offset)[0];n.word(coord,offset,old+value)
        else:
            amount=sh(item[2]);struct.pack_into('<h',entity,0x48,amount)
            vector=[0,0,0];vector[{'axis_c8':0,'vertical':1,'forward':2}[name]]=amount
            euler=struct.unpack_from('<3h',pose,0x10)
            matrix=struct.unpack('<9h',r.rotation_bytes(euler,pairs))
            vec,cmd=g.apply_model(matrix,vector);commands.extend(cmd)
            for i,value in enumerate(vec):
                offset=0x18+i*4;old=struct.unpack_from('<i',coord,offset)[0];n.word(coord,offset,old+value)
        n.word(coord,0,0)
    return dict(result,entity=bytes(entity),trace=trace,coordinate=bytes(coord),pose=bytes(pose)),commands

class Machine(s.Machine):
    def __init__(self,cb,bridge,patches=None):
        super().__init__(cb)
        self.stubs={address:spec for address,spec in self.stubs.items() if spec[0]=='trigger_ratio'}
        self.native_entries={int(e['address'],16)&n.MASK:e['function'] for e in FUNCTIONS}
        assert not set(self.stubs)&set(self.native_entries)
        for address,data in (patches or {}).items():
            self.cpu.mem_write(address&n.MASK,data)
        self.adapter=g.Cop2Adapter(bridge)
    def hook(self,cpu,address,size,unused):
        if g.handle_cop2(self.adapter,cpu,address&n.MASK):return
        super().hook(cpu,address,size,unused)
    def run(self,case):
        self.adapter.reset()
        self.case,self.trace=case,[]
        cpu=self.cpu
        entity,dream,context=s.fixtures(case)
        n.word(entity,0x14,COORD)
        coord,pose=fixtures(case)
        buffers=[('entity',n.ENTITY,entity),('dream',n.DREAM,dream),('context',n.CONTEXT,context),
                 ('child',s.CHILD,s.child_fixture()),('coordinate',COORD,coord),('pose',POSE,pose)]
        for name,address,data in buffers:cpu.mem_write(address,bytes(data))
        cpu.mem_write(n.RNG,struct.pack('<I',n.u32(case['seed'])))
        cpu.mem_write(n.STACK-0x200,bytes([0xCC])*0x400)
        saved=[n.u32(0xAB000000+0x10203*i) for i in range(len(n.SAVED))]
        for register,value in zip(n.SAVED,saved):cpu.reg_write(register,value)
        for register,value in [(n.reg.UC_MIPS_REG_SP,n.STACK),(n.reg.UC_MIPS_REG_GP,0x8008A808),
                (n.reg.UC_MIPS_REG_RA,n.END),(n.reg.UC_MIPS_REG_A0,n.ENTITY),(n.reg.UC_MIPS_REG_A1,n.CONTEXT)]:
            cpu.reg_write(register,value)
        cpu.emu_start(self.start,n.END,count=30000)
        if (cpu.reg_read(n.reg.UC_MIPS_REG_PC)!=n.END or cpu.reg_read(n.reg.UC_MIPS_REG_SP)!=n.STACK
                or [cpu.reg_read(register) for register in n.SAVED]!=saved):
            raise ValueError('Spatial callback did not preserve return/stack/saved registers.')
        return dict({name:bytes(cpu.mem_read(address,len(data))) for name,address,data in buffers},
                    rng_seed=int.from_bytes(cpu.mem_read(n.RNG,4),'little'),trace=self.trace)


def cases(callback):
    base=s.cases_by_callback()[callback]
    for case in base:yield 'existing_control_phases',case
    selected=base if callback!='entity_fish' else [base[i] for i in (0,1,2,3,5,6,11,12,31,32,63,64,499,500,501,-15,-1)]
    for euler in [(0,1024,0),(0,-1024,0),(128,777,-256),(1023,2048,2049),(-32768,-1,32767)]:
        for case in selected:
            yield 'changed_starting_pose',dict(case,euler=euler,position=(0x7fffffff,-2000,-0x80000000),scale=(-4096,8192,2048))

def negative_controls(bridge):
    records=[]
    controls=[('func_8001D008','entity_fish_giant',0x2B,0,4,'wrong_scale_destination'),
              ('func_800573CC','entity_elephant',0x2B,0x18,0x1c,'wrong_translation_destination'),
              ('func_80057534','entity_elephant_small',0x29,0x48,0x4a,'wrong_nudge_halfword')]
    functions={record['function']:record for record in FUNCTIONS}
    for function,callback,opcode,offset,changed,reason in controls:
        record=functions[function];base=int(record['address'],16)
        original=n.h.target(base,record['bytes'])
        candidates=[i for i in range(0,len(original),4) if
            (word:=int.from_bytes(original[i:i+4],'little'))>>26==opcode
            and (word>>21)&31!=29 and word&0xffff==offset]
        if not candidates:raise ValueError('No reviewed mutation instruction: '+function)
        # These callbacks use the additive translation branch, after the copy branch.
        position=candidates[-1] if function=='func_800573CC' else candidates[0]
        word=int.from_bytes(original[position:position+4],'little')
        machine=Machine(callback,bridge,{base+position:struct.pack('<I',(word&0xffff0000)|changed)})
        case=s.cases_by_callback()[callback][0]
        expected,_=model(callback,case)
        if machine.run(case)==expected:raise ValueError('Undetected spatial control: '+reason)
        records.append({'kind':reason,'function':function,'function_offset':position,'detected':True})
    base=int(g.APPLY['address'],16);original=n.h.target(base,g.APPLY['bytes'])
    words=[int.from_bytes(original[i:i+4],'little') for i in range(0,len(original),4)]
    position=words.index(g.COMMANDS[1])*4
    machine=Machine('entity_elephant_small',bridge,{base+position:struct.pack('<I',g.COMMANDS[0])})
    case=s.cases_by_callback()['entity_elephant_small'][0]
    expected,_=model('entity_elephant_small',case)
    if machine.run(case)==expected:raise ValueError('Undetected shifted GTE command control.')
    records.append({'kind':'wrong_gte_shift_command','function':'ApplyMatrixLV','function_offset':position,'detected':True})
    return records

def verify(destination,executable,runtime):
    global pairs
    dependencies=n.evidence_dependencies('tools/verify_npc_spatial.py','tools/verify_scripted_ai.py',
        'tools/verify_render_gte.py','tools/verify_render_rotation.py','src/scene/scene_node.c',
        'src/scene/scene_node.h','src/base/object_math.c','tools/nymashock_gte_bridge.cs')
    before={path:hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    n.initialize_backend(n.load_program(FUNCTIONS))
    pairs=r.table_pairs(n.h)
    backend=s.backend_identity()
    bridge_hash=hashlib.sha256(Path(executable).read_bytes()).hexdigest()
    destination=Path(destination)
    bridge=g.NativeGteBridge(executable,runtime,destination.with_suffix('.log'))
    counts,entries,groups={},Counter(),Counter()
    try:
        for cb in CALLBACKS:
            machine=Machine(cb,bridge)
            count=0
            for group,case in cases(cb):
                expected,commands=model(cb,case);actual=machine.run(case)
                if actual!=expected or [e['output'] for e in machine.adapter.commands]!=commands:
                    failure=destination.with_name(destination.stem+'-failure.json')
                    failure.write_text(json.dumps({'callback':cb,'case':case,'actual':repr(actual),'expected':repr(expected),'gte_actual':[e['output'] for e in machine.adapter.commands],'gte_expected':commands},indent=2)+'\n')
                    raise ValueError('Spatial disagreement '+cb+' fixture '+str(count))
                count+=1;groups[group]+=1
            counts[cb]=count;entries.update(machine.entry_counts)
            print(cb,count,'passed',flush=True)
        commands_before_controls=bridge.count
        controls=negative_controls(bridge)
        if (s.backend_identity()!=backend or hashlib.sha256(Path(executable).read_bytes()).hexdigest()!=bridge_hash
                or (n.ROOT/n.configure.ROM).read_bytes()!=n.h.ROM
                or (n.ROOT/n.configure.EXE).read_bytes()!=n.h.ROM or n.check_build_current(n.ROOT) is not True
                or any(hashlib.sha256(path.read_bytes()).hexdigest()!=digest for path,digest in before.items())):
            raise ValueError('Spatial producer, backend or canonical inputs changed.')
        report={'status':'passed_bounded_original_npc_spatial_composition','callback_count':len(CALLBACKS),
            'native_cases':sum(counts.values()),'cases_by_callback':counts,'case_groups':dict(groups),
            'actual_native_entry_counts':dict(entries),'native_functions':FUNCTIONS,
            'dependency_contracts':['trigger_ratio'],'cop2_adapter':'Reviewed original register transfers and checked Nymashock MVMVA; no original helper output substituted.',
            'native_gte_commands':commands_before_controls,'native_gte_control_commands':bridge.count-commands_before_controls,
            'bridge_executable_sha256':bridge_hash,'nymashock_compressed_core_sha256':g.CORE_SHA256,
            'backend_identity':backend,'negative_controls_detected':controls,
            'canonical_original_and_build_equal':True,'original_game_behavior_modified':False,'model_api_calls':0,
            'producer_dependencies':[{'path':p.resolve().relative_to(n.ROOT).as_posix(),'sha256':digest} for p,digest in before.items()],
            'whole_feature_groups_accepted':0,'whole_callback_accepted':False,
            'scope':'Seven original callbacks with actual scale/rotation/translation/axis/world helpers, SDK rotation and GTE. Full entity/dream/context/linked-child/coordinate/pose buffers, command arithmetic and ABI; manual valid object graph and ratio contract. Excludes natural construction/encounters, lifecycle histories, drawing/audio and PS1 CPU timing.'}
        with destination.open('x') as handle:json.dump(report,handle,indent=2);handle.write('\n')
        return report
    finally:bridge.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--bridge',required=True)
    parser.add_argument('--runtime',required=True)
    args=parser.parse_args()
    path=Path(args.output).resolve()
    if not path.is_relative_to((n.ROOT/'.decomp-lab').resolve()) or path.exists() or path.with_suffix('.log').exists():
        raise ValueError('Choose a fresh private report/log path inside .decomp-lab.')
    path.parent.mkdir(parents=True,exist_ok=True)
    report=verify(path,args.bridge,args.runtime)
    print(json.dumps({'status':report['status'],'native_cases':report['native_cases'],'commands':report['native_gte_commands']}))
    return 0
if __name__=='__main__':sys.exit(main())
