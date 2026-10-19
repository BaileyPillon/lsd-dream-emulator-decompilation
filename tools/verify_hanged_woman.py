"""Bounded original Hanged Woman script, mood, control lock, motion and held node.

Native original helpers and GTE execute with no dependency-output stubs.
Constructed meshless graphs, supplied clocks and no notification recipients do
not prove a natural encounter, event delivery, rendering/audio or PS1 timing."""
import hashlib
import argparse
from collections import Counter
import itertools
import json
from pathlib import Path
import struct
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import verify_native_ai as n
from tools import verify_astronaut as a
from tools import verify_npc_proximity as p
from tools import verify_npc_spatial as spatial
from tools import verify_scripted_ai as scripts
from tools import verify_locomotive_scripts as locomotive
from tools import verify_render_gte as g
from tools import verify_render_rotation as r

CALLBACK='entity_hanged_woman'
CONTEXT=n.ENTITY+0x9c
PLAYER_POSE,HELD_LIST,HELD=0x113000,0x114000,0x115000
RANGE_FILE=ROOT/'docs/hanged-woman-function-ranges.json'
FUNCTIONS=json.loads(RANGE_FILE.read_text())
DATA={'g_RotateRollNeg90Yaw270':bytes.fromhex('0000010000000100a6ff0100'),
      'g_DreamColorTable':bytes.fromhex('060702040701030005000000')}
pairs=None

def base_case():
    case=a.base_case({'index':58,'proximity':30})
    case.update(player_euler=(0,0,0),player_scale=(4096,4096,4096),move_mode=1,
                held_flags=0x12345678)
    return case

def validate_case(case):
    a.validate_case(case)
    if (case['entity_id']!=58 or case['proximity']!=30 or type(case['move_mode']) is not int
            or case['move_mode'] not in (0,1,2)):
        raise ValueError('Use the original binding and reviewed movement-control modes.')
    if type(case['held_flags']) is not int or not 0<=case['held_flags']<=0xffffffff:
        raise ValueError('Use unsigned native held-object flags.')
    for key,lower,upper in (('player_euler',-32768,32767),('player_scale',-0x80000000,0x7fffffff)):
        if len(case[key])!=3 or any(type(x) is not int or not lower<=x<=upper for x in case[key]):
            raise ValueError('Use native player pose widths.')

def fixtures(case):
    validate_case(case)
    buffers=a.fixtures(case)
    entity,dream=buffers['entity'][1],buffers['dream'][1]
    for offset,value in ((4,0),(8,0),(0x70,HELD_LIST)):
        n.word(entity,offset,value)
    for offset,value in ((4,0),(8,0),(0x20,0),(0x4c,0),(0x98,0x81234560),
                         (0x9c,case['move_mode']),(0xc4,1),(0xc8,1)):
        n.word(dream,offset,value)
    coordinate,pose=spatial.fixtures(dict(case,position=case['player_position'],
                                        euler=case['player_euler'],scale=case['player_scale']))
    n.word(coordinate,0x44,PLAYER_POSE)
    for index,value in enumerate(case['player_position']):n.word(coordinate,0x38+4*index,value)
    buffers['player_coordinate']=(p.PLAYER_COORD,coordinate)
    buffers['player_pose']=(PLAYER_POSE,pose)
    held=bytearray([0xa3]*0x60)
    for offset,value in ((0,n.h.symbols['D_800878D4']),(4,0),(8,0),(0x10,case['held_flags'])):
        n.word(held,offset,value)
    buffers['held_object']=(HELD,held)
    buffers['held_list']=(HELD_LIST,bytearray(struct.pack('<II',HELD,HELD)))
    context=bytearray([0xc4]*0x54)
    for offset,value in ((0,1),(4,case['timer']),(8,n.ENTITY),(12,n.h.symbols[CALLBACK]),
                         (20,case['proximity_scale']),(24,-1),(44,-1),(64,-1)):
        n.word(context,offset,value)
    entity[0x9c:0xf0]=context
    buffers['context']=(CONTEXT,context)
    return buffers

