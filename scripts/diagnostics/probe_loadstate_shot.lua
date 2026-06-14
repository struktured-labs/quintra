-- Load an mGBA save state into the CURRENT build and screenshot it, so we can
-- assess monster / mini-boss / hazard colorization on real game states.
-- Input:  /tmp/state_path.txt = absolute path to the .ss0 state
-- Output: /tmp/state_shot.png + /tmp/state.log (load result + state bytes)
local PATH=nil
do local h=io.open("/tmp/state_path.txt","r"); if h then PATH=h:read("*l"); h:close() end end
local function log(m) local h=io.open("/tmp/state.log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open("/tmp/state.log","w"); if h then h:write("loadstate\n");h:close() end end
local f=0;local loaded=false;local done=false
callbacks:add("frame",function()
 f=f+1
 if f==10 and PATH then
   local ok=nil
   local fn = emu.loadStateFile or emu.loadStateSlot
   if emu.loadStateFile then ok = pcall(function() return emu:loadStateFile(PATH) end) end
   log("loadStateFile("..tostring(PATH)..") pcall_ok="..tostring(ok))
   loaded=true
 end
 if loaded and f>=60 and not done then
   emu:screenshot("/tmp/state_shot.png")
   log(string.format("shot f%d D880=0x%02X FFBF=%d FFC1=%d FFBA=%d FFBD=%d",
     f, emu:read8(0xD880), emu:read8(0xFFBF), emu:read8(0xFFC1), emu:read8(0xFFBA), emu:read8(0xFFBD)))
   log("DONE"); done=true
 end
end)
