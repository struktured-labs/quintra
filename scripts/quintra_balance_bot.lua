-- Read-only heuristic play agent for real-ROM balance sampling.
-- It never edits HP, entities, RNG, or progression: only controller input.

local KEY_A, KEY_B = 0x01, 0x02
local KEY_START = 0x08
local KEY_RIGHT, KEY_LEFT, KEY_UP, KEY_DOWN = 0x10, 0x20, 0x40, 0x80
local CARD_DX, CARD_DY = {0, 1, 0, -1}, {-1, 0, 1, 0}
local CARD_KEYS = {KEY_UP, KEY_RIGHT, KEY_DOWN, KEY_LEFT}

local RS = tonumber(os.getenv("QUINTRA_RS_ADDR") or "0") or 0
local PL = tonumber(os.getenv("QUINTRA_PL_ADDR") or "0") or 0
local EN = tonumber(os.getenv("QUINTRA_EN_ADDR") or "0") or 0
local TM = tonumber(os.getenv("QUINTRA_TM_ADDR") or "0") or 0
local LS = tonumber(os.getenv("QUINTRA_SCREEN_ADDR") or "0") or 0
local CLASS = tonumber(os.getenv("QUINTRA_BOT_CLASS") or "0") or 0
local RUN = tonumber(os.getenv("QUINTRA_BOT_RUN") or "0") or 0
local LIMIT = tonumber(os.getenv("QUINTRA_BOT_FRAMES") or "10800") or 10800
local OUT = os.getenv("QUINTRA_BOT_OUT") or "/tmp/quintra-balance.csv"
local DEBUG = os.getenv("QUINTRA_BOT_DEBUG") == "1"
local DEBUG_OUT = os.getenv("QUINTRA_BOT_DEBUG_OUT")
local DEBUG_SCREEN = os.getenv("QUINTRA_BOT_DEBUG_SCREEN")

local function debug_log(line)
    console:log(line)
    if DEBUG_OUT then
        local df = io.open(DEBUG_OUT, "a")
        if df then df:write(line .. "\n"); df:close() end
    end
end

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
            if d < bestd then
                best, bestd = {
                    x=ex, y=ey, slot=i, hp=emu:read8(p + 14),
                    kind=emu:read8(p + 17), state6=emu:read8(p + 23)
                }, d
            end
        end
    end
    return best
end

local function leech_attached()
    if EN == 0 then return false end
    for i = 0, 31 do
        local p = EN + i * 28
        if emu:read8(p) == 2 and emu:read8(p + 1) % 2 == 1
            and emu:read8(p + 17) == 13 and emu:read8(p + 23) ~= 0 then
            return true
        end
    end
    return false
end

-- Hearts, currency, passive relics, and MP are part of the run economy.
-- Ignore shops (the policy has no purchasing model), weapon swaps (which
-- change range policy), and permanent villagers.
local function pickup_target(px, py)
    local best, bestd = nil, 65535
    if EN == 0 then return nil end
    for i = 0, 31 do
        local p = EN + i * 28
        local kind = emu:read8(p + 17)
        if emu:read8(p) == 3 and emu:read8(p + 1) % 2 == 1
            and (kind <= 3 or kind == 6) then
            local ex, ey = emu:read8(p + 3), emu:read8(p + 7)
            -- Byte values above the visible bounds represent negative/off-map
            -- drops (for example, an enemy dying against the north wall).
            if ex <= 152 and ey <= 128 then
                local d = math.abs(ex - px) + math.abs(ey - py)
                if d < bestd then best, bestd = {x=ex, y=ey}, d end
            end
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

-- Mirror room.c's feet-anchored collision box for one prospective pixel.
-- Tile BFS plans globally; this answers whether its immediate controller
-- input is physically possible from the body's current sub-tile offset.
local function pixel_walkable(x, y)
    if x < 0 or x >= 160 or y < 0 or y >= 136 then return false end
    return walkable(emu:read8(TM + math.floor(y / 8) * 20 + math.floor(x / 8)))
