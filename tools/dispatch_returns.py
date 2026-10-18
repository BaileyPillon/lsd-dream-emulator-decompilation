"""Verify original returns, synchronous-helper observations and bounded read data.

Read's zero result is not a transferred-byte count. Only a complete captured
synchronous return buffer is compared with the verified disc's actual sectors.
"""
from collections import Counter
import hashlib
import struct

from tools.psx_image import executable_offset
from tools.replay_cold_start_headless import require
from research.compiler.compare_function import CANONICAL_SHA256

EVENT_BYTES = 600
RETURN_EXPORTS = ('LsdResetDispatchReturns','LsdConfigureDispatchReturns','LsdConfigureDispatchReturnIO','LsdStartDispatchReturns',
    'LsdBeginDispatchReturnFrame','LsdGetDispatchReturnCount','LsdGetDispatchReturnTotal',
    'LsdGetDispatchReturnEntries','LsdGetDispatchReturnOverflow','LsdGetDispatchReturnMismatches',
    'LsdGetDispatchReturnPending','LsdGetDispatchReturnMaxDepth','LsdGetDispatchReturnEvents',
    'LsdGetDispatchReturnData','LsdGetDispatchReturnDataBytes')
FIELDS = ('frame','ordinal','entry_id','parent_id','kind','base_ordinal','entry_frame','entry_timestamp',
    'entry_pc','entry_sp','entry_ra','a0','a1','a2','a3','return_pc','return_sp','return_ra','v0','v1','timestamp',
    'jump_pc','delay_pc','jump_ram','jump_fetch','delay_ram','delay_fetch','jump_rs','jump_sp','delay_sp',
    'jump_flags','delay_flags','jump_sr','delay_sr','sr',
    *('a0_word_'+f'{n*4:02X}' for n in range(11)),
    *('table_word_'+f'{n*4:03X}' for n in range(35)), *('memory_word_'+str(n) for n in range(4)),
    'buffer_address','buffer_bytes','buffer_offset','buffer_status','helper_code_bytes','helper_code_offset',
    'sequence_low','sequence_high','entry_sequence_low','entry_sequence_high',
    'entry_transfer_pc','entry_delay_pc','entry_transfer_ram','entry_transfer_fetch','entry_delay_ram','entry_delay_fetch',
    'entry_transfer_flags','entry_delay_flags','entry_transfer_sr','entry_delay_sr',
    'entry_transfer_rs','entry_transfer_sp','entry_delay_sp',
    *('entry_a0_word_'+f'{n*4:02X}' for n in range(11)),
    'read_request_entries','read_poll_entries','read_poll_returns','last_poll_value',
    'request_a0','request_a1','request_a2','last_poll_frame','last_poll_timestamp',
    'poll_return_pc','poll_return_sp','poll_jump_pc','poll_delay_pc',
    'poll_jump_ram','poll_jump_fetch','poll_delay_ram','poll_delay_fetch','poll_jump_rs',
    'poll_jump_flags','poll_delay_flags','poll_jump_sr','poll_delay_sr',
    'poll_sequence_low','poll_sequence_high','request_sequence_low','request_sequence_high',
    'request_call_pc','request_ra','poll_call_pc','poll_ra','poll_entry_sp')
assert len(FIELDS) == EVENT_BYTES // 4


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sequence(row, prefix=''):
    return row[prefix+'sequence_low'] | row[prefix+'sequence_high'] << 32


