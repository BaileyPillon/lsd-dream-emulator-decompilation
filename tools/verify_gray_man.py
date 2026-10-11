"""Original Gray Man fixture model and scoped local native-code check.

Invoked by verify_native_ai.py --callback gray_man. Effect rendering,
allocation and movement have explicit contracts; no added in-game AI runs.
"""
import hashlib
import itertools
import json
import struct
import time

from tools import verify_native_ai as native

ROOT = native.ROOT
ENTITY, DREAM, CONTEXT, SOUND = native.ENTITY, native.DREAM, native.CONTEXT, native.SOUND
EFFECT = 0x102000
word, u32 = native.word, native.u32
NATIVE_FUNCTIONS = [
    {'function':'entity_gray_man', 'address':'0x80064618', 'bytes':192,
     'sha256':'3a8601ffa5169b93c0694e7e955036e906ec06a066569c650a51adf7e415a65a'},
    {'function':'entity_create_effect', 'address':'0x8005D108', 'bytes':228,
     'sha256':'0f497b7b3419abfad4ef1524623f5645fd161a8c84af680154615202d30f6723'},
    {'function':'effect_set_color_step', 'address':'0x8004001C', 'bytes':8,
     'sha256':'dea8127e64d9c93d9a4df51d3c54e9747090fea982aea0c75be5609a7b895eef'},
    {'function':'effect_start', 'address':'0x80040024', 'bytes':140,
     'sha256':'103995793cb7706b9b53835e04afe0c65df685a77706d6ef75f3d74ee248f50f'},
    {'function':'dream_sys_reset_flashback_list', 'address':'0x8005B8FC', 'bytes':8,
     'sha256':'e22f7599c96cbf0062f2b24b3f9c14f8892def27d2fabf06119056de9f912bd7'},
    *(record for record in native.NATIVE_FUNCTIONS if record['function'] in {
        'entity_disable_link','entity_stop_behaviour','entity_set_triggered',
        'func_8001D1A4','func_80065A5C','func_80066148','func_800662B4'}),
]


def slot(table, offset):
    return int.from_bytes(native.h.target(native.h.symbols[table] + offset, 4), 'little')


def fixtures(case):
    entity, dream, effect, context = [bytearray([seed] * size) for seed, size in
                                    [(0xD7,0x108),(0xA6,0x480),(0xB5,0xA0),(0xC4,0x60)]]
    for offset, value in [(0,native.h.symbols['g_ENTITY_VTABLE']), (0x50,case['color']),
                          (0x58,SOUND), (0x6C,0), (0x94,DREAM), (0xF0,1),
                          (0xF4,case['triggered']), (0xF8,1),
                          (0x100,EFFECT if case['existing'] else 0)]:
        word(entity, offset, value)
    word(dream, 0, native.h.symbols['g_DREAM_SYS_VTABLE'])
    word(dream, 0x46C, case['flashbacks'])
    for offset, value in [(0,native.h.symbols['g_EFFECT_VTABLE']), (0x0C,0),
                          (0x6C,case['effect_state']), (0x74,37)]:
        word(effect, offset, value)
    return entity, dream, effect, context


def expected(case):
    entity, dream, effect, context = fixtures(case)
    trace = []
    if case['triggered']:
        success = case['existing'] or not case['allocation_fails']
        if not case['existing']:
            trace.append(['effect_create', native.h.symbols['D_8008AC14'], 0, 0])
        if success:
            word(entity, 0x100, EFFECT)
            trace.append(['effect_attach', EFFECT, ENTITY, native.h.symbols['D_8008AC0C']])
            word(effect, 0x74, 10)
            if case['effect_state'] == 0:
                trace.append(['effect_activate', EFFECT, u32(case['color']), 7, 0])
                trace.append(['effect_color', EFFECT, 1, native.h.symbols['D_8006EA90'] + 21])
                word(effect, 0x6C, 1)
                word(effect, 0x74, -10)
            trace.append(['sound_entity_stop', SOUND, ENTITY + 0x9C])
            for offset in (0x8C,0x90,0xF0,0xF4,0xF8):
                word(entity, offset, 0)
            word(dream, 0x46C, 0)
    trace.append(['movement', ENTITY, u32(-30), 1])
    return {'entity':bytes(entity), 'dream':bytes(dream), 'effect':bytes(effect),
            'context':bytes(context), 'trace':trace}


