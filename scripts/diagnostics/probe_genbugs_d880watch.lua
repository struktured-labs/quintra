-- general-bugs: watch D880 transitions over a long boot (no input), log every change.
local out = io.open("/tmp/general-bugs/d880_watch.txt", "w")
local f = 0
local prev = -1
local done = false
callbacks:add("frame", function()
  f = f + 1
  if done then return end
  local d = emu:read8(0xD880)
  local ffc1 = emu:read8(0xFFC1)
  if d ~= prev then
    out:write(string.format("frame=%d D880 %02X -> %02X (FFC1=%02X)\n", f, prev, d, ffc1))
    prev = d
  end
  if f >= 3500 then out:write("DONE\n"); out:close(); done = true end
end)
