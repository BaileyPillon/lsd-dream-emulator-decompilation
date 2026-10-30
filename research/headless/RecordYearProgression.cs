// Private bounded controller-only progression study. Never loads state or writes game RAM.
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
using System.Text;
using System.Web.Script.Serialization;
using BizHawk.Common;
using BizHawk.Emulation.Common;
using BizHawk.Emulation.Cores;
using BizHawk.Emulation.Cores.Sony.PSX;
using BizHawk.Emulation.Cores.Waterbox;
using BizHawk.Emulation.DiscSystem;

namespace Lsd.Research.Headless {
internal static class YearProgressionEnding {
    const uint DreamVtable = 0x80087bdc, MenuVtable = 0x80086b60;
    const long OutputLimit = 16L * 1024 * 1024;
    static string DllRoot, Output;
    static long RetainedBytes;
    static long LastSerializedStateBytes;
    static readonly JavaScriptSerializer Json = new JavaScriptSerializer();
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern bool SetDllDirectory(string path);
    static string Hash(byte[] value) {
        using (var h = SHA256.Create()) return BitConverter.ToString(h.ComputeHash(value)).Replace("-", "").ToLowerInvariant();
    }
    static void Line(StreamWriter writer, string value) {
        RetainedBytes += Encoding.UTF8.GetByteCount(value) + 2;
        if (RetainedBytes > OutputLimit) throw new Exception("Bounded retained-output limit reached");
        writer.WriteLine(value);
    }
    static uint Word(MemoryDomain ram, int at) {
        if (at < 0 || at > 0x1ffffc) throw new Exception("Read outside complete MainRAM");
        return (uint)(ram.PeekByte(at) | ram.PeekByte(at+1) << 8 | ram.PeekByte(at+2) << 16 | ram.PeekByte(at+3) << 24);
    }
    sealed class State {
        public int address, year, day, timer, limit, paused, flashback, link, stored_day, menu, selection;
        public bool found;
        public int AbsoluteDay { get { return year * 365 + day; } }
    }
    static int Find(MemoryDomain ram, byte[] bytes, uint vtable, int dream) {
        ram.BulkPeekByte(0L.RangeTo(bytes.LongLength - 1), bytes);
        var found = new List<int>();
        for (int at = 0x90000; at < 0x1ef000; at += 4) {
            if (BitConverter.ToUInt32(bytes, at) != vtable) continue;
            if (vtable == DreamVtable) {
                int day = BitConverter.ToInt32(bytes, at + 0x180), year = BitConverter.ToInt32(bytes, at + 0x17c);
                if (day < 0 || day > 364 || year < 0 || year > 100) continue;
            } else if (BitConverter.ToUInt32(bytes, at + 0xa4) != (uint)(dream | unchecked((int)0x80000000))) continue;
            found.Add(at);
        }
        if (found.Count > 1) throw new Exception("Ambiguous native object locator: " + String.Join(",", found));
        return found.Count == 1 ? found[0] : 0;
    }
    static State Read(MemoryDomain ram, int dream, int menu) {
        var s = new State {address=dream, menu=menu, selection=-1, found=dream != 0};
        if (dream == 0) return s;
        if (Word(ram, dream) != DreamVtable) throw new Exception("Pinned dream object changed identity");
        s.year=(int)Word(ram,dream+0x17c); s.day=(int)Word(ram,dream+0x180);
        s.timer=(int)Word(ram,dream+0x24); s.limit=(int)Word(ram,dream+0x134);
        s.paused=(int)Word(ram,dream+0x6c); s.flashback=(int)Word(ram,dream+0x68);
        s.link=(int)Word(ram,dream+0x44); s.stored_day=(int)Word(ram,dream+0x88c);
        if (menu != 0 && Word(ram,menu)==MenuVtable) s.selection=(int)Word(ram,menu+0x58);
        if (s.day < 0 || s.day > 364 || s.year < 0 || s.year > 100) throw new Exception("Invalid native day/year");
        return s;
    }
    static object[] EndingMovies(MemoryDomain ram, byte[] bytes) {
        ram.BulkPeekByte(0L.RangeTo(bytes.LongLength - 1), bytes);
        var rows=new List<object>();
        for(int at=0x90000;at<0x1ef000;at+=4) {
            if(BitConverter.ToUInt32(bytes,at)!=0x8006e5f8) continue;
            uint pointer=BitConverter.ToUInt32(bytes,at+0xb8);
            if((pointer&0xe0000000)!=0x80000000) continue;
            int offset=(int)(pointer&0x1fffffff);
            if(offset<0 || offset>0x1fff80) continue;
            int length=0;while(length<128 && bytes[offset+length]!=0) length++;
            if(length==128 || Encoding.ASCII.GetString(bytes,offset,length)!="ETC\\ENDING.STR") continue;
            rows.Add(new {address=at,path_pointer=pointer,path="ETC\\ENDING.STR",
                encoded_frame_threshold=BitConverter.ToInt32(bytes,at+0xbc),play_flags=BitConverter.ToInt32(bytes,at+0xc0),
                decoder_result=BitConverter.ToInt32(bytes,at+0xa4),completion_flag=BitConverter.ToInt32(bytes,at+0xd8)});
        }
        return rows.ToArray();
    }
    static int Policy(int frame, State state) {
        if (frame == 0) return 0;
        if (frame < 1980) return frame % 120 >= 60 && frame % 120 < 72 ? 1 : 0;
        if (frame <= 1991) return 2;
        if (frame >= 2100 && frame <= 2111) return 1;
        if (frame < 2400 || state.year > 0) return 0;
        if (state.found && state.timer > 0 && state.paused == 0) return 0;
        // Menu cursor 0 is the ordinary dream; other choices are never confirmed.
        if (state.menu != 0 && state.selection > 0) return frame % 120 < 12 ? 2 : 0;
        return frame % 120 >= 60 && frame % 120 < 72 ? 1 : 0;
    }
    static byte[] ReadDomain(MemoryDomain domain) {
        var value = new byte[checked((int)domain.Size)];
        domain.BulkPeekByte(0L.RangeTo(value.LongLength - 1), value);
        return value;
    }
    static string StateHash(Nymashock core) {
        Func<Tuple<string,long>> save = () => {
            using (var stream = new BoundedSha256Stream(256L*1024*1024)) {
                using (var writer = new BinaryWriter(stream, Encoding.UTF8, true)) { ((IStatable)core).SaveStateBinary(writer); writer.Flush(); }
                if (stream.Length < 1) throw new Exception("Serialized state is empty");
                return Tuple.Create(stream.CompleteHash(),stream.Length);
            }
        };
        int frame = core.Frame;
        var first=save(); var second=save();
        if (first.Item1 != second.Item1 || first.Item2 != second.Item2 || core.Frame != frame) throw new Exception("Repeated same-frame serialization differs");
        LastSerializedStateBytes=first.Item2;
        return first.Item1;
    }

