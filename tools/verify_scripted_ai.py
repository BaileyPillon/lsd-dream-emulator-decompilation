"""Bounded native checks for nine original timed/input-driven behavior scripts.

Actual original callback, RNG, action-read and behavior-stop code executes.
Geometry, motion, animation selection and sound have explicit contracts.
These checks do not add game behavior or certify whole NPC encounters.
"""
import hashlib
import itertools
import json
import struct
import time

from tools import verify_native_ai as native

SCRIPT_FUNCTIONS = [
    {'function':'entity_bird','address':'0x8005F368','bytes':236,'sha256':'89a93cbfdcaf8d25da98f263aaf407578121c0310ef37dd199590e519ce179e5'},
    {'function':'entity_rocket','address':'0x8005F454','bytes':240,'sha256':'9661bca320473fa46baea213abc90e6648e873e35c1f1b4fad3662ceea9cddb6'},
    {'function':'entity_horse','address':'0x8005F544','bytes':196,'sha256':'bad476d8a6f01d61fed03d831c9a4008240296171a105e8ba9a77ffbf360ff05'},
    {'function':'entity_ufo','address':'0x8005F608','bytes':204,'sha256':'dad1f71e4cd3ac57f6ddc02861258a4deed243b702be8c91dffe800872f39d9c'},
    {'function':'entity_dog','address':'0x800621A8','bytes':576,'sha256':'99dcfc0101d9f894bbf40e00a9bca541be13af0c3fd213cdc50257e95db34527'},
    {'function':'entity_can','address':'0x800636E4','bytes':160,'sha256':'d56b681a0343e4edde55f876ae28f78820d99802307b634d57929cbdd07bd49c'},
    {'function':'entity_car_water','address':'0x80063784','bytes':240,'sha256':'d5e7325194dc0f33b2bff0f5cf4adc893228d97366d03e8f55e3ad450edccee1'},
    {'function':'entity_fetus_walk','address':'0x80064450','bytes':152,'sha256':'27b3ecd6d26e02c3ac9edfa033c33a7e242b82a2ba8b62140301689b0bd69dfb'},
    {'function':'entity_fetus_jump','address':'0x800644E8','bytes':304,'sha256':'b0d0683099191ec4e33ea72594623628d2db6265b1d8beaa75d98c4a7196ff5b'},
]
ACTION_READ = {'function':'dream_sys_get_action_pressed','address':'0x8005931C','bytes':12,
               'sha256':'bc9d9a4597fc5c324c34fb0acc7dc1596cd1a7b617fc46f0fd1b7f63d9bf4061'}
NATIVE_FUNCTIONS = SCRIPT_FUNCTIONS + [ACTION_READ] + [
    record for record in native.NATIVE_FUNCTIONS if record['function'] in
    {'rand','entity_stop_behaviour','func_80066148','func_800662B4'}]


def signed_remainder(value, divisor):
    if not divisor:
        raise ValueError('Zero-duration division traps are outside these fixtures.')
    quotient = abs(value) // abs(divisor)
    if (value < 0) != (divisor < 0):
        quotient = -quotient
    return value - quotient * divisor


def fixtures(case):
    entity = bytearray([0xD7] * 0x108)
    dream = bytearray([0xA6] * 0xA00)
    context = bytearray([0xC4] * 0x60)
    for offset, value in [(0,native.h.symbols['g_ENTITY_VTABLE']), (0x44,case['state']),
                          (0x48,0x12340000 | (case['nudge'] & 0xFFFF)),
                          (0x58,native.SOUND), (0x6C,0), (0x70,0),
                          (0x7C,case['variant']), (0x80,case['duration']), (0x84,case['frame']),
                          (0x8C,1), (0x90,1), (0x94,native.DREAM),
                          (0xF0,1), (0xF4,1), (0xF8,1), (0xFC,case['tick'])]:
        native.word(entity,offset,value)
    native.word(dream,0,native.h.symbols['g_DREAM_SYS_VTABLE'])
    native.word(dream,0x74,case['action'])
    native.word(context,4,case['timer'])
    return entity,dream,context


