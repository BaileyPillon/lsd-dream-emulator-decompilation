"""Execute bounded original collision paths with checked native GTE commands.

Uses local canonical game bytes, Unicorn and the pinned Nymashock bridge.
No original function output is stubbed. COP2 transfers remain an explicit
adapter; this does not verify the complete PS1 CPU, scene timing or gameplay.
"""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import verify_native_ai as native
from tools import verify_render_gte as gte

BUFFER, BUFFER_BYTES = 0x130000, 0x1800
OP, SQR = 0x4B70000C, 0x4AA00428
SQRT_TABLE, SQRT_TABLE_BYTES = 0x8006BEF0, 384
MODEL, GEOMETRY, VERTICES, PRIMITIVES = 0x100, 0x200, 0x300, 0x500
QUERY_MODEL, QUERY_GEOMETRY, QUERY_VERTICES = 0x700, 0x780, 0x800
OBJECT, CLOUD, CONTACT, MASK_OUT, NEAREST, HEIGHT = 0x900, 0xA00, 0xC00, 0xC20, 0xC40, 0xC50
VECTOR_A, VECTOR_B, VECTOR_OUT = 0x1000, 0x1020, 0x1040


def signed(value, bits=32):
    value &= (1 << bits) - 1
    return value - (1 << bits) if value >> (bits - 1) else value


def divide(numerator, denominator):
    if denominator == 0 or (numerator == -2147483648 and denominator == -1):
        raise ValueError('Original signed division would trap.')
    quotient = abs(numerator) // abs(denominator)
    return -quotient if (numerator < 0) != (denominator < 0) else quotient


def abs32(value):
    return signed(-value) if value < 0 else value


def leading_bits(value):
    value = native.u32(value)
    return 32 - (value ^ (0xFFFFFFFF if value & 0x80000000 else 0)).bit_length()


def command_model(cr, ir, command):
    if len(cr) != 5 or len(ir) != 3 or command not in (OP, SQR):
        raise ValueError('Only reviewed OP and SQR inputs are supported.')
    ir = [signed(v, 16) for v in ir]
    if command == OP:
        x, y, z = (signed(cr[i], 16) for i in (0, 2, 4))
        a, b, c = ir
        mac = [signed(y*c-z*b), signed(z*a-x*c), signed(x*b-y*a)]
    else:
        mac = [v*v for v in ir]
    flags = sum(1 << (24-i) for i, v in enumerate(mac) if not -32768 <= v <= 32767)
    if flags & 0x7F87E000:
        flags |= 1 << 31
    return dict(mac=mac, ir=[max(-32768, min(32767, v)) for v in mac], flags=flags,
                command_cycles_minus_one=5 if command == OP else 4)


def sqrt_model(value, read_halfword):
    """Retain the SDK's signed shifts and its negative-input table indexing."""
    value = signed(value)
    leading = leading_bits(value)
    if leading == 32:
        return 0
    even = leading & ~1
    exponent = (31-even) >> 1
    normalized = signed(value << (even-24)) if even >= 24 else value >> (24-even)
    coefficient = read_halfword(SQRT_TABLE + (normalized-64)*2)
    return native.u32(coefficient << exponent) >> 12


def fraction_fixed(numerator, denominator):
    quotient = divide(numerator, denominator)
    remainder = signed(numerator - quotient*denominator)
    fraction = signed(abs32(remainder) << 16)
    whole = native.u32(quotient << 16) if quotient else native.u32(numerator*denominator) & 0x80000000
    return signed(whole | native.u32(divide(fraction, abs32(denominator))))


def point_bounds(points):
    return tuple(min(p[i] for p in points) for i in range(3)), tuple(max(p[i] for p in points) for i in range(3))


