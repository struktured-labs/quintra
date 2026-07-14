-- Quintra media capture for the README: discrete screenshots at key screens
-- plus a burst of consecutive gameplay frames to assemble into a GIF.
-- Driven by game state (room counter via QUINTRA_RS_ADDR) like the smoke
-- harness, so it survives code-size timing drift.

local OUT  = os.getenv("QUINTRA_MEDIA_DIR") or "/tmp/quintra-media"
local RS   = tonumber(os.getenv("QUINTRA_RS_ADDR") or "0") or 0
local PL   = tonumber(os.getenv("QUINTRA_PL_ADDR") or "0") or 0
local EN   = tonumber(os.getenv("QUINTRA_EN_ADDR") or "0") or 0
-- "shots" = discrete screenshots only; "gif" = the frame burst only.
-- Split because per-frame screenshot IO is slow enough under xvfb to
-- starve everything scheduled after the burst.
local MODE = os.getenv("QUINTRA_MEDIA_MODE") or "shots"

local KEY_A=0x01; local KEY_B=0x02; local KEY_SELECT=0x04; local KEY_START=0x08
local KEY_RIGHT=0x10; local KEY_LEFT=0x20; local KEY_UP=0x40; local KEY_DOWN=0x80

local function tick(n) for _=1,n do emu:runFrame() end end
local function shot(name) emu:screenshot(OUT .. "/" .. name .. ".png") end
local function hold(key, frames)
  for _=1,(frames or 4) do emu:setKeys(key); emu:runFrame() end
  emu:setKeys(0); tick(3)
end

local function room() return emu:read8(RS + 1) end
local function walk_to_room(target)
  for _ = 1, 80 do
    if room() == target then break end
    if PL ~= 0 then emu:write8(PL + 2, 12); emu:write8(PL + 15, 60) end
    hold(KEY_DOWN, 20)
  end
  tick(20)
end

if MODE == "gif" then
  -- A compact release-reel: animated lore title, champion select, combat,
  -- then the dungeon -> Riftwild -> nonlinear vault-staircase cadence.
  -- Progression setup uses the same WRAM contract as test_overworld.py;
  -- every pictured transition and animation is still executed by the ROM.
  local gi = 0
  local function frame(key, n, stride)
    for i=1,n do
      emu:setKeys(key or 0); emu:runFrame()
      if (i % (stride or 2)) == 0 then
        gi = gi + 1
        emu:screenshot(string.format("%s/gif_%03d.png", OUT, gi))
      end
    end
    emu:setKeys(0)
  end
  local function put16(p, v)
    emu:write8(p, v & 255); emu:write8(p + 1, (v >> 8) & 255)
  end
  local function clear_hostiles()
    if EN == 0 then return end
    for i=0,31 do
      local p = EN + i * 28
      if emu:read8(p) == 2 then emu:write8(p, 0); emu:write8(p + 1, 0) end
    end
  end
  local function warp(x, y)
    clear_hostiles(); put16(PL + 9, x); put16(PL + 11, y); tick(45)
  end

  tick(110); frame(0, 30, 3)                 -- five-spirit title animation
  hold(KEY_START, 2); tick(20); frame(KEY_DOWN, 12, 2)
  frame(KEY_UP, 8, 2); hold(KEY_A, 2); tick(50)
  local seq = {
    {KEY_A|KEY_RIGHT, 16}, {KEY_A|KEY_DOWN, 16},
    {KEY_B|KEY_LEFT, 10}, {KEY_A|KEY_UP, 16},
  }
  for _,step in ipairs(seq) do
    for _=1,step[2] do
      if PL ~= 0 then emu:write8(PL + 2, 12) end -- keep reel combat readable
      emu:setKeys(step[1]); emu:runFrame()
      gi = gi + 1
      emu:screenshot(string.format("%s/gif_%03d.png", OUT, gi))
    end
  end
  emu:setKeys(0)

  -- Stage-one boss is already beaten for this edit; leaving the boss room
  -- performs the real runtime handoff into overworld screen zero.
  emu:write8(RS + 1, 6); emu:write8(RS + 11, 1)
  warp(72, 120); frame(KEY_A|KEY_RIGHT, 20, 2)
  warp(144, 60); frame(KEY_RIGHT, 12, 2)      -- Riftwild 0 -> 1
  warp(144, 60); frame(KEY_A|KEY_DOWN, 16, 2) -- Riftwild 1 -> cave 2
  warp(72, 52); frame(0, 24, 2)              -- cave 2 -> distant vault 15

  emu:setKeys(0)
  console:log("MEDIA CAPTURE DONE frames=" .. gi)
  emu.frontend:quit()
  return
end

-- ---- MODE == "shots" ----

-- Title (let it pulse a moment)
tick(140); shot("shot_title")

-- Class select — cursor, stats, loadout preview
hold(KEY_START, 2); tick(40); shot("shot_class")
hold(KEY_DOWN, 2); tick(20)
hold(KEY_DOWN, 2); tick(20); shot("shot_class2")
hold(KEY_UP, 2); tick(10); hold(KEY_UP, 2); tick(10)   -- back to Wolfkin

-- Enter the dungeon
hold(KEY_A, 2); tick(60); shot("shot_dungeon")

-- Pack / stats screen (stage name, loadout, run clock)
hold(KEY_START, 2); tick(30); shot("shot_pack")
hold(KEY_B, 2); tick(20)

-- A deeper stage's look: bump bosses_beaten so the NEXT room generates
-- with Ember Depths palettes, shoot it, then restore (must happen before
-- room 6 or the boss gate math changes).
if RS ~= 0 then
  emu:write8(RS + 11, 2)
  walk_to_room(2); tick(60); shot("shot_ember")   -- fade-in resolves first
  emu:write8(RS + 11, 0)
end

-- Shop (room 4): wares + amber price tags
walk_to_room(4); tick(30); shot("shot_shop")

-- Sanctuary (room 5): shrine pylons
walk_to_room(5); tick(30); shot("shot_sanctuary")

-- Stage boss (room 6): giant + HUD bar mid-fight
walk_to_room(6)
tick(50)                       -- entry drama resolves, boss opens fire
hold(KEY_A|KEY_UP, 40)         -- trade some shots for the action shot
shot("shot_boss")

console:log("MEDIA CAPTURE DONE shots")
emu.frontend:quit()
