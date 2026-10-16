"""Compare unaccepted grid C builds through actual lookup, SDK and streaming code.

Requires private complete candidate builds and the pinned native GTE bridge.
This extends bounded candidate evidence; it neither promotes source nor checks
natural scene ownership, GPU output, PS1 timing or whole-game parity.
"""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research.compiler.compare_function import elf_function
from tools import verify_render_gte as gte
from tools.verify_scripted_ai import backend_identity

native, grid, rotation, position = gte.native, gte.grid, gte.rotation, gte.position
TARGET = grid.FUNCTIONS[0]
ADDRESS = int(TARGET['address'], 16)
DISTANCES = (-2147483648, -2147483647, -1073741824, -65536, -32768,
             32767, 32768, 65536, 1073741824, 2147483647)
YAWS = (0x1FF, 0x200, 0x5FF, 0x600, 0x9FF, 0xA00, 0xDFF, 0xE00,
        0xF800, 0xFFFF, 0x8000)
DIMENSIONS = ((1, 1), (20, 20), (21, 19), (0, 0), (-3, 4))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def selected_body(original, candidate, offset, length):
    """Reject image truncation and all changes outside the qualified function."""
    if len(candidate) != len(original):
        raise ValueError('The candidate must retain the complete executable length.')
    if offset < 0 or length <= 0 or offset + length > len(original):
        raise ValueError('The complete selected extent must lie inside the image.')
    if original[:offset] != candidate[:offset] or original[offset + length:] != candidate[offset + length:]:
        raise ValueError('The candidate changes bytes outside the selected grid function.')
    return candidate[offset:offset + length]


def load_candidate(build, program):
    build = Path(build).resolve()
    if not build.is_relative_to((ROOT / '.decomp-lab').resolve()):
        raise ValueError('Candidate builds must remain inside private .decomp-lab.')
    image_path, elf_path = build / 'candidate.exe', build / 'candidate-symbols.elf'
    comparison_path = build / 'comparison.json'
    image, elf = image_path.read_bytes(), elf_path.read_bytes()
    comparison = json.loads(comparison_path.read_text(encoding='utf-8'))
    source = Path(comparison['candidate']).resolve()
    if not source.is_relative_to((ROOT / '.decomp-lab').resolve()):
        raise ValueError('Require the private complete source used by the workbench.')
    diagnostic = comparison['function_diagnostics']
    if (comparison['source'] != 'src/scene/render_context.c'
            or comparison['candidate_sha256'] != digest(source.read_bytes())
            or diagnostic['function'] != TARGET['function']
            or diagnostic['elf_sha256'] != digest(elf)
            or diagnostic['candidate_executable_sha256'] != digest(image)
            or diagnostic['diagnostic_executable_sha256'] != digest(image)
            or diagnostic['diagnostic_image_matches_candidate'] is not True):
        raise ValueError('Current candidate artifacts disagree with their workbench record.')
    offset = 0x800 + ADDRESS - program.LOAD
    body = selected_body(program.ROM, image, offset, TARGET['bytes'])
    qualified, _ = elf_function(elf, TARGET['function'], ADDRESS)
    if len(qualified) != TARGET['bytes'] or qualified != body:
        raise ValueError('Require the whole sized ELF function, identical to the full candidate image.')
    original = program.target(ADDRESS, TARGET['bytes'])
    changed = [ADDRESS + i for i in range(0, len(body), 4) if body[i:i + 4] != original[i:i + 4]]
    return body, changed, dict(image_sha256=digest(image), elf_sha256=digest(elf),
        source_sha256=digest(source.read_bytes()), function_sha256=digest(body),
        function_bytes=len(body), differing_bytes=sum(a != b for a, b in zip(body, original)),
        changed_instruction_addresses=[hex(a) for a in changed],
        complete_executable_equal=image == program.ROM), [image_path, elf_path, comparison_path, source]


