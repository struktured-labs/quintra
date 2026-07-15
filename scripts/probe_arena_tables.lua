-- v3 table generator: CORNER-BASED floor detection (robust).
-- Floor/background tiles the whole screen incl. corners; the boss is centered
-- and never fills all 4 corners. So: any tile ID seen at a screen corner
-- (0,0)(0,19)(17,0)(17,19) in >=25% of frames is floor → excluded. This
-- catches checkerboards using IDs >0x01 (Cameo/Troop) WITHOUT dropping a
-- boss's heavily-reused texture tiles (Faze) the way a frequency cap did.
-- Plus 0x00/0x01 always floor. Settle 90 after arena, HP hold, 180 frames.

local TITLE={{180,185,0x80},{193,198,0x01},{241,246,0x01},{291,296,0x01},{341,346,0x08},{391,396,0x01}}
local OUT="/tmp/tables_v3.log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("tables v3\n");h:close() end end

local B={
  {ffba=0,name="shalamar",d880=0x0C},{ffba=1,name="riff",d880=0x0D},
  {ffba=2,name="crystal_dragon",d880=0x0E},{ffba=3,name="cameo",d880=0x0F},
  {ffba=4,name="ted",d880=0x10},{ffba=5,name="troop",d880=0x11},
  {ffba=6,name="faze",d880=0x12},{ffba=7,name="angela",d880=0x13},
  {ffba=8,name="penta_dragon",d880=0x14},
}
local CORNERS={{0,0},{0,19},{17,0},{17,19}}

local f=0;local ph="boot";local i=1;local sub;local pf=0;local fid=0;local at=0
local sum={};local cnt={};local corner={};local frames=0
local COLLECT=180;local SETTLE=90;local MAXTRY=8

local function reset() sum={};cnt={};corner={};frames=0 end
local function isar(d) return d>=0x0C and d<=0x14 end
local function collect()
  emu:write8(0xFF4F,0)
  for r=0,17 do for c=0,19 do
    local t=emu:read8(0x9800+r*32+c)
    if t>0x01 then sum[t]=(sum[t] or 0)+r; cnt[t]=(cnt[t] or 0)+1 end
  end end
  for _,cc in ipairs(CORNERS) do
    local t=emu:read8(0x9800+cc[1]*32+cc[2])
    corner[t]=(corner[t] or 0)+1
  end
  frames=frames+1
end
local function emit(b)
  if frames<5 then log(b.name..": too few frames"); return end
  -- floor = tile at any corner in >=25% of frames
  local floor={}
  local cthresh=frames*0.25
  for t,c in pairs(corner) do if c>=cthresh then floor[t]=true end end
  local nfloor=0; for _ in pairs(floor) do nfloor=nfloor+1 end
  local kept={}; local lo,hi=99,-1; local dropped=0
  for t,c in pairs(cnt) do
    if floor[t] then dropped=dropped+1
    elseif c>=5 then local m=sum[t]/c; kept[t]=m; if m<lo then lo=m end; if m>hi then hi=m end end
  end
  if hi<lo then log(b.name..": NO BOSS TILES"); return end
  local span=hi-lo; if span<0.01 then span=0.01 end; local w=span/4
  local PAL={4,6,5,3};local tab={}
  for t,m in pairs(kept) do local q=math.floor((m-lo)/w); if q>3 then q=3 end; if q<0 then q=0 end; tab[t]=PAL[q+1] end
  local ids={};for t,_ in pairs(tab) do ids[#ids+1]=t end; table.sort(ids)
  local parts={};for _,t in ipairs(ids) do parts[#parts+1]=string.format("0x%02X:%d",t,tab[t]) end
  log(string.format("BOSS %s rows %.1f..%.1f tiles=%d corner_floor=%d frames=%d",b.name,lo,hi,#ids,nfloor,frames))
  log(string.format("PYDICT %s {%s}",b.name,table.concat(parts,", ")))
end

callbacks:add("frame",function()
 f=f+1
 if f<=500 then local k=0;for _,e in ipairs(TITLE) do if f>=e[1] and f<=e[2] then k=e[3];break end end;emu:setKeys(k);return end
 if ph=="boot" then emu:setKeys(0)
  if emu:read8(0xD880)==0x02 and emu:read8(0xFFC1)==1 then fid=fid+1; if fid>30 then ph="t";sub="pre";pf=0;log("dungeon") end end
  return end
 if ph=="t" then local b=B[i]
  if not b then log("ALL DONE");ph="done";return end
  if sub=="pre" then local pre=b.ffba-1; if pre<0 then pre=8 end; emu:write8(0xFFBA,pre);emu:write8(0xDF0C,0);emu:write8(0xDF1D,0);log(b.name.." pre="..pre.." try="..at);sub="pr";pf=0
  elseif sub=="pr" then emu:setKeys(0x0C);pf=pf+1;if pf>=10 then emu:setKeys(0);sub="rl";pf=0 end
  elseif sub=="rl" then emu:setKeys(0);pf=pf+1;if pf>=10 then sub="w";pf=0 end
  elseif sub=="w" then pf=pf+1;emu:write8(0xDCDC,0xFF);emu:write8(0xDCDD,0xFF)
   if emu:read8(0xD880)==b.d880 then log(b.name.." arena");sub="s";pf=0
   elseif pf>400 then at=at+1; if at>=MAXTRY then log(b.name.." giveup");i=i+1;sub="pre";at=0 else sub="pre" end end
  elseif sub=="s" then pf=pf+1;emu:write8(0xDCDC,0xFF);emu:write8(0xDCDD,0xFF)
   if not isar(emu:read8(0xD880)) then at=at+1; if at>=MAXTRY then i=i+1;sub="pre";at=0 else sub="pre";pf=0 end
   elseif pf>=SETTLE then sub="c";reset();pf=0 end
  elseif sub=="c" then emu:write8(0xDCDC,0xFF);emu:write8(0xDCDD,0xFF)
   if isar(emu:read8(0xD880)) then collect(); if frames>=COLLECT then emit(b);i=i+1;sub="pre";at=0;pf=0 end
   else if frames>30 then emit(b) end; i=i+1;sub="pre";at=0;pf=0 end
  end
 end
end)
