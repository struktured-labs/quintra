-- title-banner: confirm whether red attrs at D880=0x1B are PERSISTENT (table-driven
-- via DA00) or TRANSIENT stale attrs. Sample the banner region every 30 frames
-- while D880==0x1B and report, per tile-id, the modal palette attr + DA00 value.
-- Also dump CRAM BG pal1 vs pal0 so we know what "red" / "p0" actually look like.
local OUT = os.getenv("OUT") or "/tmp/title-banner/persist"
local f = 0
local samples = 0
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("banner persistence probe\n");h:close() end end
local function bgp(p,c) local i=p*8+c*2; emu:write8(0xFF68,i); local lo=emu:read8(0xFF69); emu:write8(0xFF68,i+1); local hi=emu:read8(0xFF69); return (hi<<8)|lo end

-- accumulate over samples: tile_id -> pal -> count
local acc = {}
callbacks:add("frame", function()
  f = f + 1
  emu:setKeys(0)
  local d = emu:read8(0xD880)
  if d == 0x1B and f % 15 == 0 then
    samples = samples + 1
    local scx = emu:read8(0xFF43); local scy = emu:read8(0xFF42)
    local col0 = (scx >> 3) & 31; local row0 = (scy >> 3) & 31
    for vr=0,17 do
      local mr=(row0+vr)&31
      for vc=0,19 do
        local mc=(col0+vc)&31
        local off=mr*32+mc
        emu:write8(0xFF4F,0); local tid=emu:read8(0x9800+off)
        emu:write8(0xFF4F,1); local pal=emu:read8(0x9800+off)&7
        acc[tid]=acc[tid] or {}; acc[tid][pal]=(acc[tid][pal] or 0)+1
      end
    end
    emu:write8(0xFF4F,0)
  end
  if (samples >= 40 and not _G.dumped) then
    _G.dumped = true
    log(string.format("samples=%d  (D880=0x1B banner, FFC1=%d)", samples, emu:read8(0xFFC1)))
    log("BG CRAM: pal0 c0-3 / pal1 c0-3")
    local s0=""; local s1=""
    for c=0,3 do s0=s0..string.format(" %04X",bgp(0,c)); s1=s1..string.format(" %04X",bgp(1,c)) end
    log("  pal0:"..s0); log("  pal1:"..s1)
    log("tile_id : modal_pal (counts)  DA00[tid]  PERSISTENT?")
    local ids={}; for t,_ in pairs(acc) do ids[#ids+1]=t end; table.sort(ids)
    for _,t in ipairs(ids) do
      local best=-1; local bestc=0; local parts=""
      for p=0,7 do if acc[t][p] then parts=parts..string.format(" p%d=%d",p,acc[t][p]); if acc[t][p]>bestc then bestc=acc[t][p]; best=p end end end
      local da=emu:read8(0xDA00+t)
      local tag = (da==best) and "table" or "MISMATCH(stale?)"
      log(string.format("  %02X : modal p%d  DA00=%d  [%s] %s", t, best, da, tag, parts))
    end
    log("DUMPED")
  end
  if f > 5200 then log("DONE_FRAMES") end
end)
