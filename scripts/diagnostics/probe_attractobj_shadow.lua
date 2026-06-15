-- attract-obj cluster: read the SHADOW OAM buffers (0xC000 + 0xC100) that the
-- OBJ colorizer actually writes, alongside real OAM (0xFE00), to prove the
-- 10-entry scan cap leaves shadow slots 10-39 uncolorized. Dumps attr byte
-- (offset +3) for all 40 shadow entries in BOTH buffers + which buffer DMA
-- sourced. Run on a real multi-enemy state.
local OUT = os.getenv("OUT") or "/tmp/attract-obj/shadow"
local STATE = os.getenv("STATE")
local f=0; local done=false; local loaded=false; local sampled=false
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("attract-obj shadow OAM: "..tostring(STATE).."\n");h:close() end end
local function dumpBuf(base, label)
  local pals={}
  for s=0,39 do
    local tile=emu:read8(base+s*4+2); local attr=emu:read8(base+s*4+3)
    local y=emu:read8(base+s*4)
    if y~=0 and y<160 then
      pals[#pals+1]=string.format("s%02d(t%02X p%d)",s,tile,attr&0x07)
    end
  end
  log("  "..label.." visible: "..table.concat(pals," "))
end
callbacks:add("frame", function()
  if done then return end
  f=f+1; emu:setKeys(0)
  if not loaded and f==4 then emu:loadStateFile(STATE); loaded=true end
  if loaded and f>180 and not sampled then
    sampled=true
    log(string.format("D880=%02X FFC1=%d FFBE=%02X FFBF=%02X",
      emu:read8(0xD880), emu:read8(0xFFC1), emu:read8(0xFFBE), emu:read8(0xFFBF)))
    log("DMA reg FF46="..string.format("%02X", emu:read8(0xFF46)))
    dumpBuf(0xC000, "shadow0(C000)")
    dumpBuf(0xC100, "shadow1(C100)")
    dumpBuf(0xFE00, "realOAM(FE00)")
  end
  if f>=400 or sampled then log("DONE"); done=true end
end)
