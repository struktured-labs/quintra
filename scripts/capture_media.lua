-- Quintra media capture for the README: discrete screenshots at key screens
-- plus a burst of consecutive gameplay frames to assemble into a GIF.
-- Driven by game state (room counter via QUINTRA_RS_ADDR) like the smoke
-- harness, so it survives code-size timing drift.

local OUT  = os.getenv("QUINTRA_MEDIA_DIR") or "/tmp/quintra-media"
local RS   = tonumber(os.getenv("QUINTRA_RS_ADDR") or "0") or 0
local PL   = tonumber(os.getenv("QUINTRA_PL_ADDR") or "0") or 0
local EN   = tonumber(os.getenv("QUINTRA_EN_ADDR") or "0") or 0
local TM   = tonumber(os.getenv("QUINTRA_TM_ADDR") or "0") or 0
local PZ   = tonumber(os.getenv("QUINTRA_PZ_ADDR") or "0") or 0
local DIRECTOR = tonumber(os.getenv("QUINTRA_DIRECTOR_ADDR") or "0") or 0
local WORLD_W = tonumber(os.getenv("QUINTRA_WORLD_WIDTH_ADDR") or "0") or 0
local WORLD_H = tonumber(os.getenv("QUINTRA_WORLD_HEIGHT_ADDR") or "0") or 0
local CAMERA_X = tonumber(os.getenv("QUINTRA_CAMERA_X_ADDR") or "0") or 0
local CAMERA_Y = tonumber(os.getenv("QUINTRA_CAMERA_Y_ADDR") or "0") or 0
local LARGE = tonumber(os.getenv("QUINTRA_LARGE_ADDR") or "0") or 0
local TOPOLOGY = tonumber(os.getenv("QUINTRA_MEDIA_TOPOLOGY") or "6") or 6
local BOSS1, SHOP1, SANCTUARY1, TOWN1, STAGE3_SIGIL, COMPASS_ROOM, FINAL_BOSS
if TOPOLOGY >= 30 then
  BOSS1, SHOP1, SANCTUARY1 = 19, 17, 18
  TOWN1, STAGE3_SIGIL, COMPASS_ROOM, FINAL_BOSS = 63, 43, 26, 220
elseif TOPOLOGY >= 20 then
  BOSS1, SHOP1, SANCTUARY1 = 13, 11, 12
  TOWN1, STAGE3_SIGIL, COMPASS_ROOM, FINAL_BOSS = 45, 31, 18, 154
elseif TOPOLOGY >= 16 then
  BOSS1, SHOP1, SANCTUARY1 = 9, 7, 8
  TOWN1, STAGE3_SIGIL, COMPASS_ROOM, FINAL_BOSS = 33, 23, 14, 118
elseif TOPOLOGY >= 12 then
  BOSS1, SHOP1, SANCTUARY1 = 6, 4, 5
  TOWN1, STAGE3_SIGIL, COMPASS_ROOM, FINAL_BOSS = 24, 17, 11, 88
else
  BOSS1, SHOP1, SANCTUARY1 = 6, 4, 5
  TOWN1, STAGE3_SIGIL, COMPASS_ROOM, FINAL_BOSS = 19, 15, 11, 54
end
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
local STAGE_START, STAGE_BOSS
if TOPOLOGY >= 30 then
  STAGE_START = {0,20,41,64,87,111,137,163,191}
  STAGE_BOSS = {19,40,62,86,110,135,162,190,220}
elseif TOPOLOGY >= 20 then
  STAGE_START = {0,14,29,46,62,79,98,116,135}
  STAGE_BOSS = {13,28,44,61,78,96,115,134,154}
else
  STAGE_START = {0,10,21,34,46,59,74,88,103}
  STAGE_BOSS = {9,20,32,45,58,72,87,102,118}
end
local function stage_for_room(target)
  for i=9,1,-1 do
    if target >= STAGE_START[i] then return i - 1 end
  end
  return 0
