-- cameo_band_probe.lua
-- Reach Cameo arena (D880=0x0F, FFBA idx 3) from level1_sara_d_alone.ss0,
-- then sample the active tilemap for ~300 frames. For each NON-ZERO tile id,
-- accumulate count + sum-of-screen-row (0-17) so we can compute mean-row +
-- row band membership + per-tile palette histogram.
--
-- Reach mechanism (build_v301_teleport.py): the VBlank hook reads FF93 (raw
-- joypad, active-high bits 2,3 = SELECT+START = 0x0C), guarded D880>=0x02,
-- debounce DF0C. On fire it does FFBA=(FFBA+1)%9 then jumps to arena
-- D880=0x0C+FFBA. So to land on Cameo (FFBA=3) we PRE-SET FFBA=2 then pulse.
-- (template = crystal_meanrow_probe.lua, proven working)
local OUT = os.getenv("OUT") or "/tmp/cameo/cameo_band"
local STATE = os.getenv("STATE") or "save_states_for_claude/level1_sara_d_alone.ss0"
local TGT = 0x0F
local TARGET_FFBA = 3
local PRESET_FFBA = 2   -- so post-increment lands on 3 = Cameo
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("cameo band probe TGT=0x0F\n");h:close() end end

local f=0
local phase="load"
local sub
local pf=0
local attempts=0
local done=false
local samples=0

local cnt={}
local rowsum={}
local rmin={}
local rmax={}
local rowset={}
local colset={}
local palhist={}

local function isar(d) return d>=0x0C and d<=0x14 end

local function sampleframe()
  local base = ((emu:read8(0xFF40)&0x08)~=0) and 0x9C00 or 0x9800
  emu:write8(0xFF4F,0)
  local tiles={}
  for r=0,17 do tiles[r]={}; for c=0,19 do tiles[r][c]=emu:read8(base+r*32+c) end end
  emu:write8(0xFF4F,1)
  local attrs={}
  for r=0,17 do attrs[r]={}; for c=0,19 do attrs[r][c]=emu:read8(base+r*32+c)&7 end end
  emu:write8(0xFF4F,0)
  for r=0,17 do for c=0,19 do
    local t=tiles[r][c]
    if t~=0 then
      cnt[t]=(cnt[t] or 0)+1
      rowsum[t]=(rowsum[t] or 0)+r
      if rmin[t]==nil or r<rmin[t] then rmin[t]=r end
      if rmax[t]==nil or r>rmax[t] then rmax[t]=r end
      rowset[t]=rowset[t] or {}; rowset[t][r]=true
      colset[t]=colset[t] or {}; colset[t][c]=true
      palhist[t]=palhist[t] or {}; local p=attrs[r][c]; palhist[t][p]=(palhist[t][p] or 0)+1
    end
  end end
  samples=samples+1
end

local function dumpresults()
  log(string.format("SAMPLES=%d D880=0x%02X FFBA=%d base=%s",samples,emu:read8(0xD880),emu:read8(0xFFBA),
    ((emu:read8(0xFF40)&0x08)~=0) and "9C00" or "9800"))
  local ids={}
  for t,_ in pairs(cnt) do ids[#ids+1]=t end
  table.sort(ids,function(a,b)
    local ma=rowsum[a]/cnt[a]; local mb=rowsum[b]/cnt[b]; return ma<mb end)
  log("tile  cnt  meanrow rmin rmax nrows ncols palhist")
  for _,t in ipairs(ids) do
    local nrows=0; for _ in pairs(rowset[t]) do nrows=nrows+1 end
    local ncols=0; for _ in pairs(colset[t]) do ncols=ncols+1 end
    local mr=rowsum[t]/cnt[t]
    local ph=""
    for p=0,7 do if palhist[t][p] then ph=ph..string.format("p%d=%d ",p,palhist[t][p]) end end
    log(string.format("0x%02X  %4d  %5.2f  %3d  %3d  %4d  %4d  %s",t,cnt[t],mr,rmin[t],rmax[t],nrows,ncols,ph))
  end
end

callbacks:add("frame",function()
 f=f+1
 if done then return end
 if phase=="load" then
   emu:loadStateFile(STATE)
   log(string.format("loaded state f%d D880=0x%02X FFC1=%d FFBA=%d",f,emu:read8(0xD880),emu:read8(0xFFC1),emu:read8(0xFFBA)))
   phase="settle"; pf=0; return
 end
 if phase=="settle" then
   emu:setKeys(0); pf=pf+1
   if pf>=20 then
     log(string.format("settled f%d D880=0x%02X FFC1=%d",f,emu:read8(0xD880),emu:read8(0xFFC1)))
     phase="tele"; sub="pre"; pf=0
   end
   return
 end
 if phase=="tele" then
   if sub=="pre" then
     emu:write8(0xFFBA,PRESET_FFBA)
     emu:write8(0xDF0C,0); emu:write8(0xDF1D,0)
     emu:setKeys(0)
     sub="gap"; pf=0
   elseif sub=="gap" then
     emu:setKeys(0); pf=pf+1
     if pf>=3 then sub="pulse"; pf=0 end
   elseif sub=="pulse" then
     emu:write8(0xFFBA,PRESET_FFBA)
     emu:setKeys(0x0C); pf=pf+1
     if pf>=8 then emu:setKeys(0); sub="wait"; pf=0 end
   elseif sub=="wait" then
     pf=pf+1
     emu:setKeys(0)
     emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF)
     local d=emu:read8(0xD880)
     if d==TGT then
       log(string.format("REACHED target f%d D880=0x%02X FFBA=%d (attempt %d)",f,d,emu:read8(0xFFBA),attempts))
       phase="hold"; pf=0
     elseif isar(d) and d~=TGT then
       log(string.format("on arena 0x%02X (want 0x%02X) f%d FFBA=%d re-pulse",d,TGT,f,emu:read8(0xFFBA)))
       emu:write8(0xFFBA,(TARGET_FFBA-1+9)%9)
       phase="tele"; sub="pre"; pf=0
     elseif pf>200 then
       attempts=attempts+1
       log(string.format("retry attempt=%d f%d D880=0x%02X FFBA=%d FF93=0x%02X",attempts,f,d,emu:read8(0xFFBA),emu:read8(0xFF93)))
       if attempts>=12 then log("GIVEUP could not reach 0x0F"); dumpresults(); log("DONE"); done=true
       else sub="pre"; pf=0 end
     end
   end
   return
 end
 if phase=="hold" then
   pf=pf+1
   emu:setKeys(0)
   emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF)
   local d=emu:read8(0xD880)
   if not isar(d) then
     log(string.format("drift f%d D880=0x%02X re-pulse",f,d))
     emu:write8(0xFFBA,(TARGET_FFBA-1+9)%9)
     phase="tele"; sub="pre"; pf=0; return
   end
   if d~=TGT then
     log(string.format("drift-to-arena f%d D880=0x%02X re-pulse",f,d))
     emu:write8(0xFFBA,(TARGET_FFBA-1+9)%9)
     phase="tele"; sub="pre"; pf=0; return
   end
   if pf>30 then sampleframe() end
   if pf % 60 == 0 then emu:screenshot(string.format("%s_hold_f%d.png",OUT,f)) end
   if samples>=300 then
     emu:screenshot(OUT.."_final.png")
     dumpresults()
     log("DONE"); done=true
   end
 end
end)
