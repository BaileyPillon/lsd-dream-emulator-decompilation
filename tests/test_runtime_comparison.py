"""Save-state and incomplete-run regressions using small synthetic outputs."""

from pathlib import Path
import struct
import sys
import tempfile
import unittest
import wave
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import compare_runtime


def run_fixture(folder, stamp, core=b"same emulated state"):
    folder.mkdir()
    (folder / "completed.txt").write_text("1 emulator frames; scenario boot; observation script, not exhaustive feature acceptance.\n")
    (folder / "emulator.txt").write_text("BizHawk test\nSystem PSX\nScenario boot\n")
    (folder / "trace.tsv").write_text("relative_frame\tcore_frame\tsystem\tlagged\tgpu_ram_sample_hash\n")
    (folder / "frame-1.png").write_bytes(b"same image fixture")
    (folder / "gpu-1.bin").write_bytes(b"same GPU fixture")
    with zipfile.ZipFile(folder / "frame-1.State", "w") as state:
        state.writestr(zipfile.ZipInfo("Core.bin.zst", stamp), core)


def movement_fixture(folder, x=100, include_frame=True, pad=None, **updates):
    values = {field: '0' for field in compare_runtime.MOVEMENT_FIELDS}
    values.update(relative_frame='1', core_frame='20', input_phase='walk_forward',
                  input_buttons='P1 D-Pad Up', game_flow='00090c90', dream_sys='00091530',
                  coordinate='00091e5c', pose='00091eb0', x=str(x))
    fields = compare_runtime.MOVEMENT_FIELDS
    if pad is not None:
        fields += compare_runtime.PAD_FIELDS
        values.update(pad='00091f34', pad_buttons='4096', pad_released='0', pad_pressed='4096')
        values.update(pad)
    values.update(updates)
    text = '\t'.join(fields) + '\n'
    if include_frame:
        text += '\t'.join(values[field] for field in fields) + '\n'
    (folder / 'movement.tsv').write_text(text)


