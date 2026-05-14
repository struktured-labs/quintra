-- Scroll Bleed Verification: measures % of visible BG tiles with wrong palette
-- Walks RIGHT for 10s, checks palette attributes every 30 frames during scrolling

local KEY_A, KEY_DOWN, KEY_START, KEY_RIGHT = 0x01, 0x80, 0x08, 0x10
local TITLE = {
    {180,185,KEY_DOWN},{186,200,0},{201,206,KEY_A},{207,260,0},
    {261,266,KEY_A},{267,320,0},{321,326,KEY_A},{327,380,0},
    {381,386,KEY_START},{387,430,0},{431,436,KEY_A},
}
local f, gameStarted, gsf, done = 0, false, 0, false
local totalChecked, totalMismatched, scanCount = 0, 0, 0

-- Load bg_tile_table from bank 13
local bgTable = nil
local function loadBgTable()
    local oldBank = emu:read8(0xFF99)
    emu:write8(0x2000, 0x0D)
    local tbl = {}
    for i = 0, 255 do tbl[i] = emu:read8(0x7000 + i) end
    emu:write8(0x2000, oldBank)
    return tbl
end

local function scanPalettes()
    local lcdc = emu:read8(0xFF40)
    local base = ((lcdc & 0x08) ~= 0) and 0x9C00 or 0x9800
    local scy = emu:read8(0xFF42)
    local scx = emu:read8(0xFF43)
    local startRow = math.floor(scy / 8)
    local startCol = math.floor(scx / 8)
    local mismatches, checked = 0, 0

    for row = 0, 17 do
        local tileRow = (startRow + row) % 32
        for col = 0, 19 do
            local tileCol = (startCol + col) % 32
            local addr = base + tileRow * 32 + tileCol
            local tileId = emu:read8(addr)
            emu:write8(0xFF4F, 1)
            local palAttr = emu:read8(addr)
            emu:write8(0xFF4F, 0)
            local expected = bgTable[tileId]
            checked = checked + 1
            if palAttr ~= expected then mismatches = mismatches + 1 end
        end
    end
    return mismatches, checked
end

callbacks:add("frame", function()
    if done then return end
    f = f + 1
    local ffc1 = emu:read8(0xFFC1)
    if not gameStarted and ffc1 == 1 then
        gameStarted = true; gsf = f
        bgTable = loadBgTable()
    end
    if not gameStarted then
        local keys = 0
        for _, s in ipairs(TITLE) do
            if f >= s[1] and f <= s[2] then keys = s[3]; break end
        end
        emu:setKeys(keys)
        return
    end
    local elapsed = f - gsf
    -- Walk right + fire
    local keys = KEY_RIGHT
    if f % 4 ~= 0 then keys = keys + KEY_A end
    emu:setKeys(keys)
    emu:write8(0xDCDD, 0x17); emu:write8(0xDCDC, 0xFF); emu:write8(0xDCBB, 0xFF)

    -- Scan every 30 frames after initial settling
    if elapsed > 60 and elapsed <= 600 and elapsed % 30 == 0 then
        local m, c = scanPalettes()
        totalMismatched = totalMismatched + m
        totalChecked = totalChecked + c
        scanCount = scanCount + 1
    end

    if elapsed > 600 then
        done = true
        local rate = totalChecked > 0 and (totalMismatched / totalChecked) or 0
        local correct = 1.0 - rate
        local file = io.open("tmp/verify/scroll_bleed.txt", "w")
        file:write(string.format("scans=%d\n", scanCount))
        file:write(string.format("total_checked=%d\n", totalChecked))
        file:write(string.format("total_mismatched=%d\n", totalMismatched))
        file:write(string.format("correct_rate=%.4f\n", correct))
        file:write(string.format("mismatch_rate=%.4f\n", rate))
        file:close()
    end
end)
