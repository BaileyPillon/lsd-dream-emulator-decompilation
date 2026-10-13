"""Observe memory-store deletion decisions in the exact matching compiler.

This is compiler analysis. It loads no game executable and accepts no C recovery.
Requires Linux/WSL, GDB and the configured MIPS preprocessor.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import configure
from research.compiler.trace_allocation import COMPILER_SHA256, require_compiler, require_output, sha256

BACKEND = Path(__file__).with_name('memory_stores_gdb.py')


def function_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z_]\w*', value):
        raise ValueError('Choose a C function identifier.')
    return value


def validate_observation(trace, normal, observed, function):
    function_name(function)
    if not isinstance(trace, dict) or trace.get('compiler_sha256') != COMPILER_SHA256:
        raise ValueError('Unsupported compiler identity in observation.')
    if (not isinstance(trace, dict) or trace.get('target') != function
            or trace.get('compiler_exited') is not True
            or type(trace.get('compiler_exit_code')) is not int
            or trace['compiler_exit_code'] != 0):
        raise ValueError('The selected compiler observation did not finish successfully.')
    if (trace.get('normal_debugger_breakpoint_machinery') is not True
            or trace.get('explicit_inferior_memory_writes_or_opcode_substitutions') is not False
            or trace.get('extra_inferior_functions_invoked') is not False):
        raise ValueError('Unsupported observer mutation or invocation policy.')
    if normal != observed:
        raise ValueError('Debugger observation changed complete compiler assembly.')
    events = trace.get('decisions')
    if not isinstance(events, list) or not events:
        raise ValueError('No selected memory-store decisions were observed.')
    equalities = 0
    for index, event in enumerate(events):
        if (not isinstance(event, dict) or type(event.get('sequence')) is not int
                or event['sequence'] != index or type(event.get('returned_dead')) is not int
                or event['returned_dead'] not in (0, 1)
                or 'last_mem_set_before' not in event or 'last_mem_set_after' not in event):
            raise ValueError('Incomplete memory-store decision.')
        pattern = event.get('pattern')
        if (not isinstance(pattern, dict) or pattern.get('code') != 'set'
                or not isinstance(pattern.get('left'), dict) or pattern['left'].get('code') != 'mem'
                or not isinstance(pattern['left'].get('address'), dict)):
            raise ValueError('Observation is not a decoded memory destination.')
        calls = event.get('equality_calls')
        if not isinstance(calls, list):
            raise ValueError('Missing memory-address equality observations.')
        for call in calls:
            if (not isinstance(call, dict) or type(call.get('returned_equal')) is not int
                    or call['returned_equal'] not in (0, 1)
                    or not isinstance(call.get('left'), dict) or not isinstance(call.get('right'), dict)):
                raise ValueError('Incomplete address-equality return.')
        equalities += len(calls)
    return {'memory_store_decisions': len(events), 'address_equality_calls': equalities,
            'dead_decisions': sum(event['returned_dead'] for event in events),
            'complete_assembly_equal': True, 'selected_function_observed': True}


def trace_source(source, output, function, compiler_mode='g8'):
    function_name(function)
    source = Path(source).resolve(strict=True)
    if source.suffix.lower() != '.c' or compiler_mode not in ('g0', 'g8'):
        raise ValueError('Use a C source and a configured G0/G8 compiler mode.')
    compiler = require_compiler(configure.CC)
    output = require_output(output, ROOT / '.decomp-lab')
    cpp, gdb = shutil.which(configure.CROSS + 'cpp'), shutil.which('gdb')
    if not cpp or not gdb:
        raise RuntimeError('Run in Linux/WSL with the MIPS preprocessor and GDB.')
    inputs = {str(path): sha256(path) for path in
              (source, compiler, BACKEND, Path(__file__), Path(configure.__file__))}
    flags = list(configure.C_FLAGS_G8 if compiler_mode == 'g8' else configure.C_FLAGS)
    output.mkdir(parents=True, exist_ok=False)
    commands = []

    def run(stage, command, env=None):
        commands.append({'stage': stage, 'argv': command})
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True)
        (output / (stage + '.stdout')).write_bytes(result.stdout)
        (output / (stage + '.stderr')).write_bytes(result.stderr)
        if result.returncode:
            raise RuntimeError(stage + ' failed; logs retained in ' + str(output))
        return result

    preprocessed = output / 'candidate.i'
    preprocessed.write_bytes(run('preprocess', [cpp, *configure.CPP_FLAGS,
                            *(['-DCCG8'] if compiler_mode == 'g8' else []), str(source)]).stdout)
    run('normal-compiler', [str(compiler), *flags, '-o', str(output / 'normal.s'), str(preprocessed)])
    env = os.environ.copy()
    env['LSD_MEMORY_STORE_FUNCTION'] = function
    env['LSD_MEMORY_STORE_REPORT'] = str(output / 'memory-stores.json')
    debug = run('observed-compiler', [gdb, '--batch', '--quiet', '-x', str(BACKEND), '--args',
                                    str(compiler), *flags, '-o', str(output / 'observed.s'), str(preprocessed)], env)
    diagnostic_text = (debug.stdout + debug.stderr).decode(errors='replace')
    if any(marker in diagnostic_text for marker in
           ('Traceback (most recent call last)', 'Error occurred in Python', 'Python Exception', 'Exception ignored')):
        raise ValueError('The GDB observer reported a Python error; logs are preserved.')
    trace = json.loads((output / 'memory-stores.json').read_bytes())
    qualification = validate_observation(trace, (output / 'normal.s').read_bytes(),
                                          (output / 'observed.s').read_bytes(), function)
    if any(sha256(path) != expected for path, expected in inputs.items()):
        raise ValueError('An observed source/compiler input changed during tracing.')
    report = {'schema_version': 1, 'status': 'passed_actual_compiler_memory_store_observation',
              'function': function, 'compiler_mode': compiler_mode, 'compiler_sha256': sha256(compiler),
              'input_hashes': inputs, 'qualification': qualification, 'commands': commands,
              'artifacts': [{'file': path.name, 'sha256': sha256(path)}
                            for path in sorted(output.iterdir()) if path.is_file()],
              'source_promoted': False, 'original_game_executed': False, 'model_api_calls': 0,
              'scope': 'Decoded SET/MEM decisions and actual RTL equality returns in the exact compiler. '
                       'Normal and observed complete assembly agree. Preprocessed input is retained; '
                       'these observations are not an original source explanation or gameplay acceptance.'}
    (output / 'report.json').write_bytes((json.dumps(report, indent=2) + '\n').encode())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--function', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--compiler-mode', choices=('g0', 'g8'), default='g8')
    args = parser.parse_args()
    try:
        result = trace_source(args.source, args.output, args.function, args.compiler_mode)
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps({'status': result['status'], **result['qualification']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
