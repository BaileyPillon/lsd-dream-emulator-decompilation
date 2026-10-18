"""Constructed route-partition and retained-output corruption controls."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.collision_call_batches import PROGRAM_NAME, partition_programs
from tools.collision_calls import PC, selection
from tools.inspect_collision_call_batches import compare_recordings, verify_partition_coverage

ROOT = Path(__file__).resolve().parents[1]


def identity(data):
    return dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def coverage_fixture():
    entries = [dict(pc=pc) for pc in (0x8001DDF4, PC, PC, 0x8001DDF4, PC, PC, PC, 0x8001DDF4, PC)]
    batches = []
    for first, ordinals in ((1, (2, 6)), (2, (3, 7)), (3, (5, 9))):
        calls = [dict(base_ordinal=ordinal, result=ordinal % 2, primitive_count=1,
                      model_address=0x80060000, geometry_address=0x80061000,
                      entry_frame=ordinal, return_frame=ordinal + (ordinal == 9)) for ordinal in ordinals]
        policy = dict(eligible_entries=6, ordinal_skips=4, nested_skips=0,
                      sample_limit_skips=0, duplicate_key_skips=0, frame_budget_skips=0)
        batches.append(dict(settings=dict(ordinal_first=first, ordinal_step=3),
                            verification=dict(policy=policy, completed_samples=2, calls=calls)))
    return entries, batches


def retained_fixture(folder, first):
    folder.mkdir()
    folder = folder.resolve(strict=True)
    (folder/'sources').mkdir()
    (folder/'observations').mkdir()
    program = json.loads((ROOT/'research/headless/collision-ordinal-opening-route.json').read_text())
    program['method_trace']['collision_calls']['ordinal_first'] = first
    raw = json.dumps(program).encode()
    (folder/'sources/program.json').write_bytes(raw)
    (folder/'observations/audio.pcm').write_bytes(b'complete PCM')
    for prefix in ('mainram', 'gpu', 'rgb'):
        (folder/f'observations/{prefix}-1.bin').write_bytes(prefix.encode())
    manifest = dict(runtime_kind='dispatch_observer',
                    settings=dict(frames=6000, checkpoint_frames=[1], collision_calls=selection(program)),
                    source_manifest=dict(bios=dict(japan=identity(b'bios')), disc=dict(tracks=[identity(b'disc')])),
                    actual_runtime_files=dict(core=identity(b'core')), submitted=identity(b'controller'),
                    source_snapshots=[dict(original=dict(path='C:/owned/'+PROGRAM_NAME), file='sources/program.json')])
    return dict(folder=folder, manifest=manifest, program=program, entries=[dict(pc=PC)],
                frames={1: 'gpu/pcm'}, RAM={1: 'ram'}, native=dict(checkpoints=[dict(relative_frame=1)]),
                producer_sources={PROGRAM_NAME: identity(raw), 'host.cs': identity(b'host'), 'profile.json': identity(b'profile')})


class CollisionBatchCoverageTests(unittest.TestCase):
    def setUp(self):
        self.entries, self.batches = coverage_fixture()

    def test_complete_partition_uses_original_entry_ordinals_with_interleaved_hull_calls(self):
        result = verify_partition_coverage(self.entries, self.batches)
        self.assertEqual(result['base_ordinals'], [2, 3, 5, 6, 7, 9])
        self.assertEqual(result['completed_primitive_calls'], 6)
        self.assertEqual(result['observed_model_addresses'], 1)
        self.assertEqual(result['calls_crossing_a_frame'], 1)
        self.assertTrue(result['every_observed_route_primitive_call_verified'])
        self.assertFalse(result['complete_state_parity_checked'])
        self.assertEqual(result['whole_feature_groups_accepted'], 0)

    def test_missing_or_duplicate_phase_cannot_claim_complete_coverage(self):
        with self.assertRaisesRegex(ValueError, 'every ordinal phase'):
            verify_partition_coverage(self.entries, self.batches[:-1])
        self.batches[2] = copy.deepcopy(self.batches[1])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            verify_partition_coverage(self.entries, self.batches)

    def test_a_lost_call_cannot_hide_behind_consistent_sample_counters(self):
        self.batches[0]['verification']['calls'].pop()
        self.batches[0]['verification']['completed_samples'] = 1
        self.batches[0]['verification']['policy']['ordinal_skips'] = 5
        with self.assertRaisesRegex(ValueError, 'missing, repeating'):
            verify_partition_coverage(self.entries, self.batches)

    def test_duplicate_and_wrong_phase_entry_ids_are_rejected(self):
        for value in (2, 3):
            entries, batches = coverage_fixture()
            batches[0]['verification']['calls'][1]['base_ordinal'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'missing, repeating'):
                verify_partition_coverage(entries, batches)

    def test_actual_frame_or_total_limit_losses_remain_incomplete(self):
        for key in ('frame_budget_skips', 'sample_limit_skips', 'nested_skips', 'duplicate_key_skips'):
            entries, batches = coverage_fixture()
            batches[0]['verification']['policy'][key] = 1
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'cannot drop'):
                verify_partition_coverage(entries, batches)

    def test_boolean_counters_and_phases_cannot_impersonate_integer_evidence(self):
        self.batches[0]['verification']['policy']['frame_budget_skips'] = False
        with self.assertRaisesRegex(ValueError, 'cannot drop'):
            verify_partition_coverage(self.entries, self.batches)
        self.entries, self.batches = coverage_fixture()
        self.batches[0]['settings']['ordinal_first'] = True
        with self.assertRaisesRegex(ValueError, 'inconsistent'):
            verify_partition_coverage(self.entries, self.batches)

    def test_wrong_eligible_entry_count_is_rejected(self):
        self.batches[0]['verification']['policy']['eligible_entries'] = 7
        with self.assertRaisesRegex(ValueError, 'misidentifying'):
            verify_partition_coverage(self.entries, self.batches)

    def test_prepare_preserves_the_complete_controller_route_and_does_not_mutate_its_input(self):
        program = json.loads((ROOT/'research/headless/collision-ordinal-opening-route.json').read_text())
        original = copy.deepcopy(program)
        parts = partition_programs(program)
        self.assertEqual(program, original)
        self.assertEqual([selection(part)['ordinal_first'] for part in parts], list(range(1, 12)))
        for part in parts:
            part['method_trace']['collision_calls']['ordinal_first'] = 1
            self.assertEqual(part, original)

    def test_prepare_refuses_a_legacy_key_sampler_as_an_ordinal_collection(self):
        program = json.loads((ROOT/'research/headless/collision-call-opening-route.json').read_text())
        with self.assertRaisesRegex(ValueError, 'ordinal'):
            partition_programs(program)


class CollisionBatchRecordingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.left = retained_fixture(root/'left', 1)
        self.right = retained_fixture(root/'right', 2)

    def test_a_recording_cannot_be_compared_with_itself_as_an_independent_run(self):
        with self.assertRaisesRegex(ValueError, 'distinct recording directories'):
            compare_recordings(self.left, self.left, different_phase=True)

    def test_only_an_explicit_phase_change_can_compare_different_sampler_programs(self):
        with self.assertRaisesRegex(ValueError, 'programs or actual observer settings'):
            compare_recordings(self.left, self.right)
        self.assertTrue(compare_recordings(self.left, self.right, different_phase=True)['every_recorded_game_output_equal'])

    def test_phase_comparison_still_checks_submitted_controller_bytes(self):
        self.right['manifest']['submitted'] = identity(b'changed controller')
        with self.assertRaisesRegex(ValueError, 'submitted controller'):
            compare_recordings(self.left, self.right, different_phase=True)

    def test_phase_change_does_not_allow_an_observer_or_compiler_source_change(self):
        self.right['producer_sources']['host.cs'] = identity(b'changed host')
        with self.assertRaisesRegex(ValueError, 'producer sources'):
            compare_recordings(self.left, self.right, different_phase=True)

    def test_phase_change_does_not_allow_a_different_native_core(self):
        self.right['manifest']['actual_runtime_files']['core'] = identity(b'other core')
        with self.assertRaisesRegex(ValueError, 'native runtime'):
            compare_recordings(self.left, self.right, different_phase=True)

    def test_phase_change_does_not_allow_other_controller_program_fields(self):
        self.right['program']['method_trace']['arm_frame'] += 1
        with self.assertRaisesRegex(ValueError, 'more than'):
            compare_recordings(self.left, self.right, different_phase=True)

    def test_recorded_program_must_match_its_actual_retained_source(self):
        path = self.right['folder']/'sources/program.json'
        path.write_text(json.dumps(self.left['program']))
        with self.assertRaisesRegex(ValueError, 'Retained ordinal program'):
            compare_recordings(self.left, self.right, different_phase=True)

    def test_equal_checkpoint_metadata_cannot_hide_changed_checkpoint_bytes(self):
        (self.right['folder']/'observations/mainram-1.bin').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'checkpoint differs'):
            compare_recordings(self.left, self.right, different_phase=True)

    def test_equal_frame_records_cannot_hide_changed_complete_audio(self):
        (self.right['folder']/'observations/audio.pcm').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'PCM output'):
            compare_recordings(self.left, self.right, different_phase=True)

    def test_method_entries_and_frame_observations_remain_exact_across_phases(self):
        self.right['entries'][0]['pc'] += 4
        with self.assertRaisesRegex(ValueError, 'entry history'):
            compare_recordings(self.left, self.right, different_phase=True)
        self.right['entries'] = copy.deepcopy(self.left['entries'])
        self.right['frames'][1] = 'changed'
        with self.assertRaisesRegex(ValueError, 'GPU/RAM/PCM'):
            compare_recordings(self.left, self.right, different_phase=True)


if __name__ == '__main__':
    unittest.main()
