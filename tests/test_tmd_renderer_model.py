"""Literal full-draw packet and context expectations without original assets."""
import struct
import unittest

from tools.tmd_renderer_model import (GPU,GPU_BYTES,CONTEXT,ORDER,OUT,FORMATS,PRIM,BUFFER,
    case_fixture,expected_draw,get)


class RendererModelTests(unittest.TestCase):
    def test_flat_unlit_triangle_packet_and_ordering_table_link(self):
        output,state,commands,outcome=expected_draw(dict(mode=0x21,flags=1))
        self.assertEqual(outcome,'submitted')
        self.assertEqual(struct.unpack_from('<5I',output[GPU]),
            (0x04FFFFFF,0x20332211,0xFFF8FFF8,0xFFF80008,0x0008FFF8))
        self.assertEqual(output[GPU][20:],bytes([0xD3])*(GPU_BYTES-20))
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
        self.assertEqual(output[GPU][8:],bytes([0xD3])*(GPU_BYTES-8))
        self.assertEqual(get(output[OUT],0),GPU)
        self.assertEqual((state.commands,len(commands)),(2,2))

    def test_two_primitive_link_and_color_history_match_literal_original_probe(self):
        case=dict(packets=[dict(mode=0x21,flags=1,colors=(color,)) for color in (0x44332211,0x66554433)])
        output,state,commands,outcome=expected_draw(case)
        self.assertEqual(struct.unpack_from('<10I',output[GPU]),
            (0x04FFFFFF,0x20332211,0xFFF8FFF8,0xFFF80008,0x0008FFF8,
             0x04160000,0x20554433,0xFFF8FFF8,0xFFF80008,0x0008FFF8))
        self.assertEqual((get(output[OUT],0),get(output[ORDER],0x3FC)),(GPU+40,0xA1160014))
        self.assertEqual((state.commands,state.data_writes,len(commands),outcome),(8,14,8,'primitive_run'))
        self.assertEqual((state.draw_stats['mode_runs'],state.draw_stats['primitive_calls']),(1,2))

    def test_later_culled_member_retains_stale_code_and_stages_only_length_byte(self):
        case=dict(packets=[dict(mode=0x21,flags=1),dict(mode=0x21,flags=1,indices=(0,2,1))])
        output,state,commands,_=expected_draw(case)
        self.assertEqual(struct.unpack_from('<2I',output[GPU],20),(0x04D3D3D3,0xD3D3D3D3))
        self.assertEqual(get(output[OUT],0),GPU+20)
        self.assertEqual((state.commands,len(commands)),(6,6))
        self.assertEqual(state.draw_stats['outcomes'],['submitted','backface_or_degenerate'])

    def test_textured_lit_run_initializes_RGB_once(self):
        _,state,commands,_=expected_draw(dict(packets=[dict(mode=0x24,flags=0)]*2))
        self.assertEqual((state.data_writes,len(commands)),(17,8))

    def test_mode_changes_split_runs_and_preserve_ignored_interior_counts(self):
        specs=[dict(mode=mode,flags=1,ignored_count=0xBEEF) for mode in (0x21,0x23,0x23,0x21)]
        case=dict(packets=specs)
        data,_,_=case_fixture(case)
        self.assertEqual([struct.unpack_from('<H',data,PRIM-BUFFER+16*i)[0] for i in range(4)],
            [1,2,0xBEEF,1])
        _,state,_,_=expected_draw(case)
        self.assertEqual((state.draw_stats['mode_runs'],state.draw_stats['primitive_calls']),(3,4))

    def test_incompatible_flags_and_out_of_pool_indices_fail_before_execution(self):
        with self.assertRaisesRegex(ValueError,'compatible flags'):
            case_fixture(dict(packets=[dict(mode=0x20,flags=0),dict(mode=0x20,flags=4)]))
        with self.assertRaisesRegex(ValueError,'outside its supplied pools'):
            case_fixture(dict(packets=[dict(mode=0x21,flags=1,indices=(0,1,4))]))


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
