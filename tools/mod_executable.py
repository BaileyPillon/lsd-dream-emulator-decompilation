"""Create reversible, fixed-size LSD exploration mods from a verified executable."""

import argparse
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import struct
import sys

try:
    from .psx_image import ORIGINAL_SHA1, executable_offset
except ImportError:
    from psx_image import ORIGINAL_SHA1, executable_offset

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TIME_LIMITS_ADDRESS = 0x80087F14
TIME_LIMITS = (240, 180, 480, 420, 120, 600, 60, 300, 240, 300, 240, 180, 120, 480)
GET_TIME_LIMIT_ADDRESS = 0x8005BB14
GRAY_MAN_ADDRESS = 0x80064618


def create_mod(original, duration=None, endless=False, passive_gray_man=False):
    actual = hashlib.sha1(original).hexdigest()
    if actual != ORIGINAL_SHA1:
        raise ValueError(f"Base must match the original executable; SHA-1 is {actual}.")
    if duration is None and not endless and not passive_gray_man:
        raise ValueError("Select at least one mod option.")
    if duration is not None and endless:
        raise ValueError("Choose --duration or --endless, since an endless timer ignores duration.")
    patched = bytearray(original)
    changes = []

    def patch(name, address, replacement, description):
        offset = executable_offset(original, address, len(replacement))
        previous = original[offset:offset + len(replacement)]
        patched[offset:offset + len(replacement)] = replacement
        changes.append({"feature": name, "description": description,
                        "address": f"0x{address:08X}", "offset": offset,
                        "before": previous.hex(), "after": replacement.hex()})

    if duration is not None or endless:
        offset = executable_offset(original, TIME_LIMITS_ADDRESS, 28)
        if struct.unpack_from("<14h", original, offset) != TIME_LIMITS:
            raise ValueError("The stage-duration table does not match the documented values.")
    if duration is not None:
        try:
            multiplier = Decimal(str(duration))
        except InvalidOperation as error:
            raise ValueError("Duration must be a positive finite multiplier.") from error
        if not multiplier.is_finite() or multiplier <= 0:
            raise ValueError("Duration must be a positive finite multiplier.")
        # Bound before Decimal multiplication so even enormous inputs fail cleanly.
        if multiplier > Decimal(32767) / max(TIME_LIMITS):
            raise ValueError("Duration exceeds the signed 16-bit stage timer limit.")
        values = tuple(int((Decimal(value) * multiplier).to_integral_value(rounding=ROUND_HALF_UP))
                       for value in TIME_LIMITS)
        if any(value < 1 or value > 32767 for value in values):
            raise ValueError("Every stage duration must round to 1..32767 seconds.")
        patch("duration", TIME_LIMITS_ADDRESS, struct.pack("<14h", *values),
              f"Stage timer seconds multiplied by {multiplier}; flashbacks and event exits are unchanged.")
        changes[-1]["seconds_before"] = list(TIME_LIMITS)
        changes[-1]["seconds_after"] = list(values)
    if endless:
        # Initial spawn generation reads the table directly, bypassing the getter.
        # Both consumers must receive -1; the existing setter preserves negatives.
        values = (-1,) * len(TIME_LIMITS)
        patch("endless", TIME_LIMITS_ADDRESS, struct.pack("<14h", *values),
              "Disable normal stage timeouts from initial spawn and later timer queries; flashbacks, falls, and other day-ending events still apply.")
        changes[-1]["seconds_before"] = list(TIME_LIMITS)
        changes[-1]["seconds_after"] = list(values)
    if passive_gray_man:
        patch("passive_gray_man", GRAY_MAN_ADDRESS, struct.pack("<2I", 0x03E00008, 0),
              "Return from the Gray Man behaviour callback; stop its movement and flashback reset. Model remains present.")
    result = bytes(patched)
    manifest = {"base_sha1": actual, "output_sha1": hashlib.sha1(result).hexdigest(),
                "output_sha256": hashlib.sha256(result).hexdigest(), "size": len(result),
                "patches": changes, "gameplay_tested": False}
    return result, manifest


def write_mod(base, output, **options):
    base, output = Path(base).resolve(), Path(output).resolve()
    manifest_path = output.with_suffix(output.suffix + ".json")
    if output == base or output.exists() or manifest_path.exists():
        raise ValueError(f"Output and manifest must be new files: {output}")
    executable, manifest = create_mod(base.read_bytes(), **options)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(executable)
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    if output.read_bytes() != executable:
        raise ValueError("Written mod failed its read-back verification.")
    return manifest_path, manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=PROJECT_ROOT / "build/SLPS015.56")
    parser.add_argument("--output", required=True, type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--duration", help="Multiply normal stage durations, e.g. 2 or 0.5.")
    modes.add_argument("--endless", action="store_true", help="Disable normal stage timeouts.")
    parser.add_argument("--passive-gray-man", action="store_true")
    args = parser.parse_args(argv)
    try:
        path, manifest = write_mod(args.base, args.output, duration=args.duration,
                                   endless=args.endless, passive_gray_man=args.passive_gray_man)
        print(f"Created: {args.output}")
        print(f"SHA-1: {manifest['output_sha1']}")
        print(f"Patch manifest: {path}")
        print("Binary patches verified; gameplay has not been tested in an emulator.")
        return 0
    except (OSError, ValueError) as error:
        print(f"[!] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
