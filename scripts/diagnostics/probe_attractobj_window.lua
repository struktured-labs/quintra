-- attract-obj cluster: hunt for ANY frame where OAM sprites are present while
-- FFC1==0 (the hypothesized "uncolorized attract sprite" window). Also capture
-- the FIRST few frames of each demo-gameplay entry to see if sprites render
-- black before the colorizer's first pass. Log every frame where OAM>0 and
-- FFC1==0, plus every frame in the first 30 frames after FFC1 flips 0->1.
local OUT = os.getenv("OUT") or "/tmp/attract-obj/window"
local f = 0
local done = false
local prevffc1 = -1
local ffc1FlipFrame = -1
local hits0 = 0
local log_lines = 0
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("attract-obj window hunt\n");h:close() end end
local function objp(p,c) local i=p*8+c*2; emu:write8(0xFF6A,i); local lo=emu:read8(0xFF6B); emu:write8(0xFF6A,i+1); local hi=emu:read8(0xFF6B); return (hi<<8)|lo end
local function oamInfo()
  local n=0; local samples={}
  for s=0,39 do
    local y=emu:read8(0xFE00+s*4); local x=emu:read8(0xFE00+s*4+1)
    local tile=emu:read8(0xFE00+s*4+2); local attr=emu:read8(0xFE00+s*4+3)
    if y~=0 and y<160 and x~=0 and x<168 then
      n=n+1
      if #samples<6 then samples[#samples+1]=string.format("t%02X/a%02X/p%d",tile,attr,attr&0x07) end
    end
  end
  return n, table.concat(samples," ")
end
callbacks:add("frame", function()
  if done then return end
  f = f + 1
  emu:setKeys(0)
  local d = emu:read8(0xD880)
  local ffc1 = emu:read8(0xFFC1)
  local n, samp = oamInfo()
  -- Hunt: OAM present while FFC1==0
  if n > 0 and ffc1 == 0 and hits0 < 60 then
    hits0 = hits0 + 1
    log(string.format("FFC1=0+OAM f%d D880=%02X OAM=%d | %s", f, d, n, samp))
  end
  -- Capture first 30 frames after each 0->1 flip of FFC1
  if ffc1 == 1 and prevffc1 == 0 then ffc1FlipFrame = f end
  if ffc1FlipFrame > 0 and f - ffc1FlipFrame < 30 and log_lines < 90 then
    log_lines = log_lines + 1
    log(string.format("postFlip+%d f%d D880=%02X OAM=%d | %s | o2c1=%04X o4c1=%04X o6c1=%04X",
      f - ffc1FlipFrame, f, d, n, samp, objp(2,1), objp(4,1), objp(6,1)))
  end
  prevffc1 = ffc1
  if f >= 11000 then log("DONE hits0="..hits0); done = true end
end)
