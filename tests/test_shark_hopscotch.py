"""Owned graph/rule fixtures; original MIPS/native GTE evidence is separate."""
from pathlib import Path
from types import SimpleNamespace
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import verify_shark_hopscotch as s


class SharkHopscotchTests(unittest.TestCase):
    def setUp(self):
        symbols={row['function']:int(row['address'],16) for row in s.FUNCTIONS}
        symbols.update(g_ENTITY_VTABLE=0x80100,g_DREAM_SYS_VTABLE=0x80200,
            g_BASE_CLASS_VTABLE=0x80300,g_RotateYawNine=0x80400,
            g_RotateYawNegNine=0x80500,g_OffsetOneTwoOne=0x80600)
        program=patch.object(s.n,'h',SimpleNamespace(symbols=symbols),create=True)
        rotation=patch.object(s.rotation,'rotation_bytes',return_value=struct.pack('<9h',
            4096,0,0,0,4096,0,0,0,4096))
        program.start()
        rotation.start()
        self.addCleanup(program.stop)
        self.addCleanup(rotation.stop)

    def result(self,callback,**updates):
        return s.expected(dict(s.base_case(callback),**updates))[0]

    @staticmethod
    def word(result,name,offset):
        return struct.unpack_from('<i',result[name],offset)[0]

    def test_embedded_context_matches_owner_entity_and_callback(self):
        for callback in s.CALLBACKS:
            with self.subTest(callback=callback):
                buffers=s.fixtures(s.base_case(callback))
                self.assertEqual(buffers['context'][0],s.n.ENTITY+0x9c)
                self.assertEqual(len(buffers['context'][1]),84)
                self.assertEqual(buffers['entity'][1][0x9c:0xf0],buffers['context'][1])
                self.assertEqual(struct.unpack_from('<I',buffers['context'][1],8)[0],s.n.ENTITY)
                self.assertEqual(struct.unpack_from('<I',buffers['context'][1],12)[0],s.n.h.symbols[callback])

    def test_shark_keeps_its_original_zero_radius(self):
        case=s.base_case('entity_shark')
        self.assertEqual(case['proximity'],0)
        s.validate_case(case)
        with self.assertRaises(ValueError):
            s.fixtures(dict(case,proximity=1))

    def test_invalid_native_widths_and_substituted_properties_are_rejected(self):
        base=s.base_case('entity_hopscotch_girl')
        for changes in ({'seed':True},{'seed':-1},{'seed':0x100000000},
                {'tick':0x80000000},{'frame':-0x80000001},{'entity_id':34},
                {'proximity':0},{'proximity_scale':0},{'has_dream':1},
                {'euler':(0,32768,0)},{'position':(0,0,0x80000000)}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                s.validate_case(dict(base,**changes))

    def test_shark_unsigned_turn_windows_have_exact_endpoints(self):
        for tick,yaw in ((-0x80000000,0),(399,0),(400,102),(409,102),(410,0),
                (699,0),(700,-102),(709,-102),(710,0),(829,0),(830,-102),(833,-102),(834,0)):
            with self.subTest(tick=tick):
                result=self.result('entity_shark',tick=tick)
                self.assertEqual(struct.unpack_from('<h',result['pose'],0x12)[0],yaw)

    def test_shark_speed_switches_at_800(self):
        for tick,amount in ((-1,-60),(799,-60),(800,-512),(0x7fffffff,-512)):
            with self.subTest(tick=tick):
                result=self.result('entity_shark',tick=tick)
                self.assertEqual(self.word(result,'coordinate',0x20),3000+amount)

    def test_disabling_clears_embedded_state_and_still_moves_that_call(self):
        result=self.result('entity_shark',tick=851)
        self.assertEqual(self.word(result,'context',0),0)
        self.assertEqual(self.word(result,'entity',0x9c),0)
        for offset in (0x8c,0x90,0xf0,0xf4,0xf8):
            self.assertEqual(self.word(result,'entity',offset),0)
        self.assertEqual(self.word(result,'coordinate',0x20),2488)
        labels=[row[0] for row in result['trace']]
        self.assertLess(labels.index('disable_link'),labels.index('forward'))

    def test_hopscotch_subtracts_32_once_instead_of_repeating_modulo(self):
        for frame,first,second in ((9,True,False),(17,True,False),(23,True,True),
                (41,True,False),(49,True,False),(55,True,True),(73,False,False),(87,False,False)):
            with self.subTest(frame=frame):
                result=self.result('entity_hopscotch_girl',frame=frame)
                self.assertEqual(self.word(result,'context',28)==19,first)
                self.assertEqual(self.word(result,'context',48)==19,second)

    def test_initial_rng_selects_nonuniform_scale_and_preserves_it_later(self):
        case=dict(s.base_case('entity_hopscotch_girl'),tick=0,seed=0,frame=0)
        first,_=s.expected(case)
        self.assertEqual(first['rng_seed'],12345)
        self.assertEqual(struct.unpack_from('<3i',first['pose'],0),(4096,8192,4096))
        later,_=s.expected(dict(case,tick=1,timer=17,frame=55),first)
        self.assertEqual(later['rng_seed'],12345)
        self.assertEqual(later['pose'],first['pose'])
        self.assertEqual(self.word(later,'context',4),17)
        self.assertEqual(self.word(later,'entity',0x84),55)
        self.assertEqual(self.word(later,'context',48),19)
        self.assertEqual(later['entity'][0x9c:0xf0],later['context'])

    def test_nonzero_tick_does_not_draw_rng(self):
        for tick in (-1,1,100):
            result=self.result('entity_hopscotch_girl',tick=tick,seed=42)
            self.assertEqual(result['rng_seed'],42)
            self.assertFalse(result['rng_trace'])

    def test_integer_ratio_at_radius_is_1024_and_outside_is_minus_one(self):
        for distance,ratio in ((40959,1023),(40960,1024),(40961,-1)):
            with self.subTest(distance=distance):
                result=self.result('entity_hopscotch_girl',position=(0,123,distance),player_position=(0,-999,0))
                self.assertEqual(self.word(result,'context',16),ratio)

    def test_missing_dream_preserves_commands_but_returns_minus_one_ratio(self):
        result=self.result('entity_hopscotch_girl',has_dream=False,frame=23)
        self.assertEqual(self.word(result,'context',16),-1)
        self.assertEqual(self.word(result,'context',28),19)
        self.assertEqual(self.word(result,'context',48),19)

    def test_evidence_output_must_be_private_before_backend_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'private .decomp-lab'):
                s.verify(Path(directory)/'evidence',Path(directory)/'missing.exe','unused')


if __name__=='__main__':
    unittest.main()
