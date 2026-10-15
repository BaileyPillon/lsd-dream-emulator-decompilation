-- Pure regression check of the production helper; no emulator APIs are called.
local path = arg and arg[1] or "research/npc_encounter/observe.lua"
local file = assert(io.open(path, "rb"))
local source = file:read("*a")
file:close()
local begin_marker = "-- BEGIN PURE NEUTRAL HELPER\n"
local end_marker = "-- END PURE NEUTRAL HELPER"
local _, first = assert(source:find(begin_marker, 1, true))
local last = assert(source:find(end_marker, first + 1, true))
local helper = source:sub(first + 1, last - 1)
local neutralize = assert(load(helper .. "\nreturn neutralize", "@production-neutral-helper", "t"))()

local function exercise(implementation)
    local cases = {
        {held = true},
        {released = false},
        {a = true, b = false, c = true},
        {},
        {axis = 128, label = "unchanged"},
    }
    for _, input in ipairs(cases) do
        local result = implementation(input)
        assert(result ~= input)
        for name, value in pairs(input) do
            if type(value) == "boolean" then
                assert(result[name] == false)
            else
                assert(result[name] == value)
            end
        end
    end
    assert(cases[1].held == true and cases[2].released == false)
    return #cases
end

assert(exercise(neutralize) == 5)
local function old_expression(values)
    local result = {}
    for name, value in pairs(values) do
        result[name] = type(value) == "boolean" and false or value
    end
    return result
end
local ok, message = pcall(exercise, old_expression)
assert(not ok and tostring(message):find("assertion failed", 1, true))
print("Passed five production-helper cases; detected the held-button negative control.")
