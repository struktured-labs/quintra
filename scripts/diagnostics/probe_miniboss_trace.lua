-- miniboss cluster: capture HW OAM over 30 consecutive frames to see if the
-- gargoyle body palette is STABLE or FLICKERS between palettes (segmentation
-- could be temporal). Records per-frame the objpal of each body tile.
local STATE = os.getenv("MB_STATE") or "save_states_for_claude/level1_sara_w_gargoyle_mini_boss.ss0"
local TAG   = os.getenv("MB_TAG") or "gargoyle_trace"
local OUT   = "/tmp/miniboss/"..TAG..".log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("trace tag="..TAG.."\n");h:close() end end
local f=0; local loaded=false
local function rd(a) return emu:read8(a) end
callbacks:add("frame", function()
  f=f+1
  if not loaded then emu:loadStateFile(STATE); loaded=true; return end
  if f < 130 then return end
  if f > 175 then return end
  -- scan HW OAM 0-23, collect (tile,pal) for body-range tiles (>=0x30)
  local parts={}
  for i=0,23 do
    local b=0xFE00+i*4
    local y=rd(b); local t=rd(b+2); local a=rd(b+3)
    if y>0 and y<150 and t>=0x30 and t<0x60 then
      parts[#parts+1]=string.format("%02X:p%d", t, a&7)
    end
  end
  log(string.format("f=%d FFBF=%02X body=[%s]", f, rd(0xFFBF), table.concat(parts," ")))
end)
