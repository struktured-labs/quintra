-- Quintra Phase 5 smoke test.
-- Boots → TITLE → CLASS_SELECT → ROOM → walk around → fire in 4 directions
-- → screenshot at each stage → exit.

local OUT_DIR = os.getenv("QUINTRA_OUT_DIR") or "/tmp/quintra-smoketest"

-- GBDK joypad bitmask
local KEY_A      = 0x01
local KEY_B      = 0x02
local KEY_SELECT = 0x04
local KEY_START  = 0x08
local KEY_RIGHT  = 0x10
local KEY_LEFT   = 0x20
local KEY_UP     = 0x40
local KEY_DOWN   = 0x80

local function shot(name)
    local path = OUT_DIR .. "/h_" .. name .. ".png"
    emu:screenshot(path)
    console:log("SHOT " .. name)
end

local function tick(n) for _ = 1, n do emu:runFrame() end end

local function press(key, frames_held)
    emu:setKeys(key)
    tick(frames_held or 4)
    emu:setKeys(0)
    tick(4)
end

local function tap(key) press(key, 2) end

-- Boot + settle
tick(120); shot("01_title")

-- TITLE → CLASS_SELECT
tap(KEY_START); tick(40); shot("02_class_select")

-- CLASS_SELECT → RUN_INIT → ROOM
tap(KEY_A); tick(40); shot("03_room_enter")

-- Movement
press(KEY_LEFT, 24); shot("04_room_left")
press(KEY_DOWN, 24); shot("05_room_down")
press(KEY_RIGHT, 24); shot("06_room_right")

-- Wall push (UP held 80 frames)
press(KEY_UP, 80); shot("07_room_wall_push")

-- Re-center and fire in 4 directions
-- Walk back down to center
press(KEY_DOWN, 30)
press(KEY_RIGHT, 10)
shot("08_pre_fire")

-- Fire B right
press(KEY_B + KEY_RIGHT, 6)
tick(8); shot("09_fire_right")

-- Fire B up
press(KEY_B + KEY_UP, 6)
tick(8); shot("10_fire_up")

-- Spray for a while + try to hit enemies
emu:setKeys(KEY_B + KEY_LEFT); tick(40); emu:setKeys(0); tick(20)
shot("11_after_spray")

-- Wait and screenshot final state (enemies may have wandered, projectiles cleared)
tick(60); shot("12_after_settle")

console:log("SMOKETEST DONE")
emu.frontend:quit()
