import copy
import json
from pathlib import Path
import tempfile
import unittest
import wave

from tools.replay_cold_start_headless import audio_window, replay, select_compiler, validate_trace, verify_replay


class HeadlessAudioTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'reference.wav'
        self.pcm = bytes(range(24))  # six complete stereo sample frames
        self.counts = [2, 3, 1]      # two dumped frames, then one extra observation
        self.write_wave(self.pcm[:20])

    def write_wave(self, data, channels=2, width=2, rate=44100):
        with wave.open(str(self.path), 'wb') as output:
            output.setparams((channels, width, rate, 0, 'NONE', 'not compressed'))
            output.writeframes(data)

    def test_declared_dump_window_compares_the_entire_WAV_and_preserves_extra_audio(self):
        result = audio_window(self.pcm, self.path, self.counts, 2)
        self.assertTrue(result['equal'])
        self.assertEqual(result['GUI_dump_PCM_sample_frames'], 5)
        self.assertEqual(result['headless_all_PCM_sample_frames'], 6)
        self.assertEqual(result['extra_observer_frame_PCM_sample_frames'], 1)
        self.assertTrue(result['complete_headless_PCM_preserved'])

    def test_changed_dump_window_PCM_is_a_real_difference(self):
        changed = bytes([255]) + self.pcm[1:]
        result = audio_window(changed, self.path, self.counts, 2)
        self.assertFalse(result['equal'])
        self.assertNotEqual(result['reference_PCM_sha256'], result['headless_dump_window_PCM_sha256'])

    def test_truncated_or_appended_headless_audio_is_rejected(self):
        for data in (self.pcm[:-1], self.pcm + b'\0'):
            with self.subTest(length=len(data)), self.assertRaisesRegex(ValueError, 'truncated or has trailing'):
                audio_window(data, self.path, self.counts, 2)

    def test_a_different_WAV_window_is_not_silently_trimmed(self):
        self.write_wave(self.pcm)
        with self.assertRaisesRegex(ValueError, 'declared dump-frame window'):
            audio_window(self.pcm, self.path, self.counts, 2)

    def test_wrong_audio_format_is_rejected(self):
        self.write_wave(self.pcm[:20], channels=1)
        with self.assertRaisesRegex(ValueError, 'stereo 16-bit'):
            audio_window(self.pcm, self.path, self.counts, 2)

    def test_invalid_counts_and_missing_observation_boundary_are_rejected(self):
        for counts, frames in (([2, 3], 2), ([2, -3, 1], 2), ([True, 3, 1], 2), ([2, 3, 1], 0)):
            with self.subTest(counts=counts, frames=frames), self.assertRaises(ValueError):
                audio_window(self.pcm, self.path, counts, frames)


class HeadlessTraceTests(unittest.TestCase):
    def setUp(self):
        self.rows, self.reference = [], []
        total = 0
        for frame, count in enumerate((2, 3, 1)):
            total += count
            gpu = f'{frame:064x}'
            self.rows.append(dict(relative_frame=str(frame), core_frame=str(frame + 1),
                phase='neutral', gpu_sha256=gpu, gpu_equal='True', sample_frames=str(count),
                total_sample_frames=str(total)))
            self.reference.append(dict(relative_frame=str(frame), core_frame=str(frame + 1), gpu_sha256=gpu))

    def test_complete_observations_keep_initial_and_extra_boundaries(self):
        counts, differences = validate_trace(self.rows, self.reference, 2)
        self.assertEqual(counts, [2, 3, 1])
        self.assertEqual(differences, 0)

    def test_missing_or_shifted_boundaries_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Missing'):
            validate_trace(self.rows[:-1], self.reference, 2)
        self.rows[1]['core_frame'] = '99'
        with self.assertRaisesRegex(ValueError, 'frame boundaries differ'):
            validate_trace(self.rows, self.reference, 2)

    def test_a_changed_GPU_hash_cannot_keep_a_success_flag(self):
        self.rows[1]['gpu_sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'GPU comparison flag'):
            validate_trace(self.rows, self.reference, 2)

    def test_reported_GPU_difference_is_retained(self):
        self.rows[1]['gpu_sha256'] = 'f' * 64
        self.rows[1]['gpu_equal'] = 'False'
        self.assertEqual(validate_trace(self.rows, self.reference, 2)[1], 1)

    def test_invalid_GPU_hash_is_rejected(self):
        self.rows[0]['gpu_sha256'] = '123'
        with self.assertRaisesRegex(ValueError, 'complete GPU hash'):
            validate_trace(self.rows, self.reference, 2)

    def test_negative_audio_or_inconsistent_cumulative_count_is_rejected(self):
        for key, value in (('sample_frames', '-1'), ('total_sample_frames', '99')):
            rows = copy.deepcopy(self.rows)
            rows[1][key] = value
            with self.assertRaises(ValueError):
                validate_trace(rows, self.reference, 2)


class HeadlessStartupTests(unittest.TestCase):
    def test_installed_SDK_versions_are_ordered_numerically(self):
        value = select_compiler('8.0.99 [C:/sdk]\n8.0.424 [C:/sdk]\n7.0.999 [D:/old]\n')
        self.assertEqual(value, Path('C:/sdk/8.0.424/Roslyn/bincore/csc.dll'))

    def test_missing_compatible_stable_SDK_is_rejected(self):
        for value in ('', '7.0.999 [C:/sdk]', '8.0.100-preview.1 [C:/sdk]'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'stable installed'):
                select_compiler(value)

    def test_existing_workspace_is_preserved_before_loading_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'retained.txt'
            marker.write_text('keep me')
            with self.assertRaisesRegex(ValueError, 'existing evidence is preserved'):
                replay(Path(directory) / 'absent-capture', directory)
            self.assertEqual(marker.read_text(), 'keep me')

    def test_native_state_restoration_is_rejected_before_output_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            report = dict(status='passed_isolated_recorded_cold_replay', frames_advanced=3,
                submitted_frames_replayed=2, restored_state=True, game_RAM_injected=False,
                emulator_UI_controlled=False)
            (folder / 'report.json').write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'controller-only cold boot'):
                verify_replay(folder / 'absent-reference', folder, {}, 2, 0)

    def test_incomplete_native_run_is_rejected_before_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'report.json').write_text(json.dumps(dict(status='startup_only')))
            with self.assertRaisesRegex(ValueError, 'did not complete'):
                verify_replay(folder, folder, {}, 2, 0)