def input_key(case):
    return json.dumps([[(name,address,bytes(data).hex()) for name,(address,data) in sorted(fixtures(case).items())],
                       case['seed']],separators=(',',':')).encode()

def expected(case,previous=None):
    validate_case(case)
    initial=fixtures(case)
    buffers={name:bytearray(data if previous is None else previous[name]) for name,(_address,data) in initial.items()}
    entity,dream,context=(buffers[name] for name in ('entity','dream','context'))
    n.word(entity,0xfc,case['tick']);n.word(context,4,case['timer'])
    trace,rng_trace,commands=[],[],[]
    seed=case['seed'] if previous is None else previous['rng_seed']
    def word(buffer,offset):return struct.unpack_from('<i',buffer,offset)[0]
    def command(index,value):n.word(context,index*4,value)
    def random():
        nonlocal seed
        rng_trace.append(['rand',seed]);seed=n.u32(seed*0x41c64e6d+0x3039)
        return (seed>>16)&0x7fff
    def distance():
        measured=p.distance(struct.unpack_from('<3i',buffers['coordinate'],0x18),
                            struct.unpack_from('<3i',buffers['player_coordinate'],0x38))
        trace.extend((['read_distance',n.ENTITY,n.DREAM],['distance',n.u32(measured)]))
        return measured
    def motion(owner,axis,value):
        coord=buffers['coordinate' if owner==n.ENTITY else 'player_coordinate']
        pose=buffers['pose' if owner==n.ENTITY else 'player_pose']
        obj=entity if owner==n.ENTITY else dream
        trace.append(['vertical' if axis==1 else 'lateral',owner,n.u32(value),0])
        struct.pack_into('<h',obj,0x48,p.s16(value))
        matrix=struct.unpack('<9h',r.rotation_bytes(struct.unpack_from('<3h',pose,0x10),pairs))
        vector=[0,0,0];vector[axis]=p.s16(value)
        moved,outputs=g.apply_model(matrix,vector)
        for command_word,part,result in zip(g.COMMANDS,g.split_vector(vector),outputs):
            commands.append({'inputs':{'cr':g.matrix_words(matrix),'ir':list(part),'command':command_word},'output':result})
        trace.append(['movement_translation',owner,struct.pack('<3i',*moved).hex()])
        for index,value in enumerate(moved):n.word(coord,0x18+4*index,word(coord,0x18+4*index)+value)
        n.word(coord,0,0)
    if word(entity,0xfc)==0:
        command(4,0);command(7,12)
        trace.append(['read_dream_color',n.DREAM])
        chunk,instance=locomotive.mood_average(dream,0x144),locomotive.mood_average(dream,0x154)
        trace.extend((['chunk_average',*chunk],['instance_average',*instance]))
        if word(dream,0x160)==0:instance=chunk
        axes=[p.div(x+y,2) for x,y in zip(chunk,instance)]
        bins=[2 if v>=4 else 0 if v < -3 else 1 for v in axes]
        color=DATA['g_DreamColorTable'][bins[0]*3+bins[1]]
        trace.append(['dream_color',color])
        if color==6:n.word(entity,0x44,11)
        elif random()%3==0:n.word(entity,0x44,12)
    if scripts.signed_remainder(case['timer'],100)==0:
        ratio=p.trigger_ratio(struct.unpack_from('<3i',buffers['coordinate'],0x18),
            struct.unpack_from('<3i',buffers['player_coordinate'],0x38),30,word(context,20))
        trace.extend((['read_trigger_ratio',n.ENTITY],['read_distance',n.ENTITY,n.DREAM],
                      ['distance',n.u32(p.distance(struct.unpack_from('<3i',buffers['coordinate'],0x18),struct.unpack_from('<3i',buffers['player_coordinate'],0x38)))],
                      ['trigger_ratio',n.u32(ratio)]))
        command(4,ratio);command(7,12);command(8,-1)
    state=word(entity,0x44)
    if state==11 and distance()<1024:
        trace.extend((['clear_callbacks',n.DREAM,0],['set_move_callback',n.DREAM,0]))
        if word(dream,0x9c)==2:
            trace.append(['set_view_mode',n.DREAM,0]);n.word(dream,0xc4,0);n.word(dream,0xc8,0)
        n.word(dream,0x9c,0);n.word(dream,0x98,0)
        n.word(entity,0x44,13);n.word(entity,0xfc,0)
    elif state==12 and distance()<1024:
        trace.append(['animation_stop',n.ENTITY]);n.word(entity,0x90,0)
        n.word(entity,0x44,14);n.word(entity,0xfc,0)
    state=word(entity,0x44);tick=word(entity,0xfc)
    if state==13:
        if tick<50:motion(n.DREAM,1,-20)
        elif tick<500:motion(n.DREAM,0,-5 if scripts.signed_remainder(tick,40)<20 else 5)
        elif tick==500:trace.append(['notify',n.ENTITY,12])
    if state==14:
        if tick<10:motion(n.ENTITY,1,200)
        elif tick==10:
            command(7,18);command(4,0);command(12,3)
            trace.append(['rotation',n.ENTITY,1,n.h.symbols['g_RotateRollNeg90Yaw270'],DATA['g_RotateRollNeg90Yaw270'].hex()])
            struct.pack_into('<3h',buffers['pose'],0x10,0,0,-1024);n.word(buffers['coordinate'],0,0)
            motion(n.ENTITY,0,2400);motion(n.ENTITY,1,1500)
            trace.append(['held_visible',HELD,0]);n.word(buffers['held_object'],0x10,word(buffers['held_object'],0x10)|0x80000000)
            n.word(entity,0x44,1)
    entity[0x9c:0xf0]=context
    return {**{name:bytes(data) for name,data in buffers.items()},'rng_seed':seed,'trace':trace,
            'rng_trace':rng_trace,'motion_scratch':bytes(8)},commands

