"""Owned disc/controller fixtures for failure accounting and reset boundaries."""
from copy import deepcopy
import io
import json
from pathlib import Path
import struct
import unittest

from tools import inspect_cd_recovery as tool
from tools import inspect_sdk_reads as sdk
from tools.inspect_file_heap import analyze_file_heap
from tests.test_dispatch_returns import disc_fixture
from tests.test_file_heap import fixture as heap_fixture


def transfers_fixture():
    disc=bytes(disc_fixture(4096));sector=disc[20*2352+24:20*2352+2072]
    payload=sector+b'X'*2048+sector
    records=[];destination=0x80040000
    def add(kind,frame,**fields):
        index=len(records)+1;row=dict.fromkeys(sdk.FIELDS,0)
        row.update(entry_id=index,kind=kind,frame=frame,entry_frame=frame,
                   entry_sequence_low=index*10,sequence_low=index*10+5)
        row.update(fields);records.append(row);return row
    seek=dict(a0=2,a1=0x80030000,arg_readable=1,v0=1,
        arg_word_0=int.from_bytes(disc[20*2352+12:20*2352+15],'little'))
    add(3,1000,**seek)
    for kind,frame,count,id_,offset,status,result in ((1,2405,2,2,0,0,1),
            (2,2420,2,2,0,5,0xffffffff),(1,3002,1,5,0,0,1),(2,3003,1,5,4096,1,0)):
        if frame==3002:add(3,3001,**seek)
        row=add(kind,frame,transfer_id=id_,transfer_sectors=count,transfer_mode=128,
            sdk_word_1=count,sdk_word_2=destination,sdk_word_3=destination+(2048 if kind==2 else 0),
            sdk_word_4=128,sdk_word_5=512,v0=result)
        if kind==1:row.update(a0=count,a1=destination,a2=128,entry_jump_pc=0x8002866C)
        else:row.update(buffer_status=status,buffer_address=destination,buffer_bytes=count*2048,buffer_offset=offset)
    return dict(records=records,payload=payload,disc=disc,
        summary=dict(completions=1,failed_transfers=1,unassociated_polls=0,overlapping_requests=0),
        config=dict(open_frame=2420,close_frame=2540,reset_frame=3000))


def ending_fixture(sync_errors=1):
    records=[];states={}
    def add(kind,call=0,a0=0,v0=0,state=None):
        index=len(records)+1;row=dict(entry_id=index,kind=kind,entry_jump_pc=call,a0=a0,v0=v0,
            entry_sequence_low=index*10,entry_sequence_high=0,sequence_low=index*10+5,sequence_high=0,
            frame=2420+index,entry_frame=2420+index)
        records.append(row)
        if state is not None:
            before=(1,3,state,1,0,0,17,18,19,20)
            after=(0,0,0,0,1,0,17,18,19,20) if kind==12 else (1,3,a0,1,0,0,17,18,19,20)
            states[index]=dict(before=before,after=after)
        return row
    fail=add(2,v0=0xffffffff);add(11,0x800286B4);add(13,0x800286C0,1,state=8)
    for n in range(sync_errors+1):
        add(3,0x800285E4,2,1);add(13,0x800286C0,2,state=1)
        add(4,0x80028600,1,5 if n<sync_errors else 2)
        if n<sync_errors:add(13,0x800286C0,1,state=2)
    add(12,0x800286A4,state=2)
    return records,states,[dict(request_id=77,terminal_id=fail['entry_id'])]


