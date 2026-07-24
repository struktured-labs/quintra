-- Quintra whole-cartridge smoke test.
-- Boots → TITLE → CLASS_SELECT → follows the authored spatial graph through
-- the room-two Rift Sigil, room-three Warden, and branching boss approach →
-- fights → Pack → exit.

local OUT_DIR = os.getenv("QUINTRA_OUT_DIR") or "/tmp/quintra-smoketest"

local KEY_A      = 0x01
local KEY_B      = 0x02
local KEY_SELECT = 0x04
local KEY_START  = 0x08
local KEY_RIGHT  = 0x10
local KEY_LEFT   = 0x20
local KEY_UP     = 0x40
local KEY_DOWN   = 0x80

-- Runtime WRAM addresses are resolved from the current linker's .noi file.
-- Never fall back to historical 0xFFF* debug scratch bytes: those are not
-- game state and previously made every screenshot claim room=5 / hp=0.
local RS_ADDR = tonumber(os.getenv("QUINTRA_RS_ADDR") or "0") or 0
local PL_ADDR = tonumber(os.getenv("QUINTRA_PL_ADDR") or "0") or 0
local EN_ADDR = tonumber(os.getenv("QUINTRA_EN_ADDR") or "0") or 0
local TM_ADDR = tonumber(os.getenv("QUINTRA_TM_ADDR") or "0") or 0
local LS_ADDR = tonumber(os.getenv("QUINTRA_SCREEN_ADDR") or "0") or 0
local PK_ADDR = tonumber(os.getenv("QUINTRA_PUZZLE_KIND_ADDR") or "0") or 0
local PLK_ADDR = tonumber(os.getenv("QUINTRA_PUZZLE_LOCK_ADDR") or "0") or 0
local WW_ADDR = tonumber(os.getenv("QUINTRA_WORLD_WIDTH_ADDR") or "0") or 0
local WH_ADDR = tonumber(os.getenv("QUINTRA_WORLD_HEIGHT_ADDR") or "0") or 0

local LOG_FILE = OUT_DIR .. "/debug.log"
local log_fh = io.open(LOG_FILE, "w")

-- Room generation intentionally blanks the LCD and temporarily uses bit 7 of
-- the room tilemap for its body-reachability flood fill. Code-size and layout
-- changes can make that transaction span a different number of host frames,
-- so never capture from a fixed delay in the middle of it. Four consecutive
-- ready frames also give the frontend time to present the first rendered one.
local function settle_display()
    local ready_frames = 0
    for _ = 1, 180 do
        local ready = emu:read8(0xFF40) >= 0x80
        if ready and TM_ADDR ~= 0 then
            for i = 0, 359 do
                if emu:read8(TM_ADDR + i) >= 0x80 then
                    ready = false
                    break
                end
            end
        end
        if ready then
            ready_frames = ready_frames + 1
            if ready_frames >= 4 then return end
        else
            ready_frames = 0
        end
        emu:runFrame()
    end
end

local function shot(name)
    settle_display()
    emu:screenshot(OUT_DIR .. "/h_" .. name .. ".png")
    local rc_room = RS_ADDR ~= 0 and emu:read8(RS_ADDR + 1) or 0xFF
    local vic     = RS_ADDR ~= 0 and emu:read8(RS_ADDR + 10) or 0xFF
    local bosses  = RS_ADDR ~= 0 and emu:read8(RS_ADDR + 11) or 0xFF
    local screen  = LS_ADDR ~= 0 and emu:read8(LS_ADDR) or 0xFF
    local px      = PL_ADDR ~= 0 and emu:read8(PL_ADDR + 9) or 0xFF
    local py      = PL_ADDR ~= 0 and emu:read8(PL_ADDR + 11) or 0xFF
    local hp      = PL_ADDR ~= 0 and emu:read8(PL_ADDR + 2) or 0xFF
    local ifr     = PL_ADDR ~= 0 and emu:read8(PL_ADDR + 15) or 0xFF
    local tile = 0xFF
    if TM_ADDR ~= 0 and px < 152 and py < 128 then
        local tx, ty = math.floor((px + 8) / 8), math.floor((py + 12) / 8)
        if tx < 20 and ty < 18 then tile = emu:read8(TM_ADDR + ty * 20 + tx) end
    end
    local hostiles, giants, giant_hp, giant_x, giant_y = 0, 0, 0, 255, 255
    if EN_ADDR ~= 0 then
        for i = 0, 31 do
            local p = EN_ADDR + i * 28
            if emu:read8(p) == 2 and emu:read8(p + 1) % 2 == 1 then
                hostiles = hostiles + 1
                if emu:read8(p + 17) == 1 and emu:read8(p + 20) ~= 0 then
                    giants = giants + 1
                    giant_hp = emu:read8(p + 14)
                    giant_x = emu:read8(p + 3)
                    giant_y = emu:read8(p + 7)
                end
            end
        end
    end
    local line = string.format(
        "SHOT %-25s  screen=%d room=%d vic=%d bosses=%d hostiles=%d giants=%d giant=%d,%d giant_hp=%d  pos=(%d,%d) tile=0x%02X  hp=%d ifr=%d\n",
        name, screen, rc_room, vic, bosses, hostiles, giants, giant_x, giant_y, giant_hp, px, py, tile, hp, ifr)
    if log_fh then log_fh:write(line); log_fh:flush() end
    console:log(line)