class Machine(a.Machine):
    def __init__(self,bridge,patches=None):
        super().__init__(bridge,patches,callback=CALLBACK,native_functions=FUNCTIONS,
                         fixture_factory=fixtures,case_validator=validate_case,context_address=CONTEXT)
        self.observed={'dream_sys_get_dream_color':('read_dream_color',1),
            'entity_get_trigger_ratio':('read_trigger_ratio',1),'entity_get_distance':('read_distance',2),
            'func_800574FC':('vertical',3),'func_800574C4':('lateral',3),
            'func_800573A8':('translation',2),'func_8001CEB4':('rotation',3),
            'func_800662B4':('animation_stop',1),'dream_sys_clear_callbacks':('clear_callbacks',2),
            'dream_sys_set_move_callback':('set_move_callback',2),'dream_sys_set_view_mode':('set_view_mode',2),
            'base_class_notify':('notify',2),'func_8001D344':('held_visible',2)}
    def hook(self,cpu,address,size,unused):
        if self.native_entries.get(address & n.MASK)=='entity_get_distance':
            target=cpu.reg_read(n.reg.UC_MIPS_REG_RA) & n.MASK
            if target in self.pending_returns:raise ValueError('Overlapping observed distance return.')
            self.pending_returns[target]=('distance',None)
        super().hook(cpu,address,size,unused)
    def run(self,case,reset=True):
        actual=super().run(case,reset)
        return dict(actual,rng_trace=self.rng_trace)

