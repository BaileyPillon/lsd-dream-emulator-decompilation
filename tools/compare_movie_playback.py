"""Compare the supported neutral startup-movie recorder without masking state."""

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import wave
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.compare_runtime import byte_comparison, compare_audio, compare_state
from tools.runtime_inputs import compare_inputs

FIELDS = ('relative_frame', 'core_frame', 'native_tables_ready', 'active_movie', 'rng', 'watchdog_counter')
FIELDS += tuple(f'movie_{offset:02x}' for offset in range(0, 0x6c, 4))
FIELDS += tuple(f'stream_{offset:02x}' for offset in range(0, 0x5c, 4))
FIELDS += ('gpu_sha256',)
STARTUP_PATHS = {90: '/CDI/ETC/ASMK.STR', **{cutoff: f'/CDI/ETC/OPENING{letter}.STR'
                 for letter, cutoff in zip('ABCDEFG', (1060, 1088, 953, 1179, 979, 1231, 1046))}}
NUMERIC_NEUTRAL = {'Disk Index': Decimal(0),
                   'P1 Left Stick Left / Right': Decimal(128), 'P1 Left Stick Up / Down': Decimal(128),
                   'P1 Right Stick Left / Right': Decimal(128), 'P1 Right Stick Up / Down': Decimal(128)}
DIGITAL_NAMES = {'Close Tray', 'Open Tray', 'P1 Analog', 'P1 D-Pad Down', 'P1 D-Pad Left',
                 'P1 D-Pad Right', 'P1 D-Pad Up', 'P1 L1', 'P1 L2', 'P1 Left Stick, Button',
                 'P1 R1', 'P1 R2', 'P1 Right Stick, Button', 'P1 Select', 'P1 Start',
                 'P1 X', 'P1 □', 'P1 △', 'P1 ○', 'Power', 'Reset'}


def read_tsv(path):
    with Path(path).open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        header, rows = tuple(reader.fieldnames or ()), list(reader)
    if (not header or len(set(header)) != len(header) or
            any(None in row or any(value is None for value in row.values()) for row in rows)):
        raise ValueError('Missing, extra, or duplicate TSV fields: ' + str(path))
    return header, rows


def aligned_pointer(value, size):
    return 0x80010000 <= value <= 0x80200000 - size and value % 4 == 0


