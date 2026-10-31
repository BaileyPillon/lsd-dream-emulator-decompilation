"""Inspect bounded cold movie recordings with framed per-window buffer hashes."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import zlib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import compare_movie_playback as playback
from tools.inspect_progression_history import document, digest, integer, png_rgb, require, rows

CHANNELS={'MainRAM','GPURAM','RGB','PCM','native','controller'}
FIELDS=playback.FIELDS[:-1]
WINDOW_FIELDS={'first_frame','last_frame','frames','PCM_sample_frames','payload_bytes','framed_sha256',
               'complete_state_sha256','final_MainRAM_sha256','final_GPURAM_sha256','final_RGB_with_dimensions_sha256'}


def framed_hash(payloads):
    """The native host prefixes every payload with three signed little-endian words."""
    algorithm=hashlib.sha256()
    for frame,core_frame,payload in payloads:
        algorithm.update(struct.pack('<iii',frame,core_frame,len(payload)))
        algorithm.update(payload)
    return algorithm.hexdigest()


def bounded_file(folder,name,limit):
    path=folder/name
    require(path.resolve(strict=True).parent==folder,'Recording file escapes its directory.')
    require(path.is_file() and path.stat().st_size<=limit,'Oversized retained recording file.')
    return path.read_bytes()


def native_rows(raw,count):
    result=rows(raw,FIELDS)
    require(len(result)==count,'Native journal must contain every advanced frame.')
    ready_seen=False
    for frame,row in enumerate(result):
        require(row['relative_frame']==str(frame) and row['core_frame']==str(frame+1),'Native frame schedule differs.')
        require(row['native_tables_ready'] in ('0','1'),'Invalid native table readiness.')
        ready=row['native_tables_ready']=='1'
        require(not ready_seen or ready,'Native program was unloaded.')
        ready_seen|=ready
        try:
            active=int(row['active_movie'])
        except ValueError as error:
            raise ValueError('Invalid movie address.') from error
        require(0<=active<=0xffffffff,'Invalid native active pointer.')
        if ready:
            require(all(row[key].isdigit() and 0<=int(row[key])<=0xffffffff
                        for key in ('rng','watchdog_counter')),'Invalid native globals.')
        else:
            require(active==0 and row['rng']=='-' and row['watchdog_counter']=='-','Premature native observations.')
        if active:
            require(ready and playback.aligned_pointer(active,0x6c),'Invalid active movie pointer.')
            require(all(row[key].isdigit() and 0<=int(row[key])<=0xffffffff for key in FIELDS[6:]),'Invalid native words.')
            require(row['movie_00']==str(0x8006f614) and row['stream_00']==str(0x800817e0)
                    and playback.aligned_pointer(int(row['movie_60']),0x5c),'Invalid native vtable/pointer chain.')
            cutoff=int(row['movie_5c'])
            state=int(row['stream_2c'])
            require(cutoff in playback.STARTUP_PATHS and state in (0,1,2,4),'Unsupported startup movie/state.')
            require((int(row['movie_24']),int(row['movie_28']))==(320,240),'Unexpected source viewport.')
            identity=playback.native_file_identity(row)
            require(identity['filename']==playback.STARTUP_PATHS[cutoff].rsplit('/',1)[1]+';1','Native filename/cutoff disagree.')
            if state in (0,2,4):
                require(int(row['stream_40'])==cutoff and 0<=int(row['stream_58'])<cutoff,'Invalid streaming counter/threshold.')
            require(row['movie_44'] in ('0','1') and row['movie_48'] in ('0','1'),'Invalid decoder completion fields.')
            if state==0:
                # Original forced-stop sets both MDEC stop flags, closes the
                # stream, and clears g_ActiveMovie on its following update.
                require(row['movie_44']==row['movie_48']=='1' and row['movie_54']=='0',
                        'Closed stream lacks original forced-stop fields.')
                require(0<frame<len(result)-1 and result[frame-1]['active_movie']==row['active_movie']
                        and result[frame-1]['stream_2c']=='2' and result[frame-1]['stream_58']==row['stream_58']
                        and result[frame+1]['active_movie']=='0','Closed stream is outside the observed skip lifecycle.')
        else:
            require(all(row[key]=='-' for key in FIELDS[6:]),'Inactive native fields must be absent.')
    return result


def controller_rows(raw,report,native):
    changes=rows(raw,('frame','mask'))
    require(changes and changes[0]=={'frame':'0','mask':'0'},'Missing neutral initial input.')
    end=report['last_frame']
    previous=-1
    previous_mask=-1
    for row in changes:
        require(row['frame'].isdigit() and row['mask'] in ('0','1'),'Invalid controller change.')
        frame,mask=int(row['frame']),int(row['mask'])
        require(previous<frame<=end and mask!=previous_mask,'Invalid or redundant input ordering.')
        previous,previous_mask=frame,mask
    skip=report['skip_submitted_frame']
    closed=[index for index,row in enumerate(native) if row['active_movie']!='0' and row['stream_2c']=='0']
    if report['mode']=='neutral':
        require(changes==[{'frame':'0','mask':'0'}] and skip==-1 and report['skip_pulse_frames']==0,'Neutral route has input.')
        require(not closed,'Neutral profile cannot contain the skip-only closed transition.')
    else:
        integer(skip,1,end-12,'skip input frame')
        require(report['skip_pulse_frames']==12 and changes==[
            {'frame':'0','mask':'0'},{'frame':str(skip),'mask':'1'},{'frame':str(skip+12),'mask':'0'}],
            'Skip request must be exactly one twelve-frame Circle pulse.')
        before=native[skip-1]
        require(before['active_movie']!='0' and before['stream_2c']=='2','Skip input was not based on a streaming movie.')
        cutoff=int(before['movie_5c'])
        minimum=20 if report['mode']=='skip-logo' else 120
        require((cutoff==90 if report['mode']=='skip-logo' else cutoff>=900)
                and int(before['stream_58'])>=minimum,'Skip input targeted the wrong movie/counter.')
        require(len(closed)==1 and skip<=closed[0]<skip+12 and native[closed[0]]['movie_5c']==before['movie_5c'],
                'Closed stream does not follow the one supported controller skip.')
    result=[]
    cursor=0
    mask=0
    for frame in range(end+1):
        if cursor<len(changes) and int(changes[cursor]['frame'])==frame:
            mask=int(changes[cursor]['mask'])
            cursor+=1
        result.append(mask)
    return changes,result


def validate_windows(windows,native_lines,masks,frames,total_samples):
    require(windows and len(native_lines)==frames and len(masks)==frames,'Missing window inputs.')
    next_frame=0
    samples=0
    for window in windows:
        require(isinstance(window,dict) and set(window)==WINDOW_FIELDS,'Wrong window fields.')
        first=integer(window['first_frame'],0,frames-1,'first window frame')
        last=integer(window['last_frame'],first,frames-1,'last window frame')
        require(first==next_frame and last==min(first+599,frames-1),'Missing, overlapping or nonstandard frame window.')
        count=last-first+1
        require(type(window['frames']) is int and window['frames']==count,'Wrong per-window frame count.')
        sample_count=integer(window['PCM_sample_frames'],0,count*5000,'window audio samples')
        sizes=window['payload_bytes']
        hashes=window['framed_sha256']
        require(isinstance(sizes,dict) and set(sizes)==CHANNELS and isinstance(hashes,dict)
                and set(hashes)==CHANNELS,'Missing native hash channel.')
        for key in CHANNELS:
            digest(hashes[key],key)
            integer(sizes[key],0,2*1024**3,'channel bytes')
        require(sizes['MainRAM']==count*0x200000 and sizes['GPURAM']==count*0x100000
                and sizes['controller']==count*4 and sizes['PCM']==sample_count*4,'Incomplete native buffer/audio coverage.')
        require(count*11<=sizes['RGB']<=count*(8+1024*1024*3),'Invalid video payload coverage.')
        selected=native_lines[first:last+1]
        require(sizes['native']==sum(map(len,selected)),'Native journal byte count differs.')
        native_hash=framed_hash((frame,frame+1,native_lines[frame]) for frame in range(first,last+1))
        input_hash=framed_hash((frame,frame+1,struct.pack('<i',masks[frame])) for frame in range(first,last+1))
        require(hashes['native']==native_hash and hashes['controller']==input_hash,'Independent native/controller framed hash differs.')
        for key in ('complete_state_sha256','final_MainRAM_sha256','final_GPURAM_sha256','final_RGB_with_dimensions_sha256'):
            digest(window[key],key)
        samples+=sample_count
        next_frame=last+1
    require(next_frame==frames and samples==total_samples,'Incomplete frame/audio window coverage.')
    return dict(frames=frames,windows=len(windows),complete_state_observations=len(windows),PCM_stereo_sample_frames=samples,
        MainRAM_bytes=frames*0x200000,GPURAM_bytes=frames*0x100000,
        RGB_payload_bytes=sum(row['payload_bytes']['RGB'] for row in windows),native_and_controller_hashes_independently_recomputed=True)


def controller_schema(report):
    buttons=report.get('controller_buttons')
    axes=report.get('controller_neutral_axes')
    # .NET's culture-sensitive ordering of the PlayStation glyph names differs
    # from Python's Unicode order. Validate every named control without changing
    # either retained report or any native/state hash.
    require(isinstance(buttons,list) and all(isinstance(name,str) for name in buttons)
            and len(buttons)==len(playback.DIGITAL_NAMES) and set(buttons)==playback.DIGITAL_NAMES
            and isinstance(axes,dict) and set(axes)==set(playback.NUMERIC_NEUTRAL)
            and all(type(value) is int and value==playback.NUMERIC_NEUTRAL[key] for key,value in axes.items()),
            'Unsupported controller schema/neutral axes.')


def load_recording(folder):
    folder=Path(folder).resolve(strict=True)
    report=document(bounded_file(folder,'report.json',65536))
    require(report['schema_version']==1 and report['status']=='opening_cleared_and_post_window_completed','Native route did not finish.')
    require(report['mode'] in ('neutral','skip-logo','skip-opening') and report['cold_start'] is True,'Unsupported movie profile.')
    require(all(report[name] is False for name in ('restored_state','game_RAM_injected','player_UI_or_saves_accessed','hardware_timing_verified'))
            and type(report['whole_feature_groups_accepted']) is int and report['whole_feature_groups_accepted']==0,'Unsupported parity/mutation scope.')
    frames=integer(report['frames_advanced'],1,8001,'advanced frames')
    integer(report['total_PCM_sample_frames'],0,frames*5000,'total audio samples')
    require(type(report['last_frame']) is int and report['last_frame']==frames-1,'Final frame disagrees.')
    require(type(report['replayed_inputs']) is bool,'Invalid replay-input flag.')
    controller_schema(report)
    require(not (folder/'STOP').exists(),'Stopped recording is incomplete.')
    compressed=bounded_file(folder,'native.tsv.gz',128*1024)
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        raw=stream.read(8*1024**2+1)
    require(len(raw)<=8*1024**2 and raw.endswith(b'\n') and b'\r' not in raw,'Native journal exceeds its bound or has invalid newlines.')
    lines=raw.splitlines(keepends=True)
    native=native_rows(raw,frames)
    require(type(report['raw_native_bytes']) is int and report['raw_native_bytes']==sum(map(len,lines[1:])),
            'Native producer byte count differs.')
    changes,masks=controller_rows(bounded_file(folder,'inputs.tsv',65536),report,native)
    windows=[document(line) for line in bounded_file(folder,'windows.jsonl',131072).splitlines()]
    dimensions=validate_windows(windows,lines[1:],masks,frames,report['total_PCM_sample_frames'])
    lifetimes=playback.summarize_lifetimes(native)
    openings=[row for row in lifetimes if row['requested_cutoff']>=900 and row['first_inactive_frame_after'] is not None]
    require(openings,'No observed opening removal.')
    cleared=openings[0]['first_inactive_frame_after']
    require(type(report['first_opening_cleared_frame']) is int and report['first_opening_cleared_frame']==cleared
            and type(report['post_opening_frames']) is int and report['post_opening_frames']==report['last_frame']-cleared==180,
            'Post-opening window disagrees with the native lifecycle.')
    return dict(report=report,windows=windows,native=native,inputs=changes,lifetimes=lifetimes,dimensions=dimensions,
        final_image=png_rgb(bounded_file(folder,'final.png',8*1024**2)),
        journal_sha256=hashlib.sha256(raw).hexdigest(),report_sha256=hashlib.sha256((folder/'report.json').read_bytes()).hexdigest())


def compare_data(original,rebuilt):
    require(original['report']['replayed_inputs'] is False and rebuilt['report']['replayed_inputs'] is True,'Require original policy and exact-input replay roles.')
    require(original['report']['mode']==rebuilt['report']['mode'],'Different native recording modes.')
    differences={}
    for key in ('windows','native','inputs','lifetimes','dimensions'):
        if original[key]!=rebuilt[key]:
            differences[key]=True
    image_keys=('width','height','RGB_sha256')
    if any(original['final_image'][key]!=rebuilt['final_image'][key] for key in image_keys):
        differences['decoded_final_PNG']=True
    return dict(schema_version=1,status='equal_for_recorded_movie_scope' if not differences else 'recorded_movie_differences',
        passed=not differences,mode=original['report']['mode'],dimensions=original['dimensions'],
        lifetimes=original['lifetimes'],skip_submitted_frame=original['report']['skip_submitted_frame'],
        original_native_journal_sha256=original['journal_sha256'],rebuilt_native_journal_sha256=rebuilt['journal_sha256'],
        original_report_sha256=original['report_sha256'],rebuilt_report_sha256=rebuilt['report_sha256'],
        differences=differences,whole_feature_groups_accepted=0,hardware_timing_verified=False,
        complete_all_movie_or_ending_playback_verified=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original',type=Path)
    parser.add_argument('rebuilt',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.output:
            target=args.output.resolve()
            require(not target.exists(),'Preserve an existing analysis report.')
            require(not target.is_relative_to(ROOT) or target.is_relative_to(ROOT/'.decomp-lab'),'Use a private analysis output path.')
        result=compare_data(load_recording(args.original),load_recording(args.rebuilt))
        if args.output:
            with args.output.open('x',encoding='utf-8',newline='\n') as stream:
                json.dump(result,stream,indent=2)
                stream.write('\n')
        print(json.dumps(result,indent=2))
        return 0 if result['passed'] else 1
    except (OSError,ValueError,KeyError,TypeError,struct.error,EOFError,zlib.error) as error:
        print(json.dumps(dict(status='invalid_movie_recording',error=str(error))),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