def compare(machine,case,previous=None):
    model,commands=expected(case,previous)
    actual=machine.run(case,reset=previous is None)
    differing=[name for name in model if model[name]!=actual[name]]
    if differing or commands!=machine.adapter.commands:
        return False,{'case':case,'differing':differing,'expected_trace':model['trace'],'actual_trace':actual['trace'],
            'expected_commands':commands,'actual_commands':machine.adapter.commands,
            'buffer_differences':{name:[(i,x,y) for i,(x,y) in enumerate(zip(model[name],actual[name])) if x!=y][:16]
                for name in differing if isinstance(model[name],bytes)}},actual
    return True,None,actual

def cases():
    base=base_case()
    moods=((-4,-4,0,0,0),(-3,-4,0,0,0),(-4,-3,0,0,0),(0,0,0,0,0),
        (3,3,0,0,0),(4,4,0,0,0),(4,-4,0,0,0),(-4,4,0,0,0),
        (1,-1,7,-7,2),(-128,127,0,0,0),(0,0,-20,20,3),(0,0,20,-20,3))
    for mood,state,seed,measured,mode in itertools.product(moods,(0,11,12),(0,1,42),(1023,1024),(1,2)):
        yield 'initial_mood_rng_and_control',dict(base,tick=0,chunk_mood=mood,state=state,
            seed=seed,position=(measured,0,0),player_position=(0,0,0),move_mode=mode)
    for state,measured,axis,mode,timer in itertools.product((11,12),(0,1,1023,1024,1025),range(4),(0,1,2),(0,99,100,101)):
        positions=((measured,33,0),(-measured,-20,0),(0,0,measured),(0,100,-measured))
        yield 'strict_distance_and_control_modes',dict(base,state=state,position=positions[axis],
            player_position=(0,0,0),move_mode=mode,timer=timer)
    ticks=(-0x80000000,-1,0,1,9,10,11,19,20,39,40,49,50,59,60,79,80,99,100,499,500,501,0x7fffffff)
    eulers=((0,0,0),(0,1024,0),(128,777,-256),(-32768,32767,-1),(4095,-4095,4096))
    positions=((1000,2000,3000),(0x7fffffff,0,-0x80000000),(-0x80000000,17,0x7fffffff))
    for state,tick,euler,position in itertools.product((13,14),ticks,eulers,positions):
        yield 'timed_motion_pose_and_word_wrap',dict(base,state=state,tick=tick,seed=1,
            euler=euler,player_euler=euler,position=position,player_position=position)
    for state,tick in itertools.product((0,1,11,12,13,14),(-1,1,10,50,500)):
        for timer,scale in itertools.product((-0x80000000,-101,-100,-1,0,1,99,100,101,0x7fffffff),(1,100,1000)):
            yield 'signed_periodic_clock_and_radius',dict(base,state=state,tick=tick,timer=timer,proximity_scale=scale)
    for flags,position in itertools.product((0,0x7fffffff,0x80000000,0xffffffff),positions):
        yield 'held_object_flag_polarity',dict(base,state=14,tick=10,held_flags=flags,position=position)

def histories():
    for mode in (1,2):
        case=dict(base_case(),tick=0,position=(1023,0,0),player_position=(0,0,0),
            chunk_mood=(-4,-4,0,0,0),move_mode=mode)
        yield 'yellow_control_lock_mode_'+str(mode),case,502
    yield 'rng_lift_roll_and_held_object',dict(base_case(),tick=0,seed=0,
        position=(1023,0,0),player_position=(0,0,0)),102

