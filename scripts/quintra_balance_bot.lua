-- Read-only heuristic play agent for real-ROM balance sampling.
-- It never edits HP, entities, RNG, or progression: only controller input.

local KEY_A, KEY_B = 0x01, 0x02
local KEY_START = 0x08
local KEY_RIGHT, KEY_LEFT, KEY_UP, KEY_DOWN = 0x10, 0x20, 0x40, 0x80
local CARD_DX, CARD_DY = {0, 1, 0, -1}, {-1, 0, 1, 0}
local CARD_KEYS = {KEY_UP, KEY_RIGHT, KEY_DOWN, KEY_LEFT}
local VOID_SAFE_X, VOID_SAFE_Y = {20, 124, 20, 124}, {20, 20, 100, 100}
-- Per-screen shortest authored exit toward dungeon gate screen 6; 4 means
-- use the central staircase rather than a boundary door.
local WORLD_ROUTE = {1, 1, 2, 2, 1, 1, 4, 3, 1, 1, 0, 3, 1, 1, 0, 3}

local RS = tonumber(os.getenv("QUINTRA_RS_ADDR") or "0") or 0
local PL = tonumber(os.getenv("QUINTRA_PL_ADDR") or "0") or 0
local EN = tonumber(os.getenv("QUINTRA_EN_ADDR") or "0") or 0
local TM = tonumber(os.getenv("QUINTRA_TM_ADDR") or "0") or 0
local LS = tonumber(os.getenv("QUINTRA_SCREEN_ADDR") or "0") or 0
local FC = tonumber(os.getenv("QUINTRA_FRAME_ADDR") or "0") or 0
local CLASS = tonumber(os.getenv("QUINTRA_BOT_CLASS") or "0") or 0
local RUN = tonumber(os.getenv("QUINTRA_BOT_RUN") or "0") or 0
local BOOT_EXTRA = tonumber(os.getenv("QUINTRA_BOT_BOOT_EXTRA") or "0") or 0
local LIMIT = tonumber(os.getenv("QUINTRA_BOT_FRAMES") or "10800") or 10800
local OUT = os.getenv("QUINTRA_BOT_OUT") or "/tmp/quintra-balance.csv"
local DEBUG = os.getenv("QUINTRA_BOT_DEBUG") == "1"
local DEBUG_OUT = os.getenv("QUINTRA_BOT_DEBUG_OUT")
local DEBUG_SCREEN = os.getenv("QUINTRA_BOT_DEBUG_SCREEN")
local TRACE_OUT = os.getenv("QUINTRA_BOT_TRACE_OUT")
-- A class-aware default uses measured pulse lanes for close/short-range
-- champions while Picsean's slow piercing bubbles use independently measured
-- orbit-and-fire spacing. A late-phase fallback below changes only the final
-- few giant HP, where that orbit otherwise risks never taking a cardinal hit.
local GIANT_POLICY = os.getenv("QUINTRA_BOT_GIANT_POLICY") or "classwise"
if GIANT_POLICY ~= "baseline" and GIANT_POLICY ~= "orbit"
    and GIANT_POLICY ~= "orbit_fire" and GIANT_POLICY ~= "pulse_fire"
    and GIANT_POLICY ~= "classwise" then
    GIANT_POLICY = "classwise"
end
-- Wolfkin's claw requires the tightest giant lane, but paired controller-only
-- trials clear two first bosses at 32px versus one at 28px. The ranged/tank
-- kits did not improve with the wider buffer, so classwise play keeps their
-- established 28px retreat. An explicit environment value always wins for
-- offline policy search.
local GIANT_RETREAT_RANGE = tonumber(os.getenv("QUINTRA_BOT_GIANT_RETREAT_RANGE")
    or ((GIANT_POLICY == "classwise" and (CLASS == 0 or CLASS == 4))
        and (CLASS == 4 and "36" or "32") or "28")) or 28
if GIANT_RETREAT_RANGE < 16 then GIANT_RETREAT_RANGE = 16 end
if GIANT_RETREAT_RANGE > 56 then GIANT_RETREAT_RANGE = 56 end
-- Keep the established controller behavior as the default, but expose an
-- explicit no-signature control.  This lets a balance experiment distinguish
-- the value of real B ability use from unrelated navigation/aim changes.
local ABILITY_POLICY = os.getenv("QUINTRA_BOT_ABILITY_POLICY") or "smart"
if ABILITY_POLICY ~= "off" and ABILITY_POLICY ~= "smart" then
    ABILITY_POLICY = "smart"
end
local trace_last, trace_count, trace_rows, trace_frames = nil, 0, {}, 0
local enemy_mask, enemy_seen = 0, {}

local function debug_log(line)
    console:log(line)
    if DEBUG_OUT then
        local df = io.open(DEBUG_OUT, "a")
        if df then df:write(line .. "\n"); df:close() end
    end
end

