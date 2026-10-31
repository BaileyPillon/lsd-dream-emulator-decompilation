"""Scalar recursive polygon subdivision, without executing original MIPS.

Workspace writes and emitted packet fields follow the original node layout.
GTE arithmetic is shared with the separately native-qualified integer model.
"""
from collections import Counter
import struct

from tools.gte_state_model import require,signed,unsigned
from tools.tmd_renderer_model import (GPU,ORDER,CONTEXT,TRI,QUAD,VERTEX,BUFFER,
    RTPT,get,put)

# Original shader returns and the four recursive call returns. These are
# source-control addresses, not stubbed outputs. The verifier checks their
# original JAL words against the canonical executable before execution.
RETURNS={
    'F3':(0x80019880,(0x8001A80C,0x8001A82C,0x8001A84C,0x8001A86C)),
    'F4':(0x80019BE8,(0x8001AC6C,0x8001AC94,0x8001ACBC,0x8001ACE4)),
    'G3':(0x800199D0,(0x8001B088,0x8001B0A8,0x8001B0C8,0x8001B0E8)),
    'G4':(0x80019D68,(0x8001B5B0,0x8001B5D8,0x8001B600,0x8001B628)),
    'FT3':(0x80019B08,(0x8001B9B8,0x8001B9D8,0x8001B9F8,0x8001BA18)),
    'FT4':(0x80019EC8,(0x8001BEB4,0x8001BEDC,0x8001BF04,0x8001BF2C)),
    'GT3':(0x8001A048,(0x8001C368,0x8001C388,0x8001C3A8,0x8001C3C8)),
    'GT4':(0x8001A208,(0x8001C950,0x8001C978,0x8001C9A0,0x8001C9C8)),
}
FUNCTIONS={
    'F3':(0x8001A564,0x8001A56C,0x8001A884),
    'F4':(0x8001A8D4,0x8001A8DC,0x8001ACFC),
    'G3':(0x8001AD54,0x8001AD5C,0x8001B100),
    'G4':(0x8001B164,0x8001B16C,0x8001B640),
    'FT3':(0x8001B6B4,0x8001B6BC,0x8001BA30),
    'FT4':(0x8001BAB4,0x8001BABC,0x8001BF44),
    'GT3':(0x8001BFD4,0x8001BFDC,0x8001C3E0),
    'GT4':(0x8001C474,0x8001C47C,0x8001C9E0),
}