def expected(callback, case):
    entity,dream,context = fixtures(case)
    trace = []
    seed = native.u32(case['seed'])
    timer,tick,state = case['timer'],case['tick'],case['state']
    def command(index, value):
        native.word(context,index*4,value)
    def call(name, *args):
        trace.append([name,*map(native.u32,args)])
    def ratio():
        call('trigger_ratio',native.ENTITY)
        command(4,case['ratio'])
    def random():
        nonlocal seed
        trace.append(['rand',seed])
        seed = native.u32(seed*0x41C64E6D + 0x3039)
        return (seed >> 16) & 0x7FFF
    def motion(name, amount, mode):
        call(name,native.ENTITY,amount,mode)
    def rotation(symbol):
        call('rotation',native.ENTITY,0,native.h.symbols[symbol])
    def stop():
        call('sound_entity_stop',native.SOUND,native.ENTITY+0x9C)
        for offset in (0x8C,0x90,0xF8):
            native.word(entity,offset,0)

    if callback == 'entity_bird':
        if signed_remainder(timer,15) == 0:
            ratio(); command(7,7); command(8,-2)
        call('scale',native.ENTITY,1,native.h.symbols['g_OffsetTwo'])
        rotation('g_RotateYawTwo')
        motion('forward',-512,0)
    elif callback == 'entity_rocket':
        command(4,0)
        if tick < 100:
            if signed_remainder(timer,3) == 0:
                command(7,22); command(8,1)
            motion('vertical',-64,0)
        elif tick < 300:
            for index,value in ((7,12),(8,-1),(12,12),(13,-1),(17,12),(18,-1)):
                command(index,value)
            motion('vertical',-256,0)
        else:
            rotation('g_RotatePitchEighth')
            motion('vertical',-512,0)
    elif callback == 'entity_horse':
        if signed_remainder(timer,case['duration']) == 0:
            ratio(); command(7,26)
        motion('lateral',-11520 if tick == 110 else -384,0)
    elif callback == 'entity_ufo':
        if signed_remainder(timer,70) == 0:
            command(4,0); command(7,27)
        motion('forward',-128,0)
        if tick < 100:
            motion('vertical',32,0)
        elif tick >= 301:
            motion('vertical',-32,0)
    elif callback == 'entity_dog':
        ratio()
        nudge = case['nudge']
        if timer == 0:
            nudge = -374 if random() & 1 else -192
            struct.pack_into('<h',entity,0x48,nudge)
        if state == 0:
            if signed_remainder(timer,10) == 0:
                command(7,28)
            rem = signed_remainder(timer,20)
            if rem == 0:
                for index,value in ((12,23),(13,-1),(17,23),(18,-1)):
                    command(index,value)
            elif rem == 14:
                command(12,-2); command(17,-2)
            if tick & 1 == 0 and case['action'] != 0:
                native.word(entity,0xFC,-1); native.word(entity,0x44,10); command(7,18)
            call('orientation',native.ENTITY,native.DREAM,1,0,0)
            motion('forward',nudge,1)
        elif state == 10:
            if tick < 8:
                rotation('g_RotateRollNine')
                call('translation',native.ENTITY,native.h.symbols['g_MoveUp8'])
            else:
                command(7,18); command(12,3); stop()
                native.word(entity,0x44,int(random() % 2 == 0))
    elif callback == 'entity_can':
        if signed_remainder(case['frame'],15) == 0:
            command(7,12); command(4,0); command(8,2)
        if tick == case['duration']:
            command(7,-2); stop(); native.word(entity,0x44,1)
    elif callback == 'entity_car_water':
        ratio()
        frame = case['frame']
        if frame < 40:
            for index,value in ((7,12),(8,-2),(17,5),(18,-1)):
                command(index,value)
        elif frame == 40:
            command(7,-2); command(17,-2)
        elif frame == 45:
            command(12,18); command(13,1)
        elif frame == 64:
            command(7,7)
        elif frame == 89:
            stop(); native.word(entity,0x44,1)
    elif callback == 'entity_fetus_walk':
        if tick == 0:
            call('motion_selection',native.ENTITY,3)
        elif tick == case['duration']:
            call('motion_selection',native.ENTITY,1)
        if case['variant'] == 1:
            motion('forward',-128,0)
    elif callback == 'entity_fetus_jump':
        if tick == 0:
            call('motion_selection',native.ENTITY,random() % 4)
        elif signed_remainder(tick,case['duration']) == 0:
            call('motion_selection',native.ENTITY,random() % 4)
            ratio()
            for index,value in ((7,22),(8,2),(9,64),(10,32)):
                command(index,value)
    else:
        raise ValueError('Unsupported callback: '+callback)
    return {'entity':bytes(entity),'dream':bytes(dream),'context':bytes(context),
            'rng_seed':seed,'trace':trace}


