"""Literal subdivision order, interpolation and workspace/control boundaries."""
import struct
import unittest

from tools.tmd_renderer_model import GPU,GPU_BYTES,CONTEXT,TRI,OUT,expected_draw,get

LARGE=((-1024,-1024,1024),(1024,-1024,1024),(-1024,1024,1024),(1024,1024,1024))


def case(mode=0x21,depth=1,**fields):
    return dict(mode=mode,flags=1,attributes=depth<<9,vertices=LARGE,ordering_head=0x00FFFFFF,**fields)


class RecursiveRendererTests(unittest.TestCase):
    def test_one_level_triangle_packet_order_and_links(self):
        output,state,_,outcome=expected_draw(case())
        expected=(0x04FFFFFF,0x20332211,0xFF000100,0,0xFF000000,
            0x04160000,0x20332211,0xFF000000,0,0x0000FF00,
            0x04160014,0x20332211,0xFF00FF00,0xFF000000,0x0000FF00,
            0x04160028,0x20332211,0x0100FF00,0x0000FF00,0)
        self.assertEqual(struct.unpack_from('<20I',output[GPU]),expected)
        self.assertEqual(output[GPU][80:],bytes([0xD3])*(GPU_BYTES-80))
        self.assertEqual((get(output[OUT],0),outcome),(GPU+80,'subdivided'))
        self.assertEqual((state.recursive_stats['nodes'],state.recursive_stats['packets']),(1,4))

    def test_recursive_visitation_order_and_saved_control_address(self):
        output,state,_,_=expected_draw(case(depth=2))
        self.assertEqual(struct.unpack_from('<5I',output[GPU]),
            (0x04FFFFFF,0x20332211,0xFF000000,0xFF80FF80,0xFF00FF80))
        self.assertEqual(get(output[TRI],0x10C),0x80019880)
        self.assertEqual((state.recursive_stats['nodes'],state.recursive_stats['packets']),(5,16))

    def test_gouraud_interpolation_retains_original_unused_alpha_bytes(self):
        output,_,_,_=expected_draw(case(mode=0x31))
        self.assertEqual(struct.unpack_from('<7I',output[GPU]),
            (0x06FFFFFF,0x30553377,0xFF000100,0xC5775566,0,0xC5442A44,0xFF000000))

    def test_flat_quad_and_gouraud_quad_preserve_different_center_rounding(self):
        odd=((-1025,-1023,1025),(1024,-1022,1024),(-1024,1024,1025),(1025,1023,1024))
        flat=case(mode=0x29)
        flat['vertices']=odd
        gouraud={**flat,'mode':0x39}
        _,a,_,_=expected_draw(flat)
        _,b,_,_=expected_draw(gouraud)
        self.assertEqual(a.dr[4],0x0000FFFF)
        self.assertEqual(b.dr[4],0)

    def test_near_plane_cull_keeps_staged_packet_and_output_cursor(self):
        near=case()
        near['vertices']=((-256,-256,64),(256,-256,64),(-256,256,64),(256,256,64))
        output,state,commands,outcome=expected_draw(near)
        self.assertEqual(outcome,'recursive_culled')
        self.assertEqual(get(output[OUT],0),GPU)
        self.assertEqual(state.recursive_stats['culled'],{'near':1})
        self.assertEqual(len(commands),4)

    def test_out_of_profile_depth_is_rejected_without_silent_clamping(self):
        with self.assertRaisesRegex(ValueError,'bounded original subdivision limit'):
            expected_draw(case(depth=6))


if __name__=='__main__':unittest.main()
