-- cameo_telediag.lua: diagnose why the teleport stack-redirect doesn't flip D880.
-- Load dungeon state, fire ONE combo, then trace D880/FFBA/DF0C/DF1D/DF1F/DF20/DF21
-- for the following ~120 frames. Try addKey-based input + a long hold.
local OUT="/tmp/cameo/telediag.log"
local STATE="save_states_for_claude/level1_sara_d_alone.ss0"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("telediag\n");h:close() end end
local f=0; local phase="load"; local pf=0; local done=false
local function snap(tag)
  log(string.format("%s f%d D880=%02X FFBA=%02X FFBF=%02X DF0C=%02X DF1D=%02X DF1F=%02X DF20=%02X DF21=%02X DF23=%02X FF93=%02X SP_n/a",
    tag,f,emu:read8(0xD880),emu:read8(0xFFBA),emu:read8(0xFFBF),emu:read8(0xDF0C),emu:read8(0xDF1D),emu:read8(0xDF1F),
    emu:read8(0xDF20),emu:read8(0xDF21),emu:read8(0xDF23),emu:read8(0xFF93)))
end
callbacks:add("frame",function()
  f=f+1
  if done then return end
  if phase=="load" then emu:loadStateFile(STATE); phase="settle"; pf=0; snap("loaded"); return end
  if phase=="settle" then emu:setKeys(0); pf=pf+1
    if pf>=20 then emu:write8(0xFFBA,2); emu:write8(0xDF0C,0); emu:write8(0xDF1D,0); snap("presettle"); phase="hold"; pf=0 end
    return end
  if phase=="hold" then
    -- hold the combo for 20 frames using setKeys
    emu:setKeys(0x0C); emu:write8(0xFFBA,2); pf=pf+1
    if pf<=4 or pf==20 then snap("hold"..pf) end
    if pf>=20 then emu:setKeys(0); phase="trace"; pf=0; snap("release") end
    return end
  if phase=="trace" then
    emu:setKeys(0); pf=pf+1
    if pf<=8 or pf%10==0 then snap("trace"..pf) end
    if pf>=150 then log("DONE"); done=true end
    return end
end)