def verified_return_selection(program, selected, executable, provenance, raw):
    config = program['method_trace'].get('return_trace')
    if config is None:
        return None
    require(isinstance(config,dict) and config.get('kind')=='original_CD_Read_buffers'
            and config.get('read_method')=='cd_file_driver_read'
            and config.get('synchronous_helper')=='cd_file_driver_read_sectors',
            'Unsupported original return/buffer interface.')
    require(isinstance(provenance,dict) and isinstance(raw,bytes) and program['method_trace'].get('flow_sites'),
            'Original returns require sealed helper provenance and selected caller-flow sites.')
    require(sha(executable)==CANONICAL_SHA256==program['executable_sha256']
            and sha(raw)==config.get('helper_provenance_sha256')
            and provenance.get('status')=='verified_canonical_compiler_census_and_corrected_source_quality'
            and provenance.get('canonical_executable_sha256')==CANONICAL_SHA256
            and provenance.get('normal_complete_build_equal') is True
            and provenance.get('fresh_complete_build_equal') is True,
            'The return helper lacks its sealed complete canonical build qualification.')
    main=[row for row in selected.values() if row['function']==config['read_method']]
    helpers=[row for row in provenance.get('source_removal_records',[]) if row['function']==config['synchronous_helper']]
    require(len(main)==len(helpers)==1,'Ambiguous or missing original return methods.')
    helper=helpers[0];pc=int(helper['original_address'],16);size=helper['original_function_bytes']
    require(helper.get('complete_symbolic_image_matches_regular') is True
            and helper.get('independent_GNU_extents_agree') is True
            and type(size) is int and 4<=size<=4096 and size%4==0 and pc%4==0,
            'Require the helper complete ELF/GNU function extent.')
    offset=executable_offset(executable,pc,size);code=executable[offset:offset+size]
    require(sha(code)==helper['original_function_sha256'],'Complete original return helper differs from its range hash.')
    require(all(pc+size<=target or pc>=target+row['function_bytes'] for target,row in selected.items()),
            'The synchronous helper must be separate from base entry targets.')
    targets=[]
    for key in ('request_pc','poll_pc'):
        value=config.get(key)
        require(isinstance(value,str) and len(value)==10 and value.startswith('0x')
                and all(c in '0123456789ABCDEF' for c in value[2:]),'Invalid original request/poll target.')
        target=int(value,16);executable_offset(executable,target,4);targets.append(target)
    require(targets[0]!=targets[1],'Request and polling targets must be distinct.')
    calls=[]
    for target in targets:
        found=[pc+i for i in range(0,len(code)-4,4)
               if (word:=struct.unpack_from('<I',code,i)[0])>>26==3
               and (((pc+i+4)&0xF0000000)|((word&0x03FFFFFF)<<2))==target]
        require(len(found)==1,'The complete helper must contain one qualified direct call to each selected wrapper.')
        calls.append(found[0])
    adjustments=[((word&65535)^0x8000)-0x8000 for (word,) in struct.iter_unpack('<I',code) if word>>16==0x27BD]
    require(len(adjustments)==2 and adjustments[0]<0 and adjustments[1]==-adjustments[0],
            'Require the original helper single fixed stack frame.')
    return dict(read_pc=int(main[0]['pc'],16),helper_pc=pc,helper_bytes=size,
        request_pc=targets[0],poll_pc=targets[1],request_call=calls[0],poll_call=calls[1])


def _instruction(executable,pc,ram,fetch,flags,sr):
    require(flags in (1,3) and not sr&0x10000,'Unqualified return instruction cache/RAM context.')
    at=executable_offset(executable,pc,4)
    require(ram==fetch==struct.unpack_from('<I',executable,at)[0],
            'Observed effective/RAM return instruction differs from the original.')


def _jump_return(row,executable,prefix='',target=None,span=None):
    jump,delay=row[prefix+'jump_pc'],row[prefix+'delay_pc']
    require(delay==jump+4,'A return lacks its actual delay slot.')
    if span:
        require(span[0]<=jump<delay<span[0]+span[1],'Return instruction lies outside the complete original callee.')
    for name in ('jump','delay'):
        _instruction(executable,row[prefix+name+'_pc'],row[prefix+name+'_ram'],row[prefix+name+'_fetch'],
                     row[prefix+name+'_flags'],row[prefix+name+'_sr'])
    require(row[prefix+'jump_fetch']==0x03E00008 and row[prefix+'jump_rs']==target,
            'The actual JR RA operand does not return to the captured caller.')
    word=row[prefix+'delay_fetch'];op=word>>26
    require(op not in (1,2,3,4,5,6,7) and not (op==0 and word&63 in (8,9,12,13)),
            'Unsupported branch/trap in a return delay slot.')


