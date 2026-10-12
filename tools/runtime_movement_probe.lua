-- Read-only native state observation with emulator-local movement inputs.
-- Use the canonical executable and a saved in-dream state. No RAM is changed.
-- Field provenance: config/symbols.txt, game/game_flow.h, dream/dream_sys.h,
-- base/transform.c (coordinate/pose layout). Addresses are edition-specific.
local output = assert(os.getenv("LSD_QA_OUTPUT"), "Set LSD_QA_OUTPUT")
local scenario = os.getenv("LSD_QA_SCENARIO") or "play"
local frames = tonumber(os.getenv("LSD_QA_FRAMES")) or 1800
assert(scenario == "play" and emu.getsystemid() == "PSX")
assert(mainmemory.getname() == "MainRAM")
local log = assert(io.open(output .. "/trace.tsv", "w"))
log:write("relative_frame\tcore_frame\tsystem\tlagged\tgpu_ram_sample_hash\n")
local state = assert(io.open(output .. "/movement.tsv", "w"))
local fields = {
    {"timer", 0x24, true}, {"link_state", 0x44}, {"flashback", 0x68},
    {"paused", 0x6c}, {"input_locked", 0x70}, {"action_pressed", 0x74},
    {"view_mode", 0x84}, {"look_state", 0x88}, {"look_position", 0x8c},
    {"turn_state", 0x90}, {"turn_offset", 0x94}, {"move_mode", 0x9c},
    {"move_state", 0xa0}, {"left_right_state", 0xa4}, {"is_forward", 0xa8},
    {"move_direction", 0xac}, {"move_step", 0xb4}, {"floor_type", 0xb8},
    {"link_interval", 0x120, true}, {"time_limit", 0x134},
    {"map", 0x164}, {"year", 0x17c}, {"day", 0x180},
    {"flashback_count", 0x46c}, {"auto_move_locked", 0x908},
    {"auto_move_active", 0x90c},
}
state:write("relative_frame\tcore_frame\tinput_phase\tinput_buttons\tgame_flow\tdream_sys")
for _, field in ipairs(fields) do state:write("\t", field[1]) end
state:write("\tcoordinate\tpose\tx\ty\tz\tscale_x\tscale_y\tscale_z\tpitch\tyaw\troll")
state:write("\tpad\tpad_buttons\tpad_released\tpad_pressed\n")
local metadata = assert(io.open(output .. "/emulator.txt", "w"))
metadata:write("BizHawk ", client.getversion(), "\nSystem ", emu.getsystemid(), "\n")
metadata:write("Scenario ", scenario, "\nMain domain ", mainmemory.getname(), "\n")
metadata:write("Probe native movement; g_GAME_FLOW=8008ac20, flow+28=dream_sys; no memory writes\n")
local neutral = {}
for name, value in pairs(joypad.get()) do
    metadata:write("Control ", name, " ", tostring(value), "\n")
    neutral[name] = type(value) == "boolean" and false or value
end
metadata:close()
-- Bindings follow the canonical pad table and set_move_from_pad, rather than
-- inferred button names. Neutral gaps expose release and view-return behavior.
-- Start from an unlocked in-dream state; a requested phase can still be locked.
local phases = {
    {60, "neutral", {}},
    {90, "look_triangle", {"P1 △"}},
    {60, "release_triangle", {}},
    {90, "look_square", {"P1 □"}},
    {60, "release_square", {}},
    {60, "turn_left", {"P1 D-Pad Left"}},
    {60, "release_left", {}},
    {60, "turn_right", {"P1 D-Pad Right"}},
    {60, "release_right", {}},
    {60, "left_shoulder_one", {"P1 L1"}},
    {60, "release_l1", {}},
    {60, "right_shoulder_one", {"P1 R1"}},
    {60, "release_r1", {}},
    {60, "left_shoulder_two", {"P1 L2"}},
    {60, "release_l2", {}},
    {60, "right_shoulder_two", {"P1 R2"}},
    {60, "release_r2", {}},
    {60, "walk_backwards", {"P1 D-Pad Down"}},
    {60, "release_down", {}},
    {60, "walk_forward", {"P1 D-Pad Up"}},
    {60, "release_up", {}},
    {60, "forward_cross", {"P1 D-Pad Up", "P1 X"}},
    {60, "release_run", {}},
    {60, "circle_taps", {"P1 ○"}, true},
    {60, "up_taps", {"P1 D-Pad Up"}, true},
}
for _, phase in ipairs(phases) do
    for _, name in ipairs(phase[3]) do assert(neutral[name] ~= nil, "Unknown control " .. name) end
