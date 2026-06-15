-- KEY: showcase
-- Map the FULL attract-mode D880 cycle (cold boot, NO input) and capture EVERY
-- entry into the 0x1B animated banner. Logs every D880 transition with frame.
-- Whenever D880==0x1B, every 4 frames dump the visible window's non-fill tile
-- content + a per-state signature so monster cycling can be detected. Runs long
-- (the attract loop is slow); record across multiple 0x1B visits.
local OUT = os.getenv("OUT") or "/tmp/showcase/d880"
local f = 0
local prev_d = -1
local last_sig = nil
local nstates = 0
local global_seen = {}
local samples = 0
local visits = 0
local function log(m) local h=io.open(OUT..".log","a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT..".log","w"); if h then h:write("d880 attract map\n");h:close() end end
local function rd_vbk(bank, addr) emu:write8(0xFF4F, bank); return emu:read8(addr) end
local FILL = {[0x00]=true, [0x28]=true, [0xDF]=true}

local function snapshot()
  local scx=emu:read8(0xFF43); local scy=emu:read8(0xFF42); local lcdc=emu:read8(0xFF40)
  local mapbase=(lcdc & 0x08)~=0 and 0x9C00 or 0x9800
  local col0=(scx>>3)&31; local row0=(scy>>3)&31
  local ids={}; local pals={}
  for vr=0,17 do ids[vr]={}; pals[vr]={}
    local mr=(row0+vr)&31
    for vc=0,19 do local mc=(col0+vc)&31; local off=mr*32+mc
      ids[vr][vc]=rd_vbk(0,mapbase+off); pals[vr][vc]=rd_vbk(1,mapbase+off)&0x07 end end
  emu:write8(0xFF4F,0)
  return ids,pals,scx,scy,lcdc,mapbase
end
local function row_sig(r) local s="" for vc=0,19 do local t=r[vc]; s=s..(FILL[t] and ".." or string.format("%02X",t)) end return s end
local function full_sig(ids) local p={} for vr=0,17 do p[#p+1]=row_sig(ids[vr]) end return table.concat(p,"|") end

callbacks:add("frame", function()
  f=f+1; emu:setKeys(0)
  local d=emu:read8(0xD880)
  if d~=prev_d then log(string.format("D880 %02X -> %02X at f=%d FFC1=%d", prev_d, d, f, emu:read8(0xFFC1))); prev_d=d
    if d==0x1B then visits=visits+1; last_sig=nil; log(string.format("** 0x1B VISIT #%d at f=%d **", visits, f)) end
  end
  if d==0x1B and f%4==0 then
    local ids,pals,scx,scy,lcdc,mapbase=snapshot()
    samples=samples+1
    local present={}; for vr=0,17 do for vc=0,19 do present[ids[vr][vc]]=true end end
    for t,_ in pairs(present) do global_seen[t]=(global_seen[t] or 0)+1 end
    local sig=full_sig(ids)
    if sig~=last_sig then last_sig=sig; nstates=nstates+1
      log(string.format("=== STATE #%d visit%d f=%d SCX=%d SCY=%d LCDC=%02X mapbase=%04X", nstates, visits, f, scx, scy, lcdc, mapbase))
      for vr=0,17 do local has=false; for vc=0,19 do if not FILL[ids[vr][vc]] then has=true;break end end
        if has then local il=string.format("R%02d ID :",vr); local pl=string.format("R%02d PAL:",vr)
          for vc=0,19 do il=il..string.format(" %02X",ids[vr][vc]); pl=pl..string.format("  %d",pals[vr][vc]) end
          log(il); log(pl) end end
      local u={}; for vr=0,17 do for vc=0,19 do local t=ids[vr][vc]; if not FILL[t] then u[t]=(u[t] or 0)+1 end end end
      local us={}; for t,_ in pairs(u) do us[#us+1]=t end; table.sort(us)
      local line="  non-fill IDs:"; for _,t in ipairs(us) do line=line..string.format(" %02X(%d)",t,u[t]) end; log(line)
      emu:screenshot(string.format("%s_v%d_state%02d_f%d.png", OUT, visits, nstates, f))
    end
  end
  if f%1000==0 then log(string.format("...hb f%d D880=%02X states=%d visits=%d", f, d, nstates, visits)) end
  if f>14000 and not _G.done then _G.done=true
    log(string.format("END states=%d samples=%d visits=%d", nstates, samples, visits))
    local ids2={}; for t,_ in pairs(global_seen) do ids2[#ids2+1]=t end; table.sort(ids2)
    log("global per-tile presence over 0x1B sampled frames:")
    for _,t in ipairs(ids2) do log(string.format("  %02X : %d/%d  %s", t, global_seen[t], samples, FILL[t] and "<FILL>" or "")) end
    log("DONE")
  end
end)
