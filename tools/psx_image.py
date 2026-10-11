"""Read a root ISO9660 file from a 2048-byte ISO or 2352-byte PS1 BIN."""

from pathlib import Path
import re
import struct

ORIGINAL_SHA1 = "76322eeade5ebb22dca57fdeac7d68c30f06308d"
EXECUTABLE_NAME = "SLPS_015.56"


def data_image(path):
    """Resolve the first BINARY file in a CUE; leave disc files untouched."""
    path = Path(path).resolve()
    if path.suffix.lower() != ".cue":
        return path
    text = path.read_text(encoding="utf-8-sig")
    match = re.search(r'^\s*FILE\s+"([^"]+)"\s+BINARY\s*$', text, re.I | re.M)
    if not match:
        raise ValueError("CUE has no quoted BINARY data image.")
    return (path.parent / match.group(1)).resolve()


def read_root_file(image, name=EXECUTABLE_NAME):
    """Return (bytes, LBA) for a contiguous, non-interleaved root file."""
    image = data_image(image)
    with image.open("rb") as stream:
        layout = None
        for sector_size, offset in ((2048, 0), (2352, 24), (2352, 16)):
            stream.seek(16 * sector_size + offset)
            if stream.read(7) == b"\x01CD001\x01":
                layout = sector_size, offset
                break
        if layout is None:
            raise ValueError("No ISO9660 volume at sector 16 (ISO / MODE1 / MODE2 Form1).")
        sector_size, offset = layout

        def read_extent(lba, size):
            if size < 0 or size > 64 * 1024 * 1024:
                raise ValueError("Unexpected ISO file size.")
            chunks = []
            for sector in range((size + 2047) // 2048):
                stream.seek((lba + sector) * sector_size + offset)
                payload = stream.read(2048)
                if len(payload) != 2048:
                    raise ValueError("Truncated ISO file extent.")
                chunks.append(payload)
            return b"".join(chunks)[:size]

        volume = read_extent(16, 2048)
        root = volume[156:190]
        directory = read_extent(struct.unpack_from("<I", root, 2)[0],
                                struct.unpack_from("<I", root, 10)[0])
        cursor = 0
        while cursor < len(directory):
            length = directory[cursor]
            if not length:
                cursor = (cursor // 2048 + 1) * 2048
                continue
            record = directory[cursor:cursor + length]
            if length < 34 or len(record) != length:
                raise ValueError("Invalid ISO directory record.")
            file_name = record[33:33 + record[32]].decode("ascii")
            if file_name.split(";", 1)[0].upper() == name.upper():
                if record[25] & (2 | 128) or record[26] or record[27]:
                    raise ValueError("Expected a single, non-interleaved regular file.")
                lba = struct.unpack_from("<I", record, 2)[0]
                size = struct.unpack_from("<I", record, 10)[0]
                return read_extent(lba, size), lba
            cursor += length
    raise ValueError(f"{name} was not found in the disc root.")


def executable_offset(executable, address, size):
    if len(executable) < 0x800 or executable[:8] != b"PS-X EXE":
        raise ValueError("Expected a PS-X EXE executable.")
    load_address, payload_size = struct.unpack_from("<II", executable, 0x18)
    offset = 0x800 + address - load_address
    if offset < 0x800 or offset + size > min(len(executable), 0x800 + payload_size):
        raise ValueError(f"Address 0x{address:08X} is outside the executable payload.")
    return offset
