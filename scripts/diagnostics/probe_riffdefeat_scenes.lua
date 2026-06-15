-- riff-defeat cluster: reach Riff arena, then directly exercise the post-boss
-- scenes (0x16 post-boss reload, 0x18 splash) and observe what scene_detect
-- loads into 0xDA00 + the resulting BG attrs + on-screen tile ids. This
-- isolates the colorizer behavior per post-defeat scene byte (the fix target).
local OUT="/tmp/riff-defeat/scenes.log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("riff-defeat per-scene trace\n");h:close() end end

local f=0; local ph="boot"; local fid=0; local pf=0; local done=false

local function da00hist()
  local hist={} for p=0,7 do hist[p]=0 end
  for i=0,255 do local v=emu:read8(0xDA00+i) & 7; hist[v]=hist[v]+1 end
  local s="DA00 hist:" for p=0,7 do s=s..string.format(" p%d=%d",p,hist[p]) end
  return s
end
local function attrhist()
  emu:write8(0xFF4F,1)
  local hist={} for p=0,7 do hist[p]=0 end
  for row=0,17 do for col=0,19 do hist[(emu:read8(0x9800+row*32+col))&7]=hist[(emu:read8(0x9800+row*32+col))&7]+1 end end
  emu:write8(0xFF4F,0)
  local s="ATTR hist:" for p=0,7 do s=s..string.format(" p%d=%d",p,hist[p]) end
  return s
end
local function tilehist()
  emu:write8(0xFF4F,0)
  -- count visible tile-ids in the 0x80-0xDF "font/item -> p1 red" band
  local nred=0; local ntot=0
  for row=0,17 do for col=0,19 do
    local t=emu:read8(0x9800+row*32+col); ntot=ntot+1
    if t>=0x80 and t<=0xDF then nred=nred+1 end
  end end
  return string.format("TILES: visible=%d in_redband(0x80-0xDF)=%d", ntot, nred)
end
local function snap(tag)
  log(string.format("[%s] f=%d D880=0x%02X FFC1=%d FFBA=%d DF0D=0x%02X DF02=0x%02X",
    tag,f,emu:read8(0xD880),emu:read8(0xFFC1),emu:read8(0xFFBA),emu:read8(0xDF0D),emu:read8(0xDF02)))
  log("  "..da00hist())
  log("  "..attrhist())
  log("  "..tilehist())
end

callbacks:add("frame",function()
  if done then return end
  f=f+1
  if ph=="boot" then
    if f==2 then pcall(function() emu:loadStateFile("save_states_for_claude/level1_sara_d_alone.ss0") end) end
    if f>4 and emu:read8(0xD880)==0x02 and emu:read8(0xFFC1)==1 then fid=fid+1; if fid>20 then ph="riff";pf=0 end end
    return
  end
  if ph=="riff" then
    if pf==0 then emu:write8(0xFFBA,0); emu:write8(0xDF0C,0); emu:write8(0xDF1D,0) end
    pf=pf+1
    if pf>=2 and pf<14 then emu:setKeys(0x0C)
    elseif pf>=14 and pf<26 then emu:setKeys(0)
    elseif pf>=26 then emu:setKeys(0)
      if emu:read8(0xD880)==0x0D then log("REACHED RIFF f="..f); ph="settle";pf=0
      elseif pf>500 then log("FAILED riff"); done=true end
    end
    return
  end
  if ph=="settle" then
    emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF); pf=pf+1
    if pf==60 then snap("RIFF_ALIVE_0x0D"); ph="scene16"; pf=0 end
    return
  end
  -- Force D880=0x16 (post-boss reload). scene_detect runs each VBlank via
  -- the teleport routine; observe which table it loads + resulting attrs.
  if ph=="scene16" then
    emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF)
    emu:write8(0xD880,0x16); pf=pf+1
    if pf==30 then snap("FORCED_0x16_t30") end
    if pf==60 then snap("FORCED_0x16_t60"); ph="scene18"; pf=0 end
    return
  end
  -- Force D880=0x18 (boss splash). scene_detect should load splash table (pal0).
  if ph=="scene18" then
    emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF)
    emu:write8(0xD880,0x18); pf=pf+1
    if pf==30 then snap("FORCED_0x18_t30") end
    if pf==60 then snap("FORCED_0x18_t60"); ph="scene1C"; pf=0 end
    return
  end
  -- Force D880=0x1C (logo-text-menu, per orchestrator notes) — another possible
  -- post-defeat menu scene; check table fallthrough.
  if ph=="scene1C" then
    emu:write8(0xD880,0x1C); pf=pf+1
    if pf==60 then snap("FORCED_0x1C_t60"); ph="scene0B"; pf=0 end
    return
  end
  -- Force D880=0x0B (stuck transitional) — sometimes the post-boss limbo.
  if ph=="scene0B" then
    emu:write8(0xD880,0x0B); pf=pf+1
    if pf==60 then snap("FORCED_0x0B_t60"); log("DONE"); done=true end
    return
  end
end)
