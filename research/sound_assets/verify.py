"""Run bounded original sound metadata checks with owned assets and RAM.

Exit 1 preserves original sequence initializer exceptions as review results.
No captured RAM, game file, emulator, SPU register or live player is changed.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.sound_assets import native_profile as native
from tools.inventory_sound import collect, sha


def campaign(layout, elf, ram):
    corpus = collect(layout)
    native.require(not corpus['unresolved'], 'Resolve structural sound inputs before native calls.')
    rows, ranges = native.qualify(elf)
    banks = {row['path']: (Path(corpus['inputs'][row['path']]['source']).read_bytes(),
                          Path(corpus['inputs'][row['body_path']]['source']).read_bytes())
             for row in corpus['records'] if row['format'] == 'VAB-v7'}
    native.require(banks, 'Supply at least one original bank.')
    pending = {name: native.pending_bank(rows, head, body) for name, (head, body) in banks.items()}
    ready = native.ready_queries(rows, ram, banks)
    binding = native.ready_bindings(ram, banks)[0]
    music = [item for item in native.ready_bindings(ram, banks) if item['path'].endswith('/STANDERD.VH')]
    if music:
        binding = music[0]
    sequences, controls = [], []
    for row in corpus['records']:
        if row['format'] != 'SEQ-v1':
            continue
        sequence = Path(corpus['inputs'][row['path']]['source']).read_bytes()
        observation = native.sequence_open(rows, ram, sequence, binding['bank_id'])
        sequences.append(dict(path=row['path'], initial_tempo_word=row['initial_tempo_word'], **observation))
        if row['zero_initial_tempo_word']:
            changed = bytearray(sequence)
            changed[10:13] = (500000).to_bytes(3, 'big')
            control = native.sequence_open(rows, ram, bytes(changed), binding['bank_id'])
            controls.append(dict(path=row['path'], changed_only_private_tempo_bytes=True,
                                 original_payload_preserved=True, **control))
    faults = native.fault_controls(rows, ram, banks)
    for row in corpus['inputs'].values():
        path = Path(row['source'])
        native.require(path.stat().st_size == row['bytes'] and sha(path.read_bytes()) == row['sha256'],
                       'Original sound payload changed during native verification.')
    reviewed = [row for row in sequences if not row['returned'] or row.get('result') == 0xffffffff]
    return dict(schema_version=1, status='native_sound_metadata_review_required' if reviewed else 'bounded_native_sound_metadata_checked',
                recorded_utc=datetime.now(timezone.utc).isoformat(), file_inventory=corpus['totals'],
                original_payload_hashes={key: row['sha256'] for key, row in corpus['inputs'].items()},
                qualified_ranges=ranges, pending_header_loads=pending, ready_metadata=ready,
                sequence_initializations=sequences, sequence_review=reviewed,
                private_tempo_controls=controls, executed_instruction_faults=faults,
                SDK_output_stubs=0, new_C_bytes=0, whole_feature_groups_accepted=0,
                SPU_waveform_transfer_executed=False, DMA_completion_verified=False,
                audible_playback_verified=False, natural_sequence_reachability_verified=False,
                BIOS_exception_handling_verified=False, original_game_modified=False,
                source_RAM_sha256=sha(ram), source_RAM_provenance_verified_by_this_tool=False,
                producer_sha256=sha(Path(__file__).read_bytes()),
                helper_sha256=sha((ROOT / 'research/sound_assets/native_profile.py').read_bytes()),
                inventory_tool_sha256=sha((ROOT / 'tools/inventory_sound.py').read_bytes()),
                model_API_calls=0,
                limits=['RAM origin, capture inputs and original-disc provenance need separate verification.',
                        'Header-open allocation and SDK metadata access do not complete waveform transfer or audible playback.',
                        'Original sequence initializer exceptions remain failures/review items; natural selection and BIOS handling are not inferred.',
                        'Source bytes are preserved; private tempo controls do not repair or replace the original sequence.',
                        'Encoded events, sample/program totals and native method calls are not feature counts.'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', type=Path, required=True)
    parser.add_argument('--elf', type=Path, required=True)
    parser.add_argument('--ram', type=Path, required=True)
    parser.add_argument('--ram-sha256', required=True)
    parser.add_argument('--ram-member')
    parser.add_argument('--archive-sha256')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        native.require(not args.output.exists(), 'Refusing to replace an existing report.')
        native.require(args.ram_member is not None or args.archive_sha256 is None,
                       'An archive hash requires an exact member.')
        ram = native.read_ram(args.ram, args.ram_sha256, args.ram_member, args.archive_sha256)
        result = campaign(args.layout, args.elf, ram)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
        print(json.dumps(dict(status=result['status'], header_loads=len(result['pending_header_loads']),
                              ready_RAM_comparisons=result['ready_metadata']['complete_RAM_comparisons'],
                              sequence_initializations=len(result['sequence_initializations']),
                              sequence_review=len(result['sequence_review']))))
        return 1 if result['sequence_review'] else 0
    except (OSError, ValueError, struct.error, tarfile.TarError) as error:
        print(json.dumps(dict(status='invalid_native_sound_inputs', error=str(error))), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
