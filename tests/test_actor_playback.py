"""Owned multi-frame fixtures with explicit state and cursor expectations."""
import struct
import unittest
from unittest.mock import patch
from uuid import uuid4

from tests.test_actor_payloads import SYMBOLS, command
from tools import verify_actor_factory as factory
from tools import verify_actor_playback as native_check
from tools.actor_playback_model import PlaybackPlan, script_frames


def mom(scripts, types=(9,)):
    scripts = [[tuple(records) for records in frames] for frames in scripts]
    declarations = tuple(record for target in types for record in (
        command(8, target=target), command(2, struct.pack('<I', 1), target=target)))
    scripts[0][0] = declarations + scripts[0][0]
    cursor, offsets, bodies = 20 + len(scripts) * 4, [], []
    for frames in scripts:
        offsets.append(cursor)
        body = struct.pack('<HHI', 0, 0, len(frames))
        for records in frames:
            body += struct.pack('<HHI', 0, len(records), 0) + b''.join(records)
        bodies.append(body)
        cursor += len(body)
    raw = bytearray(cursor + 40)
    raw[:4], raw[12:16] = b'MOM ', b'MOS '
    struct.pack_into('<III', raw, 4, len(raw), cursor, int.from_bytes(b'MOS ', 'little'))
    struct.pack_into('<I', raw, 16, len(scripts))
    for index, (offset, body) in enumerate(zip(offsets, bodies)):
        struct.pack_into('<I', raw, 20 + 4 * index, offset - 12)
        raw[offset:offset + len(body)] = body
    struct.pack_into('<III', raw, cursor, 0x41, 0, 1)
    return bytes(raw)


def prepared(raw):
    pool = factory.initial_pool('poison')
    pool.setup()
    plan = PlaybackPlan(raw, pool, SYMBOLS, factory.DATA, (0, 0, 0), (4096, 4096, 4096))
    return plan, plan.create_actor()


def relative(x):
    return command(1, struct.pack('<iii', x, 0, 0), flags=9)