class Machine(native.Machine):
    def __init__(self, code=None):
        self.stubs = {
            native.h.symbols['effect_create'] & native.MASK: 'effect_create',
            native.h.symbols['sound_entity_stop'] & native.MASK: 'sound_entity_stop',
            slot('g_EFFECT_VTABLE',0x4C) & native.MASK: 'effect_attach',
            slot('g_EFFECT_VTABLE',0xDC) & native.MASK: 'effect_activate',
            slot('g_EFFECT_VTABLE',0xB8) & native.MASK: 'effect_color',
            slot('g_ENTITY_VTABLE',0xC4) & native.MASK: 'movement',
        }
        if len(self.stubs) != 6:
            raise ValueError('Expected six distinct Gray Man dependency contracts.')
        self.entry_counts = {}
        super().__init__(code, native.h.symbols['entity_gray_man'] & native.MASK, NATIVE_FUNCTIONS)

    def hook(self, cpu, address, size, unused):
        address &= native.MASK
        if address in self.native_entries:
            name = self.native_entries[address]
            self.executed_native_functions.add(name)
            self.entry_counts[name] = self.entry_counts.get(name, 0) + 1
        name = self.stubs.get(address)
        if name is None:
            return
        args = [cpu.reg_read(getattr(native.reg,'UC_MIPS_REG_A' + str(i))) for i in range(4)]
        result = 0
        if name == 'effect_create':
            self.trace.append([name, *args[:3]])
            result = 0 if self.case['allocation_fails'] else EFFECT
        elif name == 'effect_activate':
            self.trace.append([name, *args])
            result = args[2]
        else:
            self.trace.append([name, *args[:2 if name == 'sound_entity_stop' else 3]])
        target = cpu.reg_read(native.reg.UC_MIPS_REG_RA)
        for i, register in enumerate(native.VOLATILE):
            cpu.reg_write(register, u32(0xBC000000 + 0x10203 * i))
        cpu.reg_write(native.reg.UC_MIPS_REG_V0, u32(result))
        cpu.reg_write(native.reg.UC_MIPS_REG_PC, target)

    def run(self, case):
        self.case, self.trace = case, []
        cpu, reg = self.cpu, native.reg
        buffers = fixtures(case)
        for address, data in zip((ENTITY,DREAM,EFFECT,CONTEXT), buffers):
            cpu.mem_write(address, bytes(data))
        cpu.mem_write(native.STACK - 0x200, bytes([0xCC]) * 0x400)
        saved = [u32(0xAB000000 + 0x10203 * i) for i in range(len(native.SAVED))]
        for register, value in zip(native.SAVED, saved):
            cpu.reg_write(register, value)
        for register, value in [(reg.UC_MIPS_REG_SP,native.STACK), (reg.UC_MIPS_REG_GP,0x8008A808),
                                (reg.UC_MIPS_REG_RA,native.END), (reg.UC_MIPS_REG_A0,ENTITY),
                                (reg.UC_MIPS_REG_A1,CONTEXT)]:
            cpu.reg_write(register, value)
        cpu.emu_start(self.start, native.END, count=30000)
        if (cpu.reg_read(reg.UC_MIPS_REG_PC) != native.END or
                cpu.reg_read(reg.UC_MIPS_REG_SP) != native.STACK or
                [cpu.reg_read(register) for register in native.SAVED] != saved):
            raise ValueError('Gray Man callback violated return/stack/saved-register expectations.')
        return {**{name:bytes(cpu.mem_read(address,len(buffer)))
                   for name,address,buffer in zip(('entity','dream','effect','context'),
                                                  (ENTITY,DREAM,EFFECT,CONTEXT),buffers)}, 'trace':self.trace}


