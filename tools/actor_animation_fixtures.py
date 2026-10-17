"""Owned MOM fixtures for the original interpreter's parent-word semantics.

No original media is embedded. Child IDs zero and 255 distinguish full-word
root sentinels from the low-byte lookup used for every other parent word.
"""
import struct

PARENT_WORDS = (0, 0xffff, 0x10000, 0x12340000, 0x1ffff, 0x1234ffff)
CHILD_TYPES = (0, 9, 255)


def parent_word_fixture(parent_word):
    if type(parent_word) is not int or not 0 <= parent_word <= 0xffffffff:
        raise ValueError('A parent word must be an unsigned 32-bit integer.')
    command = lambda target, kind, words: struct.pack('<I', target | kind << 16 | words << 24)
    first = b''.join(command(target, 8, 1) + command(target, 2, 2) + struct.pack('<I', 1)
                     for target in CHILD_TYPES)
    second = command(9, 3, 2) + struct.pack('<I', parent_word)
    offsets = (28, 28 + 16 + len(first))
    tmd = offsets[1] + 16 + len(second)
    raw = bytearray(tmd + 40)
    raw[:4], raw[12:16] = b'MOM ', b'MOS '
    struct.pack_into('<II', raw, 4, len(raw), tmd)
    struct.pack_into('<III', raw, 16, 2, offsets[0] - 12, offsets[1] - 12)
    for offset, count, payload in zip(offsets, (6, 1), (first, second)):
        struct.pack_into('<I', raw, offset + 4, 1)
        struct.pack_into('<H', raw, offset + 10, count)
        raw[offset + 16:offset + 16 + len(payload)] = payload
    struct.pack_into('<III', raw, tmd, 0x41, 0, 1)
    return bytes(raw)