def hand_checks(bridge):
    """Literal native observations checked without invoking expected()."""
    rows=[]
    entries=Counter()
    def word(result,name,offset):return struct.unpack_from('<i',result[name],offset)[0]
    def check(label,updates,predicate):
        machine=Machine(bridge)
        actual=machine.run(dict(base_case(),**updates))
        if not predicate(actual):raise ValueError('Independent native hand check failed: '+label)
        entries.update(machine.entries);rows.append({'name':label,'passed':True})
    check('yellow_arms_without_rng',dict(tick=0,chunk_mood=(-4,-4,0,0,0)),
          lambda x:word(x,'entity',0x44)==11 and word(x,'context',28)==12 and x['rng_seed']==0 and not x['rng_trace'])
    check('non_yellow_zero_seed_selects_twelve',dict(tick=0),
          lambda x:word(x,'entity',0x44)==12 and x['rng_seed']==12345 and x['rng_trace']==[['rand',0]])
    check('non_yellow_one_seed_preserves_zero',dict(tick=0,seed=1),
          lambda x:word(x,'entity',0x44)==0 and x['rng_seed']==1103527590)
    for distance_value,expected_state in ((1023,13),(1024,11)):
        check('strict_1024_boundary_'+str(distance_value),dict(state=11,position=(distance_value,0,0),player_position=(0,0,0)),
              lambda x,s=expected_state:word(x,'entity',0x44)==s)
    check('move_mode_two_resets_view_activity_only',dict(state=11,position=(0,0,0),player_position=(0,0,0),move_mode=2),
          lambda x:word(x,'dream',0x98)==0 and word(x,'dream',0x9c)==0 and word(x,'dream',0xc4)==0
              and word(x,'dream',0xc8)==0 and x['dream'][0x80:0x84]==bytes([0xa6])*4)
    check('tick_49_player_y_minus_twenty',dict(state=13,tick=49),lambda x:word(x,'player_coordinate',0x1c)==8980)
    check('tick_50_player_x_minus_five',dict(state=13,tick=50),lambda x:word(x,'player_coordinate',0x18)==-5)
    check('tick_60_player_x_plus_five',dict(state=13,tick=60),lambda x:word(x,'player_coordinate',0x18)==5)
    check('tick_500_requests_end',dict(state=13,tick=500),lambda x:x['trace']==[['notify',n.ENTITY,12]])
    check('tick_501_does_not_repeat_end',dict(state=13,tick=501),lambda x:x['trace']==[])
    check('tick_nine_entity_y_plus_two_hundred',dict(state=14,tick=9),lambda x:word(x,'coordinate',0x1c)==2200)
    check('tick_ten_roll_motion_and_commands',dict(state=14,tick=10),lambda x:
        struct.unpack_from('<3i',x['coordinate'],0x18)==(2500,-400,3000)
        and struct.unpack_from('<3h',x['pose'],0x10)==(0,0,-1024)
        and word(x,'entity',0x44)==1 and word(x,'context',28)==18 and word(x,'context',48)==3
        and word(x,'context',16)==0 and struct.unpack_from('<I',x['held_object'],0x10)[0]==0x92345678)
    for flags in (0,0xffffffff):
        check('held_flag_preserves_other_bits_'+str(flags),dict(state=14,tick=10,held_flags=flags),
              lambda x,f=flags:struct.unpack_from('<I',x['held_object'],0x10)[0]==f|0x80000000)
    return rows,entries

def instruction(function,opcode,immediate):
    row=next(row for row in FUNCTIONS if row['function']==function)
    start=int(row['address'],16);raw=n.h.target(start,row['bytes'])
    found=[(start+offset,word) for offset in range(0,len(raw),4)
        if (word:=struct.unpack_from('<I',raw,offset)[0])>>26==opcode and word>>21 & 31!=29 and word & 0xffff==immediate]
    if not found:raise ValueError('Reviewed fault instruction not found: '+function)
    return found[0]

