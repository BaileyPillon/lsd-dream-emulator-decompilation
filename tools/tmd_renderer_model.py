"""Scalar predictions for constructed calls to LSD's original TMD drawer.

This does not run original MIPS or predict GPU pixels.
Register arithmetic is supplied by the separately native-qualified GTE oracle.
"""
import struct

from tools.gte_state_model import GteState, require, signed, unsigned
from tools.tmd_packets import packet_layout
from tools.verify_gte_state import matrix,IDENTITY

BUFFER = 0x120000
OBJECT, OT, COORD, GEOM = BUFFER, BUFFER+0x100, BUFFER+0x200, BUFFER+0x300
VERTEX, NORMAL, PRIM = BUFFER+0x400, BUFFER+0x480, BUFFER+0x600
ORDER, GPU, CONTEXT = 0x150000, 0x160000, 0x1F800000
GPU_BYTES=65536
BUFFER_BYTES=65536
MODEL=BUFFER+0x1000
TRI, QUAD, OUT = 0x8ACD0, 0x8AEE8, 0x8E794
GLOBALS = ((TRI,0x218),(QUAD,0x400),(0x90C18,4),(0x8E248,12),(OUT,4))
FORMATS = ((0x20,0),(0x20,4),(0x21,1),(0x24,0),(0x25,1),(0x28,0),
    (0x29,1),(0x2C,0),(0x2D,1),(0x31,1),(0x35,1),(0x39,1),(0x3D,1))
SOURCE_FORMATS=FORMATS+((0x30,0),(0x34,0),(0x38,0),(0x3C,0))
COLORS = (0x44332211,0x88553377,0xCC997755,0xEE1199BB)
UV = (0x12342211,0x23454433,0x45676655,0x67898877)
RTPT,NCLIP,AVSZ3,RTPS = 0x4A280030,0x4B400006,0x4B58002D,0x4A180001
DPCS,NCDS,DPCT = 0x4A780010,0x4AE80413,0x4AF8002A


def put(data,at,value):
    struct.pack_into('<I',data,at,unsigned(value))


def get(data,at):
    return struct.unpack_from('<I',data,at)[0]


def packet_specs(case):
    """Validate supplied compatible mode runs and explicit geometry references."""
    if 'raw_tmd' in case:
        from tools.tmd_corpus_model import raw_specs
        return raw_specs(case)
    if 'packets' in case:
        raw=case['packets']
        require(type(raw) in (list,tuple) and len(raw)<=64,'Use a bounded packet list.')
    else:
        require(case.get('primitives',1) in (0,1),'Use packets for a multi-primitive fixture.')
        raw=[] if case.get('primitives',1)==0 else [case]
    result=[]
    for source in raw:
        mode,flags=source['mode'],source['flags']
        require(type(mode) is int and type(flags) is int and (mode&0xFD,flags) in SOURCE_FORMATS,
            'Use a declared renderer packet format.')
        if result and mode==result[-1]['mode']:
            require(flags==result[-1]['flags'],'Same-mode runs require compatible flags in this profile.')
        count=4 if mode&8 else 3
        indices=tuple(source.get('indices',range(count)))
        require(len(indices)==count and all(type(i) is int and 0<=i<16 for i in indices),
            'Use bounded explicit vertex indices.')
        colors=tuple(source.get('colors',case.get('colors',COLORS)))
        uv=tuple(source.get('uv',case.get('uv',UV)))
        layout=packet_layout(mode,flags)
        require(len(colors)>=layout.color_records and len(uv)>=layout.uv_records and
            all(type(v) is int and 0<=v<=0xFFFFFFFF for v in colors+uv),'Invalid packet color/UV words.')
        normal=source.get('normal_index',0)
        ignored=source.get('ignored_count',1)
        require(type(normal) is int and 0<=normal<48 and type(ignored) is int and 0<=ignored<=65535,
            'Invalid normal index or ignored interior header halfword.')
        result.append(dict(mode=mode,flags=flags,indices=indices,colors=colors,uv=uv,
            normal_index=normal,ignored_count=ignored))
    return result


