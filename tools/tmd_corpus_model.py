"""Exact original TMD fixture bytes and explicitly supplied inspection cameras.

No original instructions execute here. Mapping/linking predictions use the
separately qualified scalar SDK model. Raw vertex/normal/primitive pools and
indices are retained, including formats on which this drawer returns early.
"""
import struct

from tools.gte_state_model import require,unsigned
from tools.tmd_packets import geometries,packets,packet_layout
from tools.tmd_sdk_model import map_tmd,link_tmd
from tools.tmd_renderer_model import BUFFER,BUFFER_BYTES,MODEL,OBJECT,OT,ORDER,COORD,SOURCE_FORMATS


def geometry_for(case):
    raw=case['raw_tmd']
    require(type(raw) is bytes and 12<=len(raw)<=BUFFER_BYTES-(MODEL-BUFFER),
        'Use a bounded original relative TMD payload.')
    rows=geometries(raw)
    index=case['geometry_index']
    require(type(index) is int and 0<=index<len(rows),'Original descriptor index exceeds its TMD.')
    return rows[index]


def raw_specs(case):
    raw=case['raw_tmd']
    geometry=geometry_for(case)
    result=[]
    for packet in packets(raw,geometry):
        require((packet.mode&0xFD,packet.flags) in SOURCE_FORMATS,'Unreviewed original drawer source format.')
        if result and packet.mode==result[-1]['mode']:
            require(packet.flags==result[-1]['flags'],'Same-mode flag mixtures need a separate original-run model.')
        layout=packet_layout(packet.mode,packet.flags)
        normals=tuple(struct.unpack_from('<H',raw,packet.offset+at)[0] for at in layout.normals)
        require(all(index<geometry.normal_count for index in normals),'Original normal index exceeds its pool.')
        uv=tuple(struct.unpack_from('<I',raw,packet.offset+4+4*i)[0] for i in range(layout.uv_records))
        colors=tuple(struct.unpack_from('<I',raw,packet.offset+4+4*layout.uv_records+4*i)[0]
            for i in range(layout.color_records))
        result.append(dict(mode=packet.mode,flags=packet.flags,indices=packet.vertex_indices,
            normal_index=normals[0] if normals else 0,colors=colors,uv=uv))
    return result


def raw_fixture(case):
    geometry_for(case)
    alias=case.get('alias',0)
    require(alias in (0,0x80000000),'Use a declared original-model address alias.')
    data=bytearray(BUFFER_BYTES)
    struct.pack_into('<III',data,OBJECT-BUFFER,unsigned(case.get('attributes',0)),COORD|alias,0)
    struct.pack_into('<I',data,OT-BUFFER+4,ORDER|alias)
    mapped=map_tmd(case['raw_tmd'],MODEL|alias)
    plan=link_tmd(mapped,MODEL|alias,case['geometry_index'],data[OBJECT-BUFFER:OBJECT-BUFFER+24])
    data[OBJECT-BUFFER:OBJECT-BUFFER+24]=plan.target
    data[MODEL-BUFFER:MODEL-BUFFER+len(plan.model)]=plan.model
    return bytes(data)


def camera_for(raw,geometry,reverse=False):
    """Fit the original points using an explicit scaled oblique rotation.

    This is an analysis camera, not a recovered in-game camera or model scale.
    Opposite views exercise both sides of ordinary faces without changing data.
    """
    require(geometry.vertex_count>0,'A fitted camera needs at least one vertex.')
    points=[struct.unpack_from('<3h',raw,geometry.vertices_offset+8*i) for i in range(geometry.vertex_count)]
    base=((2896,0,-2896),(1672,3344,1672),(2364,-2364,2364))
    if reverse:base=(tuple(-v for v in base[0]),base[1],tuple(-v for v in base[2]))
    rotated=[tuple(sum(a*b for a,b in zip(row,p))//4096 for row in base) for p in points]
    span=max(max(p[i] for p in rotated)-min(p[i] for p in rotated) for i in range(3))
    factor=max(1,min(32767,1024*4096//max(1,span)))
    rotation=tuple(tuple(value*factor//4096 for value in row) for row in base)
    require(all(-32768<=v<=32767 for row in rotation for v in row),'Fitted rotation exceeds signed GTE fields.')
    scaled=[tuple(sum(a*b for a,b in zip(row,p))//4096 for row in rotation) for p in points]
    center=tuple((min(p[i] for p in scaled)+max(p[i] for p in scaled))//2 for i in range(3))
    return dict(matrix=tuple(value for row in rotation for value in row),
        translation=(-center[0],-center[1],4096-center[2]),h=512)
