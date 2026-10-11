"""Check ambiguity, catalogue integrity and SDK context discriminators."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import audit_sdk_signatures as audit


class SdkSignatureTests(unittest.TestCase):
    def test_repeated_sequences_retain_every_candidate(self):
        signature = [0x12, None, 0x34, 0x56]
        self.assertEqual(audit.find_matches(b'\x12\x10\x34\x56\x12\x20\x34\x56', signature), [0, 4])
        self.assertEqual(audit.find_matches(b'\x12\x10\x34\x57', signature), [])
        self.assertEqual(audit.find_matches(b'\0' * 32, [None] * 4), [])

    def test_fixed_bytes_and_complete_length_are_required(self):
        self.assertTrue(audit.matches(b'\xAA\x12\xBB', [0xAA, None, 0xBB]))
        self.assertFalse(audit.matches(b'\xAA\x12\xBC', [0xAA, None, 0xBB]))
        self.assertFalse(audit.matches(b'\xAA\x12', [0xAA, None, 0xBB]))

    def test_malformed_catalogues_are_rejected(self):
        valid = {'name': 'test.OBJ', 'sig': '12 ?? 34 56', 'labels': [{'name': 'entry', 'offset': 0}]}
        bad = [{}, [1], [{**valid, 'name': ''}], [{**valid, 'sig': '1?'}],
               [{**valid, 'sig': ''}], [{**valid, 'labels': 'entry'}],
               [{**valid, 'labels': [{'name': 'entry', 'offset': True}]}],
               [{**valid, 'labels': [{'name': 'entry', 'offset': 4}]}]]
        for payload in bad:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                audit.parse_catalogue(json.dumps(payload))
        self.assertEqual(audit.parse_catalogue(json.dumps([valid]))[0]['bytes'], [0x12, None, 0x34, 0x56])

    def test_volume_and_pan_wrappers_need_their_surrounding_labels(self):
        begin = audit.VOLUME_FUNCTIONS[0][1]
        size = sum(length for _, _, length in audit.VOLUME_FUNCTIONS)
        code = bytes(i % 251 for i in range(size))
        labels = [{'name': name, 'offset': address - begin} for name, address, _ in audit.VOLUME_FUNCTIONS]
        entry = {'name': 'fixture.OBJ', 'bytes': list(code), 'labels': labels}
        original = b'\0' * 0x800 + code
        self.assertEqual(audit.volume_region(original, [entry], begin)['bytes'], size)
        swapped = [dict(label) for label in labels]
        swapped[-1]['name'], swapped[-2]['name'] = swapped[-2]['name'], swapped[-1]['name']
        with self.assertRaises(ValueError):
            audit.volume_region(original, [{**entry, 'labels': swapped}], begin)
        changed = bytearray(original)
        changed[0x800 + 20] ^= 1
        with self.assertRaises(ValueError):
            audit.volume_region(bytes(changed), [entry], begin)

    def test_existing_native_evidence_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / '.decomp-lab' / 'report.json'
            path.parent.mkdir()
            path.write_bytes(b'original evidence')
            with patch.object(audit, 'ROOT', root), patch.object(audit, 'collect') as collect, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(audit.main(['--signatures', '.', '--output', str(path)]), 2)
                collect.assert_not_called()
            self.assertEqual(path.read_bytes(), b'original evidence')


if __name__ == '__main__':
    unittest.main()