def constructed_fixture(case):
    """Linked primitive/mode runs and explicit camera/light state; no assets."""
    specs=packet_specs(case)
    alias=case.get('alias',0)
    require(alias in (0,0x80000000),'Use a declared address alias.')
    vertices=case.get('vertices',((-128,-128,4096),(128,-128,4096),
        (-128,128,4096),(128,128,4096)))
    normals=case.get('normals',(case.get('normal',(256,768,4096)),))
    require(0<len(vertices)<=16 and 0<len(normals)<=48,'Fixture geometry pools exceed their spans.')
    require(all(all(i<len(vertices) for i in s['indices']) and s['normal_index']<len(normals) for s in specs),
        'Primitive references outside its supplied pools.')
    data = bytearray(4096)
    struct.pack_into('<III',data,0,unsigned(case.get('attributes',0)),COORD|alias,GEOM|alias)
    put(data,OT-BUFFER+4,ORDER|alias)
    struct.pack_into('<7I',data,GEOM-BUFFER,VERTEX|alias,len(vertices),NORMAL|alias,len(normals),PRIM|alias,len(specs),0)
    for index,point in enumerate(vertices):
        struct.pack_into('<4h',data,VERTEX-BUFFER+8*index,*point,0)
    for index,normal in enumerate(normals):struct.pack_into('<4h',data,NORMAL-BUFFER+8*index,*normal,0)
    at = PRIM-BUFFER
    run_start,run_count,previous=None,0,None
    for spec in specs:
        mode,flags=spec['mode'],spec['flags']
        layout=packet_layout(mode,flags)
        require(at+layout.bytes<=len(data),'Primitive stream exceeds its supplied span.')
        if mode!=previous:
            if run_start is not None:struct.pack_into('<H',data,run_start,run_count)
            run_start,run_count=at,0
        run_count+=1
        previous=mode
        struct.pack_into('<HBB',data,at,spec['ignored_count'],flags,mode)
        for i in range(layout.uv_records):put(data,at+4+4*i,spec['uv'][i])
        for i in range(layout.color_records):put(data,at+4+4*layout.uv_records+4*i,spec['colors'][i])
        for offset in layout.normals:struct.pack_into('<H',data,at+offset,spec['normal_index'])
        for index,offset in zip(spec['indices'],layout.vertices):struct.pack_into('<H',data,at+offset,index)
        at+=layout.bytes
    if run_start is not None:struct.pack_into('<H',data,run_start,run_count)
    return bytes(data)


def case_fixture(case):
    """Constructed inputs or exact original TMD bytes with predicted SDK binding."""
    alias=case.get('alias',0)
    require(alias in (0,0x80000000),'Use a declared address alias.')
    if 'raw_tmd' in case:
        from tools.tmd_corpus_model import raw_fixture
        data=raw_fixture(case)
    else:data=constructed_fixture(case)
    values = {CONTEXT:bytes([0xA7])*4096,GPU:bytes([0xD3])*GPU_BYTES,
        ORDER:struct.pack('<I',case.get('ordering_head',0xA1FFFFFF))*1024,TRI:bytes([0xC5])*0x218,
        QUAD:bytes([0xB6])*0x400,0x90C18:bytes([0x91])*4,
        0x8E248:bytes([0x92])*12,OUT:struct.pack('<I',GPU|alias)}
    width,height=case.get('viewport',(512,480))
    override=case.get('division_override')
    values[0x8A824]=struct.pack('<II4BII',width,height,17,34,51,68,int(override is not None),override or 0)
    writes = matrix(0,case.get('matrix',IDENTITY))+matrix(1)+matrix(2)+[(0,26,case.get('h',256)),(0,27,0),
        (0,28,unsigned(case.get('fog',0)<<12)),(0,29,1365),(0,30,1024)]
    writes += [(0,13+i,value) for i,value in enumerate(case.get('background',(1024,2048,3072)))]
    writes += [(0,21+i,value) for i,value in enumerate(case.get('far_color',(160,320,480)))]
    writes += [(0,5+i,unsigned(value)) for i,value in enumerate(case.get('translation',(0,0,0)))]
    return bytes(data),values,writes