def primitive_model(polygons, start, end, read_halfword):
    """Plane intersection followed by expanded AABB, not point-in-triangle."""
    delta = tuple(signed(b-a, 16) for a, b in zip(start, end))
    nearest, contact, height, result = 2147483647, None, None, 0
    for points in polygons:
        edge1 = tuple(signed(b-a, 16) for a, b in zip(points[0], points[1]))
        edge2 = tuple(signed(b-a, 16) for a, b in zip(points[0], points[2]))
        cr = [native.u32(edge1[0]), 0, native.u32(edge1[1]), 0, native.u32(edge1[2])]
        normal = [divide(v, 4096) for v in command_model(cr, edge2, OP)['mac']]
        plane_d = signed(-signed(sum(p*n for p, n in zip(points[0], normal))))
        dot = signed(sum(d*n for d, n in zip(delta, normal)))
        if abs32(dot) < 1:
            continue
        numerator = signed(-signed(sum(p*n for p, n in zip(start, normal)) + plane_d))
        denominator = dot
        if abs32(dot) >= 4096:
            numerator, denominator = divide(numerator, 4096), divide(denominator, 4096)
        ratio = fraction_fixed(numerator, denominator)
        if ratio < 0:
            continue
        offset = [signed(d*ratio) >> 16 for d in delta]
        intersection = [signed(a+b) for a, b in zip(start, offset)]
        offset = [signed(b-a) for a, b in zip(start, intersection)]
        squared_delta = command_model([0]*5, delta, SQR)['mac']
        squared_offset = command_model([0]*5, offset, SQR)['mac']
        length = sqrt_model(signed(sum(squared_delta)), read_halfword)
        distance = sqrt_model(signed(sum(squared_offset)), read_halfword)
        if length < distance:
            continue
        hit = tuple(signed(v, 16) for v in intersection)
        low, high = point_bounds(points)
        if all(a-24 <= p <= b+24 for a, p, b in zip(low, hit, high)):
            result = 1
            if distance < nearest:
                nearest, contact, height = distance, hit, hit[1]-low[1]
    return result, nearest, contact, height


def point_flags(box, point):
    low, high = box
    flags = 0
    for index, below, above in ((0, 4, 8), (1, 1, 2), (2, 16, 32)):
        flags |= above if high[index] < point[index] else below if point[index] < low[index] else 0
    return flags


def clip_segment(box, a, b):
    """Original recursive integer midpoint search with NULL output midpoint."""
    pending = [(tuple(a), tuple(b))]
    while pending:
        a, b = pending.pop()
        fa, fb = point_flags(box, a), point_flags(box, b)
        if not fa:
            return 1 if not fb else 2
        if not fb:
            return 3
        if fa & fb:
            continue
        half = tuple((x+y) >> 1 for x, y in zip(a, b))
        if half in (a, b):
            continue
        pending.extend(((half, b), (a, half)))
    return 0


def cube_points(bounds):
    (x0, y0, z0), (x1, y1, z1) = bounds
    return [(x0,y0,z0), (x0,y1,z0), (x1,y1,z0), (x1,y0,z0),
            (x0,y0,z1), (x0,y1,z1), (x1,y1,z1), (x1,y0,z1)]


def transform_cube(points, flip, face, amount):
    points = list(points)
    if flip:
        points = [points[i] for i in (4,5,1,0,7,6,2,3)]
    axis = 0 if flip else 2
    for i in range(4*bool(face), 4*bool(face)+4):
        point = list(points[i])
        point[axis] = signed(point[axis]+amount, 16)
        points[i] = tuple(point)
    return points


def transform_model(polygons, cloud, count, global_mode, read_halfword, initial_contact):
    bounds = point_bounds([p for polygon in polygons for p in polygon])
    mids = [tuple((a+b) >> 1 for a,b in zip(cloud[0][i], cloud[0][i+2])) for i in (0,4)]
    contact, mask, out = tuple(initial_contact), 0, 0
    def check(a, b):
        nonlocal contact
        if not clip_segment(bounds, a, b):
            return 0, None
        hit, nearest, point, height = primitive_model(polygons, a, b, read_halfword)
        if point is not None:
            contact = point
        return hit, height
    for index in range(max(count, 0)):
        hit, height = check(*mids)
        if hit and (not global_mode or height > 512):
            mask |= 1 << (index & 31)
    if mask:
        return 1, native.u32(mask), 1, contact
    for index in range(max(count, 0)):
        for path, points in enumerate(cloud):
            for j in (1,2):
                hit, height = check(points[j], points[j+4])
                if hit and height > 512:
                    mask |= 1 << (index & 31)
                    out |= 1 << (path & 31)
    return int(out != 0), native.u32(mask), native.u32(out), contact


class CollisionBridge(gte.NativeGteBridge):
    def __init__(self, *args):
        self.lz_count = 0
        super().__init__(*args)

    def leading(self, value):
        self.id += 1
        request = dict(id=self.id, command=0, lzcs=native.u32(value))
        line = json.dumps(request, separators=(',', ':')) + '\n'
        self.output.write('GTE_REQUEST ' + line)
        self.process.stdin.write(line)
        self.process.stdin.flush()
        observed = self.read('GTE_RESULT ')
        expected = dict(id=self.id, lzcs=native.u32(value), lzcr=leading_bits(value))
        if observed != expected:
            raise ValueError('Native leading-sign-bit result differs: ' + repr((request, observed, expected)))
        self.lz_count += 1
        return observed['lzcr']


