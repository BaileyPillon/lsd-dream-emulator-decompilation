"""Compare a confined bounds C candidate with original code and the scalar model.

Requires the complete private workbench image and its sized diagnostic ELF.
Agreement on constructed inputs does not accept a nonmatching source function.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import configure
from research.compiler.compare_function import elf_function
from tools import verify_native_ai as n
from tools import verify_render_bounds as bounds
from tools import verify_scripted_ai as scripts

ADDRESS, LENGTH = 0x8004CD38, 108


def new_output(path):
    output, lab = Path(path).resolve(), (ROOT / '.decomp-lab').resolve()
    if output == lab or not output.is_relative_to(lab) or output.exists():
        raise ValueError('Choose a fresh private output directory inside .decomp-lab.')
    return output


def validate_image(original, image, code, offset):
    if len(code) != LENGTH or offset < 0 or offset + LENGTH > len(original):
        raise ValueError('Require the complete original 108-byte function extent.')
    if len(image) != len(original) or image[:offset] != original[:offset] or image[offset + LENGTH:] != original[offset + LENGTH:]:
        raise ValueError('Candidate changes image length or bytes outside the bounds function.')
    if image[offset:offset + LENGTH] != code:
        raise ValueError('Sized ELF function bytes differ from the candidate image.')
    return {ADDRESS + i for i in range(0, LENGTH, 4) if code[i:i + 4] != original[offset + i:offset + i + 4]}


def fault_specifications(code):
    if len(code) != LENGTH:
        raise ValueError('Review controls for a different bounds function extent.')
    words = list(struct.unpack('<27I', code))
    shifts = [i for i, word in enumerate(words) if word & 0xFC00003F == 3 and (word >> 6) & 31 == 24]
    minima = [i for i, word in enumerate(words) if word >> 26 == 33 and word & 0xFFFF == 0]
    maxima = [i for i, word in enumerate(words) if word >> 26 == 35 and word & 0xFFFF == 8]
    comparisons = [i for i, word in enumerate(words) if word & 0xFC00003F == 42]
    if (len(shifts), len(minima), len(maxima), len(comparisons)) != (4, 1, 1, 4):
        raise ValueError('Review controls for a different bounds instruction layout.')
    x, minimum, maximum, comparison = shifts[0], minima[0], maxima[0], comparisons[1]
    return [('unsigned_x_unpack', x, (words[x] & ~63) | 2),
            ('unsigned_minimum_x', minimum, (words[minimum] & 0x03FFFFFF) | (37 << 26)),
            ('wrong_maximum_z_field', maximum, (words[maximum] & 0xFFFF0000) | 4),
            ('unsigned_maximum_x_compare', comparison, (words[comparison] & ~63) | 43)]


class Machine(bounds.Machine):
    def __init__(self, replacement=None):
        self.hits = Counter()
        super().__init__(replacement)

    def hook(self, cpu, pc, size, unused):
        physical = pc & n.MASK
        if not self.start <= physical < self.start + LENGTH:
            raise ValueError('Bounds execution left its complete sized function.')
        self.hits[physical] += 1
        super().hook(cpu, pc, size, unused)


def verify(output, candidate, symbols):
    output = new_output(output)
    paths = n.evidence_dependencies('research/render_bounds/compare_candidate.py',
        'research/render_bounds/bounds_candidate.c', 'research/render_bounds/prepare_candidate.py',
        'research/compiler/compare_function.py', 'tools/verify_render_bounds.py', 'tools/verify_scripted_ai.py',
        'src/scene/render_context.c', 'src/scene/render_context.h', 'tools/gcc263/cc1')
    candidate, symbols = Path(candidate).resolve(strict=True), Path(symbols).resolve(strict=True)
    paths = list(dict.fromkeys([*paths, candidate, symbols]))
    preserved = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    program = n.load_program(bounds.FUNCTIONS)
    image = candidate.read_bytes()
    code, qualification = elf_function(symbols.read_bytes(), 'func_8004CD38', ADDRESS)
    offset = 0x800 + ADDRESS - program.LOAD
    changed = validate_image(program.ROM, image, code, offset)
    controls = fault_specifications(code)
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'symbol-image.log').open('xb') as log:
        subprocess.run([configure.CROSS + 'objcopy', '-O', 'binary', str(symbols), str(output / 'symbol-image.exe')],
                       check=True, stdout=log, stderr=log)
    if (output / 'symbol-image.exe').read_bytes() != image:
        raise ValueError('Retaining symbols changed the complete candidate image.')
    n.initialize_backend(program)
    backend = scripts.backend_identity()
    original, replacement = Machine(), Machine(code)
    references, groups, paths_taken, initialized = [], Counter(), Counter(), set()
    digest, input_digest = hashlib.sha256(), hashlib.sha256()
    for group, case in bounds.cases():
        model = bounds.expected(case)
        expected, actual = original.run(case), replacement.run(case)
        if expected != model[:3] or actual != expected:
            raise ValueError('Bounds candidate/reference/model disagreement: ' + repr(case))
        references.append((case, expected))
        buffers, bounds_pointer, point_pointer = bounds.fixtures(case)
        segment = case.get('segment', 0)
        key = b''.join(buffers) + struct.pack('<II', bounds_pointer | segment if bounds_pointer else 0, point_pointer | segment)
        initialized.add(hashlib.sha256(key).hexdigest())
        input_digest.update(len(key).to_bytes(4, 'little') + key)
        digest.update(repr(actual).encode('utf-8'))
        groups[group] += 1
        paths_taken[model[3]] += 1
    if not references or any(not replacement.hits[pc & n.MASK] for pc in changed):
        raise ValueError('Every differing instruction must execute in the positive domain.')
    faults = []
    for name, index, word in controls:
        broken = bytearray(code)
        struct.pack_into('<I', broken, index * 4, word)
        machine = Machine(bytes(broken))
        for attempt, (case, expected) in enumerate(references, 1):
            machine.hits.clear()
            actual = machine.run(case)
            if actual[1] != expected[1]:
                pc = ADDRESS + index * 4
                if not machine.hits[pc & n.MASK]:
                    raise ValueError('A detecting fault instruction did not execute.')
                faults.append(dict(kind=name, address=hex(pc), changed_instruction_hits=machine.hits[pc & n.MASK],
                    wrong_return=True, expected_return=expected[1], actual_return=actual[1],
                    detecting_case=case, attempted_existing_fixtures=attempt))
                break
        else:
            raise ValueError('No wrong return from candidate fault: ' + name)
    if (scripts.backend_identity() != backend or (ROOT / configure.ROM).read_bytes() != program.ROM
            or (ROOT / configure.EXE).read_bytes() != program.ROM or not n.check_build_current(ROOT)
            or any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path, digest in preserved.items())):
        raise ValueError('Source, candidate, backend or canonical build changed during comparison.')
    source_dependencies = []
    for path, value in preserved.items():
        if path.is_relative_to(ROOT):
            source_dependencies.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=value))
    report = dict(status='passed_bounded_bounds_candidate_comparison', fixture_records=len(references),
        distinct_initialized_inputs=len(initialized), positive_executions=2 * len(references),
        fixture_groups=dict(groups), return_paths=dict(paths_taken), initialized_inputs_sha256=input_digest.hexdigest(),
        checked_buffers_return_and_read_trace_sha256=digest.hexdigest(),
        function_address=hex(ADDRESS), complete_function_bytes=len(code),
        original_function_sha256=hashlib.sha256(program.target(ADDRESS, LENGTH)).hexdigest(),
        candidate_function_sha256=hashlib.sha256(code).hexdigest(),
        candidate_image_sha256=hashlib.sha256(image).hexdigest(),
        candidate_symbols_sha256=hashlib.sha256(symbols.read_bytes()).hexdigest(),
        complete_image_bytes=len(image), complete_image_differing_bytes=sum(a != b for a, b in zip(image, program.ROM)),
        all_bytes_outside_selected_function_canonical=True, symbol_image_matches_candidate=True,
        differing_instruction_positive_hits={hex(pc): replacement.hits[pc & n.MASK] for pc in sorted(changed)},
        all_differing_instructions_observed=True, negative_controls=faults, dependency_output_stubs=0,
        backend_identity=backend, producer_dependencies=source_dependencies,
        source_promoted=False, new_C_bytes=0, new_distinct_original_fixture_inputs=0,
        new_bounded_NPC_callbacks=0, new_whole_features_accepted=0, model_API_calls=0,
        scope='Existing constructed scalar bounds inputs only: full guarded buffers, result, ordered reads and widths, '
              'zero writes, SP/GP/RA/saved registers and confined PC. No renderer/stage composition, natural scenes, '
              'framebuffer/audio, PS1 timing or matching-source acceptance.')
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--symbols', type=Path, required=True)
    args = parser.parse_args(argv)
    report = verify(args.output, args.candidate, args.symbols)
    print(json.dumps({key: report[key] for key in ('status', 'fixture_records', 'distinct_initialized_inputs',
                                                  'complete_image_differing_bytes')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
