"""Compare bounded original hull returns with captured geometry and nested entries.

This models declared outputs in one recorded history. It does not accept complete
instruction paths, opaque state, geometry ownership, or whole-feature parity.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import inspect_collision_calls as primitive
from tools.collision_calls import HULL_PC,HULL_FUNCTION_BYTES,PC,RAM_BYTES
from tools.dispatch_returns import sequence
from tools.replay_cold_start_headless import require,write_json
from tools.verify_collision import clip_segment,primitive_model,signed

FUNCTION='func_8001DDF4'
COUNT=0x8008AC4C
BOUNDS=0x8008B21C
MODE=0x8008A838


def hull_model(first_points,load_cloud,bounds_count,mode,box,query,initial_contact):
    """Model the hull's midpoint and fallback flow; decode geometry only on query."""
    mids=[tuple((a+b)>>1 for a,b in zip(first_points[i],first_points[i+2])) for i in (0,4)]
    mask,out,contact,queries=0,0,tuple(initial_contact),[]

    def check(a,b,phase,index,path=None,edge=None):
        nonlocal contact
        if not clip_segment(box,a,b):return 0,None
        result,distance,point,height=query(a,b)
        if point is not None:contact=tuple(point)
        require(not result or height is not None,'A primitive hit has no modeled height.')
        queries.append(dict(phase=phase,bounds_index=index,path_index=path,edge_index=edge,
                            start=list(a),end=list(b),result=result,nearest=distance,
                            contact=list(point) if point is not None else None,height=height))
        return result,height

    for index in range(max(bounds_count,0)):
        hit,height=check(*mids,'midpoint',index)
        if hit and (mode==0 or height>512):mask|=1<<(index&31)
    if mask:return dict(result=1,mask=mask&0xFFFFFFFF,hull_hits=1,contact=list(contact),midpoints=mids,queries=queries)
    for index in range(max(bounds_count,0)):
        for path,points in enumerate(load_cloud()):
            for edge in (1,2):
                hit,height=check(points[edge],points[edge+4],'fallback',index,path,edge)
                if hit and height>512:
                    mask|=1<<(index&31);out|=1<<(path&31)
    return dict(result=int(out!=0),mask=mask&0xFFFFFFFF,hull_hits=out&0xFFFFFFFF,
                contact=list(contact),midpoints=mids,queries=queries)


