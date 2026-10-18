"""Owned table, instruction and ELF fixtures for complete dispatch ownership."""
from copy import deepcopy
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import export_dispatch_catalogue as tool
from tests.test_npc_catalogue import elf, executable


BASE = 0x80010000
CODE = struct.pack('<4I', 0x0040F809, 0, 0x03E00008, 0)
PAYLOAD = CODE + b'\0' * 16 + struct.pack('<4I', 7, BASE, BASE, 0)


def inventory():
    slots = [dict(offset=index * 4, field=field, declared_function_pointer=index > 0,
        value=f'0x{value:08X}', linker_symbols=['method'] if index in (1, 2) else [])
        for index, (field, value) in enumerate((('type_id', 7), ('Run', BASE), ('Again', BASE), ('Unused', 0)))]
    return dict(tables=[dict(name='g_TABLE', type='example_vtable_t', address='0x80010020', bytes=16, slots=slots)])


class DispatchCatalogueTests(unittest.TestCase):
    def ranges(self, table=None, image=None, linked=None, symbols=None):
        return tool.target_ranges(executable(PAYLOAD) if image is None else image,
            elf(PAYLOAD, (('method', 0, 16),)) if linked is None else linked,
            inventory() if table is None else table,
            {'method': [(BASE, 16)]} if symbols is None else symbols)

    def test_shared_and_null_bindings_keep_exact_slots_and_full_ranges(self):
        tables, targets, nulls, sites = self.ranges()
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]['declared_callback_slots'], 3)
        self.assertEqual(tables[0]['nonnull_callback_slots'], 2)
        self.assertEqual(targets[0]['function_bytes'], 16)
        self.assertEqual([row['slot'] for row in targets[0]['bindings']], ['0x004', '0x008'])
        self.assertEqual(nulls, [dict(table='g_TABLE', slot='0x00C', field='Unused')])
        self.assertEqual(sites[0]['return_address'], '0x80010008')
        self.assertEqual(sites[0]['target_register'], 2)
        self.assertEqual(sites[0]['classification'], 'unobserved_indirect_transfer')

    def test_changed_target_tail_cannot_pass_an_equal_entry_word(self):
        payload = bytearray(PAYLOAD)
        payload[12:16] = b'FAIL'
        with self.assertRaisesRegex(ValueError, 'complete target differs'):
            self.ranges(image=executable(payload))

    def test_original_table_word_is_independently_checked(self):
        data = inventory()
        data['tables'][0]['slots'][1]['value'] = '0x80010004'
        with self.assertRaisesRegex(ValueError, 'table word differs'):
            self.ranges(table=data)

    def test_noncallback_table_word_is_also_checked(self):
        data = inventory()
        data['tables'][0]['slots'][0]['value'] = '0x00000008'
        with self.assertRaisesRegex(ValueError, 'table word differs'):
            self.ranges(table=data)

    def test_duplicate_tables_are_rejected(self):
        data = inventory()
        data['tables'].append(deepcopy(data['tables'][0]))
        with self.assertRaisesRegex(ValueError, 'Table names'):
            self.ranges(table=data)

    def test_unordered_or_incomplete_slots_are_rejected(self):
        for change in ('offset', 'extent', 'field', 'boolean'):
            data = inventory()
            table = data['tables'][0]
            if change == 'offset': table['slots'][1]['offset'] = 8
            if change == 'extent': table['bytes'] = 12
            if change == 'field': table['slots'][1]['field'] = 'Again'
            if change == 'boolean': table['slots'][1]['declared_function_pointer'] = 1
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.ranges(table=data)

    def test_missing_or_aliased_complete_owner_is_rejected(self):
        for symbols in ({}, {'method': [(BASE,16)], 'alias': [(BASE,16)]},
                        {'method': [(BASE,16)] * 2}):
            with self.subTest(symbols=symbols), self.assertRaisesRegex(ValueError, 'unambiguous complete GNU'):
                self.ranges(symbols=symbols)

    def test_owner_must_agree_with_audited_names(self):
        data = inventory()
        for slot in data['tables'][0]['slots'][1:3]: slot['linker_symbols'] = ['other']
        with self.assertRaisesRegex(ValueError, 'audited linker names'):
            self.ranges(table=data)

    def test_GNU_and_ELF_must_agree_on_the_whole_extent(self):
        with self.assertRaisesRegex(ValueError, 'GNU and ELF'):
            self.ranges(symbols={'method': [(BASE,8)]})

    def test_overlapping_complete_functions_are_rejected(self):
        payload = bytearray(PAYLOAD)
        struct.pack_into('<I', payload, 40, BASE + 8)
        data = inventory()
        data['tables'][0]['slots'][2].update(value='0x80010008', linker_symbols=['other'])
        with self.assertRaisesRegex(ValueError, 'ranges overlap'):
            self.ranges(table=data, image=executable(payload),
                linked=elf(payload,(('method',0,16),('other',8,8))),
                symbols={'method':[(BASE,16)], 'other':[(BASE+8,8)]})

    def test_appended_bytes_cannot_extend_executable_payload(self):
        data = bytearray(executable(PAYLOAD))
        struct.pack_into('<I', data, 0x1C, 16)
        with self.assertRaisesRegex(ValueError, 'outside the executable payload'):
            self.ranges(image=bytes(data))

    def test_nonreturn_JR_stays_an_unresolved_transfer(self):
        sites = tool.indirect_sites(struct.pack('<4I', 0x03200008,0,0x03E00008,0), BASE)
        self.assertEqual(len(sites),1)
        self.assertEqual(sites[0]['instruction'],'JR')
        self.assertEqual(sites[0]['target_register'],25)
        self.assertIsNone(sites[0]['link_register'])
        self.assertNotIn('return_address',sites[0])

    def test_nonstandard_link_does_not_claim_an_RA_return(self):
        site = tool.indirect_sites(struct.pack('<2I',0x00402009,0), BASE)[0]
        self.assertEqual(site['link_register'],4)
        self.assertNotIn('return_address',site)

    def test_reserved_bits_are_not_accepted_as_transfer_instructions(self):
        for word in (0x0041F809,0x0040F849,0x03E00808):
            with self.subTest(word=word):
                self.assertEqual(tool.indirect_sites(struct.pack('<2I',word,0),BASE),[])

    def test_transfer_delay_slot_must_belong_to_the_complete_function(self):
        with self.assertRaisesRegex(ValueError, 'owned delay slot'):
            tool.indirect_sites(struct.pack('<I',0x0040F809),BASE)

    def test_public_output_is_rejected_before_game_or_build_reads(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'public-export'
            with patch.object(tool.sys,'platform','linux'), patch.object(tool.Path,'cwd',return_value=tool.ROOT), \
                    patch.object(tool,'check_build_current') as current:
                with self.assertRaisesRegex(ValueError,'fresh private directory'):
                    tool.export(path)
            current.assert_not_called()
            self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
