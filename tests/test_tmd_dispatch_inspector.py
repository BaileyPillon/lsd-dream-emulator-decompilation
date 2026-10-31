"""Literal dispatch masks and early-return stream boundaries without assets."""
from types import SimpleNamespace
import unittest

from tools.inspect_tmd_dispatch import dispatch_summary


def packet(mode,flags):return SimpleNamespace(mode=mode,flags=flags)


class DispatchInspectorTests(unittest.TestCase):
    def test_original_mask_ignores_transparency_and_high_flag_bits(self):
        result=dispatch_summary([packet(0x21,1),packet(0x23,0x81),packet(0x22,0x84)])
        self.assertEqual((result['source_packets'],result['unsupported_packets'],
            result['predicted_primitive_setup_calls'],result['predicted_unvisited_tail_packets']),(3,0,3,0))

    def test_unsupported_format_stops_before_later_supported_packets(self):
        result=dispatch_summary([packet(0x29,1),packet(0x3C,0),packet(0x2D,1),packet(0x38,0)])
        self.assertEqual((result['unsupported_packets'],result['first_unsupported_ordinal'],
            result['predicted_primitive_setup_calls'],result['predicted_unvisited_tail_packets']),(2,1,1,3))

    def test_empty_stream_has_no_abort_or_primitive_calls(self):
        result=dispatch_summary([])
        self.assertIsNone(result['first_unsupported_ordinal'])
        self.assertEqual((result['source_packets'],result['predicted_unvisited_tail_packets']), (0,0))


if __name__=='__main__':unittest.main()
