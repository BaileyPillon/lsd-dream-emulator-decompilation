"""Owned fixtures test independent factory plans without game data or Unicorn."""
import struct
import unittest

from tools.actor_factory_model import OwnershipPlan
from tools import verify_actor_factory as verifier


def mom(parents=((9, 0), (2, 9)), animations=2, objects=2):
    commands = [struct.pack('<I', item | 8 << 16 | 1 << 24) for item in (9, 2)]
    commands += [struct.pack('<II', item | 3 << 16 | 2 << 24, parent) for item, parent in parents]
    animation = 20 + animations * 4
    frame = animation + 8
    tmd = frame + 8 + sum(map(len, commands))
    raw = bytearray(tmd + 12 + objects * 28)
    raw[:4], raw[12:16] = b'MOM ', b'MOS '
    struct.pack_into('<II', raw, 4, len(raw), tmd)
    struct.pack_into('<I', raw, 16, animations)
    for index in range(animations):
        struct.pack_into('<I', raw, 20 + index*4, animation-12)
    struct.pack_into('<I', raw, animation+4, 1)
    struct.pack_into('<H', raw, frame+2, len(commands))
    raw[frame+8:tmd] = b''.join(commands)
    struct.pack_into('<III', raw, tmd, 0x41, 0, objects)
    return raw


def plan(raw=None, scenario='actor-first', pattern='distinct'):
    pool = verifier.initial_pool(pattern)
    pool.setup()
    reference = OwnershipPlan(mom() if raw is None else raw, pool)
    return reference, reference.run(scenario)


class OwnershipPlanTests(unittest.TestCase):
    def test_all_scenarios_release_resources_and_retain_original_bytes(self):
        raw = mom()
        original = bytes(raw)
        for scenario in verifier.SCENARIOS:
            for pattern in ('poison', 'distinct'):
                with self.subTest(scenario=scenario, pattern=pattern):
                    reference, events = plan(raw, scenario, pattern)
                    self.assertEqual(len(reference.pool.blocks), 1)
                    self.assertTrue(reference.pool.blocks[0].free)
                    self.assertEqual(reference.pool.blocks[0].size, verifier.POOL_SIZE)
                    self.assertEqual(sum(event[0] == 'memory_allocate_mem' for event in events),
                                     sum(event[0] == 'memory_free_mem' for event in events))
        self.assertEqual(bytes(raw), original)

    def test_model_geometry_and_animation_counts_drive_requests(self):
        _, events = plan(scenario='actor-first')
        self.assertEqual([event[1] for event in events[:8]], [56, 48, 12, 36, 36, 44, 44, 44])
        _, other = plan(mom(animations=3, objects=1))
        self.assertEqual([event[1] for event in other[:8]], [56, 48, 8, 36, 44, 44, 44, 44])

    def test_borrowed_actor_lifetimes_reuse_the_same_address(self):
        _, events = plan()
        actors = [event[2] for event in events if event[:2] == ('memory_allocate_mem', 152)]
        self.assertEqual(len(actors), 2)
        self.assertEqual(actors[0], actors[1])

    def test_owned_actor_allocates_itself_before_its_model(self):
        _, events = plan(scenario='owned')
        self.assertEqual([event[1] for event in events[:6]], [152, 80, 40, 56, 48, 12])

    def test_model_first_notification_destroys_actor_before_model(self):
        _, events = plan(scenario='model-first')
        model = events[0][2]
        actor = next(event[2] for event in events if event[:2] == ('memory_allocate_mem', 152))
        self.assertEqual(events[-2:], [('memory_free_mem', actor, 0), ('memory_free_mem', model, 0)])

    def test_duplicate_parent_commands_do_not_allocate_extra_links(self):
        _, once = plan(mom())
        _, twice = plan(mom(parents=((9, 0), (2, 9), (2, 9))))
        self.assertEqual(once, twice)

    def test_unknown_target_type_is_ignored_before_parent_lookup(self):
        _, expected = plan(mom())
        _, actual = plan(mom(parents=((9, 0), (2, 9), (77, 88))))
        self.assertEqual(actual, expected)

    def test_parent_sentinel_ffff_attaches_to_actor(self):
        _, zero = plan(mom(parents=((9, 0), (2, 0))))
        _, sentinel = plan(mom(parents=((9, 65535), (2, 65535))))
        self.assertEqual(zero, sentinel)

    def test_absent_and_cyclic_parents_are_outside_profile(self):
        for parents in (((9, 77),), ((9, 9),), ((9, 2), (2, 9))):
            with self.subTest(parents=parents), self.assertRaises(ValueError):
                plan(mom(parents=parents))

    def test_bad_animation_pointer_and_command_extent_are_rejected(self):
        for offset, value in ((20, 0), (20, 0x10000), (38, 1000), (44, 9 | 3 << 16 | 1 << 24)):
            raw = mom()
            struct.pack_into('<I' if offset != 38 else '<H', raw, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                plan(raw)

    def test_unknown_scenario_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unknown ownership scenario'):
            plan(scenario='unclassified')


class TraceComparisonTests(unittest.TestCase):
    def test_equal_counts_cannot_hide_wrong_request_size(self):
        with self.assertRaisesRegex(ValueError, 'planned_heap_event 0'):
            verifier.compare_events([('memory_allocate_mem', 32, 100)], [('memory_allocate_mem', 36, 100)])

    def test_equal_release_sets_cannot_hide_wrong_order(self):
        with self.assertRaisesRegex(ValueError, 'planned_heap_event 0'):
            verifier.compare_events([('memory_free_mem', 12, 0), ('memory_free_mem', 28, 0)],
                                    [('memory_free_mem', 28, 0), ('memory_free_mem', 12, 0)])

    def test_missing_and_extra_events_are_rejected(self):
        event = ('memory_free_mem', 12, 0)
        for actual, expected in (([event], []), ([], [event])):
            with self.subTest(actual=actual), self.assertRaisesRegex(ValueError, 'planned_heap_event 0'):
                verifier.compare_events(actual, expected)


if __name__ == '__main__':
    unittest.main()