def _frame(executable,pc,size):
    at=executable_offset(executable,pc,size)
    values=[((word&65535)^0x8000)-0x8000 for (word,) in struct.iter_unpack('<I',executable[at:at+size])
            if word>>16==0x27BD]
    require(len(values)==2 and values[0]<0 and values[1]==-values[0],'Unsupported fixed original method frame.')
    return -values[0]


def validate_returns(data,payload,summary,entries,settings,selected,executable,program):
    require(settings is not None,'No original return settings were selected.')
    recorded_settings=summary.get('settings')
    # The optional SDK host adds this nullable property to the existing C# type.
    # Preserve old return-only selections while rejecting undeclared SDK targets.
    if (isinstance(recorded_settings,dict) and isinstance(settings,dict)
            and 'sdk_targets' not in settings and recorded_settings.get('sdk_targets',False) is None):
        recorded_settings={key:value for key,value in recorded_settings.items() if key!='sdk_targets'}
    require(summary.get('protocol')==1 and summary.get('event_bytes')==EVENT_BYTES
            and recorded_settings==settings and summary.get('frame_payload_limit')==8*1024*1024
            and summary.get('native_overflow')==summary.get('native_mismatches')==summary.get('pending_entries')==0
            and summary.get('original_game_RAM_injected') is False and summary.get('original_CPU_source_modified') is False
            and summary.get('return_values_are_not_transfer_counts') is True,
            'Native return source, protocol, overflow or pending-call state is unqualified.')
    require(len(data)%EVENT_BYTES==0 and len(data)//EVENT_BYTES==summary.get('returns')==
            summary.get('native_returns')==summary.get('native_entries') and len(payload)==summary.get('payload_bytes'),
            'Missing, extra, truncated or lost native return/payload records.')
    parsed=[dict(zip(FIELDS,words)) for words in struct.iter_unpack('<150I',data)]
    by_id={row['entry_id']:row for row in parsed}
    require(len(by_id)==len(parsed) and set(by_id)==set(range(1,len(parsed)+1)),
            'Tracked entry IDs are missing or duplicated.')
    require([row['entry_id'] for row in sorted(parsed,key=lambda row:sequence(row,'entry_'))]==list(range(1,len(parsed)+1)),
            'Tracked creation IDs do not follow actual CPU entry order.')
    cursor=0;previous=-1;base_ids=set();helpers=[];request_counts=Counter()
    for ordinal,row in enumerate(parsed,1):
        seq,start=sequence(row),sequence(row,'entry_')
        require(row['ordinal']==ordinal and previous<seq and start<seq
                and program['method_trace']['arm_frame']<=row['entry_frame']<=row['frame']<=program['frames']
                and row['entry_timestamp']<2**31 and row['timestamp']<2**31,
                'Invalid return ordinal, frame, timestamp or CPU sequence.')
        previous=seq
        require(row['return_pc']==row['entry_ra']==row['return_ra'] and row['return_sp']==row['entry_sp']
                and row['entry_sp']%8==0 and 0x80010000<=row['entry_sp']<0x80200000 and not row['sr']&0x10000,
                'A return disagrees with its original stack/caller boundary.')
        parent=by_id.get(row['parent_id'])
        if row['parent_id']:
            require(parent is not None and parent['entry_id']<row['entry_id']
                    and sequence(parent,'entry_')<start<seq<sequence(parent),
                    'A helper or nested return has an invalid call-parent interval.')
        if row['kind']==1:
            base=row['base_ordinal'];require(1<=base<=len(entries) and base not in base_ids,'Missing or duplicate base return.')
            base_ids.add(base);entry=entries[base-1]
            require(all(row[left]==entry[right] for left,right in (
                ('entry_frame','relative_frame'),('entry_timestamp','timestamp'),('entry_pc','pc'),
                ('entry_sp','sp'),('entry_ra','ra'),('a0','a0'),('a1','a1'),('a2','a2'),('a3','a3'))),
                'A base return does not identify its complete original entry.')
            require(all(row['entry_a0_word_'+f'{n*4:02X}']==entry['a0_word_'+f'{n*4:02X}'] for n in range(11)),
                    'Return entry receiver snapshot differs from the base event.')
            require(row['entry_transfer_pc']==entry['transfer_pc'] and row['entry_delay_pc']==entry['delay_pc']
                    and row['entry_transfer_ram']==row['entry_transfer_fetch']==entry['transfer_word']
                    and row['entry_delay_ram']==row['entry_delay_fetch']==entry['delay_word'],
                    'Return tracker caller context differs from the qualified base entry.')
            require(row['helper_code_bytes']==row['helper_code_offset']==0,'A base entry cannot claim helper code.')
            span=(row['entry_pc'],selected[row['entry_pc']]['function_bytes'])
        else:
            require(row['kind']==2 and row['base_ordinal']==0 and parent is not None
                    and parent['kind']==1 and parent['entry_pc']==settings['read_pc']
                    and row['entry_pc']==settings['helper_pc']
                    and all(row[name]==parent[name] for name in ('a0','a1','a2')),
                    'Synchronous helper does not belong to the observed Read arguments.')
            size,at=row['helper_code_bytes'],row['helper_code_offset']
            require(size==settings['helper_bytes'] and at==cursor and at+size<=len(payload),
                    'Missing, overlapping or unreferenced complete helper entry code.')
            original=executable_offset(executable,settings['helper_pc'],size)
            require(payload[at:at+size]==executable[original:original+size],
                    'Full synchronous-helper code captured at entry differs from the original.')
            cursor+=size;span=(settings['helper_pc'],size)
            require(row['entry_a0_word_0C']!=0,'Synchronous helper entered with an unopened file receiver.')
            require(row['entry_sp']==parent['entry_sp']-_frame(executable,parent['entry_pc'],selected[parent['entry_pc']]['function_bytes'])
                    and row['entry_transfer_sp']==row['entry_delay_sp']==row['entry_sp'],
                    'Synchronous helper does not enter on the original Read stack frame.')
            source,delay=row['entry_transfer_pc'],row['entry_delay_pc']
            require(parent['entry_pc']<=source<delay<parent['entry_pc']+selected[parent['entry_pc']]['function_bytes']
                    and delay==source+4 and row['entry_ra']==source+8,
                    'Helper lacks its original Read call/delay boundary.')
            for name in ('transfer','delay'):
                _instruction(executable,row['entry_'+name+'_pc'],row['entry_'+name+'_ram'],row['entry_'+name+'_fetch'],
                    row['entry_'+name+'_flags'],row['entry_'+name+'_sr'])
            word=row['entry_transfer_fetch']
            require(word>>26==3 and (((source+4)&0xF0000000)|((word&0x03FFFFFF)<<2))==settings['helper_pc'],
                    'Synchronous helper was not called by the recorded original direct JAL.')
            require(row['read_request_entries']>=1 and row['read_poll_entries']==row['read_poll_returns']>=1
                    and row['last_poll_value']==0 and row['v0']==0
                    and row['request_a0']==row['a2']>>11 and row['request_a1']==row['a1'] and row['request_a2']==0x80,
                    'Original synchronous request arguments or final SDK polling result disagree.')
            require(row['request_call_pc']==settings['request_call'] and row['request_ra']==settings['request_call']+8
                    and row['poll_call_pc']==settings['poll_call'] and row['poll_ra']==settings['poll_call']+8
                    and row['poll_return_pc']==settings['poll_call']+8 and row['poll_return_sp']==row['poll_entry_sp']
                    and row['poll_entry_sp']==row['entry_sp']-_frame(executable,row['entry_pc'],settings['helper_bytes'])
                    and start<sequence(row,'request_')<sequence(row,'poll_')<seq,
                    'Original request/poll events lack ordered helper/caller boundaries.')
            _jump_return(row,executable,'poll_',row['poll_return_pc'])
            helpers.append(row);request_counts['request_entries']+=row['read_request_entries']
            request_counts['poll_entries']+=row['read_poll_entries'];request_counts['poll_returns']+=row['read_poll_returns']
        _jump_return(row,executable,target=row['return_pc'],span=span)
        is_read=row['entry_pc']==settings['read_pc'] or row['kind']==2
        if is_read:
            require(row['v0']==0,'Original Read/helper result is not the captured zero result word.')
            require(row['buffer_status']==1 and row['buffer_address']==row['a1'] and row['buffer_bytes']==row['a2']
                    and row['buffer_bytes']>0 and (row['a1']&0x1FFFFFFF)+row['a2']<=0x200000
                    and row['buffer_offset']==cursor and cursor+row['buffer_bytes']<=len(payload),
                    'Missing, invalid or overlapping complete Read return RAM window.')
            cursor+=row['buffer_bytes']
        else:
            require(row['buffer_status']==row['buffer_bytes']==row['buffer_offset']==row['buffer_address']==0,
                    'A non-Read method cannot claim a Read destination payload.')
    require(base_ids==set(range(1,len(entries)+1)) and cursor==len(payload),
            'Base returns or referenced complete payload bytes are missing.')
    stack=[];maximum=0
    timeline=sorted([(sequence(row,'entry_'),0,row) for row in parsed]+[(sequence(row),1,row) for row in parsed],key=lambda item:(item[0],item[1]))
    for _,kind,row in timeline:
        if kind==0:
            require(row['parent_id']==(stack[-1] if stack else 0),'Tracked parent skips the actual enclosing call.')
            stack.append(row['entry_id']);maximum=max(maximum,len(stack))
        else:
            require(stack and stack.pop()==row['entry_id'],'Tracked returns are not LIFO.')
    require(not stack and summary.get('max_depth')==maximum,'Native maximum/pending call depth disagrees.')
    for helper in helpers:
        parent=by_id[helper['parent_id']]
        left=payload[helper['buffer_offset']:helper['buffer_offset']+helper['buffer_bytes']]
        right=payload[parent['buffer_offset']:parent['buffer_offset']+parent['buffer_bytes']]
        require(left==right,'Synchronous destination data changed before the enclosing Read returned.')
    counts=Counter(row['entry_pc'] for row in parsed if row['kind']==1)
    return dict(tracked_returns=len(parsed),base_method_returns=len(base_ids),synchronous_helper_returns=len(helpers),
        base_return_counts={f'0x{pc:08X}':count for pc,count in sorted(counts.items())},
        captured_payload_bytes=len(payload),**dict(request_counts),max_depth=maximum,
        complete_return_values_are_not_transfer_counts=True,complete_state_parity_checked=False),parsed


