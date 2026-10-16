"""Guard candidate extent, evidence preservation and actual fixture identity."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import verify_render_grid_candidates as candidates


class GridCandidateTests(unittest.TestCase):
    def test_image_guards_reject_truncation_and_changes_outside_selected_extent(self):
        original = bytes(range(64))
        for altered in (original[:-1], original + b'\0', bytes([255]) + original[1:],
                        original[:-1] + bytes([255])):
            with self.subTest(length=len(altered)), self.assertRaises(ValueError):
                candidates.selected_body(original, altered, 16, 12)
        altered = original[:16] + b'\xff' * 12 + original[28:]
        self.assertEqual(candidates.selected_body(original, altered, 16, 12), b'\xff' * 12)

    def test_extent_cannot_escape_or_be_empty(self):
        for offset, length in ((-1, 4), (0, 0), (0, -1), (63, 2)):
            with self.subTest(offset=offset, length=length), self.assertRaises(ValueError):
                candidates.selected_body(bytes(64), bytes(64), offset, length)

    def test_public_candidate_location_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(candidates, 'ROOT', Path(folder)):
            with self.assertRaisesRegex(ValueError, 'private'):
                candidates.load_candidate(Path(folder) / 'public', None)

    def test_workbench_source_image_and_elf_digests_are_rechecked(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(candidates, 'ROOT', Path(folder)):
            build = Path(folder) / '.decomp-lab' / 'build'
            build.mkdir(parents=True)
            source = build / 'source.c'
            source.write_bytes(b'complete private source')
            original = bytes(4096)
            image = original[:2048] + bytes([1]) * 660 + original[2708:]
            elf = b'synthetic ELF fixture'
            (build / 'candidate.exe').write_bytes(image)
            (build / 'candidate-symbols.elf').write_bytes(elf)
            record = dict(candidate=str(source), source='src/scene/render_context.c',
                candidate_sha256=candidates.digest(source.read_bytes()), function_diagnostics=dict(
                    function=candidates.TARGET['function'], elf_sha256=candidates.digest(elf),
                    candidate_executable_sha256=candidates.digest(image),
                    diagnostic_executable_sha256=candidates.digest(image), diagnostic_image_matches_candidate=True))
            (build / 'comparison.json').write_text(json.dumps(record), encoding='utf-8')
            program = SimpleNamespace(ROM=original, LOAD=candidates.ADDRESS, target=lambda a, n: bytes(n))
            with patch.object(candidates, 'elf_function', return_value=(bytes([1]) * 660, {})):
                self.assertEqual(candidates.load_candidate(build, program)[2]['differing_bytes'], 660)
                for name in ('source.c', 'candidate.exe', 'candidate-symbols.elf'):
                    path = build / name
                    prior = path.read_bytes()
                    path.write_bytes(prior + b'changed')
                    with self.subTest(artifact=name), self.assertRaisesRegex(ValueError, 'workbench record'):
                        candidates.load_candidate(build, program)
                    path.write_bytes(prior)
            with patch.object(candidates, 'elf_function', return_value=(bytes([1]) * 656, {})), \
                    self.assertRaisesRegex(ValueError, 'whole sized ELF'):
                candidates.load_candidate(build, program)

    def test_extension_deduplicates_actual_graphs_and_argument_registers(self):
        cases = list(candidates.extension_cases(((0, 4096),) * 4096))
        self.assertEqual(len({candidates.fixture_identity(case) for case in cases}), len(cases))

    def test_fixture_identity_counts_real_argument_changes_and_ignores_unused_case_flags(self):
        case = dict(candidates.position.base_case(), euler=(0, 0x200, 0))
        identity = candidates.fixture_identity(case)
        self.assertNotEqual(identity, candidates.fixture_identity(dict(case, width=case['width'] + 1)))
        self.assertNotEqual(identity, candidates.fixture_identity(dict(case, height=case['height'] + 1)))
        self.assertNotEqual(identity, candidates.fixture_identity(dict(case, segment=0x80000000)))
        self.assertEqual(identity, candidates.fixture_identity(dict(case, auxiliary_present=not case['auxiliary_present'])))

    def test_extension_uses_valid_world_positions_and_disjoint_long_distance_inputs(self):
        pairs = ((0, 4096),) * 4096  # Synthetic table; no original assets required.
        cases = list(candidates.extension_cases(pairs))
        self.assertEqual(len(cases), 11550)
        self.assertEqual({case['distance'] for case in cases}, set(candidates.DISTANCES))
        self.assertTrue(set(candidates.DISTANCES).isdisjoint((-65537, -32769, -1, 0, 1, 12345, 65537)))
        self.assertEqual({(case['width'], case['height']) for case in cases}, set(candidates.DIMENSIONS))
        for case in cases:
            self.assertIsNotNone(candidates.position.selected_label(case))
            self.assertEqual(case['angle'], case['euler'][1])

    def test_report_log_and_failure_outputs_are_preserved_before_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = root / '.decomp-lab' / 'report.json'
            report.parent.mkdir()
            for path in (report, report.with_suffix('.log'), report.with_name('report-stderr.log'),
                         report.with_name('report-failure.json')):
                path.write_bytes(b'prior evidence')
                with patch.object(candidates, 'ROOT', root), patch.object(candidates, 'verify') as verify, \
                        contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(candidates.main(['--edge-build', 'unused', '--cell-build', 'unused',
                        '--bridge', 'unused.exe', '--runtime', 'unused', '--output', str(report)]), 2)
                    verify.assert_not_called()
                self.assertEqual(path.read_bytes(), b'prior evidence')
                path.unlink()

    def test_public_report_is_rejected_without_loading_game_inputs(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(candidates, 'ROOT', Path(folder)), \
                patch.object(candidates, 'verify') as verify, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(candidates.main(['--edge-build', 'unused', '--cell-build', 'unused',
                '--bridge', 'unused.exe', '--runtime', 'unused', '--output', 'public.json']), 2)
            verify.assert_not_called()

    def test_report_cannot_share_the_native_log_path(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(candidates, 'ROOT', Path(folder)), \
                patch.object(candidates, 'verify') as verify, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(candidates.main(['--edge-build', 'unused', '--cell-build', 'unused',
                '--bridge', 'unused.exe', '--runtime', 'unused', '--output', '.decomp-lab/report.log']), 2)
            verify.assert_not_called()


if __name__ == '__main__':
    unittest.main()
