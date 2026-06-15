-- riff-defeat cluster: reach Riff arena (FFBA=1, D880=0x0D), then kill the boss
-- (DCBB->0) and trace the post-defeat scene transition + WRAM 0xDA00 table +
-- BG attrs + FFC1. Goal: identify the scene byte + which table scene_detect
-- loads + the red source.
local OUT="/tmp/riff-defeat/transition.log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("riff-defeat transition trace\n");h:close() end end

local f=0
local ph="boot"
local fid=0
local pf=0
local done=false
local kill_frame=nil
local last_d880=nil

local function dump_da00(tag)
  log("---- 0xDA00 table dump ("..tag..") ----")
  -- histogram of palette values
  local hist={}
  for i=0,255 do hist[i]=0 end
  for i=0,255 do local v=emu:read8(0xDA00+i); hist[v]=(hist[v] or 0)+1 end
  local hs="DA00 pal histogram:"
  for p=0,7 do hs=hs..string.format(" p%d=%d",p,hist[p] or 0) end
  log(hs)
  -- first 32 entries (low tile IDs = boss body / floor)
  for r=0,1 do
    local s=string.format("DA%02X:",r*16)
    for cc=0,15 do s=s..string.format(" %02X",emu:read8(0xDA00+r*16+cc)) end
    log(s)
  end
end

local function dump_attrs(tag)
  -- BG attr plane (VRAM bank 1) palette histogram across visible 20x18 region
  emu:write8(0xFF4F,1)
  local hist={}
  for p=0,7 do hist[p]=0 end
  for row=0,17 do
    for col=0,19 do
      local a=emu:read8(0x9800+row*32+col)
      local p=a & 0x07
      hist[p]=hist[p]+1
    end
  end
  emu:write8(0xFF4F,0)
  local hs="ATTR pal histogram ("..tag.."):"
  for p=0,7 do hs=hs..string.format(" p%d=%d",p,hist[p]) end
  log(hs)
end

local function dump_tiles(tag)
  -- BG tile-id plane (VRAM bank 0): show row 9 (middle) tile ids
  emu:write8(0xFF4F,0)
  local s="TILES row9 ("..tag.."):"
  for col=0,19 do s=s..string.format(" %02X",emu:read8(0x9800+9*32+col)) end
  log(s)
end

local function snapshot(tag)
  log(string.format("[%s] f=%d D880=0x%02X FFC1=%d FFBA=%d FFBF=%d DCBB=0x%02X DF0D(prevscene)=0x%02X DF02(coldboot)=0x%02X",
    tag, f, emu:read8(0xD880), emu:read8(0xFFC1), emu:read8(0xFFBA),
    emu:read8(0xFFBF), emu:read8(0xDCBB), emu:read8(0xDF0D), emu:read8(0xDF02)))
  dump_attrs(tag)
  dump_da00(tag)
  dump_tiles(tag)
end

callbacks:add("frame",function()
  if done then return end
  f=f+1

  if ph=="boot" then
    -- Load a real dungeon gameplay save state once.
    if f==2 then
      local ok = pcall(function() emu:loadStateFile("save_states_for_claude/level1_sara_d_alone.ss0") end)
      log("loadState ok="..tostring(ok))
    end
    if f>4 then
      local d=emu:read8(0xD880); local c=emu:read8(0xFFC1)
      if d==0x02 and c==1 then fid=fid+1; if fid>20 then ph="totriff"; pf=0; log("dungeon ready f="..f) end end
    end
    return
  end

  if ph=="totriff" then
    -- set FFBA=1 so the next teleport lands Riff (combo INCs FFBA: cycle->Riff
    -- needs FFBA=0 before press so INC->1). We force FFBA=0 then press combo.
    if pf==0 then emu:write8(0xFFBA,0); emu:write8(0xDF0C,0); emu:write8(0xDF1D,0) end
    pf=pf+1
    if pf>=2 and pf<14 then emu:setKeys(0x0C)
    elseif pf>=14 and pf<26 then emu:setKeys(0)
    elseif pf>=26 then
      emu:setKeys(0)
      if emu:read8(0xD880)==0x0D then
        log("REACHED RIFF f="..f.." FFBA="..emu:read8(0xFFBA))
        ph="settle"; pf=0
      elseif pf>500 then log("FAILED to reach Riff D880=0x"..string.format("%02X",emu:read8(0xD880))); done=true end
    end
    return
  end

  if ph=="settle" then
    -- hold Sara HP, let arena settle ~90 frames, snapshot the healthy Riff arena
    emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF)
    pf=pf+1
    if pf==90 then snapshot("RIFF_ALIVE"); ph="kill"; pf=0; log("== now killing Riff ==") end
    return
  end

  if ph=="kill" then
    -- Simulate boss death: zero DCBB (boss HP). Keep Sara alive.
    emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF)
    emu:write8(0xDCBB,0x00)
    pf=pf+1
    -- watch D880 transitions
    local d=emu:read8(0xD880)
    if d~=last_d880 then
      log(string.format("D880 TRANSITION f=%d : 0x%02X -> 0x%02X (FFC1=%d FFBA=%d DF0D=0x%02X DF02=0x%02X)",
        f, last_d880 or -1, d, emu:read8(0xFFC1), emu:read8(0xFFBA), emu:read8(0xDF0D), emu:read8(0xDF02)))
      last_d880=d
    end
    if pf==5 then snapshot("POST_KILL_t5") end
    if pf==30 then snapshot("POST_KILL_t30") end
    if pf==90 then snapshot("POST_KILL_t90"); ph="watch"; pf=0 end
    return
  end

  if ph=="watch" then
    emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF)
    pf=pf+1
    local d=emu:read8(0xD880)
    if d~=last_d880 then
      log(string.format("D880 TRANSITION f=%d : 0x%02X -> 0x%02X (FFC1=%d FFBA=%d)",
        f, last_d880 or -1, d, emu:read8(0xFFC1), emu:read8(0xFFBA)))
      last_d880=d
    end
    if pf==60 then snapshot("WATCH_t60") end
    if pf==180 then snapshot("WATCH_t180"); log("DONE"); done=true end
    return
  end
end)
