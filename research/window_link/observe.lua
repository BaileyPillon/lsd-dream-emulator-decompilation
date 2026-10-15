-- Read-only NPC records from an ordinary saved game. No game-memory writes.
local output = assert(os.getenv("LSD_QA_OUTPUT"))
local frames = tonumber(os.getenv("LSD_QA_FRAMES")) or 300
assert(emu.getsystemid() == "PSX" and mainmemory.getname() == "MainRAM")
local metadata = assert(io.open(output .. "/capabilities.txt", "w"))
metadata:write("BizHawk ", client.getversion(), "\nSystem ", emu.getsystemid(), "\n")
local scopes_ok, scopes = pcall(event.availableScopes)
metadata:write("Scopes call ", tostring(scopes_ok), "\n")
local scope_count = 0
if scopes_ok and type(scopes) == "table" then
    for key, value in pairs(scopes) do
        metadata:write("Scope ", tostring(key), " ", tostring(value), "\n")
        scope_count = scope_count + 1
    end
end
local registers_ok, registers = pcall(emu.getregisters)
local register_count = 0
if registers_ok and type(registers) == "table" then
    for key, value in pairs(registers) do
        metadata:write("Register ", tostring(key), " ", tostring(value), "\n")
        register_count = register_count + 1
    end
end
metadata:write("Register call ", tostring(registers_ok), " count ", register_count,
               "\nAvailable scopes ", scope_count, "\n")
metadata:close()
local trace = assert(io.open(output .. "/npc.tsv", "w"))
trace:write("relative_frame\tcore_frame\tmap\tdream\tobject\tentity_id\tstate\tentity_tick\tcontext_state\tcontext_tick\tcontext_owner\tcallback\texpected_callback\tlink_enabled\ttriggered\tbehaviour_active\tx\ty\tz\n")
local scene = assert(io.open(output .. "/scene.tsv", "w"))
scene:write("relative_frame\tcore_frame\tdream\tmap\ttimer\tinput_locked\tmatched_records\tregistered_contexts\n")
local function pointer(value, length)
    local segment = value & 0xe0000000
    local address = value & 0x1fffffff
    if value == 0 or address % 4 ~= 0 or address + length > 0x200000
       or (segment ~= 0 and segment ~= 0x80000000 and segment ~= 0xa0000000) then return nil end
    return address