class RuntimeComparisonTests(unittest.TestCase):
    def test_native_pad_difference_fails_despite_equal_images_and_positions(self):
        with tempfile.TemporaryDirectory() as folder:
            original, rebuilt = Path(folder) / 'original', Path(folder) / 'rebuilt'
            for path in (original, rebuilt):
                run_fixture(path, (2026, 10, 10, 1, 0, 0))
                movement_fixture(path, pad={})
            report = compare_runtime.compare_runs(original, rebuilt)
            self.assertTrue(report['equal_recorded_outputs'])
            self.assertEqual(report['native_observations']['fields_per_observation'], 47)
            movement_fixture(rebuilt, pad={'pad_pressed': '0'})
            report = compare_runtime.compare_runs(original, rebuilt)
            self.assertFalse(report['equal_recorded_outputs'])
            self.assertTrue(report['byte_outputs']['frame-1.png']['equal'])
            self.assertTrue(report['save_states']['frame-1.State']['member_contents_equal'])

    def test_requested_input_does_not_claim_unlocked_behavior_under_any_input_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            original, rebuilt = Path(folder) / 'original', Path(folder) / 'rebuilt'
            for path in (original, rebuilt):
                path.mkdir()
            for guard in ('paused', 'input_locked', 'auto_move_locked'):
                with self.subTest(guard=guard):
                    for path in (original, rebuilt):
                        movement_fixture(path, pad={}, **{guard: '1'})
                    report = compare_runtime.compare_native_observations(original, rebuilt, 1)
                    phase = report['phases']['walk_forward']
                    self.assertEqual(phase['requested_input_frames'], 1)
                    self.assertEqual(phase['unlocked_frames'], 0)
                    self.assertEqual(phase['requested_input_while_unlocked_frames'], 0)
                    self.assertEqual(phase['native_pad']['active_while_unlocked_frames'], 0)
                    self.assertTrue(report['equal_native_state'])

    def test_persistent_native_edge_is_counted_as_sampled_frames(self):
        with tempfile.TemporaryDirectory() as folder:
            original, rebuilt = Path(folder) / 'original', Path(folder) / 'rebuilt'
            for path in (original, rebuilt):
                path.mkdir()
                movement_fixture(path, pad={})
                lines = (path / 'movement.tsv').read_text().splitlines()
                lines.append(lines[1].replace('1\t20\t', '2\t21\t', 1))
                (path / 'movement.tsv').write_text('\n'.join(lines) + '\n')
            report = compare_runtime.compare_native_observations(original, rebuilt, 2)
            pad = report['phases']['walk_forward']['native_pad']
            self.assertEqual(pad['pressed_nonzero_frames'], 2)
            self.assertEqual(pad['pressed_masks'], [4096])
            self.assertEqual(pad['held_without_edge_while_unlocked_frames'], 0)
            self.assertIn('not distinct events', report['scope'])
            for path in (original, rebuilt):
                movement_fixture(path, pad={'pad_pressed': '0'})
            held = compare_runtime.compare_native_observations(original, rebuilt, 1)
            self.assertEqual(held['phases']['walk_forward']['native_pad']
                             ['held_without_edge_while_unlocked_frames'], 1)

    def test_native_pad_headers_cannot_be_partial(self):
        with tempfile.TemporaryDirectory() as folder:
            original, rebuilt = Path(folder) / 'original', Path(folder) / 'rebuilt'
            for path in (original, rebuilt):
                path.mkdir()
                movement_fixture(path, pad={})
                lines = (path / 'movement.tsv').read_text().splitlines()
                (path / 'movement.tsv').write_text('\n'.join(line.rsplit('\t', 1)[0] for line in lines) + '\n')
            with self.assertRaisesRegex(ValueError, 'header is unsupported'):
                compare_runtime.compare_native_observations(original, rebuilt, 1)

    def test_native_pad_capture_cannot_be_dropped_from_one_run(self):
        with tempfile.TemporaryDirectory() as folder:
            original, rebuilt = Path(folder) / 'original', Path(folder) / 'rebuilt'
            for path in (original, rebuilt):
                path.mkdir()
            movement_fixture(original, pad={})
            movement_fixture(rebuilt)
            with self.assertRaisesRegex(ValueError, 'headers must agree'):
                compare_runtime.compare_native_observations(original, rebuilt, 1)

    def test_native_pad_pointer_must_identify_an_aligned_whole_object(self):
        with tempfile.TemporaryDirectory() as folder:
            original, rebuilt = Path(folder) / 'original', Path(folder) / 'rebuilt'
            for path in (original, rebuilt):
                path.mkdir()
            for invalid in ('00000000', '00091f35', '001fffe4', '80091f34'):
                with self.subTest(pointer=invalid):
                    for path in (original, rebuilt):
                        movement_fixture(path, pad={'pad': invalid})
                    with self.assertRaisesRegex(ValueError, 'pad pointer'):
                        compare_runtime.compare_native_observations(original, rebuilt, 1)

    def test_native_pad_masks_cannot_be_negative_or_overflow(self):
        with tempfile.TemporaryDirectory() as folder:
            original, rebuilt = Path(folder) / 'original', Path(folder) / 'rebuilt'
            for path in (original, rebuilt):
                path.mkdir()
            for field in compare_runtime.PAD_FIELDS[1:]:
                for invalid in ('-1', '4294967296'):
                    with self.subTest(field=field, mask=invalid):
                        for path in (original, rebuilt):
                            movement_fixture(path, pad={field: invalid})
                        with self.assertRaisesRegex(ValueError, 'unsigned 32-bit'):
                            compare_runtime.compare_native_observations(original, rebuilt, 1)

    def test_changed_native_position_fails_with_equal_checkpoint_payloads(self):
        with tempfile.TemporaryDirectory() as folder:
            original, rebuilt = Path(folder) / 'original', Path(folder) / 'rebuilt'
            for path in (original, rebuilt):
                run_fixture(path, (2026, 10, 10, 1, 0, 0))
                movement_fixture(path)
            self.assertTrue(compare_runtime.compare_runs(original, rebuilt)['equal_recorded_outputs'])
            movement_fixture(rebuilt, x=101)
            report = compare_runtime.compare_runs(original, rebuilt)
            self.assertFalse(report['equal_recorded_outputs'])
            self.assertFalse(report['native_observations']['equal_native_state'])

    def test_missing_native_observation_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            original, rebuilt = Path(folder) / 'original', Path(folder) / 'rebuilt'
            for path in (original, rebuilt):
                run_fixture(path, (2026, 10, 10, 1, 0, 0))
            movement_fixture(original)
            with self.assertRaisesRegex(ValueError, 'Both runs'):
                compare_runtime.compare_runs(original, rebuilt)

    def test_identical_truncated_native_observations_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            original, rebuilt = Path(folder) / 'original', Path(folder) / 'rebuilt'
            for path in (original, rebuilt):
                run_fixture(path, (2026, 10, 10, 1, 0, 0))
                movement_fixture(path, include_frame=False)
            with self.assertRaisesRegex(ValueError, 'every frame'):
                compare_runtime.compare_runs(original, rebuilt)

    def test_native_observation_omitted_field_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            original, rebuilt = Path(folder) / 'original', Path(folder) / 'rebuilt'
            for path in (original, rebuilt):
                run_fixture(path, (2026, 10, 10, 1, 0, 0))
                movement_fixture(path)
                text = (path / 'movement.tsv').read_text().splitlines()
                text[1] = text[1].rsplit('\t', 1)[0]
                (path / 'movement.tsv').write_text('\n'.join(text) + '\n')
            with self.assertRaisesRegex(ValueError, 'every frame and field'):
                compare_runtime.compare_runs(original, rebuilt)

    def audio_fixture(self, path, samples):
        with wave.open(str(path), 'wb') as audio:
            audio.setnchannels(2)
            audio.setsampwidth(2)
            audio.setframerate(44100)
            audio.writeframes(struct.pack('<' + 'h' * len(samples), *samples))

    def test_audio_comparison_hashes_real_pcm_samples(self):
        with tempfile.TemporaryDirectory() as folder:
            original, rebuilt = Path(folder) / 'original.wav', Path(folder) / 'rebuilt.wav'
            self.audio_fixture(original, [0, 0, 42, -42])
            self.audio_fixture(rebuilt, [0, 0, 42, -42])
            report = compare_runtime.compare_audio(original, rebuilt)
            self.assertTrue(report['equal_pcm_output'])
            self.assertEqual(report['original']['sample_frames'], 2)
            self.assertEqual(report['original']['nonzero_channel_samples'], 2)
            self.audio_fixture(rebuilt, [0, 0, 43, -42])
            self.assertFalse(compare_runtime.compare_audio(original, rebuilt)['equal_pcm_output'])

    def test_empty_audio_is_not_output_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'empty.wav'
            self.audio_fixture(path, [])
            with self.assertRaisesRegex(ValueError, 'nonempty'):
                compare_runtime.inspect_audio(path)

    def test_truncated_audio_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'truncated.wav'
            self.audio_fixture(path, [1, 2, 3, 4])
            path.write_bytes(path.read_bytes()[:-4])
            with self.assertRaisesRegex(ValueError, 'declared sample count'):
                compare_runtime.inspect_audio(path)

    def test_archive_timestamp_difference_does_not_change_emulated_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            original, rebuilt = Path(folder) / "original", Path(folder) / "rebuilt"
            run_fixture(original, (2026, 10, 10, 1, 0, 0))
            run_fixture(rebuilt, (2026, 10, 10, 2, 0, 0))
            report = compare_runtime.compare_runs(original, rebuilt)
            self.assertTrue(report["equal_recorded_outputs"])
            self.assertFalse(report["save_states"]["frame-1.State"]["archive_bytes_equal"])
            self.assertEqual(report["feature_groups_accepted"], 0)

    def test_changed_core_payload_fails_even_with_equal_images(self):
        with tempfile.TemporaryDirectory() as folder:
            original, rebuilt = Path(folder) / "original", Path(folder) / "rebuilt"
            run_fixture(original, (2026, 10, 10, 1, 0, 0))
            run_fixture(rebuilt, (2026, 10, 10, 1, 0, 0), b"changed emulated state")
            self.assertFalse(compare_runtime.compare_runs(original, rebuilt)["equal_recorded_outputs"])

    def test_missing_checkpoint_cannot_be_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            original, rebuilt = Path(folder) / "original", Path(folder) / "rebuilt"
            run_fixture(original, (2026, 10, 10, 1, 0, 0))
            run_fixture(rebuilt, (2026, 10, 10, 1, 0, 0))
            (rebuilt / "gpu-1.bin").unlink()
            report = compare_runtime.compare_runs(original, rebuilt)
            self.assertFalse(report["equal_recorded_outputs"])
            self.assertEqual(report["missing_checkpoints"], ["gpu-1.bin"])

    def test_metadata_only_state_cannot_be_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            original, rebuilt = Path(folder) / "original", Path(folder) / "rebuilt"
            run_fixture(original, (2026, 10, 10, 1, 0, 0))
            run_fixture(rebuilt, (2026, 10, 10, 1, 0, 0))
            with zipfile.ZipFile(rebuilt / "frame-1.State", "w") as state:
                state.writestr("BizVersion.txt", "test")
            with self.assertRaisesRegex(ValueError, "core payload"):
                compare_runtime.compare_runs(original, rebuilt)

    def test_empty_frame_trace_cannot_be_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            original, rebuilt = Path(folder) / "original", Path(folder) / "rebuilt"
            run_fixture(original, (2026, 10, 10, 1, 0, 0))
            run_fixture(rebuilt, (2026, 10, 10, 1, 0, 0))
            (rebuilt / "trace.tsv").write_text("")
            with self.assertRaisesRegex(ValueError, "trace header"):
                compare_runtime.compare_runs(original, rebuilt)


if __name__ == "__main__":
    unittest.main()
