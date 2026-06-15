-- miniboss cluster: ATTRIBUTION TEST. Patch boss_slot_table[0] (bank13 0x68C0)
-- from 6 to a distinctive 3 via cart0. If gargoyle body changes to p3 -> our
-- colorizer's boss override is the source. If it stays p7 -> game writes attrs.
-- boss_slot_table @0x68C0 logical bank13 -> file offset 0x34000+(0x68C0-0x4000)=0x368C0
-- but cart0:write8 takes a LOGICAL bank-mapped addr? Use emu.memory.cart0:write8(file_off?)
-- Per MEMORY: emu.memory.cart0:write8(rom_addr, val) patches ROM at ABSOLUTE file address.
local STATE = "save_states_for_claude/level1_sara_w_gargoyle_mini_boss.ss0"
local OUT   = "/tmp/miniboss/gargoyle_attrib.log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("attribution test\n");h:close() end end
local f=0; local loaded=false; local patched=false
local function rd(a) return emu:read8(a) end
local SLOT0_FILEOFF = 0x34000 + (0x68C0 - 0x4000)  -- = 0x368C0
callbacks:add("frame", function()
  f=f+1
  if not patched then
    -- patch BEFORE load so it persists
    local ok=pcall(function() emu.memory.cart0:write8(SLOT0_FILEOFF, 0x03) end)
    log("patch boss_slot[0]=3 at fileoff 0x"..string.format("%X",SLOT0_FILEOFF).." ok="..tostring(ok))
    log("readback="..string.format("%02X", emu.memory.cart0:read8(SLOT0_FILEOFF)))
    patched=true
    return
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
