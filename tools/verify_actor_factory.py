"""Check original MOM/actor factory ownership against an independent event plan.

The optional model-data profile compares the complete mapped raw MOM copy.
The model-objects profile checks complete allocations at original factory return.
The actor-objects profile checks every live pool payload at actor-factory return.
Later animation playback and post-construction state are not modeled.
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
from tools.model_mapping_model import geometry_bindings, mapped_model_bytes
from tools.model_payload_model import ModelPayloadPlan
from tools.actor_payload_model import ActorPayloadPlan

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
MODEL_DATA_FAULTS = (
    dict(name='mapped-flag-extra-bit', patches=[(0x8002055C, 0x34620001, 0x34620003)]),
    dict(name='vertex-pointer-base', patches=[(0x8002058C, 0x00821021, 0x00021021)]),
    dict(name='normal-pointer-base', patches=[(0x800205A0, 0x00821021, 0x00021021)]),
    dict(name='primitive-batch-count', patches=[(0x8001F09C, 0xA6910000, 0xA6800000)]),
    dict(name='animation-slots-not-cleared', patches=[(0x80018420, 0xAE220000, 0x00000000)]),
)
MODEL_OBJECT_FAULTS = (
    dict(name='model-construction-mode-word', patches=[(0x800446CC, 0x34060001, 0x34060003)]),
    dict(name='constructed-file-flags', patches=[(0x80026C90, 0x34420001, 0x34420003)]),
    dict(name='constructor-overwrites-residue', patches=[(0x80026A98, 0xA6000028, 0xA6000018)]),
)
ACTOR_OBJECT_FAULTS = (
    dict(name='scene-height-cleared', patches=[(0x800571EC, 0xA4820048, 0xA4800048)]),
    dict(name='actor-callback-selected', patches=[(0x800658B4, 0x34050041, 0x34050042)]),
    dict(name='actor-callback-enable-word', patches=[(0x8006614C, 0xAC80008C, 0xAC84008C)]),
    dict(name='sdk-overwrites-untouched-id-word', patches=[(0x8001EFAC, 0xACA40008, 0xACA4000C)]),
)
DEPENDENCIES = common.DEPENDENCIES + ('tools/actor_factory_model.py',
    'tools/verify_actor_factory.py', 'tools/model_mapping_model.py',
    'tools/model_payload_model.py', 'tools/actor_payload_model.py',
    'docs/actor-factory-function-ranges.json')


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
    def __init__(self, program, ranges, names, raw, pattern, events, faults=(), model_payloads=(), actor_payloads=(), actor_returns=()):
        super().__init__(program, ranges, common.heap.global_addresses(program), len(raw))
        self.events, self.actual, self.pending = events, [], None
        self.model_payloads = tuple(model_payloads)
        self.model_payload_pending = None
        self.model_payload_entries = 0
        self.model_payload_snapshots = []
        self.actor_payloads = tuple(actor_payloads)
        self.actor_returns = tuple(actor_returns)
        self.actor_payload_pending = None
        self.actor_payload_entries = 0
        self.actor_payload_snapshots = []
        self.actor_return_snapshots = []
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
        self.finish_model_payloads(physical)
        self.finish_actor_payloads(physical)
        if self.actor_payloads and physical == self.program.symbols['actor_create'] & common.native.MASK:
            require(self.actor_payload_pending is None and self.actor_payload_entries < len(self.actor_payloads),
                    'The actor-object profile requires the independently planned nonrecursive factory entries.')
            self.actor_payload_pending = (cpu.reg_read(self.reg.UC_MIPS_REG_RA) & common.native.MASK,
                                          cpu.reg_read(self.reg.UC_MIPS_REG_SP), self.actor_payload_entries)
            self.actor_payload_entries += 1
        if self.model_payloads and physical == self.program.symbols['func_8004468C'] & common.native.MASK:
            require(self.model_payload_pending is None and self.model_payload_entries == 0,
                    'The successful model-object profile requires one nonrecursive factory call.')
            self.model_payload_entries += 1
            self.model_payload_pending = (cpu.reg_read(self.reg.UC_MIPS_REG_RA) & common.native.MASK,
                                          cpu.reg_read(self.reg.UC_MIPS_REG_SP))
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

    def finish_model_payloads(self, physical):
        if (self.model_payload_pending is None or physical != self.model_payload_pending[0]
                or self.cpu.reg_read(self.reg.UC_MIPS_REG_SP) != self.model_payload_pending[1]):
            return
        require(self.cpu.reg_read(self.reg.UC_MIPS_REG_V0) == self.model_payloads[0].pointer,
                'The original factory did not return the independently planned model.')
        for payload in self.model_payloads:
            actual = bytes(self.cpu.mem_read(payload.pointer & common.native.MASK, len(payload.expected)))
            mismatch = next((index for index, (a, b) in enumerate(zip(actual, payload.expected)) if a != b), None)
            self.model_payload_snapshots.append(dict(kind=payload.kind, pointer=hex(payload.pointer),
                phase='original_model_factory_return', requested_bytes=payload.requested_bytes,
                bytes_compared=len(payload.expected), matched=actual == payload.expected,
                first_difference=mismatch, expected_sha256=common.sha(payload.expected), actual_sha256=common.sha(actual)))
        self.model_payload_pending = None

    def finish_actor_payloads(self, physical):
        pending = self.actor_payload_pending
        if (pending is None or physical != pending[0]
                or self.cpu.reg_read(self.reg.UC_MIPS_REG_SP) != pending[1]):
            return
        index = pending[2]
        returned = self.cpu.reg_read(self.reg.UC_MIPS_REG_V0)
        self.actor_return_snapshots.append(dict(index=index, actual=hex(returned),
            expected=hex(self.actor_returns[index]), matched=returned == self.actor_returns[index]))
        for payload in self.actor_payloads[index]:
            actual = bytes(self.cpu.mem_read(payload.pointer & common.native.MASK, len(payload.expected)))
            mismatch = next((offset for offset, (a, b) in enumerate(zip(actual, payload.expected)) if a != b), None)
            self.actor_payload_snapshots.append(dict(actor_index=index, kind=payload.kind, pointer=hex(payload.pointer),
                phase='original_actor_factory_return', requested_bytes=payload.requested_bytes,
                bytes_compared=len(payload.expected), matched=actual == payload.expected,
                first_difference=mismatch, expected_sha256=common.sha(payload.expected), actual_sha256=common.sha(actual)))
        self.actor_payload_pending = None

    def call(self, name, *arguments):
        result = super().call(name, *arguments)
        # A top-level call stops before END executes; nested factory returns
        # are observed in code_hook, with the same SP/return-address guard.
        self.finish_model_payloads(common.native.END)
        self.finish_actor_payloads(common.native.END)
        return result


def run_case(program, ranges, names, raw, pattern, scenario, fault=None, model_data=False, model_objects=False, actor_objects=False):
    reference = initial_pool(pattern)
    reference.setup()
    # Generate every expected argument and return before starting native code.
    if actor_objects:
        angles = child.rational_values(program.target(names['D_8006B684'], 12))
        scales = child.rational_values(program.target(names['D_8006B690'], 12))
        plan = ActorPayloadPlan(raw, reference, names, DATA, angles, scales)
    else:
        plan = ModelPayloadPlan(raw, reference, names, DATA) if model_objects else OwnershipPlan(raw, reference)
    expected = plan.run(scenario)
    if model_objects:
        require(len(plan.model_payloads) == 1, 'The model-object profile requires one planned construction.')
    if model_data:
        require(len(plan.models) == 1, 'The raw-model profile requires one independently planned model.')
    mapped = mapped_model_bytes(raw, DATA, plan.models[0].animations) if model_data else None
    if model_data:
        indices = geometry_bindings(plan.types, plan.commands, plan.objects)
        linked = mapped_model_bytes(raw, DATA, plan.models[0].animations, indices)
        destroyed = mapped_model_bytes(raw, DATA, plan.models[0].animations, indices, destroyed=True)
    patches = fault['patches'] if fault else ()
    payloads = plan.model_payloads[0] if model_objects else ()
    machine = Machine(program, ranges, names, raw, pattern, expected, patches, payloads,
                      plan.actor_payloads if actor_objects else (), plan.actor_returns if actor_objects else ())
    report = dict(status='failed_bounded_actor_factory_ownership', scenario=scenario, pattern=pattern,
                  fault=fault, dependency_output_stubs=0, independent_request_and_release_plan=True,
                  independent_complete_object_payload_model=actor_objects, native_history_completed=False)
    snapshots = []
    reentered = False
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
        def compare_model_data(phase, expected_copy):
            if not model_data:
                return
            actual = bytes(machine.cpu.mem_read(DATA-32, len(raw)+64))
            expected_data = bytes(data[:32]) + expected_copy + bytes(data[-32:])
            mismatch = next((index for index, (a, b) in enumerate(zip(actual, expected_data)) if a != b), None)
            snapshots.append(dict(phase=phase, bytes_compared=len(actual), matched=actual == expected_data,
                                  first_difference=mismatch, expected_sha256=common.sha(expected_data),
                                  actual_sha256=common.sha(actual)))
        def mapping_reentry(model, expected_copy):
            nonlocal reentered
            if model_data and not reentered:
                tmd = word(model+0x2C)
                require(tmd == plan.models[0].tmd, 'Model TMD ownership pointer differs from its independent plan.')
                machine.call('tmd_map', tmd)
                reentered = True
                compare_model_data('after_original_mapping_reentry', expected_copy)
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
            compare_model_data('after_actor_factory', linked if model_data else None)
            mapping_reentry(model, linked if model_data else None)
            return actor, model
        if scenario == 'owned':
            actor, model = create_actor(0)
            require(machine.call('base_class_destructor', actor) == 0, 'Actor destructor return differs.')
            compare_model_data('after_owned_actor_destruction', destroyed if model_data else None)
            histories.append(dict(actor=actor, model=model, owned_model_destroyed_with_actor=True))
        else:
            model = machine.call('func_8004468C', MODEL_INPUT)
            require(model and word(model) == program.symbols['D_8006F384'], 'Borrowed model factory failed.')
            compare_model_data('after_model_factory', mapped)
            mapping_reentry(model, mapped)
            if scenario == 'model-first':
                actor, _ = create_actor(model)
                cleanups = machine.entries['actor_cleanup']
                require(machine.call('file_buf_destroy', model) == 0, 'Model destructor return differs.')
                require(machine.entries['actor_cleanup'] == cleanups+1 and machine.entries['func_80065790'] > 0,
                        'Original model notification did not destroy its borrowed actor.')
                compare_model_data('after_model_notification_and_destruction', destroyed if model_data else None)
                histories.append(dict(actor=actor, model=model, actor_destroyed_by_model_notification=True))
            else:
                require(scenario == 'actor-first', 'Unknown ownership scenario.')
                for _ in range(2):
                    actor, _ = create_actor(model)
                    require(machine.call('base_class_destructor', actor) == 0 and word(model+8) == 0,
                            'Borrowed model did not survive actor destruction.')
                    compare_model_data('after_borrowed_actor_destruction', linked if model_data else None)
                    histories.append(dict(actor=actor, model=model, borrowed_model_survived=True))
                require(machine.call('file_buf_destroy', model) == 0, 'Final model destruction failed.')
                compare_model_data('after_final_model_destruction', destroyed if model_data else None)
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
        if model_data:
            require(len(snapshots) == {'owned': 3, 'actor-first': 7, 'model-first': 4}[scenario]
                    and reentered, 'The model-data profile did not execute all its mapping checks.')
            wrong = next((row for row in snapshots if not row['matched']), None)
            require(wrong is None, 'mapped_model_data ' + (str(wrong) if wrong else ''))
        if model_objects:
            require(machine.model_payload_entries == 1 and machine.model_payload_pending is None
                    and len(machine.model_payload_snapshots) == len(payloads),
                    'The model-object profile did not observe its complete original factory return.')
            wrong = next((row for row in machine.model_payload_snapshots if not row['matched']), None)
            require(wrong is None, 'constructed_model_payload ' + (str(wrong) if wrong else ''))
        if actor_objects:
            require(machine.actor_payload_pending is None and machine.actor_payload_entries == len(plan.actor_payloads)
                    and len(machine.actor_payload_snapshots) == sum(len(group) for group in plan.actor_payloads),
                    'The actor-object profile did not observe every complete original factory return.')
            wrong = next((row for row in machine.actor_return_snapshots+machine.actor_payload_snapshots if not row['matched']), None)
            require(wrong is None, 'constructed_actor_payload '+(str(wrong) if wrong else ''))
        report.update(status='passed_bounded_actor_factory_ownership', histories=histories,
                      all_owned_allocations_released=True)
    except (ValueError, machine.unicorn.UcError) as error:
        report.update(error=str(error), recent_native_addresses=machine.recent)
    report.update(expected_heap_events=expected, actual_heap_events=machine.actual,
                  model_data_profile=model_data, independent_raw_model_mapping=model_data,
                  model_data_snapshots=snapshots, original_mapping_reentry=reentered,
                  model_objects_profile=model_objects, model_object_snapshots=machine.model_payload_snapshots,
                  independent_constructed_model_payload_model=model_objects,
                  actor_objects_profile=actor_objects, actor_object_snapshots=machine.actor_payload_snapshots,
                  actor_return_snapshots=machine.actor_return_snapshots,
                  instructions=machine.steps, entered_original_functions=dict(machine.entries),
                  changed_instruction_hits={hex(address): count for address, count in machine.patch_hits.items()})
    return report


def verify(layout, destination, edition_label, model_data=False, model_objects=False, actor_objects=False):
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
                result = run_case(program, ranges, names, raw, pattern, scenario,
                                  model_data=model_data, model_objects=model_objects, actor_objects=actor_objects)
                common.write_json(destination/(name+'.json'), result)
                require(result['status'] == 'passed_bounded_actor_factory_ownership', 'Retained '+name+'.json: '+result.get('error', ''))
                rows.append(dict(case=name, model_sha256=common.sha(raw), scenario=scenario, pattern=pattern,
                    actor_lifetimes=len(result['histories']), heap_events=len(result['actual_heap_events']),
                    model_data_snapshots=len(result['model_data_snapshots']),
                    model_data_bytes_compared=sum(row['bytes_compared'] for row in result['model_data_snapshots']),
                    model_object_snapshots=len(result['model_object_snapshots']),
                    model_object_bytes_compared=sum(row['bytes_compared'] for row in result['model_object_snapshots']),
                    actor_object_snapshots=len(result['actor_object_snapshots']),
                    actor_object_bytes_compared=sum(row['bytes_compared'] for row in result['actor_object_snapshots']),
                    actor_factory_returns=len(result['actor_return_snapshots']),
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
    model_controls = []
    if model_data:
        for fault in MODEL_DATA_FAULTS:
            result = run_case(program, ranges, names, raw, 'distinct', 'actor-first', fault, model_data=True)
            common.write_json(destination/('fault-'+fault['name']+'.json'), result)
            require(result['native_history_completed'] and result['status'].startswith('failed_')
                    and result.get('error', '').startswith('mapped_model_data ')
                    and all(result['changed_instruction_hits'].get(hex(address & common.native.MASK), 0)
                            for address, _, _ in fault['patches']),
                    'Model-data fault did not finish and expose a wrong byte: '+fault['name'])
            model_controls.append(dict(name=fault['name'], detected=True, native_history_completed=True,
                                       changed_instruction_hits=result['changed_instruction_hits'], detection=result['error']))
    object_controls = []
    if model_objects:
        for fault in MODEL_OBJECT_FAULTS:
            result = run_case(program, ranges, names, raw, 'distinct', 'actor-first', fault,
                              model_data=model_data, model_objects=True)
            common.write_json(destination/('fault-'+fault['name']+'.json'), result)
            require(result['native_history_completed'] and result['status'].startswith('failed_')
                    and result.get('error', '').startswith('constructed_model_payload ')
                    and all(row['matched'] for row in result['model_data_snapshots'])
                    and all(result['changed_instruction_hits'].get(hex(address & common.native.MASK), 0)
                            for address, _, _ in fault['patches']),
                    'Model-object fault did not finish and expose a wrong payload: '+fault['name'])
            object_controls.append(dict(name=fault['name'], detected=True, native_history_completed=True,
                                        changed_instruction_hits=result['changed_instruction_hits'], detection=result['error']))
    actor_controls = []
    if actor_objects:
        for fault in ACTOR_OBJECT_FAULTS:
            result = run_case(program, ranges, names, raw, 'distinct', 'actor-first', fault,
                              model_data=model_data, model_objects=model_objects, actor_objects=True)
            common.write_json(destination/('fault-'+fault['name']+'.json'), result)
            require(result['native_history_completed'] and result['status'].startswith('failed_')
                    and result.get('error', '').startswith('constructed_actor_payload ')
                    and result['actual_heap_events'] == result['expected_heap_events']
                    and all(row['matched'] for row in result['model_data_snapshots'])
                    and all(row['matched'] for row in result['model_object_snapshots'])
                    and all(row['matched'] for row in result['actor_return_snapshots'])
                    and all(result['changed_instruction_hits'].get(hex(address & common.native.MASK), 0)
                            for address, _, _ in fault['patches']),
                    'Actor-object fault did not finish and expose a wrong live payload: '+fault['name'])
            actor_controls.append(dict(name=fault['name'], detected=True, native_history_completed=True,
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
        model_data_profile=model_data, independent_raw_model_mapping=model_data, model_data_faults=model_controls,
        model_data_snapshots=sum(row['model_data_snapshots'] for row in rows),
        model_data_bytes_compared=sum(row['model_data_bytes_compared'] for row in rows),
        original_mapping_reentries=len(rows) if model_data else 0,
        model_objects_profile=model_objects, independent_constructed_model_payload_model=model_objects,
        model_object_faults=object_controls,
        model_object_snapshots=sum(row['model_object_snapshots'] for row in rows),
        model_object_bytes_compared=sum(row['model_object_bytes_compared'] for row in rows),
        actor_objects_profile=actor_objects, independent_complete_actor_construction_payload_model=actor_objects,
        actor_object_faults=actor_controls,
        actor_object_snapshots=sum(row['actor_object_snapshots'] for row in rows),
        actor_object_bytes_compared=sum(row['actor_object_bytes_compared'] for row in rows),
        actor_factory_returns=sum(row['actor_factory_returns'] for row in rows),
        backend=backend, ninja=ninja, canonical_sha256=common.sha(program.ROM),
        inventory_sha256=common.sha((destination/'inventory.json').read_bytes()),
        layout_sha256=inventory['layout_sha256'],
        protected_build_input_sha256=before, producer_dependency_sha256=dependencies,
        independent_request_and_release_plan=True, independent_complete_object_payload_model=actor_objects,
        complete_manager_comparison=True, dependency_output_stubs=0, model_api_calls=0,
        canonical_complete_image_equal=True, all_game_build_inputs_preserved=True,
        new_C_bytes=0, new_NPC_callback_profiles=0, whole_feature_acceptances=0, goal_complete=False,
        supplied_inputs=['original MOM bytes copied to writable VM memory', 'unlocked supplied pool',
                         'g_CdInitialized=1 ready-state fixture', 'SDK identity matrix table'],
        elapsed_seconds=time.monotonic()-began,
        scope='Native model/TMD/MOS factories, animation-zero initialization and three actor/model ownership histories. '
              'An independent plan predicts ordered heap requests, releases and return words before execution. ' +
              ('The optional complete guarded raw-model mapping oracle is active. ' if model_data else '') +
              ('Raw-model mutation comparisons are not enabled. ' if not model_data else '') +
              ('Complete model allocations are checked at the original factory return, before actor attachment. ' if model_objects else '') +
              ('Every live pool payload is checked at actor-factory return after frame-zero interpretation. ' if actor_objects else '') +
              ('Complete actor-construction payload comparisons are not enabled. ' if not actor_objects else '') +
              'Later animation playback and post-construction model/actor mutations, allocation failures, cold CD initialization, '
              'physical disc I/O, later playback, natural encounters, rendering and PS1 timing remain open.')
    common.write_json(destination/'report.json', report)
    print(json.dumps({key: report[key] for key in ('status', 'positive_cases', 'actor_lifetimes', 'heap_events')}), flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', required=True, help='Your dumpsxiso extraction XML.')
    parser.add_argument('--output', required=True, help='Fresh directory inside .decomp-lab.')
    parser.add_argument('--edition-label', default='unspecified', help='Provenance label; not edition detection.')
    parser.add_argument('--model-data', action='store_true', help='Also compare all guarded raw MOM mapping bytes and original mapping reentry.')
    parser.add_argument('--model-objects', action='store_true', help='Compare complete model allocations at original factory return, before actor attachment.')
    parser.add_argument('--actor-objects', action='store_true', help='Compare every live pool payload at original actor-factory return, after frame-zero interpretation.')
    args = parser.parse_args(argv)
    created = False
    try:
        destination = common.output_directory(args.output)
        destination.mkdir(parents=True, exist_ok=False)
        created = True
        verify(Path(args.layout).resolve(), destination, args.edition_label, args.model_data, args.model_objects, args.actor_objects)
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError, ET.ParseError) as error:
        if created:
            common.write_json(destination/'failure.json', dict(status='failed_actor_factory_verification',
                error=str(error), goal_complete=False, whole_feature_acceptances=0))
        print('[!] '+str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
