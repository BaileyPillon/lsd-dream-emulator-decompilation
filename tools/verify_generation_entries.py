"""Compare the original entry scanner and real world-transform chain.

Requires a current matching executable and optional Unicorn. All 56 original
entry records are checked under declared manual grid/query/flag fixtures.
This analysis neither promotes a C candidate nor accepts natural spawning.
"""
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import itertools
import json
import struct
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import verify_native_ai as n
from tools.verify_scripted_ai import backend_identity

OWNER, GRID, OUTPUT, QUERY, DISTANCE = 0x100000, 0x101000, 0x102000, 0x103000, 0x104000
FUNCTIONS = [
    {
        "function": "dream_generation_find_entry",
        "address": "0x80055620",
        "bytes": 444,
        "sha256": "e04dac2ba99cee9ee544b7df866efe44f9949e933092bc4461d9b7e179200252"
    },
    {
        "function": "func_8004B418",
        "address": "0x8004B418",
        "bytes": 52,
        "sha256": "0f689e4c1155bdffabea669f166646e7aeb2242c46b6699de61f3121386e41ac"
    },
    {
        "function": "func_8004B44C",
        "address": "0x8004B44C",
        "bytes": 292,
        "sha256": "e4cd1302002bf780ae4ab51e78be2cf9bd6230995537f81617aee313102a4551"
    }
]

TABLES = [
    {
        "symbol": "D_800866E8",
        "address": "0x800866E8",
        "bytes": 324,
        "sha256": "a16d03ea12ca4240985fa3c2443fb5e962c8b7b6ad65eb28e842e6198d6135a6"
    },
    {
        "symbol": "g_GenerationStageEntryData",
        "address": "0x800874F4",
        "bytes": 448,
        "sha256": "e5a8bd4c299730c40adee76614fb96ee156b2a161c0eea510dc95faff71449fb"
    },
    {
        "symbol": "g_GenerationStageEntries",
        "address": "0x800876B4",
        "bytes": 56,
        "sha256": "4657597d1fe06ee015d1488340121727200b23083561f793e73538ee5ebd0e19"
    },
    {
        "symbol": "g_GenerationStageEntryCounts",
        "address": "0x800876EC",
        "bytes": 16,
        "sha256": "6ebc75892b748c4cb0f02e2e6eb445509bb5a7fc22e713accb2765e377cc16dc"
    },
    {
        "symbol": "g_GenerationEntityRange",
        "address": "0x80087474",
        "bytes": 60,
        "sha256": "915b3cdbf432fc902b3532d6c74b413ce161ba9e1c9e558bae6eea5efaf46cbf"
    },
    {
        "symbol": "g_GenerationEntityEffects",
        "address": "0x800874B0",
        "bytes": 68,
        "sha256": "d9b9138504b293ecc4bd0d32c553f8f478d2b07dd7cdc93db45f4086bc8e0be7"
    }
]

def stage_pointers():
    return struct.unpack('<14I', n.h.target(n.h.symbols['g_GenerationStageEntries'], 56))


def stage_counts():
    return n.h.target(n.h.symbols['g_GenerationStageEntryCounts'], 14)


def validate_case(case):
    if (type(case.get('stage')) is not int or not 0 <= case['stage'] < 14
            or type(case.get('index')) is not int or not 0 <= case['index'] <= stage_counts()[case['stage']] + 1
            or case.get('flags') not in ('original', 'disabled', 'alternating', 'zero', 'minimum_signed')):
        raise ValueError('Fixture lies outside the original stage/entry/flag domain.')
    grid = case.get('grid')
    if (not isinstance(grid, (list, tuple)) or len(grid) != 3
            or any(type(value) is not int for value in grid)
            or not 1 <= grid[0] <= 32767 or not 1 <= grid[1] <= 32767
            or not -0x80000000 <= grid[2] <= 0x7FFFFFFF):
        raise ValueError('Expected two positive signed grid halfwords and a signed mode word.')
    for name in ('origin', 'query'):
        value = case.get(name)
        if name == 'query' and value is None:
            continue
        if (not isinstance(value, (list, tuple)) or len(value) != 3
                or any(type(word) is not int or not -0x80000000 <= word <= 0x7FFFFFFF for word in value)):
            raise ValueError('Expected three signed world/query words: ' + name)


def s32(value):
    return (value + 0x80000000) % 0x100000000 - 0x80000000


