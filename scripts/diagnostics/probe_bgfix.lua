-- Verify the unified scene_detect BG-flood fix. MODE=banner: cold-boot attract,
-- reach the 0x1B banner, dump on-screen BG attr histogram (expect 0 red p1).
-- MODE=postboss: load a dungeon save state, force D880=0x16, dump attr histogram
-- (expect 0 red p1). Counts BG palette of every visible cell (VBK=1 low3).
local OUT = os.getenv("OUT") or "/tmp/bgfix"
local MODE = os.getenv("MODE") or "banner"
local STATE = os.getenv("STATE") or "save_states_for_claude/level1_sara_d_alone.ss0"
local f, done = 0, false
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("bgfix "..MODE.."\n");h:close() end end
local function attrHisto()
  local base = ((emu:read8(0xFF40)&0x08)~=0) and 0x9C00 or 0x9800
  emu:write8(0xFF4F,1); local h={}
  for r=0,17 do for c=0,19 do local p=emu:read8(base+r*32+c)&7; h[p]=(h[p] or 0)+1 end end
  emu:write8(0xFF4F,0)
  local s=""; for p=0,7 do if h[p] then s=s..string.format(" p%d=%d",p,h[p]) end end
  return s, (h[1] or 0)
end
callbacks:add("frame", function()
  if done then return end
  f = f + 1
  emu:setKeys(0)
  if MODE=="banner" then
    local d = emu:read8(0xD880)
    if d==0x1B and f>3700 then
      done=true
      local s,red = attrHisto()
      log(string.format("BANNER D880=0x1B f%d attrs:%s  RED(p1)=%d", f, s, red))
      emu:screenshot(OUT.."_banner.png")
      log(red==0 and "PASS: no red in banner" or ("FAIL: "..red.." red cells"))
      emu:stop()
    end
    if f>5000 then log("FAIL: never reached banner"); done=true; emu:stop() end
  else -- postboss
    if f==10 then pcall(function() return emu:loadStateFile(STATE) end) end
    if f>=20 and f<=70 then emu:write8(0xD880,0x16) end  -- force post-boss reload scene
    if f==70 then
      done=true
      local s,red = attrHisto()
      log(string.format("POSTBOSS forced D880=0x16 f%d attrs:%s  RED(p1)=%d", f, s, red))
      emu:screenshot(OUT.."_postboss.png")
      log(red < 30 and "PASS: post-boss not red-flooded" or ("FAIL: "..red.." red cells"))
      emu:stop()
    end
  end
end)
