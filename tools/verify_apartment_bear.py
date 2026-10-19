"""Original Apartment Bear callback with its bound MOM animation and native helpers.

Constructed entity/model graph; injected ticks and command timers. No stage
collision target, live sound slots, engine stepping, rendering or encounter
acceptance. Original MIPS dependencies execute without output substitution.
"""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import verify_native_ai as n
from tools import verify_npc_proximity as p
from tools import verify_astronaut as a
from tools import verify_actor_factory as factory
from tools import verify_scripted_ai as scripts
from tools import verify_render_gte as g
from tools import verify_render_rotation as r
from tools.actor_animation_model import AnimationPayloadPlan
from tools.model_mapping_model import mapped_model_bytes

CALLBACK = 'entity_bear_apartment'
RANGE_FILE = ROOT / 'docs/apartment-bear-function-ranges.json'
FUNCTIONS = json.loads(RANGE_FILE.read_bytes())
RESOURCE_SHA256 = '6da66f8769eaebaa57fa4c6ef37228aa353bbe25f10a3b2a72f5870272610e80'
MODEL_SHA256 = 'af4834af69970858e9287ffd56222648388c0e082b631e3e5d0c3fc3f2719ce1'
BINDING_SHA256 = '1b8a0ea21a1d4ce5748207d72673f505cd20b56ad72e1852d38a7dda67cfb4a1'
raw, pairs, proximity_value = None, None, 10


def validate_case(case):
    p.validate_case(case)
    for key in ('tick','timer','frame','state'):
        if not -0x80000000 <= case[key] <= 0x7fffffff:
            raise ValueError('Use signed native callback words.')
    if (type(case['variant']) is not int or case['variant'] not in (0,1)
            or not 0 <= case['seed'] <= 0xffffffff
            or case.get('pattern','distinct') not in factory.child.PATTERNS):
        raise ValueError('Require a bound animation, native RNG word and known residue pattern.')


def script_actions(case, duration):
    """Predict callback scheduling without executing or reading native output."""
    result=[]
    if case['timer'] % 5 == 0:
        result.extend((('command',7,17),('command',8,-2)))
    tick,state = case['tick'],case['state']
    if case['variant'] == 0:
        if tick == duration:
            result.extend((('select',1),('random_state',11)))
        return result
    if state == 0:
        if tick in (60,212,290,320): result.append(('turn','g_RotateYawQuarter'))
        if tick == 398: result.append(('turn','g_RotateYawNegQuarter'))
        result.append(('forward',))
    else:
        if tick in (60,140): result.append(('turn','g_RotateYawQuarter'))
        if tick < 174: result.append(('forward',))
        if tick == 174: result.append(('stop',))
    return result


class EntityPlan(AnimationPayloadPlan):
    def node(self, size, kind):
        return super().node(0x108 if kind == 'actor' else size, kind)

def prepare(variant=0, tick=10, timer=5, seed=1, pattern='distinct'):
    pool = factory.initial_pool(pattern)
    pool.setup()
    angles = factory.child.rational_values(n.h.target(n.h.symbols['D_8006B684'], 12))
    scales = factory.child.rational_values(n.h.target(n.h.symbols['D_8006B690'], 12))
    plan = EntityPlan(raw, pool, n.h.symbols, factory.DATA, angles, scales)
    actor = plan.create_actor()
    if variant:
        plan.select_animation(actor, variant)
    case = dict(p.base_case(CALLBACK, 77, proximity_value), variant=variant, tick=tick, timer=timer,
                duration=plan.word(actor.pointer, 128), frame=7, seed=seed)
    buffers = p.fixtures(case)
    entity, dream, context = [buffers[key][1] for key in ('entity','dream','context')]
    for offset in (0x44, 0x48, 0x4c, 0x58, 0x8c, 0x90, 0x94, 0x98, 0xb0, 0xf0, 0xf4, 0xf8, 0xfc):
        plan.write(actor.pointer, offset, entity[offset:offset+4])
    plan.put(actor.pointer, 0, n.h.symbols['g_ENTITY_VTABLE'])
    plan.put(actor.pointer, 0x4c, 0)
    plan.put(actor.pointer, 0x58, 0)
    plan.put(actor.pointer, 0x84, case['frame'])
    coordinate, pose = buffers['coordinate'][1], buffers['pose'][1]
    coordinate = bytearray(coordinate[:80])
    n.word(coordinate, 0x44, actor.state)
    n.word(coordinate, 0x48, 0)
    plan.write(actor.coordinate, 0, coordinate)
    plan.write(actor.state, 0, pose[:40])
    model = mapped_model_bytes(raw, factory.DATA, actor.model.animations, tuple(plan.geometry_indices))
    initialized = {key: value for key,value in buffers.items() if key in ('dream','context','player_coordinate','player_root','linked_child')}
    initialized.update(pool=(factory.POOL, bytearray(pool.buffers['pool'])),
        manager=(factory.MANAGER, bytearray(pool.buffers['manager'])), model=(factory.DATA, bytearray(model)))
    return case, plan, actor, initialized

