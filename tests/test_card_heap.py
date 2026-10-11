import contextlib
import io
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import verify_card_heap as heap


class HeapCleanupModelTests(unittest.TestCase):
    def fixture(self, count=3, table_present=True, segment=0):
        model = heap.initial_model(1024, segment)
        model.setup()
        buffer = model.allocate(12)
        children = [model.allocate(size) for size in (12, 16, 20)]
        table = model.allocate(32) if table_present else 0
        if table:
            model.write_payload(table, struct.pack('<8I', *children, 0, 0, 0, 0, 0))
        owner = (heap.BASES['object'] + heap.OFFSET) | segment
        for field, value in ((0x2C, count), (0x38, table), (0x3C, buffer)):
            model.put('object', heap.OFFSET + field, value)
        return model, owner, buffer, children, table

    def test_real_heap_release_order_and_retained_owner_fields(self):
        model, owner, buffer, children, table = self.fixture()
        before = model.snapshot()['object']
        self.assertEqual(heap.expected_cleanup(model, owner), [buffer, *children, table])
        after = model.snapshot()['object']
        self.assertEqual(after[:heap.OFFSET + 0x38], before[:heap.OFFSET + 0x38])
        self.assertEqual(after[heap.OFFSET + 0x38:heap.OFFSET + 0x3C], bytes(4))
        self.assertEqual(after[heap.OFFSET + 0x3C:], before[heap.OFFSET + 0x3C:])
        self.assertEqual([(b.offset, b.size, b.free) for b in model.blocks], [(0, 1024, True)])

    def test_absent_table_preserves_live_allocations(self):
        model, owner, buffer, children, _ = self.fixture(table_present=False)
        before = model.snapshot()
        self.assertEqual(heap.expected_cleanup(model, owner), [])
        self.assertEqual(model.snapshot(), before)
        for pointer in [buffer, *children]:
            self.assertFalse(model.owned_block(pointer).free)

    def test_negative_count_keeps_unvisited_children_live(self):
        for count in (-(1 << 31), -1, 0):
            with self.subTest(count=count):
                model, owner, buffer, children, table = self.fixture(count=count)
                self.assertEqual(heap.expected_cleanup(model, owner), [buffer, table])
                for pointer in children:
                    self.assertFalse(model.owned_block(pointer).free)

    def test_repeat_cleanup_does_not_free_stale_buffer(self):
        model, owner, _, _, _ = self.fixture()
        heap.expected_cleanup(model, owner)
        before = model.snapshot()
        self.assertEqual(heap.expected_cleanup(model, owner), [])
        self.assertEqual(model.snapshot(), before)

    def test_aliases_keep_pointer_representation_in_release_trace(self):
        for segment in heap.SEGMENTS:
            with self.subTest(segment=segment):
                model, owner, buffer, children, table = self.fixture(segment=segment)
                self.assertEqual(heap.expected_cleanup(model, owner), [buffer, *children, table])

    def test_duplicate_owned_entry_is_rejected_as_outside_profile(self):
        model, owner, _, children, table = self.fixture(count=2)
        model.write_payload(table, struct.pack('<8I', children[0], children[0], 0, 0, 0, 0, 0, 0))
        with self.assertRaises(ValueError):
            heap.expected_cleanup(model, owner)

    def test_generated_cases_cover_scoped_boundaries_and_have_no_duplicates(self):
        cases = list(heap.cleanup_cases())
        self.assertEqual(len(cases), 180)
        self.assertEqual(len({tuple(sorted(case.items())) for _, case in cases}), 180)
        for _, case in cases:
            heap.validate_case(case)
        self.assertEqual({case['segment'] for _, case in cases}, set(heap.SEGMENTS))
        self.assertEqual({case['count'] for _, case in cases}, {-(1 << 31), -1, 0, 1, 2, 8})
        self.assertEqual({case['pooled_object'] for _, case in cases}, {True, False})
        self.assertEqual({case['table_order'] for _, case in cases}, {'first', 'last'})
        components = list(heap.component_cases())
        self.assertEqual(len(components), 96)
        self.assertEqual({case['registered'] for _, case in components}, {True, False})

    def test_oversized_invalid_or_overlapping_owner_profiles_are_rejected(self):
        for change in ({'count': 9}, {'count': -(1 << 31) - 1}, {'pool_size': 15},
                       {'pooled_object': True, 'pool_size': 128}, {'pattern': 'duplicates'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                heap.validate_case(dict(heap.BASE_CASE, **change))
        with self.assertRaises(ValueError):
            heap.owner_location(heap.initial_model(1024, 0), 0x120000)

    def test_owner_requires_consistent_alias_and_live_pooled_capacity(self):
        model = heap.initial_model(1024, 0)
        model.setup()
        small = model.allocate(12)
        owner = model.allocate(128)
        self.assertEqual(heap.owner_location(model, owner), ('pool', (owner & heap.native.MASK) - heap.BASES['pool']))
        for invalid in (small, owner + 4, owner | 0x80000000, -1, 1 << 32):
            with self.subTest(pointer=invalid), self.assertRaises(ValueError):
                heap.owner_location(model, invalid)
        model.free(owner)
        with self.assertRaises(ValueError):
            heap.owner_location(model, owner)


class HeapNativeCustodyTests(unittest.TestCase):
    def program(self, corruption=None):
        words = {'memory_set_manager': 0xAF840010, 'memory_set_lock': 0xAF840018}
        if corruption:
            words.update(corruption)
        ranges = {int(heap.BY_NAME[name]['address'], 16): struct.pack('<III', word, 0x03E00008, 0)
                  for name, word in words.items()}
        return SimpleNamespace(target=lambda address, size: ranges[address][:size])

    def test_global_addresses_are_derived_from_pinned_store_operands(self):
        self.assertEqual(heap.global_addresses(self.program()),
                         {'memory_set_manager': 0x8A818, 'memory_set_lock': 0x8A820})
        for word in (0xAF840014, 0x8F840010, 0xAF850010, 0xAC840010):
            with self.subTest(word=hex(word)), self.assertRaises(ValueError):
                heap.global_addresses(self.program({'memory_set_manager': word}))

    def test_unqualified_backend_is_rejected_before_guest_execution(self):
        with patch.dict(sys.modules, {'unicorn': SimpleNamespace(__version__='2.1.4')}), \
                self.assertRaisesRegex(ValueError, 'separately'):
            heap.backend_identity()

    def test_existing_report_is_preserved_before_loading_original_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / '.decomp-lab' / 'report.json'
            path.parent.mkdir()
            path.write_bytes(b'preserved')
            with patch.object(heap, 'ROOT', root), patch.object(heap, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(heap.main(['--output', str(path)]), 2)
                verify.assert_not_called()
            self.assertEqual(path.read_bytes(), b'preserved')

    def test_report_escape_is_rejected_before_loading_original_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(heap, 'ROOT', root), patch.object(heap, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(heap.main(['--output', str(root / '.decomp-lab' / '..' / 'public.json')]), 2)
                verify.assert_not_called()
            self.assertFalse((root / 'public.json').exists())


if __name__ == '__main__':
    unittest.main()
