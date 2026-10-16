"""Check original MOM/actor factory ownership against an independent event plan.

Object payloads, mapped geometry and complete animation state are not modeled.
This is a bounded analysis tool, not gameplay or whole-feature acceptance.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gc
import json
from pathlib import Path
import struct
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import configure
from tools import actor_child_model as child
from tools import verify_actor_children as common
from tools.actor_factory_model import OwnershipPlan
from tools.heap_model import PoolModel

MANAGER, POOL, POOL_SIZE = 0x90000, 0xA0000, 0x60000
DATA, MODEL_INPUT, ACTOR_INPUT = 0x140020, 0x92020, 0x93020
SCENARIOS = ('actor-first', 'owned', 'model-first')
RANGES = ROOT / 'docs/actor-factory-function-ranges.json'
DRIVER_SLOTS = (16, 17, 18, 19, 20, 21, 22, 26, 27, 28, 29)
FAULTS = (
    dict(name='primitive-allocation-size', patches=[(0x8001F25C, 0x34040024, 0x34040020)]),
    dict(name='omitted-state-release', patches=[(0x8001CC04, 0x8C440044, 0x00002021)]),
    dict(name='reversed-table-releases', patches=[(0x80065FA4, 0x8E040074, 0x8E040070),
                                                (0x80065FB0, 0x8E040070, 0x8E040074)]),
)
DEPENDENCIES = common.DEPENDENCIES + ('tools/actor_factory_model.py',
    'tools/verify_actor_factory.py', 'docs/actor-factory-function-ranges.json')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def initial_pool(pattern):
    buffers = dict(manager=child.filled(0x100, pattern, 17),
                   pool=child.filled(POOL_SIZE + 0x80, pattern, 53))
    struct.pack_into('<II', buffers['manager'], 0x40, POOL + 0x40, POOL_SIZE)
    return PoolModel(buffers, dict(manager=MANAGER, pool=POOL), 0x40, 0x40, POOL_SIZE)


def compare_events(actual, expected):
    if actual != expected:
        index = next((i for i, (a, b) in enumerate(zip(actual, expected)) if a != b),
                     min(len(actual), len(expected)))
        raise ValueError('planned_heap_event ' + str(index) + ': actual=' + str(actual[index:index+1])
                         + '; expected=' + str(expected[index:index+1]))


class Machine(common.Machine):
    def __init__(self, program, ranges, names, raw, pattern, events, faults=()):
        super().__init__(program, ranges, common.heap.global_addresses(program), len(raw))
        self.events, self.actual, self.pending = events, [], None
        self.patch_hits = Counter()
        self.patch_addresses = {address & common.native.MASK for address, _, _ in faults}
        self.observed = initial_pool(pattern)
        self.observed.setup()
        self.write_ranges = [(MANAGER, MANAGER + 0x100), (POOL, POOL + POOL_SIZE + 0x80),
            (DATA-32, DATA+len(raw)+32), (common.native.STACK-0x1000, common.native.STACK+0x100)]
        writable = list(common.heap.global_addresses(program).values()) + [
            names[name] & common.native.MASK for name in ('g_FileDriverClass', 'D_8008AC4C', 'g_CdLocked')]
        self.write_ranges.extend((address, address+4) for address in writable)
        self.read_ranges = self.write_ranges + [
            (program.LOAD & common.native.MASK, (program.LOAD & common.native.MASK)+len(program.ROM)-0x800),
            (MODEL_INPUT-32, MODEL_INPUT+48), (ACTOR_INPUT-32, ACTOR_INPUT+48),
            (child.SDK_TABLE, child.SDK_TABLE+32)]
        reference = initial_pool(pattern)
        for name, address in (('manager', MANAGER), ('pool', POOL)):
            self.cpu.mem_write(address, bytes(reference.buffers[name]))
        for address, old, new in faults:
            address &= common.native.MASK
            require(int.from_bytes(self.cpu.mem_read(address, 4), 'little') == old,
                    'Fault control no longer identifies the original instruction.')
            self.cpu.mem_write(address, struct.pack('<I', new))

    def code_hook(self, cpu, address, size, unused):
        physical = address & common.native.MASK
        if physical in self.patch_addresses:
            self.patch_hits[physical] += 1
        if self.pending and physical == self.pending[0] and cpu.reg_read(self.reg.UC_MIPS_REG_SP) == self.pending[1]:
            _, _, name, argument, expected = self.pending
            actual = cpu.reg_read(self.reg.UC_MIPS_REG_V0)
            require(actual == expected, 'Independent heap-component return mismatch.')
            self.actual.append((name, argument, actual))
            self.pending = None
        super().code_hook(cpu, address, size, unused)
        if physical in (self.program.symbols['memory_allocate_mem'] & common.native.MASK,
                        self.program.symbols['memory_free_mem'] & common.native.MASK):
            require(self.pending is None, 'Unexpected recursive heap entry.')
            name = 'memory_allocate_mem' if physical == self.program.symbols['memory_allocate_mem'] & common.native.MASK else 'memory_free_mem'
            argument = cpu.reg_read(self.reg.UC_MIPS_REG_A0)
            expected = self.observed.allocate(argument) if name == 'memory_allocate_mem' else self.observed.free(argument)
            self.pending = (cpu.reg_read(self.reg.UC_MIPS_REG_RA) & common.native.MASK,
                            cpu.reg_read(self.reg.UC_MIPS_REG_SP), name, argument, expected)


def run_case(program, ranges, names, raw, pattern, scenario, fault=None):
    reference = initial_pool(pattern)
    reference.setup()
    # Generate every expected argument and return before starting native code.
    plan = OwnershipPlan(raw, reference)
    expected = plan.run(scenario)
    patches = fault['patches'] if fault else ()
    machine = Machine(program, ranges, names, raw, pattern, expected, patches)
    report = dict(status='failed_bounded_actor_factory_ownership', scenario=scenario, pattern=pattern,
                  fault=fault, dependency_output_stubs=0, independent_request_and_release_plan=True,
                  independent_complete_object_payload_model=False, native_history_completed=False)
    word = lambda address: int.from_bytes(machine.cpu.mem_read(address & common.native.MASK, 4), 'little')
    try:
        machine.call('memory_set_manager', MANAGER+0x40)
        machine.call('memory_set_lock', 0)
        machine.call('memory_setup_manager', 0)
        getters = list(struct.unpack('<14I', program.target(names['g_FILE_DRIVER_CLASS_VTABLES'], 56)))
        getters.insert(0, program.symbols['file_buf_get_vtable'])
        by_address = {begin: name for begin, _, name in ranges}
        tables = []
        for address in getters:
            table = machine.call(by_address[address & common.native.MASK])
            require(0x8006A000 <= table < program.LOAD+len(program.ROM)-0x800, 'Invalid driver vtable.')
            tables.append(table)
            for slot in DRIVER_SLOTS:
                target = (table+slot*4) & common.native.MASK
                machine.write_ranges.append((target, target+4))
        machine.cpu.mem_write(names['g_CdInitialized'] & common.native.MASK, struct.pack('<I', 1))
        machine.cpu.mem_write(child.SDK_TABLE, child.SDK_MATRIX)
        machine.call('file_driver_set_class', 0x13)
        driver = machine.call('cd_file_driver_get_vtable')
        require(all(word(table+slot*4) == word(driver+slot*4) for table in tables for slot in DRIVER_SLOTS),
                'Original file-driver vtable initialization differs.')
        data = child.filled(len(raw)+64, pattern, 223)
        data[32:32+len(raw)] = raw
        machine.cpu.mem_write(DATA-32, bytes(data))
        model_input = child.filled(80, pattern, 241)
        struct.pack_into('<4I', model_input, 32, DATA, 0, 1, 0)
        machine.cpu.mem_write(MODEL_INPUT-32, bytes(model_input))
        histories = []
        def create_actor(borrowed):
            actor_input = child.filled(80, pattern, 197)
            struct.pack_into('<4I', actor_input, 32, *((0, 0, 0, borrowed) if borrowed else (DATA, 0, 1, 0)))
            machine.cpu.mem_write(ACTOR_INPUT-32, bytes(actor_input))
            actor = machine.call('actor_create', ACTOR_INPUT, 0)
            require(actor and machine.pending is None and word(actor) == program.symbols['g_ACTOR_VTABLE'], 'Actor factory failed.')
            model = word(actor+0x5C)
            require(model and word(model) == program.symbols['D_8006F384'], 'Model factory failed.')
            require(word(actor+0x6C) == len(plan.types), 'Actor child count differs from the original model.')
            require(word(actor+0x60) == (0 if borrowed else 1), 'Actor model ownership flag differs.')
            require(word(model+8) != 0 and (not borrowed or model == borrowed), 'Model parent link differs.')
            common.equal_buffer('actor_factory_input', bytes(machine.cpu.mem_read(ACTOR_INPUT-32, 80)), bytes(actor_input))
            return actor, model
        if scenario == 'owned':
            actor, model = create_actor(0)
            require(machine.call('base_class_destructor', actor) == 0, 'Actor destructor return differs.')
            histories.append(dict(actor=actor, model=model, owned_model_destroyed_with_actor=True))
        else:
            model = machine.call('func_8004468C', MODEL_INPUT)
            require(model and word(model) == program.symbols['D_8006F384'], 'Borrowed model factory failed.')
            if scenario == 'model-first':
                actor, _ = create_actor(model)
                cleanups = machine.entries['actor_cleanup']
                require(machine.call('file_buf_destroy', model) == 0, 'Model destructor return differs.')
                require(machine.entries['actor_cleanup'] == cleanups+1 and machine.entries['func_80065790'] > 0,
                        'Original model notification did not destroy its borrowed actor.')
                histories.append(dict(actor=actor, model=model, actor_destroyed_by_model_notification=True))
            else:
                require(scenario == 'actor-first', 'Unknown ownership scenario.')
                for _ in range(2):
                    actor, _ = create_actor(model)
                    require(machine.call('base_class_destructor', actor) == 0 and word(model+8) == 0,
                            'Borrowed model did not survive actor destruction.')
                    histories.append(dict(actor=actor, model=model, borrowed_model_survived=True))
                require(machine.call('file_buf_destroy', model) == 0, 'Final model destruction failed.')
        require(machine.pending is None, 'Unfinished heap call.')
        report['native_history_completed'] = True
        compare_events(machine.actual, machine.events)
        common.equal_buffer('complete_manager', bytes(machine.cpu.mem_read(MANAGER, 0x100)), bytes(reference.buffers['manager']))
        common.equal_buffer('pool_prefix_guard', bytes(machine.cpu.mem_read(POOL, 64)), bytes(reference.buffers['pool'][:64]))
        suffix = 0x40+POOL_SIZE+4
        common.equal_buffer('pool_suffix_guard', bytes(machine.cpu.mem_read(POOL+suffix, 60)), bytes(reference.buffers['pool'][suffix:]))
        for address, original in ((DATA-32, data[:32]), (DATA+len(raw), data[-32:]),
                                  (MODEL_INPUT-32, model_input), (child.SDK_TABLE, child.SDK_MATRIX)):
            common.equal_buffer('supplied_input_guard', bytes(machine.cpu.mem_read(address, len(original))), bytes(original))
        require(word(names['D_8008AC4C']) == 1 and word(names['g_CdLocked']) == 0,
                'Final enumeration flag or CD lock differs.')
        require(len(machine.observed.blocks) == 1 and machine.observed.blocks[0].free, 'Owned allocations remain live.')
        report.update(status='passed_bounded_actor_factory_ownership', histories=histories,
                      all_owned_allocations_released=True)
    except (ValueError, machine.unicorn.UcError) as error:
        report.update(error=str(error), recent_native_addresses=machine.recent)
    report.update(expected_heap_events=expected, actual_heap_events=machine.actual,
                  instructions=machine.steps, entered_original_functions=dict(machine.entries),
                  changed_instruction_hits={hex(address): count for address, count in machine.patch_hits.items()})
    return report


def verify(layout, destination, edition_label):
    ninja = common.require_ninja()
    backend = {key: value for key, value in common.heap.backend_identity().items() if key in common.IDENTITY_KEYS}
    functions = json.loads(RANGES.read_text(encoding='utf-8'))['functions']
    before = common.build_inputs()
    dependencies = {name: common.sha((ROOT/name).read_bytes()) for name in DEPENDENCIES}
    program = common.native.load_program(functions)
    inventory = common.inspect_animations(layout)
    common.corpus_models(inventory)  # Require a complete validated corpus before execution.
    planned = [(source, item) for source in inventory['files'] for item in source['models']]
    ranges, diagnostic = common.symbol_diagnostic(program, destination, functions)
    names = dict(program.symbols)
    for line in subprocess.check_output([configure.CROSS+'nm', '--defined-only', str(destination/'canonical-symbols.elf')], text=True).splitlines():
        fields = line.split()
        if len(fields) == 3:
            names[fields[2]] = int(fields[0], 16)
    common.write_json(destination/'inventory.json', inventory)
    common.write_json(destination/'symbol-diagnostic.json', diagnostic)
    rows, entered, began = [], Counter(), time.monotonic()
    def model_bytes(source, item):
        asset = Path(source['source']).read_bytes()
        require(common.sha(asset) == source['sha256'], 'Original model asset changed.')
        return asset[item['offset']:item['offset']+item['bytes']]
    for index, (source, item) in enumerate(planned):
        raw = model_bytes(source, item)
        for pattern in child.PATTERNS:
            for scenario in SCENARIOS:
                name = 'model-'+str(index).zfill(3)+'-'+pattern+'-'+scenario
                result = run_case(program, ranges, names, raw, pattern, scenario)
                common.write_json(destination/(name+'.json'), result)
                require(result['status'] == 'passed_bounded_actor_factory_ownership', 'Retained '+name+'.json: '+result.get('error', ''))
                rows.append(dict(case=name, model_sha256=common.sha(raw), scenario=scenario, pattern=pattern,
                    actor_lifetimes=len(result['histories']), heap_events=len(result['actual_heap_events']),
                    report_sha256=common.sha((destination/(name+'.json')).read_bytes())))
                entered.update(result['entered_original_functions'])
                gc.collect()
        if (index+1) % 10 == 0 or index+1 == len(planned):
            print(json.dumps(dict(models_completed=index+1, planned_models=len(planned), cases=len(rows))), flush=True)
    controls = []
    raw = model_bytes(*planned[0])
    for fault in FAULTS:
        result = run_case(program, ranges, names, raw, 'distinct', 'actor-first', fault)
        common.write_json(destination/('fault-'+fault['name']+'.json'), result)
        require(result['native_history_completed'] and result['status'].startswith('failed_')
                and result.get('error', '').startswith('planned_heap_event ')
                and all(result['changed_instruction_hits'].get(hex(address & common.native.MASK), 0)
                        for address, _, _ in fault['patches']), 'Fault did not finish and expose a wrong ownership event: '+fault['name'])
        controls.append(dict(name=fault['name'], detected=True, native_history_completed=True,
                             changed_instruction_hits=result['changed_instruction_hits'], detection=result['error']))
    require(before == common.build_inputs(), 'Canonical game inputs changed.')
    require(common.sha(Path(layout).read_bytes()) == inventory['layout_sha256'], 'Extraction layout changed.')
    require(all(common.sha(Path(source['source']).read_bytes()) == source['sha256']
                for source in inventory['files']), 'An inventoried original asset changed.')
    require(all(common.sha((ROOT/name).read_bytes()) == value for name, value in dependencies.items()), 'Analysis producer changed during execution.')
    require((ROOT/'build/SLPS015.56').read_bytes() == program.ROM == (ROOT/'rom/SLPS_015.56').read_bytes(), 'Complete matching build changed.')
    require(set(entered) == {row['function'] for row in functions}, 'The published function closure was not completely exercised.')
    report = dict(schema_version=1, status='passed_bounded_original_actor_factory_ownership',
        recorded_utc=datetime.now(timezone.utc).isoformat(),
        edition_label=edition_label, edition_label_is_user_supplied=True, original_model_instances=len(planned),
        distinct_model_contents=len({row['model_sha256'] for row in rows}), positive_cases=len(rows),
        actor_lifetimes=sum(row['actor_lifetimes'] for row in rows), heap_events=sum(row['heap_events'] for row in rows),
        native_allocation_calls=entered['memory_allocate_mem'], native_release_calls=entered['memory_free_mem'],
        results=rows, faults=controls, entered_original_functions=dict(entered), function_ranges=functions,
        backend=backend, ninja=ninja, canonical_sha256=common.sha(program.ROM),
        inventory_sha256=common.sha((destination/'inventory.json').read_bytes()),
        layout_sha256=inventory['layout_sha256'],
        protected_build_input_sha256=before, producer_dependency_sha256=dependencies,
        independent_request_and_release_plan=True, independent_complete_object_payload_model=False,
        complete_manager_comparison=True, dependency_output_stubs=0, model_api_calls=0,
        canonical_complete_image_equal=True, all_game_build_inputs_preserved=True,
        new_C_bytes=0, new_NPC_callback_profiles=0, whole_feature_acceptances=0, goal_complete=False,
        supplied_inputs=['original MOM bytes copied to writable VM memory', 'unlocked supplied pool',
                         'g_CdInitialized=1 ready-state fixture', 'SDK identity matrix table'],
        elapsed_seconds=time.monotonic()-began,
        scope='Native model/TMD/MOS factories, animation-zero initialization and three actor/model ownership histories. '
              'An independent plan predicts ordered heap requests, releases and return words before execution. '
              'Complete object/geometry/raw-model mutation oracles, allocation failures, cold CD initialization, '
              'physical disc I/O, later playback, natural encounters, rendering and PS1 timing remain open.')
    common.write_json(destination/'report.json', report)
    print(json.dumps({key: report[key] for key in ('status', 'positive_cases', 'actor_lifetimes', 'heap_events')}), flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', required=True, help='Your dumpsxiso extraction XML.')
    parser.add_argument('--output', required=True, help='Fresh directory inside .decomp-lab.')
    parser.add_argument('--edition-label', default='unspecified', help='Provenance label; not edition detection.')
    args = parser.parse_args(argv)
    created = False
    try:
        destination = common.output_directory(args.output)
        destination.mkdir(parents=True, exist_ok=False)
        created = True
        verify(Path(args.layout).resolve(), destination, args.edition_label)
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError, ET.ParseError) as error:
        if created:
            common.write_json(destination/'failure.json', dict(status='failed_actor_factory_verification',
                error=str(error), goal_complete=False, whole_feature_acceptances=0))
        print('[!] '+str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
