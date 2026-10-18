"""Observe temporary-storage lifetimes in the hash-pinned matching compiler.

This compiler diagnostic uses a complete C candidate and a selected function.
It requires identical complete assembly from normal and GDB compilation. It
does not load original game inputs or establish a matching C implementation.
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
from research.collision import trace_compiler_stack as stack

COMPILER_SHA256 = '3a7378955ab79dbe06cc413cc10b757777fd07b7b72bce76faf432d255da7fab'
OPERATIONS = ('assign_stack_temp', 'preserve_temp_slots', 'mark_temp_addr_taken',
              'pop_temp_slots', 'free_temp_slots')


def function_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', value):
        raise ValueError('Choose a C function name to observe.')
    return value


def compiler_profile(compiler):
    profile = stack.compiler_profile(compiler)
    if profile['sha256'] != COMPILER_SHA256:
        raise ValueError('Lifetime tracing requires the exact bundled compiler SHA-256; its heap layout is version specific.')
    return {**profile, 'temp_slot_bytes': 32, 'profile': 'bundled-gcc263-i386-temp-slot-v1'}


def pointer(value):
    return (isinstance(value, str) and re.fullmatch(r'0x[0-9a-f]{1,8}', value)
            and 0 <= int(value, 16) <= 0xFFFFFFFF)


def validate_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        raise ValueError('GDB reported an incomplete lifetime snapshot.')
    for name in ('level', 'frame_offset'):
        value = snapshot.get(name)
        if type(value) is not int or not 0 <= value <= 0x7FFFFFFF:
            raise ValueError('GDB reported an invalid lifetime snapshot.')
    slots = snapshot.get('slots')
    if not isinstance(slots, list) or len(slots) > 4096:
        raise ValueError('GDB reported an invalid temporary-storage list.')
    nodes = set()
    for slot in slots:
        if not isinstance(slot, dict):
            raise ValueError('GDB reported an invalid temporary-storage slot.')
        if any(not pointer(slot.get(name)) for name in
               ('node', 'slot_rtx', 'address_rtx', 'rtl_expr')):
            raise ValueError('GDB reported an invalid temporary-storage pointer.')
        if int(slot['node'], 16) == 0 or int(slot['slot_rtx'], 16) == 0 or slot['node'] in nodes:
            raise ValueError('GDB reported a repeated or missing temporary-storage node.')
        nodes.add(slot['node'])
        if (type(slot.get('size')) is not int or not 0 <= slot['size'] <= 0x7FFFFFFF
                or type(slot.get('level')) is not int or not -1 <= slot['level'] <= 0x7FFFFFFF
                or any(type(slot.get(name)) is not int for name in ('in_use', 'addr_taken', 'keep'))
                or slot['in_use'] not in (0, 1) or slot['addr_taken'] not in (0, 1)
                or slot['keep'] not in (0, 1, 2)):
            raise ValueError('GDB reported invalid temporary-storage fields.')


def validate_trace(trace, function):
    function_name(function)
    if (not isinstance(trace, dict) or not trace.get('compiler_exited') or trace.get('compiler_exit_code') != 0
            or trace.get('trace_errors') != []):
        raise ValueError('The traced compiler did not finish a successful lifetime observation.')
    events = trace.get('lifetime_events')
    if not isinstance(events, list) or not events:
        raise ValueError('GDB did not observe the selected function.')
    for sequence, event in enumerate(events):
        if (not isinstance(event, dict) or event.get('sequence') != sequence
                or event.get('function') != function or event.get('operation') not in OPERATIONS):
            raise ValueError('GDB reported an invalid lifetime event.')
        validate_snapshot(event.get('before'))
        validate_snapshot(event.get('after'))
        if event['operation'] == 'assign_stack_temp':
            arguments = event.get('arguments')
            if (not isinstance(arguments, list) or len(arguments) != 3
                    or any(type(value) is not int for value in arguments)
                    or not pointer(event.get('returned_rtx'))):
                raise ValueError('GDB reported an incomplete allocation return.')
        elif event['operation'] in ('preserve_temp_slots', 'mark_temp_addr_taken'):
            if not pointer(event.get('argument_rtx')):
                raise ValueError('GDB reported an incomplete lifetime argument.')
    return events


def trace_candidate(source, output, function, compiler_mode='g8', *, lab_root=None):
    output = stack.new_output(output, lab_root)
    function = function_name(function)
    if sys.platform == 'win32':
        raise ValueError('Run compiler lifetime tracing in Linux/WSL.')
    source = Path(source).resolve(strict=True)
    if source.suffix.lower() != '.c' or compiler_mode not in ('g0', 'g8'):
        raise ValueError('Select a complete C translation unit and g0 or g8 mode.')
    compiler = Path(configure.CC).resolve(strict=True)
    profile = compiler_profile(compiler)
    gdb = shutil.which('gdb')
    cpp = shutil.which(configure.CROSS + 'cpp')
    if not gdb or not cpp:
        raise ValueError('GDB and the configured MIPS preprocessor must be installed in Linux/WSL.')
    backend = Path(__file__).with_name('compiler_lifetimes_gdb.py')
    producer = Path(__file__).resolve()
    helper = Path(stack.__file__).resolve()
    configuration = Path(configure.__file__).resolve()
    inputs = (source, compiler, backend, producer, helper, configuration)
    baseline = {str(path): stack.digest(path) for path in inputs}
    cpp_flags = ['-I' + str(source.parent), *configure.CPP_FLAGS]
    flags = configure.C_FLAGS_G8 if compiler_mode == 'g8' else configure.C_FLAGS
    if compiler_mode == 'g8':
        cpp_flags.append('-DCCG8')
    commands = []

    def run(stage, argv, env=None):
        commands.append({'stage': stage, 'argv': argv})
        result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True)
        (output / (stage + '.stdout')).write_bytes(result.stdout)
        (output / (stage + '.stderr')).write_bytes(result.stderr)
        if result.returncode:
            raise ValueError(f'{stage} failed with exit code {result.returncode}; see its private logs.')
        return result

    preprocessed = output / 'candidate.i'
    preprocessed.write_bytes(run('preprocess', [cpp, *cpp_flags, str(source)]).stdout)
    normal = output / 'normal.s'
    traced = output / 'traced.s'
    run('normal-compiler', [str(compiler), *flags, '-o', str(normal), str(preprocessed)])
    env = os.environ.copy()
    env['LSD_LIFETIME_REPORT'] = str(output / 'lifetimes.json')
    env['LSD_LIFETIME_FUNCTION'] = function
    run('gdb-compiler', [gdb, '--batch', '--quiet', '-x', str(backend), '--args',
                         str(compiler), *flags, '-o', str(traced), str(preprocessed)], env)
    data = json.loads((output / 'lifetimes.json').read_text(encoding='utf-8'))
    events = validate_trace(data, function)
    assembly_equal = normal.read_bytes() == traced.read_bytes()
    preserved = all(stack.digest(path) == expected for path, expected in baseline.items())
    report = {
        'status': 'passed_compiler_lifetime_trace' if assembly_equal and preserved else 'failed',
        'scope': 'Actual compiler temporary-storage observations; no original game inputs, matching-C promotion or gameplay acceptance.',
        'function': function, 'compiler_mode': compiler_mode, 'compiler_profile': profile,
        'source': str(source), 'source_sha256': baseline[str(source)],
        'producer_sha256': baseline[str(producer)], 'backend_sha256': baseline[str(backend)],
        'helper_sha256': baseline[str(helper)], 'configuration_sha256': baseline[str(configuration)],
        'commands': commands,
        'gdb_version': subprocess.check_output([gdb, '--version'], text=True).splitlines()[0],
        'lifetime_events': len(events), 'complete_assembly_equal': assembly_equal,
        'normal_assembly_sha256': stack.digest(normal), 'traced_assembly_sha256': stack.digest(traced),
        'all_observed_inputs_preserved': preserved,
        'source_promoted': False, 'whole_feature_acceptance': False,
        'artifacts': [{'file': path.name, 'bytes': path.stat().st_size, 'sha256': stack.digest(path)}
                      for path in sorted(output.iterdir()) if path.is_file()],
    }
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    if not assembly_equal or not preserved:
        raise ValueError('Lifetime tracing changed assembly or a preserved input; reject this diagnostic.')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Complete C candidate translation unit.')
    parser.add_argument('--function', required=True, help='C function whose storage lifetimes should be observed.')
    parser.add_argument('--output', type=Path, required=True, help='New directory under .decomp-lab.')
    parser.add_argument('--lab-root', type=Path, help='Absolute existing private artifact directory; external roots must be outside Git worktrees.')
    parser.add_argument('--compiler-mode', choices=('g0', 'g8'), default='g8')
    args = parser.parse_args(argv)
    report = trace_candidate(args.source, args.output, args.function, args.compiler_mode, lab_root=args.lab_root)
    print(json.dumps({key: report[key] for key in ('status', 'function', 'lifetime_events',
                                                 'complete_assembly_equal', 'source_promoted')}, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f'error: {error}', file=sys.stderr)
        raise SystemExit(1)
