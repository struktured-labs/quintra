-- Human-skill model and per-stage balance observer for quintra_balance_bot.lua.
--
-- Loaded with dofile() by the controller only when QUINTRA_BOT_SKILL or
-- QUINTRA_STAGELOG_OUT is set, so every existing balance/endurance/replay
-- contract runs byte-identical input without it.
--
-- Two jobs, both host-side:
--   1. QH_FILTER(keys) degrades the pilot's chosen buttons the way a person's
--      hands do: late awareness of new shots (reaction delay), shots never
--      noticed (imperfect dodging), stale-input lapses, D-pad slips, aim
--      error on attack presses, dropped attack inputs, and think/orientation
--      pauses on room entry (longer in puzzle rooms). It only changes which
--      buttons are pressed. It never writes cartridge RAM, HP, RNG or timers.
--   2. QH_OBSERVE/QH_FINISH write one CSV row per stage reached: time, damage
--      taken vs dealt, burst damage, HP/MP/coin/stat/item snapshots, boss
--      time-to-kill, status-effect landings (during bosses / at low HP) and
--      which status, if any, preceded the death.
-- Randomness comes from a private xorshift seeded by (skill, run, class), so
-- a given ROM + seed is reproducible and the existing input trace replays it.

local SKILL_NAME = os.getenv("QUINTRA_BOT_SKILL") or "bot"
-- Frames at 60 Hz. Literature anchors: simple visual reaction ~250 ms, choice
-- reaction under load ~350-500 ms; casual players miss a large share of
-- off-focus projectiles. These are starting points calibrated by telemetry
-- (docs/superpowers/specs/2026-11-22-balance-harness.md).
QH_PROFILES = {
    skilled =   {reaction=15, miss=0.10, lapse=0.0015, lapse_len={6, 12},
                 slip=0.04, slip_len={2, 5}, aim=0.06, drop=0.03, drop_len={3, 6},
                 think={180, 600}, pause={6, 18}},
    average =   {reaction=21, miss=0.25, lapse=0.0035, lapse_len={10, 20},
                 slip=0.10, slip_len={3, 8}, aim=0.14, drop=0.08, drop_len={4, 10},
                 think={600, 1800}, pause={18, 45}},
    nonexpert = {reaction=27, miss=0.40, lapse=0.0060, lapse_len={15, 30},
                 slip=0.20, slip_len={4, 12}, aim=0.22, drop=0.15, drop_len={6, 14},
                 think={1200, 4500}, pause={30, 90}},
}
local P = QH_PROFILES[SKILL_NAME]
local KA, KB = 0x01, 0x02
local KR, KL, KU, KD = 0x10, 0x20, 0x40, 0x80
local DIRMASK = KR + KL + KU + KD
-- Button masks are 8 bits: A,B,SELECT,START low nibble, D-pad high nibble.
local function has(k, bit) return math.floor(k / bit) % 2 == 1 end
local function dirs_of(k) return k - k % 16 end
local function with_dirs(k, d) return k % 16 + d end
local function without_a(k) return has(k, KA) and k - KA or k end

local function noi_symbols(path)
    local syms = {}
    local f = path and io.open(path, "r")
    if not f then return syms end
    for line in f:lines() do
        local name, value = line:match("^DEF%s+(%S+)%s+0x(%x+)")
        if name then syms[name] = tonumber(value, 16) end
    end
    f:close()
    return syms
