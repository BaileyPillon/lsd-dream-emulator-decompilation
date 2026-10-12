"""Prepare the unaccepted overlap fragment in a private complete source unit."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKER = 'INCLUDE_ASM("asm/nonmatchings/base/transform", func_8001DDF4);'
TYPE_START = 'typedef struct func_8001E2E8_pt {'
FUNCTION_START = '\ns32 func_8001E110('


def compose(source, fragment):
    if source.count(MARKER) != 1 or source.count(TYPE_START) != 1:
        raise ValueError('Expected one overlap inclusion and one existing point declaration block.')
    begin = source.index(TYPE_START)
    end = source.index(FUNCTION_START, begin)
    block = source[begin:end]
    if 'func_8001E2E8_box_t;' not in block or 'void func_8001E2E8(' not in block:
        raise ValueError('Existing overlap point/bounds declarations are incomplete.')
    # Move only declarations so the same established types are available at the
    # former assembly inclusion and remain available to their original functions.
    without = source[:begin] + source[end:]
    return without.replace(MARKER, block + '\n' + fragment)


def prepare(output):
    output = Path(output).resolve()
    if not output.is_relative_to((ROOT / '.decomp-lab').resolve()) or output.exists():
        raise ValueError('Choose a fresh private directory inside .decomp-lab.')
    source = ROOT / 'src/base/transform.c'
    fragment = Path(__file__).with_name('overlap_candidate.c')
    source_bytes, fragment_bytes = source.read_bytes(), fragment.read_bytes()
    candidate = compose(source_bytes.decode(), fragment_bytes.decode())
    output.mkdir(parents=True, exist_ok=False)
    path = output / 'transform.c'
    path.write_bytes(candidate.encode())
    evidence = {'canonical_source_sha256': hashlib.sha256(source_bytes).hexdigest(),
                'research_fragment_sha256': hashlib.sha256(fragment_bytes).hexdigest(),
                'candidate_source_sha256': hashlib.sha256(candidate.encode()).hexdigest(),
                'candidate_source': str(path), 'source_promoted': False}
    (output / 'prepared.json').write_bytes((json.dumps(evidence, indent=2) + '\n').encode())
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    print(json.dumps(prepare(args.output)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
