-- crystal_meanrow_probe.lua
-- Reach Crystal Dragon arena (D880=0x0E, FFBA idx 2). Run with mgba -t <dungeon
-- state> so D880=0x02 FFC1=1 at boot (same as probe_bossverify_checklist.lua).
-- Teleport via proven combo: pre-set FFBA=idx-1=1, pulse SELECT+START (0x0C),
-- wait D880=0x0E. Then sample active tilemap ~300 frames: per NON-ZERO tile id
-- accumulate count + sum-of-screen-row + row/col spread + attr-pal histogram.
local OUT = os.getenv("OUT") or "/tmp/crystal/crystal_meanrow"
local IDX = 2          -- Crystal Dragon
local TGT = 0x0C+IDX   -- 0x0E
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("crystal meanrow probe TGT=0x0E\n");h:close() end end

local f=0
local ph="boot"
local sub="pre"
local pf=0
local fid=0
local at=0
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
local function holdhp() emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF) end

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
  log(string.format("SAMPLES=%d D880=0x%02X base=%s",samples,emu:read8(0xD880),
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
    local ph2=""
    for p=0,7 do if palhist[t][p] then ph2=ph2..string.format("p%d=%d ",p,palhist[t][p]) end end
    log(string.format("0x%02X  %4d  %5.2f  %3d  %3d  %4d  %4d  %s",t,cnt[t],mr,rmin[t],rmax[t],nrows,ncols,ph2))
  end
end

callbacks:add("frame",function()
 f=f+1
 if f<=20 then return end
 if done then return end
 holdhp()
 if ph=="boot" then
   emu:setKeys(0)
   -- Clear landing-pad sentinel so the teleport routine RE-COPIES the landing
   -- pad from the freshly-built ROM (the -t save state was made on an older
   -- build; a stale DB00 pad makes the stack redirect a no-op).
   emu:write8(0xDF0E,0)
   if emu:read8(0xD880)==0x02 and emu:read8(0xFFC1)==1 then
     fid=fid+1
     if fid>20 then log(string.format("boot ok f%d D880=0x02 FFC1=1 DF0E=0x%02X",f,emu:read8(0xDF0E))); ph="cyc"; sub="pre"; pf=0 end
   end
   return
 end
 if ph=="cyc" then
   if sub=="pre" then
     local pre=IDX-1; if pre<0 then pre=8 end
     emu:write8(0xFFBA,pre); emu:write8(0xDF0C,0); emu:write8(0xDF1D,0)
     sub="pr"; pf=0
   elseif sub=="pr" then
     emu:setKeys(0x0C); pf=pf+1
     if pf>=10 then emu:setKeys(0); sub="rl"; pf=0 end
   elseif sub=="rl" then
     emu:setKeys(0); pf=pf+1
     if pf>=10 then sub="wa"; pf=0 end
   elseif sub=="wa" then
     pf=pf+1
     if emu:read8(0xD880)==TGT then
       log(string.format("REACHED f%d D880=0x%02X FFBA=%d (at=%d)",f,emu:read8(0xD880),emu:read8(0xFFBA),at))
       ph="hold"; pf=0
     elseif pf>400 then
       at=at+1
       log(string.format("retry at=%d f%d D880=0x%02X FFBA=%d FF93=0x%02X",at,f,emu:read8(0xD880),emu:read8(0xFFBA),emu:read8(0xFF93)))
       if at>=12 then log("GIVEUP"); dumpresults(); log("DONE"); done=true
       else sub="pre"; pf=0 end
     end
   end
   return
 end
 if ph=="hold" then
   pf=pf+1
   emu:setKeys(0)
   local d=emu:read8(0xD880)
   if d~=TGT then
     if isar(d) then
       log(string.format("drift-to-arena f%d D880=0x%02X re-pulse",f,d))
     else
       log(string.format("drift f%d D880=0x%02X re-pulse",f,d))
     end
     emu:write8(0xFFBA,IDX-1); ph="cyc"; sub="pre"; pf=0; return
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
