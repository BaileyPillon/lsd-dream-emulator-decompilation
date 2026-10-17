"""Check original animation selection after real actor/model construction.

All validated MOM instances and valid animation indices; owned, shared and
model-first destruction histories. Only immediate first frames are applied.
The ready-CD, bounded pool and original SDK matrix table are supplied inputs.
No original NPC callback, natural encounter or whole feature is accepted.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import verify_actor_factory as factory
from tools import actor_child_model as child
from tools.actor_animation_model import AnimationPayloadPlan
from tools.model_mapping_model import mapped_model_bytes

ANIMATION_FAULTS = (
    dict(name='selection-index-not-stored', patch=(0x80066220, 0xAC85007C, 0)),
    dict(name='duration-cleared', patch=(0x80066250, 0xAC820080, 0xAC800080)),
    dict(name='counter-reset-omitted', patch=(0x80066274, 0xAC800084, 0)),
    dict(name='first-frame-dispatch-omitted', patch=(0x80066290, 0x0040F809, 0)),
)
CONTROL_MODEL_SHA256 = 'af4834af69970858e9287ffd56222648388c0e082b631e3e5d0c3fc3f2719ce1'


def require_backend(identity):
    if identity['package_version'] != '2.1.2':
        raise ValueError('Use isolated requirements-card-heap.txt (Unicorn 2.1.2); the newer analysis backend is not qualified for this allocator harness.')


def prepare(raw, names, pattern, scenario, program):
    pool = factory.initial_pool(pattern)
    pool.setup()
    angles = child.rational_values(program.target(names['D_8006B684'], 12))
    scales = child.rational_values(program.target(names['D_8006B690'], 12))
    plan = AnimationPayloadPlan(raw, pool, names, factory.DATA, angles, scales)
    shared = None if scenario == 'owned' else plan.create_model()
    lifetimes = []
    for _ in range(2 if scenario == 'actor-first' else 1):
        actor = plan.create_actor(shared)
        initial = mapped_model_bytes(raw, factory.DATA, actor.model.animations, tuple(plan.geometry_indices))
        selections = []
        sequence = list(range(plan.animations)) + list(reversed(range(plan.animations)))
        for index in sequence:
            counter = min(max(plan.word(actor.pointer, 128) - 1, 0), 3)
            plan.put(actor.pointer, 132, counter)
            payloads = plan.select_animation(actor, index)
            selections.append(dict(index=index, counter=counter, payloads=payloads,
                raw=mapped_model_bytes(raw, factory.DATA, actor.model.animations, tuple(plan.geometry_indices)),
                manager=bytes(pool.buffers['manager'])))
        lifetimes.append(dict(actor=actor.pointer, model=actor.model.pointer, initial_raw=initial, selections=selections))
        if scenario != 'model-first':
            plan.destroy_actor(actor)
    if shared is not None:
        plan.destroy_model(shared)
    if plan.live or len(pool.blocks) != 1 or not pool.blocks[0].free:
        raise ValueError('Independent animation history retained owned allocations.')
    return plan, lifetimes


class Machine(factory.Machine):
    def __init__(self, *args, **kwargs):
        self.selection_entries = []
        self.animation_fault_addresses = set()
        self.animation_fault_hits = Counter()
        super().__init__(*args, **kwargs)

    def set_animation_faults(self, faults, active):
        """Alter only explicit selections; constructors/destructors stay original."""
        for address, old, new in faults:
            physical = address & factory.common.native.MASK
            expected, replacement = (old, new) if active else (new, old)
            actual = int.from_bytes(self.cpu.mem_read(physical, 4), 'little')
            if actual != expected:
                raise ValueError('Animation fault no longer identifies its expected instruction.')
            self.cpu.mem_write(physical, struct.pack('<I', replacement))
            # Construction may already have translated the original selector.
            self.cpu.ctl_remove_cache(physical, physical + 4)
            self.cpu.ctl_remove_cache(address, address + 4)
        self.animation_fault_addresses = {
            address & factory.common.native.MASK for address, _old, _new in faults
        } if active else set()

    def code_hook(self, cpu, address, size, unused):
        physical = address & factory.common.native.MASK
        if physical in self.animation_fault_addresses:
            self.animation_fault_hits[physical] += 1
        if address & factory.common.native.MASK == self.program.symbols['func_80066214'] & factory.common.native.MASK:
            self.selection_entries.append((cpu.reg_read(self.reg.UC_MIPS_REG_A0), cpu.reg_read(self.reg.UC_MIPS_REG_A1)))
        super().code_hook(cpu, address, size, unused)


def initialize(machine, program, ranges, names, raw, pattern):
    machine.call('memory_set_manager', factory.MANAGER + 0x40)
    machine.call('memory_set_lock', 0)
    machine.call('memory_setup_manager', 0)
    getters = list(struct.unpack('<14I', program.target(names['g_FILE_DRIVER_CLASS_VTABLES'], 56)))
    getters.insert(0, program.symbols['file_buf_get_vtable'])
    by_address = {begin: name for begin, _end, name in ranges}
    tables = []
    for address in getters:
        table = machine.call(by_address[address & factory.common.native.MASK])
        tables.append(table)
        for slot in factory.DRIVER_SLOTS:
            target = (table + slot * 4) & factory.common.native.MASK
            machine.write_ranges.append((target, target + 4))
    machine.cpu.mem_write(names['g_CdInitialized'] & factory.common.native.MASK, struct.pack('<I', 1))
    machine.cpu.mem_write(child.SDK_TABLE, child.SDK_MATRIX)
    machine.call('file_driver_set_class', 0x13)
    driver = machine.call('cd_file_driver_get_vtable')
    word = lambda address: int.from_bytes(machine.cpu.mem_read(address & factory.common.native.MASK, 4), 'little')
    if not all(word(table + slot * 4) == word(driver + slot * 4) for table in tables for slot in factory.DRIVER_SLOTS):
        raise ValueError('Original ready-CD driver initialization differs.')
    data = child.filled(len(raw) + 64, pattern, 223)
    data[32:32 + len(raw)] = raw
    machine.cpu.mem_write(factory.DATA - 32, bytes(data))
    model_input = child.filled(80, pattern, 241)
    struct.pack_into('<4I', model_input, 32, factory.DATA, 0, 1, 0)
    machine.cpu.mem_write(factory.MODEL_INPUT - 32, bytes(model_input))
    return data, model_input


def run_case(program, ranges, names, raw, pattern, scenario, faults=()):
    plan, lifetimes = prepare(raw, names, pattern, scenario, program)
    machine = Machine(program, ranges, names, raw, pattern, plan.events, (),
                      plan.model_payloads[0], plan.actor_payloads, plan.actor_returns)
    data, model_input = initialize(machine, program, ranges, names, raw, pattern)
    shared = machine.call('func_8004468C', factory.MODEL_INPUT) if scenario != 'owned' else 0
    observations, bad = [], []
    for lifetime in lifetimes:
        descriptor = child.filled(80, pattern, 197)
        struct.pack_into('<4I', descriptor, 32, *((0, 0, 0, shared) if shared else (factory.DATA, 0, 1, 0)))
        machine.cpu.mem_write(factory.ACTOR_INPUT - 32, bytes(descriptor))
        returned = machine.call('actor_create', factory.ACTOR_INPUT, 0)
        if returned != lifetime['actor']:
            raise ValueError('Original actor return differs from its independent allocation plan.')
        factory.common.equal_buffer('actor descriptor', bytes(machine.cpu.mem_read(factory.ACTOR_INPUT - 32, 80)), bytes(descriptor))
        factory.common.equal_buffer('initial mapped MOM', bytes(machine.cpu.mem_read(factory.DATA, len(raw))), lifetime['initial_raw'])
        machine.set_animation_faults(faults, True)
        for step in lifetime['selections']:
            previous_mismatches = len(bad)
            machine.cpu.mem_write(returned + 132, struct.pack('<I', step['counter']))
            before = len(machine.selection_entries)
            machine.call('func_80066214', returned, step['index'])
            if machine.selection_entries[before:] != [(returned, step['index'])]:
                raise ValueError('Original animation selection was not entered with the planned arguments.')
            for payload in step['payloads']:
                actual = bytes(machine.cpu.mem_read(payload.pointer, len(payload.expected)))
                if actual != payload.expected:
                    bad.append(dict(index=step['index'], kind=payload.kind, pointer=hex(payload.pointer),
                        first_difference=next(i for i, (a, b) in enumerate(zip(actual, payload.expected)) if a != b),
                        actual_sha256=factory.common.sha(actual), expected_sha256=factory.common.sha(payload.expected)))
            mapped = bytes(machine.cpu.mem_read(factory.DATA, len(raw)))
            if mapped != step['raw']:
                bad.append(dict(index=step['index'], kind='complete mapped MOM',
                    actual_sha256=factory.common.sha(mapped), expected_sha256=factory.common.sha(step['raw'])))
            manager = bytes(machine.cpu.mem_read(factory.MANAGER, 0x100))
            if manager != step['manager']:
                bad.append(dict(index=step['index'], kind='complete allocation manager'))
            observations.append(dict(index=step['index'], counter_before=step['counter'],
                live_payloads=len(step['payloads']), payload_bytes=sum(len(row.expected) for row in step['payloads']),
                complete_MOM_bytes=len(raw), matched=len(bad) == previous_mismatches))
        machine.set_animation_faults(faults, False)
        if scenario != 'model-first':
            if machine.call('base_class_destructor', returned) != 0:
                raise ValueError('Original actor destruction failed.')
    if scenario != 'owned' and machine.call('file_buf_destroy', shared) != 0:
        raise ValueError('Original shared model destruction failed.')
    factory.compare_events(machine.actual, plan.events)
    factory.common.equal_buffer('complete manager after destruction', bytes(machine.cpu.mem_read(factory.MANAGER, 0x100)), bytes(plan.pool.buffers['manager']))
    expected_raw = mapped_model_bytes(raw, factory.DATA, plan.models[0].animations, tuple(plan.geometry_indices), destroyed=True)
    factory.common.equal_buffer('complete mapped MOM after destruction', bytes(machine.cpu.mem_read(factory.DATA, len(raw))), expected_raw)
    for address, expected in ((factory.DATA - 32, data[:32]), (factory.DATA + len(raw), data[-32:]),
            (factory.MODEL_INPUT - 32, model_input), (child.SDK_TABLE, child.SDK_MATRIX)):
        factory.common.equal_buffer('input guard', bytes(machine.cpu.mem_read(address, len(expected))), bytes(expected))
    if machine.pending is not None or len(machine.observed.blocks) != 1 or not machine.observed.blocks[0].free:
        raise ValueError('Original allocator history did not release every owned allocation.')
    if any(not row['matched'] for row in machine.model_payload_snapshots + machine.actor_payload_snapshots):
        raise ValueError('Original initial construction differs from its independent complete-payload model.')
    return dict(status='passed_bounded_animation_history' if not bad else 'failed_animation_payload_comparison',
        scenario=scenario, pattern=pattern, observations=observations, mismatches=bad,
        actor_lifetimes=len(lifetimes), native_history_completed=True, all_owned_allocations_released=True,
        actual_heap_events=machine.actual, native_entry_counts=dict(machine.entries),
        changed_instruction_hits={hex(address): machine.animation_fault_hits[address & factory.common.native.MASK] for address, _old, _new in faults},
        dependency_output_stubs=0, prior_counters_injected=True,
        initial_construction_preserved=True, faults_active_only_during_explicit_selections=True)


def run_controls(program, ranges, names, inventory, output):
    """Require completed wrong-output histories, rather than crashes or timeouts."""
    source, model = next((source, model) for source in inventory['files']
                        for model in source['models'] if model['sha256'] == CONTROL_MODEL_SHA256)
    asset = Path(source['source']).read_bytes()
    raw = asset[model['offset']:model['offset'] + model['bytes']]
    if factory.common.sha(asset) != source['sha256'] or factory.common.sha(raw) != model['sha256']:
        raise ValueError('The animation fault-control resource changed.')
    controls = []
    for fault in ANIMATION_FAULTS:
        for pattern in child.PATTERNS:
            for scenario in factory.SCENARIOS:
                result = run_case(program, ranges, names, raw, pattern, scenario, (fault['patch'],))
                case = 'fault-' + str(len(controls)).zfill(2) + '-' + fault['name']
                factory.common.write_json(output / (case + '.json'), result)
                if (result['status'] != 'failed_animation_payload_comparison'
                        or not result['mismatches'] or not result['native_history_completed']
                        or not result['all_owned_allocations_released']
                        or not all(result['changed_instruction_hits'].values())):
                    raise ValueError('Animation fault did not finish and expose wrong output: ' + case)
                controls.append(dict(case=case, name=fault['name'], scenario=scenario, pattern=pattern,
                    model_sha256=model['sha256'], resource_path=source['path'], model_offset=model['offset'],
                    detected=True, native_history_completed=True, initial_construction_preserved=True,
                    changed_instruction_hits=result['changed_instruction_hits'],
                    wrong_payload_snapshots=len(result['mismatches']),
                    detection=result['mismatches'][0]))
    return controls


def verify(layout, output, edition_label):
    output = factory.common.output_directory(output)
    backend = factory.common.heap.backend_identity()
    require_backend(backend)
    factory.common.require_ninja()
    before = factory.common.build_inputs()
    dependencies = (*factory.DEPENDENCIES, 'tools/verify_actor_animations.py', 'tools/actor_animation_model.py')
    producer_hashes = {name: factory.common.sha((ROOT / name).read_bytes()) for name in dependencies}
    functions = json.loads(factory.RANGES.read_bytes())['functions']
    program = factory.common.native.load_program(functions)
    inventory = factory.common.inspect_animations(layout)
    factory.common.corpus_models(inventory)
    output.mkdir(parents=True, exist_ok=False)
    ranges, diagnostic = factory.common.symbol_diagnostic(program, output, functions)
    names = dict(program.symbols)
    for line in subprocess.check_output([factory.configure.CROSS + 'nm', '--defined-only', str(output / 'canonical-symbols.elf')], text=True).splitlines():
        fields = line.split()
        if len(fields) == 3:
            names[fields[2]] = int(fields[0], 16)
    factory.common.write_json(output / 'inventory.json', inventory)
    (output / 'source-snapshot.py').write_bytes(Path(__file__).read_bytes())
    (output / 'model-source-snapshot.py').write_bytes((ROOT / 'tools/actor_animation_model.py').read_bytes())
    rows, entries, seen_models, began = [], Counter(), set(), time.monotonic()
    coverage = set()
    for source in inventory['files']:
        asset = Path(source['source']).read_bytes()
        if factory.common.sha(asset) != source['sha256']:
            raise ValueError('Original model asset changed.')
        for model in source['models']:
            raw = asset[model['offset']:model['offset'] + model['bytes']]
            if factory.common.sha(raw) != model['sha256']:
                raise ValueError('Original MOM extent changed.')
            seen_models.add(model['sha256'])
            for pattern in child.PATTERNS:
                for scenario in factory.SCENARIOS:
                    result = run_case(program, ranges, names, raw, pattern, scenario)
                    case = 'case-' + str(len(rows)).zfill(4)
                    factory.common.write_json(output / (case + '.json'), result)
                    if result['status'] != 'passed_bounded_animation_history':
                        raise ValueError('Retained unsuccessful animation history: ' + case)
                    indices = {step['index'] for step in result['observations']}
                    if indices != set(range(model['animation_count'])):
                        raise ValueError('A valid animation index was not executed.')
                    coverage.update((source['path'], model['offset'], index) for index in indices)
                    entries.update(result['native_entry_counts'])
                    rows.append(dict(case=case, model_sha256=model['sha256'], scenario=scenario, pattern=pattern,
                        actor_lifetimes=result['actor_lifetimes'], selections=len(result['observations']),
                        payloads_compared=sum(step['live_payloads'] for step in result['observations']),
                        payload_bytes=sum(step['payload_bytes'] for step in result['observations']),
                        mapped_MOM_bytes=sum(step['complete_MOM_bytes'] for step in result['observations'])))
            if len(rows) % 48 == 0:
                print(json.dumps(dict(completed_histories=len(rows), animation_instance_indices=len(coverage))), flush=True)
    if (factory.common.build_inputs() != before or factory.common.heap.backend_identity() != backend
            or any(factory.common.sha((ROOT / name).read_bytes()) != checksum for name, checksum in producer_hashes.items())):
        raise ValueError('Sources, backend or canonical game inputs changed during verification.')
    if len(coverage) != inventory['totals']['animations']:
        raise ValueError('Incomplete original animation-instance coverage.')
    controls = run_controls(program, ranges, names, inventory, output)
    if (factory.common.build_inputs() != before or factory.common.heap.backend_identity() != backend
            or any(factory.common.sha((ROOT / name).read_bytes()) != checksum for name, checksum in producer_hashes.items())):
        raise ValueError('Sources, backend or canonical game inputs changed during fault controls.')
    report = dict(status='passed_bounded_original_animation_selection', recorded_utc=datetime.now(timezone.utc).isoformat(),
        edition_label=edition_label, edition_label_is_user_supplied=True,
        original_model_instances=inventory['totals']['validated_MOM_instances'], distinct_model_contents=len(seen_models),
        animation_instance_indices=len(coverage), completed_histories=len(rows),
        actor_lifetimes=sum(row['actor_lifetimes'] for row in rows), animation_selections=sum(row['selections'] for row in rows),
        live_payloads_compared=sum(row['payloads_compared'] for row in rows),
        live_payload_bytes=sum(row['payload_bytes'] for row in rows), mapped_MOM_bytes=sum(row['mapped_MOM_bytes'] for row in rows),
        actual_native_entry_counts=dict(entries), qualified_native_functions=functions, symbol_diagnostic=diagnostic,
        rows=rows, fault_controls=controls, backend_identity=backend, producer_dependencies=producer_hashes,
        canonical_sha256=factory.common.sha(program.ROM), all_game_build_inputs_preserved=True,
        dependency_output_stubs=0, new_C_bytes=0, newly_profiled_NPC_callbacks=0,
        whole_NPC_encounters_accepted=0, whole_feature_groups_accepted=0, model_API_calls=0,
        user_game_controlled=False, original_game_modified=False,
        scope='All supplied validated MOM instances, valid animation indices and immediate first-frame commands after original construction, through owned/shared/model-first histories. Prior frame counters are injected before each selection. Live capacities, mapped MOM bytes, allocator events, manager and guards are compared. No later-frame playback, natural encounter, full engine stepping, rendering, audio or PS1 timing acceptance.',
        elapsed_seconds=round(time.monotonic() - began, 3))
    factory.common.write_json(output / 'report.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--edition-label', default='unspecified')
    args = parser.parse_args(argv)
    report = verify(args.layout, args.output, args.edition_label)
    print(json.dumps({key: report[key] for key in ('status', 'animation_instance_indices', 'completed_histories', 'animation_selections')}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
