"""Reject contexts that would silently bypass unmodelled original day logic."""
from copy import deepcopy
import json
import unittest

from tools import verify_new_game_reset as native
from tools import new_game_state as model


class ResetProfileBoundaries(unittest.TestCase):
    def test_profiles_are_unique_and_include_all_declared_groups(self):
        profiles=list(native.cases())
        self.assertEqual(len(profiles),1032)
        self.assertEqual(len({json.dumps(p,sort_keys=True) for p in profiles}),len(profiles))
        self.assertEqual({p['kind'] for p in profiles},{'reset','end','clear','query','save_view','flag','navigation'})

    def test_normal_score_chart_path_cannot_be_mislabeled_reset(self):
        case=dict(kind='end',segment=0,pattern=0,mode=0,flashback=0,stored_day=0)
        with self.assertRaisesRegex(ValueError,'score/chart'):native.fixture(case,0x31304A)

    def test_reset_and_end_reset_keep_distinct_new_game_flag_contracts(self):
        reset=native.fixture(dict(kind='reset',segment=0x80000000,pattern=1),0x31304A)
        end=native.fixture(dict(kind='end',segment=0x80000000,pattern=1,mode=2,flashback=0x80000000,stored_day=364),0x31304A)
        self.assertEqual(model.word(reset['expected_object'],model.IS_NEW_GAME),0xAABBCCDD)
        self.assertEqual(model.word(end['expected_object'],model.IS_NEW_GAME),1)
        self.assertEqual(end['returned'],0x80000000)
        self.assertEqual(reset['expected_globals'],end['expected_globals'])

    def test_unknown_alias_extra_fields_and_bad_byte_alignment_are_rejected(self):
        base=dict(kind='navigation',segment=0,other_segment=0,pattern=0,alignment=0)
        for key,value in (('segment',0xC0000000),('segment',True),('alignment',4),('pattern',True),('extra',0)):
            case=deepcopy(base);case[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):native.validate(case)

    def test_null_size_pointer_leaves_auxiliary_buffer_unchanged(self):
        null=native.fixture(dict(kind='save_view',segment=0xA0000000,pattern=2,size_alias=None),0x31304A)
        self.assertEqual(null['args'][1],0)
        self.assertEqual(null['aux'],null['expected_aux'])
        self.assertEqual(null['returned'],(native.OBJECT|0xA0000000)+0x178)


if __name__=='__main__':unittest.main()
