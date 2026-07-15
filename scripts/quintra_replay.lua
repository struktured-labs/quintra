-- Deterministic controller-trace replay. The trace contains only RLE-compressed
-- joypad states; this observer verifies the final cartridge state without
-- writing RAM, RNG, entities, or progression.
local TRACE = assert(os.getenv("QUINTRA_REPLAY_TRACE"), "missing QUINTRA_REPLAY_TRACE")
local RESULT = os.getenv("QUINTRA_REPLAY_RESULT") or "/tmp/quintra-replay.result"
local RS = tonumber(os.getenv("QUINTRA_RS_ADDR") or "0") or 0
local PL = tonumber(os.getenv("QUINTRA_PL_ADDR") or "0") or 0
local LS = tonumber(os.getenv("QUINTRA_SCREEN_ADDR") or "0") or 0

local expected, rows = {}, {}
for line in io.lines(TRACE) do
    if line:match("^# outcome ") then
        for key, value in line:gmatch("(%w+)=([%d]+)") do expected[key] = tonumber(value) end
    elseif not line:match("^#") and line ~= "" then
        local count, keys = line:match("^(%d+),(%d+)$")
        assert(count and keys, "malformed trace row: " .. line)
        rows[#rows + 1] = {tonumber(count), tonumber(keys)}
    end
end
assert(expected.frames and #rows > 0, "trace has no outcome or inputs")

local frames = 0
for _, row in ipairs(rows) do
    emu:setKeys(row[2])
    for _ = 1, row[1] do emu:runFrame(); frames = frames + 1 end
end
emu:setKeys(0)

local function read32(address)
    return emu:read8(address) + emu:read8(address + 1) * 256
        + emu:read8(address + 2) * 65536 + emu:read8(address + 3) * 16777216
end
local actual = {
    seed=read32(RS + 2), room=emu:read8(RS + 1), clears=emu:read8(RS + 9),
    kills=emu:read8(RS + 16), bosses=emu:read8(RS + 11), hp=emu:read8(PL + 2),
    won=emu:read8(RS + 10), screen=emu:read8(LS), frames=frames,
}
local mismatch = {}
for _, key in ipairs({"seed", "room", "clears", "kills", "bosses", "hp", "won", "screen", "frames"}) do
    if actual[key] ~= expected[key] then
        mismatch[#mismatch + 1] = string.format("%s=%s expected=%s", key, actual[key], expected[key])
    end
end
local out = assert(io.open(RESULT, "w"))
if #mismatch == 0 then
    out:write(string.format("PASS frames=%d seed=%.0f room=%d bosses=%d hp=%d won=%d\n",
        frames, actual.seed, actual.room, actual.bosses, actual.hp, actual.won))
else
    out:write("FAIL " .. table.concat(mismatch, " ") .. "\n")
end
out:close()
emu.frontend:quit()
