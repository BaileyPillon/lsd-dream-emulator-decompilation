"""Observe and qualify allocation decisions in the bundled compiler; no game execution."""
import argparse
import difflib
import hashlib
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

COMPILER_SHA256 = '3a7378955ab79dbe06cc413cc10b757777fd07b7b72bce76faf432d255da7fab'
BACKEND = Path(__file__).with_name('allocation_gdb.py')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_compiler(path):
    compiler = Path(path).resolve(strict=True)
    if sha256(compiler) != COMPILER_SHA256:
        raise ValueError('Unsupported compiler; only the exact bundled i386 GCC 2.6.3 is supported.')
    return compiler


def require_output(path, lab):
    output, lab = Path(path).resolve(), Path(lab).resolve()
    if output == lab or not output.is_relative_to(lab):
        raise ValueError('Choose a fresh directory inside .decomp-lab.')
    if output.exists():
        raise FileExistsError('Existing evidence cannot be overwritten: ' + str(output))
    return output


def allocation_priority(item):
    refs, length, size = item['references'], item['live_length'], item['size']
    if refs <= 0 or length <= 0 or size <= 0:
        raise ValueError('Invalid global allocation priority operands.')
    # GCC 2.6.3 global.c: floor_log2(refs) * refs / live_length * 10000 * size.
    return int((refs.bit_length() - 1) * refs / length * 10000 * size)


def register_dispositions(dump, function):
    matches = re.findall(r'^;; Function ' + re.escape(function) + r'\n(.*?)(?=^;; Function |\Z)', dump, re.M | re.S)
    if len(matches) != 1:
        raise ValueError('The selected function must appear exactly once in the compiler dump.')
    try:
        section = matches[0].split(';; Register dispositions:', 1)[1].split(';; Hard regs used:', 1)[0]
    except IndexError as error:
        raise ValueError('Missing register dispositions.') from error
    return {int(a): int(b) for a, b in re.findall(r'(\d+) in (\d+)', section)}


def validate_observation(trace, normal, traced, diagnostic, dump, function):
    if (trace.get('target') != function or trace.get('compiler_exited') is not True or
            trace.get('compiler_exit_code') != 0):
        raise ValueError('The selected compiler run did not finish successfully.')
    if (trace.get('explicit_inferior_memory_writes_or_opcode_substitutions') is not False or
            trace.get('extra_inferior_functions_invoked') is not False or
            trace.get('normal_debugger_breakpoint_machinery') is not True):
        raise ValueError('Unsupported observer mutation or invocation policy.')
    local = trace.get('local_events', [])
    equiv = trace.get('equivalence_events', [])
    if len(local) != 1 or len(equiv) != 1 or any('after' not in e for e in local + equiv):
        raise ValueError('Missing or incomplete local allocation/equivalence observation.')
    if normal != traced:
        raise ValueError('Debugger observation changed the complete compiler assembly.')
    changes = [line for line in difflib.ndiff(normal.decode().splitlines(), diagnostic.decode().splitlines())
               if line.startswith(('+ ', '- '))]
    if any(not line[2:].lstrip().startswith('#') for line in changes):
        raise ValueError('RTL diagnostic options changed emitted instructions.')
    dispositions = register_dispositions(dump, function)
    for pseudo, item in local[0]['after'].items():
        hard = item['hard_register']
        if hard >= 0 and dispositions.get(int(pseudo)) != hard:
            raise ValueError('Local allocation disagrees with the final compiler dump.')
    allocations = trace.get('allocation_events', [])
    for item in allocations:
        if 'hard_register_after' not in item:
            raise ValueError('A global allocation never returned.')
        if (not item['alternate_class'] and not item['retrying'] and
                dispositions.get(item['pseudo'], -1) != item['hard_register_after']):
            raise ValueError('Global allocation disagrees with the final compiler dump.')
    comparisons = trace.get('comparison_events', [])
    for event in comparisons:
        left, right = event['left'], event['right']
        expected = allocation_priority(right) - allocation_priority(left) or left['allocno'] - right['allocno']
        if event.get('returned_comparison') != expected:
            raise ValueError('Observed global comparison disagrees with the reference priority calculation.')
    return {'local_allocations': len(local), 'equivalence_updates': len(equiv),
            'global_allocations': len(allocations), 'priority_comparisons': len(comparisons),
            'complete_assembly_equal': True, 'register_dispositions_agree': True,
            'reference_priority_comparisons_agree': True, 'diagnostic_option_comment_changes': changes}


def trace_source(source, output, function, compiler_mode='g8'):
    if not re.fullmatch(r'[A-Za-z_]\w*', function):
        raise ValueError('Select a C function identifier.')
    source = Path(source).resolve(strict=True)
    compiler = require_compiler(configure.CC)
    output = require_output(output, ROOT / '.decomp-lab')
    cpp, gdb = shutil.which(configure.CROSS + 'cpp'), shutil.which('gdb')
    if not cpp or not gdb:
        raise RuntimeError('Run in the Linux/WSL build environment with the MIPS preprocessor and GDB.')
    flags = list(configure.C_FLAGS_G8 if compiler_mode == 'g8' else configure.C_FLAGS)
    inputs = {str(p): sha256(p) for p in (source, compiler, BACKEND, Path(__file__), Path(configure.__file__))}
    output.mkdir(parents=True, exist_ok=False)
    commands = []

    def run(stage, command, env=None):
        commands.append({'stage': stage, 'argv': command})
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True)
        (output / (stage + '.stdout')).write_bytes(result.stdout)
        (output / (stage + '.stderr')).write_bytes(result.stderr)
        if result.returncode:
            raise RuntimeError(stage + ' failed; retained its logs in ' + str(output))
        return result

    preprocessed = output / 'candidate.i'
    preprocessed.write_bytes(run('preprocess', [cpp, *configure.CPP_FLAGS,
                            *(['-DCCG8'] if compiler_mode == 'g8' else []), str(source)]).stdout)
    run('normal-compiler', [str(compiler), *flags, '-o', str(output / 'normal.s'), str(preprocessed)])
    env = os.environ.copy()
    env['LSD_GLOBAL_TRACE_FUNCTION'] = function
    env['LSD_GLOBAL_TRACE_REPORT'] = str(output / 'allocations.json')
    run('observed-compiler', [gdb, '--batch', '--quiet', '-x', str(BACKEND), '--args', str(compiler),
                            *flags, '-o', str(output / 'observed.s'), str(preprocessed)], env)
    run('diagnostic-compiler', [str(compiler), *flags, '-da', '-dumpbase', str(output / 'diagnostic'),
                              '-o', str(output / 'diagnostic.s'), str(preprocessed)])
    observation = json.loads((output / 'allocations.json').read_text())
    qualification = validate_observation(observation, (output / 'normal.s').read_bytes(),
                         (output / 'observed.s').read_bytes(), (output / 'diagnostic.s').read_bytes(),
                         (output / 'diagnostic.greg').read_text(), function)
    if any(sha256(path) != digest for path, digest in inputs.items()):
        raise ValueError('An observed input changed during the run.')
    report = {'schema_version': 1, 'status': 'passed_actual_compiler_allocation_observation',
              'function': function, 'source': str(source), 'compiler_mode': compiler_mode,
              'compiler_sha256': COMPILER_SHA256, 'input_hashes': inputs, 'commands': commands,
              'qualification': qualification, 'source_promoted': False,
              'original_game_executed': False, 'model_api_calls': 0,
              'artifacts': [{'file': p.name, 'bytes': p.stat().st_size, 'sha256': sha256(p)}
                            for p in sorted(output.iterdir()) if p.is_file()]}
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
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