    static int HostWaitCount;
    static long HostWaitMilliseconds, HostWaitBytes;
    static object WaitBoundary(Nymashock core, MemoryDomain ram, MemoryDomain gpu, long samples) {
        int frame=core.Frame;
        byte[] beforeRAM=ReadDomain(ram),beforeGPU=ReadDomain(gpu);
        string native=StateHash(core);
        if(Hash(ReadDomain(ram))!=Hash(beforeRAM) || Hash(ReadDomain(gpu))!=Hash(beforeGPU))
            throw new Exception("Host wait serialization changed game memory");
        int[] pixels=core.GetVideoBuffer(); byte[] rgb=new byte[core.BufferWidth*core.BufferHeight*3];
        for(int i=0;i<rgb.Length/3;i++) {rgb[3*i]=(byte)(pixels[i]>>16);rgb[3*i+1]=(byte)(pixels[i]>>8);rgb[3*i+2]=(byte)pixels[i];}
        if(core.Frame!=frame) throw new Exception("Host wait observation advanced the core");
        return new {core_frame=frame,MainRAM_sha256=Hash(beforeRAM),GPURAM_sha256=Hash(beforeGPU),
            RGB_sha256=Hash(rgb),serialized_state_sha256=native,PCM_sample_frames=samples};
    }
    static void WaitLine(StreamWriter writer, object value) {
        string encoded=Json.Serialize(value);
        HostWaitBytes+=Encoding.UTF8.GetByteCount(encoded)+2;
        if(HostWaitBytes>256*1024) throw new Exception("Host wait journal bound reached");
        writer.WriteLine(encoded);writer.Flush();
    }
    static void WaitStatus(object value) {
        string path=Path.Combine(Output,"host-wait-status.json"),temp=path+".tmp";
        File.WriteAllText(temp,Json.Serialize(value));
        if(File.Exists(path)) File.Replace(temp,path,null); else File.Move(temp,path);
    }
    static void HostWait(CooperativeFrameWait gate, Nymashock core, MemoryDomain ram, MemoryDomain gpu,
        StreamWriter journal, int frame, long samples, int completedDays) {
        if(!gate.RequestPending) return;
        object before=null;
        var result=gate.WaitIfRequested(token=> {
            before=WaitBoundary(core,ram,gpu,samples);
            var row=new {kind="waiting",token=token,frame=frame,completed_days=completedDays,boundary=before};
            WaitLine(journal,row);WaitStatus(row);
        },finished=> {
            object after=WaitBoundary(core,ram,gpu,samples);
            if(Json.Serialize(before)!=Json.Serialize(after)) throw new Exception("Host wait changed complete observed state");
            HostWaitCount++;HostWaitMilliseconds+=finished.ElapsedMilliseconds;
            var row=new {kind="resumed",token=finished.Token,frame=frame,completed_days=completedDays,
                boundary=after,elapsed_ms=finished.ElapsedMilliseconds,stop_requested=finished.StopRequested,timed_out=finished.TimedOut};
            WaitLine(journal,row);WaitStatus(row);
        });
        if(result!=null && result.TimedOut) File.WriteAllText(Path.Combine(Output,"STOP"),"bounded_host_wait_timeout");
    }

