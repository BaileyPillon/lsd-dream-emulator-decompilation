"""Compare every supplied MOM frame through original actor playback routines.

One complete cycle, a following tick and pause/resume per valid animation;
both residue patterns and owned/shared/model-first destruction histories.
Callbacks stay disabled by the original constructor. This is a bounded
interpreter profile, not a natural encounter, renderer or PS1 timing test.
"""
from collections import Counter
from datetime import datetime, timezone
import argparse
import gc
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import verify_actor_animations as animation
from tools import actor_child_model as child
from tools.actor_playback_model import PlaybackPlan
from tools.model_mapping_model import mapped_model_bytes

factory = animation.factory
common = factory.common
RANGES = ROOT / 'docs/actor-playback-function-ranges.json'
TICK = 'func_80065FD8'
FAULTS = (
    dict(name='frame-counter-increments-by-two', patch=(0x80066054, 0x24420001, 0x24420002)),
    dict(name='multi-frame-playback-held', patch=(0x80066024, 0x28420002, 0x28427fff)),
    dict(name='paused-ticks-still-advance', patch=(0x8006600c, 0x8e020090, 0x24020001)),
    dict(name='root-dirty-flag-not-cleared', patch=(0x800660a4, 0xac400000, 0)),
)


def prepare(raw, names, pattern, scenario, program):
    pool = factory.initial_pool(pattern)
    pool.setup()
    angles = child.rational_values(program.target(names['D_8006B684'], 12))
    scales = child.rational_values(program.target(names['D_8006B690'], 12))
    plan = PlaybackPlan(raw, pool, names, factory.DATA, angles, scales)
    shared = None if scenario == 'owned' else plan.create_model()
    lifetimes = []
    for _ in range(2 if scenario == 'actor-first' else 1):
        actor = plan.create_actor(shared)
        initial = mapped_model_bytes(raw, factory.DATA, actor.model.animations, tuple(plan.geometry_indices))
        actions = []

        def freeze(method, payloads, index, argument=None, frame=None):
            actions.append(dict(method=method, argument=argument, expected=payloads,
                expected_frames=[] if frame is None else [(actor.pointer, factory.DATA + frame.offset, 0)],
                frame_identity=None if frame is None else (index, frame.index),
                raw=mapped_model_bytes(raw, factory.DATA, actor.model.animations, tuple(plan.geometry_indices)),
                manager=bytes(pool.buffers['manager']),
                counter=plan.word(actor.pointer, 132), cursor=plan.word(actor.pointer, 136),
                age=plan.word(actor.pointer, 36), playing=plan.word(actor.pointer, 144)))

        for index, frames in enumerate(plan.scripts):
            freeze('func_80066214', plan.select_animation(actor, index), index, index, frames[0])
            freeze('func_800662A8', plan.play(actor), index)
            for tick in range(len(frames) + 1):
                if tick == 1:
                    freeze('func_800662B4', plan.pause(actor), index)
                    for _ in range(2):
                        freeze(TICK, plan.tick(actor), index, frame=plan.last_tick_frame)
                    freeze('func_800662A8', plan.play(actor), index)
                freeze(TICK, plan.tick(actor), index, frame=plan.last_tick_frame)
            freeze('func_800662B4', plan.pause(actor), index)
        lifetimes.append(dict(actor=actor.pointer, initial_raw=initial, actions=actions))
        if scenario != 'model-first':
            plan.destroy_actor(actor)
    if shared is not None:
        plan.destroy_model(shared)
    if plan.live or len(pool.blocks) != 1 or not pool.blocks[0].free:
        raise ValueError('Independent playback history retained owned allocations.')
    return plan, lifetimes


class Machine(animation.Machine):
    def __init__(self, *args, **kwargs):
        self.frame_entries = []
        super().__init__(*args, **kwargs)

    def code_hook(self, cpu, address, size, unused):
        if address & common.native.MASK == self.program.symbols['func_800662BC'] & common.native.MASK:
            self.frame_entries.append(tuple(cpu.reg_read(getattr(self.reg, 'UC_MIPS_REG_A' + str(i))) for i in range(3)))
        super().code_hook(cpu, address, size, unused)


