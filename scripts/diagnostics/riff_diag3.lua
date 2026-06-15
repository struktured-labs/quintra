-- riff_diag3.lua : check REAL sentinel DF0E, DF1D sit-out, DF1F skip, and hold
-- combo via keysRead. Try continuous hold then a clean release-press cycle.
local OUT = "/tmp/riff"
local SS  = "/home/struktured/projects/penta-dragon-dx-claude/save_states_for_claude/level1_sara_d_alone.ss0"
local f = 0
local loaded = false
local done = false
local hold = false
local function log(m) local h=io.open(OUT.."/diag3.log","a"); if h then h:write(m.."\n"); h:close() end end
do local h=io.open(OUT.."/diag3.log","w"); if h then h:write("riff_diag3 start\n"); h:close() end end

callbacks:add("keysRead", function()
  if hold then emu:setKeys(0x0C) else emu:setKeys(0) end
end)

callbacks:add("frame", function()
  if done then return end
  f = f + 1
  if not loaded and f == 3 then
    emu:loadStateFile(SS)
    emu:write8(0xFFBA, 0x01)
    loaded = true
    log(string.format("loaded D880=%02X DF0E(sentinel)=%02X DF0C=%02X DF1D=%02X DF1F=%02X",
      emu:read8(0xD880), emu:read8(0xDF0E), emu:read8(0xDF0C), emu:read8(0xDF1D), emu:read8(0xDF1F)))
    return
  end
  if not loaded then return end

  -- Phase A (f<60): let cold-boot install run, no input
  -- Phase B (f>=60): release/press cycle: 4 frames off, 4 frames on
  if f < 60 then
    hold = false
  else
    local ph = (f - 60) % 8
    hold = (ph >= 4)
  end

  if f % 4 == 0 and f < 400 then
    log(string.format("f%d hold=%s FF93=%02X DF0E=%02X DF0C=%02X DF1D=%02X DF1F=%02X D880=%02X FFBA=%02X",
      f, tostring(hold), emu:read8(0xFF93), emu:read8(0xDF0E), emu:read8(0xDF0C),
      emu:read8(0xDF1D), emu:read8(0xDF1F), emu:read8(0xD880), emu:read8(0xFFBA)))
  end
  local d = emu:read8(0xD880)
  if d ~= 0x02 then
    log(string.format("f%d D880 -> %02X FFBA=%02X FFC1=%d", f, d, emu:read8(0xFFBA), emu:read8(0xFFC1)))
    if d == 0x0D then emu:screenshot(OUT.."/diag3_riff.png"); log("REACHED RIFF"); done=true; return end
  end
  if f > 600 then log("DONE D880="..string.format("%02X",d)); done = true end
end)
