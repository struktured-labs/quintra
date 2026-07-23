-- Read-only heuristic play agent for real-ROM balance sampling.
-- It never edits HP, entities, RNG, or progression: only controller input.

local KEY_A, KEY_B = 0x01, 0x02
KEY_SELECT = 0x04
local KEY_START = 0x08
local KEY_RIGHT, KEY_LEFT, KEY_UP, KEY_DOWN = 0x10, 0x20, 0x40, 0x80
local CARD_DX, CARD_DY = {0, 1, 0, -1}, {-1, 0, 1, 0}
local CARD_KEYS = {KEY_UP, KEY_RIGHT, KEY_DOWN, KEY_LEFT}
local VOID_SAFE_X, VOID_SAFE_Y = {20, 124, 20, 124}, {20, 20, 100, 100}
-- Per-screen shortest authored exit toward dungeon gate screen 6; 4 means
-- use the central staircase rather than a boundary door.
local WORLD_ROUTE = {1, 1, 2, 2, 1, 1, 4, 3, 1, 1, 0, 3, 1, 1, 0, 3}
local STAGE_START = {0, 10, 21, 34, 46, 59, 74, 88, 103}
local STAGE_BOSS = {9, 20, 32, 45, 58, 72, 87, 102, 118}

function dungeon_local(room, stage)
    local index = math.min(stage, 8) + 1
    return math.max(0, math.min(room - STAGE_START[index],
        STAGE_BOSS[index] - STAGE_START[index]))
end

function dungeon_size(stage)
    local index = math.min(stage, 8) + 1
    return STAGE_BOSS[index] - STAGE_START[index] + 1
end

function dungeon_neighbor_local(cell, size, dir)
    local row, offset = math.floor(cell / 4), cell % 4
    local col = (row % 2 == 1) and (3 - offset) or offset
    if dir == 0 then row = row - 1
    elseif dir == 1 then col = col + 1
    elseif dir == 2 then row = row + 1
    elseif dir == 3 then col = col - 1 end
    if row < 0 or row > 3 or col < 0 or col > 3 then return nil end
    local next_cell = row * 4 + ((row % 2 == 1) and (3 - col) or col)
    return next_cell < size and next_cell or nil
end

