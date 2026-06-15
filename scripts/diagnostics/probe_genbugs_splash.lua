-- general-bugs: reach the STAGE-intro splash (D880=0x18) via the teleport ROM's
-- death/splash path is hard; instead force a dungeon state then drive a boss kill?
-- Simplest: load a dungeon state, set DCBB low to trigger the death/splash cinematic
-- (D880=0x17 death, 0x18 splash). We just watch for D880=0x18 and dump it.
local out = io.open("/tmp/general-bugs/splash_dump.txt", "w")
local f, done, loaded = 0, false, false
local seen18 = false

local function readBGPal()
  local s = {}
  for p = 0, 7 do
    local cols = {}
    for c = 0, 3 do
      emu:write8(0xFF68, (p*8+c*2)); local lo=emu:read8(0xFF69)
      emu:write8(0xFF68, (p*8+c*2+1)); local hi=emu:read8(0xFF69)
      cols[#cols+1]=string.format("%02X%02X",hi,lo)
    end
    s[#s+1]=table.concat(cols," ")
  end
  return s
end

local function dumpScene(tag)
  local lcdc=emu:read8(0xFF40); local base=(lcdc&0x08)~=0 and 0x9C00 or 0x9800
  out:write(string.format("=== %s f=%d D880=%02X FFC1=%02X base=%04X WY=%02X WX=%02X ===\n",
    tag,f,emu:read8(0xD880),emu:read8(0xFFC1),base,emu:read8(0xFF4A),emu:read8(0xFF4B)))
  local tiles,attrs={},{}
  emu:write8(0xFF4F,0); for r=0,17 do for col=0,19 do tiles[r*20+col]=emu:read8(base+r*32+col) end end
  emu:write8(0xFF4F,1); for r=0,17 do for col=0,19 do attrs[r*20+col]=emu:read8(base+r*32+col)&0x07 end end
  emu:write8(0xFF4F,0)
  local idpal={}
  for i=0,17*20+19 do local t=tiles[i]; idpal[t]=idpal[t] or {}; idpal[t][attrs[i]]=(idpal[t][attrs[i]] or 0)+1 end
  out:write("  TILE-ID -> pal(s):\n")
  local ids={}; for t in pairs(idpal) do ids[#ids+1]=t end; table.sort(ids)
  for _,t in ipairs(ids) do local pl={}; for p,c in pairs(idpal[t]) do pl[#pl+1]=string.format("p%d:%d",p,c) end; table.sort(pl)
    out:write(string.format("    %02X -> %s%s\n",t,table.concat(pl,","), #pl>1 and "  <--MULTI" or "")) end
  out:write("  BG CRAM:\n"); for p,l in ipairs(readBGPal()) do out:write(string.format("    BG%d %s\n",p-1,l)) end
  out:write("  TILE-ID GRID:\n")
  for r=0,17 do local row={}; for col=0,19 do row[#row+1]=string.format("%02X",tiles[r*20+col]) end; out:write("    "..table.concat(row," ").."\n") end
  out:write("  ATTR GRID:\n")
  for r=0,17 do local row={}; for col=0,19 do row[#row+1]=tostring(attrs[r*20+col]) end; out:write("    "..table.concat(row).."\n") end
  out:write("\n")
end

callbacks:add("frame", function()
  f=f+1
  if done then return end
  if not loaded and f==5 then emu:loadStateFile("save_states_for_claude/level1_sara_d_alone.ss0"); loaded=true; return end
  if not loaded then return end
  -- after settle, force death cinematic: DCBB -> 1 then 0 triggers timeout
  if f>=120 and f<200 then emu:write8(0xDCBB, 0x01) end
  if f>=200 and f<260 then emu:write8(0xDCBB, 0x00) end
  -- press A to advance through cinematic to splash
  if f>=260 and f%30<4 then emu:setKeys(0x01) else emu:setKeys(0) end
  local d=emu:read8(0xD880)
  if d==0x18 and not seen18 then seen18=true; dumpScene("SPLASH_18") end
  if f%40==0 and f>=130 then dumpScene("WATCH_d"..string.format("%02X",d)) end
  if f>=900 then out:write("DONE\n"); out:close(); done=true end
end)
