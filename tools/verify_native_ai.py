"""Check bounded original Lion or Gray Man behavior using optional local Unicorn.

Actual RNG, link-disable and callback-clear code executes with explicit
geometry, notification, sound and movement contracts. This developer tool
does not invoke an AI model or modify the original game. Whole-NPC acceptance
requires separate encounter and runtime coverage.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import struct
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import configure
from tools.progress import check_build_current

CANONICAL_SHA1 = '76322eeade5ebb22dca57fdeac7d68c30f06308d'
MASK = 0x1FFFFFFF
END, STACK = 0x1F0000, 0x1E0000
ENTITY, DREAM, CONTEXT, SOUND = 0x100000, 0x101000, 0x103000, 0x104000
NATIVE_FUNCTIONS = [
    {
        "function": "entity_lion",
        "address": "0x80063144",
        "bytes": 868,
        "sha256": "ccb40e57452933aa818f8ca2e6f8b8833fb7cb2745694680436ce6700ec5e980"
    },
    {
        "function": "rand",
        "address": "0x80049480",
        "bytes": 40,
        "sha256": "4c54a1210ed147afe9b02657c9b12bdec5bb62c5584a2a9fef212567d0e04c0c"
    },
    {
        "function": "entity_disable_link",
        "address": "0x8005DA3C",
        "bytes": 112,
        "sha256": "730e458b8fcbb0fbdd92a20f7825c109697c11b5c02e57668ba54d424df14efd"
    },
    {
        "function": "entity_stop_behaviour",
        "address": "0x8005DB8C",
        "bytes": 100,
        "sha256": "4fa7621002bfabe6bf1c105adc34415e5f321cde133ecbc8dc1a00aee60dcaf0"
    },
    {
        "function": "entity_set_triggered",
        "address": "0x8005DAAC",
        "bytes": 80,
        "sha256": "a552a733f16261135c347927d25a256dbee266abca01f67fadfa3ade0ac1e8ae"
    },
    {
        "function": "func_8001D1A4",
        "address": "0x8001D1A4",
        "bytes": 96,
        "sha256": "01d1e2eb0c36882c91c2b5ad8d9751361591fa66a04698d46d5e913e4e20c861"
    },
    {
        "function": "func_80065A5C",
        "address": "0x80065A5C",
        "bytes": 132,
        "sha256": "278028b4201f68dc536800ede29a45e5905ef7ed8e5929059a19709f705d1f23"
    },
    {
        "function": "func_80066148",
        "address": "0x80066148",
        "bytes": 8,
        "sha256": "d9dfabd9e6747c7995e1c7196bfc94f3f7afbb7969fabd491b62b77a117875e4"
    },
    {
        "function": "func_800662B4",
        "address": "0x800662B4",
        "bytes": 8,
        "sha256": "9551f2e22426c0ef38657b0ae7289d100e7d495c6f17cd81cbc78cddb68f81ee"
    },
    {
        "function": "dream_sys_clear_callbacks",
        "address": "0x800595A8",
        "bytes": 104,
        "sha256": "fedcd6413050a1e563cb90214529e50b9a045b6f47e0f1dc93dd3a84f424422b"
    },
    {
        "function": "dream_sys_set_move_callback",
        "address": "0x800596E8",
        "bytes": 216,
        "sha256": "e0911b100ce2b5e6a7ea7d27d2516f24c0bd02b0c26cd3acecebdb3925323b78"
    },
    {
        "function": "dream_sys_set_view_callback",
        "address": "0x8005966C",
        "bytes": 124,
        "sha256": "8c1ddc757452838059838a6a588c8b41d57dcd14ce20c3f85e024e4112fd3a1f"
    }
]


def load_program(native_functions=None):
    """Require the unchanged reference, its matching build and named ranges."""
    from tools.inventory_vtables import parse_symbols
    original = (ROOT / configure.ROM).read_bytes()
    if hashlib.sha1(original).hexdigest() != CANONICAL_SHA1:
        raise ValueError('The original executable must match canonical SLPS_015.56.')
    if (ROOT / configure.EXE).read_bytes() != original or check_build_current(ROOT) is not True:
        raise ValueError('A current complete matching build is required; run configure.py and ninja check in WSL.')
    symbols = parse_symbols((ROOT / configure.MAP_FILE).read_text(),
                            [(ROOT / path).read_text() for path in (configure.UNDEF_FUNCS, configure.UNDEF_SYMS)])
    load = struct.unpack_from('<I', original, 0x18)[0]
    def target(address, size):
        offset = 0x800 + address - load
        if offset < 0x800 or offset + size > len(original):
            raise ValueError('Native function/table range lies outside the executable.')
        return original[offset:offset+size]
    for record in NATIVE_FUNCTIONS if native_functions is None else native_functions:
        if (symbols.get(record['function']) != int(record['address'],16) or
                hashlib.sha256(target(int(record['address'],16),record['bytes'])).hexdigest() != record['sha256']):
            raise ValueError('Native range/symbol evidence changed: '+record['function'])
    return SimpleNamespace(ROM=original, LOAD=load, symbols=symbols, target=target)


def initialize_backend(program):
    global h, unicorn, reg, Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
    global START, RNG, SAVED, VOLATILE, TABLES, STUBS
    try:
        import unicorn
        from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
        from unicorn import mips_const as reg
    except ImportError as error:
        raise ValueError('Optional Unicorn is missing; install requirements-analysis.txt in your WSL environment.') from error
    h = program
    START = h.symbols['entity_lion'] & MASK
    RNG = h.symbols['small__rand'] & MASK
    SAVED = [getattr(reg,'UC_MIPS_REG_S'+str(i)) for i in range(8)]+[reg.UC_MIPS_REG_FP]
    VOLATILE = [reg.UC_MIPS_REG_V1]+[getattr(reg,'UC_MIPS_REG_A'+str(i)) for i in range(4)]+[getattr(reg,'UC_MIPS_REG_T'+str(i)) for i in range(10)]
    TABLES = {name:h.symbols[name] for name in ('g_ENTITY_VTABLE','g_DREAM_SYS_VTABLE')}
    STUBS = make_stubs()
    if len(STUBS) != 9:
        raise ValueError('Expected nine distinct native dependency contracts.')

def u32(value):
    return value & 0xFFFFFFFF

def word(data, offset, value):
    struct.pack_into('<I', data, offset, u32(value))

def slot(table, offset):
    return int.from_bytes(h.target(TABLES[table]+offset, 4), 'little')

def fixtures(case):
    entity = bytearray([0xD7]*0x108)
    dream = bytearray([0xA6]*0xA00)
    context = bytearray([0xC4]*0x60)
    for offset, value in [(0, TABLES['g_ENTITY_VTABLE']), (0x28, case['offset']),
                          (0x44, case['state']), (0x58, SOUND), (0x6C, 0),
                          (0x94, DREAM), (0xF0, 1), (0xF4, case['triggered']),
                          (0xF8, 1), (0xFC, case['tick'])]:
        word(entity, offset, value)
    for offset, value in [(0, TABLES['g_DREAM_SYS_VTABLE']), (0x80, 0xABCD1000),
                          (0x84, 1), (0x98, 0xABCD2000), (0x9C, 1)]:
        word(dream, offset, value)
    word(context, 4, case['timer'])
    return entity, dream, context

def c_rem(value, divisor):
    quotient = abs(value)//divisor
    return value - (-quotient if value < 0 else quotient)*divisor

def expected(case):
    entity, dream, context = fixtures(case)
    trace = []
    seed, state, timer = u32(case['seed']), case['state'], case['timer']
    def rng():
        nonlocal seed
        trace.append(['rand', seed])
        seed = u32(seed*0x41C64E6D + 0x3039)
        return (seed >> 16) & 0x7FFF
    if case['tick'] == 0 and rng() & 1:
        state = rng() % 3
        word(entity, 0x44, state)
    if state != 0 and case['triggered'] != 0:
        if timer >= 61:
            timer = 0
            word(context, 4, timer)
        remainder = c_rem(timer, 20)
        if remainder == 0:
            for index, value in [(4,0), (7,23), (8,-1), (12,23), (13,-1), (17,23), (18,-2)]:
                word(context, index*4, value)
        elif remainder == 14:
            for index in (7,12,17):
                word(context, index*4, -2)
        trace.append(['orientation', ENTITY, DREAM, 1, 0, 0])
        if state == 1:
            trace.append(['scale', ENTITY, 0, h.symbols['g_OffsetEightSevenths']])
            movement = -374
            trace.append(['distance', ENTITY, DREAM])
            if case['distance'] < 512:
                trace.append(['sound_entity_stop', SOUND, ENTITY+0x9C])
                for offset in (0x8C, 0x90, 0xF0, 0xF4, 0xF8):
                    word(entity, offset, 0)
                word(entity, 0x44, 1)
        else:
            for offset in (0x80,0x84,0x98,0x9C):
                word(dream, offset, 0)
            trace.append(['orientation', DREAM, ENTITY, 1, 1, 0])
            if state == 2:
                trace.append(['distance', ENTITY, DREAM])
                movement = -96
                if case['distance'] < 2400:
                    word(entity, 0x44, 11)
                    trace.append(['notification', ENTITY, 12])
            else:
                movement = 0
    else:
        trace.append(['trigger_ratio', ENTITY])
        word(context, 16, case['ratio'])
        if c_rem(timer,22) == 0:
            word(context, 28, 28)
        if case['tick'] >= 501:
            trace.append(['orientation', ENTITY, DREAM, 1, 0, 0])
        trace.append(['distance', ENTITY, DREAM])
        if case['distance'] < 2048:
            trace.append(['dream_motion', DREAM, u32(-2048), 0])
        movement = -20
    trace.append(['movement', ENTITY, u32(movement), 1])
    if case['offset'] != 0:
        trace.append(['entity_motion', ENTITY, u32(-200), 0])
    return {'entity': bytes(entity), 'dream': bytes(dream), 'context': bytes(context),
            'rng_seed': seed, 'trace': trace}

def make_stubs():
    return {
        h.symbols['func_8001EACC'] & MASK: ('orientation', 5),
        h.symbols['sound_entity_stop'] & MASK: ('sound_entity_stop', 2),
        slot('g_ENTITY_VTABLE', 0x48) & MASK: ('scale', 3),
        slot('g_ENTITY_VTABLE', 0x144) & MASK: ('distance', 2),
        slot('g_ENTITY_VTABLE', 0x148) & MASK: ('trigger_ratio', 1),
        slot('g_ENTITY_VTABLE', 0x30) & MASK: ('notification', 2),
        slot('g_ENTITY_VTABLE', 0xD0) & MASK: ('movement', 3),
        slot('g_ENTITY_VTABLE', 0xCC) & MASK: ('entity_motion', 3),
        slot('g_DREAM_SYS_VTABLE', 0xC4) & MASK: ('dream_motion', 3),
    }

class Machine:
    def __init__(self, code=None, start=None, native_functions=None):
        self.start = START if start is None else start
        functions = NATIVE_FUNCTIONS if native_functions is None else native_functions
        self.native_entries = {int(record['address'],16) & MASK: record['function'] for record in functions}
        self.executed_native_functions = set()
        self.cpu = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
        self.cpu.mem_map(0, 0x200000)
        self.cpu.mem_write(h.LOAD & MASK, h.ROM[0x800:])
        if code is not None:
            self.cpu.mem_write(self.start, code)
        self.cpu.hook_add(UC_HOOK_CODE, self.hook)

    def hook(self, cpu, address, size, unused):
        address &= MASK
        if address in self.native_entries:
            self.executed_native_functions.add(self.native_entries[address])
        if address == h.symbols['rand'] & MASK:
            self.trace.append(['rand', int.from_bytes(cpu.mem_read(RNG,4),'little')])
        entry = STUBS.get(address)
        if entry is None:
            return
        name, count = entry
        args = [cpu.reg_read(getattr(reg, 'UC_MIPS_REG_A'+str(i))) for i in range(4)]
        if count == 5:
            args.append(int.from_bytes(cpu.mem_read(cpu.reg_read(reg.UC_MIPS_REG_SP)+0x10, 4), 'little'))
        self.trace.append([name, *args[:count]])
        result = self.case['distance'] if name == 'distance' else self.case['ratio'] if name == 'trigger_ratio' else 0
        target = cpu.reg_read(reg.UC_MIPS_REG_RA)
        for i, register in enumerate(VOLATILE):
            cpu.reg_write(register, u32(0xBC000000+0x10203*i))
        cpu.reg_write(reg.UC_MIPS_REG_V0,u32(result))
        cpu.reg_write(reg.UC_MIPS_REG_PC,target)

    def run(self, case):
        self.case, self.trace = case, []
        cpu = self.cpu
        for address, data in zip((ENTITY,DREAM,CONTEXT),fixtures(case)):
            cpu.mem_write(address,bytes(data))
        cpu.mem_write(RNG,struct.pack('<I',u32(case['seed'])))
        cpu.mem_write(STACK-0x200,bytes([0xCC])*0x400)
        expected_saved = [u32(0xAB000000+0x10203*i) for i in range(len(SAVED))]
        for register,value in zip(SAVED,expected_saved):
            cpu.reg_write(register,value)
        for register,value in [(reg.UC_MIPS_REG_SP,STACK),(reg.UC_MIPS_REG_GP,0x8008A808),
                               (reg.UC_MIPS_REG_RA,END),(reg.UC_MIPS_REG_A0,ENTITY),(reg.UC_MIPS_REG_A1,CONTEXT)]:
            cpu.reg_write(register,value)
        cpu.emu_start(self.start,END,count=30000)
        assert cpu.reg_read(reg.UC_MIPS_REG_PC) == END
        assert cpu.reg_read(reg.UC_MIPS_REG_SP) == STACK
        assert [cpu.reg_read(r) for r in SAVED] == expected_saved
        return {'entity': bytes(cpu.mem_read(ENTITY,0x108)), 'dream': bytes(cpu.mem_read(DREAM,0xA00)),
                'context': bytes(cpu.mem_read(CONTEXT,0x60)),
                'rng_seed': int.from_bytes(cpu.mem_read(RNG,4),'little'), 'trace': self.trace}

def evidence_dependencies(*additional_sources):
    return [Path(__file__), ROOT / 'tools/inventory_vtables.py', ROOT / 'tools/progress.py',
                    ROOT / 'configure.py', ROOT / 'requirements-analysis.txt',
                    ROOT / configure.MAP_FILE, ROOT / configure.UNDEF_FUNCS, ROOT / configure.UNDEF_SYMS,
                    ROOT / 'src/scene/entity.c', ROOT / 'src/scene/entity.h',
                    ROOT / 'src/dream/dream_sys.c', ROOT / 'src/dream/dream_sys.h',
                    ROOT / 'src/scene/actor.c', ROOT / 'src/base/transform.c',
                    ROOT / 'asm/nonmatchings/psyq/libc/rand/rand.s',
                    *(ROOT / source for source in additional_sources)]


def verify(destination):
    dependencies = evidence_dependencies()
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    initialize_backend(load_program())
    started = time.monotonic()
    base = dict(tick=1,state=0,triggered=0,timer=1,distance=4096,offset=0,seed=0,ratio=99)
    groups = {
        'rng': [dict(base,tick=0,state=state,triggered=triggered,timer=20,seed=seed,distance=distance)
                for state,triggered,seed,distance in itertools.product(
                    (0,1,2,11),(0,1),(0,1,2,3,4,42,0x7FFFFFFF,0xFFFFFFFF),(511,512,2399,2400))],
        'active_animation': [dict(base,state=state,triggered=triggered,timer=timer,distance=distance)
                for state,triggered,timer,distance in itertools.product(
                    (1,2,11,-1),(1,-1),(-40,-20,-1,0,1,13,14,19,20,21,40,60,61,80),
                    (-1,511,512,2047,2048,2399,2400,4096))],
        'inactive': [dict(base,state=state,triggered=triggered,timer=timer,tick=tick,distance=distance,ratio=ratio)
                for state,triggered,timer,tick,distance,ratio in itertools.product(
                    (0,1),(0,),(-44,-1,0,21,22,44),(1,500,501),(-1,2047,2048,4096),(-1,0,256))],
        'motion_offset': [dict(base,state=state,triggered=triggered,offset=offset,distance=511)
                for state,triggered,offset in itertools.product((0,1,2,11),(0,1),(-1,1,0x7FFFFFFF))],
    }
    machine = Machine()
    for group,cases in groups.items():
        for index,case in enumerate(cases):
            actual, model = machine.run(case), expected(case)
            if actual != model:
                failure = destination.with_name(destination.stem+'-failure-'+str(time.time_ns())+'.json')
                with failure.open('x') as stream:
                    json.dump({'group':group,'index':index,'case':case,'native':repr(actual),'model':repr(model)},stream,indent=2)
                raise AssertionError('Native Lion callback disagrees with bounded model: '+str(failure))
        print(group,len(cases),'passed',flush=True)
    caught = []
    original = h.target(h.symbols['entity_lion'],868)
    controls = [
        ('distance_boundary',0x17C,0x28420200,0x28420201,dict(base,state=1,triggered=1,distance=512)),
        ('timer_boundary',0x94,0x2842003D,0x2842003E,dict(base,state=1,triggered=1,timer=61)),
        ('state_two_movement',0x210,0x2411FFA0,0x2411FF9F,dict(base,state=2,triggered=1,distance=2399)),
    ]
    for name,offset,expected_word,changed_word,case in controls:
        if struct.unpack_from('<I',original,offset)[0] != expected_word:
            raise ValueError('Negative control no longer identifies its canonical instruction: '+name)
        changed = bytearray(original)
        struct.pack_into('<I',changed,offset,changed_word)
        if Machine(bytes(changed)).run(case) == expected(case):
            raise ValueError('Negative control was not detected: '+name)
        caught.append({'name':name,'function_offset':offset,'expected_word':f'0x{expected_word:08X}',
                       'changed_word':f'0x{changed_word:08X}',
                       'execution_scope':'Private emulator memory; original executable and build unchanged.'})
    report = {'function':'entity_lion','status':'passed_bounded_original_npc_model',
              'canonical_executable_sha1':hashlib.sha1(h.ROM).hexdigest(),
              'original_and_current_build_equal':True,'original_behavior_modified':False,'model_api_calls':0,
              'backend':'Unicorn '+unicorn.__version__,'native_cases':sum(map(len,groups.values())),
              'case_groups':{name:len(cases) for name,cases in groups.items()},
              'negative_controls_detected':caught,
              'native_functions':NATIVE_FUNCTIONS,
              'native_range_role':'Canonical byte inventory; entry execution is measured separately.',
              'executed_native_functions':sorted(machine.executed_native_functions),
              'stubbed_calls':sorted(value[0] for value in STUBS.values()),
              'producer_dependencies':[{'path':path.resolve().relative_to(ROOT).as_posix(),'sha256':before[path]} for path in dependencies],
              'callback_runtime_accepted':False,'original_feature_groups_accepted':0,
              'scope':'Original Lion/RNG/link-disable/dream callback-clear machine code against an independent model under explicit distance, trigger-ratio, orientation, scale, sound, notification and movement contracts. Empty actor child lists and dream move mode 1. Checks full entity/dream/context buffers, final RNG seed, call order, stack restoration and saved registers. Does not validate natural encounter reachability, actual geometry/GTE, nonempty child lists, dream move mode 2, visible motion, hardware load delays/cycles or whole callback acceptance.',
              'elapsed_seconds':round(time.monotonic()-started,3)}
    if (ROOT / configure.ROM).read_bytes() != h.ROM or (ROOT / configure.EXE).read_bytes() != h.ROM or check_build_current(ROOT) is not True:
        raise ValueError('Canonical source/build evidence changed during verification.')
    if any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path, digest in before.items()):
        raise ValueError('Verifier source/symbol evidence changed during verification.')
    with destination.open('x') as stream:
        json.dump(report,stream,indent=2)
        stream.write('\n')
    print(json.dumps({'report':str(destination),'native_cases':report['native_cases'],'passed':True}),flush=True)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,help='New JSON report inside .decomp-lab; existing evidence is preserved.')
    parser.add_argument('--callback', choices=('lion', 'gray_man'), default='lion',
                        help='Original callback to check; analysis remains outside the game.')
    args=parser.parse_args(argv)
    try:
        destination=Path(args.output)
        if not destination.is_absolute():
            destination=ROOT / destination
        destination=destination.resolve()
        if not destination.is_relative_to((ROOT / '.decomp-lab').resolve()) or destination.suffix != '.json':
            raise ValueError('Output must be a new JSON report inside .decomp-lab.')
        if destination.exists():
            raise ValueError('Existing evidence is preserved; choose a new output path.')
        destination.parent.mkdir(parents=True,exist_ok=True)
        import os
        os.chdir(ROOT)
        if args.callback == 'gray_man':
            from tools.verify_gray_man import verify as verify_gray_man
            verify_gray_man(destination)
        else:
            verify(destination)
        return 0
    except (OSError,ValueError,AssertionError) as error:
        print('[!] '+str(error),file=sys.stderr)
        return 2


if __name__=='__main__':
    sys.exit(main())
