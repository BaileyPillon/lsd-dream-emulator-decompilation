"""Calibrate functional MIPS collision replay against retained natural calls.

Complete RAM, 35 exposed CPU registers, 64 architectural GTE register views and
instruction counts are compared without exclusions. Interrupts, CAUSE/EPC,
opaque CPU/GTE state and PS1 device timing are not replayed. Success is a
bounded calibration result, never whole-feature or matching-C acceptance.
"""
import argparse
from collections import Counter, deque
import hashlib
import importlib
import json
import mmap
from pathlib import Path, PureWindowsPath
import struct
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research.collision.trace_compiler_stack import new_output
from tools import inspect_collision_calls as primitive
from tools import inspect_hull_calls as hull
from tools import verify_collision as collision
from tools import verify_native_ai as native
from tools.collision_calls import CPU_FIELDS, EVENT_BYTES, FIELDS, FUNCTIONS, RAM_BYTES
from tools.dispatch_returns import sequence


def digest(path):
    path = Path(path)
    before = path.stat()
    with path.open('rb') as stream:
        value = hashlib.file_digest(stream, 'sha256').hexdigest() if sys.version_info >= (3, 11) else _stream_digest(stream)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('An input changed during hashing: ' + str(path))
    return value


def _stream_digest(stream):
    result = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        result.update(block)
    return result.hexdigest()


def load_backend():
    try:
        import unicorn
        from unicorn import mips_const
    except ImportError as error:
        raise ValueError('Install the optional requirements-analysis.txt in the replay environment.') from error
    if unicorn.__version__ != '2.1.4':
        raise ValueError('Use the pinned Unicorn 2.1.4 from requirements-analysis.txt.')
    binding = importlib.import_module('unicorn.unicorn_py3.unicorn')
    identity = dict(package_version=unicorn.__version__,
                    loaded_library_sha256=digest(Path(binding.uclib._name).resolve(strict=True)),
                    binding_sha256=digest(Path(binding.__file__).resolve(strict=True)))
    return SimpleNamespace(Uc=unicorn.Uc, reg=mips_const,
        UC_ARCH_MIPS=unicorn.UC_ARCH_MIPS, UC_MODE_MIPS32=unicorn.UC_MODE_MIPS32,
        UC_MODE_LITTLE_ENDIAN=unicorn.UC_MODE_LITTLE_ENDIAN,
        UC_HOOK_CODE=unicorn.UC_HOOK_CODE, version=unicorn.__version__, identity=identity)


class ArchitecturalCop2(collision.CollisionCop2):
    """Reviewed register views around native OP, SQR and LZCS operations.

    The native bridge resets for individual commands. Unchanged captured
    registers are carried forward, and IRGB/ORGB are derived from IR1..3 using
    the core's readback rule. This is not a full native GTE-state restoration.
    """
    def seed(self, row):
        self.initial_data = [row['entry_gte_data_' + str(i)] for i in range(32)]
        self.initial_control = [row['entry_gte_control_' + str(i)] for i in range(32)]
        self.reset(self.initial_control[:5])
        self.ir = [collision.signed(v, 16) for v in self.initial_data[9:12]]
        self.mac = [collision.signed(v) for v in self.initial_data[25:28]]
        self.lzcs, self.lzcr = self.initial_data[30:32]
        self.flags = self.initial_control[31]
        if self.views() != (self.initial_data, self.initial_control):
            raise ValueError('Captured GTE views cannot be represented by the reviewed adapter.')

    def views(self):
        data, control = self.initial_data[:], self.initial_control[:]
        data[9:12] = [native.u32(value) for value in self.ir]
        data[25:28] = [native.u32(value) for value in self.mac]
        data[28] = data[29] = sum(max(0, min(31, value >> 7)) << (5*i) for i, value in enumerate(self.ir))
        data[30:32] = [self.lzcs, self.lzcr]
        control[:5] = self.cr[:]
        control[4] = native.u32(collision.signed(control[4], 16))
        control[31] = self.flags
        return data, control

    def step_virtual(self, cpu, address):
        handled = self.step(cpu, address & native.MASK)
        if handled:
            # The existing bounded adapter uses physical PCs. Natural calls
            # must retain their virtual PC so later JAL links keep KSEG0.
            cpu.reg_write(self.backend.reg.UC_MIPS_REG_PC, native.u32(address + 4))
        return handled


