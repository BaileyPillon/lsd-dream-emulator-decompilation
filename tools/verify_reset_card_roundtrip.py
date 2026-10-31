"""Verify native reset/Save or cold-Load evidence without masking card bytes."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from tools.compare_card_roundtrip import parse_card
from tools.new_game_state import end_day, reset_write_offsets
from tools.verify_controller_reset_capture import load, paired, require, sha, snapshot_object, word

DEFAULT_TARGETS=ROOT/'research/card_roundtrip/reset-controller-functions.json'
VIRTUAL_SAVE_WARNING='Memcard 0 save error: Error opening file "SAV:0.mcr" for writing: No such file or directory'


def card_records(raw):
    records=parse_card(raw)
    result={}
    for entry in records:
        body=entry['data']
        require(len(body)>=2304 and body[:4]==b'SC\x13\x01','Unexpected LSD card header')
        require(body[512:516]==b'J01\0','Unexpected native save marker')
        result[entry['filename']]=dict(blocks=entry['blocks'],body=body,payload=body[512:2304])
    return result


def core_evidence(data,mode,targets,observer):
    r=data['report'];status={'save':'reset_native_save_completed','load':'native_cold_load_and_new_dream_completed'}
    require(mode in status and r['mode']==mode and r['status']==status[mode],'Incomplete or wrong card scenario')
    require(r['observer_enabled']==observer,'Wrong core variant')
    for key in ['cold_start','load_seen','load_returned']:require(r[key],key)
    for key in ['guest_RAM_or_instruction_writes','restored_state','player_UI_or_saves_changed','hardware_timing_verified']:require(not r[key],key)
    require(r['frames_advanced']==r['last_frame']+1 and r['replay_entries_used']==r['replay_entries_supplied'],'Frame/replay cardinality')
    schedule=[tuple(map(int,line.split(b'\t'))) for line in data['inputs'].splitlines()[1:]]
    require(schedule and schedule[0]==(0,0) and all(a[0]<b[0] for a,b in zip(schedule,schedule[1:])),'Controller order')
    require(all(0<=frame<=r['last_frame'] and 0<=mask<64 for frame,mask in schedule),'Controller frame/mask')
    end=-1;totals={};samples=0
    for row in data['windows']:
        require(row['first_frame']==end+1 and row['frames']==row['last_frame']-end,'Missing/overlapping streamed frames')
        require(1<=row['frames']<=300,'Invalid streamed window length')
        require(set(row['framed_sha256'])=={'MainRAM','GPURAM','RGB','PCM','native','controller'},'Missing channel')
        require(all(len(s)==64 and int(s,16)>=0 for s in row['framed_sha256'].values()),'Invalid channel digest')
        sizes=row['payload_bytes'];require(set(sizes)==set(row['framed_sha256']),'Missing channel byte count')
        require(sizes['MainRAM']==row['frames']*0x200000 and sizes['GPURAM']==row['frames']*0x100000
            and sizes['controller']==row['frames']*4 and sizes['PCM']==row['PCM_sample_frames']*4,'Incomplete window payload')
        for name,size in row['payload_bytes'].items():totals[name]=totals.get(name,0)+size
        samples+=row['PCM_sample_frames'];end=row['last_frame']
    require(end==r['last_frame'] and totals['MainRAM']==r['frames_advanced']*0x200000 and totals['GPURAM']==r['frames_advanced']*0x100000,'Incomplete whole-memory frames')
    require(samples==r['total_PCM_sample_frames'] and totals['PCM']==samples*4,'Incomplete PCM')
    objects={snap['frame']:snapshot_object(snap) for snap in data['snapshots']}
    frames=[snap['frame'] for snap in data['snapshots']]
    require(objects and frames==sorted(objects) and all(0<=f<=r['last_frame'] for f in frames),'Invalid full-object frame order')
    pins={row['pc']:row for row in targets};require(len(pins)==16,'Require the qualified16-target profile')
    if observer:
        counts={row['name']:0 for row in targets}
        for entry in data['entries']:
            require(entry['pc'] in pins,'Unknown native entry');pin=pins[entry['pc']]
            require(entry['name']==pin['name'] and entry['code_bytes']==pin['bytes'] and entry['code_sha256']==pin['sha256'],'Native code range pin differs')
            counts[entry['name']]+=1
        require(counts==r['native_entry_counts'] and sum(counts.values())==r['native_entries'],'Native entry count mismatch')
    else:require(not data['entries'] and r['native_entries']==0 and all(n==0 for n in r['native_entry_counts'].values()),'Stock capture contains observer entries')
    return objects,totals


def successful_card_callbacks(data,expected,root):
    entries=data['entries'];success=[]
    for i,entry in enumerate(entries):
        if entry['name']!='func_8004E230' or entry['a2']!=22:continue
        require(entry['receiver_words'][0]==0x80086b60,'Card callback receiver')
        following=next((e for e in entries[i+1:] if e['name']=='dream_sys_clear_new_game'),None)
        require(following is not None and following['frame']==entry['frame'] and following['a0']==root and following['ra']==0x8004e2a0,'Success callback must execute the original flag clear')
        success.append(entry)
    require(len(success)==expected,'Successful card callback cardinality')
    return success


def audit_capture(folder,input_card,mode,targets=DEFAULT_TARGETS,observer=True,stderr=None):
    folder=Path(folder);data=load(folder);r=data['report'];pins=json.loads(Path(targets).read_bytes())
    objects,totals=core_evidence(data,mode,pins,observer)
    seed=Path(input_card).read_bytes();seed_records=card_records(seed)
    require(sha(seed)==r['input_card_sha256']==data['card-store']['input_card_sha256']==data['card-store']['stored_SaveRAM_sha256'],'Input card identity differs')
    require(r['target_filename'] in seed_records,'Target logical file absent')
    wanted=seed_records[r['target_filename']]['payload']
    require(sha(wanted)==r['expected_loaded_payload_sha256']==data['card-store']['expected_payload_sha256'],'Pinned input payload differs')
    idle=r['initial_load_idle_frame'];require(idle in objects and objects[idle][0x178:0x878]==wanted and word(objects[idle],0x878)==0,'Complete cold-loaded payload/flag differs')
    initial=min(objects);require(r['pre_load_payload_sha256']==sha(objects[initial][0x178:0x878]) and r['pre_load_payload_sha256']!=sha(wanted),'Cold RAM was already the requested payload')
    root=next(s['state']['dream'] for s in data['snapshots'] if s['frame']==idle)|0x80000000
    callbacks=successful_card_callbacks(data,2 if mode=='save' else 1,root) if observer else []
    reads=[e for e in data['entries'] if e['name']=='memory_card_read_data_impl']
    if observer:
        require(len(reads)==1 and reads[0]['a2']==root+0x178 and reads[0]['a3']==1792,'Native logical read target/size differs')
        require(reads[0]['frame']<=callbacks[0]['frame']<=idle,'Cold read/success/idle order')
    transitions=[json.loads(line) for line in gzip.decompress((folder/'transitions.jsonl.gz').read_bytes()).splitlines()]
    data['transitions']=transitions
    selectors=[row for row in transitions if row['selection']['ready']]
    require(selectors and all(row['selection']['names'][row['selection']['targetIndex']]==r['target_filename'] for row in selectors),'Actual native file chooser target missing')
    result=dict(passed=True,mode=mode,frames=r['frames_advanced'],windows=len(data['windows']),complete_objects=len(objects),
       full_streamed_payload_bytes=totals,native_entries=r['native_entries'],target_filename=r['target_filename'],cold_load_idle_frame=idle,
       initial_RAM_payload_differs_from_loaded_card=True,loaded_payload_bytes=1792,successful_card_callback_frames=[e['frame'] for e in callbacks],
       registered_targets=16,registered_body_bytes=sum(p['bytes'] for p in pins),
       complete_body_RAM_ranges_checked_at_entry=observer,instruction_by_instruction_execution_coverage=False,
       whole_feature_groups_accepted=0,whole_goal_complete=False)
    if mode=='save':
        require(r['reset_seen'] and r['save_seen'] and r['save_idle'] and r['post_menu_seen'],'Missing reset/Save/UI lifecycle')
        require(r['reset_frame']<r['save_seen_frame']<=r['save_idle_frame'] and r['last_frame']-r['save_idle_frame']>=120,'Save lifecycle/window order')
        require(not r['external_card_unchanged'] and r['final_card_matches_native_Save'],'Native card did not change or stabilize')
        reset=r['reset_frame'];require(reset in objects and r['save_idle_frame'] in objects,'Missing reset/Save boundaries')
        prior=max(f for f in objects if f<reset);predicted,_=end_day(objects[prior],2,0x0031304a)
        require(objects[reset][0x178:0x878]==predicted[0x178:0x878] and word(objects[reset],0x878)==1,'Complete reset transform differs')
        saved_bytes=(folder/'saved-card.SaveRAM').read_bytes();saved_records=card_records(saved_bytes)
        require(sha(saved_bytes)==r['native_saved_card_sha256']==r['final_SaveRAM_sha256'],'Exported native card identity differs')
        require(r['saved_filename'] in saved_records,'Native-written logical file absent')
        written=saved_records[r['saved_filename']]['payload']
        require(written==objects[reset][0x178:0x878]==objects[r['save_idle_frame']][0x178:0x878],'Save did not persist the entire reset block')
        require(sha(written)==r['reset_payload_sha256']==r['saved_payload_sha256'] and word(objects[r['save_idle_frame']],0x878)==0,'Saved payload or cleared flag differs')
        require(all(name in saved_records and row['body']==saved_records[name]['body'] for name,row in seed_records.items() if name!=r['saved_filename']),'Unrelated existing file changed')
        if observer:
            writes=[e for e in data['entries'] if e['name']=='memory_card_write_file']
            require(len(writes)==1 and r['save_seen_frame']<=writes[0]['frame']<=callbacks[1]['frame']<=r['save_idle_frame'] and writes[0]['a3']==3,'Native write/success/idle ordering or icon count differs')
            chain=[e for e in data['entries'] if e['frame']==reset]
            wanted_chain=['func_80054208','func_800543FC','dream_session_on_link_code','dream_sys_end_day','dream_sys_init_new_game','init_nav_challenges_array']
            cursor=-1;chosen=[]
            for name in wanted_chain:
                cursor=next((i for i in range(cursor+1,len(chain)) if chain[i]['name']==name),-1);require(cursor>=0,'Missing original reset chain');chosen.append(chain[cursor])
            require(chosen[0]['memory_words'][3]==1 and chosen[2]['a2']==13 and chosen[3]['a1']==2,'Reset causal arguments differ')
        offsets=reset_write_offsets();preserved=[i for i in range(0x178,0x878) if i not in offsets]
        result.update(saved_filename=r['saved_filename'],saved_card_sha256=sha(saved_bytes),saved_payload_sha256=sha(written),
           active_card_files=list(saved_records),unrelated_files_preserved=[name for name in seed_records if name!=r['saved_filename']],
           reset_store_footprint_from_prior_VM=len(offsets),preserved_payload_bytes=len(preserved),
           nonzero_preserved_payload_bytes=sum(objects[prior][i]!=0 for i in preserved),save_idle_frame=r['save_idle_frame'])
    else:
        require(r['post_menu_seen'] and r['post_dream_seen'] and r['last_frame']-r['post_dream_frame']>=180,'Incomplete playable cold-load continuation')
        require(r['external_card_unchanged'] and r['final_SaveRAM_sha256']==sha(seed),'Read-only scenario changed the card')
        require(not r['reset_seen'] and r['native_reset_calls']==0 and not any(e['name']=='memory_card_write_file' for e in data['entries']),'Cold Load unexpectedly reset or saved')
        result.update(post_load_dream_frames=r['last_frame']-r['post_dream_frame'],input_card_unchanged=True,active_card_files=list(seed_records))
    if stderr is not None:
        message=Path(stderr).read_text(encoding='utf-8',errors='strict')
        require(message.replace(VIRTUAL_SAVE_WARNING,'').strip()=='','Unexpected core diagnostic')
        result['core_virtual_auto_save_warning_count']=message.count(VIRTUAL_SAVE_WARNING)
        # No warning on a read-only Load does not prove virtual-file persistence.
        result['native_virtual_file_auto_flush_verified']=False
        result['supported_ISaveRam_export_is_the_persistence_path']=True
    return result,data


def compare_captures(a,b,left,right,stock=False):
    """Compare every recorded output; observer entries have no stock equivalent."""
    result=paired(a,b)
    require(a['transitions']==b['transitions'],'Paired native card/menu transitions differ')
    fields=['mode','status','initial_load_idle_frame','save_seen_frame','save_idle_frame',
        'load_seen','load_returned','reset_seen','post_menu_seen','post_dream_seen',
        'save_seen','save_idle','pre_load_payload_sha256','expected_loaded_payload_sha256',
        'target_filename','reset_payload_sha256','saved_payload_sha256','saved_filename',
        'input_card_sha256','native_saved_card_sha256','external_card_unchanged',
        'final_card_matches_native_Save','reset_payload_matches_saved_payload']
    for key in fields:require(a['report'][key]==b['report'][key],'Paired card report differs: '+key)
    if not stock:require(a['entries']==b['entries'],'Paired native entry records differ')
    if a['report']['mode']=='save':
        require((Path(left)/'saved-card.SaveRAM').read_bytes()==(Path(right)/'saved-card.SaveRAM').read_bytes(),'Paired native-written cards differ')
        result['full_native_written_card_bytes_equal']=True
    result.update(native_card_menu_transitions_equal=True,native_entry_records_compared=not stock,
        native_entry_pairs=0 if stock else len(a['entries']),stock_core_comparison=stock)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture',type=Path,required=True);p.add_argument('--input-card',type=Path,required=True)
    p.add_argument('--mode',choices=['save','load'],required=True);p.add_argument('--targets',type=Path,default=DEFAULT_TARGETS)
    p.add_argument('--compare',type=Path);p.add_argument('--compare-input-card',type=Path);p.add_argument('--compare-stderr',type=Path)
    p.add_argument('--stock',action='store_true');p.add_argument('--stderr',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.compare is None and (args.compare_input_card is not None or args.compare_stderr is not None):p.error('Comparison options require --compare')
    result,data=audit_capture(args.capture,args.input_card,args.mode,args.targets,not args.stock if args.compare is None else True,args.stderr)
    if args.compare is not None:
        other_card=args.compare_input_card or args.input_card
        other,other_data=audit_capture(args.compare,other_card,args.mode,args.targets,not args.stock,args.compare_stderr)
        require(args.input_card.read_bytes()==other_card.read_bytes(),'Paired input card bytes differ')
        result=dict(original=result,other=other,comparison=compare_captures(data,other_data,args.capture,args.compare,args.stock))
    result['verifier_sha256']=sha(Path(__file__).read_bytes())
    with args.output.open('x',encoding='utf-8') as out:json.dump(result,out,indent=2)
    print(json.dumps(result))


if __name__=='__main__':
    main()
