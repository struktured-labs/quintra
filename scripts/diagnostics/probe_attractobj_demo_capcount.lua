-- attract-obj cluster: during attract DEMO gameplay, count per-frame how many
-- visible OAM sprites at REAL slots >=10 carry a wrong palette vs their tile
-- range. Confirms the cap defect is steady in the attract demo (not transient).
local OUT = os.getenv("OUT") or "/tmp/attract-obj/capcount"
local f=0; local done=false; local logged=0
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("attract-obj demo cap-victim count\n");h:close() end end
local function expFromTile(tile)
  if tile==0 then return -2 end
  if tile<=0x01 then return 3 end
  if tile<=0x0F then return 0 end
  if tile<=0x1F then return 4 end
  if tile<=0x2F then return -1 end -- Sara: form-dependent, skip
  if tile<=0x3F then return 3 end
  if tile<=0x4F then return 4 end
  if tile<=0x5F then return 5 end
  if tile<=0x6F then return 6 end
  if tile<=0x7F then return 7 end
  return 4
end
callbacks:add("frame", function()
  if done then return end
  f=f+1; emu:setKeys(0)
  local d=emu:read8(0xD880); local ffc1=emu:read8(0xFFC1)
  if ffc1==1 and (d==0x02 or d==0x0A) then
    local visLo,visHi,wrongLo,wrongHi=0,0,0,0
    for s=0,39 do
      local y=emu:read8(0xFE00+s*4); local x=emu:read8(0xFE00+s*4+1)
      local tile=emu:read8(0xFE00+s*4+2); local pal=emu:read8(0xFE00+s*4+3)&0x07
      if y~=0 and y<160 and x~=0 and x<168 and tile~=0 then
        local exp=expFromTile(tile)
        if s<10 then visLo=visLo+1; if exp>=0 and pal~=exp then wrongLo=wrongLo+1 end
        else visHi=visHi+1; if exp>=0 and pal~=exp then wrongHi=wrongHi+1 end end
      end
    end
    if (visHi>0) and logged<25 then
      logged=logged+1
      log(string.format("f%d D880=%02X visLo=%d wrongLo=%d | visHi(>=10)=%d wrongHi=%d", f,d,visLo,wrongLo,visHi,wrongHi))
    end
  end
  if f>=11000 or logged>=25 then log("DONE"); done=true end
end)
