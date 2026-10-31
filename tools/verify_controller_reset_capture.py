"""Check the causal controller route, reset bytes, guards, and paired outputs."""
import base64
import gzip
import hashlib
import json
from pathlib import Path
import struct

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_TARGETS=ROOT/'research/new_game_reset/controller-functions.json'
DEFAULT_TABLE=[0x1000,0x4000,0x8000,0x2000,0x10,0x40,0x80,0x20,0x200,0x400,0x100,8,2,4,1,0x800]
def require(ok,message):
    if not ok:raise ValueError(message)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def word(raw,at):return struct.unpack_from('<I',raw,at)[0]
def load(folder):
    d={name:json.loads((folder/(name+'.json')).read_bytes()) for name in ['report','card-store']}
    d['windows']=[json.loads(line) for line in (folder/'windows.jsonl').read_text().splitlines()]
    d['snapshots']=[json.loads(line) for line in gzip.decompress((folder/'save-blocks.jsonl.gz').read_bytes()).splitlines()]
    d['entries']=[json.loads(line) for line in gzip.decompress((folder/'entries.jsonl.gz').read_bytes()).splitlines()] if (folder/'entries.jsonl.gz').exists() else []
    d['inputs']=(folder/'inputs.tsv').read_bytes()
    return d

def snapshot_object(snap):
    """Validate one complete native object and its unmasked save payload."""
    data=base64.b64decode(snap['object_base64'],validate=True)
    require(len(data)==0x928,'Truncated dream object')
    require(sha(data[0x178:0x878])==snap['save_sha256']==snap['state']['saveHash'],'Save-block hash mismatch')
    require(word(data,0)==0x80087bdc and word(data,0x180)==snap['state']['day'] and word(data,0x17c)==snap['state']['year'],'Native object field mismatch')
    require(snap['pad_table']==DEFAULT_TABLE,'Runtime controller table differs from original default')
    return data

