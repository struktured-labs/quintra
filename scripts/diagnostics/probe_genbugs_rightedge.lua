-- general-bugs: trace right-edge wall cell (r16,c19) frame-by-frame: tile, pal,
-- SCX, SCX/8, displayed page, DF04 (sweep row), to pin WHY the right column loses gray.
local out = io.open("/tmp/general-bugs/rightedge_trace.txt","w")
local f,done,loaded=0,false,false
callbacks:add("frame", function()
  f=f+1
  if done then return end
  if not loaded and f==5 then emu:loadStateFile("save_states_for_claude/level1_sara_d_alone.ss0"); loaded=true; return end
  if not loaded then return end
  if f>=250 and f<=360 then
    local lcdc=emu:read8(0xFF40); local base=(lcdc&0x08)~=0 and 0x9C00 or 0x9800
    -- read several right-edge cells
    local parts={}
    for _,rc in ipairs({{16,19},{16,18},{0,19},{8,19}}) do
      local r,c=rc[1],rc[2]
      emu:write8(0xFF4F,0); local t=emu:read8(base+r*32+c)
      emu:write8(0xFF4F,1); local a=emu:read8(base+r*32+c)&0x07
      parts[#parts+1]=string.format("(%d,%d)%02X/%d",r,c,t,a)
    end
    emu:write8(0xFF4F,0)
    local scx=emu:read8(0xFF43)
    out:write(string.format("f=%d base=%04X SCX=%02X(/8=%d) DF04=%02X | %s\n",
      f, base, scx, scx//8, emu:read8(0xDF04), table.concat(parts," ")))
  end
  if f>=362 then out:write("DONE\n"); out:close(); done=true end
end)
