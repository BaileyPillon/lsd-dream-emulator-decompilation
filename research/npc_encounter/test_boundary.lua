-- Test the actual boundary reader helpers with synthetic bytes and no emulator.
local path = arg and arg[1] or "research/npc_encounter/hoop_boundary.lua"
local file = assert(io.open(path, "rb"))
local source = file:read("*a")
file:close()
local begin_marker = "-- BEGIN PURE MEMORY HELPERS\n"
local end_marker = "-- END PURE MEMORY HELPERS"
local _, first = assert(source:find(begin_marker, 1, true))
local last = assert(source:find(end_marker, first + 1, true))
local helpers = source:sub(first + 1, last - 1)
local u32, s32 = assert(load(helpers .. "\nreturn u32, s32", "@production-memory-helpers", "t"))()
local raw = string.pack("<I4i4", 0x89abcdef, -123456)
assert(u32(raw, 0) == 0x89abcdef and s32(raw, 4) == -123456)
assert(select("#", u32(raw, 0)) == 1 and select("#", s32(raw, 4)) == 1)
local row = {"frame", u32(raw, 0)}
assert(#row == 2 and row[2] == 0x89abcdef)
local function old_unsigned(bytes, address) return string.unpack("<I4", bytes, address + 1) end
local old_row = {"frame", old_unsigned(raw, 0)}
assert(#old_row == 3 and old_row[3] == 5)
print("Boundary readers return exactly one field; old multi-return control detected.")
