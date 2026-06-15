-- cameo_telediag2.lua: fire ONE clean combo (no FFBA re-assert during/after),
-- let the hook INC FFBA 2->3, then trace D880 for ~200 frames. Try several
-- variations to find what makes D880 flip to 0x0F.
local OUT="/tmp/cameo/telediag2.log"
local STATE="save_states_for_claude/level1_sara_d_alone.ss0"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("telediag2\n");h:close() end end
local f=0; local phase="load"; local pf=0; local done=false
local function snap(tag)
  log(string.format("%s f%d D880=%02X FFBA=%02X FFBF=%02X DF0C=%02X DF1D=%02X DF1F=%02X FF93=%02X FFC1=%02X",
    tag,f,emu:read8(0xD880),emu:read8(0xFFBA),emu:read8(0xFFBF),emu:read8(0xDF0C),emu:read8(0xDF1D),emu:read8(0xDF1F),
    emu:read8(0xFF93),emu:read8(0xFFC1)))
end
callbacks:add("frame",function()
  f=f+1
  if done then return end
  if phase=="load" then emu:loadStateFile(STATE); phase="settle"; pf=0; snap("loaded"); return end
  if phase=="settle" then emu:setKeys(0); pf=pf+1
    if pf>=25 then emu:write8(0xFFBA,2); emu:write8(0xDF0C,0); emu:write8(0xDF1D,0); emu:write8(0xDF1F,0); snap("preset"); phase="gap"; pf=0 end
    return end
  if phase=="gap" then emu:setKeys(0); pf=pf+1; if pf>=4 then phase="hold"; pf=0 end; return end
  if phase=="hold" then
    -- hold combo ~8 frames, NO FFBA re-assert
    emu:setKeys(0x0C); pf=pf+1
    if pf>=8 then emu:setKeys(0); phase="trace"; pf=0; snap("released") end
    return end
  if phase=="trace" then
    emu:setKeys(0); pf=pf+1
    if pf<=10 or pf%15==0 then snap("trace"..pf) end
    if emu:read8(0xD880)>=0x0C and emu:read8(0xD880)<=0x14 then snap("ARENA!"); log("DONE"); done=true; return end
    if pf>=260 then snap("end"); log("DONE"); done=true end
    return end
end)