def controls(bridge):
    specifications=[
        ('wrong_distance_boundary',CALLBACK,10,1024,1025,dict(state=11,position=(1024,0,0),player_position=(0,0,0))),
        ('wrong_fifty_tick_boundary',CALLBACK,10,50,51,dict(state=13,tick=50)),
        ('late_end_request',CALLBACK,13,500,501,dict(state=13,tick=500)),
        ('wrong_rotated_lateral_distance',CALLBACK,13,2400,2399,dict(state=14,tick=10)),
        ('wrong_held_flag_polarity','func_8001D344',11,1,0,dict(state=14,tick=10,held_flags=0xffffffff)),
        ('wrong_rng_increment','rand',9,12345,12346,dict(tick=0)),
    ]
    rows=[]
    for label,function,opcode,immediate,replacement,updates in specifications:
        address,word=instruction(function,opcode,immediate)
        case=dict(base_case(),**updates)
        machine=Machine(bridge,{address:struct.pack('<I',(word & 0xffff0000)|replacement)})
        model,commands=expected(case);actual=machine.run(case)
        differing=[name for name in model if model[name]!=actual[name]]
        hits=machine.hits[address & n.MASK]
        if not hits or (not differing and commands==machine.adapter.commands):
            raise ValueError('Native corruption escaped detection: '+label)
        rows.append({'name':label,'function':function,'address':hex(address),'executions':hits,'differing_outputs':differing})
    address,word=instruction(CALLBACK,43,28)
    machine=Machine(bridge,{address:struct.pack('<I',(word & 0xffff0000)|0x3000)})
    try:machine.run(dict(base_case(),tick=0))
    except ValueError as error:
        if 'escaped declared buffers' not in str(error) or machine.rejected_store is None:raise
        rows.append({'name':'escaped_command_store','detected':True,**machine.rejected_store})
    else:raise ValueError('An escaped native store was not rejected.')
    return rows

