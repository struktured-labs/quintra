# Wolfkin Will wave

Date: 2026-11-12. Status: **implemented.**

## Problem
Carmelo: when Wolfkin bullrushes at full Will (the Moonfang Rush MAX), it
feels like a big liability with no real upside. He throws himself forward
with a weak hit. He asked for a wild wave of power in front of him that also
works as a shield, and said to build it (2026-11-12). Getting hurt after the
rush because he charged into a monster is fair. Pushing survivors back was
explicitly shelved for later.

## Behavior
- Applies only to Wolfkin's Moonfang Rush, the A MAX he fires with a full
  Will meter at any tier. The other four heroes' MAX arts are unchanged, as
  are Wolfkin's ordinary Fang Stab/Sweep, Howl (B), and the double-tap
  dodge dash, which keeps its own i-frames.
- **Wave.** Alongside the three claw lanes, the rush throws a three-piece
  crescent of force 12px ahead of him. The pieces sit 9px apart
  perpendicular to the rush, with the flanks trailing 4px. Each piece has an
  11x11 hitbox and moves at 4px per tick for 12 ticks, so the wave covers a
  band about 30px wide reaching roughly 4 tiles ahead. Damage is the MAX
  damage +4 for the centre and +3 for the flanks. Each piece pierces 4
  bodies and hits a given body at most once. All pieces carry the MAX
  convergence limiter, so a Colossus is not deleted in one frame.
- **No knockback.** A body that survives a wave hit is not moved: the
  pieces carry `PROJ_FLAG_WILL_WAVE`, which skips the generic 3px hit nudge.
  The claw lanes keep the game's ordinary hit nudge.
- **Frontal guard, during the rush only.** The guard covers the fire tick
  plus the 9-tick body dash. During that time:
  - Hostile shots in his forward 90 degree cone within 28px are eaten.
  - A shot or body that touches him from that cone deals nothing.
  - A body first met from the front stays blocked while he rams through it.
  - The Reaper's warned scythe is not blocked.
  - Sides and back stay fully vulnerable.
- **No blanket i-frames.** The rush used to grant 16 i-frames. That is
  removed. When the dash ends, the guard drops on the next tick and contact
  hurts as usual.
- **Animation.** It uses four new 8x8 OBJ tiles in the free slots 200..203:
  an east-facing `)` crescent, an east-facing crash cel, and the transposes
  of both for vertical rushes. Flip bits mirror them for west and north. The
  pieces swap cels every 3 ticks. For the wave's 14 ticks, OBJ palettes 1
  (hero) and 2 (weapon) flash to the Will meter's violet ramp, then
  `room_refresh_player_appearance` restores both. The tiles are reloaded on
  every cast because the 0x8800 block is shared with menus.

## Code
`src/game/wolfkin_wave.c` is a new file (`#pragma bank 255`, BANKED). The
hooks are: `will_fire_max` (Moonfang branch), `combat_resolve` (tick before
hostile contact, absorb on a touching hostile), `combat_shot_hit.c` (skip
knockback), and `room.c` (the rush's 16 i-frames are removed).

## Evidence
`scripts/test_wolfkin_will_wave.py`. `test_will_max.py` and
`test_will_tiers.py` now count the three crescent pieces in the Moonfang MAX.
