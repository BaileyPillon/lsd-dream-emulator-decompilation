// Optional method returns and bounded RAM payloads; the original game is read-only.
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Web.Script.Serialization;
using BizHawk.BizInvoke;
using BizHawk.Emulation.Cores.Waterbox;

namespace Lsd.Research.Headless {
public sealed class DispatchReturnSettings {
    public uint read_pc { get; set; }
    public uint helper_pc { get; set; }
    public uint helper_bytes { get; set; }
    public uint request_pc { get; set; }
    public uint poll_pc { get; set; }
    public uint request_call { get; set; }
    public uint poll_call { get; set; }
}
internal sealed class DispatchReturnTrace : IDisposable {
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int Result();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int Configure(uint read, uint helper, uint bytes);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int ConfigureIO(uint request, uint poll, uint requestCall, uint pollCall);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate void VoidResult();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate uint Number();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate IntPtr Pointer();
    readonly Result Reset, Start;
    readonly Configure Set;
    readonly ConfigureIO SetIO;
    readonly VoidResult BeginNative;
    readonly Number Count, NativeTotal, NativeEntries, Overflow, Mismatches, Pending, MaxDepth, DataBytes;
    readonly Pointer Events, Data;
    readonly DispatchReturnSettings Settings;
    readonly BinaryWriter Writer, Payload;
    readonly string Output;
    uint Total;
    const int Words = 150;
    public DispatchReturnTrace(WaterboxHost host, string output, DispatchReturnSettings settings) {
        Settings=settings; Output=output;
        var adapter=CallingConventionAdapters.GetWaterboxUnsafeUnwrapped();
        Reset=adapter.GetDelegateForFunctionPointer<Result>(host.GetProcAddrOrThrow("LsdResetDispatchReturns"));
        Start=adapter.GetDelegateForFunctionPointer<Result>(host.GetProcAddrOrThrow("LsdStartDispatchReturns"));
        Set=adapter.GetDelegateForFunctionPointer<Configure>(host.GetProcAddrOrThrow("LsdConfigureDispatchReturns"));
        SetIO=adapter.GetDelegateForFunctionPointer<ConfigureIO>(host.GetProcAddrOrThrow("LsdConfigureDispatchReturnIO"));
        BeginNative=adapter.GetDelegateForFunctionPointer<VoidResult>(host.GetProcAddrOrThrow("LsdBeginDispatchReturnFrame"));
        Count=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetDispatchReturnCount"));
        NativeTotal=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetDispatchReturnTotal"));
        NativeEntries=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetDispatchReturnEntries"));
        Overflow=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetDispatchReturnOverflow"));
        Mismatches=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetDispatchReturnMismatches"));
        Pending=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetDispatchReturnPending"));
        MaxDepth=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetDispatchReturnMaxDepth"));
        DataBytes=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetDispatchReturnDataBytes"));
        Events=adapter.GetDelegateForFunctionPointer<Pointer>(host.GetProcAddrOrThrow("LsdGetDispatchReturnEvents"));
        Data=adapter.GetDelegateForFunctionPointer<Pointer>(host.GetProcAddrOrThrow("LsdGetDispatchReturnData"));
        Writer=new BinaryWriter(File.Open(Path.Combine(output,"method-returns.bin"),FileMode.CreateNew));
        Payload=new BinaryWriter(File.Open(Path.Combine(output,"method-return-data.bin"),FileMode.CreateNew));
    }
    // The owner holds the native host lock for all three methods.
    public void Begin(int frame, int arm) {
        if(frame==arm) {
            if(Reset()!=1 || Set(Settings.read_pc,Settings.helper_pc,Settings.helper_bytes)!=1 ||
                SetIO(Settings.request_pc,Settings.poll_pc,Settings.request_call,Settings.poll_call)!=1 || Start()!=1)
                throw new Exception("Native return observer setup failed");
        }
        BeginNative();
    }
    public void Drain(int frame) {
        uint count=Count(),size=DataBytes();
        if(count>1024 || size>8*1024*1024 || Overflow()!=0 || Mismatches()!=0)
            throw new Exception("Native return trace overflow or call-stack mismatch");
        int[] words=new int[checked((int)count*Words)];
        if(count!=0) Marshal.Copy(Events(),words,0,words.Length);
        byte[] data=new byte[size]; if(size!=0) Marshal.Copy(Data(),data,0,data.Length);
        long start=Payload.BaseStream.Position;
        for(int i=0;i<count;i++) {
            int at=i*Words;
            if(words[at]!=frame || unchecked((uint)words[at+1])!=Total+(uint)i+1)
                throw new Exception("Native return frame/ordinal mismatch");
            foreach(int offset in new[] {87,90}) {
                uint bytes=unchecked((uint)words[at+offset-1]),relative=unchecked((uint)words[at+offset]);
                if(bytes!=0) {
                    if((ulong)relative+bytes>size) throw new Exception("Native return payload outside its frame arena");
                    words[at+offset]=unchecked((int)checked((uint)(start+relative)));
                } else if(relative!=0) throw new Exception("Empty native return payload has an offset");
            }
        }
        Payload.Write(data);
        byte[] encoded=new byte[words.Length*4];Buffer.BlockCopy(words,0,encoded,0,encoded.Length);Writer.Write(encoded);
        Total+=count;
        if(Total!=NativeTotal()) throw new Exception("Native return observations were lost");
        if(frame%300==0) {Writer.Flush();Payload.Flush();}
    }
    public void Dispose() {
        long bytes=Payload.BaseStream.Position;
        Writer.Dispose();Payload.Dispose();
        File.WriteAllText(Path.Combine(Output,"method-return-summary.json"),new JavaScriptSerializer().Serialize(new {
            protocol=1,event_bytes=Words*4,returns=Total,native_returns=NativeTotal(),native_entries=NativeEntries(),
            native_overflow=Overflow(),native_mismatches=Mismatches(),pending_entries=Pending(),max_depth=MaxDepth(),
            payload_bytes=bytes,settings=Settings,frame_payload_limit=8*1024*1024,
            original_game_RAM_injected=false,original_CPU_source_modified=false,return_values_are_not_transfer_counts=true}));
    }
}
}
