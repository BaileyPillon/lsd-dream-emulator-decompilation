"""Compare an unaccepted complete overlap candidate through native collision/GTE."""
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import json
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import verify_collision as c
from tools import verify_native_ai as n
from tools.verify_scripted_ai import backend_identity

ADDRESS, FUNCTION_BYTES = 0x8001DDF4, 796


def candidate_patch(reference, candidate, load):
    start = 0x800 + ADDRESS - load
    end = start + FUNCTION_BYTES
    if len(candidate) != len(reference) or candidate[:start] != reference[:start] or candidate[end:] != reference[end:]:
        raise ValueError('Candidate must be a complete image differing only inside the original 796-byte overlap function.')
    return candidate[start:end]


class RecordingBridge(c.CollisionBridge):
    def __init__(self, *args):
        self.events = []
        super().__init__(*args)

    def execute(self, cr, ir, command):
        result = super().execute(cr, ir, command)
        self.events.append(dict(command=command, cr=list(cr), ir=list(ir), result=result.copy()))
        return result

    def leading(self, value):
        result = super().leading(value)
        self.events.append(dict(command=0, lzcs=n.u32(value), lzcr=result))
        return result


def capture(machine, bridge, case, read_halfword):
    machine.adapter.reset()
    bridge.events = []
    result = c.composed_check(machine, case, read_halfword)
    state = dict(cr=machine.adapter.cr[:], ir=machine.adapter.ir[:], mac=machine.adapter.mac[:],
                 lzcs=machine.adapter.lzcs, lzcr=machine.adapter.lzcr)
    events = json.dumps(bridge.events, sort_keys=True, separators=(',', ':')).encode()
    return dict(result=result, caller_buffer=bytes(machine.cpu.mem_read(c.BUFFER, c.BUFFER_BYTES)),
                state=state, events=events)


def controls(bridge, functions, patch, read_halfword):
    record = next(row for row in functions if row['function'] == 'func_8001DDF4')
    case = dict(polygons=(((-1024,-512,0),(1024,-512,0),(-1024,1536,0)),),
                query_bounds=((-128,0,-1024),(128,0,1024)), mode=1, count=1,
                flip=0, face=0, amount=0, segment=0)
    # The boundary is present in both coarse and fallback paths. Mutate every
    # occurrence, then require a native instruction execution before accepting
    # the deliberate-fault evidence.
    changed = bytearray(patch)
    offsets = [offset for offset in range(0, len(patch), 4)
               if struct.unpack_from('<I', patch, offset)[0] == 0x28420201]
    if not offsets:
        raise ValueError('Candidate lacks the reviewed 513 height-boundary instruction.')
    for offset in offsets:
        struct.pack_into('<I', changed, offset, 0x28420200)

    class FaultMachine(c.CollisionMachine):
        def __init__(self):
            self.changed_hits = Counter()
            super().__init__(bridge, functions, {ADDRESS: bytes(changed)})

        def hook(self, cpu, address, size, unused):
            offset = (address & n.MASK) - (ADDRESS & n.MASK)
            if offset in offsets:
                self.changed_hits[offset] += 1
            super().hook(cpu, address, size, unused)

    machine = FaultMachine()
    try:
        capture(machine, bridge, case, read_halfword)
    except ValueError as error:
        if 'Original composed collision differs:' not in str(error):
            raise
    else:
        raise ValueError('Height-boundary fault was not detected by the independent composed model.')
    if not sum(machine.changed_hits.values()):
        raise ValueError('Fault changed no instruction that the fixture actually reached.')
    return [{'kind': 'wrong_candidate_height_boundary', 'function': record['function'],
             'function_offsets': offsets, 'expected_word': '0x28420201', 'changed_word': '0x28420200',
             'changed_instruction_executions': dict(machine.changed_hits),
             'fixture': case, 'scope': 'Private compiled-candidate emulator memory only.'}]


