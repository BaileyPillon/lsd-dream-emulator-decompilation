"""Literal full-draw packet and context expectations without original assets."""
import struct
import unittest

from tools.tmd_renderer_model import (GPU,CONTEXT,ORDER,OUT,FORMATS,case_fixture,expected_draw,get)


class RendererModelTests(unittest.TestCase):
    def test_flat_unlit_triangle_packet_and_ordering_table_link(self):
        output,state,commands,outcome=expected_draw(dict(mode=0x21,flags=1))
        self.assertEqual(outcome,'submitted')
        self.assertEqual(struct.unpack_from('<5I',output[GPU]),
            (0x04FFFFFF,0x20332211,0xFFF8FFF8,0xFFF80008,0x0008FFF8))
        self.assertEqual(output[GPU][20:],bytes([0xD3])*(4096-20))
        self.assertEqual(get(output[ORDER],0x3FC),0xA1160000)
        self.assertEqual(get(output[OUT],0),GPU+20)
        self.assertEqual(commands,[0x4A280030,0x4B400006,0x4B58002D,0x4A780010])
        self.assertEqual(state.commands,4)

    def test_original_bbox_loop_excludes_the_final_vertex(self):
        output,_,_,_=expected_draw(dict(mode=0x21,flags=1))
        self.assertEqual(struct.unpack_from('<4h',output[CONTEXT],0x70),(-8,-8,8,-8))

    def test_hidden_object_preserves_all_initial_buffers_and_runs_no_commands(self):
        case=dict(mode=0x25,flags=1,attributes=0x80000000)
        _,initial,_=case_fixture(case)
        output,state,commands,outcome=expected_draw(case)
        self.assertEqual(output,initial)
        self.assertEqual((state.commands,commands,outcome),(0,[],'hidden'))

    def test_fog_rejection_retains_packet_storage_and_skips_color_commands(self):
        output,state,commands,outcome=expected_draw(dict(mode=0x25,flags=1,fog=4096))
        self.assertEqual(outcome,'depth_cue_rejected')
        self.assertEqual(output[GPU][8:],bytes([0xD3])*(4096-8))
        self.assertEqual(get(output[OUT],0),GPU)
        self.assertEqual((state.commands,len(commands)),(2,2))


try:
    import unicorn
except ImportError:
    unicorn=None


@unittest.skipUnless(unicorn,'Optional Unicorn synthetic backend is not installed')
class RendererPartialTransferTests(unittest.TestCase):
    def test_original_guard_executes_every_literal_merge_and_rejects_forbidden_accesses(self):
        from tools.verify_tmd_renderer import partial_transfer_checks
        self.assertEqual(partial_transfer_checks(),dict(literal_partial_transfer_programs_passed=32,
            forbidden_partial_transfers_rejected_without_memory_change=32))


if __name__=='__main__':unittest.main()
