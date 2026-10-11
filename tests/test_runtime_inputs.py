"""Reject apparently equal replays whose original launch inputs differ."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import runtime_inputs


def fixture(folder, title="original", track=b"same disc bytes", state=b"same state"):
    folder.mkdir()
    cue = folder / (title + ".cue")
    binary = folder / (title + ".bin")
    binary.write_bytes(track)
    cue.write_text(f'FILE "{binary.name}" BINARY\n TRACK 01 MODE2/2352\n INDEX 01 00:00:00\n')
    emulator, bios = folder / "emulator", folder / "bios"
    emulator.mkdir()
    bios.mkdir()
    for name in runtime_inputs.EMULATOR_FILES:
        target = emulator / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(("fixture " + name).encode())
    for name in runtime_inputs.BIOS_FILES.values():
        (bios / name).write_bytes(("fixture " + name).encode())
    config, script, start = folder / "configuration.json", folder / "input.lua", folder / "start.State"
    config.write_text('{"fixture": true}')
    script.write_text("emu.frameadvance()")
    start.write_bytes(state)
    manifest = runtime_inputs.pin_inputs(cue, bios, emulator, config, script, "play", 6000, start)
    (folder / "inputs.json").write_text(json.dumps(manifest))
    return manifest


class RuntimeInputTests(unittest.TestCase):
    def test_different_track_filenames_with_identical_inputs_compare(self):
        with tempfile.TemporaryDirectory() as temporary:
            original, rebuilt = Path(temporary) / "original", Path(temporary) / "rebuilt"
            fixture(original)
            fixture(rebuilt, "rebuilt")
            report = runtime_inputs.compare_inputs(original, rebuilt, "play", 6000)
            self.assertTrue(report["inputs_verified"])
            self.assertEqual(report["status"], "pinned_inputs_identical")

    def test_json_member_order_is_not_an_emulator_setting_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            original, rebuilt = Path(temporary) / "original", Path(temporary) / "rebuilt"
            first, second = fixture(original), fixture(rebuilt)
            for folder, manifest, text in ((original, first, '{"a": 1, "b": false}'),
                                           (rebuilt, second, '{"b": false, "a": 1}')):
                Path(manifest['configuration']['path']).write_text(text)
                manifest['configuration'] = runtime_inputs.record_file(manifest['configuration']['path'])
                (folder / 'inputs.json').write_text(json.dumps(manifest))
            self.assertTrue(runtime_inputs.compare_inputs(original, rebuilt, 'play', 6000)['inputs_verified'])

    def test_actual_configuration_value_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            original, rebuilt = Path(temporary) / "original", Path(temporary) / "rebuilt"
            fixture(original)
            manifest = fixture(rebuilt)
            Path(manifest['configuration']['path']).write_text('{"fixture": false}')
            manifest['configuration'] = runtime_inputs.record_file(manifest['configuration']['path'])
            (rebuilt / 'inputs.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'configuration'):
                runtime_inputs.compare_inputs(original, rebuilt, 'play', 6000)

    def test_different_disc_bytes_cannot_pass_with_equal_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            original, rebuilt = Path(temporary) / "original", Path(temporary) / "rebuilt"
            fixture(original)
            fixture(rebuilt, track=b"different disc")
            with self.assertRaisesRegex(ValueError, "disc_tracks"):
                runtime_inputs.compare_inputs(original, rebuilt, "play", 6000)

    def test_different_start_state_cannot_pass_with_equal_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            original, rebuilt = Path(temporary) / "original", Path(temporary) / "rebuilt"
            fixture(original)
            fixture(rebuilt, state=b"different state")
            with self.assertRaisesRegex(ValueError, "start_state"):
                runtime_inputs.compare_inputs(original, rebuilt, "play", 6000)

    def test_changed_bios_after_launch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "run"
            manifest = fixture(folder)
            Path(manifest["bios"]["J"]["path"]).write_bytes(b"changed BIOS")
            with self.assertRaisesRegex(ValueError, "pinned runtime input changed"):
                runtime_inputs.load_verified_manifest(folder)

    def test_manifest_layout_must_agree_with_real_cue(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "run"
            manifest = fixture(folder)
            manifest["disc"]["layout"][1] = "TRACK 01 MODE1/2352"
            (folder / "inputs.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "disc layout"):
                runtime_inputs.load_verified_manifest(folder)

    def test_only_one_manifest_cannot_claim_input_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            original, rebuilt = Path(temporary) / "original", Path(temporary) / "rebuilt"
            fixture(original)
            fixture(rebuilt)
            (rebuilt / "inputs.json").unlink()
            with self.assertRaisesRegex(ValueError, "Both runtime runs"):
                runtime_inputs.compare_inputs(original, rebuilt, "play", 6000)

    def test_legacy_runs_keep_explicit_unverified_input_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            original, rebuilt = Path(temporary) / "original", Path(temporary) / "rebuilt"
            original.mkdir()
            rebuilt.mkdir()
            report = runtime_inputs.compare_inputs(original, rebuilt, "boot", 1800)
            self.assertFalse(report["inputs_verified"])

    def test_frame_count_must_match_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            original, rebuilt = Path(temporary) / "original", Path(temporary) / "rebuilt"
            fixture(original)
            fixture(rebuilt)
            with self.assertRaisesRegex(ValueError, "completed runtime scenario"):
                runtime_inputs.compare_inputs(original, rebuilt, "play", 1800)

    def test_multi_file_cue_pins_every_track(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "run"
            manifest = fixture(folder)
            cue = Path(manifest["disc"]["cue"]["path"])
            (folder / "audio.bin").write_bytes(b"fixture audio")
            with cue.open("a") as output:
                output.write('FILE "audio.bin" BINARY\n TRACK 02 AUDIO\n INDEX 01 00:00:00\n')
            result = runtime_inputs.disc_inputs(cue)
            self.assertEqual(len(result["tracks"]), 2)
            self.assertEqual(result["layout"][-2], "TRACK 02 AUDIO")

    def test_unrecognized_cue_file_statement_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "run"
            manifest = fixture(folder)
            cue = Path(manifest["disc"]["cue"]["path"])
            cue.write_text('FILE "unknown.wav" WAVE\n TRACK 01 AUDIO\n')
            with self.assertRaisesRegex(ValueError, "quoted BINARY"):
                runtime_inputs.disc_inputs(cue)


if __name__ == "__main__":
    unittest.main()
