-- KEY: showcase
-- TITLE MONSTER SHOWCASE time-series probe (D880=0x1B animated banner).
-- Cold boot, NO input, run >5000 frames. The banner cycles monster names
-- (SARA W, HORSEFLY, ...). GOAL: determine (a) WHERE the showcase region is,
-- (b) whether a monster SPRITE/art is drawn or only name text, and (c) whether
-- the cycled monsters use DISTINCT tile IDs (=> a per-scene table could color
-- each) or the SAME tiles redrawn (=> a table cannot differentiate).
--
-- Method: while D880==0x1B, every 4 frames read the visible 20x18 window
-- (BG map per LCDC bit3, applying SCX/SCY). Compute a per-row content hash of
-- the NON-zero/non-fill tile IDs. When the set of (row-hashes) changes vs the
-- last logged frame, that's a new "showcase state": log the full visible tile
-- grid (ids + palettes), the union of tile IDs present (excluding the dominant
-- fill tiles 0x28 and 0xDF found earlier), and a screenshot. Also keep a global
-- per-tile-id frame-presence histogram so we can see which IDs are stable.
local OUT = os.getenv("OUT") or "/tmp/showcase/sc"
local f = 0
local last_sig = nil
local nstates = 0
local global_seen = {}   -- tile_id -> count of frames present (sampled)
local samples = 0
local first1b = nil
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("showcase time-series\n");h:close() end end

local function rd_vbk(bank, addr)
  emu:write8(0xFF4F, bank)
  return emu:read8(addr)
end

-- fill tiles that dominate the banner background (from prior tour): 0x00,0x28,0xDF
local FILL = {[0x00]=true, [0x28]=true, [0xDF]=true}

local function snapshot()
  local scx = emu:read8(0xFF43)
  local scy = emu:read8(0xFF42)
  local lcdc = emu:read8(0xFF40)
  local mapbase = (lcdc & 0x08) ~= 0 and 0x9C00 or 0x9800
  local col0 = (scx >> 3) & 31
  local row0 = (scy >> 3) & 31
  -- read both banks for the visible 18x20 window
  local ids = {}    -- ids[vr][vc]
  local pals = {}
  for vr = 0, 17 do
    ids[vr] = {}; pals[vr] = {}
    local mr = (row0 + vr) & 31
    for vc = 0, 19 do
      local mc = (col0 + vc) & 31
      local off = mr * 32 + mc
      ids[vr][vc]  = rd_vbk(0, mapbase + off)
      pals[vr][vc] = rd_vbk(1, mapbase + off) & 0x07
    end
  end
  emu:write8(0xFF4F, 0)
  return ids, pals, scx, scy, lcdc, mapbase
end

-- signature = concatenation of per-row "fingerprint" using only non-fill ids
local function row_sig(idrow)
  local s = ""
  for vc = 0, 19 do
    local t = idrow[vc]
    if not FILL[t] then s = s .. string.format("%02X", t) else s = s .. ".." end
  end
  return s
end

local function full_sig(ids)
  local parts = {}
  for vr = 0, 17 do parts[#parts+1] = row_sig(ids[vr]) end
  return table.concat(parts, "|")
end

callbacks:add("frame", function()
  f = f + 1
  emu:setKeys(0)
  local d = emu:read8(0xD880)
  if d ~= 0x1B then
    if f % 500 == 0 then log(string.format("f%d D880=%02X FFC1=%d (waiting for 0x1B)", f, d, emu:read8(0xFFC1))) end
    if f > 6500 and not _G.done then _G.done=true; log("NEVER_REACHED_1B"); log("DONE") end
    return
  end
  if not first1b then first1b = f; log(string.format("FIRST 0x1B at f=%d FFC1=%d", f, emu:read8(0xFFC1))) end

  if f % 4 ~= 0 then return end
  local ids, pals, scx, scy, lcdc, mapbase = snapshot()

  -- global per-tile presence histogram (count distinct tile ids per sampled frame)
  samples = samples + 1
  local present = {}
  for vr=0,17 do for vc=0,19 do present[ids[vr][vc]] = true end end
  for t,_ in pairs(present) do global_seen[t] = (global_seen[t] or 0) + 1 end

  local sig = full_sig(ids)
  if sig ~= last_sig then
    last_sig = sig
    nstates = nstates + 1
    log(string.format("=== STATE #%d  f=%d  D880=1B  SCX=%d SCY=%d LCDC=%02X mapbase=%04X",
        nstates, f, scx, scy, lcdc, mapbase))
    -- dump only rows that contain at least one non-fill tile (the content rows)
    for vr = 0, 17 do
      local has = false
      for vc=0,19 do if not FILL[ids[vr][vc]] then has=true; break end end
      if has then
        local idline = string.format("R%02d ID :", vr)
        local plline = string.format("R%02d PAL:", vr)
        for vc = 0, 19 do
          idline = idline .. string.format(" %02X", ids[vr][vc])
          plline = plline .. string.format("  %d", pals[vr][vc])
        end
        log(idline)
        log(plline)
      end
    end
    -- union of non-fill ids this state
    local u = {}
    for vr=0,17 do for vc=0,19 do local t=ids[vr][vc]; if not FILL[t] then u[t]=(u[t] or 0)+1 end end end
    local us={}; for t,_ in pairs(u) do us[#us+1]=t end; table.sort(us)
    local line = "  non-fill IDs:"
    for _,t in ipairs(us) do line = line .. string.format(" %02X(%d)", t, u[t]) end
    log(line)
    emu:screenshot(string.format("%s_state%02d_f%d.png", OUT, nstates, f))
  end

  -- periodic heartbeat
  if f % 200 == 0 then log(string.format("...heartbeat f%d states=%d samples=%d", f, nstates, samples)) end

  if f > 6500 and not _G.done then
    _G.done = true
    log(string.format("TOTAL states=%d samples=%d (first1b=%s)", nstates, samples, tostring(first1b)))
    log("global per-tile frame-presence (sampled frames; FILL excluded from interest):")
    local ids2={}; for t,_ in pairs(global_seen) do ids2[#ids2+1]=t end; table.sort(ids2)
    for _,t in ipairs(ids2) do
      local da = emu:read8(0xDA00 + t)
      log(string.format("  %02X : present_in %d/%d sampled frames  DA00=%d %s",
          t, global_seen[t], samples, da, FILL[t] and "<FILL>" or ""))
    end
    log("DONE")
  end
end)