class Machine(a.Machine):
    def __init__(self, bridge, patches=None):
        p.Machine.__init__(self, 'entity_bear_apartment', bridge, patches, native_functions=FUNCTIONS)
        self.changed_addresses.update(address & n.MASK for address in (patches or {}))
        self.observed = {'entity_get_trigger_ratio':('read_trigger_ratio',1),
            'func_8005748C':('forward',3), 'func_8001CEB4':('rotation',3),
            'func_800573A8':('translation',2), 'func_80066214':('selection',2),
            'entity_stop_behaviour':('stop',1)}
    def run(self, case, actor, initialized, reset=True):
        self.initial = initialized
        self.trace, self.pending_returns, self.rng_trace, self.events = [], {}, [], []
        self.hits.clear()
        self.rejected_store = None
        self.adapter.reset()
        cpu = self.cpu
        if reset:
            for address, data in initialized.values(): cpu.mem_write(address, bytes(data))
            cpu.mem_write(n.RNG, struct.pack('<I',case['seed']))
            cpu.mem_write(n.h.symbols['D_8008ABA4'] & n.MASK,bytes(8))
        else:
            cpu.mem_write(actor.pointer+0xfc,struct.pack('<I',n.u32(case['tick'])))
            cpu.mem_write(n.CONTEXT+4,struct.pack('<I',n.u32(case['timer'])))
        cpu.mem_write(n.STACK-0x800,bytes([0xcc])*0x900)
        saved=[n.u32(0xab000000+i*0x10203) for i in range(len(n.SAVED))]
        for reg,value in zip(n.SAVED,saved): cpu.reg_write(reg,value)
        for i,reg in enumerate(n.VOLATILE): cpu.reg_write(reg,n.u32(0xda000000+i*0x10203))
        for reg,val in ((n.reg.UC_MIPS_REG_SP,n.STACK),(n.reg.UC_MIPS_REG_GP,0x8008a808),
            (n.reg.UC_MIPS_REG_RA,n.END),(n.reg.UC_MIPS_REG_A0,actor.pointer),(n.reg.UC_MIPS_REG_A1,n.CONTEXT)):
            cpu.reg_write(reg,val)
        cpu.emu_start(self.start,n.END,count=100000)
        if (cpu.reg_read(n.reg.UC_MIPS_REG_PC) != n.END
                or cpu.reg_read(n.reg.UC_MIPS_REG_SP) != n.STACK
                or cpu.reg_read(n.reg.UC_MIPS_REG_GP) != 0x8008a808
                or cpu.reg_read(n.reg.UC_MIPS_REG_RA) != n.END
                or [cpu.reg_read(register) for register in n.SAVED] != saved
                or self.pending_returns
                or bytes(cpu.mem_read(n.STACK-0x800,64)) != bytes([0xcc])*64
                or bytes(cpu.mem_read(n.STACK+0x40,64)) != bytes([0xcc])*64):
            raise ValueError('Original callback violated return/ABI/stack guards.')
        return {key:bytes(cpu.mem_read(address,len(data))) for key,(address,data) in initialized.items()}


