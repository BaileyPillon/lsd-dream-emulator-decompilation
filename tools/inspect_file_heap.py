"""Verify original file-view construction, releases and allocation generations.

Uses actual native allocation/free boundaries, not equal-address snapshots.
Open lifetimes, unobserved storage and complete feature acceptance stay explicit.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import inspect_sdk_reads as sdk
from tools.dispatch_returns import FIELDS as RETURN_FIELDS
from tools.replay_cold_start_headless import require,write_json

MASK=0x1FFFFFFF
BASE_FILE_TABLE=0x8006D430
sha=lambda data:hashlib.sha256(data).hexdigest()

def analyze_file_heap(records,payload,entries,returns,transfers,program,base_table=BASE_FILE_TABLE):
    require(program['method_trace'].get('heap_lifetime') is True,'No original heap/file-view trace was selected.')
    heap=[row for row in records if row['kind']>=5]
    require(heap,'No original heap/file-view boundaries were recorded.')
    snapshots={};allocations={};active={};unknown_frees=[];null_frees=0;failed_allocations=0;zero_size_requests=0
    free_events=[];constructors=[];releases=[];destructors=[]
    for row in heap:
        kind=row['kind'];address=row['v0'] if kind==5 else row['a0']
        if not address and kind in (5,6):
            require(row['buffer_status']==row['buffer_bytes']==row['buffer_address']==row['buffer_offset']==0,
                    'A null allocation/free cannot carry a heap snapshot.')
            snapshots[row['entry_id']]=()
            continue
        size,status=(16,7) if kind==5 else (32,8) if kind==6 else (88,6)
        expected=address-4 if kind<=6 else address
        require(address!=0 and row['buffer_status']==status and row['buffer_address']==expected and row['buffer_bytes']==size,
                'Heap/file-view snapshot address, status or complete extent disagrees.')
        start=row['buffer_offset'];raw=payload[start:start+size]
        require(len(raw)==size,'Incomplete heap/file-view snapshot.')
        snapshots[row['entry_id']]=struct.unpack('<'+str(size//4)+'I',raw)
    timeline=sorted((sdk.sequence(row,prefix),phase,row) for row in heap
                    for prefix,phase in (('entry_',0),('',1)))
    for sequence,phase,row in timeline:
        kind=row['kind'];words=snapshots[row['entry_id']]
        if kind==5 and phase==1:
            if not row['v0']:
                if row['a0']:failed_allocations+=1
                else:zero_size_requests+=1
                continue
            address=row['v0']&MASK;header=words[0];capacity=(header&0x0FFFFFFF)-4
            minimum=max(12,(row['a0']+3)&~3)
            require(row['a0']!=0 and not header&0x40000000 and minimum<=capacity<minimum+16
                    and capacity%4==0 and 4<=address<0x200000 and capacity<=0x200000-address,
                    'Original allocation header cannot cover its actual request.')
            require(address not in active,'Two live allocation generations share a start address.')
            item=dict(id=row['entry_id'],address=address,original_pointer=row['v0'],requested=row['a0'],capacity=capacity,
                start=sequence,end=None,allocation_frame=row['frame'],free_frame=None,free_id=None)
            allocations[item['id']]=item;active[address]=item
        elif kind==6 and phase==0:
            if not row['a0']:null_frees+=1;continue
            address=row['a0']&MASK;header=words[0]
            require(not header&0x40000000 and (header&0x0FFFFFFF)>=16,
                    'Original free entry does not identify an allocated native block.')
            item=active.pop(address,None)
            if item is None:
                require(not any(old['address']==address for old in allocations.values()),
                        'A previously freed allocation generation is freed again without a recorded allocation.')
                unknown_frees.append(row['entry_id'])
            else:
                require((header&0x0FFFFFFF)==item['capacity']+4,
                        'Native allocation capacity changed before its recorded free.')
                item.update(end=sequence,free_frame=row['entry_frame'],free_id=row['entry_id'])
            free_events.append(row)
    all_allocations=list(allocations.values());ancestor_cache={}
    def alive(item,sequence):return item['start']<sequence and (item['end'] is None or sequence<item['end'])
    def ancestors(item):
        if item['id'] not in ancestor_cache:
            ancestor_cache[item['id']]=[other for other in all_allocations if other['id']!=item['id']
                and alive(other,item['start']) and other['address']<=item['address']-4
                and item['address']+item['capacity']<=other['address']+other['capacity']]
        return ancestor_cache[item['id']]
    def owner(address,size,start,end):
        physical=address&MASK
        candidates=[item for item in all_allocations if alive(item,start) and item['address']<=physical
                    and physical+size<=item['address']+item['capacity']]
        if not candidates:return None
        item=min(candidates,key=lambda candidate:candidate['capacity'])
        require(alive(item,end) and all(alive(parent,end) for parent in ancestors(item)),
                'File-view storage or an observed backing allocation is freed inside its use window.')
        return item
    for row in heap:
        if row['kind']<7:continue
        words=snapshots[row['entry_id']];before=list(words[:11]);after=list(words[11:])
        start,end=sdk.sequence(row,'entry_'),sdk.sequence(row)
        allocation=owner(row['a0'],44,start,start if row['kind']==8 else end)
        if row['kind']==7:
            expected=[base_table,0,0,0,0,0,before[6],before[7],0,0,0]
            require(after==expected,'Original file constructor differs from its field initialization contract.')
            constructors.append(dict(id=row['entry_id'],address=row['a0'],start=start,end=end,
                allocation_id=allocation['id'] if allocation else None))
        elif row['kind']==9:
            should_free=bool(before[4] and before[5] and not before[8]&0xFFFF)
            nested=[event for event in free_events if start<sdk.sequence(event,'entry_')<sdk.sequence(event)<end
                    and event['a0']==before[4]]
            require(len(nested)==int(should_free),'Original file release free call does not match buffer/size/ownership flags.')
            expected=before[:]
            if should_free:expected[4]=0
            require(after==expected,'Original file release changes fields outside its documented buffer clear.')
            releases.append(dict(id=row['entry_id'],address=row['a0'],freed_buffer=before[4] if should_free else None,
                native_free_id=nested[0]['entry_id'] if nested else None,allocation_id=allocation['id'] if allocation else None))
        elif row['kind']==8:
            nested=[event for event in free_events if start<sdk.sequence(event,'entry_')<sdk.sequence(event)<end
                    and event['a0']==row['a0']]
            require(row['v0']==0 and len(nested)==1,'Original file destructor lacks its exact native object free and zero result.')
            require(allocation is None or allocation['free_id']==nested[0]['entry_id'],
                    'The destructor free does not end the observed receiver allocation generation.')
            destructors.append(dict(id=row['entry_id'],address=row['a0'],native_free_id=nested[0]['entry_id']))
    # A destructor intentionally ends the backing allocation inside its call.
    # Its receiver cannot be treated as a live object at the return snapshot.
    lifecycle=sdk.link_queued_reads(entries,returns,records,transfers)
    bases={row['base_ordinal']:row for row in returns if row['kind']==1}
    by_id={row['entry_id']:row for row in records};reads=[];missing=[]
    for pair in lifecycle['pairs']:
        origin=bases[pair['origin_entry']];request=by_id[pair['request_id']];completed=by_id[pair['completion_id']]
        start,end=sdk.sequence(origin,'entry_'),sdk.sequence(completed)
        receiver=owner(origin['a0'],44,start,end)
        destination=owner(request['a1'],pair['complete_sector_bytes'],start,end)
        eligible=[row for row in constructors if row['address']==origin['a0'] and row['end']<start
                  and receiver is not None and row['allocation_id']==receiver['id']]
        if receiver is None or destination is None or not eligible:
            missing.append(dict(origin_entry=pair['origin_entry'],receiver_owned=receiver is not None,
                destination_owned=destination is not None,constructor_observed=bool(eligible)))
            continue
        constructor=max(eligible,key=lambda row:row['end'])
        reads.append(dict(origin_entry=pair['origin_entry'],replay_entry=pair['replay_entry'],
            request_id=request['entry_id'],completion_id=completed['entry_id'],
            receiver=f"0x{origin['a0']:08X}",constructor_id=constructor['id'],receiver_allocation_id=receiver['id'],
            destination_allocation_id=destination['id'],receiver_allocation_closed=receiver['end'] is not None,
            destination_allocation_closed=destination['end'] is not None,complete_sector_bytes=pair['complete_sector_bytes']))
    used={row[key] for row in reads for key in ('receiver_allocation_id','destination_allocation_id')}
    relevant=[allocations[key] for key in sorted(used)]
    return dict(status='verified_bounded_original_file_heap_history',
        boundary_calls=len(records),heap_and_file_boundary_calls=len(heap),
        successful_allocations=len(allocations),failed_allocations=failed_allocations,zero_size_allocation_requests=zero_size_requests,
        matched_frees=len(free_events)-len(unknown_frees),
        null_frees=null_frees,unobserved_allocation_frees=len(unknown_frees),
        live_allocations_at_end=len(active),file_constructors=len(constructors),file_releases=len(releases),
        file_releases_freeing_buffers=sum(row['freed_buffer'] is not None for row in releases),file_destructors=len(destructors),
        file_cleanup_calls=sum(row['kind']==10 for row in heap),
        queued_Read_lifetime_windows_qualified=len(reads),queued_Read_lifetime_windows_unqualified=len(missing),
        complete_sector_bytes_with_qualified_lifetimes=sum(row['complete_sector_bytes'] for row in reads),
        relevant_backing_allocations=len(relevant),relevant_allocations_closed=sum(row['end'] is not None for row in relevant),
        relevant_allocations_still_live=sum(row['end'] is None for row in relevant),
        reads=reads,unqualified=missing,constructors=constructors,releases=releases,destructors=destructors,
        relevant_allocation_generations=relevant,allocation_generations=all_allocations,
        whole_file_feature_accepted=False,all_object_lifetimes_accepted=False,whole_feature_groups_accepted=0,new_C_bytes=0,
        scope='Original API allocation generations, constructor/release/destructor effects, and file-view/destination liveness through observed queued SDK completion. Open lifetimes and unknown storage remain explicit; address equality alone is not identity.')

def inspect_heap(folder):
    proof,retained=sdk.inspect_sdk(folder)
    output=retained['folder']/'observations';payload=(output/'sdk-read-data.bin').read_bytes()
    records=[dict(zip(sdk.FIELDS,words)) for words in struct.iter_unpack('<116I',(output/'sdk-reads.bin').read_bytes())]
    returns=[dict(zip(RETURN_FIELDS,words)) for words in struct.iter_unpack('<150I',(output/'method-returns.bin').read_bytes())]
    model=analyze_file_heap(records,payload,retained['entries'],returns,proof['disc_transfers'],retained['program'])
    return dict(status='inspected_original_file_heap_history',SDK_verification=proof,file_heap=model),retained

def compare_heap(reference,candidate,mode='same-runtime'):
    compared=sdk.compare_sdk(reference,candidate,mode)
    before,_=inspect_heap(reference)
    if mode=='same-runtime':
        after,_=inspect_heap(candidate)
        require(before['file_heap']==after['file_heap'],'Original/rebuilt allocation generations or file-view lifetimes differ.')
    return dict(status='compared_original_file_heap_histories',mode=mode,
        every_recorded_game_output_equal=compared['every_recorded_game_output_equal'],
        heap_records_and_lifetimes_equal=mode=='same-runtime',verification=before,
        whole_file_feature_accepted=False,whole_feature_groups_accepted=0,new_C_bytes=0)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--candidate',type=Path)
    parser.add_argument('--mode',choices=('same-runtime','observer-output'),default='same-runtime')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        output=args.output.resolve()
        require(output.is_relative_to(ROOT/'.decomp-lab') and not output.exists(),'Choose a fresh private heap report.')
        report=compare_heap(args.reference,args.candidate,args.mode) if args.candidate else inspect_heap(args.reference)[0]
        report['verification_source_sha256']=sha(Path(__file__).read_bytes())
        write_json(output,report)
        model=report['verification']['file_heap'] if args.candidate else report['file_heap']
        print(json.dumps({key:value for key,value in model.items() if not isinstance(value,(dict,list))}),flush=True)
        return 0
    except (OSError,ValueError,KeyError) as error:
        print(str(error),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