def pending_caller_load(word):
    opcode, rs = word >> 26, (word >> 21) & 31
    return opcode in (0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26) or (opcode in (0x10, 0x12) and rs in (0, 2))


class NaturalMachine:
    """Execute captured code and state in a new isolated Unicorn instance."""
    def __init__(self, bridge, functions, row, before, *, backend=None):
        if len(before) != RAM_BYTES:
            raise ValueError('Require one complete 2 MiB entry snapshot.')
        if pending_caller_load(row['entry_delay_fetch']):
            raise ValueError('A pending caller delay-slot load is not reconstructed.')
        self.backend = load_backend() if backend is None else backend
        self.row = row
        self.adapter = ArchitecturalCop2(bridge, backend=self.backend)
        self.adapter.seed(row)
        self.cpu = self.backend.Uc(self.backend.UC_ARCH_MIPS,
                                  self.backend.UC_MODE_MIPS32 | self.backend.UC_MODE_LITTLE_ENDIAN)
        self.cpu.mem_map(0, RAM_BYTES)
        self.cpu.mem_write(0, bytes(before))
        self.registers = [getattr(self.backend.reg, 'UC_MIPS_REG_' + str(i)) for i in range(32)]
        for i, register in enumerate(self.registers):
            self.cpu.reg_write(register, row['entry_cpu_gpr_' + str(i)])
        for field, register in [('lo', 'UC_MIPS_REG_LO'), ('hi', 'UC_MIPS_REG_HI'), ('sr', 'UC_MIPS_REG_CP0_STATUS')]:
            self.cpu.reg_write(getattr(self.backend.reg, register), row['entry_cpu_' + field])
        self.ranges = [(int(f['address'], 16) & native.MASK, f['bytes']) for f in functions]
        self.native_entries = {int(f['address'], 16) & native.MASK: f['function'] for f in functions}
        self.instructions, self.entries, self.recent = 0, Counter(), deque(maxlen=16)
        self._hook = self.cpu.hook_add(self.backend.UC_HOOK_CODE, self.hook)

    def close(self):
        """Release the bound callback so completed machines do not form cycles."""
        if self._hook is not None:
            self.cpu.hook_del(self._hook)
            self._hook = None

    def hook(self, cpu, address, size, unused):
        physical = address & native.MASK
        self.recent.append(address)
        if not any(start <= physical < start + length for start, length in self.ranges):
            raise ValueError('Replay left the reviewed original function ranges: ' + hex(address))
        self.instructions += 1
        if physical in self.native_entries:
            self.entries[self.native_entries[physical]] += 1
        self.adapter.step_virtual(cpu, address)

    def invoke(self, *, instruction_limit=500000):
        self.cpu.emu_start(self.row['entry_pc'], self.row['return_pc'], count=instruction_limit)
        if self.cpu.reg_read(self.backend.reg.UC_MIPS_REG_PC) != self.row['return_pc']:
            raise ValueError('Replay did not reach the captured caller return.')
        cpu = {'gpr_' + str(i): native.u32(self.cpu.reg_read(register)) for i, register in enumerate(self.registers)}
        for field, register in [('lo', 'UC_MIPS_REG_LO'), ('hi', 'UC_MIPS_REG_HI'), ('sr', 'UC_MIPS_REG_CP0_STATUS')]:
            cpu[field] = native.u32(self.cpu.reg_read(getattr(self.backend.reg, register)))
        data, control = self.adapter.views()
        return bytes(self.cpu.mem_read(0, RAM_BYTES)), cpu, data, control