class CollisionCop2:
    def __init__(self, bridge, *, backend=None):
        self.bridge, self.counts = bridge, Counter()
        self.backend = native if backend is None else backend
        self.reset()

    def reset(self, cr=(0,0,0,0,0)):
        self.cr = [native.u32(v) & (0xFFFF if i == 4 else 0xFFFFFFFF) for i,v in enumerate(cr)]
        self.ir, self.mac, self.lzcs, self.lzcr = [0]*3, [0]*3, 0, 32
        self.flags = 0

    def step(self, cpu, address):
        word = int.from_bytes(cpu.mem_read(address, 4), 'little')
        opcode, rt = word >> 26, (word >> 16) & 31
        get = lambda number: cpu.reg_read(getattr(self.backend.reg, 'UC_MIPS_REG_'+str(number)))
        put = lambda number, value: cpu.reg_write(getattr(self.backend.reg, 'UC_MIPS_REG_'+str(number)), native.u32(value))
        if opcode in (0x32, 0x3A):
            pointer = (get((word >> 21) & 31)+signed(word,16)) & native.MASK
            if opcode == 0x32 and rt in (9,10,11):
                self.ir[rt-9] = signed(int.from_bytes(cpu.mem_read(pointer,4),'little'),16)
                self.counts['lwc2'] += 1
            elif opcode == 0x3A and rt in (25,26,27):
                cpu.mem_write(pointer, struct.pack('<I',native.u32(self.mac[rt-25])))
                self.counts['swc2'] += 1
            else:
                raise ValueError('Unreviewed COP2 memory transfer.')
        elif opcode == 0x12:
            rs, rd = (word >> 21) & 31, (word >> 11) & 31
            if word in (OP,SQR):
                observed = self.bridge.execute(self.cr, self.ir, word)
                expected = command_model(self.cr,self.ir,word)
                if observed != expected:
                    raise ValueError('Native collision GTE command differs: ' + repr((self.cr,self.ir,word,observed,expected)))
                self.ir, self.mac = observed['ir'][:], observed['mac'][:]
                self.flags = observed['flags']
                self.counts['command'] += 1
            elif word & 0x7FF:
                raise ValueError('Unreviewed COP2 encoding.')
            elif rs == 2 and rd in (0,2,4):
                put(rt, signed(self.cr[rd],16) if rd == 4 else self.cr[rd])
                self.counts['cfc2'] += 1
            elif rs == 6 and rd in (0,2,4):
                self.cr[rd] = get(rt) & (0xFFFF if rd == 4 else 0xFFFFFFFF)
                self.counts['ctc2'] += 1
            elif rs == 4 and rd == 30:
                self.lzcs = get(rt)
                self.lzcr = self.bridge.leading(self.lzcs)
                self.counts['mtc2_lzcs'] += 1
            elif rs == 0 and rd == 31:
                put(rt,self.lzcr)
                self.counts['mfc2_lzcr'] += 1
            else:
                raise ValueError('Unreviewed COP2 register transfer.')
        else:
            return False
        cpu.reg_write(self.backend.reg.UC_MIPS_REG_PC, address+4)
        return True


