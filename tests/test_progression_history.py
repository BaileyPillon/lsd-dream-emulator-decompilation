import contextlib
import copy
import io
import json
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest
import zlib

from tools import inspect_progression_history as history


PIXELS = bytes((10, 20, 30, 40, 50, 60, 20, 40, 60, 80, 100, 120))


def png(encoded=None):
    def chunk(kind, value):
        return (struct.pack('>I', len(value)) + kind + value
                + struct.pack('>I', zlib.crc32(kind + value) & 0xffffffff))
    encoded = encoded if encoded is not None else b'\x00' + PIXELS[:6] + b'\x00' + PIXELS[6:]
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 2, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(encoded)) + chunk(b'IEND', b''))


def native_state(frame, year):
    absolute = min(365, max(0, (frame - 1) // 2)) if year else sum(frame >= f for f in (601, 1200))
    return dict(address=0x91530 if frame else 0, year=absolute // 365, day=absolute % 365,
                timer=0, limit=3600, paused=0, flashback=0, link=0,
                stored_day=min(absolute, 364), menu=0, selection=-1, found=bool(frame),
                AbsoluteDay=absolute)


def fixture(year=False, post=12000, movie=True):
    """Synthetic file-format fixture; this is never counted as native evidence."""
    day_frames = [2 * n + 1 for n in range(366)] if year else [1, 601, 1200]
    wrap = day_frames[-1] if year else -1
    last = wrap + post if year else 1201
    ending = []
    if year and movie:
        base = (wrap // 30 + 1) * 30
        for at, flag in ((base, 0), (base + 30, 1)):
            item = dict(address=0xa0000, path_pointer=0x80074000, path='ETC\\ENDING.STR',
                        encoded_frame_threshold=474, play_flags=1, decoder_result=flag, completion_flag=flag)
            ending.append(dict(frame=at, core_frame=at + 1, state=native_state(at, year), movies=[item]))
    day_rows = [dict(frame=at, core_frame=at + 1, state=native_state(at, year), completed_days=n)
                for n, at in enumerate(day_frames)]
    states = set(day_frames) | {r['frame'] for r in ending} | {last}
    checkpoints = []
    for at in sorted(set(range(0, last + 1, 600)) | states):
        checkpoints.append(dict(frame=at, core_frame=at + 1, state=native_state(at, year),
                                MainRAM_sha256=history.sha(b'RAM'), GPURAM_sha256=history.sha(b'GPU'),
                                RGB_sha256=history.sha(PIXELS), PCM_sample_frames=at + 1,
                                serialized_state_sha256=history.sha(str(at).encode()) if at in states else None))
    audio, first = [], 0
    for end in [0, *range(600, last + 1, 600), *([] if last % 600 == 0 else [last])]:
        audio.append(dict(first_frame=str(first), last_frame=str(end), sample_frames=str(end - first + 1),
                          PCM_sha256=history.sha(str((first, end)).encode())))
        first = end + 1
    image = history.png_rgb(png())
    images = {'final.png': image}
    if year:
        images.update({'ending-' + str(n) + '.png': copy.deepcopy(image)
                       for n in history.ENDING_IMAGES if n <= post})
    report = dict(status='completed_natural_year_and_ending_objects' if year else 'frame_ceiling_reached',
                  last_frame=last, frames_advanced=last + 1, completed_days=len(day_rows) - 1,
                  final_state=native_state(last, year), retained_stream_bytes=10,
                  retained_stream_limit=history.STREAM_LIMIT, total_PCM_sample_frames=last + 1,
                  **{k: False for k in history.SCOPE_FIELDS})
    if year:
        report.update(year_boundary_frame=wrap, post_year_frames_observed=post,
                      ending_path_pending_observed=movie, ending_completion_after_pending_observed=movie,
                      ending_object_observations=len(ending))
    return dict(report=report, days=day_rows, checkpoints=checkpoints, inputs=[{'frame': '0', 'mask': '0'}],
                audio=audio, ending=ending, images=images)


def encode_capture(folder, data, extended=True):
    folder.mkdir()
    (folder / 'report.json').write_text(json.dumps(data['report']))
    for key in ('days', 'checkpoints', *(['ending'] if extended else [])):
        (folder / (key + '.jsonl')).write_text(''.join(json.dumps(row) + '\n' for row in data[key]))
    for key, fields in [('inputs', ('frame', 'mask')),
                        ('audio', ('first_frame', 'last_frame', 'sample_frames', 'PCM_sha256'))]:
        (folder / (key + '.tsv')).write_text('\t'.join(fields) + '\n' + ''.join(
            '\t'.join(row[f] for f in fields) + '\n' for row in data[key]))
    for name in data['images']:
        (folder / name).write_bytes(png())
    stream_names = ['days.jsonl', 'checkpoints.jsonl', 'audio.tsv', 'inputs.tsv']
    if extended:
        stream_names.append('ending.jsonl')
    report = copy.deepcopy(data['report'])
    report['retained_stream_bytes'] = sum((folder / name).stat().st_size for name in stream_names)
    (folder / 'report.json').write_text(json.dumps(report))


def pre_pending_fixture(raw_flag=177408):
    """Keep the raw first observation before the required zero/one transition."""
    data = fixture(True)
    raw = copy.deepcopy(data['ending'][0])
    raw['movies'][0]['completion_flag'] = raw_flag
    for row in data['ending']:
        row['frame'] += 30
        row['core_frame'] += 30
    terminal_frame = data['ending'][-1]['frame']
    checkpoint = copy.deepcopy(data['checkpoints'][-1])
    checkpoint.update(frame=terminal_frame, core_frame=terminal_frame+1,
        state=native_state(terminal_frame, True), PCM_sample_frames=terminal_frame+1,
        serialized_state_sha256=history.sha(str(terminal_frame).encode()))
    data['checkpoints'].append(checkpoint)
    data['checkpoints'].sort(key=lambda row: row['frame'])
    data['ending'].insert(0, raw)
    data['report']['ending_object_observations'] = 3
    return data


def seal(folder, members=None):
    members = list(history.JOURNALS) if members is None else members
    archive = folder / 'retained-journals.tar.xz'
    index = []
    with tarfile.open(archive, 'w:xz') as tar:
        for name in members:
            value = (folder / name).read_bytes() if (folder / name).exists() else b''
            info = tarfile.TarInfo(name)
            info.size = len(value)
            tar.addfile(info, io.BytesIO(value))
            index.append(dict(name=name, bytes=len(value), sha256=history.sha(value)))
    (folder / 'retained-journals.json').write_text(json.dumps(dict(
        archive=archive.name, archive_sha256=history.sha(archive.read_bytes()), files=index,
        all_members_full_sha256_verified=True, restore_readback_test_passed=True)))
    for name in members:
        if (folder / name).is_file():
            (folder / name).unlink()


class ProgressionHistoryTests(unittest.TestCase):
    def test_partial_scope_equality_does_not_satisfy_year_or_whole_feature(self):
        data = fixture()
        result = history.compare_data(data, copy.deepcopy(data))
        self.assertTrue(result['passed'])
        self.assertFalse(result['year_gate_observed'])
        self.assertEqual(result['whole_feature_groups_accepted'], 0)
        self.assertFalse(history.compare_data(data, data, True)['passed'])

    def test_year_window_is_bounded_recorded_evidence_and_not_movie_decode_proof(self):
        data = fixture(True)
        result = history.compare_data(data, copy.deepcopy(data), True)
        self.assertTrue(result['passed'])
        self.assertEqual(result['original']['completed_days'], 365)
        self.assertEqual(result['original']['ending_terminal_objects'], 1)
        self.assertFalse(result['original']['complete_ending_decode_verified'])
        self.assertFalse(result['complete_emulator_or_game_parity_accepted'])

    def test_missing_state_hashes_are_never_counted_as_equal_complete_states(self):
        data = fixture()
        result = history.compare_data(data, copy.deepcopy(data))
        count = result['checkpoint_comparisons']['serialized_state_sha256']
        self.assertEqual(count['compared'], 4)
        self.assertLess(count['compared'], len(data['checkpoints']))

    def test_validly_formatted_changed_complete_state_fails_raw_comparison(self):
        a, b = fixture(), fixture()
        b['checkpoints'][-1]['serialized_state_sha256'] = 'f' * 64
        result = history.compare_data(a, b)
        self.assertFalse(result['passed'])
        self.assertEqual(result['checkpoint_comparisons']['serialized_state_sha256']['different'], 1)

    def test_cannot_drop_a_scheduled_state_or_add_an_unscheduled_state(self):
        for at in (0, 1):
            data = fixture()
            data['checkpoints'][at]['serialized_state_sha256'] = '0' * 64 if at == 0 else None
            with self.subTest(at=at), self.assertRaisesRegex(ValueError, 'declared schedule'):
                history.validate(data)

    def test_checkpoint_omission_duplicate_and_frame_shift_are_rejected(self):
        for action in ('omit', 'duplicate', 'shift'):
            data = fixture()
            if action == 'omit':
                del data['checkpoints'][2]
            elif action == 'duplicate':
                data['checkpoints'].insert(2, copy.deepcopy(data['checkpoints'][2]))
            else:
                data['checkpoints'][2]['frame'] += 1
            with self.subTest(action=action), self.assertRaisesRegex(ValueError, 'checkpoint'):
                history.validate(data)

    def test_checkpoint_counter_cannot_diverge_from_day_events(self):
        data = fixture()
        data['checkpoints'][2]['state'].update(day=1, AbsoluteDay=1)
        with self.assertRaisesRegex(ValueError, 'Checkpoint day'):
            history.validate(data)

    def test_pinned_dream_object_cannot_silently_change(self):
        data = fixture()
        data['days'][1]['state']['address'] += 4
        with self.assertRaisesRegex(ValueError, 'object changed identity'):
            history.validate(data)

    def test_nonobject_report_and_journal_rows_are_rejected(self):
        data = fixture()
        data['report'] = []
        with self.assertRaisesRegex(ValueError, 'must be objects'):
            history.validate(data)
        data = fixture()
        data['days'][0] = 5
        with self.assertRaisesRegex(ValueError, 'journals must contain objects'):
            history.validate(data)

    def test_early_year_wrap_and_day_regression_are_rejected(self):
        for change in ('early_wrap', 'regression', 'gap'):
            data = fixture(True)
            row = data['days'][100]
            if change == 'early_wrap':
                row['state'].update(year=1, day=0, AbsoluteDay=365)
            elif change == 'regression':
                row['state'].update(day=99, AbsoluteDay=99)
            else:
                del data['days'][100]
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'day|Completed'):
                history.validate(data)

    def test_audio_omission_overlap_total_and_sample_boundary_drift_are_rejected(self):
        for change in ('omit', 'overlap', 'total', 'boundary', 'checkpoint'):
            data = fixture()
            if change == 'omit':
                del data['audio'][1]
            elif change == 'overlap':
                data['audio'][1]['first_frame'] = '0'
            elif change == 'total':
                data['report']['total_PCM_sample_frames'] += 1
            elif change == 'boundary':
                data['audio'][1]['last_frame'] = '599'
            else:
                data['checkpoints'][2]['PCM_sample_frames'] += 1
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'PCM'):
                history.validate(data)

    def test_audio_digest_change_remains_a_comparison_failure(self):
        a, b = fixture(), fixture()
        b['audio'][1]['PCM_sha256'] = 'f' * 64
        self.assertIn('audio', history.compare_data(a, b)['differences'])

    def test_booleans_cannot_masquerade_as_native_counts(self):
        data = fixture()
        data['report']['frames_advanced'] = True
        with self.assertRaisesRegex(ValueError, 'frame total'):
            history.validate(data)
        data = fixture()
        data['days'][0]['completed_days'] = False
        with self.assertRaisesRegex(ValueError, 'Completed-day'):
            history.validate(data)

    def test_scope_flags_cannot_turn_a_capture_into_whole_parity(self):
        for name in history.SCOPE_FIELDS:
            data = fixture()
            data['report'][name] = True
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'scope'):
                history.validate(data)

    def test_post_year_held_button_is_rejected_even_if_later_released(self):
        data = fixture(True)
        wrap = data['report']['year_boundary_frame']
        data['inputs'] += [{'frame': str(wrap), 'mask': '1'}, {'frame': str(wrap + 2), 'mask': '0'}]
        with self.assertRaisesRegex(ValueError, 'post-year frame'):
            history.validate(data)

    def test_missing_pending_or_wrong_object_cannot_become_ending_completion(self):
        for action in ('pending', 'object', 'report', 'duplicate'):
            data = fixture(True)
            if action == 'pending':
                data['ending'][0]['movies'][0]['completion_flag'] = 1
            elif action == 'object':
                data['ending'][1]['movies'][0]['address'] += 4
            elif action == 'report':
                data['report']['ending_completion_after_pending_observed'] = False
            else:
                data['ending'][0]['movies'].append(copy.deepcopy(data['ending'][0]['movies'][0]))
            with self.subTest(action=action), self.assertRaisesRegex(ValueError, 'ending|pending'):
                history.validate(data)

    def test_wrong_path_threshold_flag_and_decoder_contract_are_rejected(self):
        for key, value in [('path', 'ETC\\OTHER.STR'), ('encoded_frame_threshold', 473),
                           ('play_flags', True), ('decoder_result', True)]:
            data = fixture(True)
            data['ending'][1]['movies'][0][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'Ending|decoder'):
                history.validate(data)

    def test_opaque_nonzero_terminal_signal_is_not_complete_decode_proof(self):
        data = fixture(True)
        data['ending'][1]['movies'][0]['decoder_result'] = -2147198648
        result = history.validate(data)
        self.assertEqual(result['ending_terminal_objects'], 1)
        self.assertFalse(result['complete_ending_decode_verified'])

    def test_raw_flag_before_first_pending_is_retained_without_completion_credit(self):
        for value in (177408, -1, -(2**31), 2**31-1):
            data = pre_pending_fixture(value)
            result = history.validate(data)
            self.assertEqual(result['ending_pre_pending_raw_flag_observations'], 1)
            self.assertEqual(result['ending_pending_objects'], 1)
            self.assertEqual(result['ending_terminal_objects'], 1)
            self.assertEqual(data['ending'][0]['movies'][0]['completion_flag'], value)
            self.assertFalse(result['complete_ending_decode_verified'])
            self.assertEqual(result['whole_feature_groups_accepted'], 0)

    def test_raw_flag_difference_still_fails_strict_recording_comparison(self):
        original, rebuilt = pre_pending_fixture(), pre_pending_fixture(177409)
        result = history.compare_data(original, rebuilt, True)
        self.assertFalse(result['passed'])
        self.assertIn('ending', result['differences'])

    def test_nonboolean_flag_after_pending_and_invalid_raw_types_are_rejected(self):
        data = fixture(True)
        data['ending'][-1]['movies'][0]['completion_flag'] = 177408
        with self.assertRaisesRegex(ValueError, 'after pending'):
            history.validate(data)
        for value in (True, 2**31, -(2**31)-1, 1.5, '177408'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'completion flag'):
                history.validate(pre_pending_fixture(value))

    def test_pre_pending_raw_flag_cannot_replace_required_zero_transition(self):
        data = fixture(True)
        data['ending'][0]['movies'][0]['completion_flag'] = 177408
        with self.assertRaisesRegex(ValueError, 'pending'):
            history.validate(data)

    def test_short_neutral_window_and_missing_movie_do_not_satisfy_year(self):
        for data in (fixture(True, post=11999), fixture(True, movie=False)):
            data['report']['status'] = 'frame_ceiling_reached'
            self.assertFalse(history.compare_data(data, data, True)['passed'])

    def test_missing_ending_png_is_rejected(self):
        data = fixture(True)
        del data['images']['ending-1800.png']
        with self.assertRaisesRegex(ValueError, 'PNG coverage'):
            history.validate(data)

    def test_final_png_must_match_native_rgb(self):
        data = fixture()
        data['images']['final.png']['RGB_sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'native RGB'):
            history.validate(data)

    def test_png_filters_have_independently_encoded_known_pixels(self):
        encoded = [
            b'\x00' + PIXELS[:6] + b'\x00' + PIXELS[6:],
            bytes((1, 10, 20, 30, 30, 30, 30, 1, 20, 40, 60, 60, 60, 60)),
            bytes((2, 10, 20, 30, 40, 50, 60, 2, 10, 20, 30, 40, 50, 60)),
            bytes((3, 10, 20, 30, 35, 40, 45, 3, 15, 30, 45, 50, 55, 60)),
            bytes((4, 10, 20, 30, 30, 30, 30, 4, 10, 20, 30, 40, 50, 60)),
        ]
        for mode, raw in enumerate(encoded):
            with self.subTest(filter=mode):
                self.assertEqual(history.png_rgb(png(raw))['RGB_sha256'], history.sha(PIXELS))

    def test_png_crc_trailing_data_and_oversized_expansion_are_rejected(self):
        bad_crc = bytearray(png())
        bad_crc[-1] ^= 1
        for data in (bytes(bad_crc), png() + b'junk', png(b'\x00' * 1000)):
            with self.assertRaises(ValueError):
                history.png_rgb(data)

    def test_duplicate_json_fields_and_nonfinite_numbers_are_rejected(self):
        for raw in (b'{"frame":1,"frame":2}', b'{"frame":NaN}'):
            with self.assertRaises(ValueError):
                history.document(raw)

    def test_valid_sealed_archive_is_inspected_in_memory_without_restoration(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'recording'
            data = fixture(True)
            encode_capture(folder, data)
            seal(folder)
            self.assertTrue(history.validate(history.load_recording(folder))['year_route_observed'])
            self.assertTrue(all(not (folder / name).exists() for name in history.JOURNALS))

    def test_sealed_archive_digest_and_member_catalogue_cannot_be_changed(self):
        for change in ('digest', 'duplicate', 'member'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary) / 'recording'
                encode_capture(folder, fixture(True))
                seal(folder)
                p = folder / 'retained-journals.json'
                index = json.loads(p.read_text())
                if change == 'digest':
                    index['archive_sha256'] = '0' * 64
                elif change == 'duplicate':
                    index['files'][1] = index['files'][0]
                else:
                    index['files'][0]['sha256'] = '0' * 64
                p.write_text(json.dumps(index))
                with self.assertRaises(ValueError):
                    history.RecordingFiles(folder)

    def test_restored_file_must_still_match_its_sealed_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'recording'
            encode_capture(folder, fixture(True))
            seal(folder)
            (folder / 'days.jsonl').write_text('changed expanded copy')
            with self.assertRaisesRegex(ValueError, 'Restored journal'):
                history.load_recording(folder)

    def test_declared_storage_cannot_hide_more_retained_journal_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'recording'
            encode_capture(folder, fixture(), False)
            p = folder / 'report.json'
            report = json.loads(p.read_text())
            report['retained_stream_bytes'] -= 1
            p.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'stream bytes differ'):
                history.validate(history.load_recording(folder))

    def test_cli_preserves_existing_report_and_uses_nonzero_for_unmet_year(self):
        with tempfile.TemporaryDirectory() as temporary, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            root = Path(temporary)
            a, b = root / 'original', root / 'rebuilt'
            data = fixture()
            encode_capture(a, data, False)
            encode_capture(b, data, False)
            out = root / 'report.json'
            self.assertEqual(history.main(['compare', str(a), str(b), '--require-year-ending', '--output', str(out)]), 1)
            before = out.read_bytes()
            self.assertEqual(history.main(['compare', str(a), str(b), '--output', str(out)]), 2)
            self.assertEqual(out.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
