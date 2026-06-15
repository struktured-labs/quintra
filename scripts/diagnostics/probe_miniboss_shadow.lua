-- miniboss cluster: dump shadow OAM buffers C000/C100 AND hardware OAM FE00,
-- side by side, to see which entries the colorizer scans (first 10 of each buffer)
-- and what palette it assigns vs what the game wrote. Also read FFBF + boss_slot.
local STATE = os.getenv("MB_STATE") or "save_states_for_claude/level1_sara_w_gargoyle_mini_boss.ss0"
local TAG   = os.getenv("MB_TAG") or "gargoyle_shadow"
local OUT   = "/tmp/miniboss/"..TAG..".log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("shadow dump tag="..TAG.."\n");h:close() end end
local f=0; local loaded=false; local done=false
local function rd(a) return emu:read8(a) end
callbacks:add("frame", function()
  f=f+1
  if not loaded then emu:loadStateFile(STATE); loaded=true; return end
  if f < 130 then return end
  if done then return end
  done=true
  log(string.format("FFBF=%02X FFBE=%02X (boss_slot_table[FFBF-1] in ROM=06,07,...)", rd(0xFFBF), rd(0xFFBE)))
  -- Shadow buffer 1: 0xC000, buffer 2: 0xC100. colorizer scans HL=base+3 (attr), B=10 entries.
  for buf,base in ipairs({0xC000, 0xC100}) do
    log(string.format("--- shadow buffer %d @0x%04X (first 12 entries; colorizer scans 10) ---", buf, base))
    for i=0,11 do
      local b=base+i*4
      local y=rd(b);local x=rd(b+1);local t=rd(b+2);local a=rd(b+3)
      local mark = (i<10) and "[scan]" or "[----]"
      log(string.format("  %s e%02d: y=%3d x=%3d tile=%02X attr=%02X objpal=%d", mark, i, y,x,t,a,a&7))
    end
  end
  -- hardware OAM (post-DMA) entries 0-23
  log("--- hardware OAM 0xFE00 entries 0-23 ---")
  for i=0,23 do
    local b=0xFE00+i*4
    local y=rd(b);local x=rd(b+1);local t=rd(b+2);local a=rd(b+3)
    if y~=0 or x~=0 or t~=0 then
      log(string.format("  HW%02d: y=%3d x=%3d tile=%02X attr=%02X objpal=%d", i, y,x,t,a,a&7))
    end
  end
  log("DONE")
end)