def checks(d,mode,observer=True):
    r=d['report'];require(r['status']=='controller_reset_returned_to_menu_and_new_dream_played','Incomplete natural reset scenario')
    require(r['mode']==mode and r['observer_enabled']==observer,'Wrong scenario/core')
    for key in ['cold_start','load_seen','load_returned','reset_seen','post_menu_seen','post_dream_seen','external_card_unchanged']:require(r[key],key)
    for key in ['guest_RAM_or_instruction_writes','restored_state','player_UI_or_saves_changed','hardware_timing_verified']:require(not r[key],key)
    require(r['frames_advanced']==r['last_frame']+1 and r['last_frame']-r['post_dream_frame']>=180,'Incomplete playable post-reset window')
    require(r['replay_entries_used']==r['replay_entries_supplied'],'Unconsumed replay input')
    schedule=[tuple(map(int,line.split(b'\t'))) for line in d['inputs'].splitlines()[1:]]
    require(schedule and schedule[0]==(0,0) and all(a[0]<b[0] for a,b in zip(schedule,schedule[1:])),'Controller order')
    require(all(0<=mask<64 for _,mask in schedule),'Controller bit bound')
    end=-1;channel_bytes={};channel_hashes=[]
    for row in d['windows']:
        require(row['first_frame']==end+1 and row['frames']==row['last_frame']-row['first_frame']+1,'Missing/overlapping capture frames')
        for name,size in row['payload_bytes'].items():channel_bytes[name]=channel_bytes.get(name,0)+size
        require(set(row['framed_sha256'])=={'MainRAM','GPURAM','RGB','PCM','native','controller'},'Incomplete streamed outputs')
        require(all(len(s)==64 and int(s,16)>=0 for s in row['framed_sha256'].values()),'Malformed channel digest')
        end=row['last_frame'];channel_hashes.append(row['framed_sha256'])
    require(end==r['last_frame'] and channel_bytes['MainRAM']==r['frames_advanced']*0x200000 and channel_bytes['GPURAM']==r['frames_advanced']*0x100000,'Complete native-memory frame coverage')
    require(channel_bytes['PCM']==r['total_PCM_sample_frames']*4,'Complete PCM sample count')
    snaps=d['snapshots'];require(len(snaps)>=20,'Sparse reset evidence absent')
    ages={};objects={}
    for snap in snaps:
        data=snapshot_object(snap)
        objects[snap['frame']]=data
        if snap['sequence_age']>=0:ages[snap['sequence_age']]=snap
    # Age140 is inside the release/poll transition; age150 checks its stable
    # result, and native entries below verify the actual release callback.
    expectations={20:(False,0),50:(False,0),110:(True,0),130:(True,1),150:(True,0),170:(True,0),200:(False,0),230:(True,0),250:(True,1)}
    require(0 in ages,'Missing pre-input dream context')
    baseline=ages[0]['state']
    require(baseline['year']==0 and baseline['stored']>=1 and baseline['flash']==(mode=='flashback'),'Loaded QA context identity')
    require(baseline['day']==baseline['stored'] if mode=='normal' else 0<=baseline['day']<baseline['stored'],'Original ordinary/flashback day selection')
    guards=[]
    for age,(text,armed) in expectations.items():
        require(age in ages,'Missing guarded context age '+str(age));state=ages[age]['state']
        require((state['text']!=0)==text and state['armed']==armed and state['active'],'Unexpected guard state at age '+str(age))
        require(all(state[k]==baseline[k] for k in ['year','day','stored','flash']),'Guard changed original day/mode')
        guards.append(dict(age=age,text_active=text,armed=armed))
    reset_frame=r['reset_frame'];require(reset_frame-r['sequence_start']>=252,'Reset occurred during guarded input')
    require(reset_frame in objects,'No complete post-reset object at observed reset frame')
    prior=max(f for f in objects if f<reset_frame);old=objects[prior];new=objects[reset_frame]
    expected=bytearray(old[0x178:0x878]);struct.pack_into('<I',expected,0,0x0031304a)
    zero_words=[0x17c,0x180,0x184,0x188,0x18c,0x46c,0x600,0x67c,0x680]
    written=set(range(4))
    for at in zero_words:
        struct.pack_into('<I',expected,at-0x178,0);written.update(range(at-0x178,at-0x174))
    for at in [0x5d8,0x5df]:expected[at-0x178]=0;written.add(at-0x178)
    expected[0x5e0-0x178:0x5fe-0x178]=bytes(30);written.update(range(0x5e0-0x178,0x5fe-0x178))
    struct.pack_into('<I',expected,0x678-0x178,1);written.update(range(0x678-0x178,0x67c-0x178))
    expected[0x684-0x178:]=bytes(500);written.update(range(0x684-0x178,1792))
    require(len(written)==576 and new[0x178:0x878]==expected and word(new,0x878)==1,'Complete natural reset save-block transformation differs')
    preserved=[i for i in range(1792) if i not in written];nonzero=sum(old[0x178+i]!=0 for i in preserved)
    native_proof={}
    if observer:
        events=d['entries'];pins={t['pc']:t for t in json.loads(DEFAULT_TARGETS.read_bytes())};counts={t['name']:0 for t in pins.values()}
        for event in events:
            require(event['pc'] in pins,'Unexpected entry target');t=pins[event['pc']]
            require(event['name']==t['name'] and event['code_bytes']==t['bytes'] and event['code_sha256']==t['sha256'],'Complete native body qualification differs')
            counts[t['name']]+=1
        require(len(events)==r['native_entries'] and counts==r['native_entry_counts'],'Native event coverage mismatch')
        resets=[e for e in events if e['name']=='dream_sys_init_new_game'];require(len(resets)==r['native_reset_calls']==1,'Reset call cardinality')
        require(resets[0]['frame']==reset_frame and resets[0]['a0']==(ages[250]['state']['dream']|0x80000000),'Reset receiver/frame differs')
        same=[e for e in events if e['frame']==reset_frame];names=[e['name'] for e in same]
        chain=['func_80054208','func_800543FC','dream_session_on_link_code','dream_sys_end_day','dream_sys_init_new_game','init_nav_challenges_array']
        cursor=-1;selected=[]
        for name in chain:
            cursor=next((i for i in range(cursor+1,len(same)) if same[i]['name']==name),-1);require(cursor>=0,'Native reset causal chain missing '+name);selected.append(same[cursor])
        require(selected[0]['memory_words'][3]==1 and selected[2]['a2']==13 and selected[3]['a1']==2,'Armed link-code13 / end-mode2 arguments differ')
        require(selected[3]['memory_words'][1]==(mode=='flashback'),'Native end-day flashback mode differs')
        before=[e for e in same if e['name']=='func_80053358'];codes=[e['a2'] for e in before]
        require(0x0c in codes and 0x16 in codes and codes.index(0x0c)<codes.index(0x16),'Held Select must arm before pressed Triangle')
        ignored=[]
        for lo,hi in [(10,22),(42,56),(90,102),(148,160)]:
            es=[e for e in events if lo<=e['frame']-r['sequence_start']<=hi and e['name']=='func_80054208']
            require(es and all(e['memory_words'][3]==0 for e in es),'Missing unarmed native confirm guard '+str(lo));ignored.extend(es)
        require(any(e['name']=='func_80053358' and e['a2']==0x2c and 137<=e['frame']-r['sequence_start']<=147 for e in events),'Missing released-Select dispatch')
        mappings={65:0x800,120:0x100,95:0x10,45:0x110}
        for age,mask in mappings.items():
            es=[e for e in events if age-3<=e['frame']-r['sequence_start']<=age+3 and e['name']=='func_80025D10']
            require(es and all(e['receiver_words'][4]==mask for e in es),'Physical-to-guest controller mapping '+str(age))
        native_proof=dict(entries=len(events),complete_registered_bodies=len(pins),body_bytes=sum(t['bytes'] for t in pins.values()),
            observed_reset_chain=chain,unarmed_confirm_calls=len(ignored),original_new_game_calls=1,held_Select_precedes_pressed_Triangle=True)
    return dict(passed_original_scenario=True,mode=mode,frames=r['frames_advanced'],reset_frame=reset_frame,
      native_day_before_reset=baseline['day'],native_stored_day_before_reset=baseline['stored'],
      sequence_start=r['sequence_start'],post_dream_frames=r['last_frame']-r['post_dream_frame'],guard_snapshots=guards,
      save_bytes_compared=1792,reset_written_bytes=576,preserved_bytes=1216,nonzero_preserved_bytes=nonzero,
      before_reset_snapshot_frame=prior,native=native_proof,streamed_payload_bytes=channel_bytes,
      original_QA_card_unchanged=True,no_guest_memory_or_code_write=True,whole_feature_groups_accepted=0,
      full_feature_or_hardware_parity_proven=False)

