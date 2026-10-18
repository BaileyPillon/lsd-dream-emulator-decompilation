"""Verify original CD errors, driver completion and controller-reset recovery.

Failed read RAM is kept separate from successful transfers. A controller reset
starts a new game/heap epoch; its invalidated allocations are never counted as
native frees. The earlier success-only SDK checker keeps its strict contract.
"""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path,PureWindowsPath
import struct
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools import inspect_sdk_reads as sdk
from tools import inspect_dispatch_history as history
from tools.inspect_file_heap import analyze_file_heap
from tools.sdk_reads import DRIVER_GLOBALS
from tools.dispatch_trace import expand_program
from tools.dispatch_returns import FIELDS as RETURN_FIELDS,Form1Disc,bcd_lba
from tools.compare_npc_history import owned_file,files_equal
from tools.runtime_inputs import record_file,content_identity
from tools.replay_cold_start_headless import require,write_json

sha=lambda raw:hashlib.sha256(raw).hexdigest()

def validate_recovery_inputs(program):
    require(program['method_trace'].get('cd_recovery') is True,'No original CD recovery profile was selected.')
    config=program.get('cd_interruption',{})
    require(config.get('kind')=='original_controller_tray','Unsupported original CD interruption.')
    opened,closed,reset=(config.get(key) for key in ('open_frame','close_frame','reset_frame'))
    require(all(type(value) is int for value in (opened,closed,reset))
            and 900<opened<closed<reset<program['frames'],'Invalid original tray/reset boundaries.')
    rows=list(csv.DictReader(io.StringIO(expand_program(program).decode()),delimiter='\t'))
    for name,expected in (('Open Tray',opened),('Close Tray',closed),('Reset',reset)):
        require([int(row['relative_frame']) for row in rows if row[name]=='true']==[expected],
                'Declared tray/reset action differs from submitted controller history: '+name)
    require(all(row['Power']=='false' and row['Disk Index']=='0' for row in rows),
            'This profile requires the original first disc and a reset, without power commands.')
    return config

def validate_driver_snapshots(records,payload):
    states={};transitions=Counter();ends=[]
    for row in records:
        if row['kind'] not in (12,13):continue
        require(row['buffer_status']==9 and row['buffer_bytes']==80
                and row['buffer_address']==DRIVER_GLOBALS[0][1],
                'Original driver state snapshot lacks its exact tagged word vector.')
        data=payload[row['buffer_offset']:row['buffer_offset']+80]
        require(len(data)==80,'Truncated original driver state snapshot.')
        before=tuple(struct.unpack_from('<10I',data));after=tuple(struct.unpack_from('<10I',data,40))
        expected=list(before)
        if row['kind']==12:
            expected[:6]=[0,0,0,0,1,0];ends.append(row['entry_id'])
        else:
            expected[2]=row['a0'];expected[5]=0;transitions[(before[2],after[2])]+=1
        require(tuple(expected)==after,'Original driver state function changes the wrong words or result.')
        states[row['entry_id']]=dict(before=before,after=after)
    require(states,'No original driver state boundaries were observed.')
    return dict(state_setter_transitions={f'{a}->{b}':n for (a,b),n in sorted(transitions.items())},
                end_read_calls=len(ends),state_boundary_calls=len(states)),states

