"""Predict raw MOM mapping independently of native objects or heap traces.

This profile starts with a fresh relative TMD and valid MOS offsets. Allocation
addresses come from the independent ownership plan, never from native memory.
Untouched model bytes, including geometry and animation commands, are retained.
"""
import struct


def geometry_bindings(types, commands, object_count):
    """First nonzero kind-2 selection per child, from the original first frame."""
    bound, indices = set(), []
    for type_id, kind, payload in commands:
        if kind != 2 or type_id not in types or type_id in bound:
            continue
        if len(payload) < 2:
            raise ValueError('A geometry selection has no complete halfword.')
        selection = struct.unpack_from('<H', payload)[0]
        if selection:
            if selection > object_count:
                raise ValueError('A geometry selection exceeds the original object table.')
            bound.add(type_id)
            indices.append(selection - 1)
    return tuple(indices)


def link_primitive_runs(mapped, raw, table, index):
    """Model GsLinkObject4's mode runs, separately from the collision decoder."""
    offset = table + index * 28
    cursor = table + struct.unpack_from('<I', raw, offset + 16)[0]
    count = struct.unpack_from('<I', raw, offset + 20)[0]
    if cursor + 2 > len(raw) or count > (len(raw) - cursor) // 4:
        raise ValueError('The primitive packet extent exceeds the raw model copy.')
    group, previous, run = cursor, 0, 0
    # Sizes follow the SDK linker's own switch, not its input ilen/olen bytes.
    sizes = {0x21: 16, 0x24: 24, 0x25: 28, 0x28: 20, 0x29: 16,
             0x2C: 32, 0x2D: 32, 0x31: 24, 0x34: 28, 0x35: 36,
             0x38: 24, 0x39: 28, 0x3C: 36, 0x3D: 44}
    for _ in range(count):
        if cursor + 4 > len(raw):
            raise ValueError('A primitive packet header exceeds the raw copy.')
        mode, flags = mapped[cursor + 3], mapped[cursor + 2]
        if previous and mode != previous:
            struct.pack_into('<H', mapped, group, run & 0xFFFF)
            group, run = cursor, 0
        base = mode & 0xFD
        if base == 0x20:
            length = 24 if flags & 4 else 16
        elif base == 0x30:
            length = 28 if flags & 4 else 20
        elif base in sizes:
            length = sizes[base]
        else:
            raise ValueError('Unsupported primitive SDK error paths are outside this profile.')
        if cursor + length > len(raw):
            raise ValueError('A complete primitive packet exceeds the raw copy.')
        cursor, previous, run = cursor + length, mode, run + 1
    struct.pack_into('<H', mapped, group, run & 0xFFFF)


def mapped_model_bytes(raw, address, animation_pointers, geometry_indices=(), destroyed=False):
    raw = bytes(raw)
    pointers = tuple(animation_pointers)
    if (len(raw) < 24 or raw[:4] != b'MOM ' or raw[12:16] != b'MOS '
            or type(address) is not int or address < 0 or address % 4
            or address + len(raw) > 0x100000000):
        raise ValueError('Use a bounded aligned MOM copy with its original signatures.')
    size, tmd = struct.unpack_from('<II', raw, 4)
    animations = struct.unpack_from('<I', raw, 16)[0]
    if size != len(raw) or tmd % 4 or not 20 + animations * 4 <= tmd <= size - 12:
        raise ValueError('MOM geometry or animation table exceeds its declared extent.')
    identifier, flags, objects = struct.unpack_from('<III', raw, tmd)
    if identifier != 0x41 or flags & 1 or tmd + 12 + objects * 28 > size:
        raise ValueError('Use a complete relative TMD object table, before mapping.')
    if len(pointers) != animations or any(type(p) is not int or not 0 < p <= 0xFFFFFFFC or p % 4 for p in pointers):
        raise ValueError('Supply one planned aligned allocation pointer per animation.')
    for index in range(animations):
        offset = 12 + struct.unpack_from('<I', raw, 20 + 4 * index)[0]
        if offset % 4 or not 20 + animations * 4 <= offset <= tmd - 8:
            raise ValueError('An original animation offset exceeds the MOS extent.')
    mapped = bytearray(raw)
    struct.pack_into('<I', mapped, tmd + 4, flags | 1)
    table = tmd + 12
    for index in range(objects):
        for field in (0, 8, 16):
            offset = table + index * 28 + field
            relative = struct.unpack_from('<I', raw, offset)[0]
            if table + relative >= size or relative % 4:
                raise ValueError('A relative geometry pointer exceeds the bounded MOM copy.')
            struct.pack_into('<I', mapped, offset, address + table + relative)
    for index, pointer in enumerate(pointers):
        struct.pack_into('<I', mapped, 20 + index * 4, 0 if destroyed else pointer)
    for index in geometry_indices:
        if type(index) is not int or not 0 <= index < objects:
            raise ValueError('A linked geometry index exceeds the original object table.')
        link_primitive_runs(mapped, raw, table, index)
    return bytes(mapped)