function dungeon_route_dir(start, goal, size)
    if start == goal then return nil end
    local queue, head, seen, first = {start}, 1, {[start]=true}, {}
    while head <= #queue do
        local cell = queue[head]; head = head + 1
        for dir = 0, 3 do
            local next_cell = dungeon_neighbor_local(cell, size, dir)
            if next_cell ~= nil and not seen[next_cell] then
                seen[next_cell] = true
                first[next_cell] = (cell == start) and dir or first[cell]
                if next_cell == goal then return first[next_cell] end
                queue[#queue + 1] = next_cell
            end
        end
    end
    return nil
end

function is_town_room(room)
    return room == 33 or room == 73
end

local RS = tonumber(os.getenv("QUINTRA_RS_ADDR") or "0") or 0
local PL = tonumber(os.getenv("QUINTRA_PL_ADDR") or "0") or 0
local EN = tonumber(os.getenv("QUINTRA_EN_ADDR") or "0") or 0
local TM = tonumber(os.getenv("QUINTRA_TM_ADDR") or "0") or 0
local LS = tonumber(os.getenv("QUINTRA_SCREEN_ADDR") or "0") or 0
local FC = tonumber(os.getenv("QUINTRA_FRAME_ADDR") or "0") or 0
HITSTOP = tonumber(os.getenv("QUINTRA_HITSTOP_ADDR") or "0") or 0
-- A public cartridge flag: read it so the controller only retreats through
-- rooms the player is actually allowed to flee. It is never written.
SEALED = tonumber(os.getenv("QUINTRA_SEALED_ADDR") or "0") or 0
-- Puzzle rooms are controller objectives, not empty route stalls. Read their
-- public runtime role so the pilot can solve the visible cairn/rune/switch
-- fixtures through ordinary D-pad input. These addresses are never written.
PUZZLE_KIND = tonumber(os.getenv("QUINTRA_PUZZLE_KIND_ADDR") or "0") or 0
PUZZLE_LOCKED = tonumber(os.getenv("QUINTRA_PUZZLE_LOCKED_ADDR") or "0") or 0
local CLASS = tonumber(os.getenv("QUINTRA_BOT_CLASS") or "0") or 0
local RUN = tonumber(os.getenv("QUINTRA_BOT_RUN") or "0") or 0
local BOOT_EXTRA = tonumber(os.getenv("QUINTRA_BOT_BOOT_EXTRA") or "0") or 0
-- Normal remains the authored balance target. Specific reachability/fixture
-- diagnostics may opt into the cartridge's coarse tester assist so a harder
-- earlier boss cannot prevent them from ever reaching the system under test.
EASY = os.getenv("QUINTRA_BOT_EASY") == "1"
-- Optional exact run-init frame for replayable controller proof. This only
-- waits on the title/class-select screen and then presses the normal A button;
-- it never writes the game's RNG or run state. Without it, long-form balance
-- samples keep their intentional title-idle entropy.
local TARGET_FRAME = tonumber(os.getenv("QUINTRA_BOT_TARGET_FRAME") or "")
if TARGET_FRAME then TARGET_FRAME = TARGET_FRAME % 65536 end
-- Fixed-frame replay proofs must begin from cartridge state, not from an
-- assumed number of host frames spent drawing the first room. Visual-only
-- renderer changes can legitimately move that boundary by a frame or two.
-- The optional lower threshold remains a controller-policy experiment: it
-- only idles after room entry and never writes the hero's invulnerability.
READY_IFRAMES = tonumber(os.getenv("QUINTRA_BOT_READY_IFRAMES") or "56") or 56
if READY_IFRAMES < 0 then READY_IFRAMES = 0 end
if READY_IFRAMES > 60 then READY_IFRAMES = 60 end
local LIMIT = tonumber(os.getenv("QUINTRA_BOT_FRAMES") or "10800") or 10800
local OUT = os.getenv("QUINTRA_BOT_OUT") or "/tmp/quintra-balance.csv"
local DEBUG = os.getenv("QUINTRA_BOT_DEBUG") == "1"
local DEBUG_OUT = os.getenv("QUINTRA_BOT_DEBUG_OUT")
local DEBUG_SCREEN = os.getenv("QUINTRA_BOT_DEBUG_SCREEN")
local TRACE_OUT = os.getenv("QUINTRA_BOT_TRACE_OUT")
-- The input trace is exact but intentionally opaque (RLE button masks). The
-- optional observation trace is a compact, read-only state/action dataset for
-- controller review and future offline RL experiments. It samples each eight
-- emulated frames plus meaningful room/HP/target changes, avoiding an
-- unbounded per-frame log during long unattended endurance runs.
OBS_TRACE_OUT = os.getenv("QUINTRA_BOT_OBS_TRACE_OUT")
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
-- This is only the generic giant-range initializer. Wolfkin's authored
-- Fang-Stab branch below pins the pilot to a 24px giant buffer beneath the
-- cartridge's 64px physical lane; the ranged and
-- tank kits retain their distinct defaults. An explicit environment value
-- always wins for offline policy search.
local GIANT_RETREAT_RANGE_ENV = os.getenv("QUINTRA_BOT_GIANT_RETREAT_RANGE")
local GIANT_RETREAT_RANGE = tonumber(GIANT_RETREAT_RANGE_ENV
    or ((GIANT_POLICY == "classwise" and (CLASS == 0 or CLASS == 4))
        and (CLASS == 4 and "36" or "32") or "28")) or 28
if GIANT_RETREAT_RANGE < 16 then GIANT_RETREAT_RANGE = 16 end
if GIANT_RETREAT_RANGE > 56 then GIANT_RETREAT_RANGE = 56 end
-- Orbit-fire is deliberately not continuous point-blank DPS. Expose its
-- aimed beat cadence so offline controller research can compare pressure
-- against body-contact safety without changing combat code or save state.
local GIANT_FIRE_CADENCE = tonumber(os.getenv("QUINTRA_BOT_GIANT_FIRE_CADENCE")
    or "3") or 3
if GIANT_FIRE_CADENCE < 2 then GIANT_FIRE_CADENCE = 2 end
if GIANT_FIRE_CADENCE > 8 then GIANT_FIRE_CADENCE = 8 end
-- Optional research guard for a blind projectile dodge during a boss fight.
-- The normal dodge logic chooses the direction furthest from the incoming
-- shot, which can still step a short-range champion toward the Colossus.
-- Keep shipping behavior at zero; a matched policy trial may request a
-- minimum giant clearance and compare it without touching cartridge state.
local GIANT_DODGE_FLOOR = tonumber(os.getenv("QUINTRA_BOT_GIANT_DODGE_FLOOR")
    or "0") or 0
if GIANT_DODGE_FLOOR < 0 then GIANT_DODGE_FLOOR = 0 end
if GIANT_DODGE_FLOOR > 56 then GIANT_DODGE_FLOOR = 56 end
-- Keep the established controller behavior as the default, but expose an
-- explicit no-signature control.  This lets a balance experiment distinguish
-- the value of real B ability use from unrelated navigation/aim changes.
local ABILITY_POLICY = os.getenv("QUINTRA_BOT_ABILITY_POLICY") or "smart"
if ABILITY_POLICY ~= "off" and ABILITY_POLICY ~= "smart" then
    ABILITY_POLICY = "smart"
end
-- The legacy proximity detector treats any nearby, generally approaching
-- bullet as a dodge emergency. Collision prediction instead asks whether a
-- shot reaches the actual 6x6 hero hurtbox within eight frames. Wolfkin's
-- close physical lane needs the earlier proximity response against Frost's
-- slow dense rings, while Corvin/Picsean retain collision prediction; the
-- normal profile is deliberately class-specific rather than globally softer.
THREAT_POLICY = os.getenv("QUINTRA_BOT_THREAT_POLICY") or "adaptive"
if THREAT_POLICY ~= "proximity" and THREAT_POLICY ~= "collision"
    and THREAT_POLICY ~= "classwise" and THREAT_POLICY ~= "adaptive" then
    THREAT_POLICY = "adaptive"
end
-- Optional final-stage edge-recovery probe for controller research. It is
-- disabled in normal balance runs: the experiment only replaces a repeated
-- blocked route input with one ordinary inward D-pad press, never RAM state.
FINAL_EDGE_RECOVERY = os.getenv("QUINTRA_BOT_FINAL_EDGE_RECOVERY") == "1"
-- Close-range weapons need a separate body-safety rule from their generic
-- combat policy. Matched three-seed runs improved both Tail Spike and Stinger
-- routes at 16px with no combat or route stalls, so that is the controller
-- baseline. An environment override still permits a clean A/B comparison
-- without changing cartridge balance or conflating it with boss-orbit policy.
local LUNGE_PANIC_RANGE = tonumber(os.getenv("QUINTRA_BOT_LUNGE_PANIC_RANGE")
    or "16") or 16
if LUNGE_PANIC_RANGE < 0 then LUNGE_PANIC_RANGE = 0 end
if LUNGE_PANIC_RANGE > 24 then LUNGE_PANIC_RANGE = 24 end
-- Stoneskin is Sauran's authored answer to body contact as well as bullets,
-- but the established pilot only raised it for a projectile threat. Keep the
-- shipped policy at zero and expose a matched-seed research knob for a boss
-- entering a measured body-danger radius. This still sends only B through
-- the controller; it never alters the shield timer, HP, or entity state.
local SAURAN_BODY_SHIELD_RANGE = tonumber(os.getenv("QUINTRA_BOT_SAURAN_BODY_SHIELD_RANGE")
    or "0") or 0
if SAURAN_BODY_SHIELD_RANGE < 0 then SAURAN_BODY_SHIELD_RANGE = 0 end
if SAURAN_BODY_SHIELD_RANGE > 64 then SAURAN_BODY_SHIELD_RANGE = 64 end
-- Separate from body range: this measured cadence raises Sauran's real
-- projectile-breaking shield during an active giant fight. With Sauran's
-- collision-predicted dodge policy, the fixed deep route clears its second
-- giant at 60 frames. Longer 65--90 frame beats lose the same run during
-- that encounter; shorter 45--50 frame beats exhaust the guard timing in
-- the fourth giant. This remains ordinary B input, never a cartridge buff.
local SAURAN_GIANT_SHIELD_PERIOD = tonumber(os.getenv("QUINTRA_BOT_SAURAN_GIANT_SHIELD_PERIOD")
    or "60") or 0
if SAURAN_GIANT_SHIELD_PERIOD < 0 then SAURAN_GIANT_SHIELD_PERIOD = 0 end
if SAURAN_GIANT_SHIELD_PERIOD > 240 then SAURAN_GIANT_SHIELD_PERIOD = 240 end
-- Sauran's Tail Spike should reset out of an actual boss-body overlap before
-- relying on its timed Stoneskin. Expose the floor for matched controller
-- sweeps; this has no effect on cartridge movement, shielding, or damage.
SAURAN_GIANT_ESCAPE_RANGE = tonumber(os.getenv("QUINTRA_BOT_SAURAN_GIANT_ESCAPE_RANGE")
    or "20") or 20
if SAURAN_GIANT_ESCAPE_RANGE < 16 then SAURAN_GIANT_ESCAPE_RANGE = 16 end
if SAURAN_GIANT_ESCAPE_RANGE > 40 then SAURAN_GIANT_ESCAPE_RANGE = 40 end
-- At close range the Tail Spike pilot alternates a strike with a reset step.
-- Make that bounded beat explicit for matched-seed research: it is an input
-- policy only, never an attack-rate or invulnerability change in the ROM.
local SAURAN_GIANT_PULSE_PERIOD = tonumber(os.getenv("QUINTRA_BOT_SAURAN_GIANT_PULSE_PERIOD")
    or "2") or 2
if SAURAN_GIANT_PULSE_PERIOD < 2 then SAURAN_GIANT_PULSE_PERIOD = 2 end
if SAURAN_GIANT_PULSE_PERIOD > 8 then SAURAN_GIANT_PULSE_PERIOD = 8 end
-- Picsean's Undertow guard is a controller-search parameter, not an enemy or
-- player stat. Keep it bounded around the visible 32px giant body so sampled
-- policies cannot turn a normal ranged lane into blind full-room casting.
PICSEAN_GIANT_GUARD_RANGE = tonumber(os.getenv("QUINTRA_BOT_PICSEAN_GIANT_GUARD_RANGE")
    or "44") or 44
if PICSEAN_GIANT_GUARD_RANGE < 32 then PICSEAN_GIANT_GUARD_RANGE = 32 end
if PICSEAN_GIANT_GUARD_RANGE > 64 then PICSEAN_GIANT_GUARD_RANGE = 64 end
local trace_last, trace_count, trace_rows, trace_frames = nil, 0, {}, 0
obs_rows, obs_last_room, obs_last_hp, obs_last_kind, obs_last_slot = {}, -1, -1, -1, -1
obs_last_charge, obs_last_shield, obs_last_iframes, obs_last_weapon = -1, -1, -1, -1
obs_last_threat, obs_last_threat_eta = -1, -1
-- A+B is edge-triggered by the cartridge: both buttons must become newly
-- pressed in the same poll.  The pilot ordinarily holds A to attack, so keep
-- this tiny input-only release state outside the dense rollout loop.
local convergence_prime = 0
local enemy_mask, enemy_seen = 0, {}
-- Host-only accumulation: frames spent inside the giant's 32px safety
-- envelope.  It complements collision-confirmed giant_overlap_damage so a
-- controller experiment can distinguish "too close often" from "too close
-- and actually pinned" without consuming cartridge RAM.
enemy_seen.giant_close_frames = 0

function debug_log(line)
    console:log(line)
    if DEBUG_OUT then
        local df = io.open(DEBUG_OUT, "a")
        if df then df:write(line .. "\n"); df:close() end
    end
end

function tick(keys)
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

function observe_trace(frame, room, world_mode, world_screen, px, py,
    hp, hp_max, mp, mp_max, target, threat, keys, room_age,
    weapon, active_charge, shield_timer, iframes)
    if not OBS_TRACE_OUT then return end
    local kind = target and target.kind or 255
    local slot = target and target.slot or 255
    local projectile = quintra_nearest_hostile_projectile(px, py)
    -- Fixed-rate rows make frame-skip learning deterministic; state changes
    -- ensure a transition, weapon swap, cooldown edge, recovery window, or
    -- health loss is never hidden between beats. Timers are bucketed to the
    -- same eight-frame observation beat so their per-frame countdown cannot
    -- accidentally turn a long endurance trace into a raw frame dump.
    if frame % 8 ~= 0 and room == obs_last_room and hp == obs_last_hp
        and kind == obs_last_kind and slot == obs_last_slot
        and math.floor(active_charge / 8) == obs_last_charge
        and math.floor(shield_timer / 8) == obs_last_shield
        and math.floor(iframes / 8) == obs_last_iframes
        and weapon == obs_last_weapon
        and (threat and 1 or 0) == obs_last_threat
        and (threat and threat.hit_in or 255) == obs_last_threat_eta
        -- Preserve the short approach itself. A fast shot can be born and
        -- collide between ordinary eight-frame samples; once it is near the
        -- hero, each frame is useful diagnostic/RL state rather than noise.
        and (not projectile or projectile.d > 40) then return end
    obs_rows[#obs_rows + 1] = string.format(
        "%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d",
        frame, room, world_mode, world_screen, px, py, hp, hp_max, mp, mp_max,
        kind, target and target.hp or 255, target and target.x or 255,
        target and target.y or 255, target and target.giant or 0,
        target and target.pattern or 0, threat and 1 or 0,
        threat and threat.hit_in or 255, threat and threat.x or 255,
        threat and threat.y or 255, threat and threat.vx or 0,
        threat and threat.vy or 0,
        projectile and projectile.x or 255, projectile and projectile.y or 255,
        projectile and projectile.vx or 0, projectile and projectile.vy or 0,
        projectile and projectile.d or 255, keys,
        room_age, weapon, active_charge, shield_timer, iframes)
    obs_last_room, obs_last_hp, obs_last_kind, obs_last_slot = room, hp, kind, slot
    obs_last_charge = math.floor(active_charge / 8)
    obs_last_shield = math.floor(shield_timer / 8)
    obs_last_iframes = math.floor(iframes / 8)
    obs_last_weapon = weapon
    obs_last_threat = threat and 1 or 0
    obs_last_threat_eta = threat and threat.hit_in or 255
end

function tap(key)
    tick(key); tick(key); tick(0); tick(0)
end

function read16(address)
    return emu:read8(address) + emu:read8(address + 1) * 256
end

-- The stage objective is a real progression gate.  Reading it lets this
-- controller retrace to the Sigil room instead of grinding against the
-- sanctuary's intentionally locked forward door.  The offsets mirror
-- run_state_t: bosses_beaten at 11 and rift_sigils at 23.
function stage_sigil_missing()
    if RS == 0 then return false end
    local stage = emu:read8(RS + 11) % 9
    local bit = 2 ^ stage
    return math.floor(read16(RS + 23) / bit) % 2 == 0
end

-- The stage-one Warden is local room 3. Its clear is persisted in
-- run_state.dungeon_puzzles bit 3, the same public state used by the Compass
-- and sanctuary gate. This remains a read-only routing observation.
function stage_warden_missing()
    if RS == 0 then return false end
    return math.floor(emu:read8(RS + 27) / 8) % 2 == 0
end

-- Roomier layouts turn their already-authored back-half fixtures into route
-- objectives. Local 7 persists as the high puzzle bit; local 9's deep Warden
-- shares the otherwise-unused high bit of dungeon_phase.
function stage_waystone_missing()
    if RS == 0 then return false end
    local size = dungeon_size(emu:read8(RS + 11))
    return size >= 12 and math.floor(emu:read8(RS + 27) / 128) % 2 == 0
end

function stage_deep_warden_missing()
    if RS == 0 then return false end
    local size = dungeon_size(emu:read8(RS + 11))
    return size >= 14 and math.floor(emu:read8(RS + 28) / 128) % 2 == 0
end

function read_i16(address)
    local value = read16(address)
    return value >= 0x8000 and value - 0x10000 or value
end

function enemy_target(px, py, preferred_kind)
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
            if preferred_kind == nil or kind == preferred_kind then
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
    end
    return best
end

-- A class signature is not always a single-target attack.  The Wolfkin's
-- eight-way Howl is best spent into a crowd (or a boss at claw range), so the
-- observer needs a small, read-only local population count rather than waiting
-- for an arbitrary global timer to happen during a fight.
function hostile_count_near(px, py, radius)
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
function giant_active()
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

function leech_attached()
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

function projectile_threat(px, py)
    local best, bestd = nil, 33
    local collision_mode = THREAT_POLICY == "collision"
        or ((THREAT_POLICY == "adaptive" or THREAT_POLICY == "classwise")
            and (CLASS == 1 or CLASS == 2 or CLASS == 3))
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
            -- Match combat.c's hero hurtbox: x+5..x+11, y+9..y+15.
            -- Always retain the short collision forecast, even for the
            -- broad proximity selector: Picsean uses a near warning to
            -- raise Undertow, but should only spend a movement-dodge on a
            -- shot that actually intersects the hero's feet box.
            -- Projectiles advance before combat resolves, so inspect the
            -- same next-frame positions. Eight frames covers the full dash
            -- setup without reacting to distant fire forever.
            local hit_in = nil
            for step = 1, 8 do
                local bx, by = ex + vx * step, ey + vy * step
                if bx + 6 > px + 5 and bx < px + 11
                    and by + 6 > py + 9 and by < py + 15 then
                    hit_in = step
                    break
                end
            end
            if ((collision_mode and hit_in ~= nil)
                    or (not collision_mode and approaching))
                and d < bestd then
                best, bestd = {x=ex, y=ey, vx=vx, vy=vy, hit_in=hit_in}, d
            end
        end
    end
    return best
end

-- Keep raw hostile-projectile context alongside the policy's stricter
-- collision prediction. A nil `projectile_threat` can mean either that the
-- lane is genuinely safe or that the heuristic failed to classify a live
-- shot. This nearest sample makes the distinction visible in offline replay
-- and RL data without writing cartridge memory or changing controller input.
function quintra_nearest_hostile_projectile(px, py)
    local best, bestd = nil, 65535
    if EN == 0 then return nil end
    for i = 0, 31 do
        local p = EN + i * 28
        local flags = emu:read8(p + 1)
        if emu:read8(p) == 1 and flags % 2 == 1
            and math.floor(flags / 16) % 2 == 0 then
            local ex, ey = emu:read8(p + 3), emu:read8(p + 7)
            local vx, vy = emu:read8(p + 10), emu:read8(p + 11)
            local d = math.abs(ex - px) + math.abs(ey - py)
            if vx >= 128 then vx = vx - 256 end
            if vy >= 128 then vy = vy - 256 end
            if d < bestd then
                best, bestd = {x=ex, y=ey, vx=vx, vy=vy, d=d}, d
            end
        end
    end
    return best
end

-- Hearts, currency, passive relics, and MP are part of the run economy.
-- Weapon swaps remain outside the comparable class policy; shops are handled
-- separately below so purchases can be measured without treating wares as
-- free loot.
function pickup_target(px, py, hp, hp_max, hearts_only)
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
            and (not hearts_only or kind == 0)
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

-- A colossus reward is the guaranteed build step between boss rooms. Generic
-- loot routing may choose a nearer coin or heart and then immediately take
-- the newly unsealed door; make the observed boss orb an explicit priority so
-- the pilot proves that its recorded power curve was actually collected.
-- This reads the same public pickup state as normal loot routing and still
-- reaches it only through ordinary D-pad input.
function quintra_boss_relic_target()
    local p
    if EN == 0 or boss_relic_pending == 0 or boss_relic_slot == nil
        or boss_relic_slot < 0 then return nil end
    p = EN + boss_relic_slot * 28
    if emu:read8(p) ~= 3 or emu:read8(p + 1) % 2 == 0
        or emu:read8(p + 17) ~= 3 then return nil end
    return {x=emu:read8(p + 3), y=emu:read8(p + 7), kind=3}
end

-- Loose weapon orbs are an explicit build choice. The comparable class pilot
-- does not route toward them, but combat movement can still cross one. Report
-- that overlap to the final input stage so a fresh attack edge cannot
-- accidentally confirm a trade; navigation itself remains untouched.
function quintra_on_weapon_orb(px, py, margin)
    margin = margin or 0
    if EN == 0 then return false end
    for i = 0, 31 do
        local p = EN + i * 28
        if emu:read8(p) == 3 and emu:read8(p + 1) % 2 == 1
            and emu:read8(p + 17) == 5 then
            local ex, ey = emu:read8(p + 3), emu:read8(p + 7)
            -- Mirror aabb_overlap_player_wide(): player x+2..x+13,
            -- y+8..y+15 against the ordinary 6x6 weapon-orb box. Do not
            -- replace this with a symmetric radius—the feet anchor is why a
            -- player can validly confirm an orb that is mostly below-right.
            if px + 14 + margin > ex and ex + 6 + margin > px + 2
                and py + 16 + margin > ey and ey + 6 + margin > py + 8 then
                return true
            end
        end
    end
    return false
end

-- Village weapon shelves sell on contact, unlike loose A-confirmed orbs.
-- Return the shelf coordinates when a prospective feet box enters its
-- approach margin so generic diagonal/stuck recovery cannot silently choose
-- a different build while crossing the market.
function quintra_weapon_shop_overlap(px, py, margin)
    margin = margin or 0
    if EN == 0 then return nil end
    for i = 0, 31 do
        local p = EN + i * 28
        if emu:read8(p) == 3 and emu:read8(p + 1) % 2 == 1
            and emu:read8(p + 17) == 4 and emu:read8(p + 18) == 8 then
            local ex, ey = emu:read8(p + 3), emu:read8(p + 7)
            if px + 14 + margin > ex and ex + 6 + margin > px + 2
                and py + 16 + margin > ey and ey + 6 + margin > py + 8 then
                return ex, ey
            end
        end
    end
    return nil
end

-- Riftwild is intentionally not a loot-clear arena: ordinary drops there
-- would make controller telemetry depend on optional fights.  Its one
-- authored exception is the Riftwell, a visible once-per-region recovery
-- landmark.  Seeking it when a resource is genuinely missing exercises the
-- same walk-into interaction a player uses, rather than falsely treating
-- every post-boss crossing as a no-healing gauntlet.
function riftwell_target(px, py, hp, hp_max, mp, mp_max)
    local best, bestd = nil, 65535
    if EN == 0 or (hp >= hp_max and mp >= mp_max) then return nil end
    for i = 0, 31 do
        local p = EN + i * 28
        if emu:read8(p) == 3 and emu:read8(p + 1) % 2 == 1
            and emu:read8(p + 17) == 16 then
            local ex, ey = emu:read8(p + 3), emu:read8(p + 7)
            local d = math.abs(ex - px) + math.abs(ey - py)
            if ex <= 152 and ey <= 128 and d < bestd then
                best, bestd = {x=ex, y=ey, kind=16}, d
            end
        end
    end
    return best
end

-- Choose an affordable ware through the public walk-into purchase mechanic.
-- Missing health wins; otherwise prefer deterministic attack/max-HP upgrades
-- over the seeded general relic. This reads state to decide, but—as with aim
-- and routing—changes the cartridge only through controller input.
function shop_target(px, py, hp, hp_max, mp_max, coins)
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
                    -- The village Vampiric Sigil is a sustain build choice,
                    -- not decorative shop stock the controller always skips.
                    or (ware == 6 and hp + 2 < hp_max and 92)
                    or (ware == 6 and 82)
                    or (ware == 4 and mp_max < 20 and 85)
                    or (ware == 2 and hp_max < 16 and 80)
                    or (ware == 1 and 70) or -1
                local ex, ey = emu:read8(p + 3), emu:read8(p + 7)
                local d = math.abs(ex - px) + math.abs(ey - py)
                -- A score of -1 means "not part of this comparable build",
                -- not a weak preference. Letting it tie the initial sentinel
                -- made a full-health pilot auto-buy the nearest unselected
                -- shelf and then walk through the weapon counter.
                if score >= 0
                    and (score > best_score or (score == best_score and d < bestd)) then
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
function room_has_shop_ware()
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

function walkable(tile)
    -- Procgen temporarily uses bit 7 to mark the champion-reachable body
    -- component while placing enemies.  Cartridge collision and the authored
    -- terrain vocabulary concern the low seven bits; tolerate that private
    -- marker in a live observation too so a delayed/visible cleanup frame
    -- cannot invert the controller's navigation graph.
    tile = tile % 128
    return tile == 1 or tile == 3 or tile == 19 or tile == 20
        or tile == 23 or tile == 31 or tile == 33 or tile == 34
        or tile == 7 or (tile >= 9 and tile <= 18)
        -- Match room_tile_walkable() in the actual ROM: villages/Riftwild
        -- use the outdoor surfaces and 55..63 are traversable colossal
        -- projection art. Omitting the latter made the input agent believe
        -- the opening giant was an impassable wall while humans crossed it.
        or tile == 35 or tile == 36 or (tile >= 55 and tile <= 63)
        -- Seed-stable Riftwild flower patches are meadow floor.  The other
        -- landmark families (water, standing stones, and stumps) remain
        -- deliberately solid in both the cartridge and this input pilot.
        or tile == 96
end

-- Strategic routes avoid known floor hazards when a safe lane exists. Pixel
-- collision still treats spikes as physically walkable, so an emergency
-- dodge or a hero already standing on one can always escape.
function path_walkable(tile)
    return tile ~= 31 and walkable(tile)
end

function navigation_walkable(tile)
    return path_walkable(tile)
end

function body_walkable(cx, cy)
    if cx < 1 or cx > 19 or cy < 1 or cy > 16 then return false end
    return navigation_walkable(emu:read8(TM + (cy - 1) * 20 + (cx - 1)))
        and navigation_walkable(emu:read8(TM + (cy - 1) * 20 + cx))
        and navigation_walkable(emu:read8(TM + cy * 20 + (cx - 1)))
        and navigation_walkable(emu:read8(TM + cy * 20 + cx))
end

-- Headless mGBA can crash while taking a screenshot. For any controller
-- repro, a compact tile snapshot is more useful anyway: it records the actual
-- collision vocabulary the next policy must respect, without writing ROM/RAM
-- or requiring a frontend.
function debug_tilemap(frame, room, px, py, target)
    local rows = {}
    if not DEBUG or TM == 0 then return end
    for y = 0, 16 do
        local row = {}
        for x = 0, 19 do
            row[#row + 1] = string.format("%02X", emu:read8(TM + y * 20 + x))
        end
        rows[#rows + 1] = table.concat(row, "")
    end
    debug_log(string.format(
        "BOTTILES f=%d room=%d p=%d,%d cell=%d,%d target=%s map=%s",
        frame, room, px, py, math.floor((px + 8) / 8), math.floor((py + 12) / 8),
        target and string.format("%d@%d,%d cell=%d,%d", target.kind, target.x, target.y,
            math.floor((target.x + 4) / 8), math.floor((target.y + 4) / 8)) or "none",
        table.concat(rows, "/")))
end

function world_body_walkable(cx, cy)
    if cx < 1 or cx > 19 or cy < 1 or cy > 16 then return false end
    return walkable(emu:read8(TM + (cy - 1) * 20 + (cx - 1)))
        and walkable(emu:read8(TM + (cy - 1) * 20 + cx))
        and walkable(emu:read8(TM + cy * 20 + (cx - 1)))
        and walkable(emu:read8(TM + cy * 20 + cx))
end

-- Mirror room.c's feet-anchored collision box for one prospective pixel.
-- Tile BFS plans globally; this answers whether its immediate controller
-- input is physically possible from the body's current sub-tile offset.
function pixel_walkable(x, y)
    if x < 0 or x >= 160 or y < 0 or y >= 136 then return false end
    local tile = emu:read8(TM + math.floor(y / 8) * 20 + math.floor(x / 8))
    return walkable(tile)
end

function pixel_full_body_obstacle(x, y)
    if x < 0 or x >= 160 or y < 0 or y >= 136 then return true end
    local tile = emu:read8(TM + math.floor(y / 8) * 20 + math.floor(x / 8)) % 128
    return tile == 21 or tile == 25 or tile == 28 or tile == 29 or tile == 30
end

function can_step(px, py, key)
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
        -- Mirror room.c's vertical full-sprite rule for crates and small
        -- pillars. The earlier controller modeled only the feet box here,
        -- so its otherwise exact pixel BFS could repeatedly ask the hero to
        -- walk upward through the underside of a pillar—a move the cartridge
        -- correctly rejects.
        and (key == KEY_LEFT or key == KEY_RIGHT
            or (not pixel_full_body_obstacle(nx + 2, ny)
                and not pixel_full_body_obstacle(nx + 13, ny)
                and not pixel_full_body_obstacle(nx + 2, ny + 7)
                and not pixel_full_body_obstacle(nx + 13, ny + 7)))
end

-- A body-hit recovery is a full double-tap dash, not a single walking pixel.
-- Near a wall, the naive "away" direction can be legal for one frame yet
-- consume the whole dash into the boundary while a 32px giant keeps contact.
-- Score the complete eight-pixel lane and choose the legal endpoint furthest
-- from the live giant. This is still ordinary D-pad input; it only prevents
-- the controller from selecting a visibly doomed wall dash.
function quintra_giant_body_dash_dir(px, py, target, fallback)
    local best_key, best_clearance = fallback, -1
    for _, key in ipairs({fallback, KEY_UP, KEY_RIGHT, KEY_DOWN, KEY_LEFT}) do
        local dx = key == KEY_RIGHT and 1 or key == KEY_LEFT and -1 or 0
        local dy = key == KEY_DOWN and 1 or key == KEY_UP and -1 or 0
        local legal = true
        for step = 0, 7 do
            if not can_step(px + dx * step, py + dy * step, key) then
                legal = false
                break
            end
        end
        if legal then
            local clearance = math.max(math.abs(px + dx * 8 - target.x),
                math.abs(py + dy * 8 - target.y))
            if clearance > best_clearance then
                best_key, best_clearance = key, clearance
            end
        end
    end
    return best_key
end

-- Projectile dodges use the same ordinary eight-pixel double tap as a body
-- dash.  A one-pixel-legal UP at y=6 is not a real escape: the remaining
-- seven input beats run into the ceiling and leave the player in the shot
-- lane.  Keep this choice in one helper so every caller evaluates the whole
-- authored dash before committing it.
function quintra_projectile_dash_dir(px, py, shot_x, shot_y)
    local dx, dy = px - shot_x, py - shot_y
    local primary = math.abs(dx) >= math.abs(dy)
        and (dx >= 0 and KEY_RIGHT or KEY_LEFT)
        or (dy >= 0 and KEY_DOWN or KEY_UP)
    local candidates
    if primary == KEY_LEFT or primary == KEY_RIGHT then
        candidates = {primary, KEY_UP, KEY_DOWN,
            primary == KEY_LEFT and KEY_RIGHT or KEY_LEFT}
    else
        candidates = {primary, KEY_LEFT, KEY_RIGHT,
            primary == KEY_UP and KEY_DOWN or KEY_UP}
    end
    for _, key in ipairs(candidates) do
        local step_x = key == KEY_RIGHT and 1 or key == KEY_LEFT and -1 or 0
        local step_y = key == KEY_DOWN and 1 or key == KEY_UP and -1 or 0
        local legal = true
        for step = 0, 7 do
            if not can_step(px + step_x * step, py + step_y * step, key) then
                legal = false
                break
            end
        end
        if legal then return key end
    end
    -- A generated nook can make every complete dash illegal. Preserve the
    -- old immediate-step fallback so the pilot can still walk out instead of
    -- freezing and treating a collision corner as an impossible state.
    for _, key in ipairs(candidates) do
        if can_step(px, py, key) then return key end
    end
    return primary
end

-- Keep this helper outside the controller's large top-level loop: mGBA's Lua
-- has a strict local-variable limit for that loop, while the helper gets its
-- own small local scope.
function quintra_leech_shake_dir(px, py, cycle)
    local shake_dirs = {KEY_LEFT, KEY_UP, KEY_DOWN, KEY_RIGHT}
    local direction = shake_dirs[(cycle % #shake_dirs) + 1]
    for offset = 0, #shake_dirs - 1 do
        local candidate = shake_dirs[((cycle + offset) % #shake_dirs) + 1]
        if can_step(px, py, candidate) then
            return candidate
        end
    end
    return direction
end

function quintra_body_overlap_escape(px, py, ex, ey)
    local primary
    if math.abs(px - ex) >= math.abs(py - ey)
        and math.abs(px - ex) > 0 then
        primary = px >= ex and KEY_RIGHT or KEY_LEFT
    elseif math.abs(py - ey) > 0 then
        primary = py >= ey and KEY_DOWN or KEY_UP
    else
        -- Exact centers provide no geometric "away" vector. Bias toward the
        -- room interior, then try every other physical lane.
        primary = px < 72 and KEY_RIGHT or KEY_LEFT
    end
    local opposite = primary == KEY_LEFT and KEY_RIGHT
        or primary == KEY_RIGHT and KEY_LEFT
        or primary == KEY_UP and KEY_DOWN or KEY_UP
    local side_a = (primary == KEY_LEFT or primary == KEY_RIGHT)
        and (py < 60 and KEY_DOWN or KEY_UP)
        or (px < 72 and KEY_RIGHT or KEY_LEFT)
    local side_b = side_a == KEY_LEFT and KEY_RIGHT
        or side_a == KEY_RIGHT and KEY_LEFT
        or side_a == KEY_UP and KEY_DOWN or KEY_UP
    for _, direction in ipairs({primary, side_a, side_b, opposite}) do
        if can_step(px, py, direction) then return direction end
    end
    return primary
end

function tile_at_px(x, y)
    if x < 0 or x >= 160 or y < 0 or y >= 136 then return 0 end
    return emu:read8(TM + math.floor(y / 8) * 20 + math.floor(x / 8))
end

-- Player shots originate at +2 with a 7px hitbox. A direction that looks
-- cardinal from sprite origins can still start inside a wall seam (or sail
-- beside an 8px foe), so use the projectile's real centerline before asking
-- a short weapon to commit to a shot. Spikes are walkable hazard floor, not
-- projectile cover: body routing avoids them, but a bolt may correctly cross
-- a Toxic Mire pool to punish a mine planted inside it.
function projectile_lane_clear(px, py, ex, ey, aim)
    local sx, sy = px + 6, py + 6
    local gx, gy = ex + 4, ey + 4
    if aim == KEY_LEFT or aim == KEY_RIGHT then
        -- Most 8px enemy sprites deliberately use a 6x6 gameplay hitbox.
        -- Planning against the art's full eight pixels can approve a one-pixel
        -- "lane" where every 7px player shot misses the real body forever.
        if py + 9 <= ey or ey + 6 <= py + 2 then return false end
        local lo, hi = math.min(sx, gx), math.max(sx, gx)
        for x = lo, hi do
            if not walkable(tile_at_px(x, sy)) then return false end
        end
        return true
    end
    if px + 9 <= ex or ex + 6 <= px + 2 then return false end
    local lo, hi = math.min(sy, gy), math.max(sy, gy)
    for y = lo, hi do
        if not walkable(tile_at_px(sx, y)) then return false end
    end
    return true
end

function body_on_spike(px, py)
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
function sigil_pixel_step(room, px, py, ex, ey)
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
function giant_orbit_step(px, py, aim, retreat)
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

-- Fold Stars are hazardous even while another enemy sorts as the primary
-- target. Their expanded core is invulnerable and sheds echo pressure, so a
-- player controller needs to yield space before that core reaches contact
-- range, then may resume normal targeting for the contracted punish window.
function fold_star_guard(px, py)
    local star = enemy_target(px, py, 11)
    local range, aim, retreat
    if not star or star.state == 0 then return nil end
    range = math.max(math.abs(star.x - px), math.abs(star.y - py))
    if range >= 56 then return nil end
    if math.abs(star.x - px) >= math.abs(star.y - py) then
        aim = star.x > px and KEY_RIGHT or KEY_LEFT
    else
        aim = star.y > py and KEY_DOWN or KEY_UP
    end
    retreat = (aim == KEY_UP and KEY_DOWN)
        or (aim == KEY_DOWN and KEY_UP)
        or (aim == KEY_LEFT and KEY_RIGHT) or KEY_LEFT
    return giant_orbit_step(px, py, aim, retreat)
end

-- A flying enemy can occupy an isolated side of generated cover: there is no
-- body-valid route to its current tile, so a tile BFS correctly has no answer
-- but an aimed fallback would keep firing into the same wall. After the normal
-- no-damage watchdog has proved that this is not a brief alignment issue,
-- step sideways to expose a new cardinal lane. This remains ordinary D-pad
-- input and never assumes the enemy will stay at its sampled position.
function cover_recovery_step(px, py, aim, phase)
    local first, second, retreat
    if aim == KEY_UP or aim == KEY_DOWN then
        first = (phase % 2 == 0) and KEY_LEFT or KEY_RIGHT
        second = (first == KEY_LEFT) and KEY_RIGHT or KEY_LEFT
        retreat = (aim == KEY_UP) and KEY_DOWN or KEY_UP
    else
        first = (phase % 2 == 0) and KEY_UP or KEY_DOWN
        second = (first == KEY_UP) and KEY_DOWN or KEY_UP
        retreat = (aim == KEY_LEFT) and KEY_RIGHT or KEY_LEFT
    end
    if can_step(px, py, first) then return first end
    if can_step(px, py, second) then return second end
    if can_step(px, py, retreat) then return retreat end
    return aim
end

function direction_from_keys(keys)
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
function aligned_step(d, sx, sy, px, py, fallback)
    if not d then return fallback end
    if d == 1 or d == 3 then
        -- Direction indices are N/E/S/W, so vertical travel centers the
        -- horizontal body span before crossing a wall seam.
        local want_x = sx * 8 - 9
        if px < want_x - 1 then return KEY_RIGHT end
        if px > want_x + 1 then return KEY_LEFT end
    else
        -- Mirrored rule for east/west travel.
        local want_y = sy * 8 - 11
        if want_y < 0 then want_y = 0 elseif want_y > 120 then want_y = 120 end
        if py < want_y - 1 then return KEY_DOWN end
        if py > want_y + 1 then return KEY_UP end
    end
    return CARD_KEYS[d] or fallback
end

function clear_cardinal_lane(x, y, gx, gy)
    if x == gx then
        local lo, hi = math.min(y, gy) + 1, math.max(y, gy) - 1
        for ty = lo, hi do
            -- Spikes constrain feet routes, not a weapon's line of fire.
            if not walkable(emu:read8(TM + ty * 20 + x)) then return false end
        end
        return true
    end
    if y == gy then
        local lo, hi = math.min(x, gx) + 1, math.max(x, gx) - 1
        for tx = lo, hi do
            if not walkable(emu:read8(TM + y * 20 + tx)) then return false end
        end
        return true
    end
    return false
end

-- Controller-only melee pursuit around procgen cover. Ranged champions can
-- fire over a useful standoff distance, but short weapons must first route to
-- a body-valid cell near the target instead of clawing into the intervening
-- pillar forever.
function target_step(px, py, ex, ey, fallback, near_tiles)
    if TM == 0 then return fallback end
    local reach = near_tiles or 1
    local sx, sy = math.floor((px + 13) / 8), math.floor((py + 15) / 8)
    local gx, gy = math.floor((ex + 4) / 8), math.floor((ey + 4) / 8)
    local qx, qy, head, tail = {sx}, {sy}, 1, 1
    local seen, prev, prevkey = {}, {}, {}
    local start = sy * 20 + sx
    seen[start] = true
    local target, best, best_dist = nil, nil, 0x7FFF
    while head <= tail do
        local x, y = qx[head], qy[head]; head = head + 1
        -- A moving enemy can temporarily have no body-valid cardinal firing
        -- lane. Retain the closest reachable approach cell instead of
        -- discarding the entire BFS and blindly walking the fallback into a
        -- wall. The next frame recomputes against the enemy's live position.
        local dist = math.abs(x - gx) + math.abs(y - gy)
        if dist < best_dist then
            best, best_dist = y * 20 + x, dist
        end
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
    if not target then target = best end
    if not target or target == start then return fallback end
    while prev[target] and prev[target] ~= start do target = prev[target] end
    return aligned_step(prevkey[target], sx, sy, px, py, fallback)
end

-- Route the champion's real 12px feet box to one exact top-left coordinate.
-- Puzzle interactions care about a specific side of a cairn or the center of
-- a floor rune, so the combat helper's "any cardinal firing lane" endpoint is
-- intentionally too loose here.
local body_goal_pixel_route = nil
function exact_body_goal_step(px, py, goal_x, goal_y)
    local start = py * 160 + px
    local start_feet_tx = math.floor((px + 8) / 8)
    local start_feet_ty = math.floor((py + 12) / 8)
    if px == goal_x and py == goal_y then return 0 end
    if body_goal_pixel_route
        and body_goal_pixel_route.goal_x == goal_x
        and body_goal_pixel_route.goal_y == goal_y
        and body_goal_pixel_route.dirs[start] then
        return body_goal_pixel_route.dirs[start]
    end
    local qx, qy, head, tail = {px}, {py}, 1, 1
    local seen, previous, step = {[start] = true}, {}, {}
    local found = nil
    while head <= tail do
        local x, y = qx[head], qy[head]; head = head + 1
        local key = y * 160 + x
        if x == goal_x and y == goal_y then
            found = key
            break
        end
        for d = 1, 4 do
            local dir = CARD_KEYS[d]
            local nx, ny = x + CARD_DX[d], y + CARD_DY[d]
            local next_key = ny * 160 + nx
            local feet_tx = math.floor((nx + 8) / 8)
            local feet_ty = math.floor((ny + 12) / 8)
            local crosses_other_rune = tile_at_px(nx + 8, ny + 12) == 33
                and (feet_tx ~= start_feet_tx or feet_ty ~= start_feet_ty)
                and (math.abs(nx - goal_x) > 1 or math.abs(ny - goal_y) > 1)
            if nx >= 0 and nx <= 146 and ny >= 0 and ny <= 120
                and not seen[next_key] and can_step(x, y, dir)
                and not body_on_spike(nx, ny) and not crosses_other_rune then
                seen[next_key], previous[next_key], step[next_key] = true, key, dir
                tail = tail + 1
                qx[tail], qy[tail] = nx, ny
            end
        end
    end
    if not found then return nil end
    local dirs, node = {}, found
    while previous[node] do
        dirs[previous[node]] = step[node]
        node = previous[node]
    end
    body_goal_pixel_route = {goal_x=goal_x, goal_y=goal_y, dirs=dirs}
    return dirs[start]
end

function body_goal_step(px, py, goal_x, goal_y)
    if px == goal_x and py == goal_y then return 0 end
    -- Full-height scenery uses stricter upward/downward collision than the
    -- ordinary feet box. A tile-cell route can therefore oscillate forever
    -- beneath a pillar while trying to reach a rune. Prefer the same
    -- one-pixel physical search used for mandatory Sigils; retain the coarse
    -- fallback only for a malformed/unreachable fixture.
    local exact = exact_body_goal_step(px, py, goal_x, goal_y)
    if exact ~= nil then return exact end
    local sx, sy = math.floor((px + 13) / 8), math.floor((py + 15) / 8)
    local gx, gy = math.floor((goal_x + 13) / 8), math.floor((goal_y + 15) / 8)
    if sx == gx and sy == gy then
        local key = math.abs(px - goal_x) >= math.abs(py - goal_y)
            and (px < goal_x and KEY_RIGHT or KEY_LEFT)
            or (py < goal_y and KEY_DOWN or KEY_UP)
        if can_step(px, py, key) then return key end
        key = (key == KEY_LEFT or key == KEY_RIGHT)
            and (py < goal_y and KEY_DOWN or KEY_UP)
            or (px < goal_x and KEY_RIGHT or KEY_LEFT)
        return can_step(px, py, key) and key or 0
    end
    local qx, qy, head, tail = {sx}, {sy}, 1, 1
    local seen, prev, prevkey = {}, {}, {}
    local start = sy * 20 + sx
    local target = gy * 20 + gx
    seen[start] = true
    while head <= tail and not seen[target] do
        local x, y = qx[head], qy[head]
        head = head + 1
        for d = 1, 4 do
            local nx, ny = x + CARD_DX[d], y + CARD_DY[d]
            local nk = ny * 20 + nx
            if nx >= 1 and nx <= 19 and ny >= 1 and ny <= 16
                and not seen[nk] and body_walkable(nx, ny) then
                seen[nk], prev[nk], prevkey[nk] = true, y * 20 + x, d
                tail = tail + 1
                qx[tail], qy[tail] = nx, ny
            end
        end
    end
    if not seen[target] then
        local direct = math.abs(px - goal_x) >= math.abs(py - goal_y)
            and (px < goal_x and KEY_RIGHT or KEY_LEFT)
            or (py < goal_y and KEY_DOWN or KEY_UP)
        return can_step(px, py, direct) and direct or 0
    end
    while prev[target] and prev[target] ~= start do target = prev[target] end
    return aligned_step(prevkey[target], sx, sy, px, py, 0)
end

puzzle_policy_room = -1
puzzle_rune_index = 1
puzzle_rune_stepoff = false

function xor32(a, b)
    local value, bit = 0, 1
    a, b = a % 4294967296, b % 4294967296
    for _ = 1, 32 do
        local abit, bbit = a % 2, b % 2
        if abit ~= bbit then value = value + bit end
        a, b, bit = math.floor(a / 2), math.floor(b / 2), bit * 2
    end
    return value
end

function puzzle_run_seed(room)
    local seed = emu:read8(RS + 2)
        + emu:read8(RS + 3) * 256
        + emu:read8(RS + 4) * 65536
        + emu:read8(RS + 5) * 16777216
    local biome = emu:read8(RS)
    return xor32(xor32(seed, biome * 65536),
        (room * 0x9E3779B9) % 4294967296)
end

-- Solve every authored non-combat room from its visible fixture. The policy
-- has no puzzle-state shortcut: it walks to the cairn and pushes it, follows
-- the seed-stable three-rune order one tile at a time, and touches the phase
-- switch before advancing. Reading KIND/LOCKED merely distinguishes an
-- intentional puzzle from an empty cleared room.
function puzzle_controller_step(room, px, py, frame)
    if PUZZLE_KIND == 0 or PUZZLE_LOCKED == 0 then return nil end
    local kind = emu:read8(PUZZLE_KIND)
    local locked = emu:read8(PUZZLE_LOCKED)
    if kind == 0 then return nil end
    if room ~= puzzle_policy_room then
        puzzle_policy_room = room
        puzzle_rune_index = 1
        puzzle_rune_stepoff = false
    end
    if kind == 1 and locked ~= 0 then
        local bx, by = -1, -1
        for y = 1, 15 do
            for x = 1, 18 do
                if emu:read8(TM + y * 20 + x) == 25 then
                    bx, by = x, y
                    break
                end
            end
            if bx >= 0 then break end
        end
        if bx < 0 then return 0 end
        -- The 2x2 cairn's west face begins at bx*8. The hero's collision
        -- body extends through x+13 and the push probe sits at x+14, so the
        -- actual flush position is bx*8-14. Stopping two pixels earlier made
        -- the policy alternate right/left around its navigation waypoint
        -- instead of maintaining the ten consecutive contact frames.
        local goal_x, goal_y = bx * 8 - 14, by * 8 - 8
        if DEBUG and frame % 120 == 0 then
            debug_log(string.format(
                "BOTPUSH f=%d room=%d locked=%d block=%d,%d pos=%d:%02X,%d:%02X goal=%d,%d",
                frame, room, locked, bx, by, px, emu:read8(PL + 10),
                py, emu:read8(PL + 12), goal_x, goal_y))
        end
        if math.abs(px - goal_x) <= 1 and math.abs(py - goal_y) <= 1 then
            return KEY_RIGHT
        end
        return body_goal_step(px, py, goal_x, goal_y)
    elseif kind == 2 and locked ~= 0 then
        local orders = {
            {0, 1, 2}, {0, 2, 1}, {1, 0, 2},
            {1, 2, 0}, {2, 0, 1}, {2, 1, 0}
        }
        local rune_x, rune_y = {5, 10, 14}, {8, 5, 10}
        local order = orders[(math.floor(puzzle_run_seed(room) / 256) % 6) + 1]
        local rune = order[puzzle_rune_index] + 1
        local tx, ty = rune_x[rune], rune_y[rune]
        local goal_x = (puzzle_rune_stepoff and tx + 1 or tx) * 8 - 8
        local goal_y = ty * 8 - 12
        if DEBUG and frame % 120 == 0 then
            debug_log(string.format(
                "BOTRUNE f=%d room=%d index=%d step=%d rune=%d tile=%d pos=%d,%d goal=%d,%d",
                frame, room, puzzle_rune_index, puzzle_rune_stepoff and 1 or 0,
                rune, emu:read8(TM + ty * 20 + tx), px, py, goal_x, goal_y))
        end
        if not puzzle_rune_stepoff
            and emu:read8(TM + ty * 20 + tx) ~= 33 then
            puzzle_rune_stepoff = true
            goal_x = (tx + 1) * 8 - 8
        elseif puzzle_rune_stepoff
            and (math.floor((px + 8) / 8) ~= tx
                or math.floor((py + 12) / 8) ~= ty) then
            puzzle_rune_index = math.min(3, puzzle_rune_index + 1)
            puzzle_rune_stepoff = false
            rune = order[puzzle_rune_index] + 1
            tx, ty = rune_x[rune], rune_y[rune]
            goal_x, goal_y = tx * 8 - 8, ty * 8 - 12
        end
        return body_goal_step(px, py, goal_x, goal_y)
    elseif kind == 3 and emu:read8(RS + 28) == 0 then
        return body_goal_step(px, py, 10 * 8 - 8, 8 * 8 - 12)
    end
    return nil
end

-- A Mire Spore is a proximity mine, not a pursuer. Find a body-valid
-- cardinal firing lane while treating its 40px arming radius as forbidden
-- space. Seven tile cells give a small human-scale margin (56px) beyond that
-- radius; the projectile kits can still attack from there.
function spore_safe_step(px, py, ex, ey, fallback)
    if TM == 0 then return fallback end
    local sx, sy = math.floor((px + 13) / 8), math.floor((py + 15) / 8)
    local gx, gy = math.floor((ex + 4) / 8), math.floor((ey + 4) / 8)
    local qx, qy, head, tail = {sx}, {sy}, 1, 1
    local seen, prev, prevkey = {}, {}, {}
    local start, target = sy * 20 + sx, nil
    seen[start] = true
    while head <= tail do
        local x, y = qx[head], qy[head]; head = head + 1
        local dist = math.abs(x - gx) + math.abs(y - gy)
        if dist >= 7 and dist <= 15 and (x == gx or y == gy)
            and clear_cardinal_lane(x, y, gx, gy) then
            target = y * 20 + x
            break
        end
        for d = 1, 4 do
            local nx, ny = x + CARD_DX[d], y + CARD_DY[d]
            local nk = ny * 20 + nx
            local safe = math.abs(nx - gx) + math.abs(ny - gy) >= 6
            if nx >= 1 and nx <= 19 and ny >= 1 and ny <= 16
                and safe and not seen[nk] and body_walkable(nx, ny) then
                seen[nk], prev[nk], prevkey[nk] = true, y * 20 + x, d
                tail = tail + 1; qx[tail], qy[tail] = nx, ny
            end
        end
    end
    if not target or target == start then return fallback end
    while prev[target] and prev[target] ~= start do target = prev[target] end
    return aligned_step(prevkey[target], sx, sy, px, py, fallback)
end

-- Stationary Spores need the same exact feet-box route used for a Rift Sigil.
-- A tile row is not automatically a projectile row: the shot starts at
-- player+2 with a 7px hitbox, so a hero can be "aligned" by tile while every
-- bubble harmlessly travels beside an 8px Spore. Route to a pixel-valid firing
-- lane, keep every Spore's trigger radius out of the path, and only fire once
-- that lane exists. Claws retain the visible post-blast punish policy below.
local spore_pixel_route = nil
function spore_shot_lane(px, py, ex, ey, max_range)
    local sx, sy = px + 6, py + 6 -- player shot's 7px hitbox center
    local gx, gy = ex + 4, ey + 4
    -- Match mire_spore_update's actual trigger origin: player top-left to the
    -- Spore center. Never solve a firing lane by stepping into the fuse.
    if math.abs(px - gx) + math.abs(py - gy) < 48 then return nil end
    -- AABB overlap matches combat.c exactly: [shot, shot+7) against [enemy,
    -- enemy+8). The beam itself may be a few pixels off the Spore center.
    if py + 9 > ey and ey + 6 > py + 2
        and math.abs(gx - sx) <= max_range
        and projectile_lane_clear(px, py, ex, ey, gx > sx and KEY_RIGHT or KEY_LEFT) then
        return gx > sx and KEY_RIGHT or KEY_LEFT
    end
    if px + 9 > ex and ex + 6 > px + 2
        and math.abs(gy - sy) <= max_range
        and projectile_lane_clear(px, py, ex, ey, gy > sy and KEY_DOWN or KEY_UP) then
        return gy > sy and KEY_DOWN or KEY_UP
    end
    return nil
end

function spore_pixel_step(room, px, py, ex, ey, fallback, max_range)
    if TM == 0 or EN == 0 then return fallback, true end
    local start = py * 160 + px
    if spore_pixel_route and spore_pixel_route.room == room
        and spore_pixel_route.x == ex and spore_pixel_route.y == ey then
        if spore_pixel_route.dirs[start] then
            return spore_pixel_route.dirs[start], false
        end
        if spore_pixel_route.aims[start] then
            return spore_pixel_route.aims[start], true
        end
    end
    local function safely_outside_all_spores(x, y)
        for i = 0, 31 do
            local p = EN + i * 28
            if emu:read8(p) == 2 and emu:read8(p + 1) % 2 == 1
                and emu:read8(p + 17) == 17 then
                local sx = emu:read8(p + 3) + 4
                local sy = emu:read8(p + 7) + 4
                if math.abs(x + 8 - sx) + math.abs(y + 12 - sy) < 48 then
                    return false
                end
            end
        end
        return true
    end
    local qx, qy, head, tail = {px}, {py}, 1, 1
    local seen, previous, step = {[start] = true}, {}, {}
    local found, found_aim = nil, nil
    while head <= tail do
        local x, y = qx[head], qy[head]; head = head + 1
        local aim = spore_shot_lane(x, y, ex, ey, max_range)
        if aim then
            found = y * 160 + x
            found_aim = aim
            break
        end
        for d = 1, 4 do
            local dir = CARD_KEYS[d]
            local nx, ny = x + CARD_DX[d], y + CARD_DY[d]
            local nk = ny * 160 + nx
            if nx >= 0 and nx <= 146 and ny >= 0 and ny <= 120
                and not seen[nk] and can_step(x, y, dir)
                and safely_outside_all_spores(nx, ny) then
                seen[nk], previous[nk], step[nk] = true, y * 160 + x, dir
                tail = tail + 1; qx[tail], qy[tail] = nx, ny
            end
        end
    end
    if not found then return fallback, true end
    local dirs, node = {}, found
    while previous[node] do
        dirs[previous[node]] = step[node]
        node = previous[node]
    end
    local aims = {[found] = found_aim}
    spore_pixel_route = {room=room, x=ex, y=ey, dirs=dirs, aims=aims}
    if dirs[start] then return dirs[start], false end
    return aims[start] or fallback, true
end

-- When generated cover offers no safe long firing lane, a human resolves the
-- mine's authored three-beat loop instead: step in to arm it, leave during the
-- audible fuse, then punish its long recovery. Keep this outside the main
-- controller loop to avoid mGBA Lua's tight top-level local-variable limit.
function quintra_spore_pressure_keys(room, px, py, target, aim, routed_reach)
    if target.state == 0 then
        return target_step(px, py, target.x, target.y, aim, routed_reach)
    end
    if target.state == 1 then
        return quintra_projectile_dash_dir(px, py, target.x, target.y)
    end
    return KEY_A + target_step(px, py, target.x, target.y, aim, routed_reach)
end

-- Folding Stars expose a short punish window while their contracted core is
-- moving.  A tile-level route can say that the hero already owns a cardinal
-- lane even when the 12px body is caught on the other side of an 8px pillar
-- seam.  Find the lane in the same one-pixel space as cartridge collision so
-- the controller spends that window attacking instead of oscillating against
-- cover.  Unlike the Mire Spore route, no safety exclusion is needed: the
-- expanded Star is handled by its separate orbit policy below.
fold_star_pixel_route = nil
function fold_star_shot_lane(px, py, ex, ey, max_range)
    local sx, sy = px + 6, py + 6
    local gx, gy = ex + 4, ey + 4
    if py + 9 > ey and ey + 6 > py + 2
        and math.abs(gx - sx) <= max_range
        and projectile_lane_clear(px, py, ex, ey,
            gx > sx and KEY_RIGHT or KEY_LEFT) then
        return gx > sx and KEY_RIGHT or KEY_LEFT
    end
    if px + 9 > ex and ex + 6 > px + 2
        and math.abs(gy - sy) <= max_range
        and projectile_lane_clear(px, py, ex, ey,
            gy > sy and KEY_DOWN or KEY_UP) then
        return gy > sy and KEY_DOWN or KEY_UP
    end
    return nil
end

function fold_star_pixel_step(room, px, py, ex, ey, fallback, max_range)
    if TM == 0 then return fallback, false end
    local start = py * 160 + px
    if fold_star_pixel_route and fold_star_pixel_route.room == room
        and fold_star_pixel_route.x == ex and fold_star_pixel_route.y == ey then
        if fold_star_pixel_route.dirs[start] then
            return fold_star_pixel_route.dirs[start], false
        end
        if fold_star_pixel_route.aims[start] then
            return fold_star_pixel_route.aims[start], true
        end
    end
    local qx, qy, head, tail = {px}, {py}, 1, 1
    local seen, previous, step = {[start] = true}, {}, {}
    local found, found_aim = nil, nil
    while head <= tail do
        local x, y = qx[head], qy[head]; head = head + 1
        local aim = fold_star_shot_lane(x, y, ex, ey, max_range)
        if aim then
            found, found_aim = y * 160 + x, aim
            break
        end
        for d = 1, 4 do
            local dir = CARD_KEYS[d]
            local nx, ny = x + CARD_DX[d], y + CARD_DY[d]
            local nk = ny * 160 + nx
            if nx >= 0 and nx <= 146 and ny >= 0 and ny <= 120
                and not seen[nk] and can_step(x, y, dir) then
                seen[nk], previous[nk], step[nk] = true, y * 160 + x, dir
                tail = tail + 1; qx[tail], qy[tail] = nx, ny
            end
        end
    end
    if not found then return fallback, false end
    local dirs, node = {}, found
    while previous[node] do
        dirs[previous[node]] = step[node]
        node = previous[node]
    end
    local aims = {[found] = found_aim}
    fold_star_pixel_route = {room=room, x=ex, y=ey, dirs=dirs, aims=aims}
    if dirs[start] then return dirs[start], false end
    return aims[start] or fallback, aims[start] ~= nil
end

-- A procedural weapon orb replaces player.starter_weapon at runtime.  The
-- controller must therefore classify the held A weapon, not infer its reach
-- from the vessel chosen on the title screen.  These are generated-table
-- indices for the seven weapon entries (0..4 starters, 20 Rift Flail, 21
-- Astral Spear); active/passive indices deliberately fall back to ranged if
-- a malformed save ever exposes one.
function weapon_style(index)
    if index == 0 then return "claw" end
    if index == 1 or index == 4 then return "lunge" end
    if index == 20 then return "flail" end
    if index == 21 then return "spear" end
    return "ranged"
end

function weapon_route_tiles(style)
    -- Fang-Stab is the exception to the ordinary close-combat label: the
    -- current cartridge starts its physical blade 20px out and advances it
    -- for another 40px.  Keep the navigation lane inside that authored 60px
    -- reach, rather than teaching the Wolfkin pilot to walk into a body it
    -- can already strike.  It remains a physical melee style everywhere else
    -- (mine safety, Howl, and contact decisions), not a projectile kit.
    if style == "claw" then return 7 end
    if style == "spear" then return 10 end -- 4px * 22 ticks = 88px
    return 6 -- Tail/Stinger, Flail, and projectile kits all clear a lane here
end

-- The Void Lord's World Collapse deliberately covers almost the entire room.
-- Its marker is honest: ai_data[4] marks the long warning and ai_data[5]
-- selects one corner, modulo four. Read that public runtime state and steer
-- only with ordinary D-pad input; the player still has to reach the pocket
-- before the blast and receives no immunity from the controller.
function void_safe_pocket_step(px, py, target)
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
function rift_portal_step(px, py)
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
                -- The cartridge activates a rift from the exact feet-center
                -- tile, not from a fuzzy pixel radius.  Returning neutral two
                -- pixels early can leave (px+8,py+12) in the northwest tile
                -- forever, especially at a diagonal approach.
                if math.floor((px + 8) / 8) == tx
                    and math.floor((py + 12) / 8) == ty then
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

-- These are controller-observed town branches, deliberately separate from
-- cartridge state. The pilot must experience both shops before it can claim
-- a long run considered village build choices.
local town_market_seen, town_quarter_seen = {}, {}
local town_market_visits, town_quarter_visits = 0, 0
local debug_route_room = -1

function door_step(px, py)
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
    -- Town rooms 33 and 73 are three-screen civic hubs, not a
    -- symmetric dungeon. Visit the market and forge/apothecary quarter once,
    -- then take the north gate; branch screens return west to arrival.
    local in_town = not in_world and is_town_room(room)
    local town_screen = in_town and emu:read8(RS + 19) or 0
    local town_wanted = nil
    if in_town then
        if town_screen == 0 then
            if not town_market_seen[room] then town_wanted = 1
            elseif not town_quarter_seen[room] then town_wanted = 3
            else town_wanted = 0 end
        else
            town_wanted = 3
        end
    end
    -- The Sigil sits in local room 2. The spatial-graph policy below routes
    -- there before selecting any Colossus threshold.
    local local_room = dungeon_local(room, emu:read8(RS + 11))
    -- Local rooms 2 and 4 form a paired nonlinear rift.  Room 2 can skip
    -- forward after its Sigil is collected; if the pilot skipped it, room 4
    -- must take the paired rift back instead of wandering through the shop
    -- and sanctuary looking for a cardinal "back" door (portal arrivals
    -- deliberately have DIR_NONE).  This is controller-only routing over
    -- the cartridge's existing reversible fixture.
    if not in_world and ((local_room == 2 and not stage_sigil_missing()
            and not stage_warden_missing())
        or (local_room == 4 and stage_sigil_missing())) then
        local portal = rift_portal_step(px, py)
        if portal ~= nil then return portal end
    end
    -- Shortest authored route to dungeon gate screen 6.
    local wanted = in_world and WORLD_ROUTE[world_screen + 1] or nil
    if not in_world and not in_town then
        local size = dungeon_size(emu:read8(RS + 11))
        local sigil_missing = stage_sigil_missing()
        local warden_missing = stage_warden_missing()
        local waystone_missing = stage_waystone_missing()
        local deep_warden_missing = stage_deep_warden_missing()
        wanted = dungeon_route_dir(local_room,
            sigil_missing and 2
                or (warden_missing and 3
                or (waystone_missing and 7
                or (deep_warden_missing and 9 or (size - 1)))), size)
        if DEBUG and debug_route_room ~= room then
            debug_route_room = room
            debug_log(string.format(
                "BOTROUTE room=%d local=%d size=%d sigil_missing=%d warden_missing=%d waystone_missing=%d deep_warden_missing=%d wanted=%s doors=%d/%d/%d/%d",
                room, local_room, size, sigil_missing and 1 or 0,
                warden_missing and 1 or 0,
                waystone_missing and 1 or 0,
                deep_warden_missing and 1 or 0,
                wanted == nil and "nil" or tostring(wanted),
                emu:read8(TM + 10), emu:read8(TM + 8 * 20 + 19),
                emu:read8(TM + 16 * 20 + 10),
                emu:read8(TM + 9 * 20)))
        end
    end
    if in_town then
        -- Town roads are authored lanes, not procgen maze geometry. Using the
        -- generic feet-box BFS here occasionally failed to seed a market
        -- route and fell into its DOWN fallback forever. Centre on the lane
        -- and cross its actual boundary instead. The two return doors are
        -- intentionally asymmetric: market returns west, while the forge /
        -- apothecary quarter returns east.
        if town_screen == 0 then
            if town_wanted == 1 then
                if py < 56 then return KEY_DOWN end
                if py > 64 then return KEY_UP end
                return KEY_RIGHT
            end
            if town_wanted == 3 then
                if py < 56 then return KEY_DOWN end
                if py > 64 then return KEY_UP end
                return KEY_LEFT
            end
            if px < 70 then return KEY_RIGHT end
            if px > 74 then return KEY_LEFT end
            return KEY_UP
        end
        if town_screen == 1 then
            -- The market's weapon shelf sells on contact at (80,72).
            -- Returning on the old y=60 lane made the proof pilot buy it
            -- accidentally while merely crossing the square. Walk the clear
            -- upper aisle; deliberate shop targets still approach a ware
            -- through the ordinary purchase branch.
            if py < 52 then return KEY_DOWN end
            if py > 52 then return KEY_UP end
            return KEY_LEFT
        end
        if py < 56 then return KEY_DOWN end
        if py > 64 then return KEY_UP end
        return KEY_RIGHT
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
    -- Outdoor screens use the same small body-aware BFS as a dungeon room.
    -- Holding the coarse cardinal toward an east/west exit works in open
    -- grass, but can strand the controller against a tree line above or
    -- below the two-tile doorway while a Hornet keeps contact pressure on.
    -- The graph target below retains the authored route; its final approach
    -- centers the real feet box before crossing the screen boundary.
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
            or (in_town and dir == town_wanted)
            or (not in_world and not in_town and dir == wanted)) then
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

-- Keep signature choice out of the already dense frame loop.  This is still
-- pure controller policy: it reads the same public observations and returns
-- the same six-bit input mask, but keeps future kit experiments from hitting
-- Lua's 200-local limit in the rollout function.
function quintra_signature_keys(keys, target, aim, dx, dy, mp, mp_max,
    active_charge, waiting_star, frame, px, py, hp, threat)
    local period = (CLASS == 3) and 90 or (CLASS == 4) and 120 or 180
    local nearby = hostile_count_near(px, py, 32)
    local reach = math.max(math.abs(dx), math.abs(dy))

    -- Howl remains a player-facing clutch ward, but a generic agent cannot
    -- value its 30-frame opening better than the held Fang combo it breaks.
    -- Keep Wolfkin on A/Max Strike in comparable balance runs; all other
    -- signatures continue below through their measured threat policies.
    if ABILITY_POLICY == "smart" and CLASS == 0
        -- Howl is Wolfkin's committed answer to a required Sentinel, a
        -- Colossus inside the real Fang lane, or a genuine sealed swarm. A
        -- full-meter opening creates the authored eight-way burst and its
        -- short activation ward before the melee pilot has to establish
        -- sustained pressure. It is never spent in ordinary rooms or from
        -- across a boss arena.
        and (target.kind == 1
            or (SEALED ~= 0 and emu:read8(SEALED) ~= 0 and nearby >= 2
                and reach <= 32))
        and not waiting_star and active_charge == 0 and mp == mp_max
        and reach <= (target.giant ~= 0 and 48 or 64) then
        return KEY_B + aim
    elseif ABILITY_POLICY == "smart" and CLASS == 2
        and not waiting_star and active_charge == 0 and mp >= 2
        and (nearby >= 2 or reach <= 28) then
        return KEY_B + aim
    elseif ABILITY_POLICY == "smart" and CLASS == 1
        -- Stoneskin is not only a giant-fight clock. The fixed long-route
        -- replay can place the room-three Sentinel directly inside Tail
        -- Spike range; withholding Sauran's authored body/shot barrier there
        -- makes the pilot absorb a contact every iframe cycle while it tries
        -- to retreat through the boss. Restrict this extension to that
        -- sentinel's immediate body envelope, so ordinary small enemies do
        -- not consume the two-MP cooldown opportunistically.
        and (target.giant ~= 0 or (target.kind == 1 and reach <= 20))
        and not waiting_star
        and active_charge == 0 and mp >= 2
        and ((SAURAN_BODY_SHIELD_RANGE > 0 and reach <= SAURAN_BODY_SHIELD_RANGE)
            or (SAURAN_GIANT_SHIELD_PERIOD > 0
                and frame % SAURAN_GIANT_SHIELD_PERIOD == 0)) then
        return KEY_B + aim
    -- A full meter is Picsean's authored Spirit Convergence moment.  Spend it
    -- as the first safe answer to a newly engaged giant instead of waiting
    -- for an unrelated global clock boundary; a player can make this same
    -- A+B choice at any point.  An imminent body/shooting lane is handled by
    -- Undertow immediately below.
    elseif ABILITY_POLICY == "smart" and CLASS == 3
        and target.giant ~= 0 and not waiting_star
        and active_charge == 0 and mp == mp_max
        and reach > 20 and threat == nil
        -- Hydra's mixed 1/2/3-speed streams are the one late boss where a
        -- full bar pays for several real Undertows better than an opening
        -- A+B. Every other giant retains the visible convergence opener.
        and target.pattern ~= 7 then
        if convergence_prime < 2 then
            convergence_prime = convergence_prime + 1
            return 0
        end
        convergence_prime = 0
        return KEY_A + KEY_B + aim
    -- Picsean's Tidal Wave is not only three broad bubbles: its authored
    -- Undertow barrier blocks bodies and hostile shots for 100 frames. In an imminent
    -- giant-body collision the controller spends that real B immediately,
    -- including at full MP. Frost Spider (pattern 3) is the exception: its
    -- first nearby blink has no shot yet, so preserve the same barrier for a
    -- real warning or body overlap rather than consuming it on cooldown.
    -- Spirit Convergence remains directly available to the player and is
    -- independently exercised by its cartridge contract.
    elseif ABILITY_POLICY == "smart" and CLASS == 3
        and target.giant ~= 0 and not waiting_star
        and active_charge == 0 and mp >= 2
        and (reach <= PICSEAN_GIANT_GUARD_RANGE
            -- Hydra's five 1/2/3-speed streams threaten the whole ranged
            -- lane before the 32px body is close. Undertow is the authored
            -- defensive answer; allow its visible read out to 72px for that
            -- pattern alone rather than turning every boss into a remote B.
            or (target.pattern == 7 and reach <= 72))
        and (threat ~= nil or reach <= 20)
        and not (target.pattern == 3 and threat == nil and reach > 20) then
        return KEY_B + aim
    -- At four half-hearts or below, use the same temporary barrier to get
    -- out of an ordinary body collision. The required room-3 Warden is the
    -- one proactive exception: its large body plus two escorts is now part
    -- of every critical route, so Picsean should spend its authored guard
    -- when that body actually closes instead of dying with a full meter.
    elseif ABILITY_POLICY == "smart" and CLASS == 3
        and target.giant == 0 and not waiting_star
        and active_charge == 0 and mp >= 2
        and ((hp <= 4 and reach <= 20)
            or (target.kind == 1 and RS ~= 0
                and dungeon_local(emu:read8(RS + 1), emu:read8(RS + 11)) == 3
                and reach <= 32)) then
        return KEY_B + aim
    elseif ABILITY_POLICY == "smart" and CLASS == 4
        and target.giant ~= 0 and not waiting_star
        and active_charge == 0 and mp >= 2 and reach <= 48 then
        return KEY_B + aim
    -- A charging Rope is the exact pre-Colossus threat where Stinger's
    -- narrow 48px line can fail. Spend Vespine's real fan here instead of
    -- conserving every B charge for the boss room.
    elseif ABILITY_POLICY == "smart" and CLASS == 4
        and target.giant == 0 and target.kind == 9 and not waiting_star
        and active_charge == 0 and mp >= 2 and reach <= 48 then
        return KEY_B + aim
    -- Vespine's repeated fan is valuable after the opening Colossus,
    -- especially in the Rope route, but it drains the meter before the
    -- opening Sentinel. Keep the player kit untouched and delay only this
    -- periodic pilot cadence until that boss has actually fallen.
    elseif ABILITY_POLICY == "smart" and CLASS ~= 1 and CLASS ~= 0
        and (CLASS ~= 4 or (RS ~= 0 and emu:read8(RS + 11) > 0))
        and target.kind ~= 10 and not waiting_star
        and active_charge == 0 and mp >= 2
        and not (target.giant ~= 0 and mp == mp_max)
        and frame % period == 0 then
        return KEY_B + aim
    elseif ABILITY_POLICY == "smart" and CLASS ~= 0
        and (CLASS ~= 4 or (RS ~= 0 and emu:read8(RS + 1) >= 3))
        and not waiting_star and active_charge == 0
        and mp == mp_max and frame % 600 == 599 then
        return 0
    elseif ABILITY_POLICY == "smart" and CLASS ~= 0
        and (CLASS ~= 4 or (RS ~= 0 and emu:read8(RS + 1) >= 3))
        and not waiting_star and active_charge == 0
        and mp == mp_max and frame % 600 == 0 then
        return KEY_A + KEY_B + aim
    end
    convergence_prime = 0
    return keys
end

-- Giant tactics are isolated from the rollout loop so policy changes do not
-- consume its scarce local-variable budget. This remains a pure input choice:
-- it reads the live target and returns an ordinary button mask.
function quintra_giant_combat_keys(target, dx, dy, aim, held_style, frame, px, py)
    local adx, ady = math.abs(dx), math.abs(dy)
    local reach = (adx > ady) and adx or ady
    local offaxis = (aim == KEY_UP or aim == KEY_DOWN) and adx or ady
    local giant_mode = GIANT_POLICY
    if giant_mode == "classwise" then
        giant_mode = (held_style == "claw") and "baseline"
            or (held_style == "lunge" and CLASS == 1) and "pulse_fire"
            or (held_style == "lunge" and CLASS ~= 4) and "orbit_fire"
            or (held_style == "flail" or held_style == "spear") and "orbit_fire"
            or (held_style == "ranged" and CLASS == 0) and "orbit_fire"
            or (CLASS == 1 or CLASS == 2 or CLASS == 3 or CLASS == 4)
                and "orbit_fire" or "baseline"
    end
    local giant_retreat = GIANT_RETREAT_RANGE
    local giant_fire_range = 48
    local giant_fire_cadence = GIANT_FIRE_CADENCE
    local giant_orbit_floor = GIANT_RETREAT_RANGE_ENV and giant_retreat or 36
    if held_style == "spear" then
        giant_retreat, giant_fire_range, giant_orbit_floor = 52, 80, 52
    elseif held_style == "claw" and CLASS == 0 then
        if GIANT_RETREAT_RANGE_ENV == nil then
            giant_retreat, giant_orbit_floor = 24, 24
        else
            giant_orbit_floor = giant_retreat
        end
        -- Fang Stab now has a real 64px physical lane. Keep the proven
        -- no-contact buffer, but stop routing the pilot through the outer
        -- third of a legal sword line just to stand at the old 48px cap.
        giant_fire_range = 64
        if os.getenv("QUINTRA_BOT_GIANT_FIRE_CADENCE") == nil then giant_fire_cadence = 3 end
    elseif held_style == "claw" and CLASS == 2 then
        if GIANT_RETREAT_RANGE_ENV == nil then giant_retreat, giant_orbit_floor = 32, 32 end
    elseif held_style == "ranged" and CLASS == 2 then
        -- Featherbarb can damage a Colossus from a real ranged lane. Its old
        -- 32px reset band repeatedly overlapped the moving Hydra body; 48px
        -- cuts that observed contact sharply and turns the fixed route's
        -- second boss from a death into a clear. Keep the environment knob
        -- authoritative for offline policy sweeps.
        if GIANT_RETREAT_RANGE_ENV == nil then giant_retreat, giant_orbit_floor = 48, 48 end
    elseif CLASS == 3 then
        if GIANT_RETREAT_RANGE_ENV == nil then
            -- BubbleBolt crosses a room, so Picsean need not trade body
            -- contact for damage. The rebuilt fixed replay survives seven
            -- bosses at this 56px lane versus dying after two at 40px; it is
            -- a controller-spacing correction only, not a character buff.
            giant_retreat, giant_orbit_floor = 56, 56
        else
            giant_orbit_floor = giant_retreat
        end
        -- BubbleBolt crosses the full viewport, while Frost Spider's blink
        -- intentionally reappears 44px away. Treating Picsean like a
        -- short-range orbit fighter made the pilot spend each post-blink
        -- recovery walking back into the web instead of holding a safe,
        -- readable firing lane. This affects only that announced pattern;
        -- other giants keep Picsean's closer barrier-oriented spacing.
        if held_style == "ranged" and target.pattern == 3 then
            giant_retreat, giant_orbit_floor = 32, 32
            giant_fire_range, giant_fire_cadence = 72, 2
        -- Hydra launches five mixed-speed bubbles, but Picsean's BubbleBolt
        -- reaches across the entire room.  Keep the pilot outside the
        -- crossfire instead of treating this ranged duel like a body-orbit:
        -- it can still attack from the established 96px lane and only needs
        -- to sidestep if the boss closes the gap.
        elseif held_style == "ranged" and target.pattern == 7 then
            giant_retreat, giant_orbit_floor = 56, 56
            giant_fire_range, giant_fire_cadence = 96, 2
        end
    elseif held_style == "lunge" and CLASS == 1 then
        if GIANT_RETREAT_RANGE_ENV == nil then
            -- Tail Spike owns a real 48px lane. Holding only a 40px reset
            -- asked the tank to trade the outer edge of that strike for
            -- repeated giant contact; the fixed opening seed now clears its
            -- 200-HP Colossus alive at the authored 48px buffer.
            giant_retreat, giant_orbit_floor = 48, 48
        else
            giant_orbit_floor = giant_retreat
        end
        giant_fire_range = 52
        if os.getenv("QUINTRA_BOT_GIANT_FIRE_CADENCE") == nil then giant_fire_cadence = 2 end
    elseif held_style == "lunge" and CLASS == 4 then
        if os.getenv("QUINTRA_BOT_GIANT_FIRE_CADENCE") == nil then giant_fire_cadence = 2 end
    elseif held_style == "flail" or (held_style == "lunge" and CLASS ~= 4) then
        if GIANT_RETREAT_RANGE_ENV == nil then giant_retreat = 28 end
    end
    local retreat = (aim == KEY_UP and KEY_DOWN)
        or (aim == KEY_DOWN and KEY_UP)
        or (aim == KEY_LEFT and KEY_RIGHT) or KEY_LEFT
    if held_style == "lunge" and CLASS == 1 and reach < SAURAN_GIANT_ESCAPE_RANGE then
        return retreat
    elseif target.giant ~= 0 and giant_mode ~= "baseline" and reach < giant_orbit_floor then
        local orbit = giant_orbit_step(px, py, aim, retreat)
        if giant_mode == "pulse_fire" then
            return (frame % SAURAN_GIANT_PULSE_PERIOD == 0) and (KEY_A + aim) or retreat
        end
        return (giant_mode == "orbit_fire" and frame % giant_fire_cadence == 0)
            and (KEY_A + aim) or orbit
    elseif reach < giant_retreat then
        return retreat
    elseif held_style == "claw" and CLASS == 0
        and reach <= giant_fire_range and offaxis > 5 then
        -- Do not combine an off-axis correction with A: the D-pad would aim
        -- the physical Fang past a Serpent while also walking Wolfkin toward
        -- its rotating cross. Establish the real cardinal lane first, then
        -- use the attack/retreat beat below.
        return target_step(px, py, target.x, target.y, aim, 6)
    elseif held_style == "claw" and CLASS == 0
        and reach <= giant_fire_range and offaxis <= 5 then
        -- D-pad direction both aims and moves. Holding A+toward boss at a
        -- perfectly valid 24..64px Fang lane walked Wolfkin into the body on
        -- every attack frame. Pair one aimed strike with one outward step:
        -- it keeps the real sword lane, preserves the normal 24-frame weapon
        -- cadence, and still lets a moving Colossus close the gap honestly.
        return (frame % 2) == 0 and (KEY_A + aim) or retreat
    elseif reach <= giant_fire_range and offaxis <= 5 then
        return KEY_A + aim
    end
    local giant_route_tiles = held_style == "spear" and 10
        or held_style == "flail" and 6 or 5
    return KEY_A + target_step(px, py, target.x, target.y, aim, giant_route_tiles)
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
if EASY then tap(KEY_SELECT) end
if DEBUG then
    debug_log(string.format("BOTBOOT class=%d easy=%d select_frame=%d screen=%d target=%s",
        CLASS, EASY and 1 or 0, FC ~= 0 and read16(FC) or 0,
        LS ~= 0 and emu:read8(LS) or 255,
        TARGET_FRAME and tostring(TARGET_FRAME) or "-"))
end
if FC ~= 0 and TARGET_FRAME then
    -- run_init_enter seeds the run from this exact pre-confirm loop frame.
    -- Absolute alignment—not a delay relative to class-select entry—is what
    -- makes a saved controller trace genuinely reproducible across launches.
    while read16(FC) ~= TARGET_FRAME do tick(0) end
elseif FC ~= 0 then
    local confirm_at = (select_base + 160) % 65536
    while read16(FC) ~= confirm_at do tick(0) end
else
    -- Compatibility fallback for an old linker map.
    for _ = 1, ((4 - CLASS) * 16) do tick(0) end
end
if DEBUG then
    debug_log(string.format("BOTALIGN class=%d frame=%d screen=%d",
        CLASS, FC ~= 0 and read16(FC) or 0, LS ~= 0 and emu:read8(LS) or 255))
end
tap(KEY_A)
if TARGET_FRAME and LS ~= 0 and PL ~= 0 then
    -- Synchronize to the first actually playable room. run_init/procgen gives
    -- the hero 60 visible entry iframes; reading them makes the exact replay
    -- independent of title/class/room rendering cost while remaining pure
    -- controller input. A bounded wait turns a boot regression into a normal
    -- failed trial instead of hanging the host.
    ready_wait = 0
    while ready_wait < 120
        and (emu:read8(LS) ~= 5 or emu:read8(PL + 2) == 0
            or emu:read8(PL + 15) == 0) do
        tick(0)
        ready_wait = ready_wait + 1
    end
    while ready_wait < 180 and emu:read8(PL + 15) > READY_IFRAMES do
        tick(0)
        ready_wait = ready_wait + 1
    end
else
    for _ = 1, 45 do tick(0) end
end
-- GAME OVER clears/reuses run_state before the final CSV write. Snapshot the
-- real initialized seed now so a fatal row remains replayable rather than
-- falsely looking like title-screen entropy or memory corruption.
RUN_SEED_SNAPSHOT = RS ~= 0 and (emu:read8(RS + 2)
    + emu:read8(RS + 3) * 256
    + emu:read8(RS + 4) * 65536
    + emu:read8(RS + 5) * 16777216) or 0
if DEBUG then
    debug_log(string.format("BOTSTART class=%d frame=%d screen=%d",
        CLASS, FC ~= 0 and read16(FC) or 0, LS ~= 0 and emu:read8(LS) or 255))
end

local frames, max_room, last_hp, damage_taken, giant_overlap_damage, min_hp = 0, 0, 0, 0, 0, 255
local min_giant_hp = 255
local boss_start_frame, boss_start_beaten = -1, 0
local boss_attempts, boss_attempt_frames, boss_clear_frames = 0, 0, 0
-- Semicolon-separated at CSV write time: one elapsed-frame value for every
-- actual stage-boss kill. Keeping it in the host observer gives balance
-- analysis per-encounter timing without changing cartridge RAM or pacing.
local boss_clear_durations = {}
local last_damage_source = 255 -- enemy id, 254=hazard, 253=unresolved hostile
-- Keep the fatal-event context outside the main local scope: mGBA Lua caps
-- the number of locals in this controller's large top-level loop. These are
-- observation-only fields, never cartridge writes.
death_room, death_bosses, death_giant, death_giant_overlap = 255, 0, 0, 0
-- The cartridge clears player state as part of the GAME OVER path. Keep the
-- actual death-build stats when the fatal HP frame is observed, otherwise the
-- CSV's "final" columns describe the title-reset vessel rather than the run
-- being evaluated.
death_hp_max, death_mp_max, death_atk, death_def, death_spd, death_lck = 0, 0, 0, 0, 0, 0
last_damage_giant_overlap = 0
-- Boss relics are the guaranteed run-power curve.  This observer records
-- whether the controller sees and actually collects each post-boss orb
-- before leaving its room; it never changes cartridge state or routing.
boss_relics_seen, boss_relics_collected, boss_relics_missed = 0, 0, 0
boss_relic_pending, boss_relic_slot, boss_relic_room, last_boss_count = 0, -1, 255, 0
boss_relic_item_id = 0xFF
local rooms_seen, last_room = 1, 0
local room_enter_frame = 0
local route_start_frame = 0
local last_px, last_py, still_frames = 255, 255, 0
local escape_timer, escape_dir, escape_index = 0, KEY_UP, 0
local shake_phase = 0
shake_dir, shake_cycle = KEY_RIGHT, 0
local towns_seen, town_rooms = 0, {}
local world_hops, last_world_key = 0, -1
local world_contact_hits = 0
local debug_shot_room = -1
local debug_spore_room = -1
local last_target_slot, last_target_hp = -1, 255
local no_damage_frames, flank_timer = 0, 0
-- Independent of the generic flank timer: it records unchanged HP on one
-- selected hostile. This makes a combat-stall report mean "no progress",
-- rather than merely "a procedurally busy room took a long time to clear".
target_stall_frames = 0
local spore_pressure_timer = 0
local wall_follow_dir, wall_follow_min = 0, 0
local dodge_phase, dodge_dir, dodge_cooldown, dodge_count = 0, KEY_RIGHT, 0, 0
-- A close hostile can pin a champion against a wall before the ordinary
-- projectile-only dodge heuristic notices it.  Keep a short, read-only
-- request after an observed body hit; the input phase below turns it into the
-- same double-tap dash available to a player.  This is deliberately not an
-- HP, position, or iframe write.
local body_dash_frames, body_dash_source = 0, 255
local last_body_hit_source, last_body_hit_frame, body_hit_streak = 255, -120, 0
-- Once a feet box lands on spikes, keep one escape lane until it has truly
-- crossed a safe tile. Re-choosing every pixel can ping-pong on a wall seam.
local spike_escape_dir = 0
local last_active_charge = 0
local last_input_keys, b_uses = 0, 0
local purchases, last_coins = 0, 0
local shop_visits, visited_shop_rooms = 0, {}
local max_combat_frames, max_route_frames = 0, 0
local max_combat_room, max_combat_enemy, max_route_room = 0, 255, 0
max_target_stall_frames, max_target_stall_room, max_target_stall_enemy = 0, 0, 255
local last_weapon = 255
weapon_swaps = 0
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
    -- B's cooldown alone does not say whether the protective part of a
    -- signature is currently active. Keep the barrier timer read-only for
    -- observation/RL consumers without adding a top-level Lua local.
    observed_shield_timer = PL ~= 0 and emu:read8(PL + 20) or 0
    local equipped_weapon = PL ~= 0 and emu:read8(PL + 21) or 0
    local held_style = weapon_style(equipped_weapon)
    if equipped_weapon ~= last_weapon then
        if last_weapon ~= 255 then weapon_swaps = weapon_swaps + 1 end
        if DEBUG then debug_log(string.format(
            "BOTWEAPON f=%d room=%d item=%d style=%s",
            frames, RS ~= 0 and emu:read8(RS + 1) or 0,
            equipped_weapon, held_style)) end
        last_weapon = equipped_weapon
    end
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
    if is_town_room(room) then
        -- `world_return_screen` is a plaza index only in a town. Mark each
        -- side street when its real room has loaded so the next arrival visit
        -- advances the itinerary instead of pacing between civic doors.
        local town_screen = emu:read8(RS + 19)
        if town_screen == 1 and not town_market_seen[room] then
            town_market_seen[room], town_market_visits = true, town_market_visits + 1
        elseif town_screen == 2 and not town_quarter_seen[room] then
            town_quarter_seen[room], town_quarter_visits = true, town_quarter_visits + 1
        end
    end
    local won = RS ~= 0 and emu:read8(RS + 10) or 0
    if frames == 0 then last_hp = hp end
    if hp < last_hp then
        local taken = last_hp - hp
        last_damage_giant_overlap = 0
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
            if (CLASS == 0 or CLASS == 1 or CLASS == 4) and threat then
                -- Wolfkin, Sauran, and Vespine all use physical lanes. A
                -- repeated hit from the same body within 90 frames is the
                -- wall-pin signature for Sauran/Vespine; Wolfkin instead
                -- spends the first recovery beat immediately because its
                -- basic attack owns the tightest contact lane.
                if threat.kind == last_body_hit_source
                    and frames - last_body_hit_frame <= 90 then
                    body_hit_streak = body_hit_streak + 1
                else
                    body_hit_streak = 1
                end
                last_body_hit_source, last_body_hit_frame = threat.kind, frames
                -- Wolfkin is the one physical-contact kit whose basic
                -- weapon needs a body-adjacent lane. A controller that waits
                -- for a second scrape before using its normal dodge spends
                -- the entire recovery beat pinned to the same enemy. Other
                -- close kits retain their measured two-hit confirmation.
                if CLASS == 0 or body_hit_streak >= 2 then
                    body_dash_frames, body_dash_source = 16, threat.kind
                    body_hit_streak = 0
                end
            end
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
                    last_damage_giant_overlap = 1
                    break
                end
            end
        end
        if DEBUG then
            debug_log(string.format(
                "BOTHIT f=%d room=%d world=%d:%d hp=%d->%d src=%d pos=%d,%d ifr=%d target=%d",
                frames, room, RS ~= 0 and emu:read8(RS + 17) or 0,
                RS ~= 0 and emu:read8(RS + 18) or 0,
                last_hp, hp, last_damage_source, hit_x, hit_y, iframes,
                threat and threat.kind or 255))
        end
        if hp == 0 and death_room == 255 then
            death_room = RS ~= 0 and emu:read8(RS + 1) or 255
            death_bosses = RS ~= 0 and emu:read8(RS + 11) or 0
            death_giant = giant_active() and 1 or 0
            death_giant_overlap = last_damage_giant_overlap
            death_hp_max = PL ~= 0 and emu:read8(PL + 1) or 0
            death_mp_max = PL ~= 0 and emu:read8(PL + 3) or 0
            death_atk = PL ~= 0 and emu:read8(PL + 5) or 0
            death_def = PL ~= 0 and emu:read8(PL + 6) or 0
            death_spd = PL ~= 0 and emu:read8(PL + 7) or 0
            death_lck = PL ~= 0 and emu:read8(PL + 8) or 0
            if DEBUG then
                debug_log(string.format(
                    "BOTDEATHBUILD f=%d hpmax=%d mpmax=%d atk=%d def=%d spd=%d lck=%d",
                    frames, death_hp_max, death_mp_max, death_atk, death_def,
                    death_spd, death_lck))
            end
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
        -- Target slots are reused independently in every generated room.
        -- Carrying the prior room's unchanged-HP timer into a new optional
        -- encounter can instantly classify its first target as a six-second
        -- stall, turn back through the arrival door, and ping-pong forever.
        last_target_slot, last_target_hp = -1, 255
        no_damage_frames, target_stall_frames, flank_timer = 0, 0, 0
        fold_star_pixel_route, spore_pixel_route = nil, nil
        if is_town_room(room) and not town_rooms[room] then
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
    -- Room 3 is the authored miniboss check. If a stationary Spore escort is
    -- closer than its Sentinel, clear the actual miniboss first; only then is
    -- it sensible to spend time locating a mine-safe firing lane.
    if target and target.kind == 17
        and dungeon_local(room, emu:read8(RS + 11)) == 3 then
        local miniboss = enemy_target(px, py, 1)
        if miniboss then target = miniboss end
    end
    if target and (target.kind == 17 or target.kind == 13)
        and DEBUG and debug_spore_room ~= room then
        debug_tilemap(frames, room, px, py, target)
        debug_spore_room = room
    end
    -- Only an immediately observed, close body is allowed to request the
    -- emergency dash. A distant shooter/projectile may share an enemy ID,
    -- but should continue through the normal projectile-dodge policy.
    local body_dash_ready = body_dash_frames > 0 and target
        and target.kind == body_dash_source
        and math.max(math.abs(target.x - px), math.abs(target.y - py)) <= 20
    if body_dash_frames > 0 then body_dash_frames = body_dash_frames - 1 end
    -- Overworld encounters are optional traversal pressure. Follow the
    -- authored route while firing instead of treating every screen as a
    -- mandatory clear.  Corvin's slow returning blade is the one measured
    -- exception: a body that has actually entered its 16px lane physically
    -- prevents progress, so engage only that blocker until the route opens.
    -- The melee champions retain their independently tested flee policies.
    local overworld_threat = world_mode == 1 and target or nil
    local world_blocker = CLASS == 2 and overworld_threat
        and math.max(math.abs(overworld_threat.x - px),
            math.abs(overworld_threat.y - py)) <= 16
    if world_mode == 1 then target = world_blocker and overworld_threat or nil end
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
            "BOTSTATE f=%d room=%d local=%d stage=%d sigils=%d pos=%d,%d target=%d@%d,%d hp=%d state=%d clock=%d slot=%d stuck=%d portal=%d,%d",
            frames, room, dungeon_local(room, emu:read8(RS + 11)),
            emu:read8(RS + 11), read16(RS + 23),
            px, py, target and target.kind or 255, target and target.x or 255,
            target and target.y or 255, target and target.hp or 255,
            target and target.state or 255, target and target.clock or 255,
            target and target.slot or 255, no_damage_frames,
            portal_x, portal_y))
    end
    -- A boss fight is measured from the first real giant observation through
    -- its actual disappearance, not by room residency.  That excludes the
    -- sanctuary/door animation and records a death during an active boss as
    -- an attempt without pretending it was a clear.
    local bosses_now = RS ~= 0 and emu:read8(RS + 11) or 0
    if bosses_now > last_boss_count then
        boss_relic_pending, boss_relic_slot, boss_relic_room = 1, -1, room
    end
    last_boss_count = bosses_now
    if boss_relic_pending ~= 0 then
        if room ~= boss_relic_room then
            -- It was not collected before the controller crossed the exit.
            boss_relics_missed, boss_relic_pending = boss_relics_missed + 1, 0
        elseif boss_relic_slot < 0 and EN ~= 0 then
            for boss_relic_scan = 0, 31 do
                boss_relic_ptr = EN + boss_relic_scan * 28
                if emu:read8(boss_relic_ptr) == 3
                    and emu:read8(boss_relic_ptr + 1) % 2 == 1
                    and emu:read8(boss_relic_ptr + 17) == 3
                    -- A banked pickup constructor can cross the observer's
                    -- frame boundary after publishing PICKUP_ITEM but before
                    -- filling ai_data[1]. Bind only a completed passive item,
                    -- otherwise transient zero becomes the wrong stable ID
                    -- and a real walk-over collection is reported as missed.
                    and emu:read8(boss_relic_ptr + 18) >= 10
                    and emu:read8(boss_relic_ptr + 18) <= 19 then
                    boss_relic_slot = boss_relic_scan
                    -- Boss-relic pools contain passive table positions 10..19;
                    -- their stable content IDs are 20..29. Record the ID so
                    -- a despawn only counts as collection if the cartridge
                    -- really inserted it into player.inventory at offset 24.
                    boss_relic_item_id = emu:read8(boss_relic_ptr + 18) + 10
                    boss_relics_seen = boss_relics_seen + 1
                    if DEBUG then
                        debug_log(string.format(
                            "BOTRELICSEEN f=%d room=%d table=%d item=%d slot=%d",
                            frames, room, emu:read8(boss_relic_ptr + 18),
                            boss_relic_item_id, boss_relic_slot))
                    end
                    break
                end
            end
        elseif boss_relic_slot >= 0 then
            boss_relic_ptr = EN + boss_relic_slot * 28
            if emu:read8(boss_relic_ptr) ~= 3
                or emu:read8(boss_relic_ptr + 1) % 2 == 0 then
                boss_relic_owned = false
                if PL ~= 0 and boss_relic_item_id ~= 0xFF then
                    for boss_relic_inventory_slot = 0, 15 do
                        if emu:read8(PL + 24 + boss_relic_inventory_slot)
                            == boss_relic_item_id then
                            boss_relic_owned = true
                            break
                        end
                    end
                end
                if boss_relic_owned then
                    boss_relics_collected = boss_relics_collected + 1
                    if DEBUG then
                        debug_log(string.format(
                            "BOTRELICGET f=%d room=%d item=%d atk=%d def=%d hpmax=%d",
                            frames, room, boss_relic_item_id,
                            emu:read8(PL + 5), emu:read8(PL + 6), emu:read8(PL + 1)))
                    end
                else
                    boss_relics_missed = boss_relics_missed + 1
                end
                boss_relic_pending = 0
            end
        end
    end
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
        if target.giant ~= 0
            and math.max(math.abs(target.x - px), math.abs(target.y - py)) <= 32 then
            enemy_seen.giant_close_frames = enemy_seen.giant_close_frames + 1
        end
        if target.slot == last_target_slot and target.hp >= last_target_hp then
            no_damage_frames = no_damage_frames + 1
        else
            no_damage_frames = 0
        end
        if target.slot == last_target_slot and target.hp >= last_target_hp then
            target_stall_frames = target_stall_frames + 1
        else
            target_stall_frames = 0
        end
        if world_mode == 0 and target_stall_frames > max_target_stall_frames then
            max_target_stall_frames = target_stall_frames
            max_target_stall_room, max_target_stall_enemy = room, target.kind
        end
        last_target_slot, last_target_hp = target.slot, target.hp
    else
        last_target_slot, last_target_hp, no_damage_frames = -1, 255, 0
        target_stall_frames = 0
    end
    -- Dungeon rooms use normal loot/objective routing.  Riftwild intentionally
    -- ignores optional drops, but the one fixed Riftwell is a public recovery
    -- mechanic and must be part of an honest long-run policy.  The dedicated
    -- local-room-2 Sigil is different from ordinary loot: it is the stage
    -- gate.  Seek it before optional combat, or a melee pilot can donate its
    -- entire health pool chasing a Flutterbat and only then remember the
    -- fixture it came here for.  This is still a body-valid walk to the
    -- cartridge pickup, never a state shortcut.
    local loot = quintra_boss_relic_target()
        or (world_mode == 0
        and dungeon_local(room, emu:read8(RS + 11)) == 2 and stage_sigil_missing()
        and pickup_target(px, py, hp, hp_max))
        -- A live fight normally takes priority over floor drops. At a genuine
        -- low-health threshold, however, an existing heart is the encounter's
        -- authored recovery resource; a human takes that step instead of
        -- continuing a perfect-but-fatal damage race. Restrict this exception
        -- to hearts so the observer never abandons combat for a coin.
        or (world_mode == 0 and target and hp + 3 <= hp_max
            and pickup_target(px, py, hp, hp_max, true))
        or (not target and ((world_mode == 0 and pickup_target(px, py, hp, hp_max))
            or (world_mode == 1 and riftwell_target(px, py, hp, hp_max, mp, mp_max))) or nil)
    if loot and loot.kind == 11 then target = nil end
    local shop = (not target and not loot and world_mode == 0)
        and shop_target(px, py, hp, hp_max, mp_max, coins) or nil
    local room_age = frames - room_enter_frame
    -- Once Wolfkin's optional shop approach window expires, clear the
    -- controller's local target entirely. Leaving it truthy while taking
    -- `door_step` still made later stuck recovery classify the room as shop
    -- navigation and overwrite the chosen exit with combat-style escapes.
    -- Other champions retain their separately validated shop policies.
    if shop and CLASS == 0 and room_age >= 600 then shop = nil end
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
    -- The combat branch owns a local threat observation. Retain a read-only
    -- copy for the trace after that branch closes; otherwise Lua resolves the
    -- later trace argument as a nil global and hides real dodge decisions.
    observed_threat = nil
    local sigil_pixel_active = false
    -- An unsealed early room is allowed to keep a live optional hostile.  When
    -- the pilot deliberately yields that fight, later safety code must treat
    -- the decision as routing, not silently restore target-chase steering at
    -- the edge.  Keep `target` itself intact for telemetry until that decision
    -- is made, then clear it below so dodge/arrival guards use the same route
    -- intent as the human-facing open door.
    local optional_exit = false
    local puzzle_keys = world_mode == 0
        and puzzle_controller_step(room, px, py, frames) or nil
    -- A collected Rift Sigil immediately unlocks the portal in local room 2.
    -- Treat the static Spore's optional post-pickup encounter as lower
    -- priority than that authored route. Other enemies retain the ordinary
    -- combat-before-portal policy, except a wounded Sauran: after collecting
    -- the required Sigil at three hearts or lower, its real tank decision is
    -- to use the unlocked rift rather than donate its remaining recovery
    -- budget to an optional Rope or Orc. `door_step` contains the same portal
    -- routing after a room is clear; make this narrow exception explicit
    -- because a live enemy otherwise prevents that helper from being reached.
    progress_portal_step = nil
    if world_mode == 0
        and dungeon_local(room, emu:read8(RS + 11)) == 2
        and not stage_sigil_missing()
        and target and (target.kind == 17 or (CLASS == 1 and hp <= 6)) then
        progress_portal_step = rift_portal_step(px, py)
    end
    if puzzle_keys ~= nil then
        keys = puzzle_keys
        target, observed_threat = nil, nil
        dodge_phase, body_dash_ready = 0, false
        route_start_frame = frames
    elseif progress_portal_step ~= nil then
        keys = progress_portal_step
        -- This is an explicit progression decision: once the required Sigil
        -- is owned, the optional Spore no longer owns combat recovery,
        -- projectile dodges, or short target-stall escapes.  Keeping `target`
        -- live here let those later generic policies overwrite the portal
        -- route every few frames and orbit the room indefinitely.
        target, observed_threat = nil, nil
        dodge_phase, body_dash_ready = 0, false
    elseif target then
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
        -- The held A weapon, not the vessel, defines the valid firing lane.
        -- This lets a Picsean or Wolfkin that takes an Astral Spear hold its
        -- real ten-tile line instead of walking into claw range, while a
        -- ranged champion that takes a Flail still uses a reachable lane.
        local routed_reach = weapon_route_tiles(held_style)
        -- Both starter lunges carry 48px.  Do not collapse Sauran's Tail
        -- Spike to the adjacent-claw route: that made the input-only pilot
        -- chase Ropes all the way into the north wall even when it already
        -- held a clear, valid thrust lane.
        -- Retained through the body-safety pass below: a Leech behind cover
        -- needs an actual route, not the generic close-range retreat.
        local leech_needs_lane = false
        -- Any weapon can spend shots into cover. After four seconds without
        -- changing target HP, reposition perpendicular and reacquire.
        -- Folding Stars are intentionally invulnerable while expanded. Route
        -- around their echoes without filling the entity pool with doomed shots;
        -- resume attacks as soon as the bright contracted core returns.
        if target.giant == 0 and target.kind ~= 13
            and ((math.abs(dx) <= 8 and math.abs(dy) <= 8)
                or (CLASS == 1 and math.abs(dx) <= 16 and math.abs(dy) <= 16)) then
            -- A fast chaser can overlap the hero's 16px body after a
            -- knockback even when their origins occupy adjacent 8px cells.
            -- Cardinal fire then has no meaningful safe lane, and an edge
            -- pocket can turn the ordinary orbit choice into a permanent
            -- wall press. First take one collision-valid lane out of the
            -- shared body, then resume the enemy-specific policy. The broader
            -- adjacent-cell check is Sauran-only: ranged Corvin can still
            -- attack safely from that distance and loses its boss route if
            -- ordinary near-lane frames are misclassified as a body pin.
            keys = quintra_body_overlap_escape(px, py, target.x, target.y)
        elseif target.kind == 11 then
            local star_range = held_style == "spear" and 88
                or held_style == "flail" and 56
                or held_style == "lunge" and 52
                or held_style == "claw" and 64 or 150
            local star_step, star_ready = fold_star_pixel_step(
                room, px, py, target.x, target.y, aim, star_range)
            if waiting_star then
                -- Reposition through real pixel collision while the diffuse
                -- form is invulnerable. Once a valid lane is ready, orbit
                -- without wasting attacks until the bright core contracts.
                keys = star_ready
                    and giant_orbit_step(px, py, aim, move) or star_step
                no_damage_frames = 0
            else
                keys = star_ready and (KEY_A + star_step) or star_step
            end
        elseif target.kind == 12 then
            -- A Flutterbat may share the agent's nominal 8px tile while
            -- remaining several pixels diagonal from its cardinal shot lane.
            -- Align to its *live* pixel lane, then attack.  The old branch
            -- always sidestepped inside 16px—even after alignment—so a
            -- Wolfkin could orbit a 4-HP Keese forever without swinging.
            local bat_range = math.max(math.abs(dx), math.abs(dy))
            local bat_offaxis = (aim == KEY_UP or aim == KEY_DOWN)
                and math.abs(dx) or math.abs(dy)
            if CLASS == 4 and held_style == "lunge" then
                if bat_range <= 52 and bat_offaxis <= 5
                    and projectile_lane_clear(px, py, target.x, target.y, aim) then
                    keys = KEY_A + aim
                else
                    local route = target_step(px, py, target.x, target.y, aim, 0)
                    if not can_step(px, py, route) then
                        -- A hovering bat directly across a wall can make the
                        -- closest body-valid BFS cell be our current cell.
                        -- Commit to the nearer outer opening instead of
                        -- alternating before reaching either side.
                        local outward = px >= 72 and KEY_RIGHT or KEY_LEFT
                        local opposite = outward == KEY_RIGHT and KEY_LEFT or KEY_RIGHT
                        route = can_step(px, py, outward) and outward
                            or (can_step(px, py, opposite) and opposite or route)
                    end
                    keys = KEY_A + route
                end
            elseif bat_range <= 28 and bat_offaxis > 4 then
                -- Finish the final perpendicular pixels before committing a
                -- cardinal contact arc. This avoids a diagonal miss without
                -- forcing the target into a static/unsafe orbit.
                if aim == KEY_UP or aim == KEY_DOWN then
                    keys = dx > 0 and KEY_RIGHT or KEY_LEFT
                else
                    keys = dy > 0 and KEY_DOWN or KEY_UP
                end
            elseif bat_range <= 24 then
                keys = KEY_A + aim
            else
                -- Keep A held during the chase as well. For Wolfkin this
                -- arms the real 20-frame Max Strike gap-closer once the BFS
                -- finds a lane; for the other kits it is simply normal held
                -- fire while approaching a moving Keese.
                keys = KEY_A + target_step(px, py, target.x, target.y, aim, routed_reach)
            end
        elseif target.kind == 13 and (
            (held_style == "claw" and CLASS == 0
                and math.max(math.abs(dx), math.abs(dy)) <= 64)
            or (math.abs(dx) <= 24 and math.abs(dy) <= 24)) then
            -- Gloom Leeches can cling to the top or side wall while their
            -- 8px body is a couple of pixels off the champion's cardinal
            -- firing line. Wolfkin's Fang Stab owns a 64px physical lane, so
            -- a clear cardinal Leech need not pull him beneath a wall and
            -- into attachment range before the controller commits. At close
            -- range a generic Stinger retreat can
            -- repeatedly skim the edge forever. Align tightly first, then
            -- fire; an actually attached Leech still triggers the dash-shake
            -- override later in this controller frame.
            local leech_lane = projectile_lane_clear(px, py, target.x, target.y, aim)
            local leech_range = math.max(math.abs(dx), math.abs(dy))
            if DEBUG and frames % 120 == 0 then
                debug_log(string.format(
                    "BOTLEECH f=%d pos=%d,%d target=%d,%d d=%d,%d aim=%02X range=%d lane=%d",
                    frames, px, py, target.x, target.y, dx, dy, aim,
                    leech_range, leech_lane and 1 or 0))
            end
            -- Tail Spike can reach well beyond the contact box. Do not make
            -- Sauran walk into a perfectly straight Leech lane just to align
            -- again: the old policy maintained a 16px panic gap forever and
            -- never issued an A press, despite the 48px lunge being able to
            -- finish the fight safely from here.
            if CLASS == 1 and held_style == "lunge" and leech_lane
                and leech_range > 8 then
                keys = KEY_A + aim
            elseif not leech_lane then
                -- A Leech can cross an 8px opening that a 12px champion
                -- cannot shoot through. Ask the same body-valid BFS used by
                -- every other short weapon for a cardinal lane around that
                -- fixture instead of repeatedly slashing the wall.
                leech_needs_lane = true
                keys = target_step(px, py, target.x, target.y, aim, 6)
            elseif CLASS == 4 and active_charge == 0 and mp >= 2 then
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
        elseif CLASS == 3 and room == 50 and target.kind == 0
            and (target.x <= 8 or target.y <= 8
                or target.x >= 136 or target.y >= 112) then
            -- In the final Sigil room a small crawler can legally hug the
            -- one-tile edge band, where Picsean's cardinal BubbleBolt cannot
            -- always share its exact pixel lane. Tidal Wave is the authored
            -- three-lane answer; first route toward a reachable proxy on the
            -- hero's own row so the impossible edge cell cannot poison BFS,
            -- then cast inside the real long lane. Keep this narrowly on the
            -- replayed fixture so unrelated fights retain their policy.
            if math.abs(target.x - px) > 80 then
                keys = target_step(px, py, target.x, py, 0, 6)
            elseif active_charge == 0 and mp >= 2 then
                keys = KEY_B + aim
            else
                keys = aim
            end
        elseif target.kind == 24 and CLASS == 3 then
            -- Sunwheels orbit perpendicular to a narrow Astral Spear lane.
            -- On Picsean, use the authored three-lane Tidal Wave whenever its
            -- real MP/cooldown permits; between casts keep A armed while
            -- pursuing. This is the natural wide-shot answer to a target
            -- that can sidestep a single committed thrust in flight.
            if active_charge == 0 and mp >= 2 then
                keys = KEY_B + aim
            else
                keys = KEY_A + target_step(px, py, target.x, target.y, aim,
                    routed_reach)
            end
        elseif target.kind == 10 then
            -- Sentries do not chase. The generic ranged orbit therefore
            -- keeps a champion circling the same blocked corner forever
            -- while the turret remains on the other side of cover. Route to
            -- a real cardinal shot lane, then hold it at a six-tile safe
            -- standoff; this is exactly the lane-reading behavior the Frost
            -- hazard is intended to teach a player.
            local sentry_step, sentry_ready = fold_star_pixel_step(
                room, px, py, target.x, target.y, aim, 52)
            keys = sentry_ready and (KEY_A + sentry_step) or sentry_step
        elseif target.kind == 17 then
            if held_style ~= "claw" then
                local spore_range = held_style == "spear" and 90
                    or held_style == "flail" and 55
                    or held_style == "lunge" and 52 or 160
                if no_damage_frames > 240 then
                    -- A pixel-perfect mine-safe route can oscillate around
                    -- generated cover without ever exposing a firing lane.
                    -- Break it only after four seconds of unchanged HP, then
                    -- retry safety once the bounded body-valid reroute ends.
                    no_damage_frames, spore_pressure_timer = 0, 180
                    spore_pixel_route = nil
                end
                if spore_pressure_timer > 0 then
                    spore_pressure_timer = spore_pressure_timer - 1
                    keys = quintra_spore_pressure_keys(
                        room, px, py, target, aim, routed_reach)
                else
                    local spore_step, spore_ready = spore_pixel_step(
                        room, px, py, target.x, target.y, aim, spore_range)
                    -- Do not spend a shot while walking into a lane: the D-pad
                    -- steers both motion and aim, so a route's sideways step used
                    -- to fire past the mine. This applies to swapped long weapons
                    -- too: Tail Spike and Flail can punish from outside the fuse,
                    -- while the true-melee Claw still takes the post-blast route.
                    keys = spore_ready and (KEY_A + spore_step) or spore_step
                end
            else
                keys = spore_safe_step(px, py, target.x, target.y, KEY_A + aim)
            end
        elseif target.kind == 1 and target.giant == 0
            and held_style == "lunge" and py < 8 and target.y <= 16
            and math.abs(dx) > 20 and can_step(px, py, KEY_DOWN) then
            -- A required Sentinel can settle into the top strip while the
            -- Sauran pilot's sprite is at y=0.  Tail Spike originates six
            -- pixels above the feet box, so its otherwise-valid horizontal
            -- lane is still embedded in the ceiling tile.  The coarse body
            -- BFS used to answer UP forever from that legal feet position.
            -- Expose the real weapon origin with ordinary downward input,
            -- then let the normal 48px lunge policy resume.
            keys = KEY_DOWN
        elseif target.kind == 16 then
            -- Mirror Moths need an explicit pursuit lane for every kit.
            -- Mirror Moths move opposite the hero's last cardinal input.
            -- They only step every third tick, so sustained pursuit closes
            -- the gap despite that reflection. Their slow bolt is the real
            -- trap: ordinary dodge input repeatedly abandons the pursuit and
            -- leaves either a short weapon or cardinal projectile outside its
            -- lane. Hold the body-valid chase until the real held weapon has
            -- a cardinal shot.
            local adx, ady = math.abs(dx), math.abs(dy)
            local reach = adx > ady and adx or ady
            local offaxis = (aim == KEY_UP or aim == KEY_DOWN) and adx or ady
            local mirror_range = held_style == "spear" and 88
                or held_style == "lunge" and 52
                or held_style == "flail" and 56
                or held_style == "ranged" and 140 or 60
            if reach <= mirror_range and offaxis <= 5
                and projectile_lane_clear(px, py, target.x, target.y, aim) then
                keys = KEY_A + aim
            else
                -- Keep A armed during pursuit. Because the Moth reverses each
                -- movement sample, a body-valid route crosses a usable lane
                -- only briefly; waiting to add A until the prior frame was
                -- already aligned can miss that window forever, especially
                -- with a traded Flail's 36-frame cadence.
                keys = KEY_A + target_step(px, py, target.x, target.y, aim,
                    routed_reach)
            end
        -- Giants own a distinct spacing/readability policy. Do not let the
        -- generic unchanged-HP cover recovery steal their turns: a mobile
        -- boss can legitimately move through an obstructed lane for more
        -- than four seconds, and then needs to resume its live orbit/pulse
        -- logic rather than be mistaken for an ordinary stuck caster.
        elseif target.kind == 1 and target.giant ~= 0 then
            keys = quintra_giant_combat_keys(target, dx, dy, aim, held_style,
                frames, px, py)
        elseif flank_timer > 0 then
            -- A blind perpendicular strafe or tile-coarse endpoint can circle
            -- a U-shaped court forever. After a measured no-damage stall,
            -- use the same exact feet-box firing-lane search that resolves
            -- Folding Stars and sentries. This remains ordinary movement and
            -- attack input; it merely walks through the actual opening.
            local recovery_range = held_style == "ranged" and 140
                or held_style == "spear" and 88
                or held_style == "claw" and 64
                or held_style == "flail" and 56 or 52
            local recovery_step, recovery_ready = fold_star_pixel_step(
                room, px, py, target.x, target.y, aim, recovery_range)
            keys = recovery_ready
                and (KEY_A + recovery_step) or recovery_step
            flank_timer = flank_timer - 1
        elseif no_damage_frames > 240 then
            flank_timer, no_damage_frames = 240, 0
            local route = target_step(px, py, target.x, target.y, aim, routed_reach)
            if route == aim and not projectile_lane_clear(px, py, target.x, target.y, aim) then
                keys = cover_recovery_step(px, py, aim, math.floor(frames / 60))
            else
                keys = route + KEY_A
            end
        -- Sauran's Tail Spike and Vespine's Stinger are 48px lunges, not
        -- Wolfkin's adjacent claw. Treating all three as true melee walked
        -- these kits into contact damage and understated them. Hold a clear
        -- firing lane, dart back only when crowded, and fire the other beats.
        elseif held_style == "lunge" or held_style == "flail" or held_style == "spear" then
            local adx, ady = math.abs(dx), math.abs(dy)
            local reach = (adx > ady) and adx or ady
            local offaxis = (aim == KEY_UP or aim == KEY_DOWN) and adx or ady
            local near_range = held_style == "spear" and 36 or 28
            local fire_range = held_style == "spear" and 80 or 52
            local weapon_endpoint = routed_reach
            if not projectile_lane_clear(px, py, target.x, target.y, aim) then
                -- A Zelda-style feet box may let the hero stand below a wall
                -- while their weapon's origin is still inside it.  A coarse
                -- tile BFS can then repeatedly choose a nominally adjacent
                -- cell whose first pixel is blocked by the same pillar. The
                -- cheap tile route handles moving enemies; only after two
                -- seconds of unchanged HP do we pay for the exact feet-box
                -- search proven against Folding Stars. Rebuilding a 160x121
                -- pixel graph for every moving target would make long-form
                -- verification needlessly slower without changing play.
                if no_damage_frames > 120 then
                    local lane_step, lane_ready = fold_star_pixel_step(
                        room, px, py, target.x, target.y, aim, fire_range)
                    keys = lane_ready and (KEY_A + lane_step) or lane_step
                else
                    keys = target_step(px, py, target.x, target.y, aim, weapon_endpoint)
                end
            elseif CLASS == 0 and held_style == "lunge"
                and reach <= fire_range and offaxis > 5 and offaxis <= 12 then
                -- `target_step` deliberately works in 8px cells. Near an
                -- outer wall, a lunge can share that cell with a Wisp yet
                -- still miss by a full 11px. Finish the last perpendicular
                -- alignment in pixels before trusting the physical strike.
                if aim == KEY_UP or aim == KEY_DOWN then
                    keys = dx > 0 and KEY_RIGHT or KEY_LEFT
                else
                    keys = dy > 0 and KEY_DOWN or KEY_UP
                end
            elseif reach <= fire_range and offaxis > 5 then
                keys = target_step(px, py, target.x, target.y, aim, weapon_endpoint)
            elseif reach <= near_range then
                local retreat = (aim == KEY_UP and KEY_DOWN)
                    or (aim == KEY_DOWN and KEY_UP)
                    or (aim == KEY_LEFT and KEY_RIGHT) or KEY_LEFT
                keys = (frames % 3 == 0) and retreat or (KEY_A + aim)
            elseif reach <= fire_range then
                keys = KEY_A + aim
            else
                keys = KEY_A + target_step(px, py, target.x, target.y, aim, weapon_endpoint)
            end
        -- Claw Combo remains the roster's true melee weapon, but Wolfkin's
        -- current Fang form starts at the weapon edge and carries through a
        -- real 64px lane. Use that cardinal line when it is clear;
        -- the closer legacy claw forms still close to their adjacent swing
        -- geometry. This avoids teaching the pilot to absorb contact from a
        -- Skeleton simply because the weapon's newly visible thrust is longer.
        elseif held_style == "claw" then
            local claw_range = CLASS == 0 and 64 or 24
            if math.max(math.abs(dx), math.abs(dy)) <= claw_range
                and projectile_lane_clear(px, py, target.x, target.y, aim) then
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
            -- A roaming caster behind procgen cover is the inverse problem:
            -- the old perpendicular orbit can keep pressing into one wall
            -- while the target drifts along another, even though a valid
            -- body route to a cardinal bubble lane exists.  Route only the
            -- ranged-caster family to that lane; chasers retain their more
            -- responsive close-orbit behavior.
            local lane_caster = target.kind == 5 or target.kind == 8
                or target.kind == 19 or target.kind == 20 or target.kind == 21
                -- Dusk Midges are fast harriers, not cover-bound casters.
                -- Replanning a full BFS against their every drift spends no
                -- attack frames and lets a ten-HP foe own a room forever.
                -- Keep their fight on the responsive orbit/fire branch.
                or target.kind == 25
            if held_style == "ranged" and lane_caster
                and not projectile_lane_clear(px, py, target.x, target.y, aim) then
                keys = target_step(px, py, target.x, target.y, aim, 6)
            elseif math.abs(dx) <= 32 and math.abs(dy) <= 32
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
        -- A human can feel when a small hostile has entered their hurtbox;
        -- the old pilot only had projectile avoidance and therefore let the
        -- Tail Spike/Stinger kits repeatedly trade contact at point blank.
        -- Physical builds need a body buffer; Corvin retains its measured
        -- ranged panic behavior. This is read-only controller policy, not a
        -- cartridge-side damage or immunity adjustment.
        if target.giant == 0 and not waiting_star then
            local body_range = math.max(math.abs(dx), math.abs(dy))
            local panic_range = held_style == "claw" and 12
                -- Preserve the measured Sauran/Vespine body buffer; this
                -- wider lane is for Wolfkin only after a lunge-weapon swap.
                or (held_style == "lunge" and CLASS == 0) and 24
                -- Stinger's 48px reach must hold its firing lane against a
                -- charging Rope. Its matched seed clears four bosses alive
                -- at zero panic retreat; the generic 16px retreat walks
                -- back into the Rope's reacquisition loop.
                or (held_style == "lunge" and CLASS == 4) and 0
                -- Tail Spike has the same 48px physical lane. Sauran's
                -- generic close-body buffer is useful against most enemies,
                -- but against a Rope it repeatedly retreats out of the one
                -- clean cardinal shot line and can turn the room into a
                -- multi-thousand-frame controller stall. Hold the authored
                -- lunge lane for this specific charger instead.
                or (held_style == "lunge" and CLASS == 1 and target.kind == 9) and 0
                -- Tail Spike retains its separately measured 16px buffer.
                -- Explicit experiments may still override it on matched seeds.
                or (held_style == "lunge" and LUNGE_PANIC_RANGE > 0)
                    and LUNGE_PANIC_RANGE
                or held_style == "flail" and 24
                or held_style == "spear" and 32
                or (CLASS == 2 and 24 or 0)
            local contact_strike_lane = projectile_lane_clear(px, py, target.x, target.y, aim)
                and ((target.kind == 13 and held_style == "lunge" and body_range > 8)
                    -- Wolfkin's contact arc reaches the Leech safely from
                    -- this narrow 8..16px cardinal lane.  Without the
                    -- exception the generic claw panic rule replaced every
                    -- upward/downward hit with a retreat aimed away from the
                    -- target, producing a permanent no-damage loop.  Stay
                    -- conservative at <=8px, where an attachment/body trade
                    -- is the real threat.
                    or (target.kind == 13 and held_style == "claw"
                        and body_range > 8 and body_range <= 16)
                    -- Keese-like Flutterbats are only granted this exception
                    -- after the branch above achieved a real cardinal lane.
                    -- At <=8px the normal retreat still wins.
                    or (target.kind == 12 and held_style == "claw"
                        and body_range > 8 and body_range <= 16))
            if panic_range > 0 and body_range <= panic_range
                and not contact_strike_lane
                and not leech_needs_lane then
                local retreat = (aim == KEY_UP and KEY_DOWN)
                    or (aim == KEY_DOWN and KEY_UP)
                    or (aim == KEY_LEFT and KEY_RIGHT) or KEY_LEFT
                local side_a = (retreat == KEY_UP or retreat == KEY_DOWN)
                    and KEY_LEFT or KEY_UP
                local side_b = (side_a == KEY_LEFT) and KEY_RIGHT
                    or (side_a == KEY_RIGHT) and KEY_LEFT
                    or (side_a == KEY_UP) and KEY_DOWN or KEY_UP
                if can_step(px, py, retreat) then
                    keys = KEY_A + retreat
                elseif can_step(px, py, side_a) then
                    keys = KEY_A + side_a
                elseif can_step(px, py, side_b) then
                    keys = KEY_A + side_b
                end
            end
        end
        -- Sample the local projectile danger once; the later dodge pass
        -- reuses this observation instead of sampling a different frame.
        local threat = nil
        if not target or target.kind ~= 10
            and target.kind ~= 16 then
            threat = projectile_threat(px, py)
        end
        observed_threat = threat
        keys = quintra_signature_keys(keys, target, aim, dx, dy, mp, mp_max,
            active_charge, waiting_star, frames, px, py, hp, threat)
        -- Ordinary dungeon encounters are deliberately not all arena locks.
        -- Any champion can spend minutes pursuing a self-splitting Ooze or a
        -- fast flyer in a room whose forward door is already open. After a
        -- real six-second no-damage observation, take that authored exit
        -- rather than incorrectly turning optional combat into a progression
        -- requirement. The required Sigil room (2), miniboss (3), shop/rest
        -- choices, bosses, and towns remain under their normal objective
        -- policy.
        optional_local_room = dungeon_local(room, emu:read8(RS + 11))
        optional_room_is_town = is_town_room(room)
        optional_stage_size = dungeon_size(emu:read8(RS + 11))
        optional_open_room = target.giant == 0
            and world_mode == 0 and not optional_room_is_town
            and not (SEALED ~= 0 and emu:read8(SEALED) ~= 0)
            -- Open doors mean exactly what they show. Preserve the authored
        -- room-3 Warden, late Waystone/deep Warden, shop, sanctuary, and
        -- giant objectives; every
            -- other unsealed combat room may be yielded after a measured
            -- no-damage stall. This keeps the new two-fixture critical route
            -- meaningful without turning the expanded dungeon into a hidden
            -- kill-everything corridor.
            and (optional_local_room ~= 3 or not stage_warden_missing())
            and (optional_local_room ~= 7 or not stage_waystone_missing())
            and (optional_local_room ~= 9 or not stage_deep_warden_missing())
            and optional_local_room ~= (optional_stage_size - 3)
            and optional_local_room ~= (optional_stage_size - 2)
            and (optional_local_room ~= 2 or not stage_sigil_missing())
        -- The opening room is optional. The two fragile short-range kits
        -- preserve the run after one lost heart instead of trading required-
        -- room health for loose drops. In room 1, however, yielding beside a
        -- charging Rope can leave its live body between the pilot and door;
        -- fight there unless the ordinary no-damage stall rule fires. The
        -- other kits retain their profitable optional fights throughout.
        local opening_damage_bailout = (CLASS == 0 or CLASS == 4)
            and optional_local_room == 0
            and room_age > 180 and hp <= hp_max - 2
        if optional_open_room and (target_stall_frames > 360
                or opening_damage_bailout) then
            keys = door_step(px, py) + KEY_A
            optional_exit = true
            if DEBUG and (target_stall_frames == 361 or opening_damage_bailout) then
                debug_log(string.format(
                    "BOTEXIT f=%d room=%d enemy=%d hp=%d reason=%s",
                    frames, room, target.kind, target.hp,
                    target_stall_frames > 360 and "stalled" or "damage"))
            end
        end
    -- Shops are optional recovery/build choices. Wolfkin gets a generous
    -- ten-second body-valid approach, then yields to the route if it cannot
    -- buy; other champions retain their separately validated shop policies.
    elseif shop then
        local dx, dy = shop.x - px, shop.y - py
        local direct
        if math.abs(dx) > math.abs(dy) then
            direct = dx > 0 and KEY_RIGHT or KEY_LEFT
        else
            direct = dy > 0 and KEY_DOWN or KEY_UP
        end
        if is_town_room(room) and emu:read8(RS + 19) == 1 then
            -- Market wares share one long counter row, and every sale is a
            -- walk-into interaction. Reach the chosen shelf through the
            -- clear upper aisle before descending at its own x-coordinate;
            -- a shortest tile path can otherwise cross and auto-buy the
            -- intervening weapon trade.
            local approach_x = shop.x - 8
            if px == approach_x then
                -- Once aligned with the selected shelf, keep descending
                -- through its interaction edge. Re-centering y first on
                -- every frame creates a 52/53 oscillation and never buys.
                keys = KEY_DOWN
            elseif py < 52 then keys = KEY_DOWN
            elseif py > 52 then keys = KEY_UP
            elseif px < approach_x then keys = KEY_RIGHT
            else keys = KEY_LEFT end
        else
            -- A shop ware occupies its own tile and sells through the
            -- cartridge's wide walk-into overlap. Route to the adjacent
            -- one-tile interaction lane, not onto the occupied sprite cell;
            -- the latter can leave the pilot scraping a counter forever even
            -- though the offer is valid.
            keys = target_step(px, py, shop.x, shop.y, direct,
                CLASS == 0 and 1 or 0)
        end
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
    if FINAL_EDGE_RECOVERY and world_mode == 0 and emu:read8(RS + 11) == 8
        and not target and not loot and not shop and px >= 128 then
        keys = KEY_LEFT
    end
    if optional_exit then
        -- The exit has already been selected with the live board's body-aware
        -- `door_step`.  Do not let combat-only unstick, body-dash, or border
        -- guards turn back toward an enemy that the cartridge does not require
        -- the player to kill. This is ordinary controller input policy only.
        target, observed_threat = nil, nil
        dodge_phase, body_dash_ready = 0, false
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
            -- Prefer the graph-aware exit step over a local flee.  It has
            -- already selected and centered the actual door; a raw "away"
            -- move can keep the pilot in the enemy's lane forever instead
            -- of ending this optional encounter by crossing the boundary.
            local route = door_step(px, py)
            if route ~= 0 and can_step(px, py, route) then flee = route end
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
    if sigil_pixel_active then
        -- The mandatory Sigil uses a one-pixel, full-body route that is
        -- rebuilt from the live position whenever movement skips a cached
        -- node. Generic thirty-frame "combat" escapes treated its brief
        -- collision alignment pauses as a stall and repeatedly kicked the
        -- pilot off that proven route—most visibly into a stage-three spike
        -- loop. Let the exact objective route retain input priority.
        escape_timer = 0
        still_frames = 0
    elseif escape_timer == 0 and still_frames > stuck_limit then
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
    if escape_timer > 0 and not sigil_pixel_active then
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
    -- `loot` may deliberately clear a live target when a wounded pilot can
    -- collect a visible heart.  The hit observer above can still have armed
    -- a body dash from that target on the same frame, so require the current
    -- combat target here rather than dereferencing the stale observation.
    -- The pickup remains the correct priority and the next close body hit
    -- will arm another ordinary dash; most importantly, the controller must
    -- never abort a certification run on this valid state transition.
    if body_dash_ready and target and world_mode == 0 and dodge_phase == 0 then
        local dx, dy = px - target.x, py - target.y
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
        if target.giant ~= 0 then
            dodge_dir = quintra_giant_body_dash_dir(px, py, target, dodge_dir)
        end
        dodge_phase, dodge_count = 1, dodge_count + 1
        body_dash_frames, body_dash_source = 0, 255
        if DEBUG then
            debug_log(string.format(
                "BOTBODYDASH f=%d room=%d pos=%d,%d target=%d@%d,%d dir=%02X",
                frames, room, px, py, target.kind, target.x, target.y, dodge_dir))
        end
    elseif ABILITY_POLICY == "smart" and CLASS == 3 and world_body_close
        and world_contact_hits < 2
        and active_charge == 0 and mp >= 2 then
        keys = KEY_B
        world_guard_requested = true
        dodge_phase, dodge_cooldown = 0, 30
    elseif ABILITY_POLICY == "smart" and CLASS == 1
        and observed_threat and active_charge == 0 and mp >= 2 then
        keys = KEY_B
        dodge_phase, dodge_cooldown = 0, 30
    elseif ABILITY_POLICY == "smart" and CLASS == 3 and observed_threat
        -- Undertow handles a broad nearby warning.  Once the read-only
        -- collision predictor says the six-pixel hero box will actually be
        -- hit, preserve the real double-tap dodge below instead of consuming
        -- the barrier and hiding that response from the trace/RL dataset.
        and observed_threat.hit_in == nil and active_charge == 0 and mp >= 2 then
        keys = KEY_B
        dodge_phase, dodge_cooldown = 0, 30
    elseif dodge_phase == 0 and dodge_cooldown == 0 and observed_threat
        -- Picsean's broad proximity signal is useful for the wave's barrier,
        -- but a double-tap should be reserved for an actual incoming lane.
        -- Other kits retain their established proximity policy.
        and (CLASS ~= 3 or observed_threat.hit_in ~= nil) then
        dodge_dir = quintra_projectile_dash_dir(px, py,
            observed_threat.x, observed_threat.y)
        -- The room-three Sentinel can chase a slow Tail Spike user all the
        -- way to a north wall.  A projectile below the hero then correctly
        -- reads as an upward threat, but UP is no longer an escape: it feeds
        -- the hero into the wall and the large body can re-contact every
        -- iframe cycle.  Preserve the bullet dodge as a legal lateral step
        -- in that exact sealed, boss-below geometry.  This is not a global
        -- edge rule—ordinary rooms and other projectile lanes retain their
        -- closest-away direction.
        if CLASS == 1 and world_mode == 0
            and dungeon_local(room, emu:read8(RS + 11)) == 3
            and SEALED ~= 0 and emu:read8(SEALED) ~= 0
            and py <= 24 and target and target.y > py and dodge_dir == KEY_UP then
            local left_ok, right_ok = can_step(px, py, KEY_LEFT), can_step(px, py, KEY_RIGHT)
            if left_ok and right_ok then
                dodge_dir = (math.abs((px - 1) - observed_threat.x)
                    >= math.abs((px + 1) - observed_threat.x)) and KEY_LEFT or KEY_RIGHT
            elseif left_ok then
                dodge_dir = KEY_LEFT
            elseif right_ok then
                dodge_dir = KEY_RIGHT
            end
        end
        -- A boss's 32px visual pressure is a different hazard from an 8px
        -- bullet. When this opt-in research floor is active, do not let a
        -- bullet-only choice steer directly into the selected giant body.
        -- It evaluates only the next ordinary D-pad step and keeps the
        -- original dodge untouched whenever it already maintains clearance.
        if GIANT_DODGE_FLOOR > 0 and target and target.kind == 1
            and target.giant ~= 0 then
            local function giant_dodge_clearance(key)
                local nx = px + (key == KEY_RIGHT and 1 or key == KEY_LEFT and -1 or 0)
                local ny = py + (key == KEY_DOWN and 1 or key == KEY_UP and -1 or 0)
                return math.max(math.abs(nx - target.x), math.abs(ny - target.y))
            end
            if giant_dodge_clearance(dodge_dir) < GIANT_DODGE_FLOOR then
                local candidate, best = dodge_dir, giant_dodge_clearance(dodge_dir)
                for _, key in ipairs({KEY_UP, KEY_RIGHT, KEY_DOWN, KEY_LEFT}) do
                    local clear = giant_dodge_clearance(key)
                    if can_step(px, py, key) and clear > best then
                        candidate, best = key, clear
                    end
                end
                dodge_dir = candidate
            end
        end
        dodge_phase, dodge_count = 1, dodge_count + 1
        if DEBUG then
            debug_log(string.format(
                "BOTDODGE f=%d room=%d pos=%d,%d shot=%d,%d target=%s dir=%02X",
                frames, room, px, py, observed_threat.x, observed_threat.y,
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
    -- A covered Sentinel can remain close enough to keep producing harmless
    -- shots while the normal shield/dodge priority repeatedly interrupts the
    -- body-valid route that the no-damage watchdog already chose. Once that
    -- watchdog has proved the lane is stale, commit a short-weapon Sauran to
    -- the ordinary A+BFS inputs until it either reconnects or changes HP.
    -- This is deliberately limited to the required Sentinel, never a giant,
    -- and never rewrites game state.
    if target and CLASS == 1 and target.kind == 1 and target.giant == 0
        and flank_timer > 0 then
        if py < 8 and target.y <= 16 and math.abs(target.x - px) > 20
            and can_step(px, py, KEY_DOWN) then
            -- Preserve the ceiling-lane correction above after the watchdog
            -- has armed.  This recovery block otherwise recomputed the same
            -- coarse UP route and overwrote the deliberate inward step.
            keys = KEY_DOWN
        else
            keys = KEY_A + target_step(px, py, target.x, target.y, 0, 6)
        end
        dodge_phase = 0
    end
    -- Gloom Leeches are intentionally shaken loose by a double-tap dash.
    -- Exercise that public controller mechanic instead of letting a latched
    -- enemy bias melee samples when its body overlaps nearby terrain.
    if leech_attached() or shake_phase ~= 0 then
        if shake_phase == 0 then
            -- Preserve the established rightward shake for every champion's
            -- paired replay. Picsean alone has the measured edge-latch
            -- failure: only after her first dash fails to detach the leech
            -- does she choose a walkable double-tap direction.
            shake_dir = (CLASS == 3 and shake_cycle ~= 0)
                and quintra_leech_shake_dir(px, py, shake_cycle - 1)
                or KEY_RIGHT
            keys, shake_phase = shake_dir, 1
        elseif shake_phase == 1 then keys, shake_phase = shake_dir, 2
        elseif shake_phase == 2 then keys, shake_phase = 0, 3
        elseif shake_phase == 3 then keys, shake_phase = 0, 4
        elseif shake_phase == 4 then keys, shake_phase = shake_dir, 5
        elseif shake_phase == 5 then keys, shake_phase = shake_dir, 6
        elseif shake_phase == 6 then keys, shake_phase = 0, 7
        else
            keys, shake_phase = 0, 0
            shake_cycle = shake_cycle + 1
        end
    end
    -- Generic unstick/dodge recovery is useful in a sealed dungeon room, but
    -- must not erase a real Riftwild body-avoidance decision. Reapply the
    -- collision-checked flee step immediately before the world-edge guard.
    if world_flee ~= 0 and not world_guard_requested and not world_blocker then
        keys = world_flee + KEY_A
    end
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
    -- A small hostile can share the outer sprite strip while the champion's
    -- feet are clipped against the screen border. Cardinal aim then points
    -- along the wall and a short melee weapon repeatedly spends its attack
    -- into the boundary. Step one body-width inward before resuming combat;
    -- this is normal D-pad play and applies only when both bodies are in the
    -- same champion-width edge strip, never during an ordinary doorway
    -- crossing.
    -- A Gloam Leech can latch while the champion is pinned against a room
    -- edge.  Its authored escape is the double-tap dash assembled above.
    -- Do not let this generic "step inward" cosmetic-safety rule consume
    -- either press of that sequence: it used to leave close-range champions
    -- permanently latched at the north wall, making their balance sample a
    -- controller artifact rather than a real encounter result.
    if target and world_mode == 0 and shake_phase == 0 and not leech_attached()
        -- The required room-three Sentinel is 32x32, not a small hostile.
        -- At the north edge its valid vulnerable body extends down into the
        -- arena. The old generic nudge replaced every Sauran/Corvin attack
        -- with DOWN, letting the Sentinel's own contact push return them to
        -- y=0 forever. Preserve their real attack/BFS policy for this body.
        and not (target.kind == 1 and target.giant == 0) then
        if py <= 12 and target.y <= 12 then
            keys = KEY_DOWN
        elseif py >= 116 and target.y >= 116 then
            keys = KEY_UP
        elseif px <= 12 and target.x <= 12 then
            keys = KEY_RIGHT
        elseif px >= 132 and target.x >= 132
            -- A stationary Mire Spore can own a valid vertical shot/trigger
            -- lane in this strip. Forcing LEFT every frame erases that
            -- authored arm-retreat-punish route and pins the pilot forever.
            and target.kind ~= 17
            -- Tail Spike already has a valid vertical 48px lane here. The
            -- generic inward nudge would otherwise replace its attack with
            -- LEFT forever just because both sprites share the right strip.
            and not (CLASS == 1 and held_style == "lunge"
                and math.abs(target.y - py) > 8) then
            keys = KEY_LEFT
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
    -- An expanded Fold Star is a temporary positioning lesson, not a target
    -- to face-tank while a nearby Bomber/Leech owns the normal selection.
    -- Preserve an already-committed dodge; otherwise take the legal outward
    -- step and resume ordinary targeting once the core contracts.
    fold_guard_keys = world_mode == 0 and dodge_phase == 0
        and fold_star_guard(px, py) or nil
    if fold_guard_keys ~= nil then keys = fold_guard_keys end
    -- This final override comes after generic bullet dodges and unsticks so a
    -- one-frame evasive input cannot erase the final boss's only safe route.
    -- It applies to this specific announced phase, never to ordinary bosses.
    local collapse_keys = void_safe_pocket_step(px, py, target)
    if collapse_keys ~= nil then keys = collapse_keys end
    -- Sealed encounters deliberately leave the return door usable for a
    -- human who chooses to retreat, but an automated combat pilot must not
    -- let a recovery frame abandon a live miniboss and reset its progress.
    -- Restrict this to the dedicated local-room-three miniboss: normal rooms,
    -- bosses, and all player-facing door routing retain their authored rules.
    if world_mode == 0
        and dungeon_local(room, emu:read8(RS + 11)) == 3
        and SEALED ~= 0 and emu:read8(SEALED) ~= 0 then
        local entered = emu:read8(RS + 6)
        local back = entered ~= 255 and ((entered + 2) % 4) or 255
        local has = function(key) return math.floor(keys / key) % 2 == 1 end
        -- A pressed attack/recovery can preserve a few prior movement frames,
        -- so steer away from the return edge before the literal doorway lip.
        -- This is deliberately controller-only: humans retain their authored
        -- option to retreat from a sealed room.
        if back == 0 and py <= 32 and has(KEY_UP) then
            keys = keys - KEY_UP + KEY_DOWN
        elseif back == 1 and px >= 120 and has(KEY_RIGHT) then
            keys = keys - KEY_RIGHT + KEY_LEFT
        elseif back == 2 and py >= 88 and has(KEY_DOWN) then
            keys = keys - KEY_DOWN + KEY_UP
        elseif back == 3 and px <= 24 and has(KEY_LEFT) then
            keys = keys - KEY_LEFT + KEY_RIGHT
        end
    end
    -- A is both the attack button and the explicit loose-orb confirmation.
    -- Suppress only that confirmation while overlapping *or about to enter*
    -- an orb's real wide pickup box. The three-pixel approach margin matters:
    -- input_pressed is sampled before the controller can observe the next
    -- feet-box position, so waiting for exact overlap can still accept an
    -- unwanted trade on the crossing frame. Keep movement and B intact—this
    -- is an input-safety rule, never a navigation or game-state rewrite.
    if keys % 2 == KEY_A and quintra_on_weapon_orb(px, py, 3) then
        keys = keys - KEY_A
    end
    -- A market weapon trade is contact-triggered, so suppressing A cannot
    -- protect a comparable-build replay. If any generic recovery movement
    -- approaches its real box, sidestep horizontally until the feet clear it;
    -- the next frame then resumes the ordinary target/door route.
    local move = direction_from_keys(keys)
    if move ~= 0 then
        local nx, ny = px, py
        if move == KEY_RIGHT then nx = nx + 1
        elseif move == KEY_LEFT then nx = nx - 1
        elseif move == KEY_DOWN then ny = ny + 1
        elseif move == KEY_UP then ny = ny - 1 end
        local weapon_x = quintra_weapon_shop_overlap(nx, ny, 3)
        if weapon_x ~= nil then
            local side = (px + 8 < weapon_x + 3) and KEY_LEFT or KEY_RIGHT
            if not can_step(px, py, side) then
                side = (side == KEY_LEFT) and KEY_RIGHT or KEY_LEFT
            end
            keys = keys % 16 + side
        end
    end
    if DEBUG and (frames % 600 == 0
        or (target and target.giant ~= 0 and frames % 60 == 0)) then
        -- World traversal deliberately clears `target` so combat does not
        -- become mandatory, but debug output still needs the nearest hostile
        -- to explain an overworld hit or an avoidance choice.
        local debug_target = target or overworld_threat
        debug_log(string.format("BOTDBG f=%d room=%d world=%d:%d sealed=%d hp=%d mp=%d ifr=%d charge=%d hitstop=%d face=%d acc=%d pos=%d:%02X,%d:%02X target=%s keys=%02X route=%02X routeok=%d",
            frames, room, world_mode, world_screen,
            SEALED ~= 0 and emu:read8(SEALED) or 0,
            hp, mp, iframes, active_charge,
            HITSTOP ~= 0 and emu:read8(HITSTOP) or 0,
            emu:read8(PL + 13), emu:read8(PL + 23),
            px, emu:read8(PL + 10), py, emu:read8(PL + 12),
            debug_target and string.format("enemy:%d@%d,%d hp=%d giant=%d pattern=%d state=%d clk=%d s6=%d stall=%d",
                debug_target.kind, debug_target.x, debug_target.y,
                debug_target.hp, debug_target.giant, debug_target.pattern or 255,
                debug_target.state, debug_target.clock, debug_target.state6,
                no_damage_frames)
                or (loot and string.format("loot:%d,%d", loot.x, loot.y)
                    or (shop and string.format("shop:%d,%d", shop.x, shop.y) or "door")), keys,
            target and target_step(px, py, target.x, target.y, 0,
                weapon_route_tiles(held_style)) or 0,
            target and can_step(px, py, target_step(px, py, target.x, target.y, 0,
                weapon_route_tiles(held_style))) and 1 or 0))
    end
    -- Preserve one collision-map artifact for every long live-enemy room,
    -- not only Mire Spore repros. This makes the CSV's combat-stall column
    -- actionable during unattended balance matrices. A requested screenshot
    -- is still captured on the same event, but the text map remains the
    -- reliable headless artifact.
    if (DEBUG or DEBUG_SCREEN) and (target or (DEBUG and room == 49))
        and debug_shot_room ~= room and frames - room_enter_frame > 3600 then
        if DEBUG then debug_tilemap(frames, room, px, py, target) end
        if DEBUG_SCREEN then
            emu:screenshot(string.format("%s-r%d.png", DEBUG_SCREEN, room))
        end
        debug_shot_room = room
    end
    observe_trace(frames, room, world_mode, world_screen, px, py, hp, hp_max,
        mp, mp_max, target, observed_threat, keys, room_age,
        equipped_weapon, active_charge, observed_shield_timer, iframes)
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
final_weapon = PL ~= 0 and emu:read8(PL + 21) or 255
local final_hp_max = death_hp_max ~= 0 and death_hp_max
    or (PL ~= 0 and emu:read8(PL + 1) or 0)
local final_mp_max = death_mp_max ~= 0 and death_mp_max
    or (PL ~= 0 and emu:read8(PL + 3) or 0)
local final_atk = death_atk ~= 0 and death_atk
    or (PL ~= 0 and emu:read8(PL + 5) or 0)
local final_def = death_def ~= 0 and death_def
    or (PL ~= 0 and emu:read8(PL + 6) or 0)
local final_spd = death_spd ~= 0 and death_spd
    or (PL ~= 0 and emu:read8(PL + 7) or 0)
local final_lck = death_lck ~= 0 and death_lck
    or (PL ~= 0 and emu:read8(PL + 8) or 0)
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
local seed = RUN_SEED_SNAPSHOT or 0
if seed == 0 and RS ~= 0 then
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
if OBS_TRACE_OUT then
    local of = io.open(OBS_TRACE_OUT, "w")
    if of then
        of:write("# quintra-observation-trace-v5\n")
        of:write("# frame,room,world_mode,world_screen,px,py,hp,hp_max,mp,mp_max,target_kind,target_hp,target_x,target_y,target_giant,target_pattern,threat,threat_hit_in,threat_x,threat_y,threat_vx,threat_vy,nearest_projectile_x,nearest_projectile_y,nearest_projectile_vx,nearest_projectile_vy,nearest_projectile_distance,keys,room_age,weapon,active_charge,shield_timer,iframes\n")
        for _, row in ipairs(obs_rows) do of:write(row .. "\n") end
        of:close()
    end
end
local f = io.open(OUT, "a")
if DEBUG then
    debug_log(string.format("BOTFINAL class=%d frames=%d out=%s open=%d",
        CLASS, frames, OUT, f and 1 or 0))
end
if f then
    f:write(string.format("%d,%d,%.0f,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
        RUN, CLASS, seed, frames, max_room, rooms_seen, clears, kills,
        bosses, damage_taken, giant_overlap_damage, enemy_seen.giant_close_frames, min_hp, final_x, final_y, final_world, final_screen,
        frames - room_enter_frame, max_combat_frames, max_combat_room,
        max_combat_enemy, max_target_stall_frames, max_target_stall_room,
        max_target_stall_enemy, max_route_frames, max_route_room,
        hostiles, last_enemy, death_source, towns_seen, world_hops,
        won, ui_screen, dodge_count, shop_visits, purchases, enemy_mask, min_giant_hp, b_uses,
        boss_attempts, boss_attempt_frames, boss_clear_frames,
        town_market_visits, town_quarter_visits, boss_clear_series,
        death_room, death_bosses, death_giant, death_giant_overlap,
        boss_relics_seen, boss_relics_collected, boss_relics_missed,
        final_weapon, weapon_swaps, final_hp_max, final_mp_max, final_atk,
        final_def, final_spd, final_lck))
    f:close()
    if DEBUG then debug_log(string.format("BOTCSV class=%d written", CLASS)) end
elseif DEBUG then
    debug_log(string.format("BOTCSVFAIL class=%d out=%s", CLASS, OUT))
end
console:log(string.format("BALANCE class=%d frames=%d room=%d clears=%d kills=%d bosses=%d hp=%d",
    CLASS, frames, max_room, clears, kills, bosses, hp))
-- The Qt frontend exposes quit(), while mgba-headless deliberately has no
-- frontend object.  The latter exits naturally once this script returns and
-- is substantially faster for controller-only balance certification.
if emu.frontend and emu.frontend.quit then emu.frontend:quit() end