def extension_cases(pairs):
    """Distinct graph inputs with real long-vector projection and clipped sizes."""
    for label, yaw, distance, dimensions, segment in itertools.product(
            range(7), YAWS, DISTANCES, DIMENSIONS, (0, 0x80000000, 0xA0000000)):
        width, height = dimensions
        index = YAWS.index(yaw) + DISTANCES.index(distance) + DIMENSIONS.index(dimensions)
        cell_x, cell_z = ((0, 19), (19, 0), (9, 19), (19, 9), (0, 0))[index % 5]
        euler = ((0, 1, -1, 513, -1025, 4095, -32768)[label], yaw,
                 (0, -513, 1025, -4095, 32767, -1, 1)[label])
        matrix = struct.unpack('<9h', rotation.rotation_bytes(euler, pairs))
        projected, _ = gte.apply_model(matrix, (0, 0, distance))
        yield dict(position.base_case(position=(label * 40960 + cell_x * 2048 + 1024,
            -label * 2048, cell_z * 2048 + 1024), angle=yaw, distance=distance,
            width=width, height=height, radius=(1, 4, 9)[index % 3],
            projected_x=projected[0], projected_y=projected[1], projected_z=projected[2],
            labels=tuple(range(7)) if index % 2 else (6, 2, 5, 1, 4, 0, 3),
            segment=segment, mode=label % 2, seed=label, auxiliary_present=False), euler=euler)


def fixture_identity(case):
    buffers, pointers, template, _ = rotation.composition_fixture(case)
    data = b''.join(name.encode('ascii') + bytes(value) for name, value in sorted(buffers.items()))
    # Width and height enter through A1/A2, not through initialized graph fields.
    data += struct.pack('<II', native.u32(case['width']), native.u32(case['height']))
    return digest(data + template + json.dumps(pointers, sort_keys=True).encode('ascii'))


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      default=lambda item: {'bytes_hex': bytes(item).hex()}).encode('ascii')


class TrackedMachine(gte.CompositionMachine):
    def __init__(self, bridge, patches=None, tracked=()):
        self.hits = Counter({address & native.MASK: 0 for address in tracked})
        super().__init__(bridge, patches=patches)

    def hook(self, cpu, address, size, unused):
        if address & native.MASK in self.hits:
            self.hits[address & native.MASK] += 1
        super().hook(cpu, address, size, unused)


def fault_controls(bridge, candidates, pairs):
    """Require executed changed words and wrong graph/matrix bytes."""
    records = []
    specifications = (
        ('edge', 'inclusive_x_end', 0x8004C7D4, 0x26A20001, 0x26A20002, 0xA00, 0),
        ('cell', 'inclusive_z_end', 0x8004C890, 0x26C20001, 0x26C20002, 0x600, 0),
        ('edge', 'wrong_x_coordinate_byte', 0x8004C700, 0x83B50012, 0x83B50013, 0xA00, 0),
        ('cell', 'wrong_z_coordinate_byte', 0x8004C700, 0x83B60013, 0x83B60012, 0x600, 0),
        ('original', 'wrong_sdk_high_z_scale', 0x80015748, 0x000D68C0, 0x000D6880, 0, 65537),
    )
    for image, name, address, word, changed, yaw, distance in specifications:
        patches = {} if image == 'original' else {ADDRESS: candidates[image][0]}
        runner = TrackedMachine(bridge, patches=patches, tracked=(address,))
        physical = address & native.MASK
        if bytes(runner.cpu.mem_read(physical, 4)) != struct.pack('<I', word):
            raise ValueError('Control word differs from its qualified positive image: ' + name)
        runner.cpu.mem_write(physical, struct.pack('<I', changed))
        case = next(case for case in gte.composition_cases(pairs)
                    if case['angle'] == yaw and case['distance'] == distance
                    and position.selected_label(case) == 0
                    and case['position'][0] != case['position'][2])
        expected = rotation.composition_expected(case, pairs)[0]
        actual = runner.run(case)
        if not runner.hits[physical] or (actual[0] == expected[0] and actual[4] == expected[4]):
            raise ValueError('Control needs changed-word execution and wrong graph/matrix bytes: ' + name)
        records.append(dict(name=name, image=image, address=hex(address), changed_word_hits=runner.hits[physical],
                            wrong_graph_buffers=actual[0] != expected[0], wrong_projected_matrix=actual[4] != expected[4],
                            original_word=hex(word), fault_word=hex(changed)))
    return records


