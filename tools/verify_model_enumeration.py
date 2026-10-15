"""Check original model-record enumeration and callback argument forwarding.

Executes five actual original functions on guarded owned receivers. It changes
no game inputs and makes no model calls. Natural constructors, rendering, actor
lifetimes, hardware timing, and whole-feature acceptance remain separate gates.
"""
from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import verify_native_ai as native
from tools.progress import collect_progress
from tools.verify_scripted_ai import backend_identity

RANGES_PATH = ROOT / 'docs/model-enumeration-function-ranges.json'
ranges = json.loads(RANGES_PATH.read_text(encoding='utf-8'))
bindings = [(0x8006f404, 'func_8004497C'), (0x8006f608, 'func_800453DC'),
            (0x8006f60c, 'func_80043FE4'), (0x8006f2b8, 'func_80043FB0'),
            (0x8006f2bc, 'func_80043FE4')]
OBJ_BASE, LIST_BASE, PART_BASE, DATA_BASE, OUT_BASE, INDEX_BASE = (
    0x110000, 0x111000, 0x112000, 0x113000, 0x115000, 0x116000)
OBJ, LIST, PART, DATA, OUT, INDEX = [x + 0x20 for x in (
    OBJ_BASE, LIST_BASE, PART_BASE, DATA_BASE, OUT_BASE, INDEX_BASE)]

def fixture(path, count, selector, output, index, segment):
    specs = [(OBJ_BASE, 128), (LIST_BASE, 128), (PART_BASE, 128),
             (DATA_BASE, 4096), (OUT_BASE, 384), (INDEX_BASE, 128)]
    buffers = [bytearray((i * 31 + j * 17 + count) & 255 for i in range(size))
               for j, (_, size) in enumerate(specs)]
    native.word(buffers[0], 0x20, 0x8006f384)
    native.word(buffers[0], 0x50, LIST | segment)
    native.word(buffers[1], 0x20, 0x8006f590)
    native.word(buffers[1], 0x30, DATA | segment)
    native.word(buffers[2], 0x20, 0x8006f240)
    native.word(buffers[2], 0x30, DATA | segment)
    animation_count = (1, 3, 7)[count % 3]
    native.word(buffers[3], 0x24, animation_count)
    src_offset = 8 if path == 'model_part' else 16 + 4 * animation_count
    records = [(i & 255, 8, 0, None) for i in range(count)]
    records += [(0xA5, 8, 1, None), (0x5A, 9, 0, None),
                (0, 2, 0, 7), ((count - 1) & 255, 2, 0, 42), (0xFE, 2, 0, 65535)]
    data = struct.pack('<HHI', 0x1234, len(records), 0x56789ABC)
    for part_type, kind, flag, key in records:
        words = 2 if key is not None else 1
        data += struct.pack('<I', words << 24 | flag << 20 | kind << 16 | part_type)
        if key is not None:
            data += struct.pack('<I', 0xABCD0000 | key)
    start = 0x20 + src_offset
    buffers[3][start:start + len(data)] = data
    struct.pack_into('<i', buffers[5], 0x20, selector)
    expected = [bytearray(data) for data in buffers]
    cursor, written, found = 0, 0, 0
    for part_type, kind, flag, key in records:
        if kind == 8 and flag == 0:
            written = (written + 1) & 255
            if output:
                expected[4][0x20 + cursor] = part_type
                cursor += 1
        elif kind == 2:
            if output:
                if index and key == selector:
                    cursor -= written
                    for k in range(written):
                        val = expected[4][0x20 + cursor]
                        cursor += 1
                        if val == part_type:
                            found = k
                            break
            elif index:
                found += 1
    if index:
        struct.pack_into('<i', expected[5], 0x20, found)
    receiver = {'object_model': OBJ, 'model_part_list': LIST, 'model_part': PART}[path] | segment
    args = (receiver, (OUT | segment) if output else 0, (INDEX | segment) if index else 0)
    return specs, buffers, [bytes(data) for data in expected], args, written

class Machine(native.Machine):
    def __init__(self):
        self.entries = Counter()
        self.patch_hits = Counter()
        self.expected_forwarding = None
        super().__init__(start=native.h.symbols['func_8004497C'] & native.MASK,
                         native_functions=ranges)

    def hook(self, cpu, address, size, unused):
        address &= native.MASK
        if address == (native.h.symbols['func_8004497C'] + 0x24) & native.MASK:
            self.patch_hits[address] += 1
        name = self.native_entries.get(address)
        if name:
            self.entries[name] += 1
            if name in ('func_800453DC', 'func_80043FE4'):
                assert tuple(cpu.reg_read(getattr(native.reg, 'UC_MIPS_REG_A' + str(i)))
                             for i in (1, 2)) == self.expected_forwarding
        assert any((int(item['address'], 16) & native.MASK) <= address <
                   (int(item['address'], 16) & native.MASK) + item['bytes'] for item in ranges), hex(address)

    def run(self, case):
        specs, buffers, expected, args, result = fixture(**case)
        for (address, _), data in zip(specs, buffers):
            self.cpu.mem_write(address, bytes(data))
        self.cpu.mem_write(native.STACK - 0x400, b'\xCD' * 0x800)
        saved = [native.u32(0xB1000000 + i * 0x10203) for i in range(len(native.SAVED))]
        for register, value in zip(native.SAVED, saved):
            self.cpu.reg_write(register, value)
        for register, value in [(native.reg.UC_MIPS_REG_SP, native.STACK),
                                (native.reg.UC_MIPS_REG_GP, 0x8008A808),
                                (native.reg.UC_MIPS_REG_RA, native.END)]:
            self.cpu.reg_write(register, value)
        for i, value in enumerate(args):
            self.cpu.reg_write(getattr(native.reg, 'UC_MIPS_REG_A' + str(i)), value)
        self.expected_forwarding = args[1:]
        name = {'object_model': 'func_8004497C', 'model_part_list': 'func_800453DC',
                'model_part': 'func_80043FB0'}[case['path']]
        self.cpu.emu_start(native.h.symbols[name] & native.MASK, native.END, count=100000)
        assert self.cpu.reg_read(native.reg.UC_MIPS_REG_PC) == native.END
        assert self.cpu.reg_read(native.reg.UC_MIPS_REG_V0) == result
        assert self.cpu.reg_read(native.reg.UC_MIPS_REG_SP) == native.STACK
        assert self.cpu.reg_read(native.reg.UC_MIPS_REG_GP) == 0x8008A808
        assert self.cpu.reg_read(native.reg.UC_MIPS_REG_RA) == native.END
        assert [self.cpu.reg_read(register) for register in native.SAVED] == saved
        assert bytes(self.cpu.mem_read(native.STACK - 0x400, 64)) == b'\xCD' * 64
        assert bytes(self.cpu.mem_read(native.STACK + 0x40, 64)) == b'\xCD' * 64
        actual = [bytes(self.cpu.mem_read(address, size)) for address, size in specs]
        assert actual == expected, case

