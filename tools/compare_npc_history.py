"""Compare frozen NPC-history outputs with explicit runtime-profile boundaries.

Default comparison requires identical runtime files. The observer-output mode
allows only the declared PS1 core artifacts to differ, and reports that change.
Neither mode accepts complete emulator state, hardware timing or whole NPCs.
"""
import argparse
from bisect import bisect_right
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_npc_observer import UPSTREAM, MEDNAFEN, SOURCE_SHA256
from tools.record_npc_history import HOST_SOURCES, STOCK_RUNTIME, digest_text, expand_program, validate_program
from tools.replay_cold_start_headless import require, write_json
from tools.runtime_inputs import content_identity, record_file

FRAME_FIELDS = ('relative_frame', 'core_frame', 'phase', 'gpu_sha256', 'sample_frames', 'total_sample_frames')
RAM_FIELDS = ('relative_frame', 'core_frame', 'RAM_sha256')
ENTRY_FIELDS = ('relative_frame', 'pc', 'entity', 'ra', 'sp', 'timestamp', 'instruction', 'context_tick')
CORE_FILES = {'dll/shock.wbx', 'dll/shock.wbx.zst'}
SOURCE_NAMES = {*(path.name for path in HOST_SOURCES), 'npc_entry_observer.h', 'record_npc_history.py',
                'build_npc_observer.py', 'replay_cold_start_headless.py', 'runtime_inputs.py', 'csc.dll'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def files_equal(left, right):
    if left.stat().st_size != right.stat().st_size:
        return False
    with left.open('rb') as before, right.open('rb') as after:
        while True:
            block = before.read(1024 * 1024)
            if block != after.read(1024 * 1024):
                return False
            if not block:
                return True


def owned_file(folder, name):
    require(isinstance(name, str) and '\\' not in name and ':' not in name, 'Invalid retained file path.')
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and '..' not in relative.parts, 'Retained files must stay inside their recording.')
    path = (folder / name).resolve(strict=True)
    require(path.is_relative_to(folder), 'A retained file resolves outside its recording.')
    return path


def verify_file(folder, name, expected):
    actual = record_file(owned_file(folder, name))
    require(content_identity(actual) == content_identity(expected), 'A retained file differs from its recorded identity: ' + name)
    return actual


def read_rows(path, fields):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        require(tuple(reader.fieldnames or ()) == fields, 'Unexpected observation columns: ' + Path(path).name)
        rows = list(reader)
    require(all(None not in row and None not in row.values() for row in rows), 'Truncated or extra observation columns.')
    return rows


