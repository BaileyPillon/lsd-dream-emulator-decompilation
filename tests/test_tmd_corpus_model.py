"""Literal original-layout inputs, early returns and camera provenance bounds."""
import struct
import unittest

from tools.tmd_corpus_model import raw_fixture,raw_specs,camera_for,geometry_for
from tools.tmd_renderer_model import BUFFER,MODEL,GPU,GPU_BYTES,OUT,CONTEXT,expected_draw,get


def literal_tmd(lit=False,normal_index=0):
    """One descriptor with explicit record offsets and nonzero source padding."""
    data=bytearray(96)
    struct.pack_into('<III',data,0,0x41,0,1)
    struct.pack_into('<6Ii',data,12,28,4,60,1,68,1,0)
    for i,point in enumerate(((-128,-128,4096),(128,-128,4096),(-128,128,4096),(128,128,4096))):
        struct.pack_into('<4h',data,40+8*i,*point,100+i)
    struct.pack_into('<4h',data,72,256,768,4096,-1234)
    indices=(normal_index,0,1,2) if lit else (0,1,2,0xFEDC)
    struct.pack_into('<HBBI4H',data,80,0x0307,0 if lit else 1,0x20 if lit else 0x21,0x44332211,*indices)
    return bytes(data)


class CorpusModelTests(unittest.TestCase):
    def test_original_records_indices_and_ignored_padding_remain_exact(self):
        raw=literal_tmd()
        case=dict(raw_tmd=raw,geometry_index=0)
        data=raw_fixture(case)
        self.assertEqual(get(data,8),MODEL+12)
        self.assertEqual([get(data,MODEL-BUFFER+at) for at in (12,20,28)],
            [MODEL+40,MODEL+72,MODEL+80])
        mutable=set(range(4,8))|set(range(12,16))|set(range(20,24))|set(range(28,32))|{80,81}
        actual=data[MODEL-BUFFER:MODEL-BUFFER+len(raw)]
        self.assertTrue(all(actual[i]==raw[i] for i in range(len(raw)) if i not in mutable))
        self.assertEqual(struct.unpack_from('<H',actual,80)[0],1)
        spec=raw_specs(case)[0]
        self.assertEqual((spec['indices'],spec['colors']),((0,1,2),(0x44332211,)))

    def test_literal_original_TMD_predicts_known_packet_at_dynamic_pool_addresses(self):
        output,state,_,outcome=expected_draw(dict(raw_tmd=literal_tmd(),geometry_index=0))
        self.assertEqual(struct.unpack_from('<5I',output[GPU]),
            (0x04FFFFFF,0x20332211,0xFFF8FFF8,0xFFF80008,0x0008FFF8))
        self.assertEqual((get(output[CONTEXT],0xC),get(output[CONTEXT],0x10)),(MODEL+40,MODEL+72))
        self.assertEqual((get(output[OUT],0),state.commands,outcome),(GPU+20,4,'submitted'))

    def test_original_normal_index_bounds_are_checked_before_native_execution(self):
        with self.assertRaisesRegex(ValueError,'normal index exceeds its pool'):
            raw_specs(dict(raw_tmd=literal_tmd(lit=True,normal_index=1),geometry_index=0))

    def test_unsupported_original_mode_returns_without_staging_GPU_or_GTE_commands(self):
        for mode in (0x30,0x34,0x38,0x3C):
            for semi in (0,2):
                output,state,commands,outcome=expected_draw(dict(mode=mode|semi,flags=0))
                self.assertEqual((state.commands,commands,outcome),(0,[],'unsupported_mode_return'))
                self.assertEqual(output[GPU],bytes([0xD3])*GPU_BYTES)
                self.assertEqual(get(output[CONTEXT],0x18),mode<<8)
                self.assertEqual((state.draw_stats['mode_runs'],state.draw_stats['primitive_calls'],
                    state.draw_stats['unsupported_run_returns']),(1,0,1))

    def test_unsupported_middle_run_keeps_prior_output_and_skips_all_later_members(self):
        case=dict(packets=[dict(mode=0x21,flags=1),dict(mode=0x30,flags=0),dict(mode=0x21,flags=1)])
        output,state,commands,outcome=expected_draw(case)
        self.assertEqual((get(output[OUT],0),len(commands),outcome),(GPU+20,4,'unsupported_mode_return'))
        self.assertEqual(output[GPU][20:],bytes([0xD3])*(GPU_BYTES-20))
        self.assertEqual(state.draw_stats['outcomes'],['submitted'])
        self.assertEqual((state.draw_stats['mode_runs'],state.draw_stats['primitive_calls']),(2,1))

    def test_supplied_opposite_cameras_are_bounded_and_leave_source_unchanged(self):
        raw=literal_tmd()
        geometry=geometry_for(dict(raw_tmd=raw,geometry_index=0))
        first,second=camera_for(raw,geometry),camera_for(raw,geometry,True)
        self.assertEqual((len(first['matrix']),len(second['matrix']),first['h']),(9,9,512))
        self.assertTrue(all(-32768<=v<=32767 for v in first['matrix']+second['matrix']))
        self.assertNotEqual(first['matrix'],second['matrix'])
        self.assertEqual(raw,literal_tmd())


if __name__=='__main__':unittest.main()
