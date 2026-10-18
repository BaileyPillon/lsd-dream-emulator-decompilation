// Replay recorded controller values through the original BizHawk PS1 core.
// This managed analysis host neither restores states nor injects game RAM.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Web.Script.Serialization;
using BizHawk.Common;
using BizHawk.Emulation.Common;
using BizHawk.Emulation.Cores;
using BizHawk.Emulation.Cores.Sony.PSX;
using BizHawk.Emulation.Cores.Waterbox;
using BizHawk.Emulation.DiscSystem;

namespace Lsd.Research.Headless {
internal static class ReplayColdStart {
    static string DllRoot;
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern bool SetDllDirectory(string path);
    static string Hash(byte[] value) {
        using (var hash = SHA256.Create())
            return BitConverter.ToString(hash.ComputeHash(value)).Replace("-", "").ToLowerInvariant();
    }
    internal sealed class Files : ICoreFileProvider {
        readonly string[] Bios;
        readonly string Output;
        public Files(string[] bios, string output) { Bios = bios; Output = output; }
        public string GetRetroSaveRAMDirectory(string system) { return Output; }
        public string GetRetroSystemPath(string system) { return Path.GetDirectoryName(Bios[0]); }
        public string GetUserPath(string system, bool temp) { return Output; }
        public byte[] GetFirmware(FirmwareID id, string message) { return GetFirmwareOrThrow(id, message); }
        public byte[] GetFirmwareOrThrow(FirmwareID id, string message) {
            if (id.System != "PSX") throw new Exception("Unexpected firmware system: " + id.System);
            int index = Array.IndexOf(new[] {"J", "U", "E"}, id.Firmware);
            if (index < 0) throw new Exception("Unexpected firmware: " + id.Firmware);
            byte[] value = File.ReadAllBytes(Bios[index]);
            if (value.Length != 524288) throw new Exception("Unexpected BIOS size");
            return value;
        }
        public ValueTuple<byte[], GameInfo> GetFirmwareWithGameInfoOrThrow(FirmwareID id, string message) {
            return new ValueTuple<byte[], GameInfo>(GetFirmwareOrThrow(id, message), new GameInfo());
        }
    }
    internal sealed class DiscAsset : IDiscAsset {
        public Disc DiscData { get; private set; }
        public DiscType DiscType { get; private set; }
        public string DiscName { get; set; }
        public DiscAsset(Disc disc, string name) {
            DiscData = disc; DiscName = name; DiscType = new DiscIdentifier(disc).DetectDiscType();
        }
    }
    internal sealed class Input : IController {
        public ControllerDefinition Definition { get; private set; }
        public readonly Dictionary<string, bool> Buttons = new Dictionary<string, bool>();
        public readonly Dictionary<string, int> Axes = new Dictionary<string, int>();
        public Input(ControllerDefinition definition) {
            Definition = definition;
            foreach (string name in definition.BoolButtons) Buttons.Add(name, false);
            foreach (var axis in definition.Axes) Axes.Add(axis.Key, axis.Value.Neutral);
        }
        public bool IsPressed(string name) { return Buttons[name]; }
        public int AxisValue(string name) { return Axes[name]; }
        public IReadOnlyCollection<ValueTuple<string, int>> GetHapticsSnapshot() {
            return new ValueTuple<string, int>[0];
        }
        public void SetHapticChannelStrength(string name, int strength) { }
    }
    public static int Main(string[] args) {
        try {
            DllRoot = Path.Combine(args[0], "dll");
            AppDomain.CurrentDomain.AssemblyResolve += delegate(object sender, ResolveEventArgs ev) {
                string path = Path.Combine(DllRoot, new AssemblyName(ev.Name).Name + ".dll");
                return File.Exists(path) ? Assembly.LoadFrom(path) : null;
            };
            if (!SetDllDirectory(DllRoot)) throw new Exception("SetDllDirectory failed");
            return Run(args);
        } catch (Exception error) { Console.Error.WriteLine(error); return 2; }
    }
    sealed class FrameComparison {
        public int DifferentRGBPixels;
        public bool PNGFileEqual;
    }
    static FrameComparison SaveFrame(Nymashock core, string output, string capture, int frame) {
        int width = core.BufferWidth, height = core.BufferHeight;
        int[] pixels = core.GetVideoBuffer();
        string outputPath = Path.Combine(output, "frame-" + frame + ".png");
        string referencePath = Path.Combine(capture, "frame-" + frame + ".png");
        using (var image = new Bitmap(width, height, PixelFormat.Format24bppRgb)) {
            BitmapData data = image.LockBits(new Rectangle(0, 0, width, height),
                ImageLockMode.WriteOnly, PixelFormat.Format24bppRgb);
            try {
                byte[] line = new byte[width * 3];
                for (int row = 0; row < height; row++) {
                    for (int col = 0; col < width; col++) {
                        int pixel = pixels[row * width + col];
                        line[col * 3] = (byte)pixel;
                        line[col * 3 + 1] = (byte)(pixel >> 8);
                        line[col * 3 + 2] = (byte)(pixel >> 16);
                    }
                    Marshal.Copy(line, 0, IntPtr.Add(data.Scan0, row * data.Stride), line.Length);
                }
            } finally { image.UnlockBits(data); }
            image.Save(outputPath, ImageFormat.Png);
        }
        int different = 0;
        using (var reference = new Bitmap(referencePath)) {
            if (reference.Width != width || reference.Height != height)
                throw new Exception("Reference RGB dimensions differ");
            BitmapData data = reference.LockBits(new Rectangle(0, 0, width, height),
                ImageLockMode.ReadOnly, PixelFormat.Format24bppRgb);
            try {
                byte[] line = new byte[width * 3];
                for (int row = 0; row < height; row++) {
                    Marshal.Copy(IntPtr.Add(data.Scan0, row * data.Stride), line, 0, line.Length);
                    for (int col = 0; col < width; col++) {
                        int expected = line[col * 3] | (line[col * 3 + 1] << 8) | (line[col * 3 + 2] << 16);
                        // The native video provider supplies XRGB; its high byte is not a game color channel.
                        if ((pixels[row * width + col] & 0xFFFFFF) != expected) different++;
                    }
                }
            } finally { reference.UnlockBits(data); }
        }
        return new FrameComparison { DifferentRGBPixels = different,
            PNGFileEqual = File.ReadAllBytes(outputPath).SequenceEqual(File.ReadAllBytes(referencePath)) };
    }
    static int Run(string[] args) {
        string cue = args[1], capture = args[5], output = args[6];
        int frames = Int32.Parse(args[7], CultureInfo.InvariantCulture);
        if (Directory.Exists(output) || File.Exists(output)) throw new Exception("Preserve existing output");
        if (frames < 0 || frames > 30000) throw new Exception("Recorded profile supports at most 30000 frames");
        string[][] submissions = File.ReadAllLines(Path.Combine(capture, "submitted.tsv"))
            .Select(line => line.Split('\t')).ToArray();
        string[][] native = File.ReadAllLines(Path.Combine(capture, "cold-start.tsv"))
            .Select(line => line.Split('\t')).ToArray();
        if (submissions.Length < frames + 1 || native.Length < frames + 2)
            throw new Exception("Recorded inputs or observations are incomplete");
        int gpuColumn = Array.IndexOf(native[0], "gpu_sha256");
        if (gpuColumn < 0) throw new Exception("Missing recorded GPU identity");
        Directory.CreateDirectory(output);
        Database.InitializeDatabase(Path.Combine(args[0], "gamedb"), output, true);
        string[] bios = {args[2], args[3], args[4]};
        var comm = new CoreComm(message => Console.Error.WriteLine("CORE: " + message),
            (message, duration) => Console.Error.WriteLine("CORE: " + message), new Files(bios, output),
            (CoreComm.CorePreferencesFlags)0, null);
        var serializer = new JavaScriptSerializer();
        using (var disc = Disc.LoadAutomagic(cue)) {
            var parameters = new CoreLoadParameters<NymaCore.NymaSettings, NymaCore.NymaSyncSettings> {
                Comm = comm, Game = new GameInfo { Name = "LSD Japanese headless research", System = "PSX" },
                Settings = null, SyncSettings = null, Roms = new List<IRomAsset>(),
                Discs = new List<IDiscAsset> {new DiscAsset(disc, "LSD Japanese")},
                DeterministicEmulationRequested = false
            };
            using (var core = new Nymashock(parameters)) {
                var input = new Input(core.ControllerDefinition);
                var domains = core.ServiceProvider.GetService<IMemoryDomains>();
                if (submissions[0].Length != input.Buttons.Count + input.Axes.Count + 4)
                    throw new Exception("Incomplete controller submission schema");
                var gpu = domains["GPURAM"];
                if (domains.MainMemory.Size != 0x200000 || gpu.Size != 0x100000)
                    throw new Exception("Wrong complete native memory domains");
                Console.WriteLine("CORE_READY " + serializer.Serialize(new {
                    pid = Process.GetCurrentProcess().Id, core = core.GetType().FullName,
                    frame = core.Frame, bool_controls = input.Buttons.Count, axes = input.Axes.Count
                }));
                var rows = new List<object>();
                var timer = Stopwatch.StartNew();
                int gpuDifferences = 0, ramDifferences = 0, rgbDifferences = 0, pngDifferences = 0, firstSamples = 0;
                long samplesTotal = 0;
                byte[] gpuRaw = new byte[0x100000];
                using (var pcm = new BinaryWriter(File.Open(Path.Combine(output, "audio.pcm"), FileMode.CreateNew)))
                using (var trace = new StreamWriter(File.Open(Path.Combine(output, "headless.tsv"), FileMode.CreateNew))) {
                    trace.WriteLine("relative_frame\tcore_frame\tphase\tgpu_sha256\tgpu_equal\tsample_frames\ttotal_sample_frames");
                    for (int frame = 0; frame <= frames; frame++) {
                        string phase = "initial_neutral";
                        if (frame != 0) {
                            string[] record = submissions[frame];
                            if (record.Length != submissions[0].Length || record[0] != frame.ToString()
                                || record[1] != core.Frame.ToString()) throw new Exception("Wrong input boundary");
                            phase = record[2];
                            for (int index = 4; index < record.Length; index++) {
                                string name = submissions[0][index];
                                if (input.Buttons.ContainsKey(name)) input.Buttons[name] = Boolean.Parse(record[index]);
                                else if (input.Axes.ContainsKey(name)) input.Axes[name] = Int32.Parse(record[index], CultureInfo.InvariantCulture);
                                else throw new Exception("Unknown recorded control: " + name);
                            }
                        }
                        core.FrameAdvance(input, true, true);
                        short[] samples; int sampleCount;
                        core.GetSamplesSync(out samples, out sampleCount);
                        if (sampleCount < 0 || sampleCount * 2 > samples.Length) throw new Exception("Invalid PCM count");
                        byte[] pcmBytes = new byte[sampleCount * 4];
                        Buffer.BlockCopy(samples, 0, pcmBytes, 0, pcmBytes.Length);
                        pcm.Write(pcmBytes);
                        if (frame == 0) firstSamples = sampleCount;
                        samplesTotal += sampleCount;
                        gpu.BulkPeekByte(0L.RangeTo(gpuRaw.LongLength - 1), gpuRaw);
                        string gpuHash = Hash(gpuRaw);
                        string[] expected = native[frame + 1];
                        if (expected[0] != frame.ToString() || expected[1] != core.Frame.ToString())
                            throw new Exception("Wrong recorded native boundary");
                        bool gpuEqual = String.Equals(gpuHash, expected[gpuColumn], StringComparison.OrdinalIgnoreCase);
                        if (!gpuEqual) gpuDifferences++;
                        trace.WriteLine(String.Join("\t", frame, core.Frame, phase, gpuHash, gpuEqual, sampleCount, samplesTotal));
                        string referencePath = Path.Combine(capture, "mainram-" + frame + ".bin");
                        if (File.Exists(referencePath)) {
                            var raw = new byte[0x200000];
                            domains.MainMemory.BulkPeekByte(0L.RangeTo(raw.LongLength - 1), raw);
                            byte[] reference = File.ReadAllBytes(referencePath);
                            if (reference.Length != raw.Length) throw new Exception("Truncated reference MainRAM");
                            int differences = 0;
                            for (int index = 0; index < raw.Length; index++) if (raw[index] != reference[index]) differences++;
                            ramDifferences += differences;
                            File.WriteAllBytes(Path.Combine(output, "mainram-" + frame + ".bin"), raw);
                            File.WriteAllBytes(Path.Combine(output, "gpu-" + frame + ".bin"), gpuRaw);
                            FrameComparison image = SaveFrame(core, output, capture, frame);
                            rgbDifferences += image.DifferentRGBPixels;
                            if (!image.PNGFileEqual) pngDifferences++;
                            var row = new {relative_frame = frame, core_frame = core.Frame, RAM_sha256 = Hash(raw),
                                differing_RAM_bytes = differences, differing_RGB_pixels = image.DifferentRGBPixels,
                                PNG_file_byte_equal = image.PNGFileEqual, elapsed_ms = timer.ElapsedMilliseconds};
                            rows.Add(row);
                            Console.WriteLine("CHECKPOINT " + serializer.Serialize(row));
                        }
                        if (frame % 600 == 0 || frame == frames) {
                            trace.Flush(); pcm.Flush();
                            Console.WriteLine("PROGRESS " + serializer.Serialize(new {frame = frame,
                                differing_GPU_observations = gpuDifferences, elapsed_ms = timer.ElapsedMilliseconds}));
                        }
                    }
                }
                bool passed = gpuDifferences == 0 && ramDifferences == 0 && rgbDifferences == 0;
                File.WriteAllText(Path.Combine(output, "report.json"), serializer.Serialize(new {
                    status = passed ? "passed_isolated_recorded_cold_replay" : "recorded_headless_replay_differences",
                    frames_advanced = frames + 1, submitted_frames_replayed = frames,
                    restored_state = false, game_RAM_injected = false, emulator_UI_controlled = false,
                    rows = rows.ToArray(), differing_GPU_observations = gpuDifferences,
                    differing_MainRAM_bytes = ramDifferences, differing_RGB_pixels = rgbDifferences,
                    differing_PNG_files = pngDifferences, PNG_file_identity_required = false,
                    all_PCM_sample_frames = samplesTotal,
                    initial_observer_frame_PCM_sample_frames = firstSamples,
                    no_callback_execution_trace_collected = true, complete_state_parity_checked = false
                }));
                return passed ? 0 : 2;
            }
        }
    }
}
}
