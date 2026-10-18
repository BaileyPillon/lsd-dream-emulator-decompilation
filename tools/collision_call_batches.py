"""Prepare ordinal partitions of a controller route; verify coverage separately."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.collision_calls import selection
from tools.dispatch_trace import expand_program, validate_program
from tools.replay_cold_start_headless import require, write_json

PROGRAM_NAME = 'collision-ordinal-opening-route.json'


def partition_programs(program):
    program = validate_program(copy.deepcopy(program))
    selected = selection(program)
    require(selected is not None and 'ordinal_step' in selected,
            'Require an ordinal collision-call route template.')
    controller = expand_program(program)
    partitions = []
    for first in range(1, selected['ordinal_step'] + 1):
        part = copy.deepcopy(program)
        part['method_trace']['collision_calls']['ordinal_first'] = first
        require(expand_program(part) == controller, 'Ordinal selection changed controller inputs.')
        selection(part)
        partitions.append(part)
    return partitions


def prepare(program_file, output):
    output = Path(output).resolve()
    require(output.is_relative_to(ROOT / '.decomp-lab') and not output.exists(),
            'Choose a fresh private batch-program directory.')
    program_file = Path(program_file).resolve(strict=True)
    raw = program_file.read_bytes()
    program = json.loads(raw)
    partitions = partition_programs(program)
    output.mkdir()
    rows = []
    for first, part in enumerate(partitions, 1):
        folder = output / f'phase-{first:02d}'
        folder.mkdir()
        path = folder / PROGRAM_NAME
        write_json(path, part)
        rows.append(dict(first=first, program=str(path.relative_to(output)).replace('\\', '/'),
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    report = dict(schema_version=1, status='prepared_ordinal_collision_programs',
                  template_sha256=hashlib.sha256(raw).hexdigest(), frames=program['frames'],
                  ordinal_step=len(partitions), programs=rows, controller_inputs_preserved=True,
                  expanded_submitted_sha256=program.get('expanded_submitted_sha256'),
                  runtime_recordings_complete=False, complete_route_coverage_verified=False,
                  new_C_bytes=0, whole_feature_groups_accepted=0)
    write_json(output / 'plan.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = prepare(args.program, args.output)
        print(json.dumps(dict(status=report['status'], partitions=report['ordinal_step'])))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
