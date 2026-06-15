-- miniboss cluster probe: load spider/gargoyle miniboss save state, run frames,
-- dump OAM (sprite tile/attr/palette), full BG tilemap tile IDs + attrs, and the
-- relevant 0xDA00 table around miniboss tile range. Determine BG vs OBJ.
-- Output: /tmp/miniboss/<tag>.log  (tag from env MB_TAG, state from MB_STATE)
local STATE = os.getenv("MB_STATE") or "save_states_for_claude/level1_sara_d_spider_miniboss.ss0"
local TAG   = os.getenv("MB_TAG") or "spider"
local OUT   = "/tmp/miniboss/"..TAG..".log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("miniboss dump tag="..TAG.." state="..STATE.."\n");h:close() end end

local f=0
local loaded=false
local done=false

local function vbk(n) emu:write8(0xFF4F, n) end
local function rd(a) return emu:read8(a) end

callbacks:add("frame", function()
  f=f+1
  if not loaded then
    local ok = emu:loadStateFile(STATE)
    log("loadStateFile -> "..tostring(ok))
    loaded=true
    return
  end
  -- let colorizer re-apply
  if f < 130 then return end
  if done then return end
  done=true

  -- state regs
  log(string.format("D880=%02X FFC1=%02X FFBA=%02X FFBF=%02X DCB8=%02X FFBE=%02X",
    rd(0xD880), rd(0xFFC1), rd(0xFFBA), rd(0xFFBF), rd(0xDCB8), rd(0xFFBE)))

  -- ===== OAM dump: 40 sprites, 4 bytes each =====
  log("=== OAM (idx: y x tile attr | objpal=attr&7 vbank=(attr&8)>>3) ===")
  local objtiles = {}
  for i=0,39 do
    local base = 0xFE00 + i*4
    local y = rd(base); local x = rd(base+1); local t = rd(base+2); local a = rd(base+3)
    if y ~= 0 or x ~= 0 or t ~= 0 then
      log(string.format("OAM%02d: y=%3d x=%3d tile=%02X attr=%02X objpal=%d xflip=%d yflip=%d pri=%d",
        i, y, x, t, a, a&7, (a&0x20)>>5, (a&0x40)>>6, (a&0x80)>>7))
      objtiles[t] = (objtiles[t] or 0) + 1
    end
  end
  log("OBJ tile histogram (tile=count):")
  local keys={}; for k,_ in pairs(objtiles) do keys[#keys+1]=k end; table.sort(keys)
  local s=""; for _,k in ipairs(keys) do s=s..string.format(" %02X=%d", k, objtiles[k]) end
  log(s)

  -- ===== BG tilemap tile IDs (bank0) and attrs (bank1) full 32x32 visible area =====
  -- We scan the visible window 20x18 starting at SCX/SCY-derived origin; but simplest:
  -- dump whole 0x9800 32x18 rows; flag non-floor tiles.
  log("=== BG tilemap rows 0..17, cols 0..19 (tile/attrpal) ===")
  for r=0,17 do
    vbk(0)
    local tline = string.format("R%02d T:", r)
    local aline = string.format("R%02d P:", r)
    for c=0,19 do
      vbk(0); local t = rd(0x9800 + r*32 + c)
      vbk(1); local a = rd(0x9800 + r*32 + c)
      tline = tline .. string.format(" %02X", t)
      aline = aline .. string.format("  %d", a&7)
    end
    log(tline)
    log(aline)
  end
  vbk(0)

  -- ===== 0xDA00 active table for high tiles 0x30-0xFF (miniboss BG tile candidates) =====
  log("=== 0xDA00 active BG table (tile -> pal) for 0x20-0xFF ===")
  for hi=0x2,0xF do
    local line = string.format("DA%X0:", hi)
    for lo=0,15 do
      line = line .. string.format(" %d", rd(0xDA00 + hi*16 + lo) & 7)
    end
    log(line)
  end
  log("DONE f="..f)
end)
