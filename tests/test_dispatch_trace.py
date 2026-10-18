"""Owned program and executable fixtures for original method selection."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import dispatch_trace as tool
from tools.record_dispatch_history import load_observer_profile
from tools import inspect_dispatch_history as inspector
from tests.test_npc_catalogue import executable


def program():
    return dict(schema_version=1,frames=12,executable_sha256='a'*64,disc_track_sha256='b'*64,
        controller=dict(buttons=['Confirm'],axes={'Axis':128},column_order=['Confirm','Axis']),
        segments=[dict(until=12,phase='neutral',pressed=[])],checkpoint_frames=[0,12],RAM_sample_interval=2,
        method_trace=dict(arm_frame=0,targets=['method'],memory_symbols=['alpha','beta','gamma','delta']))


class DispatchProgramTests(unittest.TestCase):
    def test_minimal_program_has_no_NPC_identity_or_tick_fields(self):
        p=tool.validate_program(program())
        self.assertNotIn('trace',p)
        self.assertEqual(len(tool.expand_program(p).splitlines()),13)

    def test_only_a_valid_program_prefix_can_be_expanded(self):
        self.assertEqual(len(tool.expand_program(program(),4).splitlines()),5)
        for frames in (0,13,True):
            with self.subTest(frames=frames),self.assertRaises(ValueError):
                tool.expand_program(program(),frames)

    def test_duplicate_or_untyped_targets_are_rejected(self):
        for names in ([],['method']*2,[{}],['a']*17):
            p=program();p['method_trace']['targets']=names
            with self.subTest(names=names),self.assertRaises(ValueError):tool.validate_program(p)

    def test_memory_set_requires_four_distinct_named_words(self):
        for names in (['a']*4,['a','b','c'],['a','b','c',None]):
            p=program();p['method_trace']['memory_symbols']=names
            with self.subTest(names=names),self.assertRaises(ValueError):tool.validate_program(p)

    def test_observer_arm_must_be_inside_the_controller_window(self):
        for frame in (-1,13,True):
            p=program();p['method_trace']['arm_frame']=frame
            with self.subTest(frame=frame),self.assertRaises(ValueError):tool.validate_program(p)

    def test_expanded_input_checksum_detects_changed_controller_history(self):
        p=program();p['expanded_submitted_sha256']=hashlib.sha256(tool.expand_program(p)).hexdigest()
        tool.expand_program(p)
        p['segments'][0]['pressed']=['Confirm']
        with self.assertRaisesRegex(ValueError,'Expanded controller inputs differ'):tool.expand_program(p)

    def test_noncontiguous_or_repeated_checkpoints_are_rejected(self):
        for points in ([0,0,12],[0,11],[12,0]):
            p=program();p['checkpoint_frames']=points
            with self.subTest(points=points),self.assertRaises(ValueError):tool.validate_program(p)

    def test_NPC_build_cannot_be_used_as_a_method_observer(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'profile.json'
            p.write_text(json.dumps(dict(schema_version=1,status='built_separate_NPC_observer_core')))
            with self.assertRaisesRegex(ValueError,'build_dispatch_observer'):load_observer_profile(p)


class DispatchSelectionTests(unittest.TestCase):
    def setUp(self):
        self.image=executable(bytes.fromhex('0800e00300000000'))
        self.digest=hashlib.sha256(self.image).hexdigest()
        self.program=program();self.program['executable_sha256']=self.digest
        self.target=dict(function='method',pc='0x80010000',function_bytes=8,
            function_sha256=hashlib.sha256(self.image[0x800:]).hexdigest(),
            entry_instruction_sha256=hashlib.sha256(self.image[0x800:0x804]).hexdigest())
        self.catalogue=dict(schema_version=1,kind='original_LSD_declared_dispatch_targets',
            canonical_executable_sha256=self.digest,targets=[self.target])

    def select(self,catalogue=None,image=None,corrupt_seal=False):
        catalogue=deepcopy(self.catalogue if catalogue is None else catalogue)
        raw=json.dumps(catalogue,sort_keys=True).encode()
        provenance=dict(status='verified_complete_declared_dispatch_catalogue',complete_target_function_ranges=1,
                        catalogue={'sha256':'0'*64 if corrupt_seal else hashlib.sha256(raw).hexdigest()})
        with patch.object(tool,'CANONICAL_SHA256',self.digest):
            return tool.verified_selection(self.program,catalogue,provenance,raw,self.image if image is None else image)

    def test_complete_owned_method_is_selected(self):
        self.assertEqual(self.select()[0x80010000]['function_bytes'],8)

    def test_wrong_catalogue_seal_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'published provenance'):self.select(corrupt_seal=True)

    def test_changed_original_executable_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'canonical original executable'):self.select(image=self.image[:-1]+b'X')

    def test_equal_entry_word_cannot_hide_a_wrong_full_function_hash(self):
        data=deepcopy(self.catalogue);data['targets'][0]['function_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Complete selected method differs'):self.select(data)

    def test_unknown_or_ambiguous_function_names_are_rejected(self):
        self.program['method_trace']['targets']=['missing']
        with self.assertRaisesRegex(ValueError,'absent'):self.select()
        self.program['method_trace']['targets']=['method']
        data=deepcopy(self.catalogue);data['targets'].append(dict(self.target))
        with self.assertRaisesRegex(ValueError,'Incomplete|Ambiguous'):self.select(data)

    def test_oversized_or_unaligned_target_spans_are_rejected(self):
        for field,value in (('function_bytes',4100),('function_bytes',7),('pc','0x80010002')):
            data=deepcopy(self.catalogue);data['targets'][0][field]=value
            with self.subTest(field=field,value=value),self.assertRaisesRegex(ValueError,'complete unique spans'):
                self.select(data)

    def supplement(self,changed=None):
        self.image=executable(bytes.fromhex('0800e003000000000800e00300000000'))
        self.digest=hashlib.sha256(self.image).hexdigest()
        self.program['executable_sha256']=self.digest
        self.program['method_trace']['targets']=['other']
        self.catalogue['canonical_executable_sha256']=self.digest
        record=dict(function='other',address='0x80010008',bytes=8,
                    sha256=hashlib.sha256(self.image[0x808:]).hexdigest())
        if changed: record.update(changed)
        raw=json.dumps([record]).encode()
        proof=dict(status='verified_bounded_file_driver_interface_repair',canonical_executable_sha256=self.digest,
            original_symbol_diagnostic=dict(complete_canonical_image_equal=True,independent_GNU_sized_function_extents_equal=True),
            producer_dependencies={'research/file_driver/function-ranges.json':hashlib.sha256(raw).hexdigest()},
            original_function_range_count=1)
        return raw,proof

    def supplement_selection(self,raw,proof):
        catalogue_raw=json.dumps(self.catalogue,sort_keys=True).encode()
        provenance=dict(status='verified_complete_declared_dispatch_catalogue',complete_target_function_ranges=1,
            catalogue={'sha256':hashlib.sha256(catalogue_raw).hexdigest()})
        with patch.object(tool,'CANONICAL_SHA256',self.digest):
            return tool.verified_selection(self.program,self.catalogue,provenance,catalogue_raw,self.image,
                                           json.loads(raw),proof,raw)

    def test_separately_qualified_method_is_not_mislabelled_as_declared_target(self):
        raw,proof=self.supplement()
        selected=self.supplement_selection(raw,proof)
        self.assertEqual(selected[0x80010008]['range_source'],'file_driver_interface_ranges')
        self.assertEqual(len(self.catalogue['targets']),1)

    def test_supplement_requires_its_exact_published_bytes(self):
        raw,proof=self.supplement()
        proof['producer_dependencies']['research/file_driver/function-ranges.json']='0'*64
        with self.assertRaisesRegex(ValueError,'Supplemental range bytes'):self.supplement_selection(raw,proof)

    def test_supplement_requires_complete_image_and_independent_extents(self):
        raw,proof=self.supplement()
        proof['original_symbol_diagnostic']['independent_GNU_sized_function_extents_equal']=False
        with self.assertRaisesRegex(ValueError,'canonical ELF/GNU qualification'):self.supplement_selection(raw,proof)

    def test_supplement_cannot_reassign_an_existing_function_owner(self):
        raw,proof=self.supplement({'address':'0x80010000'})
        with self.assertRaisesRegex(ValueError,'function owners disagree'):self.supplement_selection(raw,proof)


class DispatchEntryTests(unittest.TestCase):
    def setUp(self):
        self.body=bytes.fromhex('0800e00300000000')
        self.image=executable(bytes.fromhex('09F84000000000000800E00300000000')+self.body)
        self.pc=0x80010010
        self.selected={self.pc:dict(function='method',function_bytes=8,function_sha256=hashlib.sha256(self.body).hexdigest())}
        self.row={field:'00000000' for field in inspector.WORD_FIELDS}
        self.row.update(relative_frame='1',timestamp='5',pc='80010010',a0='80110000',a1='FFFFFFFF',a2='80000000',
            ra='80010008',sp='801FF000',instruction='03E00008',transfer_pc='80010000',delay_pc='80010004',
            transfer_word='0040F809',delay_word='00000000',function_bytes='8',function_sha256=hashlib.sha256(self.body).hexdigest(),
            code_offset='0',a0_table_word_044='80010010')

    def validate(self,rows=None,code=None):
        return inspector.validate_entries([self.row] if rows is None else rows,program(),self.selected,
                                          self.body if code is None else code,self.image)

    def test_actual_transfer_is_separate_from_a_candidate_receiver_slot(self):
        entries,report=self.validate()
        self.assertEqual(report['transfer_classifications'],{'observed_indirect_JALR':1})
        self.assertEqual(entries[0]['candidate_receiver_slots'],['0x044'])
        self.assertEqual(report['virtual_receiver_slot_edges_accepted'],0)
        self.assertEqual(entries[0]['a1'],0xFFFFFFFF)

    def test_changed_method_tail_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Complete observed method bytes'):
            self.validate(code=self.body[:-1]+b'X')

    def test_equal_code_cannot_hide_a_changed_entry_instruction(self):
        self.row['instruction']='00000000'
        with self.assertRaisesRegex(ValueError,'entry instruction'):self.validate()

    def test_changed_original_caller_instruction_is_rejected(self):
        self.row['transfer_word']='00000000'
        with self.assertRaisesRegex(ValueError,'caller transfer/delay bytes'):self.validate()

    def test_changed_link_register_return_address_is_rejected(self):
        self.row['ra']='8001000C'
        with self.assertRaisesRegex(ValueError,'return address'):self.validate()

    def test_duplicate_events_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'Duplicated original method entry'):
            self.validate([self.row,dict(self.row)])

    def test_out_of_order_or_outside_window_events_are_rejected(self):
        late=dict(self.row,relative_frame='13')
        with self.assertRaisesRegex(ValueError,'native order/window'):self.validate([late])
        first=dict(self.row,timestamp='6');last=dict(self.row,timestamp='5')
        with self.assertRaisesRegex(ValueError,'native order/window'):self.validate([first,last])

    def test_unused_or_gapped_code_payload_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Unreferenced bytes'):self.validate(code=self.body+b'JUNK')
        self.row['code_offset']='4'
        with self.assertRaisesRegex(ValueError,'unexplained bytes'):self.validate(code=b'JUNK'+self.body)

    def test_repeated_real_calls_share_one_complete_code_body(self):
        entries,report=self.validate([self.row,dict(self.row,timestamp='9')])
        self.assertEqual(len(entries),2)
        self.assertEqual(report['distinct_complete_code_bodies'],1)

    def test_duplicate_payload_for_one_body_digest_is_rejected(self):
        other=dict(self.row,timestamp='9',code_offset='8')
        with self.assertRaisesRegex(ValueError,'multiple retained offsets'):
            self.validate([self.row,other],code=self.body+self.body)

    def test_partial_word_or_unaligned_stack_is_rejected(self):
        self.row['a1']='FFFF'
        with self.assertRaisesRegex(ValueError,'observation word'):self.validate()
        self.row['a1']='FFFFFFFF';self.row['sp']='801FF004'
        with self.assertRaisesRegex(ValueError,'stack pointer'):self.validate()

    def test_noncontiguous_preceding_sequence_is_retained_as_unresolved(self):
        self.row['delay_pc']='80010008'
        _,report=self.validate()
        self.assertEqual(report['transfer_classifications'],{'unresolved_preceding_sequence':1})
        self.assertEqual(report['observed_transfer_edges'],[])

    def test_native_total_and_overflow_are_independent_of_drained_rows(self):
        entries,_=self.validate()
        settings=dict(frames=12,arm_frame=0,dispatch_targets=[dict(pc=self.pc,bytes=8)],dispatch_words=[4,8,12,16])
        native=dict(instruction_entries=1)
        summary=dict(hook_enabled=True,hook_enabled_relative_frame=0,native_overflow=0,event_bytes=4356,
            original_instruction_entries=1,native_total=1,drained_instruction_entries=1,
            target_entry_counts={'80010010':1},targets=settings['dispatch_targets'],memory_words=settings['dispatch_words'])
        inspector.validate_native_summary(summary,native,settings,entries)
        for key,value in (('native_total',2),('native_overflow',1),('event_bytes',4216)):
            wrong=dict(summary);wrong[key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'native totals'):
                inspector.validate_native_summary(wrong,native,settings,entries)
        with self.assertRaisesRegex(ValueError,'native totals'):
            inspector.validate_native_summary(summary,native,settings,[])


if __name__=='__main__':unittest.main()