end
local function pointer(value, length)
    local segment = value & 0xe0000000
    local physical = value & 0x1fffffff
    if value == 0 or (segment ~= 0 and segment ~= 0x80000000 and segment ~= 0xa0000000)
       or physical + length > 0x200000 or physical % 4 ~= 0 then return nil end
    return physical
end
local function u32(address) return mainmemory.read_u32_le(address) end
local function inspect(frame, label, buttons)
    local flow = assert(pointer(u32(0x8ac20), 0x2c), "Invalid game-flow pointer")
    assert(u32(flow) == 0x8006d3c8, "Unexpected game-flow vtable")
    local dream = assert(pointer(u32(flow + 0x28), 0x928), "Invalid dream-system pointer")
    assert(u32(dream) == 0x80087bdc, "Unexpected dream-system vtable")
    state:write(frame, "\t", emu.framecount(), "\t", label, "\t", table.concat(buttons, ","),
                "\t", string.format("%08x", flow), "\t", string.format("%08x", dream))
    for _, field in ipairs(fields) do
        state:write("\t", field[3] and u32(dream + field[2]) or mainmemory.read_s32_le(dream + field[2]))
    end
    local coordinate = pointer(u32(dream + 0x14), 0x50)
    local pose = coordinate and pointer(u32(coordinate + 0x44), 0x28)
    state:write("\t", coordinate and string.format("%08x", coordinate) or "",
                "\t", pose and string.format("%08x", pose) or "")
    -- GsCOORDINATE2 matrix translation is at +0x18/+0x1c/+0x20.
    -- The private +0x44 parameter block starts with the three scale factors.
    for _, offset in ipairs({0x18, 0x1c, 0x20}) do
        state:write("\t", coordinate and mainmemory.read_s32_le(coordinate + offset) or "")
    end
    for _, offset in ipairs({0, 4, 8}) do
        state:write("\t", pose and mainmemory.read_s32_le(pose + offset) or "")
    end
    for _, offset in ipairs({0x10, 0x12, 0x14}) do
        state:write("\t", pose and mainmemory.read_s16_le(pose + offset) or "")
    end
    -- game_graphics_ctx_t stores the original pad object at +0x04.
    local graphics = assert(pointer(u32(flow + 0x1c), 0x14), "Invalid graphics context")
    local pad = assert(pointer(u32(graphics + 0x04), 0x20), "Invalid pad pointer")
    assert(u32(pad) == 0x8006d370, "Unexpected pad vtable")
    state:write("\t", string.format("%08x", pad), "\t", u32(pad + 0x10),
                "\t", u32(pad + 0x14), "\t", u32(pad + 0x18))
    state:write("\n")
    if frame % 60 == 0 then state:flush() end
end
local function ram_hash()
    local hash = 2166136261
    for address = 0, 65535, 64 do
        hash = ((hash ~ memory.read_u8(address, "GPURAM")) * 16777619) & 0xffffffff
    end
    return string.format("%08x", hash)
end
client.SetSoundOn(false)
client.setscreenshotosd(false)
client.speedmode(400)
local captures = {[300]=true, [600]=true, [900]=true, [1200]=true, [1500]=true, [1800]=true}
for frame = 1, frames do
    local input = {}
    for name, value in pairs(neutral) do input[name] = value end
    local remaining, label, buttons = frame, "neutral_tail", {}
    for _, phase in ipairs(phases) do
        if remaining <= phase[1] then
            label = phase[2]
            -- Twelve emulator frames reach both pressed and held native polls
            -- in the recorded scenario. Shorter pulses can miss held commands.
            if not phase[4] or (remaining - 1) % 20 < 12 then buttons = phase[3] end
            break
        end
        remaining = remaining - phase[1]
    end
    for _, name in ipairs(buttons) do input[name] = true end
    joypad.set(input)
    emu.frameadvance()
    inspect(frame, label, buttons)
    if frame % 60 == 0 then
        log:write(frame, "\t", emu.framecount(), "\t", emu.getsystemid(), "\t",
                  tostring(emu.islagged()), "\t", ram_hash(), "\n")
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
state:close()
log:close()
local done = assert(io.open(output .. "/completed.txt", "w"))
done:write(frames, " emulator frames; scenario ", scenario,
           "; observation script, not exhaustive feature acceptance.\n")
done:close()
client.exit()
