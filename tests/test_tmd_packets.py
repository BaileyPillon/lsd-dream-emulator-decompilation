"""Independent field-layout fixtures and malformed model boundary checks."""
import struct
import unittest

from tools.tmd_packets import geometries, model_ranges, packet_layout, packets, summarize

# Literal locations from the original reader; production derives field groups.
FORMATS = {
    0x20: (16, (10, 12, 14)), 0x21: (16, (8, 10, 12)),
    0x24: (24, (18, 20, 22)), 0x25: (28, (20, 22, 24)),
    0x28: (20, (10, 12, 14, 16)), 0x29: (16, (8, 10, 12, 14)),
    0x2c: (32, (22, 24, 26, 28)), 0x2d: (32, (24, 26, 28, 30)),
    0x30: (20, (10, 14, 18)), 0x31: (24, (16, 18, 20)),
    0x34: (28, (18, 22, 26)), 0x35: (36, (28, 30, 32)),
    0x38: (24, (10, 14, 18, 22)), 0x39: (28, (20, 22, 24, 26)),
    0x3c: (36, (22, 26, 30, 34)), 0x3d: (44, (36, 38, 40, 42)),
}
GRADATION = {
    0x20: (24, (18, 20, 22)), 0x28: (32, (22, 24, 26, 28)),
    0x30: (28, (18, 22, 26)), 0x38: (36, (22, 26, 30, 34)),
}
POINTS = ((-32768, 32767, -1), (19, -22, 31), (0, 2, -3), (101, 202, -303))


def primitive(mode=0x20, flags=0, indices=(3, 1, 0, 2)):
    base = mode & ~2
    length, locations = GRADATION.get(base, FORMATS[base]) if flags & 4 else FORMATS[base]
    result = bytearray([0x96] * length)
    result[:4] = bytes((0xfc, 0xfd, flags, mode))  # Deliberately unusable length bytes.
    for at, index in zip(locations, indices):
        struct.pack_into('<H', result, at, index)
    return bytes(result)


def tmd(records=None):
    records = [primitive()] if records is None else list(records)
    vertices = b''.join(struct.pack('<3hH', *point, 0xeeee) for point in POINTS)
    start = 40 + len(vertices) + 8
    result = bytearray(start + sum(map(len, records)))
    struct.pack_into('<III', result, 0, 0x41, 0, 1)
    struct.pack_into('<6Ii', result, 12, 28, 4, 28 + len(vertices), 1,
                     start - 12, len(records), -2)
    result[40:40 + len(vertices)] = vertices
    result[start:] = b''.join(records)
    return bytes(result)


def mom(data):
    result = bytearray(20 + len(data))
    result[:4] = b'MOM '
    struct.pack_into('<II', result, 4, len(result), 20)
    result[12:16] = b'MOS '
    result[20:] = data
    return bytes(result)


def lbd(data, embedded=None):
    grid, grid_bytes = 24, 4808
    tmd_at = grid + grid_bytes
    result = bytearray(tmd_at + len(data))
    struct.pack_into('<II', result, 4, grid, grid_bytes)
    struct.pack_into('<HH', result, grid + 4, 20, 20)
    result[tmd_at:] = data
    if embedded is not None:
        struct.pack_into('<H', result, 2, 1)
        offset = len(result)
        library = b'MML ' + struct.pack('<III', 2, 16, 16) + embedded
        struct.pack_into('<II', result, 16, offset, len(library))
        result.extend(library)
    return bytes(result)


