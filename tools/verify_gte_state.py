"""Compare stateful native GTE transfers and renderer commands with an oracle.

This optional analysis profile loads no game or BIOS into the native GTE host.
It qualifies the register/command boundary needed by subsequent original draw
profiles; it is not a rendered-scene or PS1 hardware-timing acceptance test.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import lzma
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.gte_state_bridge import NativeStateBridge
from tools.gte_state_model import GteState, command_word, matrix_registers, require, unsigned
from tools.inventory_model_packets import file_sha

IDENTITY = (4096, 0, 0, 0, 4096, 0, 0, 0, 4096)
EDGES = (0, 1, 2, 0x7FFF, 0x8000, 0xFFFF, 0x10000, 0x7FFFFFFF,
         0x80000000, 0xFFFFFFFF, 0x12345678, 0x87654321, 0x5555AAAA, 0xAAAA5555)


def matrix(index, values=IDENTITY):
    return [(0, 8*index+i, word) for i, word in enumerate(matrix_registers(values))]


def cases():
    for kind in (0, 1):
        for register in range(32):
            for value in EDGES:
                yield dict(kind='control_transfer' if kind == 0 else 'data_transfer',
                    reset=True, writes=[(kind, register, value)], command=None)
    rng = random.Random(0x195EC2026)
    for index in range(512):
        yield dict(kind='stateful_transfer', reset=index % 37 == 0,
            writes=[(rng.randrange(2), rng.randrange(32), rng.getrandbits(32)) for _ in range(1+index % 8)], command=None)
    for mx in range(4):
        for cv in range(4):
            for vector in range(4):
                for shift in (0, 1):
                    for limit in (0, 1):
                        yield dict(kind='MVMVA_field_combinations', reset=True,
                            writes=[(kind, register, rng.getrandbits(32)) for kind in (0, 1) for register in range(32)],
                            command=command_word(0x12, shift, mx, vector, cv, limit))
    for code in (1, 6, 0x10, 0x13, 0x16, 0x1B, 0x2D, 0x2E, 0x30, 0x3F):
        for shift in (0, 1):
            for limit in (0, 1):
                for index in range(32):
                    yield dict(kind='renderer_command_flags', reset=True,
                        writes=[(kind, register, rng.getrandbits(32)) for kind in (0, 1) for register in range(32)],
                        command=command_word(code, shift=shift, limit=limit))
    for index in range(258):
        denominator = 0x8000+max(0, min(0x7FFF, index*128-64)) if index < 257 else 0xFFFF
        yield dict(kind='projection_reciprocal_bins', reset=True,
            writes=matrix(0)+[(0, 7, 32768), (0, 26, 32767), (0, 27, 1),
                (1, 0, 256 << 16 | 128), (1, 1, denominator-32768)], command=command_word(1))
    # A literal easy-to-review chain supplements random state combinations.
    yield dict(kind='composed_projection_area_depth', reset=True,
        writes=matrix(0)+[(0, 26, 256), (0, 29, 1365), (1, 0, 0), (1, 1, 4096),
                         (1, 2, 256), (1, 3, 4096), (1, 4, 256 << 16), (1, 5, 4096)], command=command_word(0x30))
    for code in (6, 0x2D):
        yield dict(kind='composed_projection_area_depth', reset=False, writes=[], command=command_word(code))


def differences(expected, observed):
    result = {}
    for key in expected:
        if expected[key] == observed.get(key):
            continue
        if key in ('cr', 'dr'):
            result[key] = [dict(register=i, expected=a, observed=b)
                           for i, (a, b) in enumerate(zip(expected[key], observed.get(key, []))) if a != b]
        else:
            result[key] = dict(expected=expected[key], observed=observed.get(key))
    return result


def control_case(fault):
    if fault == 'wrong-light-cache':
        return matrix(1)+[(1, 0, 2 << 16 | 1), (1, 1, 3)], command_word(0x12, matrix=1)
    if fault == 'wrong-translation-cache':
        return matrix(0)+[(0, 5, 123), (1, 0, 2 << 16 | 1), (1, 1, 3)], command_word(0x12, translation=0)
    if fault == 'wrong-screen-fifo':
        return [(1, 12, 10), (1, 13, 20), (1, 14, 30), (1, 15, 40)], None
    return matrix(0)+[(0, 26, 256), (1, 0, 256), (1, 1, 4096)], command_word(1)


def verify(bridge_path, runtime, destination):
    require(not destination.exists() and destination.parent.is_dir(), 'Choose a fresh bounded output directory.')
    destination.mkdir()
    started, totals, commands = time.monotonic(), Counter(), Counter()
    stream_path, digest, decoded_bytes = destination/'transactions.jsonl.xz', hashlib.sha256(), 0
    source_names = ('tools/verify_gte_state.py', 'tools/gte_state_model.py', 'tools/gte_state_bridge.py',
        'tools/nymashock_gte_state_bridge.cs', 'tools/build_nymashock_gte_state_bridge.ps1')
    before = {name:file_sha(ROOT/name) for name in source_names}
    executable_sha = file_sha(bridge_path)
    with lzma.open(stream_path, 'xb', preset=6) as journal:
        def retain(request, observed):
            nonlocal decoded_bytes
            encoded = (json.dumps(dict(request=request, observed=observed), separators=(',', ':'))+'\n').encode()
            decoded_bytes += len(encoded)
            require(decoded_bytes <= 16*1024**2, 'Decoded register journal exceeds its 16 MiB bound.')
            digest.update(encoded)
            journal.write(encoded)
        bridge, oracle = NativeStateBridge(bridge_path, runtime, destination/'native-stderr.log', exchange=retain), GteState()
        try:
            for ordinal, case in enumerate(cases()):
                require(time.monotonic()-started < 900, 'Register qualification exceeded its 15-minute bound.')
                expected = oracle.request(case['reset'], case['writes'], case['command'])
                observed = bridge.request(case['reset'], case['writes'], case['command'])
                difference = differences(expected, observed)
                if difference:
                    failure = dict(case_number=ordinal, case=case, differences=difference,
                        source_sha256=before, compiled_bridge_sha256=executable_sha)
                    with (destination/'failure.json').open('x') as stream:
                        json.dump(failure, stream, indent=2)
                    raise ValueError('Native architectural state differs at case '+str(ordinal)+': '+json.dumps(difference))
                totals[case['kind']] += 1
                if case['command'] is not None:
                    commands[hex(case['command'] & 63)] += 1
        finally:
            bridge.close()
    controls = []
    for fault in ('wrong-light-cache', 'wrong-translation-cache', 'wrong-screen-fifo', 'skip-reciprocal-init'):
        bridge = NativeStateBridge(bridge_path, runtime, destination/(fault+'-stderr.log'), fault=fault)
        writes, command = control_case(fault)
        try:
            expected = GteState().request(True, writes, command)
            observed = bridge.request(True, writes, command)
            difference = differences(expected, observed)
            require(difference and ('dr' in difference or 'cr' in difference), 'Qualification control was not detected: '+fault)
            require(observed['native_data_writes'] > 0 and (command is None or observed['native_commands'] == 1),
                    'Qualification control did not execute its actual native operations.')
            controls.append(dict(name=fault, detected=True, actual_native_data_writes=observed['native_data_writes'],
                actual_native_commands=observed['native_commands'], differences=difference,
                native_original_game_instructions_modified=False))
        finally:
            bridge.close()
    require(all(file_sha(ROOT/name) == value for name, value in before.items())
            and file_sha(bridge_path) == executable_sha, 'Executed bridge or sources changed during qualification.')
    report = dict(schema_version=1, status='native_gte_state_matches', generated_at=datetime.now(timezone.utc).isoformat(),
        elapsed_seconds=time.monotonic()-started, case_counts=dict(totals), total_cases=sum(totals.values()),
        command_counts=dict(commands), native_data_writes=oracle.data_writes, native_commands=oracle.commands,
        all_64_architectural_words_and_cycles_compared_each_request=True,
        native_WriteDR_and_commands_executed=True, native_reciprocal_table_initialized=True,
        CR_cache_transfer_and_register_reads_are_reviewed_host_code=True,
        data_and_control_register_numbers=list(range(32)), controls=controls,
        compiled_bridge_sha256=executable_sha, source_sha256=before,
        journal=dict(file=stream_path.name, bytes=stream_path.stat().st_size, sha256=file_sha(stream_path),
                     decoded_bytes=decoded_bytes, decoded_sha256=digest.hexdigest()),
        game_or_BIOS_loaded=False, original_renderer_function_verified=False,
        full_scene_rasterization_or_hardware_timing_verified=False, whole_feature_groups_accepted=0,
        new_matching_C_bytes=0, scope='Stateful GTE register/command boundary for the pinned emulator core; original draw-function composition is separate.')
    with (destination/'comparison.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    require(sum(path.stat().st_size for path in destination.iterdir()) < 4*1024**2, 'Retained output exceeds 4 MiB.')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge', type=Path, required=True)
    parser.add_argument('--runtime', required=True, help='Runtime path as understood by the Windows bridge.')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = verify(args.bridge, args.runtime, args.output)
        print(json.dumps({key:report[key] for key in ('status', 'total_cases', 'native_commands', 'case_counts')}))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps(dict(status='invalid_gte_state_qualification', error=str(error))), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