def stage_data(stage, flags):
    count = stage_counts()[stage]
    data = bytearray(n.h.target(stage_pointers()[stage], count * 8)) if count else bytearray()
    for i in range(count):
        value = struct.unpack_from('<b', data, i * 8 + 6)[0]
        if flags == 'disabled' or (flags == 'alternating' and i % 2 == 0):
            data[i * 8 + 6] = (-abs(value)) & 255
        elif flags == 'zero':
            data[i * 8 + 6] = 0
        elif flags == 'minimum_signed':
            data[i * 8 + 6] = 128
    return data


def world(case, entry):
    tile_x, tile_z, cell_x, cell_z = struct.unpack_from('<4b', entry)
    address = n.h.symbols['g_GenerationEntityEffects'] + 60 + entry[4] * 6
    adjustment = struct.unpack('<3h', n.h.target(address, 6))
    width, height, mode = case['grid']
    base = case['origin']
    row, rows = (tile_z, height) if not mode else (0, 1)
    origin_x = s32(base[0] - width * 20480 + tile_x * 40960 - (20480 if row & 1 else 0))
    origin_z = s32(base[2] - rows * 20480 + row * 40960)
    return [s32(origin_x + (cell_x << 11) + adjustment[0] + 1024), s32(base[1] + adjustment[1]),
            s32(origin_z + (cell_z << 11) + adjustment[2] + 1024)]


def fixtures(case):
    validate_case(case)
    owner = bytearray([0xBE]) * 0x300
    n.word(owner, 0, n.h.symbols['D_800866E8'])
    n.word(owner, 0x68, GRID)
    for axis, value in enumerate(case['origin']):
        n.word(owner, 0x54 + axis * 4, value)
    output, distance = bytearray([0xA7]) * 20, bytearray([0xDA]) * 12
    query = struct.pack('<3i', *case['query']) if case['query'] is not None else bytes([0x98]) * 12
    grid = struct.pack('<hhi', *case['grid'])
    entries = bytearray(n.h.target(n.h.symbols['g_GenerationStageEntryData'], 448))
    if stage_counts()[case['stage']]:
        offset = stage_pointers()[case['stage']] - n.h.symbols['g_GenerationStageEntryData']
        data = stage_data(case['stage'], case['flags'])
        entries[offset:offset + len(data)] = data
    return dict(owner=owner, grid=grid, output=output, query=query, distance=distance, entries=entries)


def model(case):
    buffers, trace, index, result = fixtures(case), [], case['index'], 0
    if case['query'] is not None:
        while index < stage_counts()[case['stage']]:
            address = stage_pointers()[case['stage']] + index * 8
            offset = address - n.h.symbols['g_GenerationStageEntryData']
            row = bytes(buffers['entries'][offset:offset + 8])
            index += 1
            flag = struct.unpack_from('<b', row, 6)[0]
            if flag <= 0:
                continue
            packet = row[:4] + n.h.target(n.h.symbols['g_GenerationEntityEffects'] + 60 + row[4] * 6, 6)
            trace.append(['world_transform', OWNER, OUTPUT, packet.hex()])
            point = world(case, row)
            for axis, value in enumerate(point):
                n.word(buffers['output'], axis * 4, value)
            dx, dz = s32(point[0] - case['query'][0]), s32(point[2] - case['query'][2])
            dx = s32(-dx) if dx < 0 else dx
            distance = s32(dx - dz if dz < 0 else dx + dz)
            n.word(buffers['distance'], 0, distance)
            radius = struct.unpack('<i', n.h.target(n.h.symbols['g_GenerationEntityRange'] + 4 * flag, 4))[0]
            if distance < radius:
                result = address
                break
    return dict({key: bytes(data) for key, data in buffers.items()}, trace=trace, index=index, result=result)


