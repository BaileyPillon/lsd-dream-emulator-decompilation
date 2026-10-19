"""Synthetic replay regressions; no game, BIOS or native GTE core is used."""
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import replay_collision_calls as replay
from tools.collision_calls import CPU_FIELDS, FIELDS, RAM_BYTES


def row_fixture():
    row = dict.fromkeys(FIELDS, 0)
    for i in range(1, 32):
        row['entry_cpu_gpr_' + str(i)] = 0x91000000 + i
    row.update(entry_pc=0x80010000, return_pc=0x80018000, entry_delay_fetch=0,
               entry_cpu_gpr_4=0x100, entry_cpu_gpr_29=0x801FF000, entry_cpu_gpr_31=0x80018000,
               entry_cpu_lo=0x11223344, entry_cpu_hi=0x55667788, entry_cpu_sr=0x40000401,
               entry_gte_data_31=32, sequence_low=14)
    for field in CPU_FIELDS:
        row['cpu_' + field] = row['entry_cpu_' + field]
    row['cpu_gpr_2'] = 23
    row['cpu_gpr_3'] = 0x8001001C
    row['gte_data_30'], row['gte_data_31'] = 0x100, 23
    return row


class ReplayInputTests(unittest.TestCase):
    def test_contradictory_derived_GTE_view_is_rejected(self):
        row = row_fixture()
        row['entry_gte_data_28'] = 1  # IR1..3 are zero.
        adapter = replay.ArchitecturalCop2(object(), backend=SimpleNamespace())
        with self.assertRaisesRegex(ValueError, 'GTE views'):
            adapter.seed(row)

    def test_pending_CPU_loads_require_pipeline_reconstruction(self):
        for word in (0x8FA20010, 0x87A20010, 0x9BA20010, 0x4802F800, 0x40026000):
            with self.subTest(word=hex(word)):
                self.assertTrue(replay.pending_caller_load(word))
        for word in (0, 0x02403821, 0x4884F000, 0x0C004010):
            self.assertFalse(replay.pending_caller_load(word))

    def test_RAM_difference_keeps_cross_word_and_tail_bytes(self):
        expected = bytes(11)
        actual = bytearray(expected)
        actual[3:5] = b'\x11\x22'
        actual[10] = 0x33
        result = replay.ram_difference(bytes(actual), expected)
        self.assertEqual(result['different_bytes'], 3)
        self.assertEqual([(r['start'], r['end']) for r in result['first_ranges']], [(3, 5), (10, 11)])
        with self.assertRaisesRegex(ValueError, 'extents'):
            replay.ram_difference(b'one', b'two!')

    def test_incomplete_state_cannot_receive_a_positive_comparison(self):
        with self.assertRaisesRegex(ValueError, '35 exposed CPU'):
            replay.compare_state(row_fixture(), bytes(RAM_BYTES), bytes(RAM_BYTES), {}, [0]*32, [0]*32, 14)

    def test_collection_rejects_traversal_duplicates_and_absolute_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'phase').mkdir()
            manifest = root/'collection.json'
            data = dict(schema_version=1, type='ordinal_collision_recording_collection',
                        function='func_8001DDF4', reference=['phase'])
            manifest.write_text(json.dumps(data), encoding='utf-8')
            self.assertEqual(replay.collection_recordings(manifest), [(root/'phase').resolve()])
            for names in (['../outside'], ['..\\outside'], ['D:\\outside'], ['\\outside'], ['phase', 'phase'], [], [''], ['.']):
                with self.subTest(names=names):
                    data['reference'] = names
                    manifest.write_text(json.dumps(data), encoding='utf-8')
                    with self.assertRaises(ValueError):
                        replay.collection_recordings(manifest)

    def test_output_inside_retained_recording_is_rejected_before_loading_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            output = folder/'unexpected-output'
            with self.assertRaisesRegex(ValueError, 'outside retained recordings'):
                replay.run([folder], output, folder/'missing.exe', 'unused')
            self.assertFalse(output.exists())

    def test_global_limit_keeps_four_independent_recording_inspections(self):
        """Runner fixture only: source/core execution is replaced with test doubles."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root = root/'source-fixture'
            for name in ['tools/replay_collision_calls.py', 'tools/verify_collision.py', 'tools/verify_native_ai.py',
                         'tools/verify_render_gte.py', 'tools/collision_calls.py', 'tools/inspect_collision_calls.py',
                         'tools/inspect_hull_calls.py', 'tools/inspect_dispatch_history.py', 'tools/inspect_sdk_reads.py',
                         'tools/dispatch_returns.py', 'tools/psx_image.py', 'tools/nymashock_gte_bridge.cs',
                         'research/collision/trace_compiler_stack.py', 'rom/SLPS_015.56', 'build/SLPS015.56']:
                path = source_root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('synthetic runner fixture', encoding='utf-8')
            function = dict(function='synthetic', address='0x8001DDF4', bytes=4)
            (source_root/'docs').mkdir()
            (source_root/'docs/collision-function-ranges.json').write_text(json.dumps([function]), encoding='utf-8')
            bridge_file = root/'synthetic-bridge.exe'
            bridge_file.write_bytes(b'synthetic executable placeholder; never executed')
            row = dict.fromkeys(FIELDS, 0)
            row['sequence_low'] = 1
            recordings = []
            for i in range(4):
                folder = root/('recording-' + str(i))
                observation = folder/'observations'
                observation.mkdir(parents=True)
                (observation/'collision-calls.bin').write_bytes(struct.pack('<247I', *(row[field] for field in FIELDS)))
                (observation/'collision-call-ram.bin').write_bytes(bytes(RAM_BYTES*2))
                (observation/'collision-call-summary.json').write_text(json.dumps(dict(settings=dict(pc=0x8001DDF4))), encoding='utf-8')
                recordings.append(folder)

            class FakeBridge:
                def __init__(self, *args):
                    self.count, self.lz_count = 0, 0
                def close(self):
                    pass

            class FakeMachine:
                def __init__(self, *args, **kwargs):
                    self.instructions, self.entries, self.adapter = 1, {}, SimpleNamespace(counts={})
                def invoke(self):
                    return bytes(RAM_BYTES), dict.fromkeys(CPU_FIELDS[:-2], 0), [0]*32, [0]*32
                def close(self):
                    pass

            inspection = dict(collision_calls=dict(completed_samples=1, complete_RAM_payload_sha256='fixture'))
            output = root/'output'
            with patch.object(replay, 'ROOT', source_root), \
                 patch.object(replay.native, 'load_program', return_value=SimpleNamespace(target=lambda pc, length: bytes(length))), \
                 patch.object(replay, 'load_backend', return_value=SimpleNamespace(identity={'kind': 'synthetic runner fixture'})), \
                 patch.object(replay.collision, 'CollisionBridge', FakeBridge), \
                 patch.object(replay, 'NaturalMachine', FakeMachine), \
                 patch.object(replay.hull, 'inspect_call_recording', return_value=(inspection, {})):
                report = replay.run(recordings, output, bridge_file, 'unused', lab_root=root, max_calls=1)
                wrong_collection = root/'wrong-function.json'
                wrong_collection.write_text(json.dumps(dict(function='func_8001F8B8')), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'declared collection function'):
                    replay.run(recordings, root/'wrong-selection', bridge_file, 'unused',
                               lab_root=root, collection=wrong_collection)
            self.assertEqual((report['captured_calls_available'], report['calls_replayed'], report['skipped_by_requested_limit']), (4, 1, 3))
            self.assertEqual(len(list(output.glob('recording-*-inspection.json'))), 4)
            self.assertFalse(report['full_game_parity_accepted'])


try:
    BACKEND = replay.load_backend()
except ValueError:
    BACKEND = None


@unittest.skipIf(BACKEND is None, 'Optional Unicorn backend is not installed.')
class FunctionalMipsReplayTests(unittest.TestCase):
    def machine(self):
        row = row_fixture()
        memory = bytearray(RAM_BYTES)
        # Generic MIPS: save RA; transfer LZCS/LZCR; call a child that copies
        # its actual link; restore the original caller. No original game bytes.
        main = [0x27BDFFF0, 0xAFBF000C, 0x4884F000, 0x4802F800, 0,
                0x0C004010, 0, 0x8FBF000C, 0, 0x03E00008, 0x27BD0010]
        child = [0x03E01821, 0x03E00008, 0]
        struct.pack_into('<11I', memory, 0x10000, *main)
        struct.pack_into('<3I', memory, 0x10040, *child)
        functions = [dict(function='synthetic_main', address='0x80010000', bytes=44),
                     dict(function='synthetic_child', address='0x80010040', bytes=12)]

        class LeadingOnlyBridge:
            def leading(self, value):
                if value != 0x100:
                    raise AssertionError('Unexpected synthetic GTE input')
                return 23

        machine = replay.NaturalMachine(LeadingOnlyBridge(), functions, row, bytes(memory), backend=BACKEND)
        self.addCleanup(machine.close)
        return machine, row, bytes(memory)

    def test_virtual_PC_survives_COP2_and_nested_JAL(self):
        machine, row, before = self.machine()
        actual, cpu, data, control = machine.invoke()
        expected = bytearray(before)
        struct.pack_into('<I', expected, 0x1FEFFC, row['entry_cpu_gpr_31'])
        result = replay.compare_state(row, actual, bytes(expected), cpu, data, control, machine.instructions)
        self.assertEqual(cpu['gpr_3'], 0x8001001C)
        self.assertEqual(machine.instructions, 14)
        self.assertTrue(result['equal_measured_call'])
        self.assertEqual(machine.entries, {'synthetic_main': 1, 'synthetic_child': 1})

    def test_kernel_scratch_register_is_compared(self):
        machine, row, before = self.machine()
        actual, cpu, data, control = machine.invoke()
        cpu['gpr_26'] ^= 1
        result = replay.compare_state(row, actual, actual, cpu, data, control, machine.instructions)
        self.assertFalse(result['equal_measured_call'])
        self.assertIn('gpr_26', result['CPU_differences'])

    def test_executed_hidden_stack_write_is_detected(self):
        machine, row, before = self.machine()
        machine.cpu.mem_write(0x10010, struct.pack('<I', 0xAFBD0000))  # sw sp,0(sp), replacing a synthetic NOP.
        actual, cpu, data, control = machine.invoke()
        expected = bytearray(before)
        struct.pack_into('<I', expected, 0x1FEFFC, row['entry_cpu_gpr_31'])
        result = replay.compare_state(row, actual, bytes(expected), cpu, data, control, machine.instructions)
        self.assertEqual(struct.unpack_from('<I', actual, 0x1FEFF0)[0], 0x801FEFF0)
        self.assertTrue(any(r['start'] >= 0x1FEFF0 for r in result['RAM']['first_ranges']))
        self.assertFalse(result['equal_measured_call'])

    def test_unreviewed_control_transfer_is_rejected(self):
        machine, row, before = self.machine()
        machine.cpu.mem_write(0x10014, struct.pack('<I', 0x0C004400))  # jal 0x80011000, outside both ranges.
        with self.assertRaisesRegex(ValueError, 'reviewed original function ranges'):
            machine.invoke()

    def test_unfinished_call_is_not_a_return(self):
        machine, row, before = self.machine()
        with self.assertRaisesRegex(ValueError, 'captured caller return'):
            machine.invoke(instruction_limit=1)


if __name__ == '__main__':
    unittest.main()
