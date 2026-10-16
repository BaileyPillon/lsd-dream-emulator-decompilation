"""Owned synthetic inputs exercise profile boundaries without game data or Unicorn."""
import contextlib
import io
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import actor_child_model as model
from tools import verify_actor_children as verifier


def record(type_id, kind=8, flags=0, key=None):
    return model.Record(type_id, kind, flags, key)


def synthetic_mom(records=(), animations=1):
    payload = bytearray()
    for item in records:
        words = 2 if item.kind == 2 else 1
        lead = item.type_id | item.kind << 16 | item.flags << 20 | words << 24
        payload.extend(struct.pack('<I', lead))
        if item.kind == 2:
            payload.extend(struct.pack('<I', item.key))
    frame = 28 + animations * 4
    tmd = frame + 8 + len(payload)
    raw = bytearray(tmd + 12)
    raw[:4], raw[12:16] = b'MOM ', b'MOS '
    struct.pack_into('<III', raw, 4, len(raw), tmd, int.from_bytes(b'MOS ', 'little'))
    struct.pack_into('<I', raw, 16, animations)
    for index in range(animations):
        struct.pack_into('<I', raw, 20 + index * 4, 8 + animations * 4)
    struct.pack_into('<I', raw, frame - 4, 1)
    struct.pack_into('<H', raw, frame + 2, len(records))
    raw[frame + 8:tmd] = payload
    struct.pack_into('<III', raw, tmd, 0x41, 0, 0)
    return raw


class FirstFrameTests(unittest.TestCase):
    def test_native_frame_uses_table_length_and_retains_record_order(self):
        raw = synthetic_mom([record(9), record(2), record(9, 2, key=1)], animations=2)
        frame = model.decode_first_frame(raw)
        self.assertEqual(frame.offset, 36)
        self.assertEqual(frame.child_count, 2)
        self.assertEqual([item.type_id for item in frame.records], [9, 2, 9])

    def test_native_frame_does_not_follow_an_animation_table_offset(self):
        raw = synthetic_mom([record(7)])
        struct.pack_into('<I', raw, 20, 0x1234)
        # The static inventory separately validates offsets. This decoder models
        # the original constructor's direct arithmetic, even on this synthetic input.
        self.assertEqual(model.decode_first_frame(raw).records, (record(7),))

    def test_bad_signatures_extents_and_descriptors_are_rejected(self):
        valid = synthetic_mom([record(7)])
        changes = [(0, b'MOM\0'), (12, b'MOS\0'), (4, struct.pack('<I', len(valid) + 4)),
                   (8, struct.pack('<I', 21)), (16, struct.pack('<I', 0)),
                   (16, struct.pack('<I', 500)),
                   (len(valid) - 12, struct.pack('<I', 0x42)),
                   (len(valid) - 4, struct.pack('<I', 1))]
        for offset, value in changes:
            with self.subTest(offset=offset, value=value):
                raw = bytearray(valid)
                raw[offset:offset + len(value)] = value
                with self.assertRaises(ValueError):
                    model.decode_first_frame(raw)
        for size in (0, 4, 23, len(valid) - 1):
            with self.subTest(size=size), self.assertRaises(ValueError):
                model.decode_first_frame(valid[:size])

    def test_zero_short_and_cross_tmd_records_are_rejected(self):
        raw = synthetic_mom([record(7)])
        for lead in (7 | 8 << 16, 7 | 8 << 16 | 2 << 24, 7 | 2 << 16 | 1 << 24):
            with self.subTest(lead=lead):
                changed = bytearray(raw)
                struct.pack_into('<I', changed, 40, lead)
                with self.assertRaises(ValueError):
                    model.decode_first_frame(changed)
        struct.pack_into('<H', raw, 34, 2)
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            model.decode_first_frame(raw)


