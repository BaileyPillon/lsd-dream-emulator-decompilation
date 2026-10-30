"""Audit model polygon vertex references directly from a verified raw disc.

No asset is extracted or modified. This static audit does not certify rendering,
normal/texture semantics, collision timing or a whole game feature.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.disc_files import Mode2Disc, require
from tools.psx_image import EXECUTABLE_NAME, ORIGINAL_SHA1
from tools.tmd_packets import summarize


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else _stream_sha(stream)


def _stream_sha(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024**2), b''):
        digest.update(block)
    return digest.hexdigest()


def inspect(disc_path, expected_sha256, edition_label='unspecified'):
    require(len(expected_sha256) == 64 and all(c in '0123456789abcdefABCDEF' for c in expected_sha256),
            'Supply the complete expected raw-disc SHA-256.')
    with Mode2Disc(disc_path) as disc:
        before = disc.path.stat()
        require(file_sha(disc.path) == expected_sha256.lower(), 'Raw-disc SHA-256 differs.')
        files = disc.files()
        executable = disc.read_file(files['/' + EXECUTABLE_NAME])
        require(hashlib.sha1(executable).hexdigest() == ORIGINAL_SHA1,
                'Disc executable differs from the canonical Japanese executable.')
        selected = {name: record for name, record in files.items()
                    if PurePosixPath(name).suffix in ('.LBD', '.MOM', '.TMD')}
        require(selected, 'No model files were found.')
        rows, unresolved, totals, modes, flags = [], [], Counter(), Counter(), Counter()
        for name, record in sorted(selected.items()):
            raw = disc.read_file(record)
            row = dict(path=name, ISO_LBA=record.lba, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            try:
                parsed = summarize(raw, PurePosixPath(name).suffix)
                row['models'] = parsed['models']
                for model in parsed['models']:
                    totals.update(model['counts'])
                    totals['TMD_tables'] += 1
                    if model['kind'] == 'MML-MOM':
                        totals['embedded_MOM_occurrences'] += 1
                        totals['embedded_MOM_references'] += model['references']
                    modes.update(model['modes'])
                    flags.update(model['flags'])
            except (ValueError, KeyError) as error:
                unresolved.append(dict(path=name, error=str(error)))
                row['unresolved'] = str(error)
            rows.append(row)
        after = disc.path.stat()
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                and file_sha(disc.path) == expected_sha256.lower(), 'Raw disc changed during inspection.')
        dependencies = [Path(__file__), ROOT/'tools/disc_files.py', ROOT/'tools/tmd_packets.py',
                        ROOT/'tools/inventory_animations.py', ROOT/'tools/psx_image.py']
        return dict(schema_version=1, status='model_vertex_references_verified' if not unresolved else 'model_packets_need_review',
            generated_at=datetime.now(timezone.utc).isoformat(), edition_label=edition_label,
            edition_label_is_supplied_not_detected=True, raw_disc_bytes=disc.size,
            raw_disc_sha256=expected_sha256.lower(), canonical_executable_sha1=ORIGINAL_SHA1,
            ISO_files=len(files), model_files=len(rows), file_extensions=dict(Counter(PurePosixPath(row['path']).suffix for row in rows)),
            counts=dict(totals), modes=dict(sorted(modes.items())), flags=dict(sorted(flags.items())),
            rows=rows, unresolved=unresolved, checked_Form1_sector_reads=disc.sectors_read,
            model_occurrence_count_note='Descriptor/packet visits count actual file occurrences, including repeated model content; aliased MML offsets are walked once and their reference count is retained.',
            no_payload_extracted_to_disk=True, source_bytes_modified=False,
            whole_feature_groups_accepted=0, rendered_output_verified=False,
            normal_index_semantics_verified=False, texture_palette_and_lighting_verified=False,
            source_dependencies={str(path.relative_to(ROOT)): file_sha(path) for path in dependencies},
            scope='Bounded raw Mode2/Form1 file bytes and supported triangle/quad vertex references; native decoder agreement is a separate test.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disc', type=Path, required=True)
    parser.add_argument('--expected-disc-sha256', required=True)
    parser.add_argument('--edition-label', default='unspecified')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        require(not args.output.exists(), 'Refusing to replace an existing report.')
        result = inspect(args.disc, args.expected_disc_sha256, args.edition_label)
        encoded = json.dumps(result, indent=2) + '\n'
        require(len(encoded.encode('utf-8')) <= 4*1024**2, 'Inventory report exceeds its 4 MiB output bound.')
        with args.output.open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(encoded)
        print(json.dumps({key: result[key] for key in ('status', 'model_files', 'counts', 'modes', 'unresolved')}))
        return 0 if not result['unresolved'] else 1
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps(dict(status='invalid_model_inputs', error=str(error))), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