class CollisionMachine(native.Machine):
    def __init__(self, bridge, functions, patches=None):
        self.adapter, self.entries, self.first_cursors = CollisionCop2(bridge), Counter(), Counter()
        self.ranges = [(int(f['address'],16)&native.MASK, f['bytes']) for f in functions]
        super().__init__(start=int(functions[0]['address'],16)&native.MASK, native_functions=functions)
        for address, data in (patches or {}).items():
            self.cpu.mem_write(address&native.MASK,data)

    def hook(self, cpu, address, size, unused):
        address &= native.MASK
        name = self.native_entries.get(address)
        if name:
            self.entries[name] += 1
            if name == 'func_80020050':
                pointer = int.from_bytes(cpu.mem_read(cpu.reg_read(native.reg.UC_MIPS_REG_SP)+16,4),'little')
                if int.from_bytes(cpu.mem_read(pointer&native.MASK,4),'little') == 0:
                    self.first_cursors[cpu.reg_read(native.reg.UC_MIPS_REG_A1)] += 1
        if not any(start <= address < start+length for start,length in self.ranges):
            raise ValueError('Collision execution escaped reviewed original function ranges: ' + hex(address))
        self.adapter.step(cpu,address)

    def invoke(self, name, args, saved_seed=0xAD000000):
        cpu, reg = self.cpu, native.reg
        cpu.mem_write(native.STACK-0x1000,bytes([0xC9])*0x1040)
        saved = [native.u32(saved_seed+i*0x10203) for i in range(len(native.SAVED))]
        for register,value in zip(native.SAVED,saved):
            cpu.reg_write(register,value)
        for index in range(32):
            if index not in (0,28,29,30,31) and index not in range(16,24):
                cpu.reg_write(getattr(reg,'UC_MIPS_REG_'+str(index)),0xBA123456)
        for register,value in ((reg.UC_MIPS_REG_SP,native.STACK), (reg.UC_MIPS_REG_GP,0x8008A808),
                               (reg.UC_MIPS_REG_RA,native.END)):
            cpu.reg_write(register,value)
        for index,value in enumerate(args):
            if index < 4:
                cpu.reg_write(getattr(reg,'UC_MIPS_REG_A'+str(index)),native.u32(value))
            else:
                cpu.mem_write(native.STACK+index*4,struct.pack('<I',native.u32(value)))
        cpu.emu_start(native.h.symbols[name]&native.MASK,native.END,count=250000)
        if (cpu.reg_read(reg.UC_MIPS_REG_PC) != native.END or cpu.reg_read(reg.UC_MIPS_REG_SP) != native.STACK or
                [cpu.reg_read(r) for r in native.SAVED] != saved or bytes(cpu.mem_read(native.STACK-0x1000,0x400)) != bytes([0xC9])*0x400):
            raise ValueError('Collision function did not return with preserved ABI and stack guard.')
        return cpu.reg_read(reg.UC_MIPS_REG_V0)


def initial_buffer():
    return bytearray((index*37+13)&255 for index in range(BUFFER_BYTES))


def pointer(offset, segment=0):
    return (BUFFER+offset)|segment


def pack_point(data, offset, point):
    struct.pack_into('<3h',data,offset,*(signed(v,16) for v in point))


def sdk_cases():
    edges = (-32768,-1,0,32767)
    vectors = list(itertools.product(edges,repeat=3))
    for a,b in itertools.product(vectors,repeat=2):
        yield 'OuterProduct10', a,b,VECTOR_OUT,0
    wide = (-2147483648,-65537,-32769,-32768,-1,0,1,32767,32768,65535,65536,2147483647)
    for a in itertools.product(wide,repeat=3):
        yield 'Square0',a,(0,0,0),VECTOR_OUT,0
    for name in ('OuterProduct10','Square0'):
        for offset,segment in itertools.product((VECTOR_A,VECTOR_A+4,VECTOR_B,VECTOR_B-4),(0,0x80000000,0xA0000000)):
            yield name,(65537,-32769,123),(7,65535,-2147483648),offset,segment


def sqrt_cases():
    values = {0,0xFFFFFFFF,0x80000000,0x7FFFFFFF}
    for shift in range(24):
        for index in range(64,256):
            value = index << shift
            if value <= 0x7FFFFFFF:
                values.update((value, value^0xFFFFFFFF))
    for power in range(31):
        for adjustment in (-1,0,1):
            value = (1 << power)+adjustment
            values.update((value,value^0xFFFFFFFF))
    return sorted(values)


# Primitive payload layouts actually selected by the original decoder.
LAYOUTS = {
    (0x20,0):(16,(10,12,14)), (0x20,4):(24,(18,20,22)),
    (0x21,0):(16,(8,10,12)), (0x24,0):(24,(18,20,22)),
    (0x25,0):(28,(20,22,24)), (0x28,0):(20,(10,12,14,16)),
    (0x28,4):(32,(22,24,26,28)), (0x29,0):(16,(8,10,12,14)),
    (0x2C,0):(32,(22,24,26,28)), (0x2D,0):(32,(24,26,28,30)),
    (0x30,0):(20,(10,14,18)), (0x30,4):(28,(18,22,26)),
    (0x31,0):(24,(16,18,20)), (0x34,0):(28,(18,22,26)),
    (0x35,0):(36,(28,30,32)), (0x38,0):(24,(10,14,18,22)),
    (0x38,4):(36,(22,26,30,34)), (0x39,0):(28,(20,22,24,26)),
    (0x3C,0):(36,(22,26,30,34)), (0x3D,0):(44,(36,38,40,42)),
}
LAYOUTS.update({(mode+2,flag):layout for (mode,flag),layout in list(LAYOUTS.items())})


