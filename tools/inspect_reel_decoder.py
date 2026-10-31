"""Inspect actual native decoder entries; encoded prefixes are not full payload hashes."""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from tools.inventory_movies import scan_stream
from tools.inspect_progression_history import require
from tools import inspect_card_reel as card_reel

TARGETS=(0x800477b0,0x80046568,0x80045f84)
NAMES=('frame','ordinal','pc','a0','a1','a2','a3','ra','sp','timestamp','instruction','transfer_pc','delay_pc',
    'transfer_word','delay_word','active_movie','sdk_next_index','sdk_header_base','sdk_data_index','function_bytes','first_word')
HEADER=b'LSDDEC2\0'


def read_varint(stream):
    value=0
    for index in range(5):
        raw=stream.read(1);require(len(raw)==1,'Truncated numeric varint.')
        byte=raw[0]
        require(index!=4 or byte<16,'Numeric varint exceeds32 bits.')
        value|=(byte&127)<<(7*index)
        if byte<128:
            require(index==0 or value>=1<<(7*index),'Noncanonical numeric varint.')
            return value,index+1
    raise ValueError('Unterminated numeric varint.')


def entry_rows(stream):
    require(stream.read(8)==HEADER,'Wrong compact decoder header.')
    previous=[[0]*21 for _ in TARGETS]
    total=0
    while True:
        raw=stream.read(1)
        if not raw:return
        target=raw[0];require(target<len(TARGETS),'Unsupported decoder target tag.')
        values=[];length=1
        for index in range(21):
            encoded,size=read_varint(stream);length+=size
            delta=(encoded>>1)^-(encoded&1)
            value=(previous[target][index]+delta)&0xffffffff
            previous[target][index]=value;values.append(value)
        require(values[2]==TARGETS[target],'Target tag/PC disagree.')
        prefix=None
        if target==1:
            prefix=stream.read(32);require(len(prefix)==32,'Truncated encoded-prefix fingerprint.')
            prefix=prefix.hex();length+=32
        total+=length;require(total<=32*1024**2,'Decompressed decoder entries exceed their bound.')
        yield {**dict(zip(NAMES,values)),'encoded_prefix_44_sha256':prefix,'wire_bytes':length}


class MovieReader:
    """Present original raw disc sectors as the existing audited mixed STR reader."""
    def __init__(self,stream,item):
        self.stream=stream;self.remaining=item['sectors'];self.prefixes=[];self.first_words=[]
        stream.seek(item['lba']*2352)

    def read(self,size):
        require(size==2336,'Expected a bounded mixed-sector read.')
        if self.remaining==0:return b''
        raw=self.stream.read(2352);require(len(raw)==2352,'Truncated source disc sector.')
        self.remaining-=1;block=raw[16:]
        if block[2]&8 and struct.unpack_from('<I',block,8)[0]==0x80010160 and struct.unpack_from('<H',block,12)[0]==0:
            self.prefixes.append(hashlib.sha256(block[40:84]).hexdigest())
            self.first_words.append(struct.unpack_from('<I',block,40)[0])
        return block


def corpus(disc):
    disc=Path(disc)
    before=disc.stat()
    require(before.st_size==648088896,'Require the qualified complete Japanese raw disc.')
    inventory=json.loads((REPO/'docs/movie-inventory-checks.json').read_bytes())
    movies={};lookup=collections.defaultdict(set);prefix_words={};chain=hashlib.sha256();count=0
    with disc.open('rb') as stream:
        for item in inventory['movies']:
            reader=MovieReader(stream,item);observed=scan_stream(reader)
            for key in ('sha256','bytes','sectors','frame_count','sector_kinds','subheaders'):
                require(observed[key]==item[key],'Source movie differs from its complete audited inventory: '+item['path'])
            require(len(reader.prefixes)==observed['frame_count'],'Incomplete encoded-prefix corpus.')
            frames={}
            for frame,prefix,word in zip(observed['frames'],reader.prefixes,reader.first_words):
                key=frame['number'],prefix
                lookup[key].add(item['path'])
                require(key not in prefix_words or prefix_words[key]==word,'Encoded fingerprint has inconsistent command words.')
                prefix_words[key]=word
                frames[frame['number']]=dict(prefix=prefix,first_word=word)
                chain.update(item['path'].encode('ascii')+b'\0'+struct.pack('<III',frame['number'],frame['encoded_bytes'],word))
                chain.update(bytes.fromhex(prefix));chain.update(bytes.fromhex(frame['encoded_sha256']))
                count+=1
            movies[item['path']]=dict(frame_count=observed['frame_count'],lba=item['lba'],frames=frames,
                raw_mixed_sha256=observed['sha256'],distinct_prefix_fingerprints=len(set(reader.prefixes)))
    after=disc.stat()
    require((before.st_size,before.st_mtime_ns,before.st_ino)==(after.st_size,after.st_mtime_ns,after.st_ino),'Source disc changed during lookup.')
    require(len(movies)==39 and count==22382,'Wrong complete routed corpus size.')
    return dict(movies=movies,lookup=lookup,prefix_words=prefix_words,
        summary=dict(source_movies=39,source_encoded_frames=count,encoded_prefix_bytes=44,
            complete_source_mixed_movie_hashes_checked=True,source_frame_prefix_index_sha256=chain.hexdigest(),
            encoded_prefix_keys=len(lookup),ambiguous_prefix_keys=sum(len(paths)>1 for paths in lookup.values()),
            maximum_files_for_one_ID_and_prefix=max(map(len,lookup.values())),no_source_disc_or_movie_copy_created=True))


