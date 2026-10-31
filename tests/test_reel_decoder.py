"""Synthetic decoder-evidence controls; these tests are not gameplay evidence."""
import copy
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools import inspect_reel_decoder as decoder


def varint(value):
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def encode(events):
    previous = [[0] * len(decoder.NAMES) for _ in decoder.TARGETS]
    result = bytearray(decoder.HEADER)
    for event in events:
        tag = decoder.TARGETS.index(event['pc'])
        result.append(tag)
        for number, key in enumerate(decoder.NAMES):
            value = event[key]
            delta = (value - previous[tag][number]) & 0xffffffff
            if delta >= 0x80000000:
                delta -= 0x100000000
            result.extend(varint(((delta << 1) ^ (delta >> 31)) & 0xffffffff))
            previous[tag][number] = value
        if tag == 1:
            result.extend(bytes.fromhex(event['encoded_prefix_44_sha256']))
    return bytes(result)


def fixture():
    targets = json.loads((decoder.REPO / 'research/headless/reel-decoder-targets.json').read_bytes())
    rows = []
    for ordinal, tag in enumerate((0, 1, 2, 0, 1), 1):
        pc = decoder.TARGETS[tag]
        spec = next(row for row in targets['targets'] if int(row['address'], 16) == pc)
        caller = next(row for row in targets['original_direct_call_sites'] if int(row['target'], 16) == pc)
        event = dict.fromkeys(decoder.NAMES, 0)
        event.update(frame=21929 + ordinal, ordinal=ordinal, pc=pc,
            a0=(0x80012000, 0x80013000, 0x80014000)[tag],
            a1=(0x80013000, 0x80014000, 2)[tag], a2=1 if ordinal < 4 else 2,
            ra=int(caller['return_address'], 16), sp=0x801fff00, timestamp=0xffffffff,
            instruction=spec['entry_word'], transfer_pc=int(caller['pc'], 16),
            delay_pc=int(caller['pc'], 16) + 4, transfer_word=int(caller['instruction'], 16),
            delay_word=int(caller['delay_word'], 16), active_movie=0x80015000,
            function_bytes=spec['bytes'], first_word=0x800817e0 if tag == 0 else 0x38000020,
            encoded_prefix_44_sha256='ab' * 32 if tag == 1 else None)
        rows.append(event)
    raw = encode(rows)
    summary = dict(schema_version=2, protocol='delta_varint_v2', observer_enabled=True,
        arm_frame=21884, event_numeric_words=21, a0_prefix_bytes=44,
        original_function_bodies_checked_on_every_entry=True, original_CPU_source_modified=False,
        game_MainRAM_or_instructions_written=False, full_encoded_or_RLE_payload_hashes_captured=False,
        entries=5, counts={str(pc): count for pc, count in zip(decoder.TARGETS, (2, 2, 1))},
        raw_entry_bytes=len(raw) - len(decoder.HEADER), first_entry_frame=21930, last_entry_frame=21934)
    index = dict(movies={'/synthetic.STR': dict(frame_count=10)},
        lookup={(number, 'ab' * 32): {'/synthetic.STR'} for number in (1, 2)},
        prefix_words={(number, 'ab' * 32): 0x38000020 for number in (1, 2)})
    return rows, summary, index, targets


class WireTests(unittest.TestCase):
    def test_per_target_signed_deltas_wraparound_and_prefixes_are_lossless(self):
        rows, _, _, _ = fixture()
        for i, event in enumerate(rows):
            event['a3'] = 0xffffffff if i < 3 else 0
            event['timestamp'] = 0x80000000 if i < 3 else 0x7fffffff
        result = list(decoder.entry_rows(io.BytesIO(encode(rows))))
        for source, observed in zip(rows, result):
            self.assertEqual({key: observed[key] for key in source}, source)

    def test_reject_wrong_header_tag_and_truncated_numeric_or_fingerprint(self):
        raw = encode(fixture()[0])
        for bad in (b'wrong', decoder.HEADER + b'\x03', decoder.HEADER + b'\x00\x80', raw[:-1]):
            with self.subTest(bad=bad[:12]), self.assertRaises(ValueError):
                list(decoder.entry_rows(io.BytesIO(bad)))

    def test_reject_noncanonical_and_overflowing_varints(self):
        for bad in (b'\x80\x00', b'\xff\xff\xff\xff\x10', b'\x80' * 5):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                decoder.read_varint(io.BytesIO(bad))

    def test_reject_tag_pc_conflict(self):
        raw = bytearray(encode(fixture()[0]))
        raw[len(decoder.HEADER)] = 2
        with self.assertRaisesRegex(ValueError, 'tag/PC'):
            list(decoder.entry_rows(io.BytesIO(raw)))


