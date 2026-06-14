-- Pin down the menu-open wall flicker. On the CURRENT ROM: enter dungeon, open
-- SELECT menu, and each frame around the open log: 0xDA00[wall tile IDs], and the
-- live attr of the flicking right-edge wall cells (row7-13, col21). Screenshot
-- each frame so a zoomed wall-region filmstrip can be built.
local OUT = os.getenv("OUT") or "/tmp/wf"
local f = 0
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("wall flicker probe\n");h:close() end end
local function press(lo,hi,mask) return (f>=lo and f<hi) and mask or 0 end
callbacks:add("frame", function()
  f = f + 1
  local k = press(180,186,0x80)|press(193,199,0x01)|press(241,247,0x01)|press(291,297,0x01)|press(341,347,0x08)|press(391,397,0x01)
  k = k | press(1200,1206, 0x04)   -- SELECT opens item menu
  emu:setKeys(k)
  if f == 1100 then emu:screenshot(OUT.."_dungeon.png"); log("dungeon-ok shot f1100 D880="..string.format("%02X",emu:read8(0xD880))) end
  if f >= 1210 and f <= 1290 then
    local base = ((emu:read8(0xFF40)&0x08)~=0) and 0x9C00 or 0x9800
    -- DA00 wall-tile palette entries
    local da = string.format("DA00[25]=%d [35]=%d [3C]=%d [17]=%d [26]=%d",
      emu:read8(0xDA25), emu:read8(0xDA35), emu:read8(0xDA3C), emu:read8(0xDA17), emu:read8(0xDA26))
    -- live attr of the flicking cells (rows 7-13, col 21)
    emu:write8(0xFF4F,1); local a={}
    for r=7,13 do a[#a+1]=string.format("r%d=%d",r,emu:read8(base+r*32+21)&7) end
    emu:write8(0xFF4F,0)
    log(string.format("f%d %s  col21attr[%s]", f, da, table.concat(a," ")))
    emu:screenshot(string.format("%s_t%d.png", OUT, f))
  end
  if f > 1300 then log("DONE"); emu:stop() end
end)
