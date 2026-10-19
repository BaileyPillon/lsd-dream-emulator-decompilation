"""Owned protocol/sector fixtures; real canonical traces are qualified separately."""
from copy import deepcopy
import io
import json
from pathlib import Path
import struct
import unittest

from tests.test_dispatch_returns import disc_fixture, jal
from tests.test_npc_catalogue import executable
from tools.inspect_sdk_reads import FIELDS
from tools import verify_blocking_cd_retry as tool
from tools.dispatch_trace import validate_program

ROOT = Path(__file__).resolve().parents[1]

def fixture():
    body = bytearray(0x400)
    helper_pc, helper_sp, destination = 0x80010100, 0x801ffe00, 0x80040000
    targets = [dict(pc=0x80010200 + kind*32, bytes=32, kind=kind) for kind in (1, 2, 3, 4)]
    by_kind = {r['kind']: r for r in targets}
    calls = {3: helper_pc+16, 4: helper_pc+24, 1: helper_pc+32, 2: helper_pc+40}
    struct.pack_into('<I', body, 0x100, 0x27bdffd8)  # Owned 40-byte stack-frame fixture.
    struct.pack_into('<III', body, 0x104, 0x00808021, 0x26050018, 0x00003021)
    for kind, pc in calls.items(): struct.pack_into('<I', body, pc-0x80010000, jal(by_kind[kind]['pc']))
    struct.pack_into('<II', body, 0x130, 0x03e00008, 0x27bd0028)
    settings = dict(helper_pc=helper_pc, helper_bytes=56, request_call=calls[1], poll_call=calls[2], sdk_targets=targets)
    raw_disc = bytes(disc_fixture(4096))
    sectors = b''.join(raw_disc[lba*2352+24:lba*2352+2072] for lba in (20, 21))
    failed_snapshot = sectors[:2048] + b'Z' * 2048
    payload = failed_snapshot + sectors
    loc = int.from_bytes(raw_disc[20*2352+12:20*2352+15], 'little')
    rows, active = [], 0
    events = ((3, 1, 8), (4, 2, 8), (1, 1, 9), (2, 0xffffffff, 10),
              (3, 0, 11), (4, 5, 11), (3, 1, 21), (4, 2, 21), (1, 1, 21), (2, 0, 30))
    for index, (kind, value, frame) in enumerate(events, 1):
        row = dict.fromkeys(FIELDS, 0)
        row.update(entry_id=index, kind=kind, entry_frame=frame, frame=frame, timestamp=frame*100,
                   entry_sequence_low=index*10, sequence_low=index*10+5,
                   entry_pc=by_kind[kind]['pc'], entry_jump_pc=calls[kind], entry_ra=calls[kind]+8,
                   entry_sp=helper_sp-40, v0=value)
        if kind == 3:
            row.update(a0=2, a1=0x80050018, a2=0, arg_readable=1, arg_word_0=loc)
        elif kind == 1:
            active = index
            row.update(a0=2, a1=destination, a2=0x80)
        if active:
            row.update(transfer_id=active, transfer_sectors=2, transfer_mode=0x80,
                       sdk_word_1=2, sdk_word_2=destination, sdk_word_4=0x80, sdk_word_5=512)
        if kind == 2:
            success = value == 0
            row.update(buffer_status=1 if success else 5, buffer_address=destination, buffer_bytes=4096,
                       buffer_offset=4096 if success else 0, sdk_word_3=destination+(4096 if success else 2048))
            active = 0
        rows.append(row)
    helper = dict(entry_id=2, parent_id=1, kind=2, entry_frame=8, frame=30,
                  entry_sequence_low=1, entry_sequence_high=0, sequence_low=110, sequence_high=0,
                  entry_sp=helper_sp, a0=0x80050000, a1=destination, a2=4096, read_request_entries=2,
                  read_poll_entries=2, read_poll_returns=2, request_sequence_low=90, request_sequence_high=0,
                  poll_sequence_low=105, poll_sequence_high=0, last_poll_frame=30, last_poll_timestamp=3000,
                  last_poll_value=0, buffer_offset=0, buffer_bytes=4096)
    parent = dict(entry_id=1, kind=1, buffer_offset=4096, buffer_bytes=4096)
    return dict(image=executable(body), settings=settings, records=rows, payload=payload, disc=raw_disc,
                returns=[parent, helper], return_payload=sectors*2,
                summary=dict(completions=1, failed_transfers=1, unassociated_polls=0, overlapping_requests=0))

def qualify(f):
    transfers = tool.verify_transfers(f['records'], f['payload'], f['summary'], io.BytesIO(f['disc']))
    linked = tool.link_helpers(f['returns'], f['return_payload'], f['records'], f['payload'], transfers,
                               f['settings'], f['image'], 10, 20)
    return transfers, linked

