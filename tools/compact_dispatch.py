"""Bounded payload storage and exact output checks for compact method histories.

These are analysis transports. They do not alter original game code, NPC AI or
claim complete emulator-state or original-hardware timing parity.
"""
import csv
import hashlib
import json
import lzma
from pathlib import Path
import re
import struct
import zlib

from tools.compare_npc_history import inspect_png
from tools.dispatch_trace import expand_program
from tools.replay_cold_start_headless import require, write_json
from tools.runtime_inputs import record_file

STREAM_LIMIT = 64 * 1024 * 1024
CAPTURE_LIMIT = 128 * 1024 * 1024
FRAME_FIELDS = ('relative_frame', 'core_frame', 'phase', 'gpu_sha256', 'sample_frames', 'total_sample_frames')
RAM_FIELDS = ('relative_frame', 'core_frame', 'RAM_sha256')
PAYLOADS = ('method-return-data.bin', 'sdk-read-data.bin', 'collision-call-ram.bin')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None

def owned_file(folder, name):
    folder = Path(folder).resolve(strict=True)
    require(isinstance(name, str) and Path(name).name == name, 'Use a single owned payload filename.')
    path = folder / name
    require(path.resolve(strict=True).parent == folder and not path.is_symlink(), 'Payload escapes its capture folder.')
    return path

def read_payload(folder, name):
    """Read a raw or sealed XZ payload in memory, without expanding it on disk."""
    folder = Path(folder)
    metadata = folder / 'payload-archives.json'
    archives = json.loads(metadata.read_text(encoding='utf-8')) if metadata.is_file() else {}
    if name not in archives:
        path = owned_file(folder, name)
        require(path.stat().st_size <= STREAM_LIMIT, 'Raw payload exceeds its stream budget.')
        return path.read_bytes()
    row = archives[name]
    require(name in PAYLOADS and row.get('codec') == 'xz' and row.get('file') == name + '.xz'
            and type(row.get('bytes')) is int and 0 < row['bytes'] <= STREAM_LIMIT
            and digest(row.get('sha256')) and digest(row.get('compressed_sha256')),
            'Unqualified compact payload archive metadata.')
    require(not (folder / name).exists(), 'Both expanded and archived payloads exist; preserve and review them.')
    path = owned_file(folder, row['file'])
    require(path.stat().st_size == row['compressed_bytes'] <= STREAM_LIMIT
            and record_file(path)['sha256'] == row['compressed_sha256'], 'Archived payload identity differs.')
    with lzma.open(path, 'rb') as stream:
        data = stream.read(row['bytes'] + 1)
    require(len(data) == row['bytes'] and sha(data) == row['sha256'], 'Complete archived payload content differs.')
    return data

def archive_payloads(folder):
    """Retire only fresh owned data streams after full lossless roundtrip proof."""
    folder = Path(folder).resolve(strict=True)
    target = folder / 'payload-archives.json'
    require(not target.exists(), 'Preserve existing payload archive evidence.')
    archives = {}
    def save_index():
        pending = folder / 'payload-archives.pending.json'
        write_json(pending, archives)
        pending.replace(target)
    for name in PAYLOADS:
        path = folder / name
        if not path.exists() or not 512 * 1024 <= path.stat().st_size <= 32 * 1024 * 1024:
            continue
        path = owned_file(folder, name)
        before = path.stat()
        require(before.st_nlink == 1, 'Never retire a shared historical payload in place.')
        data = path.read_bytes()
        packed = lzma.compress(data, preset=3)
        require(lzma.decompress(packed) == data, 'Lossless payload roundtrip failed.')
        output = folder / (name + '.xz')
        with output.open('xb') as stream:
            stream.write(packed)
        require(sha(output.read_bytes()) == sha(packed), 'Retained compressed payload differs.')
        archives[name] = dict(codec='xz', file=output.name, bytes=len(data), sha256=sha(data),
                              compressed_bytes=len(packed), compressed_sha256=sha(packed))
        save_index()  # Recovery metadata precedes expanded-file removal.
        after = path.stat()
        require((after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_nlink) ==
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, 1)
                and sha(path.read_bytes()) == archives[name]['sha256'], 'Owned payload changed before retirement.')
        path.unlink()
        require(read_payload(folder, name) == data, 'Retained payload cannot be read after retirement.')
    if not target.exists():
        save_index()
    return archives

