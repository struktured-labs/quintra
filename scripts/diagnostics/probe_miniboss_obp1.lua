local STATE="save_states_for_claude/level1_sara_d_spider_miniboss.ss0"
local OUT="/tmp/miniboss/spider_obp1.log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("obp1 loader-runs test\n");h:close() end end
local f=0;local loaded=false;local patched=false
local function rd(a) return emu:read8(a) end
local function fo(a) return 0x34000+(a-0x4000) end
local function dec(lo,hi) local v=lo|(hi<<8); return string.format("%04X",v) end
callbacks:add("frame",function()
 f=f+1
 if not patched then
  -- OBP1 static (SaraDragon) @ obj_data+8 = 0x6848. patch c1 to sentinel ABCD
  pcall(function() emu.memory.cart0:write8(fo(0x6848)+2,0xCD); emu.memory.cart0:write8(fo(0x6848)+3,0xAB) end)
  log("OBP1 static c1 -> ABCD"); patched=true; return
 end
 if not loaded then emu:loadStateFile(STATE);loaded=true;return end
 if f<140 or f>141 then return end
 emu:write8(0xFF6A,1*8+2);local lo=rd(0xFF6B);emu:write8(0xFF6A,1*8+3);local hi=rd(0xFF6B)
 log(string.format("f=%d OBP1.c1=%s (ABCD means loader ran & copied OBP1)",f,dec(lo,hi)))
end)
