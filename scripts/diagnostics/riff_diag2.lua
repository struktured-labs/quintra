-- riff_diag2.lua : check DF1E sentinel + hold combo longer + use keysRead.
local OUT = "/tmp/riff"
local SS  = "/home/struktured/projects/penta-dragon-dx-claude/save_states_for_claude/level1_sara_d_alone.ss0"
local f = 0
local loaded = false
local done = false
local hold = false
local function log(m) local h=io.open(OUT.."/diag2.log","a"); if h then h:write(m.."\n"); h:close() end end
do local h=io.open(OUT.."/diag2.log","w"); if h then h:write("riff_diag2 start\n"); h:close() end end

-- Inject input in keysRead (fires right before the game reads the joypad).
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
    log(string.format("loaded D880=%02X FFC1=%d FFBA=%02X DF1E=%02X DF0C=%02X DF20=%02X DF21=%02X",
      emu:read8(0xD880), emu:read8(0xFFC1), emu:read8(0xFFBA),
      emu:read8(0xDF1E), emu:read8(0xDF0C), emu:read8(0xDF20), emu:read8(0xDF21)))
    return
  end
  if not loaded then return end

  -- 8 frames hold, 8 frames release
  local phase = f % 16
  hold = (phase < 8)

  if f % 4 == 0 and f < 500 then
    log(string.format("f%d hold=%s FF93=%02X DF0C=%02X DF1E=%02X D880=%02X FFBA=%02X",
      f, tostring(hold), emu:read8(0xFF93), emu:read8(0xDF0C),
      emu:read8(0xDF1E), emu:read8(0xD880), emu:read8(0xFFBA)))
  end
  if emu:read8(0xD880) ~= 0x02 and emu:read8(0xD880) ~= 0x0C+0 then
    log(string.format("f%d D880 CHANGED -> %02X FFBA=%02X", f, emu:read8(0xD880), emu:read8(0xFFBA)))
  end
  if f > 520 then log("DONE D880="..string.format("%02X",emu:read8(0xD880))); done = true end
end)
