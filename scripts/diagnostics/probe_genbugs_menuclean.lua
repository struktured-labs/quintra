-- general-bugs: clean boot (no state load) to the D880=0x1C menu (~frame 2062+),
-- then dump CRAM + attr grid at several frames to check for flicker (frame-to-frame
-- attr alternation) and verify CRAM matches expected (cond_pal loads it every frame).
local out = io.open("/tmp/general-bugs/menuclean_dump.txt", "w")
local f = 0
local done = false
local dumps = {2100, 2120, 2200, 2400, 2600, 3000}
local di = 1
local prevAttr = nil

local function readBGPal()
  local s = {}
  for p = 0, 7 do
    local cols = {}
    for c = 0, 3 do
      emu:write8(0xFF68, (p*8 + c*2)); local lo = emu:read8(0xFF69)
      emu:write8(0xFF68, (p*8 + c*2 + 1)); local hi = emu:read8(0xFF69)
      cols[#cols+1] = string.format("%02X%02X", hi, lo)
    end
    s[#s+1] = table.concat(cols, " ")
  end
  return s
end

local function getAttrGrid()
  local attrs = {}
  emu:write8(0xFF4F, 1)
  for r=0,17 do for col=0,19 do attrs[r*20+col]=emu:read8(0x9800+r*32+col)&0x07 end end
  emu:write8(0xFF4F, 0)
  return attrs
end

local function dumpScene(tag)
  local d880 = emu:read8(0xD880)
  out:write(string.format("=== %s frame=%d D880=%02X ===\n", tag, f, d880))
  out:write("  BG CRAM:\n")
  for p,line in ipairs(readBGPal()) do out:write(string.format("    BG%d %s\n",p-1,line)) end
  local a = getAttrGrid()
  out:write("  ATTR-PAL GRID:\n")
  for r=0,17 do local row={}; for col=0,19 do row[#row+1]=tostring(a[r*20+col]) end; out:write("    "..table.concat(row).."\n") end
  -- flicker check vs previous dump
  if prevAttr then
    local diffs = 0
    local difflist = {}
    for i=0,17*20+19 do if a[i] ~= prevAttr[i] then diffs=diffs+1; if #difflist<20 then difflist[#difflist+1]=string.format("(%d,%d):%d->%d",i//20,i%20,prevAttr[i],a[i]) end end end
    out:write(string.format("  ATTR DIFF vs prev dump: %d cells\n", diffs))
    if diffs>0 then out:write("    "..table.concat(difflist," ").."\n") end
  end
  prevAttr = a
  out:write("\n")
end

callbacks:add("frame", function()
  f = f + 1
  if done then return end
  if di <= #dumps and f == dumps[di] then
    dumpScene("CHK")
    di = di + 1
  end
  if f >= 3050 then out:write("DONE\n"); out:close(); done=true end
end)