end

local function can_step(px, py, key)
    local nx, ny = px, py
    if key == KEY_RIGHT then nx = nx + 1
    elseif key == KEY_LEFT then nx = nx - 1
    elseif key == KEY_DOWN then ny = ny + 1
    elseif key == KEY_UP then ny = ny - 1
    else return true end
    return pixel_walkable(nx + 2, ny + 8)
        and pixel_walkable(nx + 13, ny + 8)
        and pixel_walkable(nx + 2, ny + 15)
        and pixel_walkable(nx + 13, ny + 15)
end

local function direction_from_keys(keys)
    if keys % 0x20 >= KEY_RIGHT then return KEY_RIGHT end
    if keys % 0x40 >= KEY_LEFT then return KEY_LEFT end
    if keys % 0x80 >= KEY_UP then return KEY_UP end
    if keys >= KEY_DOWN then return KEY_DOWN end
    return 0
end

-- Convert a tile-BFS direction into collision-safe pixel input. A 12px body
-- can occupy the same nominal tile cell at several offsets; before moving
-- through a narrow gap, center the perpendicular axis on the cell represented
-- by BFS. This closes the tile-vs-pixel mismatch without touching game state.
local function aligned_step(d, sx, sy, px, py, fallback)
    if not d then return fallback end
    if d == 1 or d == 3 then
        local want_x = sx * 8 - 9
        if px < want_x - 1 then return KEY_RIGHT end
        if px > want_x + 1 then return KEY_LEFT end
    else
        local want_y = sy * 8 - 11
        if want_y < 0 then want_y = 0 elseif want_y > 120 then want_y = 120 end
        if py < want_y - 1 then return KEY_DOWN end
        if py > want_y + 1 then return KEY_UP end
    end
    return CARD_KEYS[d] or fallback
end

-- Controller-only melee pursuit around procgen cover. Ranged champions can
-- fire over a useful standoff distance, but short weapons must first route to
-- a body-valid cell near the target instead of clawing into the intervening
-- pillar forever.
local function target_step(px, py, ex, ey, fallback)
    if TM == 0 then return fallback end
    local sx, sy = math.floor((px + 13) / 8), math.floor((py + 15) / 8)
    local gx, gy = math.floor((ex + 4) / 8), math.floor((ey + 4) / 8)
    local qx, qy, head, tail = {sx}, {sy}, 1, 1
    local seen, prev, prevkey = {}, {}, {}
    local start = sy * 20 + sx
    seen[start] = true
    local target
    while head <= tail do
        local x, y = qx[head], qy[head]; head = head + 1
        -- Cardinal weapons cannot connect from a diagonal stopping cell.
        -- Finish on the target's row or column, within two tiles, so the
        -- subsequent aim input describes a real melee line instead of
        -- repeatedly slashing past one corner of the enemy hitbox.
        if (x == gx and math.abs(y - gy) <= 2)
            or (y == gy and math.abs(x - gx) <= 2) then
            target = y * 20 + x
            break
        end
        for d = 1, 4 do
            local nx, ny = x + CARD_DX[d], y + CARD_DY[d]
            local nk = ny * 20 + nx
            if nx >= 1 and nx <= 19 and ny >= 1 and ny <= 16
                and not seen[nk] and body_walkable(nx, ny) then
                seen[nk], prev[nk], prevkey[nk] = true, y * 20 + x, d
                tail = tail + 1; qx[tail], qy[tail] = nx, ny
            end
        end
    end
    if not target or target == start then return fallback end
    while prev[target] and prev[target] ~= start do target = prev[target] end
    return aligned_step(prevkey[target], sx, sy, px, py, fallback)
end

