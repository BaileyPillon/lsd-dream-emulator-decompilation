"""Bind an extracted sound inventory to raw Mode 2/Form 1 disc bytes."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.inventory_sound import FILE_LIMIT, collect, require, sha


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            digest.update(block)
    return digest.hexdigest()


def both(record, offset):
    little = struct.unpack_from('<I', record, offset)[0]
    require(little == struct.unpack_from('>I', record, offset + 4)[0],
            'ISO little/big-endian values disagree.')
    return little


def qualify(layout, disc, expected_sha256):
    disc = Path(disc)
    size = disc.stat().st_size
    require(0 < size <= 2**30 and size % 2352 == 0, 'Use a bounded raw 2352-byte-sector data track.')
    require(len(expected_sha256) == 64 and all(c in '0123456789abcdefABCDEF' for c in expected_sha256),
            'Supply the complete expected raw-disc SHA-256.')
    require(file_sha(disc) == expected_sha256.lower(), 'Raw disc hash differs.')
    corpus = collect(layout)
    require(not corpus['unresolved'], 'Resolve sound structures before qualifying their source disc.')
    layout = Path(layout)
    layout_raw = layout.read_bytes()
    require(sha(layout_raw) == corpus['layout']['sha256'], 'Layout changed.')
    layout_entries = {}

    def layout_walk(directory, parent=PurePosixPath('/')):
        for item in directory:
            if item.tag not in ('dir', 'file'):
                continue
            path = parent / item.attrib['name']
            if item.tag == 'dir':
                layout_walk(item, path)
            elif str(path).upper() in corpus['inputs']:
                layout_entries[str(path).upper()] = item.attrib

    layout_walk(ET.fromstring(layout_raw).find('./track/directory_tree'))
    with disc.open('rb') as stream:
        def extent(lba, length):
            sectors = (length + 2047) // 2048
            require(0 <= lba and 0 < length <= FILE_LIMIT and (lba + sectors) * 2352 <= size,
                    'Disc extent is outside its bound.')
            value = bytearray()
            for index in range(sectors):
                number = lba + index
                stream.seek(number * 2352)
                raw = stream.read(2352)
                absolute = number + 150
                parts = (absolute // 4500, (absolute // 75) % 60, absolute % 75)
                msf = bytes((n // 10) * 16 + n % 10 for n in parts)
                require(len(raw) == 2352 and raw[:12] == b'\0' + b'\xff' * 10 + b'\0'
                        and raw[12:15] == msf and raw[15] == 2
                        and raw[16:20] == raw[20:24] and not raw[18] & 0x20,
                        'Read sector has invalid sync, MSF or Mode 2/Form 1 fields.')
                value.extend(raw[24:2072])
            return bytes(value[:length])

        volume = extent(16, 2048)
        require(volume[:7] == b'\x01CD001\x01' and volume[128:132] == b'\x00\x08\x08\x00',
                'Unsupported ISO primary volume descriptor or block size.')
        root = volume[156:190]
        pending = [(PurePosixPath('/'), both(root, 2), both(root, 10))]
        directories, files, entries = set(), {}, 0
        while pending:
            parent, lba, length = pending.pop()
            require(len(parent.parts) <= 32 and 0 < length <= 2**20
                    and len(directories) < 128 and (lba, length) not in directories,
                    'Repeated or unbounded ISO directories.')
            directories.add((lba, length))
            data, cursor = extent(lba, length), 0
            while cursor < len(data):
                length = data[cursor]
                if length == 0:
                    cursor = (cursor // 2048 + 1) * 2048
                    continue
                record = data[cursor:cursor + length]
                require(length >= 34 and len(record) == length and record[1] == 0
                        and not record[25] & 128 and cursor % 2048 + length <= 2048
                        and 33 + record[32] <= length, 'Unsupported/truncated ISO directory record.')
                name = record[33:33 + record[32]]
                cursor += length
                if name in (b'\0', b'\x01'):
                    continue
                entries += 1
                require(entries <= 4096, 'Unbounded ISO directory entries.')
                name = name.decode('ascii').split(';', 1)[0]
                require(name not in ('', '.', '..') and '/' not in name and '\\' not in name,
                        'Invalid ISO path component.')
                path = parent / name
                child_lba, child_size = both(record, 2), both(record, 10)
                if record[25] & 2:
                    pending.append((path, child_lba, child_size))
                else:
                    key = str(path).upper()
                    require(key not in files and len(files) < 4096, 'Duplicate or unbounded ISO files.')
                    files[key] = (child_lba, child_size)
        audio = {name for name in files if PurePosixPath(name).suffix in ('.VH', '.VB', '.SEQ')}
        require(audio == set(corpus['inputs']), 'Layout and disc audio path sets differ.')
        rows = []
        for name, info in sorted(corpus['inputs'].items()):
            lba, length = files[name]
            require(int(layout_entries[name].get('offs', '-1')) == lba and length == info['bytes'],
                    'Disc and extraction audio extents differ: ' + name)
            require(sha(extent(lba, length)) == info['sha256'] == file_sha(info['source']),
                    'Disc and extraction audio bytes differ: ' + name)
            rows.append(dict(path=name, ISO_LBA=lba, bytes=length, sha256=info['sha256']))
    require(disc.stat().st_size == size and file_sha(disc) == expected_sha256.lower()
            and layout.read_bytes() == layout_raw, 'Disc or layout changed during qualification.')
    return dict(schema_version=1, status='raw_disc_sound_paths_extents_and_all_bytes_verified',
                raw_disc_sha256=expected_sha256.lower(), raw_disc_bytes=size,
                independently_walked_ISO_files=len(files), audio_files_verified=len(rows),
                audio_payload_bytes=sum(r['bytes'] for r in rows), rows=rows,
                extensions=dict(Counter(PurePosixPath(r['path']).suffix for r in rows)),
                all_read_Mode2_Form1_sectors_valid=True, no_payload_extracted_to_disk=True,
                source_edition_verified_by_this_tool=False, audio_playback_verified=False,
                producer_sha256=sha(Path(__file__).read_bytes()), layout_sha256=sha(layout_raw),
                inventory_tool_sha256=corpus['producer_sha256'], whole_feature_groups_accepted=0,
                scope='PVD, directories and audio payload bytes only; no mixed movie-sector, ECC, '
                      'audible playback or original-edition authentication is inferred.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', type=Path, required=True)
    parser.add_argument('--disc', type=Path, required=True)
    parser.add_argument('--expected-disc-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        require(not args.output.exists(), 'Refusing to replace an existing report.')
        result = qualify(args.layout, args.disc, args.expected_disc_sha256)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
        print(json.dumps({k: result[k] for k in ('status', 'audio_files_verified', 'audio_payload_bytes')}))
        return 0
    except (OSError, ValueError, KeyError, struct.error, ET.ParseError) as error:
        print(json.dumps(dict(status='invalid_sound_disc_inputs', error=str(error))), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
