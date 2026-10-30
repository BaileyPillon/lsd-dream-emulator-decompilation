"""Execute the original SDK mapper/linker over a verified local TMD corpus.

Reuses a successful static inventory, the canonical disc and an existing
Unicorn 2.1.4 environment. Writes compact reports only. Rendering and complete
PS1 timing are outside this bounded instruction-execution profile.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
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
from tools.tmd_packets import model_ranges
from tools.tmd_sdk_model import link_tmd, map_tmd
from tools.verify_model_packets import backend_identity, write_json

FUNCTIONS = {
    'map': dict(address=0x80020548, bytes=120,
        sha256='f2ebf166974181360c8d2ef9e5c2188a85a0c01d99a9be4959145a57a4809e41', frame=8),
    'link': dict(address=0x8001EF70, bytes=344,
        sha256='6fdd4c9c7f41b05ce3cb2afe03cce52971b77d7020b923a8dba730dc056fbb02', frame=56),
}
RAM_BYTES, MASK = 0x200000, 0x1FFFFFFF
BUFFER, BUFFER_BYTES = 0x101000, 0x10000
TARGET, STACK_PAGE, STACK, STOP = 0x1A0000, 0x1B0000, 0x1B0800, 0x1FF000
JUMP_TABLE, JUMP_BYTES = 0x102DC, 120
FIXTURES = ROOT/'research/model_packets/sdk-link-fixtures.json'
FAULTS = (
    dict(name='map-wrong-pointer-base', operation='map', address=0x8002058C,
         original=0x00821021, replacement=0x24420004),
    dict(name='link-wrong-run-count', operation='link', address=0x8001F098,
         original=0x26310001, replacement=0x26310002),
    dict(name='link-suppressed-mode-boundary', operation='link', address=0x8001EFD8,
         original=0x12420005, replacement=0x10000005),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Machine:
    """Two qualified SDK functions with exact writes, full state and ABI guards."""
    def __init__(self, executable, fault=None):
        import unicorn
        from unicorn import mips_const as reg
        self.u, self.r, self.fault = unicorn, reg, fault
        self.cpu = unicorn.Uc(unicorn.UC_ARCH_MIPS,
                             unicorn.UC_MODE_MIPS32 | unicorn.UC_MODE_LITTLE_ENDIAN)
        self.cpu.mem_map(0, RAM_BYTES, unicorn.UC_PROT_READ | unicorn.UC_PROT_EXEC)
        load, payload_bytes = struct.unpack_from('<II', executable, 0x18)
        load &= MASK
        require(0x800 + payload_bytes == len(executable) and load + payload_bytes < BUFFER,
                'Unexpected canonical executable RAM extent.')
        self.cpu.mem_write(load, executable[0x800:])
        for function in FUNCTIONS.values():
            at = executable_offset(executable, function['address'], function['bytes'])
            require(sha(executable[at:at+function['bytes']]) == function['sha256'],
                    'Pinned original SDK range differs.')
        self.jump_sha256 = sha(bytes(self.cpu.mem_read(JUMP_TABLE, JUMP_BYTES)))
        if fault:
            at = fault['address'] & MASK
            require(struct.unpack('<I', self.cpu.mem_read(at, 4))[0] == fault['original'],
                    'Fault does not identify its qualified original instruction.')
            self.cpu.mem_write(at, struct.pack('<I', fault['replacement']))
        for start, size in ((BUFFER, BUFFER_BYTES), (TARGET, 4096), (STACK_PAGE, 4096)):
            self.cpu.mem_protect(start, size, unicorn.UC_PROT_READ | unicorn.UC_PROT_WRITE)
        self.saved = [getattr(reg, 'UC_MIPS_REG_S'+str(i)) for i in range(8)]+[reg.UC_MIPS_REG_FP]
        self.steps, self.fault_hits, self.calls = 0, 0, Counter()
        self.active, self.write_ranges, self.visited = None, [], []
        self.cpu.hook_add(unicorn.UC_HOOK_CODE, self.instruction)
        self.cpu.hook_add(unicorn.UC_HOOK_MEM_READ | unicorn.UC_HOOK_MEM_WRITE, self.access)

    def instruction(self, cpu, address, size, unused):
        physical = address & MASK
        function = FUNCTIONS[self.active]
        lower = function['address'] & MASK
        require(lower <= physical and physical + size <= lower + function['bytes'],
                'Execution left the active qualified SDK function, including its error path.')
        self.steps += 1
        if self.fault and physical == self.fault['address'] & MASK:
            self.fault_hits += 1
        if self.active == 'link' and physical == 0x1EFC8:
            self.visited.append(cpu.reg_read(self.r.UC_MIPS_REG_S0))
        if self.active == 'map' and physical == 0x20584:
            self.visited.append(cpu.reg_read(self.r.UC_MIPS_REG_A1))

    def access(self, cpu, access, address, size, value, unused):
        address &= MASK
        spans = self.write_ranges if access == self.u.UC_MEM_WRITE else (
            (BUFFER, BUFFER+len(self.current)), (STACK-56, STACK),
            (JUMP_TABLE, JUMP_TABLE+JUMP_BYTES))
        require(any(start <= address and address+size <= end for start, end in spans),
                'SDK data access left its bounded model, exact outputs, jump table or frame: '+hex(address))

    def prepare(self, data, alias=0):
        require(alias in (0, 0x80000000) and 12 <= len(data) <= BUFFER_BYTES,
                'TMD fixture exceeds the bounded SDK analysis VM.')
        self.alias, self.address = alias, BUFFER | alias
        self.current, self.target = bytes(data), b'\xd3'*24
        self.cpu.mem_write(BUFFER, b'\xa7'*BUFFER_BYTES)
        self.cpu.mem_write(BUFFER, self.current)
        self.cpu.mem_write(TARGET, b'\xd3'*4096)
        self.cpu.mem_write(STACK_PAGE, b'\xc9'*4096)
        self.guard_before = self.immutable_hash()

    def immutable_hash(self):
        memory = bytearray(self.cpu.mem_read(0, RAM_BYTES))
        # Each masked region is separately compared byte for byte or guarded ABI.
        for start, end in ((BUFFER, BUFFER+len(self.current)), (TARGET, TARGET+24),
                           (STACK-56, STACK)):
            memory[start:end] = bytes(end-start)
        return sha(memory)

    def invoke(self, operation, index=0, allow_output_mismatch=False):
        cpu, reg = self.cpu, self.r
        self.active, self.visited = operation, []
        if operation == 'map':
            flags, count = struct.unpack_from('<II', self.current, 4)
            predicted, target = map_tmd(self.current, self.address), self.target
            slots = [4]
            if not flags & 1 and not count & 0x80000000:
                slots += [12+28*i+field for i in range(count) for field in (0, 8, 16)]
            self.write_ranges = [(BUFFER+at, BUFFER+at+4) for at in slots]
            expected_visits = tuple(self.address+12+28*i for i in range(count)) if (
                not flags & 1 and not count & 0x80000000) else ()
            arguments = (self.address+4, 0xDEAD0020, 0xDEAD0030, 0xDEAD0040)
        else:
            plan = link_tmd(self.current, self.address, index, self.target)
            predicted, target = plan.model, plan.target
            self.write_ranges = [(TARGET+8, TARGET+12)]+[
                (BUFFER+at, BUFFER+at+2) for at, _ in plan.run_headers]
            expected_visits = tuple(self.address+at for at, _ in plan.primitive_extents)
            arguments = (self.address+12, TARGET | self.alias, index, 0xDEAD0040)
        frame_bytes = FUNCTIONS[operation]['frame']
        self.write_ranges.append((STACK-frame_bytes, STACK))
        values = [0xA7000000+i*0x10301 for i in range(len(self.saved))]
        for register, value in zip(self.saved, values):
            cpu.reg_write(register, value)
        for number, value in enumerate(arguments):
            cpu.reg_write(getattr(reg, 'UC_MIPS_REG_A'+str(number)), value)
        for register, value in ((reg.UC_MIPS_REG_SP, STACK | self.alias),
                (reg.UC_MIPS_REG_GP, 0x8008B000), (reg.UC_MIPS_REG_RA, STOP | self.alias)):
            cpu.reg_write(register, value)
        stack_before = bytes(cpu.mem_read(STACK_PAGE, 4096))
        cpu.emu_start(FUNCTIONS[operation]['address'], STOP | self.alias, count=1000000)
        require(cpu.reg_read(reg.UC_MIPS_REG_PC) == STOP | self.alias
                and cpu.reg_read(reg.UC_MIPS_REG_SP) == STACK | self.alias
                and cpu.reg_read(reg.UC_MIPS_REG_GP) == 0x8008B000
                and cpu.reg_read(reg.UC_MIPS_REG_RA) == STOP | self.alias
                and [cpu.reg_read(register) for register in self.saved] == values,
                'SDK return, instruction budget or saved-register ABI differs.')
        stack_after = bytearray(cpu.mem_read(STACK_PAGE, 4096))
        at = STACK-STACK_PAGE
        stack_after[at-frame_bytes:at] = stack_before[at-frame_bytes:at]
        require(bytes(stack_after) == stack_before, 'Caller stack or callee-frame red zone changed.')
        require(self.immutable_hash() == self.guard_before, 'Full VM outside compared outputs/frame changed.')
        actual = bytes(cpu.mem_read(BUFFER, len(self.current)))
        actual_target = bytes(cpu.mem_read(TARGET, 24))
        equal = actual == predicted and actual_target == target and tuple(self.visited) == expected_visits
        self.calls[operation] += 1
        if not allow_output_mismatch:
            require(equal, 'Original SDK model, target or native cursor walk differs from the independent plan.')
            self.current, self.target = predicted, target
        return dict(equal=equal, complete_output_equal=actual == predicted and actual_target == target,
            cursor_walk_equal=tuple(self.visited) == expected_visits,
            ABI_and_full_VM_guards_intact=True, clean_return=True,
            model_sha256=sha(actual), target_sha256=sha(actual_target))


def literal_tmd(objects, flags=0x80):
    """Construct byte fixtures from literal lengths, without asking the oracle."""
    raw = bytearray(12+28*len(objects))
    struct.pack_into('<III', raw, 0, 0x41, flags, len(objects))
    for index, primitives in enumerate(objects):
        raw.extend(b'\x96'*8)
        start = len(raw)
        for mode, packet_flags, size in primitives:
            packet = bytearray(b'\xa5'*size)
            packet[:4] = bytes((0x55, 0xAA, packet_flags, mode))
            raw.extend(packet)
        raw.extend(b'\x97'*8)
        struct.pack_into('<6Ii', raw, 12+28*index, start-12, 0, start-12, 0,
                         start-12, len(primitives), -index-1)
    return bytes(raw)


def synthetic_checks(executable):
    fixture = json.loads(FIXTURES.read_bytes())
    machine, totals = Machine(executable), Counter()
    for alias in (0, 0x80000000):
        for text, size in fixture['formats'].items():
            for flags in (0, 4, 255):
                length = fixture['gradation_overrides'].get(text, size) if flags & 4 else size
                for transparent in (0, 2):
                    mode = int(text, 16) | transparent
                    # Index one ensures the 28-byte descriptor selection executes.
                    machine.prepare(literal_tmd([[(0x20, 0, 16)], [(mode, flags, length)]]), alias)
                    machine.invoke('map')
                    machine.invoke('map')
                    machine.invoke('link', 1)
                    machine.invoke('link', 1)
                    totals['mode_flag_alias_fixtures'] += 1
        for count in (0, 0x80000000, 0xFFFFFFFF):
            machine.prepare(struct.pack('<III', 0x41, 0x80, count), alias)
            machine.invoke('map')
            machine.invoke('map')
            totals['zero_or_signed_negative_count_fixtures'] += 1
        machine.prepare(literal_tmd([fixture['mixed_runs'], []]), alias)
        machine.invoke('map')
        for index in (0, 0, 1, 1):
            machine.invoke('link', index)
        totals['mixed_runs_and_zero_primitive_fixtures'] += 1
    controls = []
    for fault in FAULTS:
        control = Machine(executable, fault=fault)
        control.prepare(literal_tmd([fixture['mixed_runs']]))
        if fault['operation'] == 'link':
            control.invoke('map')
        result = control.invoke(fault['operation'], allow_output_mismatch=True)
        require(control.fault_hits > 0 and not result['complete_output_equal']
                and result['cursor_walk_equal'], 'Executed clean-return wrong-output control was not detected.')
        controls.append(dict(**fault, instruction_executions=control.fault_hits,
            returned_with_ABI_and_full_VM_guards_intact=True, output_disagreement_detected=True,
            cursor_walk_equal=True, crash_count=0))
    return dict(**totals, native_calls=dict(machine.calls), original_instructions=machine.steps,
        literal_fixture_sha256=file_sha(FIXTURES), controls=controls)


def verify(disc_path, inventory_path, destination):
    started = time.monotonic()
    require(not destination.exists() and destination.parent.is_dir(), 'Choose a fresh bounded output directory.')
    require(0 < inventory_path.stat().st_size <= 4*1024**2, 'Inventory exceeds its input byte bound.')
    inventory = json.loads(inventory_path.read_bytes())
    require(inventory.get('status') == 'model_vertex_references_verified' and inventory.get('unresolved') == []
            and inventory.get('model_files') == len(inventory['rows']), 'A complete static inventory is required.')
    for name, expected in inventory['source_dependencies'].items():
        path = (ROOT/name.replace('\\', '/')).resolve()
        require(path.is_relative_to(ROOT) and file_sha(path) == expected,
                'Static inventory dependency differs: '+name)
    backend = backend_identity()
    with Mode2Disc(disc_path) as disc:
        before = disc.path.stat()
        require(file_sha(disc.path) == inventory['raw_disc_sha256'], 'Disc differs from the static inventory.')
        files = disc.files()
        selected = {name:record for name, record in files.items()
                    if PurePosixPath(name).suffix in ('.LBD', '.MOM', '.TMD')}
        require(set(selected) == {row['path'] for row in inventory['rows']}, 'Model file set differs.')
        executable = disc.read_file(files['/'+EXECUTABLE_NAME])
        require(hashlib.sha1(executable).hexdigest() == ORIGINAL_SHA1, 'Canonical executable differs.')
        synthetic = synthetic_checks(executable)
        machine = Machine(executable)
        destination.mkdir()
        totals, journal_hash, decoded_bytes = Counter(), hashlib.sha256(), 0
        stream_path = destination/'objects.jsonl.xz'
        with lzma.open(stream_path, 'xb', preset=6) as output:
            for file_number, row in enumerate(inventory['rows'], 1):
                require(time.monotonic()-started < 3600, 'SDK corpus audit exceeded its one-hour bound.')
                raw = disc.read_file(selected[row['path']])
                require(len(raw) == row['bytes'] and sha(raw) == row['sha256'], 'Model file bytes differ.')
                ranges = model_ranges(raw, PurePosixPath(row['path']).suffix)
                require(len(ranges) == len(row['models']), 'Model table set differs from the static inventory.')
                for model, static in zip(ranges, row['models']):
                    require(all(model[key] == static[key] for key in model), 'TMD bounds or references differ.')
                    data = raw[model['tmd']:model['limit']]
                    machine.prepare(data)
                    objects = struct.unpack_from('<I', data, 8)[0]
                    require(objects == static['counts']['objects'], 'Object count differs from static inventory.')
                    machine.invoke('map')
                    mapped_sha = sha(machine.current)
                    machine.invoke('map')
                    require(sha(machine.current) == mapped_sha, 'Mapping reentry changed mapped TMD bytes.')
                    primitive_total = 0
                    for index in range(objects):
                        plan = link_tmd(machine.current, machine.address, index, machine.target)
                        packets = len(plan.primitive_extents)
                        primitive_total += packets
                        steps_before = machine.steps
                        first = machine.invoke('link', index)
                        second = machine.invoke('link', index)
                        require(first == second, 'Linking reentry changed complete model/target output.')
                        evidence = dict(path=row['path'], tmd=model['tmd'], object=index, packets=packets,
                            runs=len(plan.run_headers), instructions=machine.steps-steps_before,
                            complete_model_sha256=second['model_sha256'], target_sha256=second['target_sha256'],
                            original_cursor_walk_matches=True, repeated_call_equal=True,
                            complete_output_ABI_and_full_VM_equal=True)
                        encoded = (json.dumps(evidence, separators=(',', ':'))+'\n').encode()
                        decoded_bytes += len(encoded)
                        require(decoded_bytes <= 8*1024**2, 'Decoded journal exceeds its 8 MiB bound.')
                        journal_hash.update(encoded)
                        output.write(encoded)
                        totals.update(objects=1, packets=packets, primitive_runs=len(plan.run_headers))
                        totals['zero_primitive_objects'] += packets == 0
                    require(primitive_total == static['counts']['packets'], 'Linker packet count differs from inventory.')
                    totals['TMD_tables'] += 1
                    if model['kind'] == 'MML-MOM':
                        totals.update(embedded_MOM_occurrences=1, embedded_MOM_references=model['references'])
                require(stream_path.stat().st_size < 3*1024**2, 'Compressed journal exceeds 3 MiB.')
                print(json.dumps(dict(completed_files=file_number, total_files=len(inventory['rows']),
                    TMD_tables=totals['TMD_tables'], objects=totals['objects'], packets=totals['packets'])), flush=True)
        for key in ('TMD_tables', 'objects', 'packets', 'embedded_MOM_occurrences', 'embedded_MOM_references'):
            require(totals[key] == inventory['counts'][key], 'Complete corpus count differs: '+key)
        after = disc.path.stat()
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                and file_sha(disc.path) == inventory['raw_disc_sha256'], 'Raw disc changed during verification.')
    dependencies = ('tools/verify_tmd_sdk.py', 'tools/tmd_sdk_model.py',
        'research/model_packets/sdk-link-fixtures.json', 'tools/verify_model_packets.py',
        'tools/inventory_model_packets.py', 'tools/tmd_packets.py', 'tools/disc_files.py',
        'tools/inventory_animations.py', 'tools/psx_image.py', 'requirements-analysis.txt')
    report = dict(schema_version=1, status='original_tmd_sdk_matches',
        generated_at=datetime.now(timezone.utc).isoformat(), elapsed_seconds=time.monotonic()-started,
        raw_disc_sha256=inventory['raw_disc_sha256'], inventory_sha256=file_sha(inventory_path),
        original_executable_sha1=ORIGINAL_SHA1, functions=FUNCTIONS,
        linker_jump_table=dict(address=hex(JUMP_TABLE), bytes=JUMP_BYTES, sha256=machine.jump_sha256),
        backend=backend, synthetic=synthetic, model_files=len(inventory['rows']), counts=dict(totals),
        native_calls=dict(machine.calls), original_instructions=machine.steps,
        object_journal=dict(file=stream_path.name, bytes=stream_path.stat().st_size, sha256=file_sha(stream_path),
            decoded_bytes=decoded_bytes, decoded_sha256=journal_hash.hexdigest()),
        source_dependencies={name:file_sha(ROOT/name) for name in dependencies},
        complete_model_target_cursor_ABI_and_full_VM_compared_at_each_call=True,
        mapping_and_linking_idempotence_checked=True, corpus_data_alias='physical',
        synthetic_data_aliases=['physical', 'KSEG0'], no_original_output_stubs=True,
        no_asset_payload_written=True, source_bytes_modified=False, whole_feature_groups_accepted=0,
        rendered_output_verified=False, normal_index_semantics_verified=False,
        texture_palette_and_lighting_verified=False, complete_PS1_timing_verified=False,
        scope='Original SDK pointer mapping, descriptor binding, packet cursor walks and run header mutations only.')
    write_json(destination/'comparison.json', report)
    require(sum(p.stat().st_size for p in destination.iterdir()) <= 4*1024**2, 'Output directory exceeds 4 MiB.')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disc', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = verify(args.disc, args.inventory, args.output)
        print(json.dumps({key:report[key] for key in ('status', 'model_files', 'counts', 'native_calls', 'original_instructions')}))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps(dict(status='invalid_tmd_sdk_inputs', error=str(error))), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
