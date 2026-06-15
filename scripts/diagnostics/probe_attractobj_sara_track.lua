-- attract-obj cluster: track Sara's REAL OAM palette (slots 0-3) over 200 frames
-- in a real state to see if Sara is ever p0 (black/wrong) steadily vs transient.
-- Also count, per frame, how many visible OAM sprites at slots>=10 carry the
-- fallback palette 4 or palette 0 (the cap-victims).
local OUT = os.getenv("OUT") or "/tmp/attract-obj/sara"
local STATE = os.getenv("STATE")
local f=0; local done=false; local loaded=false; local n=0
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("attract-obj sara track: "..tostring(STATE).."\n");h:close() end end
callbacks:add("frame", function()
  if done then return end
  f=f+1; emu:setKeys(0)
  if not loaded and f==4 then emu:loadStateFile(STATE); loaded=true end
  if loaded and f>120 and n<10 then
    n=n+1
    local saraP={}
    for s=0,3 do saraP[#saraP+1]=tostring(emu:read8(0xFE00+s*4+3)&0x07) end
    -- count cap-victim sprites at slots>=10
    local victims=0; local visge10=0
    for s=10,39 do
      local y=emu:read8(0xFE00+s*4); local x=emu:read8(0xFE00+s*4+1)
      local tile=emu:read8(0xFE00+s*4+2); local pal=emu:read8(0xFE00+s*4+3)&0x07
      if y~=0 and y<160 and x~=0 and x<168 and tile~=0 then
        visge10=visge10+1
        -- victim if its tile-range expected pal != actual and actual in {0,4}
        local exp=-2
        if tile>=0x60 and tile<=0x6F then exp=6
        elseif tile>=0x70 and tile<=0x7F then exp=7
        elseif tile>=0x30 and tile<=0x3F then exp=3 end
        if exp>=0 and pal~=exp then victims=victims+1 end
      end
    end
    log(string.format("f%d FFBE=%02X SaraOAMpal=[%s] vis_slot>=10=%d wrongpal_slot>=10=%d",
      f, emu:read8(0xFFBE), table.concat(saraP,","), visge10, victims))
  end
  if f>=400 or n>=10 then log("DONE"); done=true end
end)
