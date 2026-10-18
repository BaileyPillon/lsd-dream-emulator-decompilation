"""Constructed hull sampler controls; no commercial game files required."""
import copy
import struct
import unittest

from tools.collision_calls import selection
from tools.collision_calls import FIELDS,HULL_PC,HULL_FUNCTION_BYTES,PC
from tools import inspect_hull_calls as hull
from tools import inspect_collision_calls as primitive
from tools.inspect_collision_call_batches import verify_partition_coverage
from tools.verify_collision import cube_points
from tests.test_collision_calls import fixture


def hull_fixture(*,mode=0,count=1,hit=True,indirect=True):
    """Constructed words and geometry, not a recording of the commercial game."""
    row,before,_,summary,_,program,image=fixture(hit=hit)
    before=bytearray(before);image=bytearray(image)
    caller,stack=0x80011000,row['entry_cpu_gpr_29'];frame=stack-176
    receiver,hits,contact,cloud=0x80063000,0x80064000,0x80061000,0x80065000
    model=0x80060040;sites=(0x8001DF20,0x8001E050)
    jal=0x0C000000|((PC>>2)&0x03FFFFFF)
    call=0x0040F809 if indirect else 0x0C000000|((HULL_PC>>2)&0x03FFFFFF)
    instructions={caller:call,caller+4:0,HULL_PC:0x27BDFF50,
                  HULL_PC+HULL_FUNCTION_BYTES-12:0x27BD00B0,
                  HULL_PC+HULL_FUNCTION_BYTES-8:0x03E00008,
                  HULL_PC+HULL_FUNCTION_BYTES-4:0,**{at:jal for at in sites}}
    for address,value in instructions.items():
        struct.pack_into('<I',image,0x800+address-0x80010000,value)
    before[0x10000:0x10000+len(image)-0x800]=image[0x800:]

    def pack(fmt,address,*values):struct.pack_into(fmt,before,address&0x1FFFFFFF,*values)
    pack('<I',receiver+32,model);pack('<I',receiver+44,0xFFFFFFFF)
    pack('<i',hull.COUNT,count);pack('<i',hull.MODE,mode)
    pack('<6h',hull.BOUNDS,-128,-128,0,128,128,0)
    points=cube_points(((-64,-64,-256),(64,64,256)) if hit else ((4096,-64,-256),(4224,64,256)))
    pack('<i',cloud,1)
    for index,point in enumerate(points):pack('<3h',cloud+4+6*index,*point)
    result=int(hit and count>0 and mode==0);mask=((1<<count)-1) if result else 0
    expected_contact=(0,0,0) if result else (64,64,0) if hit and count>0 else (111,222,333)
    phases=['midpoint']*max(count,0) if hit else []
    if hit and count>0 and mode!=0:phases+=['fallback','fallback']*count
    after=bytearray(before)
    for address,value in [(receiver+44,mask),(hits,result)]:struct.pack_into('<I',after,address&0x1FFFFFFF,value)
    struct.pack_into('<3h',after,contact&0x1FFFFFFF,*expected_contact)
    mids=[tuple((a+b)>>1 for a,b in zip(points[i],points[i+2])) for i in (0,4)]
    struct.pack_into('<6h',after,(frame+24)&0x1FFFFFFF,*(v for p in mids for v in p))
    row.update(entry_pc=HULL_PC,return_pc=caller+8,entry_cpu_gpr_4=receiver,entry_cpu_gpr_5=hits,
               entry_cpu_gpr_6=contact,entry_cpu_gpr_7=cloud,entry_cpu_gpr_31=caller+8,
               cpu_gpr_2=result,cpu_gpr_31=caller+8,entry_cpu_gpr_2=HULL_PC if indirect else 0)
    for prefix,jump,word in [('entry_',caller,call),('',HULL_PC+HULL_FUNCTION_BYTES-8,0x03E00008)]:
        for part,address,value in [('jump',jump,word),('delay',jump+4,0)]:
            row.update({prefix+part+'_'+key:value for key,value in
                        dict(pc=address,ram=value,fetch=value,rs=0,sp=stack,flags=1,sr=0x40000401).items()})
    row['entry_jump_rs']=HULL_PC if indirect else 0;row['jump_rs']=caller+8
    entry=dict(pc=HULL_PC,relative_frame=5,timestamp=10,a0=receiver,a1=hits,a2=contact,a3=cloud,
               sp=stack,ra=caller+8,transfer_pc=caller,delay_pc=caller+4,transfer_word=call,delay_word=0,
               transfer_classification=dict(kind='observed_indirect_JALR' if indirect else 'observed_direct_JAL'))
    entries=[entry]+[dict(pc=PC,relative_frame=5,timestamp=11+i,a0=model,a1=frame+64,a2=contact,
                         a3=frame+68,sp=frame,transfer_pc=sites[phase=='fallback']) for i,phase in enumerate(phases)]
    program['method_trace']['collision_calls']=dict(function='func_8001DDF4',max_samples=64,ordinal_first=1,ordinal_step=4)
    summary.update(protocol=2,settings=selection(program),ordinal_skips=0)
    return before,after,row,entries,bytes(image),program,summary


