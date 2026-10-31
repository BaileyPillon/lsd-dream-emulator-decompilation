// Cold-boot reset/Save and a separate cold Load of the native-written card.
// No state restoration or guest RAM writes; only separate QA card buffers.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Text;
using BizHawk.Common;
using BizHawk.Emulation.Common;
using BizHawk.Emulation.Cores;
using BizHawk.Emulation.Cores.Sony.PSX;
using BizHawk.Emulation.Cores.Waterbox;
using BizHawk.Emulation.DiscSystem;

namespace Lsd.Research.Headless {
internal static class RecordResetCardRoundtripWindows {
    public static int Main(string[] args) { return RecordNewGameResetWindows.CardRoundtripMain(args); }
}
internal static partial class RecordNewGameResetWindows {
    static bool NativeSaveSeen,NativeSaveIdle;
    static int SaveSeenFrame=-1,SaveIdleFrame=-1,InitialLoadIdleFrame=-1;
    static string ResetPayloadHash,NativeSavedPayloadHash,NativeSavedName;
    static byte[] NativeSavedCard;
    sealed class CardSelection {
        public int card,child,count,index=-1,targetIndex=-1;
        public bool ready;
        public string prefix="-";
        public string[] names=new string[0];
    }
    static string NativeASCII(byte[] ram,uint pointer,int bound) {
        int at=Pointer(pointer,bound);if(at==0)return "-";
        int length=0;
        while(length<bound && ram[at+length]!=0) {
            if(ram[at+length]<32 || ram[at+length]>126)return "<non-ascii>";
            length++;
        }
        return length==bound?"<unterminated>":Encoding.ASCII.GetString(ram,at,length);
    }
    static string RuntimeCardName(byte[] ram) { return NativeASCII(ram,Word(ram,0x8aa10),64); }
    static CardSelection ReadCardSelection(byte[] ram,State state,string wanted) {
        var result=new CardSelection();
        if(state.rawCard==0 || state.cardVtable!=0x80086dc4)return result;
        int card=state.rawCard;result.card=card;result.count=(int)Word(ram,card+0x2c);
        int names=Pointer(Word(ram,card+0x3c),64);result.prefix=NativeASCII(ram,Word(ram,card+0x30),64);
        result.child=Pointer(Word(ram,card+0x7c),0x54);
        if(result.child==0 || Word(ram,result.child)!=0x80086f88 || names==0 || result.count<1 || result.count>15)return result;
        result.index=(int)Word(ram,result.child+0x28);
        result.names=Enumerable.Range(0,result.count).Select(i=>result.prefix+NativeASCII(ram,Word(ram,names+i*4),64)).ToArray();
        result.targetIndex=Array.IndexOf(result.names,wanted);
        result.ready=Word(ram,result.child+0x50)!=0 && result.index>=0 && result.index<result.count && result.targetIndex>=0;
        return result;
    }
    static int TargetRow(State state,int row,bool pulse) {
        if(!pulse || state.menu==0 || state.selection<0 || state.selection>4)return 0;
        return state.selection>row?Up:state.selection<row?Down:Circle;
    }
    static int LoadCardPolicy(int frame,State state,CardSelection selection) {
        bool pulse=frame%120>=60 && frame%120<72;
        if(!MainSeen)return pulse?Circle:0;
        if(state==null || state.menu==0 || !pulse)return 0;
        if(state.operation==1 && state.cardState==18) {
            if(!selection.ready)return 0;
            return selection.index>selection.targetIndex?Up:selection.index<selection.targetIndex?Down:Circle;
        }
        if(state.operation!=0 || LoadSeen)return Circle;
        return TargetRow(state,3,pulse);
    }
    static int RoundtripPolicy(int frame,State state,CardSelection selection,string mode) {
        if(!LoadReturned)return LoadCardPolicy(frame,state,selection);
        bool pulse=frame%120>=60 && frame%120<72;
        if(mode=="save") {
            if(!ResetSeen)return Policy(frame,state,"normal");
            if(state==null || state.menu==0 || NativeSaveIdle)return 0;
            PostMenuSeen=true;
            if(state.operation!=0 || NativeSaveSeen)return pulse?Circle:0;
            return TargetRow(state,2,pulse);
        }
        if(state.menu!=0){PostMenuSeen=true;return TargetRow(state,0,pulse);}
        if(state.active && state.flash==0) {
            if(!PostDreamSeen){PostDreamSeen=true;PostDreamFrame=frame;}
            int age=frame-PostDreamFrame;return age>=30 && age<42?Up:0;
        }
        return 0;
    }
    static string RoundtripPhase(string mode) {
        if(!LoadReturned)return "cold_load";
        if(mode=="load")return "play_after_cold_load";
        if(!ResetSeen)return "dream_and_reset";
        return NativeSaveIdle?"native_save_idle":NativeSaveSeen?"saving":"select_save";
    }
    internal static int CardRoundtripMain(string[] args) {
        try {
            if(args.Length!=14)throw new Exception("runtime cue BIOS-J BIOS-U BIOS-E output save|load ceiling replay-or-dash QA-card targets observer|stock target-filename expected-payload-sha256");
            DllRoot=Path.Combine(args[0],"dll");
            AppDomain.CurrentDomain.AssemblyResolve+=delegate(object sender,ResolveEventArgs ev){string path=Path.Combine(DllRoot,new AssemblyName(ev.Name).Name+".dll");return File.Exists(path)?Assembly.LoadFrom(path):null;};
            if(!SetDllDirectory(DllRoot))throw new Exception("SetDllDirectory failed");
            return RunCardRoundtrip(args);
        }catch(Exception error){Console.Error.WriteLine(error);return 2;}
    }
    static int RunCardRoundtrip(string[] args) {
        string output=args[5],mode=args[6],wanted=args[12];int ceiling=Int32.Parse(args[7]);bool observe=args[11]=="observer";
        if(Directory.Exists(output) || File.Exists(output) || ceiling<1 || ceiling>30000 || (mode!="save" && mode!="load") || (!observe && args[11]!="stock"))throw new Exception("Invalid fresh bounded card capture");
        byte[] card=File.ReadAllBytes(args[9]);
        if(card.Length!=131072 || card[0]!='M' || card[1]!='C')throw new Exception("Require pinned raw QA card");
        ExpectedPayloadHash=args[13];if(ExpectedPayloadHash.Length!=64 || wanted.Length<1 || wanted.Length>20)throw new Exception("Invalid pinned file/payload identity");
        Target[] targets=Json.Deserialize<Target[]>(File.ReadAllText(args[10]));
        string[][] replay=args[8]=="-"?null:File.ReadAllLines(args[8]).Skip(1).Select(line=>line.Split('\t')).ToArray();
        if(replay!=null && (replay.Length==0 || replay[0][0]!="0" || replay[0][1]!="0"))throw new Exception("Replay must start neutral");
        Directory.CreateDirectory(output);Database.InitializeDatabase(Path.Combine(args[0],"gamedb"),output,true);
        var comm=new CoreComm(m=>Console.Error.WriteLine(m),(m,d)=>Console.Error.WriteLine(m),new ReplayColdStart.Files(new[]{args[2],args[3],args[4]},output),(CoreComm.CorePreferencesFlags)0,null);
        using(var disc=Disc.LoadAutomagic(args[1])) {
            var parameters=new CoreLoadParameters<NymaCore.NymaSettings,NymaCore.NymaSyncSettings>{Comm=comm,Game=new GameInfo{Name="LSD Japanese reset persisted card",System="PSX"},Settings=null,SyncSettings=null,Roms=new List<IRomAsset>(),Discs=new List<IDiscAsset>{new ReplayColdStart.DiscAsset(disc,"LSD Japanese")},DeterministicEmulationRequested=false};
            using(var core=new Nymashock(parameters)) {
                var domains=core.ServiceProvider.GetService<IMemoryDomains>();var ram=domains.MainMemory;var gpu=domains["GPURAM"];
                if(ram.Size!=0x200000 || gpu.Size!=0x100000 || core.Frame!=0)throw new Exception("Unexpected cold core");
                var saves=(ISaveRam)core;byte[] initial=saves.CloneSaveRam(false),expected=(byte[])initial.Clone();
                if(expected.Length!=card.Length)throw new Exception("Require one 128 KiB card domain");
                byte[] beforeRAM=Read(ram),beforeGPU=Read(gpu);Buffer.BlockCopy(card,0,expected,0,card.Length);saves.StoreSaveRam(expected);
                if(!saves.CloneSaveRam(false).SequenceEqual(expected) || core.Frame!=0 || !beforeRAM.SequenceEqual(Read(ram)) || !beforeGPU.SequenceEqual(Read(gpu)))throw new Exception("QA card setup changed guest RAM/GPU/frame");
                Write(output,"card-store.json",new {input_card_sha256=Hash(card),initial_SaveRAM_sha256=Hash(initial),stored_SaveRAM_sha256=Hash(expected),target_filename=wanted,expected_payload_sha256=ExpectedPayloadHash,MainRAM_sha256=Hash(beforeRAM),GPURAM_sha256=Hash(beforeGPU),guest_RAM_or_instruction_writes=false,state_restored=false});
                var input=new ReplayColdStart.Input(core.ControllerDefinition);string[] names={"P1 \u25cb","P1 D-Pad Up","P1 D-Pad Down","P1 Start","P1 Select","P1 \u25b3"};
                foreach(string name in names)if(!input.Buttons.ContainsKey(name))throw new Exception("Missing controller button");
                State previous=null;CardSelection priorSelection=new CardSelection();int mask=0,lastMask=-1,replayIndex=0,lastFrame=-1;long totalSamples=0;
                string lastSave="-",lastTransition="",outcome="frame_ceiling_reached",preLoadPayloadHash=null;
                var clock=Stopwatch.StartNew();Window window=new Window(0);
                using(var trace=new Trace(core,output,targets,observe))
                using(var inputs=new StreamWriter(File.Open(Path.Combine(output,"inputs.tsv"),FileMode.CreateNew),new UTF8Encoding(false)))
                using(var windows=new StreamWriter(File.Open(Path.Combine(output,"windows.jsonl"),FileMode.CreateNew),new UTF8Encoding(false)))
                using(var stateZip=new GZipStream(File.Open(Path.Combine(output,"transitions.jsonl.gz"),FileMode.CreateNew),CompressionLevel.Optimal))
                using(var transitions=new StreamWriter(stateZip,new UTF8Encoding(false)))
                using(var saveZip=new GZipStream(File.Open(Path.Combine(output,"save-blocks.jsonl.gz"),FileMode.CreateNew),CompressionLevel.Optimal))
                using(var snapshots=new StreamWriter(saveZip,new UTF8Encoding(false))) {
                    inputs.NewLine="\n";windows.NewLine="\n";transitions.NewLine="\n";snapshots.NewLine="\n";inputs.WriteLine("frame\tmask");
                    for(int frame=0;frame<=ceiling;frame++) {
                        if(File.Exists(Path.Combine(output,"STOP"))){outcome="owned_stop_requested";break;}
                        int planned=RoundtripPolicy(frame,previous,priorSelection,mode);
                        if(replay==null)mask=planned;
                        else if(replayIndex<replay.Length && Int32.Parse(replay[replayIndex][0])==frame){mask=Int32.Parse(replay[replayIndex][1]);replayIndex++;}
                        if(mask<0 || mask>=64 || (replay!=null && mask!=planned))throw new Exception("Replay/policy divergence at "+frame);
                        if(mask!=lastMask){inputs.WriteLine(frame+"\t"+mask);lastMask=mask;}
                        for(int i=0;i<names.Length;i++)input.Buttons[names[i]]=(mask&(1<<i))!=0;
                        trace.Begin(frame,previous);core.FrameAdvance(input,true,true);if(core.Frame!=frame+1)throw new Exception("Skipped core frame");trace.Drain(frame);
                        byte[] ramBytes=Read(ram),gpuBytes=Read(gpu);State state=Observe(ramBytes,frame);CardSelection selection=ReadCardSelection(ramBytes,state,wanted);
                        bool boundary=false;int age=SequenceStart<0?-1:frame-SequenceStart;
                        if(preLoadPayloadHash==null && state.dream!=0)preLoadPayloadHash=state.saveHash;
                        if(LoadReturned && InitialLoadIdleFrame<0){InitialLoadIdleFrame=frame;boundary=true;}
                        if(mode=="save" && SequenceStart>=0 && !ResetSeen && state.dream!=0 && state.year==0 && state.day==0 && state.newGame==1 && state.saveHash!=ExpectedPayloadHash){ResetSeen=true;ResetFrame=frame;ResetPayloadHash=state.saveHash;boundary=true;}
                        if(mode=="save" && ResetSeen && state.operation==2 && state.cardState!=0 && !NativeSaveSeen){NativeSaveSeen=true;SaveSeenFrame=frame;boundary=true;}
                        if(NativeSaveSeen && !NativeSaveIdle && state.menu!=0 && state.operation==0 && state.cardState==0 && state.newGame==0) {
                            NativeSaveIdle=true;SaveIdleFrame=frame;NativeSavedPayloadHash=state.saveHash;NativeSavedCard=saves.CloneSaveRam(false);NativeSavedName=RuntimeCardName(ramBytes);boundary=true;
                            File.WriteAllBytes(Path.Combine(output,"saved-card.SaveRAM"),NativeSavedCard);
                            if(replay==null)Image(core,Path.Combine(output,"after-save.png"));
                        }
                        string phase=RoundtripPhase(mode),cardName=state.dream==0?"-":RuntimeCardName(ramBytes);
                        string signature=Json.Serialize(new {state.flow,state.dream,state.menu,state.selection,state.rawCard,state.cardVtable,state.operation,state.cardState,state.year,state.day,state.newGame,state.saveHash,phase,cardName,selection.index,selection.targetIndex,selection.ready});
                        if(signature!=lastTransition || boundary){transitions.WriteLine(Json.Serialize(new {frame,phase,state,card_name=cardName,selection}));lastTransition=signature;}
                        if(state.dream!=0 && (state.saveHash!=lastSave || boundary || (age>=0 && age<=290 && age%10==0))) {
                            snapshots.WriteLine(Json.Serialize(new {frame,sequence_age=age,phase,state,object_base64=Convert.ToBase64String(Slice(ramBytes,state.dream,0x928)),save_sha256=state.saveHash,pad_table=Enumerable.Range(0,16).Select(n=>Word(ramBytes,0x8b388+n*4)).ToArray()}));lastSave=state.saveHash;
                        }
                        short[] samples;int count;core.GetSamplesSync(out samples,out count);if(count<0 || count>5000 || samples.Length<count*2)throw new Exception("Invalid PCM");
                        byte[] pcm=new byte[count*4];Buffer.BlockCopy(samples,0,pcm,0,pcm.Length);byte[] native=Encoding.UTF8.GetBytes(Json.Serialize(state)),rgb=RGB(core);
                        window.Add("MainRAM",frame,ramBytes);window.Add("GPURAM",frame,gpuBytes);window.Add("RGB",frame,rgb);window.Add("PCM",frame,pcm);window.Add("native",frame,native);window.Add("controller",frame,BitConverter.GetBytes(mask));window.samples+=count;totalSamples+=count;
                        bool complete=mode=="save"?(NativeSaveIdle && frame>=SaveIdleFrame+120):(PostDreamSeen && frame>=PostDreamFrame+180),stop=complete || frame==ceiling;
                        if(complete)outcome=mode=="save"?"reset_native_save_completed":"native_cold_load_and_new_dream_completed";
                        if(frame%300==299 || stop) {
                            windows.WriteLine(Json.Serialize(window.Finish(frame)));windows.Flush();inputs.Flush();transitions.Flush();snapshots.Flush();window.Dispose();window=stop?null:new Window(frame+1);
                            Write(output,"progress.json",new {frame,core_frame=core.Frame,elapsed_ms=clock.ElapsedMilliseconds,mode,phase,sequence_start=SequenceStart,reset_frame=ResetFrame,save_seen_frame=SaveSeenFrame,save_idle_frame=SaveIdleFrame,load_idle_frame=InitialLoadIdleFrame,post_dream_frame=PostDreamFrame,load_seen=LoadSeen,load_returned=LoadReturned,state,selection,native_entries=trace.total});
                            Console.WriteLine("FRAME "+frame+" "+phase);if(Directory.EnumerateFiles(output).Sum(f=>new FileInfo(f).Length)>2*1024*1024)throw new Exception("Capture exceeded 2 MiB");
                        }
                        previous=state;priorSelection=selection;lastFrame=frame;if(stop)break;
                    }
                    if(window!=null)window.Dispose();byte[] finalCard=saves.CloneSaveRam(false);
                    if(replay==null)Image(core,Path.Combine(output,"final.png"));
                    Write(output,"report.json",new {schema_version=1,status=outcome,mode,observer_enabled=observe,frames_advanced=lastFrame+1,last_frame=lastFrame,sequence_start=SequenceStart,reset_frame=ResetFrame,post_dream_frame=PostDreamFrame,
                        initial_load_idle_frame=InitialLoadIdleFrame,save_seen_frame=SaveSeenFrame,save_idle_frame=SaveIdleFrame,load_seen=LoadSeen,load_returned=LoadReturned,reset_seen=ResetSeen,post_menu_seen=PostMenuSeen,post_dream_seen=PostDreamSeen,save_seen=NativeSaveSeen,save_idle=NativeSaveIdle,
                        pre_load_payload_sha256=preLoadPayloadHash,expected_loaded_payload_sha256=ExpectedPayloadHash,target_filename=wanted,
                        reset_payload_sha256=ResetPayloadHash,saved_payload_sha256=NativeSavedPayloadHash,saved_filename=NativeSavedName,reset_payload_matches_saved_payload=ResetPayloadHash==NativeSavedPayloadHash,
                        native_entry_counts=trace.counts,native_entries=trace.total,native_reset_calls=trace.resetCalls,input_card_sha256=Hash(card),final_SaveRAM_sha256=Hash(finalCard),external_card_unchanged=finalCard.SequenceEqual(expected),
                        native_saved_card_sha256=NativeSavedCard==null?null:Hash(NativeSavedCard),final_card_matches_native_Save=NativeSavedCard!=null && finalCard.SequenceEqual(NativeSavedCard),
                        replayed_inputs=replay!=null,replay_entries_used=replayIndex,replay_entries_supplied=replay==null?0:replay.Length,total_PCM_sample_frames=totalSamples,elapsed_ms=clock.ElapsedMilliseconds,final_state=previous,
                        cold_start=true,guest_RAM_or_instruction_writes=false,restored_state=false,player_UI_or_saves_changed=false,hardware_timing_verified=false,whole_feature_groups_accepted=0});
                }
                return outcome=="reset_native_save_completed" || outcome=="native_cold_load_and_new_dream_completed"?0:1;
            }
        }
    }
}
}