def cases_by_callback():
    base = dict(timer=1,tick=1,frame=1,duration=15,state=0,variant=0,action=0,
                seed=0,ratio=99,nudge=-19)
    def product(**fields):
        return [dict(base,**dict(zip(fields,values)))
                for values in itertools.product(*fields.values())]
    seeds = (0,1,2,42,0xFFFFFFFF)
    timers = (-70,-30,-20,-15,-1,0,1,3,14,15,20,69,70,71)
    dog = product(state=(0,),timer=(-20,-1,0,1,9,10,13,14,19,20,21,40),
                  tick=(-1,0,1,2,7,8,9),action=(0,1,-1),seed=seeds,ratio=(-1,99))
    dog += product(state=(-1,1,10),timer=(0,1,14,20),tick=(-1,0,1,7,8,9),seed=seeds)
    return {
        'entity_bird':product(timer=timers,ratio=(-1,0,99)),
        'entity_rocket':product(timer=timers,tick=(-1,0,1,98,99,100,101,299,300,301)),
        'entity_horse':product(timer=timers,tick=(109,110,111),duration=(1,3,15,70),ratio=(-1,0,99)),
        'entity_ufo':product(timer=timers,tick=(-1,0,1,99,100,101,299,300,301,302)),
        'entity_dog':dog,
        'entity_can':product(frame=(-31,-15,-1,0,1,14,15,16,29,30),
                             tick=(-1,0,1,14,15,16),duration=(1,15),state=(0,10)),
        'entity_car_water':product(frame=(-1,0,39,40,41,44,45,46,63,64,65,88,89,90),
                                   ratio=(-1,0,99),state=(0,10)),
        'entity_fetus_walk':product(tick=(-1,0,1,14,15,16),duration=(1,15),variant=(-1,0,1,2)),
        'entity_fetus_jump':product(tick=(-31,-30,-1,0,1,14,15,16,29,30,31),
                                   duration=(1,3,15),seed=seeds,ratio=(-1,99)),
    }


