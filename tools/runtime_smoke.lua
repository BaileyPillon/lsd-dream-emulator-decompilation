-- Repeatable, emulator-local input. No desktop keyboard or controller changes.
-- Set LSD_QA_OUTPUT to a new, existing directory before launching EmuHawk.
local output = assert(os.getenv("LSD_QA_OUTPUT"), "Set LSD_QA_OUTPUT")
local scenario = os.getenv("LSD_QA_SCENARIO") or "boot"
local frames = tonumber(os.getenv("LSD_QA_FRAMES")) or 1800
local log = assert(io.open(output .. "/trace.tsv", "w"))
log:write("relative_frame\tcore_frame\tsystem\tlagged\tgpu_ram_sample_hash\n")
local metadata = assert(io.open(output .. "/emulator.txt", "w"))
metadata:write("BizHawk ", client.getversion(), "\nSystem ", emu.getsystemid(), "\n")
metadata:write("Scenario ", scenario, "\nMain domain ", mainmemory.getname(), "\n")
for _, name in ipairs(memory.getmemorydomainlist()) do
    metadata:write("Domain ", name, " ", memory.getmemorydomainsize(name), "\n")
end
local neutral = {}
for name, value in pairs(joypad.get()) do
    metadata:write("Control ", name, " ", tostring(value), "\n")
    neutral[name] = type(value) == "boolean" and false or value
end
metadata:close()
client.SetSoundOn(false)
client.setscreenshotosd(false)
client.speedmode(400)
local captures = { [300] = true, [600] = true, [900] = true,
                   [1200] = true, [1500] = true, [1800] = true }
local function ram_hash()
    -- A sampled checksum is a trace aid; screenshots and full-RAM snapshots
    -- provide the actual comparison evidence at each checkpoint.
    local domain = "GPURAM"
    local length = math.min(memory.getmemorydomainsize(domain), 65536)
    local hash = 2166136261
    for address = 0, length - 1, 64 do
        hash = ((hash ~ memory.read_u8(address, domain)) * 16777619) & 0xffffffff
    end
    return string.format("%08x", hash)
end
for frame = 1, frames do
    local input = {}
    for name, value in pairs(neutral) do input[name] = value end
    if scenario == "play" then
        -- This timeline is a broad observation script, not feature acceptance.
        if frame <= 3000 then
            local phase = frame % 300
            input["P1 Start"] = phase >= 10 and phase < 12
            input["P1 ○"] = phase >= 110 and phase < 112
        elseif frame <= 4200 then
            input["P1 D-Pad Up"] = true
        elseif frame <= 4500 then
            input["P1 D-Pad Right"] = true
        elseif frame <= 4800 then
            input["P1 D-Pad Up"] = true
            input["P1 X"] = true
        elseif frame <= 5100 then
            input["P1 L1"] = true
        end
    end
    joypad.set(input)
    emu.frameadvance()
    if frame % 60 == 0 then
        log:write(frame, "\t", emu.framecount(), "\t", emu.getsystemid(), "\t", tostring(emu.islagged()),
                  "\t", ram_hash(), "\n")
        log:flush()
    end
    if captures[frame] or frame % 600 == 0 or frame == frames then
        client.screenshot(output .. "/frame-" .. frame .. ".png")
        savestate.save(output .. "/frame-" .. frame .. ".State")
        local gpu = assert(io.open(output .. "/gpu-" .. frame .. ".bin", "wb"))
        gpu:write(memory.read_bytes_as_binary_string(0, memory.getmemorydomainsize("GPURAM"), "GPURAM"))
        gpu:close()
    end
end
log:close()
local done = assert(io.open(output .. "/completed.txt", "w"))
done:write(frames, " emulator frames; scenario ", scenario,
           "; observation script, not exhaustive feature acceptance.\n")
done:close()
client.exit()