def verify_cd_transfers(records,payload,summary,config,stream):
    reset=config['reset_frame'];disc=Form1Disc(stream)
    require(all(not(row['entry_frame']<reset<=row['frame']) for row in records),
            'A tracked SDK/driver/heap call straddles the original reset boundary.')
    timeline=sorted((sdk.sequence(row,prefix),phase,row) for row in records
                    for prefix,phase in (('entry_',0),('',1)))
    position=None;pending=None;epoch=0;entry_positions={};success=[];failed=[];request_failures=[];sync_errors=[];seek_calls=[]
    busy=0;requests=0;epoch_counts=Counter()
    for sequence,phase,row in timeline:
        current=int(row['entry_frame']>=reset)
        if current!=epoch:
            require(current==1 and pending is None,'An unfinished SDK transfer crosses the original reset.')
            epoch=1;position=None
        if phase==0:
            if row['kind']==1:
                require(pending is None,'SDK requests overlap in the error/recovery history.')
                require(row['a0']>0 and row['a2']==0x80,'Unsupported original SDK read mode or sector count.')
                entry_positions[row['entry_id']]=position
            continue
        kind=row['kind']
        if kind==3 and row['a0']==2 and row['v0']==1:
            require(pending is None and row['arg_readable']==1 and row['a1']!=0,'Setloc overlaps a transfer or lacks its actual argument.')
            position=bcd_lba(row['arg_word_0']);seek_calls.append(dict(id=row['entry_id'],epoch=epoch,lba=position))
        elif kind==4 and row['v0']==5:
            require(pending is None,'A CD sync error overlaps an unclassified active transfer.')
            position=None;sync_errors.append(row['entry_id'])
        elif kind==1:
            requests+=1
            require(row['v0'] in (0,1),'Unsupported SDK request result.')
            if row['v0']==0:request_failures.append(row['entry_id'])
            else:
                require(entry_positions[row['entry_id']] is not None,'Successful SDK request has no observed logical position.')
                require(row['sdk_word_1']==row['a0'] and row['sdk_word_2']==row['a1']
                        and row['sdk_word_4']==0x80 and row['sdk_word_5']==512,
                        'SDK backend state differs from its original request after an error/reset.')
                pending=dict(id=row['entry_id'],epoch=epoch,lba=entry_positions[row['entry_id']],
                    sectors=row['a0'],destination=row['a1'],record=row)
        require((row['transfer_id'],row['transfer_sectors'],row['transfer_mode'])==
                ((pending['id'],pending['sectors'],0x80) if pending else (0,0,0)),
                'SDK transfer identity or sector count differs in recovery history.')
        if kind==2:
            require(pending is not None,'An observed SDK poll lacks its original request.')
            if 0<row['v0']<0x80000000:
                busy+=1
                require(row['buffer_status']==row['buffer_bytes']==row['buffer_address']==0,'A busy SDK poll claims data completion.')
                continue
            require(row['v0'] in (0,0xFFFFFFFF),'Unsupported original SDK terminal result.')
            expected_status=1 if row['v0']==0 else 5
            require(row['buffer_status']==expected_status and row['buffer_address']==pending['destination']
                    and row['buffer_bytes']==pending['sectors']*2048,
                    'Successful/failed SDK RAM snapshots are missing or confused.')
            require(row['sdk_word_1']==pending['sectors'] and row['sdk_word_2']==pending['destination']
                    and row['sdk_word_4']==0x80 and row['sdk_word_5']==512,
                    'Terminal SDK backend metadata differs from its original invocation.')
            written=row['sdk_word_3']-pending['destination']
            require(0<=written<=row['buffer_bytes'] and written%2048==0,'SDK write cursor is outside its original sector window.')
            data=payload[row['buffer_offset']:row['buffer_offset']+row['buffer_bytes']]
            require(len(data)==row['buffer_bytes'],'Terminal SDK snapshot is incomplete.')
            if row['v0']==0:require(written==row['buffer_bytes'],'Successful SDK result lacks a complete write cursor.')
            require(data[:written]==disc.extent(pending['lba'],written),
                    'SDK RAM prefix differs from original sectors at the observed position.')
            item=dict(request_id=pending['id'],terminal_id=row['entry_id'],epoch=epoch,lba=pending['lba'],
                sectors=pending['sectors'],requested_sector_bytes=row['buffer_bytes'],written_prefix_bytes=written,
                request_frame=pending['record']['entry_frame'],terminal_frame=row['frame'],
                request_call=f"0x{pending['record']['entry_jump_pc']:08X}",
                destination=f"0x{pending['destination']:08X}",full_snapshot_sha256=sha(data),verified_prefix_sha256=sha(data[:written]))
            if row['v0']==0:
                item.update(completion_id=row['entry_id'],completion_frame=row['frame'],bytes=row['buffer_bytes'],
                            complete_buffer_sha256=sha(data),containing_ISO_paths=[])
                success.append(item);position=pending['lba']+pending['sectors'];epoch_counts[(epoch,'success')]+=1
            else:
                failed.append(item);position=None;epoch_counts[(epoch,'failed')]+=1
            pending=None
        elif kind in (1,3,4,11):
            require(row['buffer_status']==row['buffer_bytes']==row['buffer_address']==0,'Non-read SDK boundary claims a RAM transfer.')
    require(pending is None and len(success)==summary.get('completions') and len(failed)==summary.get('failed_transfers')
            and summary.get('unassociated_polls')==summary.get('overlapping_requests')==0,
            'Recovery transfer totals differ from native counters or remain pending.')
    require(failed and all(config['open_frame']<=row['terminal_frame']<reset for row in failed),
            'This recording does not show the declared pre-reset CD failure episode.')
    require(epoch_counts[(1,'success')]>0 and epoch_counts[(1,'failed')]==0,
            'Successful post-reset SDK recovery is unproven.')
    return dict(request_attempts=requests,failed_request_attempts=len(request_failures),busy_polls=busy,
        successful_transfers=len(success),failed_transfers=len(failed),sync_errors=len(sync_errors),
        successful_complete_RAM_bytes=sum(row['bytes'] for row in success),
        failed_snapshot_bytes=sum(row['requested_sector_bytes'] for row in failed),
        failed_verified_prefix_bytes=sum(row['written_prefix_bytes'] for row in failed),
        post_reset_successful_transfers=epoch_counts[(1,'success')],post_reset_failed_transfers=0,
        successful=success,failed=failed,Setlocs=seek_calls,sync_error_ids=sync_errors,
        failed_buffers_are_successful_transfers=False,failed_buffer_tails_accepted=False),success,failed