-- Shortest-path step to any boundary door except the door we entered from.
-- Recomputed only in cleared rooms; 340 cells is tiny compared with emulation.
local function door_step(px, py)
    if TM == 0 then return KEY_DOWN end
    local sx, sy = math.floor((px + 13) / 8), math.floor((py + 15) / 8)
    if sx < 0 then sx = 0 elseif sx > 19 then sx = 19 end
    if sy < 0 then sy = 0 elseif sy > 16 then sy = 16 end
    local entered = emu:read8(RS + 6)
    local back = entered ~= 255 and ((entered + 2) % 4) or 255
    local in_world = emu:read8(RS + 17) == 1
    local world_screen = emu:read8(RS + 18)
    -- Shortest authored route to dungeon gate screen 6.
    local world_route = {1, 1, 2, 2, 1, 1, 4, 3, 1, 1, 0, 3, 1, 1, 0, 3}
    local wanted = in_world and world_route[world_screen + 1] or nil
    local qx, qy, head, tail = {}, {}, 1, 1
    local seen, prev, prevkey = {}, {}, {}
    local start = sy * 20 + sx
    qx[1], qy[1], seen[start] = sx, sy, true
    local tx, ty, target, target_dir = sx, sy, nil, nil
    while head <= tail do
        local x, y = qx[head], qy[head]; head = head + 1
        if in_world and world_screen == 6 and x == 10 and y == 8 then
            target, target_dir, tx, ty = y * 20 + x, 4, x, y
            break
        end
        -- Nodes represent the feet center. Near-side exits trigger at inner
        -- cells (N y=1 / W x=1); verify their boundary tile is a door.
        local dir = (y == 1 and x == 10 and emu:read8(TM + 10) == 3) and 0
            or ((x == 19 and y == 9 and emu:read8(TM + 9 * 20 + 19) == 3) and 1
            or ((y == 16 and x == 10 and emu:read8(TM + 16 * 20 + 10) == 3) and 2
            or ((x == 1 and y == 9 and emu:read8(TM + 9 * 20) == 3) and 3 or 255)))
        if dir ~= 255 and ((in_world and dir == wanted)
            or (not in_world and dir ~= back)) then
            target, target_dir, tx, ty = y * 20 + x, dir, x, y
            break
        end
        for d = 1, 4 do
            local nx, ny = x + CARD_DX[d], y + CARD_DY[d]
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
    -- Tile-center BFS is not precise enough at a two-tile door: the player's
    -- 12px body can occupy the correct 8px cell while its shoulder still
    -- clips the adjacent wall. Center on the runtime's known-safe top-left
    -- coordinate before taking the final boundary step.
    if (target_dir == 0 or target_dir == 2) and math.abs(ty - sy) <= 1 then
        if px < 70 then return KEY_RIGHT end
        if px > 74 then return KEY_LEFT end
    elseif (target_dir == 1 or target_dir == 3) and math.abs(tx - sx) <= 1 then
        if py < 56 then return KEY_DOWN end
        if py > 64 then return KEY_UP end
    end
    if target == start then
        if target_dir == 4 then return 0 end
        if target_dir == 0 or target_dir == 2 then
            if px < 70 then return KEY_RIGHT end
            if px > 74 then return KEY_LEFT end
        else
            if py < 56 then return KEY_DOWN end
            if py > 64 then return KEY_UP end
        end
        return CARD_KEYS[target_dir + 1]
    end
    while prev[target] and prev[target] ~= start do target = prev[target] end
    local d = prevkey[target]
    return aligned_step(d, sx, sy, px, py, KEY_DOWN)
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