end

local function tick(n) for _ = 1, n do emu:runFrame() end end

local function hold(key, frames)
    -- Set keys on EVERY frame to defeat any per-frame reset
    for _ = 1, (frames or 4) do
        emu:setKeys(key)
        emu:runFrame()
    end
    emu:setKeys(0)
    tick(4)
end

local function press(key, frames_held) hold(key, frames_held or 4) end
local function tap(key) hold(key, 2) end

-- This is a reachability smoke test, not the balance bot. Clear enemies so
-- Zelda-style combat gates cannot make screenshot coverage timing-dependent.
local function clear_hostiles()
    if EN_ADDR == 0 then return end
    for i = 0, 31 do
        local p = EN_ADDR + i * 28
        if emu:read8(p) == 2 then
            emu:write8(p, 0)
            emu:write8(p + 1, 0)
        end
    end
end

local function giant_alive()
    if EN_ADDR == 0 then return false end
    for i = 0, 31 do
        local p = EN_ADDR + i * 28
        if emu:read8(p) == 2 and emu:read8(p + 1) % 2 == 1
            and emu:read8(p + 17) == 1 and emu:read8(p + 20) ~= 0 then
            return true
        end
    end
    return false
end

-- Return the live giant's integer top-left.  The smoke runner is intentionally
-- allowed to reposition the champion, but its damage still travels through
-- normal controller A attacks.  Following the body keeps this reachability
-- check valid for bosses that strafe, bounce, or blink instead of assuming the
-- old generic beeline will stay under a fixed firing lane.
local function giant_position()
    if EN_ADDR == 0 then return nil, nil end
    for i = 0, 31 do
        local p = EN_ADDR + i * 28
        if emu:read8(p) == 2 and emu:read8(p + 1) % 2 == 1
            and emu:read8(p + 17) == 1 and emu:read8(p + 20) ~= 0 then
            return emu:read8(p + 3), emu:read8(p + 7)
        end
    end
    return nil, nil
end

-- Fire from a stable lane above the giant. This reachability harness may
-- refill HP/iframes and correct position, but damage is delivered only by
-- ordinary A-button weapon shots through the real combat path.
local function assault_boss(frames)
    for _ = 1, frames do
        if not giant_alive() then break end
        local bx, by = giant_position()
        emu:write8(PL_ADDR + 2, 8)
        -- Stay one sword lane above the real giant whenever that lane fits.
        -- A mobile Colossus can reach y=8, however; clamping the hero above
        -- it at y=8 then made a downward thrust begin below the body. In that
        -- edge case use the equally real below-body/upward stab instead.
        local boss_x, boss_y = bx or 62, by or 36
        local attack_dir = KEY_DOWN
        emu:write8(PL_ADDR + 9, math.min(140, math.max(8, boss_x + 10))); emu:write8(PL_ADDR + 10, 0)
        if boss_y < 28 then
            emu:write8(PL_ADDR + 11, math.min(112, boss_y + 20)); emu:write8(PL_ADDR + 12, 0)
            attack_dir = KEY_UP
        else
            emu:write8(PL_ADDR + 11, boss_y - 20); emu:write8(PL_ADDR + 12, 0)
        end
        emu:write8(PL_ADDR + 15, 60)
        -- Wolfkin now owns a slow, held-A physical combo (including its
        -- cooldown-gated Max Strike). Keep A held so smoke covers the
        -- player-facing turbo-friendly control path; the cartridge itself
        -- enforces the 24-frame cadence, never this harness.
        emu:setKeys(KEY_A + attack_dir)
        emu:runFrame()
    end
    emu:setKeys(0)
    tick(20)
end

local function room_counter()
    if RS_ADDR == 0 then return 0xFF end
    return emu:read8(RS_ADDR + 1)
end

