"""Literal state/width/FIFO/flag boundaries for the renderer GTE oracle."""
import unittest

from tools.gte_state_model import GteState, command_word, matrix_registers

IDENTITY = (4096, 0, 0, 0, 4096, 0, 0, 0, 4096)


def matrix(index, values=IDENTITY):
    return [(0, 8*index+i, word) for i, word in enumerate(matrix_registers(values))]


class GteStateTests(unittest.TestCase):
    def test_sign_extensions_masks_and_readonly_registers(self):
        state = GteState()
        result = state.request(True, [(0, 4, 0xABCDEF01), (0, 26, 0x1234FFFF),
            (1, 1, 0xAAAA8000), (1, 7, 0xABCDEF01), (1, 9, 0x1234FFFF),
            (1, 29, 0xFFFFFFFF), (1, 31, 0xFFFFFFFF)])
        self.assertEqual(result['cr'][4], 0xFFFFEF01)
        self.assertEqual(result['cr'][26], 0xFFFFFFFF)
        self.assertEqual(result['dr'][1], 0xFFFF8000)
        self.assertEqual(result['dr'][7], 0xEF01)
        self.assertEqual(result['dr'][9], 0xFFFFFFFF)
        self.assertEqual(result['dr'][29], 0)
        self.assertEqual(result['dr'][31], 0)

    def test_screen_fifo_push_and_direct_tail_mirror_are_distinct(self):
        state = GteState()
        result = state.request(True, [(1, 12, 10), (1, 13, 20), (1, 14, 30), (1, 15, 40)])
        self.assertEqual(result['dr'][12:16], [20, 30, 40, 40])
        result = state.request(False, [(1, 14, 50)])
        self.assertEqual(result['dr'][12:16], [20, 30, 50, 50])

    def test_rgb_unpack_pack_signed_clamp_and_leading_sign_bits(self):
        state = GteState()
        result = state.request(True, [(1, 28, 0x7FFF)])
        self.assertEqual(result['dr'][9:12], [3968]*3)
        self.assertEqual(result['dr'][28:30], [0x7FFF]*2)
        result = state.request(False, [(1, 9, 0xFFFF), (1, 10, 4096), (1, 11, 128)])
        self.assertEqual(result['dr'][28], (31 << 5) | (1 << 10))
        for word, count in ((0, 32), (0xFFFFFFFF, 32), (0x80000000, 1), (0x7FFFFFFF, 1), (1, 31)):
            self.assertEqual(state.request(False, [(1, 30, word)])['dr'][31], count)

    def test_translation_and_stateful_commands_preserve_unrelated_registers(self):
        state = GteState()
        result = state.request(True, matrix(0)+[(0, 5, 4), (0, 6, 5), (0, 7, 6),
            (1, 0, 0xFFFE0001), (1, 1, 3), (1, 23, 0xDEADBEEF)],
            command_word(0x12, translation=0))
        self.assertEqual(result['dr'][9:12], [5, 3, 9])
        self.assertEqual(result['dr'][25:28], [5, 3, 9])
        self.assertEqual(result['dr'][23], 0xDEADBEEF)
        self.assertEqual(result['command_cycles_minus_one'], 7)
        again = state.request(False, [], command_word(0x12, vector=3, translation=0))
        self.assertEqual(again['dr'][9:12], [9, 8, 15])

    def test_identity_projection_and_fifo_then_area_and_depth(self):
        state = GteState()
        writes = matrix(0)+[(0, 26, 256), (1, 0, 0), (1, 1, 4096),
            (1, 2, 256), (1, 3, 4096), (1, 4, 256 << 16), (1, 5, 4096), (0, 29, 1365)]
        projected = state.request(True, writes, command_word(0x30))
        self.assertEqual(projected['dr'][12:16], [0, 16, 16 << 16, 16 << 16])
        self.assertEqual(projected['dr'][16:20], [0, 4096, 4096, 4096])
        self.assertEqual(projected['cr'][31], 0)
        self.assertEqual(state.request(False, [], command_word(6))['dr'][24], 256)
        depth = state.request(False, [], command_word(0x2D))
        self.assertEqual(depth['dr'][7], 4095)

    def test_far_color_quirk_drops_first_column_but_retains_its_limit_flag(self):
        state = GteState()
        result = state.request(True, matrix(0)+[(1, 0, 0x00020001), (1, 1, 3)],
                               command_word(0x12, translation=2))
        self.assertEqual(result['dr'][9:12], [0, 2, 3])

    def test_lighting_and_depth_cue_color_fifo(self):
        state = GteState()
        result = state.request(True, matrix(1)+matrix(2)+[(1, 0, 2048 << 16 | 4096),
            (1, 1, 1024), (1, 6, 0xA5204080)], command_word(0x1B, limit=1))
        self.assertEqual(result['dr'][22], 0xA5082080)
        result = state.request(False, [(1, 8, 4096), (0, 21, 160), (0, 22, 320), (0, 23, 480)],
                               command_word(0x10, limit=1))
        self.assertEqual(result['dr'][22], 0xA51E140A)

    def test_summary_mask_and_avsz_overflow_do_not_use_wrapped_mac_for_otz(self):
        state = GteState()
        self.assertEqual(state.request(True, [(0, 31, 1 << 22)])['cr'][31], 1 << 22)
        self.assertEqual(state.request(False, [(0, 31, 1 << 24)])['cr'][31], 0x81000000)
        result = state.request(True, [(0, 30, 32767)]+[(1, i, 65535) for i in range(16, 20)], command_word(0x2E))
        self.assertEqual(result['dr'][7], 65535)
        self.assertTrue(result['cr'][31] & (1 << 16))
        self.assertTrue(result['cr'][31] & (1 << 18))

    def test_invalid_types_and_unreviewed_commands_fail_closed(self):
        for operation in ((True, 0, 0), (0, 32, 0), (1, 0, True), (1, 0, -1)):
            with self.assertRaises(ValueError):
                GteState().request(True, [operation])
        for command in (True, 0x1234, 0x4A00003E, 0x14A800012):
            with self.assertRaises(ValueError):
                GteState().execute(command)


if __name__ == '__main__':
    unittest.main()
