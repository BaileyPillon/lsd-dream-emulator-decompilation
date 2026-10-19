"""Read qualified compiler traces; keep RTL phase evidence separate from matching C."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from research.compiler.trace_allocation import COMPILER_SHA256, require_output, validate_observation

FUNCTION = 'func_8004C6A8'
STAGES = ('rtl', 'combine', 'sched', 'lreg', 'greg', 'sched2', 'dbr')
REG = r'\(reg(?:/[A-Za-z]+)?:SI (\d+)(?: [^)]*)?\)'
# Inline and other RTL attributes precede an optional mode, e.g. insn/i:QI.
FORM = r'^\((?:note|insn|call_insn|jump_insn|barrier|code_label)(?:/[A-Za-z]+)*(?::[A-Z]+)?\s+\d+\b'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def recorded_path(path):
    if os.name == 'nt' and re.match(r'^/mnt/[a-z]/', path):
        return Path(path[5].upper() + ':' + path[6:])
    return Path(path)


def function_section(text, function=FUNCTION):
    sections = re.findall(r'^;; Function ' + re.escape(function) + r'\n(.*?)(?=^;; Function |\Z)',
                          text, re.M | re.S)
    if len(sections) != 1:
        raise ValueError('Expected exactly one selected function in this diagnostic stage.')
    return sections[0]


def sized_function_symbols(text):
    """Ignore the compiler's unsized/zero-size text marker labels."""
    result = []
    for line in text.splitlines():
        columns = line.split()
        if len(columns) == 4 and columns[2] in ('t', 'T'):
            try:
                address, size = int(columns[0], 16), int(columns[1], 16)
            except ValueError as error:
                raise ValueError('Malformed sized text symbol.') from error
            if size:
                result.append({'function': columns[3], 'offset': address, 'bytes': size})
    return result


def prefix_events(section):
    markers = list(re.finditer(FORM, section, re.M))
    if not markers:
        raise ValueError('Selected stage contains no RTL forms.')
    events = []
    seen_begin = False
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(section)
        form = section[marker.start():end]
        if form.startswith('(call_insn'):
            break
        uid = int(re.match(r'^\(\S+\s+(\d+)', form)[1])
        if 'NOTE_INSN_FUNCTION_BEG' in form:
            seen_begin = True
            events.append({'uid': uid, 'kind': 'function_begin_note'})
        elif 'NOTE_INSN_DELETED' in form:
            events.append({'uid': uid, 'kind': 'deleted_note'})
        move = re.search(r'\(set ' + REG + r'\s+' + REG + r'\)', form)
        if move:
            destination, source = map(int, move.groups())
            events.append({'uid': uid, 'kind': 'register_copy', 'destination': destination,
                           'source': source, 'after_function_begin_note': seen_begin})
        address = re.search(r'\(set ' + REG + r'\s+\(plus:SI ' + REG +
                            r'\s+\(const_int (\d+)\)\)\)', form)
        if address:
            destination, base, displacement = map(int, address.groups())
            if destination == 5 and base in (29, 30) and displacement == 16:
                events.append({'uid': uid, 'kind': 'lookup_buffer_address',
                               'destination': destination, 'base': base, 'displacement': displacement})
        save = re.search(r'\(set \(mem:SI \(plus:SI ' + REG +
                         r'\s+\(const_int (\d+)\)\)\)\s+' + REG + r'\)', form)
        if save:
            base, displacement, source = map(int, save.groups())
            if base == 29 and source == 30:
                events.append({'uid': uid, 'kind': 'save_incoming_fp', 'displacement': displacement})
    if not seen_begin:
        raise ValueError('Selected prefix lacks its function-begin marker.')
    return events


def inspect(trace_directory):
    directory = Path(trace_directory).resolve()
    report = json.loads((directory / 'report.json').read_bytes())
    if (report.get('status') != 'passed_actual_compiler_allocation_observation' or
            report.get('function') != FUNCTION or report.get('compiler_sha256') != COMPILER_SHA256):
        raise ValueError('Require a qualified observation of the exact bundled compiler and grid function.')
    for path, expected in report['input_hashes'].items():
        if digest(recorded_path(path)) != expected:
            raise ValueError('A preserved compiler/source input changed: ' + path)
    artifacts = {}
    for item in report['artifacts']:
        name = item['file']
        if Path(name).name != name or '/' in name or '\\' in name or name in artifacts:
            raise ValueError('Invalid or duplicate compiler artifact name.')
        if digest(directory / name) != item['sha256']:
            raise ValueError('Compiler artifact changed: ' + name)
        artifacts[name] = item['sha256']
    required = {'allocations.json', 'normal.s', 'observed.s', 'diagnostic.s', 'diagnostic.greg'}
    if not required.issubset(artifacts):
        raise ValueError('Required qualification inputs are missing from the pinned artifacts.')
    observation = json.loads((directory / 'allocations.json').read_bytes())
    qualification = validate_observation(observation, (directory / 'normal.s').read_bytes(),
        (directory / 'observed.s').read_bytes(), (directory / 'diagnostic.s').read_bytes(),
        (directory / 'diagnostic.greg').read_text(), FUNCTION)
    phases = []
    for stage in STAGES:
        name = 'diagnostic.' + stage
        if name not in artifacts:
            raise ValueError('Stage was not pinned by the compiler observer: ' + name)
        events = prefix_events(function_section((directory / name).read_text()))
        phases.append({'stage': stage, 'sha256': artifacts[name], 'prefix_events': events})
    return {'trace_report_sha256': digest(directory / 'report.json'), 'compiler_sha256': COMPILER_SHA256,
            'qualification': qualification, 'phases': phases,
            'global_allocations': observation['allocation_events'], 'source_promoted': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--formal', required=True, type=Path)
    parser.add_argument('--local', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    output = require_output(args.output, ROOT / '.decomp-lab')
    result = {'status': 'passed_qualified_grid_phase_journal',
              'formal': inspect(args.formal), 'local': inspect(args.local),
              'source_promoted': False, 'whole_feature_groups_accepted': 0, 'model_api_calls': 0,
              'scope': 'Read-only interpretation of two actual compiler observations. '
                       'Function-begin positions are reported as recorded in each phase; '
                       'later note relocation does not establish original source declarations.'}
    output.mkdir(parents=True, exist_ok=False)
    (output / 'report.json').write_bytes((json.dumps(result, indent=2) + '\n').encode())
    print(json.dumps({'status': result['status'], 'compiler_observations': 2, 'phases_each': len(STAGES),
                      'source_promoted': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