def paired(a,b):
    require(a['inputs']==b['inputs'],'Paired controller submissions differ')
    require(a['windows']==b['windows'],'Paired full-frame RAM/GPU/RGB/PCM/native/controller aggregates differ')
    require(a['snapshots']==b['snapshots'],'Paired complete object snapshots differ')
    require(a['card-store']==b['card-store'],'Paired external-card setup differs')
    for key in ['frames_advanced','sequence_start','reset_frame','post_dream_frame','final_SaveRAM_sha256','final_state','total_PCM_sample_frames']:
        require(a['report'][key]==b['report'][key],'Paired report differs: '+key)
    return dict(passed=True,frames=a['report']['frames_advanced'],windows=len(a['windows']),
        full_native_objects=len(a['snapshots']),PCM_sample_frames=a['report']['total_PCM_sample_frames'],
        all_framed_RAM_GPU_RGB_PCM_native_controller_hashes_equal=True,all_complete_save_objects_equal=True,
        final_memory_card_equal=True,serialized_whole_core_or_hardware_state_compared=False)

if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',type=Path,required=True)
    parser.add_argument('--mode',choices=['normal','flashback'],required=True)
    parser.add_argument('--compare',type=Path)
    parser.add_argument('--stock',action='store_true',help='The comparison capture uses the installed stock core.')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.stock and args.compare is None:parser.error('--stock requires --compare')
    original=load(args.capture)
    result=checks(original,args.mode)
    if args.compare:
        other=load(args.compare)
        checks(other,args.mode,observer=not args.stock)
        comparison=paired(original,other)
        if not args.stock:require(original['entries']==other['entries'],'Paired native entry records differ')
        result=dict(original=result,comparison=comparison,stock_core_comparison=args.stock)
    result['verifier_sha256']=sha(Path(__file__).read_bytes())
    with args.output.open('x',encoding='utf-8') as out:json.dump(result,out,indent=2)
    print(json.dumps(result))
