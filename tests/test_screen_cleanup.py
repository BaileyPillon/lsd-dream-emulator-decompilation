"""Enforce the initialized graph boundary without proprietary inputs."""
import struct
import unittest

from research.screen_lifecycle import verify_cleanup as tool


class ScreenCleanupProfile(unittest.TestCase):
    def case(self, **changes):
        return dict(dict(kind='chart', segment=0x80000000, seed=1,
                         buffers=True, links=True, sound='owned_bank'), **changes)

    def test_unknown_or_incomplete_context_is_rejected(self):
        for changes in ({'segment': 0x40000000}, {'sound': 'assume_loaded'},
                        {'buffers': 1}, {'links': 'yes'}, {'seed': True}, {'kind': 'movie'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                tool.validate_case(self.case(**changes))
        incomplete = self.case(); del incomplete['sound']
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            tool.validate_case(incomplete)

    def test_profile_keeps_ownership_modes_and_aliases_distinct(self):
        profiles = list(tool.cases())
        self.assertEqual(len(profiles), 144)
        identities = {tuple(sorted(case.items())) for case in profiles}
        self.assertEqual(len(identities), len(profiles))
        for kind in ('main', 'chart'):
            for sound in ('borrowed', 'owned_no_bank', 'owned_bank'):
                self.assertEqual(sum(p['kind'] == kind and p['sound'] == sound for p in profiles), 24)

    def test_chart_fixture_owns_all_hundred_distinct_cells(self):
        fixture = tool.Fixture(self.case())
        self.assertEqual(len(set(fixture.cells)), 100)
        pool = fixture.initial['pool']
        pointers = struct.unpack_from('<100I', pool, fixture.offset(fixture.root) + 0xA8)
        self.assertEqual(list(pointers), fixture.cells)
        for pointer in pointers:
            table, = struct.unpack_from('<I', pool, fixture.offset(pointer))
            coordinate, = struct.unpack_from('<I', pool, fixture.offset(pointer) + 0x14)
            self.assertEqual(table, tool.TABLES['cell'])
            self.assertNotEqual(coordinate, 0)
            self.assertEqual(fixture.free_trace.count(pointer), 1)

    def test_borrowed_sound_and_its_bank_remain_owned_externally(self):
        fixture = tool.Fixture(self.case(sound='borrowed'))
        self.assertNotIn(fixture.sound, fixture.free_trace)
        fixture.model.owned_block(fixture.sound)
        offset = fixture.offset(fixture.sound)
        self.assertEqual(fixture.initial['pool'][offset:offset+0x64],
                         fixture.model.snapshot()['pool'][offset:offset+0x64])
        self.assertEqual(fixture.sdk_before, fixture.sdk_after)
        self.assertEqual(fixture.initial['object'], fixture.model.snapshot()['object'])

    def test_unopened_sound_does_not_release_another_instances_bank(self):
        fixture = tool.Fixture(self.case(sound='owned_no_bank'))
        self.assertIn(fixture.sound, fixture.free_trace)
        self.assertEqual(fixture.initial['object'], fixture.model.snapshot()['object'])
        for address in (0x6E188, 0x8EA2C, 0x90BD0, 0x90BD4):
            self.assertEqual(fixture.sdk_before[address], fixture.sdk_after[address])
        self.assertEqual(struct.unpack('<I', fixture.sdk_after[0x8A8C4])[0], 1)

    def test_allocated_bank_returns_its_interval_and_clears_sdk_ownership(self):
        fixture = tool.Fixture(self.case())
        self.assertEqual(struct.unpack_from('<II', fixture.model.snapshot()['object'], tool.heap.OFFSET),
                         (0x40001010, 0x7EFF0))
        self.assertEqual(fixture.sdk_after[0x8EA2C], bytes(16))
        self.assertEqual(fixture.sdk_after[0x90BD0], bytes(2))

    def test_owned_graph_cleanup_preserves_only_declared_borrowed_objects(self):
        for kind in ('main', 'chart'):
            fixture = tool.Fixture(self.case(kind=kind))
            live = {fixture.model.block_pointer(block.offset)+4 for block in fixture.model.blocks if not block.free}
            self.assertEqual(live, {fixture.observer, fixture.borrowed_child})
            self.assertEqual(fixture.get(fixture.observer, 4), 0)
            self.assertEqual(fixture.get(fixture.borrowed_child, 8), 0)


if __name__ == '__main__':
    unittest.main()
