-- riff_diag6.lua : settle long (180 frames) so the game is in a stable dungeon
-- main-loop/VBlank rhythm, THEN pulse SELECT+START (5 on / 9 off) WITHOUT
-- touching DF1F/DF1D after the initial one-time clear. Watch for D880 -> 0x0D.
local OUT = "/tmp/riff"
local SS  = "/home/struktured/projects/penta-dragon-dx-claude/save_states_for_claude/level1_sara_d_alone.ss0"
local f = 0
local loaded = false
local done = false
local mask = 0
local settle = 180
local pulses = 0
local function log(m) local h=io.open(OUT.."/diag6.log","a"); if h then h:write(m.."\n"); h:close() end end
do local h=io.open(OUT.."/diag6.log","w"); if h then h:write("riff_diag6 start\n"); h:close() end end

callbacks:add("keysRead", function() emu:setKeys(mask) end)

callbacks:add("frame", function()
  if done then return end
  f = f + 1
  if not loaded and f == 3 then
    emu:loadStateFile(SS)
    emu:write8(0xFFBA, 0x00)
    emu:write8(0xDF1D, 0x00)
    emu:write8(0xDF1F, 0x00)
    emu:write8(0xDF0C, 0x00)
    loaded = true
    log("loaded D880="..string.format("%02X",emu:read8(0xD880)))
    return
  end
  if not loaded then return end

  local d = emu:read8(0xD880)
  if d == 0x0D then emu:screenshot(OUT.."/diag6_riff.png"); log("REACHED RIFF f"..f.." FFBA="..string.format("%02X",emu:read8(0xFFBA))); done=true; return end
  if d ~= 0x02 then log(string.format("f%d D880 -> %02X FFBA=%02X", f, d, emu:read8(0xFFBA))) end

  if f < settle then
    mask = 0
    return
  end

  -- pulse 5 on / 9 off
  local ph = (f - settle) % 14
  if ph < 5 then mask = 0x0C else mask = 0 end
  if ph == 0 then
    pulses = pulses + 1
    log(string.format("pulse#%d f%d D880=%02X FFBA=%02X DF0C=%02X DF1D=%02X DF1F=%02X",
      pulses, f, d, emu:read8(0xFFBA), emu:read8(0xDF0C), emu:read8(0xDF1D), emu:read8(0xDF1F)))
  end
  if f > settle + 600 then log("END D880="..string.format("%02X",d).." FFBA="..string.format("%02X",emu:read8(0xFFBA))); done = true end
end)
