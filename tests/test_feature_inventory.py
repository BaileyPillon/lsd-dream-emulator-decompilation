"""Feature counts must follow configured definitions and an unchanged matching build."""

import hashlib
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import feature_inventory


class FeatureInventoryTests(unittest.TestCase):
    def native_ai_fixture(self, root):
        paths = ['tools/verify_native_ai.py','tools/inventory_vtables.py','tools/progress.py',
            'configure.py','requirements-analysis.txt',
            'build/SLPS01556.map','build/undefined_funcs_auto.txt','build/undefined_syms_auto.txt',
            'src/scene/entity.c','src/scene/entity.h','src/dream/dream_sys.c','src/dream/dream_sys.h',
            'src/scene/actor.c','src/base/transform.c','asm/nonmatchings/psyq/libc/rand/rand.s']
        for name in paths:
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_bytes(('original '+name).encode())
        return {'canonical_executable_sha1':'canonical', 'original_and_current_build_equal':True,
            'original_behavior_modified':False, 'status':'passed_bounded_original_npc_model',
            'callback_runtime_accepted':False, 'original_feature_groups_accepted':0,
            'function':'entity_lion', 'model_api_calls':0,
            'native_cases':1608, 'case_groups':{'rng':256,'active_animation':896,'inactive':432,'motion_offset':24},
            'negative_controls_detected':[
                {'name':name,'function_offset':offset,'expected_word':before,'changed_word':after,
                 'execution_scope':'Private emulator memory; original executable and build unchanged.'}
                for name,offset,before,after in [
                    ('distance_boundary',0x17C,'0x28420200','0x28420201'),
                    ('timer_boundary',0x94,'0x2842003D','0x2842003E'),
                    ('state_two_movement',0x210,'0x2411FFA0','0x2411FF9F')]],
            'native_functions':copy.deepcopy(feature_inventory.NATIVE_FUNCTIONS),
            'native_range_role':'Canonical byte inventory; entry execution is measured separately.',
            'executed_native_functions':sorted(record['function'] for record in feature_inventory.NATIVE_FUNCTIONS
                                               if record['function'] != 'func_8001D1A4'),
            'stubbed_calls':['distance','dream_motion','entity_motion','movement','notification','orientation',
                            'scale','sound_entity_stop','trigger_ratio'],
            'producer_dependencies':[
                {'path':name, 'sha256':hashlib.sha256((root / name).read_bytes()).hexdigest()} for name in paths]}

    def test_bounded_npc_report_cannot_claim_whole_callback_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.native_ai_fixture(root)
            feature_inventory.verify_native_ai_validation(report, 'canonical', root)
            report['callback_runtime_accepted'] = True
            with self.assertRaisesRegex(ValueError, 'without whole-feature acceptance'):
                feature_inventory.verify_native_ai_validation(report, 'canonical', root)

    def test_npc_report_rejects_changed_producer_or_native_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.native_ai_fixture(root)
            (root / 'src/scene/entity.c').write_bytes(b'changed NPC behavior')
            with self.assertRaisesRegex(ValueError, 'validation evidence changed'):
                feature_inventory.verify_native_ai_validation(report, 'canonical', root)

    def test_npc_report_requires_consistent_cases_and_negative_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.native_ai_fixture(root)
            report['native_cases'] = 1609
            with self.assertRaisesRegex(ValueError, 'counts are inconsistent'):
                feature_inventory.verify_native_ai_validation(report, 'canonical', root)
            report['native_cases'] = 1608
            report['negative_controls_detected'] = []
            with self.assertRaisesRegex(ValueError, 'counts are inconsistent'):
                feature_inventory.verify_native_ai_validation(report, 'canonical', root)

    def test_npc_report_rejects_unsupported_callback_and_model_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = self.native_ai_fixture(root)
            for change in ({'function':'entity_not_audited'}, {'model_api_calls':1}):
                with self.subTest(change=change):
                    report = {**original, **change}
                    with self.assertRaisesRegex(ValueError, 'supported original NPC'):
                        feature_inventory.verify_native_ai_validation(report, 'canonical', root)

    def test_npc_report_rejects_nonpositive_and_boolean_case_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = self.native_ai_fixture(root)
            for count in (0,-1,True):
                with self.subTest(count=count):
                    report = copy.deepcopy(original)
                    report['case_groups'] = {'rng':count}
                    report['native_cases'] = count
                    with self.assertRaisesRegex(ValueError, 'counts are inconsistent'):
                        feature_inventory.verify_native_ai_validation(report, 'canonical', root)

    def test_npc_report_rejects_removed_or_corrupted_native_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = self.native_ai_fixture(root)
            for change in ('removed','wrong_hash'):
                with self.subTest(change=change):
                    report = copy.deepcopy(original)
                    if change == 'removed':
                        del report['native_functions']
                    else:
                        report['native_functions'][0]['sha256'] = '0'*64
                    with self.assertRaisesRegex(ValueError, 'canonical native range inventory'):
                        feature_inventory.verify_native_ai_validation(report, 'canonical', root)

    def test_npc_report_rejects_invented_entries_and_missing_execution_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = self.native_ai_fixture(root)
            for change in ('removed','invented','missing_chain','duplicate'):
                with self.subTest(change=change):
                    report = copy.deepcopy(original)
                    if change == 'removed':
                        del report['executed_native_functions']
                    elif change == 'invented':
                        report['executed_native_functions'].append('invented_function')
                    elif change == 'missing_chain':
                        report['executed_native_functions'].remove('dream_sys_clear_callbacks')
                    else:
                        report['executed_native_functions'].append('rand')
                    with self.assertRaisesRegex(ValueError, 'unique measured entries'):
                        feature_inventory.verify_native_ai_validation(report, 'canonical', root)

    def test_npc_report_rejects_invented_or_changed_mutation_control(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = self.native_ai_fixture(root)
            for change in ({'name':'invented_control'}, {'changed_word':'0x28420202'},
                           {'function_offset':381}):
                with self.subTest(change=change):
                    report = copy.deepcopy(original)
                    report['negative_controls_detected'][0].update(change)
                    with self.assertRaisesRegex(ValueError, 'known private-memory mutation controls'):
                        feature_inventory.verify_native_ai_validation(report, 'canonical', root)

    def gray_man_fixture(self, root):
        report = self.native_ai_fixture(root)
        extra = ['tools/verify_gray_man.py','src/graphics/effect.c','src/graphics/effect.h']
        for name in extra:
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_bytes(('original ' + name).encode())
            report['producer_dependencies'].append({
                'path':name,'sha256':hashlib.sha256((root / name).read_bytes()).hexdigest()})
        functions = copy.deepcopy(feature_inventory.GRAY_MAN_NATIVE_FUNCTIONS)
        report.update(function='entity_gray_man',entity_record=98,native_cases=768,
            case_groups={'inactive':256,'new_allocation_failure':128,'new_effect':128,'existing_effect':256},
            native_functions=functions,executed_native_functions=sorted(record['function'] for record in functions),
            native_entry_counts={record['function']:(768 if record['function'] == 'entity_gray_man'
                else 512 if record['function'] == 'entity_create_effect' else 384) for record in functions},
            stubbed_calls=['effect_activate','effect_attach','effect_color','effect_create','movement','sound_entity_stop'],
            negative_controls_detected=[{'name':name,'function_offset':offset,'expected_word':before,'changed_word':after,
                'execution_scope':'Private emulator memory; original executable and build unchanged.'}
                for name,offset,before,after in [('wrong_movement',0x98,'0x2405FFE2','0x2405FFE1'),
                    ('skip_flashback_reset',0x88,'0x0040F809','0x00000000')]])
        return report

    def test_gray_man_report_requires_real_entry_counts_and_original_property_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = self.gray_man_fixture(root)
            feature_inventory.verify_native_ai_validation(original, 'canonical', root)
            for change in ('wrong_count','boolean_count','wrong_record'):
                with self.subTest(change=change):
                    report = copy.deepcopy(original)
                    if change == 'wrong_record':
                        report['entity_record'] = 81
                    else:
                        report['native_entry_counts']['entity_create_effect'] = True if change == 'boolean_count' else 511
                    with self.assertRaisesRegex(ValueError, 'measured Gray Man entry counts'):
                        feature_inventory.verify_native_ai_validation(report, 'canonical', root)

    def test_gray_man_report_cannot_omit_failed_allocation_cases_or_detach_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = self.gray_man_fixture(root)
            report = copy.deepcopy(original)
            report['case_groups']['new_allocation_failure'] = 127
            report['case_groups']['new_effect'] = 129
            with self.assertRaisesRegex(ValueError, 'supported callback case groups'):
                feature_inventory.verify_native_ai_validation(report, 'canonical', root)
            report = copy.deepcopy(original)
            report['executed_native_functions'].remove('func_8001D1A4')
            with self.assertRaisesRegex(ValueError, 'unique measured entries'):
                feature_inventory.verify_native_ai_validation(report, 'canonical', root)

    def test_gray_man_report_requires_unchanged_effect_source_and_mutation_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.gray_man_fixture(root)
            report['negative_controls_detected'][1]['changed_word'] = '0x0040F809'
            with self.assertRaisesRegex(ValueError, 'known private-memory mutation controls'):
                feature_inventory.verify_native_ai_validation(report, 'canonical', root)
            report = self.gray_man_fixture(root)
            (root / 'src/graphics/effect.c').write_bytes(b'changed original effect behavior')
            with self.assertRaisesRegex(ValueError, 'validation evidence changed'):
                feature_inventory.verify_native_ai_validation(report, 'canonical', root)

    def native_runtime_fixture(self, root):
        path = root / 'replay.json'
        report = {'equal_recorded_outputs': True, 'frames': 2, 'checkpoints': [2],
                  'status': 'exact_for_recorded_scenario',
                  'input_provenance': {'inputs_verified': True},
                  'native_observations': {'equal_native_state': True, 'output_compared': True,
                      'frame_observations_per_run': 2, 'fields_per_observation': 43,
                      'phases': {'neutral': {'frames': 2}}, 'scope': 'One recorded stage.'}}
        path.write_text(json.dumps(report))
        return path, report

    def test_native_replay_does_not_count_as_accepted_feature_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, _report = self.native_runtime_fixture(root)
            summary = feature_inventory.native_runtime_summary(path, root)
            self.assertEqual(summary['feature_groups_accepted'], 0)
            self.assertEqual(summary['comparison_sha256'], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_additional_native_replay_rejects_unverified_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, report = self.native_runtime_fixture(root)
            report['input_provenance']['inputs_verified'] = False
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'verified inputs'):
                feature_inventory.native_runtime_summary(path, root)

    def test_additional_native_replay_rejects_truncated_observations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, report = self.native_runtime_fixture(root)
            report['native_observations']['frame_observations_per_run'] = 1
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'complete observations'):
                feature_inventory.native_runtime_summary(path, root)

    def entity_fixture(self, root):
        (root / 'tools').mkdir()
        producer = root / 'tools/inventory_entities.py'
        source = root / 'entity.c'
        producer.write_bytes(b'fixture producer')
        source.write_bytes(b'fixture original NPC source')
        return {'canonical_sha1': 'canonical', 'canonical_runtime_changed': False,
                'original_behavior_modified': False,
                'table': {'all_initializers_match_native': True},
                'evidence_sha256': {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                                    for path in (producer, source)},
                'totals': {'property_records': 2, 'nonnull_callback_slots': 1,
                           'null_callback_slots': 1, 'distinct_callback_addresses': 1,
                           'distinct_callbacks_recovered_c': 1},
                'records': [{'callback_function': 'entity_first', 'callback_address': '0x80012000'},
                            {'callback_function': None, 'callback_address': '0x00000000'}],
                'callbacks': [{'address': '0x80012000', 'recovered_c': True}]}

    def test_entity_counts_require_current_original_source_and_producer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.entity_fixture(root)
            feature_inventory.verify_entity_inputs(report, 'canonical', root)
            (root / 'entity.c').write_bytes(b'changed behavior')
            with self.assertRaisesRegex(ValueError, 'Entity audit evidence changed'):
                feature_inventory.verify_entity_inputs(report, 'canonical', root)

    def test_entity_slots_cannot_be_counted_as_distinct_callback_functions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.entity_fixture(root)
            report['totals']['distinct_callback_addresses'] = 2
            with self.assertRaisesRegex(ValueError, 'counts are inconsistent'):
                feature_inventory.verify_entity_inputs(report, 'canonical', root)

    def animation_fixture(self, root):
        names = ('unit.c', 'dependency.py', 'producer.py', 'original.MOM', 'disc.xml')
        for name in names:
            (root / name).write_bytes(('fixture ' + name).encode())
        digest = lambda name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        return {'canonical_executable_sha1': 'canonical', 'original_executable': {'sha1': 'canonical'},
                'input_modified': False, 'source_sha256': {'unit.c': digest('unit.c')},
                'dependency_sha256': {'dependency.py': digest('dependency.py')},
                'producer': {'path': 'producer.py', 'sha256': digest('producer.py')},
                'files': [{'source': str(root / 'original.MOM'), 'path': '/original.MOM',
                           'sha256': digest('original.MOM')}], 'totals': {'input_files': 1},
                'layout': str(root / 'disc.xml'), 'layout_sha256': digest('disc.xml')}

    def test_animation_report_cannot_survive_changed_native_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.animation_fixture(root)
            feature_inventory.verify_animation_inputs(report, 'canonical', root)
            (root / 'unit.c').write_bytes(b'changed interpreter')
            with self.assertRaisesRegex(ValueError, 'Animation audit source changed'):
                feature_inventory.verify_animation_inputs(report, 'canonical', root)

    def test_animation_report_cannot_survive_changed_original_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.animation_fixture(root)
            (root / 'original.MOM').write_bytes(b'changed asset')
            with self.assertRaisesRegex(ValueError, 'Original animation asset changed'):
                feature_inventory.verify_animation_inputs(report, 'canonical', root)

    def test_prototypes_and_commented_sketches_are_not_definitions(self):
        index = feature_inventory.locate_functions({"src/unit.c":
            "void declared(void);\n/* void old(void) { } */\n"
            "void recovered(int value) {\n    callback(value);\n}\n"})
        self.assertEqual(index, {"recovered": [("src/unit.c", 3)]})

    def test_inactive_candidate_does_not_replace_retained_assembly(self):
        index = feature_inventory.locate_functions({"src/unit.c":
            '#if 0\nvoid pending(void) { }\n#endif\n'
            'INCLUDE_ASM("asm/unit", pending);\n'})
        self.assertEqual(index, {"pending": [("src/unit.c", 4)]})

    def test_split_function_is_found_in_its_new_configured_unit(self):
        index = feature_inventory.locate_functions({
            "src/old.c": "void moved(void);\nvoid prior(void) { }\n",
            "src/new.c": "void moved(void) { }\n"})
        self.assertEqual(index["moved"], [("src/new.c", 1)])

    def test_changed_source_or_header_rejects_a_matching_old_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "unit.c"
            source.write_bytes(b"original source")
            snapshot = {"complete_objects": True, "build_current": True,
                "binary_match": "verified", "build_input_sha256": {
                    "unit.c": hashlib.sha256(source.read_bytes()).hexdigest()}}
            feature_inventory.verify_progress_inputs(snapshot, root)
            source.write_bytes(b"new source")
            with self.assertRaisesRegex(ValueError, "Build inputs changed.*unit.c"):
                feature_inventory.verify_progress_inputs(snapshot, root)

    def test_dispatch_audit_rejects_changed_header_and_layout_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            header = root / 'table.h'
            header.write_bytes(b'original layout')
            dispatch = {'canonical_sha1': 'canonical', 'canonical_runtime_changed': False,
                        'header_layout_issues': [], 'unresolved_declarations': [],
                        'unsupported_types': [], 'source_sha256': {
                            'table.h': hashlib.sha256(header.read_bytes()).hexdigest()}}
            feature_inventory.verify_dispatch_inputs(dispatch, 'canonical', root)
            header.write_bytes(b'new layout')
            with self.assertRaisesRegex(ValueError, 'Dispatch source changed'):
                feature_inventory.verify_dispatch_inputs(dispatch, 'canonical', root)
            dispatch['header_layout_issues'] = [{'name': 'table'}]
            with self.assertRaisesRegex(ValueError, 'layout issues'):
                feature_inventory.verify_dispatch_inputs(dispatch, 'canonical', root)


if __name__ == "__main__":
    unittest.main()
