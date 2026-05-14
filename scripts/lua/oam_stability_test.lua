-- OAM Stability Test
-- Detects sprite palette flickering by tracking per-slot changes across frames
-- Output: JSON report with flicker counts and stability scores

local TEST_FRAMES = 120
local OAM_BASE = 0xFE00
local SPRITE_COUNT = 40

-- Storage for tracking
local frame_count = 0
local prev_oam = {}  -- Previous frame's OAM data
local curr_oam = {}  -- Current frame's OAM data

-- Flicker tracking
local flicker_events = {}  -- Array of {frame, slot, old_pal, new_pal, tile_id}
local tile_oscillations = {}  -- Array of {frame, slot, old_tile, new_tile}
local slot_flicker_counts = {}  -- Per-slot flicker count
local slot_stability_scores = {}  -- Per-slot stability (frames without flicker / total visible frames)
local slot_visible_frames = {}  -- How many frames each slot was visible

-- Initialize per-slot tracking
for i = 0, SPRITE_COUNT - 1 do
    slot_flicker_counts[i] = 0
    slot_visible_frames[i] = 0
end

-- Read current OAM state
local function read_oam()
    local oam = {}
    for i = 0, SPRITE_COUNT - 1 do
        local addr = OAM_BASE + i * 4
        oam[i] = {
            y = emu:read8(addr),
            x = emu:read8(addr + 1),
            tile = emu:read8(addr + 2),
            flags = emu:read8(addr + 3),
            palette = emu:read8(addr + 3) % 8  -- bits 0-2
        }
    end
    return oam
end

-- Check if sprite is visible (on screen)
local function is_visible(sprite)
    return sprite.y > 0 and sprite.y < 160 and sprite.x > 0 and sprite.x < 168
end

-- Compare frames and detect flickering
local function check_flicker()
    for i = 0, SPRITE_COUNT - 1 do
        local prev = prev_oam[i]
        local curr = curr_oam[i]

        -- Only check if sprite is visible in both frames
        if prev and curr and is_visible(prev) and is_visible(curr) then
            slot_visible_frames[i] = slot_visible_frames[i] + 1

            -- Same tile but different palette = FLICKER
            if prev.tile == curr.tile and prev.palette ~= curr.palette then
                slot_flicker_counts[i] = slot_flicker_counts[i] + 1
                table.insert(flicker_events, {
                    frame = frame_count,
                    slot = i,
                    old_pal = prev.palette,
                    new_pal = curr.palette,
                    tile_id = curr.tile,
                    x = curr.x,
                    y = curr.y
                })
            end

            -- Tile ID changed unexpectedly (potential oscillation)
            -- Only flag if both are in Sara's range and position is same
            if prev.tile ~= curr.tile and prev.x == curr.x and prev.y == curr.y then
                -- Check if both tiles are in Sara's ranges
                local prev_is_sara = (prev.tile >= 0x20 and prev.tile <= 0x2F)
                local curr_is_sara = (curr.tile >= 0x20 and curr.tile <= 0x2F)
                if prev_is_sara and curr_is_sara then
                    table.insert(tile_oscillations, {
                        frame = frame_count,
                        slot = i,
                        old_tile = prev.tile,
                        new_tile = curr.tile,
                        x = curr.x,
                        y = curr.y
                    })
                end
            end
        end
    end
end

-- Calculate final stability scores
local function calc_stability_scores()
    for i = 0, SPRITE_COUNT - 1 do
        if slot_visible_frames[i] > 0 then
            local stable_frames = slot_visible_frames[i] - slot_flicker_counts[i]
            slot_stability_scores[i] = stable_frames / slot_visible_frames[i]
        else
            slot_stability_scores[i] = 1.0  -- Never visible = stable
        end
    end
end

-- Write JSON output
local function write_results()
    calc_stability_scores()

    local total_flickers = #flicker_events
    local total_oscillations = #tile_oscillations

    -- Find Sara-specific flickers (tiles 0x20-0x2F)
    local sara_flickers = 0
    for _, evt in ipairs(flicker_events) do
        if evt.tile_id >= 0x20 and evt.tile_id <= 0x2F then
            sara_flickers = sara_flickers + 1
        end
    end

    -- Build JSON manually (mGBA Lua doesn't have json library)
    local json = '{\n'
    json = json .. '  "test_frames": ' .. TEST_FRAMES .. ',\n'
    json = json .. '  "flicker_count": ' .. total_flickers .. ',\n'
    json = json .. '  "sara_flicker_count": ' .. sara_flickers .. ',\n'
    json = json .. '  "tile_oscillation_count": ' .. total_oscillations .. ',\n'
    json = json .. '  "passed": ' .. (total_flickers == 0 and 'true' or 'false') .. ',\n'

    -- Flicker events (first 20)
    json = json .. '  "flicker_events": [\n'
    local max_events = math.min(20, #flicker_events)
    for i, evt in ipairs(flicker_events) do
        if i > max_events then break end
        json = json .. string.format(
            '    {"frame": %d, "slot": %d, "tile": %d, "old_pal": %d, "new_pal": %d, "x": %d, "y": %d}',
            evt.frame, evt.slot, evt.tile_id, evt.old_pal, evt.new_pal, evt.x, evt.y
        )
        if i < max_events then json = json .. ',' end
        json = json .. '\n'
    end
    json = json .. '  ],\n'

    -- Tile oscillations (first 20)
    json = json .. '  "tile_oscillations": [\n'
    max_events = math.min(20, #tile_oscillations)
    for i, evt in ipairs(tile_oscillations) do
        if i > max_events then break end
        json = json .. string.format(
            '    {"frame": %d, "slot": %d, "old_tile": %d, "new_tile": %d, "x": %d, "y": %d}',
            evt.frame, evt.slot, evt.old_tile, evt.new_tile, evt.x, evt.y
        )
        if i < max_events then json = json .. ',' end
        json = json .. '\n'
    end
    json = json .. '  ],\n'

    -- Per-slot summary (only slots that were visible)
    json = json .. '  "slot_summary": {\n'
    local first = true
    for i = 0, SPRITE_COUNT - 1 do
        if slot_visible_frames[i] > 0 then
            if not first then json = json .. ',\n' end
            first = false
            json = json .. string.format(
                '    "%d": {"visible_frames": %d, "flickers": %d, "stability": %.3f}',
                i, slot_visible_frames[i], slot_flicker_counts[i], slot_stability_scores[i]
            )
        end
    end
    json = json .. '\n  }\n'
    json = json .. '}\n'

    -- Write to file
    local f = io.open('oam_stability_report.json', 'w')
    if f then
        f:write(json)
        f:close()
        console:log("OAM stability report written to oam_stability_report.json")
    else
        console:error("Failed to write report file")
    end

    -- Also log summary
    console:log(string.format("OAM Stability Test Complete: %d flickers, %d oscillations",
        total_flickers, total_oscillations))
    if total_flickers > 0 then
        console:log("FAIL: Palette flickering detected!")
    else
        console:log("PASS: No palette flickering detected")
    end
end

-- Frame callback
callbacks:add("frame", function()
    frame_count = frame_count + 1

    -- Read current OAM
    curr_oam = read_oam()

    -- Check for flicker (after first frame)
    if frame_count > 1 then
        check_flicker()
    end

    -- Store for next comparison
    prev_oam = curr_oam

    -- Done?
    if frame_count >= TEST_FRAMES then
        write_results()

        -- Write done marker
        local f = io.open('DONE', 'w')
        if f then
            f:write('OK')
            f:close()
        end
    end
end)

console:log("OAM Stability Test started - running for " .. TEST_FRAMES .. " frames")
