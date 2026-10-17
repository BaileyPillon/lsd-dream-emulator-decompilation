"""Observe inline-call argument checks in the exact bundled compiler.

Normal and GDB-observed complete assembly must agree. This analysis does not
load an original game executable, promote source, or accept gameplay parity.
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import configure
from research.compiler.trace_allocation import COMPILER_SHA256, require_compiler, require_output, sha256
from research.compiler.trace_memory_stores import function_name

BACKEND = Path(__file__).with_name('inline_calls_gdb.py')


def address(value):
    if (not isinstance(value, str) or not re.fullmatch(r'0x[0-9a-fA-F]+', value)
            or not 0 < int(value, 16) <= 0xFFFFFFFF):
        raise ValueError('Invalid compiler tree address.')
    return int(value, 16)


def type_info(value):
    if not isinstance(value, dict):
        raise ValueError('Missing compiler type information.')
    address(value.get('pointer'))
    address(value.get('main_variant'))
    if (not isinstance(value.get('code'), str) or not value['code']
            or not isinstance(value.get('mode'), str) or not value['mode']
            or type(value.get('uid')) is not int or not 0 <= value['uid'] <= 0xFFFFFFFF
            or type(value.get('alignment')) is not int or not 0 <= value['alignment'] <= 0xFFFFFFFF
            or type(value.get('readonly')) is not bool or type(value.get('volatile')) is not bool):
        raise ValueError('Incomplete compiler type information.')
    return value


def rejection_reason(formal, promoted, actual):
    formal, promoted, actual = map(type_info, (formal, promoted, actual))
    if promoted['mode'] != actual['mode']:
        return 'argument_mode_mismatch'
    if promoted['mode'] == 'BLK' and address(formal['pointer']) != address(actual['pointer']):
        return 'BLK_type_identity_mismatch'
    return None


def validate_observation(trace, normal, observed, function, helper=None):
    function_name(function)
    if helper is not None:
        function_name(helper)
    if (not isinstance(trace, dict) or type(trace.get('schema_version')) is not int
            or trace['schema_version'] != 1
            or trace.get('compiler_sha256') != COMPILER_SHA256
            or trace.get('target') != function or trace.get('helper') != helper
            or trace.get('compiler_exited') is not True
            or type(trace.get('compiler_exit_code')) is not int or trace['compiler_exit_code'] != 0
            or trace.get('call_stack_balanced') is not True):
        raise ValueError('The selected compiler observation did not finish successfully.')
    if (trace.get('normal_debugger_breakpoint_machinery') is not True
            or trace.get('explicit_inferior_memory_writes_or_opcode_substitutions') is not False
            or trace.get('extra_inferior_functions_invoked') is not False):
        raise ValueError('Unsupported observer mutation or invocation policy.')
    if normal != observed:
        raise ValueError('Debugger observation changed complete compiler assembly.')
    emitted = re.findall(rb'^\s*\.ent\s+(\S+)', normal, re.M)
    if emitted.count(function.encode()) != 1:
        raise ValueError('The selected function must be emitted exactly once.')
    events = trace.get('events')
    if not isinstance(events, list) or not events:
        raise ValueError('No selected inline calls were observed.')
    rejected = 0
    unknown = 0
    for index, event in enumerate(events):
        if (not isinstance(event, dict) or type(event.get('sequence')) is not int
                or event['sequence'] != index or event.get('caller') != function
                or not isinstance(event.get('function'), str) or not event['function']
                or (helper is not None and event['function'] != helper)
                or event.get('completed') is not True
                or not isinstance(event.get('arguments'), list)
                or not isinstance(event.get('rejections'), list)
                or len(event['rejections']) > 1):
            raise ValueError('Incomplete selected inline call.')
        returned = event.get('return_value')
        if (not isinstance(returned, str) or not re.fullmatch(r'0x[0-9a-fA-F]+', returned)
                or not 0 <= int(returned, 16) <= 0xFFFFFFFF):
            raise ValueError('Missing or invalid inline return value.')
        failed = int(returned, 16) == 0xFFFFFFFF
        arguments = {}
        for arg in event['arguments']:
            if not isinstance(arg, dict):
                raise ValueError('Incomplete inline argument.')
            node = address(arg.get('formal_node'))
            if node in arguments:
                raise ValueError('Duplicate inline argument node.')
            arguments[node] = arg
            type_info(arg.get('formal_type'))
            type_info(arg.get('promoted_type'))
            if arg.get('missing_actual') is True:
                if 'actual_type' in arg or not failed:
                    raise ValueError('Inconsistent missing actual argument.')
            else:
                actual = type_info(arg.get('actual_type'))
                if type(arg.get('same_type_identity')) is not bool or arg['same_type_identity'] != (
                        address(actual['pointer']) == address(arg['formal_type']['pointer'])):
                    raise ValueError('Inconsistent inline type identity.')
        for gate in event['rejections']:
            if (not isinstance(gate, dict) or gate.get('gate') != 'argument_mode_or_BLK_type_identity'
                    or not failed):
                raise ValueError('Inconsistent inline rejection return.')
            arg = arguments.get(address(gate.get('formal_node')))
            if arg is None or arg.get('missing_actual'):
                raise ValueError('Rejection does not identify an observed argument.')
            for key in ('formal_type', 'promoted_type', 'actual_type'):
                if type_info(gate.get(key)) != arg[key]:
                    raise ValueError('Rejection types differ from the observed call.')
            reason = rejection_reason(gate['formal_type'], gate['promoted_type'], gate['actual_type'])
            if reason is None or gate.get('reason') != reason:
                raise ValueError('Observed argument gate has no decoded rejection reason.')
        rejected += failed
        unknown += failed and not event['rejections']
    return {'inline_calls': len(events), 'inlined_calls': len(events) - rejected,
            'not_inlined_calls': rejected,
            'argument_gate_rejections': sum(len(event['rejections']) for event in events),
            'not_inlined_without_observed_argument_gate': unknown,
            'complete_assembly_equal': True, 'selected_function_observed': True}


def trace_source(source, output, function, helper=None, compiler_mode='g8'):
    function_name(function)
    if helper is not None:
        function_name(helper)
    source = Path(source).resolve(strict=True)
    if source.suffix.lower() != '.c' or compiler_mode not in ('g0', 'g8'):
        raise ValueError('Use a C source and a configured G0/G8 compiler mode.')
    compiler = require_compiler(configure.CC)
    output = require_output(output, ROOT / '.decomp-lab')
    cpp, gdb = shutil.which(configure.CROSS + 'cpp'), shutil.which('gdb')
    if sys.platform == 'win32' or not cpp or not gdb:
        raise RuntimeError('Run in Linux/WSL with the MIPS preprocessor and GDB.')
    from research.compiler import trace_allocation, trace_memory_stores
    inputs = {str(path): sha256(path) for path in
              (source, compiler, BACKEND, Path(__file__), Path(configure.__file__),
               Path(trace_allocation.__file__), Path(trace_memory_stores.__file__), Path(gdb))}
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
    version = run('gdb-version', [gdb, '--nx', '--version']).stdout.decode(errors='replace').splitlines()
    if not version:
        raise ValueError('GDB did not report its version; logs are preserved.')
    preprocessed.write_bytes(run('preprocess', [cpp, '-I' + str(source.parent), *configure.CPP_FLAGS,
                            *(['-DCCG8'] if compiler_mode == 'g8' else []), str(source)]).stdout)
    inputs[str(preprocessed)] = sha256(preprocessed)
    run('normal-compiler', [str(compiler), *flags, '-o', str(output / 'normal.s'), str(preprocessed)])
    env = dict(os.environ, LSD_INLINE_TARGET=function, LSD_INLINE_HELPER=helper or '',
               LSD_INLINE_REPORT=str(output / 'inline-events.json'))
    debug = run('observed-compiler', [gdb, '--nx', '--batch', '--quiet', '-x', str(BACKEND), '--args',
                                    str(compiler), *flags, '-o', str(output / 'observed.s'), str(preprocessed)], env)
    diagnostic = (debug.stdout + debug.stderr).decode(errors='replace')
    if any(marker in diagnostic for marker in
           ('Traceback (most recent call last)', 'Error occurred in Python', 'Python Exception', 'Exception ignored')):
        raise ValueError('The GDB observer reported a Python error; logs are preserved.')
    trace = json.loads((output / 'inline-events.json').read_bytes())
    qualification = validate_observation(trace, (output / 'normal.s').read_bytes(),
                                          (output / 'observed.s').read_bytes(), function, helper)
    if any(sha256(path) != expected for path, expected in inputs.items()):
        raise ValueError('A source, compiler or observer input changed during tracing.')
    report = {'schema_version': 1, 'status': 'passed_compiler_inline_observation',
              'function': function, 'helper': helper, 'compiler_mode': compiler_mode,
              'gdb_version': version[0], 'gdb_initialization_files_disabled': True,
              'compiler_sha256': sha256(compiler), 'input_hashes': inputs,
              'qualification': qualification, 'commands': commands,
              'artifacts': [{'file': path.name, 'sha256': sha256(path)}
                            for path in sorted(output.iterdir()) if path.is_file()],
              'source_promoted': False, 'original_game_executed': False, 'model_api_calls': 0,
              'scope': 'Actual inline-call returns and the captured argument mode/type gate in the exact '
                       'compiler. Normal and observed complete assembly agree. Other causes of rejected '
                       'inlining remain unclassified; this is not matching-source or gameplay acceptance.'}
    with (output / 'report.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--function', required=True)
    parser.add_argument('--helper', help='Observe only calls to this helper in the selected function.')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--compiler-mode', choices=('g0', 'g8'), default='g8')
    args = parser.parse_args(argv)
    try:
        result = trace_source(args.source, args.output, args.function, args.helper, args.compiler_mode)
    except (OSError, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps({'status': result['status'], **result['qualification']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
