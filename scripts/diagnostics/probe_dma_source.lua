-- Probe: which addr does the game DMA from? Track FF46 writes (DMA trigger).
-- Also: dump candidate WRAM ranges for any buffer matching HW OAM slot 14 (tile 0x52).
local frame_count = 0
local fh = io.open("/tmp/dma_source_probe.txt", "w")
local seen_ff46 = {}

callbacks:add("write", function(addr, val)
    if addr == 0xFF46 then
        if not seen_ff46[val] then
            seen_ff46[val] = 1
            fh:write(string.format("frame %d: DMA src=0x%02X00 (PC=?)\n", frame_count, val))
            fh:flush()
        end
    end
end)

callbacks:add("frame", function()
    frame_count = frame_count + 1
    if frame_count == 68 then
        -- For each candidate base, dump slot 14 raw bytes
        local CANDS = {0xC000, 0xC100, 0xC200, 0xC300, 0xC400, 0xC500, 0xC600,
                       0xC700, 0xC800, 0xC900, 0xCA00, 0xCB00, 0xCC00, 0xCD00,
                       0xCE00, 0xCF00, 0xD000, 0xD100, 0xD200, 0xD300, 0xD400,
                       0xD500, 0xD600, 0xD700, 0xD800, 0xD900}
        fh:write("=== frame 68 candidates with tile=0x52 at slot 14 (offset 58 = 14*4+2) ===\n")
        for _, base in ipairs(CANDS) do
            local tile = emu:read8(base + 14*4 + 2)
            local attr = emu:read8(base + 14*4 + 3)
            if tile == 0x52 then
                fh:write(string.format("  0x%04X: slot14 tile=0x%02X attr=0x%02X\n", base, tile, attr))
            end
        end
        -- Also list all DMA sources seen
        fh:write("\nUnique DMA sources observed:\n")
        for v, _ in pairs(seen_ff46) do
            fh:write(string.format("  0x%02X (page 0x%02X00)\n", v, v))
        end
        fh:close()
        emu:stop()
    end
end)