def run_case(program, ranges, names, raw, pattern, scenario, faults=()):
    plan, lifetimes = prepare(raw, names, pattern, scenario, program)
    machine = Machine(program, ranges, names, raw, pattern, plan.events, (),
                      plan.model_payloads[0], plan.actor_payloads, plan.actor_returns)
    guards, model_input = animation.initialize(machine, program, ranges, names, raw, pattern)
    shared = machine.call('func_8004468C', factory.MODEL_INPUT) if scenario != 'owned' else 0
    observations, bad, covered = [], [], set()
    for lifetime in lifetimes:
        descriptor = child.filled(80, pattern, 197)
        struct.pack_into('<4I', descriptor, 32, *((0, 0, 0, shared) if shared else (factory.DATA, 0, 1, 0)))
        machine.cpu.mem_write(factory.ACTOR_INPUT - 32, bytes(descriptor))
        returned = machine.call('actor_create', factory.ACTOR_INPUT, 0)
        if returned != lifetime['actor']:
            raise ValueError('Original actor return differs from the independent allocation plan.')
        common.equal_buffer('initial complete MOM', bytes(machine.cpu.mem_read(factory.DATA, len(raw))), lifetime['initial_raw'])
        for action in lifetime['actions']:
            number, previous_bad = len(observations), len(bad)
            begin = len(machine.frame_entries)
            args = (returned,) if action['argument'] is None else (returned, action['argument'])
            if action['method'] == TICK:
                machine.set_animation_faults(faults, True)
            machine.call(action['method'], *args)
            if action['method'] == TICK:
                machine.set_animation_faults(faults, False)
            actual_frames = machine.frame_entries[begin:]
            if actual_frames != action['expected_frames']:
                bad.append(dict(action=number, kind='original frame-dispatch arguments',
                    actual=actual_frames, expected=action['expected_frames']))
            elif action['frame_identity'] is not None:
                covered.add(action['frame_identity'])
            for payload in action['expected']:
                actual = bytes(machine.cpu.mem_read(payload.pointer, len(payload.expected)))
                if actual != payload.expected:
                    bad.append(dict(action=number, kind=payload.kind, pointer=hex(payload.pointer),
                        first_difference=next(i for i, (a, b) in enumerate(zip(actual, payload.expected)) if a != b),
                        actual_sha256=common.sha(actual), expected_sha256=common.sha(payload.expected)))
            common.equal_buffer('complete mapped MOM', bytes(machine.cpu.mem_read(factory.DATA, len(raw))), action['raw'])
            common.equal_buffer('complete manager', bytes(machine.cpu.mem_read(factory.MANAGER, 0x100)), action['manager'])
            observations.append(dict(method=action['method'], argument=action['argument'],
                expected_counter=action['counter'], expected_cursor=action['cursor'],
                expected_age=action['age'], expected_playing=action['playing'],
                native_frames_entered=len(actual_frames),
                live_payloads=len(action['expected']),
                payload_bytes=sum(len(row.expected) for row in action['expected']),
                mapped_MOM_bytes=len(raw), matched=len(bad) == previous_bad))
        common.equal_buffer('actor input and guards', bytes(machine.cpu.mem_read(factory.ACTOR_INPUT - 32, 80)), bytes(descriptor))
        if scenario != 'model-first' and machine.call('base_class_destructor', returned) != 0:
            raise ValueError('Original actor destruction failed.')
    if scenario != 'owned' and machine.call('file_buf_destroy', shared) != 0:
        raise ValueError('Original shared model destruction failed.')
    factory.compare_events(machine.actual, plan.events)
    common.equal_buffer('complete manager after destruction', bytes(machine.cpu.mem_read(factory.MANAGER, 0x100)), bytes(plan.pool.buffers['manager']))
    common.equal_buffer('complete MOM after destruction', bytes(machine.cpu.mem_read(factory.DATA, len(raw))),
        mapped_model_bytes(raw, factory.DATA, plan.models[0].animations, tuple(plan.geometry_indices), destroyed=True))
    for address, expected in ((factory.DATA - 32, guards[:32]), (factory.DATA + len(raw), guards[-32:]),
            (factory.MODEL_INPUT - 32, model_input), (child.SDK_TABLE, child.SDK_MATRIX)):
        common.equal_buffer('input guard', bytes(machine.cpu.mem_read(address, len(expected))), bytes(expected))
    if (machine.pending is not None or len(machine.observed.blocks) != 1 or not machine.observed.blocks[0].free
            or any(not row['matched'] for row in machine.model_payload_snapshots + machine.actor_payload_snapshots)):
        raise ValueError('Original construction or complete ownership release differs.')
    return dict(status='passed_bounded_original_playback' if not bad else 'failed_playback_output_comparison',
        pattern=pattern, scenario=scenario, actor_lifetimes=len(lifetimes), observations=observations,
        mismatches=bad, original_frames_entered=sorted(covered),
        actual_heap_events=machine.actual, original_function_entries=dict(machine.entries),
        native_history_completed=True, all_owned_allocations_released=True,
        changed_instruction_hits={hex(address): machine.animation_fault_hits[address & common.native.MASK]
                                  for address, _old, _new in faults},
        initial_construction_preserved=True, faults_active_only_during_tick_calls=True,
        injected_frame_counters=0, injected_frame_cursors=0, callbacks_enabled=False,
        dependency_output_stubs=0)


