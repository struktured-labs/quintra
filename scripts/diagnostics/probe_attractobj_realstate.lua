-- attract-obj cluster: load a REAL gameplay save state with many enemies and
-- dump full 40-slot OAM, flagging sprites beyond the 10-entry colorizer cap
-- that keep stale attr (pal0). Confirms the cap (not the FFC1 gate) is the
-- cause of "black/wrong" monster sprites.
local OUT = os.getenv("OUT") or "/tmp/attract-obj/realstate"
local STATE = os.getenv("STATE")
local f = 0
local done = false
local loaded = false
local samples = 0
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("attract-obj realstate OAM dump: "..tostring(STATE).."\n");h:close() end end
local function expectedPal(tile, ffbe)
  if tile==0x00 then return -1 end
  if tile<=0x01 then return 3 end
  if tile<=0x0F then return 0 end
  if tile<=0x1F then return 4 end
  if tile<=0x2F then return (ffbe~=0) and 1 or 2 end
  if tile<=0x3F then return 3 end
  if tile<=0x4F then return 4 end
  if tile<=0x5F then return 5 end
  if tile<=0x6F then return 6 end
  if tile<=0x7F then return 7 end
  return 4
end
callbacks:add("frame", function()
  if done then return end
  f = f + 1
  emu:setKeys(0)
  if not loaded and f == 4 then
    emu:loadStateFile(STATE)
    loaded = true
  end
  -- after load, let colorizer run ~150 frames then sample
  if loaded and f > 160 and samples < 3 then
    local d = emu:read8(0xD880); local ffc1 = emu:read8(0xFFC1); local ffbe = emu:read8(0xFFBE)
    local n=0; local rows={}; local mism=0; local beyondCap=0
    for s=0,39 do
      local y=emu:read8(0xFE00+s*4); local x=emu:read8(0xFE00+s*4+1)
      local tile=emu:read8(0xFE00+s*4+2); local attr=emu:read8(0xFE00+s*4+3)
      if y~=0 and y<160 and x~=0 and x<168 then
        n=n+1
        local pal=attr&0x07; local exp=expectedPal(tile,ffbe); local flag=""
        if exp>=0 and pal~=exp then flag="  <-- MISMATCH exp_p"..exp; mism=mism+1; if s>=10 then beyondCap=beyondCap+1 end end
        rows[#rows+1]=string.format("  slot%02d y%3d x%3d tile%02X attr%02X pal%d%s",s,y,x,tile,attr,pal,flag)
      end
    end
    samples = samples + 1
    log(string.format("=== sample%d f%d D880=%02X FFC1=%d FFBE=%02X FFBF=%02X OAM=%d MISMATCH=%d beyondCap_mism=%d",
      samples, f, d, ffc1, ffbe, emu:read8(0xFFBF), n, mism, beyondCap))
    for _,r in ipairs(rows) do log(r) end
  end
  if f >= 600 or samples >= 3 then log("DONE"); done = true end
end)