end
local function cell_xy(cell)
  local width = (TOPOLOGY >= 30) and 6 or ((TOPOLOGY >= 20) and 5 or 4)
  local row, offset = math.floor(cell / width), cell % width
  return (row % 2 == 1) and (width - 1 - offset) or offset, row
end
local FOLD_COLS = {
  2,0,5,0, 0,5,5,0, 0,0,5,0, 5,5,5,0,
  2,5,5,0, 0,5,4,0, 0,4,5,0, 0,1,5,0
}
local function fold_col(stage, upper_row)
  local size = STAGE_BOSS[stage + 1] - STAGE_START[stage + 1] + 1
  local fold = emu:read8(RS + 2) ~ emu:read8(RS + 3)
    ~ emu:read8(RS + 4) ~ emu:read8(RS + 5) ~ ((stage * 3) & 255)
  local col = FOLD_COLS[(fold & 7) * 4 + upper_row + 1]
  local lower_first = (upper_row + 1) * 6
  local lower_count = math.min(6, size - lower_first)
  local service_first = size - 3
  if lower_first < service_first then
    lower_count = math.min(lower_count, service_first - lower_first)
  end
  if (upper_row + 1) % 2 == 1 then
    col = math.max(col, 6 - lower_count)
  else
    col = math.min(col, lower_count - 1)
  end
  return col
end
local function graph_connected(a, b, stage)
  if TOPOLOGY < 30 then return b == a + 1 end
  local ax, ay = cell_xy(a)
  local bx, by = cell_xy(b)
  if math.abs(ax - bx) + math.abs(ay - by) ~= 1 then return false end
  if ay == by then return true end
  local upper = math.min(ay, by)
  return (upper == 0 and ax == 1) or ax == fold_col(stage, upper)
end
local function source_for_target(target_local, stage)
  if target_local > 0 and graph_connected(target_local - 1, target_local, stage)
      then return target_local - 1 end
  local size = STAGE_BOSS[stage + 1] - STAGE_START[stage + 1] + 1
  for source=0,size - 1 do
    if graph_connected(source, target_local, stage) then return source end
  end
  error("media target has no generated graph approach")
end
local function enter_room(target)
  -- Deterministic developer-media setup: arrange the current room's real
  -- reciprocal graph doorway, then let the cartridge generate the target. This
  -- avoids a screenshot pilot dying or waiting behind a procedural combat
  -- seal while keeping every pictured target room, palette, actor, and boss
  -- authored and rendered by the live ROM.
  if RS == 0 or PL == 0 or TM == 0 then return false end
  clear_hostiles()
  if PZ ~= 0 then emu:write8(PZ, 0) end
  -- A developer-media deep link rewrites the logical source room before the
  -- next real doorway transaction. Retire the previous room's runtime-only
  -- directive so a WAVE cannot materialize a second pack inside that
  -- synthetic sanctuary source and block its threshold.
  if DIRECTOR ~= 0 then emu:write8(DIRECTOR, 0) end
  if target == TOWN1 then
    -- A village is entered through the post-boss Riftwild gate, never by
    -- incrementing a dungeon corridor.
    emu:write8(RS + 1, STAGE_BOSS[3])
    emu:write8(RS + 11, 3)
    emu:write8(RS + 17, 1)
    -- The third return in the 6x6 regional Riftwild wakes gate 34. The old
    -- media fixture still used pre-expansion screen 12, which is ordinary
    -- grass now and therefore waited forever before the village reel beat.
    emu:write8(RS + 18, (TOPOLOGY >= 30) and 34 or 6)
    emu:write8(RS + 19, 0)
    emu:write8(TM + 8 * 20 + 10, 34)
    put16(PL + 9, 72); put16(PL + 11, 52)
    for _=1,90 do
      emu:runFrame()
      if room() == target and emu:read8(RS + 17) == 0 then break end
    end
    tick(50)
    return room() == target
  end
  local stage = stage_for_room(target)
  local target_local = target - STAGE_START[stage + 1]
  local source_local = source_for_target(target_local, stage)
  local sx, sy = cell_xy(source_local)
  local tx, ty = cell_xy(target_local)
  local key, px, py, door1, door2
  -- Media deep-links replace only the logical source. Normalize the retained
  -- live field too; otherwise a 248px source still waits for its far boundary
  -- while this fixture stamps and approaches the compact reciprocal door.
  if LARGE ~= 0 then emu:write8(LARGE, 0) end
  if WORLD_W ~= 0 then emu:write8(WORLD_W, 160) end
  if WORLD_H ~= 0 then emu:write8(WORLD_H, 136) end
  if CAMERA_X ~= 0 then emu:write8(CAMERA_X, 0) end
  if CAMERA_Y ~= 0 then emu:write8(CAMERA_Y, 0) end
  emu:write8(0xFF43, 0); emu:write8(0xFF42, 0)
  if ty < sy then
    key, px, py, door1, door2 = KEY_UP, 72, 0, 9, 10
  elseif tx > sx then
    key, px, py = KEY_RIGHT, 144, 60
    door1, door2 = 8 * 20 + 19, 9 * 20 + 19
  elseif ty > sy then
    key, px, py = KEY_DOWN, 72, 120
    door1, door2 = 16 * 20 + 9, 16 * 20 + 10
  else
    key, px, py = KEY_LEFT, 0, 60
    door1, door2 = 8 * 20, 9 * 20
  end
  emu:write8(RS + 11, stage)
  emu:write8(RS + 1, STAGE_START[stage + 1] + source_local)
  emu:write8(RS + 6, 0xFF)
  emu:write8(TM + door1, 3); emu:write8(TM + door2, 3)
  put16(PL + 9, px); put16(PL + 11, py)
  for _=1,90 do
    emu:setKeys(key); emu:runFrame()
    if room() == target then break end
  end
  emu:setKeys(0); tick(50)
  return room() == target
