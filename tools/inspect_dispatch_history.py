"""Inspect and compare retained original-method histories without controlling UI.

Complete callee bytes are checked for every entry. Preceding transfer evidence,
raw receiver/table windows and game outputs do not accept entire methods or
prove a virtual slot's use merely because it contains the destination word.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path, PureWindowsPath
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.dispatch_trace import validate_program, expand_program, verified_selection
from tools.compare_npc_history import owned_file, verify_file, read_rows, inspect_png, files_equal, FRAME_FIELDS, RAM_FIELDS
from tools.replay_cold_start_headless import require, write_json
from tools.runtime_inputs import content_identity, record_file
from tools.build_dispatch_observer import EXPORTS
from tools.dispatch_flow import FLOW_EXPORTS, flow_sites, flow_windows, validate_flow
from tools.dispatch_returns import RETURN_EXPORTS, verified_return_selection, validate_returns, verify_disc_buffers
from tools.sdk_reads import verified_sdk_selection
from tools.build_dispatch_observer import SDK_EXPORTS
from tools.build_npc_observer import UPSTREAM, MEDNAFEN, SOURCE_SHA256
from research.compiler.compare_function import CANONICAL_SHA256
from tools.psx_image import executable_offset
from tools.collision_calls import selection as collision_selection,EXPORTS as COLLISION_EXPORTS,ORDINAL_EXPORTS as COLLISION_ORDINAL_EXPORTS,EVENT_BYTES as COLLISION_EVENT_BYTES,FRAME_BYTES as COLLISION_FRAME_BYTES

HEX_FIELDS=('pc','a0','a1','a2','a3','ra','sp','instruction','transfer_pc','delay_pc','transfer_word','delay_word')
ENTRY_FIELDS=('relative_frame','pc','a0','a1','a2','a3','ra','sp','timestamp','instruction',
    'transfer_pc','delay_pc','transfer_word','delay_word',
    *('a0_word_'+f'{i*4:02X}' for i in range(11)),
    *('a0_table_word_'+f'{i*4:03X}' for i in range(35)),
    *('memory_word_'+str(i) for i in range(4)), 'function_bytes','function_sha256','code_offset')
WORD_FIELDS=tuple(field for field in ENTRY_FIELDS if field not in
                  ('relative_frame','timestamp','function_bytes','function_sha256','code_offset'))
CORE_FILES={'dll/shock.wbx','dll/shock.wbx.zst'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(value):
    return isinstance(value,str) and len(value)==64 and all(c in '0123456789abcdef' for c in value)


def transfer(entry, executable):
    pc, delay=entry['transfer_pc'],entry['delay_pc']
    if pc%4 or delay!=pc+4:
        return dict(kind='unresolved_preceding_sequence')
    try:
        offset=executable_offset(executable,pc,8)
    except ValueError:
        return dict(kind='caller_outside_canonical_executable')
    word,delay_word=struct.unpack_from('<II',executable,offset)
    require((word,delay_word)==(entry['transfer_word'],entry['delay_word']),
            'Recorded caller transfer/delay bytes differ from the canonical executable.')
    if word>>26==3:
        destination=((pc+4)&0xF0000000)|((word&0x03FFFFFF)<<2)
        require(destination==entry['pc'] and entry['ra']==pc+8,'Direct call destination or return address disagrees.')
        return dict(kind='observed_direct_JAL',source=f'0x{pc:08X}',target=f"0x{entry['pc']:08X}")
    if (word&0xFC1F07FF)==9:
        link=(word>>11)&31
        if link==31:require(entry['ra']==pc+8,'Indirect call return address disagrees.')
        return dict(kind='observed_indirect_JALR',source=f'0x{pc:08X}',target=f"0x{entry['pc']:08X}",
                    target_register=(word>>21)&31,link_register=link)
    if (word&0xFC1FFFFF)==8:
        return dict(kind='observed_indirect_JR',source=f'0x{pc:08X}',target=f"0x{entry['pc']:08X}",
                    target_register=(word>>21)&31)
    return dict(kind='unresolved_preceding_instruction')


def validate_entries(rows,program,selected,code,executable):
    counts,transfers,edges,identities,spans=Counter(),Counter(),Counter(),set(),{}
    body_offsets={}
    previous=(-1,-1)
    parsed=[]
    for row in rows:
        require(set(row)==set(ENTRY_FIELDS),'Incomplete method entry columns.')
        require(all(isinstance(row[name],str) and len(row[name])==8
                    and all(c in '0123456789ABCDEF' for c in row[name]) for name in WORD_FIELDS),
                'Invalid complete native observation word.')
        require(digest(row['function_sha256']),'Invalid complete method code hash.')
        entry={key:int(value,16) if key in WORD_FIELDS else int(value) if key!='function_sha256' else value
               for key,value in row.items()}
        frame,timestamp=entry['relative_frame'],entry['timestamp']
        require(program['method_trace']['arm_frame']<=frame<=program['frames'] and timestamp>=0
                and (frame,timestamp)>=previous,'Method entries have an invalid native order/window.')
        previous=(frame,timestamp)
        require(entry['pc'] in selected,'Observed method PC was not selected.')
        target=selected[entry['pc']]
        length,offset=entry['function_bytes'],entry['code_offset']
        require(length==target['function_bytes'] and entry['function_sha256']==target['function_sha256']
                and offset>=0 and offset%4==0 and offset+length<=len(code),
                'Complete observed method span/hash differs from its selected original.')
        body=code[offset:offset+length]
        require(sha(body)==target['function_sha256']
                and struct.unpack_from('<I',body)[0]==entry['instruction'],
                'Complete observed method bytes or entry instruction differ from original.')
        require(offset not in spans or spans[offset]==(length,sha(body)),'Conflicting retained code offsets.')
        require(sha(body) not in body_offsets or body_offsets[sha(body)]==offset,
                'A deduplicated complete method body has multiple retained offsets.')
        body_offsets[sha(body)]=offset
        spans[offset]=(length,sha(body))
        identity=tuple(row[key] for key in ENTRY_FIELDS)
        require(identity not in identities,'Duplicated original method entry.')
        identities.add(identity)
        require(entry['sp']%8==0 and 0x80010000<=entry['sp']<0x80200000,'Invalid original method stack pointer.')
        observed=transfer(entry,executable)
        counts[target['function']]+=1
        transfers[observed['kind']]+=1
        if 'source' in observed:edges[(observed['kind'],observed['source'],observed['target'])]+=1
        entry['transfer_classification']=observed
        entry['candidate_receiver_slots']=[f'0x{i*4:03X}' for i in range(35)
            if entry['a0_table_word_'+f'{i*4:03X}']==entry['pc']]
        parsed.append(entry)
    cursor=0
    for offset,(length,_) in sorted(spans.items()):
        require(offset==cursor,'Retained method bodies overlap or leave unexplained bytes.')
        cursor+=length
    require(cursor==len(code),'Unreferenced bytes follow the retained method bodies.')
    return parsed,dict(function_entry_counts=dict(counts),transfer_classifications=dict(transfers),
        observed_transfer_edges=[dict(kind=k,source=s,target=t,entries=n) for (k,s,t),n in sorted(edges.items())],
        method_entry_observations=len(parsed),distinct_complete_code_bodies=len(spans),
        every_observed_callee_byte_matches=True,virtual_receiver_slot_edges_accepted=0)


def validate_native_summary(summary,native,settings,entries):
    counts=Counter(f"{entry['pc']:08X}" for entry in entries)
    enabled=settings['arm_frame']<=settings['frames']
    require(summary['hook_enabled']==enabled and summary['hook_enabled_relative_frame']==settings['arm_frame']
            and summary['native_overflow']==0 and summary['event_bytes']==4356
            and summary['original_instruction_entries']==summary['native_total']==summary['drained_instruction_entries']
                ==native['instruction_entries']==len(entries)
            and summary['target_entry_counts']==dict(counts)
            and summary['targets']==settings['dispatch_targets'] and summary['memory_words']==settings['dispatch_words'],
            'Method native totals, drained events or complete target settings disagree.')


def observer_requested(manifest, settings):
    kind = manifest['runtime_kind']
    requested = manifest.get('instruction_observer_enabled', kind == 'dispatch_observer')
    require(type(requested) is bool and type(settings.get('trace_enabled')) is bool
            and requested is settings['trace_enabled'] and (not requested or kind == 'dispatch_observer'),
            'Recorded instruction-observer mode is inconsistent.')
    return requested


def inspect(folder):
    folder=Path(folder).resolve(strict=True)
    manifest=json.loads(owned_file(folder,'run-inputs.json').read_text(encoding='utf-8-sig'))
    result=json.loads(owned_file(folder,'result.json').read_text(encoding='utf-8-sig'))
    exit_record=json.loads(owned_file(folder,'exit.json').read_text(encoding='utf-8-sig'))
    require(result.get('status')=='recorded_pinned_dispatch_history' and result.get('input_files_preserved') is True
            and exit_record.get('exit_code')==0,'The owned method recorder did not finish and preserve its inputs.')
    program=validate_program(manifest['program'])
    collision_config=collision_selection(program)
    require(manifest['runtime_kind'] in ('distributed','dispatch_observer'),'Unsupported method runtime kind.')
    frozen={}
    for item in manifest['source_snapshots']:
        actual=verify_file(folder,item['file'],item)
        require(content_identity(actual)==content_identity(item['original']),'Snapshot and producer source identity disagree.')
        name=PureWindowsPath(item['original']['path']).name
        require(name not in frozen,'Ambiguous retained method source basename.')
        frozen[name]=(owned_file(folder,item['file']),actual)
    required={'ReplayColdStart.cs','RecordDispatchHistory.cs','DispatchInstructionTrace.cs','dispatch_entry_observer.h',
              'build_dispatch_observer.py','record_dispatch_history.py','dispatch_trace.py','SLPS_015.56','csc.dll'}
    require(required<=set(frozen),'Incomplete retained method producer source set.')
    for name,key in (('program.json','program_file'),('settings.json','settings_file'),('submitted.tsv','submitted'),
                     ('host/RecordDispatchHistory.exe','host_binary'),('host/RecordDispatchHistory.exe.config','host_configuration')):
        verify_file(folder,name,manifest[key])
    require(json.loads(owned_file(folder,'program.json').read_text())==program
            and owned_file(folder,'submitted.tsv').read_bytes()==expand_program(program,manifest['settings']['frames']),
            'Retained method program or submitted controller bytes disagree.')
    settings=manifest['settings']
    observing=observer_requested(manifest,settings)
    require(json.loads(owned_file(folder,'settings.json').read_text())==settings,'Retained method settings disagree.')
    frames=settings['frames']
    require(result['input_frames']==frames and result['runtime_kind']==manifest['runtime_kind'],
            'Completed method recorder result disagrees with its frozen inputs.')
    effective=dict(program,frames=frames)
    checkpoints=sorted({n for n in program['checkpoint_frames'] if n<=frames}|{0,frames})
    require(settings['checkpoint_frames']==checkpoints and settings['RAM_sample_interval']==program['RAM_sample_interval']
            and settings['arm_frame']==program['method_trace']['arm_frame'],'Method recording boundaries disagree.')
    for key,name in (('catalogue_file','dispatch-catalogue.json'),('provenance_file','dispatch-provenance.json'),
                     ('supplemental_file','method-ranges.json'),('supplemental_provenance_file','method-ranges-provenance.json')):
        verify_file(folder,name,manifest['dispatch'][key])
    raw=owned_file(folder,'dispatch-catalogue.json').read_bytes()
    supplemental=owned_file(folder,'method-ranges.json').read_bytes()
    executable=frozen['SLPS_015.56'][0].read_bytes()
    selected=verified_selection(program,json.loads(raw),json.loads(owned_file(folder,'dispatch-provenance.json').read_bytes()),raw,
        executable,json.loads(supplemental),json.loads(owned_file(folder,'method-ranges-provenance.json').read_bytes()),supplemental)
    sites=flow_sites(program,executable)
    require(settings.get('flow_sites',[])==flow_windows(program,executable),'Flow settings differ from declared canonical sites.')
    return_raw=None
    if 'return_provenance_file' in manifest['dispatch']:
        verify_file(folder,'return-helper-provenance.json',manifest['dispatch']['return_provenance_file'])
        return_raw=owned_file(folder,'return-helper-provenance.json').read_bytes()
    return_selection=verified_return_selection(program,selected,executable,
        json.loads(return_raw) if return_raw else None,return_raw)
    sdk_selection=None
    if program['method_trace'].get('sdk_reads',False):
        sdk_range_name='recovery-function-ranges.json' if program['method_trace'].get('cd_recovery',False) else \
            'heap-function-ranges.json' if program['method_trace'].get('heap_lifetime',False) else 'sdk-function-ranges.json'
        require(sdk_range_name in frozen,'Missing retained SDK range qualification.')
        sdk_selection=verified_sdk_selection(program,executable,json.loads(frozen[sdk_range_name][0].read_bytes()))
        require(return_selection is not None,'SDK read observation requires original method returns.')
        return_selection['sdk_targets']=sdk_selection
    require(settings.get('return_trace')==return_selection,'Return settings differ from qualified original methods.')
    require(settings.get('collision_calls')==collision_config,'Primitive sample settings differ from the declared program.')
    require(manifest['dispatch']['targets']==list(selected.values())
            and settings['dispatch_targets']==[dict(pc=pc,bytes=row['function_bytes']) for pc,row in selected.items()]
            and settings['dispatch_words']==list(manifest['dispatch']['memory_symbols'].values()),
            'Selected complete methods or memory words differ from native settings.')
    for name,expected in manifest['actual_runtime_files'].items():verify_file(folder,'host/'+name,expected)
    for name,expected in manifest['copied_host_sources'].items():verify_file(folder,'host/'+name,expected)
    kind=manifest['runtime_kind']
    profile=manifest['observer_profile']
    if kind=='dispatch_observer':
        require(profile is not None and profile.get('status')=='built_separate_dispatch_observer_core'
                and profile.get('observer_mode')=='method_entries'
                and profile.get('upstream_commit')==UPSTREAM and profile.get('mednafen_commit')==MEDNAFEN
                and profile.get('original_adapter_sha256')==SOURCE_SHA256['shock.cpp']
                and profile.get('existing_CPU_source_modified') is False and profile.get('input_files_preserved') is True,
                'Unsupported method observer provenance.')
        require(profile['observer_header_sha256']==frozen['dispatch_entry_observer.h'][1]['sha256']
                and profile['producer_sha256']==frozen['build_dispatch_observer.py'][1]['sha256']
                and set(EXPORTS)<=set(profile['exported_functions']),'Method observer producer identity differs.')
        require(bool(sites)==(profile.get('flow_protocol')==1),'Flow sites and observer protocol disagree.')
        require(bool(return_selection)==(profile.get('return_protocol')==1),'Return interface and observer protocol disagree.')
        require(bool(sdk_selection)==(profile.get('sdk_read_protocol')==1),'SDK interface and observer protocol disagree.')
        require(bool(collision_config)==(profile.get('collision_call_protocol')==1),'Primitive sample interface and observer protocol disagree.')
        if collision_config and 'ordinal_step' in collision_config:
            require(profile.get('collision_call_ordinal_selection') is True
                    and set(COLLISION_ORDINAL_EXPORTS)<=set(profile.get('exported_functions',[])),
                    'Recorded ordinal primitive selection lacks its native observer capability.')
        if collision_config:
            require({'CollisionCallTrace.cs','collision_call_observer.h','collision_calls.py'}<=set(frozen)
                    and profile.get('collision_call_event_bytes')==COLLISION_EVENT_BYTES
                    and profile.get('collision_call_frame_payload_bytes')==COLLISION_FRAME_BYTES
                    and profile.get('collision_call_header_sha256')==frozen['collision_call_observer.h'][1]['sha256']
                    and set(COLLISION_EXPORTS)<=set(profile['exported_functions']),
                    'Incomplete primitive sampler source or transport provenance.')
        if sdk_selection:
            require({'SdkReadTrace.cs','sdk_read_observer.h','sdk_reads.py',sdk_range_name}<=set(frozen)
                    and profile.get('sdk_read_event_bytes')==464
                    and profile.get('sdk_read_frame_payload_bytes') in (8*1024*1024,32*1024*1024)
                    and profile.get('sdk_read_header_sha256')==frozen['sdk_read_observer.h'][1]['sha256']
                    and set(SDK_EXPORTS)<=set(profile['exported_functions']),
                    'Incomplete original SDK read observer source or transport provenance.')
        if sites:
            require({'DispatchFlowTrace.cs','dispatch_flow_observer.h','dispatch_flow.py'}<=set(frozen)
                    and profile.get('flow_event_bytes')==664 and profile.get('flow_history_instructions')==16
                    and profile.get('flow_header_sha256')==frozen['dispatch_flow_observer.h'][1]['sha256']
                    and set(FLOW_EXPORTS)<=set(profile['exported_functions']),
                    'Incomplete native flow source or transport provenance.')
        if return_selection:
            require({'DispatchReturnTrace.cs','dispatch_return_observer.h','dispatch_returns.py','unused-local-census-checks.json'}<=set(frozen)
                    and profile.get('return_event_bytes')==600 and profile.get('return_frame_payload_bytes')==8*1024*1024
                    and profile.get('return_header_sha256')==frozen['dispatch_return_observer.h'][1]['sha256']
                    and set(RETURN_EXPORTS)<=set(profile['exported_functions']),
                    'Incomplete original return/data source or transport provenance.')
        for key,name in (('core','dll/shock.wbx'),('compressed_core','dll/shock.wbx.zst')):
            require(content_identity(profile[key])==content_identity(manifest['actual_runtime_files'][name]),
                    'Loaded method core differs from its build profile.')
    else:
        require(profile is None and settings['trace_enabled'] is False,'A distributed run cannot claim method observation.')
    output=folder/'observations'
    if not collision_config or not observing:
        require(all(not (output/name).exists() for name in ('collision-calls.bin','collision-call-ram.bin','collision-call-summary.json')),
                'Undeclared primitive sample data cannot be accepted.')
    else:
        require(all((output/name).is_file() for name in ('collision-calls.bin','collision-call-ram.bin','collision-call-summary.json')),
                'Declared primitive sample output is incomplete; use its dedicated verifier for payload acceptance.')
    native=json.loads((output/'report.json').read_text(encoding='utf-8-sig'))
    require(native['status']=='recorded_static_method_history' and native['frames_advanced']==frames+1
            and native['submitted_frames']==frames and native['game_RAM_injected'] is False
            and native['restored_state'] is False
            and native.get('observer_requested') is observing
            and native['observer_enabled']==(observing and settings['arm_frame']<=frames),
            'Incomplete method recording or unexpected execution mode.')
    observations=read_rows(output/'frames.tsv',FRAME_FIELDS)
    submitted=list(csv.DictReader(owned_file(folder,'submitted.tsv').read_text().splitlines(),delimiter='\t'))
    require(len(observations)==frames+1,'Incomplete native output sequence.')
    total=0
    for frame,row in enumerate(observations):
        count=int(row['sample_frames']);total+=count
        require(int(row['relative_frame'])==frame and int(row['core_frame'])==frame+1
                and row['phase']==('initial_neutral' if frame==0 else submitted[frame-1]['phase'])
                and digest(row['gpu_sha256']) and count>=0 and int(row['total_sample_frames'])==total,
                'Native frame/controller/audio boundaries disagree.')
    require(total==native['all_PCM_sample_frames'] and (output/'audio.pcm').stat().st_size==total*4,
            'Incomplete native PCM observations.')
    memory=read_rows(output/'ram-samples.tsv',RAM_FIELDS)
    expected_frames=sorted({frame for frame in range(frames+1) if frame%settings['RAM_sample_interval']==0}|set(checkpoints))
    require([int(row['relative_frame']) for row in memory]==expected_frames and len(memory)==native['RAM_samples'],
            'Incomplete RAM observation sequence.')
    require(all(int(row['core_frame'])==int(row['relative_frame'])+1 and digest(row['RAM_sha256']) for row in memory),
            'Invalid native RAM observation boundary or hash.')
    ram_by_frame={int(row['relative_frame']):row for row in memory}
    require([row['relative_frame'] for row in native['checkpoints']]==checkpoints,'Incomplete native checkpoints.')
    for row in native['checkpoints']:
        frame=row['relative_frame'];image=row['image']
        ram=(output/f'mainram-{frame}.bin').read_bytes();gpu=(output/f'gpu-{frame}.bin').read_bytes()
        rgb=(output/f'rgb-{frame}.bin').read_bytes()
        require(len(ram)==0x200000 and len(gpu)==0x100000
                and sha(ram)==row['RAM_sha256']==ram_by_frame[frame]['RAM_sha256']
                and sha(gpu)==row['GPU_sha256']==observations[frame]['gpu_sha256']
                and len(rgb)==image['width']*image['height']*3 and sha(rgb)==image['RGB_sha256'],
                'Complete checkpoint RAM/GPU/RGB differs from its native observation.')
        inspect_png((output/f'frame-{frame}.png').read_bytes(),image['width'],image['height'])
    entries=[];entry_report=dict(method_entry_observations=0,function_entry_counts={})
    if observing:
        entries,entry_report=validate_entries(read_rows(output/'method-instructions.tsv',ENTRY_FIELDS),effective,
            selected,(output/'method-code.bin').read_bytes(),executable)
        summary=json.loads((output/'method-trace-summary.json').read_text(encoding='utf-8-sig'))
        validate_native_summary(summary,native,settings,entries)
        if sites:
            flow_report,flow_edges=validate_flow((output/'method-flow.bin').read_bytes(),
                json.loads((output/'method-flow-summary.json').read_text(encoding='utf-8-sig')),
                entries,effective,executable)
            observed_receivers=len({(edge['receiver'],edge['table'],edge['slot'],edge['target']) for edge in flow_edges})
            flow_report['distinct_receiver_table_slot_edges']=observed_receivers
            entry_report['virtual_slot_flow']=flow_report
            entry_report['virtual_receiver_slot_edges_accepted']=observed_receivers
        else:
            require(not (output/'method-flow.bin').exists() and not (output/'method-flow-summary.json').exists(),
                    'Entry-only recordings cannot supply undeclared caller-flow data.')
        if return_selection:
            data=(output/'method-return-data.bin').read_bytes()
            report,returned=validate_returns((output/'method-returns.bin').read_bytes(),data,
                json.loads((output/'method-return-summary.json').read_text(encoding='utf-8-sig')),
                entries,return_selection,selected,executable,effective)
            track=manifest['source_manifest']['disc']['tracks'][0]
            actual=record_file(track['path'])
            require(content_identity(actual)==content_identity(track),'The complete return-data disc track changed.')
            with Path(track['path']).open('rb') as stream:
                report['disc_buffers']=verify_disc_buffers(returned,data,entries,return_selection,stream)
            require(record_file(track['path'])==actual,'The source disc changed while return buffers were checked.')
            entry_report['original_returns']=report
        else:
            require(all(not (output/name).exists() for name in
                ('method-returns.bin','method-return-data.bin','method-return-summary.json')),
                'Entry-only recordings cannot claim undeclared return/data observations.')
    else:
        require(native['instruction_entries']==0 and not (output/'method-instructions.tsv').exists()
                and not (output/'method-code.bin').exists() and not (output/'method-flow.bin').exists()
                and not (output/'method-flow-summary.json').exists() and all(not (output/name).exists() for name in
                    ('method-returns.bin','method-return-data.bin','method-return-summary.json')),
                'A run without instruction observation unexpectedly supplied method entries.')
    result=dict(status='inspected_bounded_original_method_history',runtime_kind=kind,input_frames=frames,
        GPU_observations=len(observations),RAM_observations=len(memory),complete_checkpoints=len(checkpoints),
        PCM_bytes=total*4,**entry_report,complete_state_parity_checked=False,original_hardware_timing_verified=False,
        whole_feature_groups_accepted=0,new_C_bytes=0)
    return result,dict(manifest=manifest,program=program,frames=observations,RAM=memory,entries=entries,
        native=native,folder=folder,producer_sources={name:content_identity(item) for name,(_,item) in frozen.items()})


def compare(reference,candidate,mode):
    require(mode in ('same-runtime','observer-output'),'Unknown method comparison mode.')
    before,left=inspect(reference);after,right=inspect(candidate)
    a,b=left['manifest'],right['manifest']
    source_a,source_b=left['producer_sources'],right['producer_sources']
    source_difference={name for name in set(source_a)|set(source_b) if source_a.get(name)!=source_b.get(name)}
    require(left['program']==right['program'] and a['settings']['frames']==b['settings']['frames']
            and a['settings']['checkpoint_frames']==b['settings']['checkpoint_frames'],
            'Method controller programs or recording boundaries differ.')
    for key in ('bios','disc'):
        if key=='bios':
            require({name:content_identity(item) for name,item in a['source_manifest'][key].items()}==
                    {name:content_identity(item) for name,item in b['source_manifest'][key].items()},'Method BIOS identities differ.')
        else:
            require([content_identity(item) for item in a['source_manifest'][key]['tracks']]==
                    [content_identity(item) for item in b['source_manifest'][key]['tracks']],'Complete method disc tracks differ.')
    runtime=lambda value:{name:content_identity(item) for name,item in value['actual_runtime_files'].items()}
    ar,br=runtime(a),runtime(b)
    changed=sorted(name for name in set(ar)|set(br) if ar.get(name)!=br.get(name))
    if mode=='same-runtime':
        require(a['runtime_kind']==b['runtime_kind'] and not changed,'Same-runtime method comparison has different cores.')
        require(a['settings']['trace_enabled'] is b['settings']['trace_enabled'],
                'Same-runtime method comparisons require the same instruction-observer mode.')
        require(not source_difference,'Same-runtime method producer sources or compiler identities differ.')
        require(left['entries']==right['entries'],'Original/rebuilt method entry records differ.')
        if a['settings']['trace_enabled'] and left['program']['method_trace'].get('flow_sites'):
            for name in ('method-flow.bin','method-flow-summary.json'):
                require(files_equal(left['folder']/'observations'/name,right['folder']/'observations'/name),
                        'Original/rebuilt native caller-flow records differ.')
        if a['settings']['trace_enabled'] and left['program']['method_trace'].get('return_trace'):
            for name in ('method-returns.bin','method-return-data.bin','method-return-summary.json'):
                require(files_equal(left['folder']/'observations'/name,right['folder']/'observations'/name),
                        'Original/rebuilt method return/data observations differ.')
    else:
        require({a['runtime_kind'],b['runtime_kind']}=={'distributed','dispatch_observer'} and changed
                and set(changed)<=CORE_FILES,'Observer-output comparison permits only declared core artifacts to differ.')
        require(source_difference<={'shock.wbx','shock.wbx.zst','profile.json'},
                'Observer-output comparison has different host/observer/program/compiler source identities.')
    require(left['frames']==right['frames'] and left['RAM']==right['RAM'],'Method GPU/RAM/PCM frame observations differ.')
    outa,outb=left['folder']/'observations',right['folder']/'observations'
    require(files_equal(outa/'audio.pcm',outb/'audio.pcm'),'Complete method PCM output differs.')
    require(left['native']['checkpoints']==right['native']['checkpoints'],'Method checkpoint metadata differs.')
    for row in left['native']['checkpoints']:
        for prefix in ('mainram','gpu','rgb'):
            name=f"{prefix}-{row['relative_frame']}.bin"
            require(files_equal(outa/name,outb/name),'Complete method checkpoint differs: '+name)
    return dict(status='compared_bounded_original_method_histories',mode=mode,reference=before,candidate=after,
        runtime_files_changed=changed,every_recorded_game_output_equal=True,
        method_entries_compared=len(left['entries']) if mode=='same-runtime' else 0,
        complete_state_parity_checked=False,original_hardware_timing_verified=False,
        whole_feature_groups_accepted=0,whole_NPC_encounters_accepted=0,new_C_bytes=0)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',required=True,type=Path)
    parser.add_argument('--candidate',type=Path)
    parser.add_argument('--mode',choices=('same-runtime','observer-output'),default='same-runtime')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        output=args.output.resolve()
        require(output!=ROOT/'.decomp-lab' and output.is_relative_to(ROOT/'.decomp-lab') and not output.exists(),
                'Choose a fresh private JSON report inside .decomp-lab.')
        report=compare(args.reference,args.candidate,args.mode) if args.candidate else inspect(args.reference)[0]
        report['verification_source_sha256']={name:sha((ROOT/name).read_bytes()) for name in
            ('tools/inspect_dispatch_history.py','tools/dispatch_trace.py','tools/compare_npc_history.py',
             'tools/psx_image.py','tools/runtime_inputs.py','tools/dispatch_flow.py','tools/dispatch_returns.py')}
        write_json(output,report)
        print(json.dumps(report),flush=True)
        return 0
    except (OSError,ValueError,KeyError) as error:
        print(str(error),file=sys.stderr)
        return 2


if __name__=='__main__':sys.exit(main())
