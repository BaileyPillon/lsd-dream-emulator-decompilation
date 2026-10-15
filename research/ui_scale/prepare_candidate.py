"""Prepare the unaccepted sprite-scale fragment in a private complete C unit."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
MARKER = b'INCLUDE_ASM("asm/nonmatchings/menu/ui_sprite", func_8004441C);'


def prepare(output):
    output = Path(output).resolve()
    lab = (ROOT / '.decomp-lab').resolve()
    if output == lab or not output.is_relative_to(lab) or output.exists():
        raise ValueError('Choose a fresh private directory inside .decomp-lab.')
    source = (ROOT / 'src/menu/ui_sprite.c').read_bytes()
    fragment = Path(__file__).with_name('scale_candidate.c').read_bytes()
    if source.count(MARKER) != 1:
        raise ValueError('Expected exactly one sprite-scale assembly inclusion.')
    candidate = source.replace(MARKER, fragment, 1)
    output.mkdir(parents=True, exist_ok=False)
    path = output / 'ui_sprite.c'
    path.write_bytes(candidate)
    evidence = {'canonical_source_sha256': hashlib.sha256(source).hexdigest(),
                'research_fragment_sha256': hashlib.sha256(fragment).hexdigest(),
                'candidate_source_sha256': hashlib.sha256(candidate).hexdigest(),
                'candidate_source': str(path), 'source_promoted': False}
    with (output / 'prepared.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(evidence, stream, indent=2)
        stream.write('\n')
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(prepare(args.output)))
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
