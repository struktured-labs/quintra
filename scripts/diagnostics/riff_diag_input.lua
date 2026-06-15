-- riff_diag_input.lua : diagnose why SELECT+START teleport pulse doesn't fire.
-- Load dungeon ss, pulse 0x0C, and log FF93 (raw joypad), DF0C (debounce),
-- DD09 (input block), D880, FFBA every few frames.
local OUT = "/tmp/riff"
local SS  = "/home/struktured/projects/penta-dragon-dx-claude/save_states_for_claude/level1_sara_d_alone.ss0"
local f = 0
local loaded = false
local done = false
local function log(m) local h=io.open(OUT.."/diag_input.log","a"); if h then h:write(m.."\n"); h:close() end end
do local h=io.open(OUT.."/diag_input.log","w"); if h then h:write("riff_diag_input start\n"); h:close() end end

callbacks:add("frame", function()
  if done then return end
  f = f + 1
  if not loaded and f == 3 then
    emu:loadStateFile(SS)
    emu:write8(0xFFBA, 0x01)
    loaded = true
    log(string.format("loaded D880=%02X FFC1=%d FFBA=%02X DD09=%02X",
      emu:read8(0xD880), emu:read8(0xFFC1), emu:read8(0xFFBA), emu:read8(0xDD09)))
    return
  end
  if not loaded then return end

  -- pulse SELECT+START 0x0C for 5 frames every 12
  local phase = f % 12
  if phase < 5 then emu:setKeys(0x0C) else emu:setKeys(0) end

  if f % 3 == 0 and f < 400 then
    log(string.format("f%d keysphase=%d FF93=%02X FF94=%02X DF0C=%02X DD09=%02X D880=%02X FFBA=%02X",
      f, phase, emu:read8(0xFF93), emu:read8(0xFF94), emu:read8(0xDF0C),
      emu:read8(0xDD09), emu:read8(0xD880), emu:read8(0xFFBA)))
  end
  if f > 420 then log("DONE D880="..string.format("%02X",emu:read8(0xD880))); done = true end
end)
