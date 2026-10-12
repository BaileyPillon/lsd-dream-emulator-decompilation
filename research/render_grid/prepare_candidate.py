"""Prepare the unaccepted grid fragment in a fresh, complete private source unit."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'src/scene/render_context.c'
FRAGMENT = Path(__file__).with_name('c6a8_candidate.c')
MARKER = 'INCLUDE_ASM("asm/nonmatchings/scene/render_context", func_8004C6A8);'


def prepare(output):
    output = Path(output).resolve()
    lab = (ROOT / '.decomp-lab').resolve()
    if output == lab or not output.is_relative_to(lab):
        raise ValueError('Choose a fresh directory inside .decomp-lab.')
    if output.exists():
        raise FileExistsError('Existing evidence cannot be overwritten: ' + str(output))
    original = SOURCE.read_bytes()
    fragment = FRAGMENT.read_bytes()
    text = original.decode('utf-8')
    if text.count(MARKER) != 1:
        raise ValueError('Expected exactly one remaining func_8004C6A8 assembly inclusion.')
    candidate = text.replace(MARKER, fragment.decode('utf-8')).encode('utf-8')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'render_context.c').write_bytes(candidate)
    record = {'canonical_source': SOURCE.relative_to(ROOT).as_posix(),
              'canonical_source_sha256': hashlib.sha256(original).hexdigest(),
              'fragment': FRAGMENT.relative_to(ROOT).as_posix(),
              'fragment_sha256': hashlib.sha256(fragment).hexdigest(),
              'candidate': str(output / 'render_context.c'),
              'candidate_sha256': hashlib.sha256(candidate).hexdigest(),
              'only_selected_inclusion_replaced': True, 'source_promoted': False}
    (output / 'preparation.json').write_bytes((json.dumps(record, indent=2) + '\n').encode('utf-8'))
    if SOURCE.read_bytes() != original or FRAGMENT.read_bytes() != fragment:
        raise ValueError('A source input changed during candidate preparation.')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        record = prepare(args.output)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(record))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
