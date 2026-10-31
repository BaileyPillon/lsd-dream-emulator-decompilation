"""Optionally replay private native GTE snapshots without an emulator install."""
import hashlib
import json
import lzma
import os
from pathlib import Path
import unittest

from tools.gte_state_model import GteState

ROOT = Path(__file__).resolve().parents[1]
_fixture = os.environ.get('LSD_GTE_NATIVE_TRANSCRIPT')
FIXTURE = Path(_fixture) if _fixture else None


@unittest.skipUnless(FIXTURE, 'Set LSD_GTE_NATIVE_TRANSCRIPT to a private qualified transcript')
class NativeGteTranscriptTests(unittest.TestCase):
    def test_recorded_native_register_states_match_the_integer_oracle(self):
        report = json.loads((ROOT/'docs/gte-state-checks.json').read_bytes())
        encoded = FIXTURE.read_bytes()
        self.assertEqual(hashlib.sha256(encoded).hexdigest(),report['journal']['sha256'])
        raw = lzma.decompress(encoded)
        self.assertEqual(len(raw),report['journal']['decoded_bytes'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(),report['journal']['decoded_sha256'])
        oracle = GteState()
        count = 0
        for count,line in enumerate(raw.splitlines(),1):
            record = json.loads(line)
            request,observed = record['request'],record['observed']
            self.assertEqual(request['id'],count)
            self.assertEqual(observed['id'],count)
            expected = oracle.request(request['reset'],request['writes'],request['command'])
            with self.subTest(native_request=count):
                self.assertEqual({k:v for k,v in observed.items() if k!='id'},expected)
        self.assertEqual(count,report['total_cases'])
        self.assertEqual(oracle.commands,report['native_commands'])
        self.assertEqual(oracle.data_writes,report['native_data_writes'])


if __name__ == '__main__':
    unittest.main()
