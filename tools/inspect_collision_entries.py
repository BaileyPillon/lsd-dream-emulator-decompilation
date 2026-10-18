"""Inspect natural collision call arguments without claiming returns or hit results.

Only the two direct call sites inside the hull routine receive a correlated
stack-role check. Other primitive callers retain their separate entry evidence.
Addresses identify observations, not allocation generations or owned objects.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import inspect_dispatch_history as history
from tools.replay_cold_start_headless import require,write_json

HULL=0x8001DDF4
PRIMITIVE=0x8001F8B8
HULL_CALLS={0x8001DF20:'center_segment',0x8001E048:'corner_segment'}
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def analyze_entries(entries,program):
    trace=program['method_trace']
    require(trace.get('range_family')=='collision' and trace['targets']==['func_8001DDF4','func_8001F8B8']
            and not trace.get('flow_sites') and not trace.get('return_trace'),
            'Select the declared entry-only collision profile.')
    hulls=[];primitives=[];pairs=[];last=None;last_ordinal=None;counts=Counter();other=Counter()
    for ordinal,row in enumerate(entries,1):
        if row['pc']==HULL:
            require(row['transfer_classification']['kind']=='observed_indirect_JALR',
                    'The bounded hull profile requires its observed original indirect call.')
            hulls.append(row);last=row;last_ordinal=ordinal
        elif row['pc']==PRIMITIVE:
            require(row['transfer_classification']['kind']=='observed_direct_JAL',
                    'The primitive profile requires its actual original direct call.')
            primitives.append(row);call=row['transfer_pc'];role=HULL_CALLS.get(call)
            if role is None:other[f'0x{call:08X}']+=1;continue
            require(last is not None,'A hull-owned primitive call has no preceding recorded hull entry.')
            expected=(last['sp']-176,last['sp']-176+0x40,last['a2'],last['sp']-176+0x44,last['a0_word_20'])
            actual=(row['sp'],row['a1'],row['a2'],row['a3'],row['a0'])
            require(actual==expected,'Natural hull/primitive stack roles, output address or model argument disagree.')
            require((last['relative_frame'],last['timestamp'])<=(row['relative_frame'],row['timestamp']),
                    'A primitive query precedes its correlated hull entry.')
            counts[role]+=1
            pairs.append(dict(hull_entry=last_ordinal,primitive_entry=ordinal,role=role,
                hull_frame=last['relative_frame'],primitive_frame=row['relative_frame'],
                callsite=f'0x{call:08X}',model_address=f"0x{row['a0']:08X}",
                hull_stack=f"0x{last['sp']:08X}",primitive_stack=f"0x{row['sp']:08X}",
                nearest_address=f"0x{row['a1']:08X}",height_address=f"0x{row['a3']:08X}",
                output_address=f"0x{row['a2']:08X}"))
        else:raise ValueError('Unexpected function in the bounded collision entry profile.')
    require(hulls and primitives and counts['center_segment'] and counts['corner_segment'],
            'Both collision functions and both original hull call sites must be observed.')
    used={row['hull_entry'] for row in pairs}
    return dict(status='verified_bounded_natural_collision_entry_roles',hull_entries=len(hulls),primitive_entries=len(primitives),
        correlated_hull_primitive_entries=len(pairs),hull_callsite_counts=dict(counts),other_primitive_callers=dict(other),
        hull_entries_with_recorded_primitive_queries=len(used),hull_entries_without_recorded_primitive_queries=len(hulls)-len(used),
        distinct_hull_receiver_addresses=len({row['a0'] for row in hulls}),
        distinct_hull_input_addresses=len({row['a3'] for row in hulls}),
        distinct_correlated_model_addresses=len({row['model_address'] for row in pairs}),
        original_hull_frame_bytes=176,original_nearest_offset=0x40,original_height_offset=0x44,
        first_entry_frame=min(row['relative_frame'] for row in entries),last_entry_frame=max(row['relative_frame'] for row in entries),
        associations=pairs,complete_input_geometry_ownership_accepted=False,allocation_lifetimes_accepted=False,
        stack_words_five_and_six_observed=False,callee_returns_observed=False,collision_hit_results_accepted=False,
        full_instruction_path_coverage_accepted=False,virtual_receiver_slot_edges_accepted=0,
        whole_feature_groups_accepted=0,new_C_bytes=0,
        scope='Canonical entries, preceding call/delay words and observed register/stack-role relationships in this history. '
              'A nearest preceding hull entry plus its original direct call site qualifies the argument relation; '
              'this does not observe that hull return, complete call-stack lifetime, extra stack arguments or collision results. '
              'Distinct addresses are neither object nor asset counts.')


def inspect_collision(folder):
    report,retained=history.inspect(folder)
    require(retained['manifest']['runtime_kind']=='dispatch_observer','Natural collision entries require the separate observer.')
    roles=analyze_entries(retained['entries'],retained['program'])
    return dict(status='inspected_bounded_natural_collision_entries',recording=report,collision_entry_roles=roles,
        new_C_bytes=0,whole_feature_groups_accepted=0)


def compare_collision(reference,candidate,mode='same-runtime'):
    compared=history.compare(reference,candidate,mode);before=inspect_collision(reference)
    if mode=='same-runtime':
        after=inspect_collision(candidate)
        require(before['collision_entry_roles']==after['collision_entry_roles'],'Original/rebuilt collision argument roles differ.')
    return dict(status='compared_bounded_natural_collision_entries',mode=mode,
        every_recorded_game_output_equal=compared['every_recorded_game_output_equal'],
        collision_entries_and_roles_equal=mode=='same-runtime',verification=before,new_C_bytes=0,whole_feature_groups_accepted=0)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',required=True,type=Path);parser.add_argument('--candidate',type=Path)
    parser.add_argument('--mode',choices=('same-runtime','observer-output'),default='same-runtime')
    parser.add_argument('--output',required=True,type=Path);args=parser.parse_args(argv)
    try:
        output=args.output.resolve();require(output.is_relative_to(ROOT/'.decomp-lab') and not output.exists(),
            'Choose a fresh private collision entry report.')
        report=compare_collision(args.reference,args.candidate,args.mode) if args.candidate else inspect_collision(args.reference)
        report['verification_source_SHA256']=sha(Path(__file__).read_bytes());write_json(output,report)
        print(json.dumps(dict(status=report['status'],output=str(output))));return 0
    except (OSError,ValueError,KeyError) as error:print(str(error),file=sys.stderr);return 2


if __name__=='__main__':sys.exit(main())
