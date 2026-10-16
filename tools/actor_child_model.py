"""Independent first-frame enumeration and child-construction reference model.

Only successful, bounded construction is modeled. Supplied actor/model/list
descriptors, an unlocked pool and the SDK matrix table are fixture inputs.
Untouched bytes retain their supplied values, including allocator residue.
"""
from dataclasses import dataclass
import struct

from tools.heap_model import PoolModel

MANAGER, POOL, ACTOR = 0x100000, 0x120000, 0x110020
MODEL, PART_LIST, DATA = 0x111020, 0x112020, 0x150000
POOL_SIZE = 0x10000
SDK_TABLE = 0x8E98C
SDK_MATRIX = struct.pack('<9hH3i', 4096, 0, 0, 0, 4096, 0, 0, 0, 4096, 0, 0, 0, 0)
PATTERNS = ('poison', 'distinct')


@dataclass(frozen=True)
class Record:
    type_id: int
    kind: int
    flags: int
    key: int | None


@dataclass(frozen=True)
class FirstFrame:
    mos: bytes
    records: tuple
    offset: int

    @property
    def child_count(self):
        return sum(record.kind == 8 and record.flags == 0 for record in self.records)


def decode_first_frame(raw):
    """Follow func_800453DC's arithmetic, rather than the animation offset table."""
    if len(raw) < 24 or raw[:4] != b'MOM ':
        raise ValueError('Truncated MOM header or absent signature.')
    size, tmd = struct.unpack_from('<II', raw, 4)
    if size != len(raw) or tmd % 4 or not 20 <= tmd <= size - 12:
        raise ValueError('MOM declared extent or TMD offset is invalid.')
    if raw[12:16] != b'MOS ' or struct.unpack_from('<I', raw, tmd)[0] != 0x41:
        raise ValueError('MOS or TMD signature is absent.')
    objects = struct.unpack_from('<I', raw, tmd + 8)[0]
    if tmd + 12 + objects * 28 > size:
        raise ValueError('TMD object descriptors exceed the MOM extent.')
    animations = struct.unpack_from('<I', raw, 16)[0]
    # The native enumerator skips the table and the eight-byte animation header.
    frame = 28 + animations * 4
    if not animations or frame + 8 > tmd or tmd - 12 >= 0x20000:
        raise ValueError('Native first frame exceeds the bounded MOS fixture.')
    count = struct.unpack_from('<H', raw, frame + 2)[0]
    cursor, records = frame + 8, []
    for _ in range(count):
        if cursor + 4 > tmd:
            raise ValueError('Truncated first-frame record header.')
        lead = struct.unpack_from('<I', raw, cursor)[0]
        type_id, kind = lead & 255, (lead >> 16) & 15
        flags, words = (lead >> 20) & 15, lead >> 24
        if not words or cursor + words * 4 > tmd or kind == 2 and words < 2:
            raise ValueError('First-frame record payload exceeds its bounded extent.')
        key = struct.unpack_from('<H', raw, cursor + 4)[0] if kind == 2 else None
        records.append(Record(type_id, kind, flags, key))
        cursor += words * 4
    return FirstFrame(raw[12:tmd], tuple(records), frame)


def enumerate_types(records, initial):
    """Model both native passes, preserving cursor rewinds and stale output bytes."""
    count = sum(record.kind == 8 and record.flags == 0 for record in records)
    if not 0 < count < 256 or len(initial) != count:
        raise ValueError('Positive construction requires 1..255 child declarations.')
    selector = sum(record.kind == 2 for record in records)
    result, cursor, written, selected = bytearray(initial), 0, 0, 0
    for record in records:
        if record.kind == 8 and record.flags == 0:
            written = (written + 1) & 255
            if not 0 <= cursor < count:
                raise ValueError('Native type output would exceed its owned allocation.')
            result[cursor] = record.type_id
            cursor += 1
        elif record.kind == 2 and record.key == selector:
            cursor -= written
            for index in range(written):
                if not 0 <= cursor < count:
                    raise ValueError('Native type search would leave its owned allocation.')
                current = result[cursor]
                cursor += 1
                if current == record.type_id:
                    selected = index
                    break
    return bytes(result), selected