def run_controls(program, ranges, names, inventory, output):
    source, item = next((source, item) for source in inventory['files'] for item in source['models']
                        if item['sha256'] == animation.CONTROL_MODEL_SHA256)
    asset = Path(source['source']).read_bytes()
    raw = asset[item['offset']:item['offset'] + item['bytes']]
    if common.sha(asset) != source['sha256'] or common.sha(raw) != item['sha256']:
        raise ValueError('Playback control resource changed.')
    rows = []
    for fault in FAULTS:
        for pattern in child.PATTERNS:
            for scenario in factory.SCENARIOS:
                result = run_case(program, ranges, names, raw, pattern, scenario, (fault['patch'],))
                case = 'fault-' + str(len(rows)).zfill(2) + '-' + fault['name']
                common.write_json(output / (case + '.json'), result)
                if (result['status'] != 'failed_playback_output_comparison'
                        or not any('first_difference' in row for row in result['mismatches'])
                        or not result['native_history_completed'] or not all(result['changed_instruction_hits'].values())):
                    raise ValueError('Playback fault did not finish and expose wrong payloads: ' + case)
                rows.append(dict(case=case, name=fault['name'], pattern=pattern, scenario=scenario,
                    detected=True, native_history_completed=True, changed_instruction_hits=result['changed_instruction_hits'],
                    detection=next(row for row in result['mismatches'] if 'first_difference' in row)))
                gc.collect()
    return rows


