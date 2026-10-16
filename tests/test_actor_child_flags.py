"""Synthetic flag witnesses, list order and output custody; no game inputs."""
import contextlib
import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from research.actor_children import verify as actor


class ActorChildFlagTests(unittest.TestCase):
    def case(self, **changes):
        return dict(dict(kind='direct-node', count=0, layout=0, flag=0,
                         word=0x12345678, segment=0, pattern=0), **changes)

    def test_zero_and_full_word_flags_preserve_other_bits_and_return_previous_state(self):
        for word, flag, expected_word, expected_return in (
                (0x12345678, 0, 0x92345678, 1),
                (0x12345678, 256, 0x12345678, 1),
                (0x92345678, -1, 0x12345678, 0),
                (0xBADAF00D, 1, 0x3ADAF00D, 0)):
            with self.subTest(word=word, flag=flag):
                case = self.case(word=word, flag=flag)
                before = bytes(actor.fixture(case))
                after, result, trace = actor.expected(case, before, flag)
                offset = actor.node_offset(0) + 0x10
                self.assertEqual(struct.unpack_from('<I', after, offset)[0], expected_word)
                self.assertEqual(result, expected_return)
                self.assertEqual(after[:offset], before[:offset])
                self.assertEqual(after[offset + 4:], before[offset + 4:])
                self.assertEqual(trace[0][2], flag & 0xFFFFFFFF)

    def test_duplicate_entries_dispatch_in_order_and_leave_root_and_other_nodes_unchanged(self):
        case = self.case(kind='virtual-entity', count=4, layout=2)
        before = bytes(actor.fixture(case))
        after, result, trace = actor.expected(case, before, 0)
        receivers = [entry[1] for entry in trace if entry[0] == 'func_8001D344']
        self.assertEqual(receivers, [actor.ARENA + actor.node_offset(i) for i in (0, 1, 0, 2)])
        self.assertIsNone(result)
        allowed = {actor.node_offset(i) + 0x13 for i in (0, 1, 2)}
        self.assertTrue(all(a == b for i, (a, b) in enumerate(zip(before, after)) if i not in allowed))

    def test_signed_nonpositive_counts_preserve_the_entire_child_graph(self):
        for count in (-2147483648, -1, 0):
            with self.subTest(count=count):
                case = self.case(kind='virtual-actor', count=count)
                before = bytes(actor.fixture(case))
                after, result, trace = actor.expected(case, before, 0)
                self.assertEqual(after, before)
                self.assertIsNone(result)
                self.assertEqual([entry[0] for entry in trace], ['actor_children_set_flag', 'func_80065A5C'])

    def test_declared_domain_contains_word_flags_aliases_and_repeated_call_histories(self):
        cases = list(actor.cases())
        self.assertEqual(len(cases), 16464)
        self.assertEqual({case['flag'] for case in cases}, {-2147483648, -1, 0, 1, 2, 256, 2147483647})
        self.assertEqual({case['segment'] for case in cases}, {0, 0x80000000, 0xA0000000})
        self.assertEqual(len(list(actor.histories())), 48)
        self.assertEqual(actor.HISTORY, (0, 1, 1, 0, -1))

    def test_existing_output_is_preserved_before_loading_game_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / '.decomp-lab' / 'prior'
            output.mkdir(parents=True)
            prior = output / 'evidence.json'
            prior.write_bytes(b'prior evidence')
            with patch.object(actor, 'ROOT', root), patch.object(actor, 'verify') as verify, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(actor.main(['--output', str(output)]), 2)
                verify.assert_not_called()
            self.assertEqual(prior.read_bytes(), b'prior evidence')

    def test_public_and_lab_root_outputs_are_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(actor, 'ROOT', Path(folder)), \
                patch.object(actor, 'verify') as verify, contextlib.redirect_stderr(io.StringIO()):
            for path in ('public', '.decomp-lab'):
                with self.subTest(path=path):
                    self.assertEqual(actor.main(['--output', path]), 2)
                    verify.assert_not_called()


if __name__ == '__main__':
    unittest.main()
