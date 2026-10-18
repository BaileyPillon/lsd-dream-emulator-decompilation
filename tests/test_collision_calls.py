"""Constructed transport/geometry controls; no commercial executable required."""
import struct
import unittest

from tools import inspect_collision_calls as tool
from tools.collision_calls import FIELDS, FUNCTION_BYTES, PC, RAM_BYTES, selection


def fixture(hit=True, height=True, cross_frame=False):
    load, caller, stack = 0x80010000, 0x8001DF20, 0x801FE000
    image = bytearray(0x11800)
    image[:8] = b'PS-X EXE'
    struct.pack_into('<II', image, 0x18, load, len(image) - 0x800)

    def instruction(address, value):
        struct.pack_into('<I', image, 0x800 + address - load, value)

    call = 0x0C000000 | ((PC >> 2) & 0x03FFFFFF)
    delay = 0x27A70044 if height else 0
    instruction(caller, call)
    instruction(caller + 4, delay)
    instruction(PC, 0x27BDFEA0)
    instruction(PC + FUNCTION_BYTES - 12, 0x27BD0160)
    instruction(PC + FUNCTION_BYTES - 8, 0x03E00008)
    before = bytearray(RAM_BYTES)
    before[load & 0x1FFFFFFF:(load & 0x1FFFFFFF) + len(image) - 0x800] = image[0x800:]
    model, geometry, vertices, packets = 0x80060040, 0x80060080, 0x80060100, 0x80060200
    nearest, contact, elevation = stack + 0x40, 0x80061000, stack + 0x44 if height else 0
    start, end = 0x80062000, 0x80062010

    def pack(fmt, address, *values):
        struct.pack_into(fmt, before, address & 0x1FFFFFFF, *values)

    pack('<I', model + 16, geometry)
    pack('<6I', geometry, vertices, 3, 0, 0, packets, 1)
    for index, value in enumerate(((-128, -128, 0), (128, -128, 0), (0, 128, 0))):
        pack('<3h', vertices + index * 8, *value)
    pack('<4B', packets, 0, 0, 0, 0x21)
    pack('<3H', packets + 8, 0, 1, 2)
    pack('<2I', stack + 16, start, end)
    pack('<3h', start, 0 if hit else 4096, 0, -256)
    pack('<3h', end, 0 if hit else 4096, 0, 256)
    pack('<3h', contact, 111, 222, 333)
    # These power-of-two distances use the first coefficient in SquareRoot0.
    pack('<H', 0x8006BEF0, 4096)
    after = bytearray(before)
    struct.pack_into('<I', after, nearest & 0x1FFFFFFF, 256 if hit else 0x7FFFFFFF)
    if hit:
        struct.pack_into('<3h', after, contact & 0x1FFFFFFF, 0, 0, 0)
        if height:
            struct.pack_into('<I', after, elevation & 0x1FFFFFFF, 128)
    row = dict.fromkeys(FIELDS, 0)
    row.update(frame=6 if cross_frame else 5, ordinal=1, entry_id=1, base_ordinal=1,
               entry_frame=5, entry_timestamp=10, entry_pc=PC, return_pc=caller + 8,
               timestamp=5 if cross_frame else 20, entry_sequence_low=100, sequence_low=200,
               ram_bytes=RAM_BYTES, before_offset=0, after_offset=RAM_BYTES, payload_status=1,
               entry_cpu_gpr_4=model, entry_cpu_gpr_5=nearest, entry_cpu_gpr_6=contact,
               entry_cpu_gpr_7=elevation, entry_cpu_gpr_29=stack, entry_cpu_gpr_31=caller + 8,
               cpu_gpr_2=int(hit), cpu_gpr_29=stack, cpu_gpr_31=caller + 8,
               entry_cpu_sr=0x40000401, cpu_sr=0x40000401)
    for prefix, jump, jump_word, delay_word in (
            ('entry_', caller, call, delay), ('', PC + FUNCTION_BYTES - 8, 0x03E00008, 0)):
        for part, address, value in (('jump', jump, jump_word), ('delay', jump + 4, delay_word)):
            row.update({prefix + part + '_' + key: value for key, value in
                        dict(pc=address, ram=value, fetch=value, sp=stack, flags=1, sr=0x40000401).items()})
        row[prefix + 'jump_rs'] = caller + 8 if not prefix else 0
        row[prefix + 'delay_rs'] = stack if prefix and height else 0
    entry = dict(pc=PC, relative_frame=5, timestamp=10, a0=model, a1=nearest, a2=contact, a3=elevation,
                 sp=stack, ra=caller + 8, transfer_pc=caller, delay_pc=caller + 4,
                 transfer_word=call, delay_word=delay,
                 transfer_classification=dict(kind='observed_direct_JAL'))
    program = dict(frames=20, method_trace=dict(arm_frame=1, range_family='collision',
                   targets=['func_8001DDF4', 'func_8001F8B8'], collision_calls=dict(max_samples=64, per_key=2)))
    summary = dict(protocol=1, event_bytes=988, settings=selection(program), returns=1, native_returns=1,
                   native_started=1, eligible_entries=1, native_overflow=0, pending_calls=0,
                   payload_bytes=RAM_BYTES * 2, duplicate_key_skips=0, frame_budget_skips=0,
                   sample_limit_skips=0, nested_skips=0, frame_payload_limit=RAM_BYTES * 4,
                   ram_snapshot_bytes=RAM_BYTES, CPU_register_words=37, GTE_architectural_register_words=64,
                   original_game_RAM_injected=False, original_CPU_source_modified=False,
                   observer_writes_GTE_registers=False, complete_state_parity_checked=False,
                   opaque_internal_GTE_state_serialized=False)
    return row, before, after, summary, [entry], program, bytes(image)


