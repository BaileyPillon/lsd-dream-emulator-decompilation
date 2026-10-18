"""Owned protocol fixtures for collision ranges kept outside declared vtables."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from tools import dispatch_trace as tool
import tests.test_dispatch_trace as fixture
from tools import inspect_collision_entries as roles


def entry_fixture():
    hull=dict(pc=roles.HULL,sp=0x801ff000,a0=0x80110000,a2=0x801fefe0,a3=0x80140000,
        a0_word_20=0x80130000,relative_frame=3000,timestamp=20,
        transfer_classification=dict(kind='observed_indirect_JALR'))
    primitive=dict(pc=roles.PRIMITIVE,sp=hull['sp']-176,a0=hull['a0_word_20'],
        a1=hull['sp']-176+64,a2=hull['a2'],a3=hull['sp']-176+68,
        relative_frame=3000,timestamp=30,transfer_pc=0x8001DF20,
        transfer_classification=dict(kind='observed_direct_JAL'))
    corner=dict(primitive,transfer_pc=0x8001E048,timestamp=40)
    program=dict(method_trace=dict(range_family='collision',targets=['func_8001DDF4','func_8001F8B8']))
    return [hull,primitive,corner],program


class CollisionEntryRoleTests(unittest.TestCase):
    def setUp(self):self.entries,self.program=entry_fixture()
    def analyze(self):return roles.analyze_entries(self.entries,self.program)

    def test_real_argument_relationships_do_not_claim_hit_results_or_complete_geometry(self):
        report=self.analyze()
        self.assertEqual(report['correlated_hull_primitive_entries'],2)
        for key in ('callee_returns_observed','collision_hit_results_accepted','complete_input_geometry_ownership_accepted',
                    'allocation_lifetimes_accepted','stack_words_five_and_six_observed'):
            self.assertFalse(report[key])

    def test_24_byte_nearest_storage_shift_from_the_rejected_C_layout_is_detected(self):
        self.entries[1]['a1']-=24
        with self.assertRaisesRegex(ValueError,'stack roles'):self.analyze()

    def test_wrong_frame_model_output_or_height_address_cannot_borrow_another_hull(self):
        for key in ('sp','a0','a2','a3'):
            self.entries,self.program=entry_fixture();self.entries[1][key]^=4
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'stack roles'):self.analyze()

    def test_direct_query_requires_a_preceding_hull_entry(self):
        self.entries.pop(0)
        with self.assertRaisesRegex(ValueError,'preceding recorded hull'):self.analyze()

    def test_query_must_follow_its_hull_in_native_frame_timestamp_order(self):
        self.entries[1]['timestamp']=19
        with self.assertRaisesRegex(ValueError,'precedes'):self.analyze()

    def test_an_entry_before_a_frame_boundary_can_have_a_later_child_query(self):
        for row in self.entries[1:]:row.update(relative_frame=3001,timestamp=1)
        self.assertEqual(self.analyze()['correlated_hull_primitive_entries'],2)

    def test_other_primitive_callers_are_counted_without_borrowing_hull_ownership(self):
        self.entries.append(dict(self.entries[-1],transfer_pc=0x8001EA0C,a0=0x80150000,timestamp=50))
        report=self.analyze()
        self.assertEqual(report['other_primitive_callers'],{'0x8001EA0C':1})
        self.assertEqual(report['correlated_hull_primitive_entries'],2)

    def test_hull_entry_without_a_child_is_not_reported_as_a_collision_miss(self):
        self.entries.append(dict(self.entries[0],timestamp=50))
        report=self.analyze()
        self.assertEqual(report['hull_entries_without_recorded_primitive_queries'],1)
        self.assertNotIn('collision_misses',report)

    def test_entry_only_profile_cannot_claim_a_return_or_slot_flow_selection(self):
        self.program['method_trace']['return_trace']={'kind':'invented'}
        with self.assertRaisesRegex(ValueError,'entry-only'):self.analyze()

    def test_capture_requires_both_original_hull_query_sites(self):
        self.entries.pop()
        with self.assertRaisesRegex(ValueError,'both original hull call sites'):self.analyze()


class CollisionEntrySelectionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.DispatchSelectionTests();self.fixture.setUp()
        self.raw,self.proof=self.fixture.supplement()
        self.fixture.program['method_trace']['range_family']='collision'
        self.proof['status']='verified_complete_original_collision_boundaries'
        self.proof['producer_dependencies']={'research/collision/function-ranges.json':hashlib.sha256(self.raw).hexdigest()}

    def select(self):return self.fixture.supplement_selection(self.raw,self.proof)

    def test_direct_collision_range_does_not_invent_a_declared_virtual_binding(self):
        original=deepcopy(self.fixture.catalogue)
        selected=self.select()[0x80010008]
        self.assertEqual(selected['range_source'],'collision_boundary_ranges')
        self.assertEqual(selected['bindings'],[])
        self.assertEqual(self.fixture.catalogue,original)

    def test_collision_family_cannot_accept_file_driver_provenance(self):
        self.proof['status']='verified_bounded_file_driver_interface_repair'
        with self.assertRaisesRegex(ValueError,'canonical ELF/GNU'):self.select()

    def test_collision_family_requires_its_own_exact_range_seal(self):
        self.proof['producer_dependencies']={'research/file_driver/function-ranges.json':hashlib.sha256(self.raw).hexdigest()}
        with self.assertRaisesRegex(ValueError,'Supplemental range bytes'):self.select()

    def test_collision_family_rejects_partial_image_or_unqualified_GNU_extents(self):
        for key in ('complete_canonical_image_equal','independent_GNU_sized_function_extents_equal'):
            with self.subTest(key=key):
                self.proof['original_symbol_diagnostic'][key]=False
                with self.assertRaisesRegex(ValueError,'canonical ELF/GNU'):self.select()
                self.proof['original_symbol_diagnostic'][key]=True

    def test_collision_family_cannot_borrow_a_declared_function_address(self):
        rows=json.loads(self.raw);rows[0]['address']='0x80010000';self.raw=json.dumps(rows).encode()
        self.proof['producer_dependencies']['research/collision/function-ranges.json']=hashlib.sha256(self.raw).hexdigest()
        with self.assertRaisesRegex(ValueError,'function owners disagree'):self.select()

    def test_collision_family_checks_every_original_function_byte(self):
        rows=json.loads(self.raw);rows[0]['sha256']='0'*64;self.raw=json.dumps(rows).encode()
        self.proof['producer_dependencies']['research/collision/function-ranges.json']=hashlib.sha256(self.raw).hexdigest()
        with self.assertRaisesRegex(ValueError,'differs from original'):self.select()

    def test_unknown_or_untyped_family_never_falls_back_to_another_range_set(self):
        for value in ('missing',True,None,{},[]):
            program=fixture.program();program['method_trace']['range_family']=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'range family'):tool.validate_program(program)

    def test_collision_route_preserves_the_qualified_opening_controller_values(self):
        root=Path(__file__).resolve().parents[1]
        earlier=json.loads((root/'research/headless/file-driver-sdk-route.json').read_bytes())
        current=json.loads((root/'research/headless/collision-opening-route.json').read_bytes())
        self.assertEqual(tool.expand_program(current),tool.expand_program(earlier))
        self.assertEqual(current['method_trace']['targets'],['func_8001DDF4','func_8001F8B8'])
        self.assertEqual(current['method_trace']['range_family'],'collision')
        self.assertNotIn('return_trace',current['method_trace'])


if __name__=='__main__':unittest.main()
