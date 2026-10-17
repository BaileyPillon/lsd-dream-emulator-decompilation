"""Owned synthetic records exercise cold-start evidence rejection boundaries."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import compare_cold_start as cold
from tools import capture_cold_start as capture


def checkpoint():
    raw = bytearray(0x200000)
    flow, dream, graphics, pad = 0x90000, 0x91000, 0x92000, 0x92100
    session, scene, coordinate, pose = 0x93000, 0x94000, 0x95000, 0x95100
    values = {0x8ac20: 0x80000000 + flow, flow: 0x8006d3c8, flow + 0x28: 0x80000000 + dream,
              flow + 0x1c: 0x80000000 + graphics, dream: 0x80087bdc, graphics + 4: 0x80000000 + pad,
              pad: 0x8006d370, dream + 0x24: 480, dream + 0x164: 3, dream + 0x878: 1,
              session: 0x800865c8, session + 0xc: 0x80000000 + graphics,
              session + 0x38: 0x80000000 + dream, session + 0x3c: 2, session + 0x4c: 0x80000000 + scene,
              scene: 0x80087034, dream + 0x14: 0x80000000 + coordinate, coordinate + 0x44: 0x80000000 + pose}
    for offset, value in values.items():
        struct.pack_into('<I', raw, offset, value)
    struct.pack_into('<iii', raw, coordinate + 0x18, -5120, 0, -1024)
    struct.pack_into('<h', raw, pose + 0x12, 2048)
    row = {name: '-' for name in cold.TRACE_FIELDS}
    row.update(relative_frame='0', core_frame='1', screen_kind='unlocked_dream', flow=str(flow), dream=str(dream),
               pad=str(pad), timer='480', map='3', stored_day='0', new_game='1', input_locked='0',
               session=str(session), session_state='2', map_scene=str(scene), coordinate=str(coordinate),
               pose=str(pose), x='-5120', y='0', z='-1024', yaw='2048',
               pad_held='0', pad_released='0', pad_pressed='0', gpu_sha256='0' * 64)
    return raw, row


def submissions():
    boolean = ['P1 D-Pad Up'] + ['Owned Boolean ' + str(i) for i in range(20)]
    numeric = ['P1 LStick X', 'P1 LStick Y', 'P1 RStick X', 'P1 RStick Y', 'Disc Select']
    definitions = [{'name': name, 'type': 'boolean', 'initial_value': 'false', 'neutral_value': 'false'} for name in boolean]
    definitions += [{'name': name, 'type': 'number', 'initial_value': '0' if name == 'Disc Select' else '128',
                     'neutral_value': '0' if name == 'Disc Select' else '128'} for name in numeric]
    row = {item['name']: item['neutral_value'] for item in definitions}
    row.update(relative_frame='1', core_frame='10', phase='walk_forward', buttons='P1 D-Pad Up')
    row['P1 D-Pad Up'] = 'true'
    header = ('relative_frame', 'core_frame', 'phase', 'buttons', *sorted(item['name'] for item in definitions))
    return header, definitions, [row], [{'core_frame': '10'}, {'core_frame': '11'}]


class NativeCheckpointTests(unittest.TestCase):
    def test_owned_checkpoint_has_consistent_native_owners_and_pose(self):
        raw, row = checkpoint()
        cold.validate_ram(raw, row)

    def test_forged_unlocked_state_cannot_omit_owner_chain(self):
        raw, row = checkpoint()
        row['flow'] = '-'
        with self.assertRaisesRegex(ValueError, 'owner chain'):
            cold.validate_ram(raw, row)

    def test_changed_native_input_lock_is_rejected(self):
        raw, row = checkpoint()
        struct.pack_into('<I', raw, int(row['dream']) + 0x70, 1)
        with self.assertRaisesRegex(ValueError, 'input_locked'):
            cold.validate_ram(raw, row)

    def test_wrong_dream_session_owner_is_rejected(self):
        raw, row = checkpoint()
        struct.pack_into('<I', raw, int(row['session']) + 0x38, 0x80099000)
        with self.assertRaisesRegex(ValueError, 'session ownership'):
            cold.validate_ram(raw, row)

    def test_wrong_map_scene_type_is_rejected(self):
        raw, row = checkpoint()
        struct.pack_into('<I', raw, int(row['map_scene']), 0)
        with self.assertRaisesRegex(ValueError, 'map-scene type'):
            cold.validate_ram(raw, row)

    def test_changed_position_is_rejected(self):
        raw, row = checkpoint()
        struct.pack_into('<i', raw, int(row['coordinate']) + 0x18, -5119)
        with self.assertRaisesRegex(ValueError, ': x'):
            cold.validate_ram(raw, row)

    def test_unmapped_native_field_is_rejected(self):
        raw, row = checkpoint()
        row['session'] = str(0x200000)
        with self.assertRaisesRegex(ValueError, 'outside aligned MainRAM'):
            cold.validate_ram(raw, row)

    def test_partial_ram_is_rejected(self):
        raw, row = checkpoint()
        with self.assertRaisesRegex(ValueError, 'complete MainRAM'):
            cold.validate_ram(raw[:-1], row)


class SubmittedControlTests(unittest.TestCase):
    def test_complete_owned_controller_row_is_valid(self):
        args = submissions()
        self.assertEqual(set(cold.validate_submissions(*args, frames=1)), {'walk_forward'})

    def test_unreported_button_is_rejected(self):
        args = submissions()
        args[2][0]['Owned Boolean 0'] = 'true'
        with self.assertRaisesRegex(ValueError, 'declared buttons'):
            cold.validate_submissions(*args, frames=1)

    def test_changed_analog_input_is_rejected(self):
        args = submissions()
        args[2][0]['P1 LStick X'] = '127'
        with self.assertRaisesRegex(ValueError, 'analog or disc'):
            cold.validate_submissions(*args, frames=1)

    def test_changed_disc_selector_is_rejected(self):
        args = submissions()
        args[2][0]['Disc Select'] = '1'
        with self.assertRaisesRegex(ValueError, 'analog or disc'):
            cold.validate_submissions(*args, frames=1)

    def test_pre_frame_boundary_mismatch_is_rejected(self):
        args = submissions()
        args[2][0]['core_frame'] = '11'
        with self.assertRaisesRegex(ValueError, 'pre-frame controller'):
            cold.validate_submissions(*args, frames=1)

    def test_missing_input_frame_is_rejected(self):
        header, definitions, _, observations = submissions()
        with self.assertRaisesRegex(ValueError, 'every advanced frame'):
            cold.validate_submissions(header, definitions, [], observations, frames=1)

    def test_duplicate_definition_is_rejected(self):
        header, definitions, rows, observations = submissions()
        definitions[-1] = definitions[0].copy()
        with self.assertRaisesRegex(ValueError, 'controller definition'):
            cold.validate_submissions(header, definitions, rows, observations, frames=1)


class EvidenceFileTests(unittest.TestCase):
    def test_one_day_advance_cannot_switch_dream_owner(self):
        _, first = checkpoint()
        second = dict(first, relative_frame='1', stored_day='1')
        self.assertEqual(cold.summarize_days([first, second], 0)['changes'],
                         [{'relative_frame': 1, 'before': 0, 'after': 1}])
        second['dream'] = str(int(second['dream']) + 0x100)
        with self.assertRaisesRegex(ValueError, 'dream owner changed'):
            cold.summarize_days([first, second], 0)

    def test_day_jump_is_not_single_day_progression(self):
        _, first = checkpoint()
        second = dict(first, relative_frame='1', stored_day='2')
        with self.assertRaisesRegex(ValueError, 'one-day advance'):
            cold.summarize_days([first, second], 0)

    def test_year_rollover_remains_one_day_progression(self):
        _, first = checkpoint()
        first['stored_day'] = '364'
        second = dict(first, relative_frame='1', stored_day='0')
        self.assertEqual(cold.summarize_days([first, second], 0)['changes'],
                         [{'relative_frame': 1, 'before': 364, 'after': 0}])

    def test_invalid_frame_count_is_rejected_before_capture_launch_or_input_reads(self):
        with patch.object(capture.subprocess, 'check_output') as launch_probe:
            for frames in (5999, 30001, True, 6000.0):
                with self.subTest(frames=frames), self.assertRaisesRegex(ValueError, '6,000 through 30,000'):
                    capture.capture_pair('unused', 'unused', 'unused', 'unused', 'unused', frames=frames)
            launch_probe.assert_not_called()

    def test_invalid_frame_count_is_rejected_before_comparison_input_reads(self):
        with patch.object(cold, 'compare_inputs') as load:
            for frames in (5999, 30001, False, 30000.0):
                with self.subTest(frames=frames), self.assertRaisesRegex(ValueError, '6,000 through 30,000'):
                    cold.compare_pair('unused', 'unused', frames=frames)
            load.assert_not_called()

    def test_truncated_table_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'owned.tsv'
            path.write_text('frame\tvalue\n0\n')
            with self.assertRaisesRegex(ValueError, 'truncated'):
                cold.read_tsv(path)

    def test_duplicate_columns_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'owned.tsv'
            path.write_text('frame\tframe\n0\t0\n')
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                cold.read_tsv(path)

    def test_report_path_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder, redirect_stderr(io.StringIO()):
            output = Path(folder) / 'retained.json'
            output.write_text('retained evidence')
            with patch.object(cold, 'compare_pair') as compare:
                self.assertEqual(cold.main(['--original', folder, '--rebuilt', folder, '--output', str(output)]), 2)
                compare.assert_not_called()
            self.assertEqual(output.read_text(), 'retained evidence')

    def test_equal_game_outputs_do_not_hide_raw_state_failure(self):
        report = {'status': 'recorded_cold_start_differences', 'controller_native_RAM_GPU_PNG_audio_outputs_equal': True,
                  'all_state_member_payloads_equal': False, 'state_bytes_masked': 0}
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()):
            output = Path(folder) / 'new.json'
            with patch.object(cold, 'compare_pair', return_value=report):
                self.assertEqual(cold.main(['--original', folder, '--rebuilt', folder, '--output', str(output)]), 2)
            self.assertFalse(json.loads(output.read_text())['all_state_member_payloads_equal'])


if __name__ == '__main__':
    unittest.main()
