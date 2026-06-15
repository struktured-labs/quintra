-- crystal_teleport_diag.lua: single clean fire, then watch D880/FFBA/DF20-21/DB00
-- for 200 frames to see if the landing-pad redirect ever moves us into an arena.
local OUT="/tmp/crystal/teleport_diag"
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("teleport diag\n");h:close() end end
local f=0; local ph="boot"; local fid=0; local pf=0; local done=false; local fired=false
callbacks:add("frame",function()
 f=f+1
 if done then return end
 emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF)
 if ph=="boot" then
   emu:setKeys(0); emu:write8(0xDF0E,0)
   if emu:read8(0xD880)==0x02 and emu:read8(0xFFC1)==1 then fid=fid+1
     if fid>20 then
       -- dump DB00 landing pad before fire
       local s="DB00:"; for i=0,15 do s=s..string.format(" %02X",emu:read8(0xDB00+i)) end
       log(s)
       log(string.format("pre-fire f%d D880=0x%02X FFBA=%d DF0E=%02X",f,emu:read8(0xD880),emu:read8(0xFFBA),emu:read8(0xDF0E)))
       ph="pre"; pf=0
     end
   end
   return
 end
 if ph=="pre" then
   emu:write8(0xFFBA,1); emu:write8(0xDF0C,0); emu:write8(0xDF1D,0); emu:setKeys(0)
   ph="press"; pf=0; return
 end
 if ph=="press" then
   emu:setKeys(0x0C); pf=pf+1
   if pf==1 then log(string.format("press f%d FF93=%02X",f,emu:read8(0xFF93))) end
   if pf>=10 then emu:setKeys(0); ph="watch"; pf=0; fired=true end
   return
 end
 if ph=="watch" then
   emu:setKeys(0); pf=pf+1
   if pf<=200 then
     local d=emu:read8(0xD880)
     if pf<=10 or d~=0x02 or pf%20==0 then
       log(string.format("watch f%d pf%d D880=0x%02X FFBA=%d FFBF=%d DF20=%02X DF21=%02X DF1F=%d DF1D=%d",
         f,pf,d,emu:read8(0xFFBA),emu:read8(0xFFBF),emu:read8(0xDF20),emu:read8(0xDF21),emu:read8(0xDF1F),emu:read8(0xDF1D)))
     end
   else
     -- second fire attempt with FFBA already at 2 -> try advancing again
     local s="DB00:"; for i=0,15 do s=s..string.format(" %02X",emu:read8(0xDB00+i)) end
     log(s)
     log("DONE"); done=true
   end
   return
 end
end)