class Machine(native.Machine):
    def __init__(self, callback, code=None):
        self.entry_counts = {}
        self.stubs = {native.h.symbols['func_8001EACC'] & native.MASK: ('orientation',5),
                      native.h.symbols['sound_entity_stop'] & native.MASK: ('sound_entity_stop',2)}
        for offset,name,count in ((0x44,'rotation',3),(0x48,'scale',3),(0xBC,'translation',2),
                                  (0xC4,'forward',3),(0xCC,'vertical',3),(0xD0,'lateral',3),
                                  (0x128,'motion_selection',2),(0x148,'trigger_ratio',1)):
            self.stubs[native.slot('g_ENTITY_VTABLE',offset) & native.MASK] = (name,count)
        if len(self.stubs) != 10:
            raise ValueError('Expected ten distinct native dependency contracts.')
        super().__init__(code,native.h.symbols[callback] & native.MASK,NATIVE_FUNCTIONS)

    def hook(self, cpu, address, size, unused):
        address &= native.MASK
        if address in self.native_entries:
            name = self.native_entries[address]
            self.executed_native_functions.add(name)
            self.entry_counts[name] = self.entry_counts.get(name,0)+1
        if address == native.h.symbols['rand'] & native.MASK:
            self.trace.append(['rand',int.from_bytes(cpu.mem_read(native.RNG,4),'little')])
        contract = self.stubs.get(address)
        if contract is None:
            return
        name,count = contract
        args = [cpu.reg_read(getattr(native.reg,'UC_MIPS_REG_A'+str(i))) for i in range(4)]
        if count == 5:
            args.append(int.from_bytes(cpu.mem_read(cpu.reg_read(native.reg.UC_MIPS_REG_SP)+16,4),'little'))
        self.trace.append([name,*args[:count]])
        result = self.case['ratio'] if name == 'trigger_ratio' else 0
        target = cpu.reg_read(native.reg.UC_MIPS_REG_RA)
        for index,register in enumerate(native.VOLATILE):
            cpu.reg_write(register,native.u32(0xBC000000 + 0x10203*index))
        cpu.reg_write(native.reg.UC_MIPS_REG_V0,native.u32(result))
        cpu.reg_write(native.reg.UC_MIPS_REG_PC,target)

    def run(self, case):
        self.case,self.trace = case,[]
        cpu = self.cpu
        buffers = fixtures(case)
        for address,data in zip((native.ENTITY,native.DREAM,native.CONTEXT),buffers):
            cpu.mem_write(address,bytes(data))
        cpu.mem_write(native.RNG,struct.pack('<I',native.u32(case['seed'])))
        cpu.mem_write(native.STACK-0x200,bytes([0xCC])*0x400)
        saved = [native.u32(0xAB000000 + 0x10203*i) for i in range(len(native.SAVED))]
        for register,value in zip(native.SAVED,saved):
            cpu.reg_write(register,value)
        for register,value in ((native.reg.UC_MIPS_REG_SP,native.STACK),
                               (native.reg.UC_MIPS_REG_GP,0x8008A808),
                               (native.reg.UC_MIPS_REG_RA,native.END),
                               (native.reg.UC_MIPS_REG_A0,native.ENTITY),
                               (native.reg.UC_MIPS_REG_A1,native.CONTEXT)):
            cpu.reg_write(register,value)
        cpu.emu_start(self.start,native.END,count=30000)
        if (cpu.reg_read(native.reg.UC_MIPS_REG_PC) != native.END or
                cpu.reg_read(native.reg.UC_MIPS_REG_SP) != native.STACK or
                [cpu.reg_read(register) for register in native.SAVED] != saved):
            raise ValueError('Native callback violated return/stack/saved-register expectations.')
        return {**{name:bytes(cpu.mem_read(address,len(buffer)))
                   for name,address,buffer in zip(('entity','dream','context'),
                                                 (native.ENTITY,native.DREAM,native.CONTEXT),buffers)},
                'rng_seed':int.from_bytes(cpu.mem_read(native.RNG,4),'little'),'trace':self.trace}


