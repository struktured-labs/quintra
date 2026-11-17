# Riftwild tile tidy and declutter (2026-11-17)

## Feedback
- "rift wild overworld tiles need work some tiles look like its part of a
  larger tile set and looks awkward"
- "in general the overworld feels too crammed and busy want a cleaner feel"
- "i like the walk in the water animation tho": the water ride (Tide Raft OAM
  36-38, bank-1 OBJ 0-9, ripple ring; 2026-11-15-water-ride.md) is untouched.

## Audit (before, seed 1234abcd, all 36 Waking fields)
`scripts/riftwild_tile_audit.py` walks every field over real seams headless,
then reads the BG map, attributes and palettes from VRAM.

| metric | before | after (3 seeds) |
|---|---|---|
| orphan 2x2 quarters | 4591 (~127/field) | 0 |
| open floor mean / min | 83.7% / 77.5% | 85.8-86.1% / ≥79% |
| prop clusters per field | 15.1 | 6.0-6.7 |
| one/two-cell props per field | 11.8 | 1.8-2.9 |
| ground cells carrying a mark | 100% | ~13% |
| Hollow props / singles | 37.8 / 34.2 | 10.0 / 5.6 |

Fragment causes:
1. Trees and crags render as 2x2 canopies/peaks chosen only by x/y parity.
   Single trees from procgen, the field rim, diamond `stamp_land` edges and
   one-tile walls each drew a lone quarter: half a crown or a cut ridge.
2. Each BG palette slot had its own colour 0, so any prop in another slot
   (flowers, shore, stumps, shards, path) sat in a dark 8px box.
3. The water/sinkhole autotile drew only an NW corner on one-tile tips and
   channels.
4. Hollow converted water to a water/reed checkerboard (a corner on every cell).
5. The dungeon crystal block was drawn in the open field.

Clutter causes: every ground tile was textured (sand bricks, snow flecks,
water waves, path zigzag, grass tufts on 1/4 of cells); scatter placed 3-6
clumps plus single stones/stumps; the shard meadow piece and the zone-2 stone
lattice.

## Design
- **Metatile bitmap** (`rw_block_ok`, 32 bytes WRAM): bit per aligned 2x2
  block that is a whole tree or crag. `riftwild_meta_scan()` runs after the
  final terrain write (full draw in `tiles_prepare_wide_field`, and seam step
  0 via `riftwild_seam_step`). The dress pass draws quarters only in whole
  blocks; any other tree/crag cell draws the self-contained `tree_lone` /
  `crag_lone` tile. A tree burned at runtime clears its bit and redraws the
  surviving cells as lone trees (`riftwild_tree_burned`).
- **Tidy pass** (`riftwild_tidy_field`, ordinary and fixture fields, before set
  pieces): erode incomplete interior tree/crag blocks to ground. Cells only
  ever become walkable, so routes only widen. Cells next to capability gates
  (100-104) and portals are pinned, and so is the Riftwell trader's counter
  tree (16, 4), which stops a player walking up to talk. Rim blocks,
  landmarks, cave entrances (CAVE-STONE / BLAST / THICKET) and fixtures
  written after the pass are kept. Water/sinkhole tips and one-tile channels
  are drawn with the shore set rather than pruned: a pruning scan cost about
  5 frames per field build.
- **Build cost**: field entry stays within 3 frames of main (74 vs 71 frames
  from the boss exit). The tidy and set-piece passes read cells through
  per-row pointer tables instead of 2-D index arithmetic, and `fits()` walks
  row pointers. Scatter never overdraws a placed stamp (a grove written over
  a column stamp left stamp art on tree cells).
- **Shared ground colour**: in world mode every BG slot 0-4 takes the zone
  ground slot's colour 0 (snow: crystal slot, sand: door slot, else floor),
  so props sit directly on the earth. N/S seams reload palettes at slide
  step 8.
- **Shore set**: lone, N/W cap (flips cover S/E) and H/V strait tiles for
  water and sinkholes. The sinkhole has a colour-0 shadowed lip so it reads
  as sunken.
- **Hollow reeds**: a water cell becomes reeds only with exactly one land side
  and two open-water cells behind it, giving a coherent fringe; swimmable
  channels never thin below two tiles.
- **Declutter**: scatter places 1-2 clusters (4x2 / 4x4) and no single stones
  or stumps. The shard meadow piece is dropped from the large-piece library,
  and the zone-2 second mass is crags. Climate grounds and trails are flat;
  seeded marks land on about 1 cell in 8. Snow trails use the earth (door)
  slot so they never read as water.
- **Art**: 16x16 tree and crag metatiles plus quieter ground, refreshed with a
  GPT-image reference sheet and hand-quantised to 2bpp in
  `scripts/gen_riftwild_art.py`. `riftwild_art.c` is pinned to bank 21 and
  `riftwild_tidy.c` to bank 20, since autobank placed them in near-full banks
  and broke the 256-byte floor.

## Test
`scripts/test_riftwild_tiles.py` covers seeds 1234abcd, 00c0ffee and 7e57beef
(Waking) plus 1234abcd Hollow, all 36 fields each. It requires:
- 0 orphan quarters;
- BG colour 0 identical across slots 0-4;
- open floor ≥ 78% per field and ≥ 85.5% mean;
- prop clusters ≤ 9 (Hollow ≤ 14) and one/two-cell props ≤ 4 (Hollow ≤ 9);
- marked ground ≤ 25%.

The baseline ROM fails every check.