def expected_draw(case):
    """Predict complete packet, OT, context and fixed global-buffer bytes."""
    data,initial,writes = case_fixture(case)
    result = {at:bytearray(value) for at,value in initial.items()}
    state = GteState()
    state.request(True,writes)
    commands=[]
    stats=dict(mode_runs=0,primitive_calls=0,outcomes=[],recursive_entries={},recursive_packets={},
        recursive_roots={},recursive_culls={},recursive_limits={},unsupported_run_returns=0)
    state.draw_stats=stats
    attrs,alias = unsigned(case.get('attributes',0)),case.get('alias',0)
    if attrs & 0x80000000:
        return result,state,commands,'hidden'
    descriptor=(get(data,8)&0x1FFFFFFF)-BUFFER
    vertex_base=get(data,descriptor)&0x1FFFFFFF
    normal_base=get(data,descriptor+8)&0x1FFFFFFF
    context = result[CONTEXT]
    for at,value in ((0,ORDER|alias),(4,case.get('shift',4)),(8,10),
            (0xC,vertex_base|alias),(0x10,normal_base|alias)):
        put(context,at,value)
    for start,slots,count,table_offset in ((TRI,0x88,3,0xA8),(QUAD,0x94,4,0xF0)):
        for index in range(count):
            address = 0x80000000|start+0x18+index*0x18
            put(context,slots+index*4,address)
            put(result[start],table_offset+index*4,address)
    put(result[0x90C18],0,attrs >> 9 & 7)
    for offset,value in enumerate((attrs >> 6 & 1,attrs >> 3 & 3,attrs >> 5 & 1)):
        put(result[0x8E248],offset*4,value)
    material_shift = 9 if (attrs >> 3 & 3) or (attrs & 0x20 and case.get('light_mode',0)) else 16
    put(context,0x2C,material_shift)
    context[0x34:0x37] = bytes((17,34,51))
    specs=packet_specs(case)
    if not specs:
        return result,state,commands,'empty'
    cursor,previous,recursions,termination=0,None,[],None
    for ordinal,spec in enumerate(specs):
        run_start=spec['mode']!=previous
        stats['mode_runs']+=int(run_start)
        if (spec['mode']&0xFD,spec['flags']) not in FORMATS:
            put(context,0x18,((spec['mode']<<8)|spec['flags'])&0xFD07)
            put(context,0x1C,spec['mode']>>1&1)
            stats['unsupported_run_returns']=1
            termination='unsupported_mode_return'
            break
        stats['primitive_calls']+=1
        if hasattr(state,'recursive_stats'):del state.recursive_stats
        view={**result,GPU:memoryview(result[GPU])[cursor:]}
        size,outcome=_draw_packet({**case,**spec,'vertex_base':vertex_base,'normal_base':normal_base},
            data,view,state,commands,run_start,(GPU+cursor)|alias)
        cursor+=size
        stats['outcomes'].append(outcome)
        recursion=getattr(state,'recursive_stats',None)
        if recursion:
            recursions.append(recursion)
            kind=recursion['kind']
            for key,value in (('recursive_entries',recursion['nodes']),('recursive_packets',recursion['packets']),
                    ('recursive_roots',1)):
                if value:stats[key][kind]=stats[key].get(kind,0)+value
            for reason,value in recursion['culled'].items():
                dest=stats['recursive_culls'].setdefault(kind,{})
                dest[reason]=dest.get(reason,0)+value
            limit=str(recursion['limit'])
            stats['recursive_limits'][limit]=stats['recursive_limits'].get(limit,0)+1
        previous=spec['mode']
        if ordinal+1==len(specs) or specs[ordinal+1]['mode']!=previous:
            put(result[OUT],0,(GPU+cursor)|alias)
    if recursions:
        state.recursive_stats=dict(kind=recursions[0]['kind'] if len(recursions)==1 else 'mixed',
            nodes=sum(r['nodes'] for r in recursions),packets=sum(r['packets'] for r in recursions),
            culled={reason:sum(r['culled'].get(reason,0) for r in recursions)
                for reason in ('near','right','left','bottom','top') if any(reason in r['culled'] for r in recursions)},
            limit=recursions[0]['limit'] if len(recursions)==1 else None)
    return result,state,commands,termination or (stats['outcomes'][0] if len(specs)==1 else 'primitive_run')


