// Optional multi-target analysis log; the selected-PC trace stays independent.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Web.Script.Serialization;
using BizHawk.BizInvoke;
using BizHawk.Emulation.Cores.Sony.PSX;
using BizHawk.Emulation.Cores.Waterbox;

namespace Lsd.Research.Headless {
internal sealed class NpcCatalogueFactory : INpcTraceFactory {
    readonly uint[] Pcs;
    public NpcCatalogueFactory(uint[] pcs) {
        if (pcs == null || pcs.Length < 1 || pcs.Length > 128) throw new Exception("Invalid catalogue target count");
        var unique = new HashSet<uint>();
        foreach (uint pc in pcs)
            if ((pc & 3) != 0 || pc < 0x80010000 || pc >= 0x80200000 || !unique.Add(pc))
                throw new Exception("Invalid or repeated catalogue target");
        Pcs = (uint[])pcs.Clone();
    }
    public INpcTrace Create(object core, string output, uint watch, int armFrame) {
        return new NpcCatalogueTrace((Nymashock)core, output, watch, armFrame, Pcs);
    }
}
internal sealed class NpcCatalogueTrace : INpcTrace {
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int Configure();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int AddTarget(uint pc);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate void BeginFrame(uint frame);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate uint Number();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate IntPtr Pointer();
    readonly NpcInstructionTrace Primary;
    readonly WaterboxHost Host;
    readonly Configure Reset, Start;
    readonly AddTarget Add;
    readonly BeginFrame BeginNative;
    readonly Number Count, NativeTotal, Overflow;
    readonly Pointer Events;
    readonly uint[] Pcs;
    readonly HashSet<uint> Targets;
    readonly int ArmFrame;
    readonly string Output;
    readonly StreamWriter Writer;
    uint CatalogueTotal;
    int First = -1, Last = -1;
    public uint Total { get { return Primary.Total; } }
    public bool Enabled { get { return Primary.Enabled; } }
    public NpcCatalogueTrace(Nymashock core, string output, uint watch, int armFrame, uint[] pcs) {
        Pcs = pcs; Targets = new HashSet<uint>(pcs); ArmFrame = armFrame; Output = output;
        if (!Targets.Contains(watch)) throw new Exception("Selected PC is absent from the catalogue");
        Primary = new NpcInstructionTrace(core, output, watch, armFrame);
        var field = typeof(WaterboxCore).GetField("_exe", BindingFlags.Instance | BindingFlags.NonPublic);
        if (field == null) throw new Exception("Unsupported Waterbox host interface");
        Host = (WaterboxHost)field.GetValue(core);
        Host.Enter(); try {
            var adapter = CallingConventionAdapters.GetWaterboxUnsafeUnwrapped();
            Reset = adapter.GetDelegateForFunctionPointer<Configure>(Host.GetProcAddrOrThrow("LsdResetNpcCatalogue"));
            Add = adapter.GetDelegateForFunctionPointer<AddTarget>(Host.GetProcAddrOrThrow("LsdAddNpcCatalogueTarget"));
            Start = adapter.GetDelegateForFunctionPointer<Configure>(Host.GetProcAddrOrThrow("LsdStartNpcCatalogue"));
            BeginNative = adapter.GetDelegateForFunctionPointer<BeginFrame>(Host.GetProcAddrOrThrow("LsdBeginNpcCatalogueFrame"));
            Count = adapter.GetDelegateForFunctionPointer<Number>(Host.GetProcAddrOrThrow("LsdGetNpcCatalogueCount"));
            NativeTotal = adapter.GetDelegateForFunctionPointer<Number>(Host.GetProcAddrOrThrow("LsdGetNpcCatalogueTotal"));
            Overflow = adapter.GetDelegateForFunctionPointer<Number>(Host.GetProcAddrOrThrow("LsdGetNpcCatalogueOverflow"));
            Events = adapter.GetDelegateForFunctionPointer<Pointer>(Host.GetProcAddrOrThrow("LsdGetNpcCatalogueEvents"));
        } finally { Host.Exit(); }
        Writer = new StreamWriter(File.Open(Path.Combine(output, "npc-catalogue-instructions.tsv"), FileMode.CreateNew));
        Writer.WriteLine("relative_frame\tpc\tentity\tra\tsp\ttimestamp\tinstruction\tcontext_tick\tentity_vtable\tentity_id\tcontext_state\tcontext_owner\tcontext_callback");
    }
    public void Begin(int frame) {
        Primary.Begin(frame);
        Host.Enter(); try {
            if (frame == ArmFrame) {
                if (Reset() != 1) throw new Exception("Catalogue reset failed");
                foreach (uint pc in Pcs) if (Add(pc) != 1) throw new Exception("Catalogue target rejected");
                if (Start() != 1) throw new Exception("Catalogue observer start failed");
            }
            BeginNative((uint)frame);
        } finally { Host.Exit(); }
    }
    public void Drain(int frame) {
        Primary.Drain(frame);
        Host.Enter(); try {
            uint count = Count();
            if (count > 1024 || Overflow() != 0) throw new Exception("Catalogue instruction trace overflow");
            int[] words = new int[checked((int)count * 13)];
            if (count != 0) Marshal.Copy(Events(), words, 0, words.Length);
            for (int row = 0; row < count; row++) {
                int at = row * 13;
                if (words[at] != frame || !Targets.Contains(unchecked((uint)words[at + 1])))
                    throw new Exception("Wrong catalogue observation boundary");
                if (First < 0) First = frame;
                Last = frame;
                var fields = new string[13];
                fields[0] = frame.ToString(CultureInfo.InvariantCulture);
                for (int col = 1; col < 13; col++)
                    fields[col] = col == 5 ? words[at + col].ToString(CultureInfo.InvariantCulture) :
                        col == 7 ? unchecked((uint)words[at + col]).ToString(CultureInfo.InvariantCulture) :
                        unchecked((uint)words[at + col]).ToString("X8", CultureInfo.InvariantCulture);
                Writer.WriteLine(String.Join("\t", fields));
            }
            CatalogueTotal += count;
            if (CatalogueTotal != NativeTotal()) throw new Exception("Catalogue events were lost");
            if (frame % 300 == 0) Writer.Flush();
        } finally { Host.Exit(); }
    }
    public void Dispose() {
        Primary.Dispose();
        Writer.Dispose();
        File.WriteAllText(Path.Combine(Output, "npc-catalogue-summary.json"), new JavaScriptSerializer().Serialize(new {
            watched_pcs = Pcs, hook_enabled_relative_frame = ArmFrame, hook_enabled = Enabled,
            original_instruction_entries = CatalogueTotal, first_observed_entry_frame = First,
            last_observed_entry_frame = Last, event_words = 13, per_frame_capacity = 1024,
            game_RAM_injected = false, complete_state_parity_checked = false}));
    }
}
}
