-- Quintra media capture for the README: discrete screenshots at key screens
-- plus a burst of consecutive gameplay frames to assemble into a GIF.
-- Driven by game state (room counter via QUINTRA_RS_ADDR) like the smoke
-- harness, so it survives code-size timing drift.

local OUT  = os.getenv("QUINTRA_MEDIA_DIR") or "/tmp/quintra-media"
local RS   = tonumber(os.getenv("QUINTRA_RS_ADDR") or "0") or 0
local PL   = tonumber(os.getenv("QUINTRA_PL_ADDR") or "0") or 0
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
  -- Boot straight into a run and record the burst, nothing else.
  tick(140)
  hold(KEY_START, 2); tick(40)
  hold(KEY_A, 2); tick(60)
  local gi = 0
  local seq = {
    {KEY_A|KEY_RIGHT, 18}, {KEY_A|KEY_DOWN, 18}, {KEY_A|KEY_LEFT, 18},
    {KEY_A|KEY_UP, 18}, {KEY_B|KEY_RIGHT, 10}, {KEY_A|KEY_DOWN, 16},
    {KEY_RIGHT, 10}, {KEY_A|KEY_UP, 16},
  }
  for _,step in ipairs(seq) do
    local key, frames = step[1], step[2]
    for _=1,frames do
      if PL ~= 0 then emu:write8(PL + 2, 12) end
      emu:setKeys(key); emu:runFrame()
      gi = gi + 1
      emu:screenshot(string.format("%s/gif_%03d.png", OUT, gi))
    end
  end
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
