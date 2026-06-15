-- general-bugs: compare attrs of BOTH tilemap pages (0x9800 and 0x9C00) for the
-- left wall column, after the scene has fully settled. If a wall tile (e.g. 0x17)
-- is p6 on one page but p0 on the other, the display flicker is caused by the
-- inline hook / bg_sweep only maintaining ONE page while the game ping-pongs them.
local out = io.open("/tmp/general-bugs/bothpages.txt", "w")
local f = 0
local done = false
local loaded = false

local function dumpPages(tag)
  out:write(string.format("=== %s f=%d D880=%02X FFC1=%02X LCDC=%02X(bit3=%d) ===\n",
    tag, f, emu:read8(0xD880), emu:read8(0xFFC1), emu:read8(0xFF40), (emu:read8(0xFF40)&0x08)~=0 and 1 or 0))
  for _,pg in ipairs({0x9800, 0x9C00}) do
    out:write(string.format("  PAGE %04X col0..3 of rows0..17 (tile/pal):\n", pg))
    for r=0,17 do
      local cells = {}
      for col=0,3 do
        emu:write8(0xFF4F,0); local t=emu:read8(pg+r*32+col)
        emu:write8(0xFF4F,1); local a=emu:read8(pg+r*32+col)&0x07
        cells[#cells+1]=string.format("%02X/%d", t, a)
      end
      emu:write8(0xFF4F,0)
      out:write("    r"..string.format("%02d",r).." "..table.concat(cells," ").."\n")
    end
  end
  out:write("\n")
end

callbacks:add("frame", function()
  f = f + 1
  if done then return end
  if not loaded and f==5 then emu:loadStateFile("save_states_for_claude/level1_sara_d_alone.ss0"); loaded=true; return end
  if not loaded then return end
  if f==350 then dumpPages("SETTLED1") end
  if f==360 then dumpPages("SETTLED2") end
  if f==400 then dumpPages("SETTLED3") end
  if f>=410 then out:write("DONE\n"); out:close(); done=true end
end)
