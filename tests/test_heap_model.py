import struct
import unittest

from tools.heap_model import FREE, PREVIOUS_FREE, PoolModel


def fixture(size=128, segment=0):
    buffers = {'manager': bytearray([0xD7] * 128), 'pool': bytearray([0xA5] * (size + 132))}
    bases = {'manager': 0x100000, 'pool': 0x110000}
    struct.pack_into('<II', buffers['manager'], 32, (bases['pool'] + 32) | segment, size)
    return PoolModel(buffers, bases, 32, 32, size, segment)


class HeapModelTests(unittest.TestCase):
    def test_setup_preserves_unrelated_storage(self):
        model = fixture()
        before = model.snapshot()
        model.setup()
        self.assertEqual(model.get('pool', 32), FREE | 128)
        self.assertEqual(model.get('pool', 32 + 128), PREVIOUS_FREE)
        self.assertEqual(model.get('pool', 32 + 124), model.pool_pointer)
        self.assertEqual(model.snapshot()['manager'][:32], before['manager'][:32])
        self.assertEqual(model.snapshot()['manager'][52:], before['manager'][52:])
        self.assertEqual(model.snapshot()['pool'][:32], before['pool'][:32])
        self.assertEqual(model.snapshot()['pool'][164:], before['pool'][164:])

    def test_request_alignment_and_minimum_payload(self):
        for request, block_size in ((1, 16), (12, 16), (13, 20), (17, 24)):
            with self.subTest(request=request):
                model = fixture()
                model.setup()
                self.assertEqual(model.allocate(request), model.pool_pointer + 4)
                self.assertEqual(model.blocks[0].size, block_size)
                self.assertEqual(model.blocks[1].offset, block_size)

    def test_null_and_failed_allocation_leave_all_buffers_unchanged(self):
        model = fixture()
        model.setup()
        before = model.snapshot()
        self.assertEqual(model.allocate(0), 0)
        self.assertEqual(model.allocate(129), 0)
        self.assertEqual(model.free(0), 0)
        self.assertEqual(model.snapshot(), before)

    def test_split_requires_sixteen_byte_remainder(self):
        for request, sizes in ((108, [112, 16]), (112, [128]), (124, [128])):
            with self.subTest(request=request):
                model = fixture()
                model.setup()
                model.allocate(request)
                self.assertEqual([block.size for block in model.blocks], sizes)
                self.assertEqual(model.get('pool', 160), PREVIOUS_FREE if len(sizes) == 2 else 0)

    def test_first_fit_scans_queue_order_past_small_head(self):
        model = fixture(1024)
        model.setup()
        pointers = [model.allocate(size) for size in (60, 124, 60, 252, 60)]
        model.free(pointers[3])
        model.free(pointers[0])
        self.assertEqual(model.queue, [0, 256, 576])
        self.assertEqual(model.allocate(200), model.pool_pointer + 260)
        self.assertEqual(model.queue, [0, 460, 576])

    def test_free_coalesces_left_right_and_both(self):
        for order in ((0, 1, 2), (2, 1, 0), (0, 2, 1)):
            with self.subTest(order=order):
                model = fixture(96)
                model.setup()
                pointers = [model.allocate(20) for _ in range(3)]
                for index in order:
                    model.free(pointers[index])
                self.assertEqual([(b.offset, b.size, b.free) for b in model.blocks], [(0, 96, True)])
                self.assertEqual(model.queue, [0])

    def test_coalescing_retains_intermediate_unlink_writes(self):
        model = fixture(96)
        model.setup()
        pointers = [model.allocate(20) for _ in range(3)]
        model.free(pointers[0])
        model.free(pointers[2])
        self.assertEqual(model.get('pool', 32 + 48 + 4), model.pool_pointer)
        model.free(pointers[1])
        # The removed upper free node is now payload inside the merged block.
        # Its old next link was cleared while unlinking the lower free node.
        self.assertEqual(model.get('pool', 32 + 48 + 4), 0)

    def test_aliases_are_retained_in_all_pointers(self):
        for segment in (0, 0x80000000, 0xA0000000):
            with self.subTest(segment=segment):
                model = fixture(segment=segment)
                model.setup()
                pointer = model.allocate(12)
                self.assertEqual(pointer & ~0x1FFFFFFF, segment)
                self.assertEqual(model.get('manager', 40), model.pool_pointer + 16)
                model.free(pointer)
                self.assertEqual(model.get('manager', 40), model.pool_pointer)

    def test_invalid_ownership_is_outside_profile(self):
        model = fixture()
        model.setup()
        pointer = model.allocate(12)
        for invalid in (pointer + 4, pointer | 0x80000000, -1, 1 << 32):
            with self.subTest(pointer=invalid), self.assertRaises(ValueError):
                model.free(invalid)
        model.free(pointer)
        with self.assertRaises(ValueError):
            model.free(pointer)

    def test_payload_writes_cannot_cross_owned_interval(self):
        model = fixture()
        model.setup()
        pointer = model.allocate(12)
        model.write_payload(pointer, b'hello world!')
        self.assertEqual(model.snapshot()['pool'][36:48], b'hello world!')
        with self.assertRaises(ValueError):
            model.write_payload(pointer, bytes(13))

    def test_layout_and_manager_binding_are_checked(self):
        with self.assertRaises(ValueError):
            fixture(15)
        good = fixture()
        buffers = good.snapshot()
        buffers['manager'] = bytearray(buffers['manager'])
        struct.pack_into('<I', buffers['manager'], 32, 0)
        with self.assertRaises(ValueError):
            PoolModel(buffers, good.bases, 32, 32, 128)
        with self.assertRaises(ValueError):
            PoolModel(good.snapshot(), {'manager': 0x110000, 'pool': 0x110000}, 32, 32, 128)

    def test_validation_rejects_corrupt_queue_header_and_footer(self):
        for name, offset in (('manager', 40), ('pool', 36), ('pool', 32), ('pool', 156)):
            with self.subTest(name=name, offset=offset):
                model = fixture()
                model.setup()
                model.put(name, offset, 0xDEADBEEF)
                with self.assertRaises(ValueError):
                    model.validate()

    def test_setup_and_nonoverflowing_request_profile_are_explicit(self):
        model = fixture()
        with self.assertRaises(ValueError):
            model.allocate(1)
        model.setup()
        for size in (-1, 0x10001, '12'):
            with self.subTest(size=size), self.assertRaises(ValueError):
                model.allocate(size)


if __name__ == '__main__':
    unittest.main()
