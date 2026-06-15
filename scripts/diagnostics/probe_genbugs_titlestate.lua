-- general-bugs: load title_screen.ss0, capture scene; then let it run / attract to
-- catch D880 0x1C (menu) and 0x1B (banner). Dump tilemap palette grid + bleed + CRAM
-- whenever D880 changes to a NEW value we haven't dumped.
local out = io.open("/tmp/general-bugs/titlestate_dump.txt", "w")
local f = 0
local done = false
local seen = {}
local loaded = false

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

local function dumpScene(tag)
  local d880 = emu:read8(0xD880)
  local ffc1 = emu:read8(0xFFC1)
  out:write(string.format("=== %s frame=%d D880=%02X FFC1=%02X ===\n", tag, f, d880, ffc1))
  local tiles, attrs = {}, {}
  emu:write8(0xFF4F, 0); for i=0,32*32-1 do tiles[i]=emu:read8(0x9800+i) end
  emu:write8(0xFF4F, 1); for i=0,32*32-1 do attrs[i]=emu:read8(0x9800+i) end
  emu:write8(0xFF4F, 0)
  local idpal = {}
  for r=0,17 do for col=0,19 do
    local i=r*32+col; local t=tiles[i]; local p=attrs[i]&0x07
    idpal[t]=idpal[t] or {}; idpal[t][p]=(idpal[t][p] or 0)+1
  end end
  local bleed={}
  for t,pals in pairs(idpal) do
    local n=0; local pl={}
    for p,c in pairs(pals) do n=n+1; pl[#pl+1]=string.format("p%d:%d",p,c) end
    if n>1 then table.sort(pl); bleed[#bleed+1]=string.format("tile %02X -> {%s}",t,table.concat(pl,",")) end
  end
  table.sort(bleed)
  if #bleed>0 then out:write("  MULTI-PALETTE TILES:\n"); for _,b in ipairs(bleed) do out:write("    "..b.."\n") end
  else out:write("  (no multi-palette tiles)\n") end
  -- which non-zero palettes are actually used on screen
  local palcount={}
  for r=0,17 do for col=0,19 do local p=attrs[r*32+col]&0x07; palcount[p]=(palcount[p] or 0)+1 end end
  local pc={}; for p=0,7 do if palcount[p] then pc[#pc+1]=string.format("p%d=%d",p,palcount[p]) end end
  out:write("  PAL USAGE: "..table.concat(pc," ").."\n")
  out:write("  BG CRAM:\n")
  for p,line in ipairs(readBGPal()) do out:write(string.format("    BG%d %s\n",p-1,line)) end
  out:write("  ATTR-PAL GRID rows0..17 cols0..19:\n")
  for r=0,17 do local row={}; for col=0,19 do row[#row+1]=tostring(attrs[r*32+col]&0x07) end; out:write("    "..table.concat(row).."\n") end
  -- also tile-id grid for context
  out:write("  TILE-ID GRID rows0..17 cols0..19:\n")
  for r=0,17 do local row={}; for col=0,19 do row[#row+1]=string.format("%02X",tiles[r*32+col]) end; out:write("    "..table.concat(row," ").."\n") end
  out:write("\n")
end

callbacks:add("frame", function()
  f = f + 1
  if done then return end
  if not loaded and f == 5 then
    emu:loadStateFile("save_states_for_claude/title_screen.ss0")
    loaded = true
    return
  end
  if loaded and f > 10 then
    local d = emu:read8(0xD880)
    -- dump first time we settle into each D880 value (wait a few frames after load)
    if not seen[d] and f > 30 then
      seen[d] = true
      dumpScene("D880_"..string.format("%02X", d))
    end
  end
  if f >= 2500 then out:write("DONE\n"); out:close(); done=true end
end)
