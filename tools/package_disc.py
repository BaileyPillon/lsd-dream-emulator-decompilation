"""Package a verified LSD executable into a new BIN/CUE with MKPSXISO."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

try:
    from .psx_image import EXECUTABLE_NAME, ORIGINAL_SHA1, read_root_file
except ImportError:
    from psx_image import EXECUTABLE_NAME, ORIGINAL_SHA1, read_root_file


def find_tool(name, directory=None):
    if directory:
        for suffix in (".exe", ""):
            candidate = Path(directory).resolve() / (name + suffix)
            if candidate.is_file():
                return str(candidate)
        raise ValueError(f"{name} was not found in {directory}.")
    path = shutil.which(name)
    if not path:
        raise ValueError(f"Install MKPSXISO (mkpsxiso and dumpsxiso), or use --tool-dir.")
    return path


def package(disc, executable, output, tool_dir=None):
    disc, executable, output = (Path(path).resolve() for path in (disc, executable, output))
    if output.suffix.lower() != ".cue":
        raise ValueError("--output must name a new .cue file.")
    binary = output.with_suffix(".bin")
    report_path = output.with_suffix(".disc.json")
    if any(path.exists() for path in (output, binary, report_path)):
        raise ValueError("BIN, CUE, and disc report must be new files.")
    original, original_lba = read_root_file(disc)
    if hashlib.sha1(original).hexdigest() != ORIGINAL_SHA1:
        raise ValueError("Source disc does not contain the supported original executable.")
    replacement = executable.read_bytes()
    if len(replacement) != len(original) or replacement[:0x800] != original[:0x800]:
        raise ValueError("Replacement must preserve executable size and the PS-X EXE header.")
    if replacement != original:
        # Require a verified mod manifest rather than packaging an arbitrary binary.
        manifest = json.loads(executable.with_suffix(executable.suffix + ".json").read_text())
        if manifest.get("base_sha1") != ORIGINAL_SHA1 or manifest.get("output_sha1") != hashlib.sha1(replacement).hexdigest():
            raise ValueError("Replacement executable does not match its mod manifest.")
        restored = bytearray(replacement)
        for patch in manifest["patches"]:
            offset = patch["offset"]
            before, after = bytes.fromhex(patch["before"]), bytes.fromhex(patch["after"])
            if len(before) != len(after) or replacement[offset:offset + len(after)] != after:
                raise ValueError("Invalid patch range in the mod manifest.")
            restored[offset:offset + len(before)] = before
        if bytes(restored) != original:
            raise ValueError("Mod changes bytes outside its declared patches.")
    dumpsxiso, mkpsxiso = find_tool("dumpsxiso", tool_dir), find_tool("mkpsxiso", tool_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.TemporaryDirectory(prefix=".lsd-disc-", dir=output.parent)
    workspace = Path(temporary.name).resolve()
    assert workspace.parent == output.parent and workspace.name.startswith(".lsd-disc-")
    try:
        subprocess.run([dumpsxiso, "-q", "-l", "-x", "files", "-s", "disc.xml", str(disc)],
                       cwd=workspace, check=True)
        xml = ET.parse(workspace / "disc.xml")
        entries = [entry for entry in xml.iter("file") if entry.get("name") == EXECUTABLE_NAME]
        if len(entries) != 1:
            raise ValueError("Expected exactly one executable in the extracted disc layout.")
        entry = entries[0]
        extracted = (workspace / entry.attrib["source"]).resolve()
        if not extracted.is_relative_to(workspace) or extracted.read_bytes() != original:
            raise ValueError("Extracted executable differs from the independently verified source.")
        extracted.write_bytes(replacement)
        subprocess.run([mkpsxiso, "-q", "-o", "image.bin", "-c", "image.cue", "disc.xml"],
                       cwd=workspace, check=True)
        packed, packed_lba = read_root_file(workspace / "image.bin")
        if packed != replacement or packed_lba != original_lba:
            raise ValueError("Packed executable or its disc LBA failed read-back verification.")
        cue = (workspace / "image.cue").read_text().replace('"image.bin"', json.dumps(binary.name, ensure_ascii=False))
        if f'"{binary.name}"' not in cue:
            raise ValueError("Generated CUE does not reference its BIN file.")
        with (workspace / "image.bin").open("rb") as source, binary.open("xb") as destination:
            shutil.copyfileobj(source, destination, 1024 * 1024)
        with output.open("x", encoding="utf-8") as stream:
            stream.write(cue)
        final, final_lba = read_root_file(output)
        if final != replacement or final_lba != original_lba:
            raise ValueError("Final BIN/CUE failed read-back verification.")
        report = {"source_disc": str(disc), "executable": str(executable),
                  "executable_sha1": hashlib.sha1(final).hexdigest(), "executable_lba": final_lba,
                  "image_bytes": binary.stat().st_size, "disc_layout": "original LBA offsets requested",
                  "executable_verified": True, "gameplay_tested": False}
        with report_path.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
        return report
    finally:
        # This is the unique directory created above, inside the requested output directory.
        assert workspace.parent == output.parent and workspace.name.startswith(".lsd-disc-")
        temporary.cleanup()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--disc", required=True, type=Path, help="Local original BIN/CUE.")
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="Destination .cue; never overwrites.")
    parser.add_argument("--tool-dir", type=Path, help="Folder containing mkpsxiso and dumpsxiso.")
    args = parser.parse_args(argv)
    try:
        report = package(args.disc, args.exe, args.output, args.tool_dir)
        print(f"Created: {args.output}")
        print(f"Packed executable verified at LBA {report['executable_lba']}.")
        print("Gameplay has not been tested in an emulator.")
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"[!] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
