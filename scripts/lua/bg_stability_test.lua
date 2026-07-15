-- BG Attribute Stability Test
-- Detects background palette flickering by tracking VRAM bank 1 attribute changes
-- Output: JSON report with stability metrics

local TEST_FRAMES = 60
local BG_MAP_BASE = 0x9800  -- Background tile map
local BG_MAP_SIZE = 32 * 32  -- 32x32 tiles (1024 bytes)
local VBK_REGISTER = 0xFF4F  -- VRAM bank select

-- Visible area is 20x18 tiles, but we track full map
local VISIBLE_WIDTH = 20
local VISIBLE_HEIGHT = 18

-- Storage
local frame_count = 0
local prev_attrs = nil  -- Previous frame's attribute data
local initial_attrs = nil  -- First frame's attributes (baseline)

-- Change tracking
local change_events = {}  -- Array of {frame, changes: [{x, y, old, new}]}
local total_changes = 0
local frames_with_changes = 0
local stabilization_frame = nil  -- Frame when attributes stopped changing

-- Simple hash for quick comparison
local function hash_attrs(attrs)
    local sum = 0
    for i = 1, #attrs do
        sum = (sum * 31 + attrs[i]) % 0xFFFFFFFF
    end
    return sum
end

-- Read BG attributes from VRAM bank 1
local function read_bg_attrs()
    -- Note: mGBA's emu:read8 reads the currently selected bank
    -- We need to temporarily switch to bank 1
    local old_vbk = emu:read8(VBK_REGISTER)

    -- Select VRAM bank 1
    emu:write8(VBK_REGISTER, 1)

    local attrs = {}
    for i = 0, BG_MAP_SIZE - 1 do
        attrs[i + 1] = emu:read8(BG_MAP_BASE + i)
    end

    -- Restore original bank
    emu:write8(VBK_REGISTER, old_vbk)

    return attrs
end

-- Compare attributes and find differences
local function compare_attrs(old, new)
    local changes = {}
    for i = 1, BG_MAP_SIZE do
        if old[i] ~= new[i] then
            local idx = i - 1
            local x = idx % 32
            local y = math.floor(idx / 32)
            -- Only track visible area changes
            if x < VISIBLE_WIDTH and y < VISIBLE_HEIGHT then
                table.insert(changes, {
                    x = x,
                    y = y,
                    old_attr = old[i],
                    new_attr = new[i],
                    old_pal = old[i] % 8,
                    new_pal = new[i] % 8
                })
            end
        end
    end
    return changes
end

-- Write JSON output
local function write_results()
    -- Determine if test passed
    -- Allow up to 6 frames of initial changes (for colorization to settle)
    local unexpected_changes = 0
    for _, evt in ipairs(change_events) do
        if evt.frame > 6 then
            unexpected_changes = unexpected_changes + #evt.changes
        end
    end

    local passed = (unexpected_changes == 0)

    -- Build JSON
    local json = '{\n'
    json = json .. '  "test_frames": ' .. TEST_FRAMES .. ',\n'
    json = json .. '  "total_changes": ' .. total_changes .. ',\n'
    json = json .. '  "frames_with_changes": ' .. frames_with_changes .. ',\n'
    json = json .. '  "unexpected_changes": ' .. unexpected_changes .. ',\n'
    json = json .. '  "stabilization_frame": ' .. (stabilization_frame or TEST_FRAMES) .. ',\n'
    json = json .. '  "passed": ' .. (passed and 'true' or 'false') .. ',\n'

    -- Change events (first 10 frames with changes)
    json = json .. '  "change_events": [\n'
    local max_events = math.min(10, #change_events)
    for i, evt in ipairs(change_events) do
        if i > max_events then break end
        json = json .. '    {\n'
        json = json .. '      "frame": ' .. evt.frame .. ',\n'
        json = json .. '      "change_count": ' .. #evt.changes .. ',\n'
        json = json .. '      "changes": [\n'
        local max_changes = math.min(5, #evt.changes)
        for j, chg in ipairs(evt.changes) do
            if j > max_changes then break end
            json = json .. string.format(
                '        {"x": %d, "y": %d, "old_pal": %d, "new_pal": %d}',
                chg.x, chg.y, chg.old_pal, chg.new_pal
            )
            if j < max_changes then json = json .. ',' end
            json = json .. '\n'
        end
        if #evt.changes > max_changes then
            json = json .. '        ' -- indent for "... and N more"
        end
        json = json .. '      ]\n'
        json = json .. '    }'
        if i < max_events then json = json .. ',' end
        json = json .. '\n'
    end
    json = json .. '  ]\n'
    json = json .. '}\n'

    -- Write to file
    local f = io.open('bg_stability_report.json', 'w')
    if f then
        f:write(json)
        f:close()
        console:log("BG stability report written to bg_stability_report.json")
    else
        console:error("Failed to write report file")
    end

    -- Log summary
    console:log(string.format("BG Stability Test Complete: %d total changes, %d unexpected",
        total_changes, unexpected_changes))
    if passed then
        console:log("PASS: BG attributes stable after initial colorization")
    else
        console:log("FAIL: BG attributes flickering detected!")
    end
end

-- Frame callback
callbacks:add("frame", function()
    frame_count = frame_count + 1

    -- Read current BG attributes
    local curr_attrs = read_bg_attrs()

    if frame_count == 1 then
        initial_attrs = curr_attrs
    end

    -- Compare with previous frame
    if prev_attrs then
        local changes = compare_attrs(prev_attrs, curr_attrs)

        if #changes > 0 then
            frames_with_changes = frames_with_changes + 1
            total_changes = total_changes + #changes

            table.insert(change_events, {
                frame = frame_count,
                changes = changes
            })

            -- Reset stabilization tracking
            stabilization_frame = nil
        else
            -- No changes - mark stabilization if not already set
            if not stabilization_frame then
                stabilization_frame = frame_count
            end
        end
    end

    prev_attrs = curr_attrs

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

console:log("BG Stability Test started - running for " .. TEST_FRAMES .. " frames")
