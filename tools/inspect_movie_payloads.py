"""Verify full native encoded/RLE buffer hashes; GPU presentation is separate."""
import argparse
from collections import Counter, defaultdict, deque
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import inspect_reel_decoder as prefix
from tools import inspect_card_reel as card
from tools.inspect_progression_history import require

HEADER = b'LSDMOV1\0'
FIELDS = ('frame', 'ordinal', 'kind', 'pc', 'timestamp', 'sp', 'ra',
    'entry_frame', 'entry_timestamp', 'entry_sp', 'entry_ra', 'a0', 'a1', 'a2', 'a3',
    'transfer_pc', 'delay_pc', 'transfer_word', 'delay_word',
    'return_jump_pc', 'return_delay_pc', 'return_jump_word', 'return_delay_word',
    'source_address', 'source_bytes', 'data_offset', 'command_word',
    'input_address', 'output_address', 'frame_id', 'header_address',
    *('header_' + str(n) for n in range(8)), 'status', 'active_movie', 'v0', 'v1')
assert len(FIELDS) == 43


def file_sha(path):
    with Path(path).open('rb') as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024**2), b''):
            digest.update(block)
        return digest.hexdigest()


def corpus(disc):
    disc = Path(disc)
    before = disc.stat()
    require(before.st_size == 648088896 and file_sha(disc) == 'cbf377af3e9207964f11044202eb5ecec2594a3c96e0919f7aa807d328654e61',
        'Require the qualified complete original Japanese disc.')
    inventory = json.loads((ROOT / 'docs/movie-inventory-checks.json').read_bytes())
    movies, full_lookup, lookup, words = {}, defaultdict(set), defaultdict(set), {}
    chain = hashlib.sha256()
    with disc.open('rb') as stream:
        for item in inventory['movies']:
            transport = prefix.MovieReader(stream, item)
            observed = prefix.scan_stream(transport)
            for key in ('sha256', 'bytes', 'sectors', 'frame_count', 'sector_kinds', 'subheaders'):
                require(observed[key] == item[key], 'Complete source movie differs: ' + item['path'])
            require(len(transport.prefixes) == len(observed['frames']), 'Source prefix/frame corpus is incomplete.')
            frames = {}
            for frame, fingerprint, command in zip(observed['frames'], transport.prefixes, transport.first_words):
                value = dict(frame, first_word=command, prefix=fingerprint)
                frames[frame['number']] = value
                full_lookup[(frame['number'], frame['encoded_sha256'])].add(item['path'])
                lookup[(frame['number'], fingerprint)].add(item['path'])
                words[(frame['number'], fingerprint)] = command
                chain.update(item['path'].encode('ascii') + b'\0' + struct.pack('<II', frame['number'], frame['encoded_bytes']))
                chain.update(bytes.fromhex(frame['encoded_sha256']))
            movies[item['path']] = dict(frame_count=observed['frame_count'], frames=frames)
    after = disc.stat()
    require((before.st_size, before.st_ino, before.st_mtime_ns) == (after.st_size, after.st_ino, after.st_mtime_ns),
        'The original disc changed during corpus inspection.')
    count = sum(value['frame_count'] for value in movies.values())
    require(len(movies) == 39 and count == 22382, 'Incomplete full encoded-frame corpus.')
    return dict(movies=movies, full_lookup=full_lookup, lookup=lookup, prefix_words=words,
        summary=dict(source_movies=39, source_encoded_frames=count, complete_source_movie_hashes_checked=True,
            original_disc_sha256=file_sha(disc), complete_encoded_frame_index_sha256=chain.hexdigest(),
            full_encoded_ID_hash_keys=len(full_lookup), ambiguous_full_encoded_ID_hash_keys=sum(len(v) > 1 for v in full_lookup.values()),
            source_movies_or_disc_copied=False))


def event_rows(stream):
    require(stream.read(8) == HEADER, 'Wrong full movie-payload journal header.')
    previous = [[0] * 43 for _ in range(3)]
    total_bytes, total = 0, 0
    while True:
        raw = stream.read(1)
        if not raw:
            return
        tag = raw[0]
        require(tag < 3, 'Unsupported full movie-payload target tag.')
        values, size = [], 1
        for column in range(43):
            encoded, length = prefix.read_varint(stream)
            size += length
            delta = (encoded >> 1) ^ -(encoded & 1)
            value = (previous[tag][column] + delta) & 0xffffffff
            previous[tag][column] = value
            values.append(value)
        require(values[2] == tag + 1, 'Movie-payload tag/kind disagree.')
        digest = stream.read(32)
        require(len(digest) == 32, 'Truncated full payload hash.')
        size += 32
        total_bytes += size
        total += 1
        require(total <= 40000 and total_bytes <= 32 * 1024**2, 'Movie-payload journal exceeds its bound.')
        yield dict(zip(FIELDS, values), payload_sha256=digest.hex(), wire_bytes=size)


