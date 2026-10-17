"""Independent whole-script state prediction for original actor animation ticks.

Callback execution is outside this profile and is never stubbed. The original
constructor disables that callback; playback is enabled through its real API.
"""
from dataclasses import dataclass
import struct

from tools.actor_animation_model import AnimationPayloadPlan


@dataclass(frozen=True)
class ScriptFrame:
    index: int
    offset: int
    next_offset: int
    records: tuple


def script_frames(raw, index):
    raw = bytes(raw)
    if raw[:4] != b'MOM ' or raw[12:16] != b'MOS ' or len(raw) < 24:
        raise ValueError('Require an original bounded MOM/MOS.')
    size, tmd, count = struct.unpack_from('<II4xI', raw, 4)
    if size != len(raw) or type(index) is not int or not 0 <= index < count:
        raise ValueError('Invalid model size or animation index.')
    if tmd % 4 or 20 + count * 4 > tmd or tmd + 12 > size or struct.unpack_from('<I', raw, tmd)[0] != 0x41:
        raise ValueError('Invalid MOS/TMD extents.')
    offsets = [12 + struct.unpack_from('<I', raw, 20 + 4 * item)[0] for item in range(count)]
    if any(offset % 4 or offset < 20 + count * 4 or offset + 8 > tmd for offset in offsets):
        raise ValueError('Invalid animation header extent.')
    offset = offsets[index]
    limit = min(bound for bound in {*offsets, tmd} if bound > offset)
    frames = struct.unpack_from('<I', raw, offset + 4)[0]
    cursor, result = offset + 8, []
    if not frames or frames > (limit - cursor) // 8:
        raise ValueError('Invalid frame count for the bounded script.')
    for number in range(frames):
        start, records = cursor, []
        if cursor + 8 > limit:
            raise ValueError('Truncated frame header.')
        record_count = struct.unpack_from('<H', raw, cursor + 2)[0]
        cursor += 8
        for _ in range(record_count):
            if cursor + 4 > limit:
                raise ValueError('Truncated command header.')
            lead = struct.unpack_from('<I', raw, cursor)[0]
            type_id, kind, flags, words = lead & 255, lead >> 16 & 15, lead >> 20 & 15, lead >> 24
            minimum = {0: 3, 2: 2, 3: 2}.get(kind, 1)
            if kind == 1:
                minimum = 1 + (3 if flags & 2 else 0) + (2 if flags & 4 else 0) + (3 if flags & 8 else 0)
            if words < minimum or cursor + words * 4 > limit:
                raise ValueError('Invalid bounded command payload.')
            records.append((type_id, kind, flags, raw[cursor + 4:cursor + words * 4]))
            cursor += words * 4
        result.append(ScriptFrame(number, start, cursor, tuple(records)))
    return tuple(result)


class PlaybackPlan(AnimationPayloadPlan):
    def __init__(self, *arguments, **keywords):
        super().__init__(*arguments, **keywords)
        self.scripts = tuple(script_frames(self.raw, index) for index in range(self.animations))
        self.last_tick_frame = None

    def snapshots(self):
        return tuple(self.snapshot(kind, pointer, size)
                     for pointer, (kind, size) in sorted(self.live.items()))

    def apply_frame(self, actor, frame):
        for type_id, kind, flags, payload in frame.records:
            if type_id not in self.types:
                continue
            node = actor.nodes[self.types.index(type_id)]
            self.put(node.coordinate, 0, 0)
            if kind == 0:
                mask, value = struct.unpack_from('<II', payload)
                self.put(node.pointer, 16, (self.word(node.pointer, 16) & mask) | value)
            elif kind == 1:
                self.motion(node, flags, payload)
            elif kind == 2:
                selection = struct.unpack_from('<H', payload)[0]
                if selection and not self.word(node.pointer, 32):
                    self.bind_geometry(node, actor.model, selection - 1)
            elif kind == 3 and node.coordinate_parent is None:
                parent_word = struct.unpack_from('<I', payload)[0]
                if parent_word in (0, 0xffff):
                    parent = actor
                elif parent_word & 255 in self.types:
                    parent = actor.nodes[self.types.index(parent_word & 255)]
                else:
                    raise ValueError('Absent coordinate parent type.')
                ancestor = parent
                while ancestor is not None:
                    if ancestor is node:
                        raise ValueError('Cyclic coordinate parent.')
                    ancestor = ancestor.coordinate_parent
                node.coordinate_parent = parent
                self.put(node.pointer, 12, parent.pointer)
                self.put(node.coordinate, 72, parent.coordinate)
                self.attach(parent, node)
                self.write(node.coordinate, 24, bytes(12))

    def play(self, actor):
        self.put(actor.pointer, 144, 1)
        return self.snapshots()

    def pause(self, actor):
        self.put(actor.pointer, 144, 0)
        return self.snapshots()

    def tick(self, actor):
        if self.word(actor.pointer, 140):
            raise ValueError('The callback-disabled playback profile cannot predict a callback.')
        self.put(actor.pointer, 36, self.word(actor.pointer, 36) + 1)
        self.last_tick_frame = None
        if self.word(actor.pointer, 144) and self.word(actor.pointer, 128) >= 2:
            frames = self.scripts[self.word(actor.pointer, 124)]
            number = self.word(actor.pointer, 132)
            if number >= len(frames):
                raise ValueError('The retained frame counter exceeds its original script.')
            frame = frames[number]
            if self.word(actor.pointer, 136) != self.data_address + frame.offset:
                raise ValueError('The retained frame cursor differs from its tick counter.')
            self.apply_frame(actor, frame)
            self.last_tick_frame = frame
            number += 1
            if number >= len(frames):
                number, cursor = 0, frames[0].offset
            else:
                cursor = frame.next_offset
            self.put(actor.pointer, 132, number)
            self.put(actor.pointer, 136, self.data_address + cursor)
        self.put(actor.coordinate, 0, 0)
        return self.snapshots()
