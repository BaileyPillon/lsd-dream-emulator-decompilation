"""Owned graph fixtures and verifier rejection checks; no original game needed."""
from pathlib import Path
from types import SimpleNamespace
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import verify_hanged_woman as s


class HangedWomanTests(unittest.TestCase):
    def setUp(self):
        names=('g_ENTITY_VTABLE','g_DREAM_SYS_VTABLE','g_BASE_CLASS_VTABLE',
               'D_800878D4',s.CALLBACK,'g_RotateRollNeg90Yaw270')
        program=patch.object(s.n,'h',SimpleNamespace(symbols={name:0x801000+i*0x100 for i,name in enumerate(names)}),create=True)
        program.start();self.addCleanup(program.stop)

    @staticmethod
    def word(data,offset):return struct.unpack_from('<I',data,offset)[0]

    def test_context_aliases_the_owner_and_names_the_callback(self):
        graph=s.fixtures(s.base_case());address,context=graph['context']
        self.assertEqual((address,len(context)),(s.n.ENTITY+0x9c,84))
        self.assertEqual(graph['entity'][1][0x9c:0xf0],context)
        self.assertEqual(self.word(context,8),s.n.ENTITY)
        self.assertEqual(self.word(context,12),s.n.h.symbols[s.CALLBACK])

    def test_held_object_is_slot_one_with_flags_at_transform_offset_16(self):
        graph=s.fixtures(dict(s.base_case(),held_flags=0x12345678))
        self.assertEqual(self.word(graph['entity'][1],0x70),s.HELD_LIST)
        self.assertEqual(self.word(graph['held_list'][1],4),s.HELD)
        self.assertEqual(self.word(graph['held_object'][1],0x10),0x12345678)
        self.assertEqual(graph['held_object'][1][0xc:0x10],bytes([0xa3])*4)

    def test_player_pose_pointer_has_a_separate_backing_buffer(self):
        graph=s.fixtures(dict(s.base_case(),player_euler=(1,-2,3)))
        self.assertEqual(self.word(graph['player_coordinate'][1],0x44),graph['player_pose'][0])
        self.assertNotEqual(graph['player_pose'][0],graph['pose'][0])
        self.assertEqual(struct.unpack_from('<3h',graph['player_pose'][1],0x10),(1,-2,3))

    def test_substituted_bindings_missing_dream_and_wrong_widths_fail(self):
        for changes in ({'entity_id':57},{'proximity':29},{'has_dream':False},
                {'move_mode':True},{'move_mode':3},{'held_flags':-1},{'held_flags':True},
                {'held_flags':0x100000000},{'tick':0x80000000},{'seed':-1},
                {'player_euler':(0,32768,0)},{'player_scale':(0,0,0x80000000)},
                {'chunk_mood':(0,0,-0x80000000,0,-1)}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                s.validate_case(dict(s.base_case(),**changes))

    def test_input_identity_uses_initialized_bytes_and_seed(self):
        base=s.base_case();key=s.input_key(base)
        self.assertEqual(key,s.input_key(dict(base,unconsumed_python_note='not a distinct native fixture')))
        for changes in ({'seed':1},{'held_flags':0},{'move_mode':2},{'timer':2}):
            with self.subTest(changes=changes):self.assertNotEqual(key,s.input_key(dict(base,**changes)))

    def test_yellow_arms_state_eleven_without_consuming_rng(self):
        result,_=s.expected(dict(s.base_case(),tick=0,seed=42,chunk_mood=(-4,-4,0,0,0)))
        self.assertEqual(self.word(result['entity'],0x44),11)
        self.assertEqual(result['rng_seed'],42)
        self.assertEqual(result['rng_trace'],[])

    def test_nonyellow_rng_selection_has_known_native_lcg_steps(self):
        for seed,expected_seed,state in ((0,12345,12),(1,1103527590,0)):
            with self.subTest(seed=seed):
                result,_=s.expected(dict(s.base_case(),tick=0,seed=seed))
                self.assertEqual(result['rng_seed'],expected_seed)
                self.assertEqual(self.word(result['entity'],0x44),state)

    def test_exact_1024_distance_does_not_lock_controls(self):
        result,commands=s.expected(dict(s.base_case(),state=11,position=(1024,0,0),player_position=(0,0,0)))
        self.assertEqual(self.word(result['entity'],0x44),11)
        self.assertEqual(self.word(result['dream'],0x9c),1)
        self.assertEqual(commands,[])

    def test_day_end_is_a_single_request_at_tick_500(self):
        for tick,trace in ((500,[['notify',s.n.ENTITY,12]]),(501,[])):
            with self.subTest(tick=tick):
                result,commands=s.expected(dict(s.base_case(),state=13,tick=tick))
                self.assertEqual(result['trace'],trace);self.assertEqual(commands,[])

    def test_native_output_requires_a_fresh_private_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):s.verify(Path(temporary),'unused','unused')
            with self.assertRaises(ValueError):s.verify(Path(temporary)/'outside-private','unused','unused')

if __name__=='__main__':unittest.main()