def ram_difference(actual, expected):
    if len(actual) != len(expected):
        raise ValueError('RAM extents differ.')
    if actual == expected:
        return dict(equal=True, different_bytes=0, range_count=0, first_ranges=[])
    # Identify differing words first; inspect bytes only within those words.
    end = len(actual) - len(actual) % 4
    changed = []
    for i, (a, b) in enumerate(zip(memoryview(actual)[:end].cast('I'), memoryview(expected)[:end].cast('I'))):
        if a != b:
            changed.extend(at for at in range(i*4, i*4+4) if actual[at] != expected[at])
    changed.extend(at for at in range(end, len(actual)) if actual[at] != expected[at])
    ranges = []
    for at in changed:
        if ranges and at == ranges[-1][1]:
            ranges[-1][1] += 1
        else:
            ranges.append([at, at+1])
    return dict(equal=False, different_bytes=len(changed), range_count=len(ranges),
        first_ranges=[dict(start=start, end=finish, actual=actual[start:min(finish, start+32)].hex(),
                           expected=expected[start:min(finish, start+32)].hex()) for start, finish in ranges[:32]])


def compare_state(row, actual, expected, cpu, data, control, instructions):
    if (len(actual) != RAM_BYTES or len(expected) != RAM_BYTES
            or set(cpu) != set(CPU_FIELDS[:-2]) or len(data) != 32 or len(control) != 32):
        raise ValueError('Require complete RAM, 35 exposed CPU words and both 32-word GTE views.')
    ram = ram_difference(actual, expected)
    cpu_diff = {key: dict(actual=value, expected=row['cpu_' + key]) for key, value in cpu.items() if value != row['cpu_' + key]}
    gte_diff = {kind + '_' + str(i): dict(actual=value, expected=row['gte_' + kind + '_' + str(i)])
        for kind, values in [('data', data), ('control', control)] for i, value in enumerate(values)
        if value != row['gte_' + kind + '_' + str(i)]}
    span = sequence(row) - sequence(row, 'entry_')
    return dict(equal_measured_call=ram['equal'] and not cpu_diff and not gte_diff and instructions == span,
        RAM=ram, CPU_differences=cpu_diff, GTE_view_differences=gte_diff,
        actual_RAM_sha256=hashlib.sha256(actual).hexdigest(), expected_RAM_sha256=hashlib.sha256(expected).hexdigest(),
        instructions=instructions, captured_instruction_span=span, instruction_count_equal=instructions == span,
        unmeasured_system_register_changes={key: dict(entry=row['entry_cpu_' + key], returned=row['cpu_' + key])
            for key in ('cause', 'epc') if row['entry_cpu_' + key] != row['cpu_' + key]})


def collection_recordings(manifest, side='reference'):
    if side not in ('reference', 'candidate'):
        raise ValueError('Select a declared collection side.')
    manifest = Path(manifest).resolve(strict=True)
    collection = json.loads(manifest.read_text(encoding='utf-8-sig'))
    if (collection.get('schema_version') != 1 or collection.get('type') != 'ordinal_collision_recording_collection'
            or collection.get('function', 'func_8001F8B8') not in FUNCTIONS):
        raise ValueError('Require a declared primitive or hull collision collection.')
    names = collection.get(side)
    if not isinstance(names, list) or not names or any(not isinstance(name, str) or not name for name in names):
        raise ValueError('The collection side has no declared recordings.')
    recordings = []
    for name in names:
        requested = Path(name)
        windows = PureWindowsPath(name)
        if requested.is_absolute() or windows.drive or windows.root or '..' in requested.parts or '..' in windows.parts:
            raise ValueError('Recording paths must stay inside their collection.')
        folder = (manifest.parent / requested).resolve(strict=True)
        if not folder.is_dir() or folder == manifest.parent or not folder.is_relative_to(manifest.parent) or folder in recordings:
            raise ValueError('Invalid, duplicate or escaping recording directory.')
        recordings.append(folder)
    return recordings


