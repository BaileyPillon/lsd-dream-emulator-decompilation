"""Guards against accepting unsupported, incomplete or altered compiler traces."""

import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from research.collision import trace_compiler_lifetimes as tracer


def sample_trace():
    snapshot = {'level': 1, 'frame_offset': 16, 'slots': [{
        'node': '0x100', 'slot_rtx': '0x200', 'address_rtx': '0x0', 'rtl_expr': '0x0',
        'size': 16, 'in_use': 1, 'addr_taken': 0, 'level': 1, 'keep': 1,
    }]}
    return {'compiler_exited': True, 'compiler_exit_code': 0, 'trace_errors': [],
            'lifetime_events': [{'sequence': 0, 'operation': 'assign_stack_temp',
                'function': 'example', 'before': snapshot, 'after': copy.deepcopy(snapshot),
                'arguments': [26, 16, 1], 'returned_rtx': '0x200'}]}


def fake_compiler(path):
    data = bytearray(24)
    data[:6] = b'\x7fELF\x01\x01'
    data[18:20] = (3).to_bytes(2, 'little')
    path.write_bytes(data)


class CompilerLifetimeTraceTests(unittest.TestCase):
    def test_help_does_not_start_compilation(self):
        with patch.object(tracer, 'trace_candidate', side_effect=AssertionError('unexpected compiler run')):
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as result:
                tracer.main(['--help'])
        self.assertEqual(result.exception.code, 0)

    def test_function_names_cannot_be_debugger_expressions(self):
        for name in ('', 'example; call f()', '*main', 'a-b', None):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'C function name'):
                tracer.function_name(name)
        self.assertEqual(tracer.function_name('func_8001F8B8'), 'func_8001F8B8')

    def test_public_output_is_rejected_before_reading_any_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            with patch.object(tracer.stack, 'ROOT', root), patch.object(Path, 'read_bytes') as read:
                with self.assertRaisesRegex(ValueError, 'fresh private output'):
                    tracer.trace_candidate(root/'missing.c', root/'public', 'example')
                read.assert_not_called()
            self.assertFalse((root/'public').exists())

    def test_existing_private_evidence_is_retained_without_a_debugger_run(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            output = root/'.decomp-lab'/'retained'
            output.mkdir(parents=True)
            (output/'report.json').write_text('retained', encoding='utf-8')
            with patch.object(tracer.stack, 'ROOT', root), patch.object(tracer.subprocess, 'run') as run:
                with self.assertRaises(FileExistsError):
                    tracer.trace_candidate(root/'missing.c', output, 'example')
                run.assert_not_called()
            self.assertEqual((output/'report.json').read_text(encoding='utf-8'), 'retained')

    def test_different_i386_compiler_is_rejected_before_any_command_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root/'candidate.c'
            source.write_text('int example(void) { return 1; }', encoding='utf-8')
            compiler = root/'cc1'
            fake_compiler(compiler)
            with patch.object(tracer.stack, 'ROOT', root), patch.object(tracer.sys, 'platform', 'linux'):
                with patch.object(tracer.configure, 'CC', str(compiler)), patch.object(tracer.subprocess, 'run') as run:
                    with self.assertRaisesRegex(ValueError, 'exact bundled compiler SHA-256'):
                        tracer.trace_candidate(source, root/'.decomp-lab'/'unsupported', 'example')
                    run.assert_not_called()

    def test_absent_function_compiler_failure_and_debugger_errors_are_rejected(self):
        for field, value in (('lifetime_events', []), ('compiler_exited', False),
                             ('compiler_exit_code', 1), ('trace_errors', ['read failed'])):
            trace = sample_trace()
            trace[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                tracer.validate_trace(trace, 'example')
        with self.assertRaisesRegex(ValueError, 'successful lifetime observation'):
            tracer.validate_trace([], 'example')

    def test_unfinished_returns_and_other_functions_are_rejected(self):
        for mutation in ('unfinished', 'wrong-function', 'bad-sequence', 'bad-return'):
            trace = sample_trace()
            event = trace['lifetime_events'][0]
            if mutation == 'unfinished':
                event.pop('after')
            elif mutation == 'wrong-function':
                event['function'] = 'different'
            elif mutation == 'bad-sequence':
                event['sequence'] = 8
            else:
                event['returned_rtx'] = '0x100000000'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                tracer.validate_trace(trace, 'example')

    def test_corrupt_slot_fields_and_repeated_nodes_are_rejected(self):
        for field, value in (('size', -8), ('level', -2), ('in_use', 3), ('addr_taken', '1'),
                             ('keep', 8), ('slot_rtx', 'unknown'), ('node', '0x0000')):
            trace = sample_trace()
            trace['lifetime_events'][0]['before']['slots'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                tracer.validate_trace(trace, 'example')
        trace = sample_trace()
        slots = trace['lifetime_events'][0]['after']['slots']
        slots.append(copy.deepcopy(slots[0]))
        with self.assertRaisesRegex(ValueError, 'repeated'):
            tracer.validate_trace(trace, 'example')

    def test_completed_observation_preserves_raw_slot_reuse_evidence(self):
        trace = sample_trace()
        event = trace['lifetime_events'][0]
        event['before']['slots'][0]['in_use'] = 0
        self.assertIs(tracer.validate_trace(trace, 'example'), trace['lifetime_events'])
        self.assertEqual(event['before']['slots'][0]['in_use'], 0)
        self.assertEqual(event['after']['slots'][0]['in_use'], 1)

    def test_changed_assembly_or_input_is_rejected_and_evidence_retained(self):
        for fault in ('assembly', 'source'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                source = root/'candidate.c'
                source.write_text('int example(void) { return 1; }', encoding='utf-8')
                compiler = root/'cc1'
                fake_compiler(compiler)
                output = root/'.decomp-lab'/'fault'

                def command_run(argv, **kwargs):
                    if '-o' in argv:
                        changed = '--batch' in argv and fault == 'assembly'
                        Path(argv[argv.index('-o') + 1]).write_bytes(b'li $2,2\n' if changed else b'li $2,1\n')
                    if '--batch' in argv:
                        Path(kwargs['env']['LSD_LIFETIME_REPORT']).write_text(json.dumps(sample_trace()), encoding='utf-8')
                        if fault == 'source':
                            source.write_text('int example(void) { return 2; }', encoding='utf-8')
                    return SimpleNamespace(returncode=0, stdout=b'preprocessed', stderr=b'')

                with patch.object(tracer, 'ROOT', root), patch.object(tracer.stack, 'ROOT', root):
                    with patch.object(tracer.sys, 'platform', 'linux'), patch.object(tracer.configure, 'CC', str(compiler)):
                        with patch.object(tracer, 'compiler_profile', return_value={'sha256': tracer.COMPILER_SHA256}):
                            with patch.object(tracer.shutil, 'which', side_effect=lambda name: name):
                                with patch.object(tracer.subprocess, 'run', side_effect=command_run), patch.object(tracer.subprocess, 'check_output', return_value='GDB test\n'):
                                    with self.assertRaisesRegex(ValueError, 'changed assembly or a preserved input'):
                                        tracer.trace_candidate(source, output, 'example')
                report = json.loads((output/'report.json').read_text(encoding='utf-8'))
                self.assertEqual(report['status'], 'failed')
                self.assertFalse(report['source_promoted'])
                self.assertEqual(report['complete_assembly_equal'], fault != 'assembly')
                self.assertEqual(report['all_observed_inputs_preserved'], fault != 'source')
                self.assertTrue((output/'lifetimes.json').is_file())


if __name__ == '__main__':
    unittest.main()
