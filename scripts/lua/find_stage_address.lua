-- find_stage_address.lua
-- Scans WRAM and HRAM to find addresses that might store the stage number

local frame = 0
local output = {}

-- Sample interesting WRAM ranges
local function scan_memory()
    local data = {}

    -- Scan WRAM (C000-CFFF)
    for addr = 0xC000, 0xCFFF do
        data[addr] = emu:read8(addr)
    end

    -- Scan HRAM (FF80-FFFE, excluding known addresses)
    for addr = 0xFF80, 0xFFFE do
        data[addr] = emu:read8(addr)
    end

    -- Check known gameplay addresses
    data[0xFFC1] = emu:read8(0xFFC1)  -- Gameplay active
    data[0xFFC2] = emu:read8(0xFFC2)  -- Stage title
    data[0xFFBF] = emu:read8(0xFFBF)  -- Boss flag

    return data
end

-- Look for single-byte values in range 0-10 (likely stage numbers)
local function find_candidates(data)
    local candidates = {}

    for addr, value in pairs(data) do
        if value >= 0 and value <= 10 then
            table.insert(candidates, {addr = addr, value = value})
        end
    end

    -- Sort by address
    table.sort(candidates, function(a, b) return a.addr < b.addr end)

    return candidates
end

callbacks:add("frame", function()
    frame = frame + 1

    if frame == 1 then
        console:log("=== Memory Scan Start ===")
        console:log("ROM loaded, scanning after 1 frame...")
    end

    if frame == 60 then
        -- Scan after 60 frames (1 second of gameplay)
        console:log("\n=== Scanning memory at frame 60 ===")
        local data = scan_memory()
        local candidates = find_candidates(data)

        console:log(string.format("Found %d candidate addresses (value 0-10):", #candidates))
        console:log("\nKey addresses to check:")
        console:log(string.format("  0xFFC1 (gameplay) = 0x%02X", emu:read8(0xFFC1)))
        console:log(string.format("  0xFFC2 (title)    = 0x%02X", emu:read8(0xFFC2)))
        console:log(string.format("  0xFFBF (boss)     = 0x%02X", emu:read8(0xFFBF)))

        console:log("\nLikely stage address candidates:")
        local count = 0
        for _, cand in ipairs(candidates) do
            -- Focus on HRAM and high WRAM (more likely to store state)
            if cand.addr >= 0xFF80 or (cand.addr >= 0xC200 and cand.addr <= 0xC300) then
                console:log(string.format("  0x%04X = 0x%02X (%d)", cand.addr, cand.value, cand.value))
                count = count + 1
                if count >= 20 then
                    console:log("  ... (showing first 20)")
                    break
                end
            end
        end

        -- Also check entity data region
        console:log("\nEntity region (C200-C2FF) values 0-5:")
        for addr = 0xC200, 0xC2FF do
            local val = emu:read8(addr)
            if val >= 0 and val <= 5 then
                console:log(string.format("  0x%04X = 0x%02X", addr, val))
            end
        end

        -- Take screenshot
        emu:screenshot("tmp/stage_scan.png")
        console:log("\nScreenshot saved to tmp/stage_scan.png")
        console:log("=== Scan Complete ===")

        -- Write DONE marker
        local f = io.open('DONE', 'w')
        if f then
            f:write('OK')
            f:close()
        end

        -- Quit emulator
        emu:quit()
    end
end)