def model_fixture(polygons, mode=0x21, flag=0, start=(0,0,-1000), end=(0,0,1000), height_output=True, segment=0):
    data = initial_buffer()
    vertices = [p for polygon in polygons for p in polygon]
    struct.pack_into('<I',data,MODEL+16,pointer(GEOMETRY,segment))
    struct.pack_into('<6I',data,GEOMETRY,pointer(VERTICES,segment),len(vertices),0,0,pointer(PRIMITIVES,segment),len(polygons))
    for index,point in enumerate(vertices):
        pack_point(data,VERTICES+index*8,point)
    cursor, index = PRIMITIVES, 0
    for polygon in polygons:
        length, offsets = LAYOUTS[(mode,flag)]
        if len(polygon) != len(offsets):
            raise ValueError('Primitive vertex count differs from its payload layout.')
        data[cursor+2:cursor+4] = bytes((flag,mode))
        for offset in offsets:
            struct.pack_into('<H',data,cursor+offset,index)
            index += 1
        cursor += length
    pack_point(data,VECTOR_A,start)
    pack_point(data,VECTOR_B,end)
    args = (pointer(MODEL,segment),pointer(NEAREST,segment),pointer(CONTACT,segment),
            pointer(HEIGHT,segment) if height_output else 0,pointer(VECTOR_A,segment),pointer(VECTOR_B,segment))
    return data,args


def collision_cases():
    tri = ((-1024,-1024,0),(1024,-1024,0),(-1024,1024,0))
    quad = tri+((1024,1024,0),)
    for (mode,flag),(length,offsets) in LAYOUTS.items():
        polygon = tri if len(offsets) == 3 else quad
        for x,y,z0,z1 in itertools.product((-1049,-1048,-1024,0,1024,1048,1049),(-1024,-512,0,512,1024),(-1000,0,1000),(-1000,0,1000)):
            yield dict(polygons=(polygon,),mode=mode,flag=flag,start=(x,y,z0),end=(x,y,z1))
    for polygons,start,end,height_output,segment in itertools.product(
            ((),(tri,tri),(tuple((x,y,z+400) for x,y,z in tri),tri),(tri,tuple(reversed(tri)))),
            ((0,0,-1200),(0,0,1200)),((0,0,1200),(0,0,-1200)),(False,True),(0,0x80000000,0xA0000000)):
        yield dict(polygons=polygons,start=start,end=end,height_output=height_output,segment=segment)


def composition_cases():
    for axis,plane,low_y,query_y,mode,count,flip,face,amount,segment in itertools.product(
            (0,2),(0,400),(-1024,-512,-256),((-256,0),(-128,128),(0,0)),(0,1),(-1,0,1,2),
            (0,1),(0,1),(-64,0,64),(0,0x80000000)):
        polygon = ((-1024,low_y,plane),(1024,low_y,plane),(-1024,low_y+2048,plane)) if axis == 2 else (
                   (plane,low_y,-1024),(plane,low_y,1024),(plane,low_y+2048,-1024))
        yield dict(polygons=(polygon,),query_bounds=((-128,query_y[0],-1024),(128,query_y[1],1024)),
                   mode=mode,count=count,flip=flip,face=face,amount=amount,segment=segment)


