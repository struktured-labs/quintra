-- miniboss cluster: dump live CGB OBJ CRAM (FF6A/FF6B) for all 8 OBJ palettes
-- during gargoyle AND spider fights, to confirm what colors body-index slots hold.
local STATE = os.getenv("MB_STATE") or "save_states_for_claude/level1_sara_w_gargoyle_mini_boss.ss0"
local TAG   = os.getenv("MB_TAG") or "gargoyle_cram"
local OUT   = "/tmp/miniboss/"..TAG..".log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("OBJ CRAM tag="..TAG.."\n");h:close() end end
local f=0; local loaded=false; local done=false
local function rd(a) return emu:read8(a) end
local function dec(lo,hi) local v=lo|(hi<<8); local r=v&0x1F; local g=(v>>5)&0x1F; local b=(v>>10)&0x1F
  return string.format("R%02d G%02d B%02d", r,g,b) end
callbacks:add("frame", function()
  f=f+1
  if not loaded then emu:loadStateFile(STATE); loaded=true; return end
  if f < 130 then return end
  if done then return end
  done=true
  log(string.format("FFBF=%02X FFBE=%02X", rd(0xFFBF), rd(0xFFBE)))
  for pal=0,7 do
    local cols={}
    for c=0,3 do
      emu:write8(0xFF6A, pal*8 + c*2)       -- OCPS index, no autoinc
      local lo = rd(0xFF6B)
      emu:write8(0xFF6A, pal*8 + c*2 + 1)
      local hi = rd(0xFF6B)
      cols[#cols+1] = dec(lo,hi)
    end
    log(string.format("OBP%d: [%s]", pal, table.concat(cols, " | ")))
  end
  log("DONE")
end)
