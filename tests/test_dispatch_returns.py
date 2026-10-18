"""Owned MIPS, return-tree and raw-disc fixtures; no original game inputs."""
from copy import deepcopy
import io
import json
import struct
import unittest
from unittest.mock import patch

from tools import dispatch_returns as tool
from tests.test_npc_catalogue import executable


def jal(pc):
    return 0x0C000000 | ((pc >> 2) & 0x03FFFFFF)


def fixture():
    read,helper,request,poll=0x80010040,0x800100C0,0x80010180,0x800101A0
    body=bytearray(0x200)
    code={0x80010000:[0x0040F809,0],read:[0x27BDFFE0,0xAFBF001C,jal(helper),0,0x8FBF001C,0,0x27BD0020,0x03E00008,0],
        helper:[0x27BDFFD0,0xAFBF002C,0xAFB00028,0x00808021,0x000622C2,jal(request),0x34060080,
                0x00002021,jal(poll),0x00002821,0x8FBF002C,0x8FB00028,0x27BD0030,0x03E00008,0],
        request:[0x03E00008,0],poll:[0x03E00008,0]}
    for pc,words in code.items():struct.pack_into('<'+'I'*len(words),body,pc-0x80010000,*words)
    image=executable(bytes(body))
    settings=dict(read_pc=read,helper_pc=helper,helper_bytes=60,request_pc=request,poll_pc=poll,
                  request_call=helper+20,poll_call=helper+32)
    receiver,destination,sp=0x80080000,0x80100000,0x801FF000
    entry=dict(relative_frame=2,timestamp=10,pc=read,sp=sp,ra=0x80010008,a0=receiver,a1=destination,a2=2048,a3=0,
               transfer_pc=0x80010000,delay_pc=0x80010004,transfer_word=0x0040F809,delay_word=0)
    entry.update({'a0_word_'+f'{n*4:02X}':0 for n in range(11)})
    entry.update(a0_word_00=0x80070000,a0_word_0C=1,a0_word_18=0x00200200,a0_word_1C=3)
    main={name:0 for name in tool.FIELDS}
    main.update(frame=2,ordinal=2,entry_id=1,kind=1,base_ordinal=1,entry_frame=2,entry_timestamp=10,
        entry_pc=read,entry_sp=sp,entry_ra=entry['ra'],a0=receiver,a1=destination,a2=2048,
        return_pc=entry['ra'],return_sp=sp,return_ra=entry['ra'],timestamp=60,
        jump_pc=read+28,delay_pc=read+32,jump_ram=0x03E00008,jump_fetch=0x03E00008,jump_rs=entry['ra'],
        jump_sp=sp,delay_sp=sp,jump_flags=1,delay_flags=1,buffer_address=destination,buffer_bytes=2048,
        buffer_offset=60+2048,buffer_status=1,sequence_low=60,entry_sequence_low=10,
        entry_transfer_pc=0x80010000,entry_delay_pc=0x80010004,entry_transfer_ram=0x0040F809,
        entry_transfer_fetch=0x0040F809,entry_transfer_flags=1,entry_delay_flags=1,entry_transfer_rs=read,
        entry_transfer_sp=sp,entry_delay_sp=sp)
    for n in range(11):main['entry_a0_word_'+f'{n*4:02X}']=entry['a0_word_'+f'{n*4:02X}']
    child=deepcopy(main)
    child.update(ordinal=1,entry_id=2,parent_id=1,kind=2,base_ordinal=0,entry_pc=helper,entry_sp=sp-32,
        entry_ra=read+16,return_pc=read+16,return_ra=read+16,return_sp=sp-32,entry_timestamp=20,timestamp=50,
        jump_pc=helper+52,delay_pc=helper+56,jump_rs=read+16,jump_sp=sp-32,delay_sp=sp-32,
        buffer_offset=60,helper_code_bytes=60,helper_code_offset=0,sequence_low=50,entry_sequence_low=20,
        entry_transfer_pc=read+8,entry_delay_pc=read+12,entry_transfer_ram=jal(helper),entry_transfer_fetch=jal(helper),
        entry_transfer_rs=0,entry_transfer_sp=sp-32,entry_delay_sp=sp-32,
        read_request_entries=1,read_poll_entries=1,read_poll_returns=1,request_a0=1,request_a1=destination,request_a2=0x80,
        last_poll_frame=2,last_poll_timestamp=40,poll_return_pc=helper+40,poll_return_sp=sp-80,
        poll_jump_pc=poll,poll_delay_pc=poll+4,poll_jump_ram=0x03E00008,poll_jump_fetch=0x03E00008,
        poll_jump_rs=helper+40,poll_jump_flags=1,poll_delay_flags=1,poll_sequence_low=40,request_sequence_low=30,
        request_call_pc=helper+20,request_ra=helper+28,poll_call_pc=helper+32,poll_ra=helper+40,poll_entry_sp=sp-80)
    helper_code=bytes(body[0xC0:0xFC]);buffer=b'ABC'+bytes(2045);payload=helper_code+buffer+buffer
    summary=dict(protocol=1,event_bytes=600,settings=settings,frame_payload_limit=8*1024*1024,native_overflow=0,
        native_mismatches=0,pending_entries=0,original_game_RAM_injected=False,original_CPU_source_modified=False,
        return_values_are_not_transfer_counts=True,returns=2,native_returns=2,native_entries=2,payload_bytes=len(payload),max_depth=2)
    selected={read:dict(function='cd_file_driver_read',pc=f'0x{read:08X}',function_bytes=36)}
    program=dict(frames=12,executable_sha256=tool.sha(image),method_trace=dict(arm_frame=0,flow_sites=['0x80010000']))
    return dict(image=image,settings=settings,entries=[entry],records=[child,main],payload=payload,
                summary=summary,selected=selected,program=program)


