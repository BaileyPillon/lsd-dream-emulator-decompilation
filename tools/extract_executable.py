"""Extract and verify LSD's original executable without modifying the disc."""

import argparse
import hashlib
from pathlib import Path
import sys

try:
    from .psx_image import ORIGINAL_SHA1, read_root_file
except ImportError:
    from psx_image import ORIGINAL_SHA1, read_root_file

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def extract(disc, output):
    executable, lba = read_root_file(disc)
    actual = hashlib.sha1(executable).hexdigest()
    if actual != ORIGINAL_SHA1:
        raise ValueError(f"Unexpected executable SHA-1: {actual}; expected {ORIGINAL_SHA1}.")
    output = Path(output)
    if output.exists():
        if output.read_bytes() == executable:
            return lba, False
        raise ValueError(f"Refusing to replace an existing file: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(executable)
    return lba, True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("disc", type=Path, help="Local BIN, CUE, or ISO.")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "rom/SLPS_015.56")
    args = parser.parse_args(argv)
    try:
        lba, created = extract(args.disc, args.output)
        print(f"{'Extracted' if created else 'Already verified'}: {args.output} (LBA {lba})")
        print(f"SHA-1: {ORIGINAL_SHA1}")
        return 0
    except (OSError, ValueError) as error:
        print(f"[!] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
