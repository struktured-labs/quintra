-- Dual ROM Frame Comparison State Dumper
-- Runs one ROM with identical input, dumps key memory each frame to CSV.
-- Python driver runs this twice (original + DX) then compares.
-- Config via env: VERIFY_DUMP_DIR, VERIFY_MAX_FRAMES

local DUMP_DIR = os.getenv("VERIFY_DUMP_DIR") or "verify_dual"
local MAX_FRAMES = tonumber(os.getenv("VERIFY_MAX_FRAMES") or "600")
local ROM_LABEL = os.getenv("VERIFY_ROM_LABEL") or "unknown"
local DUMP_INTERVAL = tonumber(os.getenv("VERIFY_DUMP_INTERVAL") or "1")

-- Title menu input sequence (identical for both ROMs)
local TITLE = {
    {180, 185, 0x80},  -- DOWN
    {193, 198, 0x01},  -- A
    {241, 246, 0x01},  -- A
    {291, 296, 0x01},  -- A
    {341, 346, 0x08},  -- START
    {391, 396, 0x01},  -- A
}

-- Gameplay inputs: walk RIGHT for the entire test
local GAMEPLAY_START = 500
local GAMEPLAY_KEY = 0x10  -- RIGHT

-- Memory addresses to dump
local ADDRS = {
    {0xD880, "D880"},   -- master scene state
    {0xFFC1, "FFC1"},   -- gameplay active
    {0xFFBD, "FFBD"},   -- room/section
    {0xFFBF, "FFBF"},   -- boss flag
    {0xFF93, "FF93"},   -- raw joypad
    {0xDCDD, "DCDD"},   -- HP main
    {0xDC81, "DC81"},   -- section scroll counter
    {0xFF43, "SCX"},    -- scroll X
    {0xFF42, "SCY"},    -- scroll Y
    {0xFFCF, "FFCF"},   -- scroll position index
}

local frame = 0
local gameplay_started = false
local game_start_frame = 0

-- Open CSV
local csv_path = DUMP_DIR .. "/state_" .. ROM_LABEL .. ".csv"
local csv = io.open(csv_path, "w")
if not csv then
    console:log("ERROR: cannot write to " .. csv_path)
    return
end

-- Write header
local hdr = "frame,keys"
for _, a in ipairs(ADDRS) do
    hdr = hdr .. "," .. a[2]
end
csv:write(hdr .. "\n")

callbacks:add("frame", function()
    frame = frame + 1

    -- Determine keys
    local keys = 0

    -- Title menu
    for _, seq in ipairs(TITLE) do
        if frame >= seq[1] and frame <= seq[2] then
            keys = seq[3]
            break
        end
    end

    -- Track gameplay
    local ffc1 = emu:read8(0xFFC1)
    if ffc1 == 1 and not gameplay_started then
        gameplay_started = true
        game_start_frame = frame
    end

    -- Gameplay: walk RIGHT
    if gameplay_started and frame >= GAMEPLAY_START then
        keys = GAMEPLAY_KEY
        -- Keep alive (identical for both ROMs)
        emu:write8(0xDCDD, 0x17)
        emu:write8(0xDCDC, 0xFF)
        emu:write8(0xDCBB, 0xFF)
    end

    emu:setKeys(keys)

    -- Dump state at interval
    if frame % DUMP_INTERVAL == 0 then
        local line = frame .. "," .. keys
        for _, a in ipairs(ADDRS) do
            line = line .. "," .. emu:read8(a[1])
        end
        csv:write(line .. "\n")
    end

    -- Done
    if frame >= MAX_FRAMES then
        csv:flush()
        csv:close()
        console:log(string.format("[DUAL_COMPARE] %s: %d frames dumped to %s",
            ROM_LABEL, frame, csv_path))

        local df = io.open("DONE_DUAL_" .. ROM_LABEL, "w")
        if df then df:write("OK"); df:close() end

        emu:quit()
    end
end)
