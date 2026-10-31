"""Independent byte-level expectations for the original new-game routines.

This model describes a bounded initialized context. Normal non-flashback day
completion also updates scores/chart history and is deliberately not modelled
as a reset or silently replaced with a no-op.
"""
import struct

OBJECT_BYTES = 0x928
SAVE_OFFSET, SAVE_BYTES = 0x178, 0x700
IS_FLASHBACK, IS_NEW_GAME, STORED_DAY, FLAG = 0x68, 0x878, 0x88C, 0x924
NAV_FLAGS, NAV_COUNT, DYNAMIC_LINK_COUNT = 0x5E0, 30, 0x600
ZERO_WORDS = (0x17C, 0x180, 0x184, 0x188, 0x18C, 0x46C, 0x67C, 0x680)
ZERO_BYTES = (0x5D8, 0x5DF)
RESERVED_OFFSET, RESERVED_BYTES = 0x684, 0x1F4


def require(condition, message):
    if not condition:
        raise ValueError(message)


def word(data, offset):
    return struct.unpack_from('<I', data, offset)[0]


def put(data, offset, value):
    require(type(value) is int and 0 <= value <= 0xFFFFFFFF, 'Use a native unsigned word bit pattern.')
    struct.pack_into('<I', data, offset, value)


def context(data):
    require(isinstance(data, (bytes, bytearray)) and len(data) == OBJECT_BYTES,
            'Use one complete 0x928-byte dream system, without truncation or masks.')
    return bytearray(data)


def reset_write_offsets():
    offsets = set(range(SAVE_OFFSET, SAVE_OFFSET+4))
    for offset in (*ZERO_WORDS, DYNAMIC_LINK_COUNT, 0x678):
        offsets.update(range(offset, offset+4))
    offsets.update(ZERO_BYTES)
    offsets.update(range(NAV_FLAGS, NAV_FLAGS+NAV_COUNT))
    offsets.update(range(RESERVED_OFFSET, RESERVED_OFFSET+RESERVED_BYTES))
    return offsets


def reset(data, marker):
    result = context(data)
    put(result, SAVE_OFFSET, marker)
    for offset in (*ZERO_WORDS, DYNAMIC_LINK_COUNT):
        put(result, offset, 0)
    for offset in ZERO_BYTES:
        result[offset] = 0
    result[NAV_FLAGS:NAV_FLAGS+NAV_COUNT] = bytes(NAV_COUNT)
    put(result, 0x678, 1)
    result[RESERVED_OFFSET:RESERVED_OFFSET+RESERVED_BYTES] = bytes(RESERVED_BYTES)
    return bytes(result)


def end_day(data, mode, marker):
    result = context(data)
    require(type(mode) is int and 0 <= mode <= 0xFFFFFFFF, 'Use a native end-mode bit pattern.')
    flashback = word(result, IS_FLASHBACK)
    require(mode != 0 or flashback != 0,
            'Normal non-flashback completion needs the separate score/chart model; it is not a reset.')
    put(result, 0x180, word(result, STORED_DAY))
    if mode == 2:
        result = bytearray(reset(result, marker))
        put(result, IS_NEW_GAME, 1)
    return bytes(result), flashback


def clear_new_game(data):
    result = context(data)
    put(result, IS_NEW_GAME, 0)
    return bytes(result)


def get_set_flag(data, value):
    result = context(data)
    require(type(value) is int and 0 <= value <= 0xFFFFFFFF, 'Use a native flag bit pattern.')
    old = word(result, FLAG)
    if value < 0x80000000:
        put(result, FLAG, value)
    return bytes(result), old


def nav_reset(data, flags_offset, count_offset):
    require(isinstance(data, (bytes, bytearray)), 'Use a complete guarded byte buffer.')
    require(type(flags_offset) is int and type(count_offset) is int
            and 0 <= flags_offset <= len(data)-NAV_COUNT and 0 <= count_offset <= len(data)-4
            and count_offset % 4 == 0, 'Navigation inputs must be bounded and the word aligned.')
    require(flags_offset+NAV_COUNT <= count_offset or count_offset+4 <= flags_offset,
            'This initialized profile uses disjoint flags and count storage.')
    result = bytearray(data)
    result[flags_offset:flags_offset+NAV_COUNT] = bytes(NAV_COUNT)
    put(result, count_offset, 0)
    return bytes(result)
