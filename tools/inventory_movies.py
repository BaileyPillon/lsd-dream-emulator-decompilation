"""Audit local STR frames and original movie routing; no audiovisual acceptance."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import configure
from tools.feature_inventory import mask_comments
from tools.inventory_disc import bounded_source, inspect_layout
from tools.progress import check_build_current

CANONICAL_SHA256 = '282308ade239ce61b5603651dbbab0476a681b5d3618e82c0d3c3a95316d302f'
PATH_ADDRESS, PATH_COUNT, PATH_WIDTH = 0x80081A04, 653, 28
CUTOFF_ADDRESS, CUTOFF_COUNT = 0x80086170, 50
SECTOR_BYTES, CHUNK_BYTES = 2336, 2016
FORMAT_REFERENCE = ('https://github.com/m35/jpsxdec/blob/'
                    'fd5403629ac81aaca0feff0dc89e6cadd6353b26/'
                    'jpsxdec/PlayStation1_STR_format.txt')


def reference_tables(image, paths_source, cutoff_source):
    """Require canonical bytes and exact C initializer equality, without eval."""
    if hashlib.sha256(image).hexdigest() != CANONICAL_SHA256:
        raise ValueError('The reference executable is not canonical.')
    load = struct.unpack_from('<I', image, 0x18)[0]

    def span(address, size):
        offset = 0x800 + address - load
        if offset < 0x800 or offset + size > len(image):
            raise ValueError('Native table lies outside the executable payload.')
        return image[offset:offset + size]

    paths_source, cutoff_source = mask_comments(paths_source), mask_comments(cutoff_source)
    declaration = re.search(r'\bg_STRING_TABLE\[LSD_PATH_COUNT\]\[LSD_PATH_LEN\]\s*=\s*\{(.*?)\};', paths_source, re.S)
    if not declaration:
        raise ValueError('Unsupported path-table initializer.')
    body = declaration[1]
    token = r'"(?:[^"\\]|\\.)*"'
    if re.sub(token, '', body).replace(',', '').strip():
        raise ValueError('Path-table entries must be plain string literals.')
    paths = [json.loads(value) for value in re.findall(token, body)]
    if len(paths) != PATH_COUNT:
        raise ValueError('Unexpected path-table count.')
    packed = bytearray()
    for value in paths:
        if not re.fullmatch(r'[A-Za-z0-9_.\\-]+', value):
            raise ValueError('Unsupported native path characters.')
        raw = value.encode('ascii')
        if len(raw) >= PATH_WIDTH:
            raise ValueError('Path exceeds its native record.')
        packed.extend(raw.ljust(PATH_WIDTH, b'\0'))
    native_paths = span(PATH_ADDRESS, PATH_COUNT * PATH_WIDTH)
    if packed != native_paths:
        raise ValueError('C path-table bytes differ from the executable.')
    declaration = re.search(r'\bg_MovieDurations\[\]\s*=\s*\{(.*?)\};', cutoff_source, re.S)
    if not declaration:
        raise ValueError('Unsupported movie-cutoff initializer.')
    entries = [item.strip() for item in declaration[1].split(',') if item.strip()]
    if len(entries) != CUTOFF_COUNT or any(not re.fullmatch(r'-?\d+', value) for value in entries):
        raise ValueError('Unexpected movie-cutoff values or count.')
    cutoffs = list(map(int, entries))
    if any(not -32768 <= value <= 32767 for value in cutoffs):
        raise ValueError('Movie cutoff lies outside a signed halfword.')
    native_cutoffs = span(CUTOFF_ADDRESS, CUTOFF_COUNT * 2)
    if struct.pack('<50h', *cutoffs) != native_cutoffs:
        raise ValueError('C movie-cutoff bytes differ from the executable.')
    return paths, cutoffs, {'path_table_sha256': hashlib.sha256(native_paths).hexdigest(),
                            'cutoff_table_sha256': hashlib.sha256(native_cutoffs).hexdigest()}


def movie_routes(paths, cutoffs):
    """Recorded matching getters: seven openings, ending, six events, 24 special clips, logo."""
    bindings = [('opening', 560 + i, i) for i in range(7)]
    bindings += [('ending', 567, 7)]
    bindings += [('event', 568 + i, 8 + i) for i in range(6)]
    bindings += [('special_day', 574 + 6 * day + variant, 14 + 2 * day + variant)
                 for day in range(12) for variant in range(2)]
    routes = [{'family': family, 'path': '/CDI/' + paths[index].replace('\\', '/'),
               'path_index': index, 'cutoff_index': cutoff, 'frame_cutoff': cutoffs[cutoff]}
              for family, index, cutoff in bindings]
    routes.append({'family': 'logo', 'path': '/CDI/ETC/ASMK.STR', 'path_index': None,
                   'cutoff_index': 49, 'frame_cutoff': cutoffs[49]})
    if len({row['path'] for row in routes}) != len(routes):
        raise ValueError('Movie routes have duplicate paths.')
    return routes


def scan_stream(stream):
    """Validate complete standard v2 STR frames in dumpsxiso mixed-sector input."""
    digest = hashlib.sha256()
    counts, subheaders = Counter(), Counter()
    frames, pending, payload = [], None, bytearray()
    next_chunk = 0
    sector = 0
    while block := stream.read(SECTOR_BYTES):
        if len(block) != SECTOR_BYTES:
            raise ValueError('Truncated mixed STR sector.')
        digest.update(block)
        if block[:4] != block[4:8]:
            raise ValueError('Mixed STR has disagreeing XA subheaders.')
        file_id, channel, flags, coding = block[:4]
        subheaders[(file_id, channel, flags, coding)] += 1
        if flags & 4:
            if not flags & 0x20:
                raise ValueError('XA audio sector is not Form 2.')
            counts['xa_audio'] += 1
        elif flags & 8:
            if flags & 0x20:
                raise ValueError('Video data sector is not Form 1.')
            values = struct.unpack_from('<IHHIIHHIHHI', block, 8)
            magic, chunk, chunks, number, size, width, height, codes, quant, version, reserved = values
            if magic != 0x80010160 or version != 2 or reserved != 0:
                raise ValueError('Unsupported STR video header or version.')
            if not (1 <= chunks <= 128 and chunk < chunks and number > 0 and
                    8 <= size <= chunks * CHUNK_BYTES and size % 4 == 0 and
                    0 < width <= 1024 and 0 < height <= 1024 and
                    codes >> 16 == 0x3800 and 1 <= quant <= 63):
                raise ValueError('Invalid STR video bounds or MDEC metadata.')
            identity = (file_id, channel, chunks, number, size, width, height, codes, quant, version)
            if pending is None:
                if chunk != 0 or number != len(frames) + 1:
                    raise ValueError('Movie frame IDs or initial chunks are not contiguous.')
                pending, payload, next_chunk = identity, bytearray(), 0
            if identity != pending or chunk != next_chunk:
                raise ValueError('Movie chunks are missing, reordered, or inconsistent.')
            payload.extend(block[40:40 + CHUNK_BYTES])
            next_chunk += 1
            counts['video'] += 1
            if next_chunk == chunks:
                if payload[:8] != block[28:36]:
                    raise ValueError('Demultiplexed MDEC prefix differs from its sector header.')
                frames.append({'number': number, 'chunks': chunks, 'encoded_bytes': size,
                               'width': width, 'height': height, 'quantization': quant,
                               'version': version, 'last_sector': sector,
                               'encoded_sha256': hashlib.sha256(payload[:size]).hexdigest()})
                pending, payload, next_chunk = None, bytearray(), 0
        elif flags == 0 and channel == 0 and not any(block[8:2056]):
            counts['zero_data_filler'] += 1
        else:
            raise ValueError('Unclassified STR sector; preserve and inspect this input.')
        sector += 1
    if pending is not None or not frames:
        raise ValueError('Incomplete final frame or no supported video frames.')
    return {'sha256': digest.hexdigest(), 'bytes': sector * SECTOR_BYTES, 'sectors': sector,
            'sector_kinds': dict(counts), 'frame_count': len(frames), 'frames': frames,
            'subheaders': [{'file': key[0], 'channel': key[1], 'flags': key[2],
                           'coding': key[3], 'sectors': count} for key, count in sorted(subheaders.items())]}


def collect(layout, edition_label='unspecified'):
    if check_build_current(ROOT) is not True:
        raise ValueError('A current build must be verified in the configured Linux/WSL environment.')
    image = (ROOT / configure.ROM).read_bytes()
    if (ROOT / configure.EXE).read_bytes() != image:
        raise ValueError('The current build does not match the canonical executable.')
    paths, cutoffs, tables = reference_tables(image, (ROOT / 'src/utils/paths.h').read_text(),
                                             (ROOT / 'src/utils/cd_paths.c').read_text())
    assets = inspect_layout(layout, edition_label)
    movies, non_mixed = {}, []
    for asset in assets['files']:
        if asset['extension'] != '.STR':
            continue
        path = bounded_source(layout, asset['source'])
        if asset['storage_type'] != 'mixed':
            non_mixed.append({key: asset[key] for key in ('path', 'bytes', 'sha256', 'storage_type')})
            continue
        with path.open('rb') as stream:
            movie = scan_stream(stream)
        if movie['sha256'] != asset['sha256'] or movie['bytes'] != asset['bytes']:
            raise ValueError('Movie input changed during its inspection.')
        movie.update(path=asset['path'], lba=asset['lba'])
        movies[asset['path']] = movie
    routes = movie_routes(paths, cutoffs)
    if set(movies) != {route['path'] for route in routes}:
        raise ValueError('Routed movies and mixed STR assets do not match exactly.')
    for route in routes:
        movie = movies[route['path']]
        route['encoded_frames'] = movie['frame_count']
        route['encoded_tail_after_cutoff'] = movie['frame_count'] - route['frame_cutoff']
        if not 0 < route['frame_cutoff'] < movie['frame_count']:
            raise ValueError('Routed movie cutoff is not within its encoded frame range.')
    return {'schema_version': 1, 'recorded_utc': datetime.now(timezone.utc).isoformat(),
            'scope': 'Native path/cutoff tables and complete encoded STR frame structure; not decoded audiovisual or runtime acceptance.',
            'edition_label': edition_label, 'canonical_sha256': hashlib.sha256(image).hexdigest(),
            'producer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'layout_sha256': assets['layout_sha256'], 'native_tables': tables,
            'source_hashes': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                              for name in ('src/utils/paths.h', 'src/utils/cd_paths.c',
                                           'src/file/str_stream.c', 'src/menu/mdec_movie.c',
                                           'src/game/game_flow.c')},
            'format_reference': FORMAT_REFERENCE, 'movie_count': len(movies),
            'encoded_frame_count': sum(movie['frame_count'] for movie in movies.values()),
            'routes': routes, 'movies': list(movies.values()), 'non_mixed_str_files_unparsed': non_mixed,
            'unbound_cutoff_indices': [index for index in range(CUTOFF_COUNT)
                                       if index not in {route['cutoff_index'] for route in routes}],
            'input_modified': False, 'new_c_bytes': 0, 'movie_playback_accepted': False,
            'whole_feature_groups_accepted': 0, 'model_api_calls': 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', required=True)
    parser.add_argument('--edition-label', default='unspecified')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        output = Path(args.output).resolve()
        lab = (ROOT / '.decomp-lab').resolve()
        if not output.is_relative_to(lab) or output == lab or output.exists():
            raise ValueError('Choose a new private output file inside .decomp-lab.')
        result = collect(args.layout, args.edition_label)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
        print(json.dumps({'movie_count': result['movie_count'], 'encoded_frames': result['encoded_frame_count'],
                          'unparsed_data_str_files': len(result['non_mixed_str_files_unparsed']),
                          'movie_playback_accepted': False}))
        return 0
    except (OSError, ValueError, struct.error, ET.ParseError) as error:
        print('[!] ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
