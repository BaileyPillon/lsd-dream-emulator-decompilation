"""Independent bounded predictions for the two original TMD SDK operations.

These functions predict pointer relocation and run headers, not rendered output.
The linker has its own packet-size switch; the collision reader's general
gradation layouts are deliberately not used here.
"""
from dataclasses import dataclass
import struct

from tools.disc_files import require


def _header(data, address):
    require(type(address) is int and address >= 0 and address % 4 == 0
            and address + len(data) <= 0x100000000 and len(data) >= 12,
            'Use a bounded aligned TMD address and complete header.')
    identifier, flags, count = struct.unpack_from('<III', data)
    require(identifier == 0x41, 'Expected the TMD identifier.')
    return flags, count


def map_tmd(data, address):
    """Predict GsMapModelingData(address + 4), including its early returns."""
    data = bytes(data)
    flags, count = _header(data, address)
    if flags & 1:
        return data
    mapped = bytearray(data)
    struct.pack_into('<I', mapped, 4, flags | 1)
    # The original loop tests the object count as a signed 32-bit integer.
    if count & 0x80000000:
        return bytes(mapped)
    require(count <= (len(data) - 12) // 28, 'TMD object table exceeds its container.')
    for index in range(count):
        for field in (0, 8, 16):
            at = 12 + index * 28 + field
            relative = struct.unpack_from('<I', data, at)[0]
            require(relative % 4 == 0 and relative <= len(data) - 12,
                    'Relative pointer exceeds the bounded TMD container.')
            struct.pack_into('<I', mapped, at, address + 12 + relative)
    return bytes(mapped)


def sdk_packet_bytes(mode, flags):
    require(type(mode) is int and 0 <= mode <= 255
            and type(flags) is int and 0 <= flags <= 255,
            'Invalid SDK packet mode or flags.')
    base = mode & 0xFD
    if base == 0x20:
        return 24 if flags & 4 else 16
    if base == 0x30:
        return 28 if flags & 4 else 20
    sizes = {0x21: 16, 0x24: 24, 0x25: 28, 0x28: 20, 0x29: 16,
             0x2C: 32, 0x2D: 32, 0x31: 24, 0x34: 28, 0x35: 36,
             0x38: 24, 0x39: 28, 0x3C: 36, 0x3D: 44}
    require(base in sizes, 'SDK printf/error paths are outside this profile.')
    return sizes[base]


@dataclass(frozen=True)
class LinkPlan:
    model: bytes
    target: bytes
    descriptor_offset: int
    run_headers: tuple
    primitive_extents: tuple


def link_tmd(data, address, index, target):
    """Predict GsLinkObject4(address + 12, target_address, index).

    Preserve the complete supplied target except its descriptor pointer at +8.
    A zero-primitive object still receives a zero halfword at its primitive base.
    """
    data, target = bytes(data), bytearray(target)
    flags, count = _header(data, address)
    require(flags & 1 and type(index) is int and 0 <= index < count
            and count <= (len(data) - 12) // 28 and len(target) >= 12,
            'Use a mapped bounded object table, valid index and complete target.')
    descriptor = 12 + index * 28
    pointer, primitives = struct.unpack_from('<II', data, descriptor + 16)
    cursor = pointer - address
    require(0 <= cursor <= len(data) - 2 and primitives <= (len(data) - cursor) // 4,
            'Primitive pointer/count exceeds the mapped TMD container.')
    struct.pack_into('<I', target, 8, address + descriptor)
    mapped, headers, extents = bytearray(data), [], []
    group, previous, run = cursor, None, 0
    for _ in range(primitives):
        require(cursor + 4 <= len(data), 'Truncated SDK primitive header.')
        mode, packet_flags = data[cursor + 3], data[cursor + 2]
        if previous is not None and mode != previous:
            headers.append((group, run & 0xFFFF))
            group, run = cursor, 0
        size = sdk_packet_bytes(mode, packet_flags)
        require(size <= len(data) - cursor, 'Truncated complete SDK primitive.')
        extents.append((cursor, size))
        cursor, previous, run = cursor + size, mode, run + 1
    headers.append((group, run & 0xFFFF))
    for at, number in headers:
        struct.pack_into('<H', mapped, at, number)
    return LinkPlan(bytes(mapped), bytes(target), descriptor, tuple(headers), tuple(extents))
