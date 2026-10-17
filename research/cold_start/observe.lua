-- Cold-start controller path. This observer never loads a state or writes game RAM.
local output=assert(os.getenv("LSD_QA_OUTPUT"))
local frames=assert(tonumber(os.getenv("LSD_QA_FRAMES")))
local function run()
assert(client.getversion()=="2.11.1" and emu.getsystemid()=="PSX")
assert(mainmemory.getname()=="MainRAM" and memory.getmemorydomainsize("MainRAM")==0x200000)
local function word(raw,p) return (string.unpack("<I4",raw,p+1)) end
local function signed(raw,p) return (string.unpack("<i4",raw,p+1)) end
local function ptr(v,size)
 if v<0x80010000 or v>0x80200000-size or v%4~=0 then return nil end
 return v&0x1fffffff
end
local sample=joypad.get()
local digital,analog,keys={},{},{}
for name,value in pairs(sample) do
 assert(type(value)=="boolean" or type(value)=="number")
 keys[#keys+1]=name
 if type(value)=="boolean" then digital[name]=false else analog[name]=value end
end
table.sort(keys)
local def=assert(io.open(output.."/input-definition.tsv","w"))
def:write("name\ttype\tinitial_value\tneutral_value\n")
for _,name in ipairs(keys) do
 local neutral_value=analog[name]
 if type(sample[name])=="boolean" then neutral_value=false end
 def:write(name,"\t",type(sample[name]),"\t",tostring(sample[name]),"\t",tostring(neutral_value),"\n")
end
def:close()
local submitted=assert(io.open(output.."/submitted.tsv","w"))
submitted:write("relative_frame\tcore_frame\tphase\tbuttons")
for _,name in ipairs(keys) do submitted:write("\t",name) end
submitted:write("\n")
local columns={"relative_frame","core_frame","screen_kind","menu","menu_index","session","session_state","map_scene","flow","dream","timer","input_locked","map","stored_day","new_game","coordinate","pose","x","y","z","yaw","pad","pad_held","pad_released","pad_pressed","gpu_sha256"}
local trace=assert(io.open(output.."/cold-start.tsv","w"));trace:write(table.concat(columns,"\t"),"\n")
local captures=assert(io.open(output.."/captures.tsv","w"));captures:write("relative_frame\tcore_frame\treason\n")
local raw,flow,dream,graphics,pad,menu,session,map_scene,coordinate,pose,kind
local main_seen,first_ready,last_key=false,nil,nil
local phases={
 {90,"neutral_in_dream",{}},{60,"turn_left",{"P1 D-Pad Left"}},
 {60,"release_left",{}},{60,"turn_right",{"P1 D-Pad Right"}},
 {60,"release_right",{}},{90,"walk_forward",{"P1 D-Pad Up"}},
 {60,"release_up",{}},{90,"walk_backwards",{"P1 D-Pad Down"}},
 {120,"release_down",{}},{60,"look_triangle",{"P1 \u{25b3}"}},
 {120,"release_look",{}},
}
for _,phase in ipairs(phases) do
 for _,name in ipairs(phase[3]) do assert(digital[name]~=nil,"Unknown movement control "..name) end
end
local function find_owned(vtable,dream_offset)
 local start,found=0x90001,nil
 while true do
  local hit=string.find(raw,string.pack("<I4",vtable),start,true)
  if not hit or hit>0x1e0000 then return found end
  start=hit+4
  local p=hit-1
  if p%4==0 and word(raw,p+0xc)==graphics and ptr(word(raw,p+dream_offset),0x928)==dream then
   assert(found==nil,"Ambiguous owner-qualified object")
   found=p
  end
 end
end
local function read_state()
 raw=mainmemory.read_bytes_as_binary_string(0,0x200000)
 flow,dream,graphics,pad,menu,session,map_scene,coordinate,pose=nil,nil,nil,nil,nil,nil,nil,nil,nil
 kind="startup"
 flow=ptr(word(raw,0x8ac20),0x2c)
 if not flow or word(raw,flow)~=0x8006d3c8 then flow=nil;return end
 dream=ptr(word(raw,flow+0x28),0x928)
 if not dream or word(raw,dream)~=0x80087bdc then dream=nil;return end
 graphics=word(raw,flow+0x1c)
 local gp=ptr(graphics,0x14)
 if not gp then dream=nil;return end
 pad=ptr(word(raw,gp+4),0x20)
 if not pad or word(raw,pad)~=0x8006d370 then pad=nil;return end
 menu=find_owned(0x80086b60,0xa4)
 session=find_owned(0x800865c8,0x38)
 if menu then kind="main";main_seen=true end
 if session then
  kind="dream_session"
  map_scene=ptr(word(raw,session+0x4c),4)
  if map_scene and word(raw,map_scene)~=0x80087034 then map_scene=nil end
 end
 coordinate=ptr(word(raw,dream+0x14),0x50)
 if coordinate then pose=ptr(word(raw,coordinate+0x44),0x28) end
 if session and word(raw,session+0x3c)==2 and map_scene and coordinate and pose and word(raw,dream+0x70)==0 then
  kind="unlocked_dream"
 end
end
local function binary(name,data)
 local file=assert(io.open(output.."/"..name,"wb"));file:write(data);file:close()
end
local function observe(frame)
 read_state()
 if kind=="unlocked_dream" and not first_ready then first_ready=frame end
 local row={frame,emu.framecount(),kind,menu or "-",menu and word(raw,menu+0x58) or "-",session or "-",session and word(raw,session+0x3c) or "-",map_scene or "-",flow or "-",dream or "-",dream and word(raw,dream+0x24) or "-",dream and word(raw,dream+0x70) or "-",dream and signed(raw,dream+0x164) or "-",dream and word(raw,dream+0x180) or "-",dream and word(raw,dream+0x878) or "-",coordinate or "-",pose or "-",coordinate and signed(raw,coordinate+0x18) or "-",coordinate and signed(raw,coordinate+0x1c) or "-",coordinate and signed(raw,coordinate+0x20) or "-",pose and string.unpack("<i2",raw,pose+0x12+1) or "-",pad or "-",pad and word(raw,pad+0x10) or "-",pad and word(raw,pad+0x14) or "-",pad and word(raw,pad+0x18) or "-"}
 row[#row+1]=memory.hash_region(0,0x100000,"GPURAM"):lower()
 assert(#row==#columns and #row[#row]==64)
 trace:write(table.concat(row,"\t"),"\n")
 local key=table.concat({kind,menu or "-",session or "-",session and word(raw,session+0x3c) or "-",map_scene or "-"},":")
 local reasons={}
 if frame==0 or frame==frames or frame%600==0 then reasons[#reasons+1]="scheduled" end
 if key~=last_key then reasons[#reasons+1]="owner-qualified-screen-transition" end
 if frame==first_ready then reasons[#reasons+1]="first-unlocked-dream" end
 if #reasons>0 then
  binary("mainram-"..frame..".bin",raw)
  binary("gpu-"..frame..".bin",memory.read_bytes_as_binary_string(0,0x100000,"GPURAM"))
  client.screenshot(output.."/frame-"..frame..".png")
  savestate.save(output.."/frame-"..frame..".State")
  captures:write(frame,"\t",emu.framecount(),"\t",table.concat(reasons,","),"\n");captures:flush()
 end
 last_key=key
 if frame%60==0 then trace:flush() end
 if frame%300==0 then
  local f=assert(io.open(output.."/progress.txt","w"));f:write(frame,"\t",kind,"\n");f:close()
 end
end
local function choose(frame)
 if first_ready then
  local elapsed=frame-first_ready
  for _,phase in ipairs(phases) do
   if elapsed<=phase[1] then return phase[2],phase[3] end
   elapsed=elapsed-phase[1]
  end
  return "neutral_after_movement",{}
 end
 if frame%120<60 or frame%120>=72 then return "menu_release",{} end
 if kind=="main" then
  local index=word(raw,menu+0x58)
  if index>0 and index<6 then return "select_dream_up",{"P1 D-Pad Up"} end
  if index==0 then return "start_dream",{"P1 \u{25cb}"} end
  return "wait_for_menu",{}
 end
 if not main_seen then return "skip_startup",{"P1 \u{25cb}"} end
 return "wait_for_dream",{}
end
client.SetSoundOn(false);client.setscreenshotosd(false);client.speedmode(400)
local ok,err=xpcall(function()
 observe(0)
 for frame=1,frames do
  local phase,buttons=choose(frame)
  local input={};for name,value in pairs(digital) do input[name]=value end
  for _,name in ipairs(buttons) do assert(input[name]~=nil);input[name]=true end
  submitted:write(frame,"\t",emu.framecount(),"\t",phase,"\t",table.concat(buttons,","))
  for _,name in ipairs(keys) do
   local value=input[name];if type(sample[name])=="number" then value=analog[name] end
   submitted:write("\t",tostring(value))
  end
  submitted:write("\n")
  joypad.set(input);joypad.setanalog(analog)
  emu.frameadvance();observe(frame)
  if frame%60==0 then submitted:flush() end
 end
end,debug.traceback)
trace:close();submitted:close();captures:close()
local clear={};for name in pairs(analog) do clear[name]="" end;joypad.setanalog(clear)
local result=assert(io.open(output..(ok and "/completed.txt" or "/failed.txt"),"w"))
result:write(ok and (frames.." cold-start frames; first unlocked dream="..tostring(first_ready).."; no whole-feature acceptance.\n") or tostring(err));result:close()
client.exit()
end
local ok,err=xpcall(run,debug.traceback)
if not ok then local f=assert(io.open(output.."/failed.txt","w"));f:write(tostring(err));f:close();client.exit() end