    static object ResourceUsage() {
        using (var process=Process.GetCurrentProcess()) {
            process.Refresh();
            return new {working_set_bytes=process.WorkingSet64,private_bytes=process.PrivateMemorySize64,
                handles=process.HandleCount,managed_heap_bytes=GC.GetTotalMemory(false),
                last_serialized_state_bytes=LastSerializedStateBytes};
        }
    }
    static void Image(Nymashock core, string file) {
        int w=core.BufferWidth, h=core.BufferHeight;
        if (w<1 || h<1 || w>1024 || h>1024) throw new Exception("Invalid native image dimensions");
        int[] pixels=core.GetVideoBuffer();
        using (var image=new Bitmap(w,h,PixelFormat.Format24bppRgb)) {
            for (int y=0;y<h;y++) for (int x=0;x<w;x++) image.SetPixel(x,y,Color.FromArgb(pixels[y*w+x] | unchecked((int)0xff000000)));
            image.Save(Path.Combine(Output,file),ImageFormat.Png);
        }
    }
    public static int Main(string[] args) {
        try {
            DllRoot=Path.Combine(args[0],"dll");
            AppDomain.CurrentDomain.AssemblyResolve += delegate(object sender, ResolveEventArgs ev) {
                string path=Path.Combine(DllRoot,new AssemblyName(ev.Name).Name+".dll"); return File.Exists(path)?Assembly.LoadFrom(path):null;
            };
            if (!SetDllDirectory(DllRoot)) throw new Exception("SetDllDirectory failed");
            return Run(args);
        } catch(Exception e) { Console.Error.WriteLine(e); return 2; }
    }
    static int Run(string[] args) {
        Output=args[5]; int ceiling=Int32.Parse(args[6]), target=Int32.Parse(args[7]);
        if (Directory.Exists(Output) || ceiling<1 || ceiling>8000000 || target<1 || target>365) throw new Exception("Invalid bounded recording request");
        int forcedWaitFrame=Int32.Parse(args[9]),waitLimit=Int32.Parse(args[10]);
        if((forcedWaitFrame!=-1 && forcedWaitFrame!=3000) || waitLimit<1000 || waitLimit>3600000) throw new Exception("Invalid host-wait qualification bounds");
        var replay=args[8]=="-" ? null : File.ReadAllLines(args[8]).Skip(1).Select(l=>l.Split('\t')).ToArray();
        if (replay!=null && (replay.Length==0 || replay[0][0]!="0" || replay[0][1]!="0")) throw new Exception("Replay lacks initial neutral input");
        Directory.CreateDirectory(Output);
        Database.InitializeDatabase(Path.Combine(args[0],"gamedb"),Output,true);
        var comm=new CoreComm(m=>Console.Error.WriteLine(m),(m,d)=>Console.Error.WriteLine(m),
            new ReplayColdStart.Files(new[]{args[2],args[3],args[4]},Output),(CoreComm.CorePreferencesFlags)0,null);
        using(var disc=Disc.LoadAutomagic(args[1])) {
            var parameters=new CoreLoadParameters<NymaCore.NymaSettings,NymaCore.NymaSyncSettings> {
                Comm=comm,Game=new GameInfo{Name="LSD Japanese controller-only year progression",System="PSX"},Settings=null,SyncSettings=null,
                Roms=new List<IRomAsset>(),Discs=new List<IDiscAsset>{new ReplayColdStart.DiscAsset(disc,"LSD Japanese")},DeterministicEmulationRequested=false};
            using(var core=new Nymashock(parameters)) {
                var input=new ReplayColdStart.Input(core.ControllerDefinition);
                if (!input.Buttons.ContainsKey("P1 \u25cb") || !input.Buttons.ContainsKey("P1 D-Pad Up")) throw new Exception("Unsupported controller schema");
                var domains=core.ServiceProvider.GetService<IMemoryDomains>(); var ram=domains.MainMemory; var gpu=domains["GPURAM"];
                if (ram.Size!=0x200000 || gpu.Size!=0x100000) throw new Exception("Unexpected complete native memory domains");
                int dream=0,menu=0,previous=-1,transitions=0,lastTransition=0,lastMask=-1,mask=0,replayIndex=0,finishedFrame=-1;
                long totalSamples=0,windowSamples=0; int windowStart=0; string outcome="frame_ceiling_reached";
                var scan=new byte[0x200000]; var timer=Stopwatch.StartNew(); var pcm=SHA256.Create();
                var observed=new State();
                int wrapFrame=-1,endingObservations=0; string lastEnding="";
                bool endingPending=false,endingComplete=false; int endingObject=0;
                var frameWait=new CooperativeFrameWait(Output,waitLimit);
                const int PostYearFrames=12000;
                using(var waits=new StreamWriter(File.Open(Path.Combine(Output,"host-waits.jsonl"),FileMode.CreateNew)))
                using(var inputs=new StreamWriter(File.Open(Path.Combine(Output,"inputs.tsv"),FileMode.CreateNew)))
                using(var days=new StreamWriter(File.Open(Path.Combine(Output,"days.jsonl"),FileMode.CreateNew)))
                using(var checks=new StreamWriter(File.Open(Path.Combine(Output,"checkpoints.jsonl"),FileMode.CreateNew)))
                using(var audio=new StreamWriter(File.Open(Path.Combine(Output,"audio.tsv"),FileMode.CreateNew)))
                using(var ending=new StreamWriter(File.Open(Path.Combine(Output,"ending.jsonl"),FileMode.CreateNew))) {
                    Line(inputs,"frame\tmask"); Line(audio,"first_frame\tlast_frame\tsample_frames\tPCM_sha256");
                    for(int frame=0;frame<=ceiling;frame++) {
                        if (replay==null) mask=Policy(frame,observed);
                        else while(replayIndex<replay.Length && Int32.Parse(replay[replayIndex][0])<=frame) {
                            if (replayIndex>0 && Int32.Parse(replay[replayIndex][0])<=Int32.Parse(replay[replayIndex-1][0])) throw new Exception("Nonconsecutive replay input ordering");
                            mask=Int32.Parse(replay[replayIndex][1]); replayIndex++;
                        }
                        if(mask<0 || mask>2) throw new Exception("Input mask outside ordinary confirm/up controls");
                        if(mask!=lastMask) { Line(inputs,String.Join("\t",frame,mask)); lastMask=mask; }
                        input.Buttons["P1 \u25cb"]=(mask&1)!=0; input.Buttons["P1 D-Pad Up"]=(mask&2)!=0;
                        core.FrameAdvance(input,true,true);
                        short[] samples; int count; core.GetSamplesSync(out samples,out count);
                        if(count<0 || count*2>samples.Length) throw new Exception("Invalid complete PCM count");
                        byte[] bytes=new byte[count*4]; Buffer.BlockCopy(samples,0,bytes,0,bytes.Length);
                        pcm.TransformBlock(bytes,0,bytes.Length,bytes,0); totalSamples+=count; windowSamples+=count;
                        if(dream==0 && frame%120==0) dream=Find(ram,scan,DreamVtable,0);
                        if(menu!=0 && Word(ram,menu)!=MenuVtable) menu=0;
                        if(dream!=0 && frame%120==0 && observed.timer==0) menu=Find(ram,scan,MenuVtable,dream);
                        observed=Read(ram,dream,menu);
                        bool changed=observed.found && observed.AbsoluteDay!=previous;
                        if(changed) {
                            if(previous>=0 && observed.AbsoluteDay!=previous+1) throw new Exception("Native day progression skipped or regressed");
                            if(previous>=0) transitions++;
                            previous=observed.AbsoluteDay; lastTransition=frame;
                            Line(days,Json.Serialize(new {frame=frame,core_frame=core.Frame,state=observed,completed_days=transitions})); days.Flush();
                        }
                        if(target==365 && transitions>=365 && wrapFrame<0) wrapFrame=frame;
                        bool endingChanged=false;
                        if(wrapFrame>=0 && frame%30==0) {
                            object[] movies=EndingMovies(ram,scan); string encoded=Json.Serialize(movies);
                            foreach(object movie in movies) {
                                var row=Json.Deserialize<Dictionary<string,object>>(Json.Serialize(movie));
                                if(Convert.ToInt32(row["encoded_frame_threshold"])!=474 || Convert.ToInt32(row["play_flags"])!=1)
                                    throw new Exception("Ending object's original path arguments differ from the native source contract");
                                int address=Convert.ToInt32(row["address"]);
                                if(Convert.ToInt32(row["completion_flag"])==0) {endingPending=true;endingObject=address;}
                                if(endingPending && address==endingObject && Convert.ToInt32(row["completion_flag"])==1 && Convert.ToInt32(row["decoder_result"])!=0) endingComplete=true;
                            }
                            if(encoded!=lastEnding) {
                                Line(ending,Json.Serialize(new {frame=frame,core_frame=core.Frame,state=observed,movies=movies}));ending.Flush();
                                lastEnding=encoded;endingChanged=true;endingObservations++;
                            }
                        }
                        if(wrapFrame>=0 && new[]{0,120,600,1800,3600,11999}.Contains(frame-wrapFrame)) Image(core,"ending-"+(frame-wrapFrame)+".png");
                        if(frame==forcedWaitFrame) {
                            using(var request=new FileStream(Path.Combine(Output,"HOST-WAIT"),FileMode.CreateNew,FileAccess.Write)) {
                                byte[] token=Encoding.ASCII.GetBytes("qualification-frame-3000");request.Write(token,0,token.Length);
                            }
                        }
                        HostWait(frameWait,core,ram,gpu,waits,frame,totalSamples,transitions);
                        bool targetDone=transitions>=target && (target!=365 || frame-wrapFrame>=PostYearFrames);
                        bool watchdog=frame-lastTransition>90000;
                        bool stop=targetDone || frame==ceiling || watchdog || File.Exists(Path.Combine(Output,"STOP"));
                        if(frame%600==0 || changed || endingChanged || stop) {
                            byte[] beforeRAM=ReadDomain(ram), beforeGPU=ReadDomain(gpu);
                            string native=changed || endingChanged || stop ? StateHash(core) : null;
                            if(native!=null && (Hash(ReadDomain(ram))!=Hash(beforeRAM) || Hash(ReadDomain(gpu))!=Hash(beforeGPU))) throw new Exception("Serialization changed RAM or GPU");
                            int[] pixels=core.GetVideoBuffer(); byte[] rgb=new byte[core.BufferWidth*core.BufferHeight*3];
                            for(int i=0;i<rgb.Length/3;i++) { rgb[3*i]=(byte)(pixels[i]>>16);rgb[3*i+1]=(byte)(pixels[i]>>8);rgb[3*i+2]=(byte)pixels[i]; }
                            Line(checks,Json.Serialize(new {frame=frame,core_frame=core.Frame,state=observed,MainRAM_sha256=Hash(beforeRAM),GPURAM_sha256=Hash(beforeGPU),RGB_sha256=Hash(rgb),serialized_state_sha256=native,PCM_sample_frames=totalSamples})); checks.Flush();
                        }
                        if(frame%600==0 || stop) {
                            pcm.TransformFinalBlock(new byte[0],0,0);
                            Line(audio,String.Join("\t",windowStart,frame,windowSamples,BitConverter.ToString(pcm.Hash).Replace("-","").ToLowerInvariant()));
                            pcm.Dispose();pcm=SHA256.Create();windowStart=frame+1;windowSamples=0;audio.Flush();inputs.Flush();
                            File.WriteAllText(Path.Combine(Output,"progress.json"),Json.Serialize(new {frame=frame,core_frame=core.Frame,state=observed,completed_days=transitions,elapsed_ms=timer.ElapsedMilliseconds,retained_stream_bytes=RetainedBytes,resources=ResourceUsage()}));
                        }
                        if(targetDone) {outcome=target!=365?"completed_requested_natural_days":endingPending&&endingComplete?"completed_natural_year_and_ending_objects":"completed_natural_year_missing_ending_evidence";finishedFrame=frame;break;}
                        if(File.Exists(Path.Combine(Output,"STOP"))) {outcome="owned_host_stop_requested";finishedFrame=frame;break;}
                        if(watchdog) {outcome="native_day_watchdog_reached";finishedFrame=frame;break;}
                        finishedFrame=frame;
                    }
                }
                pcm.Dispose();Image(core,"final.png");
                File.WriteAllText(Path.Combine(Output,"report.json"),Json.Serialize(new {status=outcome,frames_advanced=core.Frame,last_frame=finishedFrame,completed_days=transitions,final_state=observed,
                    total_PCM_sample_frames=totalSamples,retained_stream_bytes=RetainedBytes,retained_stream_limit=OutputLimit,elapsed_ms=timer.ElapsedMilliseconds,
                    host_wait_count=HostWaitCount,host_wait_milliseconds=HostWaitMilliseconds,host_wait_stream_bytes=HostWaitBytes,host_wait_stream_limit=256*1024,
                    year_boundary_frame=wrapFrame,post_year_frames_observed=wrapFrame<0?0:finishedFrame-wrapFrame,
                    ending_path_pending_observed=endingPending,ending_completion_after_pending_observed=endingComplete,ending_object_observations=endingObservations,
                    controller_buttons=input.Buttons.Keys.OrderBy(n=>n).ToArray(),controller_neutral_axes=input.Axes,
                    restored_state=false,game_RAM_injected=false,emulator_UI_controlled=false,original_hardware_timing_verified=false,complete_feature_parity_accepted=false}));
                return outcome=="completed_requested_natural_days" || outcome=="completed_natural_year_and_ending_objects"?0:3;
            }
        }
    }
}
}
