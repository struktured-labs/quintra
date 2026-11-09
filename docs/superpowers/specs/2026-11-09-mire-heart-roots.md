# Mire Heart root attack

Owner-approved hybrid from the Argon design and comparison. Timing is in
game updates, not LCD frames.

## Slot check (before reuse)

`BGT_COLOSSUS_VOID`..`BGT_COLOSSUS_HORN` (tiles 55..63) are loaded for stage 4
by `tiles_load_colossus_bg`. They are not on the live map:

- `tiles_paint_mire_projection` has no callers.
- `tiles_prepare_crystal_wide_arena` skips the far-chamber body when
  `bosses_beaten % 9 == 4`.
- A headless boot of the Mire arena (`scripts/test_colossal_mire.py` on the
  previous ROM) found 0 of those tile ids in `room_tilemap`.

The nine slots are therefore free to replace. Root art overwrites the unused
`bgt_mire_*` bytes. `room_tilemap` is never written, so walking and player
shots still see floor.

## Cast

Every phase, including the opening, the phase clock runs 0..255. The cast
occupies clocks 1..96 (96 updates):

| u (clock - 1) | Updates | What |
|---|---|---|
| 0..47 | 48 | Anchored. Lobes contract/flash. No damage. |
| 8..47 | 40 | Full ghost path of the cells that will erupt. |
| 48..71 | 24 | Six growth steps, 4 updates each. New cells hurt. |
| 72..87 | 16 | Hold. |
| 88..95 | 8 | Harmless wither, then the floor is restored. |

The hollow ring moves to clocks 112..144 (lock 112, resolve 144), after the
roots are gone. Summons stay at 160 and 192. A phase change or an armed
Miasma Bloom clears the roots first.

## Shape

Four branches. Variants 0 and 2 are cardinal; 1 and 3 are diagonal (2 and 3
are a 90 degree turn of 0 and 1). Each branch is four connected inner tiles,
then two empty tiles (~16 px), then two outer fork tiles. The empty tiles are
never ghosted and never armed.

At the lock, if the player's neighborhood has no 3-tile safe walk, the cast
rotates, then drops the branch in that quadrant, then fizzles if fewer than
two branches remain. The chosen cells stay fixed for the cast.

Collision tests the player's center and feet corners against the painted
band of that cell only (horizontal/vertical rows or columns 2..5, diagonals
within 1 px of the centerline). Kind 0 (ghost and wither) does not hurt.
Damage is `hurt(2)` (1 on Easy), 45 iframes, no shove.

## Suspend

The variant and a 2-tick timer live in the Mire's `ai_data[4]` (unused by its
volley). A new room or a boss kill clears the overlay. If that byte is set
but the static cast was lost and the preview had already started (`u >= 8`),
the cells are rebuilt from the stationary boss. An earlier windup cancels.
