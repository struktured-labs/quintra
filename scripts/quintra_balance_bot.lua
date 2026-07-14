-- Read-only heuristic play agent for real-ROM balance sampling.
-- It never edits HP, entities, RNG, or progression: only controller input.

local KEY_A, KEY_B = 0x01, 0x02
local KEY_START = 0x08
local KEY_RIGHT, KEY_LEFT, KEY_UP, KEY_DOWN = 0x10, 0x20, 0x40, 0x80

local RS = tonumber(os.getenv("QUINTRA_RS_ADDR") or "0") or 0
local PL = tonumber(os.getenv("QUINTRA_PL_ADDR") or "0") or 0
local EN = tonumber(os.getenv("QUINTRA_EN_ADDR") or "0") or 0
local CLASS = tonumber(os.getenv("QUINTRA_BOT_CLASS") or "0") or 0
local LIMIT = tonumber(os.getenv("QUINTRA_BOT_FRAMES") or "10800") or 10800
local OUT = os.getenv("QUINTRA_BOT_OUT") or "/tmp/quintra-balance.csv"

local function tick(keys)
    emu:setKeys(keys or 0)
    emu:runFrame()
end

local function tap(key)
    tick(key); tick(key); tick(0); tick(0)
end

local function enemy_target(px, py)
    local best, bestd = nil, 65535
    if EN == 0 then return nil end
    for i = 0, 31 do
        local p = EN + i * 28
        if emu:read8(p) == 2 and emu:read8(p + 1) % 2 == 1 then
            -- fix8_t is signed 24.8 here; byte +1 is the on-screen integer.
            local ex, ey = emu:read8(p + 3), emu:read8(p + 7)
            local d = math.abs(ex - px) + math.abs(ey - py)
            if d < bestd then best, bestd = {x=ex, y=ey}, d end
        end
    end
    return best
end

-- Boot, choose a class, start a fresh run.
for _ = 1, 120 do tick(0) end
tap(KEY_START)
for _ = 1, 40 do tick(0) end
for _ = 1, CLASS do
    tap(KEY_DOWN)
    for _ = 1, 12 do tick(0) end
end
tap(KEY_A)
for _ = 1, 45 do tick(0) end

local frames, max_room, start_hp, min_hp = 0, 0, 0, 255
local rooms_seen, last_room = 1, 0
while frames < LIMIT do
    local hp = PL ~= 0 and emu:read8(PL + 2) or 0
    local room = RS ~= 0 and emu:read8(RS + 1) or 0
    if frames == 0 then start_hp = hp end
    if hp < min_hp then min_hp = hp end
    if room > max_room then max_room = room end
    if room ~= last_room then rooms_seen, last_room = rooms_seen + 1, room end
    if hp == 0 then break end

    -- player.x/y are signed 16-bit pixels at offsets 9 and 11.
    local px, py = emu:read8(PL + 9), emu:read8(PL + 11)
    local target = enemy_target(px, py)
    local keys
    if target then
        local dx, dy = target.x - px, target.y - py
        local aim
        if math.abs(dx) > math.abs(dy) then
            aim = dx > 0 and KEY_RIGHT or KEY_LEFT
        else
            aim = dy > 0 and KEY_DOWN or KEY_UP
        end
        -- Orbit rather than face-tank; reverse orbit every 150 frames.
        local clockwise = math.floor(frames / 150) % 2 == 0
        local move
        if aim == KEY_UP then move = clockwise and KEY_RIGHT or KEY_LEFT
        elseif aim == KEY_DOWN then move = clockwise and KEY_LEFT or KEY_RIGHT
        elseif aim == KEY_LEFT then move = clockwise and KEY_UP or KEY_DOWN
        else move = clockwise and KEY_DOWN or KEY_UP end
        -- Wolfkin's primary is true melee: close distance instead of kiting.
        if CLASS == 0 then
            keys = KEY_A + aim
        else
            keys = KEY_A + aim + move
        end
        if frames % 240 < 2 then keys = keys + KEY_B end
    else
        -- Cleared: seek the south exit. Small horizontal correction helps
        -- rooms whose center lane contains a generated obstacle.
        if px < 72 then keys = KEY_RIGHT + KEY_A
        elseif px > 88 then keys = KEY_LEFT + KEY_A
        else keys = KEY_DOWN + KEY_A end
    end
    tick(keys)
    frames = frames + 1
end
emu:setKeys(0)

local bosses = RS ~= 0 and emu:read8(RS + 11) or 0
local clears = RS ~= 0 and emu:read8(RS + 9) or 0
local kills = RS ~= 0 and emu:read8(RS + 16) or 0
local hp = PL ~= 0 and emu:read8(PL + 2) or 0
local f = io.open(OUT, "a")
if f then
    f:write(string.format("%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
        CLASS, frames, max_room, rooms_seen, clears, kills, bosses, start_hp - hp, min_hp))
    f:close()
end
console:log(string.format("BALANCE class=%d frames=%d room=%d clears=%d kills=%d bosses=%d hp=%d",
    CLASS, frames, max_room, clears, kills, bosses, hp))
emu.frontend:quit()
