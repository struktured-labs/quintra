-- miniboss cluster: patch BOTH the static obj_data OBP7 AND spider boss_palette
-- to a unique sentinel green (c1=03E0), then check live OBP7 during spider fight.
-- If OBP7 becomes sentinel -> our loader controls it (fix via palette tables).
-- If OBP7 stays game orange/purple -> game overwrites it after loader (need diff fix).
-- obj_data OBP7 @ bank13 pal_addr+64+56. pal_addr=0x6800 -> obj_data=0x6840, OBP7=0x6878
-- spider boss_palette @ boss_pal_addr 0x6880 + 1*8 = 0x6888  (FFBF=2 -> idx1)
local STATE = "save_states_for_claude/level1_sara_d_spider_miniboss.ss0"
local OUT   = "/tmp/miniboss/spider_loadertest.log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("loader control test\n");h:close() end end
local f=0; local loaded=false; local patched=false
local function rd(a) return emu:read8(a) end
local function fo(addr) return 0x34000 + (addr - 0x4000) end
local OBP7_STATIC = fo(0x6878)
local SPIDER_BOSS = fo(0x6888)
local function dec(lo,hi) local v=lo|(hi<<8); return string.format("%04X(R%02dG%02dB%02d)", v, v&0x1F,(v>>5)&0x1F,(v>>10)&0x1F) end
callbacks:add("frame", function()
  f=f+1
  if not patched then
    -- write sentinel: c0=0000 c1=03E0(green) c2=7C00(blue) c3=001F(red)
    local sent = {0x00,0x00, 0xE0,0x03, 0x00,0x7C, 0x1F,0x00}
    pcall(function() for i=0,7 do emu.memory.cart0:write8(OBP7_STATIC+i, sent[i+1]) end end)
    pcall(function() for i=0,7 do emu.memory.cart0:write8(SPIDER_BOSS+i, sent[i+1]) end end)
    log("patched OBP7 static + spider boss to sentinel green/blue/red")
    patched=true; return
  end
  if not loaded then emu:loadStateFile(STATE); loaded=true; return end
  if f < 132 or f > 134 then return end
  local cols={}
  for c=0,3 do
    emu:write8(0xFF6A, 7*8+c*2); local lo=rd(0xFF6B)
    emu:write8(0xFF6A, 7*8+c*2+1); local hi=rd(0xFF6B)
    cols[#cols+1]=dec(lo,hi)
  end
  log(string.format("f=%d FFBF=%02X live OBP7=[%s]", f, rd(0xFFBF), table.concat(cols," ")))
end)