def verify(destination):
    dependencies = native.evidence_dependencies('tools/verify_gray_man.py',
                                                'src/graphics/effect.c', 'src/graphics/effect.h')
    before = {path:hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    native.initialize_backend(native.load_program(NATIVE_FUNCTIONS))
    started = time.monotonic()
    machine = Machine()
    groups = {name:[] for name in ('inactive','new_allocation_failure','new_effect','existing_effect')}
    for triggered,existing,allocation_fails,state,flashbacks,color in itertools.product(
            (0,1,-1),(False,True),(False,True),(0,1,2,-1),(0,1,20,-1),(0,1,-1,0x1020304)):
        case = dict(triggered=triggered,existing=existing,allocation_fails=allocation_fails,
                    effect_state=state,flashbacks=flashbacks,color=color)
        group = ('inactive' if not triggered else 'existing_effect' if existing else
                 'new_allocation_failure' if allocation_fails else 'new_effect')
        groups[group].append(case)
    for group,cases in groups.items():
        for index,case in enumerate(cases):
            actual, model = machine.run(case), expected(case)
            if actual != model:
                failure = destination.with_name(destination.stem + '-failure-' + str(time.time_ns()) + '.json')
                with failure.open('x') as stream:
                    json.dump({'group':group,'index':index,'case':case,
                               'native':repr(actual),'model':repr(model)},stream,indent=2)
                raise ValueError('Native Gray Man callback disagrees with bounded model: ' + str(failure))
        print(group, len(cases), 'passed', flush=True)
    original = native.h.target(native.h.symbols['entity_gray_man'],192)
    caught = []
    controls = [
        ('wrong_movement',0x98,0x2405FFE2,0x2405FFE1,groups['inactive'][0]),
        ('skip_flashback_reset',0x88,0x0040F809,0x00000000,
         dict(triggered=1,existing=False,allocation_fails=False,effect_state=0,flashbacks=20,color=1)),
    ]
    for name,offset,expected_word,changed_word,case in controls:
        if struct.unpack_from('<I',original,offset)[0] != expected_word:
            raise ValueError('Negative control no longer identifies the canonical instruction: ' + name)
        changed = bytearray(original)
        struct.pack_into('<I',changed,offset,changed_word)
        if Machine(bytes(changed)).run(case) == expected(case):
            raise ValueError('Negative control was not detected: ' + name)
        caught.append({'name':name,'function_offset':offset,'expected_word':f'0x{expected_word:08X}',
                       'changed_word':f'0x{changed_word:08X}',
                       'execution_scope':'Private emulator memory; original executable and build unchanged.'})
    report = {'function':'entity_gray_man','entity_record':98,'status':'passed_bounded_original_npc_model',
              'canonical_executable_sha1':hashlib.sha1(native.h.ROM).hexdigest(),
              'original_and_current_build_equal':True,'original_behavior_modified':False,'model_api_calls':0,
              'backend':'Unicorn ' + native.unicorn.__version__,
              'native_cases':sum(map(len,groups.values())), 'case_groups':{name:len(cases) for name,cases in groups.items()},
              'negative_controls_detected':caught, 'native_functions':NATIVE_FUNCTIONS,
              'native_range_role':'Canonical byte inventory; entry execution is measured separately.',
              'executed_native_functions':sorted(machine.executed_native_functions),
              'native_entry_counts':machine.entry_counts, 'stubbed_calls':sorted(machine.stubs.values()),
              'producer_dependencies':[{'path':path.resolve().relative_to(ROOT).as_posix(),'sha256':before[path]}
                                       for path in dependencies],
              'callback_runtime_accepted':False,'original_feature_groups_accepted':0,
              'scope':'Original Gray Man callback and eleven downstream routines against an independent model. '
                      'Explicit effect allocation, attachment, activation/color, sound stop and movement contracts. '
                      'Empty actor child lists and null effect parent. Full entity/dream/effect/context buffers, '
                      'call order, stack restoration and saved registers checked. All inventoried native entries '
                      'executed; entry coverage does not imply full branch coverage. Excludes natural encounters, '
                      'nonnull-parent detach, nonempty child lists, actual effect rendering/motion, sound cleanup, '
                      'PS1 load delays/devices/cycles and whole-callback acceptance.',
              'elapsed_seconds':round(time.monotonic() - started,3)}
    if ((ROOT / native.configure.ROM).read_bytes() != native.h.ROM or
            (ROOT / native.configure.EXE).read_bytes() != native.h.ROM or
            native.check_build_current(ROOT) is not True):
        raise ValueError('Canonical source/build evidence changed during verification.')
    if any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path,digest in before.items()):
        raise ValueError('Verifier source/symbol evidence changed during verification.')
    with destination.open('x') as stream:
        json.dump(report,stream,indent=2)
        stream.write('\n')
    print(json.dumps({'report':str(destination),'native_cases':report['native_cases'],'passed':True}),flush=True)
