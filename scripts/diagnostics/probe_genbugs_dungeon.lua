-- general-bugs: load a dungeon state, let colorizer settle, then over many frames
-- capture attr grid each frame and detect FLICKER (cells whose BG palette alternates
-- frame-to-frame on a STABLE tile id). Also dump CRAM + a representative attr grid.
-- STATE passed via env var GBSTATE; default level1_sara_d_alone.
local STATE = os.getenv("GBSTATE") or "save_states_for_claude/level1_sara_d_alone.ss0"
local TAG = os.getenv("GBTAG") or "dungeon"
local out = io.open("/tmp/general-bugs/dungeon_"..TAG..".txt", "w")
local f = 0
local done = false
local loaded = false
local settleFrame = nil
-- flicker tracking: for each cell, track (tileid, pal) history; if tileid stable but pal changes -> flicker
local hist = {}   -- hist[i] = {tile=, pals={pal->count}}
local samples = 0

local function readBGPal()
  local s = {}
  for p = 0, 7 do
    local cols = {}
    for c = 0, 3 do
      emu:write8(0xFF68, (p*8 + c*2)); local lo = emu:read8(0xFF69)
      emu:write8(0xFF68, (p*8 + c*2 + 1)); local hi = emu:read8(0xFF69)
      cols[#cols+1] = string.format("%02X%02X", hi, lo)
    end
    s[#s+1] = table.concat(cols, " ")
  end
  return s
end

-- detect which tilemap base the BG uses (LCDC bit3): 0x9800 or 0x9C00
local function bgBase()
  local lcdc = emu:read8(0xFF40)
  return (lcdc & 0x08) ~= 0 and 0x9C00 or 0x9800
end

local function dumpScene(tag)
  local base = bgBase()
  out:write(string.format("=== %s frame=%d D880=%02X FFC1=%02X FFBA=%02X base=%04X SCY=%02X SCX=%02X ===\n",
    tag, f, emu:read8(0xD880), emu:read8(0xFFC1), emu:read8(0xFFBA), base, emu:read8(0xFF42), emu:read8(0xFF43)))
  local tiles, attrs = {}, {}
  emu:write8(0xFF4F, 0); for r=0,17 do for col=0,19 do tiles[r*20+col]=emu:read8(base+r*32+col) end end
  emu:write8(0xFF4F, 1); for r=0,17 do for col=0,19 do attrs[r*20+col]=emu:read8(base+r*32+col)&0x07 end end
  emu:write8(0xFF4F, 0)
  -- per tile-id palette histogram
  local idpal={}
  for i=0,17*20+19 do local t=tiles[i]; local p=attrs[i]; idpal[t]=idpal[t] or {}; idpal[t][p]=(idpal[t][p] or 0)+1 end
  out:write("  TILE-ID -> palette(s):\n")
  local ids={}; for t in pairs(idpal) do ids[#ids+1]=t end; table.sort(ids)
  for _,t in ipairs(ids) do
    local pl={}; for p,c in pairs(idpal[t]) do pl[#pl+1]=string.format("p%d:%d",p,c) end; table.sort(pl)
    local mark = (#pl>1) and "  <-- MULTI" or ""
    out:write(string.format("    %02X -> %s%s\n", t, table.concat(pl,","), mark))
  end
  out:write("  BG CRAM:\n")
  for p,line in ipairs(readBGPal()) do out:write(string.format("    BG%d %s\n",p-1,line)) end
  out:write("  ATTR-PAL GRID:\n")
  for r=0,17 do local row={}; for col=0,19 do row[#row+1]=tostring(attrs[r*20+col]) end; out:write("    "..table.concat(row).."\n") end
  out:write("\n")
end

callbacks:add("frame", function()
  f = f + 1
  if done then return end
  if not loaded and f == 5 then emu:loadStateFile(STATE); loaded = true; return end
  if not loaded then return end
  if f == 130 then dumpScene("SETTLED"); settleFrame = f end
  -- flicker accumulation across frames 250..400 (no input, STEADY state;
  -- 250 leaves >100 frames for the post-load row-by-row convergence to finish)
  if f >= 250 and f <= 400 then
    local base = bgBase()
    samples = samples + 1
    emu:write8(0xFF4F, 0)
    local tiles = {}
    for r=0,17 do for col=0,19 do tiles[r*20+col]=emu:read8(base+r*32+col) end end
    emu:write8(0xFF4F, 1)
    for r=0,17 do for col=0,19 do
      local i=r*20+col
      local t=tiles[i]; local p=emu:read8(base+r*32+col)&0x07
      local h = hist[i]
      if not h then hist[i]={tile=t, pals={}} h=hist[i] end
      if h.tile ~= t then h.tile=t; h.pals={} end  -- tile changed (scroll); reset
      h.pals[p]=(h.pals[p] or 0)+1
    end end
    emu:write8(0xFF4F, 0)
  end
  if f == 405 then
    -- report flicker: cells where tile stable but >1 palette observed
    out:write(string.format("=== FLICKER REPORT (samples=%d, frames 140..400) ===\n", samples))
    local flick = {}
    for i,h in pairs(hist) do
      local np=0; local pl={}
      for p,c in pairs(h.pals) do np=np+1; pl[#pl+1]=string.format("p%d:%d",p,c) end
      if np>1 then table.sort(pl); flick[#flick+1]=string.format("  (%d,%d) tile=%02X pals={%s}", i//20, i%20, h.tile, table.concat(pl,",")) end
    end
    if #flick>0 then out:write("  FLICKERING CELLS:\n"); for _,l in ipairs(flick) do out:write(l.."\n") end
    else out:write("  (no flickering cells detected)\n") end
    out:write("\n")
    dumpScene("FINAL")
    out:write("DONE\n"); out:close(); done=true
  end
end)