def verify(layout, destination, edition_label):
    destination = common.output_directory(destination)
    backend = common.heap.backend_identity()
    animation.require_backend(backend)
    common.require_ninja()
    before = common.build_inputs()
    paths = (*factory.DEPENDENCIES, 'tools/verify_actor_animations.py', 'tools/actor_animation_model.py',
             'tools/actor_animation_fixtures.py', 'tools/actor_playback_model.py',
             'tools/verify_actor_playback.py', 'docs/actor-playback-function-ranges.json')
    dependencies = {path: common.sha((ROOT / path).read_bytes()) for path in paths}
    functions = json.loads(RANGES.read_bytes())['functions']
    program = common.native.load_program(functions)
    inventory = common.inspect_animations(layout)
    common.corpus_models(inventory)
    destination.mkdir(parents=True, exist_ok=False)
    ranges, diagnostic = common.symbol_diagnostic(program, destination, functions)
    names = dict(program.symbols)
    for line in subprocess.check_output([factory.configure.CROSS + 'nm', '--defined-only', str(destination / 'canonical-symbols.elf')], text=True).splitlines():
        fields = line.split()
        if len(fields) == 3:
            names[fields[2]] = int(fields[0], 16)
    common.write_json(destination / 'inventory.json', inventory)
    (destination / 'producer-snapshot.py').write_bytes(Path(__file__).read_bytes())
    (destination / 'model-source-snapshot.py').write_bytes((ROOT / 'tools/actor_playback_model.py').read_bytes())
    rows, coverage, entries, began = [], set(), Counter(), time.monotonic()
    for source in inventory['files']:
        asset = Path(source['source']).read_bytes()
        if common.sha(asset) != source['sha256']:
            raise ValueError('Original playback resource changed.')
        for item in source['models']:
            raw = asset[item['offset']:item['offset'] + item['bytes']]
            if common.sha(raw) != item['sha256']:
                raise ValueError('Original MOM extent changed.')
            for pattern in child.PATTERNS:
                for scenario in factory.SCENARIOS:
                    case = 'case-' + str(len(rows)).zfill(4)
                    result = run_case(program, ranges, names, raw, pattern, scenario)
                    common.write_json(destination / (case + '.json'), result)
                    if result['status'] != 'passed_bounded_original_playback':
                        raise ValueError('Retained unsuccessful playback history: ' + case)
                    expected = {(index, frame) for index, data in enumerate(item['animations']) for frame in range(data['frames'])}
                    if set(map(tuple, result['original_frames_entered'])) != expected:
                        raise ValueError('Original script frame coverage is incomplete.')
                    coverage.update((source['path'], item['offset'], index, frame) for index, frame in expected)
                    entries.update(result['original_function_entries'])
                    rows.append(dict(case=case, resource_path=source['path'], model_offset=item['offset'],
                        model_sha256=item['sha256'], pattern=pattern, scenario=scenario,
                        actor_lifetimes=result['actor_lifetimes'], actions=len(result['observations']),
                        tick_calls=sum(row['method'] == TICK for row in result['observations']),
                        payloads=sum(row['live_payloads'] for row in result['observations']),
                        payload_bytes=sum(row['payload_bytes'] for row in result['observations']),
                        MOM_bytes=sum(row['mapped_MOM_bytes'] for row in result['observations'])))
                    gc.collect()
            if len(rows) % 24 == 0:
                print(json.dumps(dict(completed_histories=len(rows), original_frame_instances=len(coverage))), flush=True)
    if len(coverage) != inventory['totals']['frames']:
        raise ValueError('Original frame corpus is incomplete.')
    controls = run_controls(program, ranges, names, inventory, destination)
    if (before != common.build_inputs() or backend != common.heap.backend_identity()
            or any(common.sha((ROOT / path).read_bytes()) != digest for path, digest in dependencies.items())):
        raise ValueError('Canonical game inputs, backend or playback sources changed during verification.')
    report = dict(status='passed_bounded_original_actor_playback_corpus', recorded_utc=datetime.now(timezone.utc).isoformat(),
        edition_label=edition_label, edition_label_is_user_supplied=True,
        original_model_instances=inventory['totals']['validated_MOM_instances'],
        distinct_model_contents=len({row['model_sha256'] for row in rows}),
        original_animation_instances=inventory['totals']['animations'], original_frame_instances=len(coverage),
        completed_histories=len(rows), actor_lifetimes=sum(row['actor_lifetimes'] for row in rows),
        explicit_actions=sum(row['actions'] for row in rows), tick_calls=sum(row['tick_calls'] for row in rows),
        live_payloads_compared=sum(row['payloads'] for row in rows), live_payload_bytes=sum(row['payload_bytes'] for row in rows),
        mapped_MOM_bytes=sum(row['MOM_bytes'] for row in rows), rows=rows, fault_controls=controls,
        original_function_entries=dict(entries), qualified_original_functions=functions, symbol_diagnostic=diagnostic,
        backend_identity=backend, producer_dependencies=dependencies, canonical_sha256=common.sha(program.ROM),
        game_build_inputs_preserved=True, injected_frame_counters=0, injected_frame_cursors=0,
        callbacks_enabled=False, dependency_output_stubs=0, new_C_bytes=0, new_NPC_profiles=0,
        whole_feature_groups_accepted=0, whole_NPC_encounters_accepted=0, model_API_calls=0,
        user_game_controlled=False, original_game_modified=False,
        scope='Every supplied validated MOM frame, explicit selection, pause/resume, one active cycle and following tick per animation, with owned/shared/model-first lifetimes. Complete live capacities, MOM mapping, allocator manager/events and guards are checked. Original constructors leave callbacks disabled. No callback, natural encounter, full engine scheduling, rendering, audio or PS1 timing acceptance.',
        elapsed_seconds=round(time.monotonic() - began, 3))
    common.write_json(destination / 'report.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--edition-label', default='unspecified')
    args = parser.parse_args(argv)
    report = verify(args.layout, args.output, args.edition_label)
    print(json.dumps({key: report[key] for key in ('status', 'original_frame_instances', 'completed_histories', 'tick_calls')}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
