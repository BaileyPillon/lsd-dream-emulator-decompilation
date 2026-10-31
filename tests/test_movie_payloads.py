"""Synthetic full-buffer evidence checks, separate from native runtime parity."""
import copy
import hashlib
import io
import struct
import unittest

from tools import inspect_movie_payloads as movie


def varint(value):
    raw = bytearray()
    while value >= 128:
        raw.append((value & 127) | 128)
        value >>= 7
    raw.append(value)
    return bytes(raw)


def encode(events):
    previous = [[0] * 43 for _ in range(3)]
    result = bytearray(movie.HEADER)
    for event in events:
        tag = event['kind'] - 1
        result.append(tag)
        for i, key in enumerate(movie.FIELDS):
            value = event[key]
            delta = (value - previous[tag][i]) & 0xffffffff
            if delta >= 0x80000000:
                delta -= 0x100000000
            result.extend(varint(((delta << 1) ^ (delta >> 31)) & 0xffffffff))
            previous[tag][i] = value
        result.extend(bytes.fromhex(event['payload_sha256']))
    return bytes(result)


def fixture():
    command = 0x38000020
    rows, entries = [], []
    for number in (1, 2):
        frame = 21929 + (number - 1) * 4
        event = dict.fromkeys(movie.FIELDS, 0)
        event.update(frame=frame, kind=1, pc=0x80046568, timestamp=0xffffffff, sp=0x801fff00, ra=0x80045b5c,
            entry_frame=frame, entry_timestamp=0xffffffff, entry_sp=0x801fff00, entry_ra=0x80045b5c,
            a0=0x800c0400, a1=0x800d0000 + (number - 1) * 0x10000, a2=number,
            transfer_pc=0x80045b54, delay_pc=0x80045b58, transfer_word=0x0c01195a,
            source_address=0x800c0400, source_bytes=16, command_word=command,
            input_address=0x800c0400, output_address=0x800d0000 + (number - 1) * 0x10000,
            frame_id=number, header_address=0x800c0000, header_0=4, header_2=number, header_3=16,
            header_4=320 | (240 << 16), header_5=command, header_6=1 | (2 << 16), active_movie=0x800b0000,
            payload_sha256=str(number) * 64)
        entry = {key: event[key] for key in ('frame', 'pc', 'timestamp', 'sp', 'ra', 'a0', 'a1', 'a2', 'a3',
            'transfer_pc', 'delay_pc', 'transfer_word', 'delay_word', 'active_movie')}
        entry.update(sdk_header_base=0x800c0000, sdk_data_index=32, sdk_next_index=0)
        entries.append(entry)
        rows.append(event)
        returned = dict(event, kind=2, pc=event['ra'], data_offset=16, source_address=event['output_address'], source_bytes=132,
            return_jump_pc=0x800465b0, return_delay_pc=0x800465b4, return_jump_word=0x03e00008,
            payload_sha256=str(number + 2) * 64)
        rows.append(returned)
        if number == 1:
            submitted = dict(event, kind=3, frame=frame + 1, entry_frame=frame + 1, pc=0x80045f84,
                a0=event['output_address'], a1=2, a2=2, source_address=event['output_address'], source_bytes=132,
                ra=0x80045d78, entry_ra=0x80045d78, transfer_pc=0x80045d70, delay_pc=0x80045d74,
                transfer_word=0x0c0117e1, delay_word=0x34050002, payload_sha256=returned['payload_sha256'])
            rows.append(submitted)
            entries.append({key: submitted.get(key, value) for key, value in entry.items()})
    for ordinal, row in enumerate(rows, 1):
        row['ordinal'] = ordinal
    rows = list(movie.event_rows(io.BytesIO(encode(rows))))
    chain = hashlib.sha256()
    for row in rows:
        chain.update(struct.pack('<43I', *(row[key] for key in movie.FIELDS)))
        chain.update(bytes.fromhex(row['payload_sha256']))
    summary = dict(schema_version=1, protocol='full_movie_payload_sha256_v1', event_numeric_words=43,
        native_event_bytes=172, observer_enabled=True, arm_frame=21884, frame_event_limit=16,
        frame_payload_limit_bytes=1024**2, native_errors=0, native_overflow=0, pending_VLC_returns=0,
        pending_RLE_buffers_without_MDEC_input=1, full_encoded_input_at_VLC_entry=True,
        full_RLE_at_actual_VLC_return=True, full_RLE_at_MDEC_input_entry=True,
        original_CPU_source_modified=False, game_MainRAM_or_instructions_written=False,
        individual_frame_GPU_presentation_accepted=False, entries=5, counts=[2, 2, 1], accepted_callbacks=2,
        raw_entry_bytes=sum(row['wire_bytes'] for row in rows), complete_native_payload_bytes_hashed=428,
        first_entry_frame=21929, last_entry_frame=21933, numeric_and_full_payload_hash_chain_sha256=chain.hexdigest())
    frames = {number: dict(encoded_bytes=16, first_word=command, width=320, height=240, quantization=1, version=2)
        for number in (1, 2)}
    index = dict(movies={'/synthetic.STR': dict(frame_count=2, frames=frames)},
        full_lookup={(number, str(number) * 64): {'/synthetic.STR'} for number in (1, 2)})
    return rows, summary, index, entries


