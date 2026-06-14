-- Verify item-10 mechanism: writing the ROM palette SOURCE (cart0) + forcing
-- cond_pal reload (DF00=0) makes the edit load into CRAM and PERSIST (survives
-- cond_pal's hash re-cache). Load dungeon state, edit BG0 color1 -> 001F (red)
-- and OBJ4 color1 -> 03E0 (green) via source, check CRAM after.
local OUT="/tmp/editortest"
local f,done=0,false
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("editortest\n");h:close() end end
local function bgc(p,c) local i=p*8+c*2; emu:write8(0xFF68,i); local lo=emu:read8(0xFF69); emu:write8(0xFF68,i+1); local hi=emu:read8(0xFF69); return (hi<<8)|lo end
local function objc(p,c) local i=p*8+c*2; emu:write8(0xFF6A,i); local lo=emu:read8(0xFF6B); emu:write8(0xFF6A,i+1); local hi=emu:read8(0xFF6B); return (hi<<8)|lo end
callbacks:add("frame", function()
  if done then return end
  f=f+1; emu:setKeys(0)
  if f==10 then pcall(function() return emu:loadStateFile("save_states_for_claude/level1_sara_d_alone.ss0") end) end
  if f==40 then log(string.format("BEFORE: BG0c1=%04X OBJ4c1=%04X", bgc(0,1), objc(4,1))) end
  if f>=50 and f<=120 then
    -- emulate the editor's apply_writes for BG0:1=001F and OBJ4:1=03E0
    emu.memory.cart0:write8(0x36800+2, 0x1F); emu.memory.cart0:write8(0x36800+3, 0x00)  -- BG0 c1
    emu.memory.cart0:write8(0x36840+4*8+2, 0xE0); emu.memory.cart0:write8(0x36840+4*8+3, 0x03)  -- OBJ4 c1
    emu:write8(0xDF00,0x00)  -- force cond_pal reload
  end
  if f==120 then log(string.format("AFTER:  BG0c1=%04X OBJ4c1=%04X (want 001F / 03E0)", bgc(0,1), objc(4,1))) end
  if f==121 then  -- stop forcing; check it PERSISTS via source (cond_pal reloads source)
  end
  if f==200 then log(string.format("PERSIST(no force since f120): BG0c1=%04X OBJ4c1=%04X", bgc(0,1), objc(4,1))); done=true; emu:stop() end
  if f>120 then else end
end)