def trunc_div(a, b):
    if not b:
        raise ValueError('A native rational fixture has a zero denominator.')
    return (abs(a) // abs(b)) * (-1 if (a < 0) != (b < 0) else 1)


def rational_values(data):
    if len(data) != 12:
        raise ValueError('Expected three signed-halfword rational pairs.')
    pairs, result = struct.unpack('<6h', data), []
    for a, b in zip(pairs[::2], pairs[1::2]):
        quotient = trunc_div(a, b)
        result.append((quotient << 12) + trunc_div((a - quotient * b) << 12, b))
    return result


def signed_half(value):
    return ((value & 65535) ^ 32768) - 32768


def filled(size, pattern, seed=0):
    if pattern not in PATTERNS:
        raise ValueError('Unsupported construction memory pattern.')
    if pattern == 'poison':
        return bytearray(b'\xB7' * size)
    return bytearray((index * 73 + (index >> 8) * 19 + seed) & 255 for index in range(size))


def initial_pool(pattern):
    buffers = dict(manager=filled(0x100, pattern, 17),
                   pool=filled(POOL_SIZE + 0x80, pattern, 53))
    struct.pack_into('<II', buffers['manager'], 0x40, POOL + 0x40, POOL_SIZE)
    return PoolModel(buffers, dict(manager=MANAGER, pool=POOL), 0x40, 0x40, POOL_SIZE)


def descriptors(symbols, pattern):
    actor = filled(0x180, pattern, 97)
    model, part_list = filled(0x100, pattern, 139), filled(0x100, pattern, 181)
    for offset, value in ((0, symbols['g_ACTOR_VTABLE']), (0x5C, MODEL)):
        struct.pack_into('<I', actor, 0x20 + offset, value)
    for buffer, vtable, offset, pointer in ((model, 0x8006F384, 0x30, PART_LIST),
                                          (part_list, 0x8006F590, 0x10, DATA)):
        struct.pack_into('<I', buffer, 0x20, vtable)
        struct.pack_into('<I', buffer, 0x20 + offset, pointer)
    return actor, model, part_list


def construct_reference(reference, frame, actor, scene_vtable, angles, scales):
    """Predict complete buffers using abstract pool intervals and constructor fields."""
    count = frame.child_count
    if not 0 < count < 256:
        raise ValueError('Positive construction requires 1..255 child declarations.')
    requests, children = [], []

    def allocate(size):
        requests.append(size)
        pointer = reference.allocate(size)
        if not pointer:
            raise ValueError('Allocation failure is outside this positive construction profile.')
        return pointer

    def put(pointer, offset, value):
        reference.put('pool', pointer - POOL + offset, value)

    pointers, types = allocate(count * 4), allocate(count)
    begin = types - POOL
    type_bytes, selected = enumerate_types(frame.records, reference.buffers['pool'][begin:begin + count])
    reference.buffers['pool'][begin:begin + count] = type_bytes
    for index in range(count):
        child, coordinate, state = allocate(88), allocate(80), allocate(40)
        children.append(child)
        put(pointers, index * 4, child)
        fields = ((0, scene_vtable), (4, 0), (8, 0), (0xC, 0), (0x10, 0),
                  (0x14, coordinate), (0x18, 0), (0x20, 0), (0x24, 0),
                  (0x44, 0), (0x4C, 0), (0x50, 0), (0x54, 0))
        for offset, value in fields:
            put(child, offset, value)
        struct.pack_into('<H', reference.buffers['pool'], child - POOL + 0x48, 300)
        put(coordinate, 0, 1)
        start = coordinate - POOL + 4
        reference.buffers['pool'][start:start + 32] = SDK_MATRIX
        put(coordinate, 0x44, state)
        put(coordinate, 0x48, 0)
        for axis, value in enumerate(scales):
            put(state, axis * 4, signed_half(value))
        for axis, value in enumerate(angles):
            struct.pack_into('<H', reference.buffers['pool'], state - POOL + 16 + axis * 2,
                             trunc_div(value, 360) & 65535)
    expected_actor = bytearray(actor)
    for offset, value in ((0x68, children[selected]), (0x6C, count), (0x70, pointers), (0x74, types)):
        struct.pack_into('<I', expected_actor, 0x20 + offset, value)
    return dict(actor=bytes(expected_actor), requests=requests, children=children,
                types=list(type_bytes), selected_index=selected)


def cleanup_reference(reference, actor):
    """Release a complete successful child graph, or repeat its cleared cleanup.

    All owned pointers are validated before any model mutation. Partial setup,
    attached descendants and shared/foreign allocations require other profiles.
    """
    reference.require_setup()
    if len(actor) != 0x180:
        raise ValueError('Cleanup requires the complete guarded actor fixture.')
    selected, count, pointers, types = struct.unpack_from('<4I', actor, 0x20 + 0x68)
    if pointers == 0 and types == 0:
        return dict(actor=bytes(actor), releases=[0, 0], owned_releases=0)
    if not pointers or not types or not 0 < count < 256:
        raise ValueError('Partial child setup is outside the successful lifetime profile.')

    def owned(pointer, capacity):
        block = reference.owned_block(pointer)
        if block.size - 4 < capacity:
            raise ValueError('A child graph allocation is too small for its native fields.')
        return pointer

    owned(pointers, count * 4)
    owned(types, count)
    releases, children = [], []
    for index in range(count):
        child = owned(reference.get('pool', pointers - POOL + index * 4), 88)
        coordinate = owned(reference.get('pool', child - POOL + 0x14), 80)
        state = owned(reference.get('pool', coordinate - POOL + 0x44), 40)
        # These constructed nodes have no children, parents, bound actor or
        # coordinate parent. Traversal/notification of populated links is open.
        if (any(reference.get('pool', child - POOL + offset) for offset in (4, 8, 0xC, 0x10, 0x18, 0x20, 0x24, 0x4C, 0x50))
                or reference.get('pool', coordinate - POOL + 0x48)):
            raise ValueError('Attached child graph ownership is outside this lifetime profile.')
        children.append(child)
        releases.extend((state, coordinate, child))
    releases.extend((types, pointers))
    if len(set(releases)) != len(releases) or selected not in children:
        raise ValueError('Child graph pointers alias or its selected child is not owned.')
    for pointer in releases:
        reference.free(pointer)
    expected = bytearray(actor)
    # The loop decrements once more at its terminal test; it retains -1.
    for offset, value in ((0x68, 0), (0x6C, 0xFFFFFFFF), (0x70, 0), (0x74, 0)):
        struct.pack_into('<I', expected, 0x20 + offset, value)
    return dict(actor=bytes(expected), releases=releases, owned_releases=len(releases))
