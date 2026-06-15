local OUT="/tmp/bannershot"; local f,done=0,false
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("banner\n");h:close() end end
callbacks:add("frame",function()
  if done then return end
  f=f+1; emu:setKeys(0)
  if f==4400 and emu:read8(0xD880)==0x1B then
    -- dump palettes of banner regions
    local base=((emu:read8(0xFF40)&0x08)~=0) and 0x9C00 or 0x9800
    emu:write8(0xFF4F,0); local t={}; emu:write8(0xFF4F,1); local a={}
    emu:write8(0xFF4F,0)
    local h={}; for r=0,17 do for c=0,19 do
      emu:write8(0xFF4F,0); local tid=emu:read8(base+r*32+c)
      emu:write8(0xFF4F,1); local pal=emu:read8(base+r*32+c)&7; emu:write8(0xFF4F,0)
      if tid~=0 then h[pal]=(h[pal] or 0)+1 end
    end end
    local s=""; for p=0,7 do if h[p] then s=s..string.format("p%d=%d ",p,h[p]) end end
    log("banner D880=0x1B f"..f.." palettes:["..s.."]")
    emu:screenshot(OUT..".png"); done=true; emu:stop()
  end
  if f>5200 then log("never reached banner"); done=true; emu:stop() end
end)
