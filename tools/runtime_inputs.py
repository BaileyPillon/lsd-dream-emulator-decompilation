"""Pin and verify the local inputs of a repeatable BizHawk PS1 QA run."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys


EMULATOR_FILES = ("EmuHawk.exe", "EmuHawk.exe.config",
                  "dll/BizHawk.Emulation.Cores.dll",
                  "dll/BizHawk.Emulation.Common.dll", "dll/octoshock.dll")
BIOS_FILES = {"J": "scph5500.bin", "U": "scph5501.BIN", "E": "scph5502.BIN"}


def record_file(path):
    path = Path(path).resolve(strict=True)
    before = path.stat()
    if not path.is_file():
        raise ValueError(f"QA input is not a regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
            after.st_size, after.st_mtime_ns, after.st_ino):
        raise ValueError(f"QA input changed while hashing: {path}")
    return {"path": str(path), "bytes": after.st_size, "sha256": digest.hexdigest()}


def disc_inputs(cue):
    """Keep all CUE directives; normalize only filenames and whitespace."""
    cue = Path(cue).resolve(strict=True)
    if cue.suffix.lower() != ".cue":
        raise ValueError("QA provenance requires a CUE with explicit track layout.")
    cue_record = record_file(cue)
    layout, tracks = [], []
    for line in cue.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"FILE\b", line, re.I):
            match = re.fullmatch(r'FILE\s+"([^"]+)"\s+BINARY', line, re.I)
            if not match:
                raise ValueError("Expected quoted BINARY files in the QA CUE.")
            path = Path(match[1])
            tracks.append(record_file(path if path.is_absolute() else cue.parent / path))
            layout.append(f"FILE <track-{len(tracks)}> BINARY")
        else:
            layout.append(re.sub(r"\s+", " ", line).upper())
    if not tracks or not any(line.startswith("TRACK ") for line in layout):
        raise ValueError("QA CUE has no explicit file/track layout.")
    if record_file(cue) != cue_record:
        raise ValueError("QA CUE changed while its track inputs were inspected.")
    return {"cue": cue_record, "layout": layout, "tracks": tracks}


def pin_inputs(cue, bios_root, emulator_root, configuration, script,
               scenario, frames, load_state=None, capture_audio=False):
    if scenario not in ("boot", "play") or not 1 <= frames <= 30000:
        raise ValueError("Unsupported QA scenario or frame count.")
    emulator_root, bios_root = Path(emulator_root), Path(bios_root)
    return {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
            "scenario": scenario, "frames": frames,
            "disc": disc_inputs(cue),
            "emulator_files": {name: record_file(emulator_root / name) for name in EMULATOR_FILES},
            "bios": {region: record_file(bios_root / name) for region, name in BIOS_FILES.items()},
            "configuration": record_file(configuration), "script": record_file(script),
            "start_state": record_file(load_state) if load_state else None,
            "start_kind": "saved_state" if load_state else "cold_boot",
            "audio_output_captured": False,
            "audio_output_requested": bool(capture_audio),
            "audio_writer": "wave" if capture_audio else None,
            "scope": "Local launch inputs pinned before execution. Original/rebuilt parity requires identical track contents, layout, BIOS, emulator, script, configuration and starting state."}


def manifest_records(manifest):
    return [manifest["disc"]["cue"], *manifest["disc"]["tracks"],
            *manifest["emulator_files"].values(), *manifest["bios"].values(),
            manifest["configuration"], manifest["script"],
            *([manifest["start_state"]] if manifest["start_state"] else [])]


def load_verified_manifest(folder):
    path = Path(folder) / "inputs.json"
    if not path.exists():
        return None
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported runtime input manifest schema.")
    if set(manifest["emulator_files"]) != set(EMULATOR_FILES) or set(manifest["bios"]) != set(BIOS_FILES):
        raise ValueError("Runtime input manifest omits an emulator or BIOS identity.")
    if not manifest["disc"]["tracks"] or not manifest["disc"]["layout"]:
        raise ValueError("Runtime input manifest omits disc track identities or layout.")
    if manifest["start_kind"] != ("saved_state" if manifest["start_state"] else "cold_boot"):
        raise ValueError("Runtime starting-state identity is inconsistent.")
    if disc_inputs(manifest["disc"]["cue"]["path"]) != manifest["disc"]:
        raise ValueError("Pinned disc layout or track identities no longer agree with its CUE.")
    records = manifest_records(manifest)
    for expected in records[1 + len(manifest["disc"]["tracks"]):]:
        if record_file(expected["path"]) != expected:
            raise ValueError(f"A pinned runtime input changed: {expected['path']}")
    return manifest


def content_identity(record):
    return {"bytes": record["bytes"], "sha256": record["sha256"]} if record else None


def configuration_identity(record):
    # JSON object member order is not an emulator setting. The raw file remains
    # pinned and checked above; comparison uses the complete parsed contents.
    settings = json.loads(Path(record['path']).read_text(encoding='utf-8-sig'))
    if not isinstance(settings, dict):
        raise ValueError('Runtime configuration must be a JSON settings object.')
    normalized = json.dumps(settings, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
    return {'normalized_json_sha256': hashlib.sha256(normalized).hexdigest()}


def parity_identity(manifest):
    return {"scenario": manifest["scenario"], "frames": manifest["frames"],
            "disc_layout": manifest["disc"]["layout"],
            "disc_tracks": [content_identity(record) for record in manifest["disc"]["tracks"]],
            "emulator_files": {name: content_identity(record) for name, record in manifest["emulator_files"].items()},
            "bios": {region: content_identity(record) for region, record in manifest["bios"].items()},
            "configuration": configuration_identity(manifest["configuration"]),
            "script": content_identity(manifest["script"]),
            "start_kind": manifest["start_kind"], "start_state": content_identity(manifest["start_state"]),
            "audio_output_requested": manifest.get("audio_output_requested", False),
            "audio_writer": manifest.get("audio_writer")}


def compare_inputs(original, rebuilt, scenario, frames):
    manifests = [load_verified_manifest(folder) for folder in (original, rebuilt)]
    if all(manifest is None for manifest in manifests):
        return {"status": "legacy_inputs_not_pinned", "inputs_verified": False,
                "scope": "Recorded outputs can be compared; these earlier runs have no launch-input manifest."}
    if any(manifest is None for manifest in manifests):
        raise ValueError("Both runtime runs must include pinned launch inputs.")
    identities = [parity_identity(manifest) for manifest in manifests]
    if identities[0] != identities[1]:
        changed = [key for key in identities[0] if identities[0][key] != identities[1][key]]
        raise ValueError("Runtime launch inputs differ: " + ", ".join(changed))
    if identities[0]["scenario"] != scenario or identities[0]["frames"] != frames:
        raise ValueError("Pinned inputs disagree with the completed runtime scenario.")
    return {"status": "pinned_inputs_identical", "inputs_verified": True,
            "identity": identities[0],
            "manifests": [record_file(Path(folder) / "inputs.json") for folder in (original, rebuilt)]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cue", "bios-root", "emulator-root", "configuration", "script", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--scenario", choices=("boot", "play"), required=True)
    parser.add_argument("--frames", required=True, type=int)
    parser.add_argument("--load-state", type=Path)
    parser.add_argument("--capture-audio", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = pin_inputs(args.cue, args.bios_root, args.emulator_root, args.configuration,
                            args.script, args.scenario, args.frames, args.load_state, args.capture_audio)
        with args.output.open("x", encoding="utf-8") as out:
            json.dump(report, out, indent=2)
            out.write("\n")
        print("Pinned disc, BIOS, emulator, script, configuration and start-state identities.")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"[!] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
