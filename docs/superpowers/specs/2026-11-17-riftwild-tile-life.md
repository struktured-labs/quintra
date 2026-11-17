# Riftwild tile life (follow-up to the tile tidy)

Feedback on PR #130 (tile tidy): "Generally an improvement if maybe almost
too sanitary. The light green path is arguably worse."

## Kept from the tidy pass

- Zero orphan 2x2 quarters; trees and crags are whole metatiles or the
  complete lone tiles.
- One shared BG colour 0 across palette slots 0-4.
- The water_ride animation is unchanged.

## Middle-ground density

- Ground marks grow in clumps. A seeded 2x2-block hash (per-axis tables
  `rw_cx`/`rw_cy`, odd block rows staggered by a cell so the clumps never
  line up in a grid) picks about 6 in 16 blocks. Inside a picked block, 3 of 4
  cells carry a mark, and a stray sprig lands on about 1 in 32 other cells.
  That works out to about 21% of ground cells marked in the Waking and about
  19.5% in the Hollow (roughly 1 in 5), up from 12-13%. A clump's look is either tufts (two art variants, one of them
  off-centre) or pebbles with small flowers. Half the cells swap within the
  pair, so a clump is mixed rather than stamped. Snow, sand and mud use
  their two climate marks the same way.
- Scatter tries three or four small clusters per field (a 2x2 metatile, a
  4x2 pair or a 4x4 grove/ridge/flower patch; two to four land), plus three
  or four complete standalone props (a lone bush, rock or stump), up from
  1-2 clusters and no singles.
- Open floor averages 85.3-85.7% in the Waking and 84.6-84.9% in the
  Hollow, against 85.5-86.1% after the tidy and 83.1-83.9% originally.

## Worn-earth trails

- Trails draw in the door/earth slot in the Waking for every climate: tan
  dirt with darker grit, readable on dark grass, snow and sand alike. In the
  Hollow they use the muted floor slot, because its door and crystal slots
  are the loud void-cyan and magenta landmark colours.
- A trail cell picks an edge piece from its N/S/W/E neighbours: mid,
  N-edge, W-edge, corner, or one-tile horizontal or vertical strait. Flips
  give the other sides, and edges flip again by hash so the fray never
  repeats. A neighbour outside the field counts as trail, so mouths run on
  seamlessly. The edge frays into colour 0 with an irregular dark lip,
  instead of the old hard light-green stripe.
- Trails stay on the dress fast path. `trail_run()` dresses a whole stretch
  of consecutive trail cells in one call. It takes the two along-line
  neighbours from the line itself and the two across-line neighbours from
  row pointers prepared once per line. Ground marks are one 256-byte lookup
  (`rw_mk`).
- Cost: `fits()` now uses a classification lookup, which saves about 3
  frames of scatter, so field entry is level with main (the
  test_riftwild_landmarks camera settles in 62 frames on both). A full
  redraw (for example after closing a dialogue) is about 1.5 frames slower.
  test_riftwild_polish now waits 10 frames after closing a dialogue before
  the next approach.

## Banks

- The new art ids are 92-98, in the bank-1 piece range clear of Hexa (40-55)
  and the Sun Lattice (56-62).
- `riftwild_discovery.c` moved from bank 19 to bank 20 to keep bank 19 above
  the 256-byte floor.

## Test

`scripts/test_riftwild_tiles.py` still requires 0 fragments and a shared
colour 0. It now checks:

| Measure | Limit |
|---|---|
| Open-floor mean | 83.5-87% |
| Per-field open-floor minimum | 77.5% |
| Prop clusters per field (Waking / Hollow) | at most 12 / 16 |
| One/two-cell props per field (Waking / Hollow) | at most 7 / 11 |
| Marked ground | 15-32% |