def fixture(changes):
    variant,tick,timer,seed = (changes.get(k,v) for k,v in [('variant',0),('tick',1),('timer',1),('seed',1)])
    case,plan,actor,buffers = prepare(variant,tick,timer,seed,changes.get('pattern','distinct'))
    case.update(changes,proximity=proximity_value)
    validate_case(case)
    for offset,key in ((0x44,'state'),(0xfc,'tick'),(0x84,'frame'),(0xb0,'proximity_scale')):
        plan.put(actor.pointer,offset,case[key])
    plan.put(actor.pointer,0x94,n.DREAM if case['has_dream'] else 0)
    for offset in (0xb4,0xc8,0xdc): plan.put(actor.pointer,offset,-1)
    for index,value in enumerate(case['position']): plan.put(actor.coordinate,0x18+index*4,value)
    for index,value in enumerate(case['euler']): plan.half(actor.state,0x10+index*2,value)
    for index,value in enumerate(case['player_position']): n.word(buffers['player_coordinate'][1],0x38+index*4,value)
    buffers['pool'] = (factory.POOL,bytearray(plan.pool.buffers['pool']))
    return case,plan,actor,buffers

def expect(case,plan,actor,buffers):
    context = bytearray(buffers['context'][1])
    seed,trace,commands,rng = case['seed'],[],[],[]
    position = struct.unpack('<3i',plan.read(actor.coordinate,0x18,12))
    ratio = p.trigger_ratio(position,case['player_position'],case['proximity'],case['proximity_scale'],case['has_dream'])
    trace.extend([['read_trigger_ratio',actor.pointer],['trigger_ratio',n.u32(ratio)]])
    n.word(context,16,ratio)
    def turn(symbol):
        data = n.h.target(n.h.symbols[symbol],12)
        trace.append(['rotation',actor.pointer,0,n.h.symbols[symbol],data.hex()])
        for axis in range(3):
            numerator,denominator = struct.unpack_from('<hh',data,axis*4)
            value = p.div(numerator*4096,denominator)
            value = p.div(value,360)
            old = struct.unpack('<h',plan.read(actor.state,16+axis*2,2))[0]
            plan.half(actor.state,16+axis*2,scripts.signed_remainder(old+value,4096))
        plan.put(actor.coordinate,0,0)
    def forward():
        plan.put(actor.pointer,0x28,0)
        plan.half(actor.pointer,0x48,-50)
        trace.append(['forward',actor.pointer,n.u32(-50),0])
        matrix = struct.unpack('<9h',r.rotation_bytes(struct.unpack('<3h',plan.read(actor.state,16,6)),pairs))
        vector = (0,0,-50)
        moved,outputs = g.apply_model(matrix,vector)
        for word,part,output in zip(g.COMMANDS,g.split_vector(vector),outputs):
            commands.append({'inputs':{'cr':g.matrix_words(matrix),'ir':list(part),'command':word},'output':output})
        trace.append(['movement_translation',actor.pointer,struct.pack('<3i',*moved).hex()])
        for axis,value in enumerate(moved):
            plan.put(actor.coordinate,24+axis*4,plan.word(actor.coordinate,24+axis*4)+value)
        plan.put(actor.coordinate,0,0)
    for action in script_actions(case, plan.word(actor.pointer,128)):
        kind = action[0]
        if kind == 'command': n.word(context,action[1]*4,action[2])
        elif kind == 'turn': turn(action[1])
        elif kind == 'forward': forward()
        elif kind == 'select':
            trace.append(['selection',actor.pointer,action[1]])
            plan.select_animation(actor,action[1])
        elif kind == 'random_state':
            rng.append(['rand',seed])
            seed=n.u32(seed*0x41c64e6d+0x3039)
            if seed>>16&1: plan.put(actor.pointer,0x44,action[1])
        elif kind == 'stop':
            trace.append(['stop',actor.pointer])
            for offset in (0x9c,0x90,0x8c,0xf8): plan.put(actor.pointer,offset,0)
            plan.put(actor.pointer,0x44,1)
        else: raise ValueError('Unknown independently predicted operation.')
    expected={key:bytes(data) for key,(_address,data) in buffers.items()}
    expected.update(pool=bytes(plan.pool.buffers['pool']),context=bytes(context),
        model=bytes(mapped_model_bytes(raw,factory.DATA,actor.model.animations,tuple(plan.geometry_indices))))
    return expected,seed,trace,rng,commands

