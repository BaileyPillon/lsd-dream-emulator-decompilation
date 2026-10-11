"""Native asset bounds and preservation checks without game data."""

import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import inventory_disc


def texture_fixture():
    return struct.pack("<III4H", 0x10, 2, 16, 320, 0, 2, 1) + b"\x01\x02\x03\x04"


class DiscInventoryTests(unittest.TestCase):
    def inspect_fixture(self, directory, edition_label=None):
        root = Path(directory)
        executable = b"synthetic executable for inventory provenance"
        (root / "SLPS_015.56").write_bytes(executable)
        (root / "disc.xml").write_text(
            '<iso_project><track><directory_tree>'
            '<file name="SLPS_015.56" source="SLPS_015.56" type="data" offs="24"/>'
            '</directory_tree></track></iso_project>', encoding="utf-8")
        with patch.object(inventory_disc, "ORIGINAL_SHA1", hashlib.sha1(executable).hexdigest()):
            if edition_label is None:
                return inventory_disc.inspect_layout(root / "disc.xml")
            return inventory_disc.inspect_layout(root / "disc.xml", edition_label)

    def test_default_edition_does_not_infer_a_translation_from_the_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            report = self.inspect_fixture(directory)
            self.assertEqual(report["edition_label"], "unspecified")
            self.assertNotIn("English", report["scope"])
            self.assertTrue(report["files"][0]["format_analysis"]["canonical_match"])

    def test_edition_provenance_does_not_change_content_or_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            first = self.inspect_fixture(directory, "English v1")
            second = self.inspect_fixture(directory, "Japanese source")
            self.assertEqual(first["files"], second["files"])
            self.assertEqual(first["extensions"], second["extensions"])
            self.assertEqual(second["edition_label"], "Japanese source")
            self.assertEqual(Path(directory, "SLPS_015.56").read_bytes(),
                             b"synthetic executable for inventory provenance")

    def test_tim_structure_preserves_word_units_and_padding(self):
        result = inventory_disc.tim_info(texture_fixture() + b"padding")
        self.assertEqual(result["image"]["width_words"], 2)
        self.assertEqual(result["image"]["payload_bytes"], 4)
        self.assertEqual(result["remaining_bytes"], 7)

    def test_truncated_tim_payload_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "extent"):
            inventory_disc.tim_info(texture_fixture()[:-1])

    def test_native_image_extent_is_checked_when_declared_length_is_short(self):
        data = bytearray(texture_fixture())
        struct.pack_into("<I", data, 8, 12)
        result = inventory_disc.tim_info(data)
        self.assertEqual(result["image"]["declared_extent_shortfall_bytes"], 4)
        with self.assertRaisesRegex(ValueError, "extent"):
            inventory_disc.tim_info(data[:-1])

    def test_tix_counts_records_and_shared_offsets_separately(self):
        data = struct.pack("<3I", 2, 12, 12) + texture_fixture()
        result = inventory_disc.tim_list_info(data)
        self.assertEqual(result["tim_records"], 2)
        self.assertEqual(result["distinct_tim_offsets"], 1)

    def test_tix_offset_cannot_point_into_header_or_outside_file(self):
        for offset in (0, 999):
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, "outside"):
                inventory_disc.tim_list_info(struct.pack("<2I", 1, offset) + texture_fixture())

    def test_stage_tix_contains_nested_lists_with_declared_extents(self):
        bank = struct.pack("<2I", 1, 8) + texture_fixture()
        offsets = [36 + index * len(bank) for index in range(4)]
        data = struct.pack("<9I", 4, *offsets, *([len(bank)] * 4)) + bank * 4
        result = inventory_disc.tix_info(data)
        self.assertEqual(result["tim_records"], 4)
        self.assertEqual(result["bank_count"], 4)
        with self.assertRaisesRegex(ValueError, "extent"):
            inventory_disc.tix_info(data[:-1])

    def test_layout_cannot_reference_a_file_outside_its_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            extraction = root / "extraction"
            extraction.mkdir()
            outside = root / "outside.bin"
            outside.write_bytes(b"retained")
            with self.assertRaisesRegex(ValueError, "inside"):
                inventory_disc.bounded_source(extraction / "disc.xml", "../outside.bin")
            self.assertEqual(outside.read_bytes(), b"retained")


if __name__ == "__main__":
    unittest.main()
