"""Decode the triangle/quad vertex references consumed by LSD's collision reader.

Lengths are derived from mode-controlled field groups, not the packet's input
length byte. The original SDK changes the first header halfword during linking.
Rendering, lighting and texture interpretation require separate verification.
"""
from collections import Counter
from dataclasses import dataclass
import hashlib
import struct

from tools.disc_files import FILE_LIMIT, require
from tools.inventory_animations import lbd_info, mom_info


@dataclass(frozen=True)
class PacketLayout:
    bytes: int
    vertices: tuple
    normals: tuple
    uv_records: int
    color_records: int


def packet_layout(mode, flags):
    require(type(mode) is int and type(flags) is int and 0x20 <= mode <= 0x3f
            and 0 <= flags <= 255, 'Unsupported collision primitive mode or flags.')
    count = 4 if mode & 8 else 3
    textured, gouraud, unlit = bool(mode & 4), bool(mode & 16), bool(mode & 1)
    uv = count if textured else 0
    colors = ((count if gouraud else 1) if unlit else 0) if textured else (
        count if (gouraud and unlit) or (not unlit and flags & 4) else 1)
    prefix = 4 + 4 * (uv + colors)
    if unlit:
        normals = ()
        vertices = tuple(prefix + 2 * index for index in range(count))
    elif gouraud:
        normals = tuple(prefix + 4 * index for index in range(count))
        vertices = tuple(offset + 2 for offset in normals)
    else:
        normals = (prefix,)
        vertices = tuple(prefix + 2 + 2 * index for index in range(count))
    size = (prefix + 2 * (len(normals) + count) + 3) & ~3
    return PacketLayout(size, vertices, normals, uv, colors)


@dataclass(frozen=True)
class Geometry:
    index: int
    descriptor_offset: int
    vertices_offset: int
    vertex_count: int
    normals_offset: int
    normal_count: int
    primitives_offset: int
    primitive_count: int
    scale_exponent: int
    limit: int


@dataclass(frozen=True)
class Packet:
    offset: int
    bytes: int
    mode: int
    flags: int
    header_words: tuple
    vertex_indices: tuple
    points: tuple


def _span(offset, count, stride, lower, limit, label):
    require(offset >= lower and offset % 4 == 0 and count >= 0
            and offset <= limit and count * stride <= limit - offset,
            label + ' exceeds its bounded source container.')


def geometries(data, tmd=0, limit=None):
    limit = len(data) if limit is None else limit
    require(0 < len(data) <= FILE_LIMIT and 0 <= tmd <= limit <= len(data)
            and tmd % 4 == 0 and tmd + 12 <= limit, 'Unbounded or truncated TMD header.')
    identifier, flags, count = struct.unpack_from('<III', data, tmd)
    require(identifier == 0x41 and flags == 0, 'Use a fresh relative TMD, before SDK mapping.')
    table = tmd + 12
    require(count <= (limit - table) // 28, 'TMD object table exceeds its container.')
    table_end = table + count * 28
    result = []
    for index in range(count):
        at = table + index * 28
        vertex, vertices, normal, normals, primitive, primitives = struct.unpack_from('<6I', data, at)
        offsets = table + vertex, table + normal, table + primitive
        for offset, number, stride, label in ((offsets[0], vertices, 8, 'Vertices'),
                (offsets[1], normals, 8, 'Normals'), (offsets[2], primitives, 4, 'Primitive headers')):
            _span(offset, number, stride, table_end if number else table, limit, label)
        result.append(Geometry(index, at, offsets[0], vertices, offsets[1], normals,
            offsets[2], primitives, struct.unpack_from('<i', data, at + 24)[0], limit))
    return tuple(result)


def packets(data, geometry):
    cursor = geometry.primitives_offset
    for ordinal in range(geometry.primitive_count):
        require(cursor + 4 <= geometry.limit, 'Truncated primitive header.')
        first, second, flags, mode = data[cursor:cursor + 4]
        layout = packet_layout(mode, flags)
        require(cursor + layout.bytes <= geometry.limit, 'Truncated primitive payload.')
        indices = tuple(struct.unpack_from('<H', data, cursor + offset)[0] for offset in layout.vertices)
        require(all(index < geometry.vertex_count for index in indices),
                'Primitive references a vertex outside its descriptor.')
        points = tuple(struct.unpack_from('<3h', data, geometry.vertices_offset + index * 8) for index in indices)
        yield Packet(cursor, layout.bytes, mode, flags, (first, second), indices, points)
        cursor += layout.bytes


def model_ranges(data, suffix):
    require(0 < len(data) <= FILE_LIMIT, 'Model file exceeds its byte bound.')
    suffix = suffix.upper()
    if suffix == '.TMD':
        return (dict(kind='TMD', tmd=0, limit=len(data), model_offset=0, references=1),)
    if suffix == '.MOM':
        info = mom_info(data, 0)
        return (dict(kind='MOM', tmd=info['tmd_offset'], limit=info['bytes'], model_offset=0, references=1),)
    require(suffix == '.LBD', 'Expected an LBD, MOM or TMD file.')
    info = lbd_info(data)
    library = info['MML']
    result = [dict(kind='LBD', tmd=info['tmd_offset'],
        limit=library['offset'] if library else len(data), model_offset=0, references=1)]
    grouped = Counter(model['offset'] for model in library['models']) if library else {}
    for start, references in sorted(grouped.items()):
        size = struct.unpack_from('<I', data, start + 4)[0]
        result.append(dict(kind='MML-MOM', tmd=start + struct.unpack_from('<I', data, start + 8)[0],
            limit=start + size, model_offset=start, references=references))
    return tuple(result)


def summarize(data, suffix):
    rows = []
    for model in model_ranges(data, suffix):
        counts, modes, flags, scales = Counter(), Counter(), Counter(), Counter()
        vertices_hash, packets_hash = hashlib.sha256(), hashlib.sha256()
        for geometry in geometries(data, model['tmd'], model['limit']):
            counts.update(objects=1, vertices=geometry.vertex_count, normals=geometry.normal_count)
            scales[str(geometry.scale_exponent)] += 1
            vertices_hash.update(data[geometry.vertices_offset:geometry.vertices_offset + geometry.vertex_count * 8])
            for packet in packets(data, geometry):
                counts.update(packets=1, triangles=len(packet.points) == 3, quads=len(packet.points) == 4,
                              vertex_references=len(packet.points))
                modes[f'0x{packet.mode:02x}'] += 1
                flags[f'0x{packet.flags:02x}'] += 1
                packets_hash.update(data[packet.offset:packet.offset + packet.bytes])
        rows.append(dict(**model, counts=dict(counts), modes=dict(sorted(modes.items())),
            flags=dict(sorted(flags.items())), scale_exponents=dict(sorted(scales.items())),
            vertex_record_stream_sha256=vertices_hash.hexdigest(),
            primitive_record_stream_sha256=packets_hash.hexdigest()))
    return dict(models=rows, input_bytes=len(data), input_sha256=hashlib.sha256(data).hexdigest(),
        validation='bounded_triangle_quad_vertex_references', whole_feature_groups_accepted=0,
        rendered_output_verified=False, normal_index_semantics_verified=False,
        texture_palette_and_lighting_verified=False, source_bytes_modified=False)
