-- Quintra Phase 9/10 smoke test.
-- Boots → TITLE → CLASS_SELECT → walks through 5 doors to the BOSS room
-- → fights → screenshot at each stage → exit.

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
    local hostiles, giants, giant_hp = 0, 0, 0
    if EN_ADDR ~= 0 then
        for i = 0, 31 do
            local p = EN_ADDR + i * 28
            if emu:read8(p) == 2 and emu:read8(p + 1) % 2 == 1 then
                hostiles = hostiles + 1
                if emu:read8(p + 17) == 1 and emu:read8(p + 20) ~= 0 then
                    giants = giants + 1
                    giant_hp = emu:read8(p + 14)
                end
            end
        end
    end
    local line = string.format(
        "SHOT %-25s  screen=%d room=%d vic=%d bosses=%d hostiles=%d giants=%d giant_hp=%d  pos=(%d,%d) tile=0x%02X  hp=%d ifr=%d\n",
        name, screen, rc_room, vic, bosses, hostiles, giants, giant_hp, px, py, tile, hp, ifr)
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

-- Fire from a stable lane above the giant. This reachability harness may
-- refill HP/iframes and correct position, but damage is delivered only by
-- ordinary A-button weapon shots through the real combat path.
local function assault_boss(frames)
    for _ = 1, frames do
        if not giant_alive() then break end
        emu:write8(PL_ADDR + 2, 8)
        emu:write8(PL_ADDR + 9, 72); emu:write8(PL_ADDR + 10, 0)
        emu:write8(PL_ADDR + 11, 16); emu:write8(PL_ADDR + 12, 0)
        emu:write8(PL_ADDR + 15, 60)
        -- Wolfkin's A is intentionally edge-triggered (stab/sweep), unlike
        -- the ranged held-fire kits. Pulse it every 18 frames so this still
        -- drives the real contact attack without regressing the game into a
        -- flying-sword stream just to satisfy smoke coverage.
        if (_ % 18) < 2 then emu:setKeys(KEY_A + KEY_DOWN)
        else emu:setKeys(KEY_DOWN) end
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
local function walk_to_room(target)
    for _ = 1, 80 do
        if room_counter() == target then break end
        if PL_ADDR ~= 0 then
            emu:write8(PL_ADDR + 2, 12)    -- hp: stay alive
            emu:write8(PL_ADDR + 15, 60)   -- iframes: no knockback ping-pong
        end
        clear_hostiles()
        hold(KEY_DOWN, 20)
    end
    tick(20)
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

-- Descend by room counter: 1,2,3 (mini-boss), 4 (shop), then the
-- stage-boss room at 6.
walk_to_room(1);  shot("04_room1")
walk_to_room(2);  shot("05_room2")
walk_to_room(3);  shot("06_room3")
walk_to_room(4);  shot("07_room4")
-- A new stage deliberately fades its palette in. Wait it out so this is a
-- useful boss-arena capture rather than an intended near-black transition.
walk_to_room(6);  tick(36); shot("08_BOSS_room")

-- Damage the first giant through real controller shots, sampling the fight.
assault_boss(80)
shot("09_boss_under_fire")

assault_boss(80)
shot("10_boss_mid_fight")

assault_boss(600)
shot("11_after_long_assault")

-- START opens the Pack screen; START again returns to the live room.
press(KEY_START, 4); tick(20); shot("12_pack")
press(KEY_START, 4); tick(20); shot("13_room_return")

console:log("SMOKETEST DONE")
emu.frontend:quit()
