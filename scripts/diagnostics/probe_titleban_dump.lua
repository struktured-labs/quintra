-- title-banner cluster: dump the on-screen tilemap (tile IDs + BG palette attrs)
-- for the attract-mode scenes D880=0x1B (animated banner), 0x1C (logo-text menu),
-- 0x18 (stage splash), and 0x00/0x01 (title). Pure attract: NO input, cold boot.
-- For each target scene the FIRST time it is seen (and again ~30 frames later so
-- the colorizer has re-applied), dump:
--   - the 32x32 BG map region actually displayed (using SCX/SCY to find the
--     top-left tile), 20x18 visible cells: tile id (bank0) + attr low3 (palette)
--   - a histogram: for each (tile_id -> set of palettes assigned) so we can see
--     WHICH tile IDs got p1=red vs p0.
--   - the active 0xDA00[tile] table values for the tile IDs seen on-screen.
local OUT = os.getenv("OUT") or "/tmp/title-banner/ban"
local f = 0
local done = {}
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("title-banner tilemap dump\n");h:close() end end

local function rd_vbk(bank, addr)
  emu:write8(0xFF4F, bank)
  return emu:read8(addr)
end

local function dump_scene(d, tag)
  local scx = emu:read8(0xFF43)
  local scy = emu:read8(0xFF42)
  local lcdc = emu:read8(0xFF40)
  -- BG map base: bit3 of LCDC selects 0x9800 or 0x9C00
  local mapbase = (lcdc & 0x08) ~= 0 and 0x9C00 or 0x9800
  local col0 = (scx >> 3) & 31
  local row0 = (scy >> 3) & 31
  log(string.format("=== %s D880=%02X f=%d FFC1=%d SCX=%d SCY=%d LCDC=%02X mapbase=%04X col0=%d row0=%d",
    tag, d, f, emu:read8(0xFFC1), scx, scy, lcdc, mapbase, col0, row0))
  -- tile_id -> palette-set
  local seen = {}   -- key tile_id, value table of pal->count
  -- dump the 18 visible rows x 20 visible cols
  for vr = 0, 17 do
    local mr = (row0 + vr) & 31
    local idline = string.format("R%02d:", vr)
    local palline = "    "
    for vc = 0, 19 do
      local mc = (col0 + vc) & 31
      local off = mr * 32 + mc
      local tid = rd_vbk(0, mapbase + off)
      local attr = rd_vbk(1, mapbase + off)
      local pal = attr & 0x07
      idline = idline .. string.format(" %02X", tid)
      palline = palline .. string.format("  %d", pal)
      seen[tid] = seen[tid] or {}
      seen[tid][pal] = (seen[tid][pal] or 0) + 1
    end
    log(idline)
    log(palline)
  end
  emu:write8(0xFF4F, 0)
  -- histogram: tile_id -> palettes, plus active DA00 table value
  log("  -- tile_id histogram (tid: pal=count ...  DA00=table_val) --")
  local ids = {}
  for tid,_ in pairs(seen) do ids[#ids+1] = tid end
  table.sort(ids)
  for _,tid in ipairs(ids) do
    local parts = ""
    for p=0,7 do if seen[tid][p] then parts = parts .. string.format(" p%d=%d", p, seen[tid][p]) end end
    local da = emu:read8(0xDA00 + tid)
    log(string.format("    tid %02X:%s   DA00[%02X]=%d", tid, parts, tid, da))
  end
  emu:screenshot(string.format("%s_%s_d%02X_f%d.png", OUT, tag, d, f))
end

callbacks:add("frame", function()
  f = f + 1
  emu:setKeys(0)
  local d = emu:read8(0xD880)
  -- capture each target scene: first sight + a settled sight
  for _, tgt in ipairs({0x00, 0x01, 0x1C, 0x1B, 0x18}) do
    if d == tgt then
      if not done[tgt] then
        done[tgt] = f   -- record first frame; dump after 20 frames settle
      elseif type(done[tgt]) == "number" and (f - done[tgt]) >= 20 and done[tgt] ~= true then
        dump_scene(d, string.format("scene%02X", tgt))
        done[tgt] = true
      end
    end
  end
  if f % 400 == 0 then
    log(string.format("f%d D880=%02X FFC1=%d", f, d, emu:read8(0xFFC1)))
  end
  if f > 5200 then log("DONE_FRAMES"); end
end)
