-- general-bugs: on the title menu (D880=0x1C), decode the actual pixel color
-- indices used by the font glyph tiles (e.g. 'P'=0x8F, 'A'=0x80) AND read BG1 CRAM,
-- to determine whether the red text is visible. Also screenshot.
local out = io.open("/tmp/general-bugs/fontpix.txt", "w")
local f, done = 0, false
local dumped = false

local function tilePixels(tileid)
  -- title uses LCDC bit4 for tile data base. Determine base.
  local lcdc = emu:read8(0xFF40)
  local base
  if (lcdc & 0x10) ~= 0 then base = 0x8000 + tileid*16
  else base = (tileid < 128) and (0x9000 + tileid*16) or (0x8800 + (tileid-128)*16) end
  emu:write8(0xFF4F, 0)
  local rows = {}
  local idxcount = {0,0,0,0}
  for r = 0, 7 do
    local lo = emu:read8(base + r*2)
    local hi = emu:read8(base + r*2 + 1)
    local rowstr = {}
    for b = 7, 0, -1 do
      local px = (((hi>>b)&1)<<1) | ((lo>>b)&1)
      idxcount[px+1] = idxcount[px+1] + 1
      rowstr[#rowstr+1] = (".:+#"):sub(px+1,px+1)
    end
    rows[#rows+1] = table.concat(rowstr)
  end
  return rows, idxcount
end

local function readBG(p)
  local cols={}
  for c=0,3 do
    emu:write8(0xFF68, p*8+c*2); local lo=emu:read8(0xFF69)
    emu:write8(0xFF68, p*8+c*2+1); local hi=emu:read8(0xFF69)
    cols[#cols+1]=string.format("%02X%02X",hi,lo)
  end
  return table.concat(cols," ")
end

callbacks:add("frame", function()
  f=f+1
  if done then return end
  local d = emu:read8(0xD880)
  if d==0x1C and not dumped and f>30 then
    dumped=true
    out:write(string.format("=== MENU f=%d D880=1C LCDC=%02X(bit4=%d) ===\n", f, emu:read8(0xFF40), (emu:read8(0xFF40)&0x10)~=0 and 1 or 0))
    out:write("BG0="..readBG(0).."  BG1="..readBG(1).."\n\n")
    for _,g in ipairs({{0x8F,"P"},{0x80,"A"},{0x84,"E"},{0x93,"T"},{0x83,"D"},{0x97,"X"}}) do
      local rows, ic = tilePixels(g[1])
      out:write(string.format("glyph '%s' tile %02X  idxcount[0..3]=%d,%d,%d,%d\n", g[2], g[1], ic[1],ic[2],ic[3],ic[4]))
      for _,rw in ipairs(rows) do out:write("  "..rw.."\n") end
      out:write("\n")
    end
    emu:screenshot("/tmp/general-bugs/menu_1C.png")
    out:write("screenshot -> /tmp/general-bugs/menu_1C.png\n")
    out:write("DONE\n"); out:close(); done=true
  end
  if f>=2400 then if not done then out:write("never reached 0x1C\n"); out:close() end; done=true end
end)