class Machine:
    def __init__(self, image=None, patches=None):
        self.cpu = n.Uc(n.UC_ARCH_MIPS, n.UC_MODE_MIPS32 | n.UC_MODE_LITTLE_ENDIAN)
        self.cpu.mem_map(0, 0x200000)
        self.cpu.mem_write(n.h.LOAD & n.MASK, (n.h.ROM if image is None else image)[0x800:])
        for address, data in (patches or {}).items():
            self.cpu.mem_write(address & n.MASK, data)
        self.control_address, self.control_hits = None, 0
        self.entries = {int(row['address'], 16) & n.MASK: row['function'] for row in FUNCTIONS}
        self.counts = Counter()
        self.cpu.hook_add(n.UC_HOOK_CODE, self.hook)

    def hook(self, cpu, address, size, unused):
        if address & n.MASK == self.control_address:
            self.control_hits += 1
        name = self.entries.get(address & n.MASK)
        if name:
            self.counts[name] += 1
        if name == 'func_8004B418':
            args = [cpu.reg_read(getattr(n.reg, 'UC_MIPS_REG_A' + str(i))) for i in range(3)]
            self.trace.append(['world_transform', *args[:2], bytes(cpu.mem_read(args[2] & n.MASK, 10)).hex()])

    def run(self, case):
        self.trace = []
        buffers, cpu = fixtures(case), self.cpu
        addresses = {'owner': OWNER, 'grid': GRID, 'output': OUTPUT, 'query': QUERY, 'distance': DISTANCE,
                     'entries': n.h.symbols['g_GenerationStageEntryData'] & n.MASK}
        for name, data in buffers.items():
            cpu.mem_write(addresses[name], bytes(data))
        for name, value in (('g_GenerationLocation', case['stage']), ('g_GenerationEntryIndex', case['index']),
                            ('g_GenerationOwner', OWNER)):
            cpu.mem_write(n.h.symbols[name] & n.MASK, struct.pack('<I', value))
        cpu.mem_write(n.STACK - 0x200, bytes([0xCC]) * 0x400)
        saved = [n.u32(0xAB000000 + 0x10203 * i) for i in range(len(n.SAVED))]
        for register, value in zip(n.SAVED, saved):
            cpu.reg_write(register, value)
        for register, value in ((n.reg.UC_MIPS_REG_SP, n.STACK), (n.reg.UC_MIPS_REG_GP, 0x8008A808),
                                (n.reg.UC_MIPS_REG_RA, n.END), (n.reg.UC_MIPS_REG_A0, OUTPUT),
                                (n.reg.UC_MIPS_REG_A1, DISTANCE),
                                (n.reg.UC_MIPS_REG_A2, QUERY if case['query'] is not None else 0)):
            cpu.reg_write(register, value)
        cpu.emu_start(n.h.symbols['dream_generation_find_entry'] & n.MASK, n.END, count=50000)
        if (cpu.reg_read(n.reg.UC_MIPS_REG_PC) != n.END or cpu.reg_read(n.reg.UC_MIPS_REG_SP) != n.STACK
                or [cpu.reg_read(register) for register in n.SAVED] != saved):
            raise ValueError('ABI preservation failed')
        return dict({name: bytes(cpu.mem_read(addresses[name], len(data))) for name, data in buffers.items()},
                    trace=self.trace,
                    index=int.from_bytes(cpu.mem_read(n.h.symbols['g_GenerationEntryIndex'] & n.MASK, 4), 'little'),
                    result=cpu.reg_read(n.reg.UC_MIPS_REG_V0))


def base_case(**changes):
    case = dict(stage=0, index=0, flags='original', grid=(16, 6, 0), origin=(0, 0, 0), query=(0, 0, 0))
    case.update(changes)
    return case


def cases():
    counts = stage_counts()
    for stage in range(14):
        for index, flags, query in itertools.product(
                (0, counts[stage], counts[stage] + 1),
                ('original', 'disabled', 'alternating', 'zero', 'minimum_signed'), ((0, 0, 0), None)):
            yield 'guards_and_flags', base_case(stage=stage, index=index, flags=flags, query=query)
        data = stage_data(stage, 'original')
        for row_index in range(counts[stage]):
            row = data[row_index * 8:row_index * 8 + 8]
            flag = struct.unpack_from('<b', row, 6)[0]
            radius = struct.unpack('<i', n.h.target(n.h.symbols['g_GenerationEntityRange'] + 4 * flag, 4))[0]
            for grid, origin in itertools.product(((16, 6, 0), (3, 7, 0), (5, 4, 1)),
                    ((0, 0, 0), (0x7FFFFFFF, -500, -0x80000000))):
                case = base_case(stage=stage, index=row_index, grid=grid, origin=origin)
                point = world(case, row)
                for delta in (-radius - 1, -radius, -radius + 1, -1, 0, 1, radius - 1, radius, radius + 1):
                    query = (s32(point[0] + delta), s32(point[1] + 12345), point[2])
                    yield 'all_original_entry_boundaries', dict(case, query=query)
                for query in ((-0x80000000, 0, 0x7FFFFFFF), (0x7FFFFFFF, 0, -0x80000000)):
                    yield 'signed_world_distance_edges', dict(case, query=query)