def inspect(folder,index,targets=None):
    folder=Path(folder)
    summary=json.loads((folder/'decoder-trace-summary.json').read_bytes())
    require(summary['schema_version']==2 and summary['protocol']=='delta_varint_v2'
        and summary['observer_enabled'] is True and summary['arm_frame']==21884
        and summary['event_numeric_words']==21 and summary['a0_prefix_bytes']==44
        and summary['original_function_bodies_checked_on_every_entry'] is True
        and summary['original_CPU_source_modified'] is False
        and summary['game_MainRAM_or_instructions_written'] is False
        and summary['full_encoded_or_RLE_payload_hashes_captured'] is False,'Unsupported decoder trace scope.')
    targets=json.loads((REPO/'research/headless/reel-decoder-targets.json').read_bytes()) if targets is None else targets
    specs={int(row['address'],16):row for row in targets['targets']}
    callers={(int(row['pc'],16),int(row['target'],16)):(int(row['instruction'],16),int(row['delay_word'],16),int(row['return_address'],16))
        for row in targets['original_direct_call_sites']}
    published=json.loads((REPO/'research/original-functions.json').read_bytes())
    canonical={row['function']:row for row in published['functions']}
    for row in specs.values():
        require({k:v for k,v in row.items() if k!='entry_word'}==canonical[row['function']], 'Target metadata differs from the canonical function index.')
    counts=collections.Counter();segments=[];pending_callback=None;decoded={};raw_bytes=0;total=0;previous_frame=-1;first=None;last=None
    input_pairs=submissions=0;input_chain=hashlib.sha256();submission_chain=hashlib.sha256();encoded_matches=0
    path=folder/'decoder-entries.bin.gz'
    require(path.stat().st_size<=786432,'Oversized compact decoder gzip.')
    with gzip.open(path,'rb') as stream:
        for event in entry_rows(stream):
            total+=1;raw_bytes+=event['wire_bytes'];pc=event['pc'];frame=event['frame']
            require(event['ordinal']==total and 21884<=frame<=62529 and frame>=previous_frame,'Wrong decoder event schedule/ordinal.')
            previous_frame=frame;first=frame if first is None else first;last=frame;counts[str(pc)]+=1
            spec=specs[pc]
            require(event['function_bytes']==spec['bytes']
                and event['instruction']==spec['entry_word'],'Observed decoder body/entry word differs.')
            call=callers.get((event['transfer_pc'],pc))
            require(call is not None and (event['transfer_word'],event['delay_word'],event['ra'])==call
                and event['delay_pc']==event['transfer_pc']+4,'Decoder entry lacks its original direct caller/delay slot.')
            require(0x80010000<=event['a0']<=0x801fffd4 and event['a0']%4==0
                and 0x80010000<=event['sp']<0x80200000 and event['sp']%4==0
                and 0x80010000<=event['active_movie']<0x80200000,'Invalid native decoder receiver/stack/movie context.')
            if pc==TARGETS[0]:
                require(pending_callback is None and event['first_word']==0x800817e0,'Unpaired stream callback or wrong stream vtable.')
                number=event['a2'];require(1<=number<=2000,'Unsupported actual stream frame ID.')
                if not segments or number<=segments[-1]['last_ID']:
                    require(not segments or number==1,'Native stream ID regressed without a new frame-one boundary.')
                    segments.append(dict(first_callback_frame=frame,last_callback_frame=frame,first_ID=number,last_ID=number,
                        callback_count=0,VLC_count=0,MDEC_submissions=0,ID_gaps=[],candidates=set(index['movies'])))
                segment=segments[-1]
                if segment['callback_count'] and number>segment['last_ID']+1:
                    segment['ID_gaps'].append([segment['last_ID']+1,number-1])
                segment['last_callback_frame']=frame;segment['last_ID']=number;segment['callback_count']+=1
                pending_callback=(event,len(segments)-1)
            elif pc==TARGETS[1]:
                require(pending_callback is not None,'VLC entry lacks its accepted stream callback.')
                callback,segment_index=pending_callback;pending_callback=None
                require(callback['a1']==event['a0'] and frame-callback['frame']<=1,'VLC input does not match the accepted ring buffer.')
                key=callback['a2'],event['encoded_prefix_44_sha256']
                candidates=index['lookup'].get(key,set())
                require(candidates and event['first_word']==index['prefix_words'][key],'Actual VLC input ID/prefix/command word is absent from the canonical corpus.')
                segment=segments[segment_index];segment['candidates']&=candidates;segment['VLC_count']+=1
                require(segment['candidates'],'Observed VLC sequence cannot belong to one source movie.')
                require(event['a1'] not in decoded,'A decoded work buffer was overwritten before MDEC submission.')
                decoded[event['a1']]=dict(number=callback['a2'],segment=segment_index,first_word=event['first_word'],frame=frame)
                input_chain.update(struct.pack('<IIIII',callback['a2'],frame,event['a0'],event['a1'],event['first_word']))
                input_chain.update(bytes.fromhex(event['encoded_prefix_44_sha256']));input_pairs+=1;encoded_matches+=1
            else:
                require(event['a1']==2 and event['a0'] in decoded,'MDEC submission lacks its prior decoded buffer/mode.')
                pending=decoded.pop(event['a0'])
                require(event['first_word']==pending['first_word'],'MDEC command header differs from its encoded source command.')
                segments[pending['segment']]['MDEC_submissions']+=1
                submission_chain.update(struct.pack('<IIII',pending['number'],frame,event['a0'],event['first_word']));submissions+=1
    require(total==summary['entries'] and dict(counts)==summary['counts'] and raw_bytes==summary['raw_entry_bytes']
        and first==summary['first_entry_frame'] and last==summary['last_entry_frame'],'Decoder summary differs from independently reconstructed events.')
    require(pending_callback is None and len(decoded)<=1,'Incomplete callback/decode association.')
    for segment in segments:
        segment['candidate_paths']=sorted(segment.pop('candidates'))
        segment['candidate_paths_with_matching_encoded_endpoint']=[path for path in segment['candidate_paths'] if index['movies'][path]['frame_count']==segment['last_ID']]
        segment['encoded_frame_count_for_each_candidate']={path:index['movies'][path]['frame_count'] for path in segment['candidate_paths']}
        segment['all_observed_IDs_contiguous_from_one']=segment['first_ID']==1 and not segment['ID_gaps']
    return dict(status='actual_native_decoder_entries_inspected',entries=total,counts=dict(counts),first_entry_frame=first,last_entry_frame=last,
        stream_VLC_pairs=input_pairs,canonical_encoded_prefix_matches=encoded_matches,MDEC_submissions=submissions,
        callback_segments=len(segments),segments=segments,unsubmitted_decoded_buffers=list(decoded.values()),
        input_pair_chain_sha256=input_chain.hexdigest(),MDEC_submission_chain_sha256=submission_chain.hexdigest(),
        trace_file_sha256=hashlib.sha256((folder/'decoder-entries.bin.gz').read_bytes()).hexdigest(),
        all_native_function_bodies_checked_by_host=True,actual_callers_and_delay_slots_checked=True,
        full_encoded_or_RLE_payload_hashes_captured=False,complete_frame_presentation_acceptance=False)


