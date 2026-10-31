// Bounded cold-start movie observation. No state load, game write or player UI.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.IO.Compression;
using System.Linq;
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
internal static class RecordOpeningAttract {
    static readonly JavaScriptSerializer Json = new JavaScriptSerializer();
    static string DllRoot;
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern bool SetDllDirectory(string path);
    static uint Word(byte[] data,int offset) { return BitConverter.ToUInt32(data,offset); }
    static string Hash(byte[] data) {
        using(var hash=SHA256.Create()) return BitConverter.ToString(hash.ComputeHash(data)).Replace("-","").ToLowerInvariant();
    }
    static int Pointer(uint value,int size) {
        if(value<0x80010000 || value>0x80200000-size || value%4!=0) throw new Exception("Invalid native movie pointer");
        return (int)(value&0x1fffffff);
    }
    sealed class Observation {
        public bool ready;
        public uint active,cutoff,streamState,id;
        public string row;
    }
    static Observation Observe(byte[] ram,int frame,int coreFrame) {
        var value=new Observation();
        value.ready=Word(ram,0x6f61c)==0x800454c4 && Word(ram,0x8184c)==0x80047694;
        value.active=value.ready?Word(ram,0x8a940):0;
        var row=new List<string>{frame.ToString(),coreFrame.ToString(),value.ready?"1":"0",value.active.ToString(),
            value.ready?Word(ram,0x8ac68).ToString():"-",value.ready?Word(ram,0x8a948).ToString():"-"};
        int movie=0,stream=0;
        if(value.active!=0) {
            movie=Pointer(value.active,0x6c);
            if(Word(ram,movie)!=0x8006f614) throw new Exception("Movie vtable differs");
            stream=Pointer(Word(ram,movie+0x60),0x5c);
            if(Word(ram,stream)!=0x800817e0) throw new Exception("Stream vtable differs");
            value.cutoff=Word(ram,movie+0x5c); value.streamState=Word(ram,stream+0x2c); value.id=Word(ram,stream+0x58);
        }
        for(int at=0;at<0x6c;at+=4) row.Add(movie==0?"-":Word(ram,movie+at).ToString());
        for(int at=0;at<0x5c;at+=4) row.Add(stream==0?"-":Word(ram,stream+at).ToString());
        value.row=String.Join("\t",row)+"\n";
        return value;
    }
    static byte[] RGB(Nymashock core) {
        int w=core.BufferWidth,h=core.BufferHeight;
        if(w<1 || h<1 || w>1024 || h>1024) throw new Exception("Invalid video dimensions");
        int[] pixels=core.GetVideoBuffer(); var result=new byte[checked(8+w*h*3)];
        Buffer.BlockCopy(new[]{w,h},0,result,0,8);
        for(int at=0;at<w*h;at++) {
            result[8+at*3]=(byte)(pixels[at]>>16); result[9+at*3]=(byte)(pixels[at]>>8); result[10+at*3]=(byte)pixels[at];
        }
        return result;
    }
    static void Image(Nymashock core,string path) {
        byte[] rgb=RGB(core); int w=BitConverter.ToInt32(rgb,0),h=BitConverter.ToInt32(rgb,4);
        using(var image=new Bitmap(w,h,PixelFormat.Format24bppRgb)) {
            for(int y=0;y<h;y++) for(int x=0;x<w;x++) {
                int at=8+(y*w+x)*3; image.SetPixel(x,y,Color.FromArgb(rgb[at],rgb[at+1],rgb[at+2]));
            }
            image.Save(path,ImageFormat.Png);
        }
    }
    static string StateHash(Nymashock core,MemoryDomain ram,MemoryDomain gpu,byte[] beforeRAM,byte[] beforeGPU) {
        Func<string> save=()=> {
            using(var sink=new BoundedSha256Stream(256L*1024*1024)) {
                using(var writer=new BinaryWriter(sink,Encoding.UTF8,true)) { ((IStatable)core).SaveStateBinary(writer); writer.Flush(); }
                if(sink.Length==0) throw new Exception("Empty serialized state");
                return sink.CompleteHash();
            }
        };
        int frame=core.Frame; string first=save();
        if(first!=save() || core.Frame!=frame) throw new Exception("State serialization is unstable");
        byte[] afterRAM=new byte[beforeRAM.Length],afterGPU=new byte[beforeGPU.Length];
        ram.BulkPeekByte(0L.RangeTo(afterRAM.LongLength-1),afterRAM); gpu.BulkPeekByte(0L.RangeTo(afterGPU.LongLength-1),afterGPU);
        if(!beforeRAM.SequenceEqual(afterRAM) || !beforeGPU.SequenceEqual(afterGPU)) throw new Exception("State observation changed native memory");
        return first;
    }
    sealed class Window : IDisposable {
        readonly Dictionary<string,BoundedSha256Stream> Channels=new Dictionary<string,BoundedSha256Stream>();
        readonly Dictionary<string,long> Counts=new Dictionary<string,long>();
        public readonly int first;
        public long samples;
        public Window(int start) {
            first=start;
            foreach(string name in new[]{"MainRAM","GPURAM","RGB","PCM","native","controller"}) {
                Channels[name]=new BoundedSha256Stream(2L*1024*1024*1024); Counts[name]=0;
            }
        }
        public void Add(string name,int frame,int coreFrame,byte[] bytes) {
            byte[] header=new byte[12]; Buffer.BlockCopy(new[]{frame,coreFrame,bytes.Length},0,header,0,12);
            Channels[name].Write(header,0,12); Channels[name].Write(bytes,0,bytes.Length); Counts[name]+=bytes.Length;
        }
        public object Finish(int last,string state,byte[] ram,byte[] gpu,byte[] rgb) {
            return new {first_frame=first,last_frame=last,frames=last-first+1,PCM_sample_frames=samples,
                payload_bytes=Counts,framed_sha256=Channels.ToDictionary(pair=>pair.Key,pair=>pair.Value.CompleteHash()),
                complete_state_sha256=state,final_MainRAM_sha256=Hash(ram),final_GPURAM_sha256=Hash(gpu),
                final_RGB_with_dimensions_sha256=Hash(rgb)};
        }
        public void Dispose() { foreach(var channel in Channels.Values) channel.Dispose(); }
    }
    public static int Main(string[] args) {
        try {
            if(args.Length!=9) throw new Exception("runtime cue BIOS-J BIOS-U BIOS-E output mode ceiling replay-or-dash");
            DllRoot=Path.Combine(args[0],"dll");
            AppDomain.CurrentDomain.AssemblyResolve+=delegate(object sender,ResolveEventArgs ev) {
                string path=Path.Combine(DllRoot,new AssemblyName(ev.Name).Name+".dll"); return File.Exists(path)?Assembly.LoadFrom(path):null;
            };
            if(!SetDllDirectory(DllRoot)) throw new Exception("SetDllDirectory failed");
            return Run(args);
        } catch(Exception error) { Console.Error.WriteLine(error); return 2; }
    }
    static int Run(string[] args) {
        string output=args[5],mode=args[6]; int ceiling=Int32.Parse(args[7]);
        if(Directory.Exists(output) || File.Exists(output) || ceiling<1 || ceiling>170000 ||
            mode!="neutral") throw new Exception("Invalid fresh bounded request");
        string[][] replay=args[8]=="-"?null:File.ReadAllLines(args[8]).Skip(1).Select(line=>line.Split('\t')).ToArray();
        if(replay!=null && (replay.Length==0 || replay[0][0]!="0" || replay[0][1]!="0")) throw new Exception("Replay must start neutral");
        Directory.CreateDirectory(output);
        Database.InitializeDatabase(Path.Combine(args[0],"gamedb"),output,true);
        var comm=new CoreComm(m=>Console.Error.WriteLine(m),(m,d)=>Console.Error.WriteLine(m),
            new ReplayColdStart.Files(new[]{args[2],args[3],args[4]},output),(CoreComm.CorePreferencesFlags)0,null);
        using(var disc=Disc.LoadAutomagic(args[1])) {
            var parameters=new CoreLoadParameters<NymaCore.NymaSettings,NymaCore.NymaSyncSettings> {
                Comm=comm,Game=new GameInfo{Name="LSD Japanese native movie windows",System="PSX"},Settings=null,SyncSettings=null,
                Roms=new List<IRomAsset>(),Discs=new List<IDiscAsset>{new ReplayColdStart.DiscAsset(disc,"LSD Japanese")},DeterministicEmulationRequested=false};
            using(var core=new Nymashock(parameters)) {
                var domains=core.ServiceProvider.GetService<IMemoryDomains>(); var ram=domains.MainMemory; var gpu=domains["GPURAM"];
                if(ram.Size!=0x200000 || gpu.Size!=0x100000 || core.Frame!=0) throw new Exception("Unexpected cold core or memory domains");
                var input=new ReplayColdStart.Input(core.ControllerDefinition);
                if(!input.Buttons.ContainsKey("P1 \u25cb")) throw new Exception("Missing native confirm input");
                var ramBytes=new byte[0x200000]; var gpuBytes=new byte[0x100000];
                var header=new List<string>{"relative_frame","core_frame","native_tables_ready","active_movie","rng","watchdog_counter"};
                for(int at=0;at<0x6c;at+=4) header.Add("movie_"+at.ToString("x2"));
                for(int at=0;at<0x5c;at+=4) header.Add("stream_"+at.ToString("x2"));
                int firstOpeningCleared=-1,skipFrame=-1,lastMask=-1,replayIndex=0,mask=0,lastFrame=-1;
                var completedCutoffs=new HashSet<uint>(); int openingLifetimes=0;
                long totalSamples=0,rawTraceBytes=0; var previous=new Observation(); var clock=Stopwatch.StartNew();
                string outcome="frame_ceiling_reached";
                Window window=new Window(0);
                using(var file=File.Open(Path.Combine(output,"native.tsv.gz"),FileMode.CreateNew))
                using(var zipped=new GZipStream(file,CompressionLevel.Optimal))
                using(var native=new StreamWriter(zipped,new UTF8Encoding(false)))
                using(var inputs=new StreamWriter(File.Open(Path.Combine(output,"inputs.tsv"),FileMode.CreateNew),new UTF8Encoding(false)))
                using(var windows=new StreamWriter(File.Open(Path.Combine(output,"windows.jsonl"),FileMode.CreateNew),new UTF8Encoding(false))) {
                    native.NewLine="\n"; inputs.NewLine="\n"; windows.NewLine="\n";
                    native.WriteLine(String.Join("\t",header)); inputs.WriteLine("frame\tmask");
                    for(int frame=0;frame<=ceiling;frame++) {
                        if(File.Exists(Path.Combine(output,"STOP"))) { outcome="owned_stop_requested"; break; }
                        if(replay==null) {
                            if(skipFrame<0 && previous.active!=0 && previous.streamState==2 &&
                                ((mode=="skip-logo" && previous.cutoff==90 && previous.id>=20) ||
                                 (mode=="skip-opening" && previous.cutoff>=900 && previous.id>=120))) skipFrame=frame;
                            mask=skipFrame>=0 && frame>=skipFrame && frame<skipFrame+12?1:0;
                        } else if(replayIndex<replay.Length && Int32.Parse(replay[replayIndex][0])==frame) {
                            if(replayIndex>0 && Int32.Parse(replay[replayIndex][0])<=Int32.Parse(replay[replayIndex-1][0])) throw new Exception("Invalid replay order");
                            mask=Int32.Parse(replay[replayIndex][1]); replayIndex++;
                            if(mask==1 && skipFrame<0) skipFrame=frame;
                        }
                        if(mask<0 || mask>1) throw new Exception("Only ordinary Circle or neutral input is supported");
                        if(mask!=lastMask) { inputs.WriteLine(frame+"\t"+mask); lastMask=mask; }
                        input.Buttons["P1 \u25cb"]=mask==1; core.FrameAdvance(input,true,true);
                        if(core.Frame!=frame+1) throw new Exception("Core frame schedule changed");
                        ram.BulkPeekByte(0L.RangeTo(ramBytes.LongLength-1),ramBytes); gpu.BulkPeekByte(0L.RangeTo(gpuBytes.LongLength-1),gpuBytes);
                        var observed=Observe(ramBytes,frame,core.Frame); native.Write(observed.row);
                        byte[] nativeBytes=Encoding.UTF8.GetBytes(observed.row); rawTraceBytes+=nativeBytes.Length;
                        if(rawTraceBytes>96L*1024*1024) throw new Exception("Raw native journal ceiling exceeded");
                        short[] samples; int count; core.GetSamplesSync(out samples,out count);
                        if(count<0 || count>5000 || samples.Length<count*2) throw new Exception("Invalid returned PCM window");
                        byte[] pcm=new byte[count*4]; Buffer.BlockCopy(samples,0,pcm,0,pcm.Length);
                        byte[] rgb=RGB(core);
                        window.Add("MainRAM",frame,core.Frame,ramBytes); window.Add("GPURAM",frame,core.Frame,gpuBytes);
                        window.Add("RGB",frame,core.Frame,rgb); window.Add("PCM",frame,core.Frame,pcm);
                        window.Add("native",frame,core.Frame,nativeBytes); window.Add("controller",frame,core.Frame,BitConverter.GetBytes(mask));
                        totalSamples+=count; window.samples+=count;
                        if(previous.active!=0 && previous.cutoff>=900 && observed.active==0) {
                            if(!new uint[]{1060,1088,953,1179,979,1231,1046}.Contains(previous.cutoff)) throw new Exception("Unexpected opening threshold");
                            completedCutoffs.Add(previous.cutoff); openingLifetimes++;
                            if(completedCutoffs.Count==7 && firstOpeningCleared<0) firstOpeningCleared=frame;
                        }
                        bool routeComplete=firstOpeningCleared>=0 && frame>=firstOpeningCleared+180;
                        bool stop=frame==ceiling || routeComplete;
                        if(routeComplete) outcome="all_openings_cleared_and_post_window_completed";
                        if(frame%600==599 || stop) {
                            string state=StateHash(core,ram,gpu,ramBytes,gpuBytes);
                            windows.WriteLine(Json.Serialize(window.Finish(frame,state,ramBytes,gpuBytes,rgb))); windows.Flush();
                            window.Dispose(); window=stop?null:new Window(frame+1);
                            native.Flush(); inputs.Flush(); zipped.Flush();
                            if(file.Length>2*1024*1024) throw new Exception("Compressed native journal ceiling exceeded");
                            File.WriteAllText(Path.Combine(output,"progress.json"),Json.Serialize(new {frame=frame,core_frame=core.Frame,elapsed_ms=clock.ElapsedMilliseconds,compressed_native_bytes=file.Length,opening_cutoffs_completed=completedCutoffs.OrderBy(value=>value).ToArray(),opening_lifetimes_completed=openingLifetimes}));
                            Console.WriteLine("FRAME "+frame);
                        }
                        previous=observed; lastFrame=frame;
                        if(stop) break;
                    }
                    if(window!=null) window.Dispose();
                }
                Image(core,Path.Combine(output,"final.png"));
                if(replay!=null && replayIndex!=replay.Length) throw new Exception("Unconsumed recorded controller changes");
                File.WriteAllText(Path.Combine(output,"report.json"),Json.Serialize(new {schema_version=2,status=outcome,mode=mode,
                    frames_advanced=lastFrame+1,last_frame=lastFrame,total_PCM_sample_frames=totalSamples,
                    opening_cutoffs_completed=completedCutoffs.OrderBy(value=>value).ToArray(),opening_lifetimes_completed=openingLifetimes,all_openings_cleared_frame=firstOpeningCleared,post_all_openings_frames=firstOpeningCleared<0?0:lastFrame-firstOpeningCleared,
                    skip_submitted_frame=skipFrame,skip_pulse_frames=skipFrame<0?0:12,raw_native_bytes=rawTraceBytes,
                    replayed_inputs=replay!=null,cold_start=true,restored_state=false,game_RAM_injected=false,
                    player_UI_or_saves_accessed=false,hardware_timing_verified=false,whole_feature_groups_accepted=0,
                    controller_buttons=input.Buttons.Keys.OrderBy(n=>n).ToArray(),controller_neutral_axes=input.Axes,
                    elapsed_ms=clock.ElapsedMilliseconds}));
                return outcome=="all_openings_cleared_and_post_window_completed"?0:1;
            }
        }
    }
}
}
