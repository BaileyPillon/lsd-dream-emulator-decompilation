"""Compare supplied Psy-Q signatures with current raw SDK-labelled segments.

Reports retain ambiguous labels and distinguish whole objects from complete
function-sized subranges. No source, native symbols or model API is changed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import configure
from tools.decomp_workbench import assembly_evidence
from tools.progress import check_build_current

CANONICAL_SHA1 = '76322eeade5ebb22dca57fdeac7d68c30f06308d'
VOLUME_CATALOGUE_SHA256 = 'cd35240249e36ec25ad1e3ae944fe7737db436a9ad1c37b3b3deacb61fe84248'
VOLUME_FUNCTIONS = [
    ('SsUtGetDetVVol', 0x80031C98, 88), ('SsUtSetDetVVol', 0x80031CF0, 124),
    ('SsUtGetVVol', 0x80031D6C, 140), ('SsUtSetVVol', 0x80031DF8, 156),
    ('SsUtAutoVol', 0x80031E94, 84), ('SsUtAutoPan', 0x80031EE8, 84),
]
LOCAL_LABEL = re.compile(r'^(?:loc_|text_|data_|byte_|word_|dword_|off_|unk_|flt_|dbl_|jpt_|def_|asc_)')


def parse_catalogue(data):
    entries = json.loads(data)
    if not isinstance(entries, list):
        raise ValueError('A signature catalogue must be an array.')
    result = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get('name'), str) or not entry['name'].strip():
            raise ValueError('Every library object needs a nonempty name.')
        if 'sig' not in entry:
            continue
        if not isinstance(entry['sig'], str):
            raise ValueError('An object signature must be a string.')
        tokens = entry['sig'].split()
        if not tokens or any(not re.fullmatch(r'[0-9A-Fa-f]{2}|\?\?', token) for token in tokens):
            raise ValueError('Signatures accept only hexadecimal bytes and ?? wildcards.')
        labels = entry.get('labels', [])
        if not isinstance(labels, list) or any(
                not isinstance(label, dict) or not isinstance(label.get('name'), str) or
                not label['name'].strip() or type(label.get('offset')) is not int or
                not 0 <= label['offset'] < len(tokens) for label in labels):
            raise ValueError('Labels need names and integer offsets inside their object signature.')
        result.append({'name': entry['name'], 'bytes': [None if t == '??' else int(t, 16) for t in tokens],
                       'labels': labels})
    if not result:
        raise ValueError('A signature catalogue needs at least one actual signature.')
    return result


def matches(data, signature):
    return len(data) == len(signature) and all(expected is None or actual == expected
                                             for actual, expected in zip(data, signature))


def find_matches(data, signature):
    """Return all starts; repeated code is never assigned a unique label."""
    runs, current = [], []
    for index, value in enumerate(signature):
        if value is None:
            if current:
                runs.append(current)
                current = []
        else:
            current.append((index, value))
    if current:
        runs.append(current)
    if not runs:
        return []
    anchor = max(runs, key=len)
    needle = bytes(value for _, value in anchor)
    result, position = [], data.find(needle)
    while position >= 0:
        start = position - anchor[0][0]
        if start >= 0 and matches(data[start:start + len(signature)], signature):
            result.append(start)
        position = data.find(needle, position + 1)
    return result


def volume_region(original, entries, load):
    """Resolve the ordered six-function context, rather than identical wrappers."""
    begin = VOLUME_FUNCTIONS[0][1]
    size = sum(length for _, _, length in VOLUME_FUNCTIONS)
    offset = 0x800 + begin - load
    for entry in entries:
        for first in entry['labels']:
            if first['name'] != VOLUME_FUNCTIONS[0][0]:
                continue
            start = first['offset']
            signature = entry['bytes'][start:start + size]
            labels = {(label['name'], label['offset'] - start) for label in entry['labels']}
            expected = {(name, address - begin) for name, address, _ in VOLUME_FUNCTIONS}
            if expected <= labels and matches(original[offset:offset + size], signature):
                return {'status': 'passed_pinned_six_function_context', 'object': entry['name'],
                        'address': hex(begin), 'bytes': size,
                        'fixed_bytes': sum(value is not None for value in signature),
                        'native_sha256': hashlib.sha256(original[offset:offset + size]).hexdigest(),
                        'functions': [{'function': name, 'address': hex(address), 'bytes': length}
                                      for name, address, length in VOLUME_FUNCTIONS]}
    raise ValueError('The pinned six-function SDK volume context does not match.')


def collect(catalogue):
    paths = [catalogue / name for name in ('LIBGS.LIB.json', 'LIBSND.LIB.json')]
    source_paths = [ROOT / path for path in [configure.ROM, configure.EXE, configure.SYMBOLS,
        configure.MAP_FILE, 'configure.py', 'src/sound/sound.c', 'include/psx/libsnd.h',
        'tools/audit_sdk_signatures.py', 'tools/decomp_workbench.py', 'tools/progress.py',
        *configure.asm_psyq_targets]]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in [*source_paths, *paths]}
    original = (ROOT / configure.ROM).read_bytes()
    if hashlib.sha1(original).hexdigest() != CANONICAL_SHA1 or (ROOT / configure.EXE).read_bytes() != original:
        raise ValueError('The original and current build must equal the canonical executable.')
    if check_build_current(ROOT) is not True:
        raise ValueError('A current complete matching build is required.')
    load = int.from_bytes(original[0x18:0x1C], 'little')
    functions = []
    for source in configure.asm_psyq_targets:
        text = (ROOT / source).read_text()
        for name in re.findall(r'^glabel (\w+)\s*$', text, re.M):
            functions.append({'function': name, 'assembly': source,
                              **assembly_evidence(text, name, original)})
    whole, spans, catalogue_inputs = [], [], []
    context = {'status': 'not_the_pinned_sdk_33_catalogue'}
    for path in paths:
        entries = parse_catalogue(path.read_text())
        catalogue_inputs.append({'file': path.name, 'sha256': before[path], 'objects': len(entries)})
        if path.name == 'LIBSND.LIB.json' and before[path] == VOLUME_CATALOGUE_SHA256:
            context = volume_region(original, entries, load)
        for entry in entries:
            signature = entry['bytes']
            if sum(value is not None for value in signature) < 8:
                continue
            positions = [p for p in find_matches(original[0x800:], signature) if p % 4 == 0]
            for position in positions:
                address = load + position
                covered = [f['function'] for f in functions if address <= int(f['address'], 16) and
                           int(f['address'], 16) + f['bytes'] <= address + len(signature)]
                if covered:
                    whole.append({'library': path.name, 'object': entry['name'], 'address': hex(address),
                                  'bytes': len(signature), 'candidate_address_count': len(positions),
                                  'covered_functions': covered})
            for label in entry['labels']:
                if LOCAL_LABEL.match(label['name']) or label['offset'] % 4:
                    continue
                for function in functions:
                    start, length = label['offset'], function['bytes']
                    candidate = signature[start:start + length]
                    if (sum(value is not None for value in candidate) >= 8 and
                            matches(original[function['file_offset']:function['file_offset'] + length], candidate)):
                        spans.append({'function': function['function'], 'address': function['address'],
                                      'library': path.name, 'object': entry['name'], 'candidate_label': label['name'],
                                      'bytes_compared': length, 'fixed_bytes_compared': sum(v is not None for v in candidate),
                                      'signature_offset': start, 'whole_object_identity_proven': False})
    if any(hashlib.sha256(p.read_bytes()).hexdigest() != digest for p, digest in before.items()):
        raise ValueError('Signature, source or build inputs changed during the audit.')
    if check_build_current(ROOT) is not True:
        raise ValueError('Build inputs changed during the audit.')
    return {'schema_version': 1, 'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'canonical_executable_sha1': CANONICAL_SHA1, 'catalogue_inputs': catalogue_inputs,
        'scope': 'Configured raw SDK-labelled segments only; absent matches do not prove game ownership. '
                 'Whole-object matches and complete function-sized candidate spans are separate. '
                 'Wildcard targets are not resolved by a byte-pattern match; repeated/ambiguous names remain candidates.',
        'native_functions': functions, 'whole_object_matches': whole, 'function_span_candidates': spans,
        'volume_api_context': context, 'native_names_automatically_changed': False,
        'classification_changes': 0, 'source_promotions': 0, 'original_feature_groups_accepted': 0,
        'model_api_calls': 0,
        'producer_dependencies': [{'path': p.relative_to(ROOT).as_posix(), 'sha256': before[p]} for p in source_paths]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--signatures', type=Path, required=True, help='One supplied SDK-version directory.')
    parser.add_argument('--output', type=Path, required=True, help='New JSON report inside .decomp-lab.')
    args = parser.parse_args(argv)
    try:
        destination = args.output if args.output.is_absolute() else ROOT / args.output
        destination = destination.resolve()
        if not destination.is_relative_to((ROOT / '.decomp-lab').resolve()) or destination.exists():
            raise ValueError('Choose a new report path inside the private .decomp-lab directory.')
        report = collect(args.signatures.resolve())
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')
        print(json.dumps({'report': str(destination), 'raw_functions': len(report['native_functions']),
                          'candidate_spans': len(report['function_span_candidates']),
                          'volume_context': report['volume_api_context']['status']}))
        return 0
    except (OSError, ValueError) as error:
        print('[!] ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