def cases():
    for variant,state,tick in itertools.product((0,1),(-1,0,1,11),
        (-0x80000000,-1,0,9,10,11,59,60,61,139,140,141,173,174,175,211,212,213,289,290,291,319,320,321,397,398,399,0x7fffffff)):
        yield dict(variant=variant,state=state,tick=tick)
    for state,seed in itertools.product((-1,0,1,11),(0,1,2,3,4,42,0x7fffffff,0xffffffff)):
        yield dict(variant=0,state=state,tick=10,seed=seed,timer=5)
    for tick,euler in itertools.product((60,140,398),((0,1024,0),(0,-1024,0),(-32768,32767,2048),(2048,-32768,-2048),(4095,-4095,4095))):
        yield dict(variant=1,tick=tick,euler=euler)
    for timer in (-0x80000000,-11,-10,-6,-5,-4,-1,0,1,4,5,6,9,10,0x7fffffff):
        yield dict(variant=1,tick=60,timer=timer)
    for has_dream,scale,pos in itertools.product((False,True),(1,1000),
        ((0,0,0),(0x7fffffff,0,-0x80000000),(-0x80000000,0,0),(20480,0,1))):
        yield dict(variant=1,tick=1,has_dream=has_dream,proximity_scale=scale,position=pos)


FAULTS = (
    ('periodic-command',0x80062a9c,0x34020011,0x34020012,dict(timer=5)),
    ('rng-state',0x80062af8,0x3402000b,0x3402000c,dict(tick=10,seed=3)),
    ('quarter-turn-boundary',0x80062b10,0x3402003c,0x3402003d,dict(variant=1,tick=60)),
    ('movement-distance',0x80062b90,0x2405ffce,0x2405ffcd,dict(variant=1,tick=1)),
    ('stop-active-flag',0x8005dbd8,0xae0000f8,0,dict(variant=1,state=11,tick=174)),
    ('animation-selection',0x80066220,0xac85007c,0,dict(tick=10)),
    ('animation-duration',0x80066250,0xac820080,0xac800080,dict(tick=10)),
)


def compare(machine, case, actor, initialized, expected, seed, trace, rng, commands, reset=True):
    actual=machine.run(case,actor,initialized,reset=reset)
    bad=[key for key in expected if actual[key]!=expected[key]]
    if struct.unpack('<I',machine.cpu.mem_read(n.RNG,4))[0]!=seed: bad.append('rng_seed')
    if machine.trace!=trace: bad.append('call_trace')
    if machine.rng_trace!=rng: bad.append('rng_trace')
    if machine.adapter.commands!=commands: bad.append('native_gte_commands')
    if bytes(machine.cpu.mem_read(n.h.symbols['D_8008ABA4'] & n.MASK,8))!=bytes(8):
        bad.append('motion_scratch')
    return bad


