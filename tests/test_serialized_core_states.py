"""Synthetic envelope/retention controls; real game observations remain separate."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools import inspect_serialized_core_states as states
from tools.inspect_dispatch_history import observer_requested


class SerializedStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name).resolve()
        self.native = {'frames_advanced': 2, 'checkpoints': []}
        self.summary = dict(schema_version=1,status='recorded_repeated_serialized_core_states',
            contract='BizHawk.IStatable',frames_advanced=2,serializations_per_checkpoint=2,
            second_complete_bytes_retained_on_mismatch=True,state_restored=False,game_RAM_injected=False,
            emulator_UI_controlled=False,complete_state_parity_checked=False,original_hardware_timing_verified=False,
            checkpoints=[])
        for frame in [0,1]:
            raw = self.envelope(frame+1)
            filename = f'core-state-{frame}.bin'
            (self.output/filename).write_bytes(raw)
            row = dict(relative_frame=frame,core_frame=frame+1,before_core_frame=frame+1,
                file=filename,bytes=len(raw),sha256=states.digest(raw),repeat_bytes=len(raw),repeat_sha256=states.digest(raw),
                same_frame_serializations_equal=True,MainRAM_unchanged=True,GPURAM_unchanged=True,
                core_frame_unchanged=True,deterministic_emulation=False,
                MainRAM_before_sha256='a'*64,MainRAM_after_sha256='a'*64,
                GPURAM_before_sha256='b'*64,GPURAM_after_sha256='b'*64)
            self.summary['checkpoints'].append(row)
            self.native['checkpoints'].append(dict(relative_frame=frame,core_frame=frame+1,
                RAM_sha256='a'*64,GPU_sha256='b'*64,image={'width':320,'height':240}))
            self.sidecar(frame)

    @staticmethod
    def envelope(frame=1, **values):
        fields=dict(frame=frame,lag=0,is_lag=0,cycles=100,width=320,height=240,clock=1262304000,remainder=0)
        fields.update(values)
        return (states.START+b'opaque synthetic payload'+states.END
                +states.MANAGED.pack(*fields.values())
                +states.CONTROLLER.pack(states.CONTROLLER_MAGIC, 0))

    def sidecar(self, frame):
        (self.output/f'core-state-{frame}.json').write_text(json.dumps(self.summary['checkpoints'][frame]))

    def validate(self):
        return states.validate_states(self.output,self.summary,self.native)

    def test_valid_synthetic_envelopes_and_retained_identity(self):
        self.assertEqual(len(self.validate()),2)
        self.assertEqual(states.state_envelope(self.envelope())['controller_serialized_bytes'],12)

    def test_unknown_and_duplicate_native_envelope_markers_rejected(self):
        for data in [b'unknown'+self.envelope(),self.envelope()+states.END,b'']:
            with self.subTest(data=data[:10]),self.assertRaises(ValueError):states.state_envelope(data)

    def test_truncated_managed_or_missing_controller_trailer_rejected(self):
        for length in [1,states.MANAGED.size,states.MANAGED.size+12]:
            with self.subTest(length=length),self.assertRaises(ValueError):
                states.state_envelope(self.envelope()[:-length])

    def test_invalid_managed_counters_and_dimensions_rejected(self):
        for fields in [dict(frame=-1),dict(lag=2),dict(is_lag=2),dict(cycles=-1),dict(width=0),dict(height=1025),dict(remainder=-1)]:
            with self.subTest(fields=fields),self.assertRaises(ValueError):states.state_envelope(self.envelope(**fields))

    def test_scope_overclaims_and_mutation_flags_rejected(self):
        for key in ['state_restored','game_RAM_injected','emulator_UI_controlled','complete_state_parity_checked','original_hardware_timing_verified']:
            original=self.summary[key];self.summary[key]=True
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate()
            self.summary[key]=original

    def test_boolean_protocol_version_is_not_an_integer_version(self):
        self.summary['schema_version']=True
        with self.assertRaises(ValueError):self.validate()

    def test_missing_or_reordered_checkpoint_is_rejected(self):
        rows=self.summary['checkpoints'];self.summary['checkpoints']=rows[:1]
        with self.assertRaises(ValueError):self.validate()
        self.summary['checkpoints']=list(reversed(rows))
        with self.assertRaises(ValueError):self.validate()

    def test_boolean_frame_counters_are_rejected(self):
        for key in ['relative_frame','core_frame','before_core_frame']:
            original=self.summary['checkpoints'][0][key];self.summary['checkpoints'][0][key]=bool(original)
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate()
            self.summary['checkpoints'][0][key]=original

    def test_repeat_or_memory_change_is_rejected(self):
        row=self.summary['checkpoints'][0]
        for key in ['same_frame_serializations_equal','MainRAM_unchanged','GPURAM_unchanged','core_frame_unchanged']:
            row[key]=False
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate()
            row[key]=True

    def test_repeat_size_and_hash_must_match(self):
        row=self.summary['checkpoints'][0]
        for key,value in [('repeat_bytes',row['bytes']+1),('repeat_sha256','c'*64),('sha256','A'*64)]:
            original=row[key];row[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate()
            row[key]=original

    def replace_state(self, data, frame=0, update_observation=False):
        row = self.summary['checkpoints'][frame]
        (self.output/row['file']).write_bytes(data)
        if update_observation:
            row.update(bytes=len(data), repeat_bytes=len(data),
                       sha256=states.digest(data), repeat_sha256=states.digest(data))
            self.sidecar(frame)

    def test_controller_magic_length_and_trailing_bytes_are_checked(self):
        header = self.envelope()[:-states.CONTROLLER.size]
        for controller in [states.CONTROLLER.pack(0, 0),
                           states.CONTROLLER.pack(states.CONTROLLER_MAGIC, -1),
                           states.CONTROLLER.pack(states.CONTROLLER_MAGIC, 1),
                           states.CONTROLLER.pack(states.CONTROLLER_MAGIC, 0)+b'\0']:
            with self.subTest(controller=controller), self.assertRaises(ValueError):
                states.state_envelope(header+controller)
        parsed = states.state_envelope(header+states.CONTROLLER.pack(states.CONTROLLER_MAGIC, 2)+b'\1\2')
        self.assertEqual(parsed['controller_switch_bytes'], 2)

    def test_changed_or_truncated_retained_bytes_are_rejected(self):
        data = self.envelope()
        for changed in [data[:-1], data[:30]+bytes([data[30]^1])+data[31:]]:
            self.replace_state(changed)
            with self.subTest(size=len(changed)), self.assertRaises(ValueError):self.validate()

    def test_resigned_state_with_wrong_frame_or_dimensions_is_rejected(self):
        for fields in [dict(frame=2), dict(width=321), dict(height=241)]:
            self.replace_state(self.envelope(**fields), update_observation=True)
            with self.subTest(fields=fields), self.assertRaises(ValueError):self.validate()

    def test_missing_checkpoint_file_is_rejected(self):
        (self.output/'core-state-0.bin').unlink()
        with self.assertRaises(OSError):self.validate()

    def test_state_filename_cannot_escape_or_alias_another_checkpoint(self):
        row = self.summary['checkpoints'][0]
        for name in ['../core-state-0.bin', '/core-state-0.bin', 'core-state-1.bin', 'C:\\core-state-0.bin']:
            row['file'] = name
            with self.subTest(name=name), self.assertRaises(ValueError):self.validate()

    def test_state_symlink_cannot_escape_the_recording(self):
        outside = self.output.parent/(self.output.name+'-outside.bin')
        outside.write_bytes(self.envelope())
        self.addCleanup(outside.unlink)
        state = self.output/'core-state-0.bin'
        state.unlink()
        try:
            state.symlink_to(outside)
        except OSError as error:
            self.skipTest('Host does not permit file symlinks: '+str(error))
        with self.assertRaises(ValueError):self.validate()

    def test_oversized_and_noninteger_byte_counts_are_rejected_before_read(self):
        row = self.summary['checkpoints'][0]
        for size in [True, 1.5, 0, states.MAX_STATE_BYTES+1]:
            row['bytes'] = size
            with self.subTest(size=size), self.assertRaises(ValueError):self.validate()

    def test_memory_digests_must_match_the_native_checkpoint(self):
        row = self.summary['checkpoints'][0]
        for prefix in ['MainRAM', 'GPURAM']:
            before, after = prefix+'_before_sha256', prefix+'_after_sha256'
            old = row[before], row[after]
            row[before] = row[after] = 'c'*64
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):self.validate()
            row[before], row[after] = old

    def test_sidecar_change_and_unreported_repeat_file_are_rejected(self):
        row = copy.deepcopy(self.summary['checkpoints'][0])
        self.summary['checkpoints'][0]['deterministic_emulation'] = True
        with self.assertRaises(ValueError):self.validate()
        self.summary['checkpoints'][0] = row
        (self.output/'core-state-repeat-0.bin').write_bytes(self.envelope())
        with self.assertRaises(ValueError):self.validate()

    def test_incomplete_or_wrongly_typed_summaries_are_rejected(self):
        for summary, native in [(None, self.native), (self.summary, []),
                                (dict(self.summary, checkpoints={}), self.native),
                                (dict(self.summary, frames_advanced=True), self.native)]:
            with self.subTest(summary=summary), self.assertRaises(ValueError):
                states.validate_states(self.output, summary, native)

    def test_raw_byte_comparison_preserves_cross_chunk_offsets_and_length(self):
        left = bytes(65538)
        right = left[:65535]+b'\1'+left[65536:]+b'\2\3'
        difference = states.compare_bytes(left, right)
        self.assertFalse(difference['byte_equal'])
        self.assertEqual(difference['differing_bytes'], 3)
        self.assertEqual(difference['first_differing_offsets'], [65535, 65538, 65539])
        self.assertEqual(difference['length_difference'], 2)

    def test_observer_modes_preserve_legacy_defaults_and_explicit_disable(self):
        self.assertTrue(observer_requested({'runtime_kind':'dispatch_observer'}, {'trace_enabled':True}))
        self.assertFalse(observer_requested({'runtime_kind':'distributed'}, {'trace_enabled':False}))
        self.assertFalse(observer_requested({'runtime_kind':'dispatch_observer', 'instruction_observer_enabled':False},
                                            {'trace_enabled':False}))

    def test_observer_mode_mismatch_and_boolean_substitutes_are_rejected(self):
        for manifest, settings in [
            ({'runtime_kind':'dispatch_observer'}, {'trace_enabled':False}),
            ({'runtime_kind':'distributed', 'instruction_observer_enabled':True}, {'trace_enabled':True}),
            ({'runtime_kind':'dispatch_observer', 'instruction_observer_enabled':1}, {'trace_enabled':True}),
            ({'runtime_kind':'dispatch_observer'}, {'trace_enabled':1})]:
            with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                observer_requested(manifest, settings)
