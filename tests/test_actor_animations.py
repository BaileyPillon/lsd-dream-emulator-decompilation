"""Owned animation-selection fixtures with explicit expected state changes."""
import struct
import unittest
from unittest.mock import patch
from uuid import uuid4

from tests.test_actor_payloads import SYMBOLS, command
from tools.actor_animation_model import AnimationPayloadPlan, first_frame
from tools import verify_actor_factory as factory
from tools import verify_actor_animations as native_check
from tools.actor_animation_fixtures import CHILD_TYPES, PARENT_WORDS, parent_word_fixture


def mom(commands=(), frames=(7, 13)):
    first = [command(8), command(2, struct.pack('<I', 1))]
    starts = (28, 44 + sum(map(len, first)))
    tmd = starts[1] + 16 + sum(map(len, commands))
    raw = bytearray(tmd + 40)
    raw[:4], raw[12:16] = b'MOM ', b'MOS '
    struct.pack_into('<II', raw, 4, len(raw), tmd)
    struct.pack_into('<III', raw, 16, 2, starts[0] - 12, starts[1] - 12)
    for offset, count, records in zip(starts, frames, (first, commands)):
        struct.pack_into('<I', raw, offset + 4, count)
        struct.pack_into('<H', raw, offset + 10, len(records))
        raw[offset + 16:offset + 16 + sum(map(len, records))] = b''.join(records)
    struct.pack_into('<III', raw, tmd, 0x41, 0, 1)
    return bytes(raw)


def prepared(raw=None):
    pool = factory.initial_pool('poison')
    pool.setup()
    plan = AnimationPayloadPlan(mom() if raw is None else raw, pool, SYMBOLS,
                                factory.DATA, (0, 0, 0), (4096, 4096, 4096))
    actor = plan.create_actor()
    return plan, actor