class CollisionCallTests(unittest.TestCase):
    def setUp(self):
        self.row, self.before, self.after, self.summary, self.entries, self.program, self.image = fixture()

    def verify(self):
        data = struct.pack('<247I', *(self.row[name] for name in FIELDS))
        return tool.validate_records(data, self.before + self.after, self.summary,
                                     self.entries, self.program, self.image)

    def test_hit_distance_contact_and_height_come_from_complete_geometry(self):
        report = self.verify()
        call = report['calls'][0]
        self.assertEqual((call['result'], call['nearest'], call['contact'], call['height']), (1, 256, [0, 0, 0], 128))
        self.assertEqual(report['sampled_polygon_visits'], 1)
        self.assertEqual(report['packet_mode_counts'], {'0x21': 1})
        for key in ('complete_state_parity_checked', 'geometry_allocation_ownership_accepted',
                    'opaque_internal_GTE_state_serialized', 'every_RAM_change_attributed_to_callee',
                    'full_instruction_paths_accepted'):
            self.assertFalse(report[key])
        self.assertEqual(report['new_C_bytes'], 0)

    def test_no_contact_preserves_old_contact_and_optional_height(self):
        self.row, self.before, self.after, self.summary, self.entries, self.program, self.image = fixture(hit=False)
        self.assertEqual(self.verify()['result_counts'], {'0': 1})
        struct.pack_into('<h', self.after, self.row['entry_cpu_gpr_6'] & 0x1FFFFFFF, 112)
        with self.assertRaisesRegex(ValueError, 'no-contact'):
            self.verify()

    def test_null_height_and_cross_frame_call_are_supported_without_full_state_claims(self):
        self.row, self.before, self.after, self.summary, self.entries, self.program, self.image = fixture(height=False, cross_frame=True)
        report = self.verify()
        self.assertEqual(report['calls_crossing_a_frame'], 1)
        self.assertIsNone(report['calls'][0]['height'])

    def test_wrong_nearest_contact_or_height_is_rejected(self):
        for address, fmt in ((self.row['entry_cpu_gpr_5'], '<I'), (self.row['entry_cpu_gpr_6'], '<h'),
                             (self.row['entry_cpu_gpr_7'], '<I')):
            original = self.after[:]
            struct.pack_into(fmt, self.after, address & 0x1FFFFFFF, 17)
            with self.subTest(address=address), self.assertRaisesRegex(ValueError, 'differs'):
                self.verify()
            self.after = original

    def test_summary_refuses_lost_calls_pending_calls_and_modified_game_claims(self):
        for key in ('native_overflow', 'pending_calls', 'nested_skips'):
            with self.subTest(key=key):
                self.summary[key] = 1
                with self.assertRaisesRegex(ValueError, 'Unqualified'):
                    self.verify()
                self.summary[key] = 0
        self.summary['original_game_RAM_injected'] = True
        with self.assertRaisesRegex(ValueError, 'Unqualified'):
            self.verify()

    def test_boolean_counters_cannot_impersonate_integer_protocol_values(self):
        self.summary['native_returns'] = True
        with self.assertRaisesRegex(ValueError, 'non-integer'):
            self.verify()

    def test_sample_selection_rejects_bool_limits_unbounded_counts_and_mixed_observers(self):
        for value in (True, 0, 65, '64'):
            self.program['method_trace']['collision_calls']['max_samples'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, '1..64'):
                selection(self.program)
        self.program['method_trace']['collision_calls']['max_samples'] = 64
        self.program['method_trace']['flow_sites'] = ['invented']
        with self.assertRaisesRegex(ValueError, 'entry-only'):
            selection(self.program)

    def test_truncated_extra_or_misaddressed_RAM_is_not_a_complete_sample(self):
        data = struct.pack('<247I', *(self.row[name] for name in FIELDS))
        for payload in ((self.before + self.after)[:-1], self.before + self.after + b'\0'):
            with self.subTest(length=len(payload)), self.assertRaisesRegex(ValueError, 'complete-RAM'):
                tool.validate_records(data, payload, self.summary, self.entries, self.program, self.image)
        self.row['after_offset'] += 4
        with self.assertRaisesRegex(ValueError, 'RAM extent'):
            self.verify()

    def test_false_caller_return_and_callee_saved_registers_are_rejected(self):
        for key in ('return_pc', 'cpu_gpr_29', 'cpu_gpr_20', 'entry_cpu_gpr_31'):
            self.row[key] ^= 4
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.verify()
            self.row[key] ^= 4

    def test_unqualified_fetch_and_reversed_instruction_sequence_are_rejected(self):
        self.row['entry_jump_flags'] = 0
        with self.assertRaisesRegex(ValueError, 'cache/RAM'):
            self.verify()
        self.row['entry_jump_flags'] = 1
        self.row['sequence_low'] = self.row['entry_sequence_low']
        with self.assertRaisesRegex(ValueError, 'sequence'):
            self.verify()

    def test_changed_callee_code_is_checked_beyond_the_entry_instruction(self):
        for data in (self.before, self.after):
            data[(PC & 0x1FFFFFFF) + 16] ^= 1
        with self.assertRaisesRegex(ValueError, 'Complete primitive code'):
            self.verify()

    def test_unknown_packet_extent_and_out_of_range_vertices_are_rejected(self):
        packet, geometry = 0x60200, 0x60080
        self.before[packet + 3] = 0x10
        with self.assertRaisesRegex(ValueError, 'Unsupported original primitive'):
            tool.decode_geometry(self.before, self.row['entry_cpu_gpr_4'])
        self.before[packet + 3] = 0x21
        struct.pack_into('<I', self.before, geometry + 4, 2)
        with self.assertRaisesRegex(ValueError, 'outside the captured declared array'):
            tool.decode_geometry(self.before, self.row['entry_cpu_gpr_4'])

    def test_overlarge_geometry_count_is_rejected_before_packet_iteration(self):
        struct.pack_into('<I', self.before, 0x60080 + 20, 0xFFFFFFFF)
        with self.assertRaisesRegex(ValueError, 'counts exceed'):
            tool.decode_geometry(self.before, self.row['entry_cpu_gpr_4'])

    def test_output_aliases_are_checked_through_physical_RAM_aliases(self):
        self.row['entry_cpu_gpr_5'] = 0xA0062000
        with self.assertRaisesRegex(ValueError, 'output alias'):
            tool.verify_geometry_result(self.row, self.before, self.after)

    def test_bad_RAM_addresses_do_not_wrap_into_a_valid_snapshot(self):
        for address, size in ((0x80200000, 4), (0x80000000 + RAM_BYTES - 2, 4), (0xC0060000, 4),
                              (-4, 4), (0x80060001, 4)):
            with self.subTest(address=address), self.assertRaises(ValueError):
                tool.ram(self.before, address, size, 4)
        self.assertEqual(tool.ram(self.before, 0xA0062000, 6), tool.ram(self.before, 0x80062000, 6))

    def test_geometry_change_across_a_call_is_not_hidden_by_unchanged_results(self):
        self.after[0x60100] ^= 1
        with self.assertRaisesRegex(ValueError, 'input changed'):
            self.verify()


