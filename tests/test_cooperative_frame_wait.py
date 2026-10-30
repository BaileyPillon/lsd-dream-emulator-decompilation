"""Drive the actual managed wait from a separate process; no game data is needed."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

from tests.test_streamed_state_hashes import installed_toolchain

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = r'''
using System;
using System.IO;
using Lsd.Research.Headless;
class FrameWaitFixture {
    public static int Main(string[] args) {
        string folder = args[0], mode = args[2];
        try {
            var gate = new CooperativeFrameWait(folder, Int32.Parse(args[1]), 10);
            var result = gate.WaitIfRequested(token => {
                File.WriteAllText(Path.Combine(folder, "waiting.txt"), token);
                if (mode == "fail-before") throw new InvalidOperationException();
            }, finished => {
                if (mode == "fail-after") throw new InvalidOperationException();
                File.WriteAllText(Path.Combine(folder, "resumed.txt"), finished.Token);
            });
            Console.WriteLine(result == null ? "none" : String.Join("\t", "waited", result.Token,
                result.ElapsedMilliseconds, result.StopRequested, result.TimedOut));
        } catch (Exception error) { Console.WriteLine("error\t" + error.GetType().Name); }
        return 0;
    }
}
'''


class CooperativeFrameWaitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dotnet, compiler, references, flags = installed_toolchain()
        cls.area = tempfile.TemporaryDirectory(prefix='lsd-frame-wait-')
        cls.addClassCleanup(cls.area.cleanup)
        folder = Path(cls.area.name)
        source = folder / 'FrameWaitFixture.cs'
        source.write_text(FIXTURE, encoding='utf-8')
        cls.binary = folder / 'wait.dll'
        (folder / 'wait.runtimeconfig.json').write_text(json.dumps({'runtimeOptions': {
            'tfm': references.name, 'framework': {
                'name': 'Microsoft.NETCore.App', 'version': references.name[3:] + '.0'}}}), encoding='utf-8')
        command = [dotnet, 'exec', str(compiler), '/nologo', '/target:exe', '/nostdlib+',
                   '/deterministic+', '/out:' + str(cls.binary),
                   *('/reference:' + str(p) for p in sorted(references.glob('*.dll'))),
                   str(ROOT / 'research/headless/CooperativeFrameWait.cs'), str(source)]
        compiled = subprocess.run(command, capture_output=True, text=True, timeout=30, creationflags=flags)
        if compiled.returncode:
            raise AssertionError(compiled.stdout + compiled.stderr)
        cls.dotnet, cls.flags = dotnet, flags

    def setUp(self):
        self.case = tempfile.TemporaryDirectory(dir=self.area.name)
        self.addCleanup(self.case.cleanup)
        self.folder = Path(self.case.name)

    @contextmanager
    def host(self, token=None, timeout=5000, mode='ordinary'):
        if token is not None:
            (self.folder / 'HOST-WAIT').write_bytes(token)
        child = subprocess.Popen([self.dotnet, str(self.binary), str(self.folder), str(timeout), mode],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                 creationflags=self.flags)
        try:
            yield child
        finally:
            if child.poll() is None:
                child.terminate()
            child.communicate(timeout=10)
            child.stdout.close()
            child.stderr.close()

    def acknowledgment(self, child, token='case-1'):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            self.assertIsNone(child.poll(), 'Managed host ended before acknowledging its wait.')
            path = self.folder / 'HOST-WAIT-ACK'
            if path.is_file() and path.read_text() == token:
                self.assertEqual((self.folder / 'waiting.txt').read_text(), token)
                return
            time.sleep(.01)
        self.fail('Managed host did not acknowledge its wait.')

    def result(self, child):
        output, error = child.communicate(timeout=10)
        self.assertEqual(child.returncode, 0, error)
        self.assertEqual(error, '')
        return output.strip().split('\t')

    def test_absent_request_has_no_wait_or_callbacks(self):
        with self.host() as child:
            self.assertEqual(self.result(child), ['none'])
        self.assertFalse((self.folder / 'waiting.txt').exists())
        self.assertFalse((self.folder / 'HOST-WAIT-ACK').exists())

    def test_release_holds_until_request_removal(self):
        with self.host(b'case-1') as child:
            self.acknowledgment(child)
            time.sleep(.15)
            self.assertIsNone(child.poll())
            self.assertFalse((self.folder / 'resumed.txt').exists())
            (self.folder / 'HOST-WAIT').unlink()
            row = self.result(child)
        self.assertEqual(row[:2], ['waited', 'case-1'])
        self.assertGreaterEqual(int(row[2]), 140)
        self.assertEqual(row[3:], ['False', 'False'])
        self.assertEqual((self.folder / 'resumed.txt').read_text(), 'case-1')
        self.assertFalse((self.folder / 'HOST-WAIT-ACK').exists())

    def test_stop_releases_an_acknowledged_wait(self):
        with self.host(b'case-1') as child:
            self.acknowledgment(child)
            (self.folder / 'STOP').write_text('owned-test-stop')
            row = self.result(child)
        self.assertEqual(row[3:], ['True', 'False'])
        self.assertFalse((self.folder / 'HOST-WAIT-ACK').exists())

    def test_wait_is_bounded_without_supervisor_release(self):
        with self.host(b'case-1', timeout=150) as child:
            row = self.result(child)
        self.assertEqual(row[3:], ['False', 'True'])
        self.assertGreaterEqual(int(row[2]), 150)
        self.assertFalse((self.folder / 'HOST-WAIT-ACK').exists())

    def test_replaced_token_fails_and_cleans_owned_acknowledgment(self):
        with self.host(b'case-1') as child:
            self.acknowledgment(child)
            replacement = self.folder / 'replacement'
            replacement.write_bytes(b'case-2')
            os.replace(replacement, self.folder / 'HOST-WAIT')
            self.assertEqual(self.result(child), ['error', 'IOException'])
        self.assertFalse((self.folder / 'resumed.txt').exists())
        self.assertFalse((self.folder / 'HOST-WAIT-ACK').exists())

    def test_invalid_tokens_never_acknowledge(self):
        for token in (b'', b'x' * 129, b'has space', b'line\n', b'\xff'):
            with self.subTest(token=token), self.host(token) as child:
                self.assertEqual(self.result(child), ['error', 'IOException'])
            self.assertFalse((self.folder / 'waiting.txt').exists())
            self.assertFalse((self.folder / 'HOST-WAIT-ACK').exists())

    def test_stale_acknowledgment_is_rejected_and_preserved(self):
        (self.folder / 'HOST-WAIT-ACK').write_text('stale')
        with self.host(b'case-1') as child:
            self.assertEqual(self.result(child), ['error', 'IOException'])
        self.assertEqual((self.folder / 'HOST-WAIT-ACK').read_text(), 'stale')

    def test_boundary_callback_failure_cannot_leave_an_owned_acknowledgment(self):
        for mode in ('fail-before', 'fail-after'):
            with self.subTest(mode=mode), self.host(b'case-1', timeout=20, mode=mode) as child:
                self.assertEqual(self.result(child), ['error', 'InvalidOperationException'])
            self.assertFalse((self.folder / 'HOST-WAIT-ACK').exists())

    def test_stop_before_request_does_not_enter_a_wait(self):
        (self.folder / 'STOP').write_text('owned-test-stop')
        with self.host(b'case-1') as child:
            self.assertEqual(self.result(child), ['none'])
        self.assertFalse((self.folder / 'waiting.txt').exists())

    def test_invalid_wait_bound_is_rejected(self):
        with self.host(timeout=0) as child:
            self.assertEqual(self.result(child), ['error', 'ArgumentOutOfRangeException'])


if __name__ == '__main__':
    unittest.main()
