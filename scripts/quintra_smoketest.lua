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

local LOG_FILE = OUT_DIR .. "/debug.log"
local log_fh = io.open(LOG_FILE, "w")

local function shot(name)
    emu:screenshot(OUT_DIR .. "/h_" .. name .. ".png")
    local rc_room = RS_ADDR ~= 0 and emu:read8(RS_ADDR + 1) or 0xFF
    local vic     = RS_ADDR ~= 0 and emu:read8(RS_ADDR + 10) or 0xFF
    local px      = PL_ADDR ~= 0 and emu:read8(PL_ADDR + 9) or 0xFF
    local py      = PL_ADDR ~= 0 and emu:read8(PL_ADDR + 11) or 0xFF
    local hp      = PL_ADDR ~= 0 and emu:read8(PL_ADDR + 2) or 0xFF
    local ifr     = PL_ADDR ~= 0 and emu:read8(PL_ADDR + 15) or 0xFF
    local tile = 0xFF
    if TM_ADDR ~= 0 and px < 152 and py < 128 then
        local tx, ty = math.floor((px + 8) / 8), math.floor((py + 12) / 8)
        if tx < 20 and ty < 18 then tile = emu:read8(TM_ADDR + ty * 20 + tx) end
    end
    local hostiles, giants = 0, 0
    if EN_ADDR ~= 0 then
        for i = 0, 31 do
            local p = EN_ADDR + i * 28
            if emu:read8(p) == 2 and emu:read8(p + 1) % 2 == 1 then
                hostiles = hostiles + 1
                if emu:read8(p + 17) == 1 and emu:read8(p + 20) ~= 0 then
                    giants = giants + 1
                end
            end
        end
    end
    local line = string.format(
        "SHOT %-25s  room=%d vic=%d hostiles=%d giants=%d  pos=(%d,%d) tile=0x%02X  hp=%d ifr=%d\n",
        name, rc_room, vic, hostiles, giants, px, py, tile, hp, ifr)
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
walk_to_room(6);  shot("08_BOSS_room")

-- After 5 walks, player ends up at bottom of boss room (walked into south wall).
-- Boss is at center (y=72). Player at ~y=128. Fire UP at boss.
hold(KEY_A + KEY_UP, 200)
shot("09_boss_under_fire")

tick(30)
shot("10_boss_mid_fight")

-- Long sustained assault — boss has 50 HP, 2 dmg/shot, fire every 12 ticks
-- ~16 shots / 200 frames = ~32 damage. Two presses to finish (66 dmg total).
hold(KEY_A + KEY_UP, 400)
tick(60)
shot("11_after_long_assault")

-- START now PAUSES (dims palettes) instead of exiting
press(KEY_START, 4); tick(20); shot("12_paused")
press(KEY_START, 4); tick(20); shot("13_unpaused")

console:log("SMOKETEST DONE")
emu.frontend:quit()
