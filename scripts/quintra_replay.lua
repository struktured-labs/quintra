-- Deterministic controller-trace replay. The trace contains only RLE-compressed
-- joypad states; this observer verifies the final cartridge state without
-- writing RAM, RNG, entities, or progression.
local TRACE = assert(os.getenv("QUINTRA_REPLAY_TRACE"), "missing QUINTRA_REPLAY_TRACE")
local RESULT = os.getenv("QUINTRA_REPLAY_RESULT") or "/tmp/quintra-replay.result"
local RS = tonumber(os.getenv("QUINTRA_RS_ADDR") or "0") or 0
local PL = tonumber(os.getenv("QUINTRA_PL_ADDR") or "0") or 0
local LS = tonumber(os.getenv("QUINTRA_SCREEN_ADDR") or "0") or 0
local EN = tonumber(os.getenv("QUINTRA_EN_ADDR") or "0") or 0
local DUMP_ENTITIES = os.getenv("QUINTRA_REPLAY_DUMP_ENTITIES") == "1"
local FRAME_LIMIT = tonumber(os.getenv("QUINTRA_REPLAY_FRAME_LIMIT") or "")

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
    if FRAME_LIMIT and frames >= FRAME_LIMIT then break end
    emu:setKeys(row[2])
    for _ = 1, row[1] do
        if FRAME_LIMIT and frames >= FRAME_LIMIT then break end
        emu:runFrame()
        frames = frames + 1
    end
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
if FRAME_LIMIT and frames < expected.frames then
    out:write(string.format(
        "PARTIAL frames=%d seed=%.0f room=%d bosses=%d hp=%d won=%d\n",
        frames, actual.seed, actual.room, actual.bosses, actual.hp, actual.won))
elseif #mismatch == 0 then
    out:write(string.format("PASS frames=%d seed=%.0f room=%d bosses=%d hp=%d won=%d\n",
        frames, actual.seed, actual.room, actual.bosses, actual.hp, actual.won))
else
    out:write("FAIL " .. table.concat(mismatch, " ") .. "\n")
end
if DUMP_ENTITIES and EN ~= 0 then
    for slot = 0, 31 do
        local p = EN + slot * 28
        if emu:read8(p + 1) % 2 == 1 then
            out:write(string.format(
                "ENTITY slot=%d type=%d kind=%d flags=%d x=%d y=%d aux=%d\n",
                slot, emu:read8(p), emu:read8(p + 17), emu:read8(p + 1),
                emu:read8(p + 3), emu:read8(p + 7), emu:read8(p + 18)))
        end
    end
end
out:close()
-- See quintra_balance_bot.lua: headless has no frontend object and exits once
-- the deterministic replay observer returns.
if emu.frontend and emu.frontend.quit then emu.frontend:quit() end
