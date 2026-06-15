local STATE=os.getenv("STATE"); local OUT=os.getenv("OUT") or "/tmp/objshot"
local f,done=0,false
callbacks:add("frame",function()
  if done then return end
  f=f+1; emu:setKeys(0)
  if f==10 then pcall(function() return emu:loadStateFile(STATE) end) end
  if f==150 then emu:screenshot(OUT..".png"); done=true; emu:stop() end
end)
