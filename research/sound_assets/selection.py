"""Check original stage-music selection without stubbing RNG or playing audio."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.sound_assets import native_profile as native
from tools.inventory_sound import collect, sha

ROOTS = ('get_stage_music_path', 'get_stage_music_paths', 'get_seeded_random',
         'set_audio_path_override', 'srand')


def path_at(machine, address):
    at = address & native.n.MASK
    native.require(at + 28 <= 2**21, 'Music path leaves original RAM.')
    raw = bytes(machine.cpu.mem_read(at, 28))
    end = raw.find(b'\0')
    native.require(0 < end < 28, 'Original path lacks its bounded terminator.')
    return raw[:end].decode('ascii')


def check_choice(machine, stage, residue, override, audio_paths):
    index = override - 1 if override else residue
    if stage == 9 and index == 2:
        index = 3
    base = machine.call('get_stage_music_paths', stage)
    result = machine.call('get_stage_music_path', stage, 0)
    path = path_at(machine, result)
    expected = f'STG{stage:02d}\\BG{chr(65 + index)}.SEQ'
    native.require(result == base + index * 28 and path == expected,
                   'Original music selection differs: ' + repr((stage, residue, override, path, expected)))
    native.require('/CDI/' + path.replace('\\', '/') in audio_paths,
                   'Selected original path lacks a structurally inspected disc payload.')
    return dict(stage=stage, random_residue=residue, forced_track=override,
                selected_track_index=index, selected_path=path)


def campaign(layout, elf):
    corpus = collect(layout)
    native.require(not corpus['unresolved'], 'Resolve sound payload structures first.')
    audio_paths = set(corpus['inputs'])
    rows, qualification = native.qualify(elf, ROOTS)
    machine = native.Machine(rows)
    seeds = {}
    for seed in range(1, 257):
        machine.call('srand', seed)
        result = machine.call('get_seeded_random', 0, 0)
        residue = result % 5
        seeds.setdefault(residue, dict(seed=seed, original_rand_result=result,
                                       RNG_after=bytes(machine.cpu.mem_read(native.n.RNG, 4)).hex()))
        if len(seeds) == 5:
            break
    native.require(len(seeds) == 5, 'Original RNG did not cover all five reviewed residue classes.')
    cases = []
    for stage in range(14):
        for override in range(6):
            for residue, sample in sorted(seeds.items()):
                machine.call('set_audio_path_override', 0, override)
                machine.call('srand', sample['seed'])
                row = check_choice(machine, stage, residue, override, audio_paths)
                native.require(bytes(machine.cpu.mem_read(native.n.RNG, 4)).hex() == sample['RNG_after'],
                               'Selector did not preserve the original single-rand state advance.')
                cases.append(dict(**row, seed=sample['seed'], single_rand_state_equal=True))
    # Stage 9 changes the stored override, affecting the next stage too.
    machine.call('set_audio_path_override', 0, 3)
    machine.call('srand', seeds[2]['seed'])
    first = check_choice(machine, 9, 2, 3, audio_paths)
    machine.call('set_audio_path_override', -1, -1)
    second = check_choice(machine, 8, None, 4, audio_paths)
    faults = []
    for name, pc, before, after, override in (
            ('random_track_C_remap_removed', 0x80048FD4, 0x34100003, 0x34100002, 0),
            ('stored_override_remap_removed', 0x80048FE8, 0xAF820160, 0, 3)):
        faulted = native.Machine(rows, fault=(pc, before, after))
        faulted.call('set_audio_path_override', 0, override)
        faulted.call('srand', seeds[2]['seed'])
        detected = False
        try:
            check_choice(faulted, 9, 2, override, audio_paths)
        except ValueError as error:
            native.require(str(error).startswith('Original music selection differs:'),
                           'Selection fault stopped for an unrelated reason: ' + str(error))
            detected = True
        native.require(detected and (pc & native.n.MASK) in faulted.seen,
                       'Selection fault instruction was not executed and rejected.')
        faults.append(dict(name=name, PC=hex(pc), original_word=hex(before), changed_word=hex(after),
                           instruction_executed=True, wrong_original_path_detected=True))
    for value in corpus['inputs'].values():
        p = Path(value['source'])
        native.require(p.stat().st_size == value['bytes'] and sha(p.read_bytes()) == value['sha256'],
                       'Sound payload changed during original selection checks.')
    return dict(schema_version=1, status='bounded_original_music_selection_checked',
                recorded_utc=datetime.now(timezone.utc).isoformat(), qualified_ranges=qualification,
                seeds_by_residue=seeds, matrix_cases=cases, matrix_case_count=len(cases),
                stage_9_selected_C_cases=sum(r['stage'] == 9 and r['selected_track_index'] == 2 for r in cases),
                stored_override_history=[first, second], negative_override_preserves_stored_choice=True,
                entered_original_functions=dict(machine.entries), executed_instruction_faults=faults,
                original_output_stubs=0, original_RNG_executed=True,
                producer_sha256=sha(Path(__file__).read_bytes()),
                helper_sha256=sha((ROOT / 'research/sound_assets/native_profile.py').read_bytes()),
                inventory_tool_sha256=corpus['producer_sha256'],
                canonical_executable_sha256=native.CANONICAL_SHA256,
                source_payload_hashes={k: v['sha256'] for k, v in corpus['inputs'].items()},
                new_C_bytes=0, whole_feature_groups_accepted=0, model_API_calls=0,
                original_game_modified=False, audio_playback_verified=False,
                natural_gameplay_route_verified=False,
                scope='Original selector return paths, one-call RNG advance and stored-override history '
                      'in bounded constructed calls; alternate direct SEQ routes and audible playback remain open.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', type=Path, required=True)
    parser.add_argument('--elf', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        native.require(not args.output.exists(), 'Refusing to replace an existing report.')
        result = campaign(args.layout, args.elf)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
        print(json.dumps({k: result[k] for k in ('status', 'matrix_case_count', 'stage_9_selected_C_cases')}))
        return 0
    except (OSError, ValueError, struct.error) as error:
        print(json.dumps(dict(status='invalid_original_music_selection_inputs', error=str(error))), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
