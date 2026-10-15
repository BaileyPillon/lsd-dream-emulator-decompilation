"""Inspect generation objects in local 2 MiB MainRAM captures; never execute or modify them."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
REFERENCE_SHA1 = '76322eeade5ebb22dca57fdeac7d68c30f06308d'
RAM_BYTES = 0x200000
TABLE = 0x800876FC
TYPE, COUNT, LIST = 0x8008AC80, 0x8008AC88, 0x8008E0C8
REGIONS = (
    ('dream_generation_update_structure_entities', 0x80054C74, 136),
    ('func_800564F4', 0x800564F4, 44),
    ('func_80056640', 0x80056640, 216),
    ('func_80056794', 0x80056794, 64),
    ('generation_structure_vtable', TABLE, 0xF0),
)


def offset(address, size):
    if not (0 <= address < RAM_BYTES or 0x80000000 <= address < 0x80200000
            or 0xA0000000 <= address < 0xA0200000):
        raise ValueError('Address is outside the supported MainRAM windows.')
    start = address & 0x1FFFFF
    if address % 4 or size < 0 or start + size > RAM_BYTES:
        raise ValueError('Unaligned or out-of-bounds MainRAM read.')
    return start


def inspect(ram, reference):
    if len(reference) != 505856 or hashlib.sha1(reference).hexdigest() != REFERENCE_SHA1:
        raise ValueError('Reference is not the supported canonical executable.')
    if len(ram) != RAM_BYTES:
        raise ValueError('Expected a complete 2 MiB MainRAM capture.')
    load = struct.unpack_from('<I', reference, 0x18)[0]
    regions = []
    for name, address, size in REGIONS:
        start = 0x800 + address - load
        expected = reference[start:start + size]
        position = offset(address, size)
        if len(expected) != size or ram[position:position + size] != expected:
            raise ValueError('Captured original code or virtual table differs: ' + name)
        regions.append({'name': name, 'address': hex(address), 'bytes': size,
                        'sha256': hashlib.sha256(expected).hexdigest()})

    def word(address, signed=False):
        return struct.unpack_from('<i' if signed else '<I', ram, offset(address, 4))[0]

    kind, count = word(TYPE, True), word(COUNT, True)
    active = kind >= 0 and count > 0
    objects = []
    if active:
        if count > 17:
            raise ValueError('Active structure count exceeds the identified 17-slot boundary.')
        for index in range(count):
            address = word(LIST + 4 * index)
            if address == 0:
                raise ValueError('Active structure list contains a null receiver.')
            offset(address, 0x98)
            if word(address) != TABLE:
                raise ValueError('Active receiver does not use the identified generation structure class.')
            objects.append({'index': index, 'address': hex(address), 'vtable': hex(TABLE),
                            'tick': word(address + 0x24), 'mode': word(address + 0x54, True),
                            'update': hex(word(TABLE + 0xEC)),
                            'set_position': hex(word(TABLE + 0xB8))})
    return {'mainram_bytes': len(ram), 'mainram_sha256': hashlib.sha256(ram).hexdigest(),
            'verified_regions': regions, 'generation_type': kind, 'structure_count': count,
            'dispatch_enabled': active, 'active_objects': objects}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, default=ROOT / 'rom/SLPS_015.56')
    parser.add_argument('--ram', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True,
                        help='New JSON file; existing evidence is never overwritten.')
    args = parser.parse_args()
    try:
        reference = args.reference.read_bytes()
        report = {'schema_version': 1, 'reference_sha1': REFERENCE_SHA1,
                  'scope': 'RAM field observations; no callback entry trace, construction proof, or whole-feature acceptance.',
                  'snapshots': [inspect(path.read_bytes(), reference) for path in args.ram]}
        with args.output.open('x', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2)
            handle.write('\n')
        print(json.dumps({'status': 'observed_identified_generation_objects',
                          'snapshots': len(report['snapshots']),
                          'whole_feature_groups_accepted': 0}))
        return 0
    except (OSError, ValueError, struct.error) as error:
        print('Generation observation failed: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
