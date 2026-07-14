-- Read-only heuristic play agent for real-ROM balance sampling.
-- It never edits HP, entities, RNG, or progression: only controller input.

local KEY_A, KEY_B = 0x01, 0x02
local KEY_START = 0x08
local KEY_RIGHT, KEY_LEFT, KEY_UP, KEY_DOWN = 0x10, 0x20, 0x40, 0x80

local RS = tonumber(os.getenv("QUINTRA_RS_ADDR") or "0") or 0
local PL = tonumber(os.getenv("QUINTRA_PL_ADDR") or "0") or 0
local EN = tonumber(os.getenv("QUINTRA_EN_ADDR") or "0") or 0
local TM = tonumber(os.getenv("QUINTRA_TM_ADDR") or "0") or 0
local CLASS = tonumber(os.getenv("QUINTRA_BOT_CLASS") or "0") or 0
local RUN = tonumber(os.getenv("QUINTRA_BOT_RUN") or "0") or 0
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

local function walkable(tile)
    return tile == 1 or tile == 3 or tile == 19 or tile == 20
        or tile == 23 or tile == 31 or tile == 33 or tile == 34
        or tile == 7 or (tile >= 9 and tile <= 18)
end

local function body_walkable(cx, cy)
    if cx < 1 or cx > 19 or cy < 1 or cy > 16 then return false end
    return walkable(emu:read8(TM + (cy - 1) * 20 + (cx - 1)))
        and walkable(emu:read8(TM + (cy - 1) * 20 + cx))
        and walkable(emu:read8(TM + cy * 20 + (cx - 1)))
        and walkable(emu:read8(TM + cy * 20 + cx))
end

-- Shortest-path step to any boundary door except the door we entered from.
-- Recomputed only in cleared rooms; 340 cells is tiny compared with emulation.
local function door_step(px, py)
    if TM == 0 then return KEY_DOWN end
    local sx, sy = math.floor((px + 8) / 8), math.floor((py + 12) / 8)
    if sx < 0 then sx = 0 elseif sx > 19 then sx = 19 end
    if sy < 0 then sy = 0 elseif sy > 16 then sy = 16 end
    local entered = emu:read8(RS + 6)
    local back = entered ~= 255 and ((entered + 2) % 4) or 255
    local qx, qy, head, tail = {}, {}, 1, 1
    local seen, prev, prevkey = {}, {}, {}
    local start = sy * 20 + sx
    qx[1], qy[1], seen[start] = sx, sy, true
    local tx, ty, target, target_dir = sx, sy, nil, nil
    local dx, dy = {0, 1, 0, -1}, {-1, 0, 1, 0}
    while head <= tail do
        local x, y = qx[head], qy[head]; head = head + 1
        -- Nodes represent the feet center. Near-side exits trigger at inner
        -- cells (N y=1 / W x=1); verify their boundary tile is a door.
        local dir = (y == 1 and x == 10 and emu:read8(TM + 10) == 3) and 0
            or ((x == 19 and y == 9 and emu:read8(TM + 9 * 20 + 19) == 3) and 1
            or ((y == 16 and x == 10 and emu:read8(TM + 16 * 20 + 10) == 3) and 2
            or ((x == 1 and y == 9 and emu:read8(TM + 9 * 20) == 3) and 3 or 255)))
        if dir ~= 255 and dir ~= back then
            target, target_dir, tx, ty = y * 20 + x, dir, x, y
            break
        end
        for d = 1, 4 do
            local nx, ny = x + dx[d], y + dy[d]
            if nx >= 0 and nx < 20 and ny >= 0 and ny < 17 then
                local nk = ny * 20 + nx
                if not seen[nk] and body_walkable(nx, ny) then
                    seen[nk], prev[nk], prevkey[nk] = true, y * 20 + x, d
                    tail = tail + 1; qx[tail], qy[tail] = nx, ny
                end
            end
        end
    end
    if not target then return KEY_DOWN end
    if target == start then
        if target_dir == 0 or target_dir == 2 then
            if px < 72 then return KEY_RIGHT end
            if px > 72 then return KEY_LEFT end
        else
            if py < 60 then return KEY_DOWN end
            if py > 60 then return KEY_UP end
        end
        return ({KEY_UP, KEY_RIGHT, KEY_DOWN, KEY_LEFT})[target_dir + 1]
    end
    while prev[target] and prev[target] ~= start do target = prev[target] end
    local d = prevkey[target]
    return ({KEY_UP, KEY_RIGHT, KEY_DOWN, KEY_LEFT})[d] or KEY_DOWN
end

-- Boot, choose a class, start a fresh run.
-- RUN varies title-idle entropy; the class-selection padding below keeps all
-- five champions on the same seed within a run for an apples-to-apples trial.
for _ = 1, (120 + RUN * 37) do tick(0) end
tap(KEY_START)
for _ = 1, 40 do tick(0) end
for _ = 1, CLASS do
    tap(KEY_DOWN)
    for _ = 1, 12 do tick(0) end
end
for _ = 1, ((4 - CLASS) * 12) do tick(0) end
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
            -- Separate firing and strafing frames. Holding perpendicular
            -- directions together aimed diagonal shots past cardinal targets.
            keys = (frames % 3 == 0) and move or (KEY_A + aim)
        end
        if frames % 240 < 2 and keys % 2 == 1 then keys = keys + KEY_B end
    else
        keys = door_step(px, py) + KEY_A
    end
    tick(keys)
    frames = frames + 1
end
emu:setKeys(0)

local bosses = RS ~= 0 and emu:read8(RS + 11) or 0
local clears = RS ~= 0 and emu:read8(RS + 9) or 0
local kills = RS ~= 0 and emu:read8(RS + 16) or 0
local hp = PL ~= 0 and emu:read8(PL + 2) or 0
local final_x = PL ~= 0 and emu:read8(PL + 9) or 0
local final_y = PL ~= 0 and emu:read8(PL + 11) or 0
local seed = 0
if RS ~= 0 then
    seed = emu:read8(RS + 2)
        + emu:read8(RS + 3) * 256
        + emu:read8(RS + 4) * 65536
        + emu:read8(RS + 5) * 16777216
end
local f = io.open(OUT, "a")
if f then
    f:write(string.format("%d,%d,%.0f,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
        RUN, CLASS, seed, frames, max_room, rooms_seen, clears, kills,
        bosses, start_hp - hp, min_hp, final_x, final_y))
    f:close()
end
console:log(string.format("BALANCE class=%d frames=%d room=%d clears=%d kills=%d bosses=%d hp=%d",
    CLASS, frames, max_room, clears, kills, bosses, hp))
emu.frontend:quit()