end

local function enter_dungeon_portal(target, stage)
  -- A cross-stage media cut cannot safely reinterpret the retained 248x248
  -- field as a different dungeon's compact predecessor. Use the same gate
  -- transaction as an organic Riftwild entry: begin_dungeon(), increment the
  -- counter, then let procgen author the complete requested destination.
  clear_hostiles()
  if PZ ~= 0 then emu:write8(PZ, 0) end
  if DIRECTOR ~= 0 then emu:write8(DIRECTOR, 0) end
  emu:write8(RS + 1, target - 1)
  emu:write8(RS + 11, stage)
  emu:write8(RS + 6, 0xFF)
  emu:write8(RS + 17, 1)
  if TOPOLOGY >= 30 then
    -- Regional gates are 8/21/34. bosses_beaten (stage here) selects the
    -- same current-region step as regional_riftwild.c; old media used screen
    -- 6, which became an ordinary field when the overworld grew to 6x6.
    local step = (stage == 0) and 0 or ((stage - 1) % 3)
    local gates = {8, 21, 34}
    emu:write8(RS + 18, gates[step + 1])
  else
    emu:write8(RS + 18, 6)
  end
  emu:write8(RS + 19, 0)
  -- Use the lower center apron rather than (10,8). A generated mission can
  -- make the prior room a paired phase-switch chamber, whose live update
  -- correctly owns the exact center tile and would replace a synthetic gate.
  emu:write8(TM + 9 * 20 + 10, 34)
  put16(PL + 9, 72); put16(PL + 11, 60)
  for _=1,150 do
    emu:runFrame()
    if room() == target and emu:read8(RS + 17) == 0 then break end
  end
  tick(50)
  return room() == target and emu:read8(RS + 17) == 0
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
  tick(110); frame(0, 30, 3)                 -- five-spirit title animation
  hold(KEY_START, 2); tick(20); frame(KEY_DOWN, 12, 2)
  frame(KEY_UP, 8, 2); hold(KEY_A, 2); tick(50)

  -- The first action scene is a generated 248x248 WAVE court. Pin only the
  -- low seed byte needed for that deterministic director signature, enter
  -- through its real graph edge, and let the cartridge author every enemy,
  -- label, formation, camera, and attack shown in the release reel.
  emu:write8(RS + 2, 7)
  if not enter_room(STAGE_START[1] + 4) then
    error("media could not enter stage-one WAVE court")
  end

  put16(PL + 9, 192); put16(PL + 11, 160); tick(24)
  local seq = {
    {KEY_A|KEY_RIGHT, 8}, {KEY_A|KEY_DOWN, 8},
    {KEY_B|KEY_LEFT, 8},
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

  -- Show the current abstract Compass after the live WAVE beat. Fully
  -- explored fixtures keep the semantic landmarks legible in a short reel
  -- without pretending this developer-media setup is organic progression.
  if PL ~= 0 then emu:write8(PL + 2, 12) end
  tick(20)
  local prior_room = room()
  emu:write8(RS + 1, BOSS1 - 1); emu:write8(RS + 20, 0xFF)
  if TOPOLOGY >= 12 then emu:write8(RS + 29, 0x01) end
  hold(KEY_SELECT, 2); tick(30); frame(0, 24, 2); hold(KEY_B, 2); tick(20)
  emu:write8(RS + 1, prior_room)

  -- Enter the real opening colossus through a live door and spend the reel's
  -- main action beat on its screen-scale BG body + vulnerable OBJ heart.
  put16(RS + 23, (emu:read8(RS + 23) | (emu:read8(RS + 24) << 8)) | 1)
  emu:write8(RS + 27, emu:read8(RS + 27) | 0xC9)
  emu:write8(RS + 28, emu:read8(RS + 28) | 0x84)
  if not enter_room(BOSS1) then error("media could not enter stage-one boss") end
  -- Hold the firing lane for the reel. The boss still animates and attacks,
  -- while avoiding needless whole-sprite churn in every GIF delta frame.
  frame(KEY_A, 64, 2)

  -- Stage-one boss is already beaten for this edit; leaving the boss room
  -- performs the real runtime handoff into overworld screen zero.
  emu:write8(RS + 1, BOSS1); emu:write8(RS + 11, 1)
  warp(72, 120); frame(KEY_A|KEY_RIGHT, 20, 2)
  warp(232, 60); frame(KEY_RIGHT, 12, 2)      -- Riftwild 0 -> 1
  warp(232, 60); frame(KEY_A|KEY_DOWN, 16, 2) -- Riftwild 1 -> 2
  warp(72, 232); frame(0, 8, 2)              -- short route -> gate 8
  -- Let the reel itself prove the expanded 6x6 route appears on the compact
  -- Riftwild graph while preserving the established segment budget.
  hold(KEY_SELECT, 2); tick(30); frame(0, 16, 2)
  hold(KEY_B, 2); tick(20)

  -- The public reel used to jump from Riftwild straight to the ending, which
  -- made the real three-screen village easy to mistake for an unimplemented
  -- roadmap item. Enter the first arrival square through its ordinary room
  -- threshold and spend the recovered twelve-frame budget on the live civic
  -- label, path, houses, and residents. No village tiles or actors are mocked.
  emu:write8(RS + 17, 0); emu:write8(RS + 18, 0); emu:write8(RS + 19, 0)
  emu:write8(RS + 11, 2)
  if not enter_room(TOWN1) then error("media could not enter first village") end
  emu:write8(RS + 11, 3)
  frame(KEY_RIGHT, 24, 2)

  -- Close on the real three-tableau ending. State setup skips eight stages
  -- for capture speed; room_tick, victory_enter, animation, and rendering are
  -- all cartridge code (the victory regression independently proves SRAM).
  emu:write8(RS + 1, FINAL_BOSS)
  emu:write8(RS + 10, 1)
  emu:write8(RS + 11, 9)
  tick(8)
  frame(0, 456, 12)

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

-- Enter a deterministic WAVE court, then photograph the true 248x248
-- district from its southeast camera bound. The media setup chooses a seed
-- signature and graph edge; the live cartridge authors the pictured event.
hold(KEY_A, 2); tick(60)
emu:write8(RS + 2, 7)
if not enter_room(STAGE_START[1] + 4) then
  error("media could not enter stage-one WAVE court")
end
put16(PL + 9, 192); put16(PL + 11, 160); tick(30)
shot("shot_dungeon")

-- Pack / stats screen (stage name, loadout, run clock)
hold(KEY_START, 2); tick(30); shot("shot_pack")
hold(KEY_B, 2); tick(20)

-- Current dungeon Spirit Compass, including the discovered nonlinear rift
-- edge used from dungeon two onward.
local prior_room = room()
local prior_bosses = emu:read8(RS + 11)
emu:write8(RS + 11, 1); emu:write8(RS + 1, COMPASS_ROOM); emu:write8(RS + 20, 0x1F)
hold(KEY_SELECT, 2); tick(30); shot("shot_compass")
hold(KEY_B, 2); tick(20)
emu:write8(RS + 1, prior_room); emu:write8(RS + 11, prior_bosses)

-- The outdoor Compass is a different information design, not a palette swap
-- of the dungeon snake. Show a real partially explored graph with its distant
-- vault hop and in-cartridge YOU/GATE/RIFT/BOSS legend.
local prior_world_mode = emu:read8(RS + 17)
local prior_world_screen = emu:read8(RS + 18)
local prior_seen_lo = emu:read8(RS + 21)
local prior_seen_hi = emu:read8(RS + 22)
emu:write8(RS + 17, 1); emu:write8(RS + 18, 6)
emu:write8(RS + 21, 0x47); emu:write8(RS + 22, 0x80)
hold(KEY_SELECT, 2); tick(30); shot("shot_riftwild_map")
hold(KEY_B, 2); tick(20)
emu:write8(RS + 17, prior_world_mode)
emu:write8(RS + 18, prior_world_screen)
emu:write8(RS + 21, prior_seen_lo); emu:write8(RS + 22, prior_seen_hi)

-- The remaining gallery deep-links now enter through real 6x6 Riftwild gate
-- tiles. They replace the logical source and position atomically, so the
-- retained 248x248 court does not need an obsolete compact-room detour.

-- Shop (room 7): wares + amber price tags
if not enter_dungeon_portal(SHOP1, 0) then error("media could not enter shop") end
tick(30); shot("shot_shop")
-- The shop owns a modal input loop; leave it before asking the world driver to
-- perform the sanctuary doorway transaction.
hold(KEY_B, 2); tick(20)

-- Sanctuary (room 8): shrine pylons
if not enter_room(SANCTUARY1) then error("media could not enter sanctuary") end
tick(30); shot("shot_sanctuary")

-- First village arrival: outdoor civic square, houses, residents, and label.
emu:write8(RS + 17, 0); emu:write8(RS + 18, 0); emu:write8(RS + 19, 0)
emu:write8(RS + 11, 2)
if not enter_room(TOWN1) then error("media could not enter village still") end
emu:write8(RS + 11, 3)
tick(45); shot("shot_village")

-- Stage boss (room 9): giant + HUD bar mid-fight
emu:write8(RS + 11, 0)
put16(RS + 23, (emu:read8(RS + 23) | (emu:read8(RS + 24) << 8)) | 1)
emu:write8(RS + 27, emu:read8(RS + 27) | 0xC9)
emu:write8(RS + 28, emu:read8(RS + 28) | 0x84)
if not enter_room(BOSS1) then error("media could not enter stage-one boss") end
tick(50)                       -- entry drama resolves, boss opens fire
hold(KEY_A|KEY_UP, 40)         -- trade some shots for the action shot
shot("shot_boss")

-- Finish on a deeper stage's look. A cross-stage regional-gate transaction
-- rebuilds the mission graph and Law for Ember Depths, but returning from that
-- synthetic media deep-link no longer represents a valid runtime transition.
-- Keeping it last makes every prior still independent of that terminal setup.
if RS ~= 0 then
  if not enter_dungeon_portal(STAGE3_SIGIL, 2) then
    error("media could not enter Ember room")
  end
  tick(60); shot("shot_ember")   -- fade-in resolves first
end

console:log("MEDIA CAPTURE DONE shots")
emu.frontend:quit()
