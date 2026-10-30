"""Synthetic raw sectors test bounds and directory traversal without game inputs."""
from pathlib import Path
import struct
import tempfile
import unittest

from tools.disc_files import FILE_LIMIT, Mode2Disc


def directory_record(name, lba, size, flags=0, unit=0, gap=0):
    length = 33 + len(name) + (len(name) % 2 == 0)
    record = bytearray(length)
    record[0] = length
    struct.pack_into('<I', record, 2, lba)
    struct.pack_into('>I', record, 6, lba)
    struct.pack_into('<I', record, 10, size)
    struct.pack_into('>I', record, 14, size)
    record[25:28] = bytes((flags, unit, gap))
    record[28:32] = b'\x01\0\0\x01'
    record[32] = len(name)
    record[33:33+len(name)] = name
    return bytes(record)


def raw_image(records=None):
    sectors = [bytearray(2048) for _ in range(32)]
    volume = sectors[16]
    volume[:7] = b'\x01CD001\x01'
    volume[128:132] = b'\0\x08\x08\0'
    volume[156:190] = directory_record(b'\0', 20, 2048, 2)
    entries = [directory_record(b'\0', 20, 2048, 2), directory_record(b'\x01', 20, 2048, 2)]
    entries += records if records is not None else [directory_record(b'FILE.BIN;1', 21, 10)]
    directory = b''.join(entries)
    sectors[20][:len(directory)] = directory
    sectors[21][:10] = b'model-data'
    result = bytearray()
    for lba, payload in enumerate(sectors):
        raw = bytearray(2352)
        raw[:12] = b'\0' + b'\xff'*10 + b'\0'
        address = lba + 150
        parts = address//4500, (address//75)%60, address%75
        raw[12:15] = bytes((value//10)*16+value%10 for value in parts)
        raw[15] = 2
        raw[16:20] = raw[20:24] = b'\0\0\x08\0'
        raw[24:2072] = payload
        result.extend(raw)
    return bytes(result)


class DiscFileTests(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory(prefix='lsd-disc-files-')
        self.addCleanup(area.cleanup)
        self.folder = Path(area.name)
        self.path = self.folder/'data track.bin'
        self.path.write_bytes(raw_image())

    def test_payload_is_read_without_extraction_or_modification(self):
        before = self.path.read_bytes()
        with Mode2Disc(self.path) as disc:
            files = disc.files()
            self.assertEqual(set(files), {'/FILE.BIN'})
            self.assertEqual(disc.read_file(files['/FILE.BIN']), b'model-data')
            self.assertEqual(disc.sectors_read, 3)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.folder.iterdir()), [self.path])

    def test_quoted_cue_reuses_its_existing_data_track(self):
        cue = self.folder/'disc.cue'
        cue.write_text('FILE "data track.bin" BINARY\n TRACK 01 MODE2/2352\n INDEX 01 00:00:00\n')
        with Mode2Disc(cue) as disc:
            self.assertEqual(disc.read_file(disc.files()['/FILE.BIN']), b'model-data')

    def test_sector_sync_address_mode_and_subheader_are_validated(self):
        original = raw_image()
        for offset in (0, 14, 15, 20):
            data = bytearray(original)
            data[21*2352+offset] ^= 1
            self.path.write_bytes(data)
            with self.subTest(offset=offset), Mode2Disc(self.path) as disc:
                record = disc.files()['/FILE.BIN']
                with self.assertRaises(ValueError):
                    disc.read_file(record)

    def test_form2_movie_sector_is_not_read_as_form1(self):
        data = bytearray(raw_image())
        data[21*2352+18] |= 0x20
        data[21*2352+22] |= 0x20
        self.path.write_bytes(data)
        with Mode2Disc(self.path) as disc:
            with self.assertRaises(ValueError):
                disc.read_file(disc.files()['/FILE.BIN'])

    def test_extent_bounds_are_checked_before_reading(self):
        with Mode2Disc(self.path) as disc:
            for lba, length in ((-1, 1), (21, 0), (21, FILE_LIMIT+1), (31, 4096)):
                with self.subTest(lba=lba, length=length), self.assertRaises(ValueError):
                    disc.read_extent(lba, length)

    def test_directory_cycle_is_rejected(self):
        self.path.write_bytes(raw_image([directory_record(b'LOOP', 20, 2048, 2)]))
        with Mode2Disc(self.path) as disc, self.assertRaises(ValueError):
            disc.files()

    def test_duplicate_file_names_are_rejected(self):
        item = directory_record(b'FILE.BIN;1', 21, 10)
        self.path.write_bytes(raw_image([item, item]))
        with Mode2Disc(self.path) as disc, self.assertRaises(ValueError):
            disc.files()

    def test_interleaved_file_can_be_listed_but_is_not_read(self):
        self.path.write_bytes(raw_image([directory_record(b'MOVIE.STR;1', 21, 10, unit=2, gap=1)]))
        with Mode2Disc(self.path) as disc:
            record = disc.files()['/MOVIE.STR']
            with self.assertRaises(ValueError):
                disc.read_file(record)

    def test_multiextent_file_is_rejected(self):
        self.path.write_bytes(raw_image([directory_record(b'FILE.BIN;1', 21, 10, 128)]))
        with Mode2Disc(self.path) as disc, self.assertRaises(ValueError):
            disc.files()

    def test_both_endian_directory_numbers_must_agree(self):
        data = bytearray(raw_image())
        data[16*2352+24+156+6] ^= 1
        self.path.write_bytes(data)
        with Mode2Disc(self.path) as disc, self.assertRaises(ValueError):
            disc.files()

    def test_directory_record_cannot_cross_a_sector(self):
        data = bytearray(raw_image())
        at = 20*2352+24
        dot = directory_record(b'\0', 20, 2048, 2)
        payload = bytearray(2048)
        for cursor in range(0, 2000, 250):
            payload[cursor:cursor+34] = dot
            payload[cursor] = 250
        payload[2000:2034] = dot
        payload[2000] = 40
        payload[2040] = 34  # Eight bytes remain in this sector.
        data[at:at+2048] = payload
        self.path.write_bytes(data)
        with Mode2Disc(self.path) as disc, self.assertRaises(ValueError):
            disc.files()


if __name__ == '__main__':
    unittest.main()