class TmdPacketTests(unittest.TestCase):
    def test_all_32_modes_and_gradation_lengths(self):
        for mode in range(0x20, 0x40):
            for flags in (0, 4, 255):
                base = mode & ~2
                expected = GRADATION.get(base, FORMATS[base]) if flags & 4 else FORMATS[base]
                with self.subTest(mode=mode, flags=flags):
                    layout = packet_layout(mode, flags)
                    self.assertEqual((layout.bytes, layout.vertices), expected)

    def test_signed_coordinates_and_record_stride(self):
        data = tmd()
        geometry, = geometries(data)
        packet, = packets(data, geometry)
        self.assertEqual(packet.points, (POINTS[3], POINTS[1], POINTS[0]))
        self.assertEqual(packet.vertex_indices, (3, 1, 0))
        self.assertEqual(geometry.scale_exponent, -2)
        self.assertEqual(packet.header_words, (0xfc, 0xfd))

    def test_mixed_packet_lengths_chain_without_using_header_lengths(self):
        data = tmd([primitive(0x20), primitive(0x3d), primitive(0x28, 4)])
        geometry, = geometries(data)
        decoded = list(packets(data, geometry))
        self.assertEqual([p.bytes for p in decoded], [16, 44, 32])
        self.assertEqual([p.offset for p in decoded], [80, 96, 140])
        result = summarize(data, '.TMD')['models'][0]['counts']
        self.assertEqual(result['packets'], 3)
        self.assertEqual(result['vertex_references'], 11)

    def test_linker_header_run_count_does_not_change_vertex_decode(self):
        original = tmd()
        changed = bytearray(original)
        changed[80:82] = b'\x01\0'
        first = next(packets(original, geometries(original)[0]))
        second = next(packets(changed, geometries(changed)[0]))
        self.assertEqual((first.points, first.bytes), (second.points, second.bytes))
        self.assertNotEqual(first.header_words, second.header_words)

    def test_out_of_range_vertex_is_rejected(self):
        data = bytearray(tmd())
        struct.pack_into('<H', data, 90, 4)
        with self.assertRaisesRegex(ValueError, 'outside its descriptor'):
            list(packets(data, geometries(data)[0]))

    def test_each_truncated_payload_is_rejected(self):
        original = tmd([primitive(0x3d)])
        for omitted in range(1, 45):
            data = original[:-omitted]
            with self.subTest(omitted=omitted), self.assertRaises(ValueError):
                list(packets(data, geometries(data)[0]))

    def test_unsupported_mode_is_not_silently_counted(self):
        data = bytearray(tmd())
        data[83] = 0x40
        with self.assertRaisesRegex(ValueError, 'Unsupported collision primitive'):
            list(packets(data, geometries(data)[0]))

    def test_oversized_descriptor_counts_and_offsets_are_rejected(self):
        for offset in (8, 12, 16, 20, 24, 28, 32):
            data = bytearray(tmd())
            struct.pack_into('<I', data, offset, 0xffffffff)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                geometries(data)

    def test_array_cannot_alias_the_object_table(self):
        data = bytearray(tmd())
        struct.pack_into('<I', data, 12, 0)
        with self.assertRaisesRegex(ValueError, 'Vertices exceeds'):
            geometries(data)

    def test_zero_packets_and_zero_object_table(self):
        data = tmd([])
        self.assertEqual(list(packets(data, geometries(data)[0])), [])
        empty = struct.pack('<III', 0x41, 0, 0)
        self.assertEqual(geometries(empty), ())
        self.assertEqual(summarize(empty, '.TMD')['models'][0]['counts'], {})

    def test_mapped_or_unknown_tmd_flags_are_rejected(self):
        for flag in (1, 2, 0xffffffff):
            data = bytearray(tmd())
            struct.pack_into('<I', data, 4, flag)
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, 'fresh relative TMD'):
                geometries(data)

    def test_declared_nested_model_limit_is_enforced(self):
        data = tmd()
        with self.assertRaises(ValueError):
            list(packets(data + bytes(64), geometries(data + bytes(64), limit=len(data)-1)[0]))

    def test_mom_offsets_are_relative_to_its_tmd_table(self):
        data = mom(tmd())
        model, = model_ranges(data, '.MOM')
        self.assertEqual((model['tmd'], model['limit']), (20, len(data)))
        packet, = packets(data, geometries(data, model['tmd'], model['limit'])[0])
        self.assertEqual(packet.offset, 100)
        self.assertEqual(packet.points, (POINTS[3], POINTS[1], POINTS[0]))

    def test_lbd_primary_tmd_is_bounded(self):
        data = lbd(tmd())
        model, = model_ranges(data, '.LBD')
        self.assertEqual(model['tmd'], 4832)
        self.assertEqual(summarize(data, '.LBD')['models'][0]['counts']['packets'], 1)

    def test_mml_offset_aliases_are_counted_once_with_reference_multiplicity(self):
        data = lbd(struct.pack('<III', 0x41, 0, 0), mom(tmd()))
        models = model_ranges(data, '.LBD')
        self.assertEqual(len(models), 2)
        self.assertEqual(models[1]['references'], 2)
        counts = summarize(data, '.LBD')['models'][1]['counts']
        self.assertEqual(counts['packets'], 1)

    def test_unreviewed_container_type_is_rejected(self):
        with self.assertRaises(ValueError):
            model_ranges(tmd(), '.BIN')


if __name__ == '__main__':
    unittest.main()
