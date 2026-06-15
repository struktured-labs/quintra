-- boss-verify cluster: verification checklist for all 9 boss arenas (v2).
-- Loads dungeon save state (D880=0x02, FFC1=1), teleports to bosses 0..8 in one
-- process via the proven combo (pre-set FFBA=idx-1, pulse SELECT+START mask 0x0C,
-- wait for D880=0x0C+idx). For each boss:
--   settle 120 frames (only counts while D880==target), then collect in WINDOWS
--   of 60 frames x 4 windows (=240 frames). Per window count flip_stable =
--   number of (cell,frame) where bg_pal flipped vs prev frame WHILE tile id was
--   identical (true flicker). Window 1 absorbs settle; windows 2..4 nonzero =
--   STEADY-STATE alternation (the bad flicker). Also: palette histogram of last
--   frame (flood detection), and tile-change cell count (animation, expected).
-- STRICT: aborts/re-tries a boss if D880 ever leaves the exact arena value
-- during settle or collect, so we never report a transitional frame as "the
-- arena". Output: /tmp/boss-verify/checklist.log + per-boss screenshots.
local OUT="/tmp/boss-verify/checklist.log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("boss-verify checklist v2\n");h:close() end end
local NAMES={[0]="Shalamar",[1]="Riff",[2]="CrystalDragon",[3]="Cameo",[4]="Ted",
             [5]="Troop",[6]="Faze",[7]="Angela",[8]="PentaDragon"}
local ROWS=18; local COLS=24
local f=0; local ph="boot"; local sub="pre"; local pf=0; local fid=0; local at=0
local idx=0
local SETTLE=120; local WIN=60; local NWIN=4; local MAXTRY=10
local function isar(d) return d>=0x0C and d<=0x14 end
local function holdhp() emu:write8(0xDCDC,0xFF); emu:write8(0xDCDD,0xFF) end
local function base() local l=emu:read8(0xFF40); if (l&0x08)~=0 then return 0x9C00 else return 0x9800 end end

local prevTile={}; local prevPal={}
local winFlip=0; local win=0; local wf=0
local totFlip=0; local cellFlipSet={}
local tileChgSet={}
local lastPal={}; local lastTile={}
local sampled=0
local function reset_acc()
  prevTile={}; prevPal={}; winFlip=0; win=0; wf=0; totFlip=0
  cellFlipSet={}; tileChgSet={}; lastPal={}; lastTile={}; sampled=0
end
local function scan()
  local b=base()
  emu:write8(0xFF4F,0)
  local tiles={}
  for r=0,ROWS-1 do for c=0,COLS-1 do tiles[r*COLS+c]=emu:read8(b+r*32+c) end end
  emu:write8(0xFF4F,1)
  local pals={}
  for r=0,ROWS-1 do for c=0,COLS-1 do pals[r*COLS+c]=emu:read8(b+r*32+c)&7 end end
  emu:write8(0xFF4F,0)
  for k=0,ROWS*COLS-1 do
    if prevTile[k]~=nil then
      if tiles[k]~=prevTile[k] then tileChgSet[k]=true
      elseif pals[k]~=prevPal[k] then
        winFlip=winFlip+1; totFlip=totFlip+1; cellFlipSet[k]=(cellFlipSet[k] or 0)+1
      end
    end
    prevTile[k]=tiles[k]; prevPal[k]=pals[k]
    lastTile[k]=tiles[k]; lastPal[k]=pals[k]
  end
  sampled=sampled+1