def composed_check(machine,case,read_halfword):
    segment = case['segment']
    data,_ = model_fixture(case['polygons'],segment=segment)
    struct.pack_into('<I',data,QUERY_MODEL+16,pointer(QUERY_GEOMETRY,segment))
    struct.pack_into('<6I',data,QUERY_GEOMETRY,pointer(QUERY_VERTICES,segment),2,0,0,0,0)
    for index,point in enumerate(case['query_bounds']):
        pack_point(data,QUERY_VERTICES+8*index,point)
    struct.pack_into('<I',data,OBJECT+32,pointer(MODEL,segment))
    expected = bytearray(data)
    machine.cpu.mem_write(BUFFER,bytes(data))
    shared = native.h.symbols['D_8008B21C']&native.MASK
    flag = native.h.symbols['D_8008AC4C']&native.MASK
    mode_address = native.h.symbols['D_8008A838']&native.MASK
    machine.cpu.mem_write(shared,bytes([0xCE])*64)
    machine.cpu.mem_write(flag,struct.pack('<i',case['count']))
    machine.cpu.mem_write(mode_address,struct.pack('<i',case['mode']))
    if case['count'] == 1:
        machine.invoke('class_FA50_reset_flag',(pointer(MODEL,segment),))
    if machine.invoke('class_FA50_is_active',(pointer(MODEL,segment),)) != native.u32(case['count']):
        raise ValueError('Original global enumeration value differs.')
    machine.invoke('refresh_source_vertices',(pointer(MODEL,segment),))
    bounds = point_bounds([point for polygon in case['polygons'] for point in polygon])
    shared_expected = struct.pack('<6h',*(bounds[0]+bounds[1]))+bytes([0xCE])*52
    if bytes(machine.cpu.mem_read(shared,64)) != shared_expected:
        raise ValueError('Original model bounds or shared buffer guard differs.')
    for index in (-1,0,1,31):
        if machine.invoke('get_source_vertices',(pointer(MODEL,segment),index)) != (shared|0x80000000):
            raise ValueError('Original shared bounds accessor differs.')
    machine.invoke('func_8001F51C',(pointer(QUERY_MODEL,segment),pointer(CLOUD,segment)))
    points = cube_points(case['query_bounds'])
    struct.pack_into('<I',expected,CLOUD,1)
    for index,point in enumerate(points):
        pack_point(expected,CLOUD+4+6*index,point)
    if bytes(machine.cpu.mem_read(BUFFER,BUFFER_BYTES)) != bytes(expected):
        raise ValueError('Original query cuboid expansion differs.')
    machine.invoke('func_8001F66C',(pointer(CLOUD,segment),case['flip'],case['face'],case['amount']))
    points = transform_cube(points,case['flip'],case['face'],case['amount'])
    for index,point in enumerate(points):
        pack_point(expected,CLOUD+4+6*index,point)
    if bytes(machine.cpu.mem_read(BUFFER,BUFFER_BYTES)) != bytes(expected):
        raise ValueError('Original cuboid face transform differs.')
    initial_contact = struct.unpack_from('<3h',expected,CONTACT)
    result,mask,out,contact = transform_model(case['polygons'],[points],case['count'],case['mode'],read_halfword,initial_contact)
    struct.pack_into('<I',expected,OBJECT+44,mask)
    struct.pack_into('<I',expected,MASK_OUT,out)
    pack_point(expected,CONTACT,contact)
    actual = machine.invoke('func_8001DDF4',(pointer(OBJECT,segment),pointer(MASK_OUT,segment),
                             pointer(CONTACT,segment),pointer(CLOUD,segment)))
    observed = bytes(machine.cpu.mem_read(BUFFER,BUFFER_BYTES))
    if (actual != result or observed != bytes(expected) or bytes(machine.cpu.mem_read(shared,64)) != shared_expected or
            bytes(machine.cpu.mem_read(flag,4)) != struct.pack('<i',case['count']) or
            bytes(machine.cpu.mem_read(mode_address,4)) != struct.pack('<i',case['mode'])):
        raise ValueError('Original composed collision differs: '+repr(dict(case=case,expected=result,actual=actual,
            mask=mask,out=out,contact=contact,differing_offsets=[i for i,(a,b) in enumerate(zip(expected,observed)) if a != b])))
    return result,mask,out


