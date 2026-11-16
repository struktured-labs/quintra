# GPT Image 2.6 pass: Serpent, Kilnback/Cinder Rex, Rope; plated Serpent tail

Date: 2026-11-15. Follows the hero/Sentinel, Hexa, mini-boss, monster and
Facet Ram passes (#64, #68, #80, #81, #83, #84, #90).

## Art

Three `gpt-image-2.6-sunburst` edits (2 candidates each, medium quality) of
the upscaled shipped art, then hand-reduced to the existing grids, indices and
palettes:

| Target | Grid | Change |
|---|---|---|
| Serpent (stage 2 boss) hood | 32x24, Verdant boss OBJ | Storm cobra: lightning bolts down both flares, arrow crest, slanted eyes under a heavy brow, forked tongue |
| Serpent open jaw (bank 1, 128..139) | 32x24 | Same hood with the jaws gaping: two long fangs over a dark throat |
| Serpent coil (BG 55..63, slot 6) | 9 edge-aware 8x8 tiles | Each cell is an armoured shield plate (yellow rim, magenta face, violet seam) |
| Kilnback (stage 3 pack) | 4 x 16x8 | Walking crucible with an iron grate; heat only shows when the vent blows its lid |
| Cinder Rex (stage 3 boss) | 32x16 + roar/stride pose | Iron-jawed furnace hound with dorsal heat spikes, a barred furnace grate on the flank and a slag-hammer tail |
| Rope (snake enemy) | 8x8 A/B | Coiled viper with a raised head, yellow eye and belly; frame B flicks the tongue |

Same tiles, OAM counts, palette slots and poses as before: the Serpent is
still 12 hood sprites (bank-0 closed, bank-1 open), Rex still 8 sprites with
per-row roar/stride from bank 1, Kilnbacks 2 sprites each.

## Plated tail

The coil cells now stop the player's attacks. `serpent_tail_blocks()` runs
once per live player projectile while the Serpent is in the room. It is an
O(1) lookup of the shot centre in the drawn coil bitmap (`serpent_body_cells`),
so there is no per-segment loop. On a block the shot is retired with an impact
spark, a metallic clink (a lower, heavier one for blades) and a white flash
of the coil palette. Melee arcs (Wolfkin claw, swords, spears, flail,
Morningstar) are deflected the same way.

Fairness:

- Only the hood takes damage. Anything that lands on the drawn 32x24 hood is
  never blocked, even where the neck plates sit under it.
- The tail trails the head, so the hood stays open from the front and sides.
- After every storm charge the Serpent unwinds to the corners (state 2). The
  plates go slack (dull grey palette) and shots pass straight through. This is
  the clear opening, and it lasts most of the late cycle.
- The palette is the telegraph: magenta plates mean shielded, grey means
  open, and white flashes on a block.

Exceptions: Rift Bombs and splash bursts are area damage, so the tail
ignores them. The hookshot is a tool. Max-Will signatures (Howl, Moonfang
wave, Tide Vortex) and Spirit Convergence chords cut through the plates and still respect
the existing boss caps.

Code: `src/game/serpent_shield.c` (pinned to bank 17), one check in
`combat.c`, and a palette tick from `serpent_tail_update`.

## Verification

- `cargo test` (33) passes, including the jaw/Rex/atlas golden checks.
- `[layout] OK`: bank 3 has 303 B free and bank 8 has 439 B. Every bank is
  above the floor.
- New `scripts/test_serpent_tail_shield.py` covers a shot blocked by plates,
  a blade deflected, hood damage while shielded, a Convergence chord and a Tide Vortex carrier passing
  and the slack window passing. It also checks the plated, flash and slack
  palettes.
- Existing boss tests give the same results as merged main.
- Frame updates in the full-length unwind: 792/1200 before, 787/1200 after.
