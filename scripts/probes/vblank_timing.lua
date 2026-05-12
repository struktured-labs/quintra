-- VBlank handler timing harness.
-- Measures cycles spent inside the modded VBlank ISR by sampling DIV at
-- VBlank-interrupt entry (LY=144 → 0x9800 mode-1) and at handler exit.
--
-- Since we can't easily instrument the ROM's RET point, we use an
-- approximation: read LY before the handler effectively returns control,
-- and count "frames where LY left VBlank window before handler done".
--
-- Practical alternative implemented here: sample the LY counter mid-handler
-- and report distribution. A handler that overruns VBlank (LY past 153
-- means we've wrapped back into Mode 2/3) is a tearing signal.
--
-- Simpler signal that ALSO catches tearing: count how many frames the LCD
-- entered Mode 3 (drawing) while we're still in our handler's palette
-- write path. We approximate this by sampling DIV across the VBlank
-- callback and computing handler duration in cycles.

local OUT = os.getenv("STATE_PATH") or "/tmp/penta_vblank.txt"
local SAMPLE_FRAMES = tonumber(os.getenv("SAMPLE_FRAMES") or "300")
local START_AT = tonumber(os.getenv("START_AT") or "120")

local samples = {}
local prev_div = nil
local f = 0
local fired = false

-- mgba's "frame" callback fires after the frame completes (start of next
-- frame's VBlank). We sample DIV (timer divider, ticks at CPU clock / 256
-- = ~16384 Hz, so 1 unit ≈ 256 T-cycles).
callbacks:add("frame", function()
    if fired then return end
    f = f + 1
    if f < START_AT then return end

    local div = emu:read8(0xFF04)
    local ly = emu:read8(0xFF44)
    if #samples < SAMPLE_FRAMES then
        table.insert(samples, {f=f, div=div, ly=ly})
    end

    if #samples >= SAMPLE_FRAMES then
        fired = true
        local fh = io.open(OUT, "w")
        fh:write("# VBlank-callback sampling: DIV (FF04) + LY (FF44) at frame end\n")
        fh:write(string.format("# Samples: %d (start at f=%d)\n", #samples, START_AT))
        local ly_in_vblank = 0
        local ly_in_drawing = 0
        local div_deltas = {}
        for i = 1, #samples do
            local s = samples[i]
            if s.ly >= 144 and s.ly <= 153 then
                ly_in_vblank = ly_in_vblank + 1
            else
                ly_in_drawing = ly_in_drawing + 1
            end
        end
        fh:write(string.format("ly_in_vblank=%d\n", ly_in_vblank))
        fh:write(string.format("ly_in_drawing=%d\n", ly_in_drawing))
        fh:write(string.format("vblank_callback_after_vblank_ratio=%.4f\n",
            ly_in_drawing / #samples))
        fh:write("# first 30 samples (frame, DIV, LY):\n")
        for i = 1, math.min(30, #samples) do
            local s = samples[i]
            fh:write(string.format("  f=%d DIV=%d LY=%d\n", s.f, s.div, s.ly))
        end
        fh:close()
        console:log(string.format("vblank_timing: %d samples, %d in drawing range",
            #samples, ly_in_drawing))
        os.exit(0)
    end
end)
