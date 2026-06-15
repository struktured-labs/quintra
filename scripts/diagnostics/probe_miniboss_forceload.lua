-- miniboss cluster: force palette loader to run every frame (NOP the cond_pal RET Z
-- at fileoff 0x36CBB) AND patch spider boss palette (0x6888) + OBP7 static (0x6878)
-- to sentinel. If live OBP7 becomes sentinel -> loader controls OBP7; the orange/
-- purple is a STALE CACHED value (root cause = cache skip). Fix = palette tables.
local STATE = "save_states_for_claude/level1_sara_d_spider_miniboss.ss0"
local OUT   = "/tmp/miniboss/spider_forceload.log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("force-load test\n");h:close() end end
local f=0; local loaded=false; local patched=false
local function rd(a) return emu:read8(a) end
local function fo(addr) return 0x34000 + (addr - 0x4000) end
local function dec(lo,hi) local v=lo|(hi<<8); return string.format("%04X(R%02dG%02dB%02d)", v, v&0x1F,(v>>5)&0x1F,(v>>10)&0x1F) end
callbacks:add("frame", function()
  f=f+1
  if not patched then
    pcall(function() emu.memory.cart0:write8(fo(0x6CBB), 0x00) end)  -- RET Z -> NOP
    local sent={0x00,0x00, 0xE0,0x03, 0x00,0x7C, 0x1F,0x00}  -- green/blue/red sentinel
    pcall(function() for i=0,7 do emu.memory.cart0:write8(fo(0x6878)+i, sent[i+1]) end end)  -- OBP7 static
    pcall(function() for i=0,7 do emu.memory.cart0:write8(fo(0x6888)+i, sent[i+1]) end end)  -- spider boss pal
    log("NOPed RET Z, patched OBP7 static + spider boss to sentinel")
    patched=true; return
  end
  if not loaded then emu:loadStateFile(STATE); loaded=true; return end
  if f < 140 or f > 143 then return end
  local cols={}
  for c=0,3 do
    emu:write8(0xFF6A, 7*8+c*2); local lo=rd(0xFF6B)
    emu:write8(0xFF6A, 7*8+c*2+1); local hi=rd(0xFF6B)
    cols[#cols+1]=dec(lo,hi)
  end
  -- also body OAM pal
  local bp="?"; for i=4,19 do local b=0xFE00+i*4; if rd(b)>0 and rd(b)<160 then bp=rd(b+3)&7; break end end
  log(string.format("f=%d FFBF=%02X bodypal=%s OBP7=[%s]", f, rd(0xFFBF), tostring(bp), table.concat(cols," ")))
end)
