-- probe_enemypal_forcepal.lua
-- The cond_pal hash cache (DF00) makes the per-frame palette load SKIP when
-- the save-state hash matches, leaving STALE save-state CRAM. To see what the
-- CURRENT teleport ROM actually loads, we invalidate the cache each frame:
--   DF00 = 0xFF (impossible hash) and DF02 = 0x5A (already-initialized).
-- This forces palette_loader to run every frame and rewrite CRAM from
-- bank13:0x6840. Then dump OBJ+BG CRAM and OAM sprites.
local STATE = os.getenv("PROBE_STATE")
local LABEL = os.getenv("PROBE_LABEL") or "?"
local OUT   = os.getenv("PROBE_OUT") or "/tmp/enemy-palettes/forcepal.txt"
local fh = io.open(OUT, "a")
local frame = 0
local loaded = false
local done = false
local function w(s) fh:write(s.."\n"); fh:flush() end

local function obj_pal(p)
  local r={}
  for c=0,3 do
    local idx=p*8+c*2
    emu:write8(0xFF6A, idx); local lo=emu:read8(0xFF6B)
    emu:write8(0xFF6A, idx+1); local hi=emu:read8(0xFF6B)
    r[c]=lo+hi*256
  end
  return r
end
local function bg_pal(p)
  local r={}
  for c=0,3 do
    local idx=p*8+c*2
    emu:write8(0xFF68, idx); local lo=emu:read8(0xFF69)
    emu:write8(0xFF68, idx+1); local hi=emu:read8(0xFF69)
    r[c]=lo+hi*256
  end
  return r
end

local function dump()
  w("==== STATE: "..LABEL.." (cache forced) ====")
  w(string.format("ctx: D880=%02X FFC1=%02X FFBE=%02X FFBF=%02X FFBA=%02X DCB8=%02X",
    emu:read8(0xD880),emu:read8(0xFFC1),emu:read8(0xFFBE),emu:read8(0xFFBF),
    emu:read8(0xFFBA),emu:read8(0xDCB8)))
  for p=0,7 do
    local o=obj_pal(p)
    w(string.format("OBJpal %d: %04X %04X %04X %04X",p,o[0],o[1],o[2],o[3]))
  end
  for p=0,7 do
    local b=bg_pal(p)
    w(string.format("BGpal  %d: %04X %04X %04X %04X",p,b[0],b[1],b[2],b[3]))
  end
  w("OAM:")
  for s=0,39 do
    local base=0xFE00+s*4
    local y=emu:read8(base); local x=emu:read8(base+1)
    local tile=emu:read8(base+2); local attr=emu:read8(base+3)
    if y~=0 and y<168 and x~=0 and x<176 then
      w(string.format("  slot %02d: y=%3d x=%3d tile=%02X attr=%02X pal=%d",
        s,y,x,tile,attr,attr&0x07))
    end
  end
  w("")
end

callbacks:add("frame", function()
  if done then return end
  frame=frame+1
  if not loaded and frame==2 then
    if STATE and STATE~="" then emu:loadStateFile(STATE) end
    loaded=true
    return
  end
  if loaded then
    -- invalidate palette cache each frame so palette_loader re-runs
    emu:write8(0xDF00, 0xFF)   -- impossible hash → CP B never equal → no RET Z
    emu:write8(0xDF02, 0x5A)   -- mark initialized so it uses the hash path
    if frame==150 then dump(); done=true end
  end
end)
