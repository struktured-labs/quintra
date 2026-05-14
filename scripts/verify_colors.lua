-- Color Regression Test for Penta Dragon DX
-- Verifies BG tile palette attributes and OBJ palette assignments
-- Uses a sampling approach to avoid overwhelming the emulator
-- Outputs JSON report.

local OUTPUT = os.getenv("VERIFY_OUTPUT") or "verify_colors_report.json"

-- Title menu input sequence
local TITLE = {
    {180, 185, 0x80},  -- DOWN
    {193, 198, 0x01},  -- A
    {241, 246, 0x01},  -- A
    {291, 296, 0x01},  -- A
    {341, 346, 0x08},  -- START
    {391, 396, 0x01},  -- A
}

-- Expected BG tile -> palette mapping (from ROM lookup table at 0x6B00 in bank 13)
local function expected_bg_palette(tile_id)
    if tile_id <= 0x3F then return 0 end       -- Floor/edges
    if tile_id <= 0x5F then return 6 end       -- Wall fill
    if tile_id <= 0x87 then return 0 end       -- Arches/doors
    if tile_id <= 0xDF then return 1 end       -- Items
    if tile_id <= 0xFD then return 6 end       -- Decorative
    return 0                                    -- Void (0xFE-0xFF)
end

-- Expected OBJ tile -> palette mapping
local function expected_obj_palette(tile_id, boss_flag)
    if tile_id >= 0x20 and tile_id <= 0x27 then return 2 end  -- Sara W
    if tile_id >= 0x28 and tile_id <= 0x2F then return 1 end  -- Sara D
    if tile_id >= 0x30 and tile_id <= 0x3F then return 3 end  -- Crow
    if tile_id >= 0x40 and tile_id <= 0x4F then return 4 end  -- Hornets
    if tile_id >= 0x50 and tile_id <= 0x5F then return 5 end  -- Orcs
    if tile_id >= 0x60 and tile_id <= 0x6F then return 6 end  -- Humanoids
    if tile_id >= 0x70 and tile_id <= 0x7F then return 7 end  -- Special/catfish
    return 0  -- Projectiles/effects
end

local frame = 0
local gameplay_started = false
local dungeon_entered = false
local check_phase = 0  -- 0=waiting, 1=read VBK0, 2=read VBK1, 3=done
local check_start = 0