def native_file_identity(row):
    raw = b''.join(int(row[f'stream_{offset:02x}']).to_bytes(4, 'little')
                   for offset in range(0x0c, 0x24, 4))
    def bcd(value):
        if (value & 15) > 9 or (value >> 4) > 9:
            raise ValueError('Invalid BCD CD-file location.')
        return (value >> 4) * 10 + (value & 15)
    minute, second, sector = [bcd(value) for value in raw[:3]]
    lba = (minute * 60 + second) * 75 + sector - 150
    size = struct.unpack_from('<I', raw, 4)[0]
    if second >= 60 or sector >= 75 or lba < 0 or size <= 0 or size % 2048:
        raise ValueError('Invalid movie CD-file extent.')
    if b'\0' not in raw[8:]:
        raise ValueError('Unterminated native CD filename.')
    filename = raw[8:].split(b'\0', 1)[0].decode('ascii')
    if not re.fullmatch(r'[A-Z0-9_]+\.STR;1', filename):
        raise ValueError('Unsupported native CD filename.')
    return {'filename': filename, 'lba': lba, 'logical_bytes': size, 'sectors': size // 2048}


def read_observations(path, frames):
    header, rows = read_tsv(path)
    if header != FIELDS or len(rows) != frames + 1:
        raise ValueError('Require every frame, including frame zero, with the supported movie header.')
    core_start = int(rows[0]['core_frame'])
    if core_start < 0:
        raise ValueError('Core frame numbers must be nonnegative.')
    ready_seen = False
    for index, row in enumerate(rows):
        if int(row['relative_frame']) != index or int(row['core_frame']) != core_start + index:
            raise ValueError('Movie observations must have consecutive relative and core frames.')
        if not re.fullmatch('[0-9a-f]{64}', row['gpu_sha256']):
            raise ValueError('Require a complete GPU SHA-256 for every observation.')
        if row['native_tables_ready'] not in ('0', '1'):
            raise ValueError('Invalid native-table readiness value.')
        ready = row['native_tables_ready'] == '1'
        if ready_seen and not ready:
            raise ValueError('The startup profile does not support unloading the reference program.')
        ready_seen |= ready
        active = int(row['active_movie'])
        if ready and any(not 0 <= int(row[field]) <= 0xffffffff for field in ('rng', 'watchdog_counter')):
            raise ValueError('Native global words must be unsigned 32-bit values.')
        if active:
            if (not ready or not aligned_pointer(active, 0x6c) or
                    int(row['movie_00']) != 0x8006f614 or int(row['stream_00']) != 0x800817e0 or
                    not aligned_pointer(int(row['movie_60']), 0x5c)):
                raise ValueError('Movie/stream pointers or vtables differ from the supported reference.')
            if any(not 0 <= int(row[field]) <= 0xffffffff for field in FIELDS[3:-1]):
                raise ValueError('Native words must be unsigned 32-bit values.')
            requested, state = int(row['movie_5c']), int(row['stream_2c'])
            if requested not in STARTUP_PATHS or state not in (1, 2, 4):
                raise ValueError('This profile supports startup movies in setup, streaming, and stopped states.')
            if (int(row['movie_24']), int(row['movie_28'])) != (320, 240):
                raise ValueError('This startup profile requires the native 320 by 240 viewport.')
            file = native_file_identity(row)
            if file['filename'] != STARTUP_PATHS[requested].rsplit('/', 1)[1] + ';1':
                raise ValueError('Opened CD filename disagrees with the requested startup movie.')
            # Setup may still contain an earlier size-derived threshold and a
            # stale counter. Do not classify those words as consumed frames.
            if state in (2, 4) and (int(row['stream_40']) != requested or
                                     not 0 <= int(row['stream_58']) < requested):
                raise ValueError('Active stream threshold or accepted-frame counter is inconsistent.')
            if any(row[field] not in ('0', '1') for field in ('movie_44', 'movie_48')):
                raise ValueError('Invalid movie completion flags.')
        elif any(row[field] != '-' for field in FIELDS[6:-1]):
            raise ValueError('Inactive movie fields must be explicitly absent.')
        if not ready and (active or row['rng'] != '-' or row['watchdog_counter'] != '-'):
            raise ValueError('Native state was recorded before the table guards passed.')
    return rows


def summarize_lifetimes(rows):
    lifetimes, active = [], []
    for row in rows:
        if row['active_movie'] != '0':
            if active and row['active_movie'] != active[-1]['active_movie']:
                lifetimes.append((active, None))
                active = []
            active.append(row)
        elif active:
            lifetimes.append((active, int(row['relative_frame'])))
            active = []
    if active:
        lifetimes.append((active, None))
    result = []
    for number, (samples, cleared) in enumerate(lifetimes, 1):
        requested = {int(row['movie_5c']) for row in samples}
        if len(requested) != 1:
            raise ValueError('A movie request changed within one observed lifetime.')
        cutoff = requested.pop()
        streaming = [row for row in samples if row['stream_2c'] == '2']
        ids = sorted({int(row['stream_58']) for row in streaming})
        contiguous = bool(ids) and ids == list(range(ids[-1] + 1))
        end = any(row['movie_48'] == '1' for row in samples)
        decoded = any(row['movie_44'] == '1' for row in samples)
        complete = cleared is not None and contiguous and ids[-1] == cutoff - 1 and end and decoded
        geometry = sorted({(struct.unpack('<hh', struct.pack('<I', int(row['movie_20'])))[0],
                            struct.unpack('<hh', struct.pack('<I', int(row['movie_20'])))[1],
                            int(row['movie_24']), int(row['movie_28'])) for row in samples})
        opened = {tuple(native_file_identity(row).items()) for row in samples}
        if len(opened) != 1:
            raise ValueError('Native CD-file identity changed within one movie lifetime.')
        result.append({'sequence': number, 'path': STARTUP_PATHS[cutoff],
                       'opened_file': dict(opened.pop()),
                       'first_active_frame': int(samples[0]['relative_frame']),
                       'last_active_frame': int(samples[-1]['relative_frame']),
                       'first_inactive_frame_after': cleared, 'requested_cutoff': cutoff,
                       'setup_thresholds': sorted({int(r['stream_40']) for r in samples if r['stream_2c'] == '1'}),
                       'setup_raw_frame_values': sorted({int(r['stream_58']) for r in samples if r['stream_2c'] == '1'}),
                       'maximum_accepted_frame_id_while_streaming': ids[-1] if ids else None,
                       'nonzero_frame_ids_sampled': len([value for value in ids if value]),
                       'sampled_ids_contiguous_from_zero': contiguous,
                       'movie_complete_flag_observed': end, 'decode_complete_flag_observed': decoded,
                       'observed_complete_lifetime': complete, 'source_viewports_xy_width_height': geometry})
    return result


def check_inputs(folder, observed, frames):
    header, definitions = read_tsv(folder / 'input-definition.tsv')
    if header != ('name', 'type', 'neutral_value'):
        raise ValueError('Unsupported controller definition.')
    names = [row['name'] for row in definitions]
    if names != sorted(set(names)) or len(names) != 26:
        raise ValueError('Expected the complete supported PSX controller definition.')
    if {row['name'] for row in definitions if row['type'] == 'boolean'} != DIGITAL_NAMES:
        raise ValueError('Missing or renamed digital PSX inputs.')
    for row in definitions:
        if row['type'] == 'boolean':
            if row['neutral_value'] != 'false':
                raise ValueError('Startup replay requires every digital input to remain false.')
        elif row['type'] == 'number':
            try:
                value = Decimal(row['neutral_value'])
            except InvalidOperation as error:
                raise ValueError('Invalid numeric controller input.') from error
            if not value.is_finite() or NUMERIC_NEUTRAL.get(row['name']) != value:
                raise ValueError('Analog centers and disc index differ from the supported neutral profile.')
        else:
            raise ValueError('Unsupported controller input type.')
    if {row['name'] for row in definitions if row['type'] == 'number'} != set(NUMERIC_NEUTRAL):
        raise ValueError('Missing numeric PSX inputs.')
    header, submitted = read_tsv(folder / 'submitted.tsv')
    if header != ('relative_frame', 'core_frame', *names) or len(submitted) != frames:
        raise ValueError('Require a complete submitted input vector for every frame.')
    for index, row in enumerate(submitted):
        if (int(row['relative_frame']) != index + 1 or row['core_frame'] != observed[index]['core_frame'] or
                any(row[item['name']] != item['neutral_value'] for item in definitions)):
            raise ValueError('Submitted inputs or their frame alignment changed.')
    return definitions


def compare_runs(original, rebuilt, frames=9000):
    original, rebuilt = [Path(path).resolve(strict=True) for path in (original, rebuilt)]
    if original == rebuilt or not 1 <= frames <= 12000:
        raise ValueError('Supply distinct capture folders and 1 to 12000 frames.')
    script = ROOT / 'research/movie_playback/observe.lua'
    for folder in (original, rebuilt):
        if ((folder / 'failed.txt').exists() or
                not (folder / 'completed.txt').read_text().startswith(str(frames) + ' frames;')):
            raise ValueError('Both captures must have completed successfully.')
        if (folder / 'runtime_smoke.lua').read_bytes() != script.read_bytes():
            raise ValueError('Captured observer differs from the current supported source.')
        if json.loads((folder / 'exit.json').read_text())['exit_code'] != 0:
            raise ValueError('The owned capture process did not exit successfully.')
        if json.loads((folder / 'external-save-inputs.json').read_text()) != {'files': [], 'initial_save_ram_empty': True}:
            raise ValueError('The capture did not start with empty isolated SaveRAM.')
        saves = json.loads((folder / 'exit-save-records.json').read_text())
        if not saves['shared_save_ram_empty']:
            raise ValueError('Owned SaveRAM was not isolated after exit.')
        for item in saves['files_preserved']:
            path = (folder / item['relative_path']).resolve(strict=True)
            if not path.is_relative_to(folder) or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
                raise ValueError('A preserved owned save changed or leaves its capture folder.')
    identity = compare_inputs(original, rebuilt, 'boot', frames)
    if not identity['inputs_verified'] or not identity['declared_inputs_identical']:
        raise ValueError('Full emulator/core/disc/BIOS/script/start-state identity is required.')
    runs = [read_observations(folder / 'movies.tsv', frames) for folder in (original, rebuilt)]
    for folder, observed in zip((original, rebuilt), runs):
        check_inputs(folder, observed, frames)
    lifetimes = [summarize_lifetimes(rows) for rows in runs]
    reference_movies = {row['path']: row for row in json.loads(
        (ROOT / 'docs/movie-inventory-checks.json').read_text())['movies']}
    for sequences in lifetimes:
        for movie in sequences:
            expected, opened = reference_movies[movie['path']], movie['opened_file']
            if (opened['lba'] != expected['lba'] or opened['sectors'] != expected['sectors'] or
                    opened['sectors'] * 2336 != expected['bytes']):
                raise ValueError('Native CD-file extent differs from the audited mixed-sector movie.')
    filenames = ('movies.tsv', 'submitted.tsv', 'input-definition.tsv', 'captures.tsv', 'completed.txt',
                 'external-save-inputs.json', 'exit-save-records.json')
    files = {name: byte_comparison((original / name).read_bytes(), (rebuilt / name).read_bytes()) for name in filenames}
    capture_lists = []
    for folder in (original, rebuilt):
        header, captures = read_tsv(folder / 'captures.tsv')
        if header != ('relative_frame', 'core_frame', 'reason', 'active_movie', 'threshold', 'raw_stream_frame'):
            raise ValueError('Unsupported capture index.')
        points = [int(row['relative_frame']) for row in captures]
        if points != sorted(set(points)) or not points or points[0] != 0 or points[-1] != frames:
            raise ValueError('Capture points must be unique, ordered, and include both endpoints.')
        if any(not 0 <= point <= frames for point in points):
            raise ValueError('Capture point leaves the observed frame range.')
        observed = runs[len(capture_lists)]
        required = {0, frames, *range(600, frames + 1, 600)}
        previous = None
        for index, row in enumerate(observed):
            state = (row['active_movie'], row['native_tables_ready'])
            if state != previous:
                required.add(index)
            previous = state
        if not required.issubset(points):
            raise ValueError('Scheduled or movie/table transition checkpoints are missing.')
        for capture in captures:
            row = observed[int(capture['relative_frame'])]
            expected = (row['stream_40'], row['stream_58']) if row['active_movie'] != '0' else ('0', '0')
            if (capture['core_frame'] != row['core_frame'] or capture['active_movie'] != row['active_movie'] or
                    (capture['threshold'], capture['raw_stream_frame']) != expected):
                raise ValueError('Capture index is not aligned with its native observation.')
        capture_lists.append(points)
    if capture_lists[0] != capture_lists[1]:
        raise ValueError('Capture checkpoint sets differ.')
    checkpoints = []
    for frame in capture_lists[0]:
        outputs = {}
        for label, name, size in [('ram', f'mainram-{frame}.bin', 0x200000),
                                  ('gpu', f'gpu-{frame}.bin', 0x100000), ('image', f'frame-{frame}.png', None)]:
            data = [(folder / name).read_bytes() for folder in (original, rebuilt)]
            if size and any(len(raw) != size for raw in data):
                raise ValueError('Truncated RAM or GPU checkpoint.')
            outputs[label] = byte_comparison(*data)
            if label == 'gpu' and any(hashlib.sha256(raw).hexdigest() != runs[index][frame]['gpu_sha256']
                                      for index, raw in enumerate(data)):
                raise ValueError('Per-frame GPU hash differs from the complete captured GPU bytes.')
        outputs['state'] = compare_state(original / f'frame-{frame}.State', rebuilt / f'frame-{frame}.State')
        checkpoints.append({'relative_frame': frame, **outputs})
    audio = compare_audio(original / 'audio.wav', rebuilt / 'audio.wav')
    equal = all(result['equal'] for result in files.values())
    equal = equal and all(all(row[name]['equal'] for name in ('ram', 'gpu', 'image')) and
                          row['state']['member_contents_equal'] for row in checkpoints)
    equal = equal and audio['equal_pcm_output'] and audio['wav_file_bytes']['equal']
    return {'schema_version': 1, 'recorded_utc': datetime.now(timezone.utc).isoformat(),
            'status': 'equal_recorded_movie_trajectory' if equal else 'different_recorded_movie_trajectory',
            'frames': frames, 'observed_rows_each': frames + 1, 'submitted_vectors_each': frames,
            'first_resumed_core_frame': int(runs[0][0]['core_frame']),
            'observed_columns': len(FIELDS), 'gpu_hashes_each': frames + 1, 'gpu_bytes_per_hash': 0x100000,
            'inputs': identity, 'files': files, 'checkpoints': checkpoints, 'audio': audio,
            'movie_lifetimes': lifetimes[0], 'rebuilt_movie_lifetimes': lifetimes[1],
            'movie_identification': 'Native CD filename, BCD location/LBA, and logical byte size agree with the audited mixed-sector file; requested cutoff also agrees.',
            'script_sha256': hashlib.sha256(script.read_bytes()).hexdigest(),
            'producer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'game_memory_writes': 0, 'model_api_calls': 0, 'new_c_bytes': 0,
            'whole_feature_groups_accepted': 0,
            'scope': 'Neutral shared-state startup replay. Full GPU hashes at every observation, checkpoint RAM/GPU/images/all state member payloads, and complete PCM compared without masking. Not uninterrupted cold boot, instruction tracing, every host-displayed frame, skip/error branches, all movies, or whole-feature acceptance.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('original', 'rebuilt', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--frames', type=int, default=9000)
    args = parser.parse_args(argv)
    try:
        output = Path(args.output).resolve()
        if not output.is_relative_to(ROOT / '.decomp-lab') or output.exists():
            raise ValueError('Choose a new private report inside .decomp-lab.')
        report = compare_runs(args.original, args.rebuilt, args.frames)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')
        print(json.dumps({'status': report['status'], 'frames': report['frames'],
                          'gpu_hashes_each': report['gpu_hashes_each'], 'checkpoints': len(report['checkpoints']),
                          'observed_complete_movie_lifetimes': sum(r['observed_complete_lifetime'] for r in report['movie_lifetimes']),
                          'whole_feature_groups_accepted': 0}))
        return 0 if report['status'] == 'equal_recorded_movie_trajectory' else 1
    except (OSError, ValueError, KeyError, csv.Error, wave.Error, zipfile.BadZipFile) as error:
        print('[!] ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