def inspect_events(events, summary, index, old_entries):
    require(summary['schema_version'] == 1 and summary['protocol'] == 'full_movie_payload_sha256_v1'
        and summary['event_numeric_words'] == 43 and summary['native_event_bytes'] == 172
        and summary['observer_enabled'] is True and summary['arm_frame'] == 21884
        and summary['frame_event_limit'] == 16 and summary['frame_payload_limit_bytes'] == 1024**2
        and summary['native_errors'] == summary['native_overflow'] == summary['pending_VLC_returns'] == 0
        and summary['pending_RLE_buffers_without_MDEC_input'] == 1
        and summary['full_encoded_input_at_VLC_entry'] is True
        and summary['full_RLE_at_actual_VLC_return'] is True and summary['full_RLE_at_MDEC_input_entry'] is True
        and summary['original_CPU_source_modified'] is False and summary['game_MainRAM_or_instructions_written'] is False
        and summary['individual_frame_GPU_presentation_accepted'] is False, 'Unqualified full-payload summary or scope.')
    expected = {1: deque(), 3: deque()}
    for event in old_entries:
        if event['pc'] == 0x80046568:
            expected[1].append(event)
        elif event['pc'] == 0x80045f84:
            expected[3].append(event)
    counts = Counter()
    segments, buffers = [], {}
    pending = None
    total = raw_bytes = payload_bytes = frame_count = frame_cursor = 0
    last_frame, first, last = -1, None, None
    chain = hashlib.sha256()
    encoded_chain, rle_chain = hashlib.sha256(), hashlib.sha256()
    for event in events:
        total += 1
        kind, frame = event['kind'], event['frame']
        require(kind in (1, 2, 3) and event['ordinal'] == total and 21884 <= frame <= 62529 and frame >= last_frame,
            'Wrong full-payload event ordinal/frame schedule.')
        if frame != last_frame:
            frame_count = frame_cursor = 0
        frame_count += 1
        require(frame_count <= 16 and event['data_offset'] == frame_cursor, 'Missing/reordered native per-frame payload extent.')
        size = event['source_bytes']
        require(event['status'] == 0 and 4 <= size <= 0x40000 and size % 4 == 0
            and 0x80010000 <= event['source_address'] <= 0x80200000 - size
            and event['source_address'] % 4 == 0 and 0x80010000 <= event['active_movie'] < 0x80200000,
            'Invalid full native payload pointer, size or status.')
        frame_cursor += size
        require(frame_cursor <= 1024**2, 'Native frame payload bound exceeded.')
        last_frame = frame
        first = frame if first is None else first
        last = frame
        require(event['header_2'] == event['frame_id'] and event['header_3'] >= 8
            and event['command_word'] == event['header_5'] and event['command_word'] >> 16 == 0x3800,
            'Accepted native frame header/command identity differs.')
        if kind in (1, 3):
            require(expected[kind], 'Extra full-buffer entry without its original method-entry observation.')
            entry = expected[kind].popleft()
            for key in ('frame', 'pc', 'timestamp', 'sp', 'ra', 'a0', 'a1', 'a2', 'a3',
                    'transfer_pc', 'delay_pc', 'transfer_word', 'delay_word', 'active_movie'):
                require(event[key] == entry[key], 'Full buffer does not identify its actual native entry: ' + key)
            require(event['entry_frame'] == frame and event['entry_timestamp'] == event['timestamp']
                and event['entry_sp'] == event['sp'] and event['entry_ra'] == event['ra'], 'Entry context disagrees with itself.')
        if kind == 1:
            require(pending is None and event['source_address'] == event['a0'] == event['input_address']
                and event['output_address'] == event['a1'] and event['frame_id'] == event['a2']
                and size == event['header_3'] and size <= 0x12000,
                'Encoded input lacks its accepted native size/buffer association.')
            require(event['header_address'] == entry['sdk_header_base'] + entry['sdk_next_index'] * 32
                and event['input_address'] == entry['sdk_header_base'] + entry['sdk_data_index'] * 32 + entry['sdk_next_index'] * 2016,
                'Accepted header/ring does not follow the original StGetNext address calculation.')
            number = event['frame_id']
            if not segments or number <= segments[-1]['last_ID']:
                require(number == 1, 'A full encoded source segment regressed without frame one.')
                segments.append(dict(first_ID=number, last_ID=0, encoded_inputs=0, RLE_returns=0, MDEC_inputs=0,
                    candidates=set(index['movies'])))
            segment = segments[-1]
            require(number == segment['last_ID'] + 1, 'Full encoded input IDs are missing or reordered.')
            candidates = index['full_lookup'].get((number, event['payload_sha256']), set())
            candidates = {path for path in candidates if index['movies'][path]['frames'][number]['encoded_bytes'] == size
                and index['movies'][path]['frames'][number]['first_word'] == event['command_word']
                and index['movies'][path]['frames'][number]['width'] | (index['movies'][path]['frames'][number]['height'] << 16) == event['header_4']
                and index['movies'][path]['frames'][number]['quantization'] | (index['movies'][path]['frames'][number]['version'] << 16) == event['header_6']}
            require(candidates, 'Complete native encoded input hash/size is absent from the original disc.')
            segment['candidates'] &= candidates
            require(segment['candidates'], 'Complete encoded buffer sequence has no consistent source movie.')
            segment['encoded_inputs'] += 1
            segment['last_ID'] = number
            pending = dict(event, segment=len(segments) - 1)
            encoded_chain.update(struct.pack('<III', number, frame, size) + bytes.fromhex(event['payload_sha256']))
        elif kind == 2:
            require(pending is not None, 'VLC completion lacks its full encoded entry.')
            for key in ('entry_frame', 'entry_timestamp', 'entry_sp', 'entry_ra', 'a0', 'a1', 'a2', 'a3',
                    'transfer_pc', 'delay_pc', 'transfer_word', 'delay_word', 'active_movie',
                    'input_address', 'output_address', 'frame_id', 'header_address', *('header_' + str(n) for n in range(8))):
                require(event[key] == pending[key], 'VLC return is not bound to its original full input: ' + key)
            require(event['pc'] == event['ra'] == event['entry_ra'] and event['sp'] == event['entry_sp']
                and event['return_jump_pc'] == 0x800465b0 and event['return_delay_pc'] == 0x800465b4
                and event['return_jump_word'] == 0x03e00008 and event['return_delay_word'] == 0,
                'VLC completion lacks its actual return jump/delay and restored caller stack.')
            address = event['output_address']
            require(event['source_address'] == address and size == 4 + (event['command_word'] & 0xffff) * 4
                and address not in buffers, 'VLC output size is invalid or its destination was reused before MDEC input.')
            buffers[address] = dict(event, segment=pending['segment'])
            segments[pending['segment']]['RLE_returns'] += 1
            rle_chain.update(struct.pack('<III', event['frame_id'], frame, size) + bytes.fromhex(event['payload_sha256']))
            pending = None
        else:
            address = event['source_address']
            require(address == event['a0'] == event['output_address'] and event['a1'] == 2 and address in buffers,
                'MDEC full input lacks a completed native VLC destination.')
            decoded = buffers.pop(address)
            require(all(event[key] == decoded[key] for key in ('input_address', 'output_address', 'header_address',
                *('header_' + str(n) for n in range(8)))), 'MDEC input has changed accepted source/header provenance.')
            require(event['source_bytes'] == decoded['source_bytes'] and event['payload_sha256'] == decoded['payload_sha256']
                and event['command_word'] == decoded['command_word'] and event['frame_id'] == decoded['frame_id'],
                'Complete MDEC input differs from the completed VLC output, including bytes beyond the old prefix.')
            segments[decoded['segment']]['MDEC_inputs'] += 1
        counts[kind] += 1
        raw_bytes += event['wire_bytes']
        payload_bytes += size
        chain.update(struct.pack('<43I', *(event[key] for key in FIELDS)))
        chain.update(bytes.fromhex(event['payload_sha256']))
    require(not pending and not any(expected.values()) and len(buffers) == 1, 'Missing full payload entries, returns or final pending output.')
    require(total == summary['entries'] and [counts[n] for n in (1, 2, 3)] == summary['counts']
        and counts[1] == summary['accepted_callbacks'] and raw_bytes == summary['raw_entry_bytes']
        and payload_bytes == summary['complete_native_payload_bytes_hashed']
        and first == summary['first_entry_frame'] and last == summary['last_entry_frame']
        and chain.hexdigest() == summary['numeric_and_full_payload_hash_chain_sha256'],
        'Full payload summary differs from independently reconstructed records.')
    for segment in segments:
        segment['candidate_paths'] = sorted(segment.pop('candidates'))
    return dict(status='actual_full_native_movie_buffers_inspected', entries=total, counts=[counts[n] for n in (1, 2, 3)],
        first_entry_frame=first, last_entry_frame=last, complete_payload_bytes_hashed=payload_bytes,
        encoded_chain_sha256=encoded_chain.hexdigest(), completed_RLE_chain_sha256=rle_chain.hexdigest(),
        numeric_and_full_payload_hash_chain_sha256=chain.hexdigest(), segments=segments,
        final_completed_RLE_without_MDEC_input=[{key: row[key] for key in ('frame_id', 'frame', 'source_bytes', 'payload_sha256', 'segment')}
            for row in buffers.values()], individual_frame_GPU_presentation_accepted=False)