def bcd_lba(word):
    values=[]
    for shift,limit in ((0,100),(8,60),(16,75)):
        byte=(word>>shift)&255
        require(byte&15<10 and byte>>4<10,'Invalid BCD CD position.')
        value=(byte>>4)*10+(byte&15)
        require(value<limit,'CD position component exceeds its native range.')
        values.append(value)
    lba=(values[0]*60+values[1])*75+values[2]-150
    require(lba>=0,'A file read cannot begin before the data track.')
    return lba


class Form1Disc:
    """Read ISO metadata and complete 2048-byte payloads from a verified raw data track."""
    def __init__(self,stream):
        self.stream=stream
        stream.seek(0,2);self.bytes=stream.tell()
        require(self.bytes>0 and self.bytes%2352==0,'Require a complete 2352-byte raw track.')
        volume=self.extent(16,2048)
        require(volume[:7]==b'\x01CD001\x01','The raw track has no primary ISO9660 volume.')
        self.files={};seen=set()
        def record(data):
            require(len(data)>=34 and len(data)==data[0] and data[1]==0 and data[26]==data[27]==0,
                    'Unsupported ISO record or interleaved/extended extent.')
            lba,size=struct.unpack_from('<I',data,2)[0],struct.unpack_from('<I',data,10)[0]
            require(lba==struct.unpack_from('>I',data,6)[0] and size==struct.unpack_from('>I',data,14)[0]
                    and 33+data[32]<=len(data),'ISO record endian copies or name extent disagree.')
            return lba,size,data[25],data[33:33+data[32]]
        def visit(lba,size,path,depth=0):
            require(depth<16 and size<=4*1024*1024 and (lba,size) not in seen,'Unbounded, repeated or oversized ISO directory.')
            seen.add((lba,size));data=self.extent(lba,size);cursor=0
            while cursor<len(data):
                length=data[cursor]
                if length==0:cursor=(cursor//2048+1)*2048;continue
                require(cursor%2048+length<=2048 and cursor+length<=len(data),'ISO directory record crosses its extent.')
                item=record(data[cursor:cursor+length]);cursor+=length
                address,bytes_,flags,name=item
                if name in (b'\0',b'\1'):continue
                require(not flags&128,'Multi-extent ISO files require a separate profile.')
                name=name.decode('ascii');require(name and '/' not in name and '\\' not in name,'Invalid ISO file name.')
                child=path+'/'+name.split(';',1)[0]
                if flags&2:visit(address,bytes_,child,depth+1)
                else:self.files.setdefault((address,bytes_),[]).append(child)
        root=record(volume[156:156+volume[156]])
        require(root[2]&2,'ISO root is not a directory.')
        visit(root[0],root[1],'')

    def extent(self,lba,size):
        require(type(lba) is int and type(size) is int and lba>=0 and 0<=size<=4*1024*1024
                and (lba+(size+2047)//2048)*2352<=self.bytes,'Invalid or truncated raw sector extent.')
        data=[]
        for sector in range((size+2047)//2048):
            index=lba+sector;self.stream.seek(index*2352);raw=self.stream.read(2352)
            require(len(raw)==2352 and raw[:12]==b'\0'+b'\xff'*10+b'\0' and raw[15]==2
                    and raw[16:20]==raw[20:24] and not raw[18]&0x20,
                    'Synchronous buffer extent is not complete MODE2 Form1 data.')
            require(bcd_lba(int.from_bytes(raw[12:15],'little'))==index,'Raw CD sector header position disagrees with LBA.')
            data.append(raw[24:2072])
        return b''.join(data)[:size]


def verify_disc_buffers(records,payload,entries,settings,stream):
    disc=Form1Disc(stream);by_id={row['entry_id']:row for row in records}
    files=[]
    for helper in records:
        if helper['kind']!=2:continue
        parent=by_id[helper['parent_id']];entry=entries[parent['base_ordinal']-1]
        require(entry['transfer_pc']==0x80026BB0,'This full-file profile needs the original file_buf_load Read call.')
        require(all(helper['entry_a0_word_'+field]==entry['a0_word_'+field] for field in ('0C','18','1C')),
                'Synchronous file receiver inputs changed between Read and helper entry.')
        lba=bcd_lba(entry['a0_word_18']);size=entry['a0_word_1C'];requested=entry['a2']
        require((lba,size) in disc.files and requested==((size>>11)+1)<<11,
                'Synchronous receiver size/position or original full-file aligned length disagrees with ISO metadata.')
        expected=disc.extent(lba,requested)
        actual=payload[helper['buffer_offset']:helper['buffer_offset']+helper['buffer_bytes']]
        require(actual==expected,'Complete synchronous return buffer differs from the verified disc sectors.')
        files.append(dict(helper_entry_id=helper['entry_id'],parent_base_ordinal=parent['base_ordinal'],
            ISO_paths=disc.files[(lba,size)],lba=lba,file_bytes=size,requested_bytes=requested,
            trailing_bytes=requested-size,fully_extra_sector_for_aligned_file=size%2048==0,
            complete_buffer_sha256=sha(actual),logical_file_sha256=sha(actual[:size])))
    return dict(synchronous_return_buffers_matched=len(files),complete_requested_bytes_compared=sum(row['requested_bytes'] for row in files),
        logical_file_bytes_compared=sum(row['file_bytes'] for row in files),
        aligned_files_with_an_extra_sector=sum(row['fully_extra_sector_for_aligned_file'] for row in files),
        files=files,scope='Complete requested RAM windows at synchronous helper and enclosing Read returns match original sectors, including trailing bytes. These are not CD hardware transfer counts or acceptance of asynchronous completion/error paths.')
