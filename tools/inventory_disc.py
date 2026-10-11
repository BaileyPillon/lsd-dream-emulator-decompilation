"""Index a dumpsxiso extraction and inspect native TIM/TIX structures without edits."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.psx_image import EXECUTABLE_NAME, ORIGINAL_SHA1


def bounded_source(layout, source):
    base = Path(layout).resolve().parent
    path = (base / source).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise ValueError("Extraction source must be an existing file inside its layout directory: " + source)
    return path


def tim_info(data, offset=0, limit=None):
    """Read the blocks used by tim_image_get_info / the original GsGetTimInfo."""
    limit = len(data) if limit is None else limit
    if offset < 0 or limit > len(data) or offset + 8 > limit:
        raise ValueError("Truncated TIM header")
    magic, flags = struct.unpack_from("<II", data, offset)
    if magic != 0x10 or flags & ~0xB:
        raise ValueError("Unsupported TIM magic or flags")
    cursor = offset + 8

    def block(image=False):
        nonlocal cursor
        if cursor + 12 > limit:
            raise ValueError("Truncated TIM block header")
        size, x, y, width, height = struct.unpack_from("<I4H", data, cursor)
        expected = 12 + width * height * 2
        # GsGetTimInfo locates image pixels from the rectangle header; it
        # ignores the image block's length word. Preserve malformed original
        # lengths when the native rectangle still fits the physical extent.
        if size < 12 or (not image and size < expected) or cursor + max(size, expected) > limit:
            raise ValueError("TIM block exceeds its declared extent")
        result = {"offset": cursor, "bytes": size, "x": x, "y": y,
                  "width_words": width, "height": height,
                  "payload_bytes": width * height * 2, "padding_bytes": max(0, size - expected),
                  "declared_extent_shortfall_bytes": max(0, expected - size)}
        cursor += max(size, expected)
        return result

    clut = block() if flags & 8 else None
    image = block(image=True)
    return {"format": "TIM", "flags": flags, "pixel_mode": flags & 3,
            "clut": clut, "image": image, "used_bytes": cursor - offset,
            "remaining_bytes": limit - cursor, "validation": "native_block_structure"}


def tim_list_info(data):
    """The matching tim_list loader uses count, then file-relative TIM offsets."""
    if len(data) < 4:
        raise ValueError("Truncated TIM-list count")
    count = struct.unpack_from("<I", data)[0]
    table_end = 4 + count * 4
    if table_end > len(data):
        raise ValueError("TIM-list offset table exceeds file")
    offsets = list(struct.unpack_from(f"<{count}I", data, 4))
    if any(offset < table_end or offset >= len(data) for offset in offsets):
        raise ValueError("TIM-list TIM offset is outside its payload")
    bounds = sorted(set(offsets) | {len(data)})
    records = [tim_info(data, offset, next(bound for bound in bounds if bound > offset))
               for offset in offsets]
    return {"format": "TIM-list", "tim_records": count, "distinct_tim_offsets": len(set(offsets)),
            "offsets": offsets, "textures": records, "validation": "native_offset_table_and_TIM_blocks"}


def tix_info(data):
    """Stage files have four offset/size slots and a count of populated banks."""
    if len(data) < 36:
        raise ValueError("Truncated stage texture header")
    count = struct.unpack_from("<I", data)[0]
    if not 1 <= count <= 4:
        raise ValueError("Unsupported stage texture bank count")
    offsets = struct.unpack_from("<4I", data, 4)[:count]
    sizes = struct.unpack_from("<4I", data, 20)[:count]
    banks = []
    for offset, size in zip(offsets, sizes):
        if offset < 36 or size < 4 or offset + size > len(data):
            raise ValueError("Stage texture bank exceeds its file extent")
        bank = tim_list_info(data[offset:offset + size])
        banks.append({"offset": offset, "bytes": size, **bank})
    return {"format": "TIX", "bank_count": count, "banks": banks,
            "tim_records": sum(bank["tim_records"] for bank in banks),
            "validation": "native_stage_header_TIM_lists_and_TIM_blocks"}


def digest_file(path):
    sha256, sha1 = hashlib.sha256(), hashlib.sha1()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            sha256.update(chunk)
            sha1.update(chunk)
    return sha256.hexdigest(), sha1.hexdigest()


def inspect_layout(layout):
    layout = Path(layout).resolve()
    xml = ET.parse(layout).getroot()
    tree = xml.find("./track/directory_tree")
    if tree is None:
        raise ValueError("Layout has no data-track directory tree")
    records, names = [], set()

    def visit(directory, parent=PurePosixPath("/")):
        for element in directory:
            if element.tag not in ("file", "dir"):
                continue
            name = element.get("name", "")
            if not name or name in (".", "..") or "/" in name or "\\" in name:
                raise ValueError("Invalid disc entry name")
            virtual = parent / name
            if element.tag == "dir":
                visit(element, virtual)
                continue
            if str(virtual) in names:
                raise ValueError("Duplicate disc path: " + str(virtual))
            names.add(str(virtual))
            path = bounded_source(layout, element.get("source", ""))
            sha256, sha1 = digest_file(path)
            extension = path.suffix.upper()
            record = {"path": str(virtual), "source": str(path), "lba": int(element.attrib["offs"]),
                      "storage_type": element.get("type"), "bytes": path.stat().st_size,
                      "sha256": sha256, "sha1": sha1, "extension": extension}
            with path.open("rb") as stream:
                record["header_hex"] = stream.read(32).hex()
            if name == EXECUTABLE_NAME:
                if sha1 != ORIGINAL_SHA1:
                    raise ValueError("Disc executable is not the canonical LSD executable")
                record["format_analysis"] = {"format": "PS-X EXE", "canonical_match": True,
                                             "validation": "canonical_executable_hash"}
            elif extension in (".TIM", ".TIX"):
                try:
                    record["format_analysis"] = (tim_info if extension == ".TIM" else tix_info)(path.read_bytes())
                except ValueError as error:
                    record["format_analysis"] = {"format": extension[1:], "validation": "unresolved",
                                                  "reason": str(error)}
            else:
                record["format_analysis"] = {"format": extension[1:], "validation": "header_and_hash_only"}
            records.append(record)

    visit(tree)
    if "/" + EXECUTABLE_NAME not in names:
        raise ValueError("Canonical executable is absent from the layout")
    stages = {}
    for record in records:
        parts = PurePosixPath(record["path"]).parts
        for part in parts:
            if part.startswith("STG") and len(part) == 5 and part[3:].isdigit():
                stages.setdefault(part, []).append(record)
    texture_banks = [record for record in records if record["extension"] == ".TIX"]
    return {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
        "layout": str(layout), "layout_sha256": hashlib.sha256(layout.read_bytes()).hexdigest(),
        "scope": "Owned English v1 disc extraction; file identity and selected native structures. Content counts are not feature counts.",
        "input_modified": False, "official_feature_total": None,
        "file_count": len(records), "extensions": dict(sorted(Counter(r["extension"] for r in records).items())),
        "storage_types": dict(Counter(r["storage_type"] for r in records)),
        "stage_directories": {name: {"files": len(items), "extensions": dict(Counter(r["extension"] for r in items))}
                              for name, items in sorted(stages.items())},
        "texture_bank_tim_records": sum(r["format_analysis"].get("tim_records", 0) for r in texture_banks),
        "unresolved_texture_files": [r["path"] for r in records if r["format_analysis"]["validation"] == "unresolved"],
        "native_format_evidence": ["src/scene/stage_texture.c:func_800434DC",
                                   "asm/nonmatchings/scene/stage_texture/func_80043200.s",
                                   "src/file/tim_list.c:func_80043CB8", "src/file/tim_image.c:tim_get_info",
                                   "asm/nonmatchings/psyq/gs/GsGetTimInfo/GsGetTimInfo.s"],
        "mixed_sector_note": "Movie records use dumpsxiso's mixed extraction. Generic 2048-byte ISO reads must not substitute for these records.",
        "files": records}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if Path(args.output).exists():
            raise ValueError("Choose a new output file; existing inventories are preserved.")
        report = inspect_layout(args.layout)
        with Path(args.output).open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
        print(f"{report['file_count']} files, {len(report['stage_directories'])} stage directories, "
              f"{report['texture_bank_tim_records']} bank TIM records; "
              f"{len(report['unresolved_texture_files'])} texture files unresolved.")
        return 0
    except (OSError, ValueError, ET.ParseError) as error:
        print(f"[!] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
