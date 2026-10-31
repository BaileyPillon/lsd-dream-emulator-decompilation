"""Create a separate, explicitly constructed history-card input for reel research.

Requires the qualified raw slot-01, block-1, first-year Day-002 save layout.
Neither the source card nor any emulator/player save is modified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.compare_card_roundtrip import lsd_payload, parse_card, require

CELLS = (511, 257, 0, -768)
PAYLOAD_OFFSET = 8192 + 512


def construct_card(source):
    files = parse_card(source)
    payload = lsd_payload(source)
    require(files[0]['blocks'] == [1] and struct.unpack_from('<I', payload, 4)[0] == 0,
            'Require the qualified first-year, block-1 save layout.')
    card = bytearray(source)
    struct.pack_into('<I', card, PAYLOAD_OFFSET + 8, 4)
    struct.pack_into('<4h', card, PAYLOAD_OFFSET + 0x18, *CELLS)
    card[PAYLOAD_OFFSET + 0x467] = 0
    parse_card(card)
    changes = [dict(file_offset=index, before=before, after=after)
               for index, (before, after) in enumerate(zip(source, card)) if before != after]
    allowed = set(range(PAYLOAD_OFFSET + 8, PAYLOAD_OFFSET + 12)) | set(range(PAYLOAD_OFFSET + 0x18, PAYLOAD_OFFSET + 0x20)) | {PAYLOAD_OFFSET + 0x467}
    require(changes and all(row['file_offset'] in allowed for row in changes), 'Unexpected fixture byte changes.')
    sha = lambda data: hashlib.sha256(data).hexdigest()
    return bytes(card), dict(schema_version=1, constructed_external_history_card=True, naturally_earned_history_claimed=False,
        source_card_sha256=sha(source), prepared_card_sha256=sha(card), source_payload_sha256=sha(payload),
        prepared_payload_sha256=sha(card[PAYLOAD_OFFSET:PAYLOAD_OFFSET + 1792]), prepared_day_of_year=4, display_day=5,
        required_recent_history_cells=list(CELLS), consumed_flag=0, changed_byte_allowlist=changes,
        card_directory_icons_title_and_other_bytes_preserved=True, title_retains_original_Day_002_label=True,
        MainRAM_or_instruction_writes=False, source_card_modified=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args(argv)
    require(args.source.is_file() and args.source.stat().st_size == 131072, 'Require a raw 128 KiB source card.')
    paths = [path.resolve() for path in (args.source, args.output, args.manifest)]
    require(len(set(paths)) == 3 and not args.output.exists() and not args.manifest.exists(), 'Output paths must be separate and fresh.')
    card, metadata = construct_card(args.source.read_bytes())
    with args.output.open('xb') as stream:
        stream.write(card)
    require(hashlib.sha256(args.output.read_bytes()).hexdigest() == metadata['prepared_card_sha256'], 'Fixture readback differs.')
    require(hashlib.sha256(args.source.read_bytes()).hexdigest() == metadata['source_card_sha256'], 'Source card changed.')
    with args.manifest.open('x', encoding='utf-8') as stream:
        json.dump(metadata, stream, indent=2)
        stream.write('\n')
    print(json.dumps(metadata))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
