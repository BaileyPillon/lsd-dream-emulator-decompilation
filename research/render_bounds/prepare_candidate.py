"""Prepare the unaccepted bounds fragment in a private complete source unit."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path('src/scene/render_context.c')
FRAGMENT = Path('research/render_bounds/bounds_candidate.c')
PROTOTYPE = 's32 func_8004CD38(const render_context_cell_bounds_t *bounds, const u8 *point);'
MARKER = 'INCLUDE_ASM("asm/nonmatchings/scene/render_context", func_8004CD38);'
CALL = 'func_8004CD38(This->m_NextSlotExclusionBounds,'
DEFINITION = re.compile(r'\bs32\s+func_8004CD38\s*\(\s*s32\s+\w+\s*,\s*const\s+u8\s*\*\s*\w+\s*\)\s*\{')


def prepare(output, *, root=ROOT):
    root = Path(root).resolve(strict=True)
    output = Path(output)
    output = (output if output.is_absolute() else root / output).resolve()
    lab = (root / '.decomp-lab').resolve()
    if output == lab or not output.is_relative_to(lab) or output.exists():
        raise ValueError('Choose a fresh output directory inside .decomp-lab.')
    source = (root / SOURCE).read_text(encoding='utf-8')
    fragment = (root / FRAGMENT).read_text(encoding='utf-8')
    for label, text in (('prototype', PROTOTYPE), ('assembly inclusion', MARKER), ('caller', CALL)):
        if source.count(text) != 1:
            raise ValueError('Expected exactly one current bounds ' + label + '.')
    if len(DEFINITION.findall(fragment)) != 1 or 'INCLUDE_ASM(' in fragment:
        raise ValueError('Expected the unaccepted C bounds fragment without an assembly inclusion.')
    candidate = source.replace(PROTOTYPE, 's32 func_8004CD38(s32, const u8 *);', 1)
    candidate = candidate.replace(CALL, 'func_8004CD38((s32) This->m_NextSlotExclusionBounds,', 1)
    candidate = candidate.replace(MARKER, fragment.rstrip(), 1)
    output.mkdir(parents=True, exist_ok=False)
    target = output / 'render_context.c'
    target.write_text(candidate, encoding='utf-8', newline='\n')
    digest = lambda text: hashlib.sha256(text.encode('utf-8')).hexdigest()
    report = {
        'status': 'prepared_unaccepted_bounds_candidate',
        'hash_serialization': 'UTF-8 text normalized to LF',
        'source': SOURCE.as_posix(), 'source_sha256': digest(source),
        'fragment': FRAGMENT.as_posix(), 'fragment_sha256': digest(fragment),
        'candidate': target.name, 'candidate_sha256': digest(candidate),
        'canonical_sources_modified': False, 'source_promoted': False,
        'matching_verified': False, 'native_behavior_verified': False,
    }
    (output / 'recipe.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = prepare(args.output)
    except (OSError, ValueError) as error:
        parser.exit(2, 'error: ' + str(error) + '\n')
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
