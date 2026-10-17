import struct
import unittest

from tools.inventory_runtime_scene import ENTITY_VTABLE, inspect_entities, linked_values, walk_objects


class RuntimeSceneInventoryTests(unittest.TestCase):
    def setUp(self):
        self.raw = bytearray(0x200000)
        self.executable = bytearray(0x2800)
        self.executable[:8] = b'PS-X EXE'
        struct.pack_into('<I', self.executable, 0x18, 0x80089000)
        struct.pack_into('<I', self.executable, 0x1C, 0x2000)
        self.executable[0x800:] = bytes((index * 17 + 1) & 255 for index in range(0x2000))
        self.raw[0x89000:0x8B000] = self.executable[0x800:]
        self.root, self.entity = 0x80010000, 0x80010200
        self.roots = {'dream': self.root}
        self.put(self.root, 0x80089000)
        self.put(self.root + 4, 0x80012000)
        self.put(0x80012004, self.entity)
        self.put(self.entity, ENTITY_VTABLE)
        self.put(self.entity + 8, 0x80012010)
        self.put(0x80012014, self.root)
        # Disabled contexts may contain arbitrary old payload, including pointers.
        self.raw[0x1029C:0x102F0] = b'\xDD' * 0x54
        self.put(self.entity + 0x9C, 0)
        self.put(self.entity + 0x94, self.root)
        self.put(self.entity + 0x98, 0)
        self.put(self.entity + 0xF8, 0)
        self.audit = {'table': {'address': '0x80089200', 'bytes': 16},
                      'records': [{'callback_function': 'entity_example', 'callback_address': '0x80010100'}]}

    def put(self, address, value):
        struct.pack_into('<I', self.raw, address & 0x1FFFFFFF, value)

    def graph(self):
        return walk_objects(self.raw, self.roots, self.executable)

    def inspect(self):
        return inspect_entities(self.raw, self.graph(), self.root, self.audit, self.executable)

    def test_loaded_object_does_not_imply_registered_or_executed_behavior(self):
        before = bytes(self.raw)
        report = self.inspect()
        self.assertEqual(report['loaded_entity_objects'], 1)
        self.assertEqual(report['enabled_contexts'], 0)
        self.assertIsNone(report['entities'][0]['registered_context'])
        self.assertEqual(report['instruction_entries_observed'], 0)
        self.assertEqual(report['whole_NPC_encounters_accepted'], 0)
        self.assertEqual(bytes(self.raw), before)

    def enable(self):
        self.put(self.entity + 0x9C, 1)
        self.put(self.entity + 0xA4, self.entity)
        self.put(self.entity + 0xA8, 0x80010100)
        self.put(self.entity + 0xF8, 1)

    def test_registration_matches_the_table_without_claiming_execution(self):
        self.enable()
        report = self.inspect()
        self.assertEqual(report['enabled_contexts'], 1)
        self.assertTrue(report['entities'][0]['registered_context']['matches_original_binding'])
        self.assertEqual(report['instruction_entries_observed'], 0)

    def test_negative_context_state_is_disabled_by_the_native_signed_guard(self):
        self.put(self.entity + 0x9C, 0xFFFFFFFF)
        report = self.inspect()
        self.assertEqual(report['entities'][0]['context_state'], -1)
        self.assertEqual(report['enabled_contexts'], 0)
        self.assertIsNone(report['entities'][0]['registered_context'])

    def test_cleared_callback_and_other_binding_are_reported_separately(self):
        self.enable()
        for value in (0, 0x80010104):
            self.put(self.entity + 0xA8, value)
            context = self.inspect()['entities'][0]['registered_context']
            self.assertFalse(context['matches_original_binding'])
            self.assertEqual(context['callback_cleared'], value == 0)

    def test_object_graph_cycles_are_valid_when_links_are_reciprocal(self):
        self.put(self.entity + 4, 0x80012020)
        self.put(0x80012024, self.root)
        self.put(self.root + 8, 0x80012030)
        self.put(0x80012034, self.entity)
        self.assertEqual(self.graph()['child_edges_checked'], 2)
        self.assertEqual(self.graph()['object_count'], 2)

    def test_list_cycle_is_rejected(self):
        self.put(0x80012000, 0x80012000)
        with self.assertRaisesRegex(ValueError, 'linked list contains a cycle'):
            self.graph()

    def test_nonreciprocal_or_duplicate_child_edge_is_rejected(self):
        self.put(self.entity + 8, 0)
        with self.assertRaisesRegex(ValueError, 'reciprocal'):
            self.graph()
        self.put(self.entity + 8, 0x80012010)
        self.put(0x80012000, 0x80012020)
        self.put(0x80012024, self.entity)
        with self.assertRaisesRegex(ValueError, 'reciprocal'):
            self.graph()

    def test_unaligned_unmapped_and_truncated_native_pointers_are_rejected(self):
        for pointer in (0x80012001, 0x80200000, 0x1000, 0xA0012000):
            with self.subTest(pointer=pointer), self.assertRaises(ValueError):
                linked_values(self.raw, pointer)

    def test_changed_vtable_and_property_bytes_are_rejected(self):
        self.raw[ENTITY_VTABLE & 0x1FFFFFFF] ^= 1
        with self.assertRaisesRegex(ValueError, 'vtable prefix'):
            self.graph()
        self.raw[ENTITY_VTABLE & 0x1FFFFFFF] ^= 1
        self.raw[0x89200] ^= 1
        with self.assertRaisesRegex(ValueError, 'property table'):
            self.inspect()

    def test_invalid_entity_id_and_wrong_dream_owner_are_rejected(self):
        for field, value, message in ((0x98, 1, 'invalid original ID'),
                                     (0x94, self.entity, 'different dream owner')):
            saved = struct.unpack_from('<I', self.raw, 0x10200 + field)[0]
            self.put(self.entity + field, value)
            with self.assertRaisesRegex(ValueError, message):
                self.inspect()
            self.put(self.entity + field, saved)

    def test_enabled_context_must_have_the_original_entity_and_owner(self):
        self.enable()
        for field, value, message in ((0x9C, 2, 'different entity ID'),
                                     (0xA4, self.root, 'different entity owner')):
            saved = struct.unpack_from('<I', self.raw, 0x10200 + field)[0]
            self.put(self.entity + field, value)
            with self.assertRaisesRegex(ValueError, message):
                self.inspect()
            self.put(self.entity + field, saved)

    def test_truncated_mainram_and_missing_roots_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'complete MainRAM'):
            walk_objects(self.raw[:-1], self.roots, self.executable)
        with self.assertRaisesRegex(ValueError, 'graph root'):
            walk_objects(self.raw, {}, self.executable)
