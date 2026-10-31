"""Compile a synthetic CPU/RAM transport harness; no original game is loaded."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MoviePayloadObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which('g++') or shutil.which('clang++')
        if not compiler:
            raise unittest.SkipTest('A host C++ compiler is unavailable for the synthetic native transport harness.')
        cls.temporary = tempfile.TemporaryDirectory(prefix='lsd-movie-observer-')
        cls.binary = Path(cls.temporary.name) / 'movie-observer-check.exe'
        result = subprocess.run([compiler, '-std=c++11', '-O1', '-Wall', '-Wextra', '-Werror',
            '-I', str(ROOT), str(ROOT / 'tests/fixtures/movie_payload_harness.cpp'), '-o', str(cls.binary)],
            capture_output=True, text=True, timeout=60)
        if result.returncode:
            cls.temporary.cleanup()
            raise AssertionError(result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def check(self, name):
        result = subprocess.run([str(self.binary), name], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), 'passed ' + name)

    def test_complete_entry_return_and_MDEC_buffers_are_copied_without_RAM_writes(self):
        self.check('complete')

    def test_invalid_encoded_size_is_retained_as_an_error(self):
        self.check('encoded_size')

    def test_actual_frame_header_identity_is_required(self):
        self.check('header_identity')

    def test_accepted_ring_address_must_match_native_SDK_arithmetic(self):
        self.check('ring_address')

    def test_VLC_requires_its_accepted_callback(self):
        self.check('missing_callback')

    def test_actual_return_jump_and_delay_must_have_been_observed(self):
        self.check('return_instructions')

    def test_wrong_stack_cannot_complete_a_VLC_return(self):
        self.check('wrong_return_stack')

    def test_MDEC_requires_a_prior_completed_VLC_buffer(self):
        self.check('missing_decoded_buffer')

    def test_full_payload_captures_changes_beyond_the_old_44_byte_prefix(self):
        self.check('late_payload_difference')

    def test_pending_VLC_context_survives_a_frame_boundary(self):
        self.check('cross_frame_return')

    def test_invalid_RLE_command_length_is_rejected(self):
        self.check('command_bounds')

    def test_event_overflow_is_explicit_and_bounded(self):
        self.check('overflow')
