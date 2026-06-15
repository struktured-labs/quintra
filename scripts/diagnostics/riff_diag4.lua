-- riff_diag4.lua : hold combo continuously, keep DF1D=0 each frame, log every
-- frame to see if DF0C ever flips (fire) or D880 changes. Also test pressing
-- DOWN (0x80) to confirm keysRead reaches gameplay (Sara should not move D880).
local OUT = "/tmp/riff"
local SS  = "/home/struktured/projects/penta-dragon-dx-claude/save_states_for_claude/level1_sara_d_alone.ss0"
local f = 0
local loaded = false
local done = false
local mask = 0
local function log(m) local h=io.open(OUT.."/diag4.log","a"); if h then h:write(m.."\n"); h:close() end end
do local h=io.open(OUT.."/diag4.log","w"); if h then h:write("riff_diag4 start\n"); h:close() end end

callbacks:add("keysRead", function() emu:setKeys(mask) end)

callbacks:add("frame", function()
  if done then return end
  f = f + 1
  if not loaded and f == 3 then
    emu:loadStateFile(SS)
    emu:write8(0xFFBA, 0x00)
    loaded = true
    log("loaded D880="..string.format("%02X",emu:read8(0xD880)))
    return
  end
  if not loaded then return end

  -- f 4..40: no input (let cold-boot settle), keep clearing sit-out
  -- f 41..120: press/release cycle 6 on / 6 off, clearing DF1D each frame
  emu:write8(0xDF1D, 0x00)
  emu:write8(0xDF1F, 0x00)
  if f < 40 then
    mask = 0
  else
    local ph = (f - 40) % 12
    if ph < 6 then mask = 0x0C else mask = 0 end
  end

  if f >= 38 and f < 140 then
    log(string.format("f%d mask=%02X FF93=%02X FF94=%02X DF0C=%02X DF1D=%02X D880=%02X FFBA=%02X",
      f, mask, emu:read8(0xFF93), emu:read8(0xFF94), emu:read8(0xDF0C),
      emu:read8(0xDF1D), emu:read8(0xD880), emu:read8(0xFFBA)))
  end
  local d = emu:read8(0xD880)
  if d ~= 0x02 then log(string.format("f%d D880 -> %02X FFBA=%02X", f, d, emu:read8(0xFFBA))); if d==0x0D then done=true end end
  if f > 200 then log("END D880="..string.format("%02X",d)); done = true end
end)
