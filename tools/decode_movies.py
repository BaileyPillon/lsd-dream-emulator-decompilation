"""Decode every catalogued STR payload with a recorded local FFmpeg backend.

This checks software-decoded YUV frames and PCM packets, not native MDEC/GPU,
audio mixing, controller paths, disc timing or complete movie-feature parity.
Original media remains read-only; decoded frame hashes and raw sector copies
belong in a new private output directory.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.psx_image import read_root_file
from tools.runtime_inputs import disc_inputs, record_file

CANONICAL_SHA256 = '282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f'
RAW_BYTES, PAYLOAD_BYTES = 2352, 2336
SYNC = b'\x00' + b'\xff' * 10 + b'\x00'
HEX = re.compile(r'[0-9a-f]{64}')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def output_directory(output):
    output = Path(output).resolve()
    lab = (ROOT / '.decomp-lab').resolve()
    require(not output.exists() and output != lab, 'Choose a new private output directory.')
    require(not output.is_relative_to(ROOT) or output.is_relative_to(lab),
            'Keep movie data outside the checkout or under .decomp-lab.')
    return output


def audio_profile(movie):
    headers = [row for row in movie['subheaders'] if row['flags'] & 14 == 4]
    require(bool(headers), 'Expected an XA audio stream for ' + movie['path'])
    identities = {(row['file'], row['channel'], row['coding']) for row in headers}
    require(len(identities) == 1, 'This profile needs one stable XA file/channel/coding tuple.')
    file_id, channel, coding = next(iter(identities))
    require(coding in (0, 1), 'This profile supports the audited 4-bit, 37,800 Hz mono/stereo coding.')
    channels = (coding & 1) + 1
    sectors = sum(row['sectors'] for row in headers)
    require(sectors > 0, 'XA sector count must be positive.')
    return dict(file=file_id, channel=channel, coding=coding, channels=channels,
                sample_rate=37800, sectors=sectors, samples_per_packet=4032 // channels)


def validate_catalogue(catalogue):
    canonical = catalogue.get('canonical_executable_sha256', catalogue.get('canonical_sha256'))
    require(canonical == CANONICAL_SHA256, 'Catalogue must identify the canonical Japanese executable.')
    movies = catalogue['movies']
    require(catalogue['movie_count'] == len(movies) == 39, 'Expected all 39 routed movie payloads.')
    require(sum(row['frame_count'] for row in movies) == catalogue['encoded_frame_count'],
            'Catalogue frame totals disagree.')
    require(len({row['path'] for row in movies}) == len(movies), 'Duplicate movie paths.')
    require({row['path'] for row in movies} == {row['path'] for row in catalogue['routes']},
            'Catalogue routes and movie records disagree.')
    extents = []
    for movie in movies:
        require(re.fullmatch(r'/CDI/(?:ETC|FILM)/[A-Z0-9]+\.STR', movie['path']) is not None,
                'Unsupported movie path.')
        require(type(movie['lba']) is int and movie['lba'] >= 0, 'Invalid movie LBA.')
        require(type(movie['sectors']) is int and movie['sectors'] > 0, 'Invalid movie extent.')
        require(movie['bytes'] == movie['sectors'] * PAYLOAD_BYTES, 'Mixed-sector size disagrees.')
        require(HEX.fullmatch(movie['sha256']) is not None, 'Invalid movie input checksum.')
        require(type(movie['frame_count']) is int and movie['frame_count'] > 0, 'Invalid movie frame count.')
        require(sum(row['sectors'] for row in movie['subheaders']) == movie['sectors'],
                'Subheader counts disagree with the movie extent.')
        audio_profile(movie)
        extents.append((movie['lba'], movie['lba'] + movie['sectors']))
    extents.sort()
    require(all(left[1] <= right[0] for left, right in zip(extents, extents[1:])),
            'Movie extents overlap.')
    return sorted(movies, key=lambda movie: movie['path'])


def parse_framehash(text, *, video_frames, audio_sectors, channels, sample_rate=37800):
    """Require complete decoded streams; a successful process exit is insufficient."""
    require(channels in (1, 2) and sample_rate == 37800, 'Unsupported decoded audio profile.')
    metadata, rows = {}, []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith('#'):
            match = re.fullmatch(r'#(hash|version):\s*(.+)', line)
            if match:
                key, value = match.groups()
            else:
                match = re.fullmatch(r'#(tb|media_type|codec_id|dimensions|sample_rate|channel_layout_name) (\d+):\s*(.+)', line)
                if not match:
                    continue
                field, stream, value = match.groups()
                key = field + ':' + stream
            require(key not in metadata, 'Duplicate framehash header: ' + key)
            metadata[key] = value
            continue
        values = [part.strip() for part in line.split(',')]
        require(len(values) == 6 and HEX.fullmatch(values[5]) is not None, 'Malformed framehash packet.')
        try:
            stream, dts, pts, duration, size = map(int, values[:5])
        except ValueError as error:
            raise ValueError('Noninteger framehash packet metadata.') from error
        require(stream in (0, 1) and duration > 0 and size > 0, 'Unexpected decoded packet.')
        rows.append((stream, dts, pts, duration, size, values[5]))
    expected = {'hash':'SHA256', 'version':'2', 'media_type:0':'video', 'codec_id:0':'rawvideo',
                'dimensions:0':'320x240', 'tb:0':'1/15', 'media_type:1':'audio',
                'codec_id:1':'pcm_s16le', 'tb:1':'1/37800', 'sample_rate:1':'37800',
                'channel_layout_name:1':'mono' if channels == 1 else 'stereo'}
    require(all(metadata.get(key) == value for key, value in expected.items()),
            'Framehash does not describe the required decoded YUV/PCM streams.')
    require(not any(key.rsplit(':', 1)[-1].isdigit() and int(key.rsplit(':', 1)[-1]) > 1
                    for key in metadata), 'Unexpected additional decoded stream.')
    totals, fingerprints, unique = [], [], []
    for stream, expected_packets in ((0, video_frames), (1, audio_sectors)):
        packets = [row for row in rows if row[0] == stream]
        require(len(packets) == expected_packets, 'Decoded packet count disagrees for stream ' + str(stream))
        cursor, byte_count = 0, 0
        hashes = hashlib.sha256()
        for _, dts, pts, duration, size, checksum in packets:
            require(dts == pts == cursor, 'Decoded stream has missing, repeated or reordered timestamps.')
            if stream == 0:
                require(duration == 1 and size == 320 * 240 * 3 // 2, 'Unexpected decoded YUV frame size.')
            else:
                require(duration == 4032 // channels and size == duration * channels * 2,
                        'Unexpected decoded PCM packet size or duration.')
            hashes.update(bytes.fromhex(checksum))
            cursor += duration
            byte_count += size
        totals.append(dict(packets=len(packets), duration_units=cursor, decoded_bytes=byte_count))
        fingerprints.append(hashes.hexdigest())
        unique.append(len({row[5] for row in packets}))
    return dict(video_frames=totals[0]['packets'], video_decoded_bytes=totals[0]['decoded_bytes'],
                audio_packets=totals[1]['packets'], audio_sample_frames=totals[1]['duration_units'],
                audio_PCM_bytes=totals[1]['decoded_bytes'],
                ordered_video_frame_digests_sha256=fingerprints[0],
                ordered_audio_packet_digests_sha256=fingerprints[1],
                unique_video_frame_digests=unique[0], unique_audio_packet_digests=unique[1],
                digest_scope='SHA256 over the ordered binary per-packet SHA256 digests, not a hash of concatenated raw media.',
                nominal_demuxer_video_time_base='1/15', native_playback_cadence_verified=False)


def backend_files(ffmpeg, ffprobe):
    require(ffmpeg.parent == ffprobe.parent, 'Use ffmpeg and ffprobe from the same installation directory.')
    files = {ffmpeg, ffprobe, *ffmpeg.parent.glob('*.dll')}
    if sys.platform != 'win32' and not list(ffmpeg.parent.glob('*.dll')):
        linker = shutil.which('ldd')
        require(linker is not None, 'ldd is required to fingerprint a shared Linux FFmpeg backend.')
        for binary in (ffmpeg, ffprobe):
            result = subprocess.run([linker, str(binary)], capture_output=True, text=True)
            text = result.stdout + result.stderr
            if result.returncode:
                require('not a dynamic executable' in text or 'statically linked' in text,
                        'Could not inspect decoder library dependencies.')
            for line in text.splitlines():
                if re.search(r'lib(?:avcodec|avformat|avutil|avfilter|avdevice|swresample|swscale|postproc)\.', line):
                    match = re.search(r'=>\s+(/\S+)', line)
                    require(match is not None, 'An FFmpeg media library could not be resolved.')
                    files.add(Path(match[1]).resolve(strict=True))
    return {str(path.resolve(strict=True)):record_file(path) for path in sorted(files)}


def invoke(command, folder, name):
    command = list(map(str, command))
    options = {}
    if sys.platform == 'win32':
        options['creationflags'] = subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS
    elif shutil.which('nice'):
        command = [shutil.which('nice'), '-n', '10', *command]
    with (folder / (name + '.stdout')).open('xb') as stdout, (folder / (name + '.stderr')).open('xb') as stderr:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, **options)
        write_json(folder / (name + '-process.json'), dict(pid=process.pid, argv=command))
        code = process.wait()
    errors = (folder / (name + '.stderr')).read_bytes()
    require(code == 0 and not errors, name + ' reported an error; retained logs: ' + str(folder))
    return dict(argv=command, exit_code=code, stderr_sha256=digest(errors),
                stdout_sha256=digest((folder / (name + '.stdout')).read_bytes()))


def extract_raw(track, movie, destination):
    expected = Counter({(row['file'], row['channel'], row['flags'], row['coding']):row['sectors']
                        for row in movie['subheaders']})
    seen, payload = Counter(), hashlib.sha256()
    require((movie['lba'] + movie['sectors']) * RAW_BYTES <= track.stat().st_size,
            'Movie extent lies outside the source data track.')
    with track.open('rb') as source, destination.open('xb') as target:
        source.seek(movie['lba'] * RAW_BYTES)
        for _ in range(movie['sectors']):
            sector = source.read(RAW_BYTES)
            require(len(sector) == RAW_BYTES and sector[:12] == SYNC and sector[15] == 2,
                    'Movie extent contains a truncated or non-Mode2 sector.')
            require(sector[16:20] == sector[20:24], 'Repeated XA subheaders disagree.')
            seen[tuple(sector[16:20])] += 1
            payload.update(sector[16:])
            target.write(sector)
    require(payload.hexdigest() == movie['sha256'] and seen == expected,
            'Original raw-sector payload differs from the encoded movie catalogue.')
    return record_file(destination)


def decode_one(track, movie, output, ffmpeg, ffprobe):
    relative = PurePosixPath(movie['path']).parts[1:]
    folder = output.joinpath('movies', *relative).with_suffix('')
    folder.mkdir(parents=True, exist_ok=False)
    audio = audio_profile(movie)
    raw = folder / 'input.raw.str'
    raw_identity = extract_raw(track, movie, raw)
    probe = invoke([ffprobe, '-v', 'error', '-f', 'psxstr', '-show_streams', '-show_format', '-of', 'json', raw], folder, 'probe')
    streams = json.loads((folder / 'probe.stdout').read_bytes())['streams']
    videos = [row for row in streams if row['codec_type'] == 'video']
    audios = [row for row in streams if row['codec_type'] == 'audio']
    require(len(streams) == 2 and len(videos) == len(audios) == 1, 'Expected one video and one audio stream.')
    video, sound = videos[0], audios[0]
    require(video['codec_name'] == 'mdec' and (video['width'], video['height']) == (320, 240),
            'Unexpected source video codec or dimensions.')
    require(video['pix_fmt'] in ('yuv420p', 'yuvj420p'), 'Unsupported MDEC pixel format.')
    require(sound['codec_name'] == 'adpcm_xa' and int(sound['sample_rate']) == audio['sample_rate']
            and sound['channels'] == audio['channels'], 'Probe audio parameters disagree with XA coding.')
    framehash = folder / 'decoded.framehash'
    decoded = invoke([ffmpeg, '-nostdin', '-hide_banner', '-v', 'error', '-xerror', '-cpuflags', '0',
        '-fflags', '+bitexact', '-flags', '+bitexact', '-err_detect', 'explode', '-threads', '1',
        '-f', 'psxstr', '-i', raw, '-map', '0:v:0', '-map', '0:a:0', '-fps_mode:v', 'passthrough',
        '-c:v', 'rawvideo', '-pix_fmt:v', video['pix_fmt'], '-c:a', 'pcm_s16le',
        '-flags:v', '+bitexact', '-flags:a', '+bitexact', '-threads:v', '1', '-threads:a', '1',
        '-f', 'framehash', '-hash', 'sha256', '-format_version', '2', '-n', framehash], folder, 'decode')
    result = parse_framehash(framehash.read_text(), video_frames=movie['frame_count'],
                             audio_sectors=audio['sectors'], channels=audio['channels'])
    require(record_file(raw) == raw_identity, 'Owned decoder input changed during decoding.')
    result.update(path=movie['path'], lba=movie['lba'], source_payload_sha256=movie['sha256'],
                  raw_sector_input=raw_identity, audio_profile=audio, pixel_format=video['pix_fmt'],
                  framehash_sha256=digest(framehash.read_bytes()), probe=probe, decoder=decoded,
                  streams=streams, decoder_error_output_empty=True)
    write_json(folder / 'report.json', result)
    return result


def audit(cue, catalogue_path, ffmpeg, ffprobe, output, workers=2):
    output = output_directory(output)
    require(workers in (1, 2), 'Use one or two decoder workers.')
    catalogue_path = Path(catalogue_path).resolve(strict=True)
    catalogue_identity = record_file(catalogue_path)
    catalogue = json.loads(catalogue_path.read_bytes())
    movies = validate_catalogue(catalogue)
    cue = Path(cue).resolve(strict=True)
    disc = disc_inputs(cue)
    require(disc['layout'] == ['FILE <track-1> BINARY', 'TRACK 01 MODE2/2352', 'INDEX 01 00:00:00']
            and len(disc['tracks']) == 1, 'This profile requires one Mode2/2352 data track starting at index zero.')
    require(digest(read_root_file(cue)[0]) == CANONICAL_SHA256, 'Disc executable is not canonical SLPS_015.56.')
    track = Path(disc['tracks'][0]['path'])
    ffmpeg, ffprobe = [Path(path).resolve(strict=True) for path in (ffmpeg, ffprobe)]
    backend = backend_files(ffmpeg, ffprobe)
    dependency_paths = [Path(__file__).resolve(), ROOT / 'tools/runtime_inputs.py', ROOT / 'tools/psx_image.py']
    dependencies = {str(path):record_file(path) for path in dependency_paths}
    output.mkdir(parents=True, exist_ok=False)
    for path in dependency_paths:
        snapshot = output / 'producer-sources' / path.relative_to(ROOT)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        with snapshot.open('xb') as stream:
            stream.write(path.read_bytes())
        require(digest(snapshot.read_bytes()) == dependencies[str(path)]['sha256'], 'Producer changed while being retained.')
    version = invoke([ffmpeg, '-version'], output, 'ffmpeg-version')
    probe_version = invoke([ffprobe, '-version'], output, 'ffprobe-version')
    results, failures = [], []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        jobs = {executor.submit(decode_one, track, movie, output, ffmpeg, ffprobe):movie['path'] for movie in movies}
        for future in as_completed(jobs):
            try:
                result = future.result()
                results.append(result)
                event = dict(path=result['path'], status='decoded', video_frames=result['video_frames'], audio_packets=result['audio_packets'])
            except Exception as error:
                event = dict(path=jobs[future], status='failed', error=repr(error))
                failures.append(event)
            with (output / 'progress.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(event) + '\n')
            print(json.dumps(event), flush=True)
    source_preserved = record_file(cue) == disc['cue'] and record_file(track) == disc['tracks'][0]
    backend_preserved = all(record_file(path) == identity for path, identity in backend.items())
    catalogue_preserved = record_file(catalogue_path) == catalogue_identity
    dependencies_preserved = all(record_file(path) == identity for path, identity in dependencies.items())
    passed = (not failures and len(results) == len(movies) and source_preserved
              and backend_preserved and catalogue_preserved and dependencies_preserved)
    report = dict(schema_version=1, status='passed_complete_software_movie_decode' if passed else 'failed_movie_decode_audit',
        recorded_utc=datetime.now(timezone.utc).isoformat(), source_disc=disc, catalogue=catalogue_identity,
        canonical_executable_sha256=CANONICAL_SHA256, decoder_backend=backend,
        ffmpeg_version=version, ffprobe_version=probe_version, workers=workers,
        movie_count=len(results), expected_movie_count=len(movies),
        decoded_video_frames=sum(row['video_frames'] for row in results),
        decoded_video_bytes=sum(row['video_decoded_bytes'] for row in results),
        decoded_audio_packets=sum(row['audio_packets'] for row in results),
        decoded_audio_sample_frames=sum(row['audio_sample_frames'] for row in results),
        decoded_audio_PCM_bytes=sum(row['audio_PCM_bytes'] for row in results),
        movies=sorted(results, key=lambda row:row['path']), failures=failures,
        source_disc_preserved=source_preserved, decoder_backend_preserved=backend_preserved,
        catalogue_preserved=catalogue_preserved, excluded_data_STR_files=catalogue['non_mixed_str_files_unparsed'],
        producer_sha256=dependencies[str(Path(__file__).resolve())]['sha256'],
        producer_dependencies=dependencies, producer_dependencies_preserved=dependencies_preserved,
        native_MDEC_GPU_audio_parity_accepted=False, native_playback_cadence_verified=False,
        natural_movie_scenarios_accepted=0, whole_feature_groups_accepted=0,
        original_game_modified=False, user_game_controlled=False, new_C_bytes=0, model_API_calls=0,
        scope='Complete software decoding of the supplied catalogue\'s exact raw-sector payloads into YUV frame and PCM packet hashes. Not native PS1 decoder, playback, mixing, timing, skip/error or whole-feature acceptance.')
    write_json(output / 'report.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cue', type=Path, required=True)
    parser.add_argument('--catalogue', type=Path, default=ROOT / 'docs/movie-inventory-checks.json')
    parser.add_argument('--ffmpeg', type=Path, default=shutil.which('ffmpeg'))
    parser.add_argument('--ffprobe', type=Path, default=shutil.which('ffprobe'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, choices=(1, 2), default=2)
    args = parser.parse_args(argv)
    try:
        require(args.ffmpeg is not None and args.ffprobe is not None, 'Supply local ffmpeg and ffprobe paths.')
        report = audit(args.cue, args.catalogue, args.ffmpeg, args.ffprobe, args.output, args.workers)
        print(json.dumps({key:report[key] for key in ('status','movie_count','decoded_video_frames','decoded_audio_packets','decoded_audio_PCM_bytes')}))
        return 0 if report['status'] == 'passed_complete_software_movie_decode' else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
