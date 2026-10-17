"""Predict original animation selection and immediate first-frame application.

Uses original MOM data and the independent constructor/allocator model. Native
memory and observations are never inputs to the expected snapshots.
"""
from dataclasses import dataclass
import struct

from tools.actor_payload_model import ActorPayloadPlan


@dataclass(frozen=True)
class AnimationFrame:
    index: int
    offset: int
    frames: int
    records: tuple


def first_frame(raw, index):
    """Follow the mapped MOS table, retaining the original selected header."""
    raw = bytes(raw)
    if len(raw) < 24 or raw[:4] != b'MOM ' or raw[12:16] != b'MOS ':
        raise ValueError('Require a complete original MOM/MOS input.')
    size, tmd, count = struct.unpack_from('<II4xI', raw, 4)
    if size != len(raw) or tmd % 4 or not 20 + count * 4 <= tmd <= size - 12:
        raise ValueError('Invalid MOM/MOS table extent.')
    if type(index) is not int or not 0 <= index < count:
        raise ValueError('Animation index is outside the original table.')
    offset = 12 + struct.unpack_from('<I', raw, 20 + index * 4)[0]
    if offset % 4 or not 20 + count * 4 <= offset <= tmd - 16:
        raise ValueError('Animation header or first frame exceeds the MOS extent.')
    frames = struct.unpack_from('<I', raw, offset + 4)[0]
    if not frames:
        raise ValueError('This first-frame profile requires a nonempty animation.')
    records, cursor = [], offset + 16
    for _ in range(struct.unpack_from('<H', raw, offset + 10)[0]):
        if cursor + 4 > tmd:
            raise ValueError('Truncated animation command header.')
        lead = struct.unpack_from('<I', raw, cursor)[0]
        words = lead >> 24
        if not words or cursor + words * 4 > tmd:
            raise ValueError('Animation command exceeds its original MOS extent.')
        records.append((lead & 255, lead >> 16 & 15, lead >> 20 & 15,
                        raw[cursor + 4:cursor + words * 4]))
        cursor += words * 4
    return AnimationFrame(index, offset, frames, tuple(records))


class AnimationPayloadPlan(ActorPayloadPlan):
    def __init__(self, *arguments, **keywords):
        self.geometry_indices = set()
        self.selections = []
        super().__init__(*arguments, **keywords)

    def bind_geometry(self, node, model, index):
        super().bind_geometry(node, model, index)
        self.geometry_indices.add(index)

    def select_animation(self, actor, index):
        frame = first_frame(self.raw, index)
        self.put(actor.pointer, 124, index)
        self.put(actor.pointer, 128, frame.frames)
        self.put(actor.pointer, 136, self.data_address + frame.offset + 8)
        self.put(actor.pointer, 132, 0)
        for type_id, kind, flags, payload in frame.records:
            if type_id not in self.types:
                continue
            node = actor.nodes[self.types.index(type_id)]
            self.put(node.coordinate, 0, 0)
            if kind == 0:
                if len(payload) < 8:
                    raise ValueError('Truncated animation attribute command.')
                mask, value = struct.unpack_from('<II', payload)
                self.put(node.pointer, 16, (self.word(node.pointer, 16) & mask) | value)
            elif kind == 1:
                self.motion(node, flags, payload)
            elif kind == 2:
                if len(payload) < 4:
                    raise ValueError('Truncated animation geometry command.')
                selection = struct.unpack_from('<H', payload)[0]
                if selection and not self.word(node.pointer, 32):
                    self.bind_geometry(node, actor.model, selection - 1)
            elif kind == 3 and node.coordinate_parent is None:
                if len(payload) < 4:
                    raise ValueError('Truncated animation parent command.')
                parent_id = struct.unpack_from('<H', payload)[0]
                if parent_id in (0, 0xffff):
                    parent = actor
                elif parent_id & 255 in self.types:
                    parent = actor.nodes[self.types.index(parent_id & 255)]
                else:
                    raise ValueError('Animation parent references an absent child type.')
                ancestor = parent
                while ancestor is not None:
                    if ancestor is node:
                        raise ValueError('Animation parent would introduce a coordinate cycle.')
                    ancestor = ancestor.coordinate_parent
                node.coordinate_parent = parent
                self.put(node.pointer, 12, parent.pointer)
                self.put(node.coordinate, 72, parent.coordinate)
                self.attach(parent, node)
                self.write(node.coordinate, 24, bytes(12))
        snapshot = tuple(self.snapshot(kind, pointer, size)
                         for pointer, (kind, size) in sorted(self.live.items()))
        self.selections.append(dict(index=index, frame=frame, payloads=snapshot,
                                    geometry_indices=tuple(sorted(self.geometry_indices))))
        return snapshot
