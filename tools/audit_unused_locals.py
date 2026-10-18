"""Collect canonical GCC unused-local diagnostics without changing game inputs.

Diagnostics are source-quality leads. They do not prove frame dependence,
recover original declarations or certify the absence of other workarounds.
All preprocessed source, assembly and compiler output remains private.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import configure
from tools.decomp_workbench import candidate_commands
from tools.progress import build_manifest, collect_progress
from research.compiler.compare_function import CANONICAL_SHA256

COMPILER_SHA256 = '3a7378955ab79dbe06cc413cc10b757777fd07b7b72bce76faf432d255da7fab'
CONTEXT = re.compile(r"In function [`']([A-Za-z_]\w*)'")
WARNING = re.compile(r"^(.+?):([1-9]\d*):\s+warning:\s+unused variable [`']([A-Za-z_]\w*)'\s*$")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def parse_diagnostics(text):
    """Reject an unparsed unused-variable diagnostic rather than undercount it."""
    function, records = None, []
    for line in text.splitlines():
        context = CONTEXT.search(line)
        if context:
            function = context[1]
        if 'unused variable' not in line:
            continue
        warning = WARNING.fullmatch(line)
        if warning is None or function is None:
            raise ValueError('Unsupported or unowned compiler unused-variable diagnostic: ' + line)
        records.append(dict(function=function, source=warning[1], line=int(warning[2]), variable=warning[3]))
    return records


def private_output(path, root=ROOT):
    path, lab = Path(path).resolve(), (Path(root) / '.decomp-lab').resolve()
    if path == lab or not path.is_relative_to(lab) or path.exists():
        raise ValueError('Choose a fresh output directory inside .decomp-lab; existing evidence is preserved.')
    return path


def compiler_identity(path):
    data = Path(path).read_bytes()
    if digest(data) != COMPILER_SHA256:
        raise ValueError('Use the exact bundled GCC 2.6.3 compiler.')
    return digest(data)


def audit(output):
    output = private_output(output)
    if sys.platform != 'linux':
        raise ValueError('Run the canonical compiler audit in Linux/WSL.')
    compiler = compiler_identity(configure.CC)
    before = collect_progress(ROOT)
    if before['binary_match'] != 'verified':
        raise ValueError('A complete current matching build is required.')
    executable = (ROOT / configure.ROM).read_bytes()
    if digest(executable) != CANONICAL_SHA256 or executable != (ROOT / configure.EXE).read_bytes():
        raise ValueError('The complete original and rebuilt executable must agree.')
    units = [source for source, kind in build_manifest() if kind == 'C']
    if not units or len(units) != len(set(units)):
        raise ValueError('Require unique configured game C translation units.')
    dependencies = (Path(__file__).resolve(), ROOT / 'configure.py', ROOT / 'tools/decomp_workbench.py',
                    ROOT / 'tools/progress.py', Path(configure.CC))
    pins = {str(path): digest(path.read_bytes()) for path in dependencies}
    output.mkdir(parents=True, exist_ok=False)
    records = []
    (output / 'progress-before.json').write_text(json.dumps(before, indent=2) + '\n', encoding='utf-8')
    for index, unit in enumerate(units):
        folder = output / str(index).zfill(3)
        folder.mkdir()
        source = ROOT / unit
        commands = candidate_commands(unit, source, folder / 'unused.o')
        if '-Wall' not in commands[1]:
            raise ValueError('The configured compiler must retain its ordinary -Wall setting.')
        cpp = subprocess.run(commands[0], cwd=ROOT, capture_output=True)
        (folder / 'preprocessor.log').write_bytes(cpp.stderr)
        if cpp.returncode:
            raise ValueError('Preprocessing failed for ' + unit)
        preprocessed = folder / 'candidate.i'
        preprocessed.write_bytes(cpp.stdout)
        assembly = folder / 'canonical.s'
        command = [*commands[1], '-o', str(assembly), str(preprocessed)]
        compiled = subprocess.run(command, cwd=ROOT, capture_output=True)
        (folder / 'compiler.stdout').write_bytes(compiled.stdout)
        (folder / 'compiler.log').write_bytes(compiled.stderr)
        if compiled.returncode or compiled.stdout:
            raise ValueError('Canonical compiler failed for ' + unit)
        warnings = parse_diagnostics(compiled.stderr.decode('utf-8'))
        for warning in warnings:
            path = Path(warning['source'])
            path = path.resolve() if path.is_absolute() else (ROOT / path).resolve()
            if not path.is_relative_to(ROOT) or not path.is_file():
                raise ValueError('An unused-local warning has no retained project source.')
            warning['source'] = path.relative_to(ROOT).as_posix()
        row = dict(source=unit, source_sha256=digest(source.read_bytes()), preprocessed_sha256=digest(cpp.stdout),
                   compiler_command=command, configured_compiler_flags=commands[1][1:],
                   compiler_flags_changed=False, compiler_log_sha256=digest(compiled.stderr),
                   assembly_sha256=digest(assembly.read_bytes()), unused_local_warnings=warnings)
        records.append(row)
        with (output / 'progress.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row) + '\n')
        if (index + 1) % 16 == 0:
            print(json.dumps(dict(compiled_units=index + 1, total=len(units))), flush=True)
    after = collect_progress(ROOT)
    if after != before or any(digest(Path(path).read_bytes()) != value for path, value in pins.items()):
        raise ValueError('A protected build input, compiler or audit producer changed.')
    counts = Counter(warning['source'] for row in records for warning in row['unused_local_warnings'])
    report = dict(schema_version=1, status='collected_canonical_compiler_unused_local_diagnostics',
                  canonical_executable_sha256=CANONICAL_SHA256, canonical_compiler_sha256=compiler,
                  configured_game_C_translation_units=len(units), compiler_flags_changed=False,
                  total_unused_local_warnings=sum(counts.values()), warning_source_counts=dict(counts), rows=records,
                  protected_build_input_sha256=before['build_input_sha256'], complete_build_objects=before['objects_found'],
                  c_bytes=before['c_bytes'], game_text_bytes=before['game_text_bytes'],
                  all_game_inputs_preserved=True, matching_executable_preserved=True,
                  producer_dependency_sha256=pins, source_promoted=False, new_C_bytes=0,
                  original_gameplay_executed=False, entire_features_accepted=0,
                  scope='All configured game C units with ordinary compiler flags. Diagnostics are leads; separately qualify storage and exact removals. No exhaustive source-workaround certification.')
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = audit(args.output)
        print(json.dumps({key: report[key] for key in ('status', 'configured_game_C_translation_units',
            'total_unused_local_warnings', 'new_C_bytes')}), flush=True)
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
