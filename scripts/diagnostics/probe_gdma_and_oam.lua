-- Probe: GDMA and direct HW OAM writes near slot 14 (0xFE38-0xFE3B).
local frame_count = 0
local fh = io.open("/tmp/gdma_oam_probe.txt", "w")
local writes_to_oam = {}
local writes_to_gdma = {}
local writes_to_dma = {}

callbacks:add("write", function(addr, val)
    -- Track GDMA HDMA1-5
    if addr >= 0xFF51 and addr <= 0xFF55 then
        table.insert(writes_to_gdma, string.format("f%d FF%02X=0x%02X", frame_count, addr & 0xFF, val))
        if #writes_to_gdma > 60 then table.remove(writes_to_gdma, 1) end
    end
    -- Track HW OAM slot 14 writes (0xFE38-0xFE3B)
    if addr >= 0xFE38 and addr <= 0xFE3B then
        table.insert(writes_to_oam, string.format("f%d 0x%04X=0x%02X", frame_count, addr, val))
        if #writes_to_oam > 200 then table.remove(writes_to_oam, 1) end
    end
    -- Track DMA (FF46)
    if addr == 0xFF46 then
        table.insert(writes_to_dma, string.format("f%d FF46=0x%02X", frame_count, val))
    end
end)

callbacks:add("frame", function()
    frame_count = frame_count + 1
    if frame_count == 70 then
        fh:write("=== HDMA writes (FF51-FF55) — recent ===\n")
        for _, line in ipairs(writes_to_gdma) do
            fh:write(line .. "\n")
        end
        fh:write("\n=== HW OAM slot 14 (0xFE38-0xFE3B) writes — recent ===\n")
        for _, line in ipairs(writes_to_oam) do
            fh:write(line .. "\n")
        end
        fh:write("\n=== DMA (FF46) writes ===\n")
        for _, line in ipairs(writes_to_dma) do
            fh:write(line .. "\n")
        end
        if #writes_to_dma == 0 then
            fh:write("  (none — no OAM DMA used)\n")
        end
        fh:close()
        emu:stop()
    end
end)
