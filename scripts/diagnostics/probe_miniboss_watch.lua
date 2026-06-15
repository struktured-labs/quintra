-- miniboss cluster: watchpoint on a gargoyle body OAM attr byte to find the writer.
-- Target HW OAM entry 6 (tile 0x44 body) attr byte = 0xFE00 + 6*4 + 3 = 0xFE1B.
-- Also watch the live DMA-source buffer attr. Log PC of writes.
local STATE = "save_states_for_claude/level1_sara_w_gargoyle_mini_boss.ss0"
local OUT   = "/tmp/miniboss/gargoyle_watch.log"
local function log(m) local h=io.open(OUT,"a"); if h then h:write(m.."\n");h:close() end end
do local h=io.open(OUT,"w"); if h then h:write("watch\n");h:close() end end
local f=0; local loaded=false; local wpset=false; local hits=0
local function rd(a) return emu:read8(a) end

callbacks:add("frame", function()
  f=f+1
  if not loaded then emu:loadStateFile(STATE); loaded=true; return end
  if f < 120 then return end
  if not wpset then
    -- try to set write watchpoints on shadow buffer attr bytes for gargoyle body
    -- buffer1 e06 attr = 0xC000+6*4+3 = 0xC01B ; buffer2 = 0xC11B
    local ok1 = pcall(function()
      emu:setWatchpoint(function(addr, val, prev)
        if hits < 60 then
          local pc = 0
          pcall(function() pc = emu:read16(0) end) -- placeholder
          log(string.format("WP write addr=%04X val=%02X", addr, val))
          hits = hits + 1
        end
      end, 0xC01B, 2)  -- 2 = write
    end)
    log("setWatchpoint(C01B) ok="..tostring(ok1))
    wpset = true
    return
  end
  if f > 135 then return end
end)