def subdivide(case,result,state,commands,data,positions,color_offsets,uv_offsets,payload_words):
    count=len(positions)
    textured,gouraud=bool(uv_offsets),len(color_offsets)>1
    kind=('GT' if textured and gouraud else 'G' if gouraud else 'FT' if textured else 'F')+str(count)
    base=TRI if count==3 else QUAD
    arena=result[base]
    packet=result[GPU]
    context=result[CONTEXT]
    width,height=case.get('viewport',(512,480))
    limit=case.get('division_override')
    limit=(case.get('attributes',0)>>9&7) if limit is None else limit
    require(type(limit) is int and 1<=limit<=5,'Use a bounded original subdivision limit from 1 through 5.')
    require(0<width<=32767 and 0<height<=32767,'Use bounded positive viewport dimensions.')
    put(arena,0,limit)
    put(arena,4,width)
    put(arena,8,height)
    if textured:
        struct.pack_into('<HH',arena,0xC,struct.unpack_from('<H',packet,uv_offsets[0]+2)[0],
            struct.unpack_from('<H',packet,uv_offsets[1]+2)[0])
    put(arena,0x10,get(packet,4))
    put(arena,0x14,get(context,0x30))
    nodes=[0x18+0x18*i for i in range(count)]
    for i,node in enumerate(nodes):
        arena[node:node+8]=data[VERTEX-BUFFER+8*i:VERTEX-BUFFER+8*i+8]
        put(arena,node+0x10,positions[i])
        if gouraud:
            put(arena,node+0xC,get(packet,color_offsets[i]))
        if textured:
            struct.pack_into('<H',arena,node+8,struct.unpack_from('<H',packet,uv_offsets[i])[0])
            meta_index=(2 if not gouraud or count==3 else 2 if i<2 else 3)
            meta=struct.unpack_from('<H',packet,uv_offsets[meta_index]+2)[0]
            struct.pack_into('<H',arena,node+0xA,meta)
        elif gouraud:
            struct.pack_into('<H',arena,node+0xA,packet[color_offsets[max(1,i)]+3])
    cursor=0
    stats=Counter(nodes=0,packets=0)
    culled=Counter()
    def node_world(node):return struct.unpack_from('<3h',arena,node)
    def address(offset):return 0x80000000|base+offset
    def project(group):
        for slot,node in enumerate(group):
            state.write(1,2*slot,get(arena,node))
            state.write(1,2*slot+1,get(arena,node+4))
        state.execute(RTPT)
        commands.append(RTPT)
    def screen_store(group,with_z):
        for i,node in enumerate(group):
            put(arena,node+0x10,state.dr[12+i])
            if with_z:put(arena,node+0x14,state.dr[17+i])
    def emit(group):
        nonlocal cursor
        size=4+payload_words*4
        require(cursor+size<=len(packet),'Recursive GPU packet arena exhausted.')
        if gouraud:arena[group[0]+0xF]=arena[0x13]
        at=cursor+4
        for i,node in enumerate(group):
            if i==0 or gouraud:
                put(packet,at,get(arena,node+0xC) if gouraud else get(arena,0x10))
                at+=4
            put(packet,at,get(arena,node+0x10))
            at+=4
            if textured:
                uv=struct.unpack_from('<H',arena,node+8)[0]
                if i<2:uv|=struct.unpack_from('<H',arena,0xC+2*i)[0]<<16
                put(packet,at,uv)
                at+=4
        bucket=(get(arena,0x14)&0x1FFFFFFF)-ORDER
        require(0<=bucket<len(result[ORDER])-3,'Recursive OT pointer left its arena.')
        put(packet,cursor,get(result[ORDER],bucket)|(payload_words<<24))
        put(result[ORDER],bucket,(GPU+cursor)&0xFFFFFF)
        cursor+=size
        stats['packets']+=1
    def recurse(group,frame,level,return_address):
        stats['nodes']+=1
        z_limit=unsigned(signed(state.control()[26])>>1)
        if all(get(arena,n+0x14)<z_limit for n in group):
            culled['near']+=1
            return
        xs=[signed(get(arena,n+0x10),16) for n in group]
        ys=[signed(get(arena,n+0x10)>>16,16) for n in group]
        cx,cy=signed(state.cr[24])>>16,signed(state.cr[25])>>16
        for label,condition in (('right',all(x>cx+width//2 for x in xs)),
                ('left',all(x<cx-width//2 for x in xs)),
                ('bottom',all(y>cy+height//2 for y in ys)),
                ('top',all(y<cy-height//2 for y in ys))):
            if condition:
                culled[label]+=1
                return
        new=[frame+0x18*i for i in range(3 if count==3 else 5)]
        edges=((0,1),(1,2),(2,0)) if count==3 else ((0,1),(0,2),(1,3),(2,3))
        for node,(a,b) in zip(new,edges):
            values=tuple((x+y)//2 for x,y in zip(node_world(group[a]),node_world(group[b])))
            struct.pack_into('<3h',arena,node,*values)
        if count==4:
            if kind=='F4':
                values=tuple((x+y)//2 for x,y in zip(node_world(new[0]),node_world(new[3])))
            else:values=tuple(sum(node_world(n)[axis] for n in group)//4 for axis in range(3))
            struct.pack_into('<3h',arena,new[4],*values)
        fields=([8,9] if textured else [])+([0xC,0xD,0xE] if gouraud else [])
        for field in fields:
            for node,(a,b) in zip(new,edges):arena[node+field]=(arena[group[a]+field]+arena[group[b]+field])//2
            if count==4:arena[new[4]+field]=sum(arena[n+field] for n in group)//4
        if count==3:
            project(new)
            screen_store(new,level+1<limit)
            children=((group[0],new[0],new[2]),(group[1],new[1],new[0]),
                (group[2],new[2],new[1]),(new[0],new[1],new[2]))
            leaves=(children[1],children[3],children[0],children[2])
            pointer_offset,stride,save_offset=0x48,0x58,0x54
        else:
            first=new[:2] if kind=='F4' else [new[0],new[1],new[4]]
            second=[new[2],new[3],new[4]] if kind=='F4' else [new[2],new[3]]
            project(first)
            screen_store(first,True)
            project(second)
            screen_store(second,kind=='GT4' or level+1<limit)
            children=((group[0],new[0],new[1],new[4]),(group[1],new[2],new[0],new[4]),
                (group[2],new[1],new[3],new[4]),(group[3],new[3],new[2],new[4]))
            leaves=children
            pointer_offset,stride,save_offset=0x78,0x8C,0x88
        if level+1==limit:
            for child in leaves:emit(child)
            return
        next_frame=frame+stride
        require(next_frame+save_offset+4<=len(arena),'Recursive workspace arena exhausted.')
        put(arena,next_frame+save_offset,return_address)
        for child,child_return in zip(children,RETURNS[kind][1]):
            for i,node in enumerate(child):put(arena,next_frame+pointer_offset+4*i,address(node))
            recurse(child,next_frame,level+1,child_return)
    recurse(nodes,0x60 if count==3 else 0x78,0,RETURNS[kind][0])
    state.recursive_stats=dict(kind=kind,nodes=stats['nodes'],packets=stats['packets'],culled=dict(culled),limit=limit)
    return cursor
