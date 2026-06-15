-- probe_enemypal_cramtime.lua
-- Track OBJ+BG CRAM at multiple frames after loading a state, to see if
-- cond_pal (per-frame palette load) overwrites the save-state CRAM.
local STATE = os.getenv("PROBE_STATE")
local LABEL = os.getenv("PROBE_LABEL") or "?"
local OUT   = os.getenv("PROBE_OUT") or "/tmp/enemy-palettes/cramtime.txt"
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

local function snap(tag)
  local o0=obj_pal(0); local o4=obj_pal(4); local o5=obj_pal(5); local o6=obj_pal(6); local o7=obj_pal(7)
  local b0=bg_pal(0)
  w(string.format("%s f=%d FFC1=%02X | OBJ0 %04X %04X %04X %04X | OBJ4 %04X %04X %04X %04X | OBJ5 %04X %04X %04X %04X | OBJ6 %04X %04X %04X %04X | OBJ7 %04X %04X %04X %04X | BG0 %04X %04X %04X %04X",
    tag, frame, emu:read8(0xFFC1),
    o0[0],o0[1],o0[2],o0[3], o4[0],o4[1],o4[2],o4[3], o5[0],o5[1],o5[2],o5[3],
    o6[0],o6[1],o6[2],o6[3], o7[0],o7[1],o7[2],o7[3], b0[0],b0[1],b0[2],b0[3]))
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
    if frame==3 then w("==== "..LABEL.." ===="); snap("just_loaded") end
    if frame==10 then snap("f10") end
    if frame==30 then snap("f30") end
    if frame==80 then snap("f80") end
    if frame==150 then snap("f150"); w(""); done=true end
  end
end)
