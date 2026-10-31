// Controller-only cold-boot reset study. No state restoration or guest memory writes.
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
using BizHawk.BizInvoke;
using BizHawk.Emulation.Common;
using BizHawk.Emulation.Cores;
using BizHawk.Emulation.Cores.Sony.PSX;
using BizHawk.Emulation.Cores.Waterbox;
using BizHawk.Emulation.DiscSystem;

namespace Lsd.Research.Headless {
internal static class RecordNewGameResetWindows {
    static readonly JavaScriptSerializer Json=new JavaScriptSerializer();
    static string DllRoot;
    static bool MainSeen,LoadSeen,LoadReturned,ResetSeen,PostMenuSeen,PostDreamSeen;
    static int SequenceStart=-1,ResetFrame=-1,PostDreamFrame=-1,MainAddress;
    static string ExpectedPayloadHash;
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
    static extern bool SetDllDirectory(string path);
    static string Hash(byte[] data) { using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(data)).Replace("-","").ToLowerInvariant(); }
    static uint Word(byte[] data,int at) { return BitConverter.ToUInt32(data,at); }
    static int Pointer(uint value,int bytes) { return value>=0x80010000 && value<=0x80200000-bytes && value%4==0?(int)(value&0x1fffffff):0; }
    static byte[] Slice(byte[] data,int at,int bytes) { var value=new byte[bytes];Buffer.BlockCopy(data,at,value,0,bytes);return value; }
    static byte[] Read(MemoryDomain domain) { var value=new byte[(int)domain.Size];domain.BulkPeekByte(0L.RangeTo(value.LongLength-1),value);return value; }
    static void Write(string output,string name,object value) { File.WriteAllText(Path.Combine(output,name),Json.Serialize(value)); }
    static byte[] RGB(Nymashock core) {
        int w=core.BufferWidth,h=core.BufferHeight;if(w<1 || h<1 || w>1024 || h>1024)throw new Exception("Video dimensions outside profile");
        int[] pixels=core.GetVideoBuffer();var value=new byte[8+w*h*3];Buffer.BlockCopy(new[]{w,h},0,value,0,8);
        for(int i=0;i<w*h;i++){value[8+i*3]=(byte)(pixels[i]>>16);value[9+i*3]=(byte)(pixels[i]>>8);value[10+i*3]=(byte)pixels[i];}
        return value;
    }
    static void Image(Nymashock core,string path) {
        var rgb=RGB(core);int w=BitConverter.ToInt32(rgb,0),h=BitConverter.ToInt32(rgb,4);
        using(var bitmap=new Bitmap(w,h,PixelFormat.Format24bppRgb)) {
            for(int y=0;y<h;y++)for(int x=0;x<w;x++){int at=8+(y*w+x)*3;bitmap.SetPixel(x,y,Color.FromArgb(rgb[at],rgb[at+1],rgb[at+2]));}
            bitmap.Save(path,ImageFormat.Png);
        }
    }
    sealed class State {
        public int frame,flow,dream,session,sessionState,rawMap,map,menu,selection=-1,rawCard,operation,cardState,year,day,stored,newGame,flash,timer,paused,link,mapState,text,armed,pad;
        public uint mapVtable,mapDream,cardVtable;
        public uint buttons,pressed,released;
        public string saveHash="-";
        public bool active {get{return map!=0 && link!=0 && mapState==0;}}
    }
    static int Find(byte[] ram,uint vtable,int offset,uint value) {
        int found=0;
        for(int at=0x90000;at<=0x1ef000;at+=4)if(Word(ram,at)==vtable && (offset<0 || Word(ram,at+offset)==value)) {
            if(found!=0)throw new Exception("Ambiguous native object binding "+vtable.ToString("x8"));found=at;
        }
        return found;
    }
    static State Observe(byte[] ram,int frame) {
        var s=new State{frame=frame};
        if(Word(ram,0x6f61c)!=0x800454c4 || Word(ram,0x8184c)!=0x80047694)return s;
        s.flow=Pointer(Word(ram,0x8ac20),0x2c);if(s.flow==0 || Word(ram,s.flow)!=0x8006d3c8)return s;
        s.dream=Pointer(Word(ram,s.flow+0x28),0x928);if(s.dream==0 || Word(ram,s.dream)!=0x80087bdc)throw new Exception("Invalid dream root");
        s.year=(int)Word(ram,s.dream+0x17c);s.day=(int)Word(ram,s.dream+0x180);s.stored=(int)Word(ram,s.dream+0x88c);
        s.newGame=(int)Word(ram,s.dream+0x878);s.flash=(int)Word(ram,s.dream+0x68);s.timer=(int)Word(ram,s.dream+0x24);s.paused=(int)Word(ram,s.dream+0x6c);
        s.saveHash=Hash(Slice(ram,s.dream+0x178,1792));
        uint dream=(uint)s.dream|0x80000000,graphics=Word(ram,s.flow+0x1c);
        if(MainAddress!=0 && (Word(ram,MainAddress)!=0x80086b60 || Word(ram,MainAddress+0xa4)!=dream))MainAddress=0;
        if(MainAddress==0 && frame%12==0)MainAddress=Find(ram,0x80086b60,0xa4,dream);
        s.menu=MainAddress;
        if(s.menu!=0) {
            if(Word(ram,s.menu+0xc)!=graphics)throw new Exception("Menu graphics identity changed");
            MainSeen=true;s.selection=(int)Word(ram,s.menu+0x58);int card=Pointer(Word(ram,s.menu+0xac),0x84);
            s.rawCard=card;if(card!=0)s.cardVtable=Word(ram,card);
            if(card!=0 && s.cardVtable==0x80086dc4) {
                s.operation=(int)Word(ram,card+0x24);s.cardState=(int)Word(ram,card+0x28);
                if(!LoadReturned && s.operation==1 && s.cardState!=0)LoadSeen=true;
                if(LoadSeen && !LoadReturned && s.operation==0 && s.cardState==0) {
                    if(s.saveHash!=ExpectedPayloadHash)throw new Exception("Original card UI did not load full pinned payload");LoadReturned=true;
                }
            }
        }
        // Successful Load clears the new-game flag in func_8004E230. A child
        // pointer can be retired while its parent still carries the old value.
        if(LoadSeen && !LoadReturned && s.newGame==0 && s.saveHash==ExpectedPayloadHash)LoadReturned=true;
        s.session=Find(ram,0x800865c8,0x38,dream);
        if(s.session!=0) {
            s.sessionState=(int)Word(ram,s.session+0x3c);s.rawMap=Pointer(Word(ram,s.session+0x4c),0x88);
            if(s.rawMap!=0) {s.mapVtable=Word(ram,s.rawMap);s.mapDream=Word(ram,s.rawMap+0x3c);}
            // The session constructor does not initialize m_MapScene. Its value is
            // usable only after the complete map/table/root predicate matches.
            if(s.rawMap!=0 && s.mapVtable==0x80087034 && s.mapDream==dream) {
                s.map=s.rawMap;
                s.link=(int)Word(ram,s.map+0x68);s.mapState=(int)Word(ram,s.map+0x20);s.text=(int)Word(ram,s.map+0x80);s.armed=(int)Word(ram,s.map+0x84);
            }
        }
        s.pad=Find(ram,0x8006d370,-1,0);
        if(s.pad!=0){s.buttons=Word(ram,s.pad+0x10);s.released=Word(ram,s.pad+0x14);s.pressed=Word(ram,s.pad+0x18);}
        return s;
    }
    // Local transport bits, distinct from the guest's byte-swapped PadRead masks.
    const int Circle=1,Up=2,Down=4,Start=8,Select=16,Triangle=32;
    static int Sequence(int age) {
        if(age>=10 && age<22)return Triangle;                         // unpaused confirm guard
        if(age>=30 && age<56)return Select | (age>=42?Triangle:0);     // no overlay guard
        if(age>=60 && age<72)return Start;
        if(age>=90 && age<102)return Triangle;                        // overlay without arm
        if(age>=115 && age<137)return Select;                         // arm, then release
        if(age>=148 && age<160)return Triangle;                       // released Select guard
        if(age>=175 && age<187)return Start;                          // resume
        if(age>=215 && age<227)return Start;                          // pause again
        if(age>=240 && age<276)return Select | (age>=252?Triangle:0); // original reset chord
        return 0;
    }
    static int Policy(int frame,State previous,string mode) {
        bool pulse=frame%120>=60 && frame%120<72;
        if(previous==null)return 0;
        if(!MainSeen)return pulse?Circle:0;
        if(!LoadReturned) {
            if(previous.menu==0 || !pulse)return 0;
            if(previous.operation!=0 || LoadSeen)return Circle;
            return previous.selection<3?Down:previous.selection>3?Up:Circle;
        }
        if(SequenceStart<0) {
            if(previous.active && previous.timer>=60) {
                if(previous.flash!=(mode=="flashback"?1:0))throw new Exception("Wrong native dream mode");
                SequenceStart=frame;return 0;
            }
            if(previous.menu==0 || !pulse)return 0;
            int wanted=mode=="flashback"?1:0;return previous.selection>wanted?Up:previous.selection<wanted?Down:Circle;
        }
        if(!ResetSeen)return Sequence(frame-SequenceStart);
        if(previous.menu!=0) {
            PostMenuSeen=true;if(!pulse)return 0;return previous.selection>0?Up:Circle;
        }
        if(PostMenuSeen && previous.active && previous.flash==0) {
            if(!PostDreamSeen){PostDreamSeen=true;PostDreamFrame=frame;}
            int age=frame-PostDreamFrame;return age>=30 && age<42?Up:0;
        }
        return 0;
    }
    public sealed class Target {public string name{get;set;}public uint pc{get;set;}public int bytes{get;set;}public string sha256{get;set;}}
    sealed class Trace : IDisposable {
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]delegate int ResetCall();
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]delegate int AddCall(uint pc,uint bytes);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]delegate int ConfigCall(uint a,uint b,uint c,uint d);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]delegate void FrameCall(uint frame);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]delegate uint NumberCall();
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]delegate IntPtr PointerCall();
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]delegate void VoidCall();
        readonly WaterboxHost Host;readonly ResetCall Reset,StartTrace;readonly AddCall Add;readonly ConfigCall Configure;readonly FrameCall BeginFrame;
        readonly NumberCall Count,Total,Overflow;readonly PointerCall Events;readonly VoidCall Disable;
        readonly Dictionary<uint,Target> Targets;readonly StreamWriter Writer;readonly GZipStream Zipped;readonly FileStream File;
        public readonly Dictionary<string,int> counts=new Dictionary<string,int>();
        public bool enabled;public int total;public int resetCalls;
        public Trace(Nymashock core,string output,Target[] targets,bool observe) {
            Targets=targets.ToDictionary(t=>t.pc);foreach(var target in targets)counts[target.name]=0;
            if(!observe)return;
            Host=(WaterboxHost)typeof(WaterboxCore).GetField("_exe",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(core);
            Host.Enter();try {
                var adapter=CallingConventionAdapters.GetWaterboxUnsafeUnwrapped();
                Reset=adapter.GetDelegateForFunctionPointer<ResetCall>(Host.GetProcAddrOrThrow("LsdResetDispatchTrace"));
                StartTrace=adapter.GetDelegateForFunctionPointer<ResetCall>(Host.GetProcAddrOrThrow("LsdStartDispatchTrace"));
                Add=adapter.GetDelegateForFunctionPointer<AddCall>(Host.GetProcAddrOrThrow("LsdAddDispatchTarget"));
                Configure=adapter.GetDelegateForFunctionPointer<ConfigCall>(Host.GetProcAddrOrThrow("LsdConfigureDispatchWords"));
                BeginFrame=adapter.GetDelegateForFunctionPointer<FrameCall>(Host.GetProcAddrOrThrow("LsdBeginDispatchFrame"));
                Count=adapter.GetDelegateForFunctionPointer<NumberCall>(Host.GetProcAddrOrThrow("LsdGetDispatchCount"));
                Total=adapter.GetDelegateForFunctionPointer<NumberCall>(Host.GetProcAddrOrThrow("LsdGetDispatchTotal"));
                Overflow=adapter.GetDelegateForFunctionPointer<NumberCall>(Host.GetProcAddrOrThrow("LsdGetDispatchOverflow"));
                Events=adapter.GetDelegateForFunctionPointer<PointerCall>(Host.GetProcAddrOrThrow("LsdGetDispatchEvents"));
                Disable=adapter.GetDelegateForFunctionPointer<VoidCall>(Host.GetProcAddrOrThrow("LsdDisableDispatchTrace"));
            }finally{Host.Exit();}
            File=new FileStream(Path.Combine(output,"entries.jsonl.gz"),FileMode.CreateNew);
            Zipped=new GZipStream(File,CompressionLevel.Optimal,true);Writer=new StreamWriter(Zipped,new UTF8Encoding(false));Writer.NewLine="\n";
        }
        public void Begin(int frame,State state) {
            if(Host==null || (!LoadSeen && SequenceStart<0))return;
            Host.Enter();try {
                if(!enabled) {
                    if(Reset()!=1)throw new Exception("Observer reset rejected");
                    foreach(var target in Targets.Values)if(Add(target.pc,(uint)target.bytes)!=1)throw new Exception("Observer target rejected");
                    enabled=true;
                }
                uint dream=state.dream==0?0x8008b388:(uint)state.dream|0x80000000;
                uint map=state.map==0?0x8008b388:(uint)state.map|0x80000000;
                if(Configure(dream+0x180,dream+0x68,map+0x80,map+0x84)!=1 || StartTrace()!=1)throw new Exception("Observer setup rejected");
                BeginFrame((uint)frame);
            }finally{Host.Exit();}
        }
        public void Drain(int frame) {
            if(!enabled)return;
            Host.Enter();try {
                uint count=Count();if(count>1024 || Overflow()!=0)throw new Exception("Native observer overflow");
                IntPtr baseAddress=Events();
                for(int i=0;i<count;i++) {
                    var raw=new byte[4356];Marshal.Copy(IntPtr.Add(baseAddress,i*4356),raw,0,raw.Length);
                    uint pc=Word(raw,4);Target target;if(!Targets.TryGetValue(pc,out target))throw new Exception("Unregistered native PC");
                    int bytes=(int)Word(raw,256);
                    if(Word(raw,0)!=(uint)frame || bytes!=target.bytes || Hash(Slice(raw,260,bytes))!=target.sha256)throw new Exception("Complete native body pin differs");
                    counts[target.name]++;total++;if(pc==0x8005a258)resetCalls++;
                    Writer.WriteLine(Json.Serialize(new {frame,name=target.name,pc,a0=Word(raw,8),a1=Word(raw,12),a2=Word(raw,16),a3=Word(raw,20),ra=Word(raw,24),sp=Word(raw,28),
                        timestamp=Word(raw,32),transfer_pc=Word(raw,40),delay_pc=Word(raw,44),transfer_word=Word(raw,48),delay_word=Word(raw,52),
                        receiver_words=Enumerable.Range(0,11).Select(n=>Word(raw,56+n*4)).ToArray(),
                        memory_words=Enumerable.Range(0,4).Select(n=>Word(raw,240+n*4)).ToArray(),code_bytes=bytes,code_sha256=target.sha256}));
                }
                if(Total()!=(uint)total)throw new Exception("Native event total differs");
            }finally{Host.Exit();}
            Writer.Flush();if(File.Length>1024*1024)throw new Exception("Compressed native entry journal bound reached");
        }
        public void Dispose() {
            if(Host!=null && enabled){Host.Enter();try{Disable();}finally{Host.Exit();}}
            if(Writer!=null){Writer.Dispose();File.Dispose();}
        }
    }
    sealed class Window : IDisposable {
        readonly Dictionary<string,BoundedSha256Stream> Channels=new Dictionary<string,BoundedSha256Stream>();
        readonly Dictionary<string,long> Counts=new Dictionary<string,long>();public readonly int first;public long samples;
        public Window(int frame){first=frame;foreach(string key in new[]{"MainRAM","GPURAM","RGB","PCM","native","controller"}){Channels[key]=new BoundedSha256Stream(4L*1024*1024*1024);Counts[key]=0;}}
        public void Add(string key,int frame,byte[] bytes){byte[] head=new byte[12];Buffer.BlockCopy(new[]{frame,frame+1,bytes.Length},0,head,0,12);Channels[key].Write(head,0,12);Channels[key].Write(bytes,0,bytes.Length);Counts[key]+=bytes.Length;}
        public object Finish(int frame){return new {first_frame=first,last_frame=frame,frames=frame-first+1,PCM_sample_frames=samples,payload_bytes=Counts,framed_sha256=Channels.ToDictionary(p=>p.Key,p=>p.Value.CompleteHash())};}
        public void Dispose(){foreach(var stream in Channels.Values)stream.Dispose();}
    }
    public static int Main(string[] args) {
        try {
            if(args.Length!=12)throw new Exception("runtime cue BIOS-J BIOS-U BIOS-E output normal|flashback ceiling replay-or-dash raw-card targets observer|stock");
            DllRoot=Path.Combine(args[0],"dll");AppDomain.CurrentDomain.AssemblyResolve+=delegate(object sender,ResolveEventArgs ev){string path=Path.Combine(DllRoot,new AssemblyName(ev.Name).Name+".dll");return File.Exists(path)?Assembly.LoadFrom(path):null;};
            if(!SetDllDirectory(DllRoot))throw new Exception("SetDllDirectory failed");return Run(args);
        }catch(Exception error){Console.Error.WriteLine(error);return 2;}
    }
    static int Run(string[] args) {
        string output=args[5],mode=args[6];int ceiling=Int32.Parse(args[7]);bool observe=args[11]=="observer";
        if(Directory.Exists(output) || File.Exists(output) || (mode!="normal" && mode!="flashback") || ceiling<1 || ceiling>18000 || (!observe && args[11]!="stock"))throw new Exception("Invalid fresh bounded reset capture");
        byte[] card=File.ReadAllBytes(args[9]);if(card.Length!=131072 || card[0]!='M' || card[1]!='C')throw new Exception("Require pinned raw QA card");
        ExpectedPayloadHash=Hash(Slice(card,8192+512,1792));Target[] targets=Json.Deserialize<Target[]>(File.ReadAllText(args[10]));
        string[][] replay=args[8]=="-"?null:File.ReadAllLines(args[8]).Skip(1).Select(line=>line.Split('\t')).ToArray();
        if(replay!=null && (replay.Length==0 || replay[0][0]!="0" || replay[0][1]!="0"))throw new Exception("Replay must begin neutral");
        Directory.CreateDirectory(output);Database.InitializeDatabase(Path.Combine(args[0],"gamedb"),output,true);
        var comm=new CoreComm(m=>Console.Error.WriteLine(m),(m,d)=>Console.Error.WriteLine(m),new ReplayColdStart.Files(new[]{args[2],args[3],args[4]},output),(CoreComm.CorePreferencesFlags)0,null);
        using(var disc=Disc.LoadAutomagic(args[1])) {
            var parameters=new CoreLoadParameters<NymaCore.NymaSettings,NymaCore.NymaSyncSettings>{Comm=comm,Game=new GameInfo{Name="LSD Japanese controller reset",System="PSX"},Settings=null,SyncSettings=null,Roms=new List<IRomAsset>(),Discs=new List<IDiscAsset>{new ReplayColdStart.DiscAsset(disc,"LSD Japanese")},DeterministicEmulationRequested=false};
            using(var core=new Nymashock(parameters)) {
                var domains=core.ServiceProvider.GetService<IMemoryDomains>();var ram=domains.MainMemory;var gpu=domains["GPURAM"];
                if(ram.Size!=0x200000 || gpu.Size!=0x100000 || core.Frame!=0)throw new Exception("Unexpected cold core");
                byte[] beforeRAM=Read(ram),beforeGPU=Read(gpu);var saves=(ISaveRam)core;byte[] initial=saves.CloneSaveRam(false),expected=(byte[])initial.Clone();
                if(expected.Length<card.Length || expected.Length%card.Length!=0 || expected.Length>2*1024*1024)throw new Exception("SaveRAM layout differs");
                Buffer.BlockCopy(card,0,expected,0,card.Length);saves.StoreSaveRam(expected);
                if(!saves.CloneSaveRam(false).SequenceEqual(expected) || core.Frame!=0 || !beforeRAM.SequenceEqual(Read(ram)) || !beforeGPU.SequenceEqual(Read(gpu)))throw new Exception("External card setup changed guest state");
                Write(output,"card-store.json",new {input_card_sha256=Hash(card),initial_SaveRAM_sha256=Hash(initial),stored_SaveRAM_sha256=Hash(expected),expected_payload_sha256=ExpectedPayloadHash,MainRAM_sha256=Hash(beforeRAM),GPURAM_sha256=Hash(beforeGPU),guest_RAM_or_instruction_writes=false,state_restored=false});
                var input=new ReplayColdStart.Input(core.ControllerDefinition);string[] names={"P1 \u25cb","P1 D-Pad Up","P1 D-Pad Down","P1 Start","P1 Select","P1 \u25b3"};
                foreach(string name in names)if(!input.Buttons.ContainsKey(name))throw new Exception("Controller definition missing "+name);
                State previous=null;int lastMask=-1,mask=0,replayIndex=0,lastFrame=-1;long samplesTotal=0,rawRows=0;string lastSave="-",outcome="frame_ceiling_reached";
                var clock=Stopwatch.StartNew();Window window=new Window(0);
                using(var trace=new Trace(core,output,targets,observe))
                using(var inputs=new StreamWriter(File.Open(Path.Combine(output,"inputs.tsv"),FileMode.CreateNew),new UTF8Encoding(false)))
                using(var windows=new StreamWriter(File.Open(Path.Combine(output,"windows.jsonl"),FileMode.CreateNew),new UTF8Encoding(false)))
                using(var saveFile=new GZipStream(File.Open(Path.Combine(output,"save-blocks.jsonl.gz"),FileMode.CreateNew),CompressionLevel.Optimal))
                using(var snapshots=new StreamWriter(saveFile,new UTF8Encoding(false))) {
                    inputs.NewLine="\n";windows.NewLine="\n";snapshots.NewLine="\n";inputs.WriteLine("frame\tmask");
                    for(int frame=0;frame<=ceiling;frame++) {
                        if(File.Exists(Path.Combine(output,"STOP"))){outcome="owned_stop_requested";break;}
                        int planned=Policy(frame,previous,mode);
                        if(replay==null)mask=planned;
                        else if(replayIndex<replay.Length && Int32.Parse(replay[replayIndex][0])==frame){mask=Int32.Parse(replay[replayIndex][1]);replayIndex++;}
                        if(mask<0 || mask>=64 || (replay!=null && mask!=planned))throw new Exception("Controller replay diverged from observed state policy at "+frame);
                        if(mask!=lastMask){inputs.WriteLine(frame+"\t"+mask);lastMask=mask;}
                        for(int i=0;i<names.Length;i++)input.Buttons[names[i]]=(mask&(1<<i))!=0;
                        trace.Begin(frame,previous);core.FrameAdvance(input,true,true);if(core.Frame!=frame+1)throw new Exception("Frame schedule differs");trace.Drain(frame);
                        byte[] ramBytes=Read(ram),gpuBytes=Read(gpu);State state=Observe(ramBytes,frame);int age=SequenceStart<0?-1:frame-SequenceStart;
                        if(SequenceStart>=0 && !ResetSeen && state.dream!=0 && state.year==0 && state.day==0 && state.newGame==1 && state.saveHash!=ExpectedPayloadHash) {
                            ResetSeen=true;ResetFrame=frame;if(replay==null)Image(core,Path.Combine(output,"reset.png"));
                        }
                        if(state.dream!=0 && (state.saveHash!=lastSave || (age>=0 && age<=290 && age%10==0) || frame==ResetFrame)) {
                            snapshots.WriteLine(Json.Serialize(new {frame,sequence_age=age,state,object_base64=Convert.ToBase64String(Slice(ramBytes,state.dream,0x928)),save_sha256=state.saveHash,
                                pad_table=Enumerable.Range(0,16).Select(n=>Word(ramBytes,0x8b388+n*4)).ToArray()}));lastSave=state.saveHash;
                        }
                        byte[] native=Encoding.UTF8.GetBytes(Json.Serialize(state));rawRows+=native.Length;
                        short[] samples;int count;core.GetSamplesSync(out samples,out count);if(count<0 || count>5000 || samples.Length<count*2)throw new Exception("PCM layout differs");
                        byte[] pcm=new byte[count*4];Buffer.BlockCopy(samples,0,pcm,0,pcm.Length);byte[] rgb=RGB(core);
                        window.Add("MainRAM",frame,ramBytes);window.Add("GPURAM",frame,gpuBytes);window.Add("RGB",frame,rgb);window.Add("PCM",frame,pcm);window.Add("native",frame,native);window.Add("controller",frame,BitConverter.GetBytes(mask));window.samples+=count;samplesTotal+=count;
                        bool complete=PostDreamSeen && frame>=PostDreamFrame+180,stop=frame==ceiling || complete;
                        if(complete)outcome="controller_reset_returned_to_menu_and_new_dream_played";
                        if(frame%300==299 || stop) {
                            windows.WriteLine(Json.Serialize(window.Finish(frame)));windows.Flush();inputs.Flush();snapshots.Flush();window.Dispose();window=stop?null:new Window(frame+1);
                            Write(output,"progress.json",new {frame,core_frame=core.Frame,elapsed_ms=clock.ElapsedMilliseconds,sequence_start=SequenceStart,reset_frame=ResetFrame,post_dream_frame=PostDreamFrame,load_seen=LoadSeen,load_returned=LoadReturned,state,native_entries=trace.total});Console.WriteLine("FRAME "+frame);
                            if(Directory.EnumerateFiles(output).Sum(p=>new FileInfo(p).Length)>2*1024*1024)throw new Exception("Bounded capture files exceeded 2 MiB");
                        }
                        previous=state;lastFrame=frame;if(stop)break;
                    }
                    if(window!=null)window.Dispose();
                    byte[] finalSave=saves.CloneSaveRam(false);
                    if(replay==null)Image(core,Path.Combine(output,"final.png"));
                    Write(output,"report.json",new {schema_version=1,status=outcome,mode,observer_enabled=observe,frames_advanced=lastFrame+1,last_frame=lastFrame,sequence_start=SequenceStart,reset_frame=ResetFrame,post_dream_frame=PostDreamFrame,
                        load_seen=LoadSeen,load_returned=LoadReturned,reset_seen=ResetSeen,post_menu_seen=PostMenuSeen,post_dream_seen=PostDreamSeen,native_entry_counts=trace.counts,native_entries=trace.total,native_reset_calls=trace.resetCalls,
                        input_card_sha256=Hash(card),final_SaveRAM_sha256=Hash(finalSave),external_card_unchanged=finalSave.SequenceEqual(expected),replayed_inputs=replay!=null,replay_entries_used=replayIndex,replay_entries_supplied=replay==null?0:replay.Length,
                        total_PCM_sample_frames=samplesTotal,streamed_native_row_bytes=rawRows,elapsed_ms=clock.ElapsedMilliseconds,final_state=previous,
                        cold_start=true,guest_RAM_or_instruction_writes=false,restored_state=false,player_UI_or_saves_changed=false,hardware_timing_verified=false,whole_feature_groups_accepted=0});
                }
                return outcome=="controller_reset_returned_to_menu_and_new_dream_played"?0:1;
            }
        }
    }
}
}
