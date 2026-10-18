"""Build isolated C attempts against the original executable, without changing Ninja outputs."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import configure
from tools.compile_c import run_stages
from tools.progress import build_manifest

INCLUDES = re.compile(r'\bINCLUDE_ASM\s*\(\s*"([^"\n]+)"\s*,\s*(\w+)\s*\)')
COMMENTS = re.compile(r'/\*.*?\*/|//[^\n]*', re.S)
INSTRUCTION = re.compile(r'/\*\s*([0-9A-Fa-f]+)\s+([0-9A-Fa-f]{8})\s+([0-9A-Fa-f]{8})\s*\*/')


def assembly_evidence(asm_text, function, original):
    body = re.search(r'\bglabel\s+' + re.escape(function) +
                     r'\s*\n(.*?)\bendlabel\s+' + re.escape(function) + r'\b', asm_text, re.S)
    if not body:
        raise ValueError(f"No explicit function boundaries: {function}")
    instructions = INSTRUCTION.findall(body.group(1))
    if not instructions:
        raise ValueError(f"No original instructions: {function}")
    offset = int(instructions[0][0], 16)
    address = int(instructions[0][1], 16)
    data = b"".join(bytes.fromhex(row[2]) for row in instructions)
    for i, row in enumerate(instructions):
        if int(row[0], 16) != offset + 4 * i or int(row[1], 16) != address + 4 * i:
            raise ValueError(f"Non-contiguous original instructions: {function}")
    if original[offset:offset + len(data)] != data:
        raise ValueError(f"Assembly instructions disagree with the original: {function}")
    return {"address": f"0x{address:08X}", "file_offset": offset,
            "bytes": len(data), "instructions": len(instructions),
            "sha256": hashlib.sha256(data).hexdigest()}


def catalog():
    original = (ROOT / configure.ROM).read_bytes()
    expected = (ROOT / configure.EXE_HASH).read_text().split()[0]
    if hashlib.sha1(original).hexdigest() != expected:
        raise ValueError("The original executable does not have the expected hash.")
    result = []
    for source, kind in build_manifest():
        if kind != "C":
            continue
        text = (ROOT / source).read_text(encoding="utf-8")
        for folder, function in INCLUDES.findall(COMMENTS.sub("", text)):
            assembly = ROOT / folder / (function + ".s")
            asm_text = assembly.read_text(encoding="utf-8")
            result.append({"function": function, "source": source,
                           "assembly": assembly.relative_to(ROOT).as_posix(),
                           **assembly_evidence(asm_text, function, original)})
    return sorted(result, key=lambda item: (item["bytes"], item["source"], item["function"]))


def compare_bytes(expected, actual):
    offsets = [i for i, (a, b) in enumerate(zip(expected, actual)) if a != b]
    return {"exact_match": expected == actual, "expected_bytes": len(expected),
            "actual_bytes": len(actual), "changed_bytes_in_common_range": len(offsets),
            "length_difference": len(actual) - len(expected),
            "first_changed_offsets": offsets[:16],
            "expected_sha1": hashlib.sha1(expected).hexdigest(),
            "actual_sha1": hashlib.sha1(actual).hexdigest()}


def context_bundle(function, output):
    """Prepare byte-grounded context for an AI or human matching attempt."""
    entries = catalog()
    matches = [item for item in entries if item["function"] == function]
    if not matches:
        baseline = ROOT / ".decomp-lab/remaining-game-functions.json"
        if baseline.is_file():
            matches = [item for item in json.loads(baseline.read_text())
                       if item["function"] == function]
    if len(matches) != 1:
        raise ValueError("Select a function from the current or saved baseline catalog.")
    entry = dict(matches[0])
    if not any(item["function"] == function for item in entries):
        definition = re.compile(r'\b' + re.escape(function) + r'\s*\([^;{}]*\)\s*\{', re.S)
        sources = [source for source, kind in build_manifest() if kind == "C"
                   and definition.search(COMMENTS.sub("", (ROOT / source).read_text()))]
        if len(sources) != 1:
            raise ValueError("The recovered function must have exactly one configured definition.")
        entry["original_source"] = entry["source"]
        entry["source"] = sources[0]
    assembly = ROOT / entry["assembly"]
    original = (ROOT / configure.ROM).read_bytes()
    data = original[entry["file_offset"]:entry["file_offset"] + entry["bytes"]]
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ValueError("Saved catalog disagrees with the original function bytes.")
    if assembly_evidence(assembly.read_text(), function, original)["sha256"] != entry["sha256"]:
        raise ValueError("Saved assembly disagrees with the catalog's original function bytes.")
    output = new_output_directory(output)
    evidence = []

    def save(source, target, interpretation):
        contents = source.read_bytes()
        (output / target).parent.mkdir(parents=True, exist_ok=True)
        (output / target).write_bytes(contents)
        evidence.append({"source": source.relative_to(ROOT).as_posix(),
                         "bundle_file": target, "sha256": hashlib.sha256(contents).hexdigest(),
                         "interpretation": interpretation})

    save(ROOT / entry["source"], "candidate.c", "Current complete translation unit; may contain legacy incorrect types.")
    save(assembly, "original.s", "Original disassembly; its function byte range was verified against the canonical executable.")
    pending = [ROOT / entry["source"]]
    visited = set()
    unresolved = set()
    while pending:
        source = pending.pop()
        if source in visited:
            continue
        visited.add(source)
        for header in re.findall(r'^\s*#\s*include\s*[<"]([^>"\n]+)[>"]', source.read_text(), re.M):
            choices = [source.parent / header, ROOT / "include" / header,
                       ROOT / "src" / header, ROOT / "include/asm" / header]
            resolved = next((p.resolve() for p in choices if p.is_file()
                             and p.resolve().is_relative_to(ROOT)), None)
            if resolved is None:
                unresolved.add(header)
                continue
            if resolved not in visited and resolved not in pending:
                save(resolved, "headers/" + resolved.relative_to(ROOT).as_posix(),
                     "Recovered declarations; validate ABI and field types against original instructions.")
                pending.append(resolved)
    pseudocode = ROOT / ".decomp-lab/ghidra/pseudocode" / (entry["address"][2:].lower() + "_" + function + ".c")
    if pseudocode.is_file():
        save(pseudocode, "ghidra.c", "Ghidra analysis, not original source or matching proof; indirect-call arguments may be missing.")
    inventory_path = ROOT / "docs/features.json"
    features = json.loads(inventory_path.read_text())["features"] if inventory_path.is_file() else []
    feature_ids = [item["id"] for item in features
                   if any(anchor["function"] == function for anchor in item["required_functions"])]
    report = {"function": entry, "canonical_sha1": hashlib.sha1(original).hexdigest(),
              "source_compiler_mode": "G8" if configure.c_source_uses_g8(entry["source"]) else "G0",
              "feature_ids": feature_ids, "evidence": evidence,
              "unresolved_includes": sorted(unresolved), "ai_model_invoked": False,
              "matching_proof": False, "gameplay_tested": False}
    (output / "context.json").write_text(json.dumps(report, indent=2) + "\n")
    prompt = f"""Recover `{function}` in maintainable C using this evidence bundle.

