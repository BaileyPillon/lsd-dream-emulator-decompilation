"""Owned PS-X/table/function fixtures for the common-view audit."""
from copy import deepcopy
import hashlib
import struct
import unittest

from tools import inspect_screen_prefix as tool
from research.screen_lifecycle.verify_prefix import callback_load


def fixture():
    load = 0x80010000
    image = bytearray(0x80800)
    image[:8] = b'PS-X EXE'
    struct.pack_into('<I', image, 0x18, load)
    offset = lambda address: 0x800 + address - load
    view = dict(type=tool.TYPE, header='src/game/game_flow.h', bytes=0x48,
        concrete_table_binding_claimed=False,
        slots=[dict(offset=i*4, field=name, declared_function_pointer=i*4 in set(tool.SHARED)|{0x44})
               for i,name in enumerate(tool.FIELDS)])
    tables, targets = [], {}
    for name,spec in tool.TABLES.items():
        words = {0:spec['type_id'], 0x3C:0, 0x44:spec['run'],
                 **{off:row[2] for off,row in tool.SHARED.items()},
                 **dict(zip(tool.FAMILY_SPECIFIC, spec['specific']))}
        slots = []
        for off,address in sorted(words.items()):
            struct.pack_into('<I', image, offset(spec['address']+off), address)
            field = tool.SHARED[off][0] if off in tool.SHARED else tool.FIELDS[off//4]
            slots.append(dict(offset=off, field=field, value=f'0x{address:08X}',
                              declared_function_pointer=off not in (0, 0x3C)))
            if off in (0, 0x3C):
                continue
            pc = f'0x{address:08X}'
            body = struct.pack('<4I', address, address ^ 0x55AA, 0x03E00008, 0)
            image[offset(address):offset(address)+len(body)] = body
            if pc not in targets:
                targets[pc] = dict(pc=pc,
                    function=tool.SHARED[off][1] if off in tool.SHARED else 'family_'+pc,
                    function_bytes=len(body), function_sha256=hashlib.sha256(body).hexdigest(), bindings=[])
            targets[pc]['bindings'].append(dict(table=name, slot=f'0x{off:03X}', field=field))
        tables.append(dict(name=name, type=name+'_t', address=hex(spec['address']), bytes=0x48, slots=slots))
    base_words = [0]*16
    base_slots = []
    for off,(field,_function,address) in tool.SHARED.items():
        base_words[off//4] = address
        base_slots.append(dict(offset=off, field=field, value=hex(address), declared_function_pointer=True))
    struct.pack_into('<16I', image, offset(0x8006B58C), *base_words)
    tables.append(dict(name='g_BASE_CLASS_VTABLE', type='base_class_vtable_t',
                       address='0x8006B58C', bytes=0x40, slots=base_slots))
    inventory = dict(tables=tables, unbound_type_views=[view], unsupported_types=[],
                     declared_tables_audited=57, declared_function_slots=2463)
    return image, inventory, dict(targets=list(targets.values()))


class CommonScreenPrefixTests(unittest.TestCase):
    def setUp(self):
        self.image, self.inventory, self.catalogue = fixture()

    def check(self):
        return tool.inspect(self.image, self.inventory, self.catalogue)

    def test_two_prefixes_keep_original_counts_and_family_signature_limits(self):
        result = self.check()
        self.assertEqual(result['concrete_callback_bindings'], 32)
        self.assertEqual(result['complete_target_functions'], 21)
        self.assertEqual(result['newly_exposed_shared_callbacks'], 10)
        self.assertEqual(result['callable_common_slots'], 12)
        self.assertEqual(result['declared_tables'], 57)
        self.assertEqual(result['declared_function_slots'], 2463)
        self.assertEqual(result['new_C_bytes'], 0)
        self.assertFalse(result['all_dynamic_dispatch_resolved'])
        self.assertFalse(result['screen_specific_signature_review_complete'])
        for prefix in result['concrete_prefixes']:
            specific = [b for b in prefix['bindings'] if b['family_specific_signature_retained']]
            self.assertEqual(len(specific), 4)
            self.assertTrue(all(not b['callable_through_common_view'] for b in specific))

    def test_missing_or_duplicate_common_view_is_rejected(self):
        self.inventory['unbound_type_views'] *= 2
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.check()
        self.inventory['unbound_type_views'] = []
        with self.assertRaisesRegex(ValueError, 'missing'):
            self.check()

    def test_opaque_address_cannot_become_a_guessed_callable(self):
        self.inventory['unbound_type_views'][0]['slots'][2]['declared_function_pointer'] = True
        with self.assertRaisesRegex(ValueError, 'classification'):
            self.check()

    def test_wrong_layout_name_or_offset_is_rejected(self):
        for key,value in (('field','Unknown'), ('offset',0x10)):
            with self.subTest(key=key):
                old = deepcopy(self.inventory)
                self.inventory['unbound_type_views'][0]['slots'][3][key] = value
                with self.assertRaisesRegex(ValueError, 'slot'):
                    self.check()
                self.inventory = old

    def test_partial_view_cannot_be_counted_as_another_concrete_table(self):
        self.inventory['tables'].append(dict(name='invented', type=tool.TYPE))
        with self.assertRaisesRegex(ValueError, 'must not add'):
            self.check()

    def test_original_screen_binding_change_is_rejected(self):
        struct.pack_into('<I', self.image, 0x800+0x80086B70-0x80010000, 0x80017FF0)
        with self.assertRaisesRegex(ValueError, 'word'):
            self.check()

    def test_original_base_word_is_independently_read(self):
        struct.pack_into('<I', self.image, 0x800+0x8006B59C-0x80010000, 0x80017FF0)
        with self.assertRaisesRegex(ValueError, 'base'):
            self.check()

    def test_reserved_slot_must_stay_null(self):
        struct.pack_into('<I', self.image, 0x800+0x80086B9C-0x80010000, 0x80018350)
        with self.assertRaisesRegex(ValueError, 'word'):
            self.check()

    def test_concrete_metadata_cannot_override_original_bytes(self):
        self.inventory['tables'][0]['slots'][4]['value'] = '0x80017FF0'
        with self.assertRaisesRegex(ValueError, 'word'):
            self.check()

    def test_complete_function_tail_is_checked_beyond_the_entry(self):
        target = self.catalogue['targets'][0]
        off = 0x800+int(target['pc'],16)-0x80010000+target['function_bytes']-1
        self.image[off] ^= 1
        with self.assertRaisesRegex(ValueError, 'body differs'):
            self.check()

    def test_missing_duplicate_or_wrong_owner_is_rejected(self):
        saved = deepcopy(self.catalogue)
        for kind in ('missing','duplicate','renamed'):
            with self.subTest(kind=kind):
                self.catalogue = deepcopy(saved)
                if kind == 'missing': self.catalogue['targets'].pop(0)
                elif kind == 'duplicate': self.catalogue['targets'].append(deepcopy(self.catalogue['targets'][0]))
                else: self.catalogue['targets'][0]['function'] = 'invented_owner'
                with self.assertRaises(ValueError): self.check()

    def test_invalid_complete_extents_are_rejected(self):
        for size in (0, -4, 15, True, 0x100000):
            with self.subTest(size=size):
                self.catalogue['targets'][0]['function_bytes'] = size
                with self.assertRaisesRegex(ValueError, 'extent'): self.check()

    def test_missing_or_repeated_specific_binding_is_rejected(self):
        target = next(t for t in self.catalogue['targets'] if t['pc'] == '0x8004D578')
        binding = deepcopy(target['bindings'][0])
        for bindings in ([], [binding,binding]):
            target['bindings'] = bindings
            with self.subTest(bindings=bindings), self.assertRaisesRegex(ValueError, 'binding'):
                self.check()

    def test_fault_selector_excludes_same_offset_stack_restore(self):
        body = struct.pack('<4I',0x8FBF0018,0x8C420018,0x0040F809,0)
        self.assertEqual(callback_load(body,0x180000,0x18),0x180004)

    def test_fault_selector_rejects_absent_or_ambiguous_transfer(self):
        for words in ((0x8C420018,0,0,0),
                      (0x8C420018,0x8C420018,0x0040F809,0),
                      (0x8C420018,0x0040F809,0x0060F809,0)):
            with self.subTest(words=words), self.assertRaises(ValueError):
                callback_load(struct.pack('<4I',*words),0x180000,0x18)


if __name__ == '__main__':
    unittest.main()