def qualify_tables(program):
    for record in TABLES:
        address = int(record['address'], 16)
        if (program.symbols.get(record['symbol']) != address
                or hashlib.sha256(program.target(address, record['bytes'])).hexdigest() != record['sha256']):
            raise ValueError('Original entry table changed: ' + record['symbol'])
    method = struct.unpack('<I', program.target(program.symbols['D_800866E8'] + 0xE8, 4))[0]
    if method != program.symbols['func_8004B418']:
        raise ValueError('Generation owner no longer binds the native world-transform wrapper.')
    counts = program.target(program.symbols['g_GenerationStageEntryCounts'], 14)
    pointers = struct.unpack('<14I', program.target(program.symbols['g_GenerationStageEntries'], 56))
    cursor = program.symbols['g_GenerationStageEntryData']
    records = []
    for stage, (address, count) in enumerate(zip(pointers, counts)):
        if (count and address != cursor) or (not count and address != 0):
            raise ValueError('Original stage records no longer form the pinned entry dataset.')
        data = program.target(address, count * 8) if count else b''
        records.append({'stage': stage, 'address': f'0x{address:08X}', 'entries': count,
                        'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        cursor += count * 8
        if any(data[index * 8 + 4] != 0 or not 1 <= data[index * 8 + 6] <= 14 for index in range(count)):
            raise ValueError('Entry profile requires the original zero-style selector and type flags 1 through 14.')
    if sum(counts) != 56:
        raise ValueError('Expected all 56 original stage entry records.')
    return records


def candidate_identity(program, path):
    data = Path(path).read_bytes()
    function = FUNCTIONS[0]
    start = 0x800 + int(function['address'], 16) - program.LOAD
    end = start + function['bytes']
    if len(data) != len(program.ROM) or data[:start] != program.ROM[:start] or data[end:] != program.ROM[end:]:
        raise ValueError('Candidate must be a complete image differing only inside the selected 444-byte scanner.')
    return data, {'path': str(Path(path).resolve()), 'bytes': len(data),
        'sha256': hashlib.sha256(data).hexdigest(), 'function_sha256': hashlib.sha256(data[start:end]).hexdigest(),
        'complete_image_equal': data == program.ROM,
        'changed_bytes': sum(a != b for a, b in zip(data, program.ROM)), 'source_promoted': False}


def negative_controls():
    row = stage_data(0, 'original')[:8]
    near = base_case()
    point = world(near, row)
    radius = struct.unpack('<i', n.h.target(n.h.symbols['g_GenerationEntityRange'] + row[6] * 4, 4))[0]
    near['query'] = tuple(point)
    far = dict(near, query=(s32(point[0] + radius + 1), point[1], point[2]))
    wrong_axis = dict(near, query=(point[0], s32(point[1] + 12345), point[2]))
    controls = [
        ('wrong_index_advance', 'dream_generation_find_entry', 144, 0x24420001, 0x24420002, near),
        ('wrong_positive_flag_guard', 'dream_generation_find_entry', 160, 0x18400034, 0x1C400034, near),
        ('wrong_style_halfword_destination', 'dream_generation_find_entry', 232, 0xA7A50018, 0xA7A5001A, near),
        ('wrong_distance_axis', 'dream_generation_find_entry', 292, 0x8E820008, 0x8E820004, wrong_axis),
        ('wrong_range_predicate', 'dream_generation_find_entry', 352, 0x0062102A, 0x00621023, far),
        ('wrong_grid_row_parity', 'func_8004B44C', 128, 0x31020001, 0x31020002, near),
    ]
    records = []
    for kind, name, offset, expected_word, changed_word, case in controls:
        record = next(row for row in FUNCTIONS if row['function'] == name)
        address = int(record['address'], 16)
        code = bytearray(n.h.target(address, record['bytes']))
        if struct.unpack_from('<I', code, offset)[0] != expected_word:
            raise ValueError('Fault no longer identifies the pinned native instruction: ' + kind)
        struct.pack_into('<I', code, offset, changed_word)
        machine = Machine(patches={address: bytes(code)})
        machine.control_address = (address + offset) & n.MASK
        if machine.run(case) == model(case) or not machine.control_hits:
            raise ValueError('Executed native fault was not detected: ' + kind)
        records.append({'kind': kind, 'function': name, 'function_offset': offset,
            'expected_word': f'0x{expected_word:08X}', 'changed_word': f'0x{changed_word:08X}',
            'changed_instruction_executions': machine.control_hits, 'fixture': case,
            'scope': 'Private Unicorn memory only.'})
    return records


def new_destination(value):
    path = Path(value).resolve()
    if path.suffix != '.json' or not path.is_relative_to((n.ROOT / '.decomp-lab').resolve()) or path.exists():
        raise ValueError('Choose a fresh JSON report inside .decomp-lab.')
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def verify(destination, candidate=None):
    destination = new_destination(destination)
    dependencies = n.evidence_dependencies('tools/verify_generation_entries.py', 'tools/verify_scripted_ai.py',
        'src/dream/dream_generation.c', 'src/dream/dream_generation_post.c', 'src/scene/render_context.c',
        'src/scene/render_context.h', 'src/scene/map_scene.c', 'src/dream/dream_sys.h',
        'asm/data/76EE8.data.s')
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in dependencies}
    n.initialize_backend(n.load_program(FUNCTIONS))
    entries = qualify_tables(n.h)
    backend = backend_identity()
    candidate_data, candidate_record = (None, None) if candidate is None else candidate_identity(n.h, candidate)
    profiles = [('original', Machine())]
    if candidate is not None:
        profiles.append(('unaccepted_complete_c_candidate', Machine(image=candidate_data)))
    observations = {}
    started = time.monotonic()
    for name, machine in profiles:
        groups = Counter()
        for index, (group, case) in enumerate(cases()):
            actual, expected = machine.run(case), model(case)
            if actual != expected:
                path = destination.with_name(destination.stem + '-failure-' + str(time.time_ns()) + '.json')
                with path.open('x') as handle:
                    json.dump({'profile': name, 'fixture_index': index, 'case': case,
                               'actual': repr(actual), 'expected': repr(expected)}, handle, indent=2)
                raise ValueError('Entry scanner/native-transform disagreement: ' + str(path))
            groups[group] += 1
        observations[name] = {'native_cases': sum(groups.values()), 'case_groups': dict(groups),
                              'actual_native_entry_counts': dict(sorted(machine.counts.items()))}
        print(name, sum(groups.values()), 'passed', flush=True)
    controls = negative_controls()
    if (backend_identity() != backend or (n.ROOT / n.configure.ROM).read_bytes() != n.h.ROM
            or (n.ROOT / n.configure.EXE).read_bytes() != n.h.ROM or n.check_build_current(n.ROOT) is not True
            or any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path, digest in before.items())
            or (candidate is not None and Path(candidate).read_bytes() != candidate_data)):
        raise ValueError('Entry producer, backend or preserved game evidence changed.')
    report = {'status': 'passed_bounded_original_generation_entry_composition',
        'canonical_executable_sha1': hashlib.sha1(n.h.ROM).hexdigest(), 'canonical_original_and_build_equal': True,
        'profiles': observations, 'native_functions': FUNCTIONS, 'native_tables': TABLES,
        'original_stage_entry_tables': entries, 'original_entry_records': 56,
        'owner_virtual_method': {'table': 'D_800866E8', 'offset': 0xE8, 'function': 'func_8004B418'},
        'spawn_packet_bytes_observed': 10, 'backend_identity': backend, 'dependency_output_contracts': [],
        'negative_controls_detected': controls, 'candidate': candidate_record,
        'producer_dependencies': [{'path': path.resolve().relative_to(n.ROOT).as_posix(), 'sha256': digest}
                                  for path, digest in before.items()],
        'source_functions_promoted': 0, 'whole_feature_groups_accepted': 0,
        'original_game_behavior_modified': False, 'model_api_calls': 0,
        'scope': 'Original scanner, virtual world wrapper and actual grid-coordinate conversion with all 56 original '
                 'entry records in 14 stage tables. Manual valid owner/grid/query contexts and original/disabled/alternating/'
                 'zero/minimum-signed flags. Full owner/grid/output/query/distance/all-entry buffers, ordered ten-byte '
                 'packet reads, return/index effects and ABI. Includes native signed word overflow diagnostics. '
                 'Excludes natural context construction, exact per-map grid/parameter provenance, nonzero style selectors, '
                 'sound/entity spawning, entry lifetimes, rendering/audio and PS1 CPU timing.',
        'elapsed_seconds': round(time.monotonic() - started, 3)}
    with destination.open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--candidate', type=Path)
    args = parser.parse_args(argv)
    try:
        import os
        os.chdir(n.ROOT)
        report = verify(args.output, args.candidate)
        print(json.dumps({'status': report['status'], 'profiles': report['profiles'],
                          'controls': len(report['negative_controls_detected'])}))
        return 0
    except (OSError, ValueError, AssertionError) as error:
        print('error: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