local frames, max_room, last_hp, damage_taken, min_hp = 0, 0, 0, 0, 255
local rooms_seen, last_room = 1, 0
local room_enter_frame = 0
local last_px, last_py, still_frames = 255, 255, 0
local escape_timer, escape_dir, escape_index = 0, KEY_UP, 0
local shake_phase = 0
local towns_seen, town_rooms = 0, {}
local world_hops, last_world_key = 0, -1
local debug_shot_room = -1
local last_target_slot, last_target_hp = -1, 255
local no_damage_frames, flank_timer, flank_dir = 0, 0, KEY_LEFT
local wall_follow_dir, wall_follow_min = 0, 0
while frames < LIMIT do
    local hp = PL ~= 0 and emu:read8(PL + 2) or 0
    local mp = PL ~= 0 and emu:read8(PL + 4) or 0
    local mp_max = PL ~= 0 and emu:read8(PL + 3) or 0
    local active_charge = PL ~= 0 and emu:read8(PL + 18) or 0
    local room = RS ~= 0 and emu:read8(RS + 1) or 0
    local won = RS ~= 0 and emu:read8(RS + 10) or 0
    if frames == 0 then last_hp = hp end
    if hp < last_hp then damage_taken = damage_taken + (last_hp - hp) end
    last_hp = hp
    if hp < min_hp then min_hp = hp end
    if room > max_room then max_room = room end
    if room ~= last_room then
        rooms_seen, last_room, room_enter_frame = rooms_seen + 1, room, frames
        wall_follow_dir, wall_follow_min = 0, 0
        if room > 18 and room % 18 == 1 and not town_rooms[room] then
            town_rooms[room], towns_seen = true, towns_seen + 1
        end
    end
    local world_mode = RS ~= 0 and emu:read8(RS + 17) or 0
    local world_screen = RS ~= 0 and emu:read8(RS + 18) or 0
    local world_key = world_mode == 1 and world_screen or -1
    if world_key ~= last_world_key then
        if last_world_key >= 0 or world_key >= 0 then world_hops = world_hops + 1 end
        last_world_key = world_key
        wall_follow_dir, wall_follow_min = 0, 0
    end
    if hp == 0 or won ~= 0 then break end

    -- player.x/y are signed 16-bit pixels at offsets 9 and 11.
    local px, py = emu:read8(PL + 9), emu:read8(PL + 11)
    if px == last_px and py == last_py then still_frames = still_frames + 1
    else still_frames = 0 end
    last_px, last_py = px, py
    local target = enemy_target(px, py)
    -- Overworld encounters are optional traversal pressure. Follow the
    -- authored route while firing instead of treating every screen as a
    -- mandatory clear; dungeon combat remains fully engaged.
    if world_mode == 1 then target = nil end
    if target then
        if target.slot == last_target_slot and target.hp >= last_target_hp then
            no_damage_frames = no_damage_frames + 1
        else
            no_damage_frames = 0
        end
        last_target_slot, last_target_hp = target.slot, target.hp
    else
        last_target_slot, last_target_hp, no_damage_frames = -1, 255, 0
    end
    local loot = (not target and world_mode == 0) and pickup_target(px, py) or nil
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
        -- Wolfkin's claw is true melee and Vespine's Stinger is a short lunge:
        -- both must close distance instead of orbiting outside weapon reach.
        if CLASS == 0 or CLASS == 4 then
            -- Tile BFS gets us around cover; at striking distance, finish the
            -- last few pixels of perpendicular alignment before attacking.
            -- Small enemy hurtboxes make a same-tile diagonal slash miss even
            -- though both sprites appear adjacent.
            if flank_timer > 0 then
                keys = flank_dir + KEY_A
                flank_timer = flank_timer - 1
            elseif no_damage_frames > 240 then
                -- If an apparently lined-up melee target takes no damage for
                -- four seconds, cover is probably between the sprites. Make
                -- a sustained perpendicular flank, then reacquire through
                -- the normal BFS instead of slashing into that cover forever.
                if math.abs(dx) >= math.abs(dy) then
                    flank_dir = (frames % 2 == 0) and KEY_UP or KEY_DOWN
                else
                    flank_dir = (frames % 2 == 0) and KEY_LEFT or KEY_RIGHT
                end
                flank_timer, no_damage_frames = 90, 0
                keys = flank_dir + KEY_A
            elseif math.abs(dx) <= 24 and math.abs(dy) <= 24 then
                if math.abs(dx) >= math.abs(dy) and math.abs(dy) > 2 then
                    keys = dy > 0 and KEY_DOWN or KEY_UP
                elseif math.abs(dy) > math.abs(dx) and math.abs(dx) > 2 then
                    keys = dx > 0 and KEY_RIGHT or KEY_LEFT
                else
                    keys = KEY_A + aim
                end
            else
                keys = KEY_A + target_step(px, py, target.x, target.y, aim)
            end
        else
            -- Separate firing and strafing frames. Holding perpendicular
            -- directions together aimed diagonal shots past cardinal targets.
            keys = (frames % 3 == 0) and move or (KEY_A + aim)
        end
        -- Exercise the actual class kit. Signatures require a clean B edge
        -- WITHOUT A; the old A+B chord was rejected by room.c and meant the
        -- agent never raised Sauran's shield or fired the ranged signatures.
        if active_charge == 0 and mp >= 2 and frames % 180 == 0 then
            keys = KEY_B + aim
        -- Spirit Convergence requires A and B to become pressed together.
        -- Release both on the preceding frame so the next chord has two edges.
        elseif active_charge == 0 and mp == mp_max and frames % 600 == 599 then
            keys = 0
        elseif active_charge == 0 and mp == mp_max and frames % 600 == 0 then
            keys = KEY_A + KEY_B + aim
        end
    elseif loot then
        local dx, dy = loot.x - px, loot.y - py
        if math.abs(dx) > math.abs(dy) then
            keys = dx > 0 and KEY_RIGHT or KEY_LEFT
        else
            keys = dy > 0 and KEY_DOWN or KEY_UP
        end
    else
        keys = door_step(px, py) + KEY_A
    end
    -- The tile path can point through a locally blocked feet-box state near a
    -- pillar corner. After the stall threshold, follow that solid edge for at
    -- least one body width and until the planned cardinal is truly open, then
    -- return to BFS.
    if not target and not loot and world_mode == 0
        and (wall_follow_dir ~= 0 or frames - room_enter_frame > 3600) then
        local planned = direction_from_keys(keys)
        if wall_follow_dir ~= 0 then
            if wall_follow_min > 0 then wall_follow_min = wall_follow_min - 1 end
            if wall_follow_min == 0 and planned ~= 0 and can_step(px, py, planned) then
                wall_follow_dir = 0
            elseif can_step(px, py, wall_follow_dir) then
                keys = wall_follow_dir + KEY_A
            else
                wall_follow_dir = (wall_follow_dir == KEY_UP) and KEY_DOWN
                    or (wall_follow_dir == KEY_DOWN) and KEY_UP
                    or (wall_follow_dir == KEY_LEFT) and KEY_RIGHT or KEY_LEFT
                if can_step(px, py, wall_follow_dir) then
                    keys = wall_follow_dir + KEY_A
                else
                    wall_follow_dir = 0
                end
            end
        elseif planned ~= 0 and not can_step(px, py, planned) then
            if planned == KEY_LEFT or planned == KEY_RIGHT then
                wall_follow_dir = can_step(px, py, KEY_UP) and KEY_UP or KEY_DOWN
            else
                wall_follow_dir = can_step(px, py, KEY_LEFT) and KEY_LEFT or KEY_RIGHT
            end
            wall_follow_min = 24
            if can_step(px, py, wall_follow_dir) then keys = wall_follow_dir + KEY_A end
        end
    else
        wall_follow_dir, wall_follow_min = 0, 0
    end
    -- Tile routes and direct melee pursuit can both disagree with the
    -- runtime's pixel body collision. Make a sustained perpendicular
    -- sidestep after a short stationary interval instead of repeating a
    -- blocked input forever. This remains controller-only play.
    -- Cleared-room BFS often pauses briefly to align a 12px body with an 8px
    -- tile corridor. Do not mistake that precision work for a combat wedge:
    -- give routing longer, then use a shorter nudge so the planned path gets
    -- most frames. Direct pursuit still recovers aggressively.
    local stuck_limit = (not target and not loot) and 60 or 20
    if escape_timer == 0 and still_frames > stuck_limit then
        -- A wall pocket can block the intended direction AND both
        -- perpendiculars. Cycle all four cardinals across recovery attempts
        -- so the agent eventually backs out instead of oscillating forever.
        local escape_dirs = {KEY_RIGHT, KEY_DOWN, KEY_LEFT, KEY_UP}
        escape_index = (escape_index % 4) + 1
        escape_dir = escape_dirs[escape_index]
        escape_timer = (not target and not loot) and 12 or 30
        still_frames = 0
    end
    if escape_timer > 0 then
        keys = escape_dir + KEY_A
        escape_timer = escape_timer - 1
    end
    -- Gloom Leeches are intentionally shaken loose by a double-tap dash.
    -- Exercise that public controller mechanic instead of letting a latched
    -- enemy bias melee samples when its body overlaps nearby terrain.
    if leech_attached() or shake_phase ~= 0 then
        if shake_phase == 0 then
            keys, shake_phase = KEY_RIGHT, 1
        elseif shake_phase == 1 then
            keys, shake_phase = 0, 2
        elseif shake_phase == 2 then
            keys, shake_phase = KEY_RIGHT, 3
        else
            keys, shake_phase = 0, 0
        end
    end
    if DEBUG and frames % 600 == 0 then
        debug_log(string.format("BOTDBG f=%d room=%d hp=%d pos=%d,%d target=%s keys=%02X",
            frames, room, hp, px, py,
            target and string.format("enemy:%d@%d,%d hp=%d s6=%d",
                    target.kind, target.x, target.y, target.hp, target.state6)
                or (loot and string.format("loot:%d,%d", loot.x, loot.y) or "door"), keys))
    end
    if DEBUG_SCREEN and debug_shot_room ~= room
        and frames - room_enter_frame > 3600 then
        emu:screenshot(string.format("%s-r%d.png", DEBUG_SCREEN, room))
        debug_shot_room = room
    end
    tick(keys)
    frames = frames + 1
