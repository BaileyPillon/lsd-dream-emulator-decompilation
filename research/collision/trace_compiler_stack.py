"""Trace the bundled compiler's stack allocations without original game inputs.

This is a compiler-layout diagnostic, not a matching-build or gameplay verifier.
The compiler runs normally and under GDB; their complete assembly must agree.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import configure


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def new_output(output):
    output = Path(output).resolve()
    lab = (ROOT / '.decomp-lab').resolve()
    if output == lab or not output.is_relative_to(lab):
        raise ValueError('Choose a fresh private output directory inside .decomp-lab.')
    output.mkdir(parents=True, exist_ok=False)
    return output


def compiler_profile(compiler):
    header = Path(compiler).read_bytes()[:24]
    if (header[:6] != b'\x7fELF\x01\x01' or len(header) < 24
            or int.from_bytes(header[18:20], 'little') != 3):
        raise ValueError('Stack tracing requires the bundled ELF32 little-endian i386 compiler.')
    return {'architecture': 'ELF32 little-endian i386', 'calling_convention': 'cdecl',
            'pointer_bytes': 4, 'sha256': digest(compiler)}


def validate_trace(trace):
    if not trace.get('compiler_exited') or trace.get('compiler_exit_code') != 0:
        raise ValueError('The traced compiler did not exit successfully.')
    events = trace.get('allocation_events')
    if not isinstance(events, list):
        raise ValueError('GDB did not report stack allocation events.')
    for i, event in enumerate(events):
        if (event.get('sequence') != i or not event.get('function')
                or event.get('allocator') not in ('assign_stack_local', 'assign_stack_temp')
                or 'frame_offset_after' not in event):
            raise ValueError('GDB reported an incomplete or invalid stack allocation event.')
    return events


def trace_candidate(source, output, compiler_mode='g8'):
    output = new_output(output)
    if sys.platform == 'win32':
        raise ValueError('Run compiler stack tracing in Linux/WSL.')
    source = Path(source).resolve(strict=True)
    if source.suffix.lower() != '.c':
        raise ValueError('Select a complete C translation unit.')
    if compiler_mode not in ('g0', 'g8'):
        raise ValueError('Compiler mode must be g0 or g8.')
    compiler = Path(configure.CC).resolve(strict=True)
    profile = compiler_profile(compiler)
    gdb = shutil.which('gdb')
    cpp = shutil.which(configure.CROSS + 'cpp')
    if not gdb or not cpp:
        raise ValueError('GDB and the configured MIPS preprocessor must be installed in Linux/WSL.')
    backend = Path(__file__).with_name('compiler_stack_gdb.py')
    cpp_flags = ['-I' + str(source.parent), *configure.CPP_FLAGS]
    flags = configure.C_FLAGS_G8 if compiler_mode == 'g8' else configure.C_FLAGS
    if compiler_mode == 'g8':
        cpp_flags.append('-DCCG8')
    commands = []
    producer = Path(__file__).resolve()
    configuration = Path(configure.__file__).resolve()
    baseline = {str(path): digest(path) for path in (source, compiler, backend, producer, configuration)}

    def run(name, command, env=None):
        commands.append({'stage': name, 'argv': command})
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True)
        (output / (name + '.stdout')).write_bytes(result.stdout)
        (output / (name + '.stderr')).write_bytes(result.stderr)
        if result.returncode:
            raise ValueError(f'{name} failed with exit code {result.returncode}; see its private logs.')
        return result

    cpp_result = run('preprocess', [cpp, *cpp_flags, str(source)])
    preprocessed = output / 'candidate.i'
    preprocessed.write_bytes(cpp_result.stdout)
    normal_assembly = output / 'normal.s'
    traced_assembly = output / 'traced.s'
    run('normal-compiler', [str(compiler), *flags, '-o', str(normal_assembly), str(preprocessed)])
    env = os.environ.copy()
    env['LSD_STACK_TRACE_REPORT'] = str(output / 'allocations.json')
    run('gdb-compiler', [gdb, '--batch', '--quiet', '-x', str(backend), '--args',
                        str(compiler), *flags, '-o', str(traced_assembly), str(preprocessed)], env)
    trace = json.loads((output / 'allocations.json').read_text(encoding='utf-8'))
    events = validate_trace(trace)
    assembly_equal = normal_assembly.read_bytes() == traced_assembly.read_bytes()
    inputs_preserved = all(digest(path) == expected for path, expected in baseline.items())
    report = {
        'status': 'passed_compiler_stack_trace' if assembly_equal and inputs_preserved else 'failed',
        'scope': 'Actual compiler allocator calls; no original executable, native game execution, matching-C promotion or feature acceptance.',
        'source': str(source), 'source_sha256': baseline[str(source)],
        'compiler_mode': compiler_mode, 'compiler_profile': profile,
        'backend_sha256': baseline[str(backend)], 'commands': commands,
        'producer_sha256': baseline[str(producer)],
        'configuration_sha256': baseline[str(configuration)],
        'gdb_version': subprocess.check_output([gdb, '--version'], text=True).splitlines()[0],
        'allocation_events': len(events),
        'functions': sorted({event['function'] for event in events}),
        'complete_assembly_equal': assembly_equal,
        'normal_assembly_sha256': digest(normal_assembly),
        'traced_assembly_sha256': digest(traced_assembly),
        'source_compiler_and_backend_preserved': inputs_preserved,
        'producer_and_configuration_preserved': inputs_preserved,
        'source_promoted': False, 'whole_feature_acceptance': False,
        'artifacts': [{'file': path.name, 'bytes': path.stat().st_size, 'sha256': digest(path)}
                      for path in sorted(output.iterdir()) if path.is_file()],
    }
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    if not assembly_equal or not inputs_preserved:
        raise ValueError('Compiler tracing changed assembly or a preserved input; reject this diagnostic.')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Complete C candidate translation unit.')
    parser.add_argument('--output', type=Path, required=True, help='New directory under .decomp-lab.')
    parser.add_argument('--compiler-mode', choices=('g0', 'g8'), default='g8')
    args = parser.parse_args(argv)
    report = trace_candidate(args.source, args.output, args.compiler_mode)
    print(json.dumps({key: report[key] for key in ('status', 'allocation_events', 'functions',
                                                 'complete_assembly_equal', 'source_promoted')}, indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f'error: {error}', file=sys.stderr)
        raise SystemExit(1)
