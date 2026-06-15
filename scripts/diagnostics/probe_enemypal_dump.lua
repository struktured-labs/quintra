-- probe_enemypal_dump.lua
-- enemy-palettes cluster: load a save state, run ~120 frames so the OBJ
-- colorizer applies, then dump every visible OAM sprite:
--   slot, y, x, tile_id, attr, OBJ palette index (attr low 3 bits)
-- plus the 8 OBJ CRAM palettes (4 colors each, BGR555).
-- State path + label passed via env vars PROBE_STATE and PROBE_LABEL.

local STATE = os.getenv("PROBE_STATE")
local LABEL = os.getenv("PROBE_LABEL") or "?"
local OUT   = os.getenv("PROBE_OUT") or "/tmp/enemy-palettes/dump.txt"

local fh = io.open(OUT, "a")
local frame = 0
local loaded = false
local done = false

local function w(s) fh:write(s .. "\n"); fh:flush() end

local function read_obj_cram()
  -- returns table[pal][color] = 16-bit BGR555
  local pals = {}
  for p = 0, 7 do
    pals[p] = {}
    for c = 0, 3 do
      local idx = p * 8 + c * 2
      emu:write8(0xFF6A, idx)       -- set OBJ CRAM index (no auto-inc)
      local lo = emu:read8(0xFF6B)
      emu:write8(0xFF6A, idx + 1)
      local hi = emu:read8(0xFF6B)
      pals[p][c] = lo + hi * 256
    end
  end
  return pals
end

local function read_bg_cram()
  local pals = {}
  for p = 0, 7 do
    pals[p] = {}
    for c = 0, 3 do
      local idx = p * 8 + c * 2
      emu:write8(0xFF68, idx)
      local lo = emu:read8(0xFF69)
      emu:write8(0xFF68, idx + 1)
      local hi = emu:read8(0xFF69)
      pals[p][c] = lo + hi * 256
    end
  end
  return pals
end

local function dump()
  w("==== STATE: " .. LABEL .. " ====")
  -- game-state context
  local d880 = emu:read8(0xD880)
  local ffc1 = emu:read8(0xFFC1)
  local ffbe = emu:read8(0xFFBE)
  local ffbf = emu:read8(0xFFBF)
  local ffba = emu:read8(0xFFBA)
  local dcb8 = emu:read8(0xDCB8)
  w(string.format("ctx: D880=%02X FFC1=%02X FFBE=%02X FFBF=%02X FFBA=%02X DCB8=%02X",
    d880, ffc1, ffbe, ffbf, ffba, dcb8))

  -- OBJ palettes
  local op = read_obj_cram()
  for p = 0, 7 do
    w(string.format("OBJpal %d: %04X %04X %04X %04X", p,
      op[p][0], op[p][1], op[p][2], op[p][3]))
  end
  -- BG palettes (for reference / contrast)
  local bp = read_bg_cram()
  for p = 0, 7 do
    w(string.format("BGpal  %d: %04X %04X %04X %04X", p,
      bp[p][0], bp[p][1], bp[p][2], bp[p][3]))
  end

  -- OAM sprites (40 entries, hardware OAM at 0xFE00)
  w("OAM (visible sprites: y!=0 and y<160+16 region, tile listed):")
  local tilecount = {}  -- tile_id -> count for histogram
  for s = 0, 39 do
    local base = 0xFE00 + s * 4
    local y = emu:read8(base)
    local x = emu:read8(base + 1)
    local tile = emu:read8(base + 2)
    local attr = emu:read8(base + 3)
    local pal = attr & 0x07
    -- a sprite is on-screen-ish if y between 1 and 167 and x between 1 and 175
    if y ~= 0 and y < 168 and x ~= 0 and x < 176 then
      w(string.format("  slot %02d: y=%3d x=%3d tile=%02X attr=%02X pal=%d",
        s, y, x, tile, attr, pal))
      tilecount[tile] = (tilecount[tile] or 0) + 1
    end
  end
  w("")
end

callbacks:add("frame", function()
  if done then return end
  frame = frame + 1
  if not loaded and frame == 2 then
    if STATE and STATE ~= "" then
      emu:loadStateFile(STATE)
    end
    loaded = true
  end
  -- run ~140 frames after load so colorizer settles
  if loaded and frame == 150 then
    dump()
    done = true
  end
end)