def verify(destination):
    dependencies = native.evidence_dependencies('tools/verify_scripted_ai.py')
    before = {path:hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    native.initialize_backend(native.load_program(NATIVE_FUNCTIONS))
    started = time.monotonic()
    groups = cases_by_callback()
    entry_counts,contracts,controls,bindings = {},set(),[],{}
    table = native.h.target(native.h.symbols['g_ENTITY_TABLE'],130*16)
    for record in SCRIPT_FUNCTIONS:
        callback = record['function']
        address = int(record['address'],16)
        indices = [i for i in range(130) if struct.unpack_from('<I',table,i*16+12)[0] == address]
        if not indices:
            raise ValueError('Callback has no native property-table binding: '+callback)
        bindings[callback] = indices
        machine = Machine(callback)
        for index,case in enumerate(groups[callback]):
            actual,model = machine.run(case),expected(callback,case)
            if actual != model:
                failure = destination.with_name(destination.stem+'-failure-'+str(time.time_ns())+'.json')
                failure.write_text(json.dumps({'callback':callback,'case':case,
                    'native':repr(actual),'model':repr(model)},indent=2)+'\n')
                raise ValueError('Native callback/model disagreement: '+str(failure))
        for name,count in machine.entry_counts.items():
            entry_counts[name] = entry_counts.get(name,0)+count
        contracts.update(name for name,count in machine.stubs.values())
        original = native.h.target(address,record['bytes'])
        mutation = None
        for offset in range(0,len(original),4):
            word = struct.unpack_from('<I',original,offset)[0]
            if word >> 26 == 0x2B and (word >> 21) & 31 != 29 and word & 0xFFFF == 28:
                mutation = (offset,word,(word & 0xFFFF0000) | 32,'wrong_command_destination')
                break
        if callback == 'entity_fetus_walk':
            for offset in range(0,len(original),4):
                word = struct.unpack_from('<I',original,offset)[0]
                if word in (0x34050003,0x24050003):
                    mutation = (offset,word,(word & 0xFFFF0000) | 2,'wrong_motion_selection')
                    break
        if mutation is None:
            raise ValueError('No reviewed store/selection control found: '+callback)
        offset,word,changed_word,reason = mutation
        modified = bytearray(original)
        struct.pack_into('<I',modified,offset,changed_word)
        changed = Machine(callback,bytes(modified))
        for index,case in enumerate(groups[callback]):
            if changed.run(case) != expected(callback,case):
                controls.append({'callback':callback,'kind':reason,'function_offset':offset,
                    'expected_word':f'0x{word:08X}','changed_word':f'0x{changed_word:08X}',
                    'detected_case_index':index,'fixture':case,'scope':'Private Unicorn memory only.'})
                break
        else:
            raise ValueError('Negative control was not detected: '+callback)
        print(callback,len(groups[callback]),'passed',flush=True)
    if ((native.ROOT/native.configure.ROM).read_bytes() != native.h.ROM or
            (native.ROOT/native.configure.EXE).read_bytes() != native.h.ROM or
            native.check_build_current(native.ROOT) is not True or
            any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path,digest in before.items())):
        raise ValueError('Verifier source or canonical build changed during verification.')
    report = {'status':'passed_bounded_original_scripted_callbacks',
        'canonical_executable_sha1':hashlib.sha1(native.h.ROM).hexdigest(),
        'original_and_current_build_equal':True,'original_behavior_modified':False,'model_api_calls':0,
        'backend':'Unicorn '+native.unicorn.__version__, 'callback_count':len(groups),
        'native_cases':sum(map(len,groups.values())),
        'cases_by_callback':{name:len(cases) for name,cases in groups.items()},
        'native_property_record_bindings':bindings,'native_functions':NATIVE_FUNCTIONS,
        'executed_native_entry_counts':entry_counts,'dependency_contracts':sorted(contracts),
        'negative_controls_detected':controls,
        'producer_dependencies':[{'path':path.resolve().relative_to(native.ROOT).as_posix(),'sha256':digest}
                                 for path,digest in before.items()],
        'callback_runtime_accepted':False,'original_feature_groups_accepted':0,
        'scope':'Original callback/RNG/action-read/behavior-stop code versus separate script models. '
                'Full entity/dream/context buffers, RNG, ordered calls and ABI preservation. '
                'Empty actor-child fixtures and explicit geometry/motion/selection/sound contracts. '
                'Excludes natural encounters, lifetime histories, renderer/GTE, actual sound, '
                'zero-duration traps, physical devices and PS1 instruction/cycle timing.',
        'elapsed_seconds':round(time.monotonic()-started,3)}
    with destination.open('x') as stream:
        json.dump(report,stream,indent=2)
        stream.write('\n')
    print(json.dumps({'report':str(destination),'native_cases':report['native_cases'],
                      'callbacks':len(groups),'passed':True}),flush=True)