local function tick(keys)
    keys = keys or 0
    if TRACE_OUT then
        if trace_last == nil then
            trace_last, trace_count = keys, 1
        elseif keys == trace_last then
            trace_count = trace_count + 1
        else
            trace_rows[#trace_rows + 1] = string.format("%d,%d", trace_count, trace_last)
            trace_last, trace_count = keys, 1
        end
        trace_frames = trace_frames + 1
    end
    emu:setKeys(keys)
    emu:runFrame()
end

local function tap(key)
    tick(key); tick(key); tick(0); tick(0)
end

local function read16(address)
    return emu:read8(address) + emu:read8(address + 1) * 256
end

-- The stage objective is a real progression gate.  Reading it lets this
-- controller retrace to the Sigil room instead of grinding against the
-- sanctuary's intentionally locked forward door.  The offsets mirror
-- run_state_t: bosses_beaten at 11 and rift_sigils at 23.
local function stage_sigil_missing()
    if RS == 0 then return false end
    local stage = emu:read8(RS + 11) % 9
    local bit = 2 ^ stage
    return math.floor(read16(RS + 23) / bit) % 2 == 0
end

local function read_i16(address)
    local value = read16(address)
    return value >= 0x8000 and value - 0x10000 or value
end

local function enemy_target(px, py)
    local best, bestd = nil, 65535
    if EN == 0 then return nil end
    for i = 0, 31 do
        local p = EN + i * 28
        if emu:read8(p) == 2 and emu:read8(p + 1) % 2 == 1 then
            local kind = emu:read8(p + 17)
            if kind < 31 and not enemy_seen[kind] then
                enemy_seen[kind] = true
                enemy_mask = enemy_mask + 2 ^ kind
            end
            -- fix8_t is signed 24.8 here; byte +1 is the on-screen integer.
            local ex, ey = emu:read8(p + 3), emu:read8(p + 7)
            local d = math.abs(ex - px) + math.abs(ey - py)
            if d < bestd then
                best, bestd = {
                    x=ex, y=ey, slot=i, hp=emu:read8(p + 14),
                    kind=kind, state=emu:read8(p + 15),
                    clock=emu:read8(p + 18), state6=emu:read8(p + 23),
                    giant=(kind == 1) and emu:read8(p + 20) or 0,
                    pattern=emu:read8(p + 19),
                    collapse=emu:read8(p + 21),
                    safe_slot=emu:read8(p + 22)
                }, d
            end
        end
    end
    return best
end

-- A class signature is not always a single-target attack.  The Wolfkin's
-- eight-way Howl is best spent into a crowd (or a boss at claw range), so the
-- observer needs a small, read-only local population count rather than waiting
-- for an arbitrary global timer to happen during a fight.
local function hostile_count_near(px, py, radius)
    local count = 0
    if EN == 0 then return 0 end
    for i = 0, 31 do
        local p = EN + i * 28
        if emu:read8(p) == 2 and emu:read8(p + 1) % 2 == 1 then
            local ex, ey = emu:read8(p + 3), emu:read8(p + 7)
            if math.max(math.abs(ex - px), math.abs(ey - py)) <= radius then
                count = count + 1
            end
        end
    end
    return count
end

-- Boss timing must not depend on aim selection: a minion, a temporary target
-- loss while navigating cover, or a player shot can make enemy_target nil for
-- a frame even though the large boss is still alive.  The giant marker lives
-- in ai_data[3] at entity byte +20.
local function giant_active()
    if EN == 0 then return false end
    for i = 0, 31 do
        local p = EN + i * 28
        if emu:read8(p) == 2 and emu:read8(p + 1) % 2 == 1
            and emu:read8(p + 17) == 1 and emu:read8(p + 20) ~= 0 then
            return true
        end
    end
    return false
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

local function projectile_threat(px, py)
    local best, bestd = nil, 33
    if EN == 0 then return nil end
    for i = 0, 31 do
        local p = EN + i * 28
        local flags = emu:read8(p + 1)
        if emu:read8(p) == 1 and flags % 2 == 1
            and math.floor(flags / 16) % 2 == 0 then
            local ex, ey = emu:read8(p + 3), emu:read8(p + 7)
            local vx, vy = emu:read8(p + 10), emu:read8(p + 11)
            if vx >= 128 then vx = vx - 256 end
            if vy >= 128 then vy = vy - 256 end
            local d = math.abs(ex - px) + math.abs(ey - py)
            local approaching = (px - ex) * vx + (py - ey) * vy > 0
            if approaching and d < bestd then best, bestd = {x=ex, y=ey}, d end
        end
    end
    return best
end

-- Hearts, currency, passive relics, and MP are part of the run economy.
-- Weapon swaps remain outside the comparable class policy; shops are handled
-- separately below so purchases can be measured without treating wares as
-- free loot.
local function pickup_target(px, py, hp, hp_max)
    local best, bestd = nil, 65535
    local sigil, sigild = nil, 65535
    if EN == 0 then return nil end
    for i = 0, 31 do
        local p = EN + i * 28
        local kind = emu:read8(p + 17)
        if emu:read8(p) == 3 and emu:read8(p + 1) % 2 == 1
            -- Rift Sigils are a hard progression objective, not ordinary
            -- loot: skipping one makes the sanctuary gate correctly refuse
            -- the boss. The controller-only agent must seek it just like a
            -- heart or relic before it can make a meaningful balance claim.
            and (kind <= 3 or kind == 6 or kind == 11 or kind == 14)
            -- Full-health hearts intentionally remain on the floor: the
            -- cartridge preserves their value rather than consuming them
            -- with a misleading chime. Do not route an agent forever toward
            -- a reward that the real collision rule will correctly refuse.
            and (kind ~= 0 or hp < hp_max) then
            local ex, ey = emu:read8(p + 3), emu:read8(p + 7)
            -- Byte values above the visible bounds represent negative/off-map
            -- drops (for example, an enemy dying against the north wall).
            local boundary_drop = (ey < 24 and (ex < 64 or ex > 88))
                or (ey > 104 and (ex < 64 or ex > 88))
                or (ex < 24 and (ey < 52 or ey > 76))
                or (ex > 136 and (ey < 52 or ey > 76))
            if ex <= 152 and ey <= 128 and not boundary_drop then
                local d = math.abs(ex - px) + math.abs(ey - py)
                -- Player coordinates are feet-anchored; ordinary drops drift
                -- into that box, but a persistent Rift Sigil does not. Aim
                -- its contact point eight pixels above the sprite origin so
                -- the controller actually overlaps it instead of camping one
                -- pixel below forever.
                local target_y = (kind == 11) and (ey - 8) or ey
                -- A Sigil is a hard gate, not just high-value loot.  Choose
                -- it before any nearby coin/heart so the bot cannot leave
                -- its fixture room and later mistake the sanctuary lock for
                -- a navigation failure.
                if kind == 11 then
                    if d < sigild then
                        sigil, sigild = {x=ex, y=target_y, kind=kind}, d
                    end
                elseif d < bestd then
                    best, bestd = {x=ex, y=target_y}, d
                end
            end
        end
    end
    return sigil or best
end

-- Choose an affordable ware through the public walk-into purchase mechanic.
-- Missing health wins; otherwise prefer deterministic attack/max-HP upgrades
-- over the seeded general relic. This reads state to decide, but—as with aim
-- and routing—changes the cartridge only through controller input.
local function shop_target(px, py, hp, hp_max, mp_max, coins)
    local best, best_score, bestd = nil, -1, 65535
    if EN == 0 then return nil end
    for i = 0, 31 do
        local p = EN + i * 28
        if emu:read8(p) == 3 and emu:read8(p + 1) % 2 == 1
            and emu:read8(p + 17) == 4 then
            local ware, price = emu:read8(p + 18), emu:read8(p + 19)
            if coins >= price then
                local score = (ware == 0 and hp + 1 < hp_max) and 100
                    or (ware == 3 and 90)
                    or (ware == 4 and mp_max < 20 and 85)
                    or (ware == 2 and hp_max < 16 and 80)
                    or (ware == 1 and 70) or -1
                local ex, ey = emu:read8(p + 3), emu:read8(p + 7)
                local d = math.abs(ex - px) + math.abs(ey - py)
                if score > best_score or (score == best_score and d < bestd) then
                    best, best_score, bestd = {x=ex, y=ey}, score, d
                end
            end
        end
    end
    return best
end

-- Record whether the controller actually reached a stocked shop, independent
-- of whether it can yet afford (or needs) an item there. Purchases remain a
-- separate outcome so the endurance gate measures shop reachability rather
-- than a particular class's economy preference.
local function room_has_shop_ware()
    if EN == 0 then return false end
    for i = 0, 31 do
        local p = EN + i * 28
        if emu:read8(p) == 3 and emu:read8(p + 1) % 2 == 1
            and emu:read8(p + 17) == 4 then
            return true
        end
    end
    return false
end

local function walkable(tile)
    return tile == 1 or tile == 3 or tile == 19 or tile == 20
        or tile == 23 or tile == 31 or tile == 33 or tile == 34
        or tile == 7 or (tile >= 9 and tile <= 18)
end

-- Strategic routes avoid known floor hazards when a safe lane exists. Pixel
-- collision still treats spikes as physically walkable, so an emergency
-- dodge or a hero already standing on one can always escape.
local function path_walkable(tile)
    return tile ~= 31 and walkable(tile)
end

local function body_walkable(cx, cy)
    if cx < 1 or cx > 19 or cy < 1 or cy > 16 then return false end
    return path_walkable(emu:read8(TM + (cy - 1) * 20 + (cx - 1)))
        and path_walkable(emu:read8(TM + (cy - 1) * 20 + cx))
        and path_walkable(emu:read8(TM + cy * 20 + (cx - 1)))
        and path_walkable(emu:read8(TM + cy * 20 + cx))
end

local function world_body_walkable(cx, cy)
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

local function tile_at_px(x, y)
    if x < 0 or x >= 160 or y < 0 or y >= 136 then return 0 end
    return emu:read8(TM + math.floor(y / 8) * 20 + math.floor(x / 8))
end

local function body_on_spike(px, py)
    -- Mirror room.c's hazard test exactly: spikes use the feet-box center,
    -- whereas ordinary wall collision probes four corners.
    return tile_at_px(px + 8, py + 12) == 31
end

-- Mandatory fixtures deserve the same exact body route the cartridge uses,
-- rather than a coarse tile plan plus an unrelated recovery nudge.  Cache a
-- one-pixel route for the current Sigil and rebuild only if the real pickup
-- moves toward the hero.  First seek a wholly safe path; only use spikes if
-- the level genuinely leaves no other physical route to progression.
local sigil_pixel_route = nil
local function sigil_pixel_step(room, px, py, ex, ey)
    local goal_x, goal_y = ex - 2, ey - 1
    local start = py * 160 + px
    if px == goal_x and py == goal_y then return 0 end
    if sigil_pixel_route and sigil_pixel_route.room == room
        and sigil_pixel_route.goal_x == goal_x and sigil_pixel_route.goal_y == goal_y
        and sigil_pixel_route.dirs[start] then
        return sigil_pixel_route.dirs[start]
    end
    local function build(allow_spikes)
        local qx, qy, head, tail = {px}, {py}, 1, 1
        local seen, previous, step = {[start] = true}, {}, {}
        local found = nil
        while head <= tail do
            local x, y = qx[head], qy[head]; head = head + 1
            local key = y * 160 + x
            if x == goal_x and y == goal_y then found = key; break end
            for d = 1, 4 do
                local dir = CARD_KEYS[d]
                local nx, ny = x + CARD_DX[d], y + CARD_DY[d]
                local next_key = ny * 160 + nx
                if nx >= 0 and nx <= 146 and ny >= 0 and ny <= 120
                    and not seen[next_key] and can_step(x, y, dir)
                    and (allow_spikes or not body_on_spike(nx, ny)) then
                    seen[next_key], previous[next_key], step[next_key] = true, key, dir
                    tail = tail + 1; qx[tail], qy[tail] = nx, ny
                end
            end
        end
        if not found then return nil end
        local dirs, node = {}, found
        while previous[node] do
            dirs[previous[node]] = step[node]
            node = previous[node]
        end
        return dirs
    end
    local dirs = build(false) or build(true)
    if not dirs then return nil end
    sigil_pixel_route = {room=room, goal_x=goal_x, goal_y=goal_y, dirs=dirs}
    return dirs[start]
end

-- Candidate policy used only by offline search. Its mode is selected through
-- an environment variable, never by ROM state or test writes; the default
-- remains the proven baseline below.
local function giant_orbit_step(px, py, aim, retreat)
    local primary, secondary
    if aim == KEY_LEFT or aim == KEY_RIGHT then
        primary = py > 64 and KEY_UP or KEY_DOWN
        secondary = primary == KEY_UP and KEY_DOWN or KEY_UP
    else
        primary = px > 72 and KEY_LEFT or KEY_RIGHT
        secondary = primary == KEY_LEFT and KEY_RIGHT or KEY_LEFT
    end
    if can_step(px, py, primary) then return primary end
    if can_step(px, py, secondary) then return secondary end
    return retreat
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

local function clear_cardinal_lane(x, y, gx, gy)
    if x == gx then
        local lo, hi = math.min(y, gy) + 1, math.max(y, gy) - 1
        for ty = lo, hi do
            if not path_walkable(emu:read8(TM + ty * 20 + x)) then return false end
        end
        return true
    end
    if y == gy then
        local lo, hi = math.min(x, gx) + 1, math.max(x, gx) - 1
        for tx = lo, hi do
            if not path_walkable(emu:read8(TM + y * 20 + tx)) then return false end
        end
        return true
    end
    return false
end

-- Controller-only melee pursuit around procgen cover. Ranged champions can
-- fire over a useful standoff distance, but short weapons must first route to
-- a body-valid cell near the target instead of clawing into the intervening
-- pillar forever.
local function target_step(px, py, ex, ey, fallback, near_tiles)
    if TM == 0 then return fallback end
    local reach = near_tiles or 1
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
        -- Stop within one tile: Sauran's Tail Spike and Vespine's Stinger
        -- cannot connect from the old two-tile stopping cell.
        if ((x == gx and math.abs(y - gy) <= reach)
            or (y == gy and math.abs(x - gx) <= reach))
            and clear_cardinal_lane(x, y, gx, gy)
            -- Sharing a coarse 8px tile is not a firing lane: the hero's
            -- body can be on the opposite side of a pillar seam, with the
            -- target still diagonally offset by a full hurtbox. Continue BFS
            -- to a neighboring body-valid lane until pixel aim can finish.
            and (x ~= sx or y ~= sy
                or math.abs(ex - px) <= 5 or math.abs(ey - py) <= 5) then
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

-- The Void Lord's World Collapse deliberately covers almost the entire room.
-- Its marker is honest: ai_data[4] marks the long warning and ai_data[5]
-- selects one corner, modulo four. Read that public runtime state and steer
-- only with ordinary D-pad input; the player still has to reach the pocket
-- before the blast and receives no immunity from the controller.
local function void_safe_pocket_step(px, py, target)
    if not target or target.kind ~= 1 or target.giant == 0
        or target.pattern ~= 8 or target.collapse == 0 then
        return nil
    end
    local slot = (target.safe_slot % 4) + 1
    local sx, sy = VOID_SAFE_X[slot], VOID_SAFE_Y[slot]
    local dx, dy = sx - px, sy - py
    if math.abs(dx) + math.abs(dy) <= 16 then return 0 end
    local direct = math.abs(dx) >= math.abs(dy)
        and (dx > 0 and KEY_RIGHT or KEY_LEFT)
        or (dy > 0 and KEY_DOWN or KEY_UP)
    return target_step(px, py, sx, sy, direct, 0)
end

-- Shortest-path step to any boundary door except the door we entered from.
-- Recomputed only in cleared rooms; 340 cells is tiny compared with emulation.
local function rift_portal_step(px, py)
    if TM == 0 then return nil end
    for ty = 1, 15 do
        for tx = 1, 18 do
            if emu:read8(TM + ty * 20 + tx) == 34 then -- BGT_PORTAL
                -- room.c tests the feet center at player + (8,12). Aim that
                -- point at the generated portal tile instead of assuming a
                -- central staircase.  A portal can be behind a generated
                -- pillar seam, so use the normal body-aware BFS rather than
                -- repeatedly steering along the largest direct axis.
                local gx, gy = tx * 8 - 8, ty * 8 - 12
                if math.abs(gx - px) <= 2 and math.abs(gy - py) <= 2 then
                    return 0
                end
                local direct = math.abs(gx - px) >= math.abs(gy - py)
                    and (gx > px and KEY_RIGHT or KEY_LEFT)
                    or (gy > py and KEY_DOWN or KEY_UP)
                -- `target_step`'s coarse location is the bottom-right tile
                -- of the player's feet box.  Its prior portal coordinates
                -- were the hero's top-left target, off by one tile in both
                -- axes, so the BFS stopped beside the rift then fell back to
                -- a wall-bound direct steer.  Route to the footprint whose
                -- bottom-right corner is the actual portal tile.
                return target_step(px, py, tx * 8 - 4, ty * 8 - 4,
                    direct, 0)
            end
        end
    end
    return nil
end

local function door_step(px, py)
    if TM == 0 then return KEY_DOWN end
    -- This helper runs outside the main sampling loop, so it must not capture
    -- that loop's local `room` value (which is out of scope here). Read the
    -- same cartridge byte directly for town topology decisions.
    local room = emu:read8(RS + 1)
    local sx, sy = math.floor((px + 13) / 8), math.floor((py + 15) / 8)
    if sx < 0 then sx = 0 elseif sx > 19 then sx = 19 end
    if sy < 0 then sy = 0 elseif sy > 16 then sy = 16 end
    local entered = emu:read8(RS + 6)
    local back = entered ~= 255 and ((entered + 2) % 4) or 255
    local in_world = emu:read8(RS + 17) == 1
    local world_screen = emu:read8(RS + 18)
    -- Town room 19 (then every 18 rooms) is a three-screen civic hub, not a
    -- symmetric dungeon. From the arrival square use the north gate to the
    -- next region; market/forge screens return west to arrival. Without this
    -- explicit target the generic "any exit but back" chooser can keep an
    -- endurance controller pacing between civic doors forever.
    local in_town = not in_world and room > 18 and room % 18 == 1
    local town_wanted = in_town
        and (emu:read8(RS + 19) == 0 and 0 or 3) or nil
    -- The Sigil sits in local room 2. If the sanctuary is reached without it,
    -- route back through rooms 4 and 3 to the objective instead of repeatedly
    -- pressing the forward threshold that correctly refuses entry.
    local local_room = room % 6
    local return_for_sigil = not in_world and not in_town
        and local_room > 2 and stage_sigil_missing()
    -- Local room 2 is the Sigil vault. Once its objective is collected, its
    -- seed-positioned nonlinear rift is a valid forward route to local room
    -- 4. Locate the actual generated tile rather than assuming a center exit.
    if not in_world and local_room == 2 and not stage_sigil_missing() then
        local portal = rift_portal_step(px, py)
        if portal ~= nil then return portal end
    end
    -- Shortest authored route to dungeon gate screen 6.
    local wanted = in_world and WORLD_ROUTE[world_screen + 1] or nil
    if in_town then
        -- These civic lanes are intentionally straight and wide. The north
        -- gate triggers at the boundary, not at a point just inside it: the
        -- old y=8 target made a hero at y=5 walk back down forever against
        -- the gate lip. Center first, then keep pressing through the actual
        -- exit; the market and forge similarly use their west lane.
        if town_wanted == 0 then
            if px < 70 then return KEY_RIGHT end
            if px > 74 then return KEY_LEFT end
            return KEY_UP
        end
        if py < 56 then return KEY_DOWN end
        if py > 64 then return KEY_UP end
        return KEY_LEFT
    end
    -- The dungeon gate (6) and the nonlinear cave vault (15) are both
    -- central interactable nodes, not boundary exits.  Treating the vault as
    -- a normal world screen made a long-form controller run walk into its
    -- wall forever after the screen-2 cave hop instead of stepping back onto
    -- the return staircase at 72,52.
    if in_world and (world_screen == 6 or world_screen == 15) then
        local dx, dy = 72 - px, 52 - py
        if math.abs(dx) <= 2 and math.abs(dy) <= 2 then return 0 end
        local primary = math.abs(dx) >= math.abs(dy)
            and (dx > 0 and KEY_RIGHT or KEY_LEFT)
            or (dy > 0 and KEY_DOWN or KEY_UP)
        local secondary = math.abs(dx) < math.abs(dy)
            and (dx > 0 and KEY_RIGHT or KEY_LEFT)
            or (dy > 0 and KEY_DOWN or KEY_UP)
        if can_step(px, py, primary) then return primary end
        if can_step(px, py, secondary) then return secondary end
        return primary
    end
    if in_world and world_screen ~= 6 then
        local direct = CARD_KEYS[wanted + 1]
        if can_step(px, py, direct) then return direct end
        local side_a, side_b
        if wanted == 1 or wanted == 3 then
            side_a = py < 60 and KEY_DOWN or KEY_UP
            side_b = side_a == KEY_DOWN and KEY_UP or KEY_DOWN
        else
            side_a = px < 72 and KEY_RIGHT or KEY_LEFT
            side_b = side_a == KEY_RIGHT and KEY_LEFT or KEY_RIGHT
        end
        if can_step(px, py, side_a) then return side_a end
        if can_step(px, py, side_b) then return side_b end
        return direct
    end
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
        if dir ~= 255 and ((return_for_sigil and dir == back)
            or (in_world and dir == wanted)
            or (in_town and dir == town_wanted)
            or (not in_world and not in_town and not return_for_sigil
                and dir ~= back)) then
            target, target_dir, tx, ty = y * 20 + x, dir, x, y
            break
        end
        for d = 1, 4 do
            local nx, ny = x + CARD_DX[d], y + CARD_DY[d]
            if nx >= 0 and nx < 20 and ny >= 0 and ny < 17 then
                local nk = ny * 20 + nx
                if not seen[nk] and ((in_world and world_body_walkable(nx, ny))
                    or (not in_world and body_walkable(nx, ny))) then
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
        -- If we crossed into the doorway lip off-center, the shoulders can
        -- block both horizontal corrections. Back into the room first, then
        -- center and make a clean second approach.
        if target_dir == 0 and (px < 70 or px > 74) and py < 4 then
            return KEY_DOWN
        elseif target_dir == 2 and (px < 70 or px > 74) and py > 116 then
            return KEY_UP
        end
        if px < 70 then return KEY_RIGHT end
        if px > 74 then return KEY_LEFT end
    elseif (target_dir == 1 or target_dir == 3) and math.abs(tx - sx) <= 1 then
        if target_dir == 3 and (py < 56 or py > 64) and px < 4 then
            return KEY_RIGHT
        elseif target_dir == 1 and (py < 56 or py > 64) and px > 140 then
            return KEY_LEFT
        end
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
-- RUN varies title-idle entropy. Confirm every champion at the same cartridge
-- loop counter: cursor redraws have class-dependent cost, so fixed host-frame
-- padding only looked fair while silently producing five different seeds.
-- BOOT_EXTRA narrows an entropy-dependent failure without touching cartridge
-- RNG or game state: it is literally extra title-idle time a player could wait.
for _ = 1, (120 + RUN * 37 + BOOT_EXTRA) do tick(0) end
tap(KEY_START)
for _ = 1, 40 do tick(0) end
local select_base = FC ~= 0 and read16(FC) or 0
for _ = 1, CLASS do
    tap(KEY_DOWN)
    for _ = 1, 12 do tick(0) end
end
if FC ~= 0 then
    local confirm_at = (select_base + 160) % 65536
    while read16(FC) ~= confirm_at do tick(0) end
else
    -- Compatibility fallback for an old linker map.
    for _ = 1, ((4 - CLASS) * 16) do tick(0) end
end
tap(KEY_A)
for _ = 1, 45 do tick(0) end

local frames, max_room, last_hp, damage_taken, giant_overlap_damage, min_hp = 0, 0, 0, 0, 0, 255
local min_giant_hp = 255
local boss_start_frame, boss_start_beaten = -1, 0
local boss_attempts, boss_attempt_frames, boss_clear_frames = 0, 0, 0
-- Semicolon-separated at CSV write time: one elapsed-frame value for every
-- actual stage-boss kill. Keeping it in the host observer gives balance
-- analysis per-encounter timing without changing cartridge RAM or pacing.
local boss_clear_durations = {}
local last_damage_source = 255 -- enemy id, 254=hazard, 253=unresolved hostile
local rooms_seen, last_room = 1, 0
local room_enter_frame = 0
local route_start_frame = 0
local last_px, last_py, still_frames = 255, 255, 0
local escape_timer, escape_dir, escape_index = 0, KEY_UP, 0
local shake_phase = 0
local towns_seen, town_rooms = 0, {}
local world_hops, last_world_key = 0, -1
local world_contact_hits = 0
local debug_shot_room = -1
local last_target_slot, last_target_hp = -1, 255
local no_damage_frames, flank_timer = 0, 0
local wall_follow_dir, wall_follow_min = 0, 0
local dodge_phase, dodge_dir, dodge_cooldown, dodge_count = 0, KEY_RIGHT, 0, 0
-- Once a feet box lands on spikes, keep one escape lane until it has truly
-- crossed a safe tile. Re-choosing every pixel can ping-pong on a wall seam.
local spike_escape_dir = 0
local last_active_charge = 0
local last_input_keys, b_uses = 0, 0
local purchases, last_coins = 0, 0
local shop_visits, visited_shop_rooms = 0, {}
local max_combat_frames, max_route_frames = 0, 0
local max_combat_room, max_combat_enemy, max_route_room = 0, 255, 0
while frames < LIMIT do
    local hp = PL ~= 0 and emu:read8(PL + 2) or 0
    local hp_max = PL ~= 0 and emu:read8(PL + 1) or 0
    local mp = PL ~= 0 and emu:read8(PL + 4) or 0
    local mp_max = PL ~= 0 and emu:read8(PL + 3) or 0
    local iframes = PL ~= 0 and emu:read8(PL + 15) or 0
    -- player_state_t: +18 active_item, +19 active_charge. Reading +18 made
    -- every class look permanently on cooldown and silently disabled all B
    -- abilities and Spirit Convergence in automated play.
    local active_charge = PL ~= 0 and emu:read8(PL + 19) or 0
    local coins = PL ~= 0 and (emu:read8(PL + 16) + emu:read8(PL + 17) * 256) or 0
    if frames > 0 and coins < last_coins then
        purchases = purchases + 1
        if DEBUG then debug_log(string.format("BOTBUY f=%d room=%d coins=%d->%d",
            frames, RS ~= 0 and emu:read8(RS + 1) or 0, last_coins, coins)) end
    end
    last_coins = coins
    -- Count accepted signature presses, not requested controller inputs.  The
    -- game owns the edge/cooldown/MP rules; this observer only sees whether a
    -- B-only press actually entered its 140-frame class cooldown.  A+B Spirit
    -- Convergence deliberately remains separate from this metric.
    if active_charge > 0 and last_active_charge == 0
        and (last_input_keys % 4) == KEY_B then
        b_uses = b_uses + 1
        if DEBUG then
            debug_log(string.format("BOTABILITY f=%d class=%d charge=%d uses=%d",
                frames, CLASS, active_charge, b_uses))
        end
    end
    last_active_charge = active_charge
    local room = RS ~= 0 and emu:read8(RS + 1) or 0
    local won = RS ~= 0 and emu:read8(RS + 10) or 0
    if frames == 0 then last_hp = hp end
    if hp < last_hp then
        local taken = last_hp - hp
        damage_taken = damage_taken + taken
        if RS ~= 0 and emu:read8(RS + 17) == 1 then
            world_contact_hits = world_contact_hits + taken
        end
        -- Read-only attribution: infer from the runtime state after the hit.
        -- This deliberately avoids cartridge instrumentation, whose extra
        -- instructions changed dense-frame pacing in endurance sampling.
        local hit_x = PL ~= 0 and emu:read8(PL + 9) or 0
        local hit_y = PL ~= 0 and emu:read8(PL + 11) or 0
        local tx = math.floor((hit_x + 8) / 8)
        local ty = math.floor((hit_y + 12) / 8)
        if TM ~= 0 and tx >= 0 and tx < 20 and ty >= 0 and ty < 17
            and emu:read8(TM + ty * 20 + tx) == 31 then
            last_damage_source = 254
        else
            local threat = enemy_target(hit_x, hit_y)
            last_damage_source = threat and threat.kind or 253
        end
        -- This does not guess the exact source of a mixed collision frame.
        -- It records the narrower, actionable fact that the player hurtbox
        -- overlapped a giant body when damage landed. That separates boss
        -- body-pinning from a pure projectile-spacing problem without any
        -- RAM writes or cartridge-side instrumentation.
        for i = 0, 31 do
            local p = EN + i * 28
            if emu:read8(p) == 2 and emu:read8(p + 1) % 2 == 1
                and emu:read8(p + 17) == 1
                and emu:read8(p + 20) % 2 == 1 then
                local ex, ey = emu:read8(p + 3), emu:read8(p + 7)
                if hit_x + 11 > ex and ex + 15 > hit_x + 5
                    and hit_y + 15 > ey and ey + 15 > hit_y + 9 then
                    giant_overlap_damage = giant_overlap_damage + taken
                    break
                end
            end
        end
        if DEBUG then
            debug_log(string.format(
                "BOTHIT f=%d room=%d hp=%d->%d src=%d pos=%d,%d ifr=%d",
                frames, room, last_hp, hp, last_damage_source, hit_x, hit_y, iframes))
        end
    end
    last_hp = hp
    if hp < min_hp then min_hp = hp end
    if room > max_room then max_room = room end
    if room ~= last_room then
        if DEBUG then debug_log(string.format("BOTROOM f=%d %d->%d entered=%d",
            frames, last_room, room, RS ~= 0 and emu:read8(RS + 6) or 255)) end
        rooms_seen, last_room, room_enter_frame = rooms_seen + 1, room, frames
        route_start_frame = frames
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
        world_contact_hits = 0
        wall_follow_dir, wall_follow_min = 0, 0
        dodge_phase, escape_timer = 0, 0
    end
    -- player.x/y are signed 16-bit pixels at offsets 9 and 11.
    local px, py = read_i16(PL + 9), read_i16(PL + 11)
    if dodge_cooldown > 0 then dodge_cooldown = dodge_cooldown - 1 end
    if px == last_px and py == last_py then still_frames = still_frames + 1
    else still_frames = 0 end
    last_px, last_py = px, py
    local shop_here = world_mode == 0 and room_has_shop_ware()
    if shop_here and not visited_shop_rooms[room] then
        visited_shop_rooms[room], shop_visits = true, shop_visits + 1
    end
    local target = enemy_target(px, py)
    -- Overworld encounters are optional traversal pressure. Follow the
    -- authored route while firing instead of treating every screen as a
    -- mandatory clear; dungeon combat remains fully engaged.
    local overworld_threat = world_mode == 1 and target or nil
    if world_mode == 1 then target = nil end
    if DEBUG and frames % 600 == 0 and RS ~= 0 then
        local portal_x, portal_y = -1, -1
        if TM ~= 0 then
            for ty = 1, 15 do
                for tx = 1, 18 do
                    if emu:read8(TM + ty * 20 + tx) == 34 then
                        portal_x, portal_y = tx, ty
                    end
                end
            end
        end
        debug_log(string.format(
            "BOTSTATE f=%d room=%d local=%d stage=%d sigils=%d pos=%d,%d target=%d portal=%d,%d",
            frames, room, room % 6, emu:read8(RS + 11), read16(RS + 23),
            px, py, target and target.kind or 255, portal_x, portal_y))
    end
    -- A boss fight is measured from the first real giant observation through
    -- its actual disappearance, not by room residency.  That excludes the
    -- sanctuary/door animation and records a death during an active boss as
    -- an attempt without pretending it was a clear.
    local bosses_now = RS ~= 0 and emu:read8(RS + 11) or 0
    if giant_active() then
        if boss_start_frame < 0 then
            boss_start_frame, boss_start_beaten = frames, bosses_now
        end
    elseif boss_start_frame >= 0 then
        local elapsed = frames - boss_start_frame
        boss_attempts = boss_attempts + 1
        boss_attempt_frames = boss_attempt_frames + elapsed
        if bosses_now > boss_start_beaten then
            boss_clear_frames = boss_clear_frames + elapsed
            table.insert(boss_clear_durations, elapsed)
        end
        boss_start_frame = -1
    end
    -- The cartridge switches to victory immediately on the final kill, before
    -- the entity sweep necessarily observes that giant as gone. Count that
    -- last encounter as a clear here rather than dropping it from the
    -- per-boss series (or later misclassifying it as a merely-lived attempt).
    if won ~= 0 and boss_start_frame >= 0 then
        local elapsed = frames - boss_start_frame
        boss_attempts = boss_attempts + 1
        boss_attempt_frames = boss_attempt_frames + elapsed
        boss_clear_frames = boss_clear_frames + elapsed
        table.insert(boss_clear_durations, elapsed)
        boss_start_frame = -1
    end
    -- Do this after boss telemetry: the kill frame can set victory before
    -- this observer would otherwise see the giant disappear.
    if hp == 0 or won ~= 0 then break end
    if target then
        if target.giant ~= 0 and target.hp < min_giant_hp then
            min_giant_hp = target.hp
        end
        if target.slot == last_target_slot and target.hp >= last_target_hp then
            no_damage_frames = no_damage_frames + 1
        else
            no_damage_frames = 0
        end
        last_target_slot, last_target_hp = target.slot, target.hp
    else
        last_target_slot, last_target_hp, no_damage_frames = -1, 255, 0
    end
    local loot = (not target and world_mode == 0) and pickup_target(px, py, hp, hp_max) or nil
    local shop = (not target and not loot and world_mode == 0)
        and shop_target(px, py, hp, hp_max, mp_max, coins) or nil
    local room_age = frames - room_enter_frame
    if world_mode == 0 and target and room_age > max_combat_frames then
        max_combat_frames = room_age
        max_combat_room, max_combat_enemy = room, target.kind
        route_start_frame = frames
    elseif world_mode == 0 and loot then
        route_start_frame = frames
    elseif world_mode == 0 and not target and not loot
        and frames - route_start_frame > max_route_frames then
        max_route_frames = frames - route_start_frame
        max_route_room = room
    end
    local keys
    local sigil_pixel_active = false
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
        local waiting_star = target.kind == 11 and target.state ~= 0
        -- Corvin/Picsean are ranged, and Vespine's Stinger is a 48px lunge.
        -- Giving the latter Wolfkin's adjacent-only target lane stranded the
        -- controller against Flutterbat-room cover while it fired from safely
        -- out of range. Six tiles matches the real Stinger reach without
        -- changing the cartridge's collision or projectile physics.
        local routed_reach = (CLASS == 2 or CLASS == 3 or CLASS == 4) and 6 or 1
        -- Any weapon can spend shots into cover. After four seconds without
        -- changing target HP, reposition perpendicular and reacquire.
        -- Folding Stars are intentionally invulnerable while expanded. Route
        -- around their echoes without filling the entity pool with doomed shots;
        -- resume attacks as soon as the bright contracted core returns.
        if waiting_star then
            -- Still path around cover toward a cardinal firing lane. Pure
            -- orbiting can pin a ranged vessel against the outer wall while
            -- every brief vulnerable window opens behind a pillar.
            keys = target_step(px, py, target.x, target.y, move)
            no_damage_frames = 0
        elseif target.kind == 12 then
            -- A Flutterbat may share the agent's nominal 8px tile while
            -- remaining several pixels diagonal from its cardinal shot lane.
            -- Do pixel alignment here, rather than the generic no-damage
            -- flank route: that route sees the shared tile as already solved
            -- and repeatedly fires past the bat forever.
            keys = KEY_A + target_step(px, py, target.x, target.y, aim, routed_reach)
        elseif target.kind == 13 and math.abs(dx) <= 24 and math.abs(dy) <= 24 then
            -- Gloom Leeches can cling to the top or side wall while their
            -- 8px body is a couple of pixels off the champion's cardinal
            -- firing line.  At that range a generic Stinger retreat can
            -- repeatedly skim the edge forever. Align tightly first, then
            -- fire; an actually attached Leech still triggers the dash-shake
            -- override later in this controller frame.
            if CLASS == 4 and active_charge == 0 and mp >= 2 then
                -- Vespine's real B fan is the intended close-range answer:
                -- it clears a wall-clinging Leech before a careful A-only
                -- alignment turns the encounter into attrition before the
                -- first colossus.
                keys = KEY_B + aim
            elseif math.abs(dx) >= math.abs(dy) and math.abs(dy) > 1 then
                keys = dy > 0 and KEY_DOWN or KEY_UP
            elseif math.abs(dy) > math.abs(dx) and math.abs(dx) > 1 then
                keys = dx > 0 and KEY_RIGHT or KEY_LEFT
            else
                keys = KEY_A + aim
            end
        elseif target.kind == 10 then
            -- Sentries do not chase. The generic ranged orbit therefore
            -- keeps a champion circling the same blocked corner forever
            -- while the turret remains on the other side of cover. Route to
            -- a real cardinal shot lane, then hold it at a six-tile safe
            -- standoff; this is exactly the lane-reading behavior the Frost
            -- hazard is intended to teach a player.
            local adx, ady = math.abs(dx), math.abs(dy)
            local reach = (adx > ady) and adx or ady
            local offaxis = (aim == KEY_UP or aim == KEY_DOWN) and adx or ady
            if reach <= 52 and offaxis <= 5 then
                keys = KEY_A + aim
            elseif reach <= 56 then
                -- `target_step` is deliberately tile-coarse. In the same
                -- 8px row it can validly return its fallback even though a
                -- 12px hero is still visibly off the turret's pixel firing
                -- lane. Finish that last perpendicular alignment here.
                if aim == KEY_LEFT or aim == KEY_RIGHT then
                    keys = dy > 0 and KEY_DOWN or KEY_UP
                else
                    keys = dx > 0 and KEY_RIGHT or KEY_LEFT
                end
            else
                keys = KEY_A + target_step(px, py, target.x, target.y, aim, 6)
            end
        elseif flank_timer > 0 then
            -- A blind perpendicular strafe can circle the outside of a
            -- U-shaped court forever. Reuse the collision-aware melee BFS to
            -- reach a clear one-tile firing lane through the actual opening.
            keys = target_step(px, py, target.x, target.y, aim, routed_reach) + KEY_A
            flank_timer = flank_timer - 1
        elseif no_damage_frames > 240 then
            flank_timer, no_damage_frames = 240, 0
            keys = target_step(px, py, target.x, target.y, aim, routed_reach) + KEY_A
        -- Sauran's Tail Spike and Vespine's Stinger are 48px lunges, not
        -- Wolfkin's adjacent claw. Treating all three as true melee walked
        -- these kits into contact damage and understated them. Hold a clear
        -- firing lane, dart back only when crowded, and fire the other beats.
        elseif target.kind == 1 then
            -- The Stone Sentinel is a 16px colossus. Treating its origin as
            -- an 8px crawler makes any class (especially the real-melee
            -- Wolfkin) stand inside the body while trying to fire. Keep one
            -- claw-length of cardinal space: the primary weapon can still
            -- connect, but contact damage cannot repeat through every
            -- iframe window.
            local adx, ady = math.abs(dx), math.abs(dy)
            local reach = (adx > ady) and adx or ady
            local offaxis = (aim == KEY_UP or aim == KEY_DOWN) and adx or ady
            local giant_mode = GIANT_POLICY
            if giant_mode == "classwise" then
                -- Wolfkin's Claw and Sauran's Tail Spike need a conservative
                -- pulse-fire lane. Vespine's longer Stinger is different:
                -- paired 18k-frame samples after the exact-Sigil route
                -- cleared 0/3 first bosses with pulses but two full bosses
                -- on the ordinary cardinal baseline, so preserve that real
                -- reach instead of making the agent retreat between every
                -- strike. Picsean's slow bubbles favor orbit-and-fire.
                giant_mode = (CLASS == 0 or CLASS == 1) and "pulse_fire"
                    or (CLASS == 3) and "orbit_fire" or "baseline"
            end
            if target.giant ~= 0 and giant_mode ~= "baseline" and reach < 36 then
                local retreat = (aim == KEY_UP and KEY_DOWN)
                    or (aim == KEY_DOWN and KEY_UP)
                    or (aim == KEY_LEFT and KEY_RIGHT) or KEY_LEFT
                local orbit = giant_orbit_step(px, py, aim, retreat)
                if giant_mode == "pulse_fire" then
                    -- One aimed beat, then four retreat beats: this is a
                    -- controller-realistic way for short-range champions to
                    -- keep pressure without turning every shot into another
                    -- pixel of contact.  It exists only for offline search.
                    keys = (frames % 5 == 0) and (KEY_A + aim) or retreat
                else
                    keys = (giant_mode == "orbit_fire" and frames % 3 == 0)
                        and (KEY_A + aim) or orbit
                end
            elseif reach < GIANT_RETREAT_RANGE then
                local retreat = (aim == KEY_UP and KEY_DOWN)
                    or (aim == KEY_DOWN and KEY_UP)
                    or (aim == KEY_LEFT and KEY_RIGHT) or KEY_LEFT
                keys = retreat
            elseif reach <= 48 and offaxis <= 5 then
                keys = KEY_A + aim
            else
                keys = KEY_A + target_step(px, py, target.x, target.y, aim, 5)
            end
        elseif CLASS == 1 or CLASS == 4 then
            local adx, ady = math.abs(dx), math.abs(dy)
            local reach = (adx > ady) and adx or ady
            local offaxis = (aim == KEY_UP or aim == KEY_DOWN) and adx or ady
            if reach <= 52 and offaxis > 5 then
                keys = target_step(px, py, target.x, target.y, aim)
            elseif reach <= 28 then
                local retreat = (aim == KEY_UP and KEY_DOWN)
                    or (aim == KEY_DOWN and KEY_UP)
                    or (aim == KEY_LEFT and KEY_RIGHT) or KEY_LEFT
                keys = (frames % 3 == 0) and retreat or (KEY_A + aim)
            elseif reach <= 52 then
                keys = KEY_A + aim
            else
                keys = KEY_A + target_step(px, py, target.x, target.y, aim)
            end
        -- Wolfkin's Claw is the roster's true melee weapon. It must close and
        -- align instead of orbiting outside its adjacent swing geometry.
        elseif CLASS == 0 then
            -- Tile BFS gets us around cover; at striking distance, finish the
            -- last few pixels of perpendicular alignment before attacking.
            -- Small enemy hurtboxes make a same-tile diagonal slash miss even
            -- though both sprites appear adjacent.
            if math.abs(dx) <= 24 and math.abs(dy) <= 24 then
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
            -- Ranged shots are cardinal. At close diagonal range, first step
            -- onto the target's row/column; otherwise a vessel can orbit a
            -- large boss forever while every shot passes its corner.
            if math.abs(dx) <= 32 and math.abs(dy) <= 32
                and ((aim == KEY_UP or aim == KEY_DOWN) and math.abs(dx) > 5) then
                keys = dx > 0 and KEY_RIGHT or KEY_LEFT
            elseif math.abs(dx) <= 32 and math.abs(dy) <= 32
                and ((aim == KEY_LEFT or aim == KEY_RIGHT) and math.abs(dy) > 5) then
                keys = dy > 0 and KEY_DOWN or KEY_UP
            else
                -- Separate firing and movement frames. Holding perpendicular
                -- directions together aimed diagonal shots past cardinal targets.
                keys = (frames % 3 == 0) and move or (KEY_A + aim)
            end
        end
        -- Exercise the actual class kit. Signatures require a clean B edge
        -- WITHOUT A; the old A+B chord was rejected by room.c and meant the
        -- agent never raised Sauran's shield or fired the ranged signatures.
        local signature_period = (CLASS == 3) and 90 or (CLASS == 4) and 120 or 180
        local nearby_hostiles = hostile_count_near(px, py, 32)
        -- Stoneskin is a reactive guard, not a generic damage signature.
        -- Spending it on a global cadence (including the opening room) left
        -- the tank without its defining answer when a miniboss volley began.
        -- Howl is a melee ring, so a distant every-three-second timer was
        -- effectively never exercised in short Wolfkin fights.  Take its
        -- controller-realistic opportunity when two bodies crowd the hero or
        -- a boss is actually within the ring's useful 48px range.
        if ABILITY_POLICY == "smart" and CLASS == 0 and not waiting_star
            and active_charge == 0 and mp >= 2
            and (nearby_hostiles >= 2
                or (target.giant ~= 0 and math.max(math.abs(dx), math.abs(dy)) <= 48)) then
            keys = KEY_B + aim
        elseif ABILITY_POLICY == "smart" and CLASS ~= 1 and target.kind ~= 10
            and not waiting_star
            and active_charge == 0 and mp >= 2
            and frames % signature_period == 0 then
            keys = KEY_B + aim
        -- Spirit Convergence requires A and B to become pressed together.
        -- Release both on the preceding frame so the next chord has two edges.
        elseif ABILITY_POLICY == "smart" and not waiting_star and active_charge == 0
            and mp == mp_max and frames % 600 == 599 then
            keys = 0
        elseif ABILITY_POLICY == "smart" and not waiting_star and active_charge == 0
            and mp == mp_max and frames % 600 == 0 then
            keys = KEY_A + KEY_B + aim
        end
    elseif shop then
        local dx, dy = shop.x - px, shop.y - py
        local direct
        if math.abs(dx) > math.abs(dy) then
            direct = dx > 0 and KEY_RIGHT or KEY_LEFT
        else
            direct = dy > 0 and KEY_DOWN or KEY_UP
        end
        keys = target_step(px, py, shop.x, shop.y, direct, 0)
    elseif loot then
        local dx, dy = loot.x - px, loot.y - py
        local direct = math.abs(dx) > math.abs(dy)
            and (dx > 0 and KEY_RIGHT or KEY_LEFT)
            or (dy > 0 and KEY_DOWN or KEY_UP)
        -- Persistent objectives (notably the Rift Sigil) do not magnetize.
        -- A direct D-pad line can press into a pillar forever, so route the
        -- full champion body to the pickup's tile before its normal contact
        -- box finishes collection.
        -- Sigils are hard gates, so every stage deserves the same exact
        -- feet-box route.  A seed-2 Vespine run exposed the old stage-8-only
        -- exception: a visible early Sigil behind procgen cover could make a
        -- coarse tile plan loop forever around its real collision footprint.
        -- This remains pure controller input; it merely gives the agent the
        -- same body-valid path a player has to the required fixture.
        if loot.kind == 11 then
            keys = sigil_pixel_step(room, px, py, loot.x, loot.y)
            if keys ~= nil then sigil_pixel_active = true
            else keys = target_step(px, py, loot.x, loot.y, direct, 0) end
        else
            keys = target_step(px, py, loot.x, loot.y, direct, 0)
        end
    else
        keys = door_step(px, py) + KEY_A
    end
    -- Riftwild rooms are traversal pressure, not mandatory combat clears.
    -- Still, marching through a Hornet's body until the next doorway is not
    -- meaningful route play. Briefly step away from nearby bodies while
    -- keeping A held, then resume the authored gate route next beat.
    local world_flee = 0
    if overworld_threat then
        local dx, dy = overworld_threat.x - px, overworld_threat.y - py
        -- Optional Riftwild fights are never worth a trade. Keep a wide
        -- body-and-projectile buffer at every health level, then resume the
        -- authored exit route as soon as the nearby threat is behind us.
        local flee_radius = 56
        if math.max(math.abs(dx), math.abs(dy)) < flee_radius then
            local flee
            -- If the next authored exit is physically open, taking it beats
            -- a local sidestep: a monster behind the hero cannot keep dealing
            -- contact damage across a screen boundary. This preserves the
            -- public graph rather than inventing an evasive shortcut.
            local wanted = WORLD_ROUTE[world_screen + 1]
            local forward = wanted and CARD_KEYS[wanted + 1] or 0
            if forward ~= 0 and can_step(px, py, forward) then
                flee = forward
            end
            if flee == nil and math.abs(dx) >= math.abs(dy) then
                flee = dx >= 0 and KEY_LEFT or KEY_RIGHT
            elseif flee == nil then
                flee = dy >= 0 and KEY_UP or KEY_DOWN
            end
            if not can_step(px, py, flee) then
                local alternatives = {KEY_UP, KEY_RIGHT, KEY_DOWN, KEY_LEFT}
                for _, candidate in ipairs(alternatives) do
                    if can_step(px, py, candidate) then
                        flee = candidate
                        break
                    end
                end
            end
            if can_step(px, py, flee) then world_flee = flee end
        end
    end
    -- The tile path can point through a locally blocked feet-box state near a
    -- pillar corner. After the stall threshold, follow that solid edge for at
    -- least one body width and until the planned cardinal is truly open, then
    -- return to BFS.
    if not target and not loot and not shop and world_mode == 0
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
    local stuck_limit = (not target and not loot and not shop) and 60 or 20
    if escape_timer == 0 and still_frames > stuck_limit then
        -- A wall pocket can block the intended direction AND both
        -- perpendiculars. Cycle all four cardinals across recovery attempts
        -- so the agent eventually backs out instead of oscillating forever.
        if not target and not loot and not shop then
            local route_escape_dirs = {
                KEY_RIGHT + KEY_DOWN, KEY_LEFT + KEY_DOWN,
                KEY_LEFT + KEY_UP, KEY_RIGHT + KEY_UP,
                KEY_RIGHT, KEY_DOWN, KEY_LEFT, KEY_UP,
            }
            escape_index = (escape_index % 8) + 1
            escape_dir = route_escape_dirs[escape_index]
            escape_timer = 60
        else
            local combat_escape_dirs = {KEY_RIGHT, KEY_DOWN, KEY_LEFT, KEY_UP}
            escape_index = (escape_index % 4) + 1
            escape_dir = combat_escape_dirs[escape_index]
            escape_timer = 30
        end
        still_frames = 0
    end
    if escape_timer > 0 then
        keys = escape_dir + KEY_A
        escape_timer = escape_timer - 1
    end
    -- Proactively use the public dodge-dash against nearby hostile bullets.
    -- This is still controller-only: read instrumentation chooses an escape
    -- direction, then performs the same press/release/double-tap as a player.
    -- Once a Sentry is selected, commit to the BFS-selected lane instead of
    -- letting each of its telegraphed crossfire shots restart the route. Its
    -- low damage and long cadence make this an honest controller trade: the
    -- pilot may still take a hit, but it can now demonstrate whether the
    -- hazard is killable rather than endlessly dodging at the room's edge.
    local threat = nil
    if not target or target.kind ~= 10 then
        threat = projectile_threat(px, py)
    end
    -- Picsean's Tidal Wave grants a brief body-blocking Undertow guard. In
    -- Riftwild, encounters are optional and the route can narrow to a single
    -- exit lane, so use that real B ability to cross a nearby body instead of
    -- repeatedly trying to sidestep into a wall. This is not a game-state
    -- edit: it is the same two-MP button press available to a player.
    local world_body_close = overworld_threat
        and math.max(math.abs(overworld_threat.x - px),
            math.abs(overworld_threat.y - py)) <= 32
    -- Sauran's class answer is its projectile-breaking B shield. At full
    -- simulation speed, repeatedly dashing around optional Riftwild shots
    -- could pull the slower vessel off its authored route for an entire run.
    -- Use the actual shield edge instead; its cooldown prevents spam.
    -- Tidal Wave is valuable on the trail, but a stationary cast after two
    -- real hits on one screen lets an optional body pin the pilot regardless
    -- of whether the local path tile happens to be grass or stone. Preserve
    -- the authored exit input for that observed emergency; this is controller
    -- policy, never a ROM immunity or entity mutation.
    local world_guard_requested = false
    if ABILITY_POLICY == "smart" and CLASS == 3 and world_body_close
        and world_contact_hits < 2
        and active_charge == 0 and mp >= 2 then
        keys = KEY_B
        world_guard_requested = true
        dodge_phase, dodge_cooldown = 0, 30
    elseif ABILITY_POLICY == "smart" and (CLASS == 1 or CLASS == 3)
        and threat and active_charge == 0 and mp >= 2 then
        keys = KEY_B
        dodge_phase, dodge_cooldown = 0, 30
    elseif dodge_phase == 0 and dodge_cooldown == 0 and threat then
        local dx, dy = px - threat.x, py - threat.y
        if math.abs(dx) >= math.abs(dy) then
            dodge_dir = dx >= 0 and KEY_RIGHT or KEY_LEFT
            if not can_step(px, py, dodge_dir) then
                dodge_dir = can_step(px, py, KEY_UP) and KEY_UP or KEY_DOWN
            end
        else
            dodge_dir = dy >= 0 and KEY_DOWN or KEY_UP
            if not can_step(px, py, dodge_dir) then
                dodge_dir = can_step(px, py, KEY_LEFT) and KEY_LEFT or KEY_RIGHT
            end
        end
        dodge_phase, dodge_count = 1, dodge_count + 1
        if DEBUG then
            debug_log(string.format(
                "BOTDODGE f=%d room=%d pos=%d,%d shot=%d,%d target=%s dir=%02X",
                frames, room, px, py, threat.x, threat.y,
                target and string.format("%d@%d,%d", target.kind, target.x, target.y)
                    or "-", dodge_dir))
        end
    end
    -- The CGB loop may poll once across two emulator frames. Hold every beat
    -- for two frames so neither press edge can fall between cartridge polls.
    if dodge_phase == 1 then keys, dodge_phase = dodge_dir, 2
    elseif dodge_phase == 2 then keys, dodge_phase = dodge_dir, 3
    elseif dodge_phase == 3 then keys, dodge_phase = 0, 4
    elseif dodge_phase == 4 then keys, dodge_phase = 0, 5
    elseif dodge_phase == 5 then keys, dodge_phase = dodge_dir, 6
    elseif dodge_phase == 6 then keys, dodge_phase = dodge_dir, 7
    elseif dodge_phase == 7 then keys, dodge_phase = 0, 8
    elseif dodge_phase == 8 then
        keys, dodge_phase, dodge_cooldown = 0, 0, 60
    end
    -- Gloom Leeches are intentionally shaken loose by a double-tap dash.
    -- Exercise that public controller mechanic instead of letting a latched
    -- enemy bias melee samples when its body overlaps nearby terrain.
    if leech_attached() or shake_phase ~= 0 then
        if shake_phase == 0 then keys, shake_phase = KEY_RIGHT, 1
        elseif shake_phase == 1 then keys, shake_phase = KEY_RIGHT, 2
        elseif shake_phase == 2 then keys, shake_phase = 0, 3
        elseif shake_phase == 3 then keys, shake_phase = 0, 4
        elseif shake_phase == 4 then keys, shake_phase = KEY_RIGHT, 5
        elseif shake_phase == 5 then keys, shake_phase = KEY_RIGHT, 6
        elseif shake_phase == 6 then keys, shake_phase = 0, 7
        else keys, shake_phase = 0, 0
        end
    end
    -- Generic unstick/dodge recovery is useful in a sealed dungeon room, but
    -- must not erase a real Riftwild body-avoidance decision. Reapply the
    -- collision-checked flee step immediately before the world-edge guard.
    if world_flee ~= 0 and not world_guard_requested then keys = world_flee + KEY_A end
    -- A dodge may override door_step for several frames. Keep it from
    -- carrying the agent through a non-route Riftwild boundary and undoing
    -- an entire authored graph hop; preserve A/B while steering inward.
    if world_mode == 1 then
        local wanted = WORLD_ROUTE[world_screen + 1]
        local actions = keys % 16
        -- An enemy can pin the hero toward a non-route boundary. Let the
        -- evasive sidestep use the last safe body-width near that edge, then
        -- turn inward before it accidentally crosses into another world cell.
        local near_guard = world_flee ~= 0 and 4 or 32
        local vertical_guard = world_flee ~= 0 and 116 or 88
        local horizontal_guard = world_flee ~= 0 and 140 or 112
        if wanted ~= 0 and py < near_guard and math.floor(keys / KEY_UP) % 2 == 1 then
            keys = actions + KEY_DOWN
        elseif wanted ~= 2 and py > vertical_guard and math.floor(keys / KEY_DOWN) % 2 == 1 then
            keys = actions + KEY_UP
        elseif wanted ~= 3 and px < near_guard and math.floor(keys / KEY_LEFT) % 2 == 1 then
            keys = actions + KEY_RIGHT
        elseif wanted ~= 1 and px > horizontal_guard and math.floor(keys / KEY_RIGHT) % 2 == 1 then
            keys = actions + KEY_LEFT
        end
    end
    -- A dungeon arrival places the hero beside the return door. A recovery
    -- nudge can otherwise cross that edge while pursuing a hostile, a sigil,
    -- or shop stock, sending the controller back into a just-cleared
    -- miniboss room instead of finishing the current objective. Keep it
    -- inward only at that arrival lip; ordinary forward doors stay available.
    if (target or loot or shop) and world_mode == 0 then
        local entered = emu:read8(RS + 6)
        local actions = keys % 16
        if entered == 0 and py > 108 and math.floor(keys / KEY_DOWN) % 2 == 1 then
            keys = actions + KEY_UP
        elseif entered == 2 and py < 12 and math.floor(keys / KEY_UP) % 2 == 1 then
            keys = actions + KEY_DOWN
        elseif entered == 1 and px < 12 and math.floor(keys / KEY_LEFT) % 2 == 1 then
            keys = actions + KEY_RIGHT
        elseif entered == 3 and px > 128 and math.floor(keys / KEY_RIGHT) % 2 == 1 then
            keys = actions + KEY_LEFT
        end
    end
    -- Direct combat, dodge, and dash inputs do not all travel through the
    -- tile BFS. Keep those tactical overrides from newly entering the exact
    -- feet-center spike tile the cartridge itself damages. If the body is
    -- already on a hazard, temporarily keep moving toward a safe full-body
    -- position instead of suppressing the escape input.
    if not sigil_pixel_active and body_on_spike(px, py) then
        local spike_keys = {KEY_UP, KEY_RIGHT, KEY_DOWN, KEY_LEFT}
        if DEBUG then
            local candidates = {}
            for _, candidate in ipairs(spike_keys) do
                local dx = candidate == KEY_RIGHT and 8
                    or candidate == KEY_LEFT and -8 or 0
                local dy = candidate == KEY_DOWN and 8
                    or candidate == KEY_UP and -8 or 0
                local nx, ny = px + dx, py + dy
                candidates[#candidates + 1] = string.format("%02X:%d/%d",
                    candidate, can_step(px, py, candidate) and 1 or 0,
                    body_on_spike(nx, ny) and 1 or 0)
            end
            debug_log(string.format("BOTSPIKE f=%d room=%d pos=%d,%d cand=%s",
                frames, room, px, py, table.concat(candidates, ",")))
        end
        local function clears_spike_lane(key)
            local sx, sy = px, py
            local dx = key == KEY_RIGHT and 1 or key == KEY_LEFT and -1 or 0
            local dy = key == KEY_DOWN and 1 or key == KEY_UP and -1 or 0
            local step
            for step = 1, 8 do
                if not can_step(sx, sy, key) then return false end
                sx, sy = sx + dx, sy + dy
            end
            return not body_on_spike(sx, sy)
        end
        if spike_escape_dir ~= 0 and can_step(px, py, spike_escape_dir) then
            -- A signature press can consume the D-pad edge on this frame.
            -- Standing on a hazard is the one case where movement must win
            -- outright; resume firing/casting only after the feet clear it.
            keys = spike_escape_dir
        else
            spike_escape_dir = 0
            for _, candidate in ipairs(spike_keys) do
                if clears_spike_lane(candidate) then
                    spike_escape_dir = candidate
                    keys = spike_escape_dir
                    break
                end
            end
            if spike_escape_dir == 0 then
                -- No complete eight-pixel lane is open. Keep a legal nudge
                -- rather than freezing on the damage tile; a later frame may
                -- open a lane as the nearest hostile moves.
                for _, candidate in ipairs(spike_keys) do
                    if can_step(px, py, candidate) then
                        keys = candidate
                        break
                    end
                end
            end
        end
    elseif not sigil_pixel_active then
        spike_escape_dir = 0
        if math.floor(keys / KEY_RIGHT) % 2 == 1
            and body_on_spike(px + 1, py) then keys = keys - KEY_RIGHT end
        if math.floor(keys / KEY_LEFT) % 2 == 1
            and body_on_spike(px - 1, py) then keys = keys - KEY_LEFT end
        if math.floor(keys / KEY_DOWN) % 2 == 1
            and body_on_spike(px, py + 1) then keys = keys - KEY_DOWN end
        if math.floor(keys / KEY_UP) % 2 == 1
            and body_on_spike(px, py - 1) then keys = keys - KEY_UP end
        -- A dash/recovery may hold a horizontal and vertical direction in the
        -- same game frame. The four checks above protect each cardinal step,
        -- but `(x+1,y+1)` can still land the feet center on a spike even when
        -- either axis alone is safe. Prefer the safe cardinal component; only
        -- cancel movement altogether when neither component clears the tile.
        local step_x = math.floor(keys / KEY_RIGHT) % 2 == 1 and 1
            or (math.floor(keys / KEY_LEFT) % 2 == 1 and -1 or 0)
        local step_y = math.floor(keys / KEY_DOWN) % 2 == 1 and 1
            or (math.floor(keys / KEY_UP) % 2 == 1 and -1 or 0)
        if step_x ~= 0 and step_y ~= 0 and body_on_spike(px + step_x, py + step_y) then
            if not body_on_spike(px + step_x, py) then
                keys = step_y > 0 and keys - KEY_DOWN or keys - KEY_UP
            elseif not body_on_spike(px, py + step_y) then
                keys = step_x > 0 and keys - KEY_RIGHT or keys - KEY_LEFT
            else
                keys = (step_x > 0 and keys - KEY_RIGHT or keys - KEY_LEFT)
                keys = (step_y > 0 and keys - KEY_DOWN or keys - KEY_UP)
            end
        end
    end
    -- This final override comes after generic bullet dodges and unsticks so a
    -- one-frame evasive input cannot erase the final boss's only safe route.
    -- It applies to this specific announced phase, never to ordinary bosses.
    local collapse_keys = void_safe_pocket_step(px, py, target)
    if collapse_keys ~= nil then keys = collapse_keys end
    if DEBUG and (frames % 600 == 0
        or (target and target.giant ~= 0 and frames % 60 == 0)) then
        -- World traversal deliberately clears `target` so combat does not
        -- become mandatory, but debug output still needs the nearest hostile
        -- to explain an overworld hit or an avoidance choice.
        local debug_target = target or overworld_threat
        debug_log(string.format("BOTDBG f=%d room=%d world=%d:%d hp=%d mp=%d ifr=%d charge=%d pos=%d:%02X,%d:%02X target=%s keys=%02X",
            frames, room, world_mode, world_screen, hp, mp, iframes, active_charge,
            px, emu:read8(PL + 10), py, emu:read8(PL + 12),
            debug_target and string.format("enemy:%d@%d,%d hp=%d state=%d clk=%d s6=%d",
                    debug_target.kind, debug_target.x, debug_target.y,
                    debug_target.hp, debug_target.state, debug_target.clock,
                    debug_target.state6)
                or (loot and string.format("loot:%d,%d", loot.x, loot.y)
                    or (shop and string.format("shop:%d,%d", shop.x, shop.y) or "door")), keys))
    end
    if DEBUG_SCREEN and debug_shot_room ~= room
        and frames - room_enter_frame > 3600 then
        emu:screenshot(string.format("%s-r%d.png", DEBUG_SCREEN, room))
        debug_shot_room = room
    end
    last_input_keys = keys
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
local death_source = min_hp == 0 and last_damage_source or 255
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
if boss_start_frame >= 0 then
    -- The run ended while a giant was still alive (normally player death or
    -- the configured frame ceiling). Keep its lived encounter time visible
    -- in attempts, but never call it a clear.
    boss_attempts = boss_attempts + 1
    boss_attempt_frames = boss_attempt_frames + (frames - boss_start_frame)
end
local boss_clear_series = table.concat(boss_clear_durations, ";")
if TRACE_OUT then
    if trace_count > 0 then
        trace_rows[#trace_rows + 1] = string.format("%d,%d", trace_count, trace_last)
    end
    local tf = io.open(TRACE_OUT, "w")
    if tf then
        tf:write("# quintra-input-trace-v1\n")
        tf:write(string.format("# outcome seed=%.0f room=%d clears=%d kills=%d bosses=%d hp=%d won=%d screen=%d frames=%d\n",
            seed, emu:read8(RS + 1), clears, kills, bosses, hp, won, ui_screen, trace_frames))
        for _, row in ipairs(trace_rows) do tf:write(row .. "\n") end
        tf:close()
    end
end
local f = io.open(OUT, "a")
if f then
    f:write(string.format("%d,%d,%.0f,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%s\n",
        RUN, CLASS, seed, frames, max_room, rooms_seen, clears, kills,
        bosses, damage_taken, giant_overlap_damage, min_hp, final_x, final_y, final_world, final_screen,
        frames - room_enter_frame, max_combat_frames, max_combat_room,
        max_combat_enemy, max_route_frames, max_route_room,
        hostiles, last_enemy, death_source, towns_seen, world_hops,
        won, ui_screen, dodge_count, shop_visits, purchases, enemy_mask, min_giant_hp, b_uses,
        boss_attempts, boss_attempt_frames, boss_clear_frames, boss_clear_series))
    f:close()
end
console:log(string.format("BALANCE class=%d frames=%d room=%d clears=%d kills=%d bosses=%d hp=%d",
    CLASS, frames, max_room, clears, kills, bosses, hp))
-- The Qt frontend exposes quit(), while mgba-headless deliberately has no
-- frontend object.  The latter exits naturally once this script returns and
-- is substantially faster for controller-only balance certification.
if emu.frontend and emu.frontend.quit then emu.frontend:quit() end