class HullSelectionTests(unittest.TestCase):
    def program(self):
        program=fixture()[5]
        program['method_trace']['collision_calls']=dict(function='func_8001DDF4',max_samples=64,
                                                       ordinal_first=1,ordinal_step=4)
        return program

    def test_exact_original_hull_span_and_ordinal_policy(self):
        program=self.program();before=copy.deepcopy(program)
        self.assertEqual(selection(program),dict(pc=0x8001DDF4,bytes=796,max_samples=64,
                                                 ordinal_first=1,ordinal_step=4))
        self.assertEqual(program,before)

    def test_hull_cannot_claim_the_primitive_caller_model_policy(self):
        program=self.program()
        program['method_trace']['collision_calls']=dict(function='func_8001DDF4',max_samples=64,per_key=2)
        with self.assertRaisesRegex(ValueError,'Hull snapshots require ordinal'):
            selection(program)

    def test_unknown_or_non_string_function_cannot_select_an_arbitrary_native_pc(self):
        for function in ('func_8001F8BC','primitive',0x8001DDF4,[],None):
            program=self.program();program['method_trace']['collision_calls']['function']=function
            with self.subTest(function=function),self.assertRaisesRegex(ValueError,'declared original'):
                selection(program)

    def test_target_selection_preserves_strict_unknown_field_rejection(self):
        program=self.program();program['method_trace']['collision_calls']['pc']=0x8001DDF4
        with self.assertRaisesRegex(ValueError,'Ordinal selection'):
            selection(program)

    def test_explicit_primitive_selection_matches_the_legacy_default(self):
        program=fixture()[5];before=selection(program)
        program['method_trace']['collision_calls']['function']='func_8001F8B8'
        self.assertEqual(selection(program),before)


