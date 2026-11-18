# Stage-transition vignettes

Implements spec PR #123 (`docs/superpowers/specs/2026-11-16-intro-and-stage-vignettes.md`),
stage-transition half. The power-on lore intro and attract mode are in `docs/superpowers/specs/2026-11-17-attract-mode.md`.

## What plays
| id | picture | text | trigger |
|---|---|---|---|
| `VIG_RIFT_WAKING` | `assets/vignettes/riftgate.png` | WAKING RIFTWILD / THE WILD REMEMBERS | the first dungeon to Riftwild entry of a run |
| `VIG_RIFT_HOLLOW` | same picture, `hollow()` palettes | HOLLOW RIFTWILD / THE WILD FORGETS | the first Worldglass shift into Hollow |
| `VIG_STAGE_EMBER` | `assets/vignettes/ember_depths.png` | EMBER DEPTHS / THE KILN WAKES | the first Riftwild to stage 3 entry |
| `VIG_STAGE_CRYSTAL` | `assets/vignettes/crystal_caverns.png` | CRYSTAL CAVERNS / CRYSTALS LISTEN | a new run's stage 1 foyer, or a later town-to-dungeon entry |
| `VIG_STAGE_VERDANT` | `assets/vignettes/verdant_hollow.png` | VERDANT HOLLOW / THE ROOTS HUNGER | the first Riftwild to stage 2 entry |
| `VIG_STAGE_FROST` | `assets/vignettes/frost_vault.png` | FROST VAULT / NOTHING THAWS HERE | the first Riftwild to stage 4 entry |
| `VIG_STAGE_MIRE` | `assets/vignettes/toxic_mire.png` | TOXIC MIRE / A DARK HEART BEATS | the first Riftwild to stage 5 entry |
| `VIG_STAGE_SHADOW` | `assets/vignettes/shadow_keep.png` | SHADOW KEEP / THE GATE WATCHES | the first Riftwild to stage 6 entry |
| `VIG_STAGE_GOLDEN` | `assets/vignettes/golden_temple.png` | GOLDEN TEMPLE / THE SUN NEVER SETS | the first Riftwild to stage 7 entry |
| `VIG_STAGE_BLOODMOON` | `assets/vignettes/bloodmoon.png` | BLOODMOON / THE MOON BLEEDS | the first Riftwild to stage 8 entry |
| `VIG_STAGE_VOID` | `assets/vignettes/void_sanctum.png` | VOID SANCTUM / WHERE NAMES END | the first Riftwild to stage 9 entry |

Each vignette runs about 3 s. It shows a framed picture, the stage name and motto, the class hero walking
in from behind the frame, and one cheap effect: the rift tear plus a white flash, the lava colour cycle,
a crystal palette glint, four falling leaves with a flower palette pulse, snowflakes, a mire heartbeat and bubble cycle, a rising portcullis and torch flicker, a sun ramp, a moon pulse with bats, or drifting void shards with a rift shimmer.
A, B or START skips after 8 frames. Each one plays once per run, tracked by `vignette_seen`, which is
cleared in `run_state_init`.
**PACK → Combat Help (SELECT four times) → LEFT/RIGHT** toggles `CUTSCENES ONCE/OFF`. The setting is stored in SRAM meta
(`META_FLAG_CUTSCENES_OFF`). When a vignette is not played, a Riftwild-to-dungeon entry shows the
existing stage card; a new-run foyer or town-to-dungeon entry keeps the ordinary dim fade.

## How it runs
- `SCREEN_VIGNETTE` reuses the unused `SCREEN_REST_ROOM` slot, so the bank-0 screen table does not grow.
- Art loads in chunks under black palettes with the LCD on, so the load hides inside the fade:
  32 tiles per frame, then 6 map rows per frame.
- The vignette leaves through `room_request_resume()`, the same path PACK, MAP and DIALOG use. That
  path redraws the room's BG tiles and map. The vignette uses only BG slots 0x80-0xFF and 0x40-0x6E
  (175 tiles maximum). It zero-fills the few slots that the resume path leaves alone.
- Exception: the new-run foyer vignette plays from RUN_INIT, before any room exists. It loads the
  champion tiles and class palette itself and exits through a fresh `room_enter` (procgen, spawn,
  stage music), never the resume path. Resuming there left the hero at (0,0) in a blank, silent room.
  `scripts/test_new_game_start.py` guards this for every hero and boot path.
- The champion walks in by alternating its idle pose and its authored stride beat every 8 frames,
  like the room does. It is never mirrored (an H-flip swivelled side-facing heads).
- The player lives in bank 21 with the Crystal Caverns and Verdant Hollow pictures. Bank 20 keeps the Ember/Riftgate pictures, village music, and other fixed residents. Stages 4-6 (Frost, Mire, Shadow) live in bank 22; stages 7-9 (Golden, Bloodmoon, Void) live in bank 23.

## Adding a dungeon
1. Draw a 112x96 picture (6 BG palettes or fewer, about 120 unique tiles) into `assets/vignettes/<name>.png`.
2. Add a `PICTURES` entry in `scripts/gen_vignettes.py` with the name, motto, `stage=`, hero path,
   events and an optional colour cycle. Set `bank=22` or `bank=23` once banks 20-21 are full.
3. Run `python3 scripts/gen_vignettes.py`. It regenerates `src/render/vignette_<name>.c` and
   `vignette_data.h`, including the stage table and dispatch. No code changes are needed for a
   Riftwild-to-dungeon arrival. Town-to-dungeon and the new-run foyer already share that table.
4. When a bank fills up (about 3.5 KB per vignette), change the picture's `bank=` in `PICTURES`.

`scripts/gen_vignettes.py --check` (CI) fails when generated files are stale. Run
`scripts/test_stage_vignettes.py` to play each vignette from the real ROM. It checks skip, play-once,
CUTSCENES OFF and the VRAM restore, and writes GIFs to `builds/vignettes-<sha8>/`.
Other harnesses must call `quintra_vignettes.mute_vignettes()` as soon as `run_state` exists
(during `SCREEN_RUN_INIT`, before `run_init_tick` returns). Waiting until after class-select
settle ticks lets the stage 1 foyer vignette start and breaks timing contracts. `boot_to_stage`
and `mute_after_class_select` already do this. `scripts/quintra_sitecustomize` also mutes
automatically for any PyBoy test unless `QUINTRA_KEEP_VIGNETTES=1`.

## Coverage
All nine dungeon stages plus both Riftwild phases are hooked. Town-to-dungeon and the
new-run foyer share the stage table; Riftwild-to-dungeon arrivals use the same table.
Leaving Riftwild has no extra vignette (the dungeon vignette *is* the leave beat). The
Hexa sanctum stays unannounced.
Vignette-seen bits are per boot: a continue after power-off can replay a vignette once.
