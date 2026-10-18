// Static controller replay and optional original instruction-entry observation.
// This host neither restores states nor injects emulated game RAM.
using System;
using System.Collections.Generic;
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
internal static class RecordDispatchHistory {
    static string DllRoot;
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern bool SetDllDirectory(string path);
    static string Hash(byte[] value) {
        using (var hash = SHA256.Create())
            return BitConverter.ToString(hash.ComputeHash(value)).Replace("-", "").ToLowerInvariant();
    }
    public sealed class Settings {
        public int frames { get; set; }
        public int[] checkpoint_frames { get; set; }
        public int RAM_sample_interval { get; set; }
        public bool trace_enabled { get; set; }
        public int arm_frame { get; set; }
        public DispatchTarget[] dispatch_targets { get; set; }
        public uint[] dispatch_words { get; set; }
        public uint[] flow_sites { get; set; }
        public DispatchReturnSettings return_trace { get; set; }
    }
    static object SaveImage(Nymashock core, string output, int frame) {
        int width = core.BufferWidth, height = core.BufferHeight;
        int[] pixels = core.GetVideoBuffer();
        if (width < 1 || height < 1 || width > 2048 || height > 1024 || pixels.Length < width * height)
            throw new Exception("Unsupported native video dimensions");
        byte[] rgb = new byte[checked(width * height * 3)];
        using (var image = new Bitmap(width, height, PixelFormat.Format24bppRgb)) {
            var data = image.LockBits(new Rectangle(0, 0, width, height), ImageLockMode.WriteOnly, PixelFormat.Format24bppRgb);
            try {
                byte[] bgr = new byte[width * 3];
                for (int row = 0; row < height; row++) {
                    for (int col = 0; col < width; col++) {
                        int pixel = pixels[row * width + col], at = (row * width + col) * 3;
                        rgb[at] = (byte)(pixel >> 16); rgb[at + 1] = (byte)(pixel >> 8); rgb[at + 2] = (byte)pixel;
                        bgr[col * 3] = rgb[at + 2]; bgr[col * 3 + 1] = rgb[at + 1]; bgr[col * 3 + 2] = rgb[at];
                    }
                    Marshal.Copy(bgr, 0, IntPtr.Add(data.Scan0, row * data.Stride), bgr.Length);
                }
            } finally { image.UnlockBits(data); }
            image.Save(Path.Combine(output, "frame-" + frame + ".png"), ImageFormat.Png);
        }
        File.WriteAllBytes(Path.Combine(output, "rgb-" + frame + ".bin"), rgb);
        return new {width = width, height = height, RGB_sha256 = Hash(rgb)};
    }
    public static int Main(string[] args) {
        try {
            if (args.Length != 8) throw new Exception("Expected runtime, cue, three BIOS files, inputs, settings and new output");
            DllRoot = Path.Combine(args[0], "dll");
            AppDomain.CurrentDomain.AssemblyResolve += delegate(object sender, ResolveEventArgs ev) {
                string path = Path.Combine(DllRoot, new AssemblyName(ev.Name).Name + ".dll");
                return File.Exists(path) ? Assembly.LoadFrom(path) : null;
            };
            if (!SetDllDirectory(DllRoot)) throw new Exception("SetDllDirectory failed");
            return Run(args);
        } catch (Exception error) { Console.Error.WriteLine(error); return 2; }
    }
    static int Run(string[] args) {
        var serializer = new JavaScriptSerializer();
        var settings = serializer.Deserialize<Settings>(File.ReadAllText(args[6]));
        string output = args[7];
        if (Directory.Exists(output) || File.Exists(output)) throw new Exception("Preserve existing output");
        if (settings.frames < 1 || settings.frames > 30000 || settings.RAM_sample_interval < 1 ||
            settings.checkpoint_frames == null || settings.checkpoint_frames.Any(frame => frame < 0 || frame > settings.frames))
            throw new Exception("Unsupported recording boundaries");
        var checkpoints = new HashSet<int>(settings.checkpoint_frames);
        if (checkpoints.Count != settings.checkpoint_frames.Length || !checkpoints.Contains(0) || !checkpoints.Contains(settings.frames))
            throw new Exception("Incomplete or repeated checkpoint boundaries");
        string[][] submitted = File.ReadAllLines(args[5]).Select(line => line.Split('\t')).ToArray();
        if (submitted.Length != settings.frames + 1) throw new Exception("Incomplete controller program");
        Directory.CreateDirectory(output);
        Database.InitializeDatabase(Path.Combine(args[0], "gamedb"), output, true);
        var comm = new CoreComm(message => Console.Error.WriteLine(message),
            (message, duration) => Console.Error.WriteLine(message),
            new ReplayColdStart.Files(new[] {args[2], args[3], args[4]}, output), (CoreComm.CorePreferencesFlags)0, null);
        using (var disc = Disc.LoadAutomagic(args[1])) {
            var parameters = new CoreLoadParameters<NymaCore.NymaSettings, NymaCore.NymaSyncSettings> {
                Comm = comm, Game = new GameInfo {Name = "LSD original controller-only navigation", System = "PSX"},
                Settings = null, SyncSettings = null, Roms = new List<IRomAsset>(),
                Discs = new List<IDiscAsset> {new ReplayColdStart.DiscAsset(disc, "LSD Japanese")},
                DeterministicEmulationRequested = false};
            using (var core = new Nymashock(parameters)) {
                var input = new ReplayColdStart.Input(core.ControllerDefinition);
                var domains = core.ServiceProvider.GetService<IMemoryDomains>();
                var gpu = domains["GPURAM"];
                if (domains.MainMemory.Size != 0x200000 || gpu.Size != 0x100000 ||
                    submitted[0].Length != input.Buttons.Count + input.Axes.Count + 4 ||
                    !new HashSet<string>(submitted[0].Skip(4)).SetEquals(input.Buttons.Keys.Concat(input.Axes.Keys)))
                    throw new Exception("Unsupported native domains or controller definition");
                byte[] ram = new byte[0x200000], gpuRaw = new byte[0x100000];
                long totalSamples = 0;
                int ramSamples = 0;
                var checkpointRows = new List<object>();
                DispatchInstructionTrace observer = settings.trace_enabled ?
                    new DispatchInstructionTrace(core, output, settings.dispatch_targets,
                        settings.dispatch_words, settings.arm_frame, settings.flow_sites, settings.return_trace) : null;
                using (observer)
                using (var frames = new StreamWriter(File.Open(Path.Combine(output, "frames.tsv"), FileMode.CreateNew)))
                using (var memory = new StreamWriter(File.Open(Path.Combine(output, "ram-samples.tsv"), FileMode.CreateNew)))
                using (var pcm = new BinaryWriter(File.Open(Path.Combine(output, "audio.pcm"), FileMode.CreateNew))) {
                    frames.WriteLine("relative_frame\tcore_frame\tphase\tgpu_sha256\tsample_frames\ttotal_sample_frames");
                    memory.WriteLine("relative_frame\tcore_frame\tRAM_sha256");
                    for (int frame = 0; frame <= settings.frames; frame++) {
                        string phase = "initial_neutral";
                        if (frame != 0) {
                            string[] row = submitted[frame];
                            if (row.Length != submitted[0].Length || row[0] != frame.ToString() || row[1] != core.Frame.ToString())
                                throw new Exception("Wrong controller input boundary");
                            phase = row[2];
                            for (int index = 4; index < row.Length; index++) {
                                string name = submitted[0][index];
                                if (input.Buttons.ContainsKey(name)) input.Buttons[name] = Boolean.Parse(row[index]);
                                else input.Axes[name] = Int32.Parse(row[index], CultureInfo.InvariantCulture);
                            }
                        }
                        if (observer != null) observer.Begin(frame);
                        core.FrameAdvance(input, true, true);
                        if (observer != null) observer.Drain(frame);
                        short[] samples; int count;
                        core.GetSamplesSync(out samples, out count);
                        if (count < 0 || count * 2 > samples.Length) throw new Exception("Invalid native PCM count");
                        byte[] bytes = new byte[count * 4];
                        Buffer.BlockCopy(samples, 0, bytes, 0, bytes.Length); pcm.Write(bytes); totalSamples += count;
                        gpu.BulkPeekByte(0L.RangeTo(gpuRaw.LongLength - 1), gpuRaw);
                        string gpuHash = Hash(gpuRaw);
                        frames.WriteLine(String.Join("\t", frame, core.Frame, phase, gpuHash, count, totalSamples));
                        if (frame % settings.RAM_sample_interval == 0 || checkpoints.Contains(frame)) {
                            domains.MainMemory.BulkPeekByte(0L.RangeTo(ram.LongLength - 1), ram);
                            memory.WriteLine(String.Join("\t", frame, core.Frame, Hash(ram))); ramSamples++;
                        }
                        if (checkpoints.Contains(frame)) {
                            File.WriteAllBytes(Path.Combine(output, "mainram-" + frame + ".bin"), ram);
                            File.WriteAllBytes(Path.Combine(output, "gpu-" + frame + ".bin"), gpuRaw);
                            object image = SaveImage(core, output, frame);
                            checkpointRows.Add(new {relative_frame = frame, core_frame = core.Frame,
                                RAM_sha256 = Hash(ram), GPU_sha256 = gpuHash, image = image});
                        }
                        if (frame % 600 == 0 || frame == settings.frames) {
                            frames.Flush(); memory.Flush(); pcm.Flush();
                            Console.WriteLine("PROGRESS " + serializer.Serialize(new {frame = frame, instruction_entries = observer == null ? 0 : observer.Total}));
                        }
                    }
                }
                File.WriteAllText(Path.Combine(output, "report.json"), serializer.Serialize(new {
                    status = "recorded_static_method_history", frames_advanced = settings.frames + 1,
                    submitted_frames = settings.frames, RAM_samples = ramSamples, checkpoints = checkpointRows.ToArray(),
                    all_PCM_sample_frames = totalSamples, instruction_entries = observer == null ? 0 : observer.Total,
                    observer_requested = settings.trace_enabled, observer_enabled = observer != null && observer.Enabled,
                    restored_state = false, game_RAM_injected = false, emulator_UI_controlled = false,
                    complete_state_parity_checked = false, original_hardware_timing_verified = false}));
                return 0;
            }
        }
    }
}
}
