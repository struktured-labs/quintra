# PROGRESS: basilisk tiers + bigger bombs (PR #147)

Branch: feat/basilisk-bombs. Spec: docs/superpowers/specs/2026-11-18-basilisk-and-bigger-bombs.md

## Done
- GPT Image 2.6 (gpt-image-2.6-sunburst) art for 3 tiers x idle/walk/fire, plus a 4-frame blast sheet. Quantized to 4-colour 32x32 sprites and 16x16 blast quadrants (scripts/gen_basilisk_art.py, basilisk_art_grids.json).
- Ley/Sun/Nox Basilisk (ids 40/42/43) with 16/24/32-px beams, placed in Ember, Temple and Void.
- Ghost-lane tell, then a one-upload flip to the beam.
- Fuse Hurler: 32x32 burst, debris, shake 3/14, new boom SFX, r18 hitbox while the fireball is drawn, edge markers (including for the self-burst).
- Carbon review applied (spec §6).
- Local results:
  - layout OK, home 0x3D02, bank 25 has 2442 bytes free
  - perf 180/172/169
  - test_new_game_start OK
  - test_leybeam and test_fuse_hurler pass

## Remaining
- CI green, then squash-merge. No deploy.

## Known pre-existing (not this PR)
- make_stage_states sanctuary marked_gate fails locally on main too.
- test_enemy_identity's static check `tiles_load_dread_bell_sprite in room_source` fails on main.
- enemy_is_big16 omits Bane Brute and Vault Hand.
