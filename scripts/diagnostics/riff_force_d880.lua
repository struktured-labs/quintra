-- riff_force_d880.lua : boot to dungeon, then DIRECTLY force D880=0x0D + FFBA=1
-- and CALL the arena-init path by setting scene state, to see if the game's
-- main-loop scene dispatcher renders the Riff arena tilemap. Probe-only attempt
-- to reach the arena without the (non-working) stack-redirect teleport.
local TITLE={{180,185,0x80},{193,198,0x01},{241,246,0x01},{291,296,0x01},{341,346,0x08},{391,396,0x01}}
local OUT="/tmp/riff"
local f=0;local ph="boot";local fid=0;local forced_at=nil
local cnt={};local rowsum={};local colmask={};local samples=0
local done=false
local function log(m) local h=io.open(OUT.."/force.log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT.."/force.log","w"); if h then h:write("riff_force_d880 start\n");h:close() end end
local function base() local l=emu:read8(0xFF40); if (l&0x08)~=0 then return 0x9C00 else return 0x9800 end end
local function collect()
  local b=base(); emu:write8(0xFF4F,0)
  for r=0,17 do for c=0,19 do
    local tid=emu:read8(b+r*32+c)
    if tid~=0 then cnt[tid]=(cnt[tid] or 0)+1; rowsum[tid]=(rowsum[tid] or 0)+r
      colmask[tid]=colmask[tid] or {}; colmask[tid][c]=true end
  end end
  samples=samples+1
end
local function emit()
  log("SAMPLES="..samples.." D880="..string.format("%02X",emu:read8(0xD880)))
  log("TILE count meanrow ncols mincol maxcol")
  local ids={}; for k,_ in pairs(cnt) do ids[#ids+1]=k end; table.sort(ids)
  for _,id in ipairs(ids) do local n=cnt[id]; local mr=rowsum[id]/n
    local nc=0;local mn=99;local mx=-1
    for col,_ in pairs(colmask[id]) do nc=nc+1; if col<mn then mn=col end; if col>mx then mx=col end end
    log(string.format("0x%02X %d %.2f %d %d %d",id,n,mr,nc,mn,mx)) end
  emu:screenshot(OUT.."/force_arena.png"); log("DONE")
end
callbacks:add("frame",function()
 if done then return end
 f=f+1
 if f<=500 then local k=0;for _,e in ipairs(TITLE) do if f>=e[1] and f<=e[2] then k=e[3];break end end;emu:setKeys(k);return end
 if ph=="boot" then emu:setKeys(0)
  if emu:read8(0xD880)==0x02 and emu:read8(0xFFC1)==1 then fid=fid+1; if fid>30 then ph="force"; log("dungeon f"..f) end end
  if f>1500 then log("BOOTFAIL"); done=true end
  return end
 if ph=="force" then
  -- set arena state directly
  emu:write8(0xFFBA,0x01)
  emu:write8(0xD880,0x0D)
  emu:write8(0xDCBB,0x80); emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF)
  forced_at=f; ph="watch"; log("forced D880=0D f"..f)
  return end
 if ph=="watch" then
  emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF)
  local d=emu:read8(0xD880)
  if (f-forced_at)%20==0 then log(string.format("f%d (+%d) D880=%02X FFBA=%02X FFC1=%d",f,f-forced_at,d,emu:read8(0xFFBA),emu:read8(0xFFC1))) end
  if (f-forced_at)>60 then ph="collect"; log("start collect D880="..string.format("%02X",d)) end
  return end
 if ph=="collect" then
  emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF)
  -- keep forcing D880 in case dispatcher resets it
  if emu:read8(0xD880)~=0x0D then emu:write8(0xD880,0x0D) end
  collect()
  if samples==1 then emu:screenshot(OUT.."/force_first.png") end
  if samples>=240 then emit(); done=true end
  if f>3000 then emit(); done=true end
 end
end)
