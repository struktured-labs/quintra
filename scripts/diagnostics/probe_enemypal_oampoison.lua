-- probe_enemypal_oampoison.lua
-- Does the OBJ colorizer (shadow_main/tile_based_colorizer) rewrite OAM attr
-- palette bits? Poison OAM attr low-3 bits of visible enemy sprites, run
-- frames, re-read. If colorizer runs, palette bits change per tile range.
-- Also the game keeps a SHADOW OAM at 0xC000/0xC100 that the colorizer
-- targets (per doc: 0xC003, 0xC103). Hardware OAM 0xFE00 is DMA'd from there.
-- So we poison the SHADOW OAM and check if the colorizer rewrites it.
local STATE=os.getenv("PROBE_STATE"); local LABEL=os.getenv("PROBE_LABEL")
local OUT=os.getenv("PROBE_OUT"); local fh=io.open(OUT,"a")
local frame=0; local loaded=false; local done=false
local function w(s) fh:write(s.."\n"); fh:flush() end

callbacks:add("frame",function()
  if done then return end
  frame=frame+1
  if not loaded and frame==2 then emu:loadStateFile(STATE); loaded=true; return end
  if loaded then
    if frame==30 then
      w("==== "..LABEL.." ====")
      -- dump shadow OAM block1 (0xC000) entries 1..8 tile+attr, and hardware OAM
      w("Shadow OAM @C000 (tile@+2, attr@+3) entries 0..9:")
      for e=0,9 do
        local base=0xC000+e*4
        w(string.format("  C%03X: y=%02X x=%02X tile=%02X attr=%02X (pal=%d)",
          base&0xFFF, emu:read8(base),emu:read8(base+1),emu:read8(base+2),emu:read8(base+3),
          emu:read8(base+3)&0x07))
      end
      -- poison the attr palette bits of shadow OAM entries to 7
      for e=0,39 do
        local base=0xC000+e*4
        local a=emu:read8(base+3)
        emu:write8(base+3, (a & 0xF8) | 0x07)
      end
      -- also poison hardware OAM
      for e=0,39 do
        local base=0xFE00+e*4
        local a=emu:read8(base+3)
        emu:write8(base+3, (a & 0xF8) | 0x07)
      end
      w("(poisoned shadow+hw OAM attr pal bits to 7)")
    end
    if frame==40 then
      w("Post-frames shadow OAM @C000 entries 0..9 (colorizer rewrite?):")
      for e=0,9 do
        local base=0xC000+e*4
        w(string.format("  C%03X: tile=%02X attr=%02X (pal=%d)",
          base&0xFFF, emu:read8(base+2),emu:read8(base+3), emu:read8(base+3)&0x07))
      end
      w("Post-frames hardware OAM @FE00 entries 0..9:")
      for e=0,9 do
        local base=0xFE00+e*4
        w(string.format("  FE%02X: tile=%02X attr=%02X (pal=%d)",
          (base&0xFF), emu:read8(base+2),emu:read8(base+3), emu:read8(base+3)&0x07))
      end
      w("")
      done=true
    end
  end
end)
