// Optional original SDK call/return and completed-sector RAM observation.
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Web.Script.Serialization;
using BizHawk.BizInvoke;
using BizHawk.Emulation.Cores.Waterbox;

namespace Lsd.Research.Headless {
public sealed class SdkReadTarget {
    public uint pc { get; set; }
    public uint bytes { get; set; }
    public uint kind { get; set; }
}
internal sealed class SdkReadTrace : IDisposable {
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int Result();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int AddTarget(uint pc, uint bytes, uint kind);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate void VoidResult();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate uint Number();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate IntPtr Pointer();
    readonly Result Reset, Start;
    readonly AddTarget Add;
    readonly VoidResult BeginNative;
    readonly Number Count, NativeTotal, Entries, Overflow, Pending, MaxDepth, Transfer, Completions, Failures, Unassociated, Overlaps, DataBytes;
    readonly Pointer Events, Data;
    readonly SdkReadTarget[] Targets;
    readonly BinaryWriter Writer, Payload;
    readonly string Output;
    uint Total;
    const int Words = 116;
    public SdkReadTrace(WaterboxHost host, string output, SdkReadTarget[] targets) {
        Targets=targets; Output=output;
        var adapter=CallingConventionAdapters.GetWaterboxUnsafeUnwrapped();
        Reset=adapter.GetDelegateForFunctionPointer<Result>(host.GetProcAddrOrThrow("LsdResetSdkReads"));
        Start=adapter.GetDelegateForFunctionPointer<Result>(host.GetProcAddrOrThrow("LsdStartSdkReads"));
        Add=adapter.GetDelegateForFunctionPointer<AddTarget>(host.GetProcAddrOrThrow("LsdAddSdkReadTarget"));
        BeginNative=adapter.GetDelegateForFunctionPointer<VoidResult>(host.GetProcAddrOrThrow("LsdBeginSdkReadFrame"));
        Count=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetSdkReadCount"));
        NativeTotal=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetSdkReadTotal"));
        Entries=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetSdkReadEntries"));
        Overflow=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetSdkReadOverflow"));
        Pending=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetSdkReadPending"));
        MaxDepth=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetSdkReadMaxDepth"));
        Transfer=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetSdkReadTransfer"));
        Completions=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetSdkReadCompletions"));
        Failures=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetSdkReadFailures"));
        Unassociated=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetSdkReadUnassociated"));
        Overlaps=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetSdkReadOverlaps"));
        DataBytes=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetSdkReadDataBytes"));
        Events=adapter.GetDelegateForFunctionPointer<Pointer>(host.GetProcAddrOrThrow("LsdGetSdkReadEvents"));
        Data=adapter.GetDelegateForFunctionPointer<Pointer>(host.GetProcAddrOrThrow("LsdGetSdkReadData"));
        Writer=new BinaryWriter(File.Open(Path.Combine(output,"sdk-reads.bin"),FileMode.CreateNew));
        Payload=new BinaryWriter(File.Open(Path.Combine(output,"sdk-read-data.bin"),FileMode.CreateNew));
    }
    // The owner holds the native host lock for all three methods.
    public void Begin(int frame, int arm) {
        if(frame==arm) {
            if(Reset()!=1) throw new Exception("Native SDK observer reset failed");
            foreach(var target in Targets) if(Add(target.pc,target.bytes,target.kind)!=1)
                throw new Exception("Native SDK target rejected");
            if(Start()!=1) throw new Exception("Native SDK observer start failed");
        }
        BeginNative();
    }
    public void Drain(int frame) {
        uint count=Count(),size=DataBytes();
        if(count>32768 || size>32*1024*1024 || Overflow()!=0)
            throw new Exception("Native SDK trace overflow");
        int[] words=new int[checked((int)count*Words)];
        if(count!=0) Marshal.Copy(Events(),words,0,words.Length);
        byte[] data=new byte[size]; if(size!=0) Marshal.Copy(Data(),data,0,data.Length);
        long start=Payload.BaseStream.Position;
        for(int i=0;i<count;i++) {
            int at=i*Words;
            if(words[at]!=frame || unchecked((uint)words[at+1])!=Total+(uint)i+1)
                throw new Exception("Native SDK frame/ordinal mismatch");
            foreach(int offset in new[] {108,111}) {
                uint bytes=unchecked((uint)words[at+offset-1]),relative=unchecked((uint)words[at+offset]);
                if(bytes!=0) {
                    if((ulong)relative+bytes>size) throw new Exception("Native SDK payload outside frame arena");
                    words[at+offset]=unchecked((int)checked((uint)(start+relative)));
                } else if(relative!=0) throw new Exception("Empty SDK payload has an offset");
            }
        }
        Payload.Write(data);
        byte[] encoded=new byte[words.Length*4]; Buffer.BlockCopy(words,0,encoded,0,encoded.Length); Writer.Write(encoded);
        Total+=count;
        if(Total!=NativeTotal()) throw new Exception("Native SDK observations were lost");
        if(frame%300==0) {Writer.Flush();Payload.Flush();}
    }
    public void Dispose() {
        long bytes=Payload.BaseStream.Position; Writer.Dispose(); Payload.Dispose();
        File.WriteAllText(Path.Combine(Output,"sdk-read-summary.json"),new JavaScriptSerializer().Serialize(new {
            protocol=1,event_bytes=Words*4,returns=Total,native_returns=NativeTotal(),native_entries=Entries(),
            native_overflow=Overflow(),pending_calls=Pending(),max_depth=MaxDepth(),pending_transfer=Transfer(),
            completions=Completions(),failed_transfers=Failures(),unassociated_polls=Unassociated(),overlapping_requests=Overlaps(),
            payload_bytes=bytes,targets=Targets,frame_payload_limit=32*1024*1024,
            original_game_RAM_injected=false,original_CPU_source_modified=false,
            buffer_scope="Complete sector-count times 2048 RAM at a successful zero-valued SDK poll return; disc identity requires separate verification."}));
    }
}
}
