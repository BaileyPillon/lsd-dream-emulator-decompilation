"""Synthetic checks for original collision arithmetic and reporting boundaries."""
import contextlib
import io
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import verify_collision as collision


def synthetic_lookup(address):
    index = 64 + (address-collision.SQRT_TABLE)//2
    return math.isqrt(index << 18)


TRIANGLE = ((-1024,-1024,0),(1024,-1024,0),(-1024,1024,0))


class CollisionTests(unittest.TestCase):
    def test_native_cross_product_smoke_values(self):
        result = collision.command_model([1,0,2,0,3],[4,5,6],collision.OP)
        self.assertEqual(result,dict(mac=[-3,6,-3],ir=[-3,6,-3],flags=0,command_cycles_minus_one=5))

    def test_native_square_smoke_values_and_flags(self):
        result = collision.command_model([0]*5,[-32768,32767,-1],collision.SQR)
        self.assertEqual(result,dict(mac=[1073741824,1073676289,1],ir=[32767,32767,1],
                                     flags=0x81800000,command_cycles_minus_one=4))

    def test_square_narrows_full_word_inputs(self):
        self.assertEqual(collision.command_model([0]*5,[65537,-32769,-2147483648],collision.SQR)['mac'],
                         [1,1073676289,0])

    def test_ir3_saturation_does_not_set_summary_bit(self):
        result = collision.command_model([256,0,0,0,0],[0,256,0],collision.OP)
        self.assertEqual(result['mac'],[0,0,65536])
        self.assertEqual(result['flags'],0x400000)

    def test_leading_counter_counts_sign_bits(self):
        self.assertEqual([collision.leading_bits(v) for v in (0,1,-1,-2147483648,0xFFFF0000)],
                         [32,31,32,1,16])

    def test_zero_and_negative_one_sqrt_do_not_read_table(self):
        for value in (0,-1):
            with self.subTest(value=value):
                self.assertEqual(collision.sqrt_model(value,lambda _:self.fail('unexpected table read')),0)

    def test_negative_sqrt_retains_outside_positive_table_index(self):
        reads = []
        collision.sqrt_model(-2147483648,lambda address:reads.append(address) or 4096)
        self.assertEqual(reads,[collision.SQRT_TABLE-384])

    def test_signed_fraction_truncates_toward_zero(self):
        self.assertEqual(collision.fraction_fixed(1,2),32768)
        self.assertEqual(collision.fraction_fixed(-1,2),-2147450880)
        self.assertEqual(collision.fraction_fixed(3,2),98304)
        with self.assertRaises(ValueError):
            collision.fraction_fixed(1,0)

    def test_sqrt_fixture_domain_is_unique_and_includes_both_signs(self):
        values = collision.sqrt_cases()
        self.assertEqual(len(values),len(set(values)))
        self.assertIn(0x80000000,values)
        self.assertIn(0x7FFFFFFF,values)

    def test_triangle_test_uses_expanded_bounds(self):
        # This point is outside the triangle but inside its expanded AABB.
        result = collision.primitive_model((TRIANGLE,),(900,900,-1024),(900,900,1024),synthetic_lookup)
        self.assertEqual(result,(1,1024,(900,900,0),1924))
        self.assertEqual(collision.primitive_model((TRIANGLE,),(1048,0,-1024),(1048,0,1024),synthetic_lookup)[0],1)
        self.assertEqual(collision.primitive_model((TRIANGLE,),(1049,0,-1024),(1049,0,1024),synthetic_lookup)[0],0)

    def test_height_is_not_travel_distance(self):
        result = collision.primitive_model((TRIANGLE,),(0,512,-1024),(0,512,1024),synthetic_lookup)
        self.assertEqual(result,(1,1024,(0,512,0),1536))

    def test_parallel_and_empty_models_leave_contact_unspecified(self):
        self.assertEqual(collision.primitive_model((),(0,0,-1024),(0,0,1024),synthetic_lookup),
                         (0,2147483647,None,None))
        self.assertEqual(collision.primitive_model((TRIANGLE,),(0,0,0),(100,100,0),synthetic_lookup),
                         (0,2147483647,None,None))

    def test_equal_nearest_distance_retains_first_height(self):
        second = ((-1024,-2048,0),(1024,-2048,0),(-1024,2048,0))
        self.assertEqual(collision.primitive_model((TRIANGLE,second),(0,0,-1024),(0,0,1024),synthetic_lookup),
                         (1,1024,(0,0,0),1024))

    def test_clip_segment_return_codes_and_tangent(self):
        box = ((-2,-2,-2),(2,2,2))
        for a,b,expected in (((0,0,0),(1,1,1),1),((0,0,0),(4,0,0),2),
                             ((4,0,0),(0,0,0),3),((4,4,4),(5,5,5),0),((-4,2,0),(4,2,0),3)):
            with self.subTest(a=a,b=b):
                self.assertEqual(collision.clip_segment(box,a,b),expected)

    def test_cube_face_permutation_and_halfword_wrap(self):
        points = collision.cube_points(((-1,-2,-32768),(3,4,32767)))
        self.assertEqual(collision.transform_cube(points,0,1,1)[4],(-1,-2,-32768))
        flipped = collision.transform_cube(points,1,0,10)
        self.assertEqual(flipped[0],(9,-2,32767))
        self.assertEqual(flipped[7],points[3])

    def test_height_filter_can_reject_after_contact_was_written(self):
        polygon = ((-1024,-512,0),(1024,-512,0),(-1024,512,0))
        cloud = [collision.cube_points(((-128,-256,-1024),(128,0,1024)))]
        self.assertEqual(collision.transform_model((polygon,),cloud,1,0,synthetic_lookup,(7,8,9)),
                         (1,1,1,(0,-128,0)))
        self.assertEqual(collision.transform_model((polygon,),cloud,1,1,synthetic_lookup,(7,8,9)),
                         (0,0,0,(128,0,0)))

    def test_global_loop_count_reuses_same_bounds_and_masks(self):
        cloud = [collision.cube_points(((-128,-128,-1024),(128,128,1024)))]
        self.assertEqual(collision.transform_model((TRIANGLE,),cloud,2,0,synthetic_lookup,(7,8,9)),
                         (1,3,1,(0,0,0)))
        self.assertEqual(collision.transform_model((TRIANGLE,),cloud,0,0,synthetic_lookup,(7,8,9)),
                         (0,0,0,(7,8,9)))

    def test_existing_evidence_is_rejected_before_loading_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = root/'.decomp-lab/report.json'
            report.parent.mkdir()
            for path in (report,report.with_suffix('.log'),report.with_name('report-stderr.log'),
                         report.with_name('report-failure.json')):
                path.write_bytes(b'prior evidence')
                with patch.object(collision,'ROOT',root),patch.object(collision,'verify') as verify, \
                        contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(collision.main(['--output',str(report),'--bridge','unused.exe',
                        '--runtime','unused','--ranges','unused.json']),2)
                    verify.assert_not_called()
                self.assertEqual(path.read_bytes(),b'prior evidence')
                path.unlink()

    def test_public_report_is_rejected_before_loading_inputs(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(collision,'ROOT',Path(folder)), \
                patch.object(collision,'verify') as verify,contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(collision.main(['--output','public.json','--bridge','unused.exe',
                '--runtime','unused','--ranges','unused.json']),2)
            verify.assert_not_called()


if __name__ == '__main__':
    unittest.main()