class ActorAnimationTests(unittest.TestCase):
    def test_unqualified_backend_is_rejected_before_build_or_media_access(self):
        destination = factory.ROOT / '.decomp-lab' / ('unittest-animation-' + uuid4().hex)
        with patch.object(factory.common.heap, 'backend_identity', return_value={'package_version': '2.1.4'}), \
                patch.object(factory.common, 'require_ninja') as ninja:
            with self.assertRaisesRegex(ValueError, 'Unicorn 2.1.2'):
                native_check.verify(factory.ROOT / 'not-accessed.xml', destination, 'synthetic')
            ninja.assert_not_called()
        self.assertFalse(destination.exists())

    def test_selected_header_has_its_own_duration_and_frame_start(self):
        raw = mom()
        first, second = first_frame(raw, 0), first_frame(raw, 1)
        self.assertEqual((first.offset, first.frames, len(first.records)), (28, 7, 2))
        self.assertEqual((second.offset, second.frames, len(second.records)), (56, 13, 0))

    def test_selection_resets_the_existing_counter_and_stores_header_not_end(self):
        plan, actor = prepared()
        plan.put(actor.pointer, 132, 5)
        snapshots = plan.select_animation(actor, 1)
        self.assertEqual(plan.word(actor.pointer, 124), 1)
        self.assertEqual(plan.word(actor.pointer, 128), 13)
        self.assertEqual(plan.word(actor.pointer, 132), 0)
        self.assertEqual(plan.word(actor.pointer, 136), factory.DATA + 56 + 8)
        self.assertTrue(any(row.kind == 'actor' for row in snapshots))

    def test_immediate_attribute_commands_apply_in_original_order(self):
        raw = mom((command(0, struct.pack('<II', 0xffffff00, 0x31)),
                   command(0, struct.pack('<II', 0x0fffffff, 0x80000000))))
        plan, actor = prepared(raw)
        plan.select_animation(actor, 1)
        self.assertEqual(plan.word(actor.nodes[0].pointer, 16), 0x80000031)

    def test_repeated_relative_position_restarts_apply_to_retained_state(self):
        raw = mom((command(1, struct.pack('<iii', 3, -5, 7), flags=9),))
        plan, actor = prepared(raw)
        node = actor.nodes[0]
        plan.write(node.state, 24, struct.pack('<iii', 10, 20, 30))
        first = plan.select_animation(actor, 1)
        self.assertEqual(struct.unpack('<iii', plan.read(node.state, 24, 12)), (13, 15, 37))
        plan.select_animation(actor, 1)
        self.assertEqual(struct.unpack('<iii', plan.read(node.state, 24, 12)), (16, 10, 44))
        before = next(row for row in first if row.pointer == node.state)
        self.assertEqual(struct.unpack_from('<iii', before.expected, 24), (13, 15, 37))

    def test_first_nonzero_geometry_binding_is_retained(self):
        plan, actor = prepared(mom((command(2, struct.pack('<I', 0)),)))
        pointer = plan.word(actor.nodes[0].pointer, 32)
        plan.select_animation(actor, 1)
        self.assertEqual(plan.word(actor.nodes[0].pointer, 32), pointer)
        self.assertEqual(plan.geometry_indices, {0})

    def test_only_the_full_word_root_sentinels_select_the_actor(self):
        for word in (0, 0xffff):
            with self.subTest(word=hex(word)):
                plan, actor = prepared(parent_word_fixture(word))
                target = actor.nodes[CHILD_TYPES.index(9)]
                plan.select_animation(actor, 1)
                self.assertIs(target.coordinate_parent, actor)
                self.assertEqual(plan.word(target.coordinate, 72), actor.coordinate)

    def test_other_parent_words_look_up_the_low_byte_including_zero_and_255(self):
        for word in PARENT_WORDS[2:]:
            with self.subTest(word=hex(word)):
                plan, actor = prepared(parent_word_fixture(word))
                target = actor.nodes[CHILD_TYPES.index(9)]
                parent = actor.nodes[CHILD_TYPES.index(word & 255)]
                plan.select_animation(actor, 1)
                self.assertIs(target.coordinate_parent, parent)
                self.assertEqual(plan.word(target.pointer, 12), parent.pointer)
                self.assertEqual(plan.word(target.coordinate, 72), parent.coordinate)
                plan.destroy_actor(actor)
                self.assertFalse(plan.live)

    def test_high_bits_do_not_turn_an_absent_child_into_the_actor_root(self):
        plan, actor = prepared(mom((command(3, struct.pack('<I', 0x12340000)),)))
        with self.assertRaisesRegex(ValueError, 'absent child type'):
            plan.select_animation(actor, 1)

    def test_parent_fixture_rejects_values_outside_its_encoded_word(self):
        for word in (-1, 1 << 32, True):
            with self.subTest(word=word), self.assertRaises(ValueError):
                parent_word_fixture(word)

    def test_repeated_parent_command_keeps_the_existing_coordinate_parent(self):
        plan, actor = prepared(mom((command(3, struct.pack('<I', 0)),)))
        plan.select_animation(actor, 1)
        events = len(plan.events)
        plan.select_animation(actor, 1)
        self.assertEqual(len(plan.events), events)

    def test_absent_child_type_is_ignored_without_changing_other_children(self):
        plan, actor = prepared(mom((command(0, struct.pack('<II', 0, 123), target=88),)))
        old = plan.read(actor.nodes[0].pointer, 0, 88)
        plan.select_animation(actor, 1)
        self.assertEqual(plan.read(actor.nodes[0].pointer, 0, 88), old)

    def test_invalid_index_and_header_extents_are_rejected(self):
        for index in (-1, 2, True):
            with self.subTest(index=index), self.assertRaises(ValueError):
                first_frame(mom(), index)
        raw = bytearray(mom())
        struct.pack_into('<I', raw, 24, len(raw))
        with self.assertRaisesRegex(ValueError, 'header or first frame'):
            first_frame(raw, 1)

    def test_truncated_and_zero_length_command_records_are_rejected(self):
        raw = bytearray(mom((command(8),)))
        offset = first_frame(raw, 1).offset + 16
        struct.pack_into('<I', raw, offset, 9)
        with self.assertRaisesRegex(ValueError, 'command exceeds'):
            first_frame(raw, 1)
        struct.pack_into('<I', raw, offset, 9 | 255 << 24)
        with self.assertRaisesRegex(ValueError, 'command exceeds'):
            first_frame(raw, 1)

    def test_zero_frame_animation_is_an_explicit_profile_limit(self):
        with self.assertRaisesRegex(ValueError, 'nonempty animation'):
            first_frame(mom(frames=(7, 0)), 1)

    def test_all_owned_allocations_are_released_after_switches(self):
        plan, actor = prepared(mom((command(3, struct.pack('<I', 0)),)))
        for index in (1, 0, 1, 0):
            plan.select_animation(actor, index)
        plan.destroy_actor(actor)
        self.assertFalse(plan.live)
        self.assertEqual(len(plan.pool.blocks), 1)
        self.assertTrue(plan.pool.blocks[0].free)


if __name__ == '__main__':
    unittest.main()
