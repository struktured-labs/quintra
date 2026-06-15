-- riff-defeat: reach Riff, force D880=0x16, dump the actual on-screen tile-id
-- grid + which palette each maps to under the dungeon table vs the all-pal0
-- splash table, to confirm the post-boss-reload content + validate the fix
-- (loading the splash/pal0 table makes it uniform).
local OUT="/tmp/riff-defeat/tiles16.log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("0x16 tile dump\n");h:close() end end
local f=0; local ph="boot"; local fid=0; local pf=0; local done=false

local function dumpgrid(tag)
  emu:write8(0xFF4F,0)
  log("== tile-id grid ("..tag..") rows0-17 cols0-19 ==")
  -- collect unique tile ids and count in redband
  local uniq={}; local nred=0
  for row=0,17 do
    local s=string.format("r%02d:",row)
    for col=0,19 do
      local t=emu:read8(0x9800+row*32+col)
      s=s..string.format(" %02X",t)
      uniq[t]=(uniq[t] or 0)+1
      if t>=0x80 and t<=0xDF then nred=nred+1 end
    end
    log(s)
  end
  -- top unique tiles
  local arr={}
  for k,v in pairs(uniq) do arr[#arr+1]={k,v} end
  table.sort(arr,function(a,b) return a[2]>b[2] end)
  local s="top tiles:"
  for i=1,math.min(12,#arr) do s=s..string.format(" %02X(x%d)",arr[i][1],arr[i][2]) end
  log(s)
  log(string.format("redband(0x80-0xDF) cells = %d / 360", nred))
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
    if pf==40 then ph="force16";pf=0 end
    return
  end
  if ph=="force16" then
    emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF)
    emu:write8(0xD880,0x16); pf=pf+1
    if pf==60 then
      log(string.format("D880=0x%02X FFBA=%d (post-boss-reload forced)", emu:read8(0xD880), emu:read8(0xFFBA)))
      dumpgrid("0x16_post_reload")
      log("DONE"); done=true
    end
    return
  end
end)