class HullRecordTests(unittest.TestCase):
    def verify(self,values):
        before,after,row,entries,image,program,summary=values
        data=struct.pack('<247I',*(row[field] for field in FIELDS))
        return hull.validate_records(data,before+after,summary,entries,program,image)

    def test_direct_and_indirect_entries_preserve_the_declared_hull_outputs(self):
        for indirect in (False,True):
            with self.subTest(indirect=indirect):
                report=self.verify(hull_fixture(indirect=indirect))
                call=report['calls'][0]
                self.assertEqual((call['result'],call['mask'],call['hull_hits'],call['contact']),(1,1,1,[0,0,0]))
                self.assertEqual(call['observed_nested_primitive_entries'],1)

    def test_rejected_height_still_retains_the_last_primitive_contact(self):
        call=self.verify(hull_fixture(mode=1))['calls'][0]
        self.assertEqual((call['result'],call['mask'],call['hull_hits']),(0,0,0))
        self.assertEqual(call['contact'],[64,64,0])
        self.assertEqual([q['phase'] for q in call['modeled_queries']],['midpoint','fallback','fallback'])

    def test_empty_or_clipped_queries_do_not_require_a_valid_geometry_pointer(self):
        for kwargs in (dict(count=0),dict(hit=False)):
            values=hull_fixture(**kwargs);struct.pack_into('<I',values[0],0x63020,0)
            struct.pack_into('<I',values[1],0x63020,0)
            call=self.verify(values)['calls'][0]
            self.assertEqual((call['result'],call['mask'],call['hull_hits'],call['contact']),(0,0,0,[111,222,333]))
            self.assertFalse(call['geometry_decoded'])

    def test_early_hit_uses_one_hull_hit_flag_and_a_per_bounds_mask(self):
        call=self.verify(hull_fixture(count=2))['calls'][0]
        self.assertEqual((call['result'],call['mask'],call['hull_hits']),(1,3,1))
        self.assertEqual(call['observed_nested_primitive_entries'],2)

    def test_wrong_return_mask_contact_or_midpoint_cannot_pass(self):
        for field in ('return','mask','hull_hits','contact','midpoint'):
            values=hull_fixture();before,after,row,*_=values
            if field=='return':row['cpu_gpr_2']=0
            else:
                address={'mask':0x6302C,'hull_hits':0x64000,'contact':0x61000,
                         'midpoint':row['entry_cpu_gpr_29']-176+24-0x80000000}[field]
                after[address]^=1
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'[Hh]ull'):
                self.verify(values)

    def test_missing_nested_call_wrong_caller_or_arguments_cannot_pass(self):
        for field in ('missing','transfer_pc','a0','a1','a2','a3','sp'):
            values=hull_fixture()
            if field=='missing':values[3].pop()
            else:values[3][1][field]+=4
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'[Hh]ull|nested'):
                self.verify(values)

    def test_indirect_entry_requires_the_observed_target_register_value(self):
        values=hull_fixture();values[2]['entry_jump_rs']=0
        with self.assertRaisesRegex(ValueError,'call and link'):
            self.verify(values)

    def test_changed_shared_bounds_or_mode_invalidates_the_model(self):
        for address in (hull.COUNT,hull.BOUNDS,hull.MODE):
            values=hull_fixture();values[1][address&0x1FFFFFFF]^=1
            with self.subTest(address=address),self.assertRaisesRegex(ValueError,'decoded input changed'):
                self.verify(values)

    def test_primitive_inspector_cannot_certify_a_hull_record(self):
        before,after,row,entries,image,program,summary=hull_fixture()
        data=struct.pack('<247I',*(row[field] for field in FIELDS))
        with self.assertRaisesRegex(ValueError,'inspector target differ'):
            primitive.validate_records(data,before+after,summary,entries,program,image)


class HullPartitionTests(unittest.TestCase):
    def values(self):
        entries=[dict(pc=pc) for pc in (HULL_PC,PC,PC,HULL_PC,PC)]
        batches=[]
        for first,base,nested in ((1,1,[2,3]),(2,4,[5])):
            call=dict(base_ordinal=base,result=1,primitive_count=1,polygon_visits=len(nested),
                      model_address=0x80060040,geometry_address=0x80060080,entry_frame=5,return_frame=5,
                      nested_primitive_base_ordinals=nested)
            policy=dict(eligible_entries=2,ordinal_skips=1,nested_skips=0,sample_limit_skips=0,
                        duplicate_key_skips=0,frame_budget_skips=0)
            batches.append(dict(settings=dict(ordinal_first=first,ordinal_step=2),
                                verification=dict(completed_samples=1,policy=policy,calls=[call])))
        return entries,batches

    def test_hull_partition_accounts_for_each_nested_primitive_entry(self):
        entries,batches=self.values();report=verify_partition_coverage(entries,batches,function='func_8001DDF4')
        self.assertEqual((report['completed_hull_calls'],report['observed_nested_primitive_entries']),(2,3))
        self.assertEqual(report['polygon_visits'],3)
        self.assertTrue(report['every_observed_primitive_entry_attributed_to_a_hull'])
        self.assertFalse(report['primitive_returns_verified_in_this_collection'])

    def test_duplicate_noninteger_or_nonprimitive_nested_ordinals_are_rejected(self):
        for nested in ([2],[4],[5.0]):
            entries,batches=self.values();batches[1]['verification']['calls'][0]['nested_primitive_base_ordinals']=nested
            with self.subTest(nested=nested),self.assertRaises(ValueError):
                verify_partition_coverage(entries,batches,function='func_8001DDF4')

    def test_primitive_entries_outside_hulls_remain_explicitly_unattributed(self):
        entries,batches=self.values();batches[1]['verification']['calls'][0]['nested_primitive_base_ordinals']=[]
        report=verify_partition_coverage(entries,batches,function='func_8001DDF4')
        self.assertEqual(report['unattributed_primitive_entries'],1)
        self.assertFalse(report['every_observed_primitive_entry_attributed_to_a_hull'])
        self.assertTrue(report['every_observed_route_hull_call_verified'])


if __name__=='__main__':unittest.main()