class EnumerationTests(unittest.TestCase):
    def test_unsorted_declarations_are_preserved(self):
        self.assertEqual(model.enumerate_types([record(9), record(2)], b'\xA1\xB2'), (b'\x09\x02', 0))

    def test_interleaved_search_rewinds_and_overwrites_earlier_output(self):
        records = [record(9), record(2), record(9, 2, key=1), record(7)]
        self.assertEqual(model.enumerate_types(records, b'\xA1\xB2\xC3'), (b'\x09\x07\xC3', 0))

    def test_selector_is_primitive_record_count_not_maximum_key(self):
        records = [record(9), record(2), record(9, 2, key=99), record(2, 2, key=2)]
        self.assertEqual(model.enumerate_types(records, b'\xA1\xB2'), (b'\x09\x02', 1))

    def test_nonzero_declaration_flags_do_not_create_children(self):
        self.assertEqual(model.enumerate_types([record(3, flags=1), record(7)], b'\xA1'), (b'\x07', 0))

    def test_zero_wrapping_counts_and_owned_buffer_underflow_are_outside_profile(self):
        cases = [([], b''), ([record(7)] * 256, bytes(256)), ([record(7)], b''),
                 ([record(9), record(2), record(9, 2, key=2), record(2, 2, key=2)], b'\xA1\xB2')]
        for records, initial in cases:
            with self.subTest(records=len(records), initial=initial), self.assertRaises(ValueError):
                model.enumerate_types(records, initial)


class ArithmeticTests(unittest.TestCase):
    def test_native_signed_division_truncates_toward_zero(self):
        self.assertEqual([model.trunc_div(a, b) for a, b in ((-5, 2), (5, -2), (-5, -2), (1, -2))], [-2, -2, 2, 0])
        with self.assertRaises(ValueError):
            model.trunc_div(1, 0)

    def test_rational_scaling_retains_signed_remainders_and_halfword_narrowing(self):
        values = model.rational_values(struct.pack('<6h', -1, 3, 5, -2, -32768, -1))
        self.assertEqual(values, [-1365, -10240, 134217728])
        self.assertEqual([model.signed_half(value) for value in (0x7FFF, 0x8000, 0xFFFF, 0x10000)],
                         [32767, -32768, -1, 0])
        with self.assertRaises(ValueError):
            model.rational_values(struct.pack('<6h', 0, 0, 1, 1, 1, 1))
        with self.assertRaises(ValueError):
            model.rational_values(bytes(11))


