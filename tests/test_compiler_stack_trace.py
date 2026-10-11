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
                        'compiler_exited': True, 'compiler_exit_code': 0,
                        'allocation_events': []}), encoding='utf-8')
                return SimpleNamespace(returncode=0, stdout=b'preprocessed', stderr=b'')

            before = source.read_bytes(), compiler.read_bytes()
            with patch.object(tracer, 'ROOT', root), patch.object(tracer.sys, 'platform', 'linux'):
                with patch.object(tracer.configure, 'CC', str(compiler)), patch.object(tracer.shutil, 'which', side_effect=lambda name: name):
                    with patch.object(tracer.subprocess, 'run', side_effect=command_run), patch.object(tracer.subprocess, 'check_output', return_value='GDB test\n'):
                        with self.assertRaisesRegex(ValueError, 'changed assembly'):
                            tracer.trace_candidate(source, output)
            report = json.loads((output/'report.json').read_text(encoding='utf-8'))
            self.assertEqual(report['status'], 'failed')
            self.assertFalse(report['complete_assembly_equal'])
            self.assertEqual((source.read_bytes(), compiler.read_bytes()), before)


if __name__ == '__main__':
    unittest.main()
