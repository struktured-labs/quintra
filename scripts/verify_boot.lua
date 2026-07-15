-- Boot Verification for Penta Dragon DX
-- Checks: game boots, FFC1=1 (gameplay active), D880 transitions, no crash
-- Outputs JSON report to VERIFY_OUTPUT env var (or verify_boot_report.json)
--
-- Key bitmask: A=0x01, B=0x02, SELECT=0x04, START=0x08,
--              RIGHT=0x10, LEFT=0x20, UP=0x40, DOWN=0x80

local OUTPUT = os.getenv("VERIFY_OUTPUT") or "verify_boot_report.json"
local MAX_FRAMES = tonumber(os.getenv("VERIFY_MAX_FRAMES") or "600")
local NO_CRASH_FRAMES = tonumber(os.getenv("VERIFY_NOCRASH_FRAMES") or "3600")
local MODE = os.getenv("VERIFY_MODE") or "boot" -- "boot" or "nocrash"

-- Title menu input sequence (verified working)
local TITLE = {
    {180, 185, 0x80},  -- DOWN
    {193, 198, 0x01},  -- A
    {241, 246, 0x01},  -- A
    {291, 296, 0x01},  -- A
    {341, 346, 0x08},  -- START
    {391, 396, 0x01},  -- A
}

local frame = 0
local ffc1_frame = -1
local d880_transitions = {}
local last_d880 = -1
local gameplay_started = false
local d880_reached_dungeon = false
local d880_dungeon_frame = -1
local total_frames_target = MAX_FRAMES

-- Liveness tracking: use game's internal VBlank tick counter
-- The game increments FFF5/FFF6 (stopwatch timer) every 60 frames during gameplay
-- Also track D880 changes as a heartbeat signal
local d880_change_count = 0
local prev_d880_live = -1
local lcdc_off_frames = 0  -- LCDC bit 7 = 0 means LCD disabled (potential crash)

if MODE == "nocrash" then
    total_frames_target = NO_CRASH_FRAMES
end

callbacks:add("frame", function()
    frame = frame + 1

    -- Apply title menu inputs
    local keys = 0
    for _, seq in ipairs(TITLE) do
        if frame >= seq[1] and frame <= seq[2] then
            keys = seq[3]
            break
        end
    end

    -- During no-crash mode, walk RIGHT after gameplay starts
    if MODE == "nocrash" and gameplay_started and frame > 900 then
        keys = 0x10  -- RIGHT
    end

    emu:setKeys(keys)

    -- Track FFC1 (gameplay active flag)
    local ffc1 = emu:read8(0xFFC1)
    if ffc1 == 1 and ffc1_frame < 0 then
        ffc1_frame = frame
        gameplay_started = true
    end

    -- Track D880 (master scene state)
    local d880 = emu:read8(0xD880)
    if d880 ~= last_d880 then
        table.insert(d880_transitions, {frame = frame, from = last_d880, to = d880})
        last_d880 = d880
        d880_change_count = d880_change_count + 1
    end

    -- Track D880=2 (dungeon = actual gameplay)
    if d880 == 2 and not d880_reached_dungeon then
        d880_reached_dungeon = true
        d880_dungeon_frame = frame
    end

    -- Infinite HP during gameplay (keep alive for no-crash test)
    if gameplay_started then
        emu:write8(0xDCDD, 0x17)
        emu:write8(0xDCDC, 0xFF)
        emu:write8(0xDCBB, 0xFF)
    end

    -- Liveness: check LCDC bit 7 (LCD enable)
    local lcdc = emu:read8(0xFF40)
    if lcdc < 0x80 and gameplay_started then
        lcdc_off_frames = lcdc_off_frames + 1
    end

    -- Exit
    if frame >= total_frames_target then
        -- Build report
        local transitions_str = "["
        for i, t in ipairs(d880_transitions) do
            if i > 1 then transitions_str = transitions_str .. "," end
            transitions_str = transitions_str .. string.format(
                '{"frame":%d,"from":%d,"to":%d}', t.frame, t.from, t.to
            )
        end
        transitions_str = transitions_str .. "]"

        -- Determine pass/fail
        -- Boot OK = FFC1 became 1 within 500 frames
        local boot_ok = ffc1_frame > 0 and ffc1_frame < 500

        -- No-hang detection:
        -- 1. D880 should have changed at least a few times (init -> title -> gameplay)
        -- 2. LCDC should not be disabled for extended periods during gameplay
        local no_hang = d880_change_count >= 3 and lcdc_off_frames < 60

        local passed = boot_ok and no_hang

        local f = io.open(OUTPUT, "w")
        if f then
            f:write('{\n')
            f:write(string.format('  "mode": "%s",\n', MODE))
            f:write(string.format('  "total_frames": %d,\n', frame))
            f:write(string.format('  "ffc1_frame": %d,\n', ffc1_frame))
            f:write(string.format('  "gameplay_started": %s,\n', gameplay_started and "true" or "false"))
            f:write(string.format('  "d880_reached_dungeon": %s,\n', d880_reached_dungeon and "true" or "false"))
            f:write(string.format('  "d880_dungeon_frame": %d,\n', d880_dungeon_frame))
            f:write(string.format('  "d880_change_count": %d,\n', d880_change_count))
            f:write(string.format('  "lcdc_off_frames": %d,\n', lcdc_off_frames))
            f:write(string.format('  "d880_transitions": %s,\n', transitions_str))
            f:write(string.format('  "boot_ok": %s,\n', boot_ok and "true" or "false"))
            f:write(string.format('  "no_hang": %s,\n', no_hang and "true" or "false"))
            f:write(string.format('  "passed": %s\n', passed and "true" or "false"))
            f:write('}\n')
            f:close()
        end

        console:log(string.format("[VERIFY_BOOT] FFC1@%d d880_changes=%d lcdc_off=%d passed=%s",
            ffc1_frame, d880_change_count, lcdc_off_frames, passed and "YES" or "NO"))

        -- Write done marker
        local df = io.open("DONE_VERIFY_BOOT", "w")
        if df then df:write("OK"); df:close() end

        emu:quit()
    end
end)
