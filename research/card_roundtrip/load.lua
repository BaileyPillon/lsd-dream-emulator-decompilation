-- Cold boot with the persisted QA card; controller-only Load observation.
local output=assert(os.getenv("LSD_QA_OUTPUT"))
local frames=assert(tonumber(os.getenv("LSD_QA_FRAMES")))
local function run()
assert(client.getversion()=="2.11.1" and emu.getsystemid()=="PSX")
assert(memory.getmemorydomainsize(mainmemory.getname())==0x200000)
local function word(raw,p) return (string.unpack("<I4",raw,p+1)) end
local function ptr(v,size)
 if v<0x80010000 or v>0x80200000-size or v%4~=0 then return nil end
 return v&0x1fffffff
end
local function neutralize(values)
 local result={}
 for name,value in pairs(values) do
  if type(value)=="boolean" then result[name]=false else result[name]=value end
 end
 return result
end
local sample=joypad.get()
local neutral,digital,analog,keys=neutralize(sample),{},{},{}
for name,value in pairs(sample) do
 assert(type(value)=="boolean" or type(value)=="number")
 keys[#keys+1]=name
 if type(value)=="boolean" then digital[name]=false else analog[name]=value end
end
table.sort(keys)
local def=assert(io.open(output.."/input-definition.tsv","w"))
def:write("name\ttype\tinitial_value\tneutral_value\n")
for _,name in ipairs(keys) do def:write(name,"\t",type(sample[name]),"\t",tostring(sample[name]),"\t",tostring(neutral[name]),"\n") end
def:close()
local submitted=assert(io.open(output.."/submitted.tsv","w"))
submitted:write("relative_frame\tcore_frame\tmode\tbutton")
for _,name in ipairs(keys) do submitted:write("\t",name) end
submitted:write("\n")
local columns={"relative_frame","core_frame","screen_kind","screen","dream","stored_day","new_game","load_seen","load_returned","pad_held","pad_released","pad_pressed"}
for _,spec in ipairs({{"screen",0xc0},{"card",0x80},{"comment",0x48},{"select",0x50}}) do
 for off=0,spec[2],4 do columns[#columns+1]=string.format("%s_%02x",spec[1],off) end
end
columns[#columns+1]="gpu_sha256"
local trace=assert(io.open(output.."/card.tsv","w"));trace:write(table.concat(columns,"\t"),"\n")
local captures=assert(io.open(output.."/captures.tsv","w"));captures:write("relative_frame\tcore_frame\treason\n")
local load_seen,load_returned,main_seen=false,false,false
local raw,screen,kind,dream,graphics,card,comment,select_menu,pad
local function find_screen(vtable)
 local start,found=0x90001,nil
 while true do
  local hit=string.find(raw,string.pack("<I4",vtable),start,true)
  if not hit or hit>0x1e0000 then return found end
  start=hit+4
  local p=hit-1
  if p%4==0 and word(raw,p+0xc)==graphics and ptr(word(raw,p+0xa4),0x928)==dream then
   assert(found==nil,"Ambiguous screen binding")
   found=p
  end
 end
end
local function read_state()
 raw=mainmemory.read_bytes_as_binary_string(0,0x200000)
 screen,kind,dream,graphics,card,comment,select_menu,pad=nil,"none",nil,nil,nil,nil,nil,nil
 local flow=ptr(word(raw,0x8ac20),0x2c)
 if not flow or word(raw,flow)~=0x8006d3c8 then return end
 dream=ptr(word(raw,flow+0x28),0x928)
 if not dream or word(raw,dream)~=0x80087bdc then dream=nil;return end
 graphics=word(raw,flow+0x1c)
 local graphicsp=ptr(graphics,0x14)
 if not graphicsp then dream=nil;return end
 pad=ptr(word(raw,graphicsp+4),0x20)
 if not pad or word(raw,pad)~=0x8006d370 then dream=nil;pad=nil;return end
 local main=find_screen(0x80086b60)
 local graph=find_screen(0x80087aac)
 assert(not(main and graph),"Two matching screen records")
 screen,kind=main or graph,main and "main" or (graph and "graph" or "none")
 if main then main_seen=true end
 card,comment,select_menu=nil,nil,nil
 if main then
  card=ptr(word(raw,main+0xac),0x84)
  if card then
   assert(word(raw,card)==0x80086dc4)
   comment=ptr(word(raw,card+0x78),0x4c)
   select_menu=ptr(word(raw,card+0x7c),0x54)
   if comment then assert(word(raw,comment)==0x80086ed0) end
   if select_menu then assert(word(raw,select_menu)==0x80086f88) end
   if word(raw,card+0x28)~=0 and word(raw,card+0x24)==1 then load_seen=true end
   if load_seen and word(raw,card+0x28)==0 and word(raw,card+0x24)==0 then load_returned=true end
  end
 end
end
local function binary(name,data)
 local file=assert(io.open(output.."/"..name,"wb"));file:write(data);file:close()
end
local last_key=nil
local function observe(frame)
 read_state()
 local row={frame,emu.framecount(),kind,screen or "-",dream or "-",dream and word(raw,dream+0x180) or "-",dream and word(raw,dream+0x878) or "-",load_seen and 1 or 0,load_returned and 1 or 0,pad and word(raw,pad+0x10) or "-",pad and word(raw,pad+0x14) or "-",pad and word(raw,pad+0x18) or "-"}
 for _,spec in ipairs({{screen,0xc0},{card,0x80},{comment,0x48},{select_menu,0x50}}) do
  for off=0,spec[2],4 do row[#row+1]=spec[1] and word(raw,spec[1]+off) or "-" end
 end
 local hash=memory.hash_region(0,0x100000,"GPURAM"):lower()
 assert(#hash==64 and hash:match("^[0-9a-f]+$"))
 row[#row+1]=hash;assert(#row==#columns)
 trace:write(table.concat(row,"\t"),"\n")
 local key=table.concat({kind,screen or "-",card and word(raw,card+0x24) or "-",card and word(raw,card+0x28) or "-",comment and 1 or 0,select_menu and 1 or 0,load_returned and 1 or 0},":")
 local reasons={}
 if frame==0 or frame==frames or frame%600==0 then reasons[#reasons+1]="scheduled" end
 if key~=last_key then reasons[#reasons+1]="screen-or-card-transition" end
 if #reasons>0 then
  binary("mainram-"..frame..".bin",raw)
  binary("gpu-"..frame..".bin",memory.read_bytes_as_binary_string(0,0x100000,"GPURAM"))
  client.screenshot(output.."/frame-"..frame..".png")
  savestate.save(output.."/frame-"..frame..".State")
  captures:write(frame,"\t",emu.framecount(),"\t",table.concat(reasons,","),"\n");captures:flush()
 end
 last_key=key
 if frame%60==0 then trace:flush() end
end
local function choose()
 if load_returned then return "neutral_after_card_return","" end
 if kind=="graph" then return "leave_chart","P1 \u{25cb}" end
 if kind~="main" then
  if not main_seen then return "skip_startup_with_circle","P1 \u{25cb}" end
  return "wait_for_main",""
 end
 if card and (word(raw,card+0x24)~=0 or load_seen) then
  if comment then return "accept_comment","P1 \u{25cb}" end
  return "confirm_card_dialog","P1 \u{25cb}"
 end
 local index=word(raw,screen+0x58)
 if index<3 then return "select_load_down","P1 D-Pad Down" end
 if index>3 and index<6 then return "select_load_up","P1 D-Pad Up" end
 if index==3 then return "open_load","P1 \u{25cb}" end
 return "wait_for_menu",""
end
client.SetSoundOn(false);client.setscreenshotosd(false);client.speedmode(400)
local ok,err=xpcall(function()
 observe(0)
 local mode,button="initial_neutral",""
 for frame=1,frames do
  if frame%120==60 then mode,button=choose() end
  local input={}
  for name,value in pairs(digital) do input[name]=value end
  local selected=frame%120>=60 and frame%120<72 and button or ""
  if selected~="" then assert(input[selected]~=nil);input[selected]=true end
  submitted:write(frame,"\t",emu.framecount(),"\t",mode,"\t",selected)
  for _,name in ipairs(keys) do
   local value=input[name]
   if type(sample[name])=="number" then value=analog[name] end
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
result:write(ok and (frames.." frames; controller-only cold Load trajectory, not complete save/load acceptance.\n") or tostring(err));result:close()
client.exit()
end
local ok,err=xpcall(run,debug.traceback)
if not ok then local f=assert(io.open(output.."/failed.txt","w"));f:write(tostring(err));f:close();client.exit() end
