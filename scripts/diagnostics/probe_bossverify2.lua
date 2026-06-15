-- Verify an enriched boss arena: fire teleport + pin D880=TGT/FFBA=IDX, then
-- detect FLICKER (cell whose palette changes frame-to-frame while tile is stable)
-- and report the palette histogram (multi-palette confirmation). env: TGT, IDX.
local OUT=os.getenv("OUT") or "/tmp/bv2"; local TGT=tonumber(os.getenv("TGT") or "15"); local IDX=tonumber(os.getenv("IDX") or "3")
local STATE="save_states_for_claude/level1_sara_d_alone.ss0"
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write(string.format("bv2 TGT=%02X IDX=%d\n",TGT,IDX));h:close() end end
local f,phase,pf,sub,done=0,"load",0,"gap",false
local prevt,preva,flips,samples=nil,nil,0,0
local palcount={}
local function pin() emu:write8(0xFFBA,IDX); emu:write8(0xD880,TGT); emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF); emu:write8(0xDCBB,0x80) end
callbacks:add("frame",function()
  f=f+1; if done then return end
  if phase=="load" then emu:loadStateFile(STATE); phase="settle"; pf=0; return end
  if phase=="settle" then emu:setKeys(0); pf=pf+1
    if pf>=25 then emu:write8(0xFFBA,IDX-1); emu:write8(0xDF0C,0); emu:write8(0xDF1D,0); emu:write8(0xDF1F,0); phase="tele"; sub="gap"; pf=0 end; return end
  if phase=="tele" then
    if sub=="gap" then emu:setKeys(0); pf=pf+1; if pf>=4 then sub="pulse"; pf=0 end
    elseif sub=="pulse" then emu:setKeys(0x0C); pf=pf+1; if pf>=8 then emu:setKeys(0); sub="wait"; pf=0 end
    elseif sub=="wait" then emu:setKeys(0); pf=pf+1; if pf>=20 then phase="pin"; pf=0 end end; return end
  if phase=="pin" then
    emu:setKeys(0); pin(); pf=pf+1
    if pf>40 then
      local base=((emu:read8(0xFF40)&0x08)~=0) and 0x9C00 or 0x9800
      emu:write8(0xFF4F,0); local t={}; for i=0,17*32-1 do t[i]=emu:read8(base+i) end
      emu:write8(0xFF4F,1); local a={}; for i=0,17*32-1 do a[i]=emu:read8(base+i)&7 end
      emu:write8(0xFF4F,0)
      for i=0,17*32-1 do if t[i]~=0 then palcount[a[i]]=(palcount[a[i]] or 0)+1 end end
      if prevt then for i=0,17*32-1 do if t[i]==prevt[i] and t[i]~=0 and a[i]~=preva[i] then flips=flips+1 end end end
      prevt=t; preva=a; samples=samples+1
    end
    if samples==1 then emu:screenshot(OUT..".png") end
    if samples>=150 then
      local ph=""; for p=0,7 do if palcount[p] then ph=ph..string.format("p%d=%d ",p,palcount[p]) end end
      log(string.format("D880=%02X samples=%d FLICKER_FLIPS=%d palettes:[%s]", emu:read8(0xD880), samples, flips, ph))
      emu:screenshot(OUT.."_final.png"); done=true; emu:stop()
    end
    if pf>1200 then log("timeout D880="..string.format("%02X",emu:read8(0xD880))); done=true; emu:stop() end
    return end
end)
