"""Prepare the unaccepted grid fragment in a fresh, complete private source unit."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'src/scene/render_context.c'
FRAGMENT = Path(__file__).with_name('c6a8_candidate.c')
FRAGMENTS = {'edge': FRAGMENT,
             'cell-reuse': Path(__file__).with_name('c6a8_cell_reuse_candidate.c')}
MARKER = 'INCLUDE_ASM("asm/nonmatchings/scene/render_context", func_8004C6A8);'


def prepare(output, variant='edge'):
    output = Path(output).resolve()
    lab = (ROOT / '.decomp-lab').resolve()
    if output == lab or not output.is_relative_to(lab):
        raise ValueError('Choose a fresh directory inside .decomp-lab.')
    if output.exists():
        raise FileExistsError('Existing evidence cannot be overwritten: ' + str(output))
    if variant not in FRAGMENTS:
        raise ValueError('Choose a supported grid candidate variant.')
    fragment_path = FRAGMENTS[variant]
    original = SOURCE.read_bytes()
    fragment = fragment_path.read_bytes()
    text = original.decode('utf-8')
    if text.count(MARKER) != 1:
        raise ValueError('Expected exactly one remaining func_8004C6A8 assembly inclusion.')
    candidate = text.replace(MARKER, fragment.decode('utf-8')).encode('utf-8')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'render_context.c').write_bytes(candidate)
    record = {'canonical_source': SOURCE.relative_to(ROOT).as_posix(),
              'canonical_source_sha256': hashlib.sha256(original).hexdigest(),
              'variant': variant,
              'fragment': fragment_path.relative_to(ROOT).as_posix(),
              'fragment_sha256': hashlib.sha256(fragment).hexdigest(),
              'candidate': str(output / 'render_context.c'),
              'candidate_sha256': hashlib.sha256(candidate).hexdigest(),
              'only_selected_inclusion_replaced': True, 'source_promoted': False}
    (output / 'preparation.json').write_bytes((json.dumps(record, indent=2) + '\n').encode('utf-8'))
    if SOURCE.read_bytes() != original or fragment_path.read_bytes() != fragment:
        raise ValueError('A source input changed during candidate preparation.')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--variant', choices=tuple(FRAGMENTS), default='edge',
                        help='Research source form; neither variant is accepted C.')
    args = parser.parse_args()
    try:
        record = prepare(args.output, args.variant)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(record))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