class CdRecoveryTests(unittest.TestCase):
    def setUp(self):self.f=transfers_fixture()
    def verify(self):
        f=self.f
        return tool.verify_cd_transfers(f['records'],f['payload'],f['summary'],f['config'],io.BytesIO(f['disc']))

    def test_partial_failed_RAM_is_not_counted_as_a_complete_transfer(self):
        report,success,failed=self.verify()
        self.assertEqual((report['successful_transfers'],report['failed_transfers']),(1,1))
        self.assertEqual((report['successful_complete_RAM_bytes'],report['failed_snapshot_bytes'],
                          report['failed_verified_prefix_bytes']),(2048,4096,2048))
        self.assertEqual((failed[0]['epoch'],success[0]['epoch']),(0,1))
        self.assertNotIn('completion_id',failed[0])
        self.assertFalse(report['failed_buffers_are_successful_transfers'])

    def test_failed_tail_is_retained_as_unqualified_RAM(self):
        baseline=self.verify()[0];data=bytearray(self.f['payload']);data[3000]^=1;self.f['payload']=bytes(data)
        altered=self.verify()[0]
        self.assertNotEqual(baseline['failed'][0]['full_snapshot_sha256'],altered['failed'][0]['full_snapshot_sha256'])
        self.assertEqual(baseline['failed'][0]['verified_prefix_sha256'],altered['failed'][0]['verified_prefix_sha256'])
        self.assertFalse(altered['failed_buffer_tails_accepted'])

    def test_wrong_failed_written_prefix_is_rejected(self):
        data=bytearray(self.f['payload']);data[0]^=1;self.f['payload']=bytes(data)
        with self.assertRaisesRegex(ValueError,'RAM prefix'):self.verify()

    def test_failure_cannot_borrow_success_status_or_completion_count(self):
        self.f['records'][2]['buffer_status']=1
        with self.assertRaisesRegex(ValueError,'confused'):self.verify()
        self.f=transfers_fixture();self.f['summary']['completions']=2
        with self.assertRaisesRegex(ValueError,'totals'):self.verify()

    def test_partial_write_cursor_must_be_sector_aligned_and_inside_request(self):
        for written in (-2048,1,6144):
            self.f=transfers_fixture();self.f['records'][2]['sdk_word_3']=0x80040000+written
            with self.assertRaisesRegex(ValueError,'cursor'):self.verify()

    def test_post_reset_read_requires_a_new_observed_setloc(self):
        self.f['records'][3]['v0']=0
        with self.assertRaisesRegex(ValueError,'logical position'):self.verify()

    def test_pre_reset_failure_cannot_be_moved_past_controller_reset(self):
        self.f['records'][2]['entry_frame']=self.f['records'][2]['frame']=3000
        with self.assertRaisesRegex(ValueError,'crosses'):self.verify()

    def test_no_tracked_native_call_may_straddle_controller_reset(self):
        self.f['records'][2]['frame']=3000
        with self.assertRaisesRegex(ValueError,'straddles'):self.verify()

    def test_incomplete_failed_RAM_or_wrong_backend_state_is_rejected(self):
        for key in ('buffer_bytes','buffer_address','sdk_word_1','sdk_word_2','sdk_word_5','transfer_id'):
            self.f=transfers_fixture();self.f['records'][2][key]^=4
            with self.assertRaises(ValueError):self.verify()

    def test_failed_snapshot_may_not_be_truncated(self):
        self.f['payload']=self.f['payload'][:4095]
        with self.assertRaisesRegex(ValueError,'incomplete'):self.verify()

    def test_success_after_reset_still_requires_every_requested_sector(self):
        self.f['records'][-1]['sdk_word_3']-=2048
        with self.assertRaisesRegex(ValueError,'complete write cursor'):self.verify()

    def test_success_only_verifier_still_rejects_actual_failed_reads(self):
        with self.assertRaises(ValueError):
            sdk.verify_transfers(self.f['records'],self.f['payload'],self.f['summary'],io.BytesIO(self.f['disc']))

    def test_driver_snapshots_require_tagged_sparse_word_vectors_and_exact_effects(self):
        before=[1,3,8,1,0,42,17,18,19,20];after=before[:];after[2]=1;after[5]=0
        row=dict(entry_id=1,kind=13,a0=1,buffer_status=9,buffer_bytes=80,
            buffer_address=tool.DRIVER_GLOBALS[0][1],buffer_offset=0)
        data=struct.pack('<20I',*(before+after))
        proof,_=tool.validate_driver_snapshots([row],data)
        self.assertEqual(proof['state_setter_transitions'],{'8->1':1})
        for key in ('buffer_status','buffer_address','buffer_bytes'):
            wrong=dict(row);wrong[key]^=4
            with self.assertRaisesRegex(ValueError,'word vector'):tool.validate_driver_snapshots([wrong],data)
        for index in (0,1,3,4,6,7,8,9):
            wrong=after[:];wrong[index]^=1
            with self.assertRaisesRegex(ValueError,'wrong words'):
                tool.validate_driver_snapshots([row],struct.pack('<20I',*(before+wrong)))

    def test_driver_end_clears_busy_and_state_and_preserves_request_context(self):
        before=[1,3,2,1,0,8,17,18,19,20];after=[0,0,0,0,1,0,17,18,19,20]
        row=dict(entry_id=1,kind=12,buffer_status=9,buffer_bytes=80,
            buffer_address=tool.DRIVER_GLOBALS[0][1],buffer_offset=0)
        tool.validate_driver_snapshots([row],struct.pack('<20I',*(before+after)))
        for index in range(10):
            wrong=after[:];wrong[index]^=1
            with self.assertRaisesRegex(ValueError,'wrong words'):
                tool.validate_driver_snapshots([row],struct.pack('<20I',*(before+wrong)))
        with self.assertRaisesRegex(ValueError,'Truncated'):
            tool.validate_driver_snapshots([row],struct.pack('<19I',*(before+after[:-1])))

    def test_repeated_reseek_errors_are_distinct_from_reissued_sector_reads(self):
        records,states,failed=ending_fixture(sync_errors=3)
        report=tool.qualify_error_endings(records,states,failed,3000)
        self.assertEqual(report['endings'][0]['accepted_reseek_calls'],4)
        self.assertEqual(report['endings'][0]['reseek_sync_errors'],3)
        self.assertEqual(report['endings'][0]['SDK_reads_reissued_before_driver_end'],0)

    def test_invented_SDK_retry_before_driver_end_is_rejected(self):
        records,states,failed=ending_fixture()
        records[3]['kind']=1
        with self.assertRaisesRegex(ValueError,'reissues'):tool.qualify_error_endings(records,states,failed,3000)

    def test_missing_flush_or_wrong_original_call_site_is_rejected(self):
        for index in (1,2,3,4,5,-1):
            records,states,failed=ending_fixture();records[index]['entry_jump_pc']^=4
            with self.assertRaisesRegex(ValueError,'failed-read'):tool.qualify_error_endings(records,states,failed,3000)

    def test_state_loop_cannot_skip_its_error_transition(self):
        records,states,failed=ending_fixture();records[6]['a0']=2
        with self.assertRaisesRegex(ValueError,'path disagrees'):tool.qualify_error_endings(records,states,failed,3000)

    def test_a_new_game_driver_end_cannot_complete_a_pre_reset_request(self):
        records,states,failed=ending_fixture();records[-1]['entry_frame']=records[-1]['frame']=3001
        with self.assertRaisesRegex(ValueError,'completion transition'):
            tool.qualify_error_endings(records,states,failed,3000)

    def test_reset_censored_heap_does_not_claim_queued_read_lifetime_credit(self):
        fixture=heap_fixture();fixture['records']=[row for row in fixture['records'] if row['kind']!=1]
        report=analyze_file_heap(**fixture,check_read_lifetimes=False)
        self.assertEqual(report['successful_allocations'],2)
        self.assertEqual(report['matched_frees'],2)
        self.assertEqual(report['queued_Read_lifetime_windows_qualified'],0)
        self.assertFalse(report['queued_Read_lifetimes_checked'])

    def test_skipping_pre_reset_read_linking_does_not_skip_real_heap_contracts(self):
        fixture=heap_fixture();fixture['records'][0]['buffer_status']=0
        with self.assertRaisesRegex(ValueError,'snapshot'):analyze_file_heap(**fixture,check_read_lifetimes=False)

    def test_controller_program_names_its_only_actual_tray_and_reset_inputs(self):
        program=json.loads((Path(__file__).resolve().parents[1]/'research/headless/file-driver-cd-reset-route.json').read_bytes())
        self.assertEqual(tool.validate_recovery_inputs(program)['reset_frame'],3000)
        for key in ('open_frame','close_frame','reset_frame'):
            wrong=deepcopy(program);wrong['cd_interruption'][key]+=1
            with self.assertRaisesRegex(ValueError,'controller history'):tool.validate_recovery_inputs(wrong)


if __name__=='__main__':unittest.main()