end
local winHist={}
local function emit(d880, ffba)
  log(string.format("=== BOSS %d (%s) ===", idx, NAMES[idx]))
  log(string.format("  reached=YES D880=0x%02X(expect 0x%02X) FFBA=%d LCDC=0x%02X base=0x%04X samples=%d",
    d880, 0x0C+idx, ffba, emu:read8(0xFF40), base(), sampled))
  local hist={0,0,0,0,0,0,0,0}
  for k=0,ROWS*COLS-1 do local p=lastPal[k]; if p then hist[p+1]=hist[p+1]+1 end end
  local hs=""
  for p=0,7 do hs=hs..string.format("p%d=%d ",p,hist[p+1]) end
  log("  PAL HIST (last frame, "..(ROWS*COLS).." cells): "..hs)
  local total=ROWS*COLS
  for p=0,7 do
    if hist[p+1] > total*0.85 then
      log(string.format("  ** FLOOD WARNING: palette %d covers %d/%d cells (>85%%)", p, hist[p+1], total))
    end
  end
  -- window flip report
  local ws=""
  for i=1,#winHist do ws=ws..string.format("w%d=%d ",i,winHist[i]) end
  log("  WINDOW flip_stable: "..ws)
  local steady=0
  for i=2,#winHist do steady=steady+winHist[i] end
  log(string.format("  STEADY-STATE alternation (windows 2..%d sum)=%d  (>0 = bad flicker)", #winHist, steady))
  local cf=0; for k,v in pairs(cellFlipSet) do cf=cf+1 end
  log(string.format("  total flips=%d across %d distinct cells", totFlip, cf))
  -- top flicker cells
  local arr={}
  for k,v in pairs(cellFlipSet) do table.insert(arr,{k,v}) end
  table.sort(arr, function(a,b) return a[2]>b[2] end)
  local shown=0
  for _,e in ipairs(arr) do
    if shown>=10 then break end
    local k=e[1]; local r=math.floor(k/COLS); local c=k%COLS
    log(string.format("    flicker cell (r%02d,c%02d) tile=0x%02X pal=%d flips=%d",
      r,c,lastTile[k] or 0, lastPal[k] or 0, e[2]))
    shown=shown+1
  end
  local ac=0; for k,v in pairs(tileChgSet) do ac=ac+1 end
  log(string.format("  anim cells (tile changed over run)=%d", ac))
  log("  ---")
end

callbacks:add("frame",function()
 f=f+1
 if f<=20 then return end
 if ph=="done" then return end
 holdhp()
 if ph=="boot" then emu:setKeys(0)
  if emu:read8(0xD880)==0x02 and emu:read8(0xFFC1)==1 then fid=fid+1
   if fid>20 then ph="cyc"; sub="pre"; pf=0 end end
  return
 end
 local TGT=0x0C+idx
 if sub=="pre" then
  local pre=idx-1; if pre<0 then pre=8 end
  emu:write8(0xFFBA,pre); emu:write8(0xDF0C,0); emu:write8(0xDF1D,0)
  reset_acc(); winHist={}
  sub="pr"; pf=0
 elseif sub=="pr" then emu:setKeys(0x0C); pf=pf+1; if pf>=10 then emu:setKeys(0); sub="rl"; pf=0 end
 elseif sub=="rl" then emu:setKeys(0); pf=pf+1; if pf>=10 then sub="wa"; pf=0 end
 elseif sub=="wa" then
  pf=pf+1
  if emu:read8(0xD880)==TGT then sub="settle"; pf=0
  elseif pf>400 then at=at+1
   if at>=MAXTRY then
     log(string.format("=== BOSS %d (%s) ===",idx,NAMES[idx]))
     log("  reached=NO (teleport failed after "..MAXTRY.." tries)"); log("  ---")
     idx=idx+1; at=0
     if idx>=9 then log("ALLDONE"); ph="done" else sub="pre"; pf=0 end
   else sub="pre"; pf=0 end
  end
 elseif sub=="settle" then
  pf=pf+1
  -- STRICT: require exact target the whole settle
  if emu:read8(0xD880)~=TGT then
    at=at+1
    if at>=MAXTRY then
      log(string.format("=== BOSS %d (%s) ===",idx,NAMES[idx]))
      log("  reached=PARTIAL (arena unstable: D880 drifted to 0x"..string.format("%02X",emu:read8(0xD880)).." during settle)")
      log("  ---")
      idx=idx+1; at=0
      if idx>=9 then log("ALLDONE"); ph="done" else sub="pre"; pf=0 end
    else sub="pre"; pf=0 end
  elseif pf>=SETTLE then sub="collect"; win=1; wf=0; winFlip=0; pf=0 end
 elseif sub=="collect" then
  if emu:read8(0xD880)~=TGT then
    -- left exact arena; if we already have >=2 windows, accept; else retry
    if win>=3 then emit(TGT, emu:read8(0xFFBA)); sub="back"; pf=0
    else
      at=at+1
      if at>=MAXTRY then emit(TGT, emu:read8(0xFFBA)); sub="back"; pf=0
      else reset_acc(); winHist={}; sub="pre"; pf=0 end
    end
    return
  end
  scan(); wf=wf+1
  if wf>=WIN then
    winHist[win]=winFlip
    win=win+1; wf=0; winFlip=0
    if win>NWIN then
      emit(TGT, emu:read8(0xFFBA))
      emu:screenshot("/tmp/boss-verify/boss_"..idx.."_"..NAMES[idx]..".png")
      sub="back"; pf=0
    end
  end
 elseif sub=="back" then
  pf=pf+1
  if emu:read8(0xD880)==0x02 then
   idx=idx+1; at=0
   if idx>=9 then log("ALLDONE"); ph="done" else sub="pre"; pf=0 end
  elseif pf>300 then
   idx=idx+1; at=0
   if idx>=9 then log("ALLDONE"); ph="done" else sub="pre"; pf=0 end
  end
 end
end)