class FullMoviePayloadTests(unittest.TestCase):
    def inspect(self, rows=None, summary=None, index=None, entries=None):
        values = fixture()
        return movie.inspect_events(iter(values[0] if rows is None else rows), values[1] if summary is None else summary,
            values[2] if index is None else index, values[3] if entries is None else entries)

    def test_full_buffer_entry_return_submission_and_final_pending_output(self):
        result = self.inspect()
        self.assertEqual(result['counts'], [2, 2, 1])
        self.assertEqual(result['complete_payload_bytes_hashed'], 428)
        self.assertEqual(result['final_completed_RLE_without_MDEC_input'][0]['frame_id'], 2)
        self.assertFalse(result['individual_frame_GPU_presentation_accepted'])

    def test_wire_format_retains_all_numeric_bits_and_complete_payload_hashes(self):
        rows = fixture()[0]
        decoded = list(movie.event_rows(io.BytesIO(encode(rows))))
        self.assertEqual(decoded, rows)
        self.assertEqual(decoded[0]['timestamp'], 0xffffffff)

    def test_truncated_overflowing_or_wrong_kind_wire_data_is_rejected(self):
        raw = encode(fixture()[0])
        for bad in (b'bad', movie.HEADER + b'\x03', raw[:-1], movie.HEADER + b'\x00\x80\x00',
                movie.HEADER + b'\x00\xff\xff\xff\xff\x10'):
            with self.subTest(bad=bad[:12]), self.assertRaises(ValueError):
                list(movie.event_rows(io.BytesIO(bad)))
        changed = bytearray(raw)
        changed[8] = 1
        with self.assertRaisesRegex(ValueError, 'tag/kind'):
            list(movie.event_rows(io.BytesIO(changed)))

    def test_actual_entry_context_and_native_byte_extents_are_required(self):
        for position, key, value in ((0, 'ordinal', 2), (0, 'a0', 0x800c0404), (0, 'header_address', 0),
                (0, 'source_bytes', 20), (0, 'data_offset', 4), (0, 'header_2', 2), (0, 'header_4', 0),
                (0, 'header_6', 0), (0, 'status', 1), (2, 'transfer_word', 0)):
            rows = fixture()[0]
            rows[position][key] = value
            with self.subTest(position=position, key=key), self.assertRaises(ValueError):
                self.inspect(rows=rows)

    def test_return_requires_its_complete_original_input_and_epilogue(self):
        for key, value in (('entry_sp', 0), ('entry_ra', 0), ('return_jump_pc', 0), ('return_delay_word', 1),
                ('source_address', 0x800d0004), ('source_bytes', 128), ('header_3', 20)):
            rows = fixture()[0]
            rows[1][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.inspect(rows=rows)

    def test_complete_MDEC_input_difference_beyond_old_prefix_is_detected(self):
        rows = fixture()[0]
        rows[2]['payload_sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'beyond the old prefix'):
            self.inspect(rows=rows)

    def test_missing_source_full_hash_and_changed_cached_header_are_detected(self):
        index = fixture()[2]
        index['full_lookup'][(1, '1' * 64)] = set()
        with self.assertRaises(ValueError):
            self.inspect(index=index)
        rows = fixture()[0]
        rows[2]['header_0'] = 99
        with self.assertRaisesRegex(ValueError, 'provenance'):
            self.inspect(rows=rows)

    def test_ambiguous_full_source_hash_is_not_misrepresented_as_unique(self):
        index = fixture()[2]
        index['movies']['/also-synthetic.STR'] = copy.deepcopy(index['movies']['/synthetic.STR'])
        for key in index['full_lookup']:
            index['full_lookup'][key].add('/also-synthetic.STR')
        result = self.inspect(index=index)
        self.assertEqual(result['segments'][0]['candidate_paths'], ['/also-synthetic.STR', '/synthetic.STR'])

    def test_summary_counts_hash_chain_and_unmodified_game_scope_are_checked(self):
        for key, value in (('native_errors', 1), ('entries', 6), ('raw_entry_bytes', 0),
                ('complete_native_payload_bytes_hashed', 1), ('pending_VLC_returns', 1),
                ('numeric_and_full_payload_hash_chain_sha256', '0' * 64), ('game_MainRAM_or_instructions_written', True)):
            summary = fixture()[1]
            summary[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.inspect(summary=summary)
