-- Map the FULL attract cycle incl. monster showcase + gameplay demo. NO premature
-- emu:stop() (it freezes the core in this build). Run until timeout. Log every
-- D880 change + every frame OAM sprite-count crosses 0<->nonzero, with screenshots
-- and OBJ/BG palette dumps, so we capture the showcase + demo scenes (where Sara/
-- monsters render). The demo is reached only after a long idle.
local OUT = os.getenv("OUT") or "/tmp/attract2"
local f, prevd, prevoam = 0, -1, -1
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("attract2 full cycle\n");h:close() end end
local function objp(p,c) local i=p*8+c*2; emu:write8(0xFF6A,i); local lo=emu:read8(0xFF6B); emu:write8(0xFF6A,i+1); local hi=emu:read8(0xFF6B); return (hi<<8)|lo end
local function oamCount() local n=0; for s=0,39 do local y=emu:read8(0xFE00+s*4); if y~=0 and y<160 then n=n+1 end end; return n end
callbacks:add("frame", function()
  f = f + 1
  emu:setKeys(0)
  local d, oam, ffc1 = emu:read8(0xD880), oamCount(), emu:read8(0xFFC1)
  local changed = false
  if d ~= prevd then
    log(string.format("f%d D880=%02X FFC1=%d OAM=%d FFBA=%02X", f, d, ffc1, oam, emu:read8(0xFFBA)))
    emu:screenshot(string.format("%s_d%02X_f%d.png", OUT, d, f))
    prevd = d; changed = true
  end
  -- detect OAM (sprites) appearing = showcase/demo
  local oamband = (oam==0) and 0 or 1
  if oamband ~= prevoam then
    log(string.format("f%d OAM->%d (count %d) D880=%02X FFC1=%d", f, oamband, oam, d, ffc1))
    if oamband==1 then
      emu:screenshot(string.format("%s_OAM_f%d_d%02X.png", OUT, f, d))
      -- dump OBJ palettes + first few sprites' tile+palette
      local ob=""; for p=0,7 do ob=ob..string.format(" o%d=%04X",p,objp(p,1)) end
      log("   OBJc1:"..ob)
      local s=""
      for sp=0,7 do local y=emu:read8(0xFE00+sp*4); local x=emu:read8(0xFE00+sp*4+1); local t=emu:read8(0xFE00+sp*4+2); local a=emu:read8(0xFE00+sp*4+3); if y~=0 and y<160 then s=s..string.format(" #%d(t%02X p%d)",sp,t,a&7) end end
      log("   sprites:"..s)
    end
    prevoam = oamband
  end
  -- periodic screenshot during demo (OAM active)
  if oam>0 and f%60==0 then emu:screenshot(string.format("%s_demo_f%d.png", OUT, f)) end
  -- no emu:stop(); rely on timeout
end)
