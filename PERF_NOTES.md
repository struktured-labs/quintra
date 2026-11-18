# PR #144 progress (2026-11-18, America/New_York)

## test_performance
Measured on the branch ROM at /tmp/q-wizrobe/rom/working/quintra.gbc:

- generated=180, **fixed=172**, dense=169 /180
- floor is still 167 (not lowered); origin/main fixed=171
- last confirmed after the Confusion swirl fix and the Shadow Keep prefix edit

## What landed
- Specialists 35–41 (Veil Magus, Hex Walker, Vault Hand, Bane Brute, Zag Dart, Leybeam, Fuse Hurler), GPT sprites, Leybeam BG shaft
- death_timer=0 in attract_demo_end / run_init_enter is a real hand-back fix; test_new_game_start (after_demo + Continue) passes
- test_magic Thunder ST_STOP passes (arena bumps magic_room_serial; Thunder path ticks once so leftover Convergence is dropped)
- Cartridge kept at 512 KiB: magic.c pinned to bank 31, powerup_extra.c moved to bank 29 (bdc06144). Autobank into bank 32 had padded a 1MB image.
- Confusion swirl on OAM 38 now hides after a cure via BSS flag confusion_swirl_live (f264d611). The 15-crawler roster never sets the flag.
- Stage 0 (Crystal Caverns) restored to main's opening weights. The 165/180 gap was boot-phase / DIV drift from Zag Dart in stage 0, not hook cost. That recovered 172/180.

## CI / what's next
Pushed tip is b86a68df (Shadow Keep prefix through id 27 restored so fixture seed 0xB4A60022 / room 4 still rolls Bramble 27). Specialists in that stage were carved from the id-32 tail: pool is now `(7,28),(5,18),(11,18),(19,15),(22,10),(27,5),(32,2),(35,2),(37,1),(41,1)`.

Run 44281013150: ROM was still in progress (past vignettes, approaching seeded-room fixtures). **Rust already failed** `tests::late_stages_author_one_bounded_rift_cantor_slice` — it requires `id == 32 && w == 6` on late stages. Shrinking Rift Cantor from 6 to 2 in Shadow Keep broke that.

Next: keep id 32 at weight 6 (restore the previous Shadow Keep specialist weights, which already had 32 at 6). Do not steal from the prefix through 27 *or* from Cantor. Instead, find a new Mixed-room seed for `scripts/test_bramble_sprite.py` under the original CDF, or place Vault Hand (required in STAGES[5]) without moving the 89–93 Bramble band and without changing Cantor's 6. Then wait for CI green and squash-merge PR #144.

origin/main was still f1b685f2 at the last fetch. No deploys, no hero-kit edits, no threshold change.

## GIFs (already on the box)
/workspace/quintra-monsters/veil-magus-4x.gif, vault-hand-4x.gif, bane-brute-4x.gif, leybeam-4x.gif, plus hex-walker-4x.gif, zag-dart-4x.gif, fuse-hurler-4x.gif