def inspect_png(data, width, height):
    """Check the retained PNG container; raw RGB is the pixel comparison input."""
    require(data.startswith(b'\x89PNG\r\n\x1a\n'), 'A retained image is not a PNG container.')
    offset, kinds = 8, []
    while offset < len(data):
        require(offset + 12 <= len(data), 'Truncated PNG chunk.')
        size = struct.unpack_from('>I', data, offset)[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + size
        require(end <= len(data), 'Truncated PNG payload.')
        body = data[offset + 8:offset + 8 + size]
        require(zlib.crc32(kind + body) & 0xFFFFFFFF == struct.unpack_from('>I', data, end - 4)[0],
                'A PNG chunk checksum disagrees with its bytes.')
        if not kinds:
            require(kind == b'IHDR' and size == 13, 'PNG must begin with its complete image header.')
            require(struct.unpack_from('>II', body) == (width, height), 'PNG dimensions disagree with native RGB.')
        else:
            require(kind != b'IHDR', 'Repeated PNG image header.')
        kinds.append(kind)
        offset = end
        if kind == b'IEND':
            require(size == 0 and offset == len(data), 'PNG has an invalid end or trailing bytes.')
            break
    require(kinds and kinds[-1] == b'IEND' and b'IDAT' in kinds, 'Incomplete PNG image container.')


def runtime_differences(left, right, mode):
    require(mode in ('same-runtime', 'observer-output'), 'Unknown runtime comparison mode.')
    before = {name: content_identity(value) for name, value in left['actual_runtime_files'].items()}
    after = {name: content_identity(value) for name, value in right['actual_runtime_files'].items()}
    changed = sorted(name for name in set(before) | set(after) if before.get(name) != after.get(name))
    if mode == 'same-runtime':
        require(left['runtime_kind'] == right['runtime_kind'] and not changed,
                'Runtime identities differ; same-runtime comparison does not accept an observer-core change.')
    else:
        require({left['runtime_kind'], right['runtime_kind']} == {'distributed', 'npc_observer'},
                'Observer-output mode requires one distributed run and one declared observer run.')
        require(changed and set(changed) <= CORE_FILES, 'Observer-output mode permits only the declared PS1 core artifacts to differ.')
    return [dict(file=name, reference=before.get(name), candidate=after.get(name)) for name in changed]


def validate_entries(rows, program, frames, executable):
    target = program['trace']
    pc = int(target['watched_pc'], 0)
    require(executable.startswith(b'PS-X EXE'), 'Expected the original PS-X executable.')
    load = struct.unpack_from('<I', executable, 0x18)[0]
    at = pc - load + 0x800
    require(0x800 <= at and at + target['function_bytes'] <= len(executable), 'The watched function lies outside the executable.')
    require(sha(executable[at:at + target['function_bytes']]) == target['function_sha256'],
            'The complete watched function differs from its original source profile.')
    instruction = struct.unpack_from('<I', executable, at)[0]
    entries = []
    for row in rows:
        require(all(isinstance(row[name], str) and len(row[name]) == 8
                    and all(char in '0123456789ABCDEF' for char in row[name])
                    for name in ('pc', 'entity', 'ra', 'sp', 'instruction')), 'Invalid native register or instruction word.')
        value = {name: int(text, 16) if name in ('pc', 'entity', 'ra', 'sp', 'instruction') else int(text)
                 for name, text in row.items()}
        require(value['pc'] == pc and value['instruction'] == instruction, 'An entry has the wrong original PC or instruction.')
        require(target['arm_frame'] <= value['relative_frame'] <= frames and value['timestamp'] >= 0,
                'An entry lies outside its native observation window.')
        require(value['entity'] % 4 == 0 and 0x80010000 <= value['entity'] <= 0x80200000 - 0x108
                and value['sp'] % 8 == 0 and 0x80010000 <= value['sp'] < 0x80200000,
                'Invalid original entity or stack register.')
        call_at = value['ra'] - 8 - load + 0x800
        require(0x800 <= call_at <= len(executable) - 4, 'The original return address is outside the executable.')
        call = struct.unpack_from('<I', executable, call_at)[0]
        require(call >> 26 == 3 or (call >> 26 == 0 and call & 63 == 9), 'The return address does not follow an original link instruction.')
        entries.append(value)
    if frames == program['frames']:
        require(len(entries) == target['expected_entries'], 'The complete history has a missing or extra original entry.')
    elif frames >= target['expected_first_frame'] and target['expected_entries']:
        require(entries, 'No original entries were recorded in the expected active window.')
    if entries:
        require(len({row['entity'] for row in entries}) == 1, 'This profile qualifies a single original entity history.')
        require([row['context_tick'] for row in entries] == list(range(len(entries))), 'Original entry ticks are missing, repeated or reordered.')
        require([(row['relative_frame'], row['timestamp']) for row in entries]
                == sorted((row['relative_frame'], row['timestamp']) for row in entries), 'Native entry boundaries are out of order.')
        require(entries[0]['relative_frame'] == target['expected_first_frame'], 'The first original entry frame differs from the recorded profile.')
        if frames == program['frames']:
            require(entries[-1]['relative_frame'] == target['expected_last_frame'], 'The last original entry frame differs from the recorded profile.')
    return entries


def inspect_run(folder, executable, *, context_clock_guard=None):
    """Validate a frozen run, optionally requiring rooted clock corroboration.

    The guard can exclude detached storage from clock evidence. At least one
    accepted original context must still corroborate the instruction history.
    All input, output, instruction and provenance checks remain mandatory.
    """
    require(context_clock_guard is None or callable(context_clock_guard), 'Invalid context clock guard.')
    folder = Path(folder).resolve(strict=True)
    inputs = json.loads((folder / 'run-inputs.json').read_text(encoding='utf-8-sig'))
    require(inputs.get('schema_version') == 1 and inputs.get('runtime_kind') in ('distributed', 'npc_observer'),
            'Unsupported NPC recording manifest.')
    require(all(inputs.get(name) is False for name in ('game_RAM_injected', 'restored_state', 'emulator_UI_controlled')),
            'Require controller-only cold boot without game RAM injection or emulator UI control.')
    result = json.loads((folder / 'result.json').read_text(encoding='utf-8-sig'))
    require(result['status'] == 'recorded_pinned_NPC_history' and result['input_files_preserved'] is True
            and json.loads((folder / 'exit.json').read_text())['exit_code'] == 0, 'The native recording did not finish with preserved inputs.')
    program = validate_program(inputs['program'])
    require(sha(executable) == program['executable_sha256'], 'The executable differs from this original game profile.')
    verify_file(folder, 'program.json', inputs['program_file'])
    require(json.loads((folder / 'program.json').read_bytes()) == program, 'The retained program differs from the launch manifest.')
    verify_file(folder, 'settings.json', inputs['settings_file'])
    settings = json.loads((folder / 'settings.json').read_bytes())
    require(settings == inputs['settings'], 'Native settings differ from their launch manifest.')
    frames = settings['frames']
    require(type(frames) is int and 1 <= frames <= program['frames'], 'Invalid native input window.')
    expected_settings = dict(frames=frames,
        checkpoint_frames=sorted({frame for frame in program['checkpoint_frames'] if frame <= frames} | {0, frames}),
        RAM_sample_interval=program['RAM_sample_interval'], trace_enabled=inputs['runtime_kind'] == 'npc_observer',
        watched_pc=int(program['trace']['watched_pc'], 0), arm_frame=program['trace']['arm_frame'])
    require(settings == expected_settings, 'Native settings do not describe the complete declared controller profile.')
    verify_file(folder, 'submitted.tsv', inputs['submitted'])
    require((folder / 'submitted.tsv').read_bytes() == expand_program(program, frames), 'Submitted native controls differ from the static program.')
    snapshots = inputs.get('source_snapshots', [])
    require(snapshots and len(snapshots) == len(inputs['source_pins']), 'Missing frozen recorder source inputs.')
    by_name = {}
    for item, original in zip(snapshots, inputs['source_pins']):
        require(item['original'] == original and content_identity(item) == content_identity(original), 'A frozen source identity is inconsistent.')
        verify_file(folder, item['file'], item)
        name = original['path'].replace('\\', '/').rsplit('/', 1)[-1]
        if name in SOURCE_NAMES:
            require(name not in by_name, 'Ambiguous repeated recorder source name.')
            by_name[name] = content_identity(item)
    require(set(by_name) == SOURCE_NAMES, 'The recording omits a required recorder/compiler source identity.')
    for path in HOST_SOURCES:
        verify_file(folder, 'host/' + path.name, inputs['copied_host_sources'][path.name])
        require(content_identity(inputs['copied_host_sources'][path.name]) == by_name[path.name], 'Compiled and frozen host sources disagree.')
    verify_file(folder, 'host/RecordNpcHistory.exe', inputs['host_binary'])
    verify_file(folder, 'host/RecordNpcHistory.exe.config', inputs['host_configuration'])
    runtime = inputs['actual_runtime_files']
    require(runtime and all(name.startswith(('dll/', 'gamedb/')) for name in runtime), 'Invalid retained runtime file set.')
    for name, identity in runtime.items():
        verify_file(folder, 'host/' + name, identity)
    current = {str(path.relative_to(folder / 'host')).replace('\\', '/')
               for name in ('dll', 'gamedb') for path in (folder / 'host' / name).rglob('*') if path.is_file()}
    require(current == set(runtime), 'The retained runtime gained or lost a file.')
    require(all(name in runtime and runtime[name]['sha256'] == digest
                for name, digest in STOCK_RUNTIME.items() if name not in CORE_FILES),
            'A retained runtime binding differs from the qualified distributed assembly set.')
    if inputs['runtime_kind'] == 'distributed':
        require(inputs.get('observer_profile') is None and 'dll/shock.wbx' not in runtime
                and all(runtime[name]['sha256'] == digest for name, digest in STOCK_RUNTIME.items()),
                'The distributed run contains an unsupported or shadowing core.')
    else:
        profile = inputs['observer_profile']
        require(profile['status'] == 'built_separate_NPC_observer_core' and profile['upstream_commit'] == UPSTREAM
                and profile['mednafen_commit'] == MEDNAFEN and profile['existing_CPU_source_modified'] is False
                and profile['input_files_preserved'] is True and profile['original_adapter_sha256'] == SOURCE_SHA256['shock.cpp']
                and profile['observer_header_sha256'] == by_name['npc_entry_observer.h']['sha256']
                and profile['producer_sha256'] == by_name['build_npc_observer.py']['sha256'], 'Unsupported observer build provenance.')
        for key, name in (('core', 'dll/shock.wbx'), ('compressed_core', 'dll/shock.wbx.zst')):
            require(content_identity(profile[key]) == content_identity(runtime[name]), 'Loaded observer core differs from its build profile.')
    source = inputs['source_manifest']
    require(source['schema_version'] == 2 and source['selected_core'] == 'Nymashock' and source['scenario'] == 'boot'
            and source['start_kind'] == 'cold_boot' and source['start_state'] is None
            and len(source['disc']['tracks']) == 1 and source['disc']['tracks'][0]['sha256'] == program['disc_track_sha256']
            and set(source['bios']) == {'J', 'U', 'E'}, 'Unsupported original launch input identity.')
    native = json.loads((folder / 'observations/report.json').read_text(encoding='utf-8-sig'))
    require(native['status'] == 'recorded_static_NPC_history' and native['frames_advanced'] == frames + 1
            and native['submitted_frames'] == frames and all(native[name] is False for name in
                ('restored_state', 'game_RAM_injected', 'emulator_UI_controlled', 'complete_state_parity_checked')),
            'The native observation window or execution boundary is inconsistent.')
    rows = read_rows(folder / 'observations/frames.tsv', FRAME_FIELDS)
    require(len(rows) == frames + 1, 'Missing or extra native GPU observation boundaries.')
    total, phases = 0, ['initial_neutral'] + [row['phase'] for row in read_rows(folder / 'submitted.tsv',
        ('relative_frame', 'core_frame', 'phase', 'buttons', *program['controller']['column_order']))]
    for frame, row in enumerate(rows):
        require(int(row['relative_frame']) == frame and int(row['core_frame']) == frame + 1
                and row['phase'] == phases[frame] and digest_text(row['gpu_sha256']), 'Wrong native frame, phase or complete GPU identity.')
        count = int(row['sample_frames'])
        require(count >= 0, 'Invalid native PCM sample count.')
        total += count
        require(int(row['total_sample_frames']) == total, 'Native PCM totals are not consecutive.')
    audio = folder / 'observations/audio.pcm'
    require(audio.stat().st_size == total * 4 and native['all_PCM_sample_frames'] == total, 'Truncated or appended complete native PCM.')
    memory = read_rows(folder / 'observations/ram-samples.tsv', RAM_FIELDS)
    expected_samples = sorted(set(range(0, frames + 1, settings['RAM_sample_interval'])) | set(settings['checkpoint_frames']))
    require([int(row['relative_frame']) for row in memory] == expected_samples and native['RAM_samples'] == len(memory),
            'Missing or extra complete RAM sample boundaries.')
    require(all(int(row['core_frame']) == int(row['relative_frame']) + 1 and digest_text(row['RAM_sha256']) for row in memory),
            'Invalid native RAM observation identity.')
    checkpoints = native['checkpoints']
    require([row['relative_frame'] for row in checkpoints] == settings['checkpoint_frames'], 'Native checkpoint boundaries differ from the program.')
    memory_by_frame = {int(row['relative_frame']): row['RAM_sha256'] for row in memory}
    raw_checkpoints = {}
    for row in checkpoints:
        frame = row['relative_frame']
        require(row['core_frame'] == frame + 1, 'Wrong native checkpoint core boundary.')
        ram = (folder / f'observations/mainram-{frame}.bin').read_bytes()
        gpu = (folder / f'observations/gpu-{frame}.bin').read_bytes()
        image = row['image']
        width, height = image['width'], image['height']
        require(type(width) is int and type(height) is int and 1 <= width <= 2048 and 1 <= height <= 1024,
                'Invalid native RGB dimensions.')
        rgb = (folder / f'observations/rgb-{frame}.bin').read_bytes()
        require(len(ram) == 0x200000 and sha(ram) == row['RAM_sha256'] == memory_by_frame[frame], 'Complete checkpoint RAM disagrees with its observations.')
        require(len(gpu) == 0x100000 and sha(gpu) == row['GPU_sha256'] == rows[frame]['gpu_sha256'], 'Complete checkpoint GPU disagrees with its observations.')
        require(len(rgb) == width * height * 3 and sha(rgb) == image['RGB_sha256'], 'Complete RGB bytes disagree with the native checkpoint.')
        inspect_png((folder / f'observations/frame-{frame}.png').read_bytes(), width, height)
        raw_checkpoints[frame] = dict(RAM=folder / f'observations/mainram-{frame}.bin',
            GPU=folder / f'observations/gpu-{frame}.bin', RGB=folder / f'observations/rgb-{frame}.bin',
            dimensions=(width, height))
    entries = []
    if settings['trace_enabled']:
        entries = validate_entries(read_rows(folder / 'observations/npc-instructions.tsv', ENTRY_FIELDS), program, frames, executable)
        summary = json.loads((folder / 'observations/npc-trace-summary.json').read_text())
        require(summary['original_instruction_entries'] == native['instruction_entries'] == len(entries)
                and summary['watched_pc'] == f"{settings['watched_pc']:08X}"
                and summary['hook_enabled_relative_frame'] == settings['arm_frame']
                and summary['hook_enabled'] == native['observer_enabled'] == (frames >= settings['arm_frame']),
                'Native entry count or observer enablement is inconsistent.')
        require(summary['first_observed_entry_frame'] == (entries[0]['relative_frame'] if entries else -1)
                and summary['last_observed_entry_frame'] == (entries[-1]['relative_frame'] if entries else -1),
                'Native entry summary disagrees with its complete trace.')
    else:
        require(native['instruction_entries'] == 0 and native['observer_enabled'] is False
                and not (folder / 'observations/npc-instructions.tsv').exists(), 'The distributed run unexpectedly contains an enabled observer.')
    clock_checks = 0
    if entries:
        event_frames = [row['relative_frame'] for row in entries]
        address = entries[0]['entity'] & 0x1FFFFFFF
        pc = settings['watched_pc']
        code_at = pc - struct.unpack_from('<I', executable, 0x18)[0] + 0x800
        for frame, raw in raw_checkpoints.items():
            if frame < entries[0]['relative_frame']:
                continue
            ram = raw['RAM'].read_bytes()
            require(ram[pc & 0x1FFFFFFF:(pc & 0x1FFFFFFF) + program['trace']['function_bytes']]
                    == executable[code_at:code_at + program['trace']['function_bytes']], 'The loaded original callback span differs from its executable.')
            if context_clock_guard is not None:
                reachable = context_clock_guard(ram, entries[0]['entity'], program['trace']['entity_id'], frame)
                require(type(reachable) is bool, 'The context clock guard must return a Boolean.')
                if not reachable:
                    continue
            word = lambda offset: struct.unpack_from('<I', ram, address + offset)[0]
            if (word(0) == 0x80089AD4 and word(0x98) == program['trace']['entity_id']
                    and word(0x9C) == program['trace']['entity_id'] + 1):
                require(word(0xA4) == entries[0]['entity'] and word(0xA8) == pc
                        and word(0xA0) == bisect_right(event_frames, frame), 'Original callback registration or initialized tick history disagrees with its entries.')
                clock_checks += 1
        require(clock_checks > 0, 'No complete checkpoint corroborates the original entity registration and clock.')
    require(native['observer_requested'] == settings['trace_enabled'], 'Native observer selection differs from its input profile.')
    return dict(folder=folder, inputs=inputs, program=program, settings=settings, native=native,
        frames=rows, RAM_samples=memory, raw_checkpoints=raw_checkpoints, entries=entries, clock_checks=clock_checks,
        source_identity=by_name, audio=audio)


def compare(reference, candidate, executable, mode='same-runtime'):
    source_paths = [Path(__file__).resolve(), ROOT / 'tools/record_npc_history.py',
                    ROOT / 'tools/build_npc_observer.py', ROOT / 'tools/replay_cold_start_headless.py',
                    ROOT / 'tools/runtime_inputs.py']
    source_pins = [record_file(path) for path in source_paths]
    executable = Path(executable).read_bytes()
    left, right = [inspect_run(folder, executable) for folder in (reference, candidate)]
    require(left['program'] == right['program'] and left['source_identity'] == right['source_identity'], 'Controller program or frozen recorder/compiler sources differ.')
    changed_runtime = runtime_differences(left['inputs'], right['inputs'], mode)
    before, after = [dict(run['settings']) for run in (left, right)]
    if mode == 'observer-output':
        before.pop('trace_enabled'); after.pop('trace_enabled')
    require(before == after, 'Native controller, snapshot or observer boundaries differ.')
    def launch_identity(run):
        source = run['inputs']['source_manifest']
        return dict(disc_layout=source['disc']['layout'], tracks=[content_identity(item) for item in source['disc']['tracks']],
                    bios={key: content_identity(item) for key, item in source['bios'].items()},
                    host_configuration=content_identity(run['inputs']['host_configuration']))
    require(launch_identity(left) == launch_identity(right), 'Original disc, BIOS or native host configuration identities differ.')
    frame_differences = sum(a != b for a, b in zip(left['frames'], right['frames']))
    RAM_sample_differences = sum(a != b for a, b in zip(left['RAM_samples'], right['RAM_samples']))
    checkpoints = []
    for frame in before['checkpoint_frames']:
        a, b = left['raw_checkpoints'][frame], right['raw_checkpoints'][frame]
        checkpoints.append(dict(relative_frame=frame, MainRAM_equal=files_equal(a['RAM'], b['RAM']), GPU_equal=files_equal(a['GPU'], b['GPU']),
            RGB_equal=a['dimensions'] == b['dimensions'] and files_equal(a['RGB'], b['RGB']),
            PNG_container_bytes_equal=(left['folder'] / f'observations/frame-{frame}.png').read_bytes()
                                      == (right['folder'] / f'observations/frame-{frame}.png').read_bytes()))
    audio_equal = files_equal(left['audio'], right['audio'])
    entries_equal = left['entries'] == right['entries'] if left['settings']['trace_enabled'] and right['settings']['trace_enabled'] else None
    passed = (not frame_differences and not RAM_sample_differences and audio_equal and entries_equal is not False
              and all(row['MainRAM_equal'] and row['GPU_equal'] and row['RGB_equal'] for row in checkpoints))
    require([record_file(path) for path in source_paths] == source_pins, 'Comparison source changed while checking the retained history.')
    return dict(status='passed_NPC_history_output_comparison' if passed else 'recorded_NPC_history_output_differences',
        comparison_source_pins=source_pins,
        mode=mode, runtime_differences=changed_runtime, input_frames=before['frames'], native_observation_pairs=len(left['frames']),
        RAM_observation_pairs=len(left['RAM_samples']), differing_frame_observations=frame_differences,
        differing_RAM_sample_observations=RAM_sample_differences, checkpoint_comparisons=checkpoints,
        complete_PCM_equal=audio_equal, PCM_bytes_per_run=[run['audio'].stat().st_size for run in (left, right)],
        complete_PCM_sha256=[record_file(run['audio'])['sha256'] for run in (left, right)],
        original_instruction_entries_per_run=[len(run['entries']) for run in (left, right)],
        original_entry_records_equal=entries_equal, original_clock_checkpoint_checks=[run['clock_checks'] for run in (left, right)],
        executable_sha256=sha(executable), program_sha256=record_file(left['folder'] / 'program.json')['sha256'],
        input_manifests=[record_file(run['folder'] / 'run-inputs.json') for run in (left, right)],
        PNG_containers_decoded=False, raw_RGB_pixels_compared=True, complete_state_parity_checked=False,
        original_hardware_timing_verified=False, new_C_bytes=0, new_bounded_NPC_callbacks=0,
        whole_NPC_encounters_accepted=0, whole_feature_groups_accepted=0,
        scope='Static controller history; complete declared frame/GPU hashes, sampled full-RAM hashes, selected full RAM/GPU/raw RGB, complete PCM and validated original entries when enabled. No complete-state or whole-feature acceptance.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--executable', type=Path, default=ROOT / 'rom/SLPS_015.56')
    parser.add_argument('--mode', choices=('same-runtime', 'observer-output'), default='same-runtime')
    parser.add_argument('--output', type=Path, required=True, help='New JSON comparison record.')
    args = parser.parse_args(argv)
    require(not args.output.exists(), 'Preserve the existing comparison record.')
    result = compare(args.reference, args.candidate, args.executable, args.mode)
    write_json(args.output, result)
    print(json.dumps({key: result[key] for key in ('status', 'mode', 'native_observation_pairs',
        'differing_frame_observations', 'differing_RAM_sample_observations', 'complete_PCM_equal', 'original_instruction_entries_per_run')}))
    return 0 if result['status'] == 'passed_NPC_history_output_comparison' else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError, struct.error) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
