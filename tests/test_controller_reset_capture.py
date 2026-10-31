"""Reject damaged evidence without requiring proprietary game data or an emulator."""
import base64
import copy
import hashlib
import struct
import unittest

from tools.verify_controller_reset_capture import DEFAULT_TABLE, paired, snapshot_object


def fixture():
    data=bytearray(0x928)
    struct.pack_into('<I',data,0,0x80087bdc)
    struct.pack_into('<I',data,0x180,2)
    data[0x190]=0x37
    digest=hashlib.sha256(data[0x178:0x878]).hexdigest()
    return data,dict(object_base64=base64.b64encode(data).decode(),save_sha256=digest,
        state=dict(day=2,year=0,saveHash=digest),pad_table=list(DEFAULT_TABLE))


class SnapshotEvidenceTests(unittest.TestCase):
    def test_complete_object_keeps_inactive_history(self):
        raw,snap=fixture()
        self.assertEqual(snapshot_object(snap),raw)
        self.assertEqual(snapshot_object(snap)[0x190],0x37)

    def test_truncated_object_is_rejected(self):
        raw,snap=fixture();snap['object_base64']=base64.b64encode(raw[:-1]).decode()
        with self.assertRaisesRegex(ValueError,'Truncated'):
            snapshot_object(snap)

    def test_payload_change_without_matching_digest_is_rejected(self):
        raw,snap=fixture();raw[0x190]^=1;snap['object_base64']=base64.b64encode(raw).decode()
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            snapshot_object(snap)

    def test_wrong_native_object_is_rejected(self):
        raw,snap=fixture();raw[0]^=1;snap['object_base64']=base64.b64encode(raw).decode()
        with self.assertRaisesRegex(ValueError,'field mismatch'):
            snapshot_object(snap)

    def test_decoded_day_cannot_disagree_with_native_bytes(self):
        _,snap=fixture();snap['state']['day']=3
        with self.assertRaisesRegex(ValueError,'field mismatch'):
            snapshot_object(snap)

    def test_changed_runtime_button_mapping_is_rejected(self):
        _,snap=fixture();snap['pad_table'][10]=2
        with self.assertRaisesRegex(ValueError,'controller table'):
            snapshot_object(snap)

    def test_malformed_base64_is_rejected(self):
        _,snap=fixture();snap['object_base64']='%%%'
        with self.assertRaises(ValueError):
            snapshot_object(snap)


class PairEvidenceTests(unittest.TestCase):
    def example(self):
        return {'inputs':b'frame\tmask\n0\t0\n','windows':[{'framed_sha256':{'PCM':'a'*64}}],
            'snapshots':[],'card-store':{},'report':dict(frames_advanced=1,sequence_start=0,
            reset_frame=0,post_dream_frame=0,final_SaveRAM_sha256='b'*64,final_state={},total_PCM_sample_frames=5)}

    def test_changed_audio_digest_is_rejected(self):
        original=self.example();other=copy.deepcopy(original)
        other['windows'][0]['framed_sha256']['PCM']='c'*64
        with self.assertRaisesRegex(ValueError,'aggregates differ'):
            paired(original,other)

    def test_changed_controller_schedule_is_rejected(self):
        original=self.example();other=copy.deepcopy(original);other['inputs']+=b'1\t8\n'
        with self.assertRaisesRegex(ValueError,'submissions differ'):
            paired(original,other)


if __name__=='__main__':
    unittest.main()
