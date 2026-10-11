"""Measure game C coverage from the current build, without optional packages."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
import configure

TEXT_SIZE_RE = re.compile(r"^\s*\d+\s+\.text\s+([0-9a-fA-F]+)\s", re.MULTILINE)
COMMENTS_RE = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)
INCLUDE_ASM_RE = re.compile(r'\bINCLUDE_ASM\s*\(\s*"[^"\n]+"\s*,\s*(\w+)\s*\)')


def fallback_functions(source):
    """Use current source, so stale generated assembly cannot hide progress."""
    return set(INCLUDE_ASM_RE.findall(COMMENTS_RE.sub("", source)))


def parse_text_size(output):
    found = TEXT_SIZE_RE.search(output)
    return int(found.group(1), 16) if found else 0


def parse_c_coverage(output, fallbacks):
    """Count function ranges from GNU objdump -h -t, excluding ASM fallbacks."""
    total = parse_text_size(output)
    functions = {}
    for line in output.splitlines():
        fields = line.split()
        if ".text" not in fields:
            continue
        section = fields.index(".text")
        if "F" not in fields[1:section] or len(fields) < section + 3:
            continue
        address = int(fields[0], 16)
        size = int(fields[section + 1], 16)
        name = fields[section + 2]
        if address >= total:
            if size:
                raise ValueError(f"Function {name} lies outside .text.")
            continue
        functions.setdefault(address, []).append((name, size))
    if total and not functions:
        raise ValueError("No function symbols in a nonempty game C object.")
    decompiled = 0
    addresses = sorted(functions)
    for index, address in enumerate(addresses):
        boundary = addresses[index + 1] if index + 1 < len(addresses) else total
        entries = functions[address]
        size = max(size for _, size in entries) or boundary - address
        if size > boundary - address:
            raise ValueError("Overlapping function ranges in .text.")
        if any(name in fallbacks or name.startswith("__maspsx_include_asm_hack_")
               for name, _ in entries):
            continue
        decompiled += size
    return decompiled, total


def build_manifest():
    """Classify only objects that belong to the current build configuration."""
    manifest = []
    for source in configure.asm_auto_targets + configure.asm_targets:
        if source.startswith("src/psyq/") or source in configure.asm_psyq_targets:
            kind = "sdk"
        elif source in configure.hasm_targets:
            kind = "handwritten"
        elif source in configure.asm_data_targets + configure.asm_header_targets:
            kind = "data"
        else:
            kind = "asm"
        manifest.append((source, kind))
    for source in configure.c_psyq_targets + configure.c_game_targets + configure.cpp_targets:
        manifest.append((source, "sdk" if source.startswith("src/psyq/") else "C"))
    return manifest


def find_objdump(requested=None):
    candidates = [requested] if requested else [
        configure.CROSS + "objdump", "mips-linux-gnu-objdump", "mipsel-none-elf-objdump"
    ]
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found
    raise ValueError("MIPS objdump is missing. Install binutils-mipsel-linux-gnu "
                     "in Linux/WSL, or supply --objdump PATH.")


def check_build_current(root):
    if not (Path(root) / "build.ninja").is_file():
        return None
    # Use the Python environment's Ninja before a potentially older system
    # version. Older Ninja can reset a newer build log even during a dry run.
    ninja = shutil.which("ninja", path=str(Path(sys.executable).parent)) or shutil.which("ninja")
    if not ninja:
        return None
    result = subprocess.run([ninja, "-n", "all"], cwd=root, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise ValueError("Ninja could not inspect the build graph. Run configure.py and ninja check.")
    return result.stdout.strip() == "ninja: no work to do."


def collect_progress(root=PROJECT_ROOT, manifest=None, objdump=None, allow_partial=False):
    root = Path(root)
    manifest = build_manifest() if manifest is None else manifest
    objects = [(source, kind, root / configure.BUILD_DIR / (source + ".o"))
               for source, kind in manifest]
    found = [entry for entry in objects if entry[2].is_file()]
    missing = [source for source, _, path in objects if not path.is_file()]
    if not found:
        raise ValueError("No build objects found. Run ninja check in Linux/WSL first.")
    if missing and not allow_partial:
        raise ValueError(f"Incomplete build: {len(found)}/{len(objects)} objects present. "
                         "Run ninja check, or use --allow-partial for an explicit snapshot.")
    current = check_build_current(root)
    if current is not True and not allow_partial:
        raise ValueError("Build is out of date or freshness cannot be checked. Run configure.py "
                         "and ninja check, or use --allow-partial for an explicit snapshot.")
    objdump = find_objdump(objdump)
    totals = {kind: 0 for kind in ("C", "asm", "sdk", "handwritten", "data")}
    decompiled = 0
    stats = []
    for source, kind, path in found:
        output = subprocess.check_output([objdump, "-h", "-t", str(path)],
                                         text=True, stderr=subprocess.STDOUT)
        total = parse_text_size(output)
        covered = 0
        if kind == "C":
            content = (root / source).read_text(encoding="utf-8")
            covered, total = parse_c_coverage(output, fallback_functions(content))
            decompiled += covered
        totals[kind] += total
        if kind in ("C", "asm"):
            stats.append({"source": source, "kind": kind, "c_bytes": covered,
                          "text_bytes": total,
                          "source_sha256": hashlib.sha256((root / source).read_bytes()).hexdigest()})
    game_size = totals["C"] + totals["asm"]
    expected = (root / configure.EXE_HASH).read_text(encoding="utf-8").split()[0]
    executable = root / configure.EXE
    actual = hashlib.sha1(executable.read_bytes()).hexdigest() if executable.is_file() else None
    inputs = {root / source for source, _kind in manifest}
    inputs.update(root / name for name in ("configure.py", configure.SPLAT_CONFIG, configure.SYMBOLS))
    for folder in (root / "src", root / "include"):
        if folder.is_dir():
            inputs.update(folder.rglob("*.h"))
            inputs.update(folder.rglob("*.inc"))
    input_hashes = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted(inputs) if path.is_file()}
    current = check_build_current(root)
    if current is not True and not allow_partial:
        raise ValueError("Build changed during progress collection. Refresh and retry the snapshot.")
    return {
        "objects_expected": len(objects), "objects_found": len(found),
        "complete_objects": not missing, "missing_objects": missing,
        "build_current": current,
        "c_bytes": decompiled, "game_text_bytes": game_size,
        "c_coverage_percent": 100 * decompiled / game_size if game_size else None,
        "sdk_text_bytes": totals["sdk"], "handwritten_text_bytes": totals["handwritten"],
        "binary_match": "missing" if actual is None else ("verified" if actual == expected else "mismatch"),
        "expected_sha1": expected, "actual_sha1": actual,
        "build_input_sha256": input_hashes,
        "files": sorted(stats, key=lambda item: item["source"]),
    }


def print_report(report):
    print("Game C coverage (compiled function bytes)")
    print(f"Build objects: {report['objects_found']}/{report['objects_expected']}")
    print("Build freshness: " + {True: "current", False: "out of date", None: "unavailable"}[report["build_current"]])
    if not report["complete_objects"] or report["build_current"] is not True:
        print("PARTIAL SNAPSHOT: objects may be missing or stale; coverage is not a current-build result.")
    percent = report["c_coverage_percent"]
    if percent is None:
        print("No game .text bytes to measure.")
    else:
        print(f"C: {report['c_bytes']:,}/{report['game_text_bytes']:,} bytes ({percent:.2f}%)")
    print(f"Excluded SDK: {report['sdk_text_bytes']:,} bytes; "
          f"handwritten startup: {report['handwritten_text_bytes']:,} bytes")
    print(f"Original executable match: {report['binary_match']}")
    if report["binary_match"] == "mismatch":
        print(f"Observed SHA-1: {report['actual_sha1']}")
    print("Coverage does not establish semantic understanding or independent validation.")
    print()
    for item in report["files"]:
        size = item["text_bytes"]
        percent = 100 * item["c_bytes"] / size if size else 0
        print(f"{item['source']:48} {item['c_bytes']:7}/{size:<7} {percent:6.2f}%")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable coverage.")
    parser.add_argument("--objdump", help="Path to a GNU objdump supporting MIPS objects.")
    parser.add_argument("--allow-partial", action="store_true", help="Report an incomplete or stale object snapshot.")
    args = parser.parse_args(argv)
    try:
        report = collect_progress(objdump=args.objdump, allow_partial=args.allow_partial)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_report(report)
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"[!] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
