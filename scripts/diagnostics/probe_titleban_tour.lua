-- title-banner: tour the FULL 32x32 BG map at D880=0x1B (not just the visible
-- window) to enumerate EVERY tile-id that the banner uses (letters, showcase
-- monster-name, JAM logo) and the palette the dungeon table assigns each. The
-- banner scrolls so over time many distinct glyph rows pass through; dumping the
-- whole map captures off-screen content too. Sample a few times so scrolled-in
-- content (showcase/logo) is caught. Report union of tile-ids -> DA00 palette.
local OUT = os.getenv("OUT") or "/tmp/title-banner/tour"
local f = 0
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("banner full-map tour\n");h:close() end end
local seen = {}   -- tile_id -> count across all samples
local nsamp = 0
callbacks:add("frame", function()
  f = f + 1
  emu:setKeys(0)
  local d = emu:read8(0xD880)
  if d == 0x1B and f % 20 == 0 then
    nsamp = nsamp + 1
    -- whole 32x32 map (bank0 tile ids)
    emu:write8(0xFF4F, 0)
    for off = 0, 0x3FF do
      local tid = emu:read8(0x9800 + off)
      seen[tid] = (seen[tid] or 0) + 1
    end
  end
  if nsamp >= 60 and not _G.done then
    _G.done = true
    log(string.format("samples=%d", nsamp))
    log("ALL tile-ids present anywhere in BG map during 0x1B banner:")
    log("tile_id : total_cells  DA00[tid]")
    local ids={}; for t,_ in pairs(seen) do ids[#ids+1]=t end; table.sort(ids)
    for _,t in ipairs(ids) do
      local da = emu:read8(0xDA00 + t)
      log(string.format("  %02X : %6d  DA00=%d %s", t, seen[t], da, da==1 and "<-RED" or ""))
    end
    log("DUMPED")
  end
  if f > 5200 then log("DONE_FRAMES") end
end)
