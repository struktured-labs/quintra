-- Probe: At several frames in orc state, dump SHADOW OAM vs HW OAM
-- at slots 14-15 (orc body tile 0x52/0x53) to determine where pal 4 comes from.
-- shadow OAM location is typically WRAM at 0xC000 or 0xC100 in DX builds.
-- We try a few candidates: 0xC000, 0xC100, 0xC200, 0xCA00, 0xCD00.
local frame_count = 0
local CANDIDATES = {0xC000, 0xC100, 0xC200, 0xCA00, 0xCD00}
local out_path = "/tmp/orc_shadow_probe.txt"
local fh = io.open(out_path, "w")

local function dump_oam_slice(label, base)
    -- For each candidate buffer, dump 4 bytes at offset 14*4 = 56 (slot 14)
    fh:write(string.format("[%s] base=0x%04X  slot14: ", label, base))
    for i = 0, 3 do
        fh:write(string.format("%02X ", emu:read8(base + 14*4 + i)))
    end
    fh:write(string.format("  slot15: "))
    for i = 0, 3 do
        fh:write(string.format("%02X ", emu:read8(base + 15*4 + i)))
    end
    fh:write("\n")
end

local function hw_oam_slot(label, slot)
    local raw = emu.memory.oam:readRange(slot * 4, 4)
    fh:write(string.format("[%s] HW slot%d: ", label, slot))
    for i = 1, 4 do
        fh:write(string.format("%02X ", raw:byte(i)))
    end
    fh:write("\n")
end

callbacks:add("frame", function()
    frame_count = frame_count + 1
    if frame_count == 60 or frame_count == 65 or frame_count == 68 or
       frame_count == 70 or frame_count == 75 then
        fh:write(string.format("=== frame %d ===\n", frame_count))
        for _, base in ipairs(CANDIDATES) do
            dump_oam_slice(string.format("f%d", frame_count), base)
        end
        hw_oam_slot(string.format("f%d", frame_count), 14)
        hw_oam_slot(string.format("f%d", frame_count), 15)
        fh:flush()
    end
    if frame_count == 80 then
        fh:close()
        emu:stop()
    end
end)
