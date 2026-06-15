-- general-bugs cluster: title menu + scene tracking probe.
-- Boots, lets the title sequence run, and at several frame checkpoints dumps:
--   D880, FFC1, FFBA, the 0x9800 tilemap (tile id + attr palette per cell),
--   and the BG CRAM (all 8 palettes). Detects per-tile attr "bleed" where the
--   same tile id resolves to >1 palette on screen.
local out = io.open("/tmp/general-bugs/title_dump.txt", "w")
local f = 0
local done = false
local checkpoints = {120, 200, 280, 360, 440, 520, 600, 700, 820, 960, 1100, 1300}
local ci = 1

local function readPal(which)  -- which: 0=BG (FF68/69), 1=OBJ (FF6A/6B)
  local idxreg = (which == 0) and 0xFF68 or 0xFF6A
  local datreg = (which == 0) and 0xFF69 or 0xFF6B
  local s = {}
  for p = 0, 7 do
    local cols = {}
    for c = 0, 3 do
      emu:write8(idxreg, (p*8 + c*2))
      local lo = emu:read8(datreg)
      emu:write8(idxreg, (p*8 + c*2 + 1))
      local hi = emu:read8(datreg)
      cols[#cols+1] = string.format("%02X%02X", hi, lo)
    end
    s[#s+1] = table.concat(cols, " ")
  end
  return s
end

local function dumpScene(tag)
  local d880 = emu:read8(0xD880)
  local ffc1 = emu:read8(0xFFC1)
  local ffba = emu:read8(0xFFBA)
  out:write(string.format("=== %s frame=%d D880=%02X FFC1=%02X FFBA=%02X ===\n",
    tag, f, d880, ffc1, ffba))

  -- read tilemap 0x9800: tile ids (bank0) and attrs (bank1)
  local tiles = {}
  local attrs = {}
  emu:write8(0xFF4F, 0)  -- VBK=0
  for i = 0, 32*32-1 do tiles[i] = emu:read8(0x9800 + i) end
  emu:write8(0xFF4F, 1)  -- VBK=1
  for i = 0, 32*32-1 do attrs[i] = emu:read8(0x9800 + i) end
  emu:write8(0xFF4F, 0)

  -- per-tile-id palette histogram across the visible 20x18 window
  local idpal = {}  -- idpal[tileid][pal] = count
  for r = 0, 17 do
    for col = 0, 19 do
      local i = r*32 + col
      local t = tiles[i]
      local p = attrs[i] & 0x07
      idpal[t] = idpal[t] or {}
      idpal[t][p] = (idpal[t][p] or 0) + 1
    end
  end
  -- report any tile id appearing with >1 distinct palette (= bleed/flicker source)
  local bleed = {}
  for t, pals in pairs(idpal) do
    local n = 0
    local plist = {}
    for p, c in pairs(pals) do n = n + 1; plist[#plist+1] = string.format("p%d:%d", p, c) end
    if n > 1 then
      table.sort(plist)
      bleed[#bleed+1] = string.format("tile %02X -> {%s}", t, table.concat(plist, ","))
    end
  end
  table.sort(bleed)
  if #bleed > 0 then
    out:write("  MULTI-PALETTE TILES (bleed/flicker source):\n")
    for _, b in ipairs(bleed) do out:write("    " .. b .. "\n") end
  else
    out:write("  (no multi-palette tiles in 20x18 window)\n")
  end

  -- BG palettes
  out:write("  BG CRAM:\n")
  for p, line in ipairs(readPal(0)) do
    out:write(string.format("    BG%d %s\n", p-1, line))
  end

  -- Also dump the visible tilemap palette grid (compact) for rows 0..17
  out:write("  ATTR-PAL GRID (rows0..17, cols0..19; digit=BG pal):\n")
  for r = 0, 17 do
    local row = {}
    for col = 0, 19 do
      row[#row+1] = tostring(attrs[r*32+col] & 0x07)
    end
    out:write("    " .. table.concat(row) .. "\n")
  end
  out:write("\n")
end

callbacks:add("frame", function()
  f = f + 1
  if done then return end
  -- advance through title splash to the menu: press START a couple of times
  if f == 300 or f == 360 then emu:setKeys(0x08) else emu:setKeys(0) end
  if ci <= #checkpoints and f == checkpoints[ci] then
    dumpScene("CHK")
    ci = ci + 1
  end
  if f >= 1320 then
    out:write("DONE\n")
    out:close()
    done = true
  end
end)
