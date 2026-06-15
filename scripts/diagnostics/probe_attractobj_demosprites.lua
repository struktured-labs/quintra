-- attract-obj cluster: during the ATTRACT DEMO-GAMEPLAY (D880=0x02/0x0A, FFC1=1)
-- dump the FULL 40-slot OAM with tile/attr/palette so we can see which monster
-- sprites are uncolorized (palette p0 + stale attr) because the OBJ colorizer
-- only scans the first 10 OAM entries per buffer (LD B,0x0A). Also compute, for
-- each visible sprite, what palette the tile-range colorizer WOULD assign, and
-- flag mismatches. Trigger sampling once we reach demo gameplay.
local OUT = os.getenv("OUT") or "/tmp/attract-obj/demosprites"
local f = 0
local done = false
local samples = 0
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("attract-obj demo sprite full-OAM dump\n");h:close() end end
-- tile-range -> expected palette per docs/audit (0x00-01->3, 02-0F->0, 10-1F->4,
-- 20-2F->Sara(1 or 2), 30-3F->3, 40-4F->4, 50-5F->5, 60-6F->6, 70-7F->7, 80+->4)
local function expectedPal(tile, ffbe)
  if tile==0x00 then return -1 end -- skipped (invisible)
  if tile<=0x01 then return 3 end
  if tile<=0x0F then return 0 end
  if tile<=0x1F then return 4 end
  if tile<=0x2F then return (ffbe~=0) and 1 or 2 end
  if tile<=0x3F then return 3 end
  if tile<=0x4F then return 4 end
  if tile<=0x5F then return 5 end
  if tile<=0x6F then return 6 end
  if tile<=0x7F then return 7 end
  return 4
end
callbacks:add("frame", function()
  if done then return end
  f = f + 1
  emu:setKeys(0)
  local d = emu:read8(0xD880)
  local ffc1 = emu:read8(0xFFC1)
  -- Only sample once we are deep in demo gameplay with many sprites
  if ffc1==1 and (d==0x02 or d==0x0A) and samples < 6 then
    local n=0
    local rows={}
    local mism=0
    local ffbe = emu:read8(0xFFBE)
    for s=0,39 do
      local y=emu:read8(0xFE00+s*4); local x=emu:read8(0xFE00+s*4+1)
      local tile=emu:read8(0xFE00+s*4+2); local attr=emu:read8(0xFE00+s*4+3)
      if y~=0 and y<160 and x~=0 and x<168 then
        n=n+1
        local pal=attr&0x07
        local exp=expectedPal(tile,ffbe)
        local flag=""
        if exp>=0 and pal~=exp then flag="  <-- MISMATCH exp_p"..exp; mism=mism+1 end
        rows[#rows+1]=string.format("  slot%02d y%3d x%3d tile%02X attr%02X pal%d%s",s,y,x,tile,attr,pal,flag)
      end
    end
    if n >= 12 then  -- only log busy frames
      samples = samples + 1
      log(string.format("=== sample%d f%d D880=%02X FFC1=%d FFBE=%02X FFBF=%02X OAM=%d MISMATCH=%d",
        samples, f, d, ffc1, ffbe, emu:read8(0xFFBF), n, mism))
      for _,r in ipairs(rows) do log(r) end
    end
  end
  if f >= 11000 or samples >= 6 then log("DONE samples="..samples); done = true end
end)
