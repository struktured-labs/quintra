-- miniboss cluster: disable our OBJ colorizer entirely (loop count -> 0) and see
-- if gargoyle body palette changes. If body stays p7 -> game-native attrs.
-- colorizer loop byte at bank13:0x6A11 -> fileoff 0x34000+(0x6A11-0x4000)=0x36A11
local STATE = "save_states_for_claude/level1_sara_w_gargoyle_mini_boss.ss0"
local OUT   = "/tmp/miniboss/gargoyle_disable.log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("disable colorizer test\n");h:close() end end
local f=0; local loaded=false; local patched=false
local function rd(a) return emu:read8(a) end
local LOOP_FILEOFF = 0x34000 + (0x6A11 - 0x4000)  -- 0x36A11
callbacks:add("frame", function()
  f=f+1
  if not patched then
    pcall(function() emu.memory.cart0:write8(LOOP_FILEOFF, 0x00) end)
    log("loopcount->0 readback="..string.format("%02X", emu.memory.cart0:read8(LOOP_FILEOFF)))
    patched=true; return
  end
  if not loaded then emu:loadStateFile(STATE); loaded=true; return end
  if f < 140 then return end
  if f > 142 then return end
  local parts={}
  for i=0,23 do
    local b=0xFE00+i*4
    local y=rd(b); local t=rd(b+2); local a=rd(b+3)
    if y>0 and y<150 and t>=0x30 and t<0x60 then parts[#parts+1]=string.format("%02X:p%d",t,a&7) end
  end
  log(string.format("f=%d FFBF=%02X body=[%s]", f, rd(0xFFBF), table.concat(parts," ")))
end)
