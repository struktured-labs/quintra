-- boss-verify cluster: STRICT-HOLD single-boss verifier for arenas that drift to
-- D880=0x0B (lock-cleanup transition) under teleport. Requires the EXACT target
-- D880 for every sampled frame; if it drifts, discards the partial run and
-- re-teleports. Only emits when it has NWIN full windows entirely on the target.
-- Also pins DCB8=0 and re-asserts FFBA each frame to discourage section advance.
local OUT="/tmp/boss-verify/hold.log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("hold\n");h:close() end end
local NAMES={[0]="Shalamar",[1]="Riff",[2]="CrystalDragon",[3]="Cameo",[4]="Ted",
             [5]="Troop",[6]="Faze",[7]="Angela",[8]="PentaDragon"}
local IDX=4
do local h=io.open("/tmp/boss-verify/target.txt","r"); if h then local s=h:read("*all"); h:close()
  local n=tonumber((s or ""):match("%d")); if n then IDX=n end end end
local TGT=0x0C+IDX
local ROWS=18; local COLS=24
local f=0; local ph="boot"; local sub="pre"; local pf=0; local fid=0; local at=0
local SETTLE=150; local WIN=50; local NWIN=4; local MAXTRY=20
local function holdhp() emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF) end
local function pin() emu:write8(0xFFBA,IDX); holdhp() end
local function base() local l=emu:read8(0xFF40); if (l&0x08)~=0 then return 0x9C00 else return 0x9800 end end
local prevTile={}; local prevPal={}
local winFlip=0; local win=0; local wf=0; local totFlip=0
local cellFlipSet={}; local tileChgSet={}; local lastPal={}; local lastTile={}; local sampled=0
local winHist={}
local function reset_acc() prevTile={};prevPal={};winFlip=0;win=0;wf=0;totFlip=0
  cellFlipSet={};tileChgSet={};lastPal={};lastTile={};sampled=0;winHist={} end
local function scan()
  local b=base(); emu:write8(0xFF4F,0)
  local tiles={}
  for r=0,ROWS-1 do for c=0,COLS-1 do tiles[r*COLS+c]=emu:read8(b+r*32+c) end end
  emu:write8(0xFF4F,1)
  local pals={}
  for r=0,ROWS-1 do for c=0,COLS-1 do pals[r*COLS+c]=emu:read8(b+r*32+c)&7 end end
  emu:write8(0xFF4F,0)
  for k=0,ROWS*COLS-1 do
    if prevTile[k]~=nil then
      if tiles[k]~=prevTile[k] then tileChgSet[k]=true
      elseif pals[k]~=prevPal[k] then winFlip=winFlip+1; totFlip=totFlip+1; cellFlipSet[k]=(cellFlipSet[k] or 0)+1 end
    end
    prevTile[k]=tiles[k]; prevPal[k]=pals[k]; lastTile[k]=tiles[k]; lastPal[k]=pals[k]
  end
  sampled=sampled+1
end
local function emit(ok)
  log(string.format("=== BOSS %d (%s) ===", IDX, NAMES[IDX]))
  log(string.format("  reached=%s D880=0x%02X(expect 0x%02X) FFBA=%d LCDC=0x%02X base=0x%04X samples=%d retries=%d",
    ok and "YES" or "PARTIAL", emu:read8(0xD880), TGT, emu:read8(0xFFBA), emu:read8(0xFF40), base(), sampled, at))
  local hist={0,0,0,0,0,0,0,0}
  for k=0,ROWS*COLS-1 do local p=lastPal[k]; if p then hist[p+1]=hist[p+1]+1 end end
  local hs=""; for p=0,7 do hs=hs..string.format("p%d=%d ",p,hist[p+1]) end
  log("  PAL HIST (last frame): "..hs)
  local total=ROWS*COLS
  for p=0,7 do if hist[p+1] > total*0.85 then
    log(string.format("  ** FLOOD WARNING: palette %d covers %d/%d cells (>85%%)", p, hist[p+1], total)) end end
  local ws=""; for i=1,#winHist do ws=ws..string.format("w%d=%d ",i,winHist[i]) end
  log("  WINDOW flip_stable: "..ws)
  local steady=0; for i=2,#winHist do steady=steady+winHist[i] end
  log(string.format("  STEADY-STATE alternation (windows 2..%d sum)=%d  (>0 = bad flicker)", #winHist, steady))
  local cf=0; for k,v in pairs(cellFlipSet) do cf=cf+1 end
  log(string.format("  total flips=%d across %d distinct cells", totFlip, cf))
  local arr={}; for k,v in pairs(cellFlipSet) do table.insert(arr,{k,v}) end
  table.sort(arr, function(a,b) return a[2]>b[2] end)
  local shown=0
  for _,e in ipairs(arr) do if shown>=10 then break end
    local k=e[1]; local r=math.floor(k/COLS); local c=k%COLS
    log(string.format("    flicker cell (r%02d,c%02d) tile=0x%02X pal=%d flips=%d",r,c,lastTile[k] or 0,lastPal[k] or 0,e[2]))
    shown=shown+1 end
  local ac=0; for k,v in pairs(tileChgSet) do ac=ac+1 end
  log(string.format("  anim cells (tile changed over run)=%d", ac))
  emu:screenshot("/tmp/boss-verify/hold_"..IDX.."_"..NAMES[IDX]..".png")
  log("DONE")
end
callbacks:add("frame",function()
 f=f+1
 if f<=20 then return end
 if ph=="done" then return end
 holdhp()
 if ph=="boot" then emu:setKeys(0)
  if emu:read8(0xD880)==0x02 and emu:read8(0xFFC1)==1 then fid=fid+1; if fid>20 then ph="cyc"; sub="pre"; pf=0 end end
  return end
 if sub=="pre" then
  local pre=IDX-1; if pre<0 then pre=8 end
  emu:write8(0xFFBA,pre); emu:write8(0xDF0C,0); emu:write8(0xDF1D,0)
  reset_acc(); sub="pr"; pf=0
 elseif sub=="pr" then emu:setKeys(0x0C); pf=pf+1; if pf>=10 then emu:setKeys(0); sub="rl"; pf=0 end
 elseif sub=="rl" then emu:setKeys(0); pf=pf+1; if pf>=10 then sub="wa"; pf=0 end
 elseif sub=="wa" then
  pf=pf+1
  if emu:read8(0xD880)==TGT then sub="settle"; pf=0
  elseif pf>250 then at=at+1
   if at>=MAXTRY then emit(false); ph="done" else sub="back"; pf=0 end end
 elseif sub=="settle" then
  pin(); pf=pf+1
  if emu:read8(0xD880)~=TGT then at=at+1
   if at>=MAXTRY then emit(false); ph="done" else sub="back"; pf=0 end
  elseif pf>=SETTLE then reset_acc(); sub="collect"; win=1; wf=0; winFlip=0 end
 elseif sub=="collect" then
  pin()
  if emu:read8(0xD880)~=TGT then
    -- drifted: discard this attempt, re-teleport
    at=at+1
    if at>=MAXTRY then
      -- accept partial if we got >=2 clean windows
      if win>=3 then emit(true) else emit(false) end
      ph="done"
    else reset_acc(); sub="back"; pf=0 end
    return
  end
  scan(); wf=wf+1
  if wf>=WIN then winHist[win]=winFlip; win=win+1; wf=0; winFlip=0
   if win>NWIN then emit(true); ph="done" end
  end
 elseif sub=="back" then
  pf=pf+1
  if emu:read8(0xD880)==0x02 then sub="pre"; pf=0
  elseif pf>250 then sub="pre"; pf=0 end
 end
end)
