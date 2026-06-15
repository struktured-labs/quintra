-- probe_enemypal_handleralive.lua
-- Is the colorize handler chain running at all in a gameplay save state?
-- Test 1: poison VRAM bank1 attrs (0x9800 region) -> if bg_sweep/inline hook
--   runs, attrs get rewritten by the BG colorizer.
-- Test 2: poison BG+OBJ CRAM -> see which (if any) get rewritten.
-- Also dump the cond_pal cache bytes DF00/DF02 to understand cache state.
local STATE = os.getenv("PROBE_STATE")
local LABEL = os.getenv("PROBE_LABEL") or "?"
local OUT   = os.getenv("PROBE_OUT") or "/tmp/enemy-palettes/alive.txt"
local fh = io.open(OUT, "a")
local frame = 0
local loaded = false
local done = false
local function w(s) fh:write(s.."\n"); fh:flush() end

local function read_vram_attr(addr)
  emu:write8(0xFF4F, 1)        -- VBK = 1 (attr bank)
  local v = emu:read8(addr)
  emu:write8(0xFF4F, 0)
  return v
end
local function write_vram_attr(addr, val)
  emu:write8(0xFF4F, 1)
  emu:write8(addr, val)
  emu:write8(0xFF4F, 0)
end
local function read_vram_tile(addr)
  emu:write8(0xFF4F, 0)
  return emu:read8(addr)
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
    if frame==30 then
      w("==== "..LABEL.." ====")
      w(string.format("DF00=%02X DF02=%02X DF0A=%02X FFC1=%02X D880=%02X",
        emu:read8(0xDF00),emu:read8(0xDF02),emu:read8(0xDF0A),
        emu:read8(0xFFC1),emu:read8(0xD880)))
      -- sample some VRAM tiles + attrs in the 0x9800 tilemap (visible rows)
      w("Pre-poison VRAM (tile@bank0 / attr@bank1) at 0x9904..0x990F:")
      for c=4,11 do
        local a=0x9900+c
        w(string.format("  [%04X] tile=%02X attr=%02X", a, read_vram_tile(a), read_vram_attr(a)))
      end
      -- poison the attrs to 0x07 (palette 7) to detect overwrite
      for c=4,11 do write_vram_attr(0x9900+c, 0x07) end
      w("(poisoned attrs at 0x9904..0x990B to 0x07)")
    end
    if frame==40 then
      w("Post-frames VRAM attrs at 0x9904..0x990F (did BG colorizer rewrite?):")
      for c=4,11 do
        local a=0x9900+c
        w(string.format("  [%04X] tile=%02X attr=%02X", a, read_vram_tile(a), read_vram_attr(a)))
      end
      w("")
      done=true
    end
  end
end)