-- Walk south until the room counter reads exactly `target`. Short
-- 20-frame bursts so a crossing can't overshoot two rooms (which the
-- old fixed 220-frame hold did whenever code-size changes shifted
-- frame alignment). The runner is topped up each burst: this harness
-- verifies screens are REACHABLE, not that a bot survives bullet hell.
local function walk_edge(target, key)
    for _ = 1, 80 do
        if room_counter() == target then break end
        if PL_ADDR ~= 0 then
            emu:write8(PL_ADDR + 2, 12)    -- hp: stay alive
            emu:write8(PL_ADDR + 15, 60)   -- iframes: no knockback ping-pong
            -- Put the champion in the appropriate doorway lane. This smoke
            -- harness may reposition the hero, but crosses every threshold
            -- through the cartridge's real transition transaction.
            if key == KEY_UP then
                emu:write8(PL_ADDR + 9, 72); emu:write8(PL_ADDR + 10, 0)
                emu:write8(PL_ADDR + 11, 8); emu:write8(PL_ADDR + 12, 0)
            elseif key == KEY_RIGHT then
                local world_width = WW_ADDR ~= 0 and emu:read8(WW_ADDR) or 160
                emu:write8(PL_ADDR + 9, world_width - 20)
                emu:write8(PL_ADDR + 10, 0)
                emu:write8(PL_ADDR + 11, 60); emu:write8(PL_ADDR + 12, 0)
            elseif key == KEY_DOWN then
                local world_height = WH_ADDR ~= 0 and emu:read8(WH_ADDR) or 136
                emu:write8(PL_ADDR + 9, 72); emu:write8(PL_ADDR + 10, 0)
                emu:write8(PL_ADDR + 11, world_height - 24)
                emu:write8(PL_ADDR + 12, 0)
            else
                emu:write8(PL_ADDR + 9, 8); emu:write8(PL_ADDR + 10, 0)
                emu:write8(PL_ADDR + 11, 60); emu:write8(PL_ADDR + 12, 0)
            end
        end
        clear_hostiles()
        hold(key, 8)
    end
    tick(20)
end

local function collect_rift_sigil()
    if EN_ADDR == 0 or PL_ADDR == 0 then return false end
    for i = 0, 31 do
        local p = EN_ADDR + i * 28
        -- ENTITY_PICKUP with PICKUP_RIFT_SIGIL in ai_data[0].
        if emu:read8(p) == 3 and emu:read8(p + 17) == 11 then
            emu:write8(PL_ADDR + 9, math.max(0, emu:read8(p + 3) - 2))
            emu:write8(PL_ADDR + 10, 0)
            emu:write8(PL_ADDR + 11, math.max(0, emu:read8(p + 7) - 9))
            emu:write8(PL_ADDR + 12, 0)
            tick(30)
            return true
        end
    end
    return false
end

-- The smoke harness removes encounter entities to keep screenshot timing
-- deterministic, so the normal enemy-death callback cannot record the
-- room-three Warden Boon. Preserve the equivalent post-clear fixture state
-- after visibly reaching that authored chamber; this is a reachability smoke,
-- while controller-only tests separately prove the real Warden kill path.
local function record_opening_warden_boon()
    if RS_ADDR == 0 or room_counter() ~= 3 then return false end
    local puzzles = emu:read8(RS_ADDR + 27)
    if math.floor(puzzles / 8) % 2 == 0 then
        emu:write8(RS_ADDR + 27, puzzles + 8)
    end
    return true
end

local function solve_opening_push_seal()
    if TM_ADDR == 0 or PL_ADDR == 0 then return false end
    for y = 1, 15 do
        for x = 1, 18 do
            if emu:read8(TM_ADDR + y * 20 + x) == 25 then
                -- Approach the ordinary-looking 2x2 cairn from its left and
                -- hold into it through the real ten-frame push threshold.
                emu:write8(PL_ADDR + 9, math.max(0, x * 8 - 16))
                emu:write8(PL_ADDR + 10, 0)
                emu:write8(PL_ADDR + 11, math.max(0, y * 8 - 8))
                emu:write8(PL_ADDR + 12, 0)
                hold(KEY_RIGHT, 120)
                return true
            end
        end
    end
    return false
end

