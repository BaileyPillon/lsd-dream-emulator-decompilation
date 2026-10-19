// Separate analysis trace. Original game code and RAM are read-only.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Web.Script.Serialization;
using BizHawk.BizInvoke;
using BizHawk.Emulation.Cores.Sony.PSX;
using BizHawk.Emulation.Cores.Waterbox;

namespace Lsd.Research.Headless {
public sealed class DispatchTarget { public uint pc { get; set; } public int bytes { get; set; } }
internal sealed class DispatchInstructionTrace : IDisposable {
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int ResetTrace();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int AddTarget(uint pc, uint bytes);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int ConfigureWords(uint a, uint b, uint c, uint d);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate void BeginFrame(uint frame);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate uint Number();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate IntPtr Pointer();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate void DisableTrace();
    readonly WaterboxHost Host;
    readonly ResetTrace Reset, Start;
    readonly AddTarget Add;
    readonly ConfigureWords Configure;
    readonly BeginFrame BeginNativeFrame;
    readonly Number Count, NativeTotal, Overflow;
    readonly Pointer Events;
    readonly DisableTrace Disable;
    readonly StreamWriter Writer;
    readonly BinaryWriter Bodies;
    readonly string Output;
    readonly DispatchTarget[] Targets;
    readonly uint[] Memory;
    readonly int ArmFrame;
    readonly DispatchFlowTrace Flow;
    readonly DispatchReturnTrace Returns;
    readonly SdkReadTrace SdkReads;
    readonly CollisionCallTrace CollisionCalls;
    readonly Dictionary<uint, int> Sizes = new Dictionary<uint, int>();
    readonly Dictionary<string, long> StoredBodies = new Dictionary<string, long>();
    readonly Dictionary<string, uint> Counts = new Dictionary<string, uint>();
    public uint Total { get; private set; }
    public bool Enabled { get; private set; }
    const int RecordWords = 1089;

