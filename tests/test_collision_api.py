"""Collision caller layout, output custody and evidence guards without game files."""
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from research.collision_api import verify as api


class CollisionAPITests(unittest.TestCase):
    def case(self, **changes):
        return dict(dict(polygons=(), start=(-3, -2, -1), end=(4, 5, 6)), **changes)

    def test_request_keeps_argument_order_and_address_aliases(self):
        for segment in (0, 0x80000000, 0xA0000000):
            for height in (False, True):
                with self.subTest(segment=segment, height=height):
                    case = self.case(segment=segment, height_output=height)
                    before, original_args = api.c.model_fixture(**case)
                    data, args = api.initialized(case)
                    self.assertEqual(args, original_args)
                    self.assertEqual(struct.unpack_from('<6I', data, api.REQUEST),
                                     (args[0], args[4], args[5], args[2], args[1], args[3]))
                    self.assertEqual(data[:api.REQUEST], before[:api.REQUEST])
                    self.assertEqual(data[api.REQUEST + 24:], before[api.REQUEST + 24:])

    def test_hit_changes_only_the_three_declared_outputs(self):
        case = self.case()
        data, args = api.initialized(case)
        before = bytes(data)
        with patch.object(api.c, 'primitive_model', return_value=(1, 765, (-32768, 0, 32767), -512)):
            result, output = api.expected(case, data, args, None)
        self.assertEqual(result, 1)
        wanted = bytearray(before)
        struct.pack_into('<i', wanted, api.c.NEAREST, 765)
        struct.pack_into('<3h', wanted, api.c.CONTACT, -32768, 0, 32767)
        struct.pack_into('<i', wanted, api.c.HEIGHT, -512)
        self.assertEqual(output, bytes(wanted))
        self.assertEqual(bytes(data), before)

    def test_miss_resets_distance_and_preserves_hit_and_height(self):
        case = self.case()
        data, args = api.initialized(case)
        wanted = bytearray(data)
        struct.pack_into('<i', wanted, api.c.NEAREST, 2147483647)
        with patch.object(api.c, 'primitive_model', return_value=(0, 2147483647, None, None)):
            self.assertEqual(api.expected(case, data, args, None), (0, bytes(wanted)))

    def test_null_height_preserves_its_guarded_buffer_on_a_hit(self):
        case = self.case(height_output=False)
        data, args = api.initialized(case)
        self.assertEqual(args[3], 0)
        wanted = bytearray(data)
        struct.pack_into('<i', wanted, api.c.NEAREST, 42)
        struct.pack_into('<3h', wanted, api.c.CONTACT, -1, 2, -3)
        with patch.object(api.c, 'primitive_model', return_value=(1, 42, (-1, 2, -3), 17)):
            self.assertEqual(api.expected(case, data, args, None), (1, bytes(wanted)))

    def test_fresh_private_destination_is_not_created_by_validation(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(api, 'ROOT', Path(folder)):
            output = Path(folder) / '.decomp-lab' / 'new'
            self.assertEqual(api.new_output(output), output.resolve())
            self.assertFalse(output.exists())

    def test_unsafe_or_existing_outputs_fail_before_loading_game_inputs(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(api, 'ROOT', Path(folder)):
            root = Path(folder)
            prior = root / '.decomp-lab' / 'retained'
            prior.mkdir(parents=True)
            sentinel = prior / 'evidence.json'
            sentinel.write_bytes(b'retained evidence')
            for output in (root / 'public', root / '.decomp-lab', prior,
                           root / '.decomp-lab' / '..' / 'escaped'):
                with self.subTest(output=output), patch.object(api.n, 'evidence_dependencies') as dependencies, \
                        patch.object(api.n, 'load_program') as load:
                    with self.assertRaisesRegex(ValueError, 'fresh private evidence directory'):
                        api.verify(output, root / 'missing-bridge.exe', 'missing-runtime')
                    dependencies.assert_not_called()
                    load.assert_not_called()
            self.assertEqual(sentinel.read_bytes(), b'retained evidence')


if __name__ == '__main__':
    unittest.main()
