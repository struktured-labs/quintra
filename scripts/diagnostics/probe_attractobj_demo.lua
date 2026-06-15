-- attract-obj cluster: determine whether a DEMO-GAMEPLAY attract segment exists.
-- Cold boot, NO input, run very long. Track D880, FFC1, FFBA, FFBF, OAM sprite
-- count, and on any new D880 OR when OAM>0 with FFC1==0 dump:
--   OAM sprites (tile, attr, low3=OBJ palette), OBJ CRAM (all 8 palettes),
--   FFC1. Goal: confirm hypothesis that during attract sprites are NOT
--   colorized (FFC1=0) and keep stale/boot OBJ attrs -> black.
local OUT = os.getenv("OUT") or "/tmp/attract-obj/demo"
local f, prevd, prevffc1 = 0, -1, -1
local done = false
local maxOamSeen = 0
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("attract-obj demo map\n");h:close() end end
local function objp(p,c) local i=p*8+c*2; emu:write8(0xFF6A,i); local lo=emu:read8(0xFF6B); emu:write8(0xFF6A,i+1); local hi=emu:read8(0xFF6B); return (hi<<8)|lo end
local function bgp(p,c) local i=p*8+c*2; emu:write8(0xFF68,i); local lo=emu:read8(0xFF69); emu:write8(0xFF68,i+1); local hi=emu:read8(0xFF69); return (hi<<8)|lo end
local function oamInfo()
  local n=0
  local samples={}
  for s=0,39 do
    local y=emu:read8(0xFE00+s*4)
    local x=emu:read8(0xFE00+s*4+1)
    local tile=emu:read8(0xFE00+s*4+2)
    local attr=emu:read8(0xFE00+s*4+3)
    if y~=0 and y<160 and x~=0 and x<168 then
      n=n+1
      if #samples<10 then
        samples[#samples+1]=string.format("s%d[y%d x%d t%02X a%02X p%d]",s,y,x,tile,attr,attr&0x07)
      end
    end
  end
  return n, table.concat(samples," ")
end
local function dumpObjCram()
  local out={}
  for p=0,7 do
    out[#out+1]=string.format("o%d=%04X/%04X/%04X/%04X",p,objp(p,0),objp(p,1),objp(p,2),objp(p,3))
  end
  return table.concat(out," ")
end
callbacks:add("frame", function()
  if done then return end
  f = f + 1
  emu:setKeys(0)   -- pure attract: never press anything
  local d = emu:read8(0xD880)
  local ffc1 = emu:read8(0xFFC1)
  local n, samp = oamInfo()
  if n > maxOamSeen then maxOamSeen = n end
  if d ~= prevd or ffc1 ~= prevffc1 then
    emu:screenshot(string.format("%s_d%02X_ffc1%d_f%d.png", OUT, d, ffc1, f))
    log(string.format("=== f%d D880=%02X FFC1=%d FFBA=%02X FFBF=%02X LCDC=%02X OAM=%d",
      f, d, ffc1, emu:read8(0xFFBA), emu:read8(0xFFBF), emu:read8(0xFF40), n))
    log("    OAM: "..samp)
    log("    OBJ_CRAM: "..dumpObjCram())
    log(string.format("    BG_CRAM(c1): b0=%04X b1=%04X b2=%04X", bgp(0,1), bgp(1,1), bgp(2,1)))
    prevd = d
    prevffc1 = ffc1
  end
  -- periodic snapshot every 600 frames with OAM detail
  if f % 600 == 0 then
    log(string.format("--- t%d D880=%02X FFC1=%d OAM=%d maxOAM=%d", f, d, ffc1, n, maxOamSeen))
    log("    OAM: "..samp)
    log("    OBJ_CRAM: "..dumpObjCram())
  end
  if f >= 12000 then
    log(string.format("DONE maxOAM=%d", maxOamSeen))
    done = true
  end
end)
