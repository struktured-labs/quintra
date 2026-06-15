-- probe_enemypal_poison.lua
-- Determine whether palette_loader actually writes OBJ CRAM at runtime.
-- Strategy: after loading a state, POISON all OBJ CRAM to 0x7FFF (white),
-- invalidate the cond_pal hash cache, run a frame, and re-read CRAM.
-- If palette_loader runs, CRAM should change back to the ROM 0x6840 values.
-- If CRAM stays poisoned -> palette_loader is NOT writing OBJ CRAM.
local STATE = os.getenv("PROBE_STATE")
local LABEL = os.getenv("PROBE_LABEL") or "?"
local OUT   = os.getenv("PROBE_OUT") or "/tmp/enemy-palettes/poison.txt"
local fh = io.open(OUT, "a")
local frame = 0
local loaded = false
local done = false
local poisoned = false
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

local function poison_obj()
  -- write 0x3DEF sentinel to ALL 64 OBJ CRAM bytes (8 palettes, auto-inc)
  emu:write8(0xFF6A, 0x80)  -- index 0, auto-increment
  for i=0,63 do emu:write8(0xFF6B, (i%2==0) and 0xEF or 0x3D) end
end
local function poison_bg()
  emu:write8(0xFF68, 0x80)
  for i=0,63 do emu:write8(0xFF69, (i%2==0) and 0xEF or 0x3D) end
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
    if frame==30 and not poisoned then
      poison_obj(); poison_bg()
      poisoned=true
      w("==== "..LABEL.." ====")
      local o4a=obj_pal(4); local b0a=bg_pal(0)
      w(string.format("after poison (f30): OBJ4 %04X %04X %04X %04X | BG0 %04X %04X %04X %04X",
        o4a[0],o4a[1],o4a[2],o4a[3], b0a[0],b0a[1],b0a[2],b0a[3]))
    end
    if poisoned and frame>=31 and frame<45 then
      -- invalidate cache EVERY frame so cond_pal must reload each VBlank
      emu:write8(0xDF00, 0xAA)
      emu:write8(0xDF02, 0x5A)
    end
    if frame==45 then
      -- read CRAM after several frames with cache invalidated
      for p=0,7 do
        local o=obj_pal(p)
        w(string.format("f45 OBJpal %d: %04X %04X %04X %04X",p,o[0],o[1],o[2],o[3]))
      end
      for p=0,7 do
        local b=bg_pal(p)
        w(string.format("f45 BGpal  %d: %04X %04X %04X %04X",p,b[0],b[1],b[2],b[3]))
      end
      w("")
      done=true
    end
  end
end)