def png_rgb(data, width, height):
    """Decode the producer's non-interlaced 8-bit truecolor PNG independently."""
    require(type(width) is int and type(height) is int and 1 <= width <= 2048 and 1 <= height <= 1024,
            'Unsupported compact checkpoint dimensions.')
    inspect_png(data, width, height)
    at, chunks = 8, []
    while at < len(data):
        length = struct.unpack_from('>I', data, at)[0]
        kind, body = data[at+4:at+8], data[at+8:at+8+length]
        if kind == b'IHDR':
            require(body[8:] == bytes((8, 2, 0, 0, 0)), 'Require the producer exact truecolor PNG format.')
        if kind == b'IDAT':
            chunks.append(body)
        at += length + 12
    size = height * (width * 3 + 1)
    decoder = zlib.decompressobj()
    raw = decoder.decompress(b''.join(chunks), size + 1)
    require(len(raw) == size and decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data,
            'Checkpoint PNG has truncated, oversized or concatenated pixel data.')
    previous, rgb = bytearray(width * 3), bytearray()
    for y in range(height):
        start = y * (width * 3 + 1)
        method, row = raw[start], bytearray(raw[start+1:start+1+width*3])
        require(method in range(5), 'Invalid PNG pixel filter.')
        for x in range(len(row)):
            left, up = (row[x-3] if x >= 3 else 0), previous[x]
            corner = previous[x-3] if x >= 3 else 0
            predictor = 0
            if method == 1: predictor = left
            elif method == 2: predictor = up
            elif method == 3: predictor = (left + up) // 2
            elif method == 4:
                value = left + up - corner
                distances = (abs(value-left), abs(value-up), abs(value-corner))
                predictor = (left, up, corner)[distances.index(min(distances))]
            row[x] = (row[x] + predictor) & 255
        rgb.extend(row)
        previous = row
    return bytes(rgb)

def rows(path, fields):
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream, delimiter='\t')
        require(tuple(reader.fieldnames or ()) == fields, 'Incomplete compact observation columns.')
        return list(reader)

