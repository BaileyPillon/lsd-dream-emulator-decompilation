"""Synthetic RAM bindings cannot turn matching values into a reset event."""
import unittest

from tools import inspect_new_game_save as tool
from tools import new_game_state as model


class RetainedSaveInspectionTests(unittest.TestCase):
    def setUp(self):
        self.ram=bytearray(0x200000)
        self.root=0x800A0040;self.offset=self.root&0x1FFFFFFF
        data=bytearray([0xA5])*model.OBJECT_BYTES
        model.put(data,0,tool.TABLE);model.put(data,model.IS_NEW_GAME,1)
        self.data=model.reset(data,0x31304A)
        self.ram[self.offset:self.offset+model.OBJECT_BYTES]=self.data
        model.put(self.ram,tool.NAV_GLOBAL,self.root+model.NAV_FLAGS)
        model.put(self.ram,tool.COUNT_GLOBAL,self.root+model.DYNAMIC_LINK_COUNT)
        model.put(self.ram,tool.MAGIC_GLOBAL,0x31304A)

    def test_matching_fields_keep_history_and_do_not_prove_a_reset_event(self):
        result=tool.inspect(self.ram)
        self.assertTrue(result['matches_reset_written_fields'])
        self.assertEqual(result['save_block_bytes'],1792)
        self.assertEqual(result['preserved_save_block_bytes'],1216)
        self.assertEqual(result['preserved_nonzero_bytes'],1216)
        self.assertFalse(result['reset_event_proved'])
        self.assertFalse(result['object_allocation_lifetime_proved'])

    def test_a_progressed_counter_is_reported_without_masking_its_bytes(self):
        model.put(self.ram,self.offset+0x180,364)
        result=tool.inspect(self.ram)
        self.assertFalse(result['matches_reset_written_fields'])
        self.assertEqual(result['zero_based_day'],364)
        self.assertTrue(set(result['reset_written_field_differences'])<={0x180,0x181,0x182,0x183})

    def test_one_reserved_byte_difference_is_visible(self):
        self.ram[self.offset+0x877]=1
        self.assertIn(0x877,tool.inspect(self.ram)['reset_written_field_differences'])

    def test_zero_unbound_globals_do_not_fabricate_an_object(self):
        model.put(self.ram,tool.NAV_GLOBAL,0);model.put(self.ram,tool.COUNT_GLOBAL,0)
        self.assertFalse(tool.inspect(self.ram)['object_available'])

    def test_incomplete_or_cross_object_global_binding_is_rejected(self):
        for count in (0,self.root+model.DYNAMIC_LINK_COUNT+4):
            model.put(self.ram,tool.COUNT_GLOBAL,count)
            with self.assertRaisesRegex(ValueError,'binding|same dream'):tool.inspect(self.ram)

    def test_wrong_table_and_out_of_RAM_root_are_rejected(self):
        model.put(self.ram,self.offset,0x80086B60)
        with self.assertRaisesRegex(ValueError,'table'):tool.inspect(self.ram)
        model.put(self.ram,tool.NAV_GLOBAL,0x80200000+model.NAV_FLAGS)
        model.put(self.ram,tool.COUNT_GLOBAL,0x80200000+model.DYNAMIC_LINK_COUNT)
        with self.assertRaisesRegex(ValueError,'outside'):tool.inspect(self.ram)

    def test_alias_validation_and_complete_RAM_are_required(self):
        for pointer in (True,-1,0xC00A0040,0x800000000):
            with self.subTest(pointer=pointer),self.assertRaises(ValueError):tool.physical(pointer,4)
        with self.assertRaises(ValueError):tool.inspect(self.ram[:-1])


if __name__=='__main__':unittest.main()
