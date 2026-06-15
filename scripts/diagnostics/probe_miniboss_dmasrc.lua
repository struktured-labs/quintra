-- miniboss cluster: find OAM DMA source page (0xFF80 HRAM routine reads which page),
-- dump that page's gargoyle attrs right after colorize. Also dump HRAM 0xFF80-0xFF8F.
local STATE = os.getenv("MB_STATE") or "save_states_for_claude/level1_sara_w_gargoyle_mini_boss.ss0"
local TAG   = os.getenv("MB_TAG") or "gargoyle_dma"
local OUT   = "/tmp/miniboss/"..TAG..".log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("dma src tag="..TAG.."\n");h:close() end end
local f=0; local loaded=false; local done=false
local function rd(a) return emu:read8(a) end
callbacks:add("frame", function()
  f=f+1
  if not loaded then emu:loadStateFile(STATE); loaded=true; return end
  if f < 130 then return end
  if done then return end
  done=true
  log("HRAM 0xFF80-0xFF8F (OAM DMA routine):")
  local s=""; for i=0,15 do s=s..string.format(" %02X", rd(0xFF80+i)) end; log(s)
  -- The DMA routine: LD A,page; LDH(FF46),A; LD A,0x28; dec; loop. page byte usually FF81.
  log(string.format("likely DMA source page = 0x%02X00 (byte at FF81)", rd(0xFF81)))
  -- Dump candidate pages C0,C1 entries 0-19 attrs
  for _,pg in ipairs({0xC0,0xC1}) do
    local base=pg*0x100
    log(string.format("page 0x%02X00 entries 0-19 (tile/attr/objpal):", pg))
    for i=0,19 do
      local b=base+i*4
      local t=rd(b+2); local a=rd(b+3)
      log(string.format("  e%02d tile=%02X attr=%02X pal=%d", i, t, a, a&7))
    end
  end
  log("DONE")
end)