    public DispatchInstructionTrace(Nymashock core, string output, DispatchTarget[] targets, uint[] memory, int armFrame, uint[] flowSites, DispatchReturnSettings returns, CollisionCallSettings collisionCalls) {
        if (targets == null || targets.Length < 1 || targets.Length > 16 || memory == null || memory.Length != 4)
            throw new Exception("Unsupported method trace target or memory set");
        foreach (var target in targets) {
            if ((target.pc & 3) != 0 || target.pc < 0x80010000 || target.pc >= 0x80200000 ||
                target.bytes < 4 || target.bytes > 4096 || (target.bytes & 3) != 0 ||
                (uint)target.bytes > 0x80200000 - target.pc || Sizes.ContainsKey(target.pc))
                throw new Exception("Invalid complete method target span");
            Sizes.Add(target.pc, target.bytes);
        }
        Output = output; Targets = targets; Memory = memory; ArmFrame = armFrame;
        var field = typeof(WaterboxCore).GetField("_exe", BindingFlags.Instance | BindingFlags.NonPublic);
        if (field == null) throw new Exception("Unsupported Waterbox host interface");
        Host = (WaterboxHost)field.GetValue(core);
        Host.Enter(); try {
            var adapter = CallingConventionAdapters.GetWaterboxUnsafeUnwrapped();
            Reset = adapter.GetDelegateForFunctionPointer<ResetTrace>(Host.GetProcAddrOrThrow("LsdResetDispatchTrace"));
            Start = adapter.GetDelegateForFunctionPointer<ResetTrace>(Host.GetProcAddrOrThrow("LsdStartDispatchTrace"));
            Add = adapter.GetDelegateForFunctionPointer<AddTarget>(Host.GetProcAddrOrThrow("LsdAddDispatchTarget"));
            Configure = adapter.GetDelegateForFunctionPointer<ConfigureWords>(Host.GetProcAddrOrThrow("LsdConfigureDispatchWords"));
            BeginNativeFrame = adapter.GetDelegateForFunctionPointer<BeginFrame>(Host.GetProcAddrOrThrow("LsdBeginDispatchFrame"));
            Count = adapter.GetDelegateForFunctionPointer<Number>(Host.GetProcAddrOrThrow("LsdGetDispatchCount"));
            NativeTotal = adapter.GetDelegateForFunctionPointer<Number>(Host.GetProcAddrOrThrow("LsdGetDispatchTotal"));
            Overflow = adapter.GetDelegateForFunctionPointer<Number>(Host.GetProcAddrOrThrow("LsdGetDispatchOverflow"));
            Events = adapter.GetDelegateForFunctionPointer<Pointer>(Host.GetProcAddrOrThrow("LsdGetDispatchEvents"));
            Disable = adapter.GetDelegateForFunctionPointer<DisableTrace>(Host.GetProcAddrOrThrow("LsdDisableDispatchTrace"));
            if (flowSites != null && flowSites.Length != 0) Flow = new DispatchFlowTrace(Host, output, flowSites);
            if (returns != null) {
                if (Flow == null) throw new Exception("Return observation requires original caller-flow context");
                Returns = new DispatchReturnTrace(Host, output, returns);
                if (returns.sdk_targets != null) SdkReads = new SdkReadTrace(Host, output, returns.sdk_targets);
            }
            if(collisionCalls!=null) {
                if(Flow!=null || Returns!=null) throw new Exception("Primitive samples require the separate entry-only observer");
                CollisionCalls=new CollisionCallTrace(Host,output,collisionCalls);
            }
        } finally { Host.Exit(); }
        Writer = new StreamWriter(CaptureBudget.Open(Path.Combine(output,"method-instructions.tsv"),FileMode.CreateNew));
        Bodies = new BinaryWriter(CaptureBudget.Open(Path.Combine(output,"method-code.bin"),FileMode.CreateNew));
        var fields = new List<string> {"relative_frame","pc","a0","a1","a2","a3","ra","sp","timestamp",
            "instruction","transfer_pc","delay_pc","transfer_word","delay_word"};
        for (int i=0;i<11;i++) fields.Add("a0_word_"+(i*4).ToString("X2",CultureInfo.InvariantCulture));
        for (int i=0;i<35;i++) fields.Add("a0_table_word_"+(i*4).ToString("X3",CultureInfo.InvariantCulture));
        for (int i=0;i<4;i++) fields.Add("memory_word_"+i);
        fields.AddRange(new[] {"function_bytes","function_sha256","code_offset"});
        Writer.WriteLine(String.Join("\t",fields));
    }
    public void Begin(int frame) {
        Host.Enter(); try {
            if (frame == ArmFrame) {
                if (Reset()!=1) throw new Exception("Native method observer reset failed");
                foreach (var target in Targets) if (Add(target.pc,(uint)target.bytes)!=1)
                    throw new Exception("Native method observer rejected complete target");
                if (Configure(Memory[0],Memory[1],Memory[2],Memory[3])!=1 || Start()!=1)
                    throw new Exception("Native method observer setup failed");
                Enabled=true;
            }
            BeginNativeFrame((uint)frame);
            if (Flow != null) Flow.Begin(frame, ArmFrame);
            if (Returns != null) Returns.Begin(frame, ArmFrame);
            if (SdkReads != null) SdkReads.Begin(frame, ArmFrame);
            if (CollisionCalls != null) CollisionCalls.Begin(frame, ArmFrame);
        } finally { Host.Exit(); }
    }
    public void Drain(int frame) {
        Host.Enter(); try {
            uint count=Count();
            if (count>1024 || Overflow()!=0) throw new Exception("Native method observation overflow");
            int[] words=new int[checked((int)count*RecordWords)];
            if (count!=0) Marshal.Copy(Events(),words,0,words.Length);
            for (int index=0;index<count;index++) {
                int at=index*RecordWords, bytes=words[at+64];
                uint pc=unchecked((uint)words[at+1]);
                if (words[at]!=frame || !Sizes.ContainsKey(pc) || bytes!=Sizes[pc])
                    throw new Exception("Wrong native method observation boundary or extent");
                byte[] body=new byte[bytes];
                Buffer.BlockCopy(words,(at+65)*4,body,0,bytes);
                string digest;
                using (var hash=SHA256.Create()) digest=BitConverter.ToString(hash.ComputeHash(body)).Replace("-","").ToLowerInvariant();
                long offset;
                if (!StoredBodies.TryGetValue(digest,out offset)) {
                    offset=Bodies.BaseStream.Position; Bodies.Write(body); StoredBodies.Add(digest,offset);
                }
                var row=new List<string>();
                for (int i=0;i<64;i++) row.Add(i==0 || i==8 ? words[at+i].ToString(CultureInfo.InvariantCulture) :
                    unchecked((uint)words[at+i]).ToString("X8",CultureInfo.InvariantCulture));
                row.Add(bytes.ToString(CultureInfo.InvariantCulture)); row.Add(digest);
                row.Add(offset.ToString(CultureInfo.InvariantCulture));
                Writer.WriteLine(String.Join("\t",row));
                string key=pc.ToString("X8",CultureInfo.InvariantCulture);
                if (!Counts.ContainsKey(key)) Counts.Add(key,0);
                Counts[key]++;
            }
            Total+=count;
            if (Total!=NativeTotal()) throw new Exception("Native method observations were lost");
            if (Flow != null) Flow.Drain(frame, count, Total);
            if (Returns != null) Returns.Drain(frame);
            if (SdkReads != null) SdkReads.Drain(frame);
            if (CollisionCalls != null) CollisionCalls.Drain(frame);
            if (frame%300==0) { Writer.Flush(); Bodies.Flush(); }
        } finally { Host.Exit(); }
    }
    public void Dispose() {
        uint nativeTotal, overflow;
        Host.Enter(); try {
            nativeTotal=NativeTotal(); overflow=Overflow(); Disable();
            if (Flow != null) Flow.Dispose();
            if (Returns != null) Returns.Dispose();
            if (SdkReads != null) SdkReads.Dispose();
            if (CollisionCalls != null) CollisionCalls.Dispose();
        } finally { Host.Exit(); }
        Writer.Dispose(); Bodies.Dispose();
        File.WriteAllText(Path.Combine(Output,"method-trace-summary.json"),new JavaScriptSerializer().Serialize(new {
            hook_enabled_relative_frame=ArmFrame,hook_enabled=Enabled,original_instruction_entries=Total,
            target_entry_counts=Counts,targets=Targets,memory_words=Memory,event_bytes=RecordWords*4,
            native_total=nativeTotal,drained_instruction_entries=Total,native_overflow=overflow,
            game_RAM_injected=false,original_CPU_source_modified=false,
            observer_uses_existing_DebugMode_hook=true,complete_state_parity_checked=false}));
    }
}
}
