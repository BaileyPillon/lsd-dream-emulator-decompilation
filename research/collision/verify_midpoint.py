"""Check original non-NULL clipping and midpoint outputs, including caller aliases.

Requires a current canonical local build and optional Unicorn in WSL.
No original function output is stubbed and no GTE operations are involved."""
from collections import Counter
import argparse,os,hashlib,itertools,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools import verify_collision as c
from tools import verify_native_ai as n

def verify(args):
    os.chdir(ROOT)
    out=Path(args.output).resolve()
    if not out.is_relative_to(ROOT/'.decomp-lab') or out==ROOT/'.decomp-lab':
        raise ValueError('Use a fresh private output directory inside .decomp-lab.')
    out.mkdir(parents=True,exist_ok=False)
    functions=json.loads(Path('docs/collision-function-ranges.json').read_text())
    n.initialize_backend(n.load_program(functions))
    machine=c.CollisionMachine(None,functions)

    class Point:
        def __init__(self,data,offset):self.data,self.offset=data,offset
        def get(self,axis):return struct.unpack_from('<h',self.data,self.offset+axis*2)[0]
        def put(self,axis,value):struct.pack_into('<h',self.data,self.offset+axis*2,c.signed(value,16))
        def values(self):return tuple(self.get(i) for i in range(3))
        @classmethod
        def local(cls,values):return cls(bytearray(struct.pack('<3h',*values)),0)
    def bounds(data):return struct.unpack_from('<3h',data,c.MODEL),struct.unpack_from('<3h',data,c.MODEL+6)
    def flags(data,point):return c.point_flags(bounds(data),point.values())
    def edge(data,mid,a,b):
        for _ in range(40):
            for axis in range(3):mid.put(axis,(a.get(axis)+b.get(axis))>>1)
            value=mid.values()
            if value==a.values() or value==b.values():return
            if flags(data,mid)==0:a=Point.local(value)
            else:b=Point.local(value)
        raise ValueError('Midpoint reference did not converge.')
    def clip(data,mid,a,b,depth=0):
        if depth>40:raise ValueError('Clipping reference exceeded signed-halfword depth.')
        fa,fb=flags(data,a),flags(data,b)
        if fa==0:
            if fb==0:return 1
        elif fb==0:
            if mid is not None:edge(data,mid,b,a)
            return 3
        if fa==0:
            if mid is not None:edge(data,mid,a,b)
            return 2
        if fa&fb:return 0
        half=tuple((a.get(i)+b.get(i))>>1 for i in range(3))
        if half==a.values() or half==b.values():return 0
        half=Point.local(half)
        result=clip(data,mid,a,half,depth+1)
        return result or clip(data,mid,half,b,depth+1)

    boxes=[((-16,-16,-16),(16,16,16)),((0,0,0),(0,0,0)),((-64,-32,-8),(32,16,8))]
    points=[(0,0,0),(-64,0,0),(64,0,0),(0,-64,0),(0,64,0),(0,0,-64),(0,0,64),
            (-64,-64,-64),(64,64,64),(-1,1,1)]
    outputs=(c.CONTACT,c.VECTOR_A,c.VECTOR_A+2,c.VECTOR_B,c.VECTOR_B+2,c.MODEL)
    counts=Counter();outcomes=Counter();seen=set();input_hash=hashlib.sha256();output_hash=hashlib.sha256()
    for box,a,b,segment,mid_offset in itertools.product(boxes,points,points,(0,0x80000000,0xA0000000),outputs):
        data=c.initial_buffer();struct.pack_into('<6h',data,c.MODEL,*(box[0]+box[1]))
        c.pack_point(data,c.VECTOR_A,a);c.pack_point(data,c.VECTOR_B,b)
        args=(c.pointer(mid_offset,segment),c.pointer(c.MODEL,segment),
              c.pointer(c.VECTOR_A,segment),c.pointer(c.VECTOR_B,segment))
        identity=hashlib.sha256(bytes(data)+struct.pack('<4I',*args)).digest()
        if identity in seen:raise ValueError('Duplicate midpoint fixture.')
        seen.add(identity);input_hash.update(identity)
        expected=bytearray(data)
        result=clip(expected,Point(expected,mid_offset),Point(expected,c.VECTOR_A),Point(expected,c.VECTOR_B))
        machine.cpu.mem_write(c.BUFFER,bytes(data));actual=machine.invoke('func_8001E110',args)
        observed=bytes(machine.cpu.mem_read(c.BUFFER,c.BUFFER_BYTES))
        if actual!=result or observed!=bytes(expected):
            failure=dict(box=box,a=a,b=b,segment=segment,mid_offset=mid_offset,expected=result,actual=actual,
                differing_offsets=[i for i,(x,y) in enumerate(zip(observed,expected)) if x!=y])
            (out/'failure.json').write_text(json.dumps(failure,indent=2)+'\n')
            raise ValueError('Original midpoint/alias output differs.')
        counts['nonnull_clip']+=1;outcomes[str(actual)]+=1;output_hash.update(struct.pack('<I',actual)+observed)
        if counts['nonnull_clip']%1000==0:print('Non-NULL clipping',counts['nonnull_clip'],flush=True)

    # An incorrect bisection shift must change the externally visible boundary point.
    address=0x8001E2E8;original=n.h.target(address,436)
    shift=next(i for i in range(0,len(original),4)
        if (int.from_bytes(original[i:i+4],'little')&0xFC00003F)==3 and ((int.from_bytes(original[i:i+4],'little')>>6)&31)==1)
    word=int.from_bytes(original[shift:shift+4],'little');mutated=(word&~0x7C0)|(2<<6)
    fault=c.CollisionMachine(None,functions,{address+shift:mutated.to_bytes(4,'little')})
    data=c.initial_buffer();struct.pack_into('<6h',data,c.MODEL,-16,-16,-16,16,16,16)
    c.pack_point(data,c.VECTOR_A,(0,0,0));c.pack_point(data,c.VECTOR_B,(127,0,0))
    args=(c.pointer(c.CONTACT),c.pointer(c.MODEL),c.pointer(c.VECTOR_A),c.pointer(c.VECTOR_B))
    machine.cpu.mem_write(c.BUFFER,bytes(data));machine.invoke('func_8001E110',args)
    good=bytes(machine.cpu.mem_read(c.BUFFER,c.BUFFER_BYTES))
    fault.cpu.mem_write(c.BUFFER,bytes(data));fault.invoke('func_8001E110',args)
    bad=bytes(fault.cpu.mem_read(c.BUFFER,c.BUFFER_BYTES))
    if good==bad:raise ValueError('Bad midpoint shift was not detected.')
    assert machine.entries['func_8001E2E8']>0
    assert not machine.adapter.counts
    report=dict(status='passed_bounded_nonnull_midpoint',counts=dict(counts),distinct_inputs=len(seen),
        result_counts=dict(outcomes),executed_original_entries=dict(machine.entries),
        input_order_sha256=input_hash.hexdigest(),output_order_sha256=output_hash.hexdigest(),
        zero_cop2_operations=True,explicit_function_output_stubs=0,
        negative_control=dict(address=hex(address+shift),original_word=hex(word),mutated_word=hex(mutated),detected=True),
        canonical_executable_sha1=hashlib.sha1(n.h.ROM).hexdigest(),source_promotions=0,whole_feature_groups_accepted=0,
        scope='Original recursive clipping and midpoint helper over synthetic bounds and aligned/partial caller overlaps. No natural scene or complete CPU timing acceptance.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',json.dumps(dict(counts)),flush=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    verify(args)
    return 0


if __name__=='__main__':
    sys.exit(main())
