"""Read native LBD/MML references and MOM/MOS records in a disc extraction.

Native offset tables and signature discovery are bounded and cross-checked.
This is a static content audit, not a runtime test. Inputs are never modified.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.inventory_disc import inspect_layout
from tools.psx_image import EXECUTABLE_NAME, ORIGINAL_SHA1, executable_offset

SOURCE_ANCHORS = {
    "MOM_TMD_and_MOS": "src/file/object_model.c:func_80044858",
    "MOS_relative_offsets": "src/file/model_part_list.c:func_800452FC",
    "actor_child_types": "src/file/model_part_list.c:func_800453DC",
    "animation_frame_count": "src/scene/actor.c:func_80066214",
    "frame_record_count": "src/scene/actor.c:func_800662BC",
    "record_fields": "src/file/model_part.c:func_8004416C",
    "record_payloads": "src/scene/actor.c:func_80066340",
    "LBD_grid_TMD_binding": "src/scene/render_context.c:func_8004BE54",
    "LBD_record_query": "src/file/file_object.c:class_1C92C_unk29",
    "LBD_TMD_selection": "src/file/tmd_model.c:func_80043B58",
    "MML_stream_extent": "src/file/cd_stream.c:func_80048BC0",
    "MML_offset_table": "src/file/object_model_list.c:func_80044B88",
    "MML_model_selection": "src/file/object_model_list.c:func_80044C90",
    "MML_spawn_handoff": "src/scene/map_scene_post.c:func_80054120",
    "MML_spawn_consumer": "src/scene/link.c:link_spawn_object_group",
}

# Original executable ranges, independently of generated assembly files.
NATIVE_RANGES = {
    "LBD_grid_TMD_binding": (0x8004BE54, 0x258),
    "LBD_record_query": (0x8002C278, 0x130),
    "MML_stream_extent": (0x80048BC0, 0xD8),
    "MML_offset_table": (0x80044B88, 0xD0),
    "LBD_TMD_selection_vtable_word": (0x8006F1BC, 4),
}
GRID_CELLS = 400
GRID_HEADER_BYTES = 8
TILE_BYTES = 12
GRID_BYTES = GRID_HEADER_BYTES + GRID_CELLS * TILE_BYTES


def word(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def half(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


def mom_info(container, start, limit=None):
    limit = len(container) if limit is None else limit
    if limit < 0 or limit > len(container) or start < 0 or start % 4 or start + 24 > limit:
        raise ValueError("unaligned or truncated MOM header")
    if container[start:start + 4] != b"MOM ":
        raise ValueError("MOM signature is absent")
    size = word(container, start + 4)
    if size < 24 or start + size > limit:
        raise ValueError("MOM declared size exceeds physical container")
    data = container[start:start + size]
    tmd = word(data, 8)
    if tmd < 20 or tmd % 4 or tmd + 12 > size or word(data, tmd) != 0x41:
        raise ValueError("MOM TMD offset does not identify a bounded TMD header")
    mapped, objects = word(data, tmd + 4), word(data, tmd + 8)
    if tmd + 12 + objects * 28 > size:
        raise ValueError("TMD object descriptors exceed MOM extent")
    if data[12:16] != b"MOS ":
        raise ValueError("MOM animation area does not have MOS signature")
    count = word(data, 16)
    table_end = 20 + count * 4
    if table_end > tmd:
        raise ValueError("MOS offset table overlaps TMD")
    offsets = [12 + word(data, 20 + i * 4) for i in range(count)]
    if any(offset < table_end or offset % 4 or offset + 8 > tmd for offset in offsets):
        raise ValueError("MOS animation offset is outside animation extent")
    bounds = sorted(set(offsets) | {tmd})
    kinds, flags, fields, shapes = Counter(), Counter(), Counter(), Counter()
    missing_types, parents, selections = [], [], []
    samples, animations = {}, []
    total_frames = total_records = 0
    initial_types = set()
    for animation, offset in enumerate(offsets):
        limit = next(bound for bound in bounds if bound > offset)
        tag, header_half, frames = half(data, offset), half(data, offset + 2), word(data, offset + 4)
        cursor = offset + 8
        if frames > (limit - cursor) // 8:
            raise ValueError("animation frame count exceeds bounded extent")
        records_in_animation = 0
        types = None
        for frame in range(frames):
            if cursor + 8 > limit:
                raise ValueError("truncated frame header")
            records = half(data, cursor + 2)
            cursor += 8
            frame_records = []
            for record in range(records):
                if cursor + 4 > limit:
                    raise ValueError("truncated animation record")
                lead = word(data, cursor)
                type_id, kind, flag, words = lead & 255, (lead >> 16) & 15, (lead >> 20) & 15, lead >> 24
                if not words or cursor + words * 4 > limit:
                    raise ValueError("record word count is zero or exceeds animation extent")
                minimum = {0: 3, 2: 2, 3: 2, 8: 1}.get(kind, 1)
                if kind == 1:
                    minimum = 1 + (3 if flag & 2 else 0) + (2 if flag & 4 else 0) + (3 if flag & 8 else 0)
                if words < minimum:
                    raise ValueError("record payload is shorter than native interpreter reads")
                kinds[str(kind)] += 1
                key = f"{kind}:{flag}"
                flags[key] += 1
                shapes[f"{key}:{words}"] += 1
                if kind == 1:
                    fields["relative" if flag & 1 else "absolute"] += 1
                    for mask, label in ((2, "angles"), (4, "scale"), (8, "position")):
                        if flag & mask:
                            fields[label] += 1
                location = {"animation": animation, "frame": frame, "record": record,
                            "MOM_offset": cursor, "container_offset": start + cursor,
                            "type": type_id, "words": words}
                if len(samples.setdefault(key, [])) < 3:
                    samples[key].append(location)
                payload = word(data, cursor + 4) if words > 1 else None
                frame_records.append((type_id, kind, flag, payload, location))
                cursor += words * 4
            if frame == 0:
                types = {type_id for type_id, kind, flag, _, _ in frame_records if kind == 8 and flag == 0}
                if animation == 0:
                    initial_types = types
            for type_id, kind, flag, payload, location in frame_records:
                if kind in (0, 1, 2, 3) and type_id not in initial_types:
                    missing_types.append(location)
                if kind == 2 and (payload & 65535) > objects:
                    selections.append({**location, "one_based_selection": payload & 65535})
                if kind == 3 and payload not in (0, 65535) and (payload & 255) not in initial_types:
                    parents.append({**location, "parent_type": payload & 255})
            records_in_animation += records
        animations.append({"index": animation, "offset": offset, "header_tag": tag,
                           "header_halfword": header_half, "frames": frames,
                           "records": records_in_animation, "child_type_count": len(types or ()),
                           "child_types": sorted(types or ()),
                           "child_types_equal_first_animation": (types or set()) == initial_types,
                           "used_bytes": cursor - offset, "trailing_bytes": limit - cursor})
        total_frames += frames
        total_records += records_in_animation
    return {"offset": start, "bytes": size, "sha256": hashlib.sha256(data).hexdigest(),
            "tmd_offset": tmd, "tmd_mapped_flag": mapped, "tmd_objects": objects,
            "animation_count": count, "distinct_animation_offsets": len(set(offsets)),
            "frame_count": total_frames, "record_count": total_records,
            "kind_counts": dict(kinds), "kind_flag_counts": dict(flags), "record_shapes": dict(shapes),
            "transform_fields": dict(fields), "animations": animations, "samples": samples,
            "missing_command_child_types": missing_types, "missing_parent_types": parents,
            "out_of_range_primitive_selections": selections}


def lbd_info(data):
    """Bound native fixed grid, chained records, TMD descriptors and streamed MML.

    The game's reader trusts these offsets. Here malformed data is reported,
    rather than dereferenced or silently accepted. Primitive contents are not
    decoded. Tile tag zero suppresses the model lookup in the original reader.
    """
    if len(data) < 24:
        raise ValueError("truncated LBD header")
    grid, tmd_relative = word(data, 4), word(data, 8)
    tmd = grid + tmd_relative
    if (grid < 24 or grid % 4 or tmd_relative < GRID_BYTES or tmd % 4
            or tmd + 12 > len(data) or word(data, tmd) != 0x41):
        raise ValueError("LBD grid or TMD extent is invalid")
    extra_bytes = tmd_relative - GRID_BYTES
    if extra_bytes % TILE_BYTES:
        raise ValueError("additional tile records do not have 12-byte strides")
    objects = word(data, tmd + 8)
    descriptors_end = tmd + 12 + objects * 28
    if descriptors_end > len(data):
        raise ValueError("LBD TMD object descriptors exceed file extent")
    present, models, tags, next_records = 0, Counter(), Counter(), {}
    links = links_to_base = 0
    for index in range(GRID_CELLS + extra_bytes // TILE_BYTES):
        relative = GRID_HEADER_BYTES + index * TILE_BYTES
        tag, _, model, _, _, _, continuation = struct.unpack_from("<BBHBBhI", data, grid + relative)
        tags[str(tag)] += 1
        if tag:
            present += 1
            models[str(model)] += 1
            if model >= objects:
                raise ValueError("present tile model index exceeds native TMD count")
        if continuation:
            if (continuation < GRID_HEADER_BYTES or (continuation - GRID_HEADER_BYTES) % TILE_BYTES
                    or continuation + TILE_BYTES > tmd_relative):
                raise ValueError("tile continuation is outside bounded grid records")
            links += 1
            links_to_base += continuation < GRID_BYTES
        next_records[relative] = continuation
    # Memoize lengths so shared chains and large malformed inputs stay bounded.
    lengths = {}
    for start in next_records:
        path, visited, cursor = [], set(), start
        while cursor and cursor not in lengths:
            if cursor in visited:
                raise ValueError("cyclic tile continuation")
            visited.add(cursor)
            path.append(cursor)
            cursor = next_records[cursor]
        length = lengths.get(cursor, 0)
        for cursor in reversed(path):
            length += 1
            lengths[cursor] = length
    cell_lengths = Counter(lengths[GRID_HEADER_BYTES + i * TILE_BYTES] for i in range(GRID_CELLS))
    reachable = set()
    for index in range(GRID_CELLS):
        cursor = GRID_HEADER_BYTES + index * TILE_BYTES
        while cursor and cursor not in reachable:
            reachable.add(cursor)
            cursor = next_records[cursor]
    library = None
    if half(data, 2):
        offset, size = word(data, 16), word(data, 20)
        limit = offset + size
        if (size < 8 or offset % 4 or offset < descriptors_end or limit > len(data)
                or data[offset:offset + 4] != b"MML "):
            raise ValueError("bounded streamed MML header is absent or overlaps TMD descriptors")
        count = word(data, offset + 4)
        table_end = offset + 8 + count * 4
        if table_end > limit:
            raise ValueError("MML offset table exceeds streamed extent")
        offsets = [offset + word(data, offset + 8 + i * 4) for i in range(count)]
        if any(start < table_end or start % 4 or start + 24 > limit for start in offsets):
            raise ValueError("MML model offset is outside streamed model extent")
        bounds = sorted(set(offsets) | {limit})
        referenced = []
        for index, start in enumerate(offsets):
            bound = next(bound for bound in bounds if bound > start)
            model = mom_info(data, start, limit=bound)
            referenced.append({"index": index, "offset": start, "relative_offset": start - offset,
                               "bounded_bytes": bound - start,
                               "bytes": model["bytes"], "sha256": model["sha256"]})
        library = {"offset": offset, "streamed_bytes": size, "model_count": count,
                   "distinct_model_offsets": len(set(offsets)),
                   "sha256": hashlib.sha256(data[offset:limit]).hexdigest(), "models": referenced}
    return {"grid_offset": grid, "grid_dimensions": list(struct.unpack_from("<2H", data, grid + 4)),
            "fixed_grid_cells": GRID_CELLS, "additional_tile_records": extra_bytes // TILE_BYTES,
            "tile_header_extra_halfword": half(data, grid + 2), "present_records": present,
            "tile_tags": dict(tags), "present_model_indices": dict(models),
            "continuation_links": links, "continuations_to_base_records": links_to_base,
            "cell_chain_lengths": dict(cell_lengths),
            "unreachable_additional_records": len(next_records) - len(reachable),
            "grid_sha256": hashlib.sha256(data[grid:tmd]).hexdigest(),
            "tmd_offset": tmd, "tmd_mapped_flag": word(data, tmd + 4), "tmd_objects": objects,
            "tmd_descriptor_sha256": hashlib.sha256(data[tmd:descriptors_end]).hexdigest(), "MML": library}


def native_evidence(executable):
    """Hash original instructions and verify the tile-query TMD vtable binding."""
    records = {}
    for name, (address, size) in NATIVE_RANGES.items():
        offset = executable_offset(executable, address, size)
        records[name] = {"address": f"0x{address:08X}", "bytes": size, "executable_offset": offset,
                         "sha256": hashlib.sha256(executable[offset:offset + size]).hexdigest()}
        if name in SOURCE_ANCHORS:
            records[name]["source_anchor"] = SOURCE_ANCHORS[name]
    callback = word(executable, records["LBD_TMD_selection_vtable_word"]["executable_offset"])
    if callback != 0x80043B58:
        raise ValueError("Original tile-query vtable word does not bind func_80043B58")
    records["LBD_TMD_selection_vtable_word"].update(
        {"callback": f"0x{callback:08X}", "source_anchor": SOURCE_ANCHORS["LBD_TMD_selection"]})
    return records


def audit_files(records):
    """Inspect already bounded MOM/LBD file records from an extraction layout."""
    records = sorted(records, key=lambda record: record["path"])
    files, rejected = [], []
    totals = Counter()
    kinds, flags, fields = Counter(), Counter(), Counter()
    unique = {}
    lbd_totals = Counter({key: 0 for key in ("input_LBD_files", "validated_LBD_files", "fixed_grid_cells",
        "additional_tile_records", "present_records", "continuation_links", "continuations_to_base_records",
        "unreachable_additional_records", "MML_files", "MML_model_references")})
    lbd_unresolved, scanned, referenced = [], set(), set()
    for record in records:
        path = Path(record["source"])
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise ValueError("Input changed during inventory: " + record["path"])
        models = []
        at = data.find(b"MOM ")
        while at >= 0:
            totals["signature_candidates"] += 1
            try:
                model = mom_info(data, at)
            except (ValueError, struct.error) as error:
                rejected.append({"file": record["path"], "offset": at, "reason": str(error)})
            else:
                models.append(model)
                unique[model["sha256"]] = model
                totals["validated_MOM_instances"] += 1
                totals["animations"] += model["animation_count"]
                totals["frames"] += model["frame_count"]
                totals["records"] += model["record_count"]
                totals["missing_command_child_types"] += len(model["missing_command_child_types"])
                totals["missing_parent_types"] += len(model["missing_parent_types"])
                totals["out_of_range_primitive_selections"] += len(model["out_of_range_primitive_selections"])
                kinds.update(model["kind_counts"])
                flags.update(model["kind_flag_counts"])
                fields.update(model["transform_fields"])
            at = data.find(b"MOM ", at + 1)
        lbd = None
        if path.suffix.upper() == ".LBD":
            lbd_totals["input_LBD_files"] += 1
            scanned.update((record["path"], model["offset"]) for model in models)
            try:
                lbd = lbd_info(data)
            except (ValueError, struct.error) as error:
                lbd_unresolved.append({"file": record["path"], "reason": str(error)})
            else:
                lbd_totals["validated_LBD_files"] += 1
                for key in ("fixed_grid_cells", "additional_tile_records", "present_records", "continuation_links",
                            "continuations_to_base_records", "unreachable_additional_records"):
                    lbd_totals[key] += lbd[key]
                if lbd["MML"] is not None:
                    lbd_totals["MML_files"] += 1
                    lbd_totals["MML_model_references"] += lbd["MML"]["model_count"]
                    referenced.update((record["path"], model["offset"]) for model in lbd["MML"]["models"])
        files.append({"path": record["path"], "source": str(path), "bytes": len(data),
                      "sha256": record["sha256"], "sha1": hashlib.sha1(data).hexdigest(),
                      "models": models, "validation": "unresolved" if path.suffix.upper() == ".MOM"
                          and not any(model["offset"] == 0 for model in models) else "bounded_signature_scan",
                      "LBD_analysis": lbd})
    totals["input_files"] = len(files)
    totals["distinct_MOM_hashes"] = len(unique)
    totals["rejected_signature_candidates"] = len(rejected)
    unique_totals = {"models": len(unique),
                     "animations": sum(model["animation_count"] for model in unique.values()),
                     "frames": sum(model["frame_count"] for model in unique.values()),
                     "records": sum(model["record_count"] for model in unique.values())}
    unreferenced = [{"file": path, "offset": offset} for path, offset in sorted(scanned - referenced)]
    undiscovered = [{"file": path, "offset": offset} for path, offset in sorted(referenced - scanned)]
    return {"schema_version": 2, "created_at": datetime.now(timezone.utc).isoformat(),
            "input_modified": False, "gameplay_tested": False, "official_feature_total": None,
            "scope": "Bounded MOM signatures and native LBD grid/TMD/MML offsets in extracted MOM/LBD files; static animation payload and streamed MML-to-MOM reference checks. Content counts are not features.",
            "limitations": ["Bounds grid records, continuation chains and MML-to-MOM offsets; does not decode TMD primitive payloads or collision structures, or prove the complete runtime resource graph.",
                            "MML references cross-check the signature scan without adding duplicate animation/model instance counts. Unresolved LBD files and unreferenced discovered MOMs remain explicit.",
                            "Kind 8 declarations and kind 15 records are structurally counted; runtime meaning is not inferred from their numbers.",
                            "No animation playback, visual comparison or feature acceptance is claimed."],
            "totals": dict(totals), "unique_content_totals": unique_totals,
            "kind_counts": dict(kinds), "kind_flag_counts": dict(flags),
            "transform_fields": dict(fields), "rejected": rejected, "files": files,
            "LBD_totals": dict(lbd_totals), "LBD_unresolved_files": lbd_unresolved,
            "MML_reference_audit": {"discovered_MOM_offsets_in_LBD": len(scanned),
                "distinct_referenced_MOM_offsets": len(referenced),
                "discovered_MOMs_without_MML_reference": unreferenced,
                "MML_references_not_discovered_as_MOM": undiscovered,
                "unresolved_counts": {"LBD_files": len(lbd_unresolved),
                    "discovered_MOMs_without_MML_reference": len(unreferenced),
                    "MML_references_not_discovered_as_MOM": len(undiscovered)}}}



def inspect_animations(layout):
    disc = inspect_layout(layout)
    selected = [record for record in disc["files"] if record["extension"] in (".MOM", ".LBD")]
    report = audit_files(selected)
    executable = next(record for record in disc["files"] if record["path"] == "/" + EXECUTABLE_NAME)
    original_bytes = Path(executable["source"]).read_bytes()
    if hashlib.sha256(original_bytes).hexdigest() != executable["sha256"]:
        raise ValueError("Original executable changed during inventory")
    source_files = sorted({anchor.split(":", 1)[0] for anchor in SOURCE_ANCHORS.values()})
    dependencies = ["tools/inventory_disc.py", "tools/psx_image.py"]
    report.update({"layout": disc["layout"], "layout_sha256": disc["layout_sha256"],
                   "disc_file_count": disc["file_count"],
                   "original_executable": {key: executable[key] for key in ("path", "bytes", "sha256", "sha1")},
                   "canonical_executable_sha1": ORIGINAL_SHA1,
                   "native_executable_evidence": native_evidence(original_bytes),
                   "producer": {"path": "tools/inventory_animations.py",
                                "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
                   "dependency_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                                         for path in dependencies},
                   "source_anchors": SOURCE_ANCHORS,
                   "source_sha256": {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                                     for path in source_files},
                   "unresolved_direct_model_files": [record["path"] for record in report["files"]
                                                     if record["validation"] == "unresolved"]})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        output = Path(args.output)
        if output.exists():
            raise ValueError("Choose a new output file; existing inventories are preserved.")
        report = inspect_animations(args.layout)
        with output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
        totals = report["totals"]
        print(f"{totals['input_files']} files, {totals['validated_MOM_instances']} MOM instances, "
              f"{totals['distinct_MOM_hashes']} distinct model hashes; "
              f"{totals['animations']} animations, {totals['frames']} frames, {totals['records']} records. "
              f"{totals['rejected_signature_candidates']} signatures rejected, "
              f"{len(report['unresolved_direct_model_files'])} direct models unresolved. "
              f"{report['LBD_totals']['validated_LBD_files']}/{report['LBD_totals']['input_LBD_files']} LBD files bounded, "
              f"{report['LBD_totals']['MML_model_references']} MML model references, "
              f"reference unresolved counts {report['MML_reference_audit']['unresolved_counts']}. Content counts only.")
        return 0
    except (OSError, ValueError, ET.ParseError) as error:
        print(f"[!] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
