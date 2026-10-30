"""Compare bounded model vertex decoding with the original PS1 instructions.

Consumes an existing inventory and reads its unchanged disc directly. This is a
functional leaf-reader check in an analysis VM, not PS1 rendering or timing.
Unicorn is optional; use the existing requirements-analysis.txt environment.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib
import json
import lzma
from pathlib import Path, PurePosixPath
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.disc_files import Mode2Disc, require
from tools.inventory_model_packets import file_sha
from tools.psx_image import EXECUTABLE_NAME, ORIGINAL_SHA1, executable_offset
from tools.tmd_packets import geometries, model_ranges, packets

FUNCTION, FUNCTION_BYTES = 0x80020050, 1152
FUNCTION_SHA = 'd58160f9ae8a3adcc81dfda474988896476e823a614afd7f686896ec64677469'
RAM_BYTES, MASK = 0x200000, 0x1fffffff
FIXTURE, OBJECT, GEOMETRY = 0x100000, 0x100100, 0x100200
DATA, DATA_LIMIT = 0x101000, 0x180000
OUTPUT, STACK_PAGE, STACK, STOP = 0x1a0000, 0x1b0000, 0x1b0800, 0x1ff000
COUNT, POINTS, INDEX = OUTPUT + 0x10, OUTPUT + 0x40, OUTPUT + 0x80
FIXTURES = ROOT / 'research/model_packets/layout-fixtures.json'
FAULTS = (
    dict(name='first-vertex-offset', address=0x80020108,
         original=0x9502000a, replacement=0x9502000c),
    dict(name='vertex-record-stride', address=0x80020480,
         original=0x000210c0, replacement=0x00021080),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    encoded = json.dumps(value, indent=2) + '\n'
    require(len(encoded.encode()) <= 1024**2, 'Summary exceeds its 1 MiB bound.')
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(encoded)


def backend_identity():
    try:
        import unicorn
    except ImportError as error:
        raise ValueError('Use an existing requirements-analysis.txt environment.') from error
    require(unicorn.__version__ == '2.1.4', 'This leaf-reader profile requires Unicorn 2.1.4.')
    module = importlib.import_module(unicorn.Uc.__module__)
    library, entry = Path(module.uclib._name).resolve(), Path(unicorn.__file__).resolve()
    bindings = [(p.relative_to(entry.parent).as_posix(), file_sha(p))
                for p in sorted(entry.parent.rglob('*.py'))]
    return dict(package_version=unicorn.__version__, library_api=list(unicorn.uc_version()),
        library_sha256=file_sha(library), binding_entry_sha256=file_sha(entry),
        binding_sources_sha256=sha(json.dumps(bindings).encode()), binding_source_count=len(bindings))


class Reader:
    """Original leaf instructions, read-only inputs, exact writes and saved ABI."""
    def __init__(self, executable, fault=None):
        import unicorn
        from unicorn import mips_const as reg
        self.u, self.r, self.fault = unicorn, reg, fault
        self.cpu = unicorn.Uc(unicorn.UC_ARCH_MIPS,
                             unicorn.UC_MODE_MIPS32 | unicorn.UC_MODE_LITTLE_ENDIAN)
        self.cpu.mem_map(0, RAM_BYTES, unicorn.UC_PROT_READ | unicorn.UC_PROT_EXEC)
        self.load, self.payload_bytes = struct.unpack_from('<II', executable, 0x18)
        self.load &= MASK
        require(0x800 + self.payload_bytes == len(executable)
                and self.load + self.payload_bytes <= FIXTURE, 'Unexpected executable RAM extent.')
        self.cpu.mem_write(self.load, executable[0x800:])
        for page in (OUTPUT, STACK_PAGE):
            self.cpu.mem_protect(page, 4096, unicorn.UC_PROT_READ | unicorn.UC_PROT_WRITE)
        self.cpu.mem_write(OUTPUT, b'\xd3' * 4096)
        self.cpu.mem_write(STACK_PAGE, b'\xc9' * 4096)
        code = bytes(self.cpu.mem_read(FUNCTION & MASK, FUNCTION_BYTES))
        require(sha(code) == FUNCTION_SHA, 'Original leaf-reader code hash differs.')
        if fault:
            at = fault['address'] & MASK
            require(struct.unpack('<I', self.cpu.mem_read(at, 4))[0] == fault['original'],
                    'Fault control does not identify its pinned instruction.')
            self.cpu.mem_write(at, struct.pack('<I', fault['replacement']))
        self.saved = [getattr(reg, 'UC_MIPS_REG_S' + str(i)) for i in range(8)] + [reg.UC_MIPS_REG_FP]
        self.steps, self.calls, self.fault_hits = 0, 0, 0
        self.read_ranges, self.write_ranges = [], []
        self.cpu.hook_add(unicorn.UC_HOOK_CODE, self.instruction)
        self.cpu.hook_add(unicorn.UC_HOOK_MEM_READ | unicorn.UC_HOOK_MEM_WRITE, self.access)

    def instruction(self, cpu, address, size, unused):
        physical = address & MASK
        require(FUNCTION & MASK <= physical and physical + size <= (FUNCTION & MASK) + FUNCTION_BYTES,
                'Execution left the qualified original function.')
        self.steps += 1
        if self.fault and physical == self.fault['address'] & MASK:
            self.fault_hits += 1

    def access(self, cpu, access, address, size, value, unused):
        address &= MASK
        spans = self.write_ranges if access == self.u.UC_MEM_WRITE else self.read_ranges
        require(any(a <= address and address + size <= b for a, b in spans),
                'Native data access left its exact input/output/stack ranges: ' + hex(address))

    def prepare(self, vertex_records, primitive_records, primitive_count, alias=0):
        require(alias in (0, 0x80000000) and len(vertex_records) % 8 == 0
                and 0 <= primitive_count <= 65536, 'Invalid fixture count or address alias.')
        self.alias, self.primitive_count = alias, primitive_count
        # Keep the arrays independent, aligned and separated by checked red zones.
        vertices = DATA
        primitives = (vertices + len(vertex_records) + 67) & ~3
        end = primitives + len(primitive_records) + 64
        require(end <= DATA_LIMIT, 'Geometry exceeds its bounded analysis VM fixture.')
        self.cpu.mem_write(FIXTURE, b'\xa7' * (end - FIXTURE))
        self.cpu.mem_write(vertices, vertex_records)
        self.cpu.mem_write(primitives, primitive_records)
        self.cpu.mem_write(OBJECT + 16, struct.pack('<I', GEOMETRY | alias))
        self.cpu.mem_write(GEOMETRY, struct.pack('<6I', vertices | alias, len(vertex_records)//8,
                            0, 0, primitives | alias, primitive_count))
        self.primitives = primitives
        self.cpu.mem_write(OUTPUT, b'\xd3' * 4096)
        self.cpu.mem_write(STACK_PAGE, b'\xc9' * 4096)
        self.cpu.mem_write(STACK + 16, struct.pack('<I', INDEX | alias))
        self.read_ranges = [(self.load, self.load + self.payload_bytes),
            (OBJECT + 16, OBJECT + 20), (GEOMETRY, GEOMETRY + 24),
            (vertices, vertices + len(vertex_records)),
            (primitives, primitives + len(primitive_records)),
            (COUNT, COUNT + 4), (POINTS, POINTS + 24), (INDEX, INDEX + 4),
            (STACK - 24, STACK), (STACK + 16, STACK + 20)]
        self.write_ranges = [(COUNT, COUNT + 4), (POINTS, POINTS + 24),
                             (INDEX, INDEX + 4), (STACK - 24, STACK)]
        self.guard_before = self.immutable_hash()

    def immutable_hash(self):
        data = bytearray(self.cpu.mem_read(0, RAM_BYTES))
        # Only these exact output slots and the original 24-byte frame may differ.
        for start, end in ((COUNT, COUNT+4), (POINTS, POINTS+24),
                           (INDEX, INDEX+4), (STACK-24, STACK)):
            data[start:end] = bytes(end-start)
        return sha(data)

    def check_immutable(self):
        require(self.immutable_hash() == self.guard_before,
                'Full VM memory outside exact mutable slots changed.')

    def call(self, cursor, index):
        cpu, reg, alias = self.cpu, self.r, self.alias
        self.calls += 1
        cpu.mem_write(INDEX, struct.pack('<I', index))
        # Reset caller output slots so triangle and EOF preservation is observable.
        cpu.mem_write(COUNT, b'\xd3' * 4)
        cpu.mem_write(POINTS, b'\xd3' * 24)
        output_before = bytes(cpu.mem_read(OUTPUT, 4096))
        stack_before = bytes(cpu.mem_read(STACK_PAGE, 4096))
        values = [0xa7000000 + i*0x10301 for i in range(len(self.saved))]
        for register, value in zip(self.saved, values):
            cpu.reg_write(register, value)
        for number, value in enumerate((OBJECT | alias, cursor, COUNT | alias, POINTS | alias)):
            cpu.reg_write(getattr(reg, 'UC_MIPS_REG_A' + str(number)), value)
        for register, value in ((reg.UC_MIPS_REG_SP, STACK | alias),
                (reg.UC_MIPS_REG_GP, 0x8008b000), (reg.UC_MIPS_REG_RA, STOP | alias)):
            cpu.reg_write(register, value)
        previous_steps = self.steps
        cpu.emu_start(FUNCTION, STOP | alias, count=4096)
        require(cpu.reg_read(reg.UC_MIPS_REG_PC) == STOP | alias
                and cpu.reg_read(reg.UC_MIPS_REG_SP) == STACK | alias
                and cpu.reg_read(reg.UC_MIPS_REG_GP) == 0x8008b000
                and cpu.reg_read(reg.UC_MIPS_REG_RA) == STOP | alias
                and [cpu.reg_read(register) for register in self.saved] == values,
                'Call return, instruction budget or saved-register ABI failed.')
        stack_after = bytearray(cpu.mem_read(STACK_PAGE, 4096))
        frame = STACK - STACK_PAGE
        stack_after[frame-24:frame] = stack_before[frame-24:frame]
        require(bytes(stack_after) == stack_before, 'Caller stack/argument or stack red zone changed.')
        return dict(next=cpu.reg_read(reg.UC_MIPS_REG_V0),
            count=struct.unpack('<I', cpu.mem_read(COUNT, 4))[0],
            index=struct.unpack('<I', cpu.mem_read(INDEX, 4))[0],
            points=bytes(cpu.mem_read(POINTS, 24)),
            output_before=output_before, output_after=bytes(cpu.mem_read(OUTPUT, 4096)),
            instructions=self.steps-previous_steps)


def compare_call(reader, cursor, index, point_values=None, next_offset=None):
    observed = reader.call(cursor, index)
    wanted = bytearray(observed['output_before'])
    if point_values is None:
        differences = observed['next'] != 0
    else:
        struct.pack_into('<I', wanted, COUNT-OUTPUT, len(point_values))
        struct.pack_into('<I', wanted, INDEX-OUTPUT, index+1)
        flat = [coordinate for point in point_values for coordinate in point]
        struct.pack_into('<' + 'h'*len(flat), wanted, POINTS-OUTPUT, *flat)
        differences = observed['next'] != (reader.primitives + next_offset) | reader.alias
    return observed, (not differences and bytes(wanted) == observed['output_after'])


def record_bytes(packet, observed, base):
    # This digest binds count, cursor chain, ordinal, signed XYZ and input mode.
    header = struct.pack('<BBIII', packet.mode, packet.flags, observed['count'],
                         observed['index'], (observed['next'] & MASK)-base)
    return header + observed['points'][:len(packet.points)*6]


def synthetic_checks(executable):
    fixture = json.loads(FIXTURES.read_text(encoding='utf-8'))
    vertices = b''.join(struct.pack('<3hH', *point, 0xeeee) for point in fixture['points'])
    reader, totals = Reader(executable), Counter()
    for alias in (0, 0x80000000):
        for mode in range(0x20, 0x40):
            for flags in (0, 4, 255):
                base = f'0x{mode & ~2:02x}'
                length, locations = (fixture['gradation'].get(base, fixture['formats'][base])
                                     if flags & 4 else fixture['formats'][base])
                raw = bytearray([0x96] * length)
                raw[:4] = bytes((0xfc, 0xfd, flags, mode))
                indices = (3, 1, 0, 2)[:len(locations)]
                for offset, value in zip(locations, indices):
                    struct.pack_into('<H', raw, offset, value)
                expected = [fixture['points'][value] for value in indices]
                reader.prepare(vertices, bytes(raw), 1, alias)
                observed, equal = compare_call(reader, 0xdeadbeef, 0, expected, length)
                require(equal, 'Independent signed-coordinate mode fixture disagrees: ' + hex(mode))
                for index in (1, 2, 0xffffffff):
                    _, equal = compare_call(reader, 0xdeadbeef, index)
                    require(equal, 'End-of-stream guard changed outputs or consumed invalid cursor.')
                    totals['end_guard_calls'] += 1
                reader.check_immutable()
                totals['mode_flag_alias_fixtures'] += 1
        reader.prepare(vertices, b'', 0, alias)
        for index in (0, 1, 0xffffffff):
            _, equal = compare_call(reader, 0xdeadbeef, index)
            require(equal, 'Zero-count geometry changed outputs or consumed invalid cursor.')
            totals['zero_count_guard_calls'] += 1
        reader.check_immutable()
    controls = []
    # A fresh VM for each executed fault; failure must be a result mismatch.
    length, locations = fixture['formats']['0x20']
    raw = bytearray([0x96] * length)
    raw[:4] = bytes((0xfc, 0xfd, 0, 0x20))
    for offset, index in zip(locations, (3, 1, 0)):
        struct.pack_into('<H', raw, offset, index)
    expected = [fixture['points'][index] for index in (3, 1, 0)]
    for fault in FAULTS:
        faulty = Reader(executable, fault)
        faulty.prepare(vertices, bytes(raw), 1)
        observed, equal = compare_call(faulty, 0xdeadbeef, 0, expected, length)
        faulty.check_immutable()
        require(not equal and faulty.fault_hits > 0, 'Executed fault was not detected by the output oracle.')
        require(observed['next'] == faulty.primitives + length and observed['index'] == 1
                and observed['count'] == 3, 'Fault was not a clean-return coordinate-only control.')
        controls.append(dict(**fault, instruction_executions=faulty.fault_hits,
            returned_with_ABI_and_input_guards_intact=True, output_disagreement_detected=True,
            crash_count=0))
    return dict(**totals, native_calls=reader.calls, instructions=reader.steps,
                literal_fixture_sha256=file_sha(FIXTURES), controls=controls)


def verify(disc_path, inventory_path, destination):
    started = time.monotonic()
    require(not destination.exists() and destination.parent.is_dir(), 'Choose a fresh bounded output directory.')
    require(0 < inventory_path.stat().st_size <= 4*1024**2, 'Inventory exceeds its input byte bound.')
    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
    require(inventory.get('status') == 'model_vertex_references_verified'
            and inventory.get('unresolved') == [] and inventory.get('model_files') == len(inventory['rows']),
            'A complete successful static inventory is required.')
    for name, expected in inventory['source_dependencies'].items():
        path = (ROOT / name.replace('\\', '/')).resolve()
        require(path.is_relative_to(ROOT) and file_sha(path) == expected,
                'Static inventory source dependency changed: ' + name)
    backend = backend_identity()
    with Mode2Disc(disc_path) as disc:
        before = disc.path.stat()
        require(file_sha(disc.path) == inventory['raw_disc_sha256'], 'Disc differs from the static inventory.')
        files = disc.files()
        selected = {name: record for name, record in files.items()
                    if PurePosixPath(name).suffix in ('.LBD', '.MOM', '.TMD')}
        require(set(selected) == {row['path'] for row in inventory['rows']}, 'Model file set differs.')
        executable = disc.read_file(files['/' + EXECUTABLE_NAME])
        require(hashlib.sha1(executable).hexdigest() == ORIGINAL_SHA1, 'Canonical executable differs.')
        at = executable_offset(executable, FUNCTION, FUNCTION_BYTES)
        require(sha(executable[at:at+FUNCTION_BYTES]) == FUNCTION_SHA, 'Pinned decoder range differs.')
        synthetic = synthetic_checks(executable)
        destination.mkdir()
        reader = Reader(executable)
        totals, modes, flags = Counter(), Counter(), Counter()
        object_stream = destination/'objects.jsonl.xz'
        decoded_bytes, objects_digest = 0, hashlib.sha256()
        with lzma.open(object_stream, 'xb', preset=6) as output:
            for file_number, row in enumerate(inventory['rows'], 1):
                require(time.monotonic()-started < 3600, 'Native corpus audit exceeded its one-hour bound.')
                raw = disc.read_file(selected[row['path']])
                require(len(raw) == row['bytes'] and sha(raw) == row['sha256'], 'Model file bytes changed.')
                ranges = model_ranges(raw, PurePosixPath(row['path']).suffix)
                require(len(ranges) == len(row['models']), 'TMD table set differs from the static report.')
                for model, static in zip(ranges, row['models']):
                    require(all(model[key] == static[key] for key in model), 'Model bounds or references differ.')
                    counts = Counter()
                    for geometry in geometries(raw, model['tmd'], model['limit']):
                        decoded = tuple(packets(raw, geometry))
                        length = sum(packet.bytes for packet in decoded)
                        vertex_records = raw[geometry.vertices_offset:geometry.vertices_offset+geometry.vertex_count*8]
                        primitive_records = raw[geometry.primitives_offset:geometry.primitives_offset+length]
                        reader.prepare(vertex_records, primitive_records, geometry.primitive_count)
                        cursor, expected_hash, actual_hash = 0xdeadbeef, hashlib.sha256(), hashlib.sha256()
                        steps_before = reader.steps
                        for ordinal, packet in enumerate(decoded):
                            next_offset = packet.offset-geometry.primitives_offset+packet.bytes
                            observed, equal = compare_call(reader, cursor, ordinal, packet.points, next_offset)
                            require(equal, 'Original decoder output disagrees: ' + row['path']
                                    + ' object ' + str(geometry.index) + ' packet ' + str(ordinal))
                            expected = dict(count=len(packet.points), index=ordinal+1,
                                next=reader.primitives+next_offset,
                                points=struct.pack('<'+'h'*(len(packet.points)*3),
                                                  *(c for point in packet.points for c in point)))
                            actual_hash.update(record_bytes(packet, observed, reader.primitives))
                            expected_hash.update(record_bytes(packet, expected, reader.primitives))
                            cursor = observed['next']
                            counts.update(packets=1, triangles=len(packet.points)==3,
                                quads=len(packet.points)==4, vertex_references=len(packet.points))
                            modes[f'0x{packet.mode:02x}'] += 1
                            flags[f'0x{packet.flags:02x}'] += 1
                        _, equal = compare_call(reader, cursor, geometry.primitive_count)
                        require(equal, 'Actual geometry end-of-stream guard disagrees.')
                        reader.check_immutable()
                        require(expected_hash.digest() == actual_hash.digest(), 'Object output stream hash differs.')
                        counts.update(objects=1, vertices=geometry.vertex_count, normals=geometry.normal_count)
                        evidence = dict(path=row['path'], tmd=model['tmd'], object=geometry.index,
                            packets=len(decoded), vertex_references=sum(len(p.points) for p in decoded),
                            instructions=reader.steps-steps_before, decoded_stream_sha256=actual_hash.hexdigest(),
                            complete_output_and_ABI_equal=True, full_immutable_VM_equal=True)
                        encoded = (json.dumps(evidence, separators=(',', ':'))+'\n').encode()
                        decoded_bytes += len(encoded)
                        require(decoded_bytes <= 8*1024**2, 'Decoded object journal exceeds its 8 MiB bound.')
                        output.write(encoded)
                        objects_digest.update(encoded)
                    require(dict(counts) == static['counts'], 'Native object/packet counts differ from the static report.')
                    totals.update(counts)
                    totals['TMD_tables'] += 1
                    if model['kind'] == 'MML-MOM':
                        totals.update(embedded_MOM_occurrences=1, embedded_MOM_references=model['references'])
                require(object_stream.stat().st_size < 3*1024**2, 'Compressed object journal exceeds 3 MiB.')
                print(json.dumps(dict(completed_files=file_number,
                    total_files=len(inventory['rows']), objects=totals['objects'], packets=totals['packets'])), flush=True)
        require(dict(totals) == inventory['counts'] and dict(sorted(modes.items())) == inventory['modes']
                and dict(sorted(flags.items())) == inventory['flags'], 'Complete corpus counts differ.')
        after = disc.path.stat()
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                and file_sha(disc.path) == inventory['raw_disc_sha256'], 'Raw disc changed during native verification.')
    dependencies = ('tools/verify_model_packets.py', 'research/model_packets/layout-fixtures.json',
                    'tools/tmd_packets.py', 'tools/disc_files.py', 'tools/inventory_model_packets.py',
                    'tools/psx_image.py', 'tools/inventory_animations.py', 'requirements-analysis.txt')
    result = dict(schema_version=1, status='original_model_vertex_decoder_matches',
        generated_at=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic()-started,
        raw_disc_sha256=inventory['raw_disc_sha256'], inventory_sha256=file_sha(inventory_path),
        original_executable_sha1=ORIGINAL_SHA1, function=dict(address=hex(FUNCTION), bytes=FUNCTION_BYTES,
        sha256=FUNCTION_SHA, stack_frame_bytes=24), backend=backend, synthetic=synthetic,
        model_files=len(inventory['rows']), counts=dict(totals), modes=dict(sorted(modes.items())),
        flags=dict(sorted(flags.items())), native_calls=reader.calls, original_instructions=reader.steps,
        object_journal=dict(file=object_stream.name, bytes=object_stream.stat().st_size,
            sha256=file_sha(object_stream), decoded_bytes=decoded_bytes, decoded_sha256=objects_digest.hexdigest()),
        source_dependencies={name:file_sha(ROOT/name) for name in dependencies},
        complete_point_buffers_cursor_index_ABI_and_guards_equal=True,
        full_immutable_VM_compared_at_every_object_boundary=True,
        actual_geometry_alias='physical', synthetic_geometry_aliases=['physical', 'KSEG0'],
        zero_count_and_EOF_leave_outputs_unchanged=True, invalid_initial_cursor_ignored=True,
        no_original_output_stubs=True, no_asset_payload_written=True, source_bytes_modified=False,
        rendered_output_verified=False, normal_index_semantics_verified=False,
        texture_palette_and_lighting_verified=False, complete_PS1_timing_verified=False,
        whole_feature_groups_accepted=0,
        scope='Original instruction execution on mapped per-object fixtures; signed vertex output and cursor semantics only.')
    write_json(destination/'comparison.json', result)
    require(sum(p.stat().st_size for p in destination.iterdir()) <= 4*1024**2, 'Output directory exceeds 4 MiB.')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disc', required=True, type=Path)
    parser.add_argument('--inventory', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify(args.disc, args.inventory, args.output.resolve())
        print(json.dumps({key:result[key] for key in ('status','model_files','counts','native_calls','original_instructions')}))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps(dict(status='invalid_or_differing_model_decoder', error=str(error))), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