def verify_hull_result(row,before,after,*,entries):
    receiver,hits,contact_address,cloud_address=[row[f'entry_cpu_gpr_{n}'] for n in (4,5,6,7)]
    model=primitive.word(before,receiver+32)
    count=signed(primitive.word(before,COUNT));mode=signed(primitive.word(before,MODE))
    instruction_count=sequence(row)-sequence(row,'entry_')
    require(max(count,0)<=instruction_count,'Hull loop count exceeds its observed instruction interval.')
    raw_box=struct.unpack('<6h',primitive.ram(before,BOUNDS,12,2)) if count>0 else None
    box=(raw_box[:3],raw_box[3:]) if raw_box is not None else None
    first=[primitive.point(before,cloud_address+4+6*i) for i in range(8)]
    reads=[('receiver_model',receiver+32,4),('midpoint_input',cloud_address+4,48),
           ('bounds_count',COUNT,4),('callee_code',HULL_PC,HULL_FUNCTION_BYTES)]
    if count>0:reads.extend([('shared_bounds',BOUNDS,12),('height_mode',MODE,4)])
    geometry=None;table_reads=set()

    def query(a,b):
        nonlocal geometry
        if geometry is None:
            geometry=primitive.decode_geometry(before,model)
            reads.extend(geometry['ranges'])
        def halfword(address):
            table_reads.add(address)
            return struct.unpack('<H',primitive.ram(before,address,2,2))[0]
        return primitive_model(geometry['polygons'],a,b,halfword)

    def load_cloud():
        cloud_count=signed(primitive.word(before,cloud_address))
        require(max(count,0)*max(cloud_count,0)<=instruction_count,
                'Hull path count exceeds its observed instruction interval.')
        reads.append(('hull_path_count',cloud_address,4))
        if cloud_count<=0:return []
        primitive.ram(before,cloud_address+4,48*cloud_count,2)
        reads.append(('hull_paths',cloud_address+4,48*cloud_count))
        return [[primitive.point(before,cloud_address+4+48*path+6*i) for i in range(8)]
                for path in range(cloud_count)]

    result=hull_model(first,load_cloud,count,mode,box,query,primitive.point(before,contact_address))
    reads.extend(('sqrt_coefficient',address,2) for address in sorted(table_reads))
    writes=[('receiver_mask',receiver+44,4),('hull_hits',hits,4),('contact',contact_address,6)]
    primitive._disjoint(writes,reads)
    for label,address,size in reads:
        require(primitive.ram(before,address,size)==primitive.ram(after,address,size),
                'Hull decoded input changed during the captured call: '+label)
    require(row['cpu_gpr_2']==result['result'] and primitive.word(after,receiver+44)==result['mask']
            and primitive.word(after,hits)==result['hull_hits']
            and list(primitive.point(after,contact_address))==result['contact'],
            'Original hull return, mask or contact differs from the algebraic model.')
    frame=(row['entry_cpu_gpr_29']-176)&0xFFFFFFFF
    expected_midpoints=struct.pack('<6h',*(value for point in result['midpoints'] for value in point))
    require(primitive.ram(after,frame+24,12,2)==expected_midpoints,
            'Original hull midpoint words differ from the modeled input averages.')
    code=primitive.ram(before,HULL_PC,HULL_FUNCTION_BYTES,4)
    callsites=[HULL_PC+offset for offset in range(0,len(code),4)
               if (word:=struct.unpack_from('<I',code,offset)[0])>>26==3
               and ((((word&0x03FFFFFF)<<2)|0x80000000)==PC)]
    require(len(callsites)==2,'Hull does not retain its two qualified direct primitive call sites.')
    nested=[];end=row['frame'],row['timestamp']
    for ordinal,entry in enumerate(entries[row['base_ordinal']:],row['base_ordinal']+1):
        if (entry['relative_frame'],entry['timestamp'])>=end:break
        require(entry['pc']==PC,'Nested hull recursion is outside this call model.')
        nested.append((ordinal,entry))
    require(len(nested)==len(result['queries']),'Modeled hull queries differ from the observed nested primitive count.')
    for (_,entry),expected in zip(nested,result['queries']):
        require([entry[key] for key in ('a0','a1','a2','a3','sp','transfer_pc')]==
                [model,frame+64,contact_address,frame+68,frame,callsites[expected['phase']=='fallback']],
                'Observed nested primitive caller or argument words differ from the hull model.')
    if geometry is None:
        geometry=dict(model_address=model,geometry_address=0,primitive_count=0,packet_mode_counts={},polygons=(),ranges=[])
        decoded=False
    else:decoded=True
    modes={key:value*len(nested) for key,value in geometry['packet_mode_counts'].items()}
    return dict(**{key:value for key,value in geometry.items() if key not in ('polygons','ranges','packet_mode_counts')},
        receiver_address=receiver,hull_hits_address=hits,contact_address=contact_address,cloud_address=cloud_address,
        bounds_count=count,height_mode=mode,shared_bounds=list(raw_box) if raw_box is not None else None,
        result=result['result'],mask=result['mask'],hull_hits=result['hull_hits'],contact=result['contact'],
        geometry_decoded=decoded,packet_mode_counts=modes,polygon_visits=geometry['primitive_count']*len(nested),
        modeled_queries=result['queries'],observed_nested_primitive_entries=len(nested),
        nested_primitive_base_ordinals=[ordinal for ordinal,_ in nested],midpoints=[list(p) for p in result['midpoints']],
        decoded_polygons_sha256=primitive.sha(json.dumps(geometry['polygons'],separators=(',',':')).encode()),
        source_ranges=[dict(role=label,address=address,bytes=size,sha256=primitive.sha(primitive.ram(before,address,size)))
                       for label,address,size in reads])


def validate_records(data,payload,summary,entries,program,executable):
    def inspect_result(row,before,after):return verify_hull_result(row,before,after,entries=entries)
    report=primitive.validate_records(data,payload,summary,entries,program,executable,
                                      function=FUNCTION,inspect_result=inspect_result)
    report['observed_nested_primitive_entries']=sum(call['observed_nested_primitive_entries'] for call in report['calls'])
    return report


def inspect_call_recording(folder):
    return primitive.inspect_call_recording(folder,validator=validate_records,extra_sources=('tools/inspect_hull_calls.py',))


def inspect_calls(folder):return inspect_call_recording(folder)[0]


def compare_calls(reference,candidate,mode='same-runtime'):
    compared=primitive.history.compare(reference,candidate,mode)
    before=inspect_calls(reference)
    if mode=='same-runtime':
        after=inspect_calls(candidate)
        require(before['collision_calls']==after['collision_calls'],
                'Original/rebuilt hull snapshots or modeled outputs differ.')
    return dict(status='compared_bounded_natural_hull_calls',mode=mode,
        every_recorded_game_output_equal=compared['every_recorded_game_output_equal'],
        complete_sample_records_and_RAM_equal=mode=='same-runtime',verification=before,
        new_C_bytes=0,whole_feature_groups_accepted=0)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',required=True,type=Path);parser.add_argument('--candidate',type=Path)
    parser.add_argument('--mode',choices=('same-runtime','observer-output'),default='same-runtime')
    parser.add_argument('--output',required=True,type=Path);args=parser.parse_args(argv)
    try:
        output=args.output.resolve()
        require(output.is_relative_to(ROOT/'.decomp-lab') and not output.exists(),'Choose a fresh private hull report.')
        report=compare_calls(args.reference,args.candidate,args.mode) if args.candidate else inspect_calls(args.reference)
        write_json(output,report);print(json.dumps(dict(status=report['status'],new_C_bytes=0)));return 0
    except (OSError,ValueError,KeyError) as error:
        print(str(error),file=sys.stderr);return 2


if __name__=='__main__':sys.exit(main())
