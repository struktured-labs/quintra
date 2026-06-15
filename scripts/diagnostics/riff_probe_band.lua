-- riff_probe_band.lua : reach Riff arena (D880=0x0D, FFBA idx 1) by BOOTING from
-- title (the proven reach in probe_arena_posmap_gen.lua — the teleport stack-
-- redirect only works from a real booted main-loop dungeon, NOT a loaded ss),
-- then sample the active tilemap accumulating per-tile-id count + sum-of-row +
-- column spread so we can compute mean-row and bucket body tiles into bands.
local TITLE={{180,185,0x80},{193,198,0x01},{241,246,0x01},{291,296,0x01},{341,346,0x08},{391,396,0x01}}
local OUT="/tmp/riff"
local TARGET=1                 -- Riff (idx 1)
local TGT=0x0C+TARGET          -- 0x0D
local f=0;local ph="boot";local sub;local pf=0;local fid=0;local at=0
local SETTLE=60;local COLLECT=280;local MAXTRY=24
local cnt={};local rowsum={};local colmask={};local samples=0
local reached_logged=false

local function log(m) local h=io.open(OUT.."/riff_probe.log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT.."/riff_probe.log","w"); if h then h:write("riff_band_probe (boot reach) start\n");h:close() end end
local function isar(d) return d>=0x0C and d<=0x14 end
local function base() local l=emu:read8(0xFF40); if (l&0x08)~=0 then return 0x9C00 else return 0x9800 end end

local function collect()
  local b=base(); emu:write8(0xFF4F,0)   -- bank 0 = tile ids
  for r=0,17 do for c=0,19 do
    local tid=emu:read8(b+r*32+c)
    if tid~=0 then
      cnt[tid]=(cnt[tid] or 0)+1
      rowsum[tid]=(rowsum[tid] or 0)+r
      colmask[tid]=colmask[tid] or {}
      colmask[tid][c]=true
    end
  end end
  samples=samples+1
end

local function emit()
  log(string.format("REACHED %s SAMPLES=%d D880=%02X",("riff"),samples,emu:read8(0xD880)))
  log("TILE count meanrow ncols mincol maxcol")
  local ids={}; for k,_ in pairs(cnt) do ids[#ids+1]=k end; table.sort(ids)
  for _,id in ipairs(ids) do
    local n=cnt[id]; local mr=rowsum[id]/n
    local nc=0; local mn=99; local mx=-1
    for col,_ in pairs(colmask[id]) do nc=nc+1; if col<mn then mn=col end; if col>mx then mx=col end end
    log(string.format("0x%02X %d %.2f %d %d %d",id,n,mr,nc,mn,mx))
  end
  emu:screenshot(OUT.."/riff_arena.png")
  log("DONE")
end

callbacks:add("frame",function()
 f=f+1
 if f<=500 then local k=0;for _,e in ipairs(TITLE) do if f>=e[1] and f<=e[2] then k=e[3];break end end;emu:setKeys(k);return end
 if ph=="boot" then emu:setKeys(0)
  if f%120==0 then log(string.format("boot f%d D880=%02X FFC1=%d FFBA=%02X fid=%d",f,emu:read8(0xD880),emu:read8(0xFFC1),emu:read8(0xFFBA),fid)) end
  if emu:read8(0xD880)==0x02 and emu:read8(0xFFC1)==1 then fid=fid+1; if fid>30 then ph="t";sub="pre";pf=0; log("dungeon reached f"..f) end end
  if f>2400 and ph=="boot" then log("BOOT FAIL D880="..string.format("%02X",emu:read8(0xD880)).." FFC1="..emu:read8(0xFFC1).." fid="..fid); ph="done" end
  return end
 if ph=="done" then return end
 if sub=="pre" then local pre=TARGET-1; if pre<0 then pre=8 end
  emu:write8(0xFFBA,pre);emu:write8(0xDF0C,0);emu:write8(0xDF1D,0);sub="pr";pf=0
 elseif sub=="pr" then emu:setKeys(0x0C);pf=pf+1;if pf>=10 then emu:setKeys(0);sub="rl";pf=0 end
 elseif sub=="rl" then emu:setKeys(0);pf=pf+1;if pf>=10 then sub="w";pf=0 end
 elseif sub=="w" then pf=pf+1;emu:write8(0xDCDC,0xFF);emu:write8(0xDCDD,0xFF)
  local dn=emu:read8(0xD880)
  if dn==TGT then sub="s";pf=0; if not reached_logged then log("REACHED RIFF D880="..string.format("%02X",TGT).." f"..f); reached_logged=true end
  elseif isar(dn) and dn~=TGT then
    -- overshot/undershot to another arena; re-pulse to cycle FFBA toward Riff
    if pf>120 then log(string.format("try%d f%d arena D880=%02X (not Riff) FFBA=%02X re-pulse",at,f,dn,emu:read8(0xFFBA))); at=at+1; if at>=MAXTRY then log("giveup riff");ph="done" else sub="pre" end end
  elseif pf>200 then log(string.format("try%d f%d D880=%02X FFBA=%02X timeout-wait",at,f,dn,emu:read8(0xFFBA))); at=at+1; if at>=MAXTRY then log("giveup riff");ph="done" else sub="pre" end end
 elseif sub=="s" then pf=pf+1;emu:write8(0xDCDC,0xFF);emu:write8(0xDCDD,0xFF)
  if not isar(emu:read8(0xD880)) then at=at+1; if at>=MAXTRY then ph="done" else sub="pre";pf=0 end
  elseif pf>=SETTLE then sub="c";pf=0 end
 elseif sub=="c" then emu:write8(0xDCDC,0xFF);emu:write8(0xDCDD,0xFF)
  if emu:read8(0xD880)==TGT then collect()
    if samples==1 or samples==COLLECT then emu:screenshot(string.format("%s/riff_s%d.png",OUT,samples)) end
    if samples>=COLLECT then emit();ph="done" end
  else if samples>30 then emit() end; ph="done" end
 end
end)
