-- Build one champion/difficulty set of native mGBA deep-test checkpoints.
-- These are external emulator fixtures. They never modify the cartridge ROM
-- and are loaded explicitly with mGBA's -t/--savestate option.

local OUT = assert(os.getenv("QUINTRA_MGBA_STATE_DIR"))
local REPORT = assert(os.getenv("QUINTRA_MGBA_STATE_REPORT"))
local RS = assert(tonumber(os.getenv("QUINTRA_RS_ADDR")))
local PL = assert(tonumber(os.getenv("QUINTRA_PL_ADDR")))
local EN = assert(tonumber(os.getenv("QUINTRA_EN_ADDR")))
local TM = assert(tonumber(os.getenv("QUINTRA_TM_ADDR")))
local LS = assert(tonumber(os.getenv("QUINTRA_SCREEN_ADDR")))
local WW = assert(tonumber(os.getenv("QUINTRA_WORLD_WIDTH_ADDR")))
local WH = assert(tonumber(os.getenv("QUINTRA_WORLD_HEIGHT_ADDR")))
local LR = assert(tonumber(os.getenv("QUINTRA_LARGE_ROOM_ADDR")))
local CLASS_ID = assert(tonumber(os.getenv("QUINTRA_STATE_CLASS")))
local CHAMPION = assert(os.getenv("QUINTRA_STATE_CHAMPION"))
local DIFFICULTY = assert(os.getenv("QUINTRA_STATE_DIFFICULTY"))
local EASY = DIFFICULTY == "easy"

local KEY_A, KEY_SELECT, KEY_START = 0x01, 0x04, 0x08
local KEY_RIGHT, KEY_LEFT, KEY_DOWN = 0x10, 0x20, 0x80
local BGT_FLOOR, BGT_DOOR, BGT_PORTAL = 1, 3, 34
local SCREEN_ROOM = 5
local STAGE_START = {0, 20, 41, 64, 87, 111, 137, 163, 191}
local STAGE_BOSS = {19, 40, 62, 86, 110, 135, 162, 190, 220}
local VILLAGE = {[3] = 63, [6] = 136}

local report = assert(io.open(REPORT, "w"))

local function tick(frames)
    for _ = 1, frames do emu:runFrame() end
end

local function hold(key, frames)
    for _ = 1, frames do
        emu:setKeys(key)
        emu:runFrame()
    end
    emu:setKeys(0)
    tick(3)
end

local function put16(address, value)
    emu:write8(address, value % 256)
    emu:write8(address + 1, math.floor(value / 256) % 256)
end

local function stamp_portal_apron(tx, ty)
    -- Direct checkpoint routing can begin from any generated silhouette.
    -- Clear the hero-sized collision footprint before putting the trigger
    -- under their feet, otherwise a center pillar can push them off it.
    for y = ty - 2, ty + 1 do
        for x = tx - 1, tx + 1 do
            emu:write8(TM + y * 20 + x, BGT_FLOOR)
        end
    end
    emu:write8(TM + ty * 20 + tx, BGT_PORTAL)
end

local function clear_entities()
    for i = 0, 31 do
        local entity = EN + i * 28
        emu:write8(entity, 0)
        emu:write8(entity + 1, 0)
    end
end

local function live_colossus()
    for i = 0, 31 do
        local entity = EN + i * 28
        if emu:read8(entity) == 2
            and emu:read8(entity + 1) % 2 == 1
            and emu:read8(entity + 17) == 1
            and emu:read8(entity + 20) ~= 0 then
            return true
        end
    end
    return false
end

local function hostile_count()
    local count = 0
    for i = 0, 31 do
        local entity = EN + i * 28
        if emu:read8(entity) == 2 and emu:read8(entity + 1) % 2 == 1 then
            count = count + 1
        end
    end
    return count
end

local function settle(normalize_scroll)
    local ready = 0
    for _ = 1, 300 do
        local committed = emu:read8(0xFF40) >= 0x80
        if committed then
            for i = 0, 339 do
                if emu:read8(TM + i) >= 0x80 then
                    committed = false
                    break
                end
            end
        end
        if committed and normalize_scroll
            and (emu:read8(0xFF42) ~= 0 or emu:read8(0xFF43) ~= 0) then
            committed = false
        end
        ready = committed and (ready + 1) or 0
        if ready >= 8 then return end
        emu:runFrame()
    end
    error("room never reached a save-safe display state")
