"""Locate recorded Nymashock string-storage differences without masking state bytes."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# This profile was checked against the installed BizHawk 2.11.1 Windows core,
# its symbols, Waterbox serializer and native RMD construction instructions.
CORE_SHA256 = "5c6fe90fadd670318ca74993911b171e15b167c7f2e1e88bf66de4661fc24126"
BASE = 0x36F00000000
MEMORY_SIZE = 0xD80A000
PAGE_SIZE = 4096
GAME_INFO_POINTER = BASE + 0x29A9F0
GAME_INFO = BASE + 0x29A850
RMD_OFFSET = 344
STRING_SIZE = 24
MEMORY_MAGIC = b"ActivatedMemoryBlock"
HOST_MAGIC = b"ActivatedWaterboxHost_v1"
HOST_END = "ʇsoHxoqɹǝʇɐMpǝʇɐʌᴉʇɔ∀".encode()
INVISIBLE = ((BASE + 0x296000, BASE + 0x297000),
             (BASE + 0x60A000, BASE + 0x80A000),
             (BASE + 0x480A000, BASE + 0x780A000))


def digest(data):
    return hashlib.sha256(data).hexdigest()


class MemoryView:
    """Read only pages actually stored in this profiled Waterbox snapshot."""

    def __init__(self, data):
        if not data.startswith(HOST_MAGIC):
            raise ValueError("Not an activated Waterbox v1 state.")
        marker = data.find(MEMORY_MAGIC, len(HOST_MAGIC))
        if marker < 0:
            raise ValueError("Missing Waterbox memory block.")
        header = marker + len(MEMORY_MAGIC) + 32  # sealed-memory hash
        if len(data) < header + 16:
            raise ValueError("Truncated memory-block header.")
        base, size = struct.unpack_from("<QQ", data, header)
        if (base, size) != (BASE, MEMORY_SIZE):
            raise ValueError("Memory layout does not match the checked Nymashock profile.")
        count = size // PAGE_SIZE
        start = header + 16 + 2 * count
        if len(data) < start:
            raise ValueError("Truncated page-status/dirty tables.")
        statuses = data[header + 16:header + 16 + count]
        dirty = data[header + 16 + count:start]
        if any(x > 6 for x in statuses) or any(x > 1 for x in dirty):
            raise ValueError("Invalid page-status/dirty table.")
        indices = [i for i, value in enumerate(dirty) if value and not any(
            lower <= BASE + i * PAGE_SIZE < upper for lower, upper in INVISIBLE)]
        end = start + len(indices) * PAGE_SIZE
        tail = data[end:]
        if not tail.startswith(b"GuestThreadSet") or HOST_END not in tail:
            raise ValueError("Stored pages are truncated or the serializer profile differs.")
        self.data = data
        self.pages = {page: start + i * PAGE_SIZE for i, page in enumerate(indices)}

    def offsets(self, address, size):
        if size < 0 or address < BASE or address + size > BASE + MEMORY_SIZE:
            raise ValueError("Read is outside the profiled memory block.")
        result = []
        for current in range(address, address + size):
            page, offset = divmod(current - BASE, PAGE_SIZE)
            if page not in self.pages:
                raise ValueError("Requested memory page was not saved; no baseline bytes inferred.")
            result.append(self.pages[page] + offset)
        return result

    def read(self, address, size):
        return bytes(self.data[i] for i in self.offsets(address, size))

    def pointer(self, address):
        return struct.unpack("<Q", self.read(address, 8))[0]


def media_type(view):
    game = view.pointer(GAME_INFO_POINTER)
    if game != GAME_INFO:
        raise ValueError("Game-info pointer differs from the checked core symbol.")
    rmd = view.pointer(game + RMD_OFFSET)
    if not BASE + 0x80A000 <= rmd <= BASE + 0x180A000 - 96:
        raise ValueError("RMD layout is outside the native sbrk heap.")
    begin, end, capacity = struct.unpack("<QQQ", view.read(rmd + 24, 24))
    if (end - begin != STRING_SIZE or not begin <= end <= capacity
            or not BASE + 0x80A000 <= begin <= capacity <= BASE + 0x180A000
            or (capacity - begin) % STRING_SIZE):
        raise ValueError("Expected one native RMD media-type record.")
    name = view.read(begin, STRING_SIZE)
    if name[0] != 4 or name[1:4] != b"CD\0":
        raise ValueError("Expected the checked libc++ short CD label.")
    return {"game_info_pointer": hex(GAME_INFO_POINTER), "game_info": hex(game),
            "rmd_layout": hex(rmd), "media_type_name": hex(begin),
            "name": "CD", "name_length": 2, "string_object_bytes": STRING_SIZE,
            "unused_storage_object_offsets": [4, 23],
            "unused_storage_serialized_offsets": view.offsets(begin + 4, 20)}


def compare_decoded(original, rebuilt):
    first, second = media_type(MemoryView(original)), media_type(MemoryView(rebuilt))
    differences = [i for i, (a, b) in enumerate(zip(original, rebuilt)) if a != b]
    length_difference = abs(len(original) - len(rebuilt))
    # The complete byte result remains authoritative. Classification never
    # removes differences, rewrites inputs or creates a normalized state.
    unused = set(first["unused_storage_serialized_offsets"]) & set(
        second["unused_storage_serialized_offsets"])
    classified = [i for i in differences if i in unused]
    return {"decoded_bytes": [len(original), len(rebuilt)],
            "decoded_sha256": [digest(original), digest(rebuilt)],
            "whole_decoded_bytes_equal": original == rebuilt,
            "different_bytes": len(differences) + length_difference,
            "length_difference": length_difference,
            "different_offset_sample": differences[:64],
            "identified_unused_label_storage_difference_bytes": len(classified),
            "unclassified_difference_bytes": len(differences) - len(classified) + length_difference,
            "classification": "unused_RMD_media_type_name_storage" if classified else "no_identified_label_storage_difference",
            "objects": [first, second], "state_bytes_masked": 0,
            "whole_feature_groups_accepted": 0}


def decompress(data):
    try:
        from compression import zstd
    except ImportError:
        try:
            import zstandard
        except ImportError as error:
            raise ValueError("Use Python 3.14 or install requirements-analysis.txt for Zstandard decoding.") from error
        decode = lambda value: zstandard.ZstdDecompressor().decompress(
            value, max_output_size=MEMORY_SIZE + 1024 * 1024)
        decode_error = zstandard.ZstdError
    else:
        decode, decode_error = zstd.decompress, zstd.ZstdError
    try:
        result = decode(data)
    except decode_error as error:
        raise ValueError("Invalid compressed core-state member.") from error
    if len(result) > MEMORY_SIZE + 1024 * 1024:
        raise ValueError("Decoded state exceeds the profiled memory extent.")
    return result


def read_state(path):
    path = Path(path)
    raw = path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.namelist().count("Core.bin.zst") != 1:
            raise ValueError("Expected one compressed core-state member.")
        decoded = decompress(archive.read("Core.bin.zst"))
    return decoded, {"path": str(path.resolve()), "sha256": digest(raw)}


def inspect(original, rebuilt, core):
    core = Path(core)
    core_hash = digest(core.read_bytes())
    if core_hash != CORE_SHA256:
        raise ValueError("Core binary is outside the checked BizHawk 2.11.1 Windows Nymashock profile.")
    first, first_pin = read_state(original)
    second, second_pin = read_state(rebuilt)
    return {"schema_version": 1, "profile": "BizHawk 2.11.1 Windows Nymashock",
            "core_binary_sha256": core_hash, "state_files": [first_pin, second_pin],
            **compare_decoded(first, second),
            "scope": "Read-only core-state structure and unused short-string storage diagnosis. Full byte differences remain reported. Launch-input identity, other state members, game scenarios and feature acceptance require separate evidence."}


def inspect_native(original, rebuilt, core, controls=False, execute=True):
    """Inspect pinned ELF ownership and optionally execute its real string accessors."""
    from research.emulator_state import CoreImage, Snapshot, classify, execute_accessors, require
    from tools.compare_runtime import compare_state

    require(not controls or execute, 'Accessor controls require --execute-accessors.')
    image = CoreImage(core)
    paths = [Path(original), Path(rebuilt)]
    snapshots = [Snapshot.from_file(path, image.layout) for path in paths]
    report = classify(image, *snapshots)
    report.update(schema_version=2, core_input_sha256=image.input_sha256,
                  raw_archive_comparison=compare_state(*paths), accessors_executed=execute,
                  parity_profile_accepted=False, new_c_bytes=0)
    if execute:
        report['accessor_campaigns'] = [execute_accessors(image, snapshot, controls) for snapshot in snapshots]
    report['producer_sha256'] = digest(Path(__file__).read_bytes())
    report['reader_sha256'] = digest((ROOT / 'research/emulator_state.py').read_bytes())
    report['scope'] = ('Pinned emulator media metadata and actual bundled accessors; raw archive comparisons '
                       'remain strict. This does not promote game source or accept a complete runtime profile.')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("original", "rebuilt", "core", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument('--execute-accessors', action='store_true',
                        help='Execute the pinned x86-64 string accessors in isolated Unicorn 2.1.4.')
    parser.add_argument('--controls', action='store_true',
                        help='Also vary private accessor inputs; requires --execute-accessors.')
    args = parser.parse_args(argv)
    try:
        if args.controls and not args.execute_accessors:
            raise ValueError('Accessor controls require --execute-accessors.')
        if args.output.exists():
            raise ValueError("Choose a new diagnostic output; previous evidence is preserved.")
        if args.execute_accessors:
            report = inspect_native(args.original, args.rebuilt, args.core, args.controls)
        else:
            report = inspect(args.original, args.rebuilt, args.core)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
        if args.execute_accessors:
            print(json.dumps({key: report[key] for key in ('core_frame', 'different_decoded_bytes',
                             'all_differences_in_unused_media_label_storage', 'accessors_executed',
                             'parity_profile_accepted')}))
        else:
            print(f"Decoded differences: {report['different_bytes']}; unused label storage: "
                  f"{report['identified_unused_label_storage_difference_bytes']}; "
                  f"unclassified: {report['unclassified_difference_bytes']}. No bytes masked.")
        return 0
    except (OSError, ValueError, zipfile.BadZipFile, KeyError, struct.error) as error:
        print(f"[!] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
