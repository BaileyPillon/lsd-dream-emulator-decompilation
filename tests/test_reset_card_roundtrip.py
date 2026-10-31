"""Card, causal-callback and complete-output guards without game assets."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from tests.test_card_roundtrip import blank_card, install
from tests.test_controller_reset_capture import fixture
from tools.verify_reset_card_roundtrip import (
    DEFAULT_TARGETS, card_records, compare_captures, core_evidence,
    successful_card_callbacks,
)


def evidence():
    _,snap=fixture();snap['frame']=0
    report=dict(mode='load',status='native_cold_load_and_new_dream_completed',
        observer_enabled=False,cold_start=True,load_seen=True,load_returned=True,
        guest_RAM_or_instruction_writes=False,restored_state=False,
        player_UI_or_saves_changed=False,hardware_timing_verified=False,
        frames_advanced=1,last_frame=0,replay_entries_used=0,replay_entries_supplied=0,
        total_PCM_sample_frames=5,native_entries=0,native_entry_counts={},
        sequence_start=-1,reset_frame=-1,post_dream_frame=0,
        final_SaveRAM_sha256='b'*64,final_state={},initial_load_idle_frame=0,
        save_seen_frame=-1,save_idle_frame=-1,reset_seen=False,post_menu_seen=True,
        post_dream_seen=True,save_seen=False,save_idle=False,
        pre_load_payload_sha256='a'*64,expected_loaded_payload_sha256='c'*64,
        target_filename='BISLPS-01556-02',reset_payload_sha256=None,
        saved_payload_sha256=None,saved_filename=None,input_card_sha256='b'*64,
        native_saved_card_sha256=None,external_card_unchanged=True,
        final_card_matches_native_Save=False,reset_payload_matches_saved_payload=True)
    sizes=dict(MainRAM=0x200000,GPURAM=0x100000,RGB=4,PCM=20,native=2,controller=4)
    return dict(report=report,inputs=b'frame\tmask\n0\t0\n',snapshots=[snap],entries=[],
        windows=[dict(first_frame=0,last_frame=0,frames=1,PCM_sample_frames=5,
            payload_bytes=sizes,framed_sha256={name:'a'*64 for name in sizes})],
        transitions=[dict(frame=0,selection=dict(names=['BISLPS-01556-01','BISLPS-01556-02'],index=1))],
        **{'card-store':{}})


class CompleteCardTests(unittest.TestCase):
    def test_two_files_and_last_payload_byte_are_retained(self):
        raw=install(install(blank_card()),block=2,name=b'BISLPS-01556-02')
        raw[2*8192+2303]=0xab
        files=card_records(raw)
        self.assertEqual(list(files),['BISLPS-01556-01','BISLPS-01556-02'])
        self.assertEqual(files['BISLPS-01556-02']['payload'][-1],0xab)
        self.assertEqual(len(files['BISLPS-01556-01']['body']),8192)

    def test_non_lsd_header_is_rejected_in_second_file(self):
        raw=install(install(blank_card()),block=2,name=b'BISLPS-01556-02')
        raw[2*8192+2]^=1
        with self.assertRaisesRegex(ValueError,'card header'):
            card_records(raw)

    def test_wrong_payload_marker_is_rejected_in_second_file(self):
        raw=install(install(blank_card()),block=2,name=b'BISLPS-01556-02')
        raw[2*8192+512]^=1
        with self.assertRaisesRegex(ValueError,'save marker'):
            card_records(raw)


class CardCaptureStructureTests(unittest.TestCase):
    def check(self,data):
        return core_evidence(data,'load',json.loads(DEFAULT_TARGETS.read_bytes()),False)

    def test_complete_stream_metadata_is_accepted(self):
        objects,totals=self.check(evidence())
        self.assertEqual(len(objects),1)
        self.assertEqual(totals['PCM'],20)

    def test_missing_pcm_count_is_rejected(self):
        data=evidence();del data['windows'][0]['payload_bytes']['PCM']
        with self.assertRaisesRegex(ValueError,'channel byte count'):
            self.check(data)

    def test_missing_gpu_bytes_is_rejected(self):
        data=evidence();data['windows'][0]['payload_bytes']['GPURAM']-=4
        with self.assertRaisesRegex(ValueError,'window payload'):
            self.check(data)

    def test_duplicate_object_frame_is_rejected(self):
        data=evidence();data['snapshots']*=2
        with self.assertRaisesRegex(ValueError,'object frame order'):
            self.check(data)

    def test_controller_input_after_capture_is_rejected(self):
        data=evidence();data['inputs']+=b'1\t1\n'
        with self.assertRaisesRegex(ValueError,'Controller frame'):
            self.check(data)


class CardCallbackTests(unittest.TestCase):
    def callbacks(self):
        return {'entries':[
            dict(name='func_8004E230',a2=22,frame=12,receiver_words=[0x80086b60]),
            dict(name='dream_sys_clear_new_game',frame=12,a0=0x80091530,ra=0x8004e2a0)]}

    def test_success_runs_original_flag_clear_in_same_frame(self):
        self.assertEqual(len(successful_card_callbacks(self.callbacks(),1,0x80091530)),1)

    def test_wrong_success_code_is_rejected(self):
        data=self.callbacks();data['entries'][0]['a2']=21
        with self.assertRaisesRegex(ValueError,'callback cardinality'):
            successful_card_callbacks(data,1,0x80091530)

    def test_delayed_clear_is_rejected(self):
        data=self.callbacks();data['entries'][1]['frame']+=1
        with self.assertRaisesRegex(ValueError,'original flag clear'):
            successful_card_callbacks(data,1,0x80091530)

    def test_wrong_clear_receiver_is_rejected(self):
        data=self.callbacks();data['entries'][1]['a0']+=4
        with self.assertRaisesRegex(ValueError,'original flag clear'):
            successful_card_callbacks(data,1,0x80091530)


class CompletePairTests(unittest.TestCase):
    def test_native_file_chooser_transition_is_not_masked(self):
        left=evidence();right=copy.deepcopy(left)
        right['transitions'][0]['selection']['index']=0
        with self.assertRaisesRegex(ValueError,'menu transitions'):
            compare_captures(left,right,Path('.'),Path('.'))

    def test_native_read_arguments_are_not_masked(self):
        left=evidence();left['entries']=[dict(a3=1792)]
        right=copy.deepcopy(left);right['entries'][0]['a3']=1791
        with self.assertRaisesRegex(ValueError,'entry records'):
            compare_captures(left,right,Path('.'),Path('.'))

    def test_unallocated_card_byte_is_compared(self):
        left=evidence();left['report']['mode']='save';right=copy.deepcopy(left)
        with tempfile.TemporaryDirectory() as temporary:
            a=Path(temporary)/'left';b=Path(temporary)/'right';a.mkdir();b.mkdir()
            raw=blank_card();(a/'saved-card.SaveRAM').write_bytes(raw)
            raw[-1]^=1;(b/'saved-card.SaveRAM').write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'native-written cards'):
                compare_captures(left,right,a,b)


if __name__=='__main__':
    unittest.main()