def validate_outputs(folder, settings, program):
    folder = Path(folder)
    output = folder / 'observations'
    native = json.loads((output / 'report.json').read_text(encoding='utf-8-sig'))
    frames, checkpoints = settings['frames'], settings['checkpoint_frames']
    require(settings.get('compact_capture') is True and settings.get('serialized_state', False) is False
            and len(checkpoints) <= 4 and settings['RAM_sample_interval'] >= 1,
            'Require bounded compact settings with no serialized state.')
    require((folder / 'submitted.tsv').read_bytes() == expand_program(program, frames),
            'Submitted compact controller program differs.')
    require(native.get('status') == 'recorded_compact_method_history' and native.get('compact_capture') is True
            and native.get('restored_state') is False and native.get('game_RAM_injected') is False
            and native.get('emulator_UI_controlled') is False and native.get('complete_state_parity_checked') is False
            and native.get('original_hardware_timing_verified') is False
            and native.get('observer_requested') == native.get('observer_enabled') == settings['trace_enabled']
            and native.get('frames_advanced') == frames + 1 and native.get('submitted_frames') == frames
            and native.get('retained_stream_limit') == STREAM_LIMIT
            and type(native.get('retained_stream_bytes')) is int and 0 <= native['retained_stream_bytes'] <= STREAM_LIMIT,
            'Incomplete compact capture, unsupported execution mode or stream budget.')
    require(not (output / 'audio.pcm').exists() and not list(output.glob('mainram-*.bin'))
            and not list(output.glob('gpu-*.bin')) and not list(output.glob('rgb-*.bin')),
            'Compact captures must not retain raw checkpoint or continuous PCM dumps.')
    observations = rows(output / 'frames.tsv', FRAME_FIELDS)
    submitted = list(csv.DictReader((folder / 'submitted.tsv').read_text().splitlines(), delimiter='\t'))
    require(len(observations) == len(submitted) + 1 == frames + 1, 'Incomplete compact frame sequence.')
    total = 0
    for frame, row in enumerate(observations):
        count = int(row['sample_frames'])
        total += count
        require(int(row['relative_frame']) == frame and int(row['core_frame']) == frame + 1
                and row['phase'] == ('initial_neutral' if frame == 0 else submitted[frame-1]['phase'])
                and count >= 0 and int(row['total_sample_frames']) == total and digest(row['gpu_sha256']),
                'Compact frame/controller/audio boundary disagrees.')
    require(total == native['all_PCM_sample_frames'] and total * 4 == native.get('complete_PCM_bytes')
            and digest(native.get('complete_PCM_sha256')), 'Incomplete continuous PCM digest/count.')
    memory = rows(output / 'ram-samples.tsv', RAM_FIELDS)
    expected = sorted(set(range(0, frames + 1, settings['RAM_sample_interval'])) | set(checkpoints))
    require([int(r['relative_frame']) for r in memory] == expected and len(memory) == native['RAM_samples']
            and all(int(r['core_frame']) == int(r['relative_frame']) + 1 and digest(r['RAM_sha256']) for r in memory),
            'Compact RAM sample sequence or complete RAM digest is invalid.')
    ram = {int(r['relative_frame']): r for r in memory}
    require([r['relative_frame'] for r in native['checkpoints']] == checkpoints, 'Incomplete compact checkpoints.')
    for row in native['checkpoints']:
        frame, image = row['relative_frame'], row['image']
        pixels = png_rgb(owned_file(output, f'frame-{frame}.png').read_bytes(), image['width'], image['height'])
        require(row['core_frame'] == frame + 1 and row['RAM_sha256'] == ram[frame]['RAM_sha256']
                and row['GPU_sha256'] == observations[frame]['gpu_sha256'] and sha(pixels) == image['RGB_sha256'],
                'Compact checkpoint RAM/GPU/decoded RGB differs from its observation.')
    require(sum(p.stat().st_size for p in output.iterdir() if p.is_file()) < CAPTURE_LIMIT,
            'Retained compact capture exceeds 128 MiB.')
    return native

def compare_outputs(reference, candidate, left, right):
    for name in ('submitted.tsv', 'observations/frames.tsv', 'observations/ram-samples.tsv'):
        require((Path(reference) / name).read_bytes() == (Path(candidate) / name).read_bytes(),
                'Complete bounded controller/GPU/RAM/sample-count sequence differs: ' + name)
    for name in ('checkpoints', 'complete_PCM_bytes', 'complete_PCM_sha256', 'all_PCM_sample_frames'):
        require(left[name] == right[name], 'Complete compact output window differs: ' + name)
    for row in left['checkpoints']:
        name = f"observations/frame-{row['relative_frame']}.png"
        require((Path(reference) / name).read_bytes() == (Path(candidate) / name).read_bytes(),
                'Compact checkpoint PNG container differs.')
    return dict(output_observations=left['frames_advanced'], RAM_samples=left['RAM_samples'],
                decoded_RGB_checkpoints=len(left['checkpoints']), complete_PCM_bytes=left['complete_PCM_bytes'],
                complete_PCM_sha256=left['complete_PCM_sha256'], all_equal=True,
                complete_state_parity_checked=False, original_hardware_timing_verified=False)
