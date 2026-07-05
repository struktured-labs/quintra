-- Quintra media capture for the README: discrete screenshots at key screens
-- plus a burst of consecutive gameplay frames to assemble into a GIF.

local OUT = os.getenv("QUINTRA_MEDIA_DIR") or "/tmp/quintra-media"

local KEY_A=0x01; local KEY_B=0x02; local KEY_SELECT=0x04; local KEY_START=0x08
local KEY_RIGHT=0x10; local KEY_LEFT=0x20; local KEY_UP=0x40; local KEY_DOWN=0x80

local function tick(n) for _=1,n do emu:runFrame() end end
local function shot(name) emu:screenshot(OUT .. "/" .. name .. ".png") end
local function hold(key, frames)
  for _=1,(frames or 4) do emu:setKeys(key); emu:runFrame() end
  emu:setKeys(0); tick(3)
end

-- Title (let it pulse a moment)
tick(120); shot("shot_title")

-- Class select — cursor + live preview
hold(KEY_START, 2); tick(40); shot("shot_class")
hold(KEY_DOWN, 2); tick(20)
hold(KEY_DOWN, 2); tick(20); shot("shot_class2")

-- Enter the dungeon
hold(KEY_A, 2); tick(50); shot("shot_dungeon")

-- GIF burst: move + fire around the room, one PNG every 2 frames.
local gi = 0
local seq = {
  {KEY_A|KEY_RIGHT, 18}, {KEY_A|KEY_DOWN, 18}, {KEY_A|KEY_LEFT, 18},
  {KEY_A|KEY_UP, 18}, {KEY_B|KEY_RIGHT, 10}, {KEY_A|KEY_DOWN, 16},
  {KEY_RIGHT, 10}, {KEY_A|KEY_UP, 16},
}
for _,step in ipairs(seq) do
  local key, frames = step[1], step[2]
  for _=1,frames do
    emu:setKeys(key); emu:runFrame()
    gi = gi + 1
    emu:screenshot(string.format("%s/gif_%03d.png", OUT, gi))
  end
end
emu:setKeys(0)

-- Pack / stats screen
hold(KEY_START, 2); tick(30); shot("shot_pack")

console:log("MEDIA CAPTURE DONE frames=" .. gi)
emu.frontend:quit()