def negative_controls(bridge,functions,read_halfword):
    controls = []
    variants = (
        ('wrong_contact_height',0x80020014,0x00431023,0x00401021,
         dict(polygons=(((-1024,-1024,0),(1024,-1024,0),(-1024,1024,0)),),start=(0,512,-1024),end=(0,512,1024))),
        ('wrong_expanded_bounds_edge',0x8001FF44,0x2442FFE8,0x2442FFE9,
         dict(polygons=(((-1024,-1024,0),(1024,-1024,0),(-1024,1024,0)),),start=(-1048,0,-1024),end=(-1048,0,1024))))
    for name,address,original,changed,case in variants:
        if native.h.target(address,4) != struct.pack('<I',original):
            raise ValueError('Negative-control instruction identity differs.')
        runner = CollisionMachine(bridge,functions,{address:struct.pack('<I',changed)})
        data,args = model_fixture(**case)
        runner.cpu.mem_write(BUFFER,bytes(data))
        actual = runner.invoke('func_8001F8B8',args)
        result,nearest,point,height = primitive_model(case['polygons'],case['start'],case['end'],read_halfword)
        expected = bytearray(data)
        struct.pack_into('<i',expected,NEAREST,nearest)
        pack_point(expected,CONTACT,point)
        struct.pack_into('<i',expected,HEIGHT,height)
        if actual == result and bytes(runner.cpu.mem_read(BUFFER,BUFFER_BYTES)) == bytes(expected):
            raise ValueError('Primitive negative control was not detected.')
        controls.append(dict(name=name,address=hex(address),detected=True,scope='Private Unicorn instruction memory only.'))
    address = 0x8001DF48
    if native.h.target(address,4) != struct.pack('<I',0x28420201):
        raise ValueError('Transform threshold instruction identity differs.')
    runner = CollisionMachine(bridge,functions,{address:struct.pack('<I',0x28420200)})
    case = dict(polygons=(((-1024,-512,0),(1024,-512,0),(-1024,1536,0)),),
                query_bounds=((-128,0,-1024),(128,0,1024)),mode=1,count=1,flip=0,face=0,amount=0,segment=0)
    try:
        composed_check(runner,case,read_halfword)
    except ValueError as error:
        if not str(error).startswith('Original composed collision differs:'):
            raise
    else:
        raise ValueError('Transform threshold negative control was not detected.')
    controls.append(dict(name='wrong_height_threshold',address=hex(address),detected=True,
                         scope='Private Unicorn instruction memory through the original composition.'))
    return controls