def encoded(records):
    return b''.join(struct.pack('<150I',*(row[name] for name in tool.FIELDS)) for row in records)


def directory_record(lba,size,name,flags=0):
    name=name if isinstance(name,bytes) else name.encode('ascii')
    data=bytearray(33+len(name)+(len(name)%2==0));data[0]=len(data)
    struct.pack_into('<I',data,2,lba);struct.pack_into('>I',data,6,lba)
    struct.pack_into('<I',data,10,size);struct.pack_into('>I',data,14,size)
    data[25]=flags;struct.pack_into('<H',data,28,1);struct.pack_into('>H',data,30,1)
    data[32]=len(name);data[33:33+len(name)]=name
    return bytes(data)


def disc_fixture(size=3):
    def bcd(value):return ((value//10)<<4)|(value%10)
    data=bytearray(24*2352)
    for lba in range(24):
        at=lba*2352;data[at:at+12]=b'\0'+b'\xff'*10+b'\0';position=lba+150
        data[at+12:at+16]=bytes((bcd(position//4500),bcd(position//75%60),bcd(position%75),2))
        data[at+16:at+24]=b'\0\0\x08\0'*2
    volume=bytearray(2048);volume[:7]=b'\x01CD001\x01';root=directory_record(17,2048,b'\0',2)
    volume[156:156+len(root)]=root;data[16*2352+24:16*2352+2072]=volume
    directory=directory_record(17,2048,b'\0',2)+directory_record(17,2048,b'\1',2)+directory_record(20,size,'A.BIN;1')
    data[17*2352+24:17*2352+24+len(directory)]=directory
    data[20*2352+24:20*2352+27]=b'ABC'
    data[21*2352+24:21*2352+2072]=b'Z'*2048
    return data


class OriginalReturnTests(unittest.TestCase):
    def setUp(self):self.f=fixture()
    def test_optional_null_SDK_targets_preserve_return_only_host_compatibility(self):
        self.f['summary']['settings']=deepcopy(self.f['settings'])
        self.f['summary']['settings']['sdk_targets']=None
        self.validate()

    def test_undeclared_SDK_targets_cannot_be_hidden_in_return_only_summary(self):
        self.f['summary']['settings']=deepcopy(self.f['settings'])
        self.f['summary']['settings']['sdk_targets']=[]
        with self.assertRaisesRegex(ValueError,'protocol'):self.validate()

    def validate(self):
        f=self.f
        return tool.validate_returns(encoded(f['records']),f['payload'],f['summary'],f['entries'],
            f['settings'],f['selected'],f['image'],f['program'])

    def test_original_helper_and_base_returns_have_nested_call_and_complete_data_evidence(self):
        report,rows=self.validate()
        self.assertEqual((report['base_method_returns'],report['synchronous_helper_returns'],report['max_depth']),(1,1,2))
        self.assertEqual(report['request_entries'],1)

    def test_missing_duplicate_or_reordered_return_records_are_rejected(self):
        for records in (self.f['records'][:1],self.f['records']*2,list(reversed(self.f['records']))):
            self.f=fixture();self.f['records']=records
            with self.subTest(count=len(records)),self.assertRaises(ValueError):self.validate()

    def test_wrong_base_identity_arguments_or_entry_receiver_are_rejected(self):
        for key in ('base_ordinal','entry_pc','entry_frame','entry_sp','entry_ra','a0','a1','a2','a3','entry_a0_word_18'):
            self.f=fixture();self.f['records'][1][key]^=4
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate()

    def test_wrong_return_target_stack_or_JR_operand_is_rejected(self):
        for key in ('return_pc','return_sp','return_ra','jump_rs','jump_pc','delay_pc','jump_ram','jump_fetch','delay_ram','delay_fetch'):
            self.f=fixture();self.f['records'][0][key]^=4
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate()

    def test_wrong_parent_skipped_interval_or_creation_order_is_rejected(self):
        for key,value in (('parent_id',0),('entry_id',3),('entry_sequence_low',1),('sequence_low',70)):
            self.f=fixture();self.f['records'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate()

    def test_changed_full_helper_tail_is_rejected(self):
        data=bytearray(self.f['payload']);data[59]^=1;self.f['payload']=bytes(data)
        with self.assertRaisesRegex(ValueError,'Full synchronous-helper code'):self.validate()

    def test_lost_pending_overflow_mismatch_and_transport_changes_are_rejected(self):
        for key,value in (('pending_entries',1),('native_overflow',1),('native_mismatches',1),('native_entries',3),
                          ('event_bytes',596),('max_depth',1),('payload_bytes',0)):
            self.f=fixture();self.f['summary'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate()

    def test_missing_complete_payload_changed_trailing_byte_and_overlap_are_rejected(self):
        for mode in ('truncated','different-parent-tail','overlap','extra'):
            self.f=fixture()
            if mode=='truncated':self.f['payload']=self.f['payload'][:-1]
            elif mode=='extra':self.f['payload']+=b'X';self.f['summary']['payload_bytes']+=1
            elif mode=='overlap':self.f['records'][1]['buffer_offset']=60
            else:
                data=bytearray(self.f['payload']);data[-1]^=1;self.f['payload']=bytes(data)
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.validate()

    def test_read_zero_cannot_be_replaced_by_a_claimed_byte_count(self):
        self.f['records'][1]['v0']=2048
        with self.assertRaisesRegex(ValueError,'zero result'):self.validate()

    def test_original_request_poll_arguments_status_and_boundary_must_agree(self):
        for key in ('read_request_entries','read_poll_entries','read_poll_returns','request_a0','request_a1','request_a2',
                    'last_poll_value','poll_ra','poll_entry_sp','poll_return_pc','poll_jump_rs','poll_jump_fetch'):
            self.f=fixture();self.f['records'][0][key]^=1
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate()

    def test_return_cache_isolation_and_missing_effective_instruction_context_are_rejected(self):
        for key,value in (('sr',0x10000),('jump_sr',0x10000),('jump_flags',0),('poll_jump_flags',0)):
            self.f=fixture();self.f['records'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate()


class OriginalReturnSelectionTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture();s=self.f['settings'];at=0x800+s['helper_pc']-0x80010000
        self.provenance=dict(status='verified_canonical_compiler_census_and_corrected_source_quality',
            canonical_executable_sha256=tool.sha(self.f['image']),normal_complete_build_equal=True,fresh_complete_build_equal=True,
            source_removal_records=[dict(function='cd_file_driver_read_sectors',original_address=f"0x{s['helper_pc']:08X}",
            original_function_bytes=s['helper_bytes'],original_function_sha256=tool.sha(self.f['image'][at:at+s['helper_bytes']]),
            complete_symbolic_image_matches_regular=True,independent_GNU_extents_agree=True)])
    def select(self,seal=True):
        f=self.f;raw=json.dumps(self.provenance).encode();s=f['settings']
        f['program']['method_trace']['return_trace']=dict(kind='original_CD_Read_buffers',read_method='cd_file_driver_read',
            synchronous_helper='cd_file_driver_read_sectors',helper_provenance_sha256=tool.sha(raw) if seal else '0'*64,
            request_pc=f"0x{s['request_pc']:08X}",poll_pc=f"0x{s['poll_pc']:08X}")
        with patch.object(tool,'CANONICAL_SHA256',tool.sha(f['image'])):
            return tool.verified_return_selection(f['program'],f['selected'],f['image'],self.provenance,raw)
    def test_complete_helper_range_and_actual_JAL_targets_are_selected(self):self.assertEqual(self.select(),self.f['settings'])
    def test_changed_seal_missing_range_or_false_GNU_claim_is_rejected(self):
        with self.assertRaises(ValueError):self.select(False)
        self.provenance['source_removal_records'][0]['independent_GNU_extents_agree']=False
        with self.assertRaises(ValueError):self.select()
    def test_equal_helper_entry_word_does_not_hide_a_wrong_full_body_hash(self):
        self.provenance['source_removal_records'][0]['original_function_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Complete original return helper'):self.select()


class OriginalReturnDiscTests(unittest.TestCase):
    def setUp(self):self.f=fixture();self.f['entries'][0]['transfer_pc']=0x80026BB0
    def verify(self,disc=None):
        f=self.f
        return tool.verify_disc_buffers(f['records'],f['payload'],f['entries'],f['settings'],io.BytesIO(disc_fixture() if disc is None else disc))
    def test_complete_return_buffer_matches_raw_sectors_and_ISO_file_identity(self):
        report=self.verify();self.assertEqual(report['synchronous_return_buffers_matched'],1)
        self.assertEqual(report['files'][0]['ISO_paths'],['/A.BIN'])
        self.assertEqual(report['complete_requested_bytes_compared'],2048)
    def test_matching_logical_prefix_cannot_hide_wrong_padding_bytes(self):
        data=bytearray(self.f['payload']);data[60+100]^=1;self.f['payload']=bytes(data)
        with self.assertRaisesRegex(ValueError,'Complete synchronous return buffer'):self.verify()
    def test_expected_disc_extent_comes_from_the_original_Read_inputs(self):
        self.f['entries'][0]['a0_word_18']=0x00210200
        with self.assertRaisesRegex(ValueError,'receiver inputs changed'):self.verify()
    def test_file_size_position_and_full_original_aligned_length_are_required(self):
        for key,value in (('entry_a0_word_1C',4),('entry_a0_word_18',0x00210200),('a2',3)):
            self.f=fixture();self.f['entries'][0]['transfer_pc']=0x80026BB0;self.f['records'][0][key]=value
            if key=='a2':self.f['entries'][0]['a2']=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.verify()
    def test_invalid_BCD_form2_and_wrong_sector_header_are_rejected(self):
        with self.assertRaises(ValueError):tool.bcd_lba(0x00750200)
        for mode in ('form2','wrong-header'):
            disc=disc_fixture();at=20*2352
            if mode=='form2':disc[at+18]|=0x20;disc[at+22]|=0x20
            else:disc[at+14]=0x21
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.verify(disc)
    def test_aligned_file_includes_the_fully_extra_sector(self):
        disc=disc_fixture(2048);actual=bytes(disc[20*2352+24:20*2352+2072]+disc[21*2352+24:21*2352+2072])
        self.f['payload']=self.f['payload'][:60]+actual+actual
        self.f['records'][0].update(entry_a0_word_1C=2048,a2=4096,buffer_bytes=4096)
        self.f['records'][1].update(buffer_offset=60+4096,buffer_bytes=4096,a2=4096)
        self.f['entries'][0].update(a0_word_1C=2048,a2=4096)
        report=self.verify(disc);self.assertEqual(report['aligned_files_with_an_extra_sector'],1)
        self.assertEqual(report['files'][0]['trailing_bytes'],2048)


if __name__ == '__main__':
    unittest.main()