def verify(destination, resource, bridge_path, runtime):
    global raw, pairs, proximity_value
    destination=factory.common.output_directory(destination)
    resource=Path(resource).resolve()
    data=resource.read_bytes()
    if len(data)!=47104 or hashlib.sha256(data).hexdigest()!=RESOURCE_SHA256:
        raise ValueError('Require the canonical original CDI/STG00/M001.LBD resource.')
    raw=data[36960:36960+9820]
    if hashlib.sha256(raw).hexdigest()!=MODEL_SHA256:
        raise ValueError('The bound Apartment Bear MOM payload changed.')
    dependencies=n.evidence_dependencies('tools/verify_apartment_bear.py',
        'docs/apartment-bear-function-ranges.json','tools/verify_astronaut.py',
        'tools/verify_npc_proximity.py','tools/verify_npc_spatial.py',
        'tools/verify_scripted_ai.py','tools/verify_render_gte.py',
        'tools/verify_render_rotation.py','tools/verify_gunman_scripts.py',
        'tools/actor_animation_model.py','src/sound/sound.c','src/scene/scene_node.c')
    dependencies=sorted(set(dependencies+[ROOT/path for path in factory.DEPENDENCIES]))
    pins={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    n.initialize_backend(n.load_program(FUNCTIONS))
    if scripts.backend_identity()['package_version']!='2.1.4':
        raise ValueError('Use the pinned Unicorn 2.1.4 analysis backend for this callback profile.')
    pairs=r.table_pairs(n.h)
    record=n.h.target(n.h.symbols['g_ENTITY_TABLE']+77*16,16)
    if (hashlib.sha256(record).hexdigest()!=BINDING_SHA256
            or struct.unpack_from('<I',record,12)[0]!=n.h.symbols[CALLBACK]):
        raise ValueError('Original Apartment Bear entity-property binding changed.')
    proximity_value=struct.unpack_from('<b',record,10)[0]
    destination.mkdir(parents=True)
    bridge=g.NativeGteBridge(bridge_path,runtime,destination/'gte.log')
    started=time.monotonic()
    inputs,entries,histories,faults=[],Counter(),[],[]
    try:
        machine=Machine(bridge)
        for pattern in factory.child.PATTERNS:
            for changes in cases():
                changes=dict(changes,pattern=pattern)
                case,plan,actor,initialized=fixture(changes)
                fingerprint=hashlib.sha256(struct.pack('<I',case['seed'])+b''.join(
                    struct.pack('<I',address)+bytes(buf) for address,buf in initialized.values())).hexdigest()
                predicted=expect(case,plan,actor,initialized)
                bad=compare(machine,case,actor,initialized,*predicted)
                if bad: raise ValueError('Original callback mismatch: '+repr((changes,bad)))
                inputs.append(fingerprint)
        entries.update(machine.entries)
        for seed in (1,3):
            case,plan,actor,initialized=fixture(dict(tick=8,timer=-5,seed=seed))
            oracle_buffers={key:(address,bytearray(buf)) for key,(address,buf) in initialized.items()}
            timeline=(8,9,10,59,60,139,140,173,174,175,212,290,320,398,399)
            history=Machine(bridge)
            for index,tick in enumerate(timeline):
                case.update(tick=tick,timer=index-5,state=p.s32(plan.word(actor.pointer,0x44)),
                    variant=plan.word(actor.pointer,0x7c))
                plan.put(actor.pointer,0xfc,tick)
                n.word(oracle_buffers['context'][1],4,case['timer'])
                predicted=expect(case,plan,actor,oracle_buffers)
                bad=compare(history,case,actor,initialized,*predicted,reset=index==0)
                if bad: raise ValueError('Original state history mismatch: '+repr((seed,index,bad)))
                expected,next_seed,*_rest=predicted
                case['seed']=next_seed
                oracle_buffers={key:(oracle_buffers[key][0],bytearray(buf)) for key,buf in expected.items()}
            entries.update(history.entries)
            histories.append(dict(initial_seed=seed,script_invocations=len(timeline),
                                  injected_ticks=list(timeline),final_state=plan.word(actor.pointer,0x44)))
        if set(entries)!={row['function'] for row in FUNCTIONS}:
            raise ValueError('The reviewed native composition was not fully entered.')
        for name,address,old,new,changes in FAULTS:
            if struct.unpack('<I',n.h.target(address,4))[0]!=old:
                raise ValueError('Fault no longer identifies its original instruction: '+name)
            case,plan,actor,initialized=fixture(changes)
            predicted=expect(case,plan,actor,initialized)
            broken=Machine(bridge,{address:struct.pack('<I',new)})
            bad=compare(broken,case,actor,initialized,*predicted)
            hits=broken.hits[address & n.MASK]
            if not bad or not hits:
                raise ValueError('Executed wrong-output control was not detected: '+name)
            faults.append(dict(name=name,address=hex(address),old=hex(old),replacement=hex(new),
                               executed_hits=hits,mismatched_outputs=bad))
        callback=n.h.symbols[CALLBACK]
        body=n.h.target(callback,next(row['bytes'] for row in FUNCTIONS if row['function']==CALLBACK))
        stores=[(callback+i*4,word) for i,(word,) in enumerate(struct.iter_unpack('<I',body))
                if word>>26==43 and word&0xffff==28]
        if len(stores)!=1: raise ValueError('Require one original periodic-command store.')
        address,old=stores[0]
        case,plan,actor,initialized=fixture(dict(timer=5))
        guarded=Machine(bridge,{address:struct.pack('<I',(old&0xffff0000)|0x100)})
        try: guarded.run(case,actor,initialized)
        except ValueError as exc:
            if not guarded.rejected_store or guarded.rejected_store['address']!=n.CONTEXT+0x100:
                raise
            guard=dict(instruction=hex(address),rejected_before_write=True,detail=guarded.rejected_store)
        else: raise ValueError('Escaped native store was not rejected.')
        after={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
        if pins!=after or hashlib.sha256(resource.read_bytes()).hexdigest()!=RESOURCE_SHA256:
            raise ValueError('Verifier source or original model inputs changed during execution.')
        if (ROOT/'build/SLPS015.56').read_bytes()!=(ROOT/'rom/SLPS_015.56').read_bytes():
            raise ValueError('The matching executable changed during verification.')
        report=dict(schema_version=1,callback=CALLBACK,canonical_executable_sha256=hashlib.sha256(n.h.ROM).hexdigest(),
            resource_sha256=RESOURCE_SHA256,model_sha256=MODEL_SHA256,model_offset=36960,model_bytes=len(raw),
            animation_frame_counts=[10,30],binding_index=77,binding_record_sha256=BINDING_SHA256,
            backend=scripts.backend_identity(),source_sha256=pins,standalone_native_cases=len(inputs),
            distinct_initialized_inputs=len(set(inputs)),input_sha256=inputs,
            qualified_original_functions=FUNCTIONS,native_entry_counts=dict(entries),
            histories=histories,wrong_output_controls=faults,escaped_store_control=guard,
            bridge_sha256=hashlib.sha256(Path(bridge_path).read_bytes()).hexdigest(),native_gte_commands=bridge.count,
            dependency_output_stubs=0,external_model_API_calls=0,new_C_bytes=0,
            whole_NPC_encounters_accepted=0,whole_feature_groups_accepted=0,
            scope='Constructed original-model entity, no collision-stage target or active sound slots; injected callback ticks and command timers. Immediate first-frame selection, not animation playback or engine-driven encounters.',
            elapsed_seconds=time.monotonic()-started)
        with (destination/'report.json').open('x',encoding='utf-8') as stream:
            json.dump(report,stream,indent=2);stream.write('\n')
        return report
    finally: bridge.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--resource',required=True,help='Original extracted CDI/STG00/M001.LBD, kept private.')
    parser.add_argument('--bridge',required=True)
    parser.add_argument('--runtime',required=True,help='Windows path to the pinned existing BizHawk runtime.')
    args=parser.parse_args()
    try: report=verify(args.output,args.resource,args.bridge,args.runtime)
    except (ValueError,OSError) as exc: parser.exit(1,str(exc)+'\n')
    print(json.dumps({key:report[key] for key in ('standalone_native_cases','distinct_initialized_inputs',
        'native_gte_commands','new_C_bytes','whole_NPC_encounters_accepted')}))


if __name__=='__main__': main()
