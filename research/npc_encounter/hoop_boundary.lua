-- Read-only continuation of the naturally reached, registered Hoop Girl.
-- Supply the original route's frame-12000 state. No game-memory writes.
local output = assert(os.getenv("LSD_QA_OUTPUT"))
local frames = tonumber(os.getenv("LSD_QA_FRAMES")) or 1800
assert(emu.getsystemid() == "PSX" and mainmemory.getname() == "MainRAM")
local function pointer(value, length)
    local address, segment = value & 0x1fffffff, value & 0xe0000000
    assert(value ~= 0 and address % 4 == 0 and address + length <= 0x200000)
    assert(segment == 0 or segment == 0x80000000 or segment == 0xa0000000)
    return address
end
-- BEGIN PURE MEMORY HELPERS
local function u32(raw, address) return (string.unpack("<I4", raw, address + 1)) end
local function s32(raw, address) return (string.unpack("<i4", raw, address + 1)) end
-- END PURE MEMORY HELPERS
-- BEGIN PURE NEUTRAL HELPER
local function neutralize(values)
    local result = {}
    for name, value in pairs(values) do
        if type(value) == "boolean" then result[name] = false
        else result[name] = value end
    end
    return result
end
-- END PURE NEUTRAL HELPER
local sample = joypad.get()
local neutral, keys, digital, analog = neutralize(sample), {}, {}, {}
for name, value in pairs(sample) do
    assert(type(value) == "boolean" or type(value) == "number")
    keys[#keys + 1] = name
    if type(value) == "boolean" then digital[name] = false
    else
        assert(value == value and math.abs(value) < 2147483648)
        analog[name] = value
    end
end
table.sort(keys)
local definitions = assert(io.open(output .. "/input-definition.tsv", "w"))
definitions:write("name\ttype\tinitial_value\tneutral_value\n")
for _, name in ipairs(keys) do
    definitions:write(name, "\t", type(sample[name]), "\t", tostring(sample[name]), "\t", tostring(neutral[name]), "\n")
end
definitions:close()
local trace = assert(io.open(output .. "/boundary.tsv", "w"))
trace:write("relative_frame\tcore_frame\tmap\ttimer\tinput_locked\tdream\tobject\tentity_tick\tcontext_tick\tx\ty\tz\tpose_yaw\tanimation_frame\tduration\tpad_buttons\tpad_released\tpad_pressed\n")
local submitted = assert(io.open(output .. "/submitted.tsv", "w"))
submitted:write("relative_frame\tcore_frame")
for _, name in ipairs(keys) do submitted:write("\t", name) end
submitted:write("\n")
local captures = assert(io.open(output .. "/captures.tsv", "w"))
captures:write("relative_frame\tentity_tick\tcontext_tick\n")
local seen = {}
local function inspect(frame)
    local raw = mainmemory.read_bytes_as_binary_string(0, 0x200000)
    assert(#raw == 0x200000)
    local flow = pointer(u32(raw, 0x8ac20), 0x2c)
    assert(u32(raw, flow) == 0x8006d3c8)
    local dream = pointer(u32(raw, flow + 0x28), 0x928)
    assert(u32(raw, dream) == 0x80087bdc and s32(raw, dream + 0x164) == 12)
    local object = 0x1c5dcc
    assert(u32(raw, object) == 0x80089ad4 and s32(raw, object + 0x98) == 71)
    assert(pointer(u32(raw, object + 0x94), 0x928) == dream)
    assert(s32(raw, object + 0x9c) == 72 and s32(raw, object + 0xf8) == 1)
    assert(pointer(u32(raw, object + 0xa4), 0x108) == object)
    assert(u32(raw, object + 0xa8) == 0x80062570 and u32(raw, 0x89ea4 + 71 * 16 + 12) == 0x80062570)
    local transform = pointer(u32(raw, object + 0x14), 0x50)
    local pose = pointer(u32(raw, transform + 0x44), 0x28)
    local graphics = pointer(u32(raw, flow + 0x1c), 0x14)
    local pad = pointer(u32(raw, graphics + 4), 0x20)
    assert(u32(raw, pad) == 0x8006d370)
    local tick, context_tick = s32(raw, object + 0xfc), s32(raw, object + 0xa0)
    trace:write(table.concat({frame, emu.framecount(), 12, u32(raw, dream + 0x24), s32(raw, dream + 0x70),
        string.format("%08x", dream), string.format("%08x", object), tick, context_tick,
        s32(raw, transform + 0x18), s32(raw, transform + 0x1c), s32(raw, transform + 0x20),
        string.unpack("<i2", raw, pose + 0x12 + 1), s32(raw, object + 0x84), s32(raw, object + 0x80),
        u32(raw, pad + 0x10), u32(raw, pad + 0x14), u32(raw, pad + 0x18)}, "\t"), "\n")
    if frame == 0 or frame == frames or (tick >= 2399 and tick <= 2403 and not seen[tick]) then
        seen[tick] = true
        local memory_file = assert(io.open(output .. "/mainram-" .. frame .. ".bin", "wb"))
        memory_file:write(raw)
        memory_file:close()
        client.screenshot(output .. "/frame-" .. frame .. ".png")
        savestate.save(output .. "/frame-" .. frame .. ".State")
        captures:write(frame, "\t", tick, "\t", context_tick, "\n")
        captures:flush()
    end
    if frame % 60 == 0 then trace:flush() end
end
client.SetSoundOn(false)
client.setscreenshotosd(false)
client.speedmode(400)
inspect(0)
for frame = 1, frames do
    submitted:write(frame, "\t", emu.framecount())
    for _, name in ipairs(keys) do submitted:write("\t", tostring(neutral[name])) end
    submitted:write("\n")
    if frame % 60 == 0 then submitted:flush() end
    joypad.set(digital)
    joypad.setanalog(analog)
    emu.frameadvance()
    inspect(frame)
end
trace:close()
submitted:close()
captures:close()
local done = assert(io.open(output .. "/completed.txt", "w"))
done:write(frames, " frames; complete frame observations at a warm-state NPC boundary, not direct callback tracing or encounter acceptance.\n")
done:close()
local clear_analog = {}
for name in pairs(analog) do clear_analog[name] = "" end
joypad.setanalog(clear_analog)
client.exit()
