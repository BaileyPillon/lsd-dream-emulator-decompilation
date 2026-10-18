"""Owned MIPS/sector fixtures for SDK provenance and sequential completions."""
from copy import deepcopy
import io
import struct
import unittest

from tools import inspect_sdk_reads as tool
from tests.test_npc_catalogue import executable
from tests.test_dispatch_returns import disc_fixture,jal


def fixture():
    body=bytearray(0x200)
    targets=[dict(pc=0x80010100,bytes=32,kind=3),dict(pc=0x80010140,bytes=32,kind=1),
             dict(pc=0x80010180,bytes=32,kind=2)]
    code=struct.pack('<8I',0x27BDFFE8,0xAFBF0014,0,0,0x8FBF0014,0,0x03E00008,0x27BD0018)
    for target in targets:body[target['pc']-0x80010000:target['pc']-0x80010000+32]=code
    raw=bytes(disc_fixture(4096));payload=bytearray();records=[]
    active=0;destination=0;sp=0x801FFE00
    for index,target in enumerate((targets[0],targets[1],targets[2],targets[1],targets[2])):
        caller=0x80010000+8*index
        struct.pack_into('<II',body,caller-0x80010000,jal(target['pc']),0)
        row=dict.fromkeys(tool.FIELDS,0)
        row.update(frame=2,ordinal=index+1,entry_id=index+1,kind=target['kind'],entry_frame=2,
            entry_pc=target['pc'],entry_sp=sp,entry_ra=caller+8,
            return_pc=caller+8,return_sp=sp,return_ra=caller+8,
            entry_sequence_low=10+index*10,sequence_low=15+index*10,
            code_bytes=32,code_offset=len(payload))
        for prefix,pc,word,rs,stack in (
            ('entry_jump',caller,jal(target['pc']),0,sp),('entry_delay',caller+4,0,0,sp),
            ('jump',target['pc']+24,0x03E00008,caller+8,sp-24),
            ('delay',target['pc']+28,0x27BD0018,sp-24,sp-24)):
            for name,value in dict(pc=pc,ram=word,fetch=word,rs=rs,sp=stack,flags=1,sr=0).items():
                row[prefix+'_'+name]=value
        payload.extend(code)
        if target['kind']==3:
            row.update(a0=2,a1=0x80030000,arg_readable=1,v0=1,
                arg_word_0=int.from_bytes(raw[20*2352+12:20*2352+15],'little'))
        elif target['kind']==1:
            active=index+1;destination=0x80040000+((index-1)//2)*4096
            row.update(a0=1,a1=destination,a2=0x80,v0=1)
        else:
            lba=20+(index-2)//2
            row.update(buffer_address=destination,buffer_bytes=2048,buffer_offset=len(payload),buffer_status=1)
            payload.extend(raw[lba*2352+24:lba*2352+2072])
        if active:
            row.update(transfer_id=active,transfer_sectors=1,transfer_mode=0x80,
                sdk_word_1=1,sdk_word_2=destination,sdk_word_3=destination+(2048 if target['kind']==2 else 0),
                sdk_word_4=0x80,sdk_word_5=512)
        if target['kind']==2:active=0
        records.append(row)
    summary=dict(protocol=1,event_bytes=464,returns=5,native_returns=5,native_entries=5,payload_bytes=len(payload),
        targets=targets,native_overflow=0,pending_calls=0,pending_transfer=0,max_depth=1,frame_payload_limit=8*1024*1024,
        original_game_RAM_injected=False,original_CPU_source_modified=False,completions=2,
        failed_transfers=0,unassociated_polls=0,overlapping_requests=0)
    return dict(records=records,payload=bytes(payload),summary=summary,targets=targets,image=executable(body),
                program=dict(frames=2,method_trace=dict(arm_frame=0)),disc=raw)


def encoded(records):
    return b''.join(struct.pack('<116I',*(row[name] for name in tool.FIELDS)) for row in records)


class SdkReadTests(unittest.TestCase):
    def setUp(self):self.f=fixture()
    def validate(self,data=None,payload=None):
        f=self.f
        return tool.validate_records(encoded(f['records']) if data is None else data,
            f['payload'] if payload is None else payload,f['summary'],f['targets'],f['image'],f['program'])
    def transfers(self,disc=None):
        f=self.f
        return tool.verify_transfers(f['records'],f['payload'],f['summary'],io.BytesIO(f['disc'] if disc is None else disc))

    def test_two_completed_reads_advance_the_observed_cursor_without_repeating_cached_start(self):
        report,rows=self.validate();transfers=self.transfers()
        self.assertEqual((report['calls'],len(rows),transfers['completed_transfers']),(5,5,2))
        self.assertEqual([row['lba'] for row in transfers['transfers']],[20,21])
        self.assertEqual(transfers['complete_sector_RAM_bytes_compared'],4096)
        self.assertNotEqual(transfers['transfers'][0]['complete_buffer_sha256'],transfers['transfers'][1]['complete_buffer_sha256'])

    def test_truncated_transport_or_lost_native_calls_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'Truncated'):self.validate(data=encoded(self.f['records'])[:-1])
        with self.assertRaisesRegex(ValueError,'native totals'):self.validate(data=encoded(self.f['records'][:-1]))

    def test_complete_callee_code_cannot_be_replaced_by_an_equal_sized_payload(self):
        data=bytearray(self.f['payload']);data[0]^=1
        with self.assertRaisesRegex(ValueError,'entry code'):self.validate(payload=bytes(data))

    def test_callee_extent_must_cover_the_declared_original_range(self):
        self.f['records'][1]['code_bytes']-=4
        with self.assertRaisesRegex(ValueError,'callee range'):self.validate()

    def test_entry_call_and_delay_must_be_original_effective_instructions(self):
        for key in ('entry_jump_ram','entry_jump_fetch','entry_delay_pc','entry_ra'):
            original=deepcopy(self.f)
            self.f['records'][1][key]^=4
            with self.assertRaises(ValueError):self.validate()
            self.f=original

    def test_cache_isolation_and_missing_cache_context_are_rejected(self):
        for key,value in (('entry_sr',0x10000),('jump_flags',0),('entry_delay_sr',0x10000)):
            original=deepcopy(self.f);self.f['records'][1][key]=value
            with self.assertRaises(ValueError):self.validate()
            self.f=original

    def test_return_operand_stack_or_delay_cannot_be_forged(self):
        for key in ('jump_rs','return_sp','delay_sp','delay_fetch'):
            original=deepcopy(self.f);self.f['records'][1][key]^=4
            with self.assertRaises(ValueError):self.validate()
            self.f=original

    def test_duplicate_entry_ids_or_reordered_returns_are_rejected(self):
        self.f['records'][2]['entry_id']=2
        with self.assertRaisesRegex(ValueError,'lost or duplicated'):self.validate()
        self.f=fixture();self.f['records'][1],self.f['records'][2]=self.f['records'][2],self.f['records'][1]
        with self.assertRaisesRegex(ValueError,'sequence or frame'):self.validate()

    def test_non_nested_parent_and_missing_parent_are_rejected(self):
        for value in (1,99):
            self.f['records'][1]['parent_id']=value
            with self.assertRaises(ValueError):self.validate()

    def test_payload_alias_truncation_and_unreferenced_bytes_are_rejected(self):
        self.f['records'][2]['buffer_offset']-=1
        with self.assertRaisesRegex(ValueError,'RAM payload'):self.validate()
        self.f=fixture();self.f['summary']['payload_bytes']+=1
        with self.assertRaisesRegex(ValueError,'unreferenced'):self.validate(payload=self.f['payload']+b'X')

    def test_transfer_id_and_mode_cannot_be_substituted(self):
        for key in ('transfer_id','transfer_sectors','transfer_mode'):
            self.f=fixture();self.f['records'][2][key]^=1
            with self.assertRaisesRegex(ValueError,'transfer identity'):self.transfers()

    def test_successful_recorded_setloc_is_required(self):
        for key,value in (('arg_readable',0),('a1',0),('v0',0)):
            self.f=fixture();self.f['records'][0][key]=value
            with self.assertRaises(ValueError):self.transfers()

    def test_wrong_valid_bcd_cursor_cannot_pass_sector_contents(self):
        self.f['records'][0]['arg_word_0']+=0x10000
        with self.assertRaisesRegex(ValueError,'original disc sectors'):self.transfers()

    def test_second_completion_cannot_reuse_the_first_sector(self):
        data=bytearray(self.f['payload']);a,b=self.f['records'][2],self.f['records'][4]
        data[b['buffer_offset']:b['buffer_offset']+2048]=data[a['buffer_offset']:a['buffer_offset']+2048]
        self.f['payload']=bytes(data)
        self.validate()
        with self.assertRaisesRegex(ValueError,'original disc sectors'):self.transfers()

    def test_completed_destination_length_and_backend_cursor_are_checked(self):
        for key in ('buffer_address','buffer_bytes','sdk_word_1','sdk_word_2','sdk_word_3','sdk_word_5'):
            self.f=fixture();self.f['records'][2][key]^=4
            with self.assertRaisesRegex(ValueError,'destination'):self.transfers()

    def test_overlapping_request_and_invented_busy_completion_are_rejected(self):
        self.f['records'][2]['kind']=1
        with self.assertRaisesRegex(ValueError,'overlaps'):self.transfers()
        self.f=fixture();self.f['records'][2]['v0']=1
        with self.assertRaisesRegex(ValueError,'busy SDK poll'):self.transfers()

    def test_failed_sdk_calls_do_not_become_successful_completions(self):
        for index in (1,2):
            self.f=fixture();self.f['records'][index]['v0']=0xFFFFFFFF
            with self.assertRaises(ValueError):self.transfers()

    def test_truncated_or_wrong_mode_raw_disc_is_rejected(self):
        with self.assertRaises(ValueError):self.transfers(disc=self.f['disc'][:18*2352])
        raw=bytearray(self.f['disc']);raw[20*2352+18]|=0x20;raw[20*2352+22]|=0x20
        with self.assertRaisesRegex(ValueError,'Form1'):self.transfers(disc=bytes(raw))

    def test_native_completion_or_pending_state_disagreement_is_rejected(self):
        self.f['summary']['completions']=1
        with self.assertRaisesRegex(ValueError,'completion counts'):self.transfers()
        self.f=fixture();self.f['summary']['pending_transfer']=2
        with self.assertRaisesRegex(ValueError,'transfer state'):self.validate()

    def test_request_return_cannot_claim_completed_payload(self):
        self.f['records'][1]['buffer_status']=1
        with self.assertRaisesRegex(ValueError,'request/control'):self.transfers()


if __name__=='__main__':unittest.main()
