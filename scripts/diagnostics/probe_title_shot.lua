-- Capture the TITLE screen (no input) to verify the PENTA DRAGON DX logo + the
-- STRUKTURED LABS attribution render correctly. Shots at a few frames (the logo
-- animates). Output /tmp/title_<n>.png + /tmp/title.log (D880/FFC1).
local function log(m) local h=io.open("/tmp/title.log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open("/tmp/title.log","w"); if h then h:write("title shot\n");h:close() end end
local f=0;local n=0
local SHOTS={400,520}
callbacks:add("frame",function()
 f=f+1
 emu:setKeys(0)  -- never press anything; stay on title
 for _,sf in ipairs(SHOTS) do
   if f==sf then n=n+1; emu:screenshot("/tmp/title_"..n..".png")
     log(string.format("shot %d f%d D880=0x%02X FFC1=%d",n,f,emu:read8(0xD880),emu:read8(0xFFC1))) end
 end
 if f>640 then log("DONE") end
end)
