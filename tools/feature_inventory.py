"""Refresh stable feature anchors against an immutable baseline and a verified build."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.decomp_workbench import catalog
from tools.progress import build_manifest, fallback_functions
from tools.verify_native_ai import NATIVE_FUNCTIONS
from tools.verify_gray_man import NATIVE_FUNCTIONS as GRAY_MAN_NATIVE_FUNCTIONS


def mask_comments(text):
    return re.sub(r'/\*.*?\*/|//[^\n]*',
                  lambda match: ''.join('\n' if char == '\n' else ' ' for char in match[0]), text, flags=re.S)


def locate_functions(sources):
    index = {}
    pattern = re.compile(r'(?m)^[ \t]*[A-Za-z_][\w \t*\n]*?\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{')
    for source, text in sources.items():
        masked = mask_comments(text)
        fallbacks = fallback_functions(text)
        for match in pattern.finditer(masked):
            name = match[1]
            if name not in fallbacks:
                index.setdefault(name, []).append((source, text.count('\n', 0, match.start(1)) + 1))
        for name in fallbacks:
            match = re.search(r'\bINCLUDE_ASM\s*\(\s*"[^"\n]+"\s*,\s*' + re.escape(name) + r'\b', masked)
            index.setdefault(name, []).append((source, text.count('\n', 0, match.start()) + 1))
    return index


def verify_progress_inputs(progress, root=ROOT):
    """Reject stale or unverified snapshots before writing any feature counts."""
    root = Path(root)
    hashes = progress.get("build_input_sha256")
    if not hashes or not progress["complete_objects"] or not progress["build_current"] or progress["binary_match"] != "verified":
        raise ValueError("A current matching progress snapshot with build-input hashes is required.")
    changed = [name for name, expected in hashes.items()
               if not (root / name).is_file() or hashlib.sha256((root / name).read_bytes()).hexdigest() != expected]
    if changed:
        raise ValueError("Build inputs changed after the progress snapshot: " + ', '.join(changed[:8]))


def verify_dispatch_inputs(dispatch, canonical_sha1, root=ROOT):
    if dispatch.get('canonical_sha1') != canonical_sha1 or dispatch.get('canonical_runtime_changed') is not False:
        raise ValueError('Dispatch inventory must describe the unchanged canonical executable.')
    if dispatch.get('header_layout_issues') or dispatch.get('unresolved_declarations'):
        raise ValueError('Dispatch declarations still have unresolved layout issues.')
    hashes = dispatch.get('source_sha256')
    if not hashes:
        raise ValueError('Dispatch source hashes are required.')
    for name, expected in hashes.items():
        path = Path(root) / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Dispatch source changed after the audit: ' + name)


def verify_animation_inputs(animations, canonical_sha1, root=ROOT):
    if (animations.get('canonical_executable_sha1') != canonical_sha1 or
            animations.get('original_executable', {}).get('sha1') != canonical_sha1 or
            animations.get('input_modified') is not False):
        raise ValueError('Animation inventory must preserve the canonical executable and original assets.')
    hashes = animations.get('source_sha256')
    dependencies = animations.get('dependency_sha256')
    producer = animations.get('producer', {})
    if not hashes or not dependencies or not producer.get('path') or not producer.get('sha256'):
        raise ValueError('Animation producer, dependency and native source hashes are required.')
    for name, expected in {**hashes, **dependencies, producer['path']: producer['sha256']}.items():
        path = Path(root) / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Animation audit source changed: ' + name)
    files = animations.get('files', [])
    if not files or len(files) != animations['totals']['input_files']:
        raise ValueError('Animation inventory file counts are inconsistent.')
    for record in files:
        path = Path(record['source'])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('Original animation asset changed: ' + record['path'])
    layout = Path(animations['layout'])
    if not layout.is_file() or hashlib.sha256(layout.read_bytes()).hexdigest() != animations['layout_sha256']:
        raise ValueError('Original animation extraction layout changed.')


def verify_entity_inputs(entities, canonical_sha1, root=ROOT):
    if (entities.get('canonical_sha1') != canonical_sha1 or
            entities.get('canonical_runtime_changed') is not False or
            entities.get('original_behavior_modified') is not False or
            entities.get('table', {}).get('all_initializers_match_native') is not True):
        raise ValueError('Entity inventory must describe unchanged canonical NPC properties and bindings.')
    hashes = entities.get('evidence_sha256')
    if not hashes or 'tools/inventory_entities.py' not in hashes:
        raise ValueError('Entity source, producer and executable evidence hashes are required.')
    for name, expected in hashes.items():
        path = Path(root) / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Entity audit evidence changed: ' + name)
    counts = entities['totals']
    records, callbacks = entities['records'], entities['callbacks']
    nonnull = [record for record in records if record['callback_function'] is not None]
    if (len(records) != counts['property_records'] or
            len(nonnull) != counts['nonnull_callback_slots'] or
            len(records) - len(nonnull) != counts['null_callback_slots'] or
            len(callbacks) != counts['distinct_callback_addresses'] or
            len({record['callback_address'] for record in nonnull}) != len(callbacks) or
            sum(callback['recovered_c'] for callback in callbacks) != counts['distinct_callbacks_recovered_c']):
        raise ValueError('Entity inventory callback/property counts are inconsistent.')


def native_runtime_summary(path, root=ROOT):
    """Keep a pinned native-state replay distinct from whole-feature acceptance."""
    path = Path(path).resolve()
    data = path.read_bytes()
    runtime = json.loads(data)
    observations = runtime.get('native_observations', {})
    if (runtime.get('equal_recorded_outputs') is not True or
            runtime.get('input_provenance', {}).get('inputs_verified') is not True or
            observations.get('equal_native_state') is not True or
            observations.get('output_compared') is not True or
            observations.get('frame_observations_per_run') != runtime.get('frames') or
            not observations.get('fields_per_observation')):
        raise ValueError('Additional native replay requires equal complete observations and verified inputs.')
    return {'comparison': path.relative_to(Path(root).resolve()).as_posix(),
            'comparison_sha256': hashlib.sha256(data).hexdigest(),
            'frames': runtime['frames'], 'checkpoints': len(runtime['checkpoints']),
            'status': runtime['status'], 'feature_groups_accepted': 0,
            'scope': observations['scope'],
            'fields_per_observation': observations['fields_per_observation'],
            'frame_observations_per_run': observations['frame_observations_per_run'],
            'input_phases': list(observations['phases']),
            'audio_output': runtime.get('audio_output', {}),
            'inputs_verified': True}


def verify_native_ai_validation(validation, canonical_sha1, root=ROOT):
    if (validation.get('canonical_executable_sha1') != canonical_sha1 or
            validation.get('original_and_current_build_equal') is not True or
            validation.get('original_behavior_modified') is not False or
            validation.get('status') != 'passed_bounded_original_npc_model' or
            validation.get('callback_runtime_accepted') is not False or
            validation.get('original_feature_groups_accepted') != 0):
        raise ValueError('Native AI validation must preserve scoped original behavior without whole-feature acceptance.')
    if (validation.get('function') not in ('entity_lion','entity_gray_man') or
            type(validation.get('model_api_calls')) is not int or validation['model_api_calls'] != 0):
        raise ValueError('Native AI validation requires a supported original NPC callback and zero model calls.')
    is_gray_man = validation['function'] == 'entity_gray_man'
    functions = GRAY_MAN_NATIVE_FUNCTIONS if is_gray_man else NATIVE_FUNCTIONS
    groups = validation.get('case_groups', {})
    if (not isinstance(groups, dict) or not groups or
            any(type(count) is not int or count <= 0 for count in groups.values()) or
            type(validation.get('native_cases')) is not int or validation['native_cases'] <= 0 or
            sum(groups.values()) != validation['native_cases'] or
            not validation.get('negative_controls_detected') or not validation.get('stubbed_calls')):
        raise ValueError('Native AI validation case/contract/control counts are inconsistent.')
    expected_groups = ({'inactive':256,'new_allocation_failure':128,'new_effect':128,'existing_effect':256}
                       if is_gray_man else {'rng':256,'active_animation':896,'inactive':432,'motion_offset':24})
    if groups != expected_groups:
        raise ValueError('Native AI validation does not cover the supported callback case groups.')
    if (validation.get('native_functions') != functions or
            validation.get('native_range_role') != 'Canonical byte inventory; entry execution is measured separately.'):
        raise ValueError('Native AI validation requires the canonical native range inventory.')
    executed = validation.get('executed_native_functions')
    native_names = {record['function'] for record in functions}
    required = native_names if is_gray_man else native_names - {'func_8001D1A4'}
    if (not isinstance(executed, list) or not executed or
            any(not isinstance(name, str) for name in executed) or
            len(set(executed)) != len(executed) or
            not set(executed).issubset(native_names) or not required.issubset(executed)):
        raise ValueError('Native AI validation requires unique measured entries for the claimed original chains.')
    if is_gray_man:
        counts = validation.get('native_entry_counts')
        expected_counts = {name:(768 if name == 'entity_gray_man' else 512 if name == 'entity_create_effect'
                                else 384) for name in native_names}
        if (not isinstance(counts,dict) or any(type(count) is not int for count in counts.values()) or
                counts != expected_counts or validation.get('entity_record') != 98):
            raise ValueError('Native AI validation requires measured Gray Man entry counts and property binding.')
    controls = validation['negative_controls_detected']
    known_controls = {
        'distance_boundary':(0x17C,'0x28420200','0x28420201'),
        'timer_boundary':(0x94,'0x2842003D','0x2842003E'),
        'state_two_movement':(0x210,'0x2411FFA0','0x2411FF9F'),
    }
    if is_gray_man:
        known_controls = {'wrong_movement':(0x98,'0x2405FFE2','0x2405FFE1'),
                          'skip_flashback_reset':(0x88,'0x0040F809','0x00000000')}
    if (not isinstance(controls, list) or len(controls) != len(known_controls) or
            any(not isinstance(control, dict) or not isinstance(control.get('name'),str) for control in controls) or
            {control.get('name') for control in controls} != set(known_controls) or
            any((control.get('function_offset'),control.get('expected_word'),control.get('changed_word'))
                != known_controls[control['name']] or control.get('execution_scope') !=
                'Private emulator memory; original executable and build unchanged.' for control in controls)):
        raise ValueError('Native AI validation requires the known private-memory mutation controls.')
    contracts = ['distance','dream_motion','entity_motion','movement','notification','orientation',
                 'scale','sound_entity_stop','trigger_ratio']
    if is_gray_man:
        contracts = ['effect_activate','effect_attach','effect_color','effect_create','movement','sound_entity_stop']
    if validation.get('stubbed_calls') != contracts:
        raise ValueError('Native AI validation requires the declared dependency contracts.')
    records = validation.get('producer_dependencies', [])
    if (not isinstance(records,list) or any(not isinstance(record,dict) or
            not isinstance(record.get('path'),str) or not isinstance(record.get('sha256'),str) for record in records)):
        raise ValueError('Native AI validation requires producer and native source hashes.')
    dependencies = {record['path']: record['sha256'] for record in records}
    required_dependencies = {'tools/verify_native_ai.py','tools/inventory_vtables.py','tools/progress.py',
        'configure.py','requirements-analysis.txt',
        'build/SLPS01556.map','build/undefined_funcs_auto.txt','build/undefined_syms_auto.txt',
        'src/scene/entity.c','src/scene/entity.h','src/dream/dream_sys.c','src/dream/dream_sys.h',
        'src/scene/actor.c','src/base/transform.c','asm/nonmatchings/psyq/libc/rand/rand.s'}
    if is_gray_man:
        required_dependencies |= {'tools/verify_gray_man.py','src/graphics/effect.c','src/graphics/effect.h'}
    if len(records) != len(dependencies) or not required_dependencies.issubset(dependencies):
        raise ValueError('Native AI validation requires producer and native source hashes.')
    for name, digest in dependencies.items():
        path = (Path(root) / name).resolve()
        if (not path.is_relative_to(Path(root).resolve()) or not path.is_file() or
                hashlib.sha256(path.read_bytes()).hexdigest() != digest):
            raise ValueError('Native AI validation evidence changed: '+name)


def refresh(inventory, progress_path, runtime_path=None, assets_path=None, dispatch_path=None, animations_path=None, entities_path=None, additional_runtime_paths=None, native_ai_validation_path=None):
    report = json.loads(Path(inventory).read_text())
    if dispatch_path is None and 'native_dispatch_inventory' in report:
        dispatch_path = ROOT / report['native_dispatch_inventory']['reference']
    if animations_path is None and 'native_animation_inventory' in report:
        animations_path = ROOT / report['native_animation_inventory']['reference']
    if entities_path is None and 'native_entity_inventory' in report:
        entities_path = ROOT / report['native_entity_inventory']['reference']
    if native_ai_validation_path is None and 'bounded_native_ai_validation' in report:
        native_ai_validation_path = [ROOT / entry['reference'] for entry in
            [report['bounded_native_ai_validation'],*report.get('additional_bounded_native_ai_validations',[])]]
    elif isinstance(native_ai_validation_path,(str,Path)):
        native_ai_validation_path = [native_ai_validation_path]
    baseline = json.loads((ROOT / ".decomp-lab/prompt-baseline.json").read_text())
    progress = json.loads(Path(progress_path).read_text())
    verify_progress_inputs(progress)
    sources = {name: (ROOT / name).read_text() for name, kind in build_manifest() if kind == "C"}
    index = locate_functions(sources)
    remaining = catalog()
    after_fallbacks = {item["function"] for item in remaining}
    before_fallbacks = {name for names in baseline["fallbacks"].values() for name in names}
    now = datetime.now(timezone.utc).isoformat()
    features = report["features"]
    for feature in features:
        for anchor in feature["required_functions"]:
            name = anchor["function"]
            old_source = anchor.setdefault("before_source", anchor["source"])
            candidates = list(set(index.get(name, [])))
            preferred = [item for item in candidates if item[0] == anchor["source"]]
            if len(preferred) == 1:
                source, line = preferred[0]
            elif len(candidates) == 1:
                source, line = candidates[0]
            else:
                raise ValueError(f"No unique configured definition for {name}: {candidates}")
            anchor.update(source=source, line=line,
                          before="retained_assembly" if name in before_fallbacks else "recovered_c",
                          after="retained_assembly" if name in after_fallbacks else "recovered_c")
            if old_source not in baseline["sources"]:
                raise ValueError("An anchor's original source is absent from the baseline: " + old_source)
        for phase in ("before", "after"):
            outstanding = [anchor["function"] for anchor in feature["required_functions"] if anchor[phase] == "retained_assembly"]
            feature["c_recovery"][phase].update(core_complete=not outstanding,
                required_functions=len(feature["required_functions"]), retained_assembly_functions=outstanding,
                call_graph_exhaustive=False)
        feature["implementation"]["after"] = "original behavior inherited in the verified matching C plus assembly build"
    by_id = {feature["id"]: feature for feature in features}

    def support_complete(identifier, phase, visited=None):
        visited = set() if visited is None else visited
        feature = by_id[identifier]
        if not feature["c_recovery"][phase]["core_complete"]:
            return False
        if identifier in visited:
            return True
        visited = visited | {identifier}
        return all(support_complete(child, phase, visited) for child in feature["shared_support_features"])

    for feature in features:
        for phase in ("before", "after"):
            feature["c_recovery"][phase]["known_core_and_support_complete"] = support_complete(feature["id"], phase)
    callbacks = report["native_ai"]["callback_functions"]
    for callback in callbacks:
        callback["source"], callback["line"] = index[callback["function"]][0]
    after_callbacks = [callback["function"] for callback in callbacks if callback["function"] in after_fallbacks]
    report["native_ai"]["after_inventory_pass"].update(callbacks_recovered_c=len(callbacks)-len(after_callbacks),
        retained_assembly_callbacks=after_callbacks, runtime_validated_callbacks=0)
    report["native_ai"]["tooling_scope"] = {
        "user_confirmed": "Recover original NPC behavior and add separately measured AI-assisted tools, analysis and modding.",
        "canonical_runtime_changed_by_ai_tools": False,
        "context_exporter": "tools/decomp_workbench.py context",
        "private_matching_gate": "tools/decomp_workbench.py check",
        "native_analysis_server": "tools/start_analysis.ps1",
        "replay_comparator": "tools/compare_runtime.py",
        "context_bundle_model_invocation": False}
    report["developer_tooling"] = {
        "scope": "AI-assisted developer workflow, separate from original game and NPC features.",
        "capabilities_before_this_prompt": 0, "capabilities_after_this_prompt": 5,
        "baseline_basis": "These capabilities were introduced and exercised during this prompt; prior build/mod utilities are not included in this count.",
        "model_api_calls_by_these_tools": 0,
        "capabilities": [
            {"id": "A001", "name": "Verified AI-analysis context bundles", "entry": "tools/decomp_workbench.py context",
             "evidence": ".decomp-lab/ai-context-renderer/context.json"},
            {"id": "A002", "name": "Isolated complete-executable candidate comparison", "entry": "tools/decomp_workbench.py check",
             "evidence": ".decomp-lab/root-work/renderer-inline-full-check/comparison.json"},
            {"id": "A003", "name": "Native MIPS Ghidra context and local analysis API", "entry": "tools/start_analysis.ps1",
             "evidence": ".decomp-lab/ghidra/effect-start-attached-mcp.json"},
            {"id": "A004", "name": "Pinned checkpoint replay, state and PCM audio comparison", "entry": "tools/compare_runtime.py",
             "evidence": ".decomp-lab/runtime-play-comparison-checked.json"},
            {"id": "A005", "name": "Native disc asset inventory and texture inspection", "entry": "tools/inventory_disc.py",
             "evidence": ".decomp-lab/disc-asset-inventory-current.json"}]}
    for gap in report["unresolved_scope"]:
        if gap["id"] == "U005":
            gap.update(description="A pinned PS1 emulator comparison environment is available and recorded video/state/PCM subsets match. Exhaustive SDK/hardware timing, video/audio events, memory-card errors and disc behavior still require coverage and independent review.")
        if gap["id"] == "U006":
            gap.update(status="resolved_scope_clarification",
                description="User confirmed original NPC behavior and separate AI-assisted analysis/modding tools. Tooling additions do not change canonical gameplay or count as original features.")
    counts = {}
    for phase in ("before", "after"):
        counts[phase] = {"catalogued_feature_groups": len(features),
            "original_feature_groups_present_in_matching_c_plus_assembly": len(features),
            "core_logic_recovered_c": sum(feature["c_recovery"][phase]["core_complete"] for feature in features),
            "known_core_and_support_recovered_c": sum(feature["c_recovery"][phase]["known_core_and_support_complete"] for feature in features),
            "runtime_accepted_feature_groups": 0, "new_gameplay_features_implemented": 0,
            "native_behavior_callbacks_recovered_c": sum(callback["function"] not in (before_fallbacks if phase == "before" else after_fallbacks) for callback in callbacks)}
    report["snapshots"]["before_prompt"]["feature_counts"] = counts["before"]
    report["snapshots"]["after_inventory_pass"] = {"timestamp": now, "source_status_only": False,
        "source": Path(progress_path).resolve().relative_to(ROOT).as_posix(),
        "game_assembly_functions": len(remaining), "c_coverage_percent": progress["c_coverage_percent"],
        "matching_executable_sha1": progress["actual_sha1"], "binary_match": "verified",
        "build_objects": progress["objects_found"], "feature_counts": counts["after"], "inventory_scope_change": 0}
    if runtime_path:
        runtime = json.loads(Path(runtime_path).read_text())
        if not runtime["equal_recorded_outputs"]:
            raise ValueError("Runtime comparison does not have equal recorded outputs.")
        reference = Path(runtime_path).resolve().relative_to(ROOT).as_posix()
        report["runtime_evidence"] = {"comparison": reference, "frames": runtime["frames"],
            "checkpoints": len(runtime["checkpoints"]), "status": runtime["status"],
            "feature_groups_accepted": 0, "scope": runtime["scope"],
            "audio_output": runtime.get('audio_output', {'status': 'output_not_captured',
                'output_compared': False}),
            "input_provenance": runtime.get('input_provenance', {
                'status': 'legacy_inputs_not_pinned', 'inputs_verified': False})}
        report['developer_tooling']['capabilities'][3]['evidence'] = reference
        recorded_groups = ["F001", "F002", "F005", "F006", "F033", "F040"]
        if report['runtime_evidence']['audio_output'].get('equal_pcm_output'):
            recorded_groups.extend(["F030", "F031"])
        for identifier in recorded_groups:
            by_id[identifier]["runtime_validation"].update(status="recorded_subset_compared",
                evidence=[{"reference": reference, "scope": "One scripted play sequence; full feature scenario remains unaccepted."}])
    if additional_runtime_paths is not None:
        report['additional_runtime_evidence'] = [native_runtime_summary(path) for path in additional_runtime_paths]
    if native_ai_validation_path:
        validations, summaries = [], []
        for path in native_ai_validation_path:
            validation_bytes = Path(path).read_bytes()
            validation_digest = hashlib.sha256(validation_bytes).hexdigest()
            validation = json.loads(validation_bytes)
            verify_native_ai_validation(validation, report['target']['canonical_sha1'])
            if any(previous['function'] == validation['function'] for _,previous,_ in validations):
                raise ValueError('Native AI validation cannot count the same callback twice.')
            reference = Path(path).resolve().relative_to(ROOT).as_posix()
            summary = {'reference':reference,'reference_sha256':validation_digest, 'function':validation['function'],
                'native_cases':validation['native_cases'],'case_groups':validation['case_groups'],
                'negative_controls_detected':validation['negative_controls_detected'],
                'native_functions':validation['native_functions'],'native_range_role':validation['native_range_role'],
                'executed_native_functions':validation['executed_native_functions'],
                'stubbed_calls':validation['stubbed_calls'],'scope':validation['scope'],
                'callback_runtime_accepted':False,'original_feature_groups_accepted':0}
            if 'native_entry_counts' in validation:
                summary['native_entry_counts'] = validation['native_entry_counts']
            summaries.append(summary)
            validations.append((path,validation,validation_digest))
        report['bounded_native_ai_validation'] = summaries[0]
        report['additional_bounded_native_ai_validations'] = summaries[1:]
        report['native_ai']['bounded_execution_evidence'] = {
            'distinct_callbacks':len(summaries), 'native_fixture_cases':sum(item['native_cases'] for item in summaries),
            'callback_runtime_accepted':0, 'original_feature_groups_accepted':0,
            'scope':'Bounded models and explicit external contracts; separate from whole-callback acceptance.'}
        report['developer_tooling']['capabilities'].append({'id':'A009',
            'name':'Bounded original NPC execution and branch verification',
            'entry':'tools/verify_native_ai.py', 'evidence':summaries[0]['reference'],
            'additional_evidence':[summary['reference'] for summary in summaries[1:]]})
    if assets_path:
        assets = json.loads(Path(assets_path).read_text())
        executable = [item for item in assets["files"] if item["path"] == "/SLPS_015.56"]
        if (len(assets["files"]) != assets["file_count"] or len(executable) != 1 or
                executable[0]["sha1"] != report["target"]["canonical_sha1"] or assets["input_modified"]):
            raise ValueError("Asset inventory must preserve and identify the canonical disc executable.")
        report["asset_inventory"] = {
            "reference": Path(assets_path).resolve().relative_to(ROOT).as_posix(),
            "scope": assets["scope"], "file_count": assets["file_count"], "extensions": assets["extensions"],
            "stage_directories": len(assets["stage_directories"]),
            "texture_bank_tim_records": assets["texture_bank_tim_records"],
            "unresolved_texture_files": assets["unresolved_texture_files"],
            "semantic_content_audit_complete": False, "independent_runtime_content_coverage_complete": False}
    if dispatch_path:
        dispatch = json.loads(Path(dispatch_path).read_text())
        verify_dispatch_inputs(dispatch, report['target']['canonical_sha1'])
        reference = Path(dispatch_path).resolve().relative_to(ROOT).as_posix()
        report['native_dispatch_inventory'] = {
            'reference': reference, 'declared_tables': dispatch['declared_tables_audited'],
            'c_initializers_verified': dispatch['explicit_c_initializers_verified'],
            'declared_function_slots': dispatch['declared_function_slots'],
            'nonnull_declared_function_slots': dispatch['nonnull_declared_function_slots'],
            'unique_declared_function_addresses': dispatch['unique_declared_function_addresses'],
            'unbound_unsupported_type_views': dispatch['unsupported_types'],
            'unbound_supported_type_views': dispatch.get('unbound_type_views', []),
            'all_dynamic_dispatch_resolved': False, 'semantic_signature_review_complete': False,
            'scope': dispatch['scope']}
        report['developer_tooling']['capabilities'].append({
            'id': 'A006', 'name': 'Native virtual-table binding and layout audit',
            'entry': 'tools/inventory_vtables.py', 'evidence': reference})
    if animations_path:
        animations = json.loads(Path(animations_path).read_text())
        verify_animation_inputs(animations, report['target']['canonical_sha1'])
        reference = Path(animations_path).resolve().relative_to(ROOT).as_posix()
        report['native_animation_inventory'] = {
            'reference': reference, 'totals': animations['totals'],
            'unique_content_totals': animations['unique_content_totals'],
            'record_kind_counts': animations['kind_counts'],
            'LBD_totals': animations.get('LBD_totals'),
            'LBD_unresolved_files': animations.get('LBD_unresolved_files'),
            'MML_reference_audit': animations.get('MML_reference_audit'),
            'native_executable_evidence': animations.get('native_executable_evidence'),
            'unresolved_direct_model_files': animations['unresolved_direct_model_files'],
            'semantic_content_audit_complete': False, 'animation_playback_accepted': False,
            'scope': animations['scope']}
        report['developer_tooling']['capabilities'].append({
            'id': 'A007', 'name': 'Bounded native scene/model/animation reference audit',
            'entry': 'tools/inventory_animations.py', 'evidence': reference})
    if entities_path:
        entities = json.loads(Path(entities_path).read_text())
        verify_entity_inputs(entities, report['target']['canonical_sha1'])
        native_names = {record['callback_function'] for record in entities['records'] if record['callback_function']}
        if native_names != {callback['function'] for callback in callbacks}:
            raise ValueError('Audited native callback names differ from the fixed NPC inventory.')
        reference = Path(entities_path).resolve().relative_to(ROOT).as_posix()
        report['native_entity_inventory'] = {
            'reference': reference, 'table': entities['table'], 'totals': entities['totals'],
            'property_histograms': entities['property_histograms'],
            'runtime_validated_callbacks': 0, 'scope': entities['scope']}
        report['developer_tooling']['capabilities'].append({
            'id': 'A008', 'name': 'Original NPC property and callback byte audit',
            'entry': 'tools/inventory_entities.py', 'evidence': reference})
    report['developer_tooling']['capabilities_after_this_prompt'] = len(report['developer_tooling']['capabilities'])
    report["generated_at"] = now
    report["source_hashes"] = {name: {"before_prompt_sha256": baseline["sources"].get(name),
        "after_inventory_sha256": hashlib.sha256((ROOT / name).read_bytes()).hexdigest()} for name in sorted(sources)}
    verify_progress_inputs(progress)
    if dispatch_path:
        verify_dispatch_inputs(dispatch, report['target']['canonical_sha1'])
    if animations_path:
        verify_animation_inputs(animations, report['target']['canonical_sha1'])
    if entities_path:
        verify_entity_inputs(entities, report['target']['canonical_sha1'])
    if native_ai_validation_path:
        for path,validation,validation_digest in validations:
            verify_native_ai_validation(validation, report['target']['canonical_sha1'])
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != validation_digest:
                raise ValueError('Native AI validation report changed during refresh.')
    Path(inventory).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def markdown(report):
    before = report["snapshots"]["before_prompt"]
    after = report["snapshots"]["after_inventory_pass"]
    a, b = before["feature_counts"], after["feature_counts"]
    tools_count = report['developer_tooling']['capabilities_after_this_prompt']
    text = f"""# LSD feature inventory