class ActorPlaybackTests(unittest.TestCase):
    def test_every_frame_has_an_exact_original_stream_extent(self):
        raw = mom((((), (), (relative(3),)),))
        frames = script_frames(raw, 0)
        self.assertEqual([(row.offset, row.next_offset, len(row.records)) for row in frames],
                         [(32, 52, 2), (52, 60, 0), (60, 84, 1)])
        self.assertEqual(struct.unpack_from('<I', raw, 8)[0], 84)

    def test_first_active_tick_reapplies_the_already_selected_first_frame(self):
        plan, actor = prepared(mom((((relative(1),), ()),)))
        node = actor.nodes[0]
        before = plan.word(node.state, 24)
        plan.play(actor)
        plan.tick(actor)
        self.assertEqual(plan.word(node.state, 24), (before + 1) & 0xffffffff)
        self.assertEqual(plan.word(actor.pointer, 132), 1)
        self.assertEqual(plan.word(actor.pointer, 136), factory.DATA + plan.scripts[0][1].offset)
        self.assertEqual(plan.last_tick_frame.index, 0)

    def test_last_frame_wraps_without_applying_the_first_until_the_following_tick(self):
        plan, actor = prepared(mom((((relative(1),), (relative(10),)),)))
        node = actor.nodes[0]
        before = plan.word(node.state, 24)
        plan.play(actor)
        plan.tick(actor)
        plan.tick(actor)
        self.assertEqual(plan.word(node.state, 24), (before + 11) & 0xffffffff)
        self.assertEqual(plan.word(actor.pointer, 132), 0)
        self.assertEqual(plan.word(actor.pointer, 136), factory.DATA + plan.scripts[0][0].offset)
        plan.tick(actor)
        self.assertEqual(plan.word(node.state, 24), (before + 12) & 0xffffffff)

    def test_pause_holds_animation_but_age_and_dirty_state_still_update(self):
        plan, actor = prepared(mom((((relative(1),), (relative(10),)),)))
        plan.play(actor)
        plan.tick(actor)
        plan.pause(actor)
        state = plan.read(actor.nodes[0].state, 0, 40)
        cursor = plan.word(actor.pointer, 136)
        age = plan.word(actor.pointer, 36)
        plan.put(actor.coordinate, 0, 1)
        for _ in range(2):
            plan.tick(actor)
            self.assertIsNone(plan.last_tick_frame)
        self.assertEqual(plan.read(actor.nodes[0].state, 0, 40), state)
        self.assertEqual(plan.word(actor.pointer, 132), 1)
        self.assertEqual(plan.word(actor.pointer, 136), cursor)
        self.assertEqual(plan.word(actor.pointer, 36), age + 2)
        self.assertEqual(plan.word(actor.coordinate, 0), 0)
        plan.play(actor)
        plan.tick(actor)
        self.assertEqual(plan.last_tick_frame.index, 1)
        self.assertEqual(plan.word(actor.pointer, 132), 0)

    def test_single_frame_scripts_are_not_reinterpreted_by_active_ticks(self):
        plan, actor = prepared(mom((((relative(1),),),)))
        before = plan.read(actor.nodes[0].state, 0, 40)
        cursor = plan.word(actor.pointer, 136)
        plan.play(actor)
        for _ in range(3):
            plan.tick(actor)
            self.assertIsNone(plan.last_tick_frame)
        self.assertEqual(plan.read(actor.nodes[0].state, 0, 40), before)
        self.assertEqual(plan.word(actor.pointer, 132), 0)
        self.assertEqual(plan.word(actor.pointer, 136), cursor)
        self.assertEqual(plan.word(actor.pointer, 36), 3)

    def test_reselection_resets_the_cursor_and_preserves_the_playing_flag(self):
        plan, actor = prepared(mom((((), ()), ((), (), ()))))
        plan.play(actor)
        plan.tick(actor)
        plan.select_animation(actor, 1)
        self.assertEqual(plan.word(actor.pointer, 132), 0)
        self.assertEqual(plan.word(actor.pointer, 128), 3)
        self.assertEqual(plan.word(actor.pointer, 136), factory.DATA + plan.scripts[1][0].offset)
        self.assertEqual(plan.word(actor.pointer, 144), 1)

    def test_callbacks_are_rejected_before_mutating_the_tick_state(self):
        plan, actor = prepared(mom((((), ()),)))
        plan.put(actor.pointer, 140, 1)
        age = plan.word(actor.pointer, 36)
        with self.assertRaisesRegex(ValueError, 'callback-disabled'):
            plan.tick(actor)
        self.assertEqual(plan.word(actor.pointer, 36), age)

    def test_later_parent_frames_keep_full_word_sentinel_semantics(self):
        for word in (0xffff, 0x10000, 0x1234ffff):
            with self.subTest(word=hex(word)):
                raw = mom((((), (command(3, struct.pack('<I', word)),)),), types=(0, 9, 255))
                plan, actor = prepared(raw)
                plan.play(actor)
                plan.tick(actor)
                plan.tick(actor)
                target = actor.nodes[1]
                parent = actor if word == 0xffff else actor.nodes[(0, 9, 255).index(word & 255)]
                self.assertIs(target.coordinate_parent, parent)
                plan.destroy_actor(actor)
                self.assertFalse(plan.live)

    def test_age_uses_original_word_wrapping(self):
        plan, actor = prepared(mom((((),),)))
        plan.put(actor.pointer, 36, 0xffffffff)
        plan.tick(actor)
        self.assertEqual(plan.word(actor.pointer, 36), 0)

    def test_counter_and_cursor_must_describe_a_valid_retained_frame(self):
        for field, value in ((132, 2), (136, factory.DATA)):
            with self.subTest(field=field):
                plan, actor = prepared(mom((((), ()),)))
                plan.play(actor)
                plan.put(actor.pointer, field, value)
                with self.assertRaisesRegex(ValueError, 'retained frame'):
                    plan.tick(actor)

    def test_truncated_frame_tables_and_commands_are_rejected(self):
        raw = bytearray(mom((((), ()),)))
        struct.pack_into('<I', raw, 28, 99)
        with self.assertRaisesRegex(ValueError, 'frame count'):
            script_frames(raw, 0)
        raw = bytearray(mom((((), (relative(1),)),)))
        last = script_frames(raw, 0)[1]
        struct.pack_into('<I', raw, last.offset + 8, 9)
        with self.assertRaisesRegex(ValueError, 'command payload'):
            script_frames(raw, 0)

    def test_unqualified_backend_is_rejected_before_any_build_or_media_access(self):
        destination = factory.ROOT / '.decomp-lab' / ('unittest-playback-' + uuid4().hex)
        with patch.object(factory.common.heap, 'backend_identity', return_value={'package_version': '2.1.4'}), \
                patch.object(factory.common, 'require_ninja') as ninja:
            with self.assertRaisesRegex(ValueError, 'Unicorn 2.1.2'):
                native_check.verify(factory.ROOT / 'not-accessed.xml', destination, 'synthetic')
            ninja.assert_not_called()
        self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