def verify(output,executable,runtime):
    global pairs
    output=Path(output).resolve()
    if output.exists() or not output.is_relative_to((ROOT/'.decomp-lab').resolve()):
        raise ValueError('Use a fresh private .decomp-lab output directory.')
    dependencies=n.evidence_dependencies('tools/verify_hanged_woman.py','docs/hanged-woman-function-ranges.json',
        'tools/verify_astronaut.py','tools/verify_npc_proximity.py','tools/verify_npc_spatial.py',
        'tools/verify_scripted_ai.py','tools/verify_locomotive_scripts.py','tools/verify_render_gte.py',
        'tools/verify_render_rotation.py','tools/nymashock_gte_bridge.cs','src/scene/scene_node.c',
        'src/base/object_math.c','src/dream/dream_sys.c','PROJECT_OBJECTIVE.md')
    before={path:hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    n.initialize_backend(n.load_program(FUNCTIONS));pairs=r.table_pairs(n.h)
    for name,data in DATA.items():
        if n.h.target(n.h.symbols[name],len(data))!=data:raise ValueError('Original data changed: '+name)
    table=n.h.target(n.h.symbols['g_ENTITY_TABLE'],2080);binding=table[58*16:59*16]
    if (hashlib.sha256(binding).hexdigest()!='9f3c0d04364cbea8771e9131030e33e7c85651e2c44921360a228c7610df5d79'
            or struct.unpack_from('<I',binding,12)[0]!=n.h.symbols[CALLBACK] or struct.unpack_from('<b',binding,10)[0]!=30):
        raise ValueError('Original property binding changed.')
    backend=scripts.backend_identity();executable=Path(executable).resolve(strict=True)
    bridge_sha=hashlib.sha256(executable.read_bytes()).hexdigest()
    output.mkdir();bridge=g.NativeGteBridge(executable,runtime,output/'gte.log')
    seen=set();counts=Counter();entries=Counter();inputs=hashlib.sha256();outputs=hashlib.sha256()
    duplicates=0;started=time.monotonic();history_reports=[]
    def checked(machine,case,previous=None):
        ok,failure,actual=compare(machine,case,previous)
        if not ok:
            (output/'failure.json').write_text(json.dumps(failure,indent=2))
            raise ValueError('Original script/model mismatch; retained private failure.json')
        outputs.update(repr(actual).encode());return actual
    try:
        machine=Machine(bridge)
        for group,case in cases():
            key=input_key(case)
            if key in seen:duplicates+=1;continue
            seen.add(key);inputs.update(len(key).to_bytes(4,'little')+key)
            checked(machine,case);counts[group]+=1
        entries.update(machine.entries)
        print(len(seen),'distinct initialized fixtures passed',flush=True)
        for label,base,count in histories():
            machine=Machine(bridge);previous=None;tick=0
            for timer in range(count):
                case=dict(base,timer=timer,tick=tick)
                previous=checked(machine,case,previous)
                tick=p.s32(struct.unpack_from('<i',previous['entity'],0xfc)[0]+1)
            entries.update(machine.entries)
            history_reports.append({'name':label,'calls':count,'final_state':struct.unpack_from('<i',previous['entity'],0x44)[0],
                                    'final_rng_seed':previous['rng_seed']})
        hands,hand_entries=hand_checks(bridge);entries.update(hand_entries)
        positive_commands=bridge.count;faults=controls(bridge)
    finally:bridge.close()
    if (scripts.backend_identity()!=backend or hashlib.sha256(executable.read_bytes()).hexdigest()!=bridge_sha
            or (ROOT/n.configure.ROM).read_bytes()!=n.h.ROM or (ROOT/n.configure.EXE).read_bytes()!=n.h.ROM
            or n.check_build_current(ROOT) is not True
            or any(hashlib.sha256(path.read_bytes()).hexdigest()!=sha for path,sha in before.items())):
        raise ValueError('Source/build/backend inputs changed during verification.')
    report={'status':'passed_bounded_original_hanged_woman','callbacks':[CALLBACK],
        'distinct_fixture_cases':len(seen),'duplicate_initialized_inputs_skipped':duplicates,'cases_by_group':dict(counts),
        'histories':history_reports,'native_history_calls':sum(row['calls'] for row in history_reports),
        'independent_native_hand_checks':hands,'property_binding':{'index':58,'proximity':30,'record_sha256':hashlib.sha256(binding).hexdigest()},
        'property_table_sha256':hashlib.sha256(table).hexdigest(),'native_functions':FUNCTIONS,
        'executed_native_entry_counts':dict(entries),'native_gte_commands':positive_commands,
        'native_gte_control_commands':bridge.count-positive_commands,'dependency_output_stubs':0,
        'initialized_inputs_sha256':inputs.hexdigest(),'checked_buffers_sha256':outputs.hexdigest(),
        'negative_controls_detected':faults,'backend_identity':backend,'bridge_executable_sha256':bridge_sha,
        'nymashock_compressed_core_sha256':g.CORE_SHA256,
        'preserved_dependencies':[{'path':path.relative_to(ROOT).as_posix(),'sha256':sha} for path,sha in before.items()],
        'embedded_context_address':hex(CONTEXT),'embedded_context_bytes':84,
        'externally_supplied_history_fields':['tick_incremented_from_previous_native_tick','command_timer'],
        'canonical_original_and_build_equal':True,'source_promoted':False,'new_bounded_callbacks':1,
        'bounded_callback_total_before':43,'bounded_callback_total_after':44,
        'whole_callback_acceptances':0,'whole_feature_groups_accepted':0,'model_api_calls':0,
        'original_game_behavior_modified':False,'elapsed_seconds':round(time.monotonic()-started,3),
        'scope':'One original callback with embedded owner context, real property/mood/control/motion/held-node helpers and native GTE. '
            'Constructed meshless/colliderless graphs; no notification recipients. Clocks supplied outside engine dispatch. '
            'Player world-coordinate propagation is outside this profile. No natural encounter, delivered day-end event, rendering/audio or PS1 timing acceptance.'}
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path);parser.add_argument('--bridge',required=True,type=Path)
    parser.add_argument('--runtime',required=True);args=parser.parse_args()
    report=verify(args.output,args.bridge,args.runtime)
    print(json.dumps({key:report[key] for key in ('status','distinct_fixture_cases','native_history_calls','native_gte_commands')}))
    return 0

if __name__=='__main__':raise SystemExit(main())