def load_profile(folder, index):
    folder = Path(folder)
    recording = card.load_recording(folder)
    old = prefix.inspect(folder, index)
    prefix.validate_complete_reel(old, index)
    summary = json.loads((folder / 'payload-summary.json').read_bytes())
    path = folder / 'payload-entries.bin.gz'
    require(path.is_file() and path.stat().st_size <= 1572864 and path.stat().st_size == summary['compressed_entry_bytes'],
        'Oversized or incomplete compressed full-payload journal.')
    with gzip.open(folder / 'decoder-entries.bin.gz', 'rb') as stream:
        entries = list(prefix.entry_rows(stream))
    with gzip.open(path, 'rb') as stream:
        payloads = inspect_events(event_rows(stream), summary, index, entries)
    expected = [f'/CDI/FILM/SPDAY{day:02d}{variant}.STR' for day in range(1, 11) for variant in 'AB']
    require([row['candidate_paths'] for row in payloads['segments']] == [[path] for path in expected],
        'Full encoded hashes must uniquely identify all twenty reel films in original order.')
    for i, row in enumerate(payloads['segments']):
        limit = index['movies'][expected[i]]['frame_count']
        require(row['encoded_inputs'] == row['RLE_returns'] == row['last_ID']
            and row['MDEC_inputs'] == row['last_ID'] - int(i == 19)
            and (row['last_ID'] == limit if i < 19 else row['last_ID'] < limit), 'Unexpected complete/timed film payload range.')
    return dict(recording=recording, decoder=old, payloads=payloads, summary=summary, payload_trace_sha256=file_sha(path))


