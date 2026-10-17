"""Independent raw-model fixtures; no game assets, executable or Unicorn needed."""
import struct
import unittest

from tools.model_mapping_model import geometry_bindings, mapped_model_bytes


def mom(objects=2, animations=2):
    animation = 20 + animations * 4
    tmd = animation + 16
    raw = bytearray(tmd + 12 + objects * 28)
    raw[:4], raw[12:16] = b'MOM ', b'MOS '
    struct.pack_into('<II', raw, 4, len(raw), tmd)
    struct.pack_into('<I', raw, 16, animations)
    for index in range(animations):
        struct.pack_into('<I', raw, 20 + index * 4, animation - 12)
    struct.pack_into('<III', raw, tmd, 0x41, 0, objects)
    return raw


def primitive_mom(packets):
    raw = mom(objects=1)
    tmd = struct.unpack_from('<I', raw, 8)[0]
    table = tmd + 12
    struct.pack_into('<II', raw, table + 16, 28, len(packets))
    for mode, flags, size in packets:
        packet = bytearray([0xA5]) * size
        packet[:4] = bytes((0x55, 0xAA, flags, mode))
        raw.extend(packet)
    struct.pack_into('<I', raw, 4, len(raw))
    return raw, table + 28


class ModelMappingTests(unittest.TestCase):
    def test_geometry_is_relative_to_object_table_and_other_bytes_survive(self):
        raw = mom()
        tmd = struct.unpack_from('<I', raw, 8)[0]
        table = tmd + 12
        struct.pack_into('<I', raw, tmd + 4, 0x80)
        for offset, value in ((0, 4), (8, 12), (16, 20), (28, 0), (36, 8), (44, 16)):
            struct.pack_into('<I', raw, table + offset, value)
        before = bytes(raw)
        expected = bytearray(raw)
        struct.pack_into('<I', expected, tmd + 4, 0x81)
        struct.pack_into('<II', expected, 20, 0xA0100, 0xA0200)
        for offset, value in ((0, 4), (8, 12), (16, 20), (28, 0), (36, 8), (44, 16)):
            struct.pack_into('<I', expected, table + offset, 0x140020 + table + value)
        self.assertEqual(mapped_model_bytes(raw, 0x140020, (0xA0100, 0xA0200)), bytes(expected))
        self.assertEqual(bytes(raw), before)

    def test_shared_animation_payloads_still_receive_distinct_planned_objects(self):
        raw = mom()
        self.assertEqual(raw[20:24], raw[24:28])
        actual = mapped_model_bytes(raw, 0x140020, (0xA0100, 0xA0200))
        self.assertEqual(struct.unpack_from('<II', actual, 20), (0xA0100, 0xA0200))

    def test_allocation_addresses_change_only_animation_pointer_slots(self):
        raw = mom()
        first = mapped_model_bytes(raw, 0x140020, (0xA0100, 0xA0200))
        second = mapped_model_bytes(raw, 0x140020, (0xB0300, 0xB0400))
        self.assertEqual(first[:20], second[:20])
        self.assertEqual(first[28:], second[28:])

    def test_empty_geometry_table_sets_mapped_flag_without_touching_other_data(self):
        raw = mom(objects=0)
        tmd = struct.unpack_from('<I', raw, 8)[0]
        actual = mapped_model_bytes(raw, 0x140020, (0xA0100, 0xA0200))
        self.assertEqual(struct.unpack_from('<III', actual, tmd), (0x41, 1, 0))

    def test_bad_signatures_declared_extent_and_tables_are_rejected(self):
        for offset, value in ((0, 0), (4, 4), (8, 0xFFFFFFFC), (12, 0), (16, 0xFFFFFFFF)):
            raw = mom()
            struct.pack_into('<I', raw, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                mapped_model_bytes(raw, 0x140020, (0xA0100, 0xA0200))

    def test_wrong_or_already_mapped_geometry_is_outside_fresh_input_profile(self):
        for field, value in ((0, 0), (4, 1), (8, 0xFFFFFFFF)):
            raw = mom()
            tmd = struct.unpack_from('<I', raw, 8)[0]
            struct.pack_into('<I', raw, tmd + field, value)
            with self.subTest(field=field), self.assertRaises(ValueError):
                mapped_model_bytes(raw, 0x140020, (0xA0100, 0xA0200))

    def test_escaping_and_misaligned_geometry_offsets_are_rejected(self):
        for value in (1, 0xFFFFFFFC):
            raw = mom()
            tmd = struct.unpack_from('<I', raw, 8)[0]
            struct.pack_into('<I', raw, tmd + 12, value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                mapped_model_bytes(raw, 0x140020, (0xA0100, 0xA0200))

    def test_escaping_header_and_misaligned_animation_offsets_are_rejected(self):
        for value in (0, 1, 0xFFFFFFFC):
            raw = mom()
            struct.pack_into('<I', raw, 20, value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                mapped_model_bytes(raw, 0x140020, (0xA0100, 0xA0200))

    def test_missing_invalid_and_misaligned_planned_pointers_are_rejected(self):
        for pointers in ((), (0xA0100,), (0xA0100, 0), (0xA0100, 3), (True, 0xA0200), (0xA0100, 0x100000000)):
            with self.subTest(pointers=pointers), self.assertRaises(ValueError):
                mapped_model_bytes(mom(), 0x140020, pointers)

    def test_unbounded_or_misaligned_vm_copy_is_rejected(self):
        for address in (-4, 1, True, 0xFFFFFFFC):
            with self.subTest(address=address), self.assertRaises(ValueError):
                mapped_model_bytes(mom(), address, (0xA0100, 0xA0200))

    def test_geometry_binding_uses_first_nonzero_selection_for_each_known_child(self):
        command = lambda child, index: (child, 2, struct.pack('<I', index))
        commands = [command(99, 90), command(9, 0), command(9, 2), command(9, 1), command(2, 1)]
        self.assertEqual(geometry_bindings((9, 2), commands, 2), (1, 0))
        for invalid in ((9, 2, b''), command(9, 3)):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                geometry_bindings((9,), [invalid], 2)

    def test_mode_runs_preserve_inner_headers_and_split_on_transparency_bit(self):
        raw, start = primitive_mom(((0x24, 0, 24), (0x24, 0, 24), (0x26, 0, 24), (0x24, 0, 24)))
        actual = mapped_model_bytes(raw, 0x140020, (0xA0100, 0xA0200), (0,))
        self.assertEqual([struct.unpack_from('<H', actual, start + offset)[0] for offset in (0, 24, 48, 72)],
                         [2, 0xAA55, 1, 1])
        self.assertEqual(mapped_model_bytes(raw, 0x140020, (0xA0100, 0xA0200), (0, 0)), actual)

    def test_sdk_packet_sizes_reach_the_next_group_without_using_length_bytes(self):
        sizes = ((0x20, 0, 16), (0x20, 4, 24), (0x21, 0, 16), (0x24, 0, 24),
                 (0x25, 0, 28), (0x28, 4, 20), (0x29, 0, 16), (0x2C, 0, 32),
                 (0x2D, 0, 32), (0x30, 0, 20), (0x30, 4, 28), (0x31, 0, 24),
                 (0x34, 0, 28), (0x35, 0, 36), (0x38, 0, 24), (0x39, 0, 28),
                 (0x3C, 0, 36), (0x3D, 0, 44))
        for mode, flags, size in sizes:
            for transparent in (0, 2):
                first = mode | transparent
                second = 0x20 if first != 0x20 else 0x24
                tail_size = 16 if second == 0x20 else 24
                raw, start = primitive_mom(((first, flags, size), (second, 0, tail_size)))
                with self.subTest(mode=first, flags=flags):
                    actual = mapped_model_bytes(raw, 0x140020, (0xA0100, 0xA0200), (0,))
                    self.assertEqual(struct.unpack_from('<H', actual, start)[0], 1)
                    self.assertEqual(struct.unpack_from('<H', actual, start + size)[0], 1)
                    self.assertEqual(actual[start+2:start+size], raw[start+2:start+size])

    def test_destruction_clears_object_slots_and_retains_packet_batching(self):
        raw, _ = primitive_mom(((0x24, 0, 24),))
        linked = mapped_model_bytes(raw, 0x140020, (0xA0100, 0xA0200), (0,))
        final = mapped_model_bytes(raw, 0x140020, (0xA0100, 0xA0200), (0,), destroyed=True)
        self.assertEqual(final[20:28], bytes(8))
        self.assertEqual(final[:20] + final[28:], linked[:20] + linked[28:])

    def test_unsupported_modes_missing_packets_and_outside_indices_are_rejected(self):
        raw, _ = primitive_mom(((0, 0, 16),))
        with self.assertRaises(ValueError):
            mapped_model_bytes(raw, 0x140020, (0xA0100, 0xA0200), (0,))
        raw, _ = primitive_mom(((0x3D, 0, 16),))
        with self.assertRaises(ValueError):
            mapped_model_bytes(raw, 0x140020, (0xA0100, 0xA0200), (0,))
        for index in (-1, 1, True):
            with self.subTest(index=index), self.assertRaises(ValueError):
                mapped_model_bytes(raw, 0x140020, (0xA0100, 0xA0200), (index,))


if __name__ == '__main__':
    unittest.main()