def validate_complete_reel(value,index):
    expected=[f'/CDI/FILM/SPDAY{day:02d}{variant}.STR' for day in range(1,11) for variant in 'AB']
    require(value['callback_segments']==20 and [row['candidate_paths'] for row in value['segments']]==[[path] for path in expected],
        'Require twenty uniquely attributed native reel segments in source order.')
    for number,row in enumerate(value['segments']):
        require(row['all_observed_IDs_contiguous_from_one'] and row['callback_count']==row['VLC_count']==row['last_ID'],
            'Reel segment has missing/noncontiguous accepted decoder inputs.')
        count=index['movies'][expected[number]]['frame_count']
        if number<19:
            require(row['last_ID']==count and row['MDEC_submissions']==count,'An earlier reel film did not reach its complete source ID range and MDEC input calls.')
        else:
            require(row['last_ID']<count and row['MDEC_submissions']==row['VLC_count']-1,'Unexpected timed final-film stop/pipeline relation.')
    require(len(value['unsubmitted_decoded_buffers'])==1
        and value['unsubmitted_decoded_buffers'][0]['segment']==19
        and value['unsubmitted_decoded_buffers'][0]['number']==value['segments'][-1]['last_ID'],
        'Timed reel must retain its one final decoded buffer without a later MDEC input call.')


