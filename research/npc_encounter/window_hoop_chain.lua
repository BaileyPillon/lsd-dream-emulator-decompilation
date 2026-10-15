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
trace:write("relative_frame\tcore_frame\tmap\tdream\tobject\tentity_id\tstate\tentity_tick\tcontext_state\tcontext_tick\tcontext_owner\tcallback\texpected_callback\tlink_enabled\ttriggered\tbehaviour_active\tx\ty\tz\tduration\tanimation_frame\tpose_yaw\tcontext_arg4\tcontext_arg7\n")
local scene = assert(io.open(output .. "/scene.tsv", "w"))
scene:write("relative_frame\tcore_frame\tdream\tmap\ttimer\tinput_locked\tmatched_records\tregistered_contexts\tdream_object_layout_valid\n")
local function pointer(value, length)
    local segment = value & 0xe0000000
    local address = value & 0x1fffffff
    if value == 0 or address % 4 ~= 0 or address + length > 0x200000
       or (segment ~= 0 and segment ~= 0x80000000 and segment ~= 0xa0000000) then return nil end
    return address
end
local function u32(raw, offset) return string.unpack("<I4", raw, offset + 1) end
local function s32(raw, offset) return string.unpack("<i4", raw, offset + 1) end
local function capture(frame, raw)
    if frame == 0 or frame % 3000 == 0 or frame == frames then
        local memory_file = assert(io.open(output .. "/mainram-" .. frame .. ".bin", "wb"))
        memory_file:write(raw)
        memory_file:close()
        client.screenshot(output .. "/frame-" .. frame .. ".png")
        savestate.save(output .. "/frame-" .. frame .. ".State")
    end
