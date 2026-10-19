"""Evidence and output guards for the canonical compiler tracing diagnostic."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from research.collision import trace_compiler_stack as tracer


class CompilerStackTraceTests(unittest.TestCase):
    def reload_trace(self):
        return {'schema_version': 2, 'compiler_exited': True, 'compiler_exit_code': 0,
                'allocation_events': [{'sequence': 0, 'function': 'example',
                    'allocator': 'assign_stack_local', 'frame_offset_after': 8,
                    'call_stack': ['assign_stack_local', 'alter_reg', 'reload'],
                    'alter_reg_context': {'pseudo': 141, 'from_pseudo': -1,
                                          'function': 'example', 'completed': True}}]}

    def test_completed_reload_context_is_retained(self):
        trace = self.reload_trace()
        self.assertIs(tracer.validate_trace(trace), trace['allocation_events'])
        self.assertEqual(trace['allocation_events'][0]['alter_reg_context']['pseudo'], 141)

    def test_missing_or_unfinished_reload_context_is_rejected(self):
        for replacement in (None, {}, {'pseudo': 141, 'from_pseudo': -1,
                                      'function': 'example', 'completed': False}):
            trace = self.reload_trace()
            trace['allocation_events'][0]['alter_reg_context'] = replacement
            with self.subTest(context=replacement), self.assertRaisesRegex(ValueError, 'reload caller context'):
                tracer.validate_trace(trace)

    def test_wrong_function_and_invalid_pseudo_values_are_rejected(self):
        for key, value in (('function', 'other'), ('pseudo', True), ('pseudo', 70),
                           ('pseudo', 65536), ('from_pseudo', -2), ('from_pseudo', False)):
            trace = self.reload_trace()
            trace['allocation_events'][0]['alter_reg_context'][key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'reload caller context'):
                tracer.validate_trace(trace)

    def test_non_reload_allocation_needs_no_pseudo_context(self):
        trace = self.reload_trace()
        event = trace['allocation_events'][0]
        event['call_stack'] = ['assign_stack_local', 'reload']
        event['alter_reg_context'] = None
        self.assertEqual(tracer.validate_trace(trace), [event])

    def outer_trace(self):
        trace = self.reload_trace()
        trace.update(schema_version=3, outer_allocation_errors=[], outer_allocation_events=[{
            'sequence': 0, 'allocator': 'assign_outer_stack_local',
            'active_function': 'nested_midpoint', 'owner_context': '0x8300370',
            'mode_number': 4, 'size': 4, 'alignment': 0,
            'active_function_frame_before': 4, 'active_function_frame_after': 4,
            'returned_rtx': '0x8320100', 'returned_slot': {'base_register': 54, 'offset': 16},
            'call_stack': ['assign_outer_stack_local', 'put_reg_into_stack'], 'completed': True,
        }])
        return trace

    def test_outer_owner_slot_is_not_the_active_nested_function_frame(self):
        trace = self.outer_trace()
        self.assertIs(tracer.validate_trace(trace), trace['allocation_events'])
        outer = tracer.validate_outer_allocations(trace)
        self.assertIs(outer, trace['outer_allocation_events'])
        self.assertEqual(outer[0]['returned_slot']['offset'], 16)
        self.assertEqual(outer[0]['active_function_frame_after'], 4)

    def test_legacy_trace_does_not_invent_outer_observations(self):
        self.assertEqual(tracer.validate_outer_allocations(self.reload_trace()), [])

    def test_new_schema_requires_explicit_outer_observation_results(self):
        for key in ('outer_allocation_events', 'outer_allocation_errors'):
            trace = self.outer_trace()
            del trace[key]
            with self.subTest(missing=key), self.assertRaisesRegex(ValueError, 'outer-scope'):
                tracer.validate_trace(trace)

    def test_outer_allocator_errors_and_unfinished_returns_are_rejected(self):
        trace = self.outer_trace()
        trace['outer_allocation_errors'] = ['outer allocator did not return']
        with self.assertRaisesRegex(ValueError, 'outer-scope'):
            tracer.validate_trace(trace)
        for key, value in (('completed', False), ('owner_context', '0x0'),
                           ('owner_context', '0x100000000'), ('size', True),
                           ('size', -1), ('returned_rtx', None), ('returned_slot', None),
                           ('sequence', 1), ('sequence', False), ('active_function', None), ('call_stack', [])):
            trace = self.outer_trace()
            trace['outer_allocation_events'][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'outer-scope'):
                tracer.validate_trace(trace)

    def test_non_record_outer_events_are_rejected(self):
        for event in (None, [], 'incomplete'):
            trace = self.outer_trace()
            trace['outer_allocation_events'] = [event]
            with self.subTest(event=event), self.assertRaisesRegex(ValueError, 'outer-scope'):
                tracer.validate_trace(trace)

    def test_invalid_returned_slots_are_rejected(self):
        for slot in ({'base_register': True, 'offset': 16}, {'base_register': 65536, 'offset': 16},
                     {'base_register': 54, 'offset': True}, {'base_register': 54, 'offset': 0x80000000}):
            trace = self.outer_trace()
            trace['outer_allocation_events'][0]['returned_slot'] = slot
            with self.subTest(slot=slot), self.assertRaisesRegex(ValueError, 'outer-scope'):
                tracer.validate_trace(trace)

    def test_new_schema_still_requires_completed_reload_contexts(self):
        trace = self.outer_trace()
        trace['allocation_events'][0]['alter_reg_context'] = None
        with self.assertRaisesRegex(ValueError, 'reload caller context'):
            tracer.validate_trace(trace)

    def test_unpinned_i386_compiler_is_rejected_before_debugger(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            compiler, source = root / 'cc1', root / 'candidate.c'
            data = bytearray(24)
            data[:6], data[18:20] = b'\x7fELF\x01\x01', (3).to_bytes(2, 'little')
            compiler.write_bytes(data)
            source.write_text('int example(void) { return 1; }')
            with patch.object(tracer, 'ROOT', root), patch.object(tracer.sys, 'platform', 'linux'):
                with patch.object(tracer.configure, 'CC', str(compiler)), patch.object(tracer.subprocess, 'run') as run:
                    with self.assertRaisesRegex(ValueError, 'exact bundled compiler'):
                        tracer.trace_candidate(source, root / '.decomp-lab/rejected')
                    run.assert_not_called()

    def test_help_does_not_read_inputs_or_launch_a_debugger(self):
        with patch.object(tracer, 'trace_candidate', side_effect=AssertionError('unexpected compiler run')):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as result:
                tracer.main(['--help'])
        self.assertEqual(result.exception.code, 0)

    def test_public_output_is_rejected_before_any_source_or_compiler_read(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            with patch.object(tracer, 'ROOT', root), patch.object(Path, 'read_bytes') as read:
                with self.assertRaisesRegex(ValueError, 'fresh private output'):
                    tracer.trace_candidate(root/'missing.c', root/'published')
                read.assert_not_called()
            self.assertFalse((root/'published').exists())

    def test_existing_private_evidence_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            output = root/'.decomp-lab'/'retained'
            output.mkdir(parents=True)
            sentinel = output/'report.json'
            sentinel.write_text('retained', encoding='utf-8')
            with patch.object(tracer, 'ROOT', root), patch.object(tracer.subprocess, 'run') as run:
                with self.assertRaises(FileExistsError):
                    tracer.trace_candidate(root/'missing.c', output)
                run.assert_not_called()
            self.assertEqual(sentinel.read_text(encoding='utf-8'), 'retained')

    def test_wrong_compiler_abi_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            compiler = Path(folder)/'compiler'
            header = bytearray(24)
            header[:6] = b'\x7fELF\x02\x01'
            header[18:20] = (62).to_bytes(2, 'little')
            compiler.write_bytes(header)
            with self.assertRaisesRegex(ValueError, 'ELF32'):
                tracer.compiler_profile(compiler)

    def test_valid_profile_records_the_actual_compiler_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            compiler = Path(folder)/'compiler'
            data = bytearray(24)
            data[:6] = b'\x7fELF\x01\x01'
            data[18:20] = (3).to_bytes(2, 'little')
            compiler.write_bytes(data)
            profile = tracer.compiler_profile(compiler)
            self.assertEqual(profile['sha256'], hashlib.sha256(data).hexdigest())
            self.assertEqual(profile['pointer_bytes'], 4)

    def test_compiler_failures_and_unfinished_allocator_returns_are_rejected(self):
        for trace in (
            {'compiler_exited': False, 'compiler_exit_code': 0, 'allocation_events': []},
            {'compiler_exited': True, 'compiler_exit_code': 1, 'allocation_events': []},
            {'compiler_exited': True, 'compiler_exit_code': 0, 'allocation_events': None},
            {'compiler_exited': True, 'compiler_exit_code': 0, 'allocation_events': [
                {'sequence': 0, 'function': 'example', 'allocator': 'assign_stack_temp'}]},
        ):
            with self.subTest(trace=trace), self.assertRaises(ValueError):
                tracer.validate_trace(trace)

    def test_a_function_without_stack_storage_can_have_zero_allocator_calls(self):
        self.assertEqual(tracer.validate_trace({'compiler_exited': True,
            'compiler_exit_code': 0, 'allocation_events': []}), [])

    def test_changed_debugger_output_is_rejected_and_retained(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root/'candidate.c'
            source.write_text('int example(void) { return 1; }', encoding='utf-8')
            output = root/'.decomp-lab'/'fault'
            compiler = root/'cc1'
            header = bytearray(24)
            header[:6] = b'\x7fELF\x01\x01'
            header[18:20] = (3).to_bytes(2, 'little')
            compiler.write_bytes(header)

            def command_run(argv, **kwargs):
                if '-o' in argv:
                    Path(argv[argv.index('-o') + 1]).write_bytes(b'li $2,2\n' if '--batch' in argv else b'li $2,1\n')
                if '--batch' in argv:
                    Path(kwargs['env']['LSD_STACK_TRACE_REPORT']).write_text(json.dumps({
                        'schema_version': 3, 'compiler_exited': True, 'compiler_exit_code': 0,
                        'allocation_events': [], 'outer_allocation_events': [],
                        'outer_allocation_errors': []}), encoding='utf-8')
                return SimpleNamespace(returncode=0, stdout=b'preprocessed', stderr=b'')

            before = source.read_bytes(), compiler.read_bytes()
            with patch.object(tracer, 'ROOT', root), patch.object(tracer.sys, 'platform', 'linux'):
                with patch.object(tracer.configure, 'CC', str(compiler)), patch.object(tracer.shutil, 'which', side_effect=lambda name: name):
                    with patch.object(tracer, 'COMPILER_SHA256', hashlib.sha256(header).hexdigest()), patch.object(tracer.subprocess, 'run', side_effect=command_run), patch.object(tracer.subprocess, 'check_output', return_value='GDB test\n'):
                        with self.assertRaisesRegex(ValueError, 'changed assembly'):
                            tracer.trace_candidate(source, output)
            report = json.loads((output/'report.json').read_text(encoding='utf-8'))
            self.assertEqual(report['status'], 'failed')
            self.assertFalse(report['complete_assembly_equal'])
            self.assertEqual((source.read_bytes(), compiler.read_bytes()), before)


if __name__ == '__main__':
    unittest.main()
