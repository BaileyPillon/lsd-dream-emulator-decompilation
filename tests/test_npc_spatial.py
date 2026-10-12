"""Spatial state checks with synthetic coefficients and object buffers."""
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import verify_npc_spatial as spatial


class NpcSpatialModelTests(unittest.TestCase):
    def setUp(self):
        names=('g_ENTITY_VTABLE','g_DREAM_SYS_VTABLE','g_OffsetTwo','g_OffsetHalf',
               'g_OffsetSix','g_MoveDown64Then32','g_MoveUp64')
        self.symbols={name:0x80010000+16*i for i,name in enumerate(names)}
        data={self.symbols['g_OffsetTwo']:struct.pack('<6h',2,1,2,1,2,1),
              self.symbols['g_OffsetHalf']:struct.pack('<6h',1,2,1,2,1,2),
              self.symbols['g_OffsetSix']:struct.pack('<6h',6,1,6,1,6,1),
              self.symbols['g_MoveDown64Then32']:struct.pack('<3i',0,-64,0),
              self.symbols['g_MoveUp64']:struct.pack('<3i',0,64,0)}
        target=lambda address,length:data[address][:length]
        self.program=patch.object(spatial.n,'h',SimpleNamespace(symbols=self.symbols,target=target),create=True)
        self.program.start();self.addCleanup(self.program.stop)
        pairs=[(0,4096)]*4096;pairs[1024]=(4096,0)
        self.trig=patch.object(spatial,'pairs',tuple(pairs));self.trig.start();self.addCleanup(self.trig.stop)

    def case(self,**changes):
        value=dict(timer=1,tick=0,frame=1,duration=15,state=0,variant=0,
                   action=0,seed=0,ratio=99,nudge=-19)
        value.update(changes);return value

    def position(self,result):
        return struct.unpack_from('<3i',result['coordinate'],0x18)

    def test_giant_fish_replaces_three_scales_and_invalidates_cached_coordinate(self):
        result,commands=spatial.model('entity_fish_giant',self.case(scale=(-4096,8192,2048)))
        self.assertEqual(struct.unpack_from('<3i',result['pose']), (24576,24576,24576))
        self.assertEqual(struct.unpack_from('<I',result['coordinate'])[0],0)
        self.assertEqual(self.position(result),(1000,2000,3000))
        self.assertEqual(commands,[])

    def test_elephant_uses_first_vector_not_the_following_translation_record(self):
        result,commands=spatial.model('entity_elephant',self.case())
        self.assertEqual(self.position(result),(1000,1936,3000))
        self.assertEqual(commands,[])

    def test_quarter_turn_rotates_small_elephant_forward_into_world_x(self):
        result,commands=spatial.model('entity_elephant_small',self.case(euler=(0,1024,0)))
        self.assertEqual(self.position(result),(990,2000,3000))
        self.assertEqual(struct.unpack_from('<3i',result['pose']),(2048,2048,2048))
        self.assertEqual(len(commands),2)
        self.assertEqual(struct.unpack_from('<h',result['entity'],0x48)[0],-10)

    def test_fish_accumulates_all_three_axes_and_the_translation_request(self):
        result,commands=spatial.model('entity_fish',self.case())
        self.assertEqual(self.position(result),(936,1872,2872))
        self.assertEqual(len(commands),6)
        self.assertEqual(struct.unpack_from('<h',result['entity'],0x48)[0],-128)

    def test_signed_translation_wraps_at_native_word_width(self):
        result,_=spatial.model('entity_fish',self.case(position=(1000,-0x80000000,3000)))
        self.assertEqual(self.position(result)[1],0x7fffff80)

    def test_spatial_buffer_guards_and_unmodified_pose_fields_remain_preserved(self):
        case=self.case()
        result,_=spatial.model('entity_fish',case)
        coord,pose=spatial.fixtures(case)
        self.assertEqual(result['coordinate'][0x50:],bytes(coord[0x50:]))
        self.assertEqual(result['pose'][0xc:],bytes(pose[0xc:]))

    def test_spatial_operations_are_executed_not_retained_as_output_contracts(self):
        result,_=spatial.model('entity_fish',self.case())
        self.assertEqual(result['trace'],[])

    def test_full_fish_cycle_is_retained_with_additional_pose_contexts(self):
        cases=list(spatial.cases('entity_fish'))
        base=[case for group,case in cases if group=='existing_control_phases']
        self.assertEqual(len(base),24015)
        self.assertEqual([case['tick'] for case in base[:24000]],list(range(24000)))
        self.assertTrue(any(case.get('euler')==(0,-1024,0) for group,case in cases))


if __name__=='__main__':unittest.main()
