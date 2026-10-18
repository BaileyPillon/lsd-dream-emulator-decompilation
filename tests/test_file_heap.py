"""Owned boundary/heap fixtures; no game data or original-function output stubs."""
from copy import deepcopy
import struct
import unittest
from tools import inspect_file_heap as tool
from tools.inspect_read_lifecycle import READ_PC,DISPATCH_PC

def fixture():
    payload=bytearray();records=[]
    receiver=0x80110020;buffer=0x80140000
    initial=[11]*11;constructed=[tool.BASE_FILE_TABLE,0,0,0,0,0,11,11,0,0,0]
    loaded=constructed[:];loaded[3]=1;loaded[4]=buffer;loaded[5]=2048
    released=loaded[:];released[4]=0
    def add(id_,kind,start,end,a0=0,v0=0,words=(),status=0,address=0):
        row=dict(entry_id=id_,kind=kind,a0=a0,v0=v0,entry_frame=1,frame=1,
            entry_sequence_low=start,entry_sequence_high=0,sequence_low=end,sequence_high=0,
            buffer_address=address,buffer_bytes=4*len(words),buffer_offset=len(payload) if words else 0,buffer_status=status)
        payload.extend(struct.pack('<'+str(len(words))+'I',*words));records.append(row);return row
    add(1,5,10,15,44,receiver,(48,0,0,0),7,receiver-4)
    add(2,5,20,25,2048,buffer,(2052,0,0,0),7,buffer-4)
    add(3,7,30,35,receiver,words=initial+constructed,status=6,address=receiver)
    request=add(4,1,300,310,1,1);request.update(a1=buffer,a2=128,entry_jump_pc=0x8002866C)
    add(5,2,320,350)
    add(6,9,400,450,receiver,words=loaded+released,status=6,address=receiver)
    add(7,6,410,420,buffer,words=(2052,0,0,0)*2,status=8,address=buffer-4)
    add(8,8,500,550,receiver,words=released+released,status=6,address=receiver)
    add(9,6,510,520,receiver,words=(48,0,0,0)*2,status=8,address=receiver-4)
    records.sort(key=lambda row:row['sequence_low'])
    entries=[];returns=[]
    for n,flag in ((1,0),(2,1)):
        entry=dict(pc=READ_PC,transfer_pc=DISPATCH_PC if flag else 0x80043184,relative_frame=n,
            a0=receiver,a1=buffer,a2=2048,a0_word_28=flag,a0_word_0C=1,
            memory_word_0=1,memory_word_1=1,memory_word_2=0)
        returned=dict(kind=1,base_ordinal=n,entry_pc=READ_PC,v0=0,a0=receiver,a1=buffer,a2=2048,
            entry_sequence_low=100*n,entry_sequence_high=0,sequence_low=100*n+50,sequence_high=0,memory_word_2=flag)
        entries.append(entry);returns.append(returned)
    transfers=dict(transfers=[dict(request_id=4,completion_id=5,bytes=2048,lba=20,
        destination=f'0x{buffer:08X}',complete_buffer_sha256='0'*64)])
    return dict(records=records,payload=bytes(payload),entries=entries,returns=returns,transfers=transfers,
                program=dict(method_trace=dict(heap_lifetime=True)))

