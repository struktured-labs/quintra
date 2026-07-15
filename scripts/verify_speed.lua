-- Speed Verification for Penta Dragon DX
-- Starts game, walks RIGHT for 10 seconds, counts game state advancement frames.
-- Compares to original ROM's advancement rate.
-- Outputs JSON report.

local OUTPUT = os.getenv("VERIFY_OUTPUT") or "verify_speed_report.json"
local TEST_DURATION = 600  -- 10 seconds at 60fps
local ROM_LABEL = os.getenv("VERIFY_ROM_LABEL") or "dx"

-- Title menu input sequence
local TITLE = {
    {180, 185, 0x80},  -- DOWN
    {193, 198, 0x01},  -- A
    {241, 246, 0x01},  -- A
    {291, 296, 0x01},  -- A
    {341, 346, 0x08},  -- START
    {391, 396, 0x01},  -- A
}

local frame = 0
local gameplay_started = false
local game_start_frame = 0
local test_start_frame = 0
local test_running = false

-- Tracking counters
local d880_changes = 0
local ffbd_changes = 0
local dc81_changes = 0
local scroll_ticks = 0

local prev_d880 = -1
local prev_ffbd = -1
local prev_dc81 = -1
local prev_scx = -1

-- OAM change detection
local prev_oam_hash = 0
local oam_change_count = 0

local function hash_oam()
    local sum = 0
    for i = 0, 39 do
        local base = 0xFE00 + i * 4
        sum = (sum * 31 + emu:read8(base)) % 0xFFFFFF
        sum = (sum * 31 + emu:read8(base + 1)) % 0xFFFFFF
    end
    return sum
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

    -- Track FFC1
    local ffc1 = emu:read8(0xFFC1)
    if ffc1 == 1 and not gameplay_started then
        gameplay_started = true
        game_start_frame = frame
        -- Wait 120 frames for game to stabilize before test
        test_start_frame = frame + 120
    end

    -- Before test: navigate menu
    if not gameplay_started then
        emu:setKeys(keys)
        return
    end

    -- Stabilization period
    if frame < test_start_frame then
        emu:setKeys(0)
        -- Keep alive
        emu:write8(0xDCDD, 0x17)
        emu:write8(0xDCDC, 0xFF)
        emu:write8(0xDCBB, 0xFF)
        return
    end

    -- Start test
    if not test_running then
        test_running = true
        prev_d880 = emu:read8(0xD880)
        prev_ffbd = emu:read8(0xFFBD)
        prev_dc81 = emu:read8(0xDC81)
        prev_scx = emu:read8(0xFF43)
        prev_oam_hash = hash_oam()
    end

    -- During test: walk RIGHT
    local elapsed = frame - test_start_frame
    if elapsed < TEST_DURATION then
        emu:setKeys(0x10)  -- RIGHT

        -- Keep alive
        emu:write8(0xDCDD, 0x17)
        emu:write8(0xDCDC, 0xFF)
        emu:write8(0xDCBB, 0xFF)

        -- Track state changes
        local d880 = emu:read8(0xD880)
        local ffbd = emu:read8(0xFFBD)
        local dc81 = emu:read8(0xDC81)
        local scx = emu:read8(0xFF43)

        if d880 ~= prev_d880 then d880_changes = d880_changes + 1 end
        if ffbd ~= prev_ffbd then ffbd_changes = ffbd_changes + 1 end
        if dc81 ~= prev_dc81 then dc81_changes = dc81_changes + 1 end
        if scx ~= prev_scx then scroll_ticks = scroll_ticks + 1 end

        prev_d880 = d880
        prev_ffbd = ffbd
        prev_dc81 = dc81
        prev_scx = scx

        local h = hash_oam()
        if h ~= prev_oam_hash then oam_change_count = oam_change_count + 1 end
        prev_oam_hash = h
    else
        -- Test complete
        emu:setKeys(0)

        local f = io.open(OUTPUT, "w")
        if f then
            f:write('{\n')
            f:write(string.format('  "rom_label": "%s",\n', ROM_LABEL))
            f:write(string.format('  "test_frames": %d,\n', TEST_DURATION))
            f:write(string.format('  "game_start_frame": %d,\n', game_start_frame))
            f:write(string.format('  "d880_changes": %d,\n', d880_changes))
            f:write(string.format('  "ffbd_changes": %d,\n', ffbd_changes))
            f:write(string.format('  "dc81_changes": %d,\n', dc81_changes))
            f:write(string.format('  "scroll_ticks": %d,\n', scroll_ticks))
            f:write(string.format('  "oam_changes": %d\n', oam_change_count))
            f:write('}\n')
            f:close()
        end

        console:log(string.format("[VERIFY_SPEED] %s: scroll=%d dc81=%d oam=%d in %d frames",
            ROM_LABEL, scroll_ticks, dc81_changes, oam_change_count, TEST_DURATION))

        local df = io.open("DONE_VERIFY_SPEED_" .. ROM_LABEL, "w")
        if df then df:write("OK"); df:close() end

        emu:quit()
    end
end)