def run(recordings, output, bridge_executable, runtime, *, lab_root=None, max_calls=None, collection=None):
    if max_calls is not None and (type(max_calls) is not int or max_calls < 1):
        raise ValueError('max_calls must be a positive integer, or omitted for every captured call.')
    folders = [Path(folder).resolve(strict=True) for folder in recordings]
    if not folders or len(set(folders)) != len(folders) or any(not folder.is_dir() for folder in folders):
        raise ValueError('Choose distinct retained collision recordings.')
    requested_output = Path(output).resolve()
    # File identity also protects case aliases on Windows volumes accessed
    # through WSL, where lexical POSIX path comparisons are case sensitive.
    for ancestor in (requested_output, *requested_output.parents):
        if ancestor.exists() and any(ancestor.samefile(folder) for folder in folders):
            raise ValueError('Write calibration output outside retained recordings.')
    source_names = ['tools/replay_collision_calls.py', 'tools/verify_collision.py', 'tools/verify_native_ai.py',
                    'tools/verify_render_gte.py', 'tools/collision_calls.py', 'tools/inspect_collision_calls.py',
                    'tools/inspect_hull_calls.py', 'tools/inspect_dispatch_history.py', 'tools/inspect_sdk_reads.py',
                    'tools/dispatch_returns.py', 'tools/psx_image.py', 'tools/nymashock_gte_bridge.cs',
                    'research/collision/trace_compiler_stack.py', 'docs/collision-function-ranges.json']
    pins = {str(ROOT/name): digest(ROOT/name) for name in source_names}
    bridge_executable = Path(bridge_executable).resolve(strict=True)
    pins[str(bridge_executable)] = digest(bridge_executable)
    collection_function = None
    if collection:
        collection = Path(collection).resolve(strict=True)
        pins[str(collection)] = digest(collection)
        collection_function = json.loads(collection.read_text(encoding='utf-8-sig')).get('function', 'func_8001F8B8')
        if collection_function not in FUNCTIONS:
            raise ValueError('The collection declares an unsupported collision function.')
    functions = json.loads((ROOT/'docs/collision-function-ranges.json').read_text())
    program = native.load_program(functions)
    for name in ('rom/SLPS_015.56', 'build/SLPS015.56'):
        pins[str(ROOT/name)] = digest(ROOT/name)
    backend = load_backend()
    output = new_output(output, lab_root)
    calls, available = [], 0
    bridge = collision.CollisionBridge(bridge_executable, runtime, output/'native-gte.log')
    try:
        for recording_index, folder in enumerate(folders, 1):
            observation = folder/'observations'
            summary = json.loads((observation/'collision-call-summary.json').read_text(encoding='utf-8-sig'))
            selected = next((name for name, (pc, _) in FUNCTIONS.items() if pc == summary.get('settings', {}).get('pc')), None)
            if selected is None:
                raise ValueError('Recording does not select a declared collision function.')
            if collection_function is not None and selected != collection_function:
                raise ValueError('Recording disagrees with the declared collection function.')
            inspector = hull if selected == 'func_8001DDF4' else primitive
            checked, retained = inspector.inspect_call_recording(folder)
            with (output/('recording-' + str(recording_index) + '-inspection.json')).open('x', encoding='utf-8') as stream:
                json.dump(dict(recording=str(folder), function=selected,
                    captured_calls=checked['collision_calls']['completed_samples'],
                    payload_sha256=checked['collision_calls']['complete_RAM_payload_sha256']), stream, indent=2)
            for name in ('collision-calls.bin', 'collision-call-ram.bin', 'collision-call-summary.json'):
                pins[str(observation/name)] = digest(observation/name)
            data = (observation/'collision-calls.bin').read_bytes()
            available += len(data)//EVENT_BYTES
            with (observation/'collision-call-ram.bin').open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as payload:
                for ordinal, values in enumerate(struct.iter_unpack('<247I', data), 1):
                    if max_calls is not None and len(calls) >= max_calls:
                        break
                    row = dict(zip(FIELDS, values))
                    before = payload[row['before_offset']:row['before_offset']+RAM_BYTES]
                    expected = payload[row['after_offset']:row['after_offset']+RAM_BYTES]
                    for function in functions:
                        pc, length = int(function['address'], 16), function['bytes']
                        if before[pc & native.MASK:(pc & native.MASK)+length] != program.target(pc, length):
                            raise ValueError('Captured native callee bytes differ: ' + function['function'])
                    result = dict(recording=str(folder), ordinal=ordinal, function=selected,
                                  entry_frame=row['entry_frame'], return_frame=row['frame'])
                    machine = None
                    try:
                        machine = NaturalMachine(bridge, functions, row, before, backend=backend)
                        actual, cpu, gte_data, gte_control = machine.invoke()
                        result.update(compare_state(row, actual, expected, cpu, gte_data, gte_control, machine.instructions),
                                      executed_functions=dict(machine.entries), adapter_counts=dict(machine.adapter.counts))
                    except Exception as error:
                        result.update(equal_measured_call=False, error=str(error))
                        if machine:
                            result.update(instructions=machine.instructions, recent_PCs=list(machine.recent))
                    finally:
                        if machine is not None:
                            machine.close()
                    calls.append(result)
                    with (output/('call-' + str(len(calls)).zfill(4) + '.json')).open('x', encoding='utf-8') as destination:
                        json.dump(result, destination, indent=2)
    finally:
        bridge.close()
    if not calls:
        raise ValueError('No captured calls were selected for replay.')
    if any(digest(path) != value for path, value in pins.items()):
        raise ValueError('A pinned original, capture, verifier or bridge changed during replay.')
    native.load_program(functions)
    equal = sum(call['equal_measured_call'] for call in calls)
    report = dict(schema_version=1, status='completed_natural_collision_calibration',
        captured_calls_available=available, calls_replayed=len(calls), skipped_by_requested_limit=available-len(calls),
        equal_measured_calls=equal, failed_measured_calls=len(calls)-equal,
        unmasked_full_RAM_matches=sum(call.get('RAM', {}).get('equal', False) for call in calls),
        exposed_35_CPU_register_matches=sum('CPU_differences' in call and not call['CPU_differences'] for call in calls),
        architectural_64_GTE_view_matches=sum('GTE_view_differences' in call and not call['GTE_view_differences'] for call in calls),
        instruction_count_matches=sum(call.get('instruction_count_equal', False) for call in calls),
        native_OP_SQR_commands=bridge.count, native_LZCS_operations=bridge.lz_count,
        backend=backend.identity, input_sha256=pins, all_pinned_inputs_preserved=True,
        canonical_build_preserved=True, game_RAM_or_running_emulator_modified=False,
        all_37_CPU_registers_replayed=False, full_native_GTE_state_restored=False,
        interrupts_or_devices_scheduled=False, original_PS1_timing_verified=False,
        full_game_parity_accepted=False, whole_feature_groups_accepted=0, new_C_bytes=0,
        scope='Functional replay of selected captured calls. All RAM and measured state are compared without exclusions. '
              'GTE views use native OP/SQR/LZCS results and reviewed transfer/readback rules; unchanged views are carried forward. '
              'CAUSE/EPC, opaque pipelines/cache/device state, interrupts, PS1 timing and other histories remain open.')
    with (output/'report.json').open('x', encoding='utf-8') as destination:
        json.dump(report, destination, indent=2)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--collection', type=Path, help='Retained ordinal collision collection.json.')
    source.add_argument('--recording', type=Path, action='append', help='Retained recording directory; repeat for several recordings.')
    parser.add_argument('--side', choices=('reference', 'candidate'), default='reference')
    parser.add_argument('--bridge', type=Path, required=True, help='Locally compiled tools/nymashock_gte_bridge.cs executable.')
    parser.add_argument('--runtime', required=True, help='Windows-form BizHawk 2.11.1 directory passed to the native bridge.')
    parser.add_argument('--output', type=Path, required=True, help='Fresh private result directory.')
    parser.add_argument('--lab-root', type=Path, help='Existing dedicated private artifact directory outside Git worktrees.')
    parser.add_argument('--max-calls', type=int, help='Optional global selection limit; omitted means all captured calls.')
    args = parser.parse_args(argv)
    try:
        if args.recording and args.side != 'reference':
            raise ValueError('--side selects a collection side; omit it for individual recordings.')
        folders = collection_recordings(args.collection, args.side) if args.collection else args.recording
        report = run(folders, args.output, args.bridge, args.runtime, lab_root=args.lab_root,
                     max_calls=args.max_calls, collection=args.collection)
        print(json.dumps({key: report[key] for key in ('status', 'captured_calls_available', 'calls_replayed',
              'equal_measured_calls', 'failed_measured_calls', 'full_game_parity_accepted', 'new_C_bytes')}))
        return 0 if not report['failed_measured_calls'] else 1
    except (OSError, ValueError, KeyError, struct.error) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
