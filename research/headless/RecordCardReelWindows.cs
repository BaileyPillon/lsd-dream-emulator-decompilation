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
internal static class RecordCardReelWindows {
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
            if(args.Length!=10) throw new Exception("runtime cue BIOS-J BIOS-U BIOS-E output mode ceiling replay-or-dash prepared-card");
            DllRoot=Path.Combine(args[0],"dll");
            AppDomain.CurrentDomain.AssemblyResolve+=delegate(object sender,ResolveEventArgs ev) {
                string path=Path.Combine(DllRoot,new AssemblyName(ev.Name).Name+".dll"); return File.Exists(path)?Assembly.LoadFrom(path):null;
            };
            if(!SetDllDirectory(DllRoot)) throw new Exception("SetDllDirectory failed");
            return Run(args);
        } catch(Exception error) { Console.Error.WriteLine(error); return 2; }
    }
    static readonly string[] SceneNames = {
        "flow","dream","year","day","stored_day","new_game","dream_timer","dream_limit","dream_paused",
        "main","main_selection","main_state","card","card_operation","card_state",
        "graph","graph_timer","graph_state","graph_result","graph_reel_ready","graph_event_index",
        "history_flag","four_cells_found","payload_sha256","main_seen","load_seen","load_returned","dream_started",
        "reel_seen","reel_cleared","movie_player","player_path","player_threshold","player_length","player_result","player_done",
        "sdk_next_index","sdk_header_base","sdk_data_index","sdk_header_00","sdk_header_04","sdk_header_08","sdk_header_0c",
        "sdk_header_10","sdk_header_14","sdk_header_18","sdk_header_1c"
    };
    static bool MainSeen,LoadSeen,LoadReturned,DreamStarted,ReelSeen,PreviousWasReel;
    static int FirstReel=-1,ReelCleared=-1,MainAddress,GraphAddress,PlayerAddress;
    static string ExpectedPayloadHash;
    sealed class Scene {
        public Dictionary<string,string> values=SceneNames.ToDictionary(name=>name,name=>"-");
        public int main,selection=-1,operation,cardState,timer,paused;
        public bool isReel;
        public string Row() { return String.Join("\t",SceneNames.Select(name=>values[name])); }
    }
    static int MaybePointer(uint value,int size) {
        return value>=0x80010000 && value<=0x80200000-size && value%4==0?(int)(value&0x1fffffff):0;
    }
    static string AsciiPath(byte[] ram,uint value) {
        int at=MaybePointer(value,128);
        if(at==0) return "-";
        int length=0;
        while(length<128 && ram[at+length]!=0) {
            byte c=ram[at+length];
            if(c<32 || c>126) throw new Exception("Invalid native movie path byte");
            length++;
        }
        if(length==128) throw new Exception("Unterminated native movie path");
        return Encoding.ASCII.GetString(ram,at,length);
    }
    static int FindScreen(byte[] ram,uint type,uint graphics,uint dream,int child,int cached) {
        Func<int,bool> matches=at=>at>=0x90000 && at<=0x1ef000 && Word(ram,at)==type &&
            Word(ram,at+0x0c)==graphics && (type==0x8006e5f8?Word(ram,at+0xb4)==(uint)child:Word(ram,at+0xa4)==dream);
        if(cached!=0 && matches(cached)) return cached;
        int found=0;
        for(int at=0x90000;at<=0x1ef000;at+=4) if(matches(at)) {
            if(found!=0) throw new Exception("Ambiguous native screen binding");
            found=at;
        }
        return found;
    }
    static Scene ReadScene(byte[] ram,Observation movie,int frame) {
        var scene=new Scene();
        foreach(string name in new[]{"flow","dream","main","card","graph","movie_player"}) scene.values[name]="0";
        int flow=movie.ready?MaybePointer(Word(ram,0x8ac20),0x2c):0;
        if(flow!=0 && Word(ram,flow)==0x8006d3c8) {
            int dream=MaybePointer(Word(ram,flow+0x28),0x928);
            if(dream!=0 && Word(ram,dream)==0x80087bdc) {
                scene.values["flow"]=flow.ToString();scene.values["dream"]=dream.ToString();
                foreach(var pair in new[]{Tuple.Create("year",0x17c),Tuple.Create("day",0x180),Tuple.Create("stored_day",0x88c),
                    Tuple.Create("new_game",0x878),Tuple.Create("dream_timer",0x24),Tuple.Create("dream_limit",0x134),Tuple.Create("dream_paused",0x6c)})
                    scene.values[pair.Item1]=Word(ram,dream+pair.Item2).ToString();
                scene.timer=(int)Word(ram,dream+0x24);scene.paused=(int)Word(ram,dream+0x6c);
                byte[] payload=new byte[1792];Buffer.BlockCopy(ram,dream+0x178,payload,0,payload.Length);
                scene.values["payload_sha256"]=Hash(payload);
                scene.values["history_flag"]=ram[dream+0x5df].ToString();
                int year=(int)Word(ram,dream+0x17c),day=(int)Word(ram,dream+0x180);
                if(year<0 || year>100 || day<0 || day>364) throw new Exception("Invalid native day/year");
                int limit=year==0?Math.Min(day,100):100,hits=0;
                for(int slot=0;slot<4;slot++) {
                    short wanted=BitConverter.ToInt16(ram,0x87bd4+slot*2);bool hit=false;
                    for(int i=0;i<limit;i++) {
                        int index=day-1-i;if(index<0) index+=365;
                        if(BitConverter.ToInt16(ram,dream+0x190+index*2)==wanted) hit=true;
                    }
                    if(hit) hits++;
                }
                scene.values["four_cells_found"]=hits.ToString();
                uint graphics=Word(ram,flow+0x1c),dreamPointer=(uint)(dream|unchecked((int)0x80000000));
                if(frame%30==0 || MainAddress!=0) MainAddress=FindScreen(ram,0x80086b60,graphics,dreamPointer,0,MainAddress);
                if(frame%30==0 || GraphAddress!=0) GraphAddress=FindScreen(ram,0x80087aac,graphics,dreamPointer,0,GraphAddress);
                scene.main=MainAddress;scene.values["main"]=MainAddress.ToString();scene.values["graph"]=GraphAddress.ToString();
                if(MainAddress!=0) {
                    MainSeen=true;scene.selection=(int)Word(ram,MainAddress+0x58);
                    scene.values["main_selection"]=scene.selection.ToString();scene.values["main_state"]=Word(ram,MainAddress+0x84).ToString();
                    int card=MaybePointer(Word(ram,MainAddress+0xac),0x84);
                    if(card!=0) {
                        if(Word(ram,card)!=0x80086dc4) throw new Exception("Invalid card object vtable");
                        scene.values["card"]=card.ToString();scene.operation=(int)Word(ram,card+0x24);scene.cardState=(int)Word(ram,card+0x28);
                        scene.values["card_operation"]=scene.operation.ToString();scene.values["card_state"]=scene.cardState.ToString();
                        if(scene.operation==1 && scene.cardState!=0) LoadSeen=true;
                        if(LoadSeen && !LoadReturned && scene.operation==0 && scene.cardState==0) {
                            if(scene.values["payload_sha256"]!=ExpectedPayloadHash) throw new Exception("Card load returned without the complete prepared payload");
                            LoadReturned=true;
                        }
                    }
                }
                if(GraphAddress!=0) foreach(var pair in new[]{Tuple.Create("graph_timer",0x2c),Tuple.Create("graph_state",0x84),
                    Tuple.Create("graph_result",0x38),Tuple.Create("graph_reel_ready",0x238),Tuple.Create("graph_event_index",0x23c)})
                    scene.values[pair.Item1]=Word(ram,GraphAddress+pair.Item2).ToString();
                if(LoadReturned && scene.timer>0 && scene.paused==0) DreamStarted=true;
                if(movie.active!=0) {
                    PlayerAddress=FindScreen(ram,0x8006e5f8,graphics,dreamPointer,unchecked((int)movie.active),PlayerAddress);
                    if(PlayerAddress!=0) {
                        scene.values["movie_player"]=PlayerAddress.ToString();scene.values["player_path"]=AsciiPath(ram,Word(ram,PlayerAddress+0xb8));
                        foreach(var pair in new[]{Tuple.Create("player_threshold",0xbc),Tuple.Create("player_length",0x40),
                            Tuple.Create("player_result",0xa4),Tuple.Create("player_done",0xd8)}) scene.values[pair.Item1]=Word(ram,PlayerAddress+pair.Item2).ToString();
                    }
                } else PlayerAddress=0;
            }
        }
        if(movie.active!=0) {
            int stream=Pointer(Word(ram,Pointer(movie.active,0x6c)+0x60),0x5c);
            string file=Encoding.ASCII.GetString(ram,stream+0x14,16).Split('\0')[0];
            scene.isReel=movie.cutoff==0xffffffff && file=="SPDAY01A.STR;1";
            int next=(int)Word(ram,0x9025c),head=MaybePointer(Word(ram,0x90b8c),32),data=(int)Word(ram,0x90c5c);
            scene.values["sdk_next_index"]=next.ToString();scene.values["sdk_header_base"]=Word(ram,0x90b8c).ToString();scene.values["sdk_data_index"]=data.ToString();
            if(head!=0 && next>=0 && next<1024 && head+next*32<=0x1fffe0)
                for(int i=0;i<8;i++) scene.values["sdk_header_"+(i*4).ToString("x2")]=Word(ram,head+next*32+i*4).ToString();
        }
        if(scene.isReel) {
            if(!LoadReturned) throw new Exception("Reel appeared before the prepared card load");
            ReelSeen=true;if(FirstReel<0) FirstReel=frame;
        }
        if(PreviousWasReel && movie.active==0 && ReelCleared<0) ReelCleared=frame;
        PreviousWasReel=scene.isReel;
        scene.values["main_seen"]=MainSeen?"1":"0";scene.values["load_seen"]=LoadSeen?"1":"0";
        scene.values["load_returned"]=LoadReturned?"1":"0";scene.values["dream_started"]=DreamStarted?"1":"0";
        scene.values["reel_seen"]=ReelSeen?"1":"0";scene.values["reel_cleared"]=ReelCleared>=0?"1":"0";
        return scene;
    }
    static int Policy(int frame,Scene previous) {
        if(frame%120<60 || frame%120>=72 || ReelSeen) return 0;
        if(!MainSeen) return 1;
        if(previous==null || previous.main==0) return 0;
        if(!LoadReturned) {
            if(previous.operation!=0 || LoadSeen) return 1;
            if(previous.selection<3) return 4;
            if(previous.selection>3 && previous.selection<6) return 2;
            return previous.selection==3?1:0;
        }
        if(!DreamStarted) {
            if(previous.selection>0 && previous.selection<6) return 2;
            return previous.selection==0?1:0;
        }
        return 0;
    }
    static int Run(string[] args) {
        string output=args[5];int ceiling=Int32.Parse(args[7]);
        if(Directory.Exists(output) || File.Exists(output) || args[6]!="card-reel" || ceiling<1 || ceiling>80000)
            throw new Exception("Invalid fresh bounded card-reel request");
        byte[] card=File.ReadAllBytes(args[9]);
        if(card.Length!=131072 || card[0]!='M' || card[1]!='C') throw new Exception("Require a raw prepared 128 KiB card");
        byte[] expectedPayload=new byte[1792];Buffer.BlockCopy(card,8192+512,expectedPayload,0,1792);ExpectedPayloadHash=Hash(expectedPayload);
        string[][] replay=args[8]=="-"?null:File.ReadAllLines(args[8]).Skip(1).Select(line=>line.Split('\t')).ToArray();
        if(replay!=null && (replay.Length==0 || replay[0][0]!="0" || replay[0][1]!="0")) throw new Exception("Replay must start neutral");
        Directory.CreateDirectory(output);Database.InitializeDatabase(Path.Combine(args[0],"gamedb"),output,true);
        var comm=new CoreComm(m=>Console.Error.WriteLine(m),(m,d)=>Console.Error.WriteLine(m),
            new ReplayColdStart.Files(new[]{args[2],args[3],args[4]},output),(CoreComm.CorePreferencesFlags)0,null);
        using(var disc=Disc.LoadAutomagic(args[1])) {
            var parameters=new CoreLoadParameters<NymaCore.NymaSettings,NymaCore.NymaSyncSettings> {
                Comm=comm,Game=new GameInfo{Name="LSD Japanese prepared-card reel windows",System="PSX"},Settings=null,SyncSettings=null,
                Roms=new List<IRomAsset>(),Discs=new List<IDiscAsset>{new ReplayColdStart.DiscAsset(disc,"LSD Japanese")},DeterministicEmulationRequested=false};
            using(var core=new Nymashock(parameters)) {
                var domains=core.ServiceProvider.GetService<IMemoryDomains>();var ram=domains.MainMemory;var gpu=domains["GPURAM"];
                if(ram.Size!=0x200000 || gpu.Size!=0x100000 || core.Frame!=0) throw new Exception("Unexpected cold core");
                var ramBytes=new byte[0x200000];var gpuBytes=new byte[0x100000];
                ram.BulkPeekByte(0L.RangeTo(ramBytes.LongLength-1),ramBytes);gpu.BulkPeekByte(0L.RangeTo(gpuBytes.LongLength-1),gpuBytes);
                string beforeRAM=Hash(ramBytes),beforeGPU=Hash(gpuBytes);
                var saves=(ISaveRam)core;byte[] initial=saves.CloneSaveRam(false);
                if(initial==null || initial.Length<card.Length || initial.Length%card.Length!=0 || initial.Length>2*1024*1024)
                    throw new Exception("Unsupported core SaveRAM layout");
                byte[] expected=(byte[])initial.Clone();Buffer.BlockCopy(card,0,expected,0,card.Length);
                saves.StoreSaveRam(expected);byte[] readback=saves.CloneSaveRam(false);
                if(!readback.SequenceEqual(expected) || core.Frame!=0) throw new Exception("SaveRAM store/readback differs");
                ram.BulkPeekByte(0L.RangeTo(ramBytes.LongLength-1),ramBytes);gpu.BulkPeekByte(0L.RangeTo(gpuBytes.LongLength-1),gpuBytes);
                if(Hash(ramBytes)!=beforeRAM || Hash(gpuBytes)!=beforeGPU) throw new Exception("External card store changed MainRAM/GPU");
                File.WriteAllText(Path.Combine(output,"card-store.json"),Json.Serialize(new {core_frame=core.Frame,
                    initial_SaveRAM_bytes=initial.Length,initial_SaveRAM_sha256=Hash(initial),input_card_sha256=Hash(card),
                    stored_SaveRAM_sha256=Hash(readback),expected_payload_sha256=ExpectedPayloadHash,
                    MainRAM_before_sha256=beforeRAM,MainRAM_after_sha256=Hash(ramBytes),GPURAM_before_sha256=beforeGPU,GPURAM_after_sha256=Hash(gpuBytes),
                    prepared_external_card_loaded_using_ISaveRam=true,main_RAM_or_instruction_writes=false,restored_state=false,user_player_saves_accessed=false}));
                var input=new ReplayColdStart.Input(core.ControllerDefinition);
                var header=new List<string>{"relative_frame","core_frame","native_tables_ready","active_movie","rng","watchdog_counter"};
                for(int at=0;at<0x6c;at+=4) header.Add("movie_"+at.ToString("x2"));
                for(int at=0;at<0x5c;at+=4) header.Add("stream_"+at.ToString("x2"));header.AddRange(SceneNames);
                int lastMask=-1,replayIndex=0,mask=0,lastFrame=-1,loadReturnedFrame=-1;long totalSamples=0,rawTraceBytes=0;
                Scene previous=null;var clock=Stopwatch.StartNew();string outcome="frame_ceiling_reached";Window window=new Window(0);
                using(var file=File.Open(Path.Combine(output,"native.tsv.gz"),FileMode.CreateNew))
                using(var zipped=new GZipStream(file,CompressionLevel.Optimal))
                using(var native=new StreamWriter(zipped,new UTF8Encoding(false)))
                using(var inputs=new StreamWriter(File.Open(Path.Combine(output,"inputs.tsv"),FileMode.CreateNew),new UTF8Encoding(false)))
                using(var windows=new StreamWriter(File.Open(Path.Combine(output,"windows.jsonl"),FileMode.CreateNew),new UTF8Encoding(false))) {
                    native.NewLine="\n";inputs.NewLine="\n";windows.NewLine="\n";native.WriteLine(String.Join("\t",header));inputs.WriteLine("frame\tmask");
                    for(int frame=0;frame<=ceiling;frame++) {
                        if(File.Exists(Path.Combine(output,"STOP"))) {outcome="owned_stop_requested";break;}
                        if(replay==null) mask=Policy(frame,previous);
                        else if(replayIndex<replay.Length && Int32.Parse(replay[replayIndex][0])==frame) {
                            if(replayIndex>0 && Int32.Parse(replay[replayIndex][0])<=Int32.Parse(replay[replayIndex-1][0])) throw new Exception("Invalid replay order");
                            mask=Int32.Parse(replay[replayIndex][1]);replayIndex++;
                        }
                        if(mask<0 || mask>4 || (mask!=0 && mask!=1 && mask!=2 && mask!=4)) throw new Exception("Unsupported controller mask");
                        if(mask!=lastMask) {inputs.WriteLine(frame+"\t"+mask);lastMask=mask;}
                        input.Buttons["P1 \u25cb"]=mask==1;input.Buttons["P1 D-Pad Up"]=mask==2;input.Buttons["P1 D-Pad Down"]=mask==4;
                        core.FrameAdvance(input,true,true);if(core.Frame!=frame+1) throw new Exception("Core frame schedule changed");
                        ram.BulkPeekByte(0L.RangeTo(ramBytes.LongLength-1),ramBytes);gpu.BulkPeekByte(0L.RangeTo(gpuBytes.LongLength-1),gpuBytes);
                        var movie=Observe(ramBytes,frame,core.Frame);var scene=ReadScene(ramBytes,movie,frame);
                        byte[] nativeBytes=Encoding.UTF8.GetBytes(movie.row.TrimEnd('\n')+"\t"+scene.Row()+"\n");
                        native.Write(Encoding.UTF8.GetString(nativeBytes));rawTraceBytes+=nativeBytes.Length;
                        if(rawTraceBytes>96L*1024*1024) throw new Exception("Raw journal bound exceeded");
                        short[] samples;int count;core.GetSamplesSync(out samples,out count);
                        if(count<0 || count>5000 || samples.Length<count*2) throw new Exception("Invalid PCM");
                        byte[] pcm=new byte[count*4];Buffer.BlockCopy(samples,0,pcm,0,pcm.Length);byte[] rgb=RGB(core);
                        window.Add("MainRAM",frame,core.Frame,ramBytes);window.Add("GPURAM",frame,core.Frame,gpuBytes);window.Add("RGB",frame,core.Frame,rgb);
                        window.Add("PCM",frame,core.Frame,pcm);window.Add("native",frame,core.Frame,nativeBytes);window.Add("controller",frame,core.Frame,BitConverter.GetBytes(mask));
                        totalSamples+=count;window.samples+=count;
                        if(LoadReturned && loadReturnedFrame<0) {loadReturnedFrame=frame;Image(core,Path.Combine(output,"load-return.png"));}
                        if(frame==FirstReel) Image(core,Path.Combine(output,"reel-start.png"));
                        if(FirstReel>=0 && frame==FirstReel+600) Image(core,Path.Combine(output,"reel-plus-600.png"));
                        bool complete=ReelCleared>=0 && frame>=ReelCleared+180,stop=frame==ceiling || complete;
                        if(complete) outcome="card_reel_cleared_and_post_window_completed";
                        if(frame%600==599 || stop) {
                            string state=StateHash(core,ram,gpu,ramBytes,gpuBytes);
                            windows.WriteLine(Json.Serialize(window.Finish(frame,state,ramBytes,gpuBytes,rgb)));windows.Flush();window.Dispose();window=stop?null:new Window(frame+1);
                            native.Flush();inputs.Flush();zipped.Flush();if(file.Length>1310720) throw new Exception("Compressed journal bound exceeded");
                            File.WriteAllText(Path.Combine(output,"progress.json"),Json.Serialize(new {frame,core_frame=core.Frame,elapsed_ms=clock.ElapsedMilliseconds,
                                compressed_native_bytes=file.Length,load_seen=LoadSeen,load_returned=LoadReturned,dream_started=DreamStarted,
                                reel_seen=ReelSeen,reel_cleared_frame=ReelCleared,main=scene.main,selection=scene.selection}));
                            Console.WriteLine("FRAME "+frame);
                        }
                        previous=scene;lastFrame=frame;if(stop) break;
                    }
                    if(window!=null) window.Dispose();
                }
                if(replay!=null && replayIndex!=replay.Length) throw new Exception("Unconsumed replay inputs");
                Image(core,Path.Combine(output,"final.png"));byte[] finalSave=saves.CloneSaveRam(false);
                File.WriteAllText(Path.Combine(output,"report.json"),Json.Serialize(new {schema_version=3,status=outcome,mode="card-reel",
                    frames_advanced=lastFrame+1,last_frame=lastFrame,total_PCM_sample_frames=totalSamples,raw_native_bytes=rawTraceBytes,
                    load_seen=LoadSeen,load_returned=LoadReturned,load_returned_frame=loadReturnedFrame,dream_started=DreamStarted,
                    reel_seen=ReelSeen,first_reel_frame=FirstReel,reel_cleared_frame=ReelCleared,post_reel_frames=ReelCleared<0?0:lastFrame-ReelCleared,
                    input_card_sha256=Hash(card),final_SaveRAM_sha256=Hash(finalSave),final_SaveRAM_matches_stored=finalSave.SequenceEqual(expected),
                    expected_payload_sha256=ExpectedPayloadHash,prepared_external_card_loaded_using_ISaveRam=true,
                    replayed_inputs=replay!=null,cold_start=true,restored_state=false,main_RAM_or_instruction_writes=false,
                    player_UI_or_saves_accessed=false,hardware_timing_verified=false,whole_feature_groups_accepted=0,
                    controller_buttons=input.Buttons.Keys.OrderBy(name=>name).ToArray(),controller_neutral_axes=input.Axes,elapsed_ms=clock.ElapsedMilliseconds}));
                return outcome=="card_reel_cleared_and_post_window_completed"?0:1;
            }
        }
    }
}
}