def _draw_packet(case,data,result,state,commands,run_start,gpu_address):
    """Predict one member while retaining the invocation's state and buffers."""
    context=result[CONTEXT]
    attrs,alias=unsigned(case.get('attributes',0)),case.get('alias',0)
    material_shift=get(context,0x2C)
    def command(word):
        state.execute(word)
        commands.append(word)
    def load_vertex(index,slot):
        at=case['vertex_base']-BUFFER+8*case['indices'][index]
        state.write(1,slot*2,get(data,at))
        state.write(1,slot*2+1,get(data,at+4))
    mode,flags=case['mode'],case['flags']
    count=4 if mode & 8 else 3
    textured,unlit=bool(mode&4),bool(mode&1)
    gouraud=bool(mode&16) or flags==4
    output_mode=(mode & 0xFC) | (0x10 if gouraud else 0) | (attrs >> 6 & 1)
    payload_words=count*(1+textured+gouraud)+(0 if gouraud else 1)
    output_mode |= mode & 2
    if run_start:
        result[GPU][3],result[GPU][7]=payload_words,output_mode
        context[0x14],context[0x15]=payload_words,output_mode
        put(context,0x18,((mode<<8)|flags)&0xFD07)
        put(context,0x1C,mode >> 1 & 1)
    if run_start and textured and not unlit:
        state.write(1,6,get(context,0x34))
    for i,index in enumerate(case['indices']):put(context,0xA4+4*i,(case['vertex_base']+8*index)|alias)
    for i in range(3):load_vertex(i,i)
    put(context,0x78,0)
    command(RTPT)
    result[GPU][3]=context[0x14]
    clip=state.cr[31]&0x40000
    put(context,0x5C,clip)
    if clip:put(context,0x78,1)
    command(NCLIP)
    put(context,0x28,state.dr[24])
    if signed(state.dr[24])<=0:
        return 0,'backface_or_degenerate'
    depth = state.dr[8]
    put(context,0x24,depth)
    if signed(depth)>=4096:
        return 0,'depth_cue_rejected'
    command(AVSZ3)
    put(context,0x20,state.dr[7])
    positions=state.dr[12:15]
    for i,value in enumerate(positions):put(context,0x60+i*4,value)
    bucket=unsigned((ORDER|alias)+((signed(state.dr[7]) >> (case.get('shift',4)&31))<<2))
    require(ORDER <= (bucket&0x1FFFFFFF) < ORDER+4096,'Ordering bucket left its fixture.')
    put(context,0x30,bucket)
    if count==4:
        load_vertex(3,0)
        command(RTPS)
        positions.append(state.dr[14])
        put(context,0x6C,state.dr[14])
    zs=state.dr[16:20] if count==4 else state.dr[17:20]
    table=result[QUAD if count==4 else TRI]
    for i,z in enumerate(zs):put(table,0x18+0x18*i+0x14,z)
    # The original helper's endpoint excludes the final supplied vertex.
    # Preserve that observed loop bound, including its effect on clip flags.
    xs=[signed(v,16) for v in positions[:-1]]
    ys=[signed(v>>16,16) for v in positions[:-1]]
    struct.pack_into('<4h',context,0x70,min(xs),min(ys),max(xs),max(ys))
    if max(xs)-min(xs)>256 or max(ys)-min(ys)>256:put(context,0x78,1)
    colors=case.get('colors',COLORS)
    output_colors=[]
    if not unlit:
        at=case['normal_base']-BUFFER+8*case['normal_index']
        state.write(1,0,get(data,at))
        state.write(1,1,get(data,at+4))
        for i in range(count if gouraud else 1):
            if not textured:state.write(1,6,colors[i])
            command(NCDS)
            output_colors.append(state.dr[22])
    elif gouraud:
        for i in range(3):state.write(1,20+i,colors[i])
        state.write(1,6,colors[2])
        command(DPCT)
        output_colors=state.dr[20:23]
        if count==4:
            state.write(1,6,colors[3])
            command(DPCS)
            output_colors.append(state.dr[22])
    else:
        state.write(1,6,colors[0])
        command(DPCS)
        output_colors=[state.dr[22]]
    cursor=4
    color_offsets,uv_offsets=[],[]
    for index,position in enumerate(positions):
        if index==0 or gouraud:
            color_offsets.append(cursor)
            put(result[GPU],cursor,output_colors[index if gouraud else 0])
            cursor+=4
        put(result[GPU],cursor,position)
        cursor+=4
        if textured:
            uv_offsets.append(cursor)
            put(result[GPU],cursor,case['uv'][index])
            cursor+=4
    result[GPU][7]=output_mode
    if textured:
        clut=struct.unpack_from('<H',result[GPU],0xE)[0]
        struct.pack_into('<H',result[GPU],0xE,(clut+((signed(depth)>>material_shift)<<6))&65535)
    require(cursor==4+payload_words*4,'Predicted GPU packet size differs.')
    if get(context,0x78):
        from tools.tmd_recursive_model import subdivide
        cursor=subdivide(case,result,state,commands,data,positions,color_offsets,uv_offsets,payload_words,gpu_address)
        return cursor,'subdivided' if cursor else 'recursive_culled'
    at=(bucket&0x1FFFFFFF)-ORDER
    put(result[GPU],0,(payload_words<<24)|(get(result[ORDER],at)&0xFFFFFF))
    put(result[ORDER],at,(get(result[ORDER],at)&0xFF000000)|(gpu_address&0xFFFFFF))
    return cursor,'submitted'
