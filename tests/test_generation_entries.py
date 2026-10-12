"""Scanner and packet guards use synthetic records and independent edge cases."""
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import verify_generation_entries as entries


class GenerationEntryTests(unittest.TestCase):
    def setUp(self):
        names = ('D_800866E8', 'g_GenerationStageEntryData', 'g_GenerationStageEntries',
                 'g_GenerationStageEntryCounts', 'g_GenerationEntityEffects', 'g_GenerationEntityRange')
        self.symbols = {name: 0x80001000 + i * 0x1000 for i, name in enumerate(names)}
        self.data = bytearray(448)
        self.data[:8] = bytes((0, 0, 1, 2, 0, 0, 1, 0))
        self.data[8:16] = bytes((1, 0, 1, 2, 0, 0, 1, 0))
        self.blocks = {
            self.symbols['g_GenerationStageEntryData']: bytes(self.data),
            self.symbols['g_GenerationStageEntries']: struct.pack('<14I', self.symbols['g_GenerationStageEntryData'], *([0] * 13)),
            self.symbols['g_GenerationStageEntryCounts']: bytes((2, *([0] * 15))),
            self.symbols['g_GenerationEntityEffects']: bytes(68),
            self.symbols['g_GenerationEntityRange']: struct.pack('<15i', 0, *([100] * 14)),
        }

        def target(address, size):
            for start, block in self.blocks.items():
                if start <= address and address + size <= start + len(block):
                    return block[address - start:address - start + size]
            raise AssertionError('Unexpected synthetic input read.')

        self.program = patch.object(entries.n, 'h', SimpleNamespace(symbols=self.symbols, target=target), create=True)
        self.program.start()
        self.addCleanup(self.program.stop)

    def near_case(self, **changes):
        case = entries.base_case(**changes)
        case['query'] = tuple(entries.world(case, self.data[:8]))
        return case

    def test_null_query_preserves_index_outputs_and_all_entry_records(self):
        case = entries.base_case(query=None, index=1)
        expected = entries.fixtures(case)
        result = entries.model(case)
        self.assertEqual(result['index'], 1)
        self.assertEqual(result['result'], 0)
        self.assertEqual(result['trace'], [])
        for name, buffer in expected.items():
            self.assertEqual(result[name], bytes(buffer))

    def test_first_eligible_record_returns_with_one_consumed_index_and_ten_byte_packet(self):
        result = entries.model(self.near_case())
        self.assertEqual(result['result'], self.symbols['g_GenerationStageEntryData'])
        self.assertEqual(result['index'], 1)
        self.assertEqual(len(bytes.fromhex(result['trace'][0][-1])), 10)
        self.assertEqual(result['entries'], bytes(self.data))

    def test_range_boundary_is_strict_and_does_not_use_query_height(self):
        case = self.near_case()
        point = case['query']
        inside = entries.model(dict(case, query=(point[0] + 99, 0x7FFFFFFF, point[2])))
        boundary = entries.model(dict(case, query=(point[0] + 100, -0x80000000, point[2])))
        self.assertNotEqual(inside['result'], 0)
        self.assertEqual(boundary['result'], 0)
        self.assertEqual(boundary['index'], 2)

    def test_inactive_signed_flags_consume_rows_without_overwriting_outputs(self):
        for flag_mode in ('disabled', 'zero', 'minimum_signed'):
            case = entries.base_case(flags=flag_mode)
            expected = entries.fixtures(case)
            result = entries.model(case)
            self.assertEqual(result['index'], 2)
            self.assertEqual(result['trace'], [])
            self.assertEqual(result['output'], bytes(expected['output']))
            self.assertEqual(result['distance'], bytes(expected['distance']))

    def test_alternating_flags_skip_the_first_row_and_preserve_unselected_stage_data(self):
        case = entries.base_case(flags='alternating')
        case['query'] = tuple(entries.world(case, self.data[8:16]))
        result = entries.model(case)
        self.assertEqual(result['result'], self.symbols['g_GenerationStageEntryData'] + 8)
        self.assertEqual(result['index'], 2)
        self.assertEqual(result['entries'][16:], bytes(self.data[16:]))

    def test_odd_grid_rows_shift_x_while_nonzero_mode_uses_one_row(self):
        row = bytes((0, 1, 1, 2, 0, 0, 1, 0))
        case = entries.base_case(grid=(3, 2, 0))
        self.assertEqual(entries.world(case, row), [-78848, 0, 5120])
        self.assertEqual(entries.world(dict(case, grid=(3, 2, 1)), row), [-58368, 0, -15360])

    def test_native_int_min_absolute_distance_keeps_the_wrapped_signed_result(self):
        case = self.near_case()
        point = case['query']
        result = entries.model(dict(case, query=(entries.s32(point[0] + 0x80000000), point[1], point[2])))
        self.assertEqual(struct.unpack_from('<i', result['distance'])[0], -0x80000000)
        self.assertEqual(result['result'], self.symbols['g_GenerationStageEntryData'])

    def test_invalid_pointer_domain_grid_or_word_values_are_rejected(self):
        for changes in ({'stage': 14}, {'index': -1}, {'index': 4}, {'flags': 'unknown'},
                        {'grid': (0, 2, 0)}, {'query': (0, 0, 0x80000000)}, {'stage': True}):
            with self.assertRaises(ValueError):
                entries.fixtures(entries.base_case(**changes))

    def test_candidate_outside_scanner_changes_are_rejected_and_inside_changes_stay_unaccepted(self):
        program = SimpleNamespace(LOAD=int(entries.FUNCTIONS[0]['address'], 16), ROM=bytes(0x800 + 444 + 8))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'candidate.exe'
            data = bytearray(program.ROM)
            data[0x800] = 1
            path.write_bytes(data)
            observed, identity = entries.candidate_identity(program, path)
            self.assertEqual(observed, bytes(data))
            self.assertEqual(identity['changed_bytes'], 1)
            self.assertFalse(identity['source_promoted'])
            data[-1] = 1
            path.write_bytes(data)
            with self.assertRaises(ValueError):
                entries.candidate_identity(program, path)


if __name__ == '__main__':
    unittest.main()
