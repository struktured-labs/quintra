-- miniboss cluster: dump OBP6/OBP7 CRAM over consecutive frames during gargoyle
-- fight, to see if our loader is writing them or if they are stale/native.
local STATE = "save_states_for_claude/level1_sara_w_gargoyle_mini_boss.ss0"
local OUT   = "/tmp/miniboss/gargoyle_cram_native.log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("native cram trace\n");h:close() end end
local f=0; local loaded=false
local function rd(a) return emu:read8(a) end
local function dec(lo,hi) local v=lo|(hi<<8); return string.format("%04X(R%02dG%02dB%02d)", v, v&0x1F,(v>>5)&0x1F,(v>>10)&0x1F) end
local function palcols(pal)
  local cols={}
  for c=0,3 do
    emu:write8(0xFF6A, pal*8+c*2); local lo=rd(0xFF6B)
    emu:write8(0xFF6A, pal*8+c*2+1); local hi=rd(0xFF6B)
    cols[#cols+1]=dec(lo,hi)
  end
  return table.concat(cols," ")
end
callbacks:add("frame", function()
  f=f+1
  if not loaded then emu:loadStateFile(STATE); loaded=true; return end
  if f < 132 or f > 138 then return end
  log(string.format("f=%d FFBF=%02X", f, rd(0xFFBF)))
  log("  OBP6: "..palcols(6))
  log("  OBP7: "..palcols(7))
end)
