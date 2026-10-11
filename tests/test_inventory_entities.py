import struct
import unittest

from tools.inventory_entities import audit_entities, entity_initializers, signed_byte_literal, verify_layout


class EntityInventoryTests(unittest.TestCase):
    def setUp(self):
        self.executable = bytearray(0x900)
        self.executable[:8] = b'PS-X EXE'
        struct.pack_into('<II', self.executable, 0x18, 0x80010000, 0x100)
        self.symbols = {'g_ENTITY_TABLE': 0x80010010, 'entity_first': 0x80010080}
        self.source = '''
            entity_prop_t g_ENTITY_TABLE[2] = {
                { { -128, 127 }, -1, 4, 2, -3, 1, -14, 9, -6, 10, -1, entity_first },
                { { 0, 0 }, -100, 0, 0, 0, 1, -5, 1, 1, 0, 0, NULL },
            };
            void entity_first(entity_t *owner, s32 *context) { }
        '''
        struct.pack_into('<12bI', self.executable, 0x810, -128, 127, -1, 4, 2, -3, 1, -14, 9, -6, 10, -1, 0x80010080)
        struct.pack_into('<12bI', self.executable, 0x820, 0, 0, -100, 0, 0, 0, 1, -5, 1, 1, 0, 0, 0)

    def test_signed_properties_and_null_slots_come_from_verified_bytes(self):
        result = audit_entities(self.executable, self.source, self.symbols)
        self.assertEqual(result['records'][0]['properties']['mood_x'], -128)
        self.assertEqual(result['records'][0]['properties']['link_flag'], -1)
        self.assertEqual(result['totals']['nonnull_callback_slots'], 1)
        self.assertEqual(result['totals']['null_callback_slots'], 1)
        self.assertEqual(result['totals']['distinct_callbacks_recovered_c'], 1)
        self.assertEqual(result['totals']['runtime_validated_callbacks'], 0)
        self.assertFalse(result['original_behavior_modified'])

    def test_duplicate_callback_slots_do_not_inflate_the_function_count(self):
        source = self.source.replace('0, 0, NULL', '0, 0, entity_first')
        struct.pack_into('<I', self.executable, 0x82C, 0x80010080)
        result = audit_entities(self.executable, source, self.symbols)
        self.assertEqual(result['totals']['nonnull_callback_slots'], 2)
        self.assertEqual(result['totals']['distinct_callback_addresses'], 1)
        self.assertEqual(result['callbacks'][0]['entity_indices'], [0, 1])

    def test_changed_callback_or_signed_property_rejects_the_snapshot(self):
        for offset, value in ((0x810, 0), (0x81C, 0)):
            executable = self.executable.copy()
            executable[offset] = value
            with self.assertRaisesRegex(ValueError, 'C/native property or callback mismatch'):
                audit_entities(executable, self.source, self.symbols)

    def test_unmapped_or_truncated_table_is_rejected(self):
        symbols = dict(self.symbols, g_ENTITY_TABLE=0x800100F0)
        with self.assertRaisesRegex(ValueError, 'outside the executable payload'):
            audit_entities(self.executable, self.source, symbols)

    def test_pointer_without_a_configured_definition_is_not_counted(self):
        source = self.source.replace('void entity_first(entity_t *owner, s32 *context) { }', '')
        with self.assertRaisesRegex(ValueError, 'one configured C or assembly definition'):
            audit_entities(self.executable, source, self.symbols)

    def test_capacity_and_record_fields_are_not_silently_zero_filled(self):
        for source in (self.source.replace('[2]', '[3]'), self.source.replace('{ -128, 127 }', '{ -128 }')):
            with self.assertRaises(ValueError):
                entity_initializers(source, self.symbols)

    def test_literal_parser_accepts_c_octal_and_rejects_code_and_overflow(self):
        self.assertEqual(signed_byte_literal('-010'), -8)
        self.assertEqual(signed_byte_literal('0x7f'), 127)
        for expression in ('128', '-129', '(s8)255', '1 + 1', '__import__("os")'):
            with self.assertRaises(ValueError):
                signed_byte_literal(expression)

    def test_a_guessed_pointer_expression_is_not_an_original_binding(self):
        source = self.source.replace('entity_first },', 'entity_first + 4 },')
        with self.assertRaisesRegex(ValueError, 'named symbol or a null literal'):
            entity_initializers(source, self.symbols)

    def test_header_layout_change_requires_review(self):
        header = '''typedef struct {
            s8 mood_effect[2]; s8 unlock; s8 behaviour; s8 interaction_type;
            s8 interaction_range; s8 interaction_angle; s8 link_stage;
            s8 event_video_id; s8 interaction_param; s8 proximity; s8 link_flag;
            void (*behaviour_fn)(entity_t *This, s32 *arg1);
        } entity_prop_t;'''
        verify_layout(header)
        with self.assertRaisesRegex(ValueError, 'Unsupported entity_prop_t layout'):
            verify_layout(header.replace('s8 unlock', 's32 unlock'))


if __name__ == '__main__':
    unittest.main()
