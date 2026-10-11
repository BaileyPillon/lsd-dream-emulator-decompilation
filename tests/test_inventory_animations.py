"""Native LBD/MML/MOM/MOS bounds, references and identity without game data."""

from contextlib import redirect_stderr
import hashlib
import io
from pathlib import Path
import struct
import tempfile
import unittest

from tools import inventory_animations


def command(type_id, kind, flags=0, payload=()):
    return struct.pack("<I", type_id | kind << 16 | flags << 20 | (len(payload) + 1) << 24) + \
        struct.pack(f"<{len(payload)}I", *payload)


def fixture(animations=None, objects=1):
    if animations is None:
        records = [command(6, 8), command(6, 0, payload=(0xFFFFFFFF, 1)),
                   command(6, 2, payload=(1,)), command(6, 3, payload=(0xFFFF,)),
                   command(6, 1, 14, (0, 360, 720, 0x10001000, 0x1000, 1, 2, 3)),
                   command(0, 15)]
        animations = [[records]]
    blobs = [struct.pack("<HHI", 0x50, 4, len(frames)) + b"".join(
        struct.pack("<HHI", 0x20, len(records), 0) + b"".join(records) for records in frames)
        for frames in animations]
    cursor = 8 + 4 * len(blobs)
    offsets = []
    for blob in blobs:
        offsets.append(cursor)
        cursor += len(blob)
    mos = b"MOS " + struct.pack("<I", len(blobs)) + struct.pack(f"<{len(blobs)}I", *offsets) + b"".join(blobs)
    tmd = struct.pack("<III", 0x41, 0, objects) + bytes(objects * 28)
    return bytearray(b"MOM " + struct.pack("<II", 12 + len(mos) + len(tmd), 12 + len(mos)) + mos + tmd)


def lbd_fixture(extra=0, objects=1, library_models=None, aliases=None):
    grid = struct.pack("<IHH", 0x4C, 20, 20) + bytes((400 + extra) * 12)
    tmd = struct.pack("<III", 0x41, 0, objects) + bytes(objects * 28)
    data = bytearray(struct.pack("<6I", 1, 24, len(grid), len(tmd), 0xFFFFFFFF, 0) + grid + tmd)
    if library_models is not None:
        aliases = list(range(len(library_models))) if aliases is None else aliases
        cursor = 8 + len(aliases) * 4
        offsets = []
        for model in library_models:
            offsets.append(cursor)
            cursor += len(model)
        library = b"MML " + struct.pack("<I", len(aliases)) + \
            struct.pack(f"<{len(aliases)}I", *(offsets[index] for index in aliases)) + b"".join(library_models)
        struct.pack_into("<H", data, 2, 1)
        struct.pack_into("<II", data, 16, len(data), len(library))
        data.extend(library)
    return data


def tile(data, index, tag=1, model=0, continuation=0):
    struct.pack_into("<BBHBBhI", data, 24 + 8 + index * 12, tag, 0, model, 0, 3, -1, continuation)


