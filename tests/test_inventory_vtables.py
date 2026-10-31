import struct
import unittest

from tools.inventory_vtables import audit_tables, initializer_value, table_words


class NativeTableAuditTests(unittest.TestCase):
    def setUp(self):
        self.executable = bytearray(0x840)
        self.executable[:8] = b'PS-X EXE'
        struct.pack_into('<I', self.executable, 0x18, 0x80010000)
        struct.pack_into('<III', self.executable, 0x810, 8, 0, 0x80012000)
        self.headers = {'src/sample.h': '''
            typedef struct sample_vtable sample_vtable_t;
            struct sample_vtable {
                u32 type_id;
                void (*Destroy)(void *);
                void (*Construct)(void *, s32);
            };
            extern sample_vtable_t g_TABLE;
        '''}
        self.sources = {'src/sample.c': '''
            sample_vtable_t g_TABLE = {
                .Construct = (void (*)(void *, s32)) work,
                .type_id = 010,
                .Destroy = (void *)NULL,
            };
        '''}
        self.symbols = {'g_TABLE': 0x80010010, 'work': 0x80012000}

    def test_original_bindings_accept_casts_designators_and_c_octal(self):
        report = audit_tables(self.executable, self.sources, self.headers, self.symbols)
        self.assertEqual(report['declared_tables_audited'], 1)
        self.assertEqual(report['explicit_c_initializers_verified'], 1)
        self.assertEqual(report['tables'][0]['slots'][2]['linker_symbols'], ['work'])
        self.assertFalse(report['all_dynamic_dispatch_resolved'])

    def test_changed_original_callback_is_rejected(self):
        struct.pack_into('<I', self.executable, 0x818, 0x80012100)
        with self.assertRaisesRegex(ValueError, 'binding mismatch'):
            audit_tables(self.executable, self.sources, self.headers, self.symbols)

    def test_conflicting_declarations_are_not_silently_combined(self):
        self.sources['src/other.c'] = 'extern other_vtable_t g_TABLE;'
        with self.assertRaisesRegex(ValueError, 'Conflicting table declarations'):
            audit_tables(self.executable, self.sources, self.headers, self.symbols)

    def test_unsupported_member_layout_stays_explicitly_unresolved(self):
        header = self.headers['src/sample.h'].replace('u32 type_id;', 'u8 type_id;')
        report = audit_tables(self.executable, {}, {'src/sample.h': header}, self.symbols)
        self.assertEqual(report['declared_tables_audited'], 0)
        self.assertEqual(len(report['unresolved_declarations']), 1)
        self.assertEqual(len(report['unsupported_types']), 1)

    def test_original_table_cannot_extend_beyond_the_executable(self):
        with self.assertRaisesRegex(ValueError, 'outside'):
            table_words(self.executable, 0x8001003C, 2)

    def test_supported_unbound_view_does_not_add_a_table_or_callback_count(self):
        baseline = audit_tables(self.executable, self.sources, self.headers, self.symbols)
        self.headers['src/view.h'] = '''
            typedef struct runnable_vtable {
                u32 type_id;
                u32 FamilySpecificAddress;
                s32 (*Run)(void *, void *, s32);
            } runnable_vtable_t;
        '''
        report = audit_tables(self.executable, self.sources, self.headers, self.symbols)
        view, = report['unbound_type_views']
        self.assertEqual(view['type'], 'runnable_vtable_t')
        self.assertEqual(view['bytes'], 12)
        self.assertFalse(view['concrete_table_binding_claimed'])
        self.assertEqual([(s['offset'], s['declared_function_pointer']) for s in view['slots']],
                         [(0, False), (4, False), (8, True)])
        for key in ('declared_tables_audited', 'declared_function_slots',
                    'nonnull_declared_function_slots', 'unique_declared_function_addresses'):
            self.assertEqual(report[key], baseline[key])

    def test_unsupported_unbound_view_keeps_its_layout_failure(self):
        self.headers['src/view.h'] = 'typedef struct { u8 gap[60]; } opaque_vtable_t;'
        report = audit_tables(self.executable, self.sources, self.headers, self.symbols)
        self.assertEqual(report['unbound_type_views'], [])
        self.assertEqual(report['unsupported_types'][0]['type'], 'opaque_vtable_t')

    def test_pointer_arithmetic_is_not_mistaken_for_a_symbol(self):
        with self.assertRaisesRegex(ValueError, 'Unresolved C initializer'):
            initializer_value('work + 4', self.symbols)
        self.assertEqual(initializer_value('-1', self.symbols), 0xFFFFFFFF)

    def test_adjacent_data_in_a_label_does_not_invent_callback_members(self):
        struct.pack_into('<II', self.executable, 0x81C, 0x1F801800, 0x1F801801)
        extents = {'g_TABLE': {'bytes': 20, 'assembly': 'asm/sample.s'}}
        report = audit_tables(self.executable, self.sources, self.headers, self.symbols, extents)
        self.assertEqual(report['declared_tables_audited'], 1)
        self.assertEqual(report['tables'][0]['bytes'], 12)
        self.assertEqual(report['header_layout_issues'], [])
        self.assertEqual(report['unresolved_declarations'], [])
        self.assertEqual(report['assembly_extent_notes'][0]['words_after_declared_layout'],
                         ['0x1F801800', '0x1F801801'])

    def test_header_spill_past_a_shorter_label_is_reported_and_not_audited(self):
        self.headers['src/sample.h'] = self.headers['src/sample.h'].replace(
            'void (*Construct)(void *, s32);',
            'void (*Construct)(void *, s32); void (*extra)(void *);')
        extents = {'g_TABLE': {'bytes': 12, 'assembly': 'asm/sample.s'}}
        report = audit_tables(self.executable, self.sources, self.headers, self.symbols, extents)
        self.assertEqual(report['header_layout_issues'][0]['declared_bytes'], 16)
        self.assertEqual(report['tables'][0]['bytes'], 12)
        self.assertEqual(len(report['tables'][0]['slots']), 3)


if __name__ == '__main__':
    unittest.main()