class FileHeapTests(unittest.TestCase):
    def setUp(self):self.f=fixture()
    def row(self,id_):return next(row for row in self.f['records'] if row['entry_id']==id_)
    def analyze(self):return tool.analyze_file_heap(**self.f)
    def set_word(self,id_,index,value):
        data=bytearray(self.f['payload']);struct.pack_into('<I',data,self.row(id_)['buffer_offset']+4*index,value)
        self.f['payload']=bytes(data)

    def test_constructor_read_release_and_destructor_share_exact_allocation_generations(self):
        report=self.analyze()
        self.assertEqual((report['successful_allocations'],report['matched_frees'],report['file_destructors']),(2,2,1))
        self.assertEqual((report['queued_Read_lifetime_windows_qualified'],report['relevant_allocations_closed']),(1,2))
        self.assertEqual(report['reads'][0]['receiver_allocation_id'],1)
        self.assertFalse(report['whole_file_feature_accepted'])

    def test_ctor_must_clear_its_actual_file_fields_and_keep_locator_residue(self):
        for index in (11,14,15,16,17,19,20,21):
            self.f=fixture();self.set_word(3,index,123)
            with self.assertRaisesRegex(ValueError,'constructor'):self.analyze()

    def test_heap_snapshot_status_address_and_extent_are_not_interchangeable(self):
        for key in ('buffer_status','buffer_address','buffer_bytes'):
            self.f=fixture();self.row(1)[key]^=4
            with self.assertRaisesRegex(ValueError,'snapshot'):self.analyze()

    def test_malloc_header_must_cover_the_real_requested_size(self):
        self.set_word(2,0,16)
        with self.assertRaisesRegex(ValueError,'allocation header'):self.analyze()

    def test_free_block_flag_cannot_describe_a_successful_allocation(self):
        self.set_word(1,0,48|0x40000000)
        with self.assertRaisesRegex(ValueError,'allocation header'):self.analyze()

    def test_capacity_cannot_invent_storage_beyond_the_original_split_threshold(self):
        self.set_word(2,0,2052+16)
        with self.assertRaisesRegex(ValueError,'allocation header'):self.analyze()

    def test_zero_size_request_is_distinct_from_an_observed_allocation_failure(self):
        self.f['records'].append(dict(entry_id=10,kind=5,a0=0,v0=0,entry_frame=1,frame=1,
            entry_sequence_low=600,entry_sequence_high=0,sequence_low=610,sequence_high=0,
            buffer_address=0,buffer_bytes=0,buffer_offset=0,buffer_status=0))
        report=self.analyze()
        self.assertEqual((report['zero_size_allocation_requests'],report['failed_allocations']),(1,0))

    def test_two_live_generations_at_the_same_pointer_are_rejected(self):
        self.row(2)['v0']=self.row(1)['v0'];self.row(2)['buffer_address']=self.row(1)['v0']-4
        with self.assertRaisesRegex(ValueError,'share a start'):self.analyze()

    def test_free_header_capacity_cannot_change_before_the_observed_free(self):
        self.set_word(7,0,2068)
        with self.assertRaisesRegex(ValueError,'capacity changed'):self.analyze()

    def test_release_requires_the_real_buffer_free_and_pointer_clear(self):
        self.f['records']=[row for row in self.f['records'] if row['entry_id']!=7]
        with self.assertRaisesRegex(ValueError,'release free call'):self.analyze()

    def test_release_cannot_change_unrelated_receiver_fields(self):
        self.set_word(6,11+7,123)
        with self.assertRaisesRegex(ValueError,'outside'):self.analyze()

    def test_no_free_release_preserves_payload_and_open_lifetimes(self):
        before=self.row(6)['buffer_offset'];data=bytearray(self.f['payload'])
        words=list(struct.unpack_from('<22I',data,before));words[8]=words[19]=1;words[15]=words[4]
        struct.pack_into('<22I',data,before,*words);self.f['payload']=bytes(data)
        self.f['records']=[row for row in self.f['records'] if row['entry_id'] not in (7,8,9)]
        report=self.analyze()
        self.assertEqual((report['file_releases_freeing_buffers'],report['relevant_allocations_still_live']),(0,2))

    def test_destructor_must_free_its_exact_original_receiver(self):
        self.row(9)['a0']+=4;self.row(9)['buffer_address']+=4
        with self.assertRaises(ValueError):self.analyze()

    def test_free_inside_the_pending_read_window_is_rejected(self):
        self.f['records']=[row for row in self.f['records'] if row['entry_id'] not in (6,8)]
        self.row(7)['entry_sequence_low']=330;self.row(7)['sequence_low']=340
        with self.assertRaisesRegex(ValueError,'freed inside'):self.analyze()

    def test_an_unobserved_constructor_does_not_become_an_accepted_object_lifetime(self):
        self.f['records']=[row for row in self.f['records'] if row['entry_id']!=3]
        report=self.analyze()
        self.assertEqual((report['queued_Read_lifetime_windows_qualified'],report['queued_Read_lifetime_windows_unqualified']),(0,1))
        self.assertFalse(report['unqualified'][0]['constructor_observed'])

    def test_double_free_is_not_reclassified_as_an_unobserved_birth(self):
        extra=deepcopy(self.row(7));extra.update(entry_id=10,entry_sequence_low=600,sequence_low=610)
        self.f['records'].append(extra)
        with self.assertRaisesRegex(ValueError,'freed again'):self.analyze()

    def test_unobserved_birth_is_reported_without_accepting_a_complete_heap_history(self):
        self.row(9)['a0']=0x80170000;self.row(9)['buffer_address']=0x8016FFFC
        self.f['records']=[row for row in self.f['records'] if row['entry_id']!=8]
        report=self.analyze()
        self.assertEqual(report['unobserved_allocation_frees'],1)
        self.assertFalse(report['all_object_lifetimes_accepted'])

    def test_undeclared_heap_profile_is_rejected(self):
        self.f['program']['method_trace']['heap_lifetime']=False
        with self.assertRaisesRegex(ValueError,'selected'):self.analyze()

    def test_reused_addresses_require_a_constructor_in_the_new_allocation_generation(self):
        for include_constructor in (False,True):
            self.f=fixture()
            def copy_event(old,id_,start,end):
                row=deepcopy(self.row(old));row.update(entry_id=id_,entry_sequence_low=start,sequence_low=end)
                if row['buffer_bytes']:
                    data=bytearray(self.f['payload']);raw=data[row['buffer_offset']:row['buffer_offset']+row['buffer_bytes']]
                    row['buffer_offset']=len(data);data.extend(raw);self.f['payload']=bytes(data)
                self.f['records'].append(row);return row
            copy_event(1,10,600,610);copy_event(2,11,620,630)
            if include_constructor:copy_event(3,12,640,650)
            request_id=13 if include_constructor else 12;completion_id=request_id+1
            copy_event(4,request_id,900,910);copy_event(5,completion_id,920,950)
            for index in range(2):
                entry=deepcopy(self.f['entries'][index]);entry['relative_frame']+=2;self.f['entries'].append(entry)
                returned=deepcopy(self.f['returns'][index]);returned['base_ordinal']+=2
                returned['entry_sequence_low']+=600;returned['sequence_low']+=600;self.f['returns'].append(returned)
            transfer=deepcopy(self.f['transfers']['transfers'][0]);transfer.update(request_id=request_id,completion_id=completion_id,lba=21)
            self.f['transfers']['transfers'].append(transfer)
            report=self.analyze()
            self.assertEqual(report['reads'][0]['receiver_allocation_id'],1)
            self.assertEqual(report['queued_Read_lifetime_windows_qualified'],2 if include_constructor else 1)
            if include_constructor:self.assertEqual(report['reads'][1]['receiver_allocation_id'],10)
            else:self.assertFalse(report['unqualified'][0]['constructor_observed'])

if __name__=='__main__':unittest.main()
