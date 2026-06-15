-- riff-defeat cluster: attempt a REAL Riff defeat to confirm the post-defeat
-- scene byte sequence. Reach Riff (D880=0x0D), then drive the boss through its
-- damage phases by repeatedly clearing entity slots / advancing the event
-- sequence, and log EVERY D880 value seen until it leaves the arena. Also
-- snapshots DA00/attr histograms each time D880 changes.
local OUT="/tmp/riff-defeat/realkill.log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("riff-defeat real-kill trace\n");h:close() end end

local f=0; local ph="boot"; local fid=0; local pf=0; local done=false; local last=nil
local seen={}

local function da00hist()
  local hist={} for p=0,7 do hist[p]=0 end
  for i=0,255 do hist[(emu:read8(0xDA00+i))&7]=hist[(emu:read8(0xDA00+i))&7]+1 end
  local s="DA00:" for p=0,7 do s=s..string.format(" p%d=%d",p,hist[p]) end return s
end
local function attrhist()
  emu:write8(0xFF4F,1)
  local hist={} for p=0,7 do hist[p]=0 end
  for row=0,17 do for col=0,19 do hist[(emu:read8(0x9800+row*32+col))&7]=hist[(emu:read8(0x9800+row*32+col))&7]+1 end end
  emu:write8(0xFF4F,0)
  local s="ATTR:" for p=0,7 do s=s..string.format(" p%d=%d",p,hist[p]) end return s
end

local function note(tag)
  local d=emu:read8(0xD880)
  if d~=last then
    log(string.format("D880=0x%02X f=%d FFC1=%d FFBA=%d FFD3=0x%02X DCBB=0x%02X DF0D=0x%02X [%s]",
      d,f,emu:read8(0xFFC1),emu:read8(0xFFBA),emu:read8(0xFFD3),emu:read8(0xDCBB),emu:read8(0xDF0D),tag))
    log("  "..da00hist())
    log("  "..attrhist())
    last=d; seen[d]=(seen[d] or 0)+1
  end
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
      if emu:read8(0xD880)==0x0D then log("REACHED RIFF f="..f); ph="fight";pf=0; last=0x0D; seen[0x0D]=1
        log(string.format("D880=0x0D f=%d FFBA=%d (entry)",f,emu:read8(0xFFBA))); log("  "..da00hist()); log("  "..attrhist())
      elseif pf>500 then log("FAILED riff"); done=true end
    end
    return
  end
  if ph=="fight" then
    -- keep Sara alive; do NOT zero DCBB (that = death path 0x17). Instead try to
    -- legitimately end the fight: clear all entity slots (boss + minions) so the
    -- arena's "all cleared -> victory" check fires, and nudge the event seq.
    emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF)
    -- spam A (fire) to land weak-point hits in the held direction
    if (f%4)<2 then emu:setKeys(0x01) else emu:setKeys(0) end
    pf=pf+1
    -- Every 60 frames, try clearing boss entity slots DC85.. (5 slots x ? ) to
    -- simulate the boss being destroyed via the normal "slots empty" advance.
    if pf%60==0 then
      for s=0,0x7F do emu:write8(0xDC85+s,0) end  -- clear entity region
    end
    note("fight")
    local d=emu:read8(0xD880)
    if d~=0x0D and d~=0x18 then
      -- left the arena into some other scene; observe it for a while
      ph="observe"; pf=0
    end
    if pf>900 then log("no transition in 900f of fight; seen="..tostring(next(seen))); ph="observe"; pf=0 end
    return
  end
  if ph=="observe" then
    emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF)
    pf=pf+1
    note("observe")
    if pf>=240 then
      local s="SCENES SEEN:" for k,v in pairs(seen) do s=s..string.format(" 0x%02X(x%d)",k,v) end
      log(s); log("DONE"); done=true
    end
    return
  end
end)
