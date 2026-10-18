"""Owned fixtures exercise provenance, complete output and entry-trace failures."""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import zlib

from tools import compare_npc_history as comparison
from tools.build_npc_observer import VARIABLES, parse_make_variables, build, UPSTREAM, MEDNAFEN, SOURCE_SHA256
from tools.record_npc_history import DEFAULT_PROGRAM, HOST_SOURCES, STOCK_RUNTIME, expand_program, record, validate_program
from tools.runtime_inputs import record_file

ROOT = Path(__file__).resolve().parents[1]
digest = lambda data: hashlib.sha256(data).hexdigest()


def png(rgb, width=2, height=1, note=None):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)
    result = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
    if note is not None:
        result += chunk(b'tEXt', b'Note\0' + note)
    return result + chunk(b'IDAT', zlib.compress(b'\0' + rgb)) + chunk(b'IEND', b'')


def write_json(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


def write_rows(path, fields, rows):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter='\t', lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


def fixture_program():
    executable = bytearray(0x1000)
    executable[:8] = b'PS-X EXE'
    struct.pack_into('<I', executable, 0x18, 0x80010000)
    struct.pack_into('<I', executable, 0x800, 0x27BDFFE0)
    struct.pack_into('<I', executable, 0x810, (2 << 21) | (31 << 11) | 9)  # owned JALR
    executable = bytes(executable)
    return dict(schema_version=1, frames=3, executable_sha256=digest(executable), disc_track_sha256='a' * 64,
        controller=dict(buttons=['Fire'], axes={}, column_order=['Fire']),
        segments=[dict(until=1, phase='press', pressed=['Fire']), dict(until=3, phase='release', pressed=[])],
        checkpoint_frames=[0, 3], RAM_sample_interval=1,
        trace=dict(watched_pc='0x80010000', arm_frame=0, function_bytes=4,
                   function_sha256=digest(executable[0x800:0x804]), context_tick_offset=160,
                   expected_entries=2, expected_first_frame=1, expected_last_frame=3, entity_id=42)), executable


def fixture_run(folder, program, executable, context_state=None):
    folder.mkdir()
    for name in ('host/dll', 'sources', 'observations'):
        (folder / name).mkdir(parents=True)
    (folder / 'host/gamedb').mkdir()
    source_paths = [*HOST_SOURCES, ROOT / 'research/runtime_state/npc_entry_observer.h',
                    *(ROOT / 'tools' / name for name in ('record_npc_history.py', 'build_npc_observer.py',
                                                        'replay_cold_start_headless.py', 'runtime_inputs.py'))]
    originals, snapshots, copied = [], [], {}
    for index, path in enumerate(source_paths):
        target = folder / 'sources' / (str(index) + '-' + path.name)
        target.write_bytes(path.read_bytes())
        original = record_file(path)
        actual = record_file(target)
        originals.append(original)
        snapshots.append(dict(original=original, file=str(target.relative_to(folder)).replace('\\', '/'),
                              bytes=actual['bytes'], sha256=actual['sha256']))
        if path in HOST_SOURCES:
            (folder / 'host' / path.name).write_bytes(path.read_bytes())
            copied[path.name] = record_file(folder / 'host' / path.name)
    compiler = folder / 'sources/csc.dll'
    compiler.write_bytes(b'owned synthetic compiler identity')
    originals.append(record_file(compiler))
    snapshots.append(dict(original=originals[-1], file='sources/csc.dll',
                          bytes=compiler.stat().st_size, sha256=digest(compiler.read_bytes())))
    for name in STOCK_RUNTIME:
        (folder / 'host' / name).write_bytes(name.encode())
    (folder / 'host/dll/shock.wbx').write_bytes(b'owned observer core')
    (folder / 'host/dll/shock.wbx.zst').write_bytes(b'owned observer compressed-core identity')
    runtime = {str(path.relative_to(folder / 'host')).replace('\\', '/'): record_file(path)
               for path in (folder / 'host').rglob('*') if path.is_file() and path.parent.name == 'dll'}
    profile = dict(status='built_separate_NPC_observer_core', upstream_commit=UPSTREAM, mednafen_commit=MEDNAFEN,
        existing_CPU_source_modified=False, input_files_preserved=True, original_adapter_sha256=SOURCE_SHA256['shock.cpp'],
        observer_header_sha256=digest((ROOT / 'research/runtime_state/npc_entry_observer.h').read_bytes()),
        producer_sha256=digest((ROOT / 'tools/build_npc_observer.py').read_bytes()),
        core=runtime['dll/shock.wbx'], compressed_core=runtime['dll/shock.wbx.zst'])
    for name, data in (('RecordNpcHistory.exe', b'owned host identity'), ('RecordNpcHistory.exe.config', b'owned configuration')):
        (folder / 'host' / name).write_bytes(data)
    write_json(folder / 'program.json', program)
    (folder / 'submitted.tsv').write_bytes(expand_program(program))
    settings = dict(frames=3, checkpoint_frames=[0, 3], RAM_sample_interval=1,
                    trace_enabled=True, watched_pc=0x80010000, arm_frame=0)
    write_json(folder / 'settings.json', settings)
    source_manifest = dict(schema_version=2, selected_core='Nymashock', scenario='boot', start_kind='cold_boot', start_state=None,
        disc=dict(tracks=[dict(bytes=32, sha256=program['disc_track_sha256'])], layout=['TRACK 01 MODE2/2352']),
        bios={region: dict(bytes=524288, sha256=digest(region.encode())) for region in ('J', 'U', 'E')})
    inputs = dict(schema_version=1, runtime_kind='npc_observer', source_manifest=source_manifest,
        game_RAM_injected=False, restored_state=False, emulator_UI_controlled=False, program=program,
        program_file=record_file(folder / 'program.json'), settings=settings, settings_file=record_file(folder / 'settings.json'),
        submitted=record_file(folder / 'submitted.tsv'), source_pins=originals, source_snapshots=snapshots,
        copied_host_sources=copied, host_binary=record_file(folder / 'host/RecordNpcHistory.exe'),
        host_configuration=record_file(folder / 'host/RecordNpcHistory.exe.config'), actual_runtime_files=runtime,
        observer_profile=profile)
    write_json(folder / 'run-inputs.json', inputs)
    write_json(folder / 'exit.json', dict(exit_code=0))
    write_json(folder / 'result.json', dict(status='recorded_pinned_NPC_history', input_files_preserved=True))
    observed, memory, checkpoints = [], [], []
    gpu = bytes([73]) * 0x100000
    rgb = bytes((18, 52, 86, 171, 205, 239))
    for frame, tick in enumerate((0, 1, 1, 2)):
        raw = bytearray(0x200000)
        raw[0x10000:0x10004] = executable[0x800:0x804]
        entity_id = program['trace']['entity_id']
        state = entity_id + 1 if context_state is None else context_state
        for offset, value in ((0, 0x80089AD4), (0x98, entity_id), (0x9C, state), (0xA0, tick), (0xA4, 0x80011000), (0xA8, 0x80010000)):
            struct.pack_into('<I', raw, 0x11000 + offset, value)
        observed.append(dict(relative_frame=frame, core_frame=frame + 1, phase=('initial_neutral', 'press', 'release', 'release')[frame],
                             gpu_sha256=digest(gpu), sample_frames=1, total_sample_frames=frame + 1))
        memory.append(dict(relative_frame=frame, core_frame=frame + 1, RAM_sha256=digest(raw)))
        if frame in (0, 3):
            for kind, data in (('mainram', raw), ('gpu', gpu), ('rgb', rgb)):
                (folder / f'observations/{kind}-{frame}.bin').write_bytes(data)
            (folder / f'observations/frame-{frame}.png').write_bytes(png(rgb))
            checkpoints.append(dict(relative_frame=frame, core_frame=frame + 1, RAM_sha256=digest(raw), GPU_sha256=digest(gpu),
                                    image=dict(width=2, height=1, RGB_sha256=digest(rgb))))
    write_rows(folder / 'observations/frames.tsv', comparison.FRAME_FIELDS, observed)
    write_rows(folder / 'observations/ram-samples.tsv', comparison.RAM_FIELDS, memory)
    (folder / 'observations/audio.pcm').write_bytes(bytes(range(16)))
    entries = [dict(relative_frame=frame, pc='80010000', entity='80011000', ra='80010018', sp='8001FF00',
                    timestamp=10, instruction='27BDFFE0', context_tick=tick) for frame, tick in ((1, 0), (3, 1))]
    write_rows(folder / 'observations/npc-instructions.tsv', comparison.ENTRY_FIELDS, entries)
    write_json(folder / 'observations/npc-trace-summary.json', dict(original_instruction_entries=2, watched_pc='80010000',
        hook_enabled_relative_frame=0, hook_enabled=True, first_observed_entry_frame=1, last_observed_entry_frame=3))
    write_json(folder / 'observations/report.json', dict(status='recorded_static_NPC_history', frames_advanced=4, submitted_frames=3,
        RAM_samples=4, checkpoints=checkpoints, all_PCM_sample_frames=4, instruction_entries=2,
        observer_enabled=True, observer_requested=True, restored_state=False, game_RAM_injected=False,
        emulator_UI_controlled=False, complete_state_parity_checked=False))
    return entries


class ProgramTests(unittest.TestCase):
    def test_published_route_expands_to_the_prior_recorded_controller_checksum(self):
        program = json.loads(DEFAULT_PROGRAM.read_bytes())
        self.assertEqual(digest(expand_program(program)), program['expanded_submitted_sha256'])
        self.assertEqual(len(program['segments']), 61)

    def test_prefix_has_exact_input_boundaries(self):
        program, _ = fixture_program()
        rows = list(csv.DictReader(io.StringIO(expand_program(program, 2).decode()), delimiter='\t'))
        self.assertEqual([(row['relative_frame'], row['core_frame'], row['Fire']) for row in rows], [('1', '1', 'true'), ('2', '2', 'false')])

    def test_unknown_controls_gaps_and_duplicate_checkpoints_are_rejected(self):
        program, _ = fixture_program()
        for mutate in (lambda p: p['segments'][0]['pressed'].append('Unknown'),
                       lambda p: p['segments'][-1].update(until=2),
                       lambda p: p['checkpoint_frames'].append(3),
                       lambda p: p['controller']['column_order'].append('Fire')):
            changed = copy.deepcopy(program); mutate(changed)
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate_program(changed)

    def test_a_changed_expanded_input_checksum_is_not_ignored(self):
        program, _ = fixture_program(); program['expanded_submitted_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'recorded program checksum'):
            expand_program(program)

    def test_existing_recording_is_rejected_before_original_inputs_load(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch('tools.record_npc_history.load_verified_manifest') as load:
            with self.assertRaisesRegex(ValueError, 'existing evidence'):
                record('missing-capture', folder)
            load.assert_not_called()


class BuilderAndRuntimeTests(unittest.TestCase):
    def test_empty_optional_make_flags_are_preserved(self):
        values = {name: ('value' if name not in ('LDFLAGS_RELEASE',) else '') for name in VARIABLES}
        text = '\n'.join(name + ' =' + (' ' + value if value else '') for name, value in values.items())
        self.assertEqual(parse_make_variables(text), values)

    def test_missing_and_repeated_make_variables_are_rejected(self):
        with self.assertRaises(ValueError): parse_make_variables('CC = compiler')
        with self.assertRaises(ValueError): parse_make_variables('CC = one\nCC = two')

    def test_existing_core_output_is_preserved_before_source_checkout_is_read(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch('tools.build_npc_observer.subprocess.check_output') as call:
            with self.assertRaisesRegex(ValueError, 'existing builds'):
                build('missing-source', folder)
            call.assert_not_called()

    def test_same_runtime_never_implicitly_accepts_the_observer(self):
        a = dict(runtime_kind='distributed', actual_runtime_files={'dll/shock.wbx.zst': dict(bytes=1, sha256='a' * 64)})
        b = dict(runtime_kind='npc_observer', actual_runtime_files={'dll/shock.wbx.zst': dict(bytes=1, sha256='b' * 64)})
        with self.assertRaisesRegex(ValueError, 'does not accept'):
            comparison.runtime_differences(a, b, 'same-runtime')
        self.assertEqual(len(comparison.runtime_differences(a, b, 'observer-output')), 1)

    def test_observer_output_mode_rejects_an_unrelated_binding_change(self):
        a = dict(runtime_kind='distributed', actual_runtime_files={'dll/shock.wbx.zst': dict(bytes=1, sha256='a' * 64)})
        b = dict(runtime_kind='npc_observer', actual_runtime_files={**a['actual_runtime_files'], 'dll/other.dll': dict(bytes=1, sha256='b' * 64)})
        with self.assertRaisesRegex(ValueError, 'only the declared PS1'):
            comparison.runtime_differences(a, b, 'observer-output')


class FrozenHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.program, self.executable = fixture_program()
        self.exe = self.root / 'owned.exe'; self.exe.write_bytes(self.executable)
        hashes = {name: digest(name.encode()) for name in STOCK_RUNTIME}
        self.addCleanup(mock.patch.stopall)
        mock.patch('tools.compare_npc_history.STOCK_RUNTIME', hashes).start()
        self.left, self.right = self.root / 'original', self.root / 'rebuilt'
        self.entries = fixture_run(self.left, self.program, self.executable)
        fixture_run(self.right, self.program, self.executable)

    def compare(self):
        return comparison.compare(self.left, self.right, self.exe)

    def test_complete_owned_history_passes_with_original_clock_checks(self):
        result = self.compare()
        self.assertEqual(result['status'], 'passed_NPC_history_output_comparison')
        self.assertEqual(result['original_instruction_entries_per_run'], [2, 2])
        self.assertEqual(result['original_clock_checkpoint_checks'], [1, 1])
        self.assertFalse(result['complete_state_parity_checked'])

    def test_clock_guard_observes_the_native_context_before_accepting_it(self):
        calls = []

        def guard(raw, address, entity_id, frame):
            self.assertIsInstance(raw, bytes)
            calls.append((address, entity_id, frame))
            return True

        run = comparison.inspect_run(self.left, self.executable, context_clock_guard=guard)
        self.assertEqual(run['clock_checks'], 1)
        self.assertEqual(calls, [(0x80011000, 42, 3)])

    def test_clock_guard_cannot_accept_a_history_without_any_corroborating_context(self):
        with self.assertRaisesRegex(ValueError, 'No complete checkpoint corroborates'):
            comparison.inspect_run(self.left, self.executable, context_clock_guard=lambda *args: False)

    def test_clock_guard_rejects_non_boolean_results(self):
        with self.assertRaisesRegex(ValueError, 'must return a Boolean'):
            comparison.inspect_run(self.left, self.executable, context_clock_guard=lambda *args: 'yes')

    def test_another_entity_id_has_its_own_native_context_state(self):
        program = copy.deepcopy(self.program)
        program['trace']['entity_id'] = 7
        folder = self.root / 'another-entity'
        fixture_run(folder, program, self.executable)
        self.assertEqual(comparison.inspect_run(folder, self.executable)['clock_checks'], 1)

    def test_buddha_state_does_not_corroborate_another_entity_id(self):
        folder = self.root / 'wrong-state'
        fixture_run(folder, self.program, self.executable, context_state=21)
        with self.assertRaisesRegex(ValueError, 'No complete checkpoint corroborates'):
            comparison.inspect_run(folder, self.executable)

    def test_all_distinct_wrong_trace_controls_are_rejected(self):
        for name, change in (
            ('PC', lambda r: r[0].update(pc='80010004')),
            ('opcode', lambda r: r[0].update(instruction='00000000')),
            ('entity', lambda r: r[1].update(entity='80011004')),
            ('missing', lambda r: r.pop()),
            ('duplicate', lambda r: r.append(dict(r[-1]))),
            ('tick', lambda r: r[0].update(context_tick=1)),
            ('first-frame', lambda r: r[0].update(relative_frame=0)),
        ):
            rows = copy.deepcopy(self.entries); change(rows)
            with self.subTest(control=name), self.assertRaises(ValueError):
                comparison.validate_entries(rows, self.program, 3, self.executable)

    def test_a_same_length_PCM_fault_is_an_output_difference(self):
        path = self.right / 'observations/audio.pcm'
        path.write_bytes(b'\xff' + path.read_bytes()[1:])
        result = self.compare()
        self.assertFalse(result['complete_PCM_equal'])
        self.assertEqual(result['status'], 'recorded_NPC_history_output_differences')

    def test_truncated_and_appended_PCM_are_rejected(self):
        path = self.right / 'observations/audio.pcm'; before = path.read_bytes()
        for raw in (before[:-1], before + b'\0'):
            path.write_bytes(raw)
            with self.subTest(bytes=len(raw)), self.assertRaisesRegex(ValueError, 'complete native PCM'):
                self.compare()

    def test_a_changed_retained_source_is_rejected(self):
        source = next((self.right / 'sources').glob('*-NpcInstructionTrace.cs'))
        source.write_bytes(source.read_bytes() + b'\nchanged')
        with self.assertRaisesRegex(ValueError, 'retained file differs'):
            self.compare()

    def test_corrupted_checkpoint_bytes_cannot_hide_behind_native_metadata(self):
        path = self.right / 'observations/mainram-0.bin'
        path.write_bytes(b'\x01' + path.read_bytes()[1:])
        with self.assertRaisesRegex(ValueError, 'checkpoint RAM disagrees'):
            self.compare()

    def test_a_valid_PNG_container_difference_preserves_the_RGB_result(self):
        path = self.right / 'observations/frame-0.png'
        path.write_bytes(png((self.right / 'observations/rgb-0.bin').read_bytes(), note=b'owned metadata'))
        result = self.compare()
        self.assertEqual(result['status'], 'passed_NPC_history_output_comparison')
        self.assertFalse(result['checkpoint_comparisons'][0]['PNG_container_bytes_equal'])

    def test_a_broken_PNG_chunk_is_rejected(self):
        path = self.right / 'observations/frame-0.png'; raw = bytearray(path.read_bytes()); raw[-5] ^= 1; path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'PNG chunk checksum'):
            self.compare()

    def test_a_loaded_runtime_binding_is_checked_against_the_qualified_set(self):
        inputs_path = self.right / 'run-inputs.json'; inputs = json.loads(inputs_path.read_bytes())
        name = next(name for name in STOCK_RUNTIME if name not in comparison.CORE_FILES)
        path = self.right / 'host' / name; path.write_bytes(b'changed binding')
        inputs['actual_runtime_files'][name] = record_file(path); write_json(inputs_path, inputs)
        with self.assertRaisesRegex(ValueError, 'runtime binding differs'):
            self.compare()

    def test_frozen_paths_cannot_escape_the_recording(self):
        with self.assertRaisesRegex(ValueError, 'inside their recording'):
            comparison.owned_file(self.left, '../owned.exe')


if __name__ == '__main__':
    unittest.main()