def verify(destination, executable, runtime, functions):
    native.initialize_backend(native.load_program(functions))
    read_halfword = lambda address: struct.unpack('<h',native.h.target(address,2))[0]
    dependencies = [Path(__file__),ROOT/'tools/verify_native_ai.py',ROOT/'tools/verify_render_gte.py',
                    ROOT/'tools/nymashock_gte_bridge.cs',ROOT/'configure.py',ROOT/'docs/features.json']
    before = {p:hashlib.sha256(p.read_bytes()).hexdigest() for p in dependencies}
    bridge = CollisionBridge(executable,runtime,destination.with_suffix('.log'))
    machine = CollisionMachine(bridge,functions)
    counts, distinct, outcomes, composed_outcomes = Counter(),set(),Counter(),Counter()
    try:
        for name,a,b,out,segment in sdk_cases():
            data = initial_buffer()
            struct.pack_into('<3i',data,VECTOR_A,*a)
            struct.pack_into('<3i',data,VECTOR_B,*b)
            expected = bytearray(data)
            cr = [0x9ABCDEF0,0x12345678,0x87654321,0x0BADCAFE,0xFEDC]
            machine.adapter.reset(cr)
            if name == 'OuterProduct10':
                working = [native.u32(a[0]),cr[1],native.u32(a[1]),cr[3],native.u32(a[2])&65535]
                result = command_model(working,b,OP)['mac']
                args = (pointer(VECTOR_A,segment),pointer(VECTOR_B,segment),pointer(out,segment))
            else:
                result = command_model(cr,a,SQR)['mac']
                args = (pointer(VECTOR_A,segment),pointer(out,segment))
            struct.pack_into('<3i',expected,out,*result)
            machine.cpu.mem_write(BUFFER,bytes(data))
            returned = machine.invoke(name,args)
            if (bytes(machine.cpu.mem_read(BUFFER,BUFFER_BYTES)) != bytes(expected) or
                    machine.adapter.cr != cr or returned != (pointer(out,segment) if name == 'Square0' else 0xBA123456)):
                raise ValueError('Original SDK vector helper differs: '+repr((name,a,b,out,segment)))
            identity = hashlib.sha256(name.encode()+bytes(data)+struct.pack('<3I',*(list(args)+[0])[:3])).hexdigest()
            if identity in distinct:
                raise ValueError('Duplicate SDK fixture.')
            distinct.add(identity)
            counts[name] += 1
        print('Original vector SDK cases:',dict(counts),flush=True)
        for value in sqrt_cases():
            machine.adapter.reset()
            actual = machine.invoke('SquareRoot0',(value,))
            expected = sqrt_model(value,read_halfword)
            if actual != expected:
                raise ValueError('Original square root differs: '+repr((hex(value),actual,expected)))
            counts['SquareRoot0'] += 1
        print('Original SquareRoot0 cases:',counts['SquareRoot0'],flush=True)
        for case in collision_cases():
            data,args = model_fixture(**case)
            expected = bytearray(data)
            result,nearest,point,height = primitive_model(case['polygons'],case['start'],case['end'],read_halfword)
            struct.pack_into('<i',expected,NEAREST,nearest)
            if point is not None:
                pack_point(expected,CONTACT,point)
                if args[3]:
                    struct.pack_into('<i',expected,HEIGHT,height)
            machine.adapter.reset()
            machine.cpu.mem_write(BUFFER,bytes(data))
            actual = machine.invoke('func_8001F8B8',args)
            if actual != result or bytes(machine.cpu.mem_read(BUFFER,BUFFER_BYTES)) != bytes(expected):
                failure = dict(case=case,expected_result=result,actual_result=actual,nearest=nearest,contact=point,height=height,
                    differing_offsets=[i for i,(a,b) in enumerate(zip(expected,machine.cpu.mem_read(BUFFER,BUFFER_BYTES))) if a != b])
                with destination.with_name(destination.stem+'-failure.json').open('x',encoding='utf-8',newline='\n') as f:
                    json.dump(failure,f,indent=2)
                    f.write('\n')
                raise ValueError('Original primitive collision differs; private failure retained.')
            counts['primitive_collision'] += 1
            outcomes[result] += 1
        print('Original primitive collision cases:',counts['primitive_collision'],flush=True)
        for case in composition_cases():
            machine.adapter.reset()
            result,mask,out = composed_check(machine,case,read_halfword)
            counts['composed_collision'] += 1
            composed_outcomes[(result,mask,out)] += 1
        print('Original composed collision cases:',counts['composed_collision'],flush=True)
        controls = negative_controls(bridge,functions,read_halfword)
    finally:
        bridge.close()
    if any(hashlib.sha256(p.read_bytes()).hexdigest() != digest for p,digest in before.items()):
        raise ValueError('An evidence dependency changed during collision checks.')
    report = dict(status='passed_bounded_original_collision',case_groups=dict(counts),
        original_function_ranges=functions,executed_native_entries=dict(machine.entries),
        primitive_outcomes=dict(outcomes),incoming_decoder_cursors={hex(k):v for k,v in machine.first_cursors.items()},
        composed_outcomes={','.join(map(str,k)):v for k,v in composed_outcomes.items()},
        negative_controls_detected=controls,
        explicit_function_output_stubs=0,cop2_adapter_operations=dict(machine.adapter.counts),
        native_gte_command_invocations=bridge.count,native_lzcs_invocations=bridge.lz_count,
        native_core_sha256=gte.CORE_SHA256,bridge_sha256=hashlib.sha256(Path(executable).read_bytes()).hexdigest(),
        source_promotions=0,original_feature_groups_accepted=0,full_ps1_cpu_timing_checked=False,
        producer_dependencies=[dict(path=p.relative_to(ROOT).as_posix(),sha256=digest) for p,digest in before.items()],
        canonical_executable_sha1=hashlib.sha1(native.h.ROM).hexdigest(),
        lookup_windows=[dict(address=hex(address),bytes=size,sha256=hashlib.sha256(native.h.target(address,size)).hexdigest())
                        for address,size in ((SQRT_TABLE,SQRT_TABLE_BYTES),(SQRT_TABLE-640,640))],
        scope='Synthetic guarded SDK and primitive-collision fixtures; actual native commands and original functions. '
              'COP2 transfer adapter, no complete PS1 CPU, scene, hardware or whole-feature acceptance.')
    with destination.open('x',encoding='utf-8',newline='\n') as output:
        json.dump(report,output,indent=2)
        output.write('\n')
    print(json.dumps(dict(report=str(destination),case_groups=dict(counts))),flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--bridge',type=Path,required=True)
    parser.add_argument('--runtime',required=True)
    parser.add_argument('--ranges',type=Path,required=True,help='Private checked original function range manifest.')
    args = parser.parse_args(argv)
    try:
        destination = (ROOT/args.output).resolve()
        paths = (destination,destination.with_suffix('.log'),destination.with_name(destination.stem+'-stderr.log'),
                 destination.with_name(destination.stem+'-failure.json'))
        if not destination.is_relative_to((ROOT/'.decomp-lab').resolve()) or any(p.exists() for p in paths):
            raise ValueError('Choose new private report and log paths inside .decomp-lab.')
        functions = json.loads(args.ranges.read_text())
        if not isinstance(functions,list) or not functions or any(not f.get('bytes') or not f.get('sha256') for f in functions):
            raise ValueError('A complete function range manifest is required.')
        destination.parent.mkdir(parents=True,exist_ok=True)
        verify(destination,args.bridge.resolve(),args.runtime,functions)
        return 0
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        print('[!] '+str(error),file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