class CollisionSamplingPolicyTests(unittest.TestCase):
    def test_only_first_two_samples_per_caller_model_key_are_selected(self):
        entries = [dict(pc=PC, relative_frame=n, timestamp=10, transfer_pc=0x8001DF20, a0=0x80100000)
                   for n in range(5, 9)]
        rows = [dict(base_ordinal=n + 1, frame=5 + n, timestamp=20) for n in range(2)]
        settings = dict(max_samples=64, per_key=2)
        summary = dict(eligible_entries=4, nested_skips=0, sample_limit_skips=0,
                       duplicate_key_skips=2, frame_budget_skips=0)
        report = tool.verify_policy(rows, entries, settings, summary)
        self.assertEqual(report['duplicate_key_skips'], 2)
        rows[1]['base_ordinal'] = 3
        with self.assertRaisesRegex(ValueError, 'required caller/model'):
            tool.verify_policy(rows, entries, settings, summary)

    def test_frame_budget_skip_does_not_consume_a_new_model_key(self):
        entries = [dict(pc=PC, relative_frame=5, timestamp=10, transfer_pc=0x8001DF20, a0=0x80100000),
                   dict(pc=PC, relative_frame=5, timestamp=30, transfer_pc=0x8001DF20, a0=0x80100004),
                   dict(pc=PC, relative_frame=6, timestamp=10, transfer_pc=0x8001DF20, a0=0x80100004)]
        rows = [dict(base_ordinal=1, frame=5, timestamp=20), dict(base_ordinal=3, frame=6, timestamp=20)]
        settings = dict(max_samples=64, per_key=2)
        summary = dict(eligible_entries=3, nested_skips=0, sample_limit_skips=0,
                       duplicate_key_skips=0, frame_budget_skips=1)
        self.assertEqual(tool.verify_policy(rows, entries, settings, summary)['selected_calls'], 2)
        summary['frame_budget_skips'] = 0
        with self.assertRaisesRegex(ValueError, 'counters disagree'):
            tool.verify_policy(rows, entries, settings, summary)

    def test_bounded_sample_limit_precedes_duplicate_key_counting(self):
        entries = [dict(pc=PC, relative_frame=n, timestamp=10, transfer_pc=0x8001DF20, a0=0x80100000)
                   for n in (5, 6)]
        rows = [dict(base_ordinal=1, frame=5, timestamp=20)]
        summary = dict(eligible_entries=2, nested_skips=0, sample_limit_skips=1,
                       duplicate_key_skips=0, frame_budget_skips=0)
        self.assertEqual(tool.verify_policy(rows, entries, dict(max_samples=1, per_key=2), summary)['sample_limit_skips'], 1)


if __name__ == '__main__':
    unittest.main()
