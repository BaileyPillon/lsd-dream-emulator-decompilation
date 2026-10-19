import copy
import hashlib
import struct
import unittest

from tools.npc_catalogue_trace import CATALOGUE_FIELDS
from tools.npc_engine_entries import method_ranges, qualify_engine_entry


class EngineEntryTests(unittest.TestCase):
    def setUp(self):
        image = bytearray(0x1800)
        image[:8] = b'PS-X EXE'
        struct.pack_into('<II', image, 0x18, 0x80010000, 0x1000)
        # Owned synthetic method and caller. No game instructions or data.
        struct.pack_into('<I', image, 0x900, 0x0040f809)  # jalr $ra,$v0
        self.image = bytes(image)
        self.engine_value = self.catalogue('engine_fixture', 0x80010000, 8)
        self.caller_value = self.catalogue('caller_fixture', 0x80010100, 8)
        self.methods = method_ranges(self.engine_value, self.image, {'engine_fixture'})
        self.callers = method_ranges(self.caller_value, self.image, {'caller_fixture'})
        self.targets = {0x80010200: dict(entity_ids=[14])}
        self.row = {name: 0 for name in CATALOGUE_FIELDS}
        self.row.update(relative_frame=5074, pc=0x80010000, entity=0x801d056c,
                        ra=0x80010108, sp=0x801ff000, timestamp=12345,
                        entity_vtable=0x80089ad4, entity_id=14, context_state=15,
                        context_owner=0x801d056c, context_callback=0x80010200, context_tick=87)

    def catalogue(self, name, address, size):
        at = address - 0x80010000 + 0x800
        return dict(schema_version=1, canonical_executable_sha256=hashlib.sha256(self.image).hexdigest(),
                    methods=[dict(name=name, address=address, bytes=size,
                                  sha256=hashlib.sha256(self.image[at:at + size]).hexdigest())])

    def qualify(self, row=None, **kwargs):
        args = dict(row=self.row if row is None else row, executable=self.image,
                    methods=self.methods, callers=self.callers, targets=self.targets)
        args.update(kwargs)
        return qualify_engine_entry(**args)

    def test_enabled_stop_keeps_original_clock_and_checked_saved_return_site(self):
        result = self.qualify()
        self.assertEqual(result['context_tick'], 87)
        self.assertEqual(result['reviewed_caller'], 'caller_fixture')
        self.assertEqual(result['original_callsite'], 0x80010100)
        self.assertEqual(result['call_kind'], 'JALR')
        self.assertFalse(result['registered_callback_dispatch'])
        self.assertFalse(result['whole_encounter_accepted'])

    def test_disabled_payload_never_becomes_a_clock_or_binding(self):
        disabled = dict(self.row, context_state=0, context_tick=0xffffffff,
                        context_owner=0xffffffff, context_callback=0xffffffff)
        result = self.qualify(disabled)
        self.assertTrue(result['disabled_payload_ignored'])
        self.assertIsNone(result['context_tick'])
        self.assertIsNone(result['context_owner'])
        self.assertIsNone(result['context_callback'])
        self.assertEqual(result, self.qualify(dict(disabled, context_tick=7, context_owner=1, context_callback=2)))

    def test_enabled_foreign_owner_callback_and_state_are_rejected(self):
        for key, value in [('context_owner', 0x801d0570), ('context_callback', 0x80010204), ('context_state', 16)]:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'Enabled context differs'):
                self.qualify(dict(self.row, **{key: value}))

    def test_signed_nonpositive_states_do_not_expose_stale_payload(self):
        for state in (0, 0x80000000, 0xffffffff):
            with self.subTest(state=state):
                result = self.qualify(dict(self.row, context_state=state, context_tick=0xffffffff,
                                          context_owner=1, context_callback=2))
                self.assertFalse(result['context_enabled'])
                self.assertIsNone(result['context_tick'])

    def test_unknown_caller_name_stays_unknown_with_a_valid_original_call(self):
        result = self.qualify(callers={})
        self.assertIsNone(result['reviewed_caller'])
        self.assertEqual(result['call_kind'], 'JALR')

    def test_complete_span_identity_and_method_names_are_required(self):
        changed = copy.deepcopy(self.engine_value)
        changed['methods'][0]['sha256'] = hashlib.sha256(bytes(4) + b'FAIL').hexdigest()
        with self.assertRaisesRegex(ValueError, 'complete original method span'):
            method_ranges(changed, self.image, {'engine_fixture'})
        with self.assertRaisesRegex(ValueError, 'identities differ'):
            method_ranges(self.engine_value, self.image, {'guessed_method'})
        changed = copy.deepcopy(self.engine_value)
        changed['methods'][0]['bytes'] = True
        with self.assertRaisesRegex(ValueError, 'aligned complete'):
            method_ranges(changed, self.image, {'engine_fixture'})

    def test_changed_entry_instruction_and_unsupported_saved_return_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'entry instruction differs'):
            self.qualify(dict(self.row, instruction=1))
        with self.assertRaisesRegex(ValueError, 'no supported original call'):
            self.qualify(dict(self.row, ra=0x8001010c))

    def test_original_direct_call_target_is_checked(self):
        image = bytearray(self.image)
        struct.pack_into('<I', image, 0x900, 0x0c004000)  # jal 0x80010000
        result = self.qualify(executable=bytes(image))
        self.assertEqual(result['call_kind'], 'JAL')
        struct.pack_into('<I', image, 0x900, 0x0c004001)
        with self.assertRaisesRegex(ValueError, 'targets another function'):
            self.qualify(executable=bytes(image))

    def test_missing_wrong_width_and_unbound_entities_are_rejected(self):
        missing = dict(self.row)
        del missing['sp']
        with self.assertRaisesRegex(ValueError, 'complete parsed'):
            self.qualify(missing)
        for row in [dict(self.row, context_tick=True), dict(self.row, timestamp=-1),
                    dict(self.row, entity=3), dict(self.row, sp=3), dict(self.row, entity_id=130), dict(self.row, pc=0x80010004)]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.qualify(row)

    def test_overlapping_caller_ranges_cannot_supply_an_ambiguous_name(self):
        overlap = {0x80010004: dict(name='ambiguous', address=0x80010004, bytes=0x100)}
        with self.assertRaisesRegex(ValueError, 'ranges overlap'):
            self.qualify(callers=overlap)


if __name__ == '__main__':
    unittest.main()
