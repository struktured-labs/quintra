-- riff_diag5.lua : fire the combo ONCE cleanly (FFBA pre-set 0 -> Riff), then
-- DO NOT touch DF1D/DF1F afterwards. Wait up to 300 frames for D880 to change
-- to the arena. Logs D880/FFBA/DF1D/DF1F/DF20/DF21 every frame after the fire.
local OUT = "/tmp/riff"
local SS  = "/home/struktured/projects/penta-dragon-dx-claude/save_states_for_claude/level1_sara_d_alone.ss0"
local f = 0
local loaded = false
local done = false
local mask = 0
local fired = false
local fire_frame = nil
local function log(m) local h=io.open(OUT.."/diag5.log","a"); if h then h:write(m.."\n"); h:close() end end
do local h=io.open(OUT.."/diag5.log","w"); if h then h:write("riff_diag5 start\n"); h:close() end end

callbacks:add("keysRead", function() emu:setKeys(mask) end)

callbacks:add("frame", function()
  if done then return end
  f = f + 1
  if not loaded and f == 3 then
    emu:loadStateFile(SS)
    emu:write8(0xFFBA, 0x00)   -- INC on fire -> 1 -> Riff
    -- clear guards ONCE so the single fire is allowed
    emu:write8(0xDF1D, 0x00)
    emu:write8(0xDF1F, 0x00)
    emu:write8(0xDF0C, 0x00)
    loaded = true
    log("loaded D880="..string.format("%02X",emu:read8(0xD880)))
    return
  end
  if not loaded then return end

  if not fired then
    -- press combo for 5 frames starting at f=40 (after settle)
    if f >= 40 and f < 45 then mask = 0x0C else mask = 0 end
    if f == 50 then
      fired = true; fire_frame = f
      log(string.format("post-press FFBA=%02X DF0C=%02X DF1D=%02X DF1F=%02X DF20=%02X DF21=%02X D880=%02X",
        emu:read8(0xFFBA), emu:read8(0xDF0C), emu:read8(0xDF1D), emu:read8(0xDF1F),
        emu:read8(0xDF20), emu:read8(0xDF21), emu:read8(0xD880)))
    end
    return
  end

  mask = 0
  local d = emu:read8(0xD880)
  if (f - fire_frame) % 5 == 0 then
    log(string.format("f%d (+%d) D880=%02X FFBA=%02X FFC1=%d DF1D=%02X DF1F=%02X",
      f, f-fire_frame, d, emu:read8(0xFFBA), emu:read8(0xFFC1), emu:read8(0xDF1D), emu:read8(0xDF1F)))
  end
  if d == 0x0D then emu:screenshot(OUT.."/diag5_riff.png"); log("REACHED RIFF f"..f); done = true; return end
  if d ~= 0x02 and d ~= 0x0D then log(string.format("f%d D880 -> %02X", f, d)) end
  if f - fire_frame > 300 then log("GAVE UP D880="..string.format("%02X",d)); done = true end
end)
