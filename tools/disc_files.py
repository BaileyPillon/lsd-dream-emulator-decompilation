"""Read bounded Mode 2/Form 1 files directly from a raw PS1 data track.

Directory metadata can list mixed-sector movies; read_file deliberately accepts
only non-interleaved Form 1 payloads. This reader does not check EDC/ECC or
authenticate an edition. Callers qualify the complete input hash separately.
"""
from dataclasses import dataclass
from pathlib import PurePosixPath
import struct

from tools.psx_image import data_image

FILE_LIMIT = 8 * 1024**2


def require(value, message):
    if not value:
        raise ValueError(message)


def both_endian(record, offset):
    require(offset >= 0 and offset + 8 <= len(record), 'Truncated ISO integer.')
    little = struct.unpack_from('<I', record, offset)[0]
    require(little == struct.unpack_from('>I', record, offset + 4)[0],
            'ISO little/big-endian integers disagree.')
    return little


@dataclass(frozen=True)
class DiscFile:
    path: str
    lba: int
    size: int
    flags: int
    file_unit: int
    interleave_gap: int


class Mode2Disc:
    def __init__(self, path):
        self.path = data_image(path)
        self.size = self.path.stat().st_size
        require(0 < self.size <= 1024**3 and self.size % 2352 == 0,
                'Use a bounded raw 2352-byte-sector data track.')
        self.stream = self.path.open('rb')
        self.sectors_read = 0

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.stream.close()

    def read_extent(self, lba, length):
        require(type(lba) is int and type(length) is int and lba >= 0
                and 0 < length <= FILE_LIMIT, 'Invalid or oversized data extent.')
        sectors = (length + 2047) // 2048
        require((lba + sectors) * 2352 <= self.size, 'Data extent exceeds the raw disc.')
        result = bytearray()
        for number in range(lba, lba + sectors):
            self.stream.seek(number * 2352)
            raw = self.stream.read(2352)
            absolute = number + 150
            parts = absolute // 4500, (absolute // 75) % 60, absolute % 75
            msf = bytes((part // 10) * 16 + part % 10 for part in parts)
            require(len(raw) == 2352 and raw[:12] == b'\0' + b'\xff' * 10 + b'\0'
                    and raw[12:15] == msf and raw[15] == 2
                    and raw[16:20] == raw[20:24] and not raw[18] & 0x20,
                    'Invalid sync/MSF or unsupported Mode 2/Form 1 sector.')
            result.extend(raw[24:2072])
            self.sectors_read += 1
        return bytes(result[:length])

    def files(self):
        volume = self.read_extent(16, 2048)
        require(volume[:7] == b'\x01CD001\x01' and volume[128:132] == b'\x00\x08\x08\x00',
                'Unsupported primary volume descriptor or ISO block size.')
        root = volume[156:190]
        pending = [(PurePosixPath('/'), both_endian(root, 2), both_endian(root, 10))]
        visited, files, entries = set(), {}, 0
        while pending:
            parent, lba, length = pending.pop()
            require(len(parent.parts) <= 32 and 0 < length <= 1024**2
                    and len(visited) < 128 and (lba, length) not in visited,
                    'Repeated or unbounded ISO directory.')
            visited.add((lba, length))
            data, cursor = self.read_extent(lba, length), 0
            while cursor < len(data):
                size = data[cursor]
                if size == 0:
                    cursor = (cursor // 2048 + 1) * 2048
                    continue
                record = data[cursor:cursor + size]
                require(size >= 34 and len(record) == size and record[1] == 0
                        and not record[25] & 128 and cursor % 2048 + size <= 2048
                        and 0 < record[32] <= size - 33,
                        'Unsupported or truncated ISO directory record.')
                cursor += size
                name = record[33:33 + record[32]]
                if name in (b'\0', b'\x01'):
                    continue
                entries += 1
                require(entries <= 4096, 'Too many ISO directory entries.')
                name = name.decode('ascii').split(';', 1)[0]
                require(name not in ('', '.', '..') and '/' not in name and '\\' not in name,
                        'Invalid ISO path component.')
                path = parent / name
                child_lba, child_size = both_endian(record, 2), both_endian(record, 10)
                if record[25] & 2:
                    require(record[26] == record[27] == 0, 'Interleaved directories are unsupported.')
                    pending.append((path, child_lba, child_size))
                else:
                    key = str(path).upper()
                    require(key not in files and len(files) < 4096, 'Duplicate or unbounded ISO files.')
                    files[key] = DiscFile(key, child_lba, child_size, record[25], record[26], record[27])
        return files

    def read_file(self, record):
        require(isinstance(record, DiscFile) and not record.flags & (2 | 128)
                and record.file_unit == record.interleave_gap == 0,
                'Expected one non-interleaved regular Form 1 file.')
        return self.read_extent(record.lba, record.size)
