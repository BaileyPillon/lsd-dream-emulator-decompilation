// Optional caller context; no original game RAM or CPU instruction is changed.
using System;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Web.Script.Serialization;
using BizHawk.BizInvoke;
using BizHawk.Emulation.Cores.Waterbox;

namespace Lsd.Research.Headless {
internal sealed class DispatchFlowTrace : IDisposable {
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int NumberResult();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int AddSite(uint pc);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate void VoidResult();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate uint Number();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate IntPtr Pointer();
    readonly NumberResult Reset, Start;
    readonly AddSite Add;
    readonly VoidResult BeginNative;
    readonly Number Count, NativeTotal, Overflow;
    readonly Pointer Events;
    readonly uint[] Sites;
    readonly BinaryWriter Writer;
    readonly string Output;
    uint Total;
    const int Words = 166;
    public DispatchFlowTrace(WaterboxHost host, string output, uint[] sites) {
        if (sites == null || sites.Length < 1 || sites.Length > 16) throw new Exception("Invalid flow sites");
        Sites=sites; Output=output;
        var adapter=CallingConventionAdapters.GetWaterboxUnsafeUnwrapped();
        Reset=adapter.GetDelegateForFunctionPointer<NumberResult>(host.GetProcAddrOrThrow("LsdResetDispatchFlow"));
        Start=adapter.GetDelegateForFunctionPointer<NumberResult>(host.GetProcAddrOrThrow("LsdStartDispatchFlow"));
        Add=adapter.GetDelegateForFunctionPointer<AddSite>(host.GetProcAddrOrThrow("LsdAddDispatchFlowSite"));
        BeginNative=adapter.GetDelegateForFunctionPointer<VoidResult>(host.GetProcAddrOrThrow("LsdBeginDispatchFlowFrame"));
        Count=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetDispatchFlowCount"));
        NativeTotal=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetDispatchFlowTotal"));
        Overflow=adapter.GetDelegateForFunctionPointer<Number>(host.GetProcAddrOrThrow("LsdGetDispatchFlowOverflow"));
        Events=adapter.GetDelegateForFunctionPointer<Pointer>(host.GetProcAddrOrThrow("LsdGetDispatchFlowEvents"));
        Writer=new BinaryWriter(File.Open(Path.Combine(output,"method-flow.bin"),FileMode.CreateNew));
    }
    // Called while the owning method trace holds the Waterbox host lock.
    public void Begin(int frame, int arm) {
        if (frame==arm) {
            if (Reset()!=1) throw new Exception("Native flow reset failed");
            foreach(uint site in Sites) if(Add(site)!=1) throw new Exception("Native flow site rejected");
            if(Start()!=1) throw new Exception("Native flow setup failed");
        }
        BeginNative();
    }
    public void Drain(int frame, uint expectedCount, uint expectedTotal) {
        uint count=Count();
        if(count!=expectedCount || count>1024 || Overflow()!=0) throw new Exception("Native flow count/overflow mismatch");
        int[] words=new int[checked((int)count*Words)];
        if(count!=0) Marshal.Copy(Events(),words,0,words.Length);
        for(int i=0;i<count;i++) if(words[i*Words]!=frame || unchecked((uint)words[i*Words+1])!=Total+(uint)i+1)
            throw new Exception("Native flow frame/ordinal mismatch");
        byte[] bytes=new byte[words.Length*4]; Buffer.BlockCopy(words,0,bytes,0,bytes.Length); Writer.Write(bytes);
        Total+=count;
        if(Total!=expectedTotal || Total!=NativeTotal()) throw new Exception("Native flow entries were lost");
        if(frame%300==0) Writer.Flush();
    }
    public void Dispose() {
        Writer.Dispose();
        File.WriteAllText(Path.Combine(Output,"method-flow-summary.json"),new JavaScriptSerializer().Serialize(new {
            protocol=1,event_bytes=Words*4,history_instructions=16,entries=Total,sites=Sites,
            native_total=NativeTotal(),native_overflow=Overflow(),game_RAM_injected=false,
            CPU_source_modified=false,instruction_cache_peek_only=true}));
    }
}
}