class AnimationInventoryTests(unittest.TestCase):
    def test_native_commands_have_bounded_payloads_and_absolute_transform_fields(self):
        result = inventory_animations.mom_info(fixture(), 0)
        self.assertEqual(result["frame_count"], 1)
        self.assertEqual(result["record_count"], 6)
        self.assertEqual(result["animations"][0]["trailing_bytes"], 0)
        self.assertEqual(result["animations"][0]["child_types"], [6])
        self.assertEqual(result["record_shapes"]["1:14:9"], 1)
        self.assertEqual(result["transform_fields"], {"absolute": 1, "angles": 1, "scale": 1, "position": 1})
        self.assertFalse(result["missing_command_child_types"])
        self.assertFalse(result["out_of_range_primitive_selections"])

    def test_relative_angles_scale_and_position_word_counts_follow_native_reads(self):
        cases = ((3, (360, 0, 0)), (5, (0x10001000, 0x1000)),
                 (9, (1, 2, 3)), (7, (360, 0, 0, 0x10001000, 0x1000)),
                 (13, (0x10001000, 0x1000, 1, 2, 3)),
                 (11, (360, 0, 0, 1, 2, 3)))
        records = [command(6, 8)] + [command(6, 1, flags, payload) for flags, payload in cases]
        result = inventory_animations.mom_info(fixture([[records]]), 0)
        self.assertEqual(result["transform_fields"]["relative"], 6)
        self.assertEqual(result["record_shapes"]["1:7:6"], 1)
        self.assertEqual(result["record_shapes"]["1:11:7"], 1)

    def test_declared_MOM_size_and_TMD_descriptor_extent_are_checked(self):
        for offset, value in ((4, 0xFFFFFF), (8, 0xFFFFFF), (8, 4)):
            data = fixture()
            struct.pack_into("<I", data, offset, value)
            with self.subTest(offset=offset, value=value), self.assertRaises(ValueError):
                inventory_animations.mom_info(data, 0)
        data = fixture()
        struct.pack_into("<I", data, struct.unpack_from("<I", data, 8)[0] + 8, 1000)
        with self.assertRaisesRegex(ValueError, "descriptors"):
            inventory_animations.mom_info(data, 0)

    def test_signature_alignment_and_negative_offsets_are_rejected(self):
        for data, offset in ((b"x" + fixture(), 1), (fixture(), -4), (b"".join((b"NOPE", fixture()[4:])), 0)):
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                inventory_animations.mom_info(data, offset)

    def test_MOS_offset_table_cannot_point_into_header_or_TMD(self):
        for value in (0, 4, 13, 0xFFFFFF):
            data = fixture()
            struct.pack_into("<I", data, 20, value)
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "outside"):
                inventory_animations.mom_info(data, 0)
        data = fixture()
        struct.pack_into("<I", data, 16, 0xFFFFFF)
        with self.assertRaisesRegex(ValueError, "overlaps"):
            inventory_animations.mom_info(data, 0)

    def test_frame_and_record_counts_are_physically_bounded(self):
        data = fixture()
        struct.pack_into("<I", data, 28, 0xFFFFFF)
        with self.assertRaisesRegex(ValueError, "frame count"):
            inventory_animations.mom_info(data, 0)
        data = fixture()
        struct.pack_into("<H", data, 34, 1000)
        with self.assertRaisesRegex(ValueError, "truncated"):
            inventory_animations.mom_info(data, 0)

    def test_zero_word_record_and_native_payload_shortfall_are_rejected(self):
        data = fixture()
        data[43] = 0
        with self.assertRaisesRegex(ValueError, "zero"):
            inventory_animations.mom_info(data, 0)
        for record in (command(6, 0), command(6, 2), command(6, 3), command(6, 1, 14)):
            with self.subTest(record=record.hex()), self.assertRaisesRegex(ValueError, "shorter"):
                inventory_animations.mom_info(fixture([[[command(6, 8), record]]]), 0)

    def test_record_cannot_consume_the_next_animation_even_if_inside_MOM(self):
        data = fixture([[[command(6, 8)]], [[command(6, 8)]]])
        data[47] = 10
        with self.assertRaisesRegex(ValueError, "animation extent"):
            inventory_animations.mom_info(data, 0)

    def test_child_references_use_the_first_animation_declarations(self):
        result = inventory_animations.mom_info(fixture([
            [[command(6, 8)]], [[command(7, 8), command(7, 1, 9, (1, 2, 3))]]]), 0)
        self.assertEqual(len(result["missing_command_child_types"]), 1)
        self.assertFalse(result["animations"][1]["child_types_equal_first_animation"])

    def test_invalid_parent_and_selection_are_reported_without_inventing_behavior(self):
        result = inventory_animations.mom_info(fixture([[[command(6, 8),
            command(6, 2, payload=(2,)), command(6, 3, payload=(7,))]]]), 0)
        self.assertEqual(result["out_of_range_primitive_selections"][0]["one_based_selection"], 2)
        self.assertEqual(result["missing_parent_types"][0]["parent_type"], 7)

    def test_zero_primitive_selection_and_native_parent_sentinels_are_allowed(self):
        result = inventory_animations.mom_info(fixture([[[command(6, 8),
            command(6, 2, payload=(0,)), command(6, 3, payload=(0,)),
            command(6, 3, payload=(0xFFFF,))]]]), 0)
        self.assertFalse(result["out_of_range_primitive_selections"])
        self.assertFalse(result["missing_parent_types"])

    def test_unknown_record_kind_remains_structural_and_empty_frame_is_bounded(self):
        result = inventory_animations.mom_info(fixture([[[command(6, 7)], []]]), 0)
        self.assertEqual(result["kind_counts"], {"7": 1})
        self.assertEqual(result["frame_count"], 2)
        self.assertFalse(result["transform_fields"])

    def test_duplicate_instances_and_content_hashes_are_counted_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "M000.LBD"
            original = b"LBD " + fixture() + fixture()
            path.write_bytes(original)
            records = [{"path": "/CDI/STG00/M000.LBD", "source": str(path),
                        "sha256": hashlib.sha256(original).hexdigest()}]
            result = inventory_animations.audit_files(records)
            self.assertEqual(result["totals"]["validated_MOM_instances"], 2)
            self.assertEqual(result["unique_content_totals"]["models"], 1)
            self.assertEqual(result["totals"]["records"], 12)
            self.assertEqual(result["unique_content_totals"]["records"], 6)
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(result["gameplay_tested"])
            records[0]["sha256"] = "changed"
            with self.assertRaisesRegex(ValueError, "Input changed"):
                inventory_animations.audit_files(records)

    def test_missing_direct_MOM_signature_is_explicitly_unresolved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "UNKNOWN.MOM"
            data = b"unidentified"
            path.write_bytes(data)
            result = inventory_animations.audit_files([{"path": "/UNKNOWN.MOM", "source": str(path),
                "sha256": hashlib.sha256(data).hexdigest()}])
            self.assertEqual(result["files"][0]["validation"], "unresolved")

    def test_existing_output_is_preserved_before_layout_is_read(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "kept.json"
            output.write_bytes(b"retained")
            with redirect_stderr(io.StringIO()):
                result = inventory_animations.main(["--layout", "absent.xml", "--output", str(output)])
            self.assertEqual(result, 1)
            self.assertEqual(output.read_bytes(), b"retained")


class LbdReferenceTests(unittest.TestCase):
    def test_native_fixed_grid_and_inactive_stream_ignore_unread_offset(self):
        result = inventory_animations.lbd_info(lbd_fixture())
        self.assertEqual(result["fixed_grid_cells"], 400)
        self.assertEqual(result["grid_dimensions"], [20, 20])
        self.assertEqual(result["cell_chain_lengths"], {1: 400})
        self.assertEqual(result["tile_tags"], {"0": 400})
        self.assertIsNone(result["MML"])

    def test_model_index_is_validated_only_when_native_tile_tag_is_present(self):
        data = lbd_fixture()
        tile(data, 0, tag=0, model=65535)
        result = inventory_animations.lbd_info(data)
        self.assertEqual(result["present_records"], 0)
        tile(data, 0, tag=2, model=0)
        result = inventory_animations.lbd_info(data)
        self.assertEqual(result["present_model_indices"], {"0": 1})
        tile(data, 0, model=1)
        with self.assertRaisesRegex(ValueError, "model index"):
            inventory_animations.lbd_info(data)

    def test_native_continuations_are_grid_relative_and_may_reference_base_records(self):
        data = lbd_fixture(extra=2)
        tile(data, 0, continuation=4808)
        tile(data, 400, continuation=4820)
        tile(data, 401)
        tile(data, 1, continuation=32)  # Cell 2, not an absolute file offset.
        result = inventory_animations.lbd_info(data)
        self.assertEqual(result["additional_tile_records"], 2)
        self.assertEqual(result["continuation_links"], 3)
        self.assertEqual(result["continuations_to_base_records"], 1)
        self.assertEqual(result["cell_chain_lengths"], {3: 1, 2: 1, 1: 398})
        self.assertEqual(result["unreachable_additional_records"], 0)

    def test_unused_extra_record_is_reported_without_inventing_playback(self):
        result = inventory_animations.lbd_info(lbd_fixture(extra=1))
        self.assertEqual(result["unreachable_additional_records"], 1)

    def test_continuation_alignment_bounds_and_cycles_are_rejected(self):
        for offset in (4, 9, 4808, 0xFFFFFFFF):
            data = lbd_fixture()
            tile(data, 0, continuation=offset)
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, "continuation"):
                inventory_animations.lbd_info(data)
        for extra, index, offset in ((0, 0, 8), (1, 400, 4808)):
            data = lbd_fixture(extra=extra)
            tile(data, index, continuation=offset)
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, "cyclic"):
                inventory_animations.lbd_info(data)
        data = lbd_fixture()
        tile(data, 0, continuation=20)
        tile(data, 1, continuation=8)
        with self.assertRaisesRegex(ValueError, "cyclic"):
            inventory_animations.lbd_info(data)

    def test_grid_stride_and_TMD_descriptor_bounds_are_checked(self):
        for offset, value in ((4, 0), (4, 25), (8, 4804), (8, 0xFFFFFFFF)):
            data = lbd_fixture()
            struct.pack_into("<I", data, offset, value)
            with self.subTest(offset=offset, value=value), self.assertRaises(ValueError):
                inventory_animations.lbd_info(data)
        data = lbd_fixture()
        data[24 + 4808:24 + 4808] = bytes(4)
        struct.pack_into("<I", data, 8, 4812)
        with self.assertRaisesRegex(ValueError, "strides"):
            inventory_animations.lbd_info(data)
        data = lbd_fixture()
        struct.pack_into("<I", data, 24 + 4808 + 8, 1000)
        with self.assertRaisesRegex(ValueError, "descriptors"):
            inventory_animations.lbd_info(data)

    def test_MML_count_offsets_and_stream_extent_follow_native_reference_table(self):
        model = fixture()
        data = lbd_fixture(library_models=[model])
        result = inventory_animations.lbd_info(data)
        library = result["MML"]
        self.assertEqual(library["model_count"], 1)
        self.assertEqual(library["models"][0]["relative_offset"], 12)
        self.assertEqual(library["models"][0]["sha256"], hashlib.sha256(model).hexdigest())
        self.assertEqual(library["sha256"], hashlib.sha256(data[library["offset"]:]).hexdigest())
        self.assertEqual(result["grid_sha256"], hashlib.sha256(data[24:24 + 4808]).hexdigest())

    def test_empty_MML_table_and_aliased_references_remain_distinct_from_content(self):
        empty = inventory_animations.lbd_info(lbd_fixture(library_models=[]))["MML"]
        self.assertEqual(empty["model_count"], 0)
        self.assertFalse(empty["models"])
        result = inventory_animations.lbd_info(lbd_fixture(library_models=[fixture()], aliases=[0, 0]))
        library = result["MML"]
        self.assertEqual(library["model_count"], 2)
        self.assertEqual(library["distinct_model_offsets"], 1)
        self.assertEqual(library["models"][0]["offset"], library["models"][1]["offset"])

    def test_MML_stream_header_and_offsets_cannot_overlap_or_escape(self):
        for field, value in ((16, 24), (16, 0xFFFFFFFF), (20, 0), (20, 0xFFFFFFFF)):
            data = lbd_fixture(library_models=[fixture()])
            struct.pack_into("<I", data, field, value)
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "MML"):
                inventory_animations.lbd_info(data)
        for value in (0, 8, 13, 0xFFFFFFFF):
            data = lbd_fixture(library_models=[fixture()])
            library = struct.unpack_from("<I", data, 16)[0]
            struct.pack_into("<I", data, library + 8, value)
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "model offset"):
                inventory_animations.lbd_info(data)
        data = lbd_fixture(library_models=[fixture()])
        library = struct.unpack_from("<I", data, 16)[0]
        struct.pack_into("<I", data, library + 4, 1000)
        with self.assertRaisesRegex(ValueError, "offset table"):
            inventory_animations.lbd_info(data)

    def test_MML_model_cannot_consume_next_referenced_model_or_stream_padding(self):
        for truncate_stream in (False, True):
            data = lbd_fixture(library_models=[fixture(), fixture()])
            library = struct.unpack_from("<I", data, 16)[0]
            first = library + struct.unpack_from("<I", data, library + 8)[0]
            if truncate_stream:
                size = struct.unpack_from("<I", data, 20)[0]
                struct.pack_into("<I", data, 20, size - 4)
            else:
                struct.pack_into("<I", data, first + 4, len(fixture()) + 4)
            with self.subTest(truncate_stream=truncate_stream), self.assertRaisesRegex(ValueError, "declared size"):
                inventory_animations.lbd_info(data)

    def test_aliased_library_does_not_change_signature_instance_or_animation_totals(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "M000.LBD"
            data = lbd_fixture(library_models=[fixture()], aliases=[0, 0])
            path.write_bytes(data)
            report = inventory_animations.audit_files([{"path": "/M000.LBD", "source": str(path),
                "sha256": hashlib.sha256(data).hexdigest()}])
            self.assertEqual(report["totals"]["validated_MOM_instances"], 1)
            self.assertEqual(report["totals"]["records"], 6)
            self.assertEqual(report["LBD_totals"]["MML_model_references"], 2)
            self.assertEqual(report["MML_reference_audit"]["distinct_referenced_MOM_offsets"], 1)
            self.assertEqual(report["MML_reference_audit"]["unresolved_counts"], {
                "LBD_files": 0, "discovered_MOMs_without_MML_reference": 0,
                "MML_references_not_discovered_as_MOM": 0})
            self.assertEqual(path.read_bytes(), data)

    def test_unreferenced_signature_and_invalid_LBD_are_reported_explicitly(self):
        for valid in (True, False):
            with self.subTest(valid=valid), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "M000.LBD"
                data = lbd_fixture() if valid else bytearray(b"LBD ")
                data.extend(fixture())
                path.write_bytes(data)
                report = inventory_animations.audit_files([{"path": "/M000.LBD", "source": str(path),
                    "sha256": hashlib.sha256(data).hexdigest()}])
                counts = report["MML_reference_audit"]["unresolved_counts"]
                self.assertEqual(counts["LBD_files"], int(not valid))
                self.assertEqual(counts["discovered_MOMs_without_MML_reference"], 1)
                self.assertEqual(report["LBD_totals"]["validated_LBD_files"], int(valid))
                self.assertEqual(len(report["LBD_unresolved_files"]), int(not valid))

    def test_direct_model_is_excluded_from_LBD_reference_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "DIRECT.MOM"
            data = fixture()
            path.write_bytes(data)
            report = inventory_animations.audit_files([{"path": "/DIRECT.MOM", "source": str(path),
                "sha256": hashlib.sha256(data).hexdigest()}])
            self.assertEqual(report["totals"]["validated_MOM_instances"], 1)
            self.assertEqual(report["LBD_totals"]["input_LBD_files"], 0)
            self.assertEqual(report["MML_reference_audit"]["discovered_MOM_offsets_in_LBD"], 0)


class NativeEvidenceTests(unittest.TestCase):
    def executable(self):
        base, size = 0x80010000, 0x60000
        data = bytearray(0x800 + size)
        data[:8] = b"PS-X EXE"
        struct.pack_into("<II", data, 0x18, base, size)
        struct.pack_into("<I", data, 0x800 + 0x8006F1BC - base, 0x80043B58)
        return data

    def test_original_instruction_ranges_and_vtable_binding_have_byte_provenance(self):
        data = self.executable()
        result = inventory_animations.native_evidence(data)
        query = result["LBD_record_query"]
        offset = 0x800 + 0x8002C278 - 0x80010000
        self.assertEqual(query["executable_offset"], offset)
        self.assertEqual(query["bytes"], 304)
        self.assertEqual(query["sha256"], hashlib.sha256(data[offset:offset + 304]).hexdigest())
        self.assertEqual(result["LBD_TMD_selection_vtable_word"]["callback"], "0x80043B58")
        self.assertEqual(query["source_anchor"], "src/file/file_object.c:class_1C92C_unk29")

    def test_truncated_executable_and_wrong_vtable_target_do_not_pass_provenance(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            inventory_animations.native_evidence(self.executable()[:0x900])
        data = self.executable()
        struct.pack_into("<I", data, 0x800 + 0x8006F1BC - 0x80010000, 0x8004416C)
        with self.assertRaisesRegex(ValueError, "vtable word"):
            inventory_animations.native_evidence(data)


if __name__ == "__main__":
    unittest.main()
