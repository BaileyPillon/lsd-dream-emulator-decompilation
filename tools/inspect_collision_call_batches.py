"""Verify every primitive call in one route through disjoint ordinal recordings.

This does not accept hull returns, full instruction paths, opaque CPU/GTE state,
allocation ownership, other input histories, or whole-feature parity.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path, PureWindowsPath
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import inspect_dispatch_history as history
from tools.collision_call_batches import PROGRAM_NAME
from tools.collision_calls import PC, selection
from tools.inspect_collision_calls import compare_calls, inspect_call_recording
from tools.replay_cold_start_headless import require, write_json
from tools.runtime_inputs import content_identity
from research.compiler.compare_function import CANONICAL_SHA256


def verify_partition_coverage(entries, batches):
    require(isinstance(batches, list) and batches, 'Require a nonempty ordinal batch collection.')
    eligible = [index for index, row in enumerate(entries, 1) if row['pc'] == PC]
    require(eligible, 'The route has no original primitive entries.')
    step = batches[0]['settings'].get('ordinal_step')
    require(type(step) is int and 1 <= step <= 64 and len(batches) == step,
            'The collection must contain every ordinal phase exactly once.')
    phases, covered, calls = set(), Counter(), []
    for batch in batches:
        settings, verification = batch['settings'], batch['verification']
        first = settings.get('ordinal_first')
        require(type(first) is int and 1 <= first <= step and first not in phases
                and type(settings.get('ordinal_step')) is int and settings['ordinal_step'] == step,
                'Duplicate, missing, or inconsistent ordinal phase.')
        phases.add(first)
        require(all(type(verification['policy'].get(key)) is int and verification['policy'][key] == 0 for key in
                    ('nested_skips', 'sample_limit_skips', 'duplicate_key_skips', 'frame_budget_skips')),
                'A complete ordinal partition cannot drop primitive calls.')
        expected = set(eligible[first - 1::step])
        actual = [row['base_ordinal'] for row in verification['calls']]
        require(all(type(value) is int for value in actual) and len(actual) == len(set(actual))
                and set(actual) == expected and type(verification['completed_samples']) is int
                and verification['completed_samples'] == len(actual)
                and type(verification['policy']['eligible_entries']) is int
                and verification['policy']['eligible_entries'] == len(eligible)
                and type(verification['policy'].get('ordinal_skips')) is int
                and verification['policy']['ordinal_skips'] == len(eligible) - len(actual),
                'An ordinal phase is missing, repeating, or misidentifying original calls.')
        covered.update(actual)
        calls.extend(verification['calls'])
    require(phases == set(range(1, step + 1)) and set(covered) == set(eligible)
            and all(count == 1 for count in covered.values()),
            'The route primitive-entry partition is incomplete or overlapping.')
    calls.sort(key=lambda row: row['base_ordinal'])
    return dict(status='verified_complete_primitive_entry_partition_for_one_route',
                original_primitive_entries=len(eligible), completed_primitive_calls=len(calls),
                phases=step, every_observed_route_primitive_call_verified=True,
                result_counts=dict(sorted(Counter(str(row['result']) for row in calls).items())),
                polygon_visits=sum(row['primitive_count'] for row in calls),
                observed_model_addresses=len({row['model_address'] for row in calls}),
                observed_geometry_addresses=len({row['geometry_address'] for row in calls}),
                calls_crossing_a_frame=sum(row['entry_frame'] != row['return_frame'] for row in calls),
                base_ordinals=[row['base_ordinal'] for row in calls],
                calls=calls, complete_state_parity_checked=False, whole_feature_groups_accepted=0, new_C_bytes=0)


def _program_without_phase(program):
    selected = selection(program)
    require(selected is not None and 'ordinal_step' in selected, 'Require the declared ordinal primitive policy.')
    normalized = copy.deepcopy(program)
    del normalized['method_trace']['collision_calls']['ordinal_first']
    return normalized


def _settings_without_phase(settings):
    normalized = copy.deepcopy(settings)
    require(isinstance(normalized.get('collision_calls'), dict)
            and type(normalized['collision_calls'].get('ordinal_first')) is int,
            'Missing actual ordinal observer settings.')
    del normalized['collision_calls']['ordinal_first']
    return normalized


def _require_program_snapshot(retained):
    matches = [row for row in retained['manifest']['source_snapshots']
               if PureWindowsPath(row['original']['path']).name == PROGRAM_NAME]
    require(len(matches) == 1, 'Require the uniquely retained ordinal controller program source.')
    raw = history.owned_file(retained['folder'], matches[0]['file']).read_bytes()
    require(json.loads(raw) == retained['program'], 'Retained ordinal program and actual route differ.')


def compare_recordings(left, right, *, different_phase=False):
    """Compare already inspected observer recordings; permit only a declared phase change."""
    require(left['folder'] != right['folder'],
            'Independent comparisons require distinct recording directories.')
    a, b = left['manifest'], right['manifest']
    require(a['runtime_kind'] == b['runtime_kind'] == 'dispatch_observer',
            'Ordinal recording pairs require the same separate observer runtime.')
    if different_phase:
        require(_program_without_phase(left['program']) == _program_without_phase(right['program'])
                and _settings_without_phase(a['settings']) == _settings_without_phase(b['settings']),
                'Ordinal partitions changed more than the declared selection phase.')
        _require_program_snapshot(left)
        _require_program_snapshot(right)
    else:
        require(left['program'] == right['program'] and a['settings'] == b['settings'],
                'Original/rebuilt ordinal programs or actual observer settings differ.')
    for key in ('bios', 'disc'):
        if key == 'bios':
            identities = lambda value: {name: content_identity(item) for name, item in value['source_manifest']['bios'].items()}
        else:
            identities = lambda value: [content_identity(item) for item in value['source_manifest']['disc']['tracks']]
        require(identities(a) == identities(b), 'Ordinal recording BIOS or complete disc identities differ.')
    runtime = lambda value: {name: content_identity(item) for name, item in value['actual_runtime_files'].items()}
    require(runtime(a) == runtime(b), 'Ordinal recording native runtime identities differ.')
    source_a, source_b = left['producer_sources'], right['producer_sources']
    changed = {name for name in set(source_a) | set(source_b) if source_a.get(name) != source_b.get(name)}
    require(changed <= ({PROGRAM_NAME} if different_phase else set()),
            'Ordinal recording producer sources or compiler identities differ.')
    require(content_identity(a['submitted']) == content_identity(b['submitted']),
            'Ordinal selection changed submitted controller bytes.')
    require(left['entries'] == right['entries'], 'Ordinal partitions changed original method entry history.')
    require(left['frames'] == right['frames'] and left['RAM'] == right['RAM']
            and left['native']['checkpoints'] == right['native']['checkpoints'],
            'Ordinal recording GPU/RAM/PCM observations or checkpoint metadata differ.')
    out_a, out_b = left['folder'] / 'observations', right['folder'] / 'observations'
    require(history.files_equal(out_a / 'audio.pcm', out_b / 'audio.pcm'), 'Complete ordinal PCM output differs.')
    for row in left['native']['checkpoints']:
        for prefix in ('mainram', 'gpu', 'rgb'):
            name = f"{prefix}-{row['relative_frame']}.bin"
            require(history.files_equal(out_a / name, out_b / name), 'Complete ordinal checkpoint differs: ' + name)
    return dict(every_recorded_game_output_equal=True, original_method_entry_histories_equal=True,
                permitted_difference='ordinal_first only' if different_phase else 'none')


def _capture(root, relative):
    require(isinstance(relative, str) and not Path(relative).is_absolute()
            and '\\' not in relative and '..' not in Path(relative).parts,
            'Use owned relative recording paths in the ordinal collection.')
    folder = (root / relative).resolve(strict=True)
    require(folder.is_relative_to(root) and folder.is_dir(), 'An ordinal recording escaped its collection directory.')
    return folder


def inspect_collection(manifest_file):
    manifest_file = Path(manifest_file).resolve(strict=True)
    root = manifest_file.parent
    original_manifest = manifest_file.read_bytes()
    collection = json.loads(original_manifest)
    require(type(collection.get('schema_version')) is int and collection['schema_version'] == 1
            and collection.get('type') == 'ordinal_collision_recording_collection'
            and isinstance(collection.get('reference'), list) and isinstance(collection.get('candidate'), list)
            and type(collection.get('ordinal_step')) is int
            and len(collection['reference']) == len(collection['candidate']) == collection['ordinal_step']
            and collection.get('canonical_executable_sha256') == CANONICAL_SHA256,
            'Require a complete declared original/rebuilt ordinal collection.')
    plan_path = history.owned_file(root, collection['program_plan'])
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes)
    require(plan.get('status') == 'prepared_ordinal_collision_programs'
            and type(plan.get('ordinal_step')) is int and plan['ordinal_step'] == collection['ordinal_step']
            and isinstance(plan.get('programs'), list) and len(plan['programs']) == collection['ordinal_step'],
            'The retained ordinal preparation plan is incomplete.')
    program_root = _capture(root, collection['prepared_programs'])
    programs = {}
    for row in plan['programs']:
        require(type(row.get('first')) is int and 1 <= row['first'] <= collection['ordinal_step']
                and row['first'] not in programs, 'Prepared ordinal phases are incomplete or duplicated.')
        raw = history.owned_file(program_root, row['program']).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == row['sha256'], 'A prepared ordinal controller program changed.')
        program = json.loads(raw)
        require(program.get('frames') == plan.get('frames')
                and program.get('expanded_submitted_sha256') == plan.get('expanded_submitted_sha256'),
                'The retained preparation plan and actual controller program disagree.')
        programs[row['first']] = program
    batches, candidate_batches, comparisons = [], [], []
    anchor = None
    source_reports = []
    for reference, candidate in zip(collection['reference'], collection['candidate']):
        reference_path, candidate_path = _capture(root, reference), _capture(root, candidate)
        before, left = inspect_call_recording(reference_path)
        after, right = inspect_call_recording(candidate_path)
        selected = selection(left['program'])
        require('ordinal_step' in selected and selected == selection(right['program']),
                'A recording pair uses different or nonordinal selection.')
        require(left['program'] == programs.get(selected['ordinal_first']),
                'The actual ordinal recording differs from its retained preparation plan.')
        comparison = compare_recordings(left, right)
        require(before['collision_calls'] == after['collision_calls'],
                'Original/rebuilt complete collision records, RAM, or geometry results differ.')
        if anchor is None:
            anchor = left
        else:
            compare_recordings(anchor, left, different_phase=True)
        batches.append(dict(settings=selected, verification=before['collision_calls']))
        candidate_batches.append(dict(settings=selected, verification=after['collision_calls']))
        comparisons.append(dict(first=selected['ordinal_first'], reference=reference, candidate=candidate, **comparison))
        source_reports.append(dict(first=selected['ordinal_first'],
            reference_manifest_sha256=hashlib.sha256((reference_path/'run-inputs.json').read_bytes()).hexdigest(),
            candidate_manifest_sha256=hashlib.sha256((candidate_path/'run-inputs.json').read_bytes()).hexdigest(),
            records_sha256=before['collision_calls']['binary_records_sha256'],
            complete_RAM_payload_sha256=before['collision_calls']['complete_RAM_payload_sha256']))
    coverage = verify_partition_coverage(anchor['entries'], batches)
    candidate_coverage = verify_partition_coverage(anchor['entries'], candidate_batches)
    require(coverage == candidate_coverage, 'Original/rebuilt complete route collision partitions differ.')
    require(coverage['phases'] == collection['ordinal_step'], 'Observed and declared ordinal partition sizes differ.')
    coverage['observation_frame_window'] = dict(first=anchor['program']['method_trace']['arm_frame'],
                                              last=anchor['manifest']['settings']['frames'])
    stock = compare_calls(_capture(root, collection['reference'][0]), _capture(root, collection['stock']), 'observer-output')
    require(manifest_file.read_bytes() == original_manifest and plan_path.read_bytes() == plan_bytes,
            'The ordinal collection or preparation plan changed during verification.')
    sources = ['tools/inspect_collision_call_batches.py', 'tools/inspect_collision_calls.py',
               'tools/collision_calls.py', 'tools/collision_call_batches.py', 'tools/inspect_dispatch_history.py']
    return dict(status='verified_all_observed_primitive_calls_in_one_original_route',
                manifest_sha256=hashlib.sha256(original_manifest).hexdigest(), coverage=coverage,
                preparation_plan_sha256=hashlib.sha256(plan_bytes).hexdigest(),
                original_rebuilt_complete_samples_and_RAM_equal=True, every_recorded_game_output_equal=True,
                all_partitions_preserve_the_same_entry_history=True, comparisons=comparisons,
                stock_control=stock, retained_recordings=source_reports,
                verifier_sources={name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources},
                original_game_behavior_modified=False, hull_returns_verified=False,
                complete_state_parity_checked=False, full_instruction_paths_accepted=False,
                geometry_allocation_ownership_accepted=False, original_hardware_timing_verified=False,
                whole_feature_groups_accepted=0, new_C_bytes=0)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        output = args.output.resolve()
        require(output.is_relative_to(ROOT/'.decomp-lab') and not output.exists(), 'Choose a fresh private ordinal collection report.')
        report = inspect_collection(args.manifest)
        write_json(output, report)
        print(json.dumps(dict(status=report['status'], primitive_calls=report['coverage']['completed_primitive_calls'])))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
