"""Check raw Nymashock IStatable checkpoints and their recorded provenance.

The v1 envelope and managed counters are decoded. Native contents remain opaque
and are compared byte for byte. This does not accept whole-game/hardware parity.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import inspect_dispatch_history as history
from tools.compare_npc_history import owned_file
from tools.replay_cold_start_headless import require, write_json

MAX_STATE_BYTES = 256 * 1024 * 1024
START = b'ActivatedWaterboxHost_v1'
END = 'ʇsoHxoqɹǝʇɐMpǝʇɐʌᴉʇɔ∀'.encode('utf-8')
MANAGED = struct.Struct('<iiBqiiqi')
CONTROLLER = struct.Struct('<Qi')
CONTROLLER_MAGIC = 9569546739673486731


def digest(data):
    return hashlib.sha256(data).hexdigest()


def integer(value, minimum, maximum, label):
    require(type(value) is int and minimum <= value <= maximum, 'Invalid '+label+'.')
    return value


def state_envelope(data):
    require(type(data) is bytes and 1 <= len(data) <= MAX_STATE_BYTES,
            'Unsupported serialized-state size.')
    require(data.startswith(START) and data.count(END) == 1, 'Unsupported IStatable/Waterbox envelope.')
    trailer = data.index(END) + len(END)
    controller = trailer + MANAGED.size
    require(controller + CONTROLLER.size <= len(data), 'Truncated managed/controller state trailer.')
    frame, lag, is_lag, cycles, width, height, clock, remainder = MANAGED.unpack_from(data, trailer)
    require(0 <= lag <= frame <= 30001 and is_lag in (0, 1) and cycles >= 0
            and 1 <= width <= 2048 and 1 <= height <= 1024 and remainder >= 0,
            'Invalid managed state counters or video dimensions.')
    magic, switch_bytes = CONTROLLER.unpack_from(data, controller)
    require(magic == CONTROLLER_MAGIC and switch_bytes >= 0
            and controller + CONTROLLER.size + switch_bytes == len(data),
            'Invalid Nyma controller signature or retained switch-buffer length.')
    return dict(core_frame=frame, lag_count=lag, is_lag_frame=bool(is_lag), cycles=cycles,
                width=width, height=height, clock=clock, clock_remainder=remainder,
                native_serialized_bytes=trailer, controller_switch_bytes=switch_bytes,
                controller_serialized_bytes=CONTROLLER.size+switch_bytes)


def validate_states(output, summary, native):
    output = Path(output).resolve(strict=True)
    require(output.is_dir(), 'Serialized checkpoints need an existing recording directory.')
    require(type(summary) is dict and type(native) is dict, 'Serialized summaries must be objects.')
    require(type(summary.get('schema_version')) is int and summary['schema_version'] == 1
            and summary.get('status') == 'recorded_repeated_serialized_core_states'
            and summary.get('contract') == 'BizHawk.IStatable'
            and type(summary.get('serializations_per_checkpoint')) is int
            and summary['serializations_per_checkpoint'] == 2
            and summary.get('second_complete_bytes_retained_on_mismatch') is True,
            'Unsupported serialized-state summary.')
    for key in ('state_restored', 'game_RAM_injected', 'emulator_UI_controlled',
                'complete_state_parity_checked', 'original_hardware_timing_verified'):
        require(summary.get(key) is False, 'Unsupported serialized-state scope or mutation policy.')
    window = integer(summary.get('frames_advanced'), 1, 30001, 'serialized frame window')
    require(type(native['frames_advanced']) is int and window == native['frames_advanced'],
            'Serialized-state frame window differs.')
    rows = summary.get('checkpoints')
    expected = native['checkpoints']
    require(type(rows) is list and type(expected) is list and len(rows) == len(expected) >= 2,
            'Incomplete serialized checkpoint sequence.')
    validated = []
    for row, checkpoint in zip(rows, expected):
        require(type(row) is dict and type(checkpoint) is dict, 'Serialized checkpoints must be objects.')
        frame = integer(row.get('relative_frame'), 0, 30000, 'serialized relative frame')
        core = integer(row.get('core_frame'), 1, 30001, 'serialized core frame')
        require(frame == checkpoint['relative_frame'] and core == checkpoint['core_frame'] == frame+1
                and type(checkpoint['relative_frame']) is int and type(checkpoint['core_frame']) is int
                and type(row.get('before_core_frame')) is int
                and row['before_core_frame'] == core, 'Serialized checkpoint order/frame differs.')
        filename = 'core-state-'+str(frame)+'.bin'
        require(row.get('file') == filename, 'Unexpected serialized-state filename.')
        for key in ('same_frame_serializations_equal', 'MainRAM_unchanged', 'GPURAM_unchanged', 'core_frame_unchanged'):
            require(row.get(key) is True, 'A repeated state/frame/memory observation changed.')
        require(type(row.get('deterministic_emulation')) is bool, 'Missing actual core determinism declaration.')
        size = integer(row.get('bytes'), 1, MAX_STATE_BYTES, 'serialized byte count')
        require(type(row.get('repeat_bytes')) is int and row['repeat_bytes'] == size,
                'Repeated serialized size differs.')
        code = row.get('sha256')
        require(type(code) is str and re.fullmatch('[0-9a-f]{64}', code)
                and row.get('repeat_sha256') == code, 'Repeated serialized digest differs.')
        path = owned_file(output, filename)
        require(path.stat().st_size == size, 'Retained serialized size differs from its observation.')
        data = path.read_bytes()
        require(len(data) == size and digest(data) == code, 'Retained serialized bytes differ from their observation.')
        envelope = state_envelope(data)
        require(envelope['core_frame'] == core and envelope['width'] == checkpoint['image']['width']
                and envelope['height'] == checkpoint['image']['height'], 'Serialized managed counters disagree with recorded output.')
        for prefix, expected_digest in [('MainRAM', checkpoint['RAM_sha256']), ('GPURAM', checkpoint['GPU_sha256'])]:
            require(row.get(prefix+'_before_sha256') == row.get(prefix+'_after_sha256') == expected_digest,
                    'Serialized observer memory stability differs from the native checkpoint.')
        sidecar = json.loads(owned_file(output, 'core-state-'+str(frame)+'.json').read_text(encoding='utf-8-sig'))
        require(sidecar == row, 'Serialized checkpoint sidecar differs from its summary.')
        validated.append(dict(row, envelope=envelope))
    require({p.name for p in Path(output).glob('core-state-*.bin')} == {row['file'] for row in rows},
            'Unexpected or repeated serialized-state files.')
    return validated


def load_states(folder):
    folder = Path(folder).resolve(strict=True)
    manifest = json.loads(owned_file(folder, 'run-inputs.json').read_text(encoding='utf-8-sig'))
    require(manifest['settings'].get('serialized_state') is True, 'Serialized-state capture was not requested.')
    snapshots = {PureWindowsPath(item['original']['path']).name for item in manifest['source_snapshots']}
    require('SerializedCoreStateTrace.cs' in snapshots, 'Missing retained serialized-state producer source.')
    output = owned_file(folder, 'observations/report.json').parent
    native = json.loads(owned_file(output, 'report.json').read_text(encoding='utf-8-sig'))
    summary = json.loads(owned_file(output, 'serialized-state-summary.json').read_text(encoding='utf-8-sig'))
    rows = validate_states(output, summary, native)
    return manifest, output, rows


def inspect(folder):
    base, _context = history.inspect(folder)
    _manifest, _output, rows = load_states(folder)
    return dict(status='inspected_repeated_serialized_core_checkpoints', history=base,
                serialized_checkpoints=len(rows), serializer_invocations=2*len(rows),
                retained_state_bytes=sum(row['bytes'] for row in rows),
                same_frame_repeats_and_memory_checks_passed=True,
                normalization_applied=False, complete_state_parity_checked=False,
                whole_feature_groups_accepted=0, whole_NPC_encounters_accepted=0)


def compare_bytes(left, right):
    differing, offsets = 0, []
    for start in range(0, max(len(left), len(right)), 65536):
        a, b = left[start:start+65536], right[start:start+65536]
        if a == b:
            continue
        differing += abs(len(a)-len(b))
        for index, (x, y) in enumerate(zip(a, b)):
            if x != y:
                differing += 1
                if len(offsets) < 16:
                    offsets.append(start+index)
        if len(a) != len(b) and len(offsets) < 16:
            offsets.extend(range(start+min(len(a), len(b)), min(start+max(len(a), len(b)), start+min(len(a), len(b))+16-len(offsets))))
    return dict(byte_equal=left == right, differing_bytes=differing,
                length_difference=len(right)-len(left), first_differing_offsets=offsets)


def compare(reference, candidate):
    base = history.compare(reference, candidate, 'same-runtime')
    a, outa, left = load_states(reference)
    b, outb, right = load_states(candidate)
    require(a['settings'] == b['settings'], 'Raw serialized comparisons require identical recorder settings.')
    require(len(left) == len(right), 'Serialized checkpoint counts differ.')
    rows = []
    for x, y in zip(left, right):
        require(x['relative_frame'] == y['relative_frame'] and x['core_frame'] == y['core_frame']
                and x['deterministic_emulation'] is y['deterministic_emulation'],
                'Serialized comparison frame or determinism declarations differ.')
        difference = compare_bytes(owned_file(outa, x['file']).read_bytes(), owned_file(outb, y['file']).read_bytes())
        rows.append(dict(relative_frame=x['relative_frame'], core_frame=x['core_frame'],
                         reference_bytes=x['bytes'], candidate_bytes=y['bytes'], **difference))
    return dict(status='compared_raw_serialized_core_checkpoints', history=base,
                reference=str(Path(reference).resolve()), candidate=str(Path(candidate).resolve()),
                serialized_checkpoints_compared=len(rows), every_serialized_byte_equal=all(row['byte_equal'] for row in rows),
                same_frame_repeat_checks=2*len(rows), serializer_invocations=4*len(rows), rows=rows,
                normalization_applied=False, complete_state_parity_checked=False,
                original_hardware_timing_verified=False, whole_feature_groups_accepted=0,
                whole_NPC_encounters_accepted=0, new_C_bytes=0)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    one = commands.add_parser('inspect')
    one.add_argument('folder', type=Path)
    pair = commands.add_parser('compare')
    pair.add_argument('reference', type=Path)
    pair.add_argument('candidate', type=Path)
    one.add_argument('--output', required=True, type=Path)
    pair.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        require(not os.path.lexists(args.output), 'Preserve existing comparison evidence.')
        result = inspect(args.folder) if args.command == 'inspect' else compare(args.reference, args.candidate)
        write_json(args.output, result)
        print(json.dumps({key: value for key, value in result.items() if key not in ('rows', 'history')}))
        return 0 if result.get('every_serialized_byte_equal', True) else 1
    except (OSError, ValueError, KeyError, TypeError, struct.error) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