end
local function inspect(frame)
    local raw = mainmemory.read_bytes_as_binary_string(0, 0x200000)
    assert(#raw == 0x200000)
    local flow = pointer(u32(raw, 0x8ac20), 0x2c)
    local dream = flow and pointer(u32(raw, flow + 0x28), 0x928)
    if not flow or u32(raw, flow) ~= 0x8006d3c8 or not dream or u32(raw, dream) ~= 0x80087bdc then
        scene:write(frame, "\t", emu.framecount(), "\t\t\t\t\t0\t0\t0\n")
        trace:flush()
        scene:flush()
        capture(frame, raw)
        return
    end
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
                local transform = pointer(u32(raw, object + 0x14), 0x50)
                local x, y, z = "", "", ""
                if transform then x, y, z = s32(raw, transform + 0x18), s32(raw, transform + 0x1c), s32(raw, transform + 0x20) end
                local object_pose = transform and pointer(u32(raw, transform + 0x44), 0x28)
                local pose_yaw = object_pose and string.unpack("<i2", raw, object_pose + 0x12 + 1) or ""
                trace:write(frame, "\t", emu.framecount(), "\t", map, "\t", string.format("%08x", dream),
                    "\t", string.format("%08x", object), "\t", entity_id, "\t", s32(raw, object + 0x44),
                    "\t", s32(raw, object + 0xfc), "\t", context, "\t", s32(raw, object + 0xa0),
                    "\t", string.format("%08x", owner), "\t", string.format("%08x", callback),
                    "\t", string.format("%08x", expected), "\t", s32(raw, object + 0xf0),
                    "\t", s32(raw, object + 0xf4), "\t", s32(raw, object + 0xf8), "\t", x, "\t", y, "\t", z, "\t", s32(raw, object + 0x80), "\t", s32(raw, object + 0x84), "\t", pose_yaw, "\t", s32(raw, object + 0xac), "\t", s32(raw, object + 0xb8), "\n")
            end
        end
    end
    scene:write(frame, "\t", emu.framecount(), "\t", string.format("%08x", dream), "\t", map,
                "\t", u32(raw, dream + 0x24), "\t", s32(raw, dream + 0x70), "\t", found, "\t", active, "\t1\n")
    trace:flush()
    scene:flush()
    capture(frame, raw)
end
-- BEGIN PURE NEUTRAL HELPER
local function neutralize(values)
    local result = {}
    for name, value in pairs(values) do
        if type(value) == "boolean" then
            result[name] = false
        else
            result[name] = value
        end
    end
    return result
end
-- END PURE NEUTRAL HELPER
local input_sample = joypad.get()
local neutral = neutralize(input_sample)
local input_keys = {}
for name, value in pairs(input_sample) do
    assert(type(value) == "boolean" or type(value) == "number", "Unsupported controller value: " .. name)
    if type(value) == "boolean" then
        assert(neutral[name] == false)
    else
        assert(value == value and math.abs(value) < 2147483648)
        assert(neutral[name] == value)
    end
    input_keys[#input_keys + 1] = name
end
table.sort(input_keys)
local input_definition = assert(io.open(output .. "/input-definition.tsv", "w"))
input_definition:write("name\ttype\tinitial_value\tneutral_value\n")
for _, name in ipairs(input_keys) do
    input_definition:write(name, "\t", type(input_sample[name]), "\t", tostring(input_sample[name]), "\t", tostring(neutral[name]), "\n")
end
input_definition:close()
local submitted = assert(io.open(output .. "/submitted.tsv", "w"))
submitted:write("relative_frame\tcore_frame\tmode\tpad_buttons\tpad_released\tpad_pressed")
for _, name in ipairs(input_keys) do submitted:write("\t", name) end
submitted:write("\n")
local controls = assert(io.open(output .. "/controls.tsv", "w"))
controls:write("relative_frame\tcore_frame\tmode\tbuttons\tx\ty\tz\tyaw\ttarget_x\ttarget_y\ttarget_z\tdistance_xz\tyaw_error\tcontext_state\tbehaviour_active\tlink_state\tinput_locked\tmap\n")
local target = 0x1c690c -- Window after the original early map-3 load
local target_entity = 75
local chain_stage = 0
local activated = false
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
        if chain_stage == 0 and map == 12 then
            chain_stage, target, target_entity, starting_map = 1, 0x1c5dcc, 71, 12
            activated = false
        end
        mode = "neutral_transition"
        if map == starting_map and locked == 0 and u(target) == 0x80089ad4 and s(target + 0x98) == target_entity
           and pointer(u(target + 0x94), 0x928) == dream then
            local coordinate = pointer(u(dream + 0x14), 0x50)
            local pose = coordinate and pointer(u(coordinate + 0x44), 0x28)
            local object_coordinate = pointer(u(target + 0x14), 0x28)
            if coordinate and pose and object_coordinate then
                x, y, z = s(coordinate + 0x18), s(coordinate + 0x1c), s(coordinate + 0x20)
                yaw = mainmemory.read_s16_le(pose + 0x12) & 0xfff
                tx, ty, tz = s(object_coordinate + 0x18), s(object_coordinate + 0x1c), s(object_coordinate + 0x20)
                state, active = s(target + 0x9c), s(target + 0xf8)
                if state == target_entity + 1 and active == 1 and pointer(u(target + 0xa4), 0x108) == target
                   and u(target + 0xa8) == u(0x89ea4 + target_entity * 16 + 12) then
                    activated = true
                end
                local dx, dz = tx - x, tz - z
                distance = math.sqrt(dx * dx + dz * dz)
                local desired = math.atan(dx, dz) * 4096 / (2 * math.pi)
                error = (desired - yaw + 2048) % 4096 - 2048
                mode = (activated and "neutral_after_entity_" or "wait_at_entity_") .. tostring(target_entity)
                if not activated and state <= 0 and active == 0 and distance > 1800 then
                    mode = "approach_entity_" .. tostring(target_entity)
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
    local pad_buttons, pad_released, pad_pressed = "", "", ""
    if flow and u(flow) == 0x8006d3c8 then
        local graphics = pointer(u(flow + 0x1c), 0x14)
        local pad = graphics and pointer(u(graphics + 4), 0x20)
        if pad and u(pad) == 0x8006d370 then
            pad_buttons, pad_released, pad_pressed = u(pad + 0x10), u(pad + 0x14), u(pad + 0x18)
        end
    end
    submitted:write(frame, "\t", emu.framecount(), "\t", mode, "\t", pad_buttons, "\t", pad_released, "\t", pad_pressed)
    local requested = {}
    for _, name in ipairs(buttons) do requested[name] = true end
    for _, name in ipairs(input_keys) do
        if type(input[name]) == "boolean" then
            assert(input[name] == (requested[name] == true), "Unrecorded held digital button")
            submitted:write("\t", input[name] and "1" or "0")
        else
            assert(input[name] == neutral[name], "Analog baseline changed")
            submitted:write("\t", tostring(input[name]))
        end
    end
    submitted:write("\n")
    if frame % 60 == 0 then submitted:flush() end
    controls:write(frame, "\t", emu.framecount(), "\t", mode, "\t", table.concat(buttons, ","), "\t", x, "\t", y, "\t", z,
        "\t", yaw, "\t", tx, "\t", ty, "\t", tz, "\t", distance, "\t", error, "\t", state, "\t", active,
        "\t", link, "\t", locked, "\t", map, "\n")
    if frame % 60 == 0 then controls:flush() end
    local digital, analog = {}, {}
    for _, name in ipairs(input_keys) do
        if type(input[name]) == "boolean" then digital[name] = input[name]
        else analog[name] = input[name] end
    end
    return digital, analog
end
client.SetSoundOn(false)
client.setscreenshotosd(false)
client.speedmode(400)
inspect(0)
for frame = 1, frames do
    local digital, analog = control(frame)
    joypad.set(digital)
    joypad.setanalog(analog)
    emu.frameadvance()
    if frame % 30 == 0 or frame == frames then inspect(frame) end
end
controls:close()
submitted:close()
trace:close()
scene:close()
local done = assert(io.open(output .. "/completed.txt", "w"))
done:write(frames, " frames; frame-level NPC memory observations, not direct callback entries or whole-encounter acceptance.\n")
done:close()
local clear_analog = {}
for name, value in pairs(input_sample) do
    if type(value) == "number" then clear_analog[name] = "" end
end
joypad.setanalog(clear_analog)
client.exit()