def output_path(value):
    path = Path(value).resolve()
    lab = (ROOT / '.decomp-lab').resolve()
    if not path.is_relative_to(lab) or path == lab or path.suffix != '.json':
        raise ValueError('Output must be a new .json file inside .decomp-lab.')
    if path.exists():
        raise ValueError('Output already exists; choose a fresh private report.')
    return path


def verify(output):
    report_path = output_path(output)
    progress = collect_progress()
    if progress['binary_match'] != 'verified':
        raise ValueError('A current matching build is required.')
    pins = progress['build_input_sha256']
    native.initialize_backend(native.load_program(ranges))
    for slot, name in bindings:
        assert int.from_bytes(native.h.target(slot, 4), 'little') == native.h.symbols[name]
    machine = Machine()
    groups, seen = Counter(), set()
    for path, count, selector, output, index, segment in itertools.product(
            ('object_model', 'model_part_list', 'model_part'),
            (0, 1, 2, 4, 15, 127, 254, 255, 256, 257, 260),
            (7, 42, 65535, -1, 65536, 0), (False, True), (False, True), (0, 0x80000000)):
        case = dict(path=path, count=count, selector=selector, output=output, index=index, segment=segment)
        key = tuple(sorted(case.items()))
        assert key not in seen
        seen.add(key)
        machine.run(case)
        groups[path] += 1
    assert len(seen) == 1584 and groups == {'object_model': 528, 'model_part_list': 528, 'model_part': 528}
    assert all(machine.entries[row['function']] > 0 for row in ranges)

    # A single changed delay-slot instruction drops either forwarded argument.
    faults = []
    case = dict(path='object_model', count=4, selector=42, output=True, index=True, segment=0)
    address = (native.h.symbols['func_8004497C'] + 0x24) & native.MASK
    assert bytes(machine.cpu.mem_read(address, 4)) == b'\0' * 4
    for argument, word in [('output', 0x00002821), ('index', 0x00003021)]:
        faulty = Machine()
        faulty.cpu.mem_write(address, struct.pack('<I', word))
        caught = None
        try:
            faulty.run(case)
        except AssertionError:
            caught = 'forwarding_or_output_guard'
        assert caught is not None
        assert faulty.entries['func_8004497C'] == 1 and faulty.entries['func_800453DC'] == 1
        assert faulty.patch_hits[address] == 1
        faults.append({'argument': argument, 'changed_instructions': 1, 'executed_patch_address': hex(address),
                       'detected_by': caught, 'entered_original_wrapper_and_list': True,
                       'executed_changed_instruction_hits': faulty.patch_hits[address]})
    for rel, digest in pins.items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == digest
    assert (ROOT / 'rom/SLPS_015.56').read_bytes() == (ROOT / 'build/SLPS015.56').read_bytes()
    report = {'status': 'passed_bounded_original_model_enumeration', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
              'producer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'native_cases': len(seen),
              'case_groups': dict(groups), 'original_ranges': ranges, 'original_table_bindings': [
                  {'slot': hex(slot), 'function': name} for slot, name in bindings],
              'executed_native_entries': dict(machine.entries), 'dependency_output_stubs': 0,
              'caller_buffers_per_case': 6, 'caller_buffer_bytes_per_case': 4992,
              'original_argument_drop_controls': faults, 'source_input_sha256': pins,
              'index_write_bytes': 4, 'index_record_tail_twelve_bytes_unchanged': True,
              'new_c_functions': 0, 'whole_feature_groups_accepted': 0, 'model_api_calls': 0,
              'scope': 'Constructed receivers and animation frames only. Real table words and all five original functions execute. Full receiver, library, output and index buffers, preserved registers and outer stack guards checked. No natural constructors, assets, allocator closure, actor node creation, rendering, load-delay fidelity or whole-feature acceptance.'}
    report['function_ranges_sha256'] = hashlib.sha256(RANGES_PATH.read_bytes()).hexdigest()
    report['backend'] = backend_identity()
    report['record_decoder_visits'] = machine.entries['func_8004416C']
    assert report['record_decoder_visits'] == 213984
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = verify(args.output)
    except (OSError, ValueError, AssertionError, RuntimeError) as error:
        print('[!] ' + (str(error) or type(error).__name__), file=sys.stderr)
        return 1
    print(json.dumps({key: report[key] for key in
                      ('status', 'native_cases', 'record_decoder_visits', 'dependency_output_stubs')}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