end
emu:setKeys(0)

-- Let a true win execute room_tick -> victory_enter, including the rendered
-- ending, suspend invalidation, and meta-record write, before sampling it.
if RS ~= 0 and emu:read8(RS + 10) ~= 0 then
    for _ = 1, 120 do tick(0) end
end

local bosses = RS ~= 0 and emu:read8(RS + 11) or 0
local won = RS ~= 0 and emu:read8(RS + 10) or 0
local ui_screen = LS ~= 0 and emu:read8(LS) or 255
local clears = RS ~= 0 and emu:read8(RS + 9) or 0
local kills = RS ~= 0 and emu:read8(RS + 16) or 0
local hp = PL ~= 0 and emu:read8(PL + 2) or 0
local final_x = PL ~= 0 and emu:read8(PL + 9) or 0
local final_y = PL ~= 0 and emu:read8(PL + 11) or 0
local final_world = RS ~= 0 and emu:read8(RS + 17) or 0
local final_screen = RS ~= 0 and emu:read8(RS + 18) or 0
local hostiles, last_enemy = 0, 255
if EN ~= 0 then
    for i = 0, 31 do
        local p = EN + i * 28
        if emu:read8(p) == 2 and emu:read8(p + 1) % 2 == 1 then
            hostiles = hostiles + 1
            last_enemy = emu:read8(p + 17) -- ai_data[0] / content enemy id
        end
    end
end
local seed = 0
if RS ~= 0 then
    seed = emu:read8(RS + 2)
        + emu:read8(RS + 3) * 256
        + emu:read8(RS + 4) * 65536
        + emu:read8(RS + 5) * 16777216
end
local f = io.open(OUT, "a")
if f then
    f:write(string.format("%d,%d,%.0f,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
        RUN, CLASS, seed, frames, max_room, rooms_seen, clears, kills,
        bosses, damage_taken, min_hp, final_x, final_y, final_world, final_screen,
        frames - room_enter_frame, hostiles, last_enemy, towns_seen, world_hops,
        won, ui_screen))
    f:close()
end
console:log(string.format("BALANCE class=%d frames=%d room=%d clears=%d kills=%d bosses=%d hp=%d",
    CLASS, frames, max_room, clears, kills, bosses, hp))
emu.frontend:quit()
