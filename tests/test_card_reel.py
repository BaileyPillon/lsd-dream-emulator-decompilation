"""Synthetic verifier fault tests; these are not native game/parity evidence."""
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

from tools import inspect_card_reel as reel
from tools.inspect_movie_windows import CHANNELS
from tools import prepare_card_reel as prepare
from tests.test_card_roundtrip import blank_card, install


def encode(row):
    return ('\t'.join(row[key] for key in reel.FIELDS) + '\n').encode('ascii')


def movie(row, cutoff, state, counter=0):
    identity = reel.catalog()[reel.REEL_PATH if cutoff == reel.REEL_CUTOFF else reel.playback.STARTUP_PATHS[cutoff]]
    row.update({key: '0' for key in reel.MOVIE_FIELDS[6:]})
    minute, second = divmod((identity['lba'] + 150) // 75, 60)
    sector = (identity['lba'] + 150) % 75
    bcd = lambda value: ((value // 10) << 4) | (value % 10)
    raw = struct.pack('<4BI16s', bcd(minute), bcd(second), bcd(sector), 0,
                      identity['logical_bytes'], identity['filename'].encode())
    for offset in range(0, 24, 4):
        row[f'stream_{offset + 12:02x}'] = str(int.from_bytes(raw[offset:offset + 4], 'little'))
    row.update(active_movie=str(0x800a0000), movie_00=str(0x8006f614), stream_00=str(0x800817e0),
        movie_60=str(0x800b0000), movie_24='320', movie_28='240', movie_5c=str(cutoff),
        stream_40=str(cutoff), stream_58=str(counter), stream_2c=str(state),
        movie_44='1' if state == 0 else '0', movie_48='1' if state == 0 else '0',
        movie_player=str(0x96000), player_path=('FILM\\SPDAY01A.STR' if cutoff == reel.REEL_CUTOFF
            else 'ETC\\' + identity['filename'].split(';')[0]), player_threshold=str(cutoff),
        player_length=str(reel.REEL_LENGTH if cutoff == reel.REEL_CUTOFF else 0xffffffff), player_result='0', player_done='0')


def image():
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\x00\x12\x34\x56')) + chunk(b'IEND', b''))


def fixture():
    rows = []
    for frame in range(1183):
        row = {key: '-' for key in reel.FIELDS}
        row.update(relative_frame=str(frame), core_frame=str(frame + 1), native_tables_ready='1', active_movie='0', rng='1', watchdog_counter='0')
        row.update({key: '0' for key in reel.ADDRESSES})
        row.update({key: str(int(frame >= start)) for key, start in zip(reel.STICKY, (200, 240, 300, 330, 380, 1002))})
        row.update(flow=str(0x94000), dream=str(0x95000), year='0', day='0' if frame < 280 else ('4' if frame < 350 else '5'),
            stored_day='4', new_game='0', dream_timer='1' if 330 <= frame < 350 else '0', dream_limit='18000', dream_paused='0',
            history_flag=str(int(frame >= 360)), four_cells_found='4' if frame >= 280 else '0',
            payload_sha256=('e' if frame >= 280 else 'f') * 64)
        if 200 <= frame < 320 or frame >= 1143:
            row.update(main=str(0x97000), main_selection='3' if frame < 300 else '0', main_state='0')
            if frame >= 240:
                row.update(card=str(0x98000), card_operation='1' if frame < 300 else '0', card_state='1' if frame < 300 else '0')
        if 355 <= frame < 376:
            row.update(graph=str(0x97000), graph_timer=str(frame - 355), graph_state='0', graph_result='0',
                       graph_reel_ready=str(int(frame >= 360)), graph_event_index=str(min(4, max(0, (frame - 360) // 2))))
        if 5 <= frame <= 62:
            movie(row, 90, 1 if frame == 5 else (0 if frame == 62 else 2), max(0, (min(frame, 61) - 6) // 4))
        elif 125 <= frame <= 182:
            movie(row, 1046, 1 if frame == 125 else (0 if frame == 182 else 2), max(0, (min(frame, 181) - 126) // 4))
        elif 380 <= frame < 1002:
            movie(row, reel.REEL_CUTOFF, 1 if frame == 380 else 2)
        rows.append(row)
    changes = [(0, 0)]
    for frame, row in enumerate(rows):
        mask = reel.controller_policy(frame, rows[frame - 1] if frame else None)
        if mask != changes[-1][1]:
            changes.append((frame, mask))
    lines = [encode(row) for row in rows]
    windows = []
    for first in range(0, len(lines), 600):
        selected = lines[first:first + 600]
        count, last = len(selected), first + len(selected) - 1
        native_hash, controller_hash = hashlib.sha256(), hashlib.sha256()
        for frame, line in enumerate(selected, first):
            native_hash.update(struct.pack('<iii', frame, frame + 1, len(line))); native_hash.update(line)
            mask = reel.controller_policy(frame, rows[frame - 1] if frame else None)
            controller_hash.update(struct.pack('<iiii', frame, frame + 1, 4, mask))
        hashes = {key: 'a' * 64 for key in CHANNELS}
        hashes.update(native=native_hash.hexdigest(), controller=controller_hash.hexdigest())
        windows.append(dict(first_frame=first, last_frame=last, frames=count, PCM_sample_frames=count,
            payload_bytes=dict(MainRAM=count * 0x200000, GPURAM=count * 0x100000, RGB=count * 11,
                PCM=count * 4, native=sum(map(len, selected)), controller=count * 4),
            framed_sha256=hashes, complete_state_sha256='b' * 64, final_MainRAM_sha256='c' * 64,
            final_GPURAM_sha256='d' * 64, final_RGB_with_dimensions_sha256='e' * 64))
    report = dict(schema_version=3, status='card_reel_cleared_and_post_window_completed', mode='card-reel',
        frames_advanced=len(lines), last_frame=len(lines) - 1, total_PCM_sample_frames=len(lines), raw_native_bytes=sum(map(len, lines)),
        load_seen=True, load_returned=True, load_returned_frame=300, dream_started=True, reel_seen=True,
        first_reel_frame=380, reel_cleared_frame=1002, post_reel_frames=180, input_card_sha256='a' * 64,
        final_SaveRAM_sha256='a' * 64, final_SaveRAM_matches_stored=True, expected_payload_sha256='e' * 64,
        prepared_external_card_loaded_using_ISaveRam=True, replayed_inputs=False, cold_start=True, restored_state=False,
        main_RAM_or_instruction_writes=False, player_UI_or_saves_accessed=False, hardware_timing_verified=False,
        whole_feature_groups_accepted=0, controller_buttons=sorted(reel.playback.DIGITAL_NAMES),
        controller_neutral_axes={key: int(value) for key, value in reel.playback.NUMERIC_NEUTRAL.items()}, elapsed_ms=1)
    store = dict(core_frame=0, initial_SaveRAM_bytes=131072, initial_SaveRAM_sha256='f' * 64, input_card_sha256='a' * 64,
        stored_SaveRAM_sha256='a' * 64, expected_payload_sha256='e' * 64, MainRAM_before_sha256='b' * 64,
        MainRAM_after_sha256='b' * 64, GPURAM_before_sha256='c' * 64, GPURAM_after_sha256='c' * 64,
        prepared_external_card_loaded_using_ISaveRam=True, main_RAM_or_instruction_writes=False,
        restored_state=False, user_player_saves_accessed=False)
    return rows, lines, changes, windows, report, store


class OneLineStream(io.BytesIO):
    def read(self, *args):
        raise AssertionError('Whole-stream reads are forbidden.')

    def readline(self, size=-1):
        if size != reel.LINE_LIMIT + 1:
            raise AssertionError('Every line read requires its bound.')
        return super().readline(size)


class CardReelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.lines, cls.changes, cls.windows, cls.report, cls.store = fixture()
        cls.header = ('\t'.join(reel.FIELDS) + '\n').encode('ascii')
        cls.raw = cls.header + b''.join(cls.lines)

    def inspect(self, raw=None, windows=None, changes=None):
        return reel.inspect_native(OneLineStream(self.raw if raw is None else raw), len(self.lines),
            self.windows if windows is None else windows, reel.catalog(), self.changes if changes is None else changes, self.report)

    def changed(self, index, values):
        row = dict(self.rows[index]); row.update(values)
        return self.header + b''.join(self.lines[:index]) + encode(row) + b''.join(self.lines[index + 1:])

    def test_full_streaming_route_and_complete_buffer_schedule(self):
        reel.validate_report(self.report); reel.validate_store(self.store, self.report)
        reel.validate_windows(self.windows, len(self.lines), len(self.lines))
        result = self.inspect()
        self.assertTrue(result['complete_card_reel_scope'])
        self.assertEqual(result['journal_sha256'], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(result['graph_flash_indices'], list(range(5)))
        self.assertTrue(result['concatenated_movie_payloads_consumed_not_claimed'])
        self.assertEqual(result['lifetimes'][-1]['maximum_id'], -1)

    def test_card_store_is_external_cold_input_with_no_RAM_mutation(self):
        for values in ({'core_frame': 1}, {'initial_SaveRAM_bytes': 262144}, {'stored_SaveRAM_sha256': 'd' * 64},
                       {'MainRAM_after_sha256': 'd' * 64}, {'restored_state': True}, {'user_player_saves_accessed': True}):
            store = dict(self.store); store.update(values)
            with self.subTest(values=values), self.assertRaises(ValueError):
                reel.validate_store(store, self.report)

    def test_incomplete_injected_overclaimed_or_unordered_reports_rejected(self):
        for values in ({'status': 'frame_ceiling_reached'}, {'whole_feature_groups_accepted': 1},
                       {'main_RAM_or_instruction_writes': True}, {'hardware_timing_verified': True},
                       {'first_reel_frame': 300}, {'post_reel_frames': 179}, {'schema_version': True},
                       {'final_SaveRAM_sha256': 'd' * 64}):
            report = dict(self.report); report.update(values)
            with self.subTest(values=values), self.assertRaises(ValueError):
                reel.validate_report(report)

    def test_complete_loaded_payload_and_four_cell_trigger_are_required(self):
        for frame, values in ((300, {'payload_sha256': 'd' * 64}), (300, {'four_cells_found': '3'}),
                              (360, {'graph_reel_ready': '0'}), (360, {'history_flag': '0'}),
                              (366, {'graph_event_index': '5'}), (400, {'history_flag': '0'})):
            with self.subTest(frame=frame, values=values), self.assertRaises(ValueError):
                self.inspect(self.changed(frame, values))

    def test_requested_extent_player_interval_and_bypass_counter_are_bound(self):
        for values in ({'stream_14': '1'}, {'movie_60': str(0x800b0004)}, {'player_length': '10109'},
                       {'player_threshold': '484'}, {'stream_58': '1'}, {'movie_44': '1'}, {'stream_2c': '0'}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.inspect(self.changed(400, values))

    def test_startup_skip_closes_then_removes_pointer(self):
        for frame, values in ((62, {'movie_48': '0'}), (62, {'stream_58': '1'}), (62, {'stream_2c': '2'}),
                              (125, {'stream_2c': '2'}), (130, {'stream_58': '100'})):
            with self.subTest(frame=frame, values=values), self.assertRaises(ValueError):
                self.inspect(self.changed(frame, values))

    def test_exact_UI_policy_and_neutral_gameplay_reel_are_required(self):
        self.assertEqual(reel.controller_policy(2220, {'reel_seen': '0', 'main_seen': '1', 'main': '1',
            'main_selection': '3', 'load_returned': '0', 'load_seen': '0', 'card_operation': '-'}), 1)
        changes = list(self.changes) + [(500, 1)]
        changes.sort()
        with self.assertRaisesRegex(ValueError, 'UI-only policy'):
            self.inspect(changes=changes)
        for raw in (b'frame\tmask\n0\t0\n1\t8\n', b'frame\tmask\n0\t0\n0\t1\n', b'frame\tmask\n0\t0\n1\t0\n'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                reel.input_changes(raw, len(self.lines))

    def test_native_and_controller_hashes_are_independently_checked(self):
        for channel in ('native', 'controller'):
            windows = copy.deepcopy(self.windows); windows[0]['framed_sha256'][channel] = 'f' * 64
            with self.subTest(channel=channel), self.assertRaisesRegex(ValueError, 'framed hash'):
                self.inspect(windows=windows)

    def test_schedule_full_channels_and_serialized_states_are_required(self):
        for change in ('gap', 'GPU', 'PCM', 'state'):
            windows = copy.deepcopy(self.windows)
            if change == 'gap': windows[0]['first_frame'] = 1
            elif change == 'state': windows[0]['complete_state_sha256'] = None
            else: windows[0]['payload_bytes']['GPURAM' if change == 'GPU' else 'PCM'] -= 1
            with self.subTest(change=change), self.assertRaises(ValueError):
                reel.validate_windows(windows, len(self.lines), len(self.lines))

    def test_bounded_lines_headers_truncation_and_trailing_data(self):
        for raw in (self.raw + b'\n', self.raw[:-1], self.header + b'x' * (reel.LINE_LIMIT + 1),
                    self.header + b'\xff\n', self.raw.replace(b'core_frame', b'extra\tcore_frame', 1)):
            with self.subTest(prefix=raw[:30]), self.assertRaises((ValueError, UnicodeError)):
                self.inspect(raw)

    def recording(self, folder):
        (folder / 'report.json').write_text(json.dumps(self.report), encoding='utf-8')
        (folder / 'card-store.json').write_text(json.dumps(self.store), encoding='utf-8')
        (folder / 'windows.jsonl').write_text('\n'.join(json.dumps(w) for w in self.windows) + '\n', encoding='utf-8')
        (folder / 'inputs.tsv').write_bytes(b'frame\tmask\n' + b''.join(f'{frame}\t{mask}\n'.encode() for frame, mask in self.changes))
        (folder / 'native.tsv.gz').write_bytes(gzip.compress(self.raw, mtime=0))
        for name in reel.IMAGES: (folder / name).write_bytes(image())

    def test_saved_recording_pair_compares_unmasked_buffers_states_cards_and_images(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name); self.recording(folder)
            left = reel.load_recording(folder)
        right = copy.deepcopy(left); right['report']['replayed_inputs'] = True
        self.assertTrue(reel.compare_data(left, right)['passed'])
        for group in ('windows', 'images', 'card_store', 'native', 'inputs_sha256'):
            changed = copy.deepcopy(right)
            if group == 'windows': changed[group][0]['framed_sha256']['GPURAM'] = 'f' * 64
            elif group == 'images': changed[group]['final.png']['RGB_sha256'] = 'f' * 64
            elif group == 'card_store': changed[group]['initial_SaveRAM_sha256'] = 'd' * 64
            elif group == 'native': changed[group]['journal_sha256'] = 'd' * 64
            else: changed[group] = 'd' * 64
            with self.subTest(group=group): self.assertFalse(reel.compare_data(left, changed)['passed'])

    def test_gzip_crc_stop_and_invalid_images_fail_closed(self):
        for failure in ('crc', 'STOP', 'image'):
            with tempfile.TemporaryDirectory() as name:
                folder = Path(name); self.recording(folder)
                if failure == 'STOP': (folder / 'STOP').touch()
                elif failure == 'image': (folder / 'final.png').write_bytes(b'not a PNG')
                else:
                    raw = bytearray((folder / 'native.tsv.gz').read_bytes()); raw[-8] ^= 1
                    (folder / 'native.tsv.gz').write_bytes(raw)
                with self.subTest(failure=failure), self.assertRaises((ValueError, OSError, EOFError)):
                    reel.load_recording(folder)

    def test_fixture_preserves_complete_card_outside_explicit_history_fields(self):
        source = bytes(install(blank_card()))
        card, metadata = prepare.construct_card(source)
        self.assertEqual(source, bytes(install(blank_card())))
        self.assertEqual(card[:prepare.PAYLOAD_OFFSET], source[:prepare.PAYLOAD_OFFSET])
        changed = {row['file_offset'] for row in metadata['changed_byte_allowlist']}
        self.assertEqual(changed, {index for index, (a, b) in enumerate(zip(source, card)) if a != b})
        self.assertEqual(struct.unpack_from('<4h', card, prepare.PAYLOAD_OFFSET + 0x18), prepare.CELLS)
        self.assertFalse(metadata['naturally_earned_history_claimed'])

    def test_fixture_refuses_unqualified_card_layout_magic_and_calendar(self):
        bad_magic = install(blank_card()); bad_magic[prepare.PAYLOAD_OFFSET] = 0
        next_year = install(blank_card()); struct.pack_into('<I', next_year, prepare.PAYLOAD_OFFSET + 4, 1)
        day_three = install(blank_card()); struct.pack_into('<I', day_three, prepare.PAYLOAD_OFFSET + 8, 2)
        for source in (blank_card(), install(blank_card(), block=3), bad_magic, next_year, day_three):
            with self.subTest(prefix=source[:2]), self.assertRaises(ValueError):
                prepare.construct_card(source)

    def test_fixture_CLI_writes_only_fresh_separate_outputs_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name); source = folder / 'source.card'; output = folder / 'fixture.card'; manifest = folder / 'fixture.json'
            raw = bytes(install(blank_card())); source.write_bytes(raw)
            with patch('builtins.print'):
                self.assertEqual(prepare.main([str(source), str(output), '--manifest', str(manifest)]), 0)
            self.assertEqual(source.read_bytes(), raw)
            self.assertEqual(output.read_bytes(), prepare.construct_card(raw)[0])
            with self.assertRaisesRegex(ValueError, 'separate and fresh'):
                prepare.main([str(source), str(output), '--manifest', str(manifest)])
            with self.assertRaisesRegex(ValueError, 'separate and fresh'):
                prepare.main([str(source), str(source), '--manifest', str(folder / 'other.json')])


if __name__ == '__main__':
    unittest.main()