def qualify_error_endings(records,states,failed,reset_frame):
    by_id={row['entry_id']:row for row in records};endings=[]
    for failure in failed:
        terminal=by_id[failure['terminal_id']];start=sdk.sequence(terminal)
        require(terminal['frame']<reset_frame,'A failed driver request is outside the pre-reset epoch.')
        candidates=[row for row in records if row['kind']==12 and sdk.sequence(row,'entry_')>start
                    and row['entry_frame']<reset_frame
                    and states[row['entry_id']]['before'][0:3]==(1,3,2)]
        require(candidates,'A failed read lacks its observed driver completion transition.')
        end=min(candidates,key=lambda row:sdk.sequence(row,'entry_'));stop=sdk.sequence(end)
        require(end['entry_jump_pc']==0x800286A4,'Original failed-read driver end uses an unexpected call site.')
        between=[row for row in records if start<sdk.sequence(row,'entry_')<sdk.sequence(row)<stop]
        path=sorted((row for row in between if row['kind'] in (1,3,4,11,12,13)),
                    key=lambda row:sdk.sequence(row,'entry_'))
        at=0
        def take(kind,call,argument=None,result=None,state=None):
            nonlocal at
            require(at<len(path),'Original failed-read state path ends before its driver completion.')
            row=path[at];at+=1
            require(row['kind']==kind and row['entry_jump_pc']==call
                    and (argument is None or row['a0']==argument)
                    and (result is None or row['v0']==result),
                    'Original failed-read flush/reseek/state path disagrees or unexpectedly reissues an SDK read.')
            if state is not None:
                require(states[row['entry_id']]['before'][2]==state,
                        'Original failed-read state setter starts in the wrong observed state.')
            return row
        flush=take(11,0x800286B4)
        take(13,0x800286C0,1,state=8)
        seeks=0;sync_errors=0
        while True:
            take(3,0x800285E4,2,1);seeks+=1
            take(13,0x800286C0,2,state=1)
            synced=take(4,0x80028600,1)
            require(synced['v0'] in (2,5),'Unqualified CD sync result in this original failed-read path.')
            if synced['v0']==2:break
            sync_errors+=1;take(13,0x800286C0,1,state=2)
        require(at==len(path),'Unexpected original SDK/driver boundary follows the final reseek sync.')
        endings.append(dict(request_id=failure['request_id'],failure_id=failure['terminal_id'],
            flush_id=flush['entry_id'],driver_end_id=end['entry_id'],
            failure_frame=terminal['frame'],driver_end_frame=end['frame'],SDK_reads_reissued_before_driver_end=0,
            accepted_reseek_calls=seeks,reseek_sync_errors=sync_errors,
            driver_busy_after=states[end['entry_id']]['after'][0],failed_data_counted_as_completed=False))
    return dict(qualified_failed_driver_endings=len(endings),endings=endings,
        automatic_SDK_retry_within_each_failed_driver_request_observed=False)