class CustodyTests(unittest.TestCase):
    def test_existing_and_external_destinations_reject_before_original_access(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lab = root / '.decomp-lab'
            lab.mkdir()
            existing = lab / 'old'
            existing.mkdir()
            for path in (root / 'outside', lab, existing):
                with self.subTest(path=path), patch.object(verifier, 'ROOT', root), \
                        patch.object(verifier, 'verify') as verify, contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(verifier.main(['--layout', str(root / 'missing.xml'), '--output', str(path)]), 2)
                    verify.assert_not_called()

    def test_output_symlink_cannot_escape_private_evidence_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / '.decomp-lab').mkdir()
            external = root / 'external'
            external.mkdir()
            link = root / '.decomp-lab' / 'link'
            try:
                link.symlink_to(external, target_is_directory=True)
            except OSError:
                self.skipTest('Directory symlinks unavailable for this account.')
            with patch.object(verifier, 'ROOT', root), self.assertRaises(ValueError):
                verifier.output_directory(link / 'new')

    def test_old_ninja_is_rejected_by_version_probe_before_any_dry_run(self):
        with patch.object(verifier.shutil, 'which', return_value='/owned/ninja'), \
                patch.object(verifier.subprocess, 'check_output', return_value='1.11.1\n') as call:
            with self.assertRaisesRegex(ValueError, 'before checking build freshness'):
                verifier.require_ninja()
            self.assertEqual(call.call_count, 1)
            self.assertEqual(call.call_args.args[0], ['/owned/ninja', '--version'])

    def test_pinned_ninja_package_build_suffix_is_accepted_without_a_dry_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / 'ninja'
            binary.write_bytes(b'owned synthetic executable')
            for version in verifier.NINJA_BUILD_VERSIONS:
                with self.subTest(version=version), patch.object(verifier.shutil, 'which', return_value=str(binary)), \
                        patch.object(verifier.subprocess, 'check_output', return_value=version + '\n') as call:
                    self.assertEqual(verifier.require_ninja()['version'], version)
                    self.assertEqual(call.call_args.args[0], [str(binary), '--version'])

    def test_failed_run_retains_a_failure_record_without_claiming_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / '.decomp-lab' / 'new'
            with patch.object(verifier, 'ROOT', root), \
                    patch.object(verifier, 'verify', side_effect=ValueError('owned failure')), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(verifier.main(['--layout', str(root / 'missing.xml'), '--output', str(target)]), 2)
            self.assertTrue((target / 'failure.json').is_file())
            self.assertIn('owned failure', (target / 'failure.json').read_text())
            self.assertFalse((target / 'report.json').exists())

    def test_diagnostic_binary_mismatch_rejects_before_symbol_parsing(self):
        with patch.object(verifier, 'elf_function') as function, self.assertRaisesRegex(ValueError, 'complete symbol diagnostic'):
            verifier.qualify_diagnostic(SimpleNamespace(ROM=b'owned original'), b'', b'changed', [])
        function.assert_not_called()

    def test_sized_symbol_extent_and_code_identity_are_both_required(self):
        code = b'owned synthetic code'
        function = dict(function='owned', address='0x80010000', bytes=len(code), sha256=verifier.sha(code))
        program = SimpleNamespace(ROM=b'owned original', symbols={'owned': 0x80010000}, target=lambda *_: code)
        with patch.object(verifier, 'elf_function', return_value=(code, {})):
            self.assertEqual(verifier.qualify_diagnostic(program, b'', program.ROM, [function]),
                             [(0x10000, 0x10000 + len(code), 'owned')])
            for field, value in (('bytes', len(code) + 4), ('sha256', '0' * 64)):
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'qualification failed'):
                    verifier.qualify_diagnostic(program, b'', program.ROM, [dict(function, **{field: value})])
        with patch.object(verifier, 'elf_function', return_value=(b'changed', {})), self.assertRaises(ValueError):
            verifier.qualify_diagnostic(program, b'', program.ROM, [function])

    def test_partial_inventory_is_not_silently_promoted_to_complete_corpus(self):
        inventory = dict(MML_reference_audit={'unresolved_counts': {'LBD_files': 0}},
                         unresolved_direct_model_files=[], LBD_unresolved_files=[], rejected=[], files=[],
                         totals={'validated_MOM_instances': 0})
        for key, value in (('unresolved_direct_model_files', ['owned.MOM']), ('LBD_unresolved_files', ['owned.LBD']),
                           ('rejected', ['signature']), ('MML_reference_audit', {'unresolved_counts': {'missing': 1}})):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'partial or unresolved'):
                verifier.corpus_models(dict(inventory, **{key: value}))
        with self.assertRaisesRegex(ValueError, 'complete model-instance corpus'):
            verifier.corpus_models(inventory)

    def test_changed_assets_and_wrong_instance_totals_reject(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / 'owned.MOM'
            source.write_bytes(synthetic_mom([record(7)]))
            data = source.read_bytes()
            file = dict(source=str(source), path='/owned.MOM', bytes=len(data), sha256=verifier.sha(data),
                        models=[dict(offset=0, bytes=len(data))])
            inventory = dict(MML_reference_audit={'unresolved_counts': {}}, unresolved_direct_model_files=[],
                             LBD_unresolved_files=[], rejected=[], files=[file], totals={'validated_MOM_instances': 1})
            planned = verifier.corpus_models(inventory)
            self.assertEqual(len(planned), 1)
            self.assertEqual(planned[0][1].child_count, 1)
            with self.assertRaises(ValueError):
                verifier.corpus_models(dict(inventory, totals={'validated_MOM_instances': 2}))
            source.write_bytes(data + b'changed')
            with self.assertRaisesRegex(ValueError, 'asset changed'):
                verifier.corpus_models(inventory)


if __name__ == '__main__':
    unittest.main()
