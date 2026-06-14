-- Map the ATTRACT MODE (title sequence): cold boot, NO input, let it run through
-- banner scroll -> settled title + monster showcase -> demo gameplay -> loop.
-- Log every D880 change with FFC1/FFBA + a screenshot, and periodically dump BG
-- and OBJ palette CRAM + a count of OAM sprites + dominant on-screen BG tiles,
-- so we know each scene's byte, palette state, and whether OBJ is colorized.
local OUT = os.getenv("OUT") or "/tmp/attract"
local f, prevd = 0, -1
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("attract map\n");h:close() end end
local function bgp(p,c) local i=p*8+c*2; emu:write8(0xFF68,i); local lo=emu:read8(0xFF69); emu:write8(0xFF68,i+1); local hi=emu:read8(0xFF69); return (hi<<8)|lo end
local function objp(p,c) local i=p*8+c*2; emu:write8(0xFF6A,i); local lo=emu:read8(0xFF6B); emu:write8(0xFF6A,i+1); local hi=emu:read8(0xFF6B); return (hi<<8)|lo end
local function oamCount() local n=0; for s=0,39 do local y=emu:read8(0xFE00+s*4); if y~=0 and y<160 then n=n+1 end end; return n end
callbacks:add("frame", function()
  f = f + 1
  emu:setKeys(0)   -- never press anything: pure attract mode
  local d = emu:read8(0xD880)
  if d ~= prevd then
    emu:screenshot(string.format("%s_d%02X_f%d.png", OUT, d, f))
    log(string.format("f%d D880=%02X FFC1=%d FFBA=%02X FFBF=%02X LCDC=%02X OAM=%d",
      f, d, emu:read8(0xFFC1), emu:read8(0xFFBA), emu:read8(0xFFBF), emu:read8(0xFF40), oamCount()))
    prevd = d
  end
  -- periodic full palette + screenshot snapshots
  if f % 200 == 0 then
    emu:screenshot(string.format("%s_t%d.png", OUT, f))
    local bg=""; for p=0,7 do bg=bg..string.format(" b%d=%04X",p,bgp(p,1)) end
    local ob=""; for p=0,7 do ob=ob..string.format(" o%d=%04X",p,objp(p,1)) end
    log(string.format("  t%d D880=%02X FFC1=%d OAM=%d", f, d, emu:read8(0xFFC1), oamCount()))
    log("    BGc1:"..bg)
    log("    OBJc1:"..ob)
  end
  if f > 3600 then log("DONE"); emu:stop() end
end)