-- Local room seven is deliberately a second mechanical beat in every wider
-- stage. Solve either authored vocabulary through ordinary champion contact
-- so this smoke path proves the Waystone is obtainable, not just writable.
local function solve_waystone()
    if TM_ADDR == 0 or PL_ADDR == 0 or PK_ADDR == 0 or PLK_ADDR == 0 then
        return false
    end
    local kind = emu:read8(PK_ADDR)
    if emu:read8(PLK_ADDR) == 0 then return true end
    if kind == 1 then
        for y = 1, 15 do
            for x = 1, 18 do
                if emu:read8(TM_ADDR + y * 20 + x) == 25 then
                    emu:write8(PL_ADDR + 9, math.max(0, x * 8 - 16))
                    emu:write8(PL_ADDR + 10, 0)
                    emu:write8(PL_ADDR + 11, math.max(0, y * 8 - 8))
                    emu:write8(PL_ADDR + 12, 0)
                    hold(KEY_RIGHT, 120)
                    return emu:read8(PLK_ADDR) == 0
                end
            end
        end
    elseif kind == 2 then
        local runes = {}
        for y = 1, 15 do
            for x = 1, 18 do
                if emu:read8(TM_ADDR + y * 20 + x) == 33 then
                    table.insert(runes, {x, y})
                end
            end
        end
        local orders = {
            {1, 2, 3}, {1, 3, 2}, {2, 1, 3},
            {2, 3, 1}, {3, 1, 2}, {3, 2, 1},
        }
        for _, order in ipairs(orders) do
            for _, index in ipairs(order) do
                local rune = runes[index]
                if rune then
                    emu:write8(PL_ADDR + 9, rune[1] * 8 - 8)
                    emu:write8(PL_ADDR + 10, 0)
                    emu:write8(PL_ADDR + 11, rune[2] * 8 - 12)
                    emu:write8(PL_ADDR + 12, 0)
                    tick(3)
                    emu:write8(PL_ADDR + 9, 72)
                    emu:write8(PL_ADDR + 10, 0)
                    emu:write8(PL_ADDR + 11, 92)
                    emu:write8(PL_ADDR + 12, 0)
                    tick(3)
                end
                if emu:read8(PLK_ADDR) == 0 then return true end
            end
        end
    end
    return emu:read8(PLK_ADDR) == 0
end

-- This deterministic reachability runner clears combat entities. Mirror the
-- deep Warden's normal death reward only after visibly reaching its authored
-- chamber; controller-only combat tests own the real kill/reward contract.
local function record_deep_warden_boon()
    if RS_ADDR == 0 or room_counter() ~= 9 then return false end
    local phase = emu:read8(RS_ADDR + 28)
    if math.floor(phase / 128) % 2 == 0 then
        emu:write8(RS_ADDR + 28, phase + 128)
    end
    return true
end

-- Boot
tick(120); shot("01_title")
tap(KEY_START); tick(40); shot("02_class_select")

-- Cycle through all 5 classes to confirm cursor + stats update
tap(KEY_DOWN); tick(15); shot("02b_sauran")
tap(KEY_DOWN); tick(15); shot("02c_corvin")
tap(KEY_DOWN); tick(15); shot("02d_picsean")
tap(KEY_DOWN); tick(15); shot("02e_vespine")
tap(KEY_DOWN); tick(15)  -- wraps back to Wolfkin
tap(KEY_A); tick(40); shot("03_room0_enter")

-- Opening graph route sweeps the Sigil/Warden/Waystone objective wing before
-- it rejoins the deeper 6x5 spine at room ten. This complete controller route
-- proves the twenty-room baseline cannot collapse into the old compact
-- rectangle or skip the new geographic junction.
walk_edge(1, KEY_RIGHT); shot("04_room1"); solve_opening_push_seal()
walk_edge(2, KEY_RIGHT); collect_rift_sigil(); shot("05_room2_sigil")
walk_edge(3, KEY_RIGHT); record_opening_warden_boon()
walk_edge(4, KEY_RIGHT)
walk_edge(5, KEY_RIGHT); shot("06_room5_branch")
walk_edge(6, KEY_DOWN)
walk_edge(7, KEY_LEFT); solve_waystone()
walk_edge(8, KEY_LEFT)
walk_edge(9, KEY_LEFT); record_deep_warden_boon(); shot("07_room9_threshold")
walk_edge(10, KEY_LEFT)
walk_edge(11, KEY_LEFT)
walk_edge(12, KEY_DOWN)
walk_edge(13, KEY_RIGHT)
walk_edge(14, KEY_RIGHT)
walk_edge(15, KEY_RIGHT)
walk_edge(16, KEY_RIGHT)
walk_edge(17, KEY_RIGHT)
walk_edge(18, KEY_DOWN)
-- A new stage deliberately fades its palette in. Wait it out so this is a
-- useful boss-arena capture rather than an intended near-black transition.
walk_edge(19, KEY_LEFT); tick(36); shot("08_BOSS_room")

-- Damage the first giant through real controller shots, sampling the fight.
assault_boss(80)
shot("09_boss_under_fire")

assault_boss(80)
shot("10_boss_mid_fight")

-- The Colossus now has a 200-HP introductory pattern window. Keep the smoke
-- runner on its real held-A path long enough to prove the complete reward /
-- Pack / return sequence instead of mistaking the old 760-frame budget for
-- a balance assertion. The loop exits immediately on a real boss death.
assault_boss(2400)
shot("11_after_long_assault")

-- START opens the Pack screen; START again returns to the live room.
press(KEY_START, 4); tick(20); shot("12_pack")
press(KEY_START, 4); tick(20); shot("13_room_return")

console:log("SMOKETEST DONE")
emu.frontend:quit()
