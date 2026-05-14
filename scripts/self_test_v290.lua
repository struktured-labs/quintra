-- Self-test for Penta Dragon DX v290
-- Uses CGB-flag-only ROM + Lua palette injection to verify colors
-- (The VBlank hook breaks mgba's automated input but works on MiSTer)

local frame = 0
local keys = {[185]=0x80,[193]=0x01,[241]=0x01,[291]=0x01,[341]=0x08,[391]=0x01}
local scy_changes = 0
local prev_scy = -1
local d887_garbage = 0
local prev_d887 = 0

-- BG palette data (from penta_palettes_v097.yaml)
local bg_pals = {
    -- Pal 0: Dungeon floor (White, Light blue, Teal, Black)
    {0xFF,0x7F, 0x94,0x7E, 0x4A,0x3D, 0x00,0x00},
    -- Pal 1: Items (White, Silver-blue, Deep steel, Black)
    {0xFF,0x7F, 0x5A,0x7F, 0x08,0x3D, 0x00,0x00},
    -- Pal 2: Decorative (Magenta)
    {0x1F,0x7E, 0x0F,0x5C, 0x07,0x38, 0x00,0x00},
    -- Pal 3: Nature (Green)
    {0xE0,0x03, 0xA0,0x02, 0x60,0x01, 0x00,0x00},
    -- Pal 4: Water (Cyan)
    {0xE0,0x7F, 0xC0,0x5E, 0x80,0x3D, 0x00,0x00},
    -- Pal 5: Fire (Red)
    {0xFF,0x03, 0xDF,0x00, 0x1F,0x00, 0x00,0x00},
    -- Pal 6: Stone/castle (Blue-gray)
    {0x7B,0x6F, 0x73,0x4E, 0x4A,0x2D, 0x00,0x00},
    -- Pal 7: Mystery (Deep blue)
    {0xFF,0x7F, 0x5C,0xFF, 0x38,0x00, 0x00,0x00},
}

-- Tile-to-palette table (matches create_bg_tile_table)
local function tile_to_pal(tile)
    if tile < 0x05 then return 0
    elseif tile < 0x07 then return 0  -- floor accents
    elseif tile < 0x13 then return 0
    elseif tile < 0x60 then return 6  -- walls
    elseif tile < 0x88 then return 0
    elseif tile < 0xE0 then return 1  -- items
    elseif tile < 0xFE then return 6
    else return 0 end
end

callbacks:add("frame", function()
    frame = frame + 1
    if keys[frame] then emu:setKeys(keys[frame])
    elseif keys[frame-5] then emu:setKeys(0) end
    if frame >= 600 then emu:setKeys(0x40) end  -- walk UP

    local ffc1 = emu:read8(0xFFC1)
    
    -- Load palettes during gameplay
    if ffc1 == 1 then
        -- Write BG palettes
        for p = 0, 7 do
            emu:write8(0xFF68, p * 8 + 0x80)  -- BCPS auto-increment
            for b = 1, 8 do
                emu:write8(0xFF69, bg_pals[p+1][b])
            end
        end
        
        -- Write VBK=1 palette attributes for visible tiles
        local scy = emu:read8(0xFF42)
        local lcdc = emu:read8(0xFF40)
        local base = (bit32.band(lcdc, 0x08) ~= 0) and 0x9C00 or 0x9800
        local start_row = math.floor(scy / 8)
        
        emu:write8(0xFF4F, 0)  -- VBK=0 to read tiles
        for row = 0, 23 do
            local vram_row = (start_row + row) % 32
            for col = 0, 31 do
                local addr = base + vram_row * 32 + col
                local tile = emu:read8(addr)
                local pal = tile_to_pal(tile)
                -- Write attribute to VBK=1
                emu:write8(0xFF4F, 1)
                emu:write8(addr, pal)
                emu:write8(0xFF4F, 0)
            end
        end
        emu:write8(0xFF4F, 0)
    end
    
    -- Track SCY changes (speed metric)
    local scy = emu:read8(0xFF42)
    if scy ~= prev_scy then scy_changes = scy_changes + 1; prev_scy = scy end
    
    -- Track D887 garbage
    local d887 = emu:read8(0xD887)
    if d887 ~= 0 and d887 ~= prev_d887 then
        if d887 < 1 or d887 > 0x29 then d887_garbage = d887_garbage + 1 end
    end
    prev_d887 = d887
    
    -- Screenshots
    if frame == 700 then emu:screenshot("tmp/selftest_f700.png") end
    if frame == 1000 then emu:screenshot("tmp/selftest_f1000.png") end
    
    if frame == 1200 then
        local f = io.open("/tmp/selftest_result.txt", "w")
        f:write(string.format("SCY_changes: %d (frames 1-1200)\n", scy_changes))
        f:write(string.format("D887_garbage: %d\n", d887_garbage))
        f:write(string.format("D880: %02X\n", emu:read8(0xD880)))
        f:write(string.format("FFC1: %02X\n", emu:read8(0xFFC1)))
        f:close()
        os.exit(0)
    end
end)
