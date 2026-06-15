-- cameo_fire_pin.lua: fire the teleport combo (runs the natural boss-entry
-- handler 0x1A2B via the landing pad, which loads the Cameo arena VRAM), THEN
-- pin D880=0x0F + FFBA=3 + HP every frame so the dungeon main-loop can't revert
-- the scene. Then sample the (real arena) tilemap with mean-row accumulation.
local OUT=os.getenv("OUT") or "/tmp/cameo/cameo_band"
local STATE="save_states_for_claude/level1_sara_d_alone.ss0"
local TGT=0x0F
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("cameo fire+pin probe\n");h:close() end end

local f=0; local phase="load"; local sub; local pf=0; local done=false; local samples=0
local cnt={}; local rowsum={}; local rmin={}; local rmax={}; local rowset={}; local colset={}; local palhist={}

local function pin()
  emu:write8(0xFFBA,0x03)
  emu:write8(0xD880,TGT)
  emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF); emu:write8(0xDCBB,0x80)
end
local function sampleframe()
  local base=((emu:read8(0xFF40)&0x08)~=0) and 0x9C00 or 0x9800
  emu:write8(0xFF4F,0); local tiles={}
  for r=0,17 do tiles[r]={}; for c=0,19 do tiles[r][c]=emu:read8(base+r*32+c) end end
  emu:write8(0xFF4F,1); local attrs={}
  for r=0,17 do attrs[r]={}; for c=0,19 do attrs[r][c]=emu:read8(base+r*32+c)&7 end end
  emu:write8(0xFF4F,0)
  for r=0,17 do for c=0,19 do local t=tiles[r][c]
    if t~=0 then
      cnt[t]=(cnt[t] or 0)+1; rowsum[t]=(rowsum[t] or 0)+r
      if rmin[t]==nil or r<rmin[t] then rmin[t]=r end
      if rmax[t]==nil or r>rmax[t] then rmax[t]=r end
      rowset[t]=rowset[t] or {}; rowset[t][r]=true
      colset[t]=colset[t] or {}; colset[t][c]=true
      palhist[t]=palhist[t] or {}; local p=attrs[r][c]; palhist[t][p]=(palhist[t][p] or 0)+1
    end end end
  samples=samples+1
end
local function dumpresults()
  log(string.format("SAMPLES=%d D880=0x%02X FFBA=%d base=%s",samples,emu:read8(0xD880),emu:read8(0xFFBA),
    ((emu:read8(0xFF40)&0x08)~=0) and "9C00" or "9800"))
  local ids={}; for t,_ in pairs(cnt) do ids[#ids+1]=t end
  table.sort(ids,function(a,b) return (rowsum[a]/cnt[a])<(rowsum[b]/cnt[b]) end)
  log("tile  cnt  meanrow rmin rmax nrows ncols palhist")
  for _,t in ipairs(ids) do
    local nrows=0; for _ in pairs(rowset[t]) do nrows=nrows+1 end
    local ncols=0; for _ in pairs(colset[t]) do ncols=ncols+1 end
    local ph=""; for p=0,7 do if palhist[t][p] then ph=ph..string.format("p%d=%d ",p,palhist[t][p]) end end
    log(string.format("0x%02X  %4d  %5.2f  %3d  %3d  %4d  %4d  %s",t,cnt[t],rowsum[t]/cnt[t],rmin[t],rmax[t],nrows,ncols,ph))
  end
end

callbacks:add("frame",function()
  f=f+1
  if done then return end
  if phase=="load" then emu:loadStateFile(STATE); phase="settle"; pf=0; return end
  if phase=="settle" then emu:setKeys(0); pf=pf+1
    if pf>=25 then emu:write8(0xFFBA,2); emu:write8(0xDF0C,0); emu:write8(0xDF1D,0); emu:write8(0xDF1F,0)
      phase="tele"; sub="gap"; pf=0 end
    return end
  if phase=="tele" then
    if sub=="gap" then emu:setKeys(0); pf=pf+1; if pf>=4 then sub="pulse"; pf=0 end
    elseif sub=="pulse" then emu:setKeys(0x0C); pf=pf+1
      if pf>=8 then emu:setKeys(0); sub="wait"; pf=0
        log(string.format("fired f%d FFBA=%d D880=%02X",f,emu:read8(0xFFBA),emu:read8(0xD880))) end
    elseif sub=="wait" then
      -- give the landing pad / 0x1A2B a few frames to load arena VRAM, THEN pin
      emu:setKeys(0); pf=pf+1
      if pf>=20 then phase="pinhold"; pf=0
        log(string.format("post-1A2B f%d D880=%02X FFBA=%d",f,emu:read8(0xD880),emu:read8(0xFFBA))) end
    end
    return end
  if phase=="pinhold" then
    emu:setKeys(0); pin(); pf=pf+1
    if pf==1 or pf%60==0 then log(string.format("pin f%d D880=%02X FFBA=%d FFC1=%02X",f,emu:read8(0xD880),emu:read8(0xFFBA),emu:read8(0xFFC1))) end
    if pf>40 then sampleframe() end
    if pf%80==0 then emu:screenshot(string.format("%s_pin_f%d.png",OUT,f)) end
    if samples>=300 then emu:screenshot(OUT.."_final.png"); dumpresults(); log("DONE"); done=true end
    if pf>900 then dumpresults(); log("DONE-timeout"); done=true end
    return end
end)