def stock_comparison(stock,observed):
    require(len(stock['windows'])==len(observed['windows']),'Stock/observer window schedules differ.')
    # State hashes remain complete and unmasked. Different core bodies have a
    # separate state result; output equality does not claim their state equality.
    output_fields=('first_frame','last_frame','frames','PCM_sample_frames','payload_bytes','framed_sha256',
        'final_MainRAM_sha256','final_GPURAM_sha256','final_RGB_with_dimensions_sha256')
    differences=[];state_differences=[]
    for number,(left,right) in enumerate(zip(stock['windows'],observed['windows'])):
        if any(left[key]!=right[key] for key in output_fields):differences.append(number)
        if left['complete_state_sha256']!=right['complete_state_sha256']:state_differences.append(number)
    for key in ('native','images','inputs_sha256','dimensions','card_store'):
        if stock[key]!=observed[key]:differences.append(key)
    return dict(all_complete_output_windows_equal=not differences,output_differences=differences,
        complete_serialized_state_hashes_equal=not state_differences,
        complete_serialized_state_differing_windows=state_differences,
        full_unmasked_state_hashes_retained=True,state_equality_not_inferred_from_output_equality=True)


def compare_profiles(original,rebuilt,index,stock):
    for value in (original,rebuilt):validate_complete_reel(value['decoder'],index)
    game=card_reel.compare_data(original['recording'],rebuilt['recording'])
    qualification=[stock_comparison(stock,value['recording']) for value in (original,rebuilt)]
    differences={}
    if not game['passed']:differences['original_rebuilt_full_recording']=game['differences']
    if original['decoder']!=rebuilt['decoder']:differences['actual_native_decoder_entries']=True
    if not all(value['all_complete_output_windows_equal'] for value in qualification):differences['stock_output_qualification']=True
    final=original['decoder']['segments'][-1]
    left,right=original['recording']['windows'],rebuilt['recording']['windows']
    complete_states_equal=len(left)==len(right) and all(
        a['complete_state_sha256']==b['complete_state_sha256'] for a,b in zip(left,right))
    return dict(schema_version=1,status='equal_for_actual_native_reel_decoder_scope' if not differences else 'recorded_native_reel_differences',
        passed=not differences,dimensions=original['recording']['dimensions'],native_decoder=original['decoder'],
        source_corpus=index['summary'],observer_original_rebuilt_unmasked_complete_states_equal=complete_states_equal,
        stock_observer_qualification=qualification,differences=differences,
        source_films_uniquely_attributed=20,earlier_films_with_all_source_IDs_at_VLC_and_MDEC_input_entry=19,
        final_film_encoded_frames=index['movies'][final['candidate_paths'][0]]['frame_count'],
        final_film_last_VLC_ID=final['last_ID'],final_film_MDEC_input_calls=final['MDEC_submissions'],
        final_film_encoded_IDs_not_reached=index['movies'][final['candidate_paths'][0]]['frame_count']-final['last_ID'],
        prepared_history_not_naturally_earned=True,full_encoded_or_RLE_payload_hashes_captured=False,
        per_encoded_frame_GPU_presentation_accepted=False,original_hardware_timing_verified=False,
        whole_feature_groups_accepted=0,whole_NPC_encounters_accepted=0,new_matching_C_bytes=0,new_gameplay_features=0,model_API_calls=0)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original',type=Path)
    parser.add_argument('rebuilt',type=Path)
    parser.add_argument('--disc',type=Path,required=True)
    parser.add_argument('--stock',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(argv)
    try:
        index=corpus(args.disc)
        original=dict(recording=card_reel.load_recording(args.original),decoder=inspect(args.original,index))
        rebuilt=dict(recording=card_reel.load_recording(args.rebuilt),decoder=inspect(args.rebuilt,index))
        result=compare_profiles(original,rebuilt,index,card_reel.load_recording(args.stock))
        code=0 if result['passed'] else 1
    except (OSError,ValueError,KeyError,TypeError,EOFError) as error:
        result=dict(status='invalid_or_incomplete_native_reel_recording',passed=False,error=str(error));code=2
    rendered=json.dumps(result,indent=2)+'\n'
    if args.output:
        with args.output.open('x',encoding='utf-8') as stream:stream.write(rendered)
    print(rendered,end='')
    return code


if __name__=='__main__':raise SystemExit(main())