class NativeEvidenceTests(unittest.TestCase):
    def inspect(self, rows=None, summary=None, index=None):
        baseline, header, corpus, targets = fixture()
        rows = baseline if rows is None else rows
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / 'decoder-entries.bin.gz').write_bytes(gzip.compress(encode(rows), mtime=0))
            (folder / 'decoder-trace-summary.json').write_text(json.dumps(header if summary is None else summary), encoding='utf-8')
            return decoder.inspect(folder, corpus if index is None else index, targets)

    def test_callback_vlc_buffer_and_mdec_input_associations(self):
        result = self.inspect()
        self.assertEqual((result['stream_VLC_pairs'], result['MDEC_submissions']), (2, 1))
        self.assertEqual(result['segments'][0]['candidate_paths'], ['/synthetic.STR'])
        self.assertEqual(result['unsubmitted_decoded_buffers'][0]['number'], 2)
        self.assertFalse(result['full_encoded_or_RLE_payload_hashes_captured'])
        self.assertFalse(result['complete_frame_presentation_acceptance'])

    def test_reject_changed_call_site_body_stack_schedule_and_stream_context(self):
        for position, key, value in ((0, 'ordinal', 2), (0, 'frame', 1), (0, 'instruction', 0),
                (0, 'function_bytes', 4), (0, 'transfer_word', 0), (0, 'delay_word', 1),
                (0, 'ra', 0), (0, 'delay_pc', 0), (0, 'sp', 0), (0, 'a0', 1),
                (0, 'active_movie', 0), (0, 'first_word', 0), (3, 'a2', 0)):
            rows = fixture()[0]
            rows[position][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.inspect(rows=rows)

    def test_reject_unpaired_or_changed_encoded_and_decoded_buffers(self):
        for position, key, value in ((1, 'a0', 0x80016000), (1, 'first_word', 0),
                (1, 'encoded_prefix_44_sha256', '00' * 32), (2, 'a0', 0x80016000),
                (2, 'a1', 1), (2, 'first_word', 0), (4, 'a1', 0x80014000)):
            rows = fixture()[0]
            rows[position][key] = value
            if position == 4:
                rows.pop(2)  # Simulate reuse without the intervening MDEC input call.
                for i, event in enumerate(rows, 1):
                    event['ordinal'] = i
            with self.subTest(position=position, key=key), self.assertRaises(ValueError):
                self.inspect(rows=rows)

    def test_reject_invalid_host_scope_counts_and_noncanonical_source_identity(self):
        for key, value in (('schema_version', 1), ('entries', 6), ('raw_entry_bytes', 0),
                ('observer_enabled', False), ('game_MainRAM_or_instructions_written', True),
                ('original_function_bodies_checked_on_every_entry', False)):
            summary = fixture()[1]
            summary[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.inspect(summary=summary)
        index = fixture()[2]
        index['lookup'][(2, 'ab' * 32)] = set()
        with self.assertRaises(ValueError):
            self.inspect(index=index)

    def test_reel_requires_twenty_unique_ordered_sources_and_final_pending_buffer(self):
        paths = [f'/CDI/FILM/SPDAY{day:02d}{variant}.STR' for day in range(1, 11) for variant in 'AB']
        index = dict(movies={path: dict(frame_count=2 if i < 19 else 10) for i, path in enumerate(paths)})
        baseline = dict(callback_segments=20, segments=[dict(candidate_paths=[path],
            all_observed_IDs_contiguous_from_one=True, callback_count=2, VLC_count=2,
            last_ID=2, MDEC_submissions=2 if i < 19 else 1) for i, path in enumerate(paths)],
            unsubmitted_decoded_buffers=[dict(segment=19, number=2)])
        decoder.validate_complete_reel(baseline, index)
        for change in (lambda data: data['segments'][0].update(candidate_paths=paths[:2]),
                lambda data: data['segments'][0].update(MDEC_submissions=1),
                lambda data: data['segments'][-1].update(MDEC_submissions=2),
                lambda data: data.update(unsubmitted_decoded_buffers=[])):
            edited = copy.deepcopy(baseline)
            change(edited)
            with self.assertRaises(ValueError):
                decoder.validate_complete_reel(edited, index)

    def test_stock_output_equality_keeps_unmasked_state_differences_separate(self):
        row = dict.fromkeys(('first_frame', 'last_frame', 'frames', 'PCM_sample_frames',
            'payload_bytes', 'framed_sha256', 'final_MainRAM_sha256', 'final_GPURAM_sha256',
            'final_RGB_with_dimensions_sha256', 'complete_state_sha256'), 'unchanged')
        stock = dict(windows=[row], native={}, images={}, inputs_sha256='a', dimensions={}, card_store={})
        observed = copy.deepcopy(stock)
        observed['windows'][0]['complete_state_sha256'] = 'different-core-body'
        result = decoder.stock_comparison(stock, observed)
        self.assertTrue(result['all_complete_output_windows_equal'])
        self.assertFalse(result['complete_serialized_state_hashes_equal'])
        self.assertEqual(result['complete_serialized_state_differing_windows'], [0])
        observed['windows'][0]['framed_sha256'] = 'changed-output'
        self.assertFalse(decoder.stock_comparison(stock, observed)['all_complete_output_windows_equal'])


if __name__ == '__main__':
    unittest.main()
