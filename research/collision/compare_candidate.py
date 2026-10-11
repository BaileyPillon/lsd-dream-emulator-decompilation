"""Compare an isolated complete-build primitive candidate with original collision paths.

Original outputs, guarded caller buffers and ordered native GTE events must agree.
This is bounded research evidence; it neither accepts C nor verifies PS1 timing."""
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
    reference=n.h.ROM
    candidate_path=Path(args.candidate).resolve()
    candidate=candidate_path.read_bytes()
    diffs=[i for i,(a,b) in enumerate(zip(reference,candidate)) if a!=b]
    offset=0x800+0x8001F8B8-n.h.LOAD
    if len(candidate)!=len(reference) or any(not offset<=i<offset+1944 for i in diffs):
        raise ValueError('Candidate changes bytes outside the original primitive function.')
    patch=candidate[offset:offset+1944]
    protected={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),candidate_path,Path('rom/SLPS_015.56'),
        Path('build/SLPS015.56'),Path('tools/verify_collision.py'),Path('docs/collision-function-ranges.json'),
        Path('tools/nymashock_gte_bridge.cs')]}
    read_halfword=lambda address:struct.unpack('<h',n.h.target(address,2))[0]

    class RecordingBridge(c.CollisionBridge):
        def __init__(self,*args):
            self.events=[]
            super().__init__(*args)
        def execute(self,cr,ir,command):
            result=super().execute(cr,ir,command)
            self.events.append(dict(command=command,cr=list(cr),ir=list(ir),result=result.copy()))
            return result
        def leading(self,value):
            result=super().leading(value)
            self.events.append(dict(command=0,lzcs=n.u32(value),lzcr=result))
            return result

    bridge_exe=Path(args.bridge).resolve()
    runtime=args.runtime
    bridge=RecordingBridge(bridge_exe,runtime,out/'bridge.log')
    original=c.CollisionMachine(bridge,functions)
    recovered=c.CollisionMachine(bridge,functions,{0x8001F8B8:patch})
    counts=Counter();identities=set();outputs=hashlib.sha256();event_digest=hashlib.sha256()

    def capture(machine,run):
        machine.adapter.reset();bridge.events=[]
        result=run(machine)
        state=dict(cr=machine.adapter.cr,ir=machine.adapter.ir,mac=machine.adapter.mac,
                   lzcs=machine.adapter.lzcs,lzcr=machine.adapter.lzcr)
        events=json.dumps(bridge.events,sort_keys=True,separators=(',',':')).encode()
        return result,bytes(machine.cpu.mem_read(c.BUFFER,c.BUFFER_BYTES)),state,events

    def pair_primitive(data,args,kind):
        identity=hashlib.sha256(bytes(data)+struct.pack('<6I',*args)).hexdigest()
        if identity in identities:raise ValueError('Duplicate paired primitive input: '+identity)
        identities.add(identity)
        def run(machine):
            machine.cpu.mem_write(c.BUFFER,bytes(data))
            return machine.invoke('func_8001F8B8',args)
        a=capture(original,run);b=capture(recovered,run)
        if a!=b:raise ValueError('Original/candidate primitive pair differs: '+repr((kind,args)))
        counts[kind]+=1
        outputs.update(struct.pack('<I',a[0])+a[1]);event_digest.update(a[3])

    try:
        for number,case in enumerate(c.collision_cases(),1):
            data,args=c.model_fixture(**case);pair_primitive(data,args,'primitive')
            if number%2000==0:print('Primitive pairs',number,flush=True)
        # Valid caller-buffer overlaps and KUSEG/KSEG0/KSEG1 pointers. Inputs stay aligned.
        tri=((-1024,-1024,0),(1024,-1024,0),(-1024,1024,0))
        for start,end,segment,contact,nearest,height in itertools.product(
                ((0,0,-1000),(-1048,0,-1000),(0,-512,1000)),
                ((0,0,1000),(-1048,0,1000),(0,-512,-1000)),
                (0,0x80000000,0xA0000000),
                (c.CONTACT,c.VECTOR_A,c.VECTOR_B),
                (c.NEAREST,c.CONTACT,c.VECTOR_A,c.VECTOR_B),
                (0,c.HEIGHT,c.CONTACT,c.VECTOR_A,c.VECTOR_B)):
            if contact==c.CONTACT and nearest==c.NEAREST and height in (0,c.HEIGHT):continue
            data,args=c.model_fixture((tri,),start=start,end=end,segment=segment)
            args=(args[0],c.pointer(nearest,segment),c.pointer(contact,segment),
                  c.pointer(height,segment) if height else 0,args[4],args[5])
            pair_primitive(data,args,'caller_alias')
        print('Caller alias pairs',counts['caller_alias'],flush=True)
        compositions=set()
        for number,case in enumerate(c.composition_cases(),1):
            identity=hashlib.sha256(json.dumps(case,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if identity in compositions:raise ValueError('Duplicate stage-input graph.')
            compositions.add(identity)
            a=capture(original,lambda machine:c.composed_check(machine,case,read_halfword))
            b=capture(recovered,lambda machine:c.composed_check(machine,case,read_halfword))
            if a!=b:raise ValueError('Original/candidate composed pair differs.')
            counts['composition']+=1
            outputs.update(struct.pack('<3I',*a[0])+a[1]);event_digest.update(a[3])
            if number%1000==0:print('Composition pairs',number,flush=True)
        # Prove the same bounded assertion detects a broken candidate edge rule.
        mutated=bytearray(patch);at=0x8001FF44-0x8001F8B8
        word=int.from_bytes(mutated[at:at+4],'little')
        if word!=0x2442FFE8:raise ValueError('Candidate negative control lost its reviewed instruction.')
        mutated[at:at+4]=(0x2442FFE9).to_bytes(4,'little')
        fault=c.CollisionMachine(bridge,functions,{0x8001F8B8:bytes(mutated)})
        data,args=c.model_fixture((tri,),start=(-1048,0,-1000),end=(-1048,0,1000))
        def invoke(machine):
            machine.cpu.mem_write(c.BUFFER,bytes(data));return machine.invoke('func_8001F8B8',args)
        a=capture(original,invoke);b=capture(fault,invoke)
        if a==b:raise ValueError('Broken candidate edge was not detected.')
        controls=[dict(address='0x8001ff44',native_word=hex(word),mutated_word='0x2442ffe9',detected=True)]
    finally:
        bridge.close()
    for p,digest in protected.items():
        if hashlib.sha256(p.read_bytes()).hexdigest()!=digest:raise ValueError('Protected dependency changed: '+str(p))
    report=dict(status='passed_bounded_candidate_pairs',counts=dict(counts),
        canonical_executable_sha1=hashlib.sha1(reference).hexdigest(),
        candidate_executable_sha1=hashlib.sha1(candidate).hexdigest(),
        candidate_function_sha256=hashlib.sha256(patch).hexdigest(),
        differing_executable_bytes=diffs,only_changed_function='func_8001F8B8',
        original_entry_counts=dict(original.entries),candidate_run_entry_counts=dict(recovered.entries),
        pair_outputs_sha256=outputs.hexdigest(),ordered_native_events_sha256=event_digest.hexdigest(),
        native_op_sqr_invocations=bridge.count,native_lzcs_invocations=bridge.lz_count,
        explicit_function_output_stubs=0,negative_controls=controls,
        exact_build_match=(candidate==reference),source_promotions=0,original_feature_groups_accepted=0,
        protected_dependencies=[dict(path=str(p),sha256=digest) for p,digest in protected.items()],
        scope='Private complete-build candidate versus canonical routines; synthetic caller aliases and stage graphs. '
              'Actual native OP/SQR/LZCS; explicit COP2 adapter. No hardware timing, natural scenes or whole-feature acceptance.')
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',json.dumps(dict(counts)),flush=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--bridge',type=Path,required=True)
    parser.add_argument('--runtime',required=True)
    args=parser.parse_args(argv)
    verify(args)
    return 0


if __name__=='__main__':
    sys.exit(main())