def compare(original, rebuilt, stock):
    base = card.compare_data(original['recording'], rebuilt['recording'])
    qualification = [prefix.stock_comparison(stock, value['recording']) for value in (original, rebuilt)]
    differences = {}
    if not base['passed']:
        differences['original_rebuilt_recording'] = base['differences']
    for key in ('decoder', 'payloads', 'payload_trace_sha256'):
        if original[key] != rebuilt[key]:
            differences[key] = True
    require(original['summary']['journal_storage_mode'] == 'direct_file', 'Require an independently stored original payload journal.')
    require(rebuilt['summary']['replay_compressed_bytes_generated_and_compared'] is True
        and rebuilt['summary']['reused_source_sha256'] == original['payload_trace_sha256'], 'Missing rebuilt full-byte generation/source qualification.')
    if not all(row['all_complete_output_windows_equal'] for row in qualification):
        differences['stock_output_qualification'] = True
    return dict(schema_version=1, status='equal_for_full_native_movie_payload_scope' if not differences else 'recorded_full_native_movie_payload_differences',
        passed=not differences, dimensions=original['recording']['dimensions'], full_payloads=original['payloads'],
        stock_observer_qualification=qualification, differences=differences,
        observer_original_rebuilt_complete_states_and_full_outputs_equal=base['passed'],
        rebuilt_journal_storage_mode=rebuilt['summary']['journal_storage_mode'],
        all_generated_rebuilt_payload_journal_bytes_compared=True, constructed_history_not_naturally_earned=True,
        individual_frame_GPU_presentation_accepted=False, original_hardware_timing_verified=False,
        new_matching_C_bytes=0, new_gameplay_features=0, whole_feature_groups_accepted=0, whole_NPC_encounters_accepted=0, model_API_calls=0)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original', type=Path)
    parser.add_argument('rebuilt', nargs='?', type=Path)
    parser.add_argument('--disc', type=Path, required=True)
    parser.add_argument('--stock', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        index = corpus(args.disc)
        original = load_profile(args.original, index)
        stock = card.load_recording(args.stock)
        if args.rebuilt:
            result = compare(original, load_profile(args.rebuilt, index), stock)
        else:
            qualified = prefix.stock_comparison(stock, original['recording'])
            result = dict(status='original_full_native_payload_reel_inspected', passed=qualified['all_complete_output_windows_equal'],
                dimensions=original['recording']['dimensions'], payloads=original['payloads'], stock_qualification=qualified,
                payload_trace_sha256=original['payload_trace_sha256'], complete_payload_scope=True,
                stock_full_outputs_equal=qualified['all_complete_output_windows_equal'])
        result['source_corpus'] = index['summary']
        code = 0 if result['passed'] else 1
    except (OSError, ValueError, KeyError, TypeError, EOFError) as error:
        result = dict(status='invalid_or_incomplete_full_movie_payload_evidence', passed=False, error=str(error))
        code = 2
    raw = json.dumps(result, indent=2) + '\n'
    if args.output:
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(raw)
    print(raw, end='')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
