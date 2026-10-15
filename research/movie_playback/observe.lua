-- Read-only movie observations during an owned, neutral-input replay.
local output = assert(os.getenv("LSD_QA_OUTPUT"))
local frames = assert(tonumber(os.getenv("LSD_QA_FRAMES")))
local function run()
assert(frames >= 1 and frames <= 12000)
assert(client.getversion() == "2.11.1" and emu.getsystemid() == "PSX")
assert(memory.getmemorydomainsize(mainmemory.getname()) == 0x200000)

local function word(raw, offset)
    local value = string.unpack("<I4", raw, offset + 1)
    return value
end
local function u32(address)
    return word(mainmemory.read_bytes_as_binary_string(address, 4), 0)
end
local function pointer(value, size)
    assert(value >= 0x80010000 and value <= 0x80200000 - size and value % 4 == 0,
           "Unexpected movie pointer")
    return value & 0x1fffffff
end
local function save_binary(name, bytes)
    local file = assert(io.open(output .. "/" .. name, "wb"))
    file:write(bytes)
    file:close()
end

local neutral, digital, analog, keys = {}, {}, {}, {}
for name, value in pairs(joypad.get()) do
    keys[#keys + 1] = name
    assert(type(value) == "boolean" or type(value) == "number")
    neutral[name] = type(value) == "boolean" and false or value
    if type(value) == "boolean" then digital[name] = false else analog[name] = value end
end
table.sort(keys)
local definition = assert(io.open(output .. "/input-definition.tsv", "w"))
definition:write("name\ttype\tneutral_value\n")
for _, name in ipairs(keys) do definition:write(name, "\t", type(neutral[name]), "\t", tostring(neutral[name]), "\n") end
definition:close()
local submitted = assert(io.open(output .. "/submitted.tsv", "w"))
submitted:write("relative_frame\tcore_frame")
for _, name in ipairs(keys) do submitted:write("\t", name) end
submitted:write("\n")

local columns = {"relative_frame", "core_frame", "native_tables_ready", "active_movie", "rng", "watchdog_counter"}
for offset = 0, 0x68, 4 do columns[#columns + 1] = string.format("movie_%02x", offset) end
for offset = 0, 0x58, 4 do columns[#columns + 1] = string.format("stream_%02x", offset) end
columns[#columns + 1] = "gpu_sha256"
local trace = assert(io.open(output .. "/movies.tsv", "w"))
trace:write(table.concat(columns, "\t"), "\n")
local captures = assert(io.open(output .. "/captures.tsv", "w"))
captures:write("relative_frame\tcore_frame\treason\tactive_movie\tthreshold\traw_stream_frame\n")
local metadata = assert(io.open(output .. "/emulator.txt", "w"))
metadata:write("BizHawk ", client.getversion(), "\nSystem ", emu.getsystemid(), "\nMain memory ", mainmemory.getname(), "\n")
for _, name in ipairs(memory.getmemorydomainlist()) do
    metadata:write("Domain ", name, " ", memory.getmemorydomainsize(name), "\n")
end
metadata:close()

client.SetSoundOn(false)
client.setscreenshotosd(false)
client.speedmode(400)
local last_active, last_ready, serial = nil, nil, 0
local seen = {}
local function observe(frame)
    local ready = u32(0x6f61c) == 0x800454c4 and u32(0x8184c) == 0x80047694
    local active, threshold, last_frame = 0, 0, 0
    local row = {frame, emu.framecount(), ready and 1 or 0, 0, "-", "-"}
    local movie, stream
    if ready then
        active = u32(0x8a940)
        row[4], row[5], row[6] = active, u32(0x8ac68), u32(0x8a948)
        if active ~= 0 then
            movie = mainmemory.read_bytes_as_binary_string(pointer(active, 0x6c), 0x6c)
            assert(word(movie, 0) == 0x8006f614, "Unexpected movie vtable")
            stream = mainmemory.read_bytes_as_binary_string(pointer(word(movie, 0x60), 0x5c), 0x5c)
            assert(word(stream, 0) == 0x800817e0, "Unexpected stream vtable")
            threshold, last_frame = word(stream, 0x40), word(stream, 0x58)
        end
    end
    for offset = 0, 0x68, 4 do row[#row + 1] = movie and word(movie, offset) or "-" end
    for offset = 0, 0x58, 4 do row[#row + 1] = stream and word(stream, offset) or "-" end
    local gpu_hash = memory.hash_region(0, 0x100000, "GPURAM"):lower()
    assert(#gpu_hash == 64 and gpu_hash:match("^[0-9a-f]+$"))
    row[#row + 1] = gpu_hash
    assert(#row == #columns)
    trace:write(table.concat(row, "\t"), "\n")
    local reasons = {}
    if frame == 0 or frame == frames or frame % 600 == 0 then reasons[#reasons + 1] = "scheduled" end
    if active ~= last_active then
        serial = serial + 1
        reasons[#reasons + 1] = "movie-lifetime-transition"
    end
    if ready ~= last_ready then reasons[#reasons + 1] = "native-table-transition" end
    if movie and (word(stream, 0x2c) == 2 or word(stream, 0x2c) == 4)
       and threshold == word(movie, 0x5c) and threshold > 0 and threshold < 10000
       and last_frame >= threshold - 3 then
        local key = serial .. ":" .. last_frame .. ":" .. word(movie, 0x48) .. ":" .. word(movie, 0x44)
        if not seen[key] then seen[key] = true; reasons[#reasons + 1] = "near-stream-threshold" end
    end
    if #reasons > 0 then
        save_binary("mainram-" .. frame .. ".bin", mainmemory.read_bytes_as_binary_string(0, 0x200000))
        save_binary("gpu-" .. frame .. ".bin", memory.read_bytes_as_binary_string(0, memory.getmemorydomainsize("GPURAM"), "GPURAM"))
        client.screenshot(output .. "/frame-" .. frame .. ".png")
        savestate.save(output .. "/frame-" .. frame .. ".State")
        captures:write(frame, "\t", emu.framecount(), "\t", table.concat(reasons, ","), "\t", active,
                       "\t", threshold, "\t", last_frame, "\n")
        captures:flush()
    end
    if frame % 120 == 0 then trace:flush() end
    last_active, last_ready = active, ready
end

local ok, err = xpcall(function()
    observe(0)
    for frame = 1, frames do
        submitted:write(frame, "\t", emu.framecount())
        for _, name in ipairs(keys) do submitted:write("\t", tostring(neutral[name])) end
        submitted:write("\n")
        if frame % 120 == 0 then submitted:flush() end
        joypad.set(digital)
        joypad.setanalog(analog)
        emu.frameadvance()
        observe(frame)
    end
end, debug.traceback)
trace:close(); submitted:close(); captures:close()
local clear_analog = {}
for name in pairs(analog) do clear_analog[name] = "" end
joypad.setanalog(clear_analog)
local result = assert(io.open(output .. (ok and "/completed.txt" or "/failed.txt"), "w"))
result:write(ok and (frames .. " frames; neutral shared-state movie observation, not full movie acceptance.\n") or tostring(err))
result:close()
client.exit()

end
local startup_ok, startup_error = xpcall(run, debug.traceback)
if not startup_ok then
    local failure = assert(io.open(output .. "/failed.txt", "w"))
    failure:write(tostring(startup_error)); failure:close()
    client.exit()
end
