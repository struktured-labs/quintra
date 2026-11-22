# Passable rune boulders stay readable

Status: **in progress.** Issue #172. A Riftwild `BGT_GATE_BOULDER` must look
passable whenever the hero can walk through it: Sauran (`class_id == 1`) or
any hero who owns the Titan Glove. Solid and passable states stay distinct
from each other and from the gold shot-wall (`BGT_WALL_CRACK`).

## Rule

The room tilemap keeps `BGT_GATE_BOULDER` (VRAM slot 100). Collision stays on
`WAYGEAR_TILE_PASSABLE` and does not gain a second map id.

When the hero can pass, a one-time VRAM swap loads the open-boulder art into
slot 100 and the tile uses `BGPAL_CRACK` (the existing gold secret-wall
palette). No new palette is added. The swap runs at dungeon-BG load and again
inside `waygear_grant` if the Glove is picked up mid-room. It has no
per-frame cost.

`BGT_GATE_BOULDER_OPEN` (133) names the open art and is reserved so the
parallel bomb-only wall work (#173) does not claim it. It is never written
into `room_tilemap`.

Color 0 of every Riftwild BG slot is the field's ground, so the open tile
uses color 0 for cracks and hollows, color 1 for dark stone, and colors 2–3
for the gold rune and highlights.

## Approach cue

The first time the hero moves toward a passable boulder in a room, that one
tile does a brief gold shimmer (attribute flash between `BGPAL_CRACK` and
`BGPAL_DOOR`, then settles on `BGPAL_CRACK`). The check reads only the tile
in front of the player. The per-room flag resets on `room_enter`.

There is no field HUD hook for the Titan Glove — the glove icon lives in
the pack — so this change does not add a per-frame HUD pulse.

The first time the hero bumps a boulder they cannot pass (no Glove and not
Sauran), the existing `SFX_REFUSE` two-note nuh-uh plays once. The check
reads only the front tile, and only while a direction is held, so holding
against the rock does not retrigger it every frame. A separate per-room
flag resets on `room_enter`, so a mid-room Glove grant can still shimmer.

## What does not change

Passability, Sauran's innate walk, Glove grant, other waygear gates, secret
gold walls, and Riftwild art slots 0–39 and 64–98 stay as they are. No
full-screen scan runs in the frame loop. Slowdown remains the top
priority: attr choice is a macro, and the approach cue returns immediately
after the room's first shimmer or blocked refuse cue.

## Art

Open-boulder art is generated with GPT Image 2 (`gpt-image-2.6-sunburst`),
quantized to the four `BGPAL_CRACK` colors, and reviewed by Gemini Carbon
against the solid boulder and the gold shot-wall before it is committed.

## Evidence

`scripts/test_boulder_refuse.py` asserts the blocked bump plays `SFX_REFUSE`
once. `scripts/test_new_game_start.py` (including Continue) and the
fixed-roster / dense performance floors (167 / 135) must stay green. Before and after
previews live at 3x scale under `/workspace/quintra-boulder/`.
