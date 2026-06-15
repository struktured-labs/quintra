-- miniboss cluster: isolate whether loader's STATIC OBP7 copy reaches OBP7.
-- Force-skip the boss-slot override (28->18 at 0x3699B), NOP cache RET Z (0x36CBB),
-- patch OBP7 static (0x6878) to sentinel. If OBP7 becomes sentinel -> static copy
-- reaches OBP7 and the orange/purple is from the boss-slot override write.
local STATE = "save_states_for_claude/level1_sara_d_spider_miniboss.ss0"
local OUT   = "/tmp/miniboss/spider_static7.log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("static7 isolation\n");h:close() end end
local f=0; local loaded=false; local patched=false
local function rd(a) return emu:read8(a) end
local function fo(addr) return 0x34000 + (addr - 0x4000) end
local function dec(lo,hi) local v=lo|(hi<<8); return string.format("%04X(R%02dG%02dB%02d)", v, v&0x1F,(v>>5)&0x1F,(v>>10)&0x1F) end
callbacks:add("frame", function()
  f=f+1
  if not patched then
    pcall(function() emu.memory.cart0:write8(fo(0x6CBB), 0x00) end)        -- cache RET Z -> NOP
    pcall(function() emu.memory.cart0:write8(0x3699B, 0x18) end)           -- boss override JR Z -> JR (always skip)
    local sent={0x00,0x00, 0xE0,0x03, 0x00,0x7C, 0x1F,0x00}                -- green/blue/red
    pcall(function() for i=0,7 do emu.memory.cart0:write8(fo(0x6878)+i, sent[i+1]) end end)
    log("forced cache off + boss override skip + OBP7 static=sentinel")
    patched=true; return
  end
  if not loaded then emu:loadStateFile(STATE); loaded=true; return end
  if f < 140 or f > 142 then return end
  local cols={}
  for c=0,3 do
    emu:write8(0xFF6A, 7*8+c*2); local lo=rd(0xFF6B)
    emu:write8(0xFF6A, 7*8+c*2+1); local hi=rd(0xFF6B)
    cols[#cols+1]=dec(lo,hi)
  end
  log(string.format("f=%d FFBF=%02X OBP7=[%s]", f, rd(0xFFBF), table.concat(cols," ")))
end)
