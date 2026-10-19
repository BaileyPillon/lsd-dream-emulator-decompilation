// Raw IStatable observations. This class never loads a state or writes game RAM.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using BizHawk.Common;
using BizHawk.Emulation.Common;
using BizHawk.Emulation.Cores.Sony.PSX;

namespace Lsd.Research.Headless {
internal sealed class SerializedCoreStateTrace {
    readonly string Output;
    readonly List<object> Rows = new List<object>();
    const int MaxStateBytes = 256 * 1024 * 1024;
    static string Hash(byte[] bytes) {
        using (var hash = SHA256.Create())
            return BitConverter.ToString(hash.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
    }
    static byte[] Save(IStatable core) {
        using (var memory = new MemoryStream()) {
            using (var writer = new BinaryWriter(memory, Encoding.UTF8, true)) {
                core.SaveStateBinary(writer); writer.Flush();
            }
            if (memory.Length < 1 || memory.Length > MaxStateBytes)
                throw new Exception("Unsupported serialized core-state size");
            return memory.ToArray();
        }
    }
    public SerializedCoreStateTrace(string output) { Output = output; }
    public void Capture(Nymashock core, IMemoryDomains domains, MemoryDomain gpu,
                        int frame, byte[] beforeRAM, byte[] beforeGPU) {
        int beforeFrame = core.Frame;
        byte[] first = Save(core), second = Save(core);
        string file = "core-state-" + frame + ".bin";
        using (var stream = File.Open(Path.Combine(Output, file), FileMode.CreateNew))
            stream.Write(first, 0, first.Length);
        bool repeated = first.SequenceEqual(second);
        if (!repeated) {
            using (var stream = File.Open(Path.Combine(Output, "core-state-repeat-" + frame + ".bin"), FileMode.CreateNew))
                stream.Write(second, 0, second.Length);
        }
        byte[] afterRAM = new byte[beforeRAM.Length], afterGPU = new byte[beforeGPU.Length];
        domains.MainMemory.BulkPeekByte(0L.RangeTo(afterRAM.LongLength - 1), afterRAM);
        gpu.BulkPeekByte(0L.RangeTo(afterGPU.LongLength - 1), afterGPU);
        bool ramEqual = beforeRAM.SequenceEqual(afterRAM), gpuEqual = beforeGPU.SequenceEqual(afterGPU);
        var row = new {relative_frame = frame, core_frame = core.Frame, before_core_frame = beforeFrame,
            file = file, bytes = first.Length, sha256 = Hash(first), repeat_bytes = second.Length,
            repeat_sha256 = Hash(second), same_frame_serializations_equal = repeated,
            MainRAM_before_sha256 = Hash(beforeRAM), MainRAM_after_sha256 = Hash(afterRAM),
            GPURAM_before_sha256 = Hash(beforeGPU), GPURAM_after_sha256 = Hash(afterGPU),
            MainRAM_unchanged = ramEqual, GPURAM_unchanged = gpuEqual,
            core_frame_unchanged = beforeFrame == core.Frame,
            deterministic_emulation = core.DeterministicEmulation};
        Rows.Add(row);
        File.WriteAllText(Path.Combine(Output, "core-state-" + frame + ".json"),
                          new JavaScriptSerializer().Serialize(row));
        if (!repeated || !ramEqual || !gpuEqual || beforeFrame != core.Frame)
            throw new Exception("Core-state capture changed repeated state, frame count or observed memory");
    }
    public void Complete(int frames) {
        File.WriteAllText(Path.Combine(Output, "serialized-state-summary.json"),
            new JavaScriptSerializer().Serialize(new {schema_version = 1,
                status = "recorded_repeated_serialized_core_states", contract = "BizHawk.IStatable",
                frames_advanced = frames + 1, checkpoints = Rows.ToArray(), serializations_per_checkpoint = 2,
                second_complete_bytes_retained_on_mismatch = true, state_restored = false,
                game_RAM_injected = false, emulator_UI_controlled = false,
                complete_state_parity_checked = false, original_hardware_timing_verified = false}));
    }
}
}
