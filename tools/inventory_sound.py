"""Inspect LSD VAB banks and encoded SEQ events without playing or changing them.

File structures, SDK metadata, transfer completion and audible playback are
different evidence. This tool accepts no whole sound/game feature as verified.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.inventory_disc import bounded_source

FILE_LIMIT = 8 * 2**20
LAYOUT_LIMIT = 4 * 2**20
PROGRAMS = 128
TONE_BASE = 32 + PROGRAMS * 16


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def vab_info(header, body):
    """Decode the v7 layout consumed by LSD's original sound library.

    Header program count is a population count. Native IDs index a fixed
    128-row table; populated programs own dense, sixteen-tone storage blocks.
    """
    require(32 <= len(header) <= FILE_LIMIT and len(body) <= FILE_LIMIT,
            'Unbounded or truncated VAB payload.')
    require(header[:4] == b'pBAV' and struct.unpack_from('<I', header, 4)[0] == 7,
            'Only the reviewed pBAV version 7 layout is supported.')
    count, tones, samples = struct.unpack_from('<3H', header, 0x12)
    require(0 <= count <= PROGRAMS and 0 <= tones <= count * 16 and samples <= 255,
            'VAB declared counts exceed their tables.')
    sizes_at = TONE_BASE + count * 512
    require(len(header) == sizes_at + 512, 'VAB header/tone/size-table extent differs.')
    require(struct.unpack_from('<I', header, 12)[0] == len(header) + len(body),
            'VAB total size disagrees with its VH/VB pair.')
    sizes = struct.unpack_from('<256H', header, sizes_at)
    require(sizes[0] == 0 and not any(sizes[samples + 1:]),
            'Reserved or undeclared VAG size entries are nonzero.')
    require(sum(sizes[1:samples + 1]) * 8 == len(body), 'VAG lengths do not cover the complete VB.')
    programs, unused = [], bytearray()
    for native_id in range(PROGRAMS):
        at = 32 + native_id * 16
        number = header[at]
        require(number <= 16, 'Program exceeds sixteen tone slots.')
        if number == 0:
            continue
        ordinal = len(programs)
        require(ordinal < count, 'Populated program count exceeds its header.')
        require(header[at + 1] <= 127 and header[at + 4] <= 127,
                'Active program volume/pan exceeds seven bits.')
        records = []
        for tone in range(number):
            where = TONE_BASE + ordinal * 512 + tone * 32
            raw = header[where:where + 32]
            program_id, vag = struct.unpack_from('<2H', raw, 20)
            require(program_id == native_id, 'Tone owner differs from its native program ID.')
            require(1 <= vag <= samples, 'Tone references an undeclared/reserved VAG ID.')
            require(raw[2] <= 127 and raw[3] <= 127 and raw[4] <= 127
                    and raw[6] <= raw[7] <= 127, 'Unsupported tone volume/pan/key range.')
            records.append(dict(index=tone, header_offset=where, priority=raw[0], mode=raw[1],
                                volume=raw[2], pan=raw[3], center_key=raw[4], shift_byte=raw[5],
                                min_key=raw[6], max_key=raw[7], vibrato_width=raw[8], vibrato_time=raw[9],
                                portamento_width=raw[10], portamento_time=raw[11],
                                pitchbend_down=raw[12], pitchbend_up=raw[13],
                                ADSR1=struct.unpack_from('<H', raw, 16)[0],
                                ADSR2=struct.unpack_from('<H', raw, 18)[0],
                                native_program_id=program_id, VAG_id=vag, raw_sha256=sha(raw)))
        unused.extend(header[TONE_BASE + ordinal * 512 + number * 32:TONE_BASE + (ordinal + 1) * 512])
        programs.append(dict(native_id=native_id, dense_tone_block=ordinal, tone_count=number,
                             volume=header[at + 1], priority=header[at + 2], mode=header[at + 3],
                             pan=header[at + 4], attribute=struct.unpack_from('<H', header, at + 6)[0],
                             tones=records))
    require(len(programs) == count and sum(p['tone_count'] for p in programs) == tones,
            'VAB population/tone totals disagree with actual records.')
    waves, offset = [], 0
    for vag, units in enumerate(sizes[1:samples + 1], 1):
        length = units * 8
        require(length > 0 and length % 16 == 0, 'VAG sample is empty or not block-aligned.')
        raw = body[offset:offset + length]
        filters = Counter(value >> 4 for value in raw[::16])
        shifts = Counter(value & 15 for value in raw[::16])
        flags = Counter(raw[1::16])
        require(all(value <= 4 for value in filters) and all(value <= 12 for value in shifts)
                and all(value <= 7 for value in flags), 'Unreviewed ADPCM filter/shift/flag bits.')
        ends = [i for i, flag in enumerate(raw[1::16]) if flag & 1]
        require(ends, 'Sample has no encoded end flag.')
        first_end = ends[0]
        waves.append(dict(VAG_id=vag, body_offset=offset, bytes=length, ADPCM_blocks=length // 16,
                          raw_sha256=sha(raw), filters=dict(sorted(filters.items())),
                          shifts=dict(sorted(shifts.items())), flags=dict(sorted(flags.items())),
                          first_end_block=first_end, first_end_repeats=bool(raw[first_end * 16 + 1] & 2),
                          loop_start_blocks=[i for i, flag in enumerate(raw[1::16]) if flag & 4],
                          encoded_end_blocks=ends))
        offset += length
    require(offset == len(body), 'Unclassified VB tail.')
    return dict(format='VAB-v7', header_bytes=len(header), body_bytes=len(body),
                header_sha256=sha(header), body_sha256=sha(body), declared_programs=count,
                native_program_ids=[p['native_id'] for p in programs], declared_tones=tones,
                declared_samples=samples, master_volume=header[24], master_pan=header[25],
                active_program_ids_outside_count_prefix=[p['native_id'] for p in programs if p['native_id'] >= count],
                programs=programs, samples=waves, unused_tone_slots=count * 16 - tones,
                unused_tone_storage_sha256=sha(unused), validation='complete_reviewed_file_structure',
                SPU_transfer_verified=False, audible_playback_verified=False)


def seq_info(data):
    """Count encoded channel events; do not assume an initial instrument or duration."""
    require(15 <= len(data) <= FILE_LIMIT and data[:4] == b'pQES', 'Truncated/unsupported SEQ header.')
    require(struct.unpack_from('>I', data, 4)[0] == 1, 'Only SEQ version 1 is supported.')
    resolution = struct.unpack_from('>H', data, 8)[0]
    tempo = int.from_bytes(data[10:13], 'big')
    require(0 < resolution < 0x8000 and data[14] <= 7,
            'Unsupported SEQ resolution/tempo/rhythm.')
    cursor, ticks, running, events, reused, unknown = 15, 0, None, 0, 0, 0
    counts, controls = Counter(), Counter()
    channel_program = [None] * 16
    keys = defaultdict(set)
    programs = defaultdict(set)
    channels = Counter()

    def read_byte():
        nonlocal cursor
        require(cursor < len(data), 'Truncated SEQ event.')
        value = data[cursor]
        cursor += 1
        return value

    def variable():
        value = 0
        for _ in range(4):
            current = read_byte()
            value = (value << 7) | (current & 127)
            if current < 128:
                return value
        raise ValueError('Overlong SEQ delta-time quantity.')

    ended = False
    while cursor < len(data):
        ticks += variable()
        require(cursor < len(data), 'SEQ delta has no event.')
        status = data[cursor]
        if status >= 128:
            cursor += 1
            if status == 255:
                require(read_byte() == 0x2f and read_byte() == 0,
                        'Unreviewed SEQ meta event; only zero-length end-of-track is supported.')
                counts['end_of_track'] += 1
                events += 1
                ended = True
                break
            require(0x80 <= status < 0xf0, 'Unreviewed SEQ system/sysex event.')
            running = status
        else:
            require(running is not None, 'SEQ running status precedes a channel status.')
            status = running
            reused += 1
        operation, channel = status >> 4, status & 15
        values = [read_byte() for _ in range(1 if operation in (12, 13) else 2)]
        require(all(value < 128 for value in values), 'SEQ channel data contains a status byte.')
        channels[channel] += 1
        events += 1
        if operation == 9 and values[1] != 0:
            counts['note_on'] += 1
            program = channel_program[channel]
            if program is None:
                unknown += 1
            else:
                keys[program].add(values[0])
        elif operation == 8 or (operation == 9 and values[1] == 0):
            counts['note_off'] += 1
        elif operation == 11:
            counts['control_change'] += 1
            controls[values[0]] += 1
        elif operation == 12:
            counts['program_change'] += 1
            channel_program[channel] = values[0]
            programs[channel].add(values[0])
        else:
            counts[{10: 'poly_pressure', 13: 'channel_pressure', 14: 'pitch_bend'}[operation]] += 1
    require(ended and cursor == len(data), 'SEQ end is absent or has an unclassified tail.')
    return dict(format='SEQ-v1', bytes=len(data), raw_sha256=sha(data), resolution=resolution,
                initial_tempo_word=tempo, rhythm_numerator=data[13], rhythm_denominator_power=data[14],
                zero_initial_tempo_word=tempo == 0, zero_rhythm_numerator=data[13] == 0,
                zero_header_words_replaced=False, native_header_semantics_verified=False,
                encoded_tick_span=ticks, events=events, event_kinds=dict(sorted(counts.items())),
                running_status_events=reused, channel_event_counts=dict(sorted(channels.items())),
                controllers=dict(sorted(controls.items())),
                declared_program_changes={str(k): sorted(v) for k, v in sorted(programs.items())},
                known_program_note_keys={str(k): sorted(v) for k, v in sorted(keys.items())},
                note_ons_before_first_channel_program_change=unknown,
                initial_channel_programs_assumed=False, encoded_ticks_are_playback_duration=False,
                native_event_execution_verified=False, audible_playback_verified=False)


def audio_files(layout):
    layout = Path(layout).resolve(strict=True)
    require(layout.is_file() and layout.stat().st_size <= LAYOUT_LIMIT, 'Unbounded layout.')
    raw = layout.read_bytes()
    tree = ET.fromstring(raw).find('./track/directory_tree')
    require(tree is not None, 'Layout has no data-track directory tree.')
    found, visited, directories, nodes = {}, set(), set(), 0

    def visit(directory, parent=PurePosixPath('/')):
        nonlocal nodes
        require(len(parent.parts) <= 32, 'Oversized directory depth.')
        for element in directory:
            if element.tag not in ('file', 'dir'):
                continue
            name = element.get('name', '')
            require(name and name not in ('.', '..') and '/' not in name and '\\' not in name,
                    'Invalid disc entry name.')
            virtual = parent / name
            key = str(virtual).upper()
            nodes += 1
            require(nodes <= 4096, 'Oversized directory inventory.')
            if key in directories and element.tag == 'dir' and set(element.attrib) == {'name'}:
                visit(element, virtual)  # dumpsxiso can reopen FILM to append a later file.
                continue
            require(key not in visited, 'Repeated payload/directory path.')
            visited.add(key)
            if element.tag == 'dir':
                directories.add(key)
                visit(element, virtual)
            elif virtual.suffix.upper() in ('.VH', '.VB', '.SEQ'):
                path = bounded_source(layout, element.get('source', ''))
                require(path.stat().st_size <= FILE_LIMIT, 'Unbounded sound payload.')
                found[key] = path

    visit(tree)
    require(found, 'Layout declares no sound payloads.')
    return layout, raw, found


def collect(layout, edition_label='unspecified'):
    require(isinstance(edition_label, str) and edition_label.strip(), 'Supply an edition label.')
    layout, layout_raw, files = audio_files(layout)
    records, inputs, unresolved = [], {}, []

    def payload(name):
        path = files[name]
        value = path.read_bytes()
        require(len(value) <= FILE_LIMIT, 'Sound payload grew beyond its bound.')
        inputs[name] = dict(source=str(path), bytes=len(value), sha256=sha(value))
        return value

    for name in sorted(files):
        if name.endswith('.VB'):
            if name[:-3] + '.VH' not in files:
                payload(name)
                unresolved.append(dict(path=name, reason='VB has no paired VH.'))
            continue
        try:
            if name.endswith('.VH'):
                pair = name[:-3] + '.VB'
                head = payload(name)
                require(pair in files, 'VH has no paired VB.')
                body = payload(pair)
                records.append(dict(path=name, body_path=pair, **vab_info(head, body)))
            else:
                records.append(dict(path=name, **seq_info(payload(name))))
        except ValueError as error:
            unresolved.append(dict(path=name, reason=str(error)))
    for name, row in inputs.items():
        require(files[name].stat().st_size == row['bytes'] and sha(files[name].read_bytes()) == row['sha256'],
                'Sound input changed during inspection: ' + name)
    require(layout.read_bytes() == layout_raw, 'Layout changed during inspection.')
    banks = [r for r in records if r['format'] == 'VAB-v7']
    seqs = [r for r in records if r['format'] == 'SEQ-v1']
    samples = [s for bank in banks for s in bank['samples']]
    review = [dict(path=s['path'], reason='Original zero tempo is preserved; evaluate the pinned native initializer and natural route separately.')
              for s in seqs if s['zero_initial_tempo_word']]
    return dict(schema_version=1, status='sound_payloads_need_review' if unresolved or review else 'inspected_structural_sound_inventory',
                recorded_utc=datetime.now(timezone.utc).isoformat(), edition_label=edition_label.strip(),
                layout=dict(path=str(layout), sha256=sha(layout_raw)), inputs=inputs,
                totals=dict(layout_audio_files=len(files), parsed_banks=len(banks), parsed_sequences=len(seqs),
                            programs=sum(b['declared_programs'] for b in banks),
                            tones=sum(b['declared_tones'] for b in banks), samples=len(samples),
                            distinct_sample_payloads=len({s['raw_sha256'] for s in samples}),
                            ADPCM_blocks=sum(s['ADPCM_blocks'] for s in samples),
                            first_end_repeat_flagged_samples=sum(s['first_end_repeats'] for s in samples),
                            encoded_sequence_events=sum(s['events'] for s in seqs),
                            zero_initial_tempo_sequences=sum(s['zero_initial_tempo_word'] for s in seqs),
                            zero_rhythm_numerator_sequences=sum(s['zero_rhythm_numerator'] for s in seqs),
                            native_header_review_sequences=len(review),
                            unresolved_files=len(unresolved)),
                records=records, unresolved=unresolved, native_header_review=review,
                producer_sha256=sha(Path(__file__).read_bytes()),
                original_game_modified=False, new_C_bytes=0, model_API_calls=0,
                whole_feature_groups_accepted=0, SPU_transfer_verified=False, audible_playback_verified=False,
                scope='Caller-provided layout payload structures and encoded events only; source edition, original disc provenance, '
                      'SDK execution, initial instruments, loop/control semantics, transfer completion and playback require separate evidence.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', type=Path, required=True)
    parser.add_argument('--edition-label', default='unspecified')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        require(not args.output.exists(), 'Refusing to replace an existing report.')
        result = collect(args.layout, args.edition_label)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
        print(json.dumps(result['totals']))
        return 1 if result['unresolved'] or result['native_header_review'] else 0
    except (OSError, ValueError, ET.ParseError, struct.error) as error:
        print(json.dumps(dict(status='invalid_sound_inputs', error=str(error))), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