The canonical executable SHA-1 is {report['canonical_sha1']}.
Read context.json, original.s, candidate.c and headers. Treat ghidra.c as
fallible analysis. Check actual callee signatures, signed widths, field offsets,
virtual-call argument forwarding, and the configured {report['source_compiler_mode']} compiler mode.
Do not add padding, inline assembly, hardcoded instruction bytes, or alter the
original behavior to obtain a match. Preserve other functions and data ownership.

Make the attempt in candidate.c. In the repository's Linux/WSL build environment:

    python tools/decomp_workbench.py check --source {entry['source']} --candidate '{(output / 'candidate.c').relative_to(ROOT).as_posix()}' --output .decomp-lab/NEW-ATTEMPT

Choose a new output directory for every attempt. Promote only a whole executable
byte match, then refresh the standard build. A compiler match does not establish
exhaustive feature understanding or runtime acceptance. Feature anchors: {', '.join(feature_ids) or 'none recorded'}.
"""
    (output / "PROMPT.md").write_text(prompt, encoding="utf-8")
    return report


def candidate_commands(source, candidate, obj):
    g8 = configure.c_source_uses_g8(source)
    flags = ["-I" + str((ROOT / source).parent), *configure.CPP_FLAGS]
    if g8:
        flags.append("-DCCG8")
    return [[configure.CROSS + "cpp", *flags, str(candidate)],
            [configure.CC, *(configure.C_FLAGS_G8 if g8 else configure.C_FLAGS)],
            [sys.executable, configure.MASPSX, *configure.MASPSX_FLAGS],
            [configure.CROSS + "as", "-EL", *configure.AS_FLAGS, "-o", str(obj)]]


def new_output_directory(output):
    output = Path(output).resolve()
    lab = (ROOT / ".decomp-lab").resolve()
    if not output.is_relative_to(lab) or output == lab:
        raise ValueError("Output must be a new directory inside .decomp-lab.")
    output.mkdir(parents=True, exist_ok=False)
    return output


def candidate_link_command(elf, map_path, ldscript, objects, flags):
    # Keep the object spellings used by the linker script. Absolute versions of
    # its relative object paths can make ld include the same input twice.
    return [configure.CROSS + "ld", "-EL", "-o", str(elf),
            "-Map", str(map_path), "-T", str(ldscript),
            "-T", configure.UNDEF_SYMS, "-T", configure.UNDEF_FUNCS,
            *flags, *map(str, objects)]


def diagnostic_image(output, ldscript, objects, binary, log=None):
    """Retain link symbols and require the complete allocated image to agree."""
    stripped = [flag for flag in configure.LD_FLAGS if flag in ("-s", "--strip-all")]
    if len(stripped) != 1:
        raise ValueError("Function diagnostics require exactly one symbol-strip flag.")
    flags = [flag for flag in configure.LD_FLAGS if flag not in stripped]
    elf = output / "candidate-symbols.elf"
    diagnostic_binary = output / "candidate-symbols.exe"
    if any(path.exists() for path in (elf, output / "candidate-symbols.map", diagnostic_binary)):
        raise ValueError("Existing symbol diagnostics must be preserved; choose a new output.")
    subprocess.run(candidate_link_command(
        elf, output / "candidate-symbols.map", ldscript, objects, flags), check=True,
        stdout=log, stderr=log)
    subprocess.run([configure.CROSS + "objcopy", "-O", "binary",
                    str(elf), str(diagnostic_binary)], check=True, stdout=log, stderr=log)
    expected, actual = binary.read_bytes(), diagnostic_binary.read_bytes()
    if expected != actual:
        raise ValueError("Retaining function symbols changed the complete candidate image.")
    return elf, {"diagnostic_image_matches_candidate": True,
                   "candidate_executable_sha256": hashlib.sha256(expected).hexdigest(),
                   "diagnostic_executable_sha256": hashlib.sha256(actual).hexdigest(),
                   "original_link_flags": list(configure.LD_FLAGS),
                   "diagnostic_link_flags": flags,
                   "removed_symbol_strip_flag": stripped[0]}


def diagnostic_function(entry, original, output, ldscript, objects, binary):
    """Retain real function symbols without accepting a changed allocated image."""
    from research.compiler.compare_function import compare

    start = entry["file_offset"]
    reference = original[start:start + entry["bytes"]]
    if hashlib.sha256(reference).hexdigest() != entry["sha256"]:
        raise ValueError("Original function evidence changed before comparison.")
    elf, image = diagnostic_image(output, ldscript, objects, binary)
    result = compare(elf.read_bytes(), reference, entry["function"], int(entry["address"], 16))
    result.update(image)
    return result


def check_candidate(source, candidate, output, function=None):
    if sys.platform == "win32":
        raise ValueError("Run candidate builds in Linux/WSL with the matching compiler environment.")
    import os
    os.chdir(ROOT)
    source = Path(source).as_posix()
    allowed = {p for p, kind in build_manifest() if kind == "C"}
    if source not in allowed:
        raise ValueError("Select one of the configured game C source files.")
    entry = None
    if function is not None:
        entries = [item for item in catalog()
                   if item["function"] == function and item["source"] == source]
        if len(entries) != 1:
            raise ValueError("Select a current assembly function in the candidate's source file.")
        entry = entries[0]
    candidate = Path(candidate).resolve(strict=True)
    output = new_output_directory(output)
    obj = output / "candidate.o"
    run_stages(candidate_commands(source, candidate, obj))
    old_obj = (Path(configure.BUILD_DIR) / (source + ".o")).as_posix()
    script = (ROOT / configure.LD_SCRIPT).read_text(encoding="utf-8")
    if old_obj not in script:
        raise ValueError("Selected object has no placement in the original linker script.")
    script = script.replace(old_obj, '"' + obj.as_posix() + '"')
    ldscript = output / "candidate.ld"
    ldscript.write_text(script, encoding="utf-8")
    objects = [obj if name == source else Path(configure.BUILD_DIR) / (name + ".o")
               for name, _kind in build_manifest()]
    if any(not p.is_file() for p in objects):
        raise ValueError("A complete baseline build is required before candidate comparison.")
    elf = output / "candidate.elf"
    subprocess.run(candidate_link_command(
        elf, output / "candidate.map", ldscript, objects, configure.LD_FLAGS), check=True)
    binary = output / "candidate.exe"
    subprocess.run([configure.CROSS + "objcopy", "-O", "binary", str(elf), str(binary)], check=True)
    original = (ROOT / configure.ROM).read_bytes()
    report = compare_bytes(original, binary.read_bytes())
    report.update({"source": source, "candidate": str(candidate),
                   "candidate_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                   "output": str(output), "gameplay_tested": False})
    if entry is not None:
        report["function_diagnostics"] = diagnostic_function(
            entry, original, output, ldscript, objects, binary)
    (output / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("catalog", help="List active game assembly routines with original byte evidence.")
    check = commands.add_parser("check", help="Compile a full candidate translation unit into a private build.")
    check.add_argument("--source", required=True)
    check.add_argument("--candidate", required=True)
    check.add_argument("--output", required=True)
    check.add_argument("--function", help="Also qualify and compare one current assembly function; the whole-image gate is unchanged.")
    context = commands.add_parser("context", help="Prepare original bytes, source, headers and AI matching instructions.")
    context.add_argument("--function", required=True)
    context.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "catalog":
            result = catalog()
        elif args.command == "context":
            result = context_bundle(args.function, args.output)
        else:
            result = check_candidate(args.source, args.candidate, args.output, args.function)
        printed = result
        if args.command == "check" and args.function:
            # Detailed instruction words and the full ELF symbol inventory stay
            # in the private report instead of flooding a terminal or AI context.
            printed = dict(result)
            diagnostic = result.get("function_diagnostics", {})
            summary = ("function", "address", "original_bytes", "candidate_bytes",
                       "length_difference", "differing_bytes", "selected_function_bytes_equal",
                       "diagnostic_image_matches_candidate", "source_promoted",
                       "complete_executable_verified")
            printed["function_diagnostics"] = {key: diagnostic[key] for key in summary if key in diagnostic}
            printed["full_report"] = str(Path(args.output) / "comparison.json")
        print(json.dumps(printed, indent=2))
        return 0 if args.command != "check" or result["exact_match"] else 1
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"[!] {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
