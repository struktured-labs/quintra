-- Phantom sound detector v2: more aggressive gameplay exercise.
-- Cycles through: shoot, item-cycle (up/down in pause), drop-item (start press),
-- secondary-fire (B). User's exact complaint was phantom sounds "when using
-- items / actions" so we hit item-use and pause-menu actions.

local OUT = os.getenv("STATE_PATH") or "/tmp/penta_d887.txt"
local MEASURE_FRAMES = tonumber(os.getenv("MEASURE_FRAMES") or "1800")  -- 30s
local MAX_BOOT_FRAMES = tonumber(os.getenv("MAX_BOOT_FRAMES") or "600")

local KEY_A     = 0x01
local KEY_B     = 0x02
local KEY_SEL   = 0x04
local KEY_START = 0x08
local KEY_RIGHT = 0x10
local KEY_LEFT  = 0x20
local KEY_UP    = 0x40
local KEY_DOWN  = 0x80

local SCHEDULE = {
    {180, 185, KEY_DOWN}, {186, 200, 0},
    {201, 206, KEY_A},    {207, 260, 0},
    {261, 266, KEY_A},    {267, 320, 0},
    {321, 326, KEY_A},    {327, 380, 0},
    {381, 386, KEY_START}, {387, 430, 0},
    {431, 436, KEY_A},
}

-- Gameplay action cycle: 30-frame phases that exercise different sound triggers
-- Phase 0:  walk right + shoot A (footsteps + projectile sounds)
-- Phase 1:  walk down + shoot A
-- Phase 2:  fire B (mega-flash if available)
-- Phase 3:  pause menu (START)
-- Phase 4:  item cycle (UP/DOWN in pause)
-- Phase 5:  drop item (START while item held — user said this drops items)
-- Phase 6:  unpause (START)
-- Phase 7:  idle
local GAMEPLAY_PHASES = {
    {30, KEY_RIGHT + KEY_A},
    {30, KEY_DOWN + KEY_A},
    {15, KEY_B},
    {15, 0},
    {6,  KEY_START},
    {30, 0},
    {15, KEY_UP},
    {15, KEY_DOWN},
    {6,  KEY_START},  -- drop item
    {30, 0},
    {6,  KEY_START},  -- unpause
    {30, 0},
}

local f = 0
local gameplay_at = -1
local prev_d887 = 0
local transitions = 0
local trans_log = {}
local fired = false

callbacks:add("frame", function()
    if fired then return end
    f = f + 1

    if gameplay_at < 0 then
        local keys = 0
        for _, sched in ipairs(SCHEDULE) do
            if f >= sched[1] and f <= sched[2] then keys = sched[3]; break end
        end
        emu:setKeys(keys)
        if emu:read8(0xFFC1) == 1 then
            gameplay_at = f
            prev_d887 = emu:read8(0xD887)
            console:log("gameplay reached at frame " .. f)
        elseif f >= MAX_BOOT_FRAMES then
            local fh = io.open(OUT, "w")
            fh:write("transitions=-1\n# gameplay never reached\n")
            fh:close()
            os.exit(0)
        end
        return
    end

    local elapsed = f - gameplay_at
    -- Walk gameplay phases cyclically
    local cycle_total = 0
    for _, ph in ipairs(GAMEPLAY_PHASES) do cycle_total = cycle_total + ph[1] end
    local in_cycle = elapsed % cycle_total
    local acc = 0
    local keys = 0
    for _, ph in ipairs(GAMEPLAY_PHASES) do
        if in_cycle < acc + ph[1] then keys = ph[2]; break end
        acc = acc + ph[1]
    end
    emu:setKeys(keys)

    -- Godmode HP so we don't die during the test
    emu:write8(0xDCDD, 0x17)
    emu:write8(0xDCDC, 0xFF)
    emu:write8(0xDCBB, 0xFF)

    local d887 = emu:read8(0xD887)
    if d887 ~= prev_d887 then
        transitions = transitions + 1
        if #trans_log < 300 then
            table.insert(trans_log, string.format("f=%d  D887: %02X -> %02X  in_cycle=%d",
                f, prev_d887, d887, in_cycle))
        end
        prev_d887 = d887
    end

    if elapsed >= MEASURE_FRAMES then
        fired = true
        local fh = io.open(OUT, "w")
        fh:write(string.format("# Phantom sound D887 monitor v2 (aggressive)\n"))
        fh:write(string.format("# Boot frames: %d, measure frames: %d (=%.1fs)\n",
            gameplay_at, MEASURE_FRAMES, MEASURE_FRAMES/60))
        fh:write(string.format("transitions=%d\n", transitions))
        fh:write(string.format("transitions_per_second=%.2f\n", transitions * 60 / MEASURE_FRAMES))
        fh:write("\n--- first 300 transitions ---\n")
        for _, l in ipairs(trans_log) do fh:write(l .. "\n") end
        fh:close()
        console:log(string.format("phantom_d887_v2: %d transitions in %d frames",
            transitions, MEASURE_FRAMES))
        os.exit(0)
    end
end)
