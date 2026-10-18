// Optional sampled original primitive calls. No game RAM, CPU or GTE writes.
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Web.Script.Serialization;
using BizHawk.BizInvoke;
using BizHawk.Emulation.Cores.Waterbox;

namespace Lsd.Research.Headless {
public sealed class CollisionCallSettings {
    public uint pc { get; set; }
    public uint bytes { get; set; }
    public uint max_samples { get; set; }
    public uint per_key { get; set; }
}
internal sealed class CollisionCallTrace : IDisposable {
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int Result();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int Configure(uint pc,uint bytes,uint limit);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate void VoidResult();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate uint Number();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate IntPtr Pointer();
    readonly Result Reset,Start;
    readonly Configure ConfigureNative;
    readonly VoidResult BeginNative;
    readonly Number Count,NativeTotal,Started,Eligible,Overflow,Pending,DuplicateSkips,FrameSkips,LimitSkips,NestedSkips,DataBytes;
    readonly Pointer Events,Data;
    readonly CollisionCallSettings Settings;
    readonly BinaryWriter Writer,Payload;
    readonly string Output;
    uint Total;
    const int Words=247;
    public CollisionCallTrace(WaterboxHost host,string output,CollisionCallSettings settings) {
        if(settings.pc!=0x8001F8B8 || settings.bytes!=1944 || settings.max_samples<1 || settings.max_samples>64 || settings.per_key!=2)
            throw new Exception("Unsupported original primitive sample selection");
        Settings=settings;Output=output;
        var adapter=CallingConventionAdapters.GetWaterboxUnsafeUnwrapped();
        Reset=adapter.GetDelegateForFunctionPointer<Result>(host.GetProcAddrOrThrow("LsdResetCollisionCalls"));
        Start=adapter.GetDelegateForFunctionPointer<Result>(host.GetProcAddrOrThrow("LsdStartCollisionCalls"));
        ConfigureNative=adapter.GetDelegateForFunctionPointer<Configure>(host.GetProcAddrOrThrow("LsdConfigureCollisionCalls"));
        BeginNative=adapter.GetDelegateForFunctionPointer<VoidResult>(host.GetProcAddrOrThrow("LsdBeginCollisionCallFrame"));
        Count=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetCollisionCallCount"));
        NativeTotal=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetCollisionCallTotal"));
        Started=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetCollisionCallStarted"));
        Eligible=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetCollisionCallEligible"));
        Overflow=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetCollisionCallOverflow"));
        Pending=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetCollisionCallPending"));
        DuplicateSkips=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetCollisionCallDuplicateSkips"));
        FrameSkips=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetCollisionCallFrameSkips"));
        LimitSkips=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetCollisionCallLimitSkips"));
        NestedSkips=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetCollisionCallNestedSkips"));
        DataBytes=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetCollisionCallDataBytes"));
        Events=adapter.GetDelegateForFunctionPointer<Pointer>(host.GetProcAddrOrThrow("LsdGetCollisionCallEvents"));
        Data=adapter.GetDelegateForFunctionPointer<Pointer>(host.GetProcAddrOrThrow("LsdGetCollisionCallData"));
        Writer=new BinaryWriter(File.Open(Path.Combine(output,"collision-calls.bin"),FileMode.CreateNew));
        Payload=new BinaryWriter(File.Open(Path.Combine(output,"collision-call-ram.bin"),FileMode.CreateNew));
    }
    // The owner holds the Waterbox lock while configuring, draining and closing.
    public void Begin(int frame,int arm) {
        if(frame==arm && (Reset()!=1 || ConfigureNative(Settings.pc,Settings.bytes,Settings.max_samples)!=1 || Start()!=1))
            throw new Exception("Native primitive sampler setup failed");
        BeginNative();
    }
    public void Drain(int frame) {
        uint count=Count(),bytes=DataBytes();
        if(count>2 || bytes>0x800000 || bytes!=count*0x400000 || Overflow()!=0)
            throw new Exception("Native primitive sample transport overflow");
        int[] words=new int[checked((int)count*Words)];if(count!=0) Marshal.Copy(Events(),words,0,words.Length);
        byte[] data=new byte[bytes];if(bytes!=0) Marshal.Copy(Data(),data,0,data.Length);
        long start=Payload.BaseStream.Position;
        for(int i=0;i<count;++i) {
            int at=i*Words;
            if(words[at]!=frame || unchecked((uint)words[at+1])!=Total+(uint)i+1 || words[at+243]!=0x200000 || words[at+246]!=1)
                throw new Exception("Native primitive sample frame, ordinal or extent differs");
            foreach(int field in new[] {244,245}) {
                uint relative=unchecked((uint)words[at+field]);
                if((ulong)relative+0x200000>bytes) throw new Exception("Primitive RAM outside frame payload");
                words[at+field]=unchecked((int)checked((uint)(start+relative)));
            }
        }
        Payload.Write(data);byte[] encoded=new byte[words.Length*4];Buffer.BlockCopy(words,0,encoded,0,encoded.Length);Writer.Write(encoded);
        Total+=count;if(Total!=NativeTotal()) throw new Exception("Native primitive samples were lost");
        if(frame%300==0) {Writer.Flush();Payload.Flush();}
    }
    public void Dispose() {
        long bytes=Payload.BaseStream.Position;Writer.Dispose();Payload.Dispose();
        File.WriteAllText(Path.Combine(Output,"collision-call-summary.json"),new JavaScriptSerializer().Serialize(new {
            protocol=1,event_bytes=Words*4,settings=Settings,returns=Total,native_returns=NativeTotal(),native_started=Started(),
            eligible_entries=Eligible(),native_overflow=Overflow(),pending_calls=Pending(),payload_bytes=bytes,
            duplicate_key_skips=DuplicateSkips(),frame_budget_skips=FrameSkips(),sample_limit_skips=LimitSkips(),nested_skips=NestedSkips(),
            frame_payload_limit=0x800000,ram_snapshot_bytes=0x200000,CPU_register_words=37,GTE_architectural_register_words=64,
            original_game_RAM_injected=false,original_CPU_source_modified=false,observer_writes_GTE_registers=false,
            complete_state_parity_checked=false,opaque_internal_GTE_state_serialized=false,
            sampling_policy="First two invocations per observed caller/model-address pair; one start per frame, bounded total. Addresses are not lifetime identities."}));
    }
}
}
