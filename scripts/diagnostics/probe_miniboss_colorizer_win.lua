-- miniboss cluster: can the COLORIZER win the OAM attr? Raise loop count to 40
-- and patch boss_slot_table[1] (spider) to a distinct index 5. If HW OAM body
-- becomes p5 -> colorizer can control the body (fix = colorizer + slot + loader-on-5).
-- loop byte @0x6A11 fileoff 0x36A11. boss_slot[1] @0x68C1 fileoff 0x368C1.
local STATE = "save_states_for_claude/level1_sara_d_spider_miniboss.ss0"
local OUT   = "/tmp/miniboss/spider_colorizer_win.log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("colorizer win test\n");h:close() end end
local f=0; local loaded=false; local patched=false
local function rd(a) return emu:read8(a) end
local function fo(addr) return 0x34000 + (addr - 0x4000) end
callbacks:add("frame", function()
  f=f+1
  if not patched then
    pcall(function() emu.memory.cart0:write8(fo(0x6A11), 0x28) end)   -- loop=40
    pcall(function() emu.memory.cart0:write8(fo(0x68C1), 0x05) end)   -- spider slot=5
    log("loop=40 spider_slot=5; readback loop="..string.format("%02X",emu.memory.cart0:read8(fo(0x6A11)))..
        " slot1="..string.format("%02X",emu.memory.cart0:read8(fo(0x68C1))))
    patched=true; return
  end
  if not loaded then emu:loadStateFile(STATE); loaded=true; return end
  if f < 140 or f > 142 then return end
  local parts={}
  for i=0,23 do
    local b=0xFE00+i*4
    local y=rd(b); local t=rd(b+2); local a=rd(b+3)
    if y>0 and y<160 and t>=0x30 and t<0x60 then parts[#parts+1]=string.format("%02X:p%d",t,a&7) end
  end
  log(string.format("f=%d FFBF=%02X body=[%s]", f, rd(0xFFBF), table.concat(parts," ")))
end)