The current catalogue contains **{len(report['features'])} provisional behavior/system groups**. This is an executable-grounded inventory, not a developer-official exhaustive total. Stage, asset and NPC variant counts are measured separately.

The matching baseline already preserved the original behavior in C plus assembly. C recovery measures source reconstruction; runtime acceptance measures reviewed coverage of the specified scenarios.

## Before and after this prompt

Before is pinned to `{before['timestamp']}`. After is the verified source/build snapshot at `{after['timestamp']}`, with {after['build_objects']} objects and canonical SHA-1 `{after['matching_executable_sha1']}`. Both columns use the same feature denominator.

| Measure | Before | After |
| --- | ---: | ---: |
| Catalogued original feature groups present in matching C plus assembly | {a['catalogued_feature_groups']} | {b['catalogued_feature_groups']} |
| Groups with every listed core function in C | {a['core_logic_recovered_c']} | {b['core_logic_recovered_c']} |
| Groups with listed core and shared support in C | {a['known_core_and_support_recovered_c']} | {b['known_core_and_support_recovered_c']} |
| Entire feature groups independently accepted at runtime | 0 | 0 |
| Game code bytes recovered in C | {before['c_coverage_percent']:.2f}% | {after['c_coverage_percent']:.2f}% |
| Remaining game assembly functions | {before['game_assembly_functions']} | {after['game_assembly_functions']} |
| Original native behavior callbacks in C | {a['native_behavior_callbacks_recovered_c']} / 107 | {b['native_behavior_callbacks_recovered_c']} / 107 |
| Separately implemented AI-assisted developer capabilities | 0 | {tools_count} |

