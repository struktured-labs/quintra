-- Capture regular dungeon gameplay (monsters spawn as Sara roams) for a
-- color-quality assessment. Boots via the title autostart, then roams by
-- cycling directions + occasional attack, screenshotting every ~75 frames.
-- Output: /tmp/mon_<n>.png  (+ /tmp/mon.log with D880/FFBF/FFC1 per shot).
local TITLE={{180,185,0x80},{193,198,0x01},{241,246,0x01},{291,296,0x01},{341,346,0x08},{391,396,0x01}}
local function log(m) local h=io.open("/tmp/mon.log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open("/tmp/mon.log","w"); if h then h:write("monster capture\n");h:close() end end
local f=0;local started=false;local sf=0;local n=0;local NMAX=10
-- roam pattern: dir bitmask R=0x10 L=0x20 U=0x40 D=0x80 ; A=0x01
local DIRS={0x10,0x10,0x80,0x80,0x20,0x20,0x40,0x40}
callbacks:add("frame",function()
 f=f+1
 if f<=500 then local k=0;for _,e in ipairs(TITLE) do if f>=e[1] and f<=e[2] then k=e[3];break end end;emu:setKeys(k);return end
 if not started then emu:setKeys(0)
   if emu:read8(0xD880)==0x02 and emu:read8(0xFFC1)==1 then started=true;sf=0;log("dungeon reached f"..f) end
   return end
 if n>=NMAX then return end
 sf=sf+1
 -- roam: choose direction by phase, add attack every 8th frame
 local d=DIRS[((sf//20)%#DIRS)+1]
 local k=d
 if sf%8==0 then k=k|0x01 end  -- press A (attack)
 emu:setKeys(k)
 if sf%75==0 then
   n=n+1
   emu:screenshot("/tmp/mon_"..n..".png")
   log(string.format("shot %d f%d D880=0x%02X FFBF=%d FFC1=%d",n,f,emu:read8(0xD880),emu:read8(0xFFBF),emu:read8(0xFFC1)))
   if n>=NMAX then log("DONE") end
 end
end)