-- Spread VBK reads across multiple frames to avoid crashes
local bg_tiles = {}     -- {tile_id, map_offset} pairs from VBK=0
local bg_attrs = {}     -- {attr_val, map_offset} pairs from VBK=1
local SAMPLE_COUNT = 36 -- Sample 36 tiles (6x6 grid from visible area)

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
    emu:setKeys(keys)

    -- Track FFC1
    local ffc1 = emu:read8(0xFFC1)
    if ffc1 == 1 and not gameplay_started then
        gameplay_started = true
    end

    if not gameplay_started then return end

    -- Keep alive
    emu:write8(0xDCDD, 0x17)
    emu:write8(0xDCDC, 0xFF)
    emu:write8(0xDCBB, 0xFF)

    -- Wait for dungeon state (D880=2)
    local d880 = emu:read8(0xD880)
    if not dungeon_entered and d880 == 2 then
        dungeon_entered = true
        check_start = frame + 120  -- Wait for BG sweep
    end

    if not dungeon_entered then
        if frame > 2000 then
            local ef = io.open(OUTPUT, "w")
            if ef then
                ef:write('{"passed": false, "error": "D880 never reached dungeon state"}\n')
                ef:close()
            end
            emu:quit()
        end
        return
    end

    if frame < check_start then return end

    -- Phase 1: Read tile IDs (VBK=0) - one frame
    if check_phase == 0 then
        check_phase = 1
        local scx = emu:read8(0xFF43)
        local scy = emu:read8(0xFF42)
        local tile_x_start = math.floor(scx / 8) % 32
        local tile_y_start = math.floor(scy / 8) % 32

        -- Sample a 6x6 grid spread across the visible area
        for sy = 0, 5 do
            for sx = 0, 5 do
                local tx = sx * 3 + 1  -- Tiles 1,4,7,10,13,16
                local ty = sy * 3     -- Tiles 0,3,6,9,12,15
                local map_x = (tile_x_start + tx) % 32
                local map_y = (tile_y_start + ty) % 32
                local offset = map_y * 32 + map_x
                local tile_id = emu:read8(0x9800 + offset)
                table.insert(bg_tiles, {id = tile_id, offset = offset})
            end
        end
        return
    end

    -- Phase 2: Read attributes (VBK=1) - one frame
    if check_phase == 1 then
        check_phase = 2
        -- Switch to VBK=1 to read attributes
        emu:write8(0xFF4F, 1)
        for _, t in ipairs(bg_tiles) do
            local attr = emu:read8(0x9800 + t.offset)
            table.insert(bg_attrs, {pal = attr % 8, offset = t.offset})
        end
        -- Restore VBK=0
        emu:write8(0xFF4F, 0)
        return
    end

    -- Phase 3: Compare and report
    if check_phase == 2 then
        check_phase = 3

        local bg_total = 0
        local bg_correct = 0
        local bg_wrong = 0
        local bg_errors = {}

        for i, t in ipairs(bg_tiles) do
            local a = bg_attrs[i]
            if a then
                bg_total = bg_total + 1
                local expected_pal = expected_bg_palette(t.id)
                if a.pal == expected_pal then
                    bg_correct = bg_correct + 1
                else
                    bg_wrong = bg_wrong + 1
                    if #bg_errors < 10 then
                        table.insert(bg_errors, string.format(
                            '{"tile":"0x%02X","expected":%d,"actual":%d}',
                            t.id, expected_pal, a.pal
                        ))
                    end
                end
            end
        end

        -- OBJ check: read shadow OAM from C000/C100
        local obj_total = 0
        local obj_correct = 0
        local obj_wrong = 0
        local obj_errors = {}
        local boss_flag = emu:read8(0xFFBF)

        -- Check both shadow buffers for any populated sprites
        local ffcb = emu:read8(0xFFCB)
        local oam_base = (ffcb == 0) and 0xC100 or 0xC000  -- Opposite of current DMA buffer

        for i = 0, 39 do
            local base = oam_base + i * 4
            local y = emu:read8(base)
            local x = emu:read8(base + 1)
            local tile = emu:read8(base + 2)
            local flags = emu:read8(base + 3)
            local actual_pal = flags % 8

            if y > 0 and y < 160 and x > 0 and x < 168 and tile >= 0x20 then
                obj_total = obj_total + 1
                local expected_pal = expected_obj_palette(tile, boss_flag)
                if actual_pal == expected_pal then
                    obj_correct = obj_correct + 1
                else
                    obj_wrong = obj_wrong + 1
                    if #obj_errors < 10 then
                        table.insert(obj_errors, string.format(
                            '{"slot":%d,"tile":"0x%02X","expected":%d,"actual":%d}',
                            i, tile, expected_pal, actual_pal
                        ))
                    end
                end
            end
        end

        -- Calculate accuracy
        local bg_accuracy = 0
        if bg_total > 0 then bg_accuracy = bg_correct / bg_total * 100 end
        local obj_accuracy = 0
        if obj_total > 0 then obj_accuracy = obj_correct / obj_total * 100 end

        -- Pass criteria: >90% BG correct, OBJ either none visible or >90%
        local bg_pass = bg_accuracy >= 90.0
        local obj_pass = obj_total == 0 or obj_accuracy >= 90.0
        local passed = bg_pass and obj_pass

        -- Write report
        local rf = io.open(OUTPUT, "w")
        if rf then
            rf:write('{\n')
            rf:write(string.format('  "check_frame": %d,\n', frame))
            rf:write(string.format('  "boss_flag": %d,\n', boss_flag))
            rf:write(string.format('  "bg_total": %d,\n', bg_total))
            rf:write(string.format('  "bg_correct": %d,\n', bg_correct))
            rf:write(string.format('  "bg_wrong": %d,\n', bg_wrong))
            rf:write(string.format('  "bg_accuracy": %.1f,\n', bg_accuracy))
            rf:write(string.format('  "bg_errors": [%s],\n', table.concat(bg_errors, ",")))
            rf:write(string.format('  "obj_total": %d,\n', obj_total))
            rf:write(string.format('  "obj_correct": %d,\n', obj_correct))
            rf:write(string.format('  "obj_wrong": %d,\n', obj_wrong))
            rf:write(string.format('  "obj_accuracy": %.1f,\n', obj_accuracy))
            rf:write(string.format('  "obj_errors": [%s],\n', table.concat(obj_errors, ",")))
            rf:write(string.format('  "bg_pass": %s,\n', bg_pass and "true" or "false"))
            rf:write(string.format('  "obj_pass": %s,\n', obj_pass and "true" or "false"))
            rf:write(string.format('  "passed": %s\n', passed and "true" or "false"))
            rf:write('}\n')
            rf:close()
        end

        console:log(string.format("[VERIFY_COLORS] BG: %d/%d (%.1f%%) OBJ: %d/%d (%.1f%%) %s",
            bg_correct, bg_total, bg_accuracy,
            obj_correct, obj_total, obj_accuracy,
            passed and "PASS" or "FAIL"))

        local df = io.open("DONE_VERIFY_COLORS", "w")
        if df then df:write("OK"); df:close() end

        emu:quit()
    end
end)
