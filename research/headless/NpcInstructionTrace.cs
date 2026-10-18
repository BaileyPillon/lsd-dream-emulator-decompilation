// Optional observer for the separately built PS1 analysis core.
// Original game code and emulated RAM are never written by this class.
using System;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Web.Script.Serialization;
using BizHawk.BizInvoke;
using BizHawk.Emulation.Cores.Sony.PSX;
using BizHawk.Emulation.Cores.Waterbox;

namespace Lsd.Research.Headless {
public interface INpcTrace : IDisposable {
    void Begin(int frame);
    void Drain(int frame);
    uint Total { get; }
    bool Enabled { get; }
}
public interface INpcTraceFactory {
    INpcTrace Create(object core, string output, uint watch, int armFrame);
}
internal sealed class NpcInstructionTrace : INpcTrace {
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int ConfigureTrace(uint pc);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate void BeginTraceFrame(uint frame);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate uint TraceNumber();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate IntPtr TracePointer();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate void EndTrace();
    readonly WaterboxHost Host;
    readonly ConfigureTrace Configure;
    readonly BeginTraceFrame BeginFrame;
    readonly TraceNumber Count, NativeTotal, Overflow;
    readonly TracePointer Events;
    readonly EndTrace Disable;
    readonly StreamWriter Writer;
    readonly string Output;
    readonly uint Watch;
    readonly int ArmFrame;
    public uint Total { get; private set; }
    public bool Enabled { get; private set; }
    int First = -1, Last = -1;

    public NpcInstructionTrace(Nymashock core, string output, uint watch, int armFrame) {
        Output = output; Watch = watch; ArmFrame = armFrame;
        var field = typeof(WaterboxCore).GetField("_exe", BindingFlags.Instance | BindingFlags.NonPublic);
        if (field == null) throw new Exception("Unsupported Waterbox host interface");
        Host = (WaterboxHost)field.GetValue(core);
        Host.Enter(); try {
            var adapter = CallingConventionAdapters.GetWaterboxUnsafeUnwrapped();
            Configure = adapter.GetDelegateForFunctionPointer<ConfigureTrace>(Host.GetProcAddrOrThrow("LsdConfigureNpcTrace"));
            BeginFrame = adapter.GetDelegateForFunctionPointer<BeginTraceFrame>(Host.GetProcAddrOrThrow("LsdBeginNpcTraceFrame"));
            Count = adapter.GetDelegateForFunctionPointer<TraceNumber>(Host.GetProcAddrOrThrow("LsdGetNpcTraceCount"));
            NativeTotal = adapter.GetDelegateForFunctionPointer<TraceNumber>(Host.GetProcAddrOrThrow("LsdGetNpcTraceTotal"));
            Overflow = adapter.GetDelegateForFunctionPointer<TraceNumber>(Host.GetProcAddrOrThrow("LsdGetNpcTraceOverflow"));
            Events = adapter.GetDelegateForFunctionPointer<TracePointer>(Host.GetProcAddrOrThrow("LsdGetNpcTraceEvents"));
            Disable = adapter.GetDelegateForFunctionPointer<EndTrace>(Host.GetProcAddrOrThrow("LsdDisableNpcTrace"));
        } finally { Host.Exit(); }
        Writer = new StreamWriter(File.Open(Path.Combine(output, "npc-instructions.tsv"), FileMode.CreateNew));
        Writer.WriteLine("relative_frame\tpc\tentity\tra\tsp\ttimestamp\tinstruction\tcontext_tick");
    }

    public void Begin(int frame) {
        Host.Enter(); try {
            if (frame == ArmFrame) {
                if (Configure(Watch) != 1) throw new Exception("Native observer rejected watched PC");
                Enabled = true;
            }
            BeginFrame((uint)frame);
        } finally { Host.Exit(); }
    }

    public void Drain(int frame) {
        Host.Enter(); try {
            uint count = Count();
            if (count > 256 || Overflow() != 0) throw new Exception("Native instruction trace overflow");
            int[] words = new int[checked((int)count * 8)];
            if (count != 0) Marshal.Copy(Events(), words, 0, words.Length);
            for (int row = 0; row < count; row++) {
                int at = row * 8;
                if (words[at] != frame || unchecked((uint)words[at + 1]) != Watch)
                    throw new Exception("Wrong instruction observation boundary");
                if (First < 0) First = frame;
                Last = frame;
                Writer.WriteLine(String.Join("\t", frame,
                    unchecked((uint)words[at + 1]).ToString("X8", CultureInfo.InvariantCulture),
                    unchecked((uint)words[at + 2]).ToString("X8", CultureInfo.InvariantCulture),
                    unchecked((uint)words[at + 3]).ToString("X8", CultureInfo.InvariantCulture),
                    unchecked((uint)words[at + 4]).ToString("X8", CultureInfo.InvariantCulture),
                    words[at + 5], unchecked((uint)words[at + 6]).ToString("X8", CultureInfo.InvariantCulture),
                    unchecked((uint)words[at + 7])));
            }
            Total += count;
            if (Total != NativeTotal()) throw new Exception("Native instruction events were lost");
            if (frame % 300 == 0) Writer.Flush();
        } finally { Host.Exit(); }
    }

    public void Dispose() {
        Host.Enter(); try { Disable(); } finally { Host.Exit(); }
        Writer.Dispose();
        File.WriteAllText(Path.Combine(Output, "npc-trace-summary.json"), new JavaScriptSerializer().Serialize(new {
            watched_pc = Watch.ToString("X8", CultureInfo.InvariantCulture), hook_enabled_relative_frame = ArmFrame,
            hook_enabled = Enabled, original_instruction_entries = Total,
            first_observed_entry_frame = First, last_observed_entry_frame = Last,
            game_RAM_injected = false, original_CPU_source_modified = false,
            observer_uses_existing_DebugMode_hook = true, complete_state_parity_checked = false}));
    }
}
}
