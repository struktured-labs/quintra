-- general-bugs: from a clean dungeon state, OPEN the SELECT item menu and measure
-- the right-edge wall column color over time. Check the "right-edge wall sliver
-- lost its gray" report. Logs D880, the right 4 columns (16..19) tile/pal per row,
-- across pre-open and post-open windows.
local STATE = "save_states_for_claude/level1_sara_d_alone.ss0"
local out = io.open("/tmp/general-bugs/selectmenu_open.txt", "w")
local f, done, loaded = 0, false, false
local opened = false

local function dumpRight(tag)
  local lcdc=emu:read8(0xFF40); local base=(lcdc&0x08)~=0 and 0x9C00 or 0x9800
  out:write(string.format("=== %s f=%d D880=%02X FFC1=%02X base=%04X SCX=%02X SCY=%02X ===\n",
    tag,f,emu:read8(0xD880),emu:read8(0xFFC1),base,emu:read8(0xFF43),emu:read8(0xFF42)))
  for r=0,17 do
    local cells={}
    for col=16,19 do
      emu:write8(0xFF4F,0); local t=emu:read8(base+r*32+col)
      emu:write8(0xFF4F,1); local a=emu:read8(base+r*32+col)&0x07
      cells[#cells+1]=string.format("%02X/%d",t,a)
    end
    emu:write8(0xFF4F,0)
    out:write("  r"..string.format("%02d",r).." "..table.concat(cells," ").."\n")
  end
  out:write("\n")
end

callbacks:add("frame", function()
  f=f+1
  if done then return end
  if not loaded and f==5 then emu:loadStateFile(STATE); loaded=true; return end
  if not loaded then return end
  if f==120 then dumpRight("PRE_OPEN") end
  -- open SELECT menu
  if f>=140 and f<146 then emu:setKeys(0x04) else emu:setKeys(0) end
  if f==200 then dumpRight("POST_OPEN_1"); opened=true end
  if f==260 then dumpRight("POST_OPEN_2") end
  if f==340 then dumpRight("POST_OPEN_3") end
  -- accumulate right-edge wall flicker (cols 16..19) for rows 0..17, frames 210..400
  if f>=210 and f<=400 then
    local lcdc=emu:read8(0xFF40); local base=(lcdc&0x08)~=0 and 0x9C00 or 0x9800
    flick = flick or {}
    emu:write8(0xFF4F,0); local tiles={}
    for r=0,17 do for col=16,19 do tiles[r*4+(col-16)]=emu:read8(base+r*32+col) end end
    emu:write8(0xFF4F,1)
    for r=0,17 do for col=16,19 do
      local i=r*4+(col-16); local t=tiles[i]; local p=emu:read8(base+r*32+col)&0x07
      local h=flick[i]; if not h then flick[i]={tile=t,pals={}}; h=flick[i] end
      if h.tile~=t then h.tile=t; h.pals={} end
      h.pals[p]=(h.pals[p] or 0)+1
    end end
    emu:write8(0xFF4F,0)
  end
  if f==405 then
    out:write("=== RIGHT-EDGE FLICKER (cols16..19, frames210..400) ===\n")
    for i=0,17*4+3 do local h=flick and flick[i]
      if h then local np=0; local pl={}
        for p,c in pairs(h.pals) do np=np+1; pl[#pl+1]=string.format("p%d:%d",p,c) end
        if np>1 then table.sort(pl); out:write(string.format("  (r%d,c%d) tile=%02X {%s}\n", i//4, 16+(i%4), h.tile, table.concat(pl,","))) end
      end
    end
    out:write("DONE\n"); out:close(); done=true
  end
end)
