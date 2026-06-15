-- general-bugs: reach a lava stage via LEVEL-SELECT and verify the molten field
-- tiles get pal5. TARGET via env LAVA_TARGET (4=stage5, 6=stage7).
local TARGET = tonumber(os.getenv("LAVA_TARGET") or "4")
local out = io.open("/tmp/general-bugs/lava_"..TARGET..".txt","w")
local KEY_A, KEY_START = 0x01, 0x08
local f, phase, seeded, started, conf = 0, "title", false, false, 0
local done = false

local function seedSRAM()
  emu:write8(0x0000, 0x0A)
  for _,b in ipairs({0xBF00,0xBF28,0xBF50,0xBF78,0xBFA0,0xBFC8}) do
    emu:write8(b, 0xFF); for i=1,0x1F do emu:write8(b+i,0x00) end
  end
end

local function readBG(p)
  local cols={}
  for c=0,3 do
    emu:write8(0xFF68,p*8+c*2); local lo=emu:read8(0xFF69)
    emu:write8(0xFF68,p*8+c*2+1); local hi=emu:read8(0xFF69)
    cols[#cols+1]=string.format("%02X%02X",hi,lo)
  end
  return table.concat(cols," ")
end

local function dumpScene(tag)
  local lcdc=emu:read8(0xFF40); local base=(lcdc&0x08)~=0 and 0x9C00 or 0x9800
  out:write(string.format("=== %s f=%d D880=%02X FFC1=%02X FFBA=%02X base=%04X ===\n",
    tag,f,emu:read8(0xD880),emu:read8(0xFFC1),emu:read8(0xFFBA),base))
  local tiles,attrs={},{}
  emu:write8(0xFF4F,0); for r=0,17 do for col=0,19 do tiles[r*20+col]=emu:read8(base+r*32+col) end end
  emu:write8(0xFF4F,1); for r=0,17 do for col=0,19 do attrs[r*20+col]=emu:read8(base+r*32+col)&0x07 end end
  emu:write8(0xFF4F,0)
  local idpal={}
  for i=0,17*20+19 do local t=tiles[i]; idpal[t]=idpal[t] or {}; idpal[t][attrs[i]]=(idpal[t][attrs[i]] or 0)+1 end
  out:write("  TILE-ID -> pal(s) (sorted by count):\n")
  local ids={}; for t in pairs(idpal) do ids[#ids+1]=t end; table.sort(ids)
  for _,t in ipairs(ids) do local pl={}; local tot=0; for p,c in pairs(idpal[t]) do pl[#pl+1]=string.format("p%d:%d",p,c); tot=tot+c end; table.sort(pl)
    out:write(string.format("    %02X (n=%d) -> %s\n", t, tot, table.concat(pl,","))) end
  out:write("  BG5(lava)="..readBG(5).."\n")
  out:write("\n")
end

callbacks:add("frame", function()
  f=f+1
  if done then return end
  emu:write8(0xDCFD, 0x01)
  if not seeded and f>=100 then seedSRAM(); seeded=true end
  local d880,ffc1 = emu:read8(0xD880), emu:read8(0xFFC1)
  if phase=="title" then
    if f>=300 and f<306 then emu:setKeys(KEY_START)
    elseif f>=360 and f<366 then emu:setKeys(KEY_START)
    else emu:setKeys(0) end
    if f>=330 then phase="ls" end
    return
  end
  if phase=="ls" and not started then
    emu:write8(0xFFBA, TARGET); seedSRAM()
    if f%60>=10 and f%60<16 then emu:setKeys(KEY_A) else emu:setKeys(0) end
    if ffc1==1 or d880==0x18 then started=true; conf=f; phase="play" end
    return
  end
  if phase=="play" then
    emu:write8(0xDCDD,0x17); emu:write8(0xDCDC,0xFF); emu:write8(0xDCBB,0xF0)
    emu:write8(0xFFBA, TARGET)
    emu:setKeys(0x10 + ((f%4<2) and KEY_A or 0))
    if f==conf+400 then dumpScene("LAVA1") end
    if f==conf+500 then dumpScene("LAVA2") end
    if f>conf+520 then out:write("DONE\n"); out:close(); done=true end
  end
end)
