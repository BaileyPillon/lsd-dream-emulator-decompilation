"""Pair recorded queued CD Read entries with their original FIFO dispatches.

This verifies entry/replay arguments and the recorded driver busy transition.
It does not accept SDK completion, transferred bytes or complete file behavior.
"""
import argparse
from collections import Counter,deque
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import inspect_dispatch_history as history
from tools.compare_npc_history import owned_file
from tools.dispatch_returns import FIELDS,sequence
from tools.replay_cold_start_headless import require

READ_PC=0x800276D0
DISPATCH_PC=0x80027B0C

def analyze_read_lifecycle(entries,returns):
    bases=[row for row in returns if row['kind']==1]
    by_ordinal={row['base_ordinal']:row for row in bases}
    require(len(bases)==len(by_ordinal)==len(entries) and set(by_ordinal)==set(range(1,len(entries)+1)),
            'Missing or duplicate original base-method return.')
    pending=deque();pairs=[];synchronous=0;origin_counts=Counter()
    for ordinal,entry in enumerate(entries,1):
        if entry['pc']!=READ_PC:
            continue
        returned=by_ordinal[ordinal]
        require(returned['entry_pc']==entry['pc'] and returned['v0']==0
                and all(returned[name]==entry[name] for name in ('a0','a1','a2')),
                'A Read return lacks its original arguments or zero status word.')
        active,param=entry['memory_word_0'],entry['memory_word_1']
        if active==param==0:
            synchronous+=1
            continue
        require(active==param==1,'This FIFO profile requires the observed framed mode (1,1).')
        flag=entry['a0_word_28']&0xFFFF
        key=tuple(entry[name] for name in ('a0','a1','a2'))
        require(flag in (0,1),'Unsupported queued-dispatch receiver flag.')
        if flag==0:
            require(entry['transfer_pc']!=DISPATCH_PC,'The replay caller cannot identify a new queued origin.')
            pending.append((ordinal,entry,returned,key));origin_counts[entry['transfer_pc']]+=1
            continue
        require(entry['transfer_pc']==DISPATCH_PC and pending,
                'A queued replay lacks the original dispatcher or a pending origin.')
        first,origin,origin_return,expected=pending.popleft()
        require(key==expected,'The original FIFO replay changes receiver, destination or byte-length word.')
        require(first<ordinal and origin['relative_frame']<=entry['relative_frame']
                and sequence(origin_return)<sequence(returned,'entry_'),
                'A queued replay precedes completion of its originating call.')
        require(entry['a0_word_0C']!=0 and entry['memory_word_2']==0
                and returned['memory_word_2']==1,
                'The replay does not show the observed opened-file driver transition from idle to busy.')
        pairs.append(dict(origin_entry=first,replay_entry=ordinal,
            origin_call=f"0x{origin['transfer_pc']:08X}",replay_call=f'0x{DISPATCH_PC:08X}',
            receiver=f'0x{key[0]:08X}',destination=f'0x{key[1]:08X}',requested_byte_length_word=key[2],
            origin_frame=origin['relative_frame'],replay_frame=entry['relative_frame'],
            driver_busy_at_replay_entry=0,driver_busy_at_replay_return=1,Read_return_status_word=0))
    require(not pending,'Queued Read origins remain without a recorded replay.')
    require(pairs,'No original framed Read handoff was observed.')
    return dict(status='verified_bounded_queued_CD_Read_entry_replays',
        synchronous_Read_entries=synchronous,framed_Read_entries=2*len(pairs),logical_Read_argument_pairs=len(pairs),
        origin_call_counts={f'0x{pc:08X}':count for pc,count in sorted(origin_counts.items())},
        requested_byte_length_words_sum=sum(row['requested_byte_length_word'] for row in pairs),pairs=pairs,
        FIFO_entry_order_matches=True,all_replays_return_with_driver_busy=True,
        requested_length_sum_is_not_a_transfer_count=True,SDK_completion_accepted=False,
        destination_data_accepted=False,new_emulator_runs=0,whole_feature_groups_accepted=0,new_C_bytes=0,
        scope='Recorded queued origins and later FIFO replays, unchanged argument words, and the game driver busy flag at dispatch return. No actual SDK request, completion, transferred-byte, destination-content, object-lifetime or whole-feature acceptance.')

def inspect_folder(folder):
    folder=Path(folder).resolve();output=folder/'observations'
    data=owned_file(output,'method-returns.bin').read_bytes()
    entries_file=owned_file(output,'method-instructions.tsv');entry_bytes=entries_file.read_bytes()
    checked,detail=history.inspect(folder)
    require('original_returns' in checked,'Require an already qualified original return capture.')
    require(owned_file(output,'method-returns.bin').read_bytes()==data and entries_file.read_bytes()==entry_bytes,
            'Return or entry data changed during qualification.')
    require(len(data)%600==0,'Incomplete original return transport.')
    returns=[dict(zip(FIELDS,words)) for words in struct.iter_unpack('<150I',data)]
    return analyze_read_lifecycle(detail['entries'],returns),dict(
        return_stream_sha256=hashlib.sha256(data).hexdigest(),
        entry_stream_sha256=hashlib.sha256(entry_bytes).hexdigest())

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',required=True,type=Path)
    parser.add_argument('--candidate',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        output=args.output.resolve()
        require(output.is_relative_to(ROOT/'.decomp-lab') and output!=ROOT/'.decomp-lab' and not output.exists(),
                'Choose a fresh private report inside .decomp-lab.')
        compared=history.compare(args.reference,args.candidate,'same-runtime') if args.candidate else None
        left,left_pins=inspect_folder(args.reference)
        if args.candidate:
            right,right_pins=inspect_folder(args.candidate)
            require(left==right and left_pins==right_pins,'Original/rebuilt queued-read histories differ.')
        else:right_pins=None
        report=dict(status='inspected_original_queued_read_lifecycle',lifecycle=left,reference_streams=left_pins,
            candidate_streams=right_pins,original_rebuilt_histories_equal=True if args.candidate else None,
            prior_method_and_game_output_comparison=compared,
            producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
        print(json.dumps({key:left[key] for key in ('status','logical_Read_argument_pairs','framed_Read_entries',
            'synchronous_Read_entries','requested_byte_length_words_sum','SDK_completion_accepted','new_C_bytes')}),flush=True)
        return 0
    except (OSError,ValueError,KeyError) as error:
        print('[!] '+str(error),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
