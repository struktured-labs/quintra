-- cameo_forcescene.lua: bypass the (PyBoy-tuned) teleport stack-redirect.
-- Several strategies to actually enter Cameo arena under mgba:
--   A) write D880=0x0F + FFBA=3 directly and hold; let the D880-dispatch build arena.
--   B) if A doesn't render arena tiles, also pin DCB8/HP and watch what D880 settles to.
-- We sample the tilemap once we observe arena-family tiles + a stable D880.
local OUT="/tmp/cameo/forcescene.log"
local STATE="save_states_for_claude/level1_sara_d_alone.ss0"
local MODE=tonumber(os.getenv("MODE") or "1")
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("forcescene MODE="..MODE.."\n");h:close() end end
local f=0; local phase="load"; local pf=0; local done=false
local function dumprow()
  local base=((emu:read8(0xFF40)&0x08)~=0) and 0x9C00 or 0x9800
  emu:write8(0xFF4F,0)
  for r=0,17 do local s=""; for c=0,19 do local t=emu:read8(base+r*32+c); if t~=0 then s=s..string.format("%02X ",t) end end
    if s~="" then log(string.format("  r%02d %s",r,s)) end end
end
callbacks:add("frame",function()
  f=f+1
  if done then return end
  if phase=="load" then emu:loadStateFile(STATE); phase="settle"; pf=0; return end
  if phase=="settle" then emu:setKeys(0); pf=pf+1
    if pf>=20 then phase="force"; pf=0
      log(string.format("pre-force D880=%02X FFBA=%02X FFC1=%02X",emu:read8(0xD880),emu:read8(0xFFBA),emu:read8(0xFFC1))) end
    return end
  if phase=="force" then
    emu:setKeys(0); pf=pf+1
    -- MODE 1: write D880 + FFBA directly each frame
    emu:write8(0xFFBA,0x03)
    emu:write8(0xD880,0x0F)
    emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF); emu:write8(0xDCBB,0x80)
    if pf%30==0 then
      log(string.format("force f%d D880=%02X FFBA=%02X FFC1=%02X FFBD=%02X",
        f,emu:read8(0xD880),emu:read8(0xFFBA),emu:read8(0xFFC1),emu:read8(0xFFBD)))
    end
    if pf==150 or pf==300 then
      log("=== TILEMAP @pf"..pf.." D880="..string.format("%02X",emu:read8(0xD880)).." ===")
      dumprow()
      emu:screenshot(string.format("%s_pf%d.png","/tmp/cameo/forcescene",pf))
    end
    if pf>=320 then log("DONE"); done=true end
    return end
end)