end
local SYMS = noi_symbols(os.getenv("QUINTRA_NOI_PATH"))
local Q_RS = tonumber(os.getenv("QUINTRA_RS_ADDR") or "0") or 0
local Q_PL = tonumber(os.getenv("QUINTRA_PL_ADDR") or "0") or 0
local Q_EN = tonumber(os.getenv("QUINTRA_EN_ADDR") or "0") or 0
local Q_LS = tonumber(os.getenv("QUINTRA_SCREEN_ADDR") or "0") or 0
local Q_STATUS = SYMS["_player_status_kind"] or 0
local Q_STATUS_TICKS = SYMS["_player_status_ticks"] or 0
local Q_PUZZLE_KIND = SYMS["_room_puzzle_kind"] or 0
local Q_PUZZLE_LOCKED = SYMS["_room_puzzle_locked"] or 0
local SKILL_ID = ({bot=0, skilled=1, average=2, nonexpert=3})[SKILL_NAME] or 9
local RUN_ID = tonumber(os.getenv("QUINTRA_BOT_RUN") or "0") or 0
local CLASS_ID = tonumber(os.getenv("QUINTRA_BOT_CLASS") or "0") or 0
local MODE = os.getenv("QUINTRA_BOT_MODE") or "full"
local STOP_AFTER = tonumber(os.getenv("QUINTRA_BOT_STOP_AFTER_CLEARS") or "")
local STAGELOG_OUT = os.getenv("QUINTRA_STAGELOG_OUT")
local STATUSLOG_OUT = os.getenv("QUINTRA_STATUSLOG_OUT")
local STALL_FRAMES = tonumber(os.getenv("QUINTRA_BOT_STALL_FRAMES") or "10800") or 10800
-- Harmful player conditions (status.h order). Regen/Haste are buffs;
-- Rift Inversion is a trade and logged but not counted as harmful.
local STATUS_NAMES = {"poison", "burn", "slow", "stop", "blind", "confusion",
    "mute", "brittle", "bleed", "curse", "regen", "haste", "inversion"}
local function harmful(kind) return kind >= 1 and kind <= 10 end
QH_STATUS_NAMES = STATUS_NAMES