{b['native_behavior_callbacks_recovered_c']} of 107 distinct NPC callbacks have C bodies. The entity table contains 130 records, including 111 script slots and 19 null slots; these are content dimensions. Original NPC behavior belongs to the canonical game. AI-assisted context export, native analysis, isolated matching and replay comparison are separate developer tools and do not change the canonical runtime.

"""
    if 'native_entity_inventory' in report:
        entities = report['native_entity_inventory']
        text += f"The [original NPC audit](NATIVE_AI.md) byte-checked all {entities['totals']['property_records']} property records and callback bindings at `{entities['table']['address']}`. Signed mood, interaction, link and event fields match the C initializer. This verifies static original data; callback state/RNG/input branches remain separate runtime requirements. Evidence: `{entities['reference']}`.\n\n"
    if 'bounded_native_ai_validation' in report:
        for validation in [report['bounded_native_ai_validation'],*report.get('additional_bounded_native_ai_validations',[])]:
            text += f"The optional native NPC verifier passed {validation['native_cases']:,} original `{validation['function']}` cases and detected {len(validation['negative_controls_detected'])} deliberately wrong controls. Native entry execution is measured separately from the byte inventory, with explicit external-call contracts. This bounded result extends one developer capability and leaves whole-callback/feature acceptance at zero. [Scope and usage](NATIVE_AI.md). Evidence: `{validation['reference']}`.\n\n"
    if "runtime_evidence" in report:
        runtime = report["runtime_evidence"]
        text += f"The original and rebuilt discs matched for a {runtime['frames']}-frame scripted play sequence at {runtime['checkpoints']} checkpoints: the frame trace, PNGs, full GPU memory and every save-state member payload were equal. Save-state archive wrappers differ. Evidence: `{runtime['comparison']}`.\n\n"
        if runtime.get('input_provenance', {}).get('inputs_verified'):
            text += "The comparator verified the frozen disc layout/content, emulator/core binaries, BIOS files, launch settings, script and starting state against both input manifests.\n\n"
        audio = runtime.get('audio_output', {})
        if audio.get('output_compared') and audio.get('equal_pcm_output'):
            original = audio['original']
            text += f"The recorded audio also matched: {original['sample_frames']:,} sample frames, {original['channels']} channels, {original['sample_rate']:,} Hz and {original['sample_width'] * 8}-bit PCM, with {original['nonzero_channel_samples']:,} nonzero channel samples. This verifies non-silent captured output for the sequence, not every music track or sound event.\n\n"
        else:
            text += "Audio output was not compared for this sequence.\n\n"
        text += "This limited sequence does not cover every feature branch, content item, audio event or card error. Full feature scenarios remain unaccepted.\n\n"
    for runtime in report.get('additional_runtime_evidence', []):
        values = runtime['frame_observations_per_run'] * runtime['fields_per_observation']
        text += f"An additional {runtime['frames']}-frame movement replay matched {runtime['fields_per_observation']} native input/player-state fields each frame ({values:,} field values per run), plus {runtime['checkpoints']} image/GPU/state checkpoints. This covers the recorded turning, looking, movement and input phases in one stage; entire feature groups remain unaccepted. [Replay details](RUNTIME_COMPARISON.md). Evidence: `{runtime['comparison']}`.\n\n"
    if "asset_inventory" in report:
        assets = report["asset_inventory"]
        text += f"The reference extraction contains {assets['file_count']} files across {assets['stage_directories']} stage directories. Its texture containers contain {assets['texture_bank_tim_records']} TIM records. [Asset inventory](ASSET_INVENTORY.md) documents counts, native structures and the preserved original length-field anomaly; semantic and runtime content auditing remain open.\n\n"
    if 'native_dispatch_inventory' in report:
        dispatch = report['native_dispatch_inventory']
        text += f"The [native dispatch audit](NATIVE_DISPATCH.md) checked {dispatch['declared_tables']} declared virtual tables, including {dispatch['c_initializers_verified']} C initializers, against original executable words. Their {dispatch['nonnull_declared_function_slots']} non-null declared callback slots refer to {dispatch['unique_declared_function_addresses']} distinct addresses. These are dispatch dimensions, separate from NPC callback and game-feature counts; call-site closure and semantic signatures remain open. Evidence: `{dispatch['reference']}`.\n\n"
    if 'native_animation_inventory' in report:
        animations = report['native_animation_inventory']
        totals, unique = animations['totals'], animations['unique_content_totals']
        text += f"The [native animation audit](NATIVE_ANIMATIONS.md) inspected {totals['input_files']} original MOM/LBD files: {totals['validated_MOM_instances']} model instances contain {totals['animations']} animations, {totals['frames']} frames and {totals['records']} records. Unique content comprises {unique['models']} model hashes and {unique['animations']} animations. These structural content counts do not establish playback or add game features. Evidence: `{animations['reference']}`.\n\n"
        if animations.get('LBD_totals') and animations.get('MML_reference_audit'):
            lbd = animations['LBD_totals']
            references = animations['MML_reference_audit']
            unresolved = sum(references['unresolved_counts'].values())
            text += f"The same audit bounded {lbd['validated_LBD_files']} of {lbd['input_LBD_files']} LBD files, {lbd['fixed_grid_cells']:,} grid cells and {lbd['additional_tile_records']} additional tile records. Its {lbd['MML_files']} streamed libraries contain {lbd['MML_model_references']} model references, with {unresolved} unresolved structures/reference associations. This closes the audited static LBD/MML-to-MOM associations; primitive payloads, collision data and runtime reachability remain separate requirements.\n\n"
    text += "## Feature groups\n\n| ID | Behavior/system group | Core C before / after | Primary source | Remaining runtime scenario |\n| --- | --- | --- | --- | --- |\n"
    for feature in report["features"]:
        anchor = feature["required_functions"][0]
        states = ['complete' if feature['c_recovery'][phase]['core_complete'] else 'partial' for phase in ('before', 'after')]
        text += f"| {feature['id']} | {feature['title']} | {' / '.join(states)} | [{anchor['source']}](../{anchor['source']}#L{anchor['line']}) | {feature['runtime_validation']['scenario']} |\n"
    text += "\n## Remaining scope\n\nAsset/command records, virtual-call closure, rare state/RNG/save/error branches, hardware timing and audio coverage remain to audit. [features.json](features.json) preserves requirements, dependencies, immutable before statuses, current source hashes and runtime evidence. Five inventory gaps remain open; U006 records the user's resolved separation of original behavior from AI tooling.\n\nA core-C count is based on actual configured definitions and live assembly inclusions. Shared support follows explicit dependencies and does not claim exhaustive call-graph closure. Optional gameplay mods have their own outputs and do not count toward original parity.\n"
    return text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", default="docs/features.json")
    parser.add_argument("--progress", required=True)
    parser.add_argument("--runtime")
    parser.add_argument("--assets")
    parser.add_argument("--dispatch")
    parser.add_argument("--animations")
    parser.add_argument("--entities")
    parser.add_argument("--additional-runtime", action="append", help="Pinned native-state replay; repeat for separate scoped comparisons.")
    parser.add_argument("--native-ai-validation", action="append", help="Current bounded original NPC verifier report; repeat for distinct callbacks. Not whole-callback acceptance.")
    args = parser.parse_args(argv)
    try:
        report = refresh(args.inventory, args.progress, args.runtime, args.assets, args.dispatch, args.animations, args.entities, args.additional_runtime, args.native_ai_validation)
        (ROOT / "docs/FEATURE_INVENTORY.md").write_text(markdown(report), encoding="utf-8")
        counts = report["snapshots"]["after_inventory_pass"]["feature_counts"]
        print(f"{counts['catalogued_feature_groups']} provisional groups; {counts['core_logic_recovered_c']} core-C groups; {report['snapshots']['after_inventory_pass']['game_assembly_functions']} game ASM functions remain.")
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f"[!] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