def verify(destination, edge_build, cell_build, executable, runtime):
    program = native.load_program(gte.FUNCTIONS)
    candidates = {name: load_candidate(build, program) for name, build in (('edge', edge_build), ('cell', cell_build))}
    dependencies = native.evidence_dependencies('tools/verify_render_grid_candidates.py',
        'tools/verify_render_gte.py', 'tools/verify_render_rotation.py', 'tools/verify_render_position.py',
        'tools/verify_render_stream.py', 'tools/verify_render_grid.py', 'tools/verify_scripted_ai.py',
        'research/compiler/compare_function.py', 'tools/decomp_workbench.py',
        'research/render_grid/c6a8_candidate.c', 'research/render_grid/c6a8_cell_reuse_candidate.c',
        'src/scene/render_context.c', 'src/scene/render_context.h', 'tools/nymashock_gte_bridge.cs',
        'tools/build_nymashock_gte_bridge.ps1')
    dependencies += [Path(executable), *(path for value in candidates.values() for path in value[3])]
    before = {path: digest(path.read_bytes()) for path in dependencies}
    native.initialize_backend(program)
    backend = backend_identity()
    pairs = rotation.table_pairs(program)
    bindings = position.canonical_bindings(program)
    bridge = gte.NativeGteBridge(executable, runtime, destination.with_suffix('.log'))
    try:
        runners = {'original': TrackedMachine(bridge)}
        runners.update({name: TrackedMachine(bridge, {ADDRESS: item[0]}, item[1]) for name, item in candidates.items()})
        for name, runner in runners.items():
            image = program.ROM if name == 'original' else (Path(edge_build if name == 'edge' else cell_build) / 'candidate.exe').read_bytes()
            if bytes(runner.cpu.mem_read(program.LOAD & native.MASK, len(image) - 0x800)) != image[0x800:]:
                raise ValueError('The initial VM does not contain its complete positive image: ' + name)
        seen, groups, axes, rectangles, flags = set(), Counter(), Counter(), Counter(), Counter()
        snapshots = {name: hashlib.sha256() for name in runners}
        controls = fault_controls(bridge, candidates, pairs)
        for group, cases in (('retained_original_composition', gte.composition_cases(pairs)),
                             ('long_distance_dimension_yaw_graphs', extension_cases(pairs))):
            for case in cases:
                identity = fixture_identity(case)
                if identity in seen:
                    raise ValueError('Repeated actual initialized graph/argument inputs need classification.')
                seen.add(identity)
                expected, axis, rectangle_count = rotation.composition_expected(case, pairs)
                commands = None
                for name, runner in runners.items():
                    actual = runner.run(case)
                    if actual != expected or (commands is not None and runner.adapter.commands != commands):
                        with destination.with_name(destination.stem + '-failure.json').open('xb') as failure:
                            failure.write(encode(dict(image=name, case=case, expected=expected, actual=actual,
                                                      commands=runner.adapter.commands)) + b'\n')
                        raise ValueError('Whole graph/trace comparison differs; private failure retained: ' + name)
                    commands = runner.adapter.commands
                    snapshots[name].update(bytes.fromhex(identity) + encode(actual))
                for entry in commands:
                    flags[str(entry['output']['flags'])] += 1
                groups[group] += 1
                axes[axis] += 1
                rectangles[rectangle_count] += 1
                if len(seen) % 1000 == 0:
                    print(json.dumps(dict(cases_per_image=len(seen), native_commands=bridge.count)), flush=True)
        for name, runner in runners.items():
            if name != 'original' and any(not count for count in runner.hits.values()):
                raise ValueError('A candidate changed instruction was never executed: ' + name)
            for function in gte.FUNCTIONS:
                address, length = int(function['address'], 16), function['bytes']
                expected = candidates[name][0] if name != 'original' and address == ADDRESS else program.target(address, length)
                if runner.read(address, length) != expected:
                    raise ValueError('Positive function bytes changed during comparison: ' + name)
            if runner.read(int(rotation.TABLE['address'], 16), rotation.TABLE['bytes']) != program.target(
                    int(rotation.TABLE['address'], 16), rotation.TABLE['bytes']):
                raise ValueError('The packed rotation table changed during comparison.')
    finally:
        bridge.close()
    if (any(digest(path.read_bytes()) != value for path, value in before.items())
            or backend_identity() != backend or native.load_program(gte.FUNCTIONS).ROM != program.ROM):
        raise ValueError('An input, backend or canonical build changed during comparison.')
    report = dict(status='passed_bounded_grid_candidate_native_composition',
        cases_per_image=len(seen), executions=len(seen) * len(runners), case_groups=dict(groups),
        original_and_current_build_equal=True, original_behavior_modified=False,
        candidate_builds={name: item[2] for name, item in candidates.items()},
        function_ranges=gte.FUNCTIONS, pipeline_function_bytes=sum(row['bytes'] for row in gte.FUNCTIONS),
        function_output_contracts=[], axes=dict(axes), emitted_rectangle_counts=dict(rectangles),
        executed_entry_counts={name: dict(runner.entry_counts) for name, runner in runners.items()},
        candidate_changed_instruction_hits={name: {hex(address | 0x80000000): count for address, count in runner.hits.items()}
                                            for name, runner in runners.items() if name != 'original'},
        graph_and_trace_sha256={name: value.hexdigest() for name, value in snapshots.items()},
        negative_controls=controls, backend_identity=backend, canonical_virtual_bindings=bindings,
        native_gte=dict(compressed_core_sha256=gte.CORE_SHA256, bridge_sha256=digest(Path(executable).read_bytes()),
            actual_command_invocations_excluding_identity_self_check=bridge.count,
            command_flag_counts_per_positive_image=dict(flags), hardware_command_cache=False,
            stdout_log_sha256=digest(destination.with_suffix('.log').read_bytes()),
            stderr_log_sha256=digest(destination.with_name(destination.stem + '-stderr.log').read_bytes())),
        producer_dependencies=[dict(path=path.relative_to(ROOT).as_posix(), sha256=value) for path, value in before.items()],
        source_promotions=0, new_C_bytes=0, original_feature_groups_accepted=0,
        scope='Original and two compiled C images run through the existing eleven-function native-GTE composition. '
              'Each hardware command executes in the pinned native core and is checked against independent integer arithmetic. '
              'Retained graph inputs are repeated for the candidates; the extension combines signed long distances, yaw boundaries, '
              'dimensions and valid world positions. No natural scene, GPU, audio, full PS1 CPU timing or whole-feature acceptance is claimed.')
    with destination.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(report=str(destination), cases_per_image=len(seen), source_promotions=0)), flush=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--edge-build', required=True, type=Path)
    parser.add_argument('--cell-build', required=True, type=Path)
    parser.add_argument('--bridge', required=True, type=Path)
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        destination = (ROOT / args.output).resolve()
        outputs = (destination, destination.with_suffix('.log'), destination.with_name(destination.stem + '-stderr.log'),
                   destination.with_name(destination.stem + '-failure.json'))
        if (destination.suffix != '.json' or not destination.is_relative_to((ROOT / '.decomp-lab').resolve())
                or any(path.exists() for path in outputs)):
            raise ValueError('Choose fresh private report, failure and log paths inside .decomp-lab.')
        if not args.bridge.resolve().is_relative_to((ROOT / '.decomp-lab').resolve()):
            raise ValueError('Use a private bridge built by tools/build_nymashock_gte_bridge.ps1.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        verify(destination, args.edge_build, args.cell_build, args.bridge.resolve(), args.runtime)
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print('[!] ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
