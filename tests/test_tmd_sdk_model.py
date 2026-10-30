"""Independent literal fixtures for pointer relocation and SDK run headers."""
import json
from pathlib import Path
import struct
import unittest

from tools.tmd_sdk_model import link_tmd, map_tmd, sdk_packet_bytes

FIXTURES = Path(__file__).resolve().parents[1]/'research/model_packets/sdk-link-fixtures.json'


def make_tmd(objects, flags=0x80):
    raw = bytearray(12 + 28*len(objects))
    struct.pack_into('<III', raw, 0, 0x41, flags, len(objects))
    starts = []
    for index, packets in enumerate(objects):
        raw.extend(b'\x96'*8)
        start = len(raw)
        starts.append(start)
        for mode, packet_flags, size in packets:
            packet = bytearray(b'\xa5'*size)
            packet[:4] = bytes((0x55, 0xAA, packet_flags, mode))
            raw.extend(packet)
        raw.extend(b'\x97'*8)
        # Distinct metadata must survive; these profiles do not dereference arrays.
        struct.pack_into('<6Ii', raw, 12 + 28*index,
                         start-12, 0, start-12, 0, start-12, len(packets), -index-1)
    return bytes(raw), starts


class TmdSdkModelTests(unittest.TestCase):
    def test_pointer_base_is_first_object_not_current_descriptor(self):
        raw, starts = make_tmd([[(0x20, 0, 16)], [(0x24, 0, 24)]])
        for address in (0x101000, 0x80101000):
            actual = map_tmd(raw, address)
            expected = bytearray(raw)
            struct.pack_into('<I', expected, 4, 0x81)
            for index, start in enumerate(starts):
                for field in (0, 8, 16):
                    struct.pack_into('<I', expected, 12+28*index+field, address+start)
            self.assertEqual(actual, bytes(expected))
            self.assertEqual(map_tmd(actual, address), actual)
        self.assertEqual(struct.unpack_from('<I', raw, 4)[0], 0x80)

    def test_zero_signed_negative_and_already_mapped_early_returns(self):
        for count in (0, 0x80000000, 0xFFFFFFFF):
            raw = struct.pack('<III', 0x41, 0x80, count)
            self.assertEqual(map_tmd(raw, 0x101000), struct.pack('<III', 0x41, 0x81, count))
            self.assertEqual(map_tmd(struct.pack('<III', 0x41, 0x83, count), 0x101000),
                             struct.pack('<III', 0x41, 0x83, count))

    def test_literal_mode_flag_lengths_including_sdk_gradation_difference(self):
        fixture = json.loads(FIXTURES.read_text())
        for text, size in fixture['formats'].items():
            for flags in (0, 4, 255):
                expected = fixture['gradation_overrides'].get(text, size) if flags & 4 else size
                for transparent in (0, 2):
                    self.assertEqual(sdk_packet_bytes(int(text, 16)|transparent, flags), expected)
        self.assertEqual(sdk_packet_bytes(0x28, 4), 20)
        self.assertEqual(sdk_packet_bytes(0x38, 4), 24)

    def test_runs_split_on_transparency_but_not_flag_change(self):
        fixture = json.loads(FIXTURES.read_text())
        raw, starts = make_tmd([fixture['mixed_runs']])
        mapped, target = map_tmd(raw, 0x80101000), b'\xd3'*24
        plan = link_tmd(mapped, 0x80101000, 0, target)
        expected = bytearray(mapped)
        offsets = (starts[0], starts[0]+40, starts[0]+72, starts[0]+96)
        for offset, count in zip(offsets, (2, 2, 1, 1)):
            struct.pack_into('<H', expected, offset, count)
        self.assertEqual(plan.model, bytes(expected))
        self.assertEqual(tuple(count for _, count in plan.run_headers), (2, 2, 1, 1))
        self.assertEqual(plan.target, target[:8]+struct.pack('<I', 0x8010100C)+target[12:])
        self.assertEqual(link_tmd(plan.model, 0x80101000, 0, plan.target), plan)

    def test_index_selection_and_zero_primitive_side_effect(self):
        raw, starts = make_tmd([[(0x20, 0, 16)], []])
        mapped = map_tmd(raw, 0x101000)
        plan = link_tmd(mapped, 0x101000, 1, b'\xd3'*24)
        self.assertEqual(plan.descriptor_offset, 40)
        self.assertEqual(plan.target[8:12], struct.pack('<I', 0x101028))
        self.assertEqual(plan.model[:starts[1]], mapped[:starts[1]])
        self.assertEqual(plan.model[starts[1]:], b'\0\0'+mapped[starts[1]+2:])
        self.assertEqual(plan.run_headers, ((starts[1], 0),))

    def test_unbounded_tables_pointers_packets_and_error_paths_rejected(self):
        raw, _ = make_tmd([[(0x20, 0, 16)]])
        for address in (-4, 3, True, 0xFFFFFFFC):
            with self.assertRaises(ValueError):
                map_tmd(raw, address)
        for broken in (raw[:11], struct.pack('<III', 0x41, 0, 2), b'\0'*12):
            with self.assertRaises(ValueError):
                map_tmd(broken, 0x101000)
        broken = bytearray(raw)
        struct.pack_into('<I', broken, 12, 0xFFFFFFFC)
        with self.assertRaises(ValueError):
            map_tmd(broken, 0x101000)
        mapped = map_tmd(raw, 0x101000)
        for index in (-1, 1, True):
            with self.assertRaises(ValueError):
                link_tmd(mapped, 0x101000, index, b'\xd3'*24)
        with self.assertRaises(ValueError):
            link_tmd(mapped, 0x80101000, 0, b'\xd3'*24)
        with self.assertRaises(ValueError):
            link_tmd(mapped[:-12], 0x101000, 0, b'\xd3'*24)
        with self.assertRaises(ValueError):
            sdk_packet_bytes(0x40, 0)


if __name__ == '__main__':
    unittest.main()
