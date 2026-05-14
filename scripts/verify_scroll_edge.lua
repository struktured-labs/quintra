-- Scroll-edge verification test
-- Measures palette attribute delay for newly visible tiles during scrolling
-- Runs on CGB-flag-only ROM with Lua palette injection (matches v290 sweep behavior)

local frame = 0
local keys = {[185]=0x80,[193]=0x01,[241]=0x01,[291]=0x01,[341]=0x08,[391]=0x01}
local prev_scy_row = -1
local edge_delays = {}
local pending_edges = {}  -- {row=, appear_frame=}

-- Tile to palette (matches v290 table)
local function tile_pal(t)
    if t < 0x05 then return 0
    elseif t < 0x07 then return 0
    elseif t < 0x13 then return 0
    elseif t < 0x60 then return 6
    elseif t < 0x88 then return 0
    elseif t < 0xE0 then return 1
    elseif t < 0xFE then return 6
    else return 0 end
end

-- Simulate v290 sweep: 2 rows per frame, direction-aware edge priority
local sweep_row = 0
local prev_scy8 = 0

local function do_sweep()
    local scy = emu:read8(0xFF42)
    local scy8 = math.floor(scy / 8)
    local lcdc = emu:read8(0xFF40)
    local base = 0x9800
    if lcdc % 16 >= 8 then base = 0x9C00 end
    
    -- Edge priority
    if scy8 ~= prev_scy8 then
        local diff = (scy8 - prev_scy8) % 32
        if diff < 16 then
            sweep_row = 17  -- scrolling down, bottom edge
        else
            sweep_row = 0   -- scrolling up, top edge
        end
        prev_scy8 = scy8
    end
    
    -- Write palettes + BG palette attrs for 2 rows
    emu:write8(0xFF68, 0x80)
    local p0 = {0xFF,0x7F, 0x94,0x7E, 0x4A,0x3D, 0x00,0x00}
    for i=1,8 do emu:write8(0xFF69, p0[i]) end
    emu:write8(0xFF68, 0x80+8)
    local p1 = {0xFF,0x7F, 0x5A,0x7F, 0x08,0x3D, 0x00,0x00}
    for i=1,8 do emu:write8(0xFF69, p1[i]) end
    emu:write8(0xFF68, 0x80+48)
    local p6 = {0x7B,0x6F, 0x73,0x4E, 0x4A,0x2D, 0x00,0x00}
    for i=1,8 do emu:write8(0xFF69, p6[i]) end
    
    for r = 0, 1 do
        local vr = (scy8 + sweep_row) % 32
        for col = 0, 31 do
            local addr = base + vr * 32 + col
            emu:write8(0xFF4F, 0)
            local tile = emu:read8(addr)
            local pal = tile_pal(tile)
            emu:write8(0xFF4F, 1)
            emu:write8(addr, pal)
        end
        sweep_row = (sweep_row + 1) % 24
    end
    emu:write8(0xFF4F, 0)
end

callbacks:add("frame", function()
    frame = frame + 1
    if keys[frame] then emu:setKeys(keys[frame])
    elseif keys[frame-5] then emu:setKeys(0) end
    if frame >= 600 then emu:setKeys(0x40) end  -- walk UP
    
    local ffc1 = emu:read8(0xFFC1)
    if ffc1 == 1 then
        -- Track new scroll rows appearing
        local scy = emu:read8(0xFF42)
        local scy_row = math.floor(scy / 8)
        if scy_row ~= prev_scy_row and prev_scy_row >= 0 then
            -- New row appeared at scroll edge
            table.insert(pending_edges, {row=scy_row, appear=frame, colored=false})
        end
        prev_scy_row = scy_row
        
        -- Run sweep simulation
        do_sweep()
        
        -- Check pending edges — are they colored yet?
        local lcdc = emu:read8(0xFF40)
        local base = 0x9800
        if lcdc % 16 >= 8 then base = 0x9C00 end
        
        for _, edge in ipairs(pending_edges) do
            if not edge.colored then
                local vr = edge.row % 32
                local addr = base + vr * 32 + 5  -- check column 5 (should be non-empty)
                emu:write8(0xFF4F, 1)
                local attr = emu:read8(addr)
                emu:write8(0xFF4F, 0)
                if attr ~= 0 or frame - edge.appear > 20 then
                    edge.colored = true
                    edge.delay = frame - edge.appear
                    table.insert(edge_delays, edge.delay)
                end
            end
        end
    end
    
    if frame == 1200 then
        local f = io.open("/tmp/scroll_edge_result.txt", "w")
        if #edge_delays > 0 then
            local sum = 0
            local max_d = 0
            for _, d in ipairs(edge_delays) do
                sum = sum + d
                if d > max_d then max_d = d end
            end
            f:write(string.format("Scroll edges detected: %d\n", #edge_delays))
            f:write(string.format("Avg delay: %.1f frames\n", sum / #edge_delays))
            f:write(string.format("Max delay: %d frames\n", max_d))
            f:write(string.format("Delays: "))
            for i, d in ipairs(edge_delays) do
                if i <= 20 then f:write(d .. " ") end
            end
            f:write("\n")
        else
            f:write("No scroll edges detected (game may not have scrolled)\n")
        end
        f:close()
        os.exit(0)
    end
end)
