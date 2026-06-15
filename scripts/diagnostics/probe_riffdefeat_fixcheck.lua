-- riff-defeat FIX VALIDATION: at the forced 0x16 post-boss-reload scene, simulate
-- the proposed fix (scene_detect loads the all-pal0 SPLASH table for 0x16) by
-- writing 0x00 to all 256 entries of WRAM 0xDA00, then let the inline hook +
-- bg_sweep re-apply for ~30 frames and confirm the BG attr plane goes uniform
-- pal0 (no red). Compares against the unpatched (dungeon-table) baseline.
local OUT="/tmp/riff-defeat/fixcheck.log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("0x16 fix validation\n");h:close() end end
local f=0; local ph="boot"; local fid=0; local pf=0; local done=false

local function attrhist(tag)
  emu:write8(0xFF4F,1)
  local hist={} for p=0,7 do hist[p]=0 end
  for row=0,17 do for col=0,19 do hist[(emu:read8(0x9800+row*32+col))&7]=hist[(emu:read8(0x9800+row*32+col))&7]+1 end end
  emu:write8(0xFF4F,0)
  local s="ATTR("..tag.."):" for p=0,7 do s=s..string.format(" p%d=%d",p,hist[p]) end
  log(s)
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
      if emu:read8(0xD880)==0x0D then ph="settle";pf=0
      elseif pf>500 then log("FAILED riff"); done=true end
    end
    return
  end
  if ph=="settle" then
    emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF); pf=pf+1
    if pf==40 then ph="baseline16";pf=0 end
    return
  end
  -- Baseline: force 0x16, let dungeon table apply (current buggy behavior)
  if ph=="baseline16" then
    emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF)
    emu:write8(0xD880,0x16); pf=pf+1
    if pf==40 then attrhist("BASELINE_0x16_dungeon_table"); ph="applyfix";pf=0 end
    return
  end
  -- Apply simulated fix: overwrite DA00 with all pal0 each frame (what the
  -- splash-table case would do). Keep D880=0x16. The inline hook/bg_sweep read
  -- DA00 -> attrs should converge to pal0.
  if ph=="applyfix" then
    emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF)
    emu:write8(0xD880,0x16)
    for i=0,255 do emu:write8(0xDA00+i,0) end
    pf=pf+1
    if pf==30 then attrhist("FIXED_0x16_pal0_table"); log("DONE"); done=true end
    return
  end
end)
