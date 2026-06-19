-- Probe: in spider_w savestate, does HW OAM accept writes? Iter 26 classified
-- DF1F=0xFF as FROZEN — but maybe iter 31's hwoam_recolor B=40 brought it back.
local frame_count = 0
local fh = io.open("/tmp/spider_w_liveness.txt", "w")

callbacks:add("frame", function()
    frame_count = frame_count + 1
    if frame_count == 50 then
        -- Sample HW OAM[0] tile + attr at f=50
        local raw1 = emu.memory.oam:readRange(0, 4)
        fh:write(string.format("f50 (pre-poison): y=0x%02X x=0x%02X tile=0x%02X attr=0x%02X\n",
            raw1:byte(1), raw1:byte(2), raw1:byte(3), raw1:byte(4)))
    end
    if frame_count == 55 then
        -- Poison: write 0xAB to HW OAM[0].attr (offset 3)
        emu:write8(0xFE03, 0xAB)
        local raw_after = emu.memory.oam:readRange(0, 4)
        fh:write(string.format("f55 (post-poison): attr=0x%02X (expected 0xAB if accepted)\n",
            raw_after:byte(4)))
    end
    if frame_count == 60 then
        local raw1 = emu.memory.oam:readRange(0, 4)
        fh:write(string.format("f60 (5 frames later): tile=0x%02X attr=0x%02X\n",
            raw1:byte(3), raw1:byte(4)))
    end
    if frame_count == 70 then
        local raw1 = emu.memory.oam:readRange(0, 4)
        fh:write(string.format("f70: tile=0x%02X attr=0x%02X\n",
            raw1:byte(3), raw1:byte(4)))
        -- Verdict: if attr drifts from 0xAB → other value → LIVE (colorizer overrode)
        --          if attr stays 0xAB → POISON_PERSISTS (frozen)
        --          if attr matches savestate's pal=1 → game-OWNED writes
        fh:close()
        emu:stop()
    end
end)
