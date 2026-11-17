# Stage-transition vignettes

Implements spec PR #123 (`docs/superpowers/specs/2026-11-16-intro-and-stage-vignettes.md`),
stage-transition half only. The title intro is not built yet.

## What plays
| id | picture | text | trigger |
|---|---|---|---|
| `VIG_RIFT_WAKING` | `assets/vignettes/riftgate.png` | WAKING RIFTWILD / THE WILD REMEMBERS | the first dungeon to Riftwild entry of a run |
| `VIG_RIFT_HOLLOW` | same picture, `hollow()` palettes | HOLLOW RIFTWILD / THE WILD FORGETS | the first Worldglass shift into Hollow |
| `VIG_STAGE_EMBER` | `assets/vignettes/ember_depths.png` | EMBER DEPTHS / THE KILN WAKES | the first Riftwild to stage 3 entry |

Each vignette runs about 3 s. It shows a framed picture, the stage name and motto, the class hero walking
in from behind the frame, and one cheap effect: the rift tear plus a white flash, or the lava colour cycle.
A, B or START skips after 8 frames. Each one plays once per run, tracked by `vignette_seen`, which is
cleared in `run_state_init`.
**PACK → aim page → LEFT/RIGHT** toggles `CUTSCENES ONCE/OFF`. The setting is stored in SRAM meta
(`META_FLAG_CUTSCENES_OFF`). When a vignette is not played, the dungeon entry shows the existing stage card.

## How it runs
- `SCREEN_VIGNETTE` reuses the unused `SCREEN_REST_ROOM` slot, so the bank-0 screen table does not grow.
- Art loads in chunks under black palettes with the LCD on, so the load hides inside the fade:
  32 tiles per frame, then 6 map rows per frame.
- The vignette leaves through `room_request_resume()`, the same path PACK, MAP and DIALOG use. That
  path redraws the room's BG tiles and map. The vignette uses only BG slots 0x80-0xFF and 0x40-0x6E
  (175 tiles maximum). It zero-fills the few slots that the resume path leaves alone.
- Code and data are pinned to bank 20.

## Adding a dungeon
1. Draw a 112x96 picture (6 BG palettes or fewer, about 120 unique tiles) into `assets/vignettes/<name>.png`.
2. Add a `PICTURES` entry in `scripts/gen_vignettes.py` with the name, motto, `stage=`, hero path,
   events and an optional colour cycle.
3. Run `python3 scripts/gen_vignettes.py`. It regenerates `src/render/vignette_<name>.c` and
   `vignette_data.h`, including the stage table and dispatch. No code changes are needed.
4. When bank 20 fills up (about 3.5 KB per vignette), change `#pragma bank` for the new files to 21.

`scripts/gen_vignettes.py --check` (CI) fails when generated files are stale. Run
`scripts/test_stage_vignettes.py` to play each vignette from the real ROM. It checks skip, play-once,
CUTSCENES OFF and the VRAM restore, and writes GIFs to `builds/vignettes-<sha8>/`.
Other harnesses call `quintra_vignettes.mute_vignettes()` after class select, which keeps their timing unchanged.

## Not yet hooked
Town to dungeon entries (stages 4 and 7) and the run-start stage 1 do not have hooks yet.
Vignette-seen bits are per boot: a continue after power-off can replay a vignette once.