def inspect_recovery(folder):
    base,retained=history.inspect(folder);manifest=retained['manifest'];program=retained['program']
    config=validate_recovery_inputs(program);reset=config['reset_frame'];folder=retained['folder'];output=folder/'observations'
    require(manifest['runtime_kind']=='dispatch_observer','Recovery boundaries require the separate observer.')
    snapshots={PureWindowsPath(row['original']['path']).name:row for row in manifest['source_snapshots']}
    executable=owned_file(folder,snapshots['SLPS_015.56']['file']).read_bytes()
    payload=(output/'sdk-read-data.bin').read_bytes();summary=json.loads((output/'sdk-read-summary.json').read_bytes())
    require(summary['frame_payload_limit']==manifest['observer_profile']['sdk_read_frame_payload_bytes'],
            'Recovery payload capacity differs from its native build.')
    structural,records=sdk.validate_records((output/'sdk-reads.bin').read_bytes(),payload,summary,
        manifest['settings']['return_trace']['sdk_targets'],executable,program)
    driver,states=validate_driver_snapshots(records,payload)
    track=manifest['source_manifest']['disc']['tracks'][0];before=record_file(track['path'])
    require(content_identity(before)==content_identity(track),'Original recovery disc identity changed.')
    with Path(track['path']).open('rb') as stream:transfers,successful,failed=verify_cd_transfers(records,payload,summary,config,stream)
    require(record_file(track['path'])==before,'Original recovery disc changed during verification.')
    endings=qualify_error_endings(records,states,failed,reset)
    returns=[dict(zip(RETURN_FIELDS,words)) for words in struct.iter_unpack('<150I',(output/'method-returns.bin').read_bytes())]
    require(all(not(row['entry_frame']<reset<=row['frame']) for row in returns),'An original method straddles controller reset.')
    heap_epochs=[]
    for epoch in (0,1):
        selected=[row for row in records if int(row['entry_frame']>=reset)==epoch]
        ordinals={old:new for new,(old,entry) in enumerate(((i,entry) for i,entry in enumerate(retained['entries'],1)
                    if int(entry['relative_frame']>=reset)==epoch),1)}
        entries=[entry for entry in retained['entries'] if int(entry['relative_frame']>=reset)==epoch]
        returned=[]
        for row in returns:
            if int(row['entry_frame']>=reset)!=epoch:continue
            copied=dict(row)
            if row['kind']==1:copied['base_ordinal']=ordinals[row['base_ordinal']]
            returned.append(copied)
        verified=dict(transfers=[row for row in successful if row['epoch']==epoch])
        model=analyze_file_heap(selected,payload,entries,returned,verified,program,check_read_lifetimes=epoch==1)
        heap_epochs.append(dict(epoch=epoch,terminated_by_controller_reset=epoch==0,
            live_allocations_at_epoch_end_are_native_frees=False,verification=model))
    require(heap_epochs[1]['verification']['queued_Read_lifetime_windows_qualified']>0,
            'Post-reset original queued-read lifetimes remain unverified.')
    return dict(status='verified_bounded_original_CD_failure_and_reset_recovery',recording=base,
        boundary_records=structural,driver_state_effects=driver,transfers=transfers,original_error_endings=endings,
        heap_epochs=heap_epochs,reset_frame=reset,reset_is_original_controller_input=True,
        automatic_read_recovery_accepted=False,controller_reset_recovery_observed=True,
        original_game_modified=False,whole_file_feature_accepted=False,whole_feature_groups_accepted=0,new_C_bytes=0),retained

def compare_recovery(reference,candidate,mode='same-runtime'):
    outputs=history.compare(reference,candidate,mode);before,left=inspect_recovery(reference)
    if mode=='same-runtime':
        after,right=inspect_recovery(candidate)
        for name in ('sdk-reads.bin','sdk-read-data.bin','sdk-read-summary.json'):
            require(files_equal(left['folder']/'observations'/name,right['folder']/'observations'/name),
                    'Original/rebuilt recovery records, failed RAM or summaries differ.')
        require(before['transfers']==after['transfers'] and before['heap_epochs']==after['heap_epochs']
                and before['original_error_endings']==after['original_error_endings'],
                'Original/rebuilt error behavior, reset epochs or recovered lifetimes differ.')
    return dict(status='compared_bounded_original_CD_reset_recovery',mode=mode,
        every_recorded_game_output_equal=outputs['every_recorded_game_output_equal'],
        recovery_records_and_models_equal=mode=='same-runtime',verification=before,
        whole_feature_groups_accepted=0,new_C_bytes=0)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',required=True,type=Path);parser.add_argument('--candidate',type=Path)
    parser.add_argument('--mode',choices=('same-runtime','observer-output'),default='same-runtime')
    parser.add_argument('--output',required=True,type=Path);args=parser.parse_args(argv)
    try:
        output=args.output.resolve();require(output.is_relative_to(ROOT/'.decomp-lab') and not output.exists(),
            'Choose a fresh private recovery report.')
        report=compare_recovery(args.reference,args.candidate,args.mode) if args.candidate else inspect_recovery(args.reference)[0]
        report['verification_source_SHA256']=sha(Path(__file__).read_bytes());write_json(output,report)
        print(json.dumps(dict(status=report['status'],output=str(output))),flush=True);return 0
    except (OSError,ValueError,KeyError) as error:print(str(error),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