def verify(args):
    import os
    os.chdir(ROOT)
    output = Path(args.output).resolve()
    if not output.is_relative_to((ROOT / '.decomp-lab').resolve()) or output.exists():
        raise ValueError('Choose a fresh private directory inside .decomp-lab.')
    output.mkdir(parents=True, exist_ok=False)
    ranges = ROOT / 'docs/collision-function-ranges.json'
    functions = json.loads(ranges.read_text())
    n.initialize_backend(n.load_program(functions))
    backend = backend_identity()
    reference = n.h.ROM
    candidate_path = Path(args.candidate).resolve()
    candidate = candidate_path.read_bytes()
    patch = candidate_patch(reference, candidate, n.h.LOAD)
    bridge_path = Path(args.bridge).resolve()
    sources = [Path(__file__), Path(__file__).with_name('overlap_candidate.c'),
               Path(__file__).with_name('prepare_overlap_candidate.py'), ranges,
               ROOT / 'tools/verify_collision.py', ROOT / 'tools/verify_render_gte.py',
               ROOT / 'tools/verify_native_ai.py', ROOT / 'tools/verify_scripted_ai.py',
               ROOT / 'tools/nymashock_gte_bridge.cs', ROOT / 'src/base/transform.c',
               ROOT / 'src/base/transform.h', candidate_path, bridge_path,
               ROOT / 'rom/SLPS_015.56', ROOT / 'build/SLPS015.56']
    preserved = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    read_halfword = lambda address: struct.unpack('<h', n.h.target(address, 2))[0]
    bridge = RecordingBridge(bridge_path, args.runtime, output / 'bridge.log')
    original = c.CollisionMachine(bridge, functions)
    recovered = c.CollisionMachine(bridge, functions, {ADDRESS: patch})
    identities, final_inputs, counts = set(), Counter(), Counter()
    outputs, commands = hashlib.sha256(), hashlib.sha256()
    started = time.monotonic()
    try:
        for index, case in enumerate(c.composition_cases(), 1):
            identity = hashlib.sha256(json.dumps(case, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            if identity in identities:
                raise ValueError('Duplicate composition parameter graph.')
            identities.add(identity)
            baseline = capture(original, bridge, case, read_halfword)
            observed = capture(recovered, bridge, case, read_halfword)
            if observed != baseline:
                (output / 'failure.json').write_bytes((json.dumps({'case': case, 'original': repr(baseline),
                                                                  'candidate': repr(observed)}, indent=2) + '\n').encode())
                raise ValueError('Original and overlap candidate differ in caller/ABI/GTE evidence.')
            final_identity = hashlib.sha256(baseline['caller_buffer'][c.CLOUD:c.CLOUD + 52] +
                json.dumps({key: value for key, value in case.items() if key not in ('flip', 'face', 'amount')},
                           sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            final_inputs[final_identity] += 1
            counts['composition_pairs'] += 1
            outputs.update(struct.pack('<3I', *baseline['result']) + baseline['caller_buffer'])
            commands.update(baseline['events'])
            if index % 1000 == 0:
                print('Overlap pairs', index, 'passed', flush=True)
        native_commands, leading_requests = bridge.count, bridge.lz_count
        fault_records = controls(bridge, functions, patch, read_halfword)
        if (backend_identity() != backend or n.check_build_current(ROOT) is not True
                or any(hashlib.sha256(path.read_bytes()).hexdigest() != digest for path, digest in preserved.items())):
            raise ValueError('Overlap evidence, backend or preserved game inputs changed.')
        report = {'status': 'passed_bounded_unpadded_overlap_candidate_pairs', 'composition_pairs': counts['composition_pairs'],
            'distinct_final_input_graphs': len(final_inputs), 'repeated_final_input_graphs': sum(final_inputs.values()) - len(final_inputs),
            'original_native_entries': dict(original.entries), 'candidate_native_entries': dict(recovered.entries),
            'original_executable_sha1': hashlib.sha1(reference).hexdigest(), 'candidate_executable_sha1': hashlib.sha1(candidate).hexdigest(),
            'candidate_function_sha256': hashlib.sha256(patch).hexdigest(),
            'changed_executable_bytes': sum(a != b for a, b in zip(reference, candidate)),
            'only_changed_function': 'func_8001DDF4', 'candidate_frame_bytes': 152, 'midpoint_storage_bytes': 12,
            'native_gte_commands_before_controls': native_commands, 'native_leading_requests_before_controls': leading_requests,
            'native_gte_control_commands': bridge.count - native_commands, 'native_leading_control_requests': bridge.lz_count - leading_requests,
            'pair_outputs_sha256': outputs.hexdigest(), 'ordered_native_events_sha256': commands.hexdigest(),
            'negative_controls_detected': fault_records, 'backend_identity': backend,
            'native_compressed_core_sha256': c.gte.CORE_SHA256,
            'preserved_dependencies': [{'path': str(path), 'sha256': digest} for path, digest in preserved.items()],
            'source_promoted': False, 'whole_feature_groups_accepted': 0, 'original_game_behavior_modified': False,
            'model_api_calls': 0, 'elapsed_seconds': round(time.monotonic() - started, 3),
            'scope': 'Unpadded complete overlap candidate versus original over manual stage/query graphs. '
                     'Full caller buffers, returns, saved registers/stack guards and exact ordered native GTE/leading events. '
                     'Original shared bounds, clipping, primitive decoding and SDK routines execute without output stubs. '
                     'Excludes natural model/scene histories, exhaustive geometry/alias combinations and complete PS1 CPU/timing acceptance.'}
        (output / 'report.json').write_bytes((json.dumps(report, indent=2) + '\n').encode())
        print(json.dumps({'pairs': counts['composition_pairs'], 'native_commands': native_commands,
                          'passed': True}), flush=True)
        return report
    finally:
        bridge.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--bridge', type=Path, required=True)
    parser.add_argument('--runtime', required=True)
    args = parser.parse_args(argv)
    verify(args)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