end

-- Boot through the real title and class selector so class-specific player
-- initialization, palettes, starter weapon, and Easy modifiers are genuine.
tick(240)
hold(KEY_START, 2)
tick(25)
for _ = 1, CLASS_ID do
    hold(KEY_DOWN, 2)
    tick(5)
end
if EASY then
    hold(KEY_SELECT, 2)
    tick(5)
end
hold(KEY_A, 2)
tick(80)
if emu:read8(LS) ~= SCREEN_ROOM or emu:read8(PL) ~= CLASS_ID then
    error("could not boot selected champion into the dungeon")
end

local base_player = {}
for i = 0, 41 do base_player[i] = emu:read8(PL + i) end

local function restore_player(stage)
    for i = 0, 41 do emu:write8(PL + i, base_player[i]) end
    local hp_max, atk, spd = base_player[1], base_player[5], base_player[7]
    local rewards = {22, 27, 29}
    for i = 0, stage - 1 do
        local item = rewards[(i % #rewards) + 1]
        emu:write8(PL + 24 + i, item)
        if item == 22 then
            atk = math.min(15, atk + 1)
        elseif item == 27 then
            atk = math.min(15, atk + 1)
            spd = math.min(9, spd + 1)
        else
            atk = math.min(15, atk + 1)
            hp_max = math.min(30, hp_max + 1)
        end
    end
    emu:write8(PL + 1, hp_max)
    emu:write8(PL + 2, hp_max)
    emu:write8(PL + 5, atk)
    emu:write8(PL + 7, spd)
    put16(PL + 16, math.min(999, stage * 8))
end

local function reset_run(stage)
    for i = 0, 34 do emu:write8(RS + i, 0) end
    emu:write8(RS + 2, 0x0D)
    emu:write8(RS + 3, 0xD0)
    emu:write8(RS + 4, 0xA6)
    emu:write8(RS + 5, 0x51)
    emu:write8(RS + 6, 0xFF)
    put16(RS + 7, stage * 300)
    emu:write8(RS + 9, math.min(255, stage * 10))
    emu:write8(RS + 11, stage)
    put16(RS + 14, math.min(65535, stage * 750))
    emu:write8(RS + 16, math.min(255, stage * 12))
    put16(RS + 23, (2 ^ stage) - 1)
    emu:write8(RS + 26, EASY and 1 or 0)
    restore_player(stage)
end

local function mark_seen(local_room)
    if local_room < 8 then
        emu:write8(RS + 20, (2 ^ (local_room + 1)) - 1)
        emu:write8(RS + 29, 0)
        emu:write8(RS + 31, 0)
        emu:write8(RS + 33, 0)
    elseif local_room < 16 then
        emu:write8(RS + 20, 0xFF)
        emu:write8(RS + 29, (2 ^ (local_room - 7)) - 1)
        emu:write8(RS + 31, 0)
        emu:write8(RS + 33, 0)
    elseif local_room < 24 then
        emu:write8(RS + 20, 0xFF)
        emu:write8(RS + 29, 0xFF)
        emu:write8(RS + 31, (2 ^ (local_room - 15)) - 1)
        emu:write8(RS + 33, 0)
    else
        emu:write8(RS + 20, 0xFF)
        emu:write8(RS + 29, 0xFF)
        emu:write8(RS + 31, 0xFF)
        emu:write8(RS + 33, (2 ^ (local_room - 23)) - 1)
    end
end

local function qualify_stage(stage)
    put16(RS + 23, (2 ^ (stage + 1)) - 1)
    emu:write8(RS + 27, 0x88) -- Warden Boon + Waystone
    emu:write8(RS + 28, 0x80) -- deep Warden
end

local function enter_dungeon(target, stage, qualified, normalize_scroll)
    clear_entities()
    reset_run(stage)
    if qualified then qualify_stage(stage) end
    emu:write8(RS + 1, target - 1)
    emu:write8(RS + 17, 1)
    emu:write8(RS + 18, 6)
    emu:write8(RS + 19, 0)
    put16(PL + 9, 72)
    put16(PL + 11, 60)
    stamp_portal_apron(10, 9)
    for _ = 1, 150 do
        emu:runFrame()
        if emu:read8(RS + 1) == target and emu:read8(RS + 17) == 0 then
            break
        end
    end
    if emu:read8(RS + 1) ~= target or emu:read8(RS + 17) ~= 0 then
        error(string.format(
            "could not enter stage=%d room=%d (actual room=%d world=%d screen=%d x=%d y=%d)",
            stage + 1, target, emu:read8(RS + 1), emu:read8(RS + 17),
            emu:read8(RS + 18), emu:read8(PL + 9), emu:read8(PL + 11)))
    end
    if qualified then qualify_stage(stage) end
    mark_seen(target - STAGE_START[stage + 1])
    if normalize_scroll == nil then
        normalize_scroll = target ~= STAGE_BOSS[stage + 1]
    end
    settle(normalize_scroll)
    emu:write8(PL + 2, emu:read8(PL + 1))
    emu:write8(PL + 4, emu:read8(PL + 3))
    emu:write8(PL + 15, 60)
end

local function state_name(stage, checkpoint)
    local suffix = EASY and "-easy" or ""
    if checkpoint == "riftwild" then
        return string.format(
            "quintra-riftwild-after-stage-%02d-%s%s.ss0",
            stage, CHAMPION, suffix)
    elseif checkpoint == "village" then
        return string.format(
            "quintra-village-after-stage-%02d-%s%s.ss0",
            stage, CHAMPION, suffix)
    end
    return string.format(
        "quintra-stage-%02d-%s-%s%s.ss0",
        stage, checkpoint, CHAMPION, suffix)
end

local function verify_loaded(checkpoint, stage, room, world_mode)
    if emu:read8(RS + 1) ~= room
        or emu:read8(RS + 11) ~= stage
        or emu:read8(RS + 17) ~= world_mode
        or emu:read8(RS + 26) ~= (EASY and 1 or 0)
        or emu:read8(PL) ~= CLASS_ID
        or emu:read8(PL + 2) == 0
        or emu:read8(LS) ~= SCREEN_ROOM then
        error("native state restored the wrong public game context")
    end
    if checkpoint == "boss" and not live_colossus() then
        error("boss checkpoint restored without a live Colossus")
    elseif checkpoint == "court"
        and (emu:read8(LR) == 0 or emu:read8(WW) ~= 224
            or emu:read8(WH) ~= 200) then
        error("court checkpoint restored without its 224x200 dungeon field")
    elseif checkpoint == "sanctuary" and hostile_count() ~= 0 then
        error("sanctuary checkpoint restored with hostiles")
    elseif checkpoint == "riftwild" and emu:read8(RS + 18) ~= 0 then
        error("Riftwild checkpoint restored away from its arrival")
    elseif checkpoint == "village"
        and emu:read8(RS + 19) ~= 0 then
        error("village checkpoint restored away from its arrival square")
    end
end

local function save_checkpoint(checkpoint, human_stage, stage, after_stage)
    emu:setKeys(0)
    tick(2)
    emu:write8(PL + 2, emu:read8(PL + 1))
    emu:write8(PL + 4, emu:read8(PL + 3))
    emu:write8(PL + 15, 60)
    local room = emu:read8(RS + 1)
    local world_mode = emu:read8(RS + 17)
    local name = state_name(after_stage or human_stage, checkpoint)
    local path = OUT .. "/" .. name
    -- The default state flags include an embedded screenshot, while our
    -- deterministic frontend intentionally has no video buffer. Writing the
    -- raw native buffer also avoids mGBA 0.11's POSIX saveStateFile mapping
    -- regression (an O_WRONLY mapping can yield an all-zero state).
    local state = emu:saveStateBuffer(0)
    if not state then error("mGBA could not serialize " .. path) end
    local state_file = assert(io.open(path, "wb"))
    state_file:write(state)
    state_file:close()

    -- Prove mGBA itself can restore every generated file before publishing it.
    emu:write8(RS + 1, 0xEE)
    if not emu:loadStateBuffer(state, 0) then
        error("mGBA could not reload " .. path)
    end
    verify_loaded(checkpoint, stage, room, world_mode)
    report:write(string.format(
        "%s\t%s\t%d\t%d\t%d\t%s\t%d\t%d\n",
        name, checkpoint, human_stage, after_stage or 0, room,
        DIFFICULTY, CLASS_ID, world_mode))
    report:flush()
end

for stage = 0, 8 do
    local entry = stage == 0 and 1 or STAGE_START[stage + 1]
    enter_dungeon(entry, stage, false)
    save_checkpoint("entry", stage + 1, stage)

    enter_dungeon(STAGE_START[stage + 1] + 5, stage, false, false)
    mark_seen(5)
    save_checkpoint("court", stage + 1, stage)

    enter_dungeon(STAGE_BOSS[stage + 1] - 1, stage, true)
    save_checkpoint("sanctuary", stage + 1, stage)

    enter_dungeon(STAGE_BOSS[stage + 1], stage, true)
    tick(24)
    emu:write8(PL + 2, emu:read8(PL + 1))
    save_checkpoint("boss", stage + 1, stage)
end

for after_stage = 1, 8 do
    -- Build the next stage's progression, then cross the prior defeated
    -- Colossus room's real south threshold into Riftwild screen zero.
    enter_dungeon(STAGE_START[after_stage + 1], after_stage, false)
    emu:write8(RS + 1, STAGE_BOSS[after_stage])
    emu:write8(RS + 6, 0xFF)
    emu:write8(RS + 17, 0)
    emu:write8(RS + 18, 0)
    emu:write8(RS + 19, 0)
    emu:write8(RS + 20, 0)
    emu:write8(RS + 21, 0)
    emu:write8(RS + 22, 0)
    clear_entities()
    emu:write8(TM + 16 * 20 + 9, BGT_DOOR)
    emu:write8(TM + 16 * 20 + 10, BGT_DOOR)
    put16(PL + 9, 72)
    put16(PL + 11, 120)
    for _ = 1, 150 do
        emu:setKeys(KEY_DOWN)
        emu:runFrame()
        if emu:read8(RS + 17) == 1 then break end
    end
    emu:setKeys(0)
    if emu:read8(RS + 17) ~= 1 or emu:read8(RS + 18) ~= 0 then
        error("could not enter Riftwild after stage " .. after_stage)
    end
    settle(true)
    save_checkpoint("riftwild", after_stage + 1, after_stage, after_stage)
end

for _, after_stage in ipairs({3, 6}) do
    enter_dungeon(STAGE_START[after_stage + 1], after_stage, false)
    emu:write8(RS + 1, STAGE_BOSS[after_stage])
    emu:write8(RS + 11, after_stage)
    emu:write8(RS + 17, 1)
    emu:write8(RS + 18, 6)
    emu:write8(RS + 19, 0)
    clear_entities()
    stamp_portal_apron(10, 8)
    put16(PL + 9, 72)
    put16(PL + 11, 52)
    for _ = 1, 150 do
        emu:runFrame()
        if emu:read8(RS + 1) == VILLAGE[after_stage]
            and emu:read8(RS + 17) == 0 then break end
    end
    if emu:read8(RS + 1) ~= VILLAGE[after_stage] then
        error("could not enter village after stage " .. after_stage)
    end
    settle(true)

    -- Exercise both halves of the civic edge and save on the safe arrival.
    put16(PL + 9, 144); put16(PL + 11, 60)
    for _ = 1, 120 do
        emu:setKeys(KEY_RIGHT); emu:runFrame()
        if emu:read8(RS + 19) == 1 then break end
    end
    emu:setKeys(0)
    if emu:read8(RS + 19) ~= 1 then error("village market edge failed") end
    settle(true)
    put16(PL + 9, 0); put16(PL + 11, 60)
    for _ = 1, 120 do
        emu:setKeys(KEY_LEFT); emu:runFrame()
        if emu:read8(RS + 19) == 0 then break end
    end
    emu:setKeys(0)
    if emu:read8(RS + 19) ~= 0 then error("village return edge failed") end
    settle(true)
    save_checkpoint("village", after_stage + 1, after_stage, after_stage)
end

report:write("DONE\n")
report:close()
console:log(string.format(
    "MGBA STATES DONE champion=%s difficulty=%s count=46",
    CHAMPION, DIFFICULTY))
emu.frontend:quit()
