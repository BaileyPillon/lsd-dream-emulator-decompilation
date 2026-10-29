// Short serializer-equivalence check; controller-only, no state loading or RAM writes.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Web.Script.Serialization;
using BizHawk.Common;
using BizHawk.Emulation.Common;
using BizHawk.Emulation.Cores;
using BizHawk.Emulation.Cores.Sony.PSX;
using BizHawk.Emulation.Cores.Waterbox;
using BizHawk.Emulation.DiscSystem;

namespace Lsd.Research.Headless {
internal static class StateHashCompatibility {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern bool SetDllDirectory(string path);
    static readonly JavaScriptSerializer Json = new JavaScriptSerializer();
    static string Hex(byte[] bytes) { return BitConverter.ToString(bytes).Replace("-", "").ToLowerInvariant(); }
    static string Hash(byte[] data) { using (var hash=SHA256.Create()) return Hex(hash.ComputeHash(data)); }
    static string Domain(MemoryDomain domain) {
        var bytes=new byte[checked((int)domain.Size)];
        domain.BulkPeekByte(0L.RangeTo(bytes.LongLength-1),bytes);
        return Hash(bytes);
    }
    static Tuple<string,long,long> Buffered(Nymashock core) {
        using (var memory=new MemoryStream()) {
            using (var writer=new BinaryWriter(memory,Encoding.UTF8,true)) {
                ((IStatable)core).SaveStateBinary(writer);writer.Flush();
            }
            if (memory.Length<1 || memory.Length>256L*1024*1024) throw new Exception("Invalid state size");
            var copy=memory.ToArray();
            return Tuple.Create(Hash(copy),memory.Length,(long)memory.Capacity+copy.LongLength);
        }
    }
    static Tuple<string,long> Streaming(Nymashock core) {
        using (var stream=new BoundedSha256Stream(256L*1024*1024)) {
            using (var writer=new BinaryWriter(stream,Encoding.UTF8,true)) {
                ((IStatable)core).SaveStateBinary(writer);writer.Flush();
            }
            if (stream.Length<1) throw new Exception("Empty serialized state");
            return Tuple.Create(stream.CompleteHash(),stream.Length);
        }
    }
    public static int Main(string[] args) {
        try {
            string dll=args[1];
            AppDomain.CurrentDomain.AssemblyResolve += delegate(object sender,ResolveEventArgs ev) {
                string p=Path.Combine(dll,new AssemblyName(ev.Name).Name+".dll");return File.Exists(p)?Assembly.LoadFrom(p):null;
            };
            if (!SetDllDirectory(dll)) throw new Exception("SetDllDirectory failed");
            return Run(args);
        } catch (Exception error) {Console.Error.WriteLine(error);return 2;}
    }
    static int Run(string[] args) {
        string output=args[6];
        if (Directory.Exists(output)) throw new Exception("Choose a new private output");
        Directory.CreateDirectory(output);
        Database.InitializeDatabase(Path.Combine(args[0],"gamedb"),output,true);
        var comm=new CoreComm(m=>Console.Error.WriteLine(m),(m,d)=>Console.Error.WriteLine(m),
            new ReplayColdStart.Files(new[]{args[3],args[4],args[5]},output),(CoreComm.CorePreferencesFlags)0,null);
        var rows=new List<object>();
        Type progression=args.Length>7?Type.GetType(args[7],true):typeof(YearProgression);
        using (var disc=Disc.LoadAutomagic(args[2])) {
            var parameters=new CoreLoadParameters<NymaCore.NymaSettings,NymaCore.NymaSyncSettings> {
                Comm=comm,Game=new GameInfo{Name="LSD bounded state-hash equivalence",System="PSX"},Settings=null,SyncSettings=null,
                Roms=new List<IRomAsset>(),Discs=new List<IDiscAsset>{new ReplayColdStart.DiscAsset(disc,"LSD Japanese")},
                DeterministicEmulationRequested=false};
            using (var core=new Nymashock(parameters)) {
                var domains=core.ServiceProvider.GetService<IMemoryDomains>();
                var ram=domains.MainMemory;var gpu=domains["GPURAM"];
                var input=new ReplayColdStart.Input(core.ControllerDefinition);
                foreach (int target in new[]{0,1,60,300}) {
                    while (core.Frame<target) {
                        core.FrameAdvance(input,true,true);
                        short[] samples;int count;core.GetSamplesSync(out samples,out count);
                        if (count<0 || count*2>samples.Length) throw new Exception("Invalid PCM count");
                    }
                    int frame=core.Frame;string beforeRam=Domain(ram),beforeGpu=Domain(gpu);
                    var buffered=Buffered(core);var streamed=Streaming(core);var repeated=Streaming(core);
                    var method=progression.GetMethod("StateHash",BindingFlags.Static|BindingFlags.NonPublic);
                    string integrated=(string)method.Invoke(null,new object[]{core});
                    if (integrated!=streamed.Item1) throw new Exception("Integrated progression hash differs");
                    if (buffered.Item1!=streamed.Item1 || streamed.Item1!=repeated.Item1
                        || buffered.Item2!=streamed.Item2 || streamed.Item2!=repeated.Item2 || frame!=core.Frame)
                        throw new Exception("Serialized stream equivalence failed");
                    if (Domain(ram)!=beforeRam || Domain(gpu)!=beforeGpu) throw new Exception("State save changed RAM/GPU");
                    var resourceMethod=progression.GetMethod("ResourceUsage",BindingFlags.Static|BindingFlags.NonPublic);
                    object measured=resourceMethod.Invoke(null,null);
                    long lastBytes=(long)measured.GetType().GetProperty("last_serialized_state_bytes").GetValue(measured,null);
                    if (lastBytes!=streamed.Item2) throw new Exception("Integrated resource counter differs");
                    rows.Add(new {frame=frame,integrated_progression_wrapper_checked=true,state_sha256=streamed.Item1,state_bytes=streamed.Item2,
                        buffered_state_array_bytes=buffered.Item3,stream_own_input_buffer_bytes=1,
                        full_RAM_sha256=beforeRam,full_GPU_sha256=beforeGpu,resources=measured});
                    File.WriteAllText(Path.Combine(output,"progress.json"),Json.Serialize(new {frame=frame,verified=rows.Count}));
                }
            }
        }
        File.WriteAllText(Path.Combine(output,"report.json"),Json.Serialize(new {status="verified_bounded_state_hash_equivalence",
            checks=rows,progression_hash_type=progression.FullName,core_frame_ceiling=300,buffered_and_streamed_serialization_calls=20,
            game_RAM_injected=false,restored_state=false,emulator_UI_controlled=false,
            full_year_restarted=false,original_failure_root_cause_established=false,
            original_game_feature_accepted=false}));
        Console.WriteLine(Json.Serialize(new {status="verified_bounded_state_hash_equivalence",checkpoints=rows.Count}));
        return 0;
    }
}
}
