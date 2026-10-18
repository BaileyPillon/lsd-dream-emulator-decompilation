"""Verify retained original SDK calls, completed sector RAM and disc positions.

The logical cursor comes from successful original Setloc calls and successful
sector reads, never from a receiver's cached file-start position. This is bounded
emulator evidence, not hardware timing or complete original-game acceptance.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PureWindowsPath
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.dispatch_returns import _instruction,_jump_return,bcd_lba,Form1Disc
from tools.dispatch_returns import FIELDS as RETURN_FIELDS
from tools.inspect_read_lifecycle import analyze_read_lifecycle
from tools.inspect_dispatch_history import inspect,compare
from tools.compare_npc_history import owned_file,files_equal
from tools.runtime_inputs import record_file,content_identity
from tools.replay_cold_start_headless import require,write_json
from tools.psx_image import executable_offset

CONTEXT=('pc','ram','fetch','rs','sp','flags','sr')
FIELDS=('frame','ordinal','entry_id','parent_id','kind','entry_frame','entry_timestamp',
    'entry_pc','entry_sp','entry_ra','a0','a1','a2','a3','return_pc','return_sp','return_ra','v0','v1','timestamp',
    'entry_sequence_low','entry_sequence_high','sequence_low','sequence_high',
    *(prefix+'_'+field for prefix in ('entry_jump','entry_delay','jump','delay') for field in CONTEXT),
    'entry_sr','sr','arg_readable',*('arg_word_'+str(i) for i in range(4)),
    *('entry_sdk_word_'+str(i) for i in range(16)),*('sdk_word_'+str(i) for i in range(16)),
    *('entry_cd_word_'+str(i) for i in range(8)),*('cd_word_'+str(i) for i in range(8)),
    'code_bytes','code_offset','buffer_address','buffer_bytes','buffer_offset','buffer_status',
    'transfer_id','transfer_sectors','transfer_mode')
EVENT_BYTES=464
assert len(FIELDS)*4==EVENT_BYTES
sha=lambda data:hashlib.sha256(data).hexdigest()

def sequence(row,prefix=''):
    return row[prefix+'sequence_low'] | row[prefix+'sequence_high']<<32

def _stack_after_delay(row,prefix,target):
    jump,delay=row[prefix+'jump_sp'],row[prefix+'delay_sp']
    require(jump==delay,'SDK transfer changed SP before its delay instruction.')
    word=row[prefix+'delay_fetch']
    if word>>16==0x27BD:
        expected=(delay+(((word&65535)^32768)-32768))&0xFFFFFFFF
    else:
        # Reject unmodelled writes to SP rather than assuming their effect.
        op=word>>26;rd=(word>>11)&31;rt=(word>>16)&31
        require(not (op==0 and rd==29 and word&63 not in (8,12,13,17,19,24,25,26,27))
                and not (op not in (0,1,2,3,4,5,6,7,40,41,42,43,46) and rt==29),
                'Unmodelled SDK transfer delay-slot SP write.')
        expected=delay
    require(expected==target,'SDK transfer delay-slot stack does not reach captured SP.')

def validate_records(data,payload,summary,targets,executable,program):
    require(isinstance(data,bytes) and isinstance(payload,bytes) and len(data)%EVENT_BYTES==0,
            'Truncated SDK transport.')
    records=[dict(zip(FIELDS,values)) for values in struct.iter_unpack('<116I',data)]
    require(summary.get('protocol')==1 and summary.get('event_bytes')==EVENT_BYTES
            and summary.get('returns')==summary.get('native_returns')==summary.get('native_entries')==len(records)
            and summary.get('payload_bytes')==len(payload) and summary.get('targets')==targets
            and summary.get('native_overflow')==0 and summary.get('pending_calls')==0
            and summary.get('pending_transfer')==0 and summary.get('frame_payload_limit') in (8*1024*1024,32*1024*1024)
            and summary.get('original_game_RAM_injected') is False
            and summary.get('original_CPU_source_modified') is False,
            'Incomplete SDK native totals, transport, call stack or transfer state.')
    require(records,'No SDK boundaries were observed.')
    by_pc={row['pc']:row for row in targets}
    require(len(by_pc)==len(targets),'Duplicate SDK target.')
    ids={row['entry_id']:row for row in records}
    require(set(ids)==set(range(1,len(records)+1)),'SDK entries were lost or duplicated.')
    cursor=0;previous_sequence=-1;previous_frame=-1;max_depth=0
    for ordinal,row in enumerate(records,1):
        target=by_pc.get(row['entry_pc'])
        require(target is not None and target['kind']==row['kind'] and target['bytes']==row['code_bytes'],
                'Unexpected or incomplete SDK callee range.')
        require(row['ordinal']==ordinal and sequence(row)>previous_sequence and row['frame']>=previous_frame
                and sequence(row,'entry_')<sequence(row)
                and program['method_trace']['arm_frame']<=row['entry_frame']<=row['frame']<=program['frames'],
                'SDK call/return sequence or frame order disagrees.')
        previous_sequence,previous_frame=sequence(row),row['frame']
        require(not (row['entry_sr']|row['sr'])&0x10000 and row['entry_ra']==row['return_pc']==row['return_ra']
                and row['entry_sp']==row['return_sp'],
                'SDK return target, saved stack or cache-isolation state disagrees.')
        at=executable_offset(executable,row['entry_pc'],row['code_bytes'])
        require(row['code_offset']==cursor and payload[cursor:cursor+row['code_bytes']]==executable[at:at+row['code_bytes']],
                'Complete SDK entry code or payload coverage differs from the original.')
        cursor+=row['code_bytes']
        if row['buffer_bytes']:
            require(row['buffer_offset']==cursor and row['buffer_bytes']<=len(payload)-cursor,
                    'Completed SDK RAM payload is truncated, overlaps or has a gap.')
            cursor+=row['buffer_bytes']
        else:require(row['buffer_offset']==0,'Empty SDK RAM has an offset.')
        for part in ('entry_jump','entry_delay'):
            _instruction(executable,*(row[part+'_'+name] for name in ('pc','ram','fetch','flags','sr')))
        word=row['entry_jump_fetch'];pc=row['entry_jump_pc']
        direct=word>>26==3 and row['entry_ra']==pc+8 and \
            (((pc+4)&0xF0000000)|((word&0x03FFFFFF)<<2))==row['entry_pc']
        indirect=False;tail=False
        if program['method_trace'].get('heap_lifetime',False):
            indirect=(word&0xFC1F07FF)==9 and (word>>11)&31==31 and \
                row['entry_jump_rs']==row['entry_pc'] and row['entry_ra']==pc+8
            tail=(word>>26==2 and (((pc+4)&0xF0000000)|((word&0x03FFFFFF)<<2))==row['entry_pc']) or \
                ((word&0xFC1FFFFF)==8 and row['entry_jump_rs']==row['entry_pc'])
        require(row['entry_delay_pc']==pc+4 and (direct or indirect or tail),
                'SDK/heap entry lacks its actual original transfer and delay context.')
        _stack_after_delay(row,'entry_',row['entry_sp'])
        _jump_return(row,executable,target=row['entry_ra'],span=(row['entry_pc'],row['code_bytes']))
        _stack_after_delay(row,'',row['return_sp'])
        depth=1;child=row;seen=set()
        while child['parent_id']:
            require(child['parent_id'] in ids and child['parent_id'] not in seen,'Invalid SDK parent chain.')
            seen.add(child['parent_id']);parent=ids[child['parent_id']]
            require(sequence(parent,'entry_')<sequence(child,'entry_')<sequence(child)<sequence(parent),
                    'SDK nested call interval disagrees with its parent.')
            child=parent;depth+=1
        max_depth=max(max_depth,depth)
    require(cursor==len(payload) and max_depth==summary.get('max_depth'),
            'SDK payload has unreferenced bytes or native call depth disagrees.')
    entered=sorted(records,key=lambda row:sequence(row,'entry_'))
    require([row['entry_id'] for row in entered]==list(range(1,len(records)+1)),
            'SDK entry IDs do not follow instruction order.')
    stack=[]
    for _,phase,row in sorted((sequence(row,prefix),kind,row) for row in records
                              for prefix,kind in (('entry_',0),('',1))):
        if phase==0:
            require(row['parent_id']==(stack[-1] if stack else 0),
                    'SDK parent does not match the actual instruction-order call stack.')
            stack.append(row['entry_id'])
        else:
            require(stack and stack.pop()==row['entry_id'],'SDK returns cross or lose a nested call.')
    require(not stack,'SDK calls remain pending after the final native return.')
    return dict(calls=len(records),max_depth=max_depth,
        call_counts={f'0x{pc:08X}':count for pc,count in sorted(Counter(row['entry_pc'] for row in records).items())},
        complete_code_bytes_compared=sum(row['code_bytes'] for row in records),
        payload_bytes=len(payload)),records

def verify_transfers(records,payload,summary,stream):
    disc=Form1Disc(stream);cursor=None;pending=None;completions=[];setlocs=[]
    timeline=sorted((sequence(row,prefix),kind,row) for row in records
                    for prefix,kind in (('entry_',0),('',1)))
    entry_positions={};requests=0;polls=0;busy=0;controls=Counter();sync=Counter()
    for _,phase,row in timeline:
        if phase==0:
            if row['kind']==1:
                require(pending is None,'SDK request overlaps an unfinished transfer.')
                require(cursor is not None,'SDK request has no observed successful Setloc/position history.')
                require(row['a0']>0 and row['a2']==0x80,'Unsupported original SDK sector count or mode.')
                entry_positions[row['entry_id']]=cursor
            continue
        if row['kind']==3:
            controls[row['a0']]+=1
            if row['a0']==2 and row['v0']:
                require(pending is None and row['arg_readable']==1 and row['a1']!=0,
                        'Setloc has no captured position or changes an active transfer.')
                cursor=bcd_lba(row['arg_word_0'])
                setlocs.append(dict(entry_id=row['entry_id'],lba=cursor))
        elif row['kind']==4:
            sync[row['v0']]+=1
            require(row['v0']!=5,'CD sync error needs an explicitly verified retry history.')
        elif row['kind']==1:
            requests+=1
            require(row['v0']==1,'SDK request failure needs an explicitly verified retry history.')
            pending=dict(id=row['entry_id'],sectors=row['a0'],destination=row['a1'],mode=row['a2'],
                         lba=entry_positions[row['entry_id']],request=row)
            require(row['sdk_word_1']==row['a0'] and row['sdk_word_2']==row['a1']
                    and row['sdk_word_4']==row['a2'] and row['sdk_word_5']==512,
                    'Original SDK backend request state differs from the captured invocation.')
        active=pending
        require((row['transfer_id'],row['transfer_sectors'],row['transfer_mode'])==
                ((active['id'],active['sectors'],active['mode']) if active else (0,0,0)),
                'SDK transfer identity, sector count or mode disagrees with native history.')
        if row['kind']==2:
            polls+=1
            require(active is not None,'SDK completion poll has no recorded successful request.')
            if 0<row['v0']<0x80000000:
                busy+=1
                require(row['buffer_status']==row['buffer_bytes']==row['buffer_address']==0,
                        'A busy SDK poll cannot claim completed sector RAM.')
                continue
            require(row['v0']==0 and row['buffer_status']==1,'SDK read error or unqualified completion.')
            require(row['buffer_address']==active['destination'] and row['buffer_bytes']==active['sectors']*2048
                    and row['sdk_word_1']==active['sectors'] and row['sdk_word_2']==active['destination']
                    and row['sdk_word_3']==active['destination']+active['sectors']*2048
                    and row['sdk_word_4']==0x80 and row['sdk_word_5']==512,
                    'Completed SDK destination, full-sector length or backend write cursor disagrees.')
            start=row['buffer_offset'];actual=payload[start:start+row['buffer_bytes']]
            expected=disc.extent(active['lba'],row['buffer_bytes'])
            require(actual==expected,'Complete SDK completion RAM differs from original disc sectors at the observed logical cursor.')
            paths=[]
            for (lba,size),names in disc.files.items():
                if lba<=active['lba']<lba+(size+2047)//2048 and active['lba']+active['sectors']<=lba+(size>>11)+1:
                    paths.extend(names)
            completions.append(dict(request_id=active['id'],completion_id=row['entry_id'],
                request_frame=active['request']['entry_frame'],completion_frame=row['frame'],
                request_call=f"0x{active['request']['entry_jump_pc']:08X}",lba=active['lba'],
                sectors=active['sectors'],bytes=row['buffer_bytes'],destination=f"0x{active['destination']:08X}",
                complete_buffer_sha256=sha(actual),containing_ISO_paths=paths))
            cursor=active['lba']+active['sectors'];pending=None
        elif row['kind']<=4:
            require(row['buffer_status']==row['buffer_bytes']==row['buffer_address']==0,
                    'A request/control/sync return cannot claim completed read RAM.')
    require(pending is None and requests==len(completions)==summary.get('completions')
            and summary.get('failed_transfers')==summary.get('unassociated_polls')==summary.get('overlapping_requests')==0,
            'SDK transfer history is incomplete or native completion counts disagree.')
    sectors={lba for row in completions for lba in range(row['lba'],row['lba']+row['sectors'])}
    return dict(successful_requests=requests,poll_returns=polls,busy_poll_returns=busy,
        completed_transfers=len(completions),complete_sector_RAM_bytes_compared=sum(row['bytes'] for row in completions),
        distinct_disc_sectors_compared=len(sectors),observed_Setlocs=len(setlocs),
        completed_requests_by_call=dict(Counter(row['request_call'] for row in completions)),
        control_command_counts={str(key):value for key,value in sorted(controls.items())},
        sync_result_counts={str(key):value for key,value in sorted(sync.items())},
        Setlocs=setlocs,transfers=completions,
        physical_drive_transfer_count_claimed=False,all_error_retry_paths_accepted=False,
        cursor_scope='Observed successful Setloc plus completed original mode-0x80 sector counts; cached receiver start positions are not reused for sequential reads.')

def inspect_sdk(folder):
    base,retained=inspect(folder)
    manifest=retained['manifest'];program=retained['program'];folder=retained['folder']
    require(manifest['runtime_kind']=='dispatch_observer' and program['method_trace'].get('sdk_reads') is True,
            'This recording does not declare the original SDK read observer.')
    snapshots={PureWindowsPath(item['original']['path']).name:item for item in manifest['source_snapshots']}
    executable=owned_file(folder,snapshots['SLPS_015.56']['file']).read_bytes()
    output=folder/'observations'
    payload=(output/'sdk-read-data.bin').read_bytes()
    summary=json.loads((output/'sdk-read-summary.json').read_bytes())
    require(summary.get('frame_payload_limit')==manifest['observer_profile'].get('sdk_read_frame_payload_bytes'),
            'SDK payload capacity differs from its recorded native build.')
    report,records=validate_records((output/'sdk-reads.bin').read_bytes(),payload,summary,
        manifest['settings']['return_trace']['sdk_targets'],executable,program)
    track=manifest['source_manifest']['disc']['tracks'][0]
    before=record_file(track['path'])
    require(content_identity(before)==content_identity(track),'Original SDK disc identity changed.')
    with Path(track['path']).open('rb') as stream:
        transfers=verify_transfers(records,payload,summary,stream)
    require(record_file(track['path'])==before,'Original SDK disc changed during sector verification.')
    returns=[dict(zip(RETURN_FIELDS,words)) for words in struct.iter_unpack('<150I',
        (output/'method-returns.bin').read_bytes())]
    handoffs=link_queued_reads(retained['entries'],returns,records,transfers)
    return dict(status='verified_bounded_original_SDK_completions',recording=base,
        SDK_boundaries=report,disc_transfers=transfers,queued_Read_completions=handoffs,
        new_C_bytes=0,whole_feature_groups_accepted=0,
        complete_state_parity_checked=False,original_hardware_timing_verified=False),retained

def link_queued_reads(entries,returns,sdk_records,transfers):
    lifecycle=analyze_read_lifecycle(entries,returns)
    bases={row['base_ordinal']:row for row in returns if row['kind']==1}
    requests=sorted((row for row in sdk_records if row['kind']==1 and row['entry_jump_pc']==0x8002866C),
                    key=lambda row:sequence(row,'entry_'))
    by_id={row['entry_id']:row for row in sdk_records}
    completions={row['request_id']:row for row in transfers['transfers']}
    require(len(requests)==len(lifecycle['pairs']),'Queued replay and original read-state request counts differ.')
    linked=[];previous_completion=-1
    for pair,request in zip(lifecycle['pairs'],requests):
        replay=bases[pair['replay_entry']]
        require(previous_completion<sequence(replay,'entry_')<sequence(replay)<sequence(request,'entry_')
                and request['a1']==replay['a1'] and request['a0']==replay['a2']>>11
                and request['a2']==0x80 and request['entry_id'] in completions,
                'Queued replay, original SDK request, arguments or asynchronous order disagree.')
        completed=completions[request['entry_id']]
        result=by_id[completed['completion_id']]
        require(sequence(request)<sequence(result) and completed['bytes']==(replay['a2']>>11)*2048,
                'Queued SDK completion precedes request return or has the wrong full-sector extent.')
        previous_completion=sequence(result)
        linked.append(dict(origin_entry=pair['origin_entry'],replay_entry=pair['replay_entry'],
            request_id=request['entry_id'],completion_id=result['entry_id'],
            requested_byte_length_word=replay['a2'],complete_sector_bytes=completed['bytes'],
            requested_tail_bytes_outside_sector_transfer=replay['a2']-completed['bytes'],
            lba=completed['lba'],destination=completed['destination'],
            complete_buffer_sha256=completed['complete_buffer_sha256']))
    return dict(queued_Read_completions=len(linked),
        requested_byte_length_words_sum=sum(row['requested_byte_length_word'] for row in linked),
        complete_sector_RAM_bytes_compared=sum(row['complete_sector_bytes'] for row in linked),
        requested_tail_bytes_outside_sector_transfers=sum(row['requested_tail_bytes_outside_sector_transfer'] for row in linked),
        pairs=linked,source_of_sector_count='Actual original SDK request A0, checked against the original Read byte-length word shifted right by 11.',
        object_lifetime_accepted=False,complete_file_feature_accepted=False)

def compare_sdk(reference,candidate,mode='same-runtime'):
    outputs=compare(reference,candidate,mode)
    before,left=inspect_sdk(reference)
    if mode=='same-runtime':
        after,right=inspect_sdk(candidate)
        for name in ('sdk-reads.bin','sdk-read-data.bin','sdk-read-summary.json'):
            require(files_equal(left['folder']/'observations'/name,right['folder']/'observations'/name),
                    'Original/rebuilt complete SDK boundary, code, RAM or summary observations differ.')
        require(before['disc_transfers']==after['disc_transfers'],'Original/rebuilt SDK disc histories differ.')
    else:
        require(left['manifest']['runtime_kind']=='dispatch_observer',
                'Use the SDK observer as reference and distributed core as candidate.')
        for name in ('sdk-reads.bin','sdk-read-data.bin','sdk-read-summary.json'):
            require(not (Path(candidate)/'observations'/name).exists(),'Distributed core supplied SDK observation.')
    return dict(status='compared_bounded_original_SDK_completions',mode=mode,
        every_recorded_game_output_equal=outputs['every_recorded_game_output_equal'],
        SDK_observations_equal=mode=='same-runtime',verification=before,
        new_C_bytes=0,whole_feature_groups_accepted=0,complete_state_parity_checked=False,
        original_hardware_timing_verified=False)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--candidate',type=Path)
    parser.add_argument('--mode',choices=('same-runtime','observer-output'),default='same-runtime')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        output=args.output.resolve()
        require(output.is_relative_to(ROOT/'.decomp-lab') and not output.exists(),
                'Choose a fresh private SDK verification report.')
        report=compare_sdk(args.reference,args.candidate,args.mode) if args.candidate else inspect_sdk(args.reference)[0]
        report['verification_source_sha256']={name:sha((ROOT/name).read_bytes()) for name in
            ('tools/inspect_sdk_reads.py','tools/sdk_reads.py','tools/inspect_dispatch_history.py','tools/dispatch_returns.py')}
        write_json(output,report)
        print(json.dumps(dict(status=report['status'],output=str(output))),flush=True)
        return 0
    except (OSError,ValueError,KeyError) as error:
        print(str(error),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