end
local function u32(raw, offset) return string.unpack("<I4", raw, offset + 1) end
local function s32(raw, offset) return string.unpack("<i4", raw, offset + 1) end
local function inspect(frame)
    local raw = mainmemory.read_bytes_as_binary_string(0, 0x200000)
    assert(#raw == 0x200000)
    local flow = assert(pointer(u32(raw, 0x8ac20), 0x2c))
    assert(u32(raw, flow) == 0x8006d3c8)
    local dream = assert(pointer(u32(raw, flow + 0x28), 0x928))
    assert(u32(raw, dream) == 0x80087bdc)
    local map = s32(raw, dream + 0x164)
    local found, active = 0, 0
    local search = 1
    local pattern = string.char(0xd4, 0x9a, 0x08, 0x80)
    while true do
        local hit = string.find(raw, pattern, search, true)
        if hit == nil then break end
        search = hit + 4
        local object = hit - 1
        if object % 4 == 0 and object + 0x108 <= #raw then
            local entity_id = s32(raw, object + 0x98)
            if entity_id >= 0 and entity_id < 130 and pointer(u32(raw, object + 0x94), 0x928) == dream then
                local owner = u32(raw, object + 0xa4)
                local callback = u32(raw, object + 0xa8)
                local expected = u32(raw, 0x89ea4 + entity_id * 16 + 12)
                local context = s32(raw, object + 0x9c)
                if context == entity_id + 1 and pointer(owner, 0x108) == object and callback == expected then active = active + 1 end
                found = found + 1
                local transform = pointer(u32(raw, object + 0x14), 0x28)
                local x, y, z = "", "", ""
                if transform then x, y, z = s32(raw, transform + 0x18), s32(raw, transform + 0x1c), s32(raw, transform + 0x20) end
                trace:write(frame, "\t", emu.framecount(), "\t", map, "\t", string.format("%08x", dream),
                    "\t", string.format("%08x", object), "\t", entity_id, "\t", s32(raw, object + 0x44),
                    "\t", s32(raw, object + 0xfc), "\t", context, "\t", s32(raw, object + 0xa0),
                    "\t", string.format("%08x", owner), "\t", string.format("%08x", callback),
                    "\t", string.format("%08x", expected), "\t", s32(raw, object + 0xf0),
                    "\t", s32(raw, object + 0xf4), "\t", s32(raw, object + 0xf8), "\t", x, "\t", y, "\t", z, "\n")
            end
        end
    end
    scene:write(frame, "\t", emu.framecount(), "\t", string.format("%08x", dream), "\t", map,
                "\t", u32(raw, dream + 0x24), "\t", s32(raw, dream + 0x70), "\t", found, "\t", active, "\n")
    trace:flush()
    scene:flush()
    if frame == 0 or frame % 600 == 0 or frame == frames then
        local memory_file = assert(io.open(output .. "/mainram-" .. frame .. ".bin", "wb"))
        memory_file:write(raw)
        memory_file:close()
        client.screenshot(output .. "/frame-" .. frame .. ".png")
        savestate.save(output .. "/frame-" .. frame .. ".State")
    end
end
local neutral = {}
for name, value in pairs(joypad.get()) do neutral[name] = type(value) == "boolean" and false or value end
local controls = assert(io.open(output .. "/controls.tsv", "w"))
controls:write("relative_frame\tcore_frame\tmode\tbuttons\tx\ty\tz\tyaw\ttarget_x\ttarget_y\ttarget_z\tdistance_xz\tyaw_error\tcontext_state\tbehaviour_active\tlink_state\tinput_locked\tmap\n")
local target = 0x1c690c -- present in the unmodified, recorded initial game state
local starting_map = 3
local function u(address) return mainmemory.read_u32_le(address) end
local function s(address) return mainmemory.read_s32_le(address) end
local function control(frame)
    local input = {}
    for name, value in pairs(neutral) do input[name] = value end
    local mode, buttons = "neutral_invalid_context", {}
    local x, y, z, yaw, tx, ty, tz, distance, error, state, active, link, locked, map = "", "", "", "", "", "", "", "", "", "", "", "", "", ""
    local flow = pointer(u(0x8ac20), 0x2c)
    local dream = flow and pointer(u(flow + 0x28), 0x928)
    if dream and u(dream) == 0x80087bdc then
        map, link, locked = s(dream + 0x164), s(dream + 0x44), s(dream + 0x70)
        mode = "neutral_transition"
        if map == starting_map and locked == 0 and u(target) == 0x80089ad4 and s(target + 0x98) == 75
           and pointer(u(target + 0x94), 0x928) == dream then
            local coordinate = pointer(u(dream + 0x14), 0x50)
            local pose = coordinate and pointer(u(coordinate + 0x44), 0x28)
            local object_coordinate = pointer(u(target + 0x14), 0x28)
            if coordinate and pose and object_coordinate then
                x, y, z = s(coordinate + 0x18), s(coordinate + 0x1c), s(coordinate + 0x20)
                yaw = mainmemory.read_s16_le(pose + 0x12) & 0xfff
                tx, ty, tz = s(object_coordinate + 0x18), s(object_coordinate + 0x1c), s(object_coordinate + 0x20)
                state, active = s(target + 0x9c), s(target + 0xf8)
                local dx, dz = tx - x, tz - z
                distance = math.sqrt(dx * dx + dz * dz)
                local desired = math.atan(dx, dz) * 4096 / (2 * math.pi)
                error = (desired - yaw + 2048) % 4096 - 2048
                mode = "wait_at_window"
                if state <= 0 and active == 0 and distance > 1800 then
                    mode = "approach_window"
                    if error < -96 then buttons[#buttons + 1] = "P1 D-Pad Left" end
                    if error > 96 then buttons[#buttons + 1] = "P1 D-Pad Right" end
                    if math.abs(error) < 1100 then
                        buttons[#buttons + 1] = "P1 D-Pad Up"
                        if distance > 12288 then buttons[#buttons + 1] = "P1 X" end
                    end
                end
            end
        end
    end
    for _, name in ipairs(buttons) do
        assert(neutral[name] ~= nil, "Unknown requested control")
        input[name] = true
    end
    controls:write(frame, "\t", emu.framecount(), "\t", mode, "\t", table.concat(buttons, ","), "\t", x, "\t", y, "\t", z,
        "\t", yaw, "\t", tx, "\t", ty, "\t", tz, "\t", distance, "\t", error, "\t", state, "\t", active,
        "\t", link, "\t", locked, "\t", map, "\n")
    if frame % 60 == 0 then controls:flush() end
    return input
end
client.SetSoundOn(false)
client.setscreenshotosd(false)
client.speedmode(400)
inspect(0)
for frame = 1, frames do
    joypad.set(control(frame))
    emu.frameadvance()
    if frame % 30 == 0 or frame == frames then inspect(frame) end
end
controls:close()
trace:close()
scene:close()
local done = assert(io.open(output .. "/completed.txt", "w"))
done:write(frames, " frames; frame-level NPC memory observations, not direct callback entries or whole-encounter acceptance.\n")
done:close()
client.exit()