-- Park-Miller minimal standard generator, deterministic per (skill, run,
-- class). Plain arithmetic keeps it exact in Lua 5.1 doubles (CI's luac -p)
-- and in mGBA's Lua 5.4 alike.
local rng = ((SKILL_ID * 7919 + RUN_ID * 104729 + CLASS_ID * 1299709) % 2147483646) + 1
local function rand()
    rng = (rng * 48271) % 2147483647
    return rng / 2147483647
end
local function between(range)
    return range[1] + math.floor(rand() * (range[2] - range[1] + 1))
end

-- ---------------------------------------------------------------------------
-- Human input filter
-- ---------------------------------------------------------------------------
local qh = {frame=0, active=false, proj={}, lapse=0, lapse_keys=0, slip=0,
    slip_dir=0, aim=0, aim_dir=0, drop=0, think=0, last_room=-1, last_keys=0,
    think_frames=0, missed=0, lapses=0, aware_now=false, last_in=0}
QH = qh

local DIRS = {KR, KR + KD, KD, KD + KL, KL, KL + KU, KU, KU + KR}
local function dir_index(d)
    for i, v in ipairs(DIRS) do if v == d then return i end end
    return nil
end

-- Track each hostile projectile slot from the frame it appears. A person can
-- only respond once it has been on screen for `reaction` frames, and some
-- shots are simply never noticed.
local function scan_projectiles()
    if Q_EN == 0 then return end
    for i = 0, 31 do
        local p = Q_EN + i * 28
        local flags = emu:read8(p + 1)
        local live = emu:read8(p) == 1 and flags % 2 == 1 and math.floor(flags / 16) % 2 == 0
        local t = qh.proj[i]
        if live then
            if not t then
                local missed = P and rand() < P.miss or false
                if missed then qh.missed = qh.missed + 1 end
                qh.proj[i] = {born=qh.frame, missed=missed}
            end
        elseif t then
            qh.proj[i] = nil
        end
    end
end

local function projectile_slot_at(x, y)
    for i = 0, 31 do
        local p = Q_EN + i * 28
        local flags = emu:read8(p + 1)
        if emu:read8(p) == 1 and flags % 2 == 1 and math.floor(flags / 16) % 2 == 0
            and emu:read8(p + 3) == x and emu:read8(p + 7) == y then
            return i
        end
    end
    return nil
end

-- Blind darkens the screen for a person; a RAM-reading pilot would not
-- notice, so while blinded only shots within 32 px are seen.
local function aware_of(i, x, y)
    if Q_STATUS ~= 0 and Q_PL ~= 0 and emu:read8(Q_STATUS) == 5
        and math.max(math.abs(x - emu:read8(Q_PL + 9)), math.abs(y - emu:read8(Q_PL + 11))) > 32 then
        return false
    end
    local t = qh.proj[i]
    if not t then return true end
    return (not t.missed) and qh.frame - t.born >= P.reaction
end

function QH_INSTALL()
    if not P or QH_INSTALLED then return end
    QH_INSTALLED = true
    local orig = projectile_threat
    projectile_threat = function(px, py)
        local th = orig(px, py)
        if th == nil then return nil end
        local slot = projectile_slot_at(th.x, th.y)
        if slot and not aware_of(slot, th.x, th.y) then return nil end
        qh.aware_now = true
        return th
    end
    if quintra_nearest_hostile_projectile then
        local orig_near = quintra_nearest_hostile_projectile
        quintra_nearest_hostile_projectile = function(px, py)
            local th = orig_near(px, py)
            if th == nil then return nil end
            local slot = projectile_slot_at(th.x, th.y)
            if slot and not aware_of(slot, th.x, th.y) then return nil end
            return th
        end
    end
end

local function hostile_near(radius)
    if Q_EN == 0 or Q_PL == 0 then return false end
    local px, py = emu:read8(Q_PL + 9), emu:read8(Q_PL + 11)
    for i = 0, 31 do
        local p = Q_EN + i * 28
        if emu:read8(p) == 2 and emu:read8(p + 1) % 2 == 1 then
            local ex, ey = emu:read8(p + 3), emu:read8(p + 7)
            if math.max(math.abs(ex - px), math.abs(ey - py)) <= radius then return true end
        end
    end
    return false
end

function QH_FILTER(keys)
    -- Only the controller's one-per-frame decision is humanized. Nested
    -- helper loops (doors, map, shops) wait on a screen change and must
    -- receive the exact buttons they ask for, or they could never finish.
    if not P or not qh.active or not QH_IN_MAIN or Q_LS == 0
        or emu:read8(Q_LS) ~= 5 then
        qh.last_keys = keys
        return keys
    end
    -- Room entry: orientation pause, much longer when a puzzle is locked.
    local room = Q_RS ~= 0 and emu:read8(Q_RS + 1) or 0
    if room ~= qh.last_room then
        qh.last_room = room
        local puzzle = Q_PUZZLE_KIND ~= 0 and Q_PUZZLE_LOCKED ~= 0
            and emu:read8(Q_PUZZLE_KIND) ~= 0 and emu:read8(Q_PUZZLE_LOCKED) ~= 0
        qh.think = puzzle and between(P.think) or between(P.pause)
        qh.puzzle_seen, qh.room_age = puzzle, 0
    end
    -- Puzzle state can latch a few frames after the room counter moves.
    qh.room_age = (qh.room_age or 0) + 1
    if not qh.puzzle_seen and qh.room_age <= 30 and Q_PUZZLE_KIND ~= 0
        and emu:read8(Q_PUZZLE_KIND) ~= 0 and emu:read8(Q_PUZZLE_LOCKED) ~= 0 then
        qh.puzzle_seen, qh.think = true, between(P.think)
    end
    local out = keys
    if qh.think > 0 then
        qh.think = qh.think - 1
        -- Nobody keeps puzzling with a monster in their face.
        if not qh.aware_now and not hostile_near(40) then
            qh.think_frames = qh.think_frames + 1
            qh.aware_now = false
            qh.last_keys = 0
            return 0
        end
        qh.think = 0
    end
    qh.aware_now = false
    -- Lapse: hands keep doing what they did a moment ago.
    if qh.lapse > 0 then
        qh.lapse = qh.lapse - 1
        out = qh.lapse_keys
    elseif rand() < P.lapse then
        qh.lapse, qh.lapse_keys = between(P.lapse_len), qh.last_keys
        qh.lapses = qh.lapses + 1
        out = qh.lapse_keys
    end
    -- Aim error: a fresh attack press lands one octant off for its hold.
    local a_edge = has(out, KA) and not has(qh.last_keys, KA)
    if a_edge then
        qh.aim = 0
        local idx = dir_index(dirs_of(out))
        if idx and rand() < P.aim then
            local shift = rand() < 0.5 and -1 or 1
            qh.aim, qh.aim_dir = 10, DIRS[(idx - 1 + shift) % 8 + 1]
        end
    end
    if qh.aim > 0 and has(out, KA) and dirs_of(out) ~= 0 then
        qh.aim = qh.aim - 1
        out = with_dirs(out, qh.aim_dir)
    elseif not has(out, KA) then
        qh.aim = 0
    end
    -- D-pad slip: a short wrong or released direction.
    if qh.slip > 0 then
        qh.slip = qh.slip - 1
        out = with_dirs(out, qh.slip_dir)
    elseif dirs_of(out) ~= 0 and dirs_of(keys) ~= dirs_of(qh.last_in) and rand() < P.slip then
        -- Slips happen when the hand changes direction, not mid-hold.
        qh.slip = between(P.slip_len) - 1
        qh.slip_dir = rand() < 0.3 and 0 or DIRS[between({1, 8})]
        out = with_dirs(out, qh.slip_dir)
    end
    -- Dropped attack timing.
    if qh.drop > 0 then
        qh.drop = qh.drop - 1
        out = without_a(out)
    elseif a_edge and rand() < P.drop then
        qh.drop = between(P.drop_len) - 1
        out = without_a(out)
    end
    qh.last_in = keys
    qh.last_keys = out
    return out
end

-- ---------------------------------------------------------------------------
-- Per-stage observer
-- ---------------------------------------------------------------------------
local BURST_WINDOW = 120         -- 2 s
local BURST_SPIKE_FRACTION = 0.4 -- of max HP inside one window
local LOW_HP_FRACTION = 1 / 3
local obs = {cur=nil, hits={}, last_hp=nil, last_status=0, last_ticks=0,
    enemy={}, last_bosses=nil, last_harm_kind=0, last_harm_frame=-1,
    seed=0, stop=false, status_rows={}, in_spike=false}
QH_STOP = false

local function rd(addr, off) return addr ~= 0 and emu:read8(addr + off) or 0 end
local function giant_alive()
    if Q_EN == 0 then return false end
    for i = 0, 31 do
        local p = Q_EN + i * 28
        if emu:read8(p) == 2 and emu:read8(p + 1) % 2 == 1
            and emu:read8(p + 17) == 1 and emu:read8(p + 20) ~= 0 then
            return true
        end
    end
    return false
end
local function items_held()
    local n = 0
    for i = 24, 39 do
        local v = rd(Q_PL, i)
        if v ~= 0 and v ~= 0xFF then n = n + 1 end
    end
    return n
end

local function open_stage(frame)
    local bosses = rd(Q_RS, 11)
    obs.cur = {
        stage=math.min(9, bosses + 1), start=frame, dmg=0, healed=0, dealt=0,
        hits=0, hp_start=rd(Q_PL, 2), hp_min=rd(Q_PL, 2), hpmax_start=rd(Q_PL, 1),
        coins_start=rd(Q_PL, 16) + rd(Q_PL, 17) * 256,
        kills_start=rd(Q_RS, 16) + rd(Q_RS, 35) * 256,
        boss_first=-1, boss_frames=0, boss_dmg=0, burst_max=0, spikes=0,
        lands=0, harmful=0, in_boss=0, low_hp=0, kinds={}, exposed=0,
        think0=qh.think_frames, missed0=qh.missed, lapses0=qh.lapses,
    }
    obs.hits, obs.in_spike = {}, false
end

local function csv_row(c, frame, outcome, death)
    local kinds = {}
    for k = 1, #STATUS_NAMES do
        if c.kinds[k] then kinds[#kinds + 1] = STATUS_NAMES[k] .. ":" .. c.kinds[k] end
    end
    local ttk = (outcome == "cleared" or outcome == "won") and c.boss_first >= 0
        and (frame - c.boss_first) or -1
    local d_kind, d_age, d_active, d_boss = "", -1, "", 0
    if death then
        d_boss = death.in_boss
        if obs.last_harm_frame >= 0 then
            d_kind = STATUS_NAMES[obs.last_harm_kind] or ""
            d_age = death.frame - obs.last_harm_frame
        end
        d_active = harmful(death.active) and STATUS_NAMES[death.active] or ""
    end
    return string.format(
        "%s,%d,%d,%.0f,%s,%d,%d,%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%s,%d,%s,%d,%s,%d,%d,%d,%d,%d",
        SKILL_NAME, RUN_ID, CLASS_ID, obs.seed, MODE, rd(Q_RS, 26), c.stage, outcome,
        frame - c.start, c.start, frame, c.dmg, c.dealt, c.healed, c.hits,
        c.hp_start, rd(Q_PL, 2), c.hp_min, c.hpmax_start, rd(Q_PL, 1),
        rd(Q_PL, 4), rd(Q_PL, 3), c.coins_start, rd(Q_PL, 16) + rd(Q_PL, 17) * 256,
        rd(Q_PL, 5), rd(Q_PL, 6), rd(Q_PL, 7), rd(Q_PL, 8), rd(Q_PL, 21), items_held(),
        rd(Q_RS, 16) + rd(Q_RS, 35) * 256 - c.kills_start,
        c.boss_first >= 0 and 1 or 0, c.boss_frames,
        (outcome == "cleared" or outcome == "won") and 1 or 0, ttk, c.boss_dmg,
        c.burst_max, c.spikes, c.lands, c.harmful, c.in_boss, c.low_hp,
        rd(Q_RS, 7) + rd(Q_RS, 8) * 256,
        table.concat(kinds, ";"), d_boss, d_kind, d_age, d_active,
        qh.think_frames - c.think0, qh.missed - c.missed0, qh.lapses - c.lapses0,
        death and death.burst or 0, c.exposed)
end
QH_STAGE_HEADER = "skill,run,class,seed,mode,difficulty,stage,outcome,frames,start_frame,end_frame,dmg_taken,dmg_dealt,healed,hits,hp_start,hp_end,hp_min,hp_max_start,hp_max_end,mp_end,mp_max_end,coins_start,coins_end,atk,def,spd,lck,weapon,items,kills,boss_seen,boss_frames,boss_cleared,boss_ttk,boss_dmg_taken,burst_max_2s,burst_spikes,status_lands,status_harmful,status_in_boss,status_low_hp,run_timer_s,status_kinds,death_in_boss,death_status_kind,death_status_age,death_status_active,think_frames,missed_dodges,lapses,death_burst_2s,status_exposed_frames"

local function emit(line)
    if not STAGELOG_OUT then return end
    local f = io.open(STAGELOG_OUT, "a")
    if f then f:write(line .. "\n"); f:close() end
end

-- Watchdog: a controller helper that never returns would hang the host
-- until its timeout and lose the whole run. Abort the frame after
-- QUINTRA_BOT_WATCHDOG_SECONDS of CPU time, logging a traceback and a
-- `hang` stage row so the sweep keeps the stages already measured.
local WATCHDOG = tonumber(os.getenv("QUINTRA_BOT_WATCHDOG_SECONDS") or "")
local frame_clock = os.clock()
function QH_ON_HANG(trace)
    local out = os.getenv("QUINTRA_BOT_HANG_OUT")
    if out then
        local f = io.open(out, "a")
        if f then
            f:write(string.format("frame=%d room=%d stage=%d\n%s\n", qh.frame,
                rd(Q_RS, 1), rd(Q_RS, 11) + 1, trace))
            f:close()
        end
    end
    if obs.cur and not obs.closed then
        emit(csv_row(obs.cur, qh.frame, "hang", nil))
        obs.closed = true
    end
end

function QH_BEGIN()
    qh.active = true
    if WATCHDOG and debug and debug.sethook then
        debug.sethook(function()
            if os.clock() - frame_clock > WATCHDOG then
                debug.sethook()
                local trace = debug.traceback("controller watchdog", 2)
                QH_ON_HANG(trace)
                error(trace)
            end
        end, "", 100000)
    end
    if Q_RS ~= 0 then
        obs.seed = rd(Q_RS, 2) + rd(Q_RS, 3) * 256 + rd(Q_RS, 4) * 65536 + rd(Q_RS, 5) * 16777216
    end
    QH_INSTALL()
end

function QH_OBSERVE(frame)
    qh.frame = frame
    frame_clock = os.clock()
    if P then scan_projectiles() end
    if Q_RS == 0 or Q_PL == 0 then return end
    local bosses = rd(Q_RS, 11)
    if obs.cur == nil then
        open_stage(frame)
        obs.last_bosses, obs.start_bosses = bosses, bosses
    end
    local c = obs.cur
    if bosses > obs.last_bosses then
        emit(csv_row(c, frame, "cleared", nil))
        obs.last_bosses = bosses
        if STOP_AFTER and bosses - obs.start_bosses >= STOP_AFTER then
            QH_STOP = true
            obs.cur = nil
            obs.closed = true
            return
        end
        open_stage(frame)
        c = obs.cur
    end
    local hp, hp_max = rd(Q_PL, 2), rd(Q_PL, 1)
    local boss = giant_alive()
    -- Harness stall: no room/field change and no live Colossus for
    -- STALL_FRAMES means the pilot is lost, not that the stage is hard.
    -- Close the stage as `stalled` (excluded from difficulty stats, counted
    -- as harness coverage) instead of burning the host on a stuck run.
    local loc = rd(Q_RS, 1) * 256 + rd(Q_RS, 17) * 64 + rd(Q_RS, 18)
    if loc ~= obs.loc or boss then obs.loc, obs.loc_frame = loc, frame end
    if STALL_FRAMES > 0 and frame - (obs.loc_frame or frame) > STALL_FRAMES then
        emit(csv_row(c, frame, "stalled", nil))
        obs.closed, QH_STOP = true, true
        return
    end
    if boss then
        if c.boss_first < 0 then c.boss_first = frame end
        c.boss_frames = c.boss_frames + 1
    end
    if obs.last_hp == nil then obs.last_hp = hp end
    if hp < obs.last_hp then
        local taken = obs.last_hp - hp
        c.dmg, c.hits = c.dmg + taken, c.hits + 1
        if boss then c.boss_dmg = c.boss_dmg + taken end
        obs.hits[#obs.hits + 1] = {frame, taken}
    elseif hp > obs.last_hp then
        c.healed = c.healed + (hp - obs.last_hp)
    end
    obs.last_hp = hp
    if hp < c.hp_min then c.hp_min = hp end
    -- Burst: damage inside the trailing 2 s window.
    local sum, keep = 0, {}
    for _, h in ipairs(obs.hits) do
        if frame - h[1] < BURST_WINDOW then keep[#keep + 1] = h; sum = sum + h[2] end
    end
    obs.hits, obs.burst = keep, sum
    if sum > c.burst_max then c.burst_max = sum end
    local spike = hp_max > 0 and sum >= hp_max * BURST_SPIKE_FRACTION
    if spike and not obs.in_spike then c.spikes = c.spikes + 1 end
    obs.in_spike = spike
    -- Status landings: a new kind, or a refresh that raises its timer.
    if Q_STATUS ~= 0 then
        local kind, ticks = emu:read8(Q_STATUS), emu:read8(Q_STATUS_TICKS)
        if kind ~= 0 and kind <= #STATUS_NAMES
            and (kind ~= obs.last_status or ticks > obs.last_ticks) then
            c.lands = c.lands + 1
            c.kinds[kind] = (c.kinds[kind] or 0) + 1
            local low = hp_max > 0 and hp <= hp_max * LOW_HP_FRACTION
            if harmful(kind) then
                c.harmful = c.harmful + 1
                if boss then c.in_boss = c.in_boss + 1 end
                if low then c.low_hp = c.low_hp + 1 end
                obs.last_harm_kind, obs.last_harm_frame = kind, frame
            end
            if STATUSLOG_OUT then
                obs.status_rows[#obs.status_rows + 1] = string.format(
                    "%s,%d,%d,%d,%d,%s,%d,%d,%d,%d", SKILL_NAME, RUN_ID, CLASS_ID,
                    c.stage, frame, STATUS_NAMES[kind], boss and 1 or 0,
                    low and 1 or 0, hp, hp_max)
            end
        end
        obs.last_status, obs.last_ticks = kind, ticks
        -- Exposure: frames under a harmful status or within 5 s of one, the
        -- denominator for "deaths after a status" (lift over chance).
        if harmful(kind) or (obs.last_harm_frame >= 0 and frame - obs.last_harm_frame < 300) then
            c.exposed = c.exposed + 1
        end
    end
    -- Damage dealt: HP drops on the same live hostile in the same slot.
    if Q_EN ~= 0 then
        for i = 0, 31 do
            local p = Q_EN + i * 28
            local e = obs.enemy[i]
            if emu:read8(p) == 2 and emu:read8(p + 1) % 2 == 1 then
                local kind, ehp = emu:read8(p + 17), emu:read8(p + 14)
                if e and e[1] == kind and ehp < e[2] then
                    c.dealt = c.dealt + (e[2] - ehp)
                elseif e and e[1] == kind and ehp > e[2] + 32 then
                    -- respawned/reused slot; no credit
                end
                if e then e[1], e[2] = kind, ehp else obs.enemy[i] = {kind, ehp} end
            elseif e then
                -- A hostile that vanished was killed or despawned. Credit
                -- its last HP only if it died in combat (hp was low).
                if e[2] <= 2 then c.dealt = c.dealt + e[2] end
                obs.enemy[i] = nil
            end
        end
    end
end

function QH_FINISH(frame, won)
    if obs.closed then
        if STATUSLOG_OUT and #obs.status_rows > 0 and not obs.status_flushed then
            local f = io.open(STATUSLOG_OUT, "a")
            if f then
                for _, row in ipairs(obs.status_rows) do f:write(row .. "\n") end
                f:close()
            end
            obs.status_flushed = true
        end
        return
    end
    if obs.cur == nil then
        if Q_RS == 0 then return end
        open_stage(frame)
    end
    local hp = rd(Q_PL, 2)
    local outcome, death = "timeout", nil
    if won ~= 0 then
        outcome = "won"
    elseif hp == 0 or (obs.last_hp ~= nil and obs.last_hp == 0) then
        outcome = "died"
        death = {frame=frame, in_boss=obs.cur.boss_first >= 0 and giant_alive() and 1 or 0,
            active=Q_STATUS ~= 0 and emu:read8(Q_STATUS) or 0, burst=obs.burst or 0}
        if obs.cur.boss_frames > 0 and death.in_boss == 0 then
            -- The giant may already be swept by GAME OVER; a death inside an
            -- observed boss encounter is still a boss death.
            death.in_boss = obs.cur.boss_first >= 0 and 1 or 0
        end
    end
    emit(csv_row(obs.cur, frame, outcome, death))
    if STATUSLOG_OUT and #obs.status_rows > 0 then
        local f = io.open(STATUSLOG_OUT, "a")
        if f then
            for _, row in ipairs(obs.status_rows) do f:write(row .. "\n") end
            f:close()
        end
    end
    obs.closed = true
end