class BlockingRetryTests(unittest.TestCase):
    def test_observed_failure_seek_rejection_retry_and_complete_return(self):
        transfers, linked = qualify(fixture())
        self.assertEqual([r['success'] for r in transfers['endings']], [False, True])
        self.assertEqual([r['written_prefix_bytes'] for r in transfers['endings']], [2048, 4096])
        self.assertEqual(linked['original_helper_frame_bytes'], 40)
        self.assertEqual(linked['helpers'][0]['request_count'], 2)
        self.assertEqual(len(linked['error_to_setloc_edges']), 2)
        self.assertEqual(len(linked['rejected_setloc_to_sync_errors']), 1)
        self.assertFalse(linked['failed_buffer_tails_accepted'])
        self.assertFalse(linked['status_words_treated_as_byte_counts'])

    def test_unwritten_failed_tail_is_not_accepted_as_disc_data(self):
        first = fixture(); second = deepcopy(first)
        changed = bytearray(second['payload']); changed[2048] ^= 1; second['payload'] = bytes(changed)
        before, _ = qualify(first); after, _ = qualify(second)
        self.assertEqual(before['endings'][0]['verified_prefix_sha256'], after['endings'][0]['verified_prefix_sha256'])
        self.assertNotEqual(before['endings'][0]['full_snapshot_sha256'], after['endings'][0]['full_snapshot_sha256'])

    def test_changed_failed_prefix_or_successful_data_is_rejected(self):
        for offset in (0, 4096):
            f = fixture(); data = bytearray(f['payload']); data[offset] ^= 1; f['payload'] = bytes(data)
            with self.subTest(offset=offset), self.assertRaises(ValueError): qualify(f)

    def test_failed_snapshot_cannot_be_labeled_successful(self):
        f = fixture(); f['records'][3]['buffer_status'] = 1
        with self.assertRaises(ValueError): qualify(f)

    def test_nonsector_write_cursor_is_rejected(self):
        f = fixture(); f['records'][3]['sdk_word_3'] += 1
        with self.assertRaises(ValueError): qualify(f)

    def test_transfer_identity_and_native_totals_are_checked(self):
        for target, field, value in (('record', 'transfer_id', 999), ('summary', 'failed_transfers', 0)):
            f = fixture()
            (f['records'][3] if target == 'record' else f['summary'])[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): qualify(f)

    def test_missing_retry_seek_is_rejected(self):
        f = fixture(); f['records'].pop(4)
        with self.assertRaisesRegex(ValueError, 'original Setloc'): qualify(f)

    def test_rejected_setloc_must_reach_observed_sync_error(self):
        f = fixture(); f['records'][5]['v0'] = 2
        with self.assertRaisesRegex(ValueError, 'Rejected helper Setloc'): qualify(f)

    def test_requestless_seek_cannot_change_position(self):
        f = fixture(); f['records'][4]['arg_word_0'] ^= 1
        with self.assertRaises(ValueError): qualify(f)

    def test_seek_argument_pointer_is_tied_to_the_original_receiver(self):
        f = fixture(); f['records'][4]['a1'] += 4
        with self.assertRaisesRegex(ValueError, 'Setloc invocation'): qualify(f)

    def test_request_count_stack_and_arguments_are_linked(self):
        for target, field, value in (('helper', 'read_request_entries', 1), ('request', 'entry_sp', 0x801ffd00),
                                     ('request', 'a1', 0x80045000)):
            f = fixture()
            (f['returns'][1] if target == 'helper' else f['records'][8])[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): qualify(f)

    def test_original_parent_and_helper_return_buffers_must_match(self):
        f = fixture(); data = bytearray(f['return_payload']); data[4096] ^= 1; f['return_payload'] = bytes(data)
        with self.assertRaises(ValueError): qualify(f)

    def test_final_poll_identity_is_checked(self):
        f = fixture(); f['returns'][1]['poll_sequence_low'] += 1
        with self.assertRaises(ValueError): qualify(f)

    def test_recovery_must_complete_after_the_declared_close(self):
        f = fixture(); f['records'][-1]['frame'] = 19; f['returns'][1]['last_poll_frame'] = 19
        with self.assertRaises(ValueError): qualify(f)

    def test_direct_call_sites_are_derived_from_complete_helper_bytes(self):
        f = fixture(); calls, frame = tool.helper_calls(f['image'], f['settings'])
        self.assertEqual(frame, 40); self.assertEqual(calls[1], f['settings']['request_call'])
        changed = deepcopy(f['settings']); changed['request_call'] += 4
        with self.assertRaises(ValueError): tool.helper_calls(f['image'], changed)

    def test_duplicate_helper_sdk_call_is_rejected(self):
        f = fixture(); data = bytearray(f['image'])
        from tools.psx_image import executable_offset
        struct.pack_into('<I', data, executable_offset(data, f['settings']['poll_call'], 4), jal(f['settings']['sdk_targets'][0]['pc']))
        with self.assertRaises(ValueError): tool.helper_calls(bytes(data), f['settings'])

    def test_published_program_declares_only_the_bounded_tray_pair(self):
        program = validate_program(json.loads((ROOT / 'research/headless/blocking-cd-retry-route.json').read_text()))
        self.assertEqual(tool.tray_window(program, 2000), (1020, 1070))
        changed = deepcopy(program); changed['segments'][0]['pressed'].append('Reset')
        with self.assertRaises(ValueError): tool.tray_window(changed, 2000)

    def test_repeated_tray_inputs_or_other_disc_index_are_rejected(self):
        program = json.loads((ROOT / 'research/headless/blocking-cd-retry-route.json').read_text())
        for kind in ('repeat', 'disc'):
            changed = deepcopy(program)
            if kind == 'repeat':
                row = next(r for r in changed['segments'] if 'Open Tray' in r['pressed']); row['until'] += 1
            else: changed['controller']['axes']['Disk Index'] = 1
            with self.subTest(kind=kind), self.assertRaises(ValueError): tool.tray_window(changed, 2000)

if __name__ == '__main__': unittest.main()
