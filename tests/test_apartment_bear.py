import unittest
import hashlib
import json

from tools import verify_apartment_bear as bear


class ApartmentBearScheduleTests(unittest.TestCase):
    def actions(self, **changes):
        case=dict(variant=1,state=0,tick=1,timer=1)
        case.update(changes)
        return bear.script_actions(case,10)

    def test_animation_switch_requires_exact_original_duration(self):
        self.assertEqual(self.actions(variant=0,tick=10), [('select',1),('random_state',11)])
        for tick in (9,11,-1,0x7fffffff):
            self.assertEqual(self.actions(variant=0,tick=tick), [])

    def test_periodic_command_precedes_animation_switch(self):
        self.assertEqual(self.actions(variant=0,tick=10,timer=-5),
                         [('command',7,17),('command',8,-2),('select',1),('random_state',11)])

    def test_negative_and_extreme_command_timers(self):
        for timer in (-10,-5,0,5,10):
            self.assertEqual(self.actions(variant=0,timer=timer), [('command',7,17),('command',8,-2)])
        for timer in (-0x80000000,-6,-4,-1,1,4,6,0x7fffffff):
            self.assertEqual(self.actions(variant=0,timer=timer), [])

    def test_zero_state_turns_and_moves_at_all_four_boundaries(self):
        for tick in (60,212,290,320):
            self.assertEqual(self.actions(tick=tick), [('turn','g_RotateYawQuarter'),('forward',)])
            self.assertEqual(self.actions(tick=tick-1), [('forward',)])
            self.assertEqual(self.actions(tick=tick+1), [('forward',)])

    def test_zero_state_reverses_turn_at_398_and_does_not_stop_at_174(self):
        self.assertEqual(self.actions(tick=398), [('turn','g_RotateYawNegQuarter'),('forward',)])
        self.assertEqual(self.actions(tick=174), [('forward',)])

    def test_nonzero_state_stops_exactly_at_174(self):
        for state in (-1,1,11):
            self.assertEqual(self.actions(state=state,tick=173), [('forward',)])
            self.assertEqual(self.actions(state=state,tick=174), [('stop',)])
            self.assertEqual(self.actions(state=state,tick=175), [])

    def test_nonzero_state_has_its_own_turn_schedule(self):
        self.assertEqual(self.actions(state=11,tick=140), [('turn','g_RotateYawQuarter'),('forward',)])
        self.assertEqual(self.actions(state=11,tick=212), [])
        self.assertEqual(self.actions(state=0,tick=140), [('forward',)])

    def test_fixture_rejects_an_unbound_animation(self):
        case=bear.p.base_case(bear.CALLBACK,77,10)
        case['variant']=2
        with self.assertRaisesRegex(ValueError,'bound animation'):
            bear.validate_case(case)

    def test_native_composition_has_complete_nonoverlapping_ranges(self):
        intervals=sorted((int(row['address'],16),row['bytes']) for row in bear.FUNCTIONS)
        self.assertEqual(len(intervals),30)
        self.assertTrue(all(size>0 and size%4==0 for _address,size in intervals))
        self.assertTrue(all(a+size<=b for (a,size),(b,_next_size) in zip(intervals,intervals[1:])))

    def test_published_source_and_range_pins_match(self):
        evidence=json.loads((bear.ROOT/'docs/apartment-bear-checks.json').read_bytes())
        for path in ('tools/verify_apartment_bear.py','docs/apartment-bear-function-ranges.json'):
            self.assertEqual(hashlib.sha256((bear.ROOT/path).read_bytes()).hexdigest(),
                             evidence['source_sha256'][path])

    def test_profile_does_not_promote_c_or_whole_encounter_counts(self):
        evidence=json.loads((bear.ROOT/'docs/apartment-bear-checks.json').read_bytes())
        self.assertEqual(evidence['before']['bounded_NPC_callbacks'],40)
        self.assertEqual(evidence['after']['bounded_NPC_callbacks'],41)
        self.assertEqual(evidence['new_C_bytes'],0)
        self.assertFalse(evidence['natural_encounter_verified'])
        self.assertEqual(evidence['whole_NPC_encounters_accepted'],0)
        self.assertEqual(evidence['whole_feature_groups_accepted'],0)

    def test_published_faults_executed_and_changed_outputs(self):
        evidence=json.loads((bear.ROOT/'docs/apartment-bear-checks.json').read_bytes())
        self.assertEqual(len(evidence['wrong_output_controls']),7)
        for control in evidence['wrong_output_controls']:
            self.assertGreater(control['executed_hits'],0)
            self.assertTrue(control['mismatched_outputs'])
        self.assertTrue(evidence['escaped_store_control']['rejected_before_write'])

    def test_published_histories_retain_both_rng_branches(self):
        evidence=json.loads((bear.ROOT/'docs/apartment-bear-checks.json').read_bytes())
        self.assertEqual(evidence['standalone_native_cases'],604)
        self.assertEqual(evidence['distinct_initialized_inputs'],602)
        self.assertEqual(sum(h['script_invocations'] for h in evidence['histories']),30)
        self.assertEqual([h['final_state'] for h in evidence['histories']],[0,1])


if __name__=='__main__': unittest.main()
