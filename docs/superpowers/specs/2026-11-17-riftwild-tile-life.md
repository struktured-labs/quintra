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
  line up in a grid) picks about 5 in 16 blocks. Inside a picked block, 3 of 4
  cells carry a mark, and a stray sprig lands on about 1 in 32 other cells.
  That works out to about 22-24% of ground cells marked (1 in 4-5), up from
  12-13%. A clump's look is either tufts (two art variants, one of them
  off-centre) or pebbles with small flowers. Half the cells swap within the
  pair, so a clump is mixed rather than stamped. Snow, sand and mud use
  their two climate marks the same way.
- Scatter tries three or four small clusters per field (a 2x2 metatile, a
  4x2 pair or a 4x4 grove/ridge/flower patch; two to four land), plus three
  or four complete standalone props (a lone bush, rock or stump), up from
  1-2 clusters and no singles.
- Open floor averages about 85.3% in the Waking and about 84.6% in the
  Hollow, against 85.5-86.1% after the tidy and 83.1-83.9% originally.

## Worn-earth trails

- Trails draw in the door/earth slot in the Waking for every climate: tan
  dirt with darker grit, readable on dark grass, snow and sand alike. In the
  Hollow they use the ground slot, because its door slot is the void-cyan
  landmark colour.
- A trail cell picks an edge piece from its N/S/W/E neighbours: mid,
  N-edge, W-edge, corner, or one-tile horizontal or vertical strait. Flips
  give the other sides, and edges flip again by hash so the fray never
  repeats. A neighbour outside the field counts as trail, so mouths run on
  seamlessly. The edge frays into colour 0 with an irregular dark lip,
  instead of the old hard light-green stripe.
- Trails left the inline dress fast path and now go through `dress_cell`.
  Field build is about +3 frames against main (77 vs 74 in the
  boss-to-overworld probe).

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
