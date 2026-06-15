-- general-bugs: trace EXACTLY which frames a specific wall cell flips palette.
-- Load sara_d_alone, watch cell (5,1) [left wall, tile 0x17] and a few neighbors
-- every frame from 250..420. Log frame, tile, attr-pal, plus DF04 (sweep row ctr)
-- and D880/FFC1, to pin the flicker mechanism.
local out = io.open("/tmp/general-bugs/flickertrace.txt", "w")
local f = 0
local done = false
local loaded = false
local base = 0x9C00
-- cells to watch (row,col)
local cells = {{5,1},{6,1},{10,1},{0,1},{15,6}}

callbacks:add("frame", function()
  f = f + 1
  if done then return end
  if not loaded and f == 5 then emu:loadStateFile("save_states_for_claude/level1_sara_d_alone.ss0"); loaded=true; return end
  if not loaded then return end
  local lcdc = emu:read8(0xFF40)
  base = (lcdc & 0x08) ~= 0 and 0x9C00 or 0x9800
  if f >= 250 and f <= 430 then
    local parts = {}
    for _,c in ipairs(cells) do
      local r,col = c[1], c[2]
      emu:write8(0xFF4F,0); local t = emu:read8(base+r*32+col)
      emu:write8(0xFF4F,1); local a = emu:read8(base+r*32+col)&0x07
      emu:write8(0xFF4F,0)
      parts[#parts+1] = string.format("(%d,%d)t%02Xp%d", r, col, t, a)
    end
    out:write(string.format("f=%d D880=%02X FFC1=%02X DF04=%02X DF07=%02X base=%04X | %s\n",
      f, emu:read8(0xD880), emu:read8(0xFFC1), emu:read8(0xDF04), emu:read8(0xDF07),
      base, table.concat(parts," ")))
  end
  if f >= 432 then out:write("DONE\n"); out:close(); done=true end
end)
