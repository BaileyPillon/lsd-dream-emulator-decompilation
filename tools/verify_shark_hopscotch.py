"""Bounded original Shark and Hopscotch Girl callbacks with embedded contexts.

Original MIPS helpers and native GTE execute; no dependency-output stubs.
Constructed meshless, childless graphs and inactive sound handles do not prove
natural encounters, engine scheduling, drawing, sound, or whole NPC parity.
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
from tools import verify_scripted_ai as scripts
from tools import verify_npc_proximity as p
from tools import verify_npc_spatial as spatial
from tools import verify_astronaut as a
from tools import verify_render_gte as g
from tools import verify_render_rotation as rotation

CALLBACKS = ('entity_shark', 'entity_hopscotch_girl')
FUNCTIONS = json.loads((ROOT / 'docs/shark-hopscotch-function-ranges.json').read_bytes())
CONTEXT = n.ENTITY + 0x9c
EXPECTED_BINDINGS = {
    'entity_shark': (34, 0, '047b9318a02dd924f473f9d067b07ca56905b095ee2369736885807dad803c99'),
    'entity_hopscotch_girl': (55, 20, '552f9a89764a609fbab371d4e244e46d7e842d33e60af749e4684ea02a1ed102'),
}
DATA = {'g_RotateYawNine': bytes.fromhex('000001000900010000000100'),
        'g_RotateYawNegNine': bytes.fromhex('00000100f7ff010000000100'),
        'g_OffsetOneTwoOne': bytes.fromhex('010001000200010001000100')}
pairs = None


def base_case(callback):
    index, radius, _ = EXPECTED_BINDINGS[callback]
    return dict(callback=callback, entity_id=index, proximity=radius, tick=1, timer=1,
                frame=1, state=0, seed=42, proximity_scale=1000, has_dream=True,
                position=(1000, 2000, 3000), player_position=(0, 9000, 0),
                scale=(4096, 4096, 4096), euler=(0, 0, 0))


def validate_case(case):
    callback = case['callback']
    if callback not in CALLBACKS:
        raise ValueError('Unsupported original callback.')
    for key in ('entity_id','proximity','tick','timer','frame','state','seed','proximity_scale'):
        if type(case[key]) is not int:
            raise ValueError('Native scalar fields must be integers.')
    if ((case['entity_id'], case['proximity']) != EXPECTED_BINDINGS[callback][:2]
            or not 1 <= case['proximity_scale'] <= 1000 or type(case['has_dream']) is not bool
            or not 0 <= case['seed'] <= 0xffffffff):
        raise ValueError('Use the original property binding and native input widths.')
    for key in ('tick','timer','frame','state'):
        if not -0x80000000 <= case[key] <= 0x7fffffff:
            raise ValueError('Use signed native callback words.')
    for key, lower, upper in (('position',-0x80000000,0x7fffffff),
                              ('player_position',-0x80000000,0x7fffffff),
                              ('scale',-0x80000000,0x7fffffff), ('euler',-32768,32767)):
        values = case[key]
        if (not isinstance(values,(list,tuple)) or len(values) != 3
                or any(type(value) is not int or not lower <= value <= upper for value in values)):
            raise ValueError('Use correctly sized native coordinate/pose vectors.')


def fixtures(case):
    validate_case(case)
    entity, dream, _ = scripts.fixtures(dict(case, duration=64, variant=0, action=0,
                                            ratio=0, nudge=-19))
    n.word(entity, 0x14, spatial.COORD)
    n.word(entity, 0x20, 0)
    n.word(entity, 0x4c, 0)
    n.word(entity, 0x94, n.DREAM if case['has_dream'] else 0)
    n.word(entity, 0x98, case['entity_id'])
    context = bytearray([0xc4] * 0x54)
    for offset, value in ((0,1),(4,case['timer']),(8,n.ENTITY),
            (12,n.h.symbols[case['callback']]),(20,case['proximity_scale']),
            (24,-1),(44,-1),(64,-1)):
        n.word(context, offset, value)
    entity[0x9c:0xf0] = context
    coordinate, pose = spatial.fixtures(case)
    n.word(dream, 0x0c, p.PLAYER_ROOT)
    n.word(dream, 0x14, p.PLAYER_COORD)
    player, root = bytearray([0x93] * 0x60), bytearray(0x40)
    n.word(root, 0, n.h.symbols['g_BASE_CLASS_VTABLE'])
    for index, value in enumerate(case['player_position']):
        n.word(player, 0x38 + index * 4, value)
    return {'entity': (n.ENTITY,entity), 'dream': (n.DREAM,dream),
            'context': (CONTEXT,context), 'coordinate': (spatial.COORD,coordinate),
            'pose': (spatial.POSE,pose), 'player_coordinate': (p.PLAYER_COORD,player),
            'player_root': (p.PLAYER_ROOT,root)}


def input_key(case):
    initialized = [(name,address,bytes(data).hex())
                   for name,(address,data) in sorted(fixtures(case).items())]
    return json.dumps([case['callback'],initialized,case['seed']],separators=(',',':')).encode()


def expected(case, previous=None):
    validate_case(case)
    initialized = fixtures(case)
    buffers = {name:bytearray(data if previous is None else previous[name])
               for name,(_address,data) in initialized.items()}
    entity, context, coordinate, pose = [buffers[name] for name in ('entity','context','coordinate','pose')]
    if previous is not None:
        n.word(entity,0xfc,case['tick'])
        n.word(entity,0x84,case['frame'])
        n.word(context,4,case['timer'])
    trace, rng_trace, commands = [], [], []
    seed = case['seed'] if previous is None else previous['rng_seed']
    tick = case['tick']
    if case['callback'] == 'entity_shark':
        turn = ('g_RotateYawNine' if n.u32(tick-400) < 10 else
                'g_RotateYawNegNine' if n.u32(tick-700) < 10 or n.u32(tick-830) < 4 else None)
        if turn is not None:
            raw = DATA[turn]
            trace.append(['rotation',n.ENTITY,0,n.h.symbols[turn],raw.hex()])
            for axis in range(3):
                numerator, denominator = struct.unpack_from('<hh',raw,axis*4)
                fixed = p.div(numerator*4096,denominator)
                old = struct.unpack_from('<h',pose,0x10+axis*2)[0]
                new = scripts.signed_remainder(old+p.div(fixed,360),4096)
                struct.pack_into('<h',pose,0x10+axis*2,p.s16(new))
            n.word(coordinate,0,0)
        elif tick >= 851:
            trace.extend((['disable_link',n.ENTITY],['sound_stop',n.SOUND,CONTEXT]))
            n.word(context,0,0)
            for offset in (0x8c,0x90,0xf0,0xf4,0xf8):
                n.word(entity,offset,0)
        amount = -60 if tick < 800 else -512
        trace.append(['forward',n.ENTITY,n.u32(amount),1])
        struct.pack_into('<h',entity,0x48,amount)
        matrix = struct.unpack('<9h',rotation.rotation_bytes(struct.unpack_from('<3h',pose,0x10),pairs))
        vector = (0,0,amount)
        moved, outputs = g.apply_model(matrix,vector)
        for word, part, output in zip(g.COMMANDS,g.split_vector(vector),outputs):
            commands.append({'inputs':{'cr':g.matrix_words(matrix),'ir':list(part),'command':word},'output':output})
        trace.append(['movement_translation',n.ENTITY,struct.pack('<3i',*moved).hex()])
        for axis,value in enumerate(moved):
            offset = 0x18+axis*4
            n.word(coordinate,offset,struct.unpack_from('<i',coordinate,offset)[0]+value)
        n.word(coordinate,0,0)
        trace.append(['motion_event',n.ENTITY,6])
    else:
        if tick == 0:
            rng_trace.append(['rand',seed])
            seed = n.u32(seed*0x41c64e6d+0x3039)
            if ((seed >> 16) & 0x7fff) % 3 == 0:
                trace.append(['scale',n.ENTITY,1,n.h.symbols['g_OffsetOneTwoOne']])
                struct.pack_into('<3i',pose,0,4096,8192,4096)
                n.word(coordinate,0,0)
        ratio = p.trigger_ratio(struct.unpack_from('<3i',coordinate,0x18),
            struct.unpack_from('<3i',buffers['player_coordinate'],0x38),20,
            struct.unpack_from('<i',context,20)[0],case['has_dream'])
        trace.extend((['read_trigger_ratio',n.ENTITY],['trigger_ratio',n.u32(ratio)]))
        n.word(context,16,ratio)
        frame = struct.unpack_from('<i',entity,0x84)[0]
        if frame >= 32:
            frame -= 32
        if frame in (9,17,23):
            n.word(context,28,19)
            if frame == 23:
                n.word(context,48,19)
    entity[0x9c:0xf0] = context
    return {**{name:bytes(data) for name,data in buffers.items()},'rng_seed':seed,
            'rng_trace':rng_trace,'trace':trace,'motion_scratch':bytes(8)}, commands


class Machine(a.Machine):
    def __init__(self, callback, bridge, patches=None):
        super().__init__(bridge,patches,callback=callback,native_functions=FUNCTIONS,
                         fixture_factory=fixtures,case_validator=validate_case,context_address=CONTEXT)
        self.observed = {'func_8001CEB4':('rotation',3),'func_8001D008':('scale',3),
            'func_8005748C':('forward',3),'func_800573A8':('translation',2),
            'func_800571F8':('motion_event',2),'entity_disable_link':('disable_link',1),
            'sound_entity_stop':('sound_stop',2),'entity_get_trigger_ratio':('read_trigger_ratio',1)}

    def run(self, case, reset=True):
        validate_case(case)
        if n.h.symbols[case['callback']] & n.MASK != self.start:
            raise ValueError('Case and native callback do not agree.')
        if not reset:
            self.cpu.mem_write(n.ENTITY+0x84,struct.pack('<I',n.u32(case['frame'])))
        result = super().run(case,reset)
        return dict(result,rng_trace=self.rng_trace)


def bindings():
    table = n.h.target(n.h.symbols['g_ENTITY_TABLE'],130*16)
    found = {}
    for callback, (index, radius, sha) in EXPECTED_BINDINGS.items():
        matching = [i for i in range(130) if struct.unpack_from('<I',table,i*16+12)[0] == n.h.symbols[callback]]
        raw = table[index*16:index*16+16]
        if matching != [index] or struct.unpack_from('<b',raw,10)[0] != radius or hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError('Original callback/property binding changed: '+callback)
        found[callback] = dict(index=index,proximity=radius,record_sha256=sha)
    return found, hashlib.sha256(table).hexdigest()


def cases(callback):
    base = base_case(callback)
    if callback == 'entity_shark':
        ticks = (-0x80000000,-1,0,1,398,399,400,401,408,409,410,411,699,700,709,710,
                 798,799,800,801,829,830,833,834,849,850,851,852,0x7fffffff)
        for tick in ticks:
            yield 'turn_speed_and_disable_boundaries',dict(base,tick=tick)
        for tick,euler,position,scale in itertools.product((399,400,409,410,700,709,710,800,830,833,834,851),
            ((0,0,0),(0,1024,0),(128,777,-256),(-32768,32767,-1),(4095,-4095,4096)),
            ((1000,2000,3000),(0x7fffffff,0,-0x80000000),(-0x80000000,17,0x7fffffff)),
            ((4096,4096,4096),(-4096,8192,2048))):
            yield 'native_pose_word_wrap_and_motion_mode',dict(base,tick=tick,euler=euler,position=position,scale=scale)
    else:
        seeds = (0,1,2,3,4,5,42,0x7fffffff,0x80000000,0xffffffff)
        frames = (-0x80000000,-1,0,8,9,10,16,17,18,22,23,24,31,32,33,40,41,42,48,49,50,54,55,56,64,73,0x7fffffff)
        for tick,frame,seed in itertools.product((-1,0,1),frames,seeds):
            yield 'initial_rng_and_single_frame_fold',dict(base,tick=tick,frame=frame,seed=seed)
        for measured,axis,scale,dream,frame in itertools.product((0,1,40959,40960,40961),range(4),
                (1,100,1000),(False,True),(9,23,55)):
            points=((measured,123,0),(-measured,-999,0),(0,0,measured),(0,0,-measured))
            yield 'original_radius_and_command_boundaries',dict(base,position=points[axis],proximity_scale=scale,
                                                              has_dream=dream,frame=frame)
        for position,player in itertools.product(((0x7fffffff,0,-1),(-0x80000000,0,1),(1000,2000,3000)),
                                                ((0,17,0),(-1,-9000,0x7fffffff))):
            yield 'signed_distance_word_boundaries',dict(base,position=position,player_position=player,frame=23)


def histories():
    shark = base_case('entity_shark')
    yield 'shark_first_tick_through_disable', [dict(shark,tick=i,timer=i,frame=i%64) for i in range(852)]
    for seed in (0,1):
        hop = dict(base_case('entity_hopscotch_girl'),seed=seed)
        yield 'hopscotch_frame_sequence_seed_'+str(seed), [dict(hop,tick=i,timer=i,frame=i%64) for i in range(96)]


def compare(machine,case,previous=None):
    model,commands = expected(case,previous)
    actual = machine.run(case,reset=previous is None)
    if actual != model or machine.adapter.commands != commands:
        differing = [name for name in model if actual[name] != model[name]]
        raise ValueError('Original callback disagrees with checked buffers/trace/GTE: '+repr((case,differing)))
    return actual


def hand_checks(bridge):
    """Literal native output checks, independent of expected()."""
    checks,entries = [],Counter()
    shark = Machine('entity_shark',bridge)
    for tick,yaw,speed,state in ((399,0,-60,1),(400,102,-60,1),(409,102,-60,1),
            (410,0,-60,1),(700,-102,-60,1),(709,-102,-60,1),(710,0,-60,1),
            (799,0,-60,1),(800,0,-512,1),(830,-102,-512,1),(833,-102,-512,1),
            (834,0,-512,1),(850,0,-512,1),(851,0,-512,0)):
        actual=shark.run(dict(base_case('entity_shark'),tick=tick))
        if (struct.unpack_from('<h',actual['pose'],0x12)[0] != yaw
                or struct.unpack_from('<h',actual['entity'],0x48)[0] != speed
                or struct.unpack_from('<i',actual['context'],0)[0] != state
                or actual['entity'][0x9c:0xf0] != actual['context']):
            raise ValueError('Literal native Shark boundary check failed.')
        checks.append(dict(kind='native_shark_boundary',tick=tick,yaw=yaw,speed=speed,context_state=state))
    entries.update(shark.entries)
    hop=Machine('entity_hopscotch_girl',bridge)
    for frame,selected,double in ((8,False,False),(9,True,False),(17,True,False),
            (23,True,True),(41,True,False),(55,True,True),(73,False,False),(87,False,False)):
        actual=hop.run(dict(base_case('entity_hopscotch_girl'),frame=frame))
        if ((struct.unpack_from('<i',actual['context'],28)[0] == 19) != selected
                or (struct.unpack_from('<i',actual['context'],48)[0] == 19) != double):
            raise ValueError('Literal native single frame-fold check failed.')
        checks.append(dict(kind='native_frame_fold',frame=frame,first_command=selected,second_command=double))
    for seed,result_seed,y in ((0,12345,8192),(1,1103527590,4096)):
        actual=hop.run(dict(base_case('entity_hopscotch_girl'),tick=0,seed=seed))
        if actual['rng_seed'] != result_seed or struct.unpack_from('<i',actual['pose'],4)[0] != y:
            raise ValueError('Literal native RNG/scale check failed.')
        checks.append(dict(kind='native_initial_rng_scale',seed=seed,result_seed=result_seed,scale_y=y))
    actual=hop.run(dict(base_case('entity_hopscotch_girl'),position=(0,0,40960),player_position=(0,0,0)))
    if struct.unpack_from('<i',actual['context'],16)[0] != 1024:
        raise ValueError('Literal native integer proximity quotient check failed.')
    checks.append(dict(kind='native_radius_integer_quotient',distance=40960,ratio=1024))
    entries.update(hop.entries)
    return checks,entries


def instruction(function,opcode,immediate):
    record=next(row for row in FUNCTIONS if row['function']==function)
    address=int(record['address'],16)
    code=n.h.target(address,record['bytes'])
    matches=[(address+offset,word) for offset in range(0,len(code),4)
             if (word:=struct.unpack_from('<I',code,offset)[0]) >> 26 == opcode
             and word >> 21 & 31 != 29 and word & 0xffff == immediate]
    if not matches:
        raise ValueError('Reviewed fault instruction was not found: '+function)
    return matches[0]


def controls(bridge):
    specifications=[
        ('shortened_first_turn_window','entity_shark','entity_shark',11,10,9,dict(tick=409)),
        ('late_fast_motion','entity_shark','entity_shark',10,800,801,dict(tick=800)),
        ('late_link_disable','entity_shark','entity_shark',10,851,852,dict(tick=851)),
        ('wrong_first_sound_command','entity_hopscotch_girl','entity_hopscotch_girl',43,28,32,dict(frame=9)),
        ('overwritten_proximity_scale','entity_hopscotch_girl','entity_hopscotch_girl',43,16,20,dict(frame=23)),
        ('wrong_rng_increment','rand','entity_hopscotch_girl',9,12345,12346,dict(tick=0,seed=0)),
        ('wrong_movement_halfword','func_80057534','entity_shark',41,72,74,dict(tick=800)),
    ]
    found=[]
    for label,function,callback,opcode,immediate,replacement,updates in specifications:
        address,word=instruction(function,opcode,immediate)
        case=dict(base_case(callback),**updates)
        model,commands=expected(case)
        faulty=Machine(callback,bridge,{address:struct.pack('<I',(word & 0xffff0000)|replacement)})
        actual=faulty.run(case)
        differences=[key for key in model if actual[key]!=model[key]]
        hits=faulty.hits[address & n.MASK]
        if not hits or (not differences and faulty.adapter.commands==commands):
            raise ValueError('A changed native instruction escaped detection: '+label)
        found.append(dict(kind=label,function=function,address=hex(address),
                          changed_instruction_executions=hits,changed_checked_fields=differences))
    address,word=instruction('entity_hopscotch_girl',43,28)
    faulty=Machine('entity_hopscotch_girl',bridge,{address:struct.pack('<I',(word & 0xffff0000)|0x3000)})
    try:
        faulty.run(dict(base_case('entity_hopscotch_girl'),frame=9))
    except ValueError as error:
        if 'escaped declared buffers' not in str(error) or faulty.rejected_store is None:
            raise
        found.append(dict(kind='escaped_command_store',detected=True,**faulty.rejected_store))
    else:
        raise ValueError('Escaped command write was not rejected.')
    return found


def verify(output,executable,runtime):
    global pairs
    output=Path(output).resolve()
    if not output.is_relative_to((ROOT/'.decomp-lab').resolve()) or output.exists():
        raise ValueError('Use a fresh evidence directory inside private .decomp-lab.')
    dependencies=n.evidence_dependencies('tools/verify_shark_hopscotch.py','docs/shark-hopscotch-function-ranges.json',
        'tools/verify_astronaut.py','tools/verify_npc_proximity.py','tools/verify_npc_spatial.py',
        'tools/verify_scripted_ai.py','tools/verify_locomotive_scripts.py','tools/verify_gunman_scripts.py',
        'tools/verify_render_gte.py','tools/verify_render_rotation.py','tools/nymashock_gte_bridge.cs',
        'src/scene/scene_node.c','src/base/object_math.c','src/sound/sound.c','PROJECT_OBJECTIVE.md')
    before={path:hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    n.initialize_backend(n.load_program(FUNCTIONS))
    for name,raw in DATA.items():
        if n.h.target(n.h.symbols[name],len(raw)) != raw:
            raise ValueError('Original data bytes changed: '+name)
    pairs=rotation.table_pairs(n.h)
    bound,table_hash=bindings()
    backend=scripts.backend_identity()
    executable=Path(executable).resolve(strict=True)
    bridge_hash=hashlib.sha256(executable.read_bytes()).hexdigest()
    output.mkdir(exist_ok=False)
    bridge=g.NativeGteBridge(executable,runtime,output/'gte.log')
    counts,entries=Counter(),Counter()
    input_digest,output_digest=hashlib.sha256(),hashlib.sha256()
    duplicates,started=0,time.monotonic()
    history_reports=[]
    try:
        for callback in CALLBACKS:
            machine=Machine(callback,bridge)
            seen=set()
            for group,case in cases(callback):
                key=input_key(case)
                if key in seen:
                    duplicates+=1
                    continue
                seen.add(key)
                actual=compare(machine,case)
                input_digest.update(len(key).to_bytes(4,'little')+key)
                output_digest.update(repr(actual).encode())
                counts[(callback,group)]+=1
            entries.update(machine.entries)
            print(callback,len(seen),'distinct fixtures passed',flush=True)
        for label,sequence in histories():
            machine=Machine(sequence[0]['callback'],bridge)
            previous=None
            for case in sequence:
                previous=compare(machine,case,previous)
                output_digest.update(repr(previous).encode())
            entries.update(machine.entries)
            history_reports.append(dict(kind=label,callback=sequence[0]['callback'],calls=len(sequence),
                first_tick=sequence[0]['tick'],last_tick=sequence[-1]['tick'],
                final_embedded_context_state=struct.unpack_from('<i',previous['context'],0)[0],
                final_rng_seed=previous['rng_seed']))
        hands,hand_entries=hand_checks(bridge)
        entries.update(hand_entries)
        commands_before_controls=bridge.count
        faults=controls(bridge)
    finally:
        bridge.close()
    if (scripts.backend_identity()!=backend or hashlib.sha256(executable.read_bytes()).hexdigest()!=bridge_hash
            or (ROOT/n.configure.ROM).read_bytes()!=n.h.ROM or (ROOT/n.configure.EXE).read_bytes()!=n.h.ROM
            or n.check_build_current(ROOT) is not True
            or any(hashlib.sha256(path.read_bytes()).hexdigest()!=sha for path,sha in before.items())):
        raise ValueError('Source/build/backend inputs changed during native verification.')
    report=dict(status='passed_bounded_original_shark_hopscotch',callbacks=list(CALLBACKS),
        distinct_fixture_cases=sum(counts.values()),duplicate_initialized_inputs_skipped=duplicates,
        cases_by_group=[dict(callback=cb,group=group,cases=count) for (cb,group),count in sorted(counts.items())],
        histories=history_reports,native_history_calls=sum(row['calls'] for row in history_reports),
        independent_native_hand_checks=hands,property_bindings=bound,property_table_sha256=table_hash,
        native_functions=FUNCTIONS,executed_native_entry_counts=dict(entries),
        native_gte_commands=commands_before_controls,native_gte_control_commands=bridge.count-commands_before_controls,
        dependency_output_stubs=0,initialized_inputs_sha256=input_digest.hexdigest(),checked_buffers_sha256=output_digest.hexdigest(),
        negative_controls_detected=faults,backend_identity=backend,bridge_executable_sha256=bridge_hash,
        nymashock_compressed_core_sha256=g.CORE_SHA256,
        preserved_dependencies=[dict(path=path.relative_to(ROOT).as_posix(),sha256=sha) for path,sha in before.items()],
        embedded_context_address=hex(CONTEXT),embedded_context_bytes=84,
        externally_injected_history_fields=['tick','timer','animation_frame'],
        canonical_original_and_build_equal=True,source_promoted=False,new_bounded_callbacks=2,
        bounded_callback_total_before=41,bounded_callback_total_after=43,
        whole_callback_acceptances=0,whole_feature_groups_accepted=0,model_api_calls=0,
        original_game_behavior_modified=False,elapsed_seconds=round(time.monotonic()-started,3),
        scope='Two original callbacks, original property rows, embedded owner/callback context, actual native helpers and GTE. '
              'Constructed meshless/childless graphs with inactive sound handles. Full buffers, ordered calls/GTE, ABI and write guards. '
              'History ticks, command timers and animation frames are supplied externally. '
              'No natural construction, active collider/audio handles, engine dispatch, rendering/audio, full encounters or PS1 timing acceptance.')
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--bridge',required=True,type=Path)
    parser.add_argument('--runtime',required=True)
    args=parser.parse_args()
    report=verify(args.output,args.bridge,args.runtime)
    print(json.dumps({key:report[key] for key in ('status','distinct_fixture_cases','native_history_calls','native_gte_commands')}))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
