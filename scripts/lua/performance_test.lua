-- Performance Test
-- Measures game speed and detects slowdown caused by VBlank overhead
-- Output: JSON report with timing metrics

local TEST_FRAMES = 600  -- 10 seconds at 60fps
local EXPECTED_FPS = 59.7275  -- Game Boy's actual frame rate
local EXPECTED_TIME = TEST_FRAMES / EXPECTED_FPS  -- ~10.05 seconds
local TOLERANCE = 1.15  -- Allow 15% slower than expected

local OAM_BASE = 0xFE00
local SPRITE_COUNT = 40

-- Storage
local frame_count = 0
local start_time = nil

-- Stutter detection (frames where OAM didn't change)
local prev_oam_hash = nil
local stutter_frames = 0
local consecutive_stutter = 0
local max_consecutive_stutter = 0

-- Simple OAM hash
local function hash_oam()
    local sum = 0
    for i = 0, SPRITE_COUNT * 4 - 1 do
        sum = (sum * 31 + emu:read8(OAM_BASE + i)) % 0xFFFFFFFF
    end
    return sum
end

-- Write JSON output
local function write_results()
    local end_time = os.clock()
    local actual_time = end_time - start_time
    local time_ratio = actual_time / EXPECTED_TIME
    local actual_fps = TEST_FRAMES / actual_time

    local passed = (time_ratio <= TOLERANCE)

    -- Build JSON
    local json = '{\n'
    json = json .. '  "test_frames": ' .. TEST_FRAMES .. ',\n'
    json = json .. string.format('  "expected_time_seconds": %.3f,\n', EXPECTED_TIME)
    json = json .. string.format('  "actual_time_seconds": %.3f,\n', actual_time)
    json = json .. string.format('  "time_ratio": %.3f,\n', time_ratio)
    json = json .. string.format('  "expected_fps": %.2f,\n', EXPECTED_FPS)
    json = json .. string.format('  "actual_fps": %.2f,\n', actual_fps)
    json = json .. '  "stutter_frames": ' .. stutter_frames .. ',\n'
    json = json .. '  "max_consecutive_stutter": ' .. max_consecutive_stutter .. ',\n'
    json = json .. string.format('  "tolerance": %.2f,\n', TOLERANCE)
    json = json .. '  "passed": ' .. (passed and 'true' or 'false') .. '\n'
    json = json .. '}\n'

    -- Write to file
    local f = io.open('performance_report.json', 'w')
    if f then
        f:write(json)
        f:close()
        console:log("Performance report written to performance_report.json")
    else
        console:error("Failed to write report file")
    end

    -- Log summary
    console:log(string.format("Performance Test Complete: %.2f FPS (%.1f%% of expected)",
        actual_fps, (actual_fps / EXPECTED_FPS) * 100))
    console:log(string.format("Time ratio: %.3f (threshold: %.2f)", time_ratio, TOLERANCE))

    if passed then
        console:log("PASS: Performance within acceptable limits")
    else
        console:log("FAIL: Game running too slow!")
    end

    if stutter_frames > 0 then
        console:log(string.format("Warning: %d stutter frames detected (max %d consecutive)",
            stutter_frames, max_consecutive_stutter))
    end
end

-- Frame callback
callbacks:add("frame", function()
    frame_count = frame_count + 1

    -- Start timing on first frame
    if frame_count == 1 then
        start_time = os.clock()
    end

    -- Stutter detection
    local curr_hash = hash_oam()
    if prev_oam_hash and curr_hash == prev_oam_hash then
        stutter_frames = stutter_frames + 1
        consecutive_stutter = consecutive_stutter + 1
        if consecutive_stutter > max_consecutive_stutter then
            max_consecutive_stutter = consecutive_stutter
        end
    else
        consecutive_stutter = 0
    end
    prev_oam_hash = curr_hash

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

console:log("Performance Test started - running for " .. TEST_FRAMES .. " frames")
console:log("Expected time: " .. string.format("%.2f", EXPECTED_TIME) .. " seconds")
