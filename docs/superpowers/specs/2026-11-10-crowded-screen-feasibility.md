# Crowded-screen feasibility study (code-only)

Status: study only. No optimization is approved by this document.
Carmelo / struktured decides whether any of the batches below become code.

Measured tree: `5060e765f704dd14a520df031a118b97e583c4de` on `main`.
The annotated tag `v0.20.20-beta36` (tag object `d594654`) points at that
commit. `git diff v0.20.20-beta36 HEAD` is empty.

ROM under test: `rom/working/quintra.gbc`, sha256
`017ba7879c916f921e4436e9e635d31b628993b4346a92271b555a926a7397de`.
Built with GBDK-2020 4.5.0 / SDCC 4.5.1. PyBoy 2.7.0, headless, 180 LCD
frames. Every scene reported `frame_budget_ok`: PyBoy advanced 140448
T-cycles per LCD frame. Host wall time is not a result.

Pass 1 numbers below are the attached phase-2 before/after sheet (the
ROM after the first crowded-screen pass, before the headroom note).
Pass 2 is the rest of PR #15 (`5f61dc7`), which is what `main` still
contains for these hot files. Later commits did not edit `combat.c`,
`projectile.c`, `projectile_hostile.c`, `room_collision.c`, `hud.c`, or
`entity_draw_core.h`.

## What pass 2 already changed

The headroom note estimated savings against the pass-1 ROM. Pass 2
already took the large ones. Fresh medians:

| Scene | Pass 1 median | This ROM median | Pass 1 lag | This lag | Updates |
|---|---:|---:|---:|---:|---|
| natural_opening | 115808 | 91652 | 1 | 0 | 180/180 |
| fixed_crawlers | 125620 | 96184 | 11 | 3 | 177/180 |
| dense12_stationary | 156372 | 144348 | 17 | 6 | 174/180 |
| empty_room | 56280 | 44800 | 0 | 0 | 180/180 |
| walkers8_pinned | 142808 | 119792 | 12 | 0 | 180/180 |
| walkers16_pinned | 228260 | 197056 | 74 | 58 | 122/180 |
| orcs8_pinned | 155084 | 142844 | 16 | 8 | 172/180 |
| wisps6_live | 127812 | 113860 | 4 | 2 | 178/180 |
| player_shots_miss | 502912 | 284452 | 131 | 93 | 87/180 |
| player_shots_overlap | 323448 | 219480 | 115 | 78 | 102/180 |
| hostile16_moving | 157124 | 144064 | 15 | 5 | 175/180 |

`player_shots_miss` fell by 218460 T-cycles after pass 2. That is the
saving the headroom note attributed to the target list and the split
hit handler. It is already in the ROM. It must not be counted again.

Work p90 on this ROM: miss 307876, overlap 320040, walkers16 250956,
orcs 162028, fixed crawlers 152992, wisps 149640, hostile16 147124,
dense12 147020, walkers8 144256, natural 118896, empty 47944.

## How a T-cycle was attributed

`scripts/bench_crowded_baseline.py` hooks function entries. An exclusive
slice runs from one hooked entry until the next hooked entry, so it
includes the unhooked tail after a short callee returns. The banked-call
trampoline at `___sdcc_bcall_ehl` (`0x3C0E`) runs *before* the callee
hook. Its cost sits in the caller's slice.

The trampoline bytes in this ROM are:

```
F0 90        LDH A, (current bank)
F5           PUSH AF
7B           LD A, E
E0 90        LDH (current bank), A
EA 00 20     LD (0x2000), A
E7           RST 0x20          ; 0x0020 is E9, JP (HL)
; callee RET comes back here
E1 6F 7C     POP HL / LD L,A / LD A,H
E0 90        LDH (current bank), A
EA 00 20     LD (0x2000), A
7D C9        LD A, L / RET
```

Counted at SM83 T-cycle rates (NOP = 4): about 172 T-cycles including
the caller's `CALL` and the trampoline's final `RET`, roughly 150 more
than a same-bank `CALL`/`RET`. `walker_tick` pays this to reach
`enemy_try_step` even though both functions are in bank 2
(`obj/src/game/enemy_ai.asm` around the `b_enemy_try_step` call).

`hud_redraw_boss`'s slice is mostly `room_tick` after that call. On a
non-boss scene the call is `hud_redraw_boss(0, 0)` and the slice median
is 4756–4808. That is not the Will bar.

`aabb_overlap_player` never appears as a hook hit on the walker or shot
scenes. SDCC inlined it into `combat_resolve`. Contact cost is inside
the `combat_resolve` slice.

Walker steps are not every frame. `walker_tick` steps when
`(state_timer & 3) == 0` after the decrement. The sixteen pinned
crawlers start synchronized and then desynchronize when each rolls a
new timer. `walkers16_pinned` recorded 477 `room_player_position_clear`
calls across 121 updates, about four steps on a typical frame, not
sixteen. A frame that fires a pattern is a different animal:
`enemy_update` max on that scene is 123368 for a single crawler.

## Bank headroom on this ROM

`scripts/check_rom_layout.py` after the clean link:

| Area | Free bytes | Floor note |
|---|---:|---|
| Home, ends `0x3F5B` | 165 | No 256-byte rule. Little room for new home code. |
| Bank 1 (`room.c`) | 283 | 27 bytes above the 256-byte emergency floor. |
| Bank 2 (`enemy_ai.c`) | 948 | |
| Bank 3 (combat, player shots) | 1001 | The "bank 3 is at the floor" comment in `projectile_hostile.c` is stale. |
| Bank 6 | 1791 | |
| Bank 8 (collision, HUD) | 630 | |
| Bank 14 (crawler patterns) | 1579 | |
| Bank 16 (hostile shots, hit handler) | 1151 | |

`projectile_update_hostile` is 676 bytes (`0x000`–`0x2A3` in its listing).
The open-floor return is reached by `0x1AC`. A hot prefix of about 430
bytes fits in bank 3 with roughly 570 bytes left. The whole 676-byte
function would leave 325 bytes, 69 above the floor. That is too tight
to move verbatim.

## Per-item verdict

Savings are T-cycles per update on this ROM, not on the pass-1 ROM.
"Measured" means a throwaway edit, rebuilt locally, benched, then
reverted with `git checkout`. Those ROMs are not the sha256 above.

| Item | Pass 2 | What it costs now | Difficulty | Gameplay risk and how to prove it | ROM / RAM | Realistic save | Confidence |
|---|---|---|---|---|---|---|---|
| a. Split hit handler, static shot box, active-enemy list | Done for ordinary bullets | `combat_resolve` on a miss frame is 114460, against 14500 with no actors. The difference is the 8×8 pair walk plus the outer slot walk. | Remainder is item b. Another C split of the wide macro was measured at −3040 on miss and −1740 on overlap. | List is ascending slot order. A split sets `combat_tail_rescan` and finishes with `combat_scan_slots` from `j+1`, so a new ooze fragment is not skipped. Pierce, RNG, and hit-stop stay in `combat_apply_player_shot_hit` (bank 16). | Target list is 32 bytes BSS already. The C split saved ROM (bank 3 free 1001 → 1132) and almost no time. | Do not budget more than ~3k for further C structure. | High. Measured. |
| b. Hand-written byte AABB | Not done | `combat_shot_misses` is 518 bytes and opens with `add sp, #-11`. The in-range X-miss path is 92 instructions. SDCC emits the first signed compare before it tests `shot_box_wide`. | M, about 4–8 hours with the equivalence run. | A wrong compare changes which enemy is hit, pierce, and knockback. Overlap census on the prototype matched the baseline exactly: same slots at 247 or 255 HP, same four spent player shots. Wide boxes and coordinates outside 0..240 must keep the C macro. | Prototype asm shrank bank 3 (free 1001 → 1230). No new RAM. | Miss −36156 work (−32928 in the combat slice), lag 93 → 82. Overlap −14832. | High for that delta. Low for a further 100k. |
| c. Inline bounds + direct tilemap row in the ground check | Done, and it moved to bank 8 | `room_player_position_clear` median 6508–7380 on walker scenes. `room_tile_at_px` is not on that hot path: the fast path reads `room_tilemap[ty]` directly. Callers already pay one banked call; bank 8 did not add a second trampoline. | Residual: inline `row_feet` / `row_body`, and make the walker call a near call. S–M, 4–6 hours. Unmeasured. | Fast path is `x <= 146 && y <= 120`, else the original 12 probes. Tiles are masked with `0x7F`. Equivalence is the existing return-value sweep over x,y plus `test_crowded_equivalence.py`. | Bank 8 has 630 free. A near-call wrapper does not change the banked public entry. | Maybe 5–15k on walkers16's median (four steps, not sixteen). Not enough to reach the budget. Fire frames do not use this path. | Medium that more collision micro-work is the wrong next PR. |
| d. Tick the crawler timer in `enemy_update`; bank-call only on fire clocks | Not done | Idle `enemy_update` median 3964 per crawler (16 × 3964 plus about four step tails is the 107304 entity phase). The pattern function is bank 14, 1499 bytes, and allocates 15 stack bytes before it knows the clock is idle. | S, 3–5 hours. | Must keep init (`ai_data[4] == 0`), the `ai_data[3] == 0` easy/boss adjust, and every side-effect clock: variant 1 at `>= 145`; variant 2 at 145, 161–193 step 8, and `>= 194`; variant 3 at 150, 160, and `>= 170`. Other clocks only store `clock+1`. Prove with 200-update equivalence on `walkers16_pinned` and `fixed_crawlers`, plus a forced fire clock. | Prototype helper cost 115 bytes in bank 2 (948 → 833). No RAM. | Walkers16 −24424 (lag 58 → 41). Walkers8 −11360 (p90 144256 → 132212). Fixed crawlers −2840. Eight crawlers on the miss scene are about −11k of the combined −48k. | High. Measured. A fire clock still costs ~122k inside one `enemy_update`. |
| e. Hostile floor path back in bank 3, sharing the solid tail | Not done. The 8-bit `tx < ROOM_W && ty < ROOM_H` test and the player open-floor return are done. | `projectile_update_one` median 3752 on dense12 (2076 calls / 173 updates = 12 shots) and on hostile16 (2383 / 174 ≈ 14 live shots). That slice includes the bank-16 body. 12 × ~170 trampoline ≈ 2.0k; 16 × ~170 ≈ 2.7k. | M, 4–8 hours, mostly bank placement. | Same kill/break rules. Equivalence: dense12, hostile16, and one crystal/pot room so the cold tail still runs. | Hot prefix ~430 bytes into bank 3 (1001 free → ~570). Leave the crystal/pot/wall tail in bank 16. Do not move all 676 bytes (only 69 bytes of floor margin). | Median of dense12 / hostile16 can fall under 140448. p90 is only ~7k over, so 0 lag is plausible if the body shrinks a little too, and not plausible from the trampoline alone. | Medium on the trampoline math. Low on any claim larger than ~8k until measured. |
| f. Will bar: constant thresholds and an owner cache | Done, and the note's premise was wrong | `WILL_NEXT_MAX` is `(WILL_MAX + 30 * player.will_level)`, not a compile-time constant. Thresholds recompute only when `will_level` changes (`__divuint` is on that cold path). The steady path returns when `lane_palette == 5` and the segment matches. | Residual hoist of the cache check to the caller: S, ~2 hours. | `lane_palette` is how shop, loot, boss, and notice writers invalidate the lane. A caller-side skip must use that same byte. | Bank 8. Two cache bytes already exist. | The 4.8k `hud_redraw_boss` slice is the room tail. Expect well under 1k from skipping one banked call. | High that this is not a 1500–2500 T-cycle item anymore. |
| g. `has_pickups` / `has_enemies` during the frame's own scan; pointerize the room sweep | Pickups are done. The enemy sweep is not. | `pickup_check_player_collision` is absent from every scene in this run. `entity_pickup_pending` is set by the slot walk and by `entity_spawn`. The post-combat sweep in `room.c` is still `entities[i]` for all 32 slots. Empty-room `combat_resolve` (which includes that sweep, up to `dungeon_director_update`) is 14500. | S, 2–3 hours. | A flag computed in this frame is immune to tests that poke `entities[]` between frames. `entity_enemy_count` is still the wrong signal. The sweep must still call `dungeon_director_update(0)` and the Will/shop lane when no enemy is active. Pointer order stays ascending. | Bank 1 has 27 bytes of margin above 256. The patch has to shrink or hold bank 1. | A few thousand at most, buried in the 14500 empty combat floor. | Medium. Not measured. |
| h. Extract the per-sprite body so inactive slots are cheap | Not done | `entity_draw_all` allocates 22 stack bytes. An inactive slot still computes `slot * 28` before the flag test: about 340 T-cycles in the listing. 32 × 340 ≈ 11k, and empty-room draw is 13296. Sixteen crawlers draw at 56140 (~2.7k each beyond the empty scan). Eight orcs, which are 16×16, draw at 59032. | M, 6–10 hours. | OAM order, flicker rotation, and the serpent/cinder/hexa skips have to stay put. Prove with shadow-OAM compares on empty, walkers, orcs, and dense12, not just the cycle bench. | Likely ROM-neutral. Home has 165 bytes free, so the outer loop must stay smaller than today's function. The body can live in the bank that already draws the world. | 3–8k where many slots are idle. Less where the sprites are real 16×16 writes. | Medium. The inactive-slot listing is solid. The active-path saving is not measured. |

### New opportunities, ranked against the list above

None of these beat the measured crawler guard or the measured asm
predicate.

1. Same-bank near call for `enemy_try_step` from `walker_tick`. The
   public entry stays `BANKED` for knockback and hookshot. About 150
   T-cycles times the four steps on a typical walkers16 frame. Small.
2. `combat_load_shot_box` is 130 bytes and 600 T-cycles, called once
   per live player shot. Eight shots are ~4.8k. Worth doing inside the
   asm PR, not as its own change.
3. The general pattern is real and narrower than the headroom note:
   a cold path in the same function makes SDCC allocate the cold frame
   on the hot path. Pulling the signed macro into its own C function
   did **not** make the byte path cheap (still `add sp, #-10`, −3k on
   the scene). The byte path needed asm. Future C-only splits should
   be assumed worthless until a bench says otherwise.

## Throwaway prototypes (reverted, not in the baseline ROM)

Both prototypes were stacked for the last bench. Walker scenes have no
player shots, so their delta is the crawler guard alone.
`player_shots_miss` on that last bench is both changes.

Crawler guard (`crawler_needs_pattern` in bank 2, near call, bank-call
only for init, a zero clock, or a side-effect clock):

| Scene | Median before → after | Lag before → after |
|---|---|---|
| walkers8_pinned | 119792 → 108432 | 0 → 0 |
| walkers16_pinned | 197056 → 172632 | 58 → 41 |
| fixed_crawlers | 96184 → 93344 | 3 → 3 |
| player_shots_miss (plus the asm) | 284452 → 236400 | 93 → 78 |

`enemy_update` median fell from 3964 to 2632. Its max stayed 122548.
That max is a fire clock, which still enters `blue_crawler_pattern_tick`.

Asm byte test, overlap end state identical to the baseline census
(HP 247/255 on the same slots, four player shots reduced to pierce 1):

| Scene | Median before → after | Combat slice | Lag |
|---|---|---|---|
| player_shots_miss | 284452 → 248296 | 114460 → 81532 | 93 → 82 |
| player_shots_overlap | 219480 → 204648 | 66380 → 50236 | 78 → 71 |
| empty_room | 44800 → 44800 | 14500 → 14500 | 0 → 0 |

The C-only split of the wide macro, before the asm, saved 3040 on miss
and 1740 on overlap.

## Per-scene ceiling

The budget is 140448 T-cycles. "0 lag" means 180 updates in 180 LCD
frames, which requires the slow frames, not just the median, to fit.
Empty-room work of 44800 is the shell with no actors: input, the room
preamble, an empty entity scan, an empty combat scan plus the 32-slot
clear check, a 13k draw of inactive slots, and the HUD/shop tail.

| Scene | Median now | Best credible code-only median | 0 lag? | Why |
|---|---:|---:|---|---|
| empty_room | 44800 | already there | Yes, already | Nothing left that matters. |
| natural_opening | 91652 | already there | Yes, already | p90 118896 is under the budget. |
| walkers8_pinned | 119792 | ~108k, measured | Yes, already | The crawler guard also pulls p90 from 144256 to 132212. |
| wisps6_live | 113860 | low 100ks | Yes, credible | Median is 0.81 of a frame. Two lag frames and a 149640 p90 are pattern spikes, the same class as the crawler fire clock. The guard does not cover wisps. A small draw/projectile trim can eat the two late frames. Not guaranteed. |
| fixed_crawlers | 96184 | ~93k, measured | Unlikely | Median is fine. p90 stays ~150k because the natural room sometimes shoots. One fire clock is ~122k by itself. |
| dense12_stationary | 144348 | ~135–140k | Yes, credible | 3900 over at the median, 6572 over at p90. Twelve hostile updates dominate (`entities_to_combat` 47884, draw 42016). The bank-3 floor path is the change aimed at this scene. |
| hostile16_moving | 144064 | ~135–140k | Yes, credible | Same shape as dense12. p90 is 147124. Trampoline removal alone is ~2.7k, short of the p90. It needs the tighter body as well. |
| orcs8_pinned | 142844 | ~135–145k | Possible, not the bet | Only 2396 over at the median, but p90 is 162028 and draw is 59032 because orcs are 16×16. The crawler guard does not apply (`enemy_update` here is 3444, and orcs are not blue crawlers). 0 lag depends on the draw extract actually shrinking 16×16 sprites. |
| walkers16_pinned | 197056 | ~155–170k | No | Measured 172632 after the guard. Four steps × ~9k of try-step plus clear, sixteen draws at 56k, and combat at 19k remain. A fire frame's single `enemy_update` is still ~122k, and the scene max only fell from 367124 to 321072. Slow frames stay above one LCD frame no matter how cheap the idle clock becomes. |
| player_shots_overlap | 219480 | ~190–205k | No | Measured 204648 with the asm predicate. Hits still run the bank-16 handler, knockback, and `room_player_position_clear` (p90 36820 on that slice). Eight crawlers add the guard's ~11k. The pair walk is no longer the whole frame. |
| player_shots_miss | 284452 | ~210–230k | No | Measured 236400 with both prototypes. Combat remains ~81k after the asm (empty combat is 14.5k, so ~67k of pair-walk scaffolding is still there). Eight player projectiles at 5512 each and a 55k draw are on top of eight crawlers. Cutting the caller scaffolding and the 600-cycle box load might take another 15–25k. That still leaves about one and a half frames. |

The minimum that does not go away, even with perfect code, on a miss
frame: the 18k non-actor shell (empty room minus its draw and its empty
combat), a real draw of 16 sprites, eight projectile integrates, eight
walker ticks, and 64 overlap tests. Those are allowed to get cheaper.
They are not allowed to be deleted. Their honest sum, using the
post-prototype measurements where we have them and tight-but-not-fantasy
costs where we do not, sits above 200k. The optimistic sum can be
talked under 160k only by assuming every remaining function loses most
of its body at once. That is not the planning number.

## What would be required past code-only

Parked. No design work in this study.

- Emit crawler patterns every other cycle, or stagger the sixteen fire
  clocks so two never fall on one frame. The player sees a thinner,
  later volley. RNG consumption and which shot exists on a given frame
  both change. This is the only lever that removes the ~122k fire spike.
- Step ground enemies on alternating frames. Blocked crawlers change
  direction later. A shot that would have met a crawler mid-step misses
  or hits one frame later. Equivalence tests fail on purpose.
- Alternate the pair scan across frames. Pierce order and hit-stop move.
- Shrink the 12-probe ground envelope. Small enemies can enter pockets
  the player's feet cannot, which is the softlock the current check exists
  to prevent.

## Order of attack

Each batch is one PR. Equivalence is `scripts/test_crowded_equivalence.py`
at 20 and 200 updates on the scenes named, plus the bench at 180 frames.
Do not merge a batch whose bench regresses a scene that was already at
0 lag.

1. **Crawler idle guard** (item d). Highest measured save per hour.
   Bank 2 can spare 115 bytes. Scenes: walkers16, walkers8, fixed
   crawlers, and the miss scene for the side effect. Add one test that
   a variant-1 clock of 144 still fires on the next frame and that a
   clock of 10 does not.
2. **Asm byte overlap** (item b), with `combat_load_shot_box` tightened
   in the same PR if it stays small. Scenes: both shot fixtures. Keep
   the signed macro for wide and out-of-range boxes. The overlap HP
   census above is the model for the equivalence check. Bank 3 got
   smaller in the prototype.
3. **Hostile floor prefix in bank 3** (item e). This is the PR aimed at
   dense12 and hostile16, the two scenes whose p90 is only ~7k over.
   Leave the solid tail in bank 16. Re-measure before believing it
   clears 0 lag. If the save is under ~4k, stop and report that.
4. **Draw-body extract** (item h), only if orcs or the idle scan still
   matter after 1–3. Gate it on an OAM compare, and revert if the bench
   saves less than ~3k. Home has 165 bytes free.
5. **Do not schedule** a further C rewrite of the pair walk, a Will-bar
   PR, or more ground-collision inlining as a path to 0 lag on
   walkers16. Item c is already the fast path. Item f is already cached.
   Item a's list is already built. Item g's pickup skip is already live;
   the pointer sweep is a small follow-up only if bank 1 can hold it
   without crossing the 256-byte floor.

## Hexa Dragmar, reference only

Entered the real sanctum the way `scripts/test_hexa_dragmar.py` does
(victory poke, START to the results beat, A). Not part of the harness
ceiling above.

| Window | Updates | Lag | Median | p90 | Max | Bullets |
|---|---|---:|---:|---:|---:|---|
| Phase 0, first 180 LCD frames | 166/180 | 14 | 146536 | 164144 | 465456 | 2–4 |
| Phase 2 after HP poked to 40 against a 200 max | 165/180 | 15 | 147900 | 170276 | 475360 | 4–7 |

Draw median is about 60k. `enemy_update` median is about 15k, and its
max is about 340k. That spike, not the bullet count, is the 465k frame.
Arming all five limbs to fire at once did not stack a volley: the
shunt in `enemy_hexa.c` spread the timers, and a 90-frame window after
that ended at 2 bullets with median 139704 and 3 lag frames. A dense
Hexa frame is a boss-tick hitch, not a second `player_shots_miss`.

## Source of the hot functions

- `src/game/combat.c` — `combat_load_shot_box`, `combat_shot_misses`,
  `combat_collect_targets`, `combat_resolve_ordinary`,
  `combat_player_shots`. Hit application is `src/game/combat_shot_hit.c`.
- `src/game/enemy_ai.c` — `enemy_try_step`, `walker_tick`, the
  `ENEMY_BLUE_CRAWLER` branch in `enemy_update`.
- `src/game/enemy_weak_pattern.c` — `blue_crawler_pattern_tick`.
- `src/game/room_collision.c` — `room_player_position_clear`.
- `src/game/projectile.c` — `projectile_update_one` and the player
  open-floor return. `src/game/projectile_hostile.c` —
  `projectile_update_hostile`.
- `src/render/hud.c` — `hud_redraw_action_charge`.
- `src/game/room.c` — the boss/alive sweep just after `combat_resolve`.
- `src/game/entity_draw_core.h` — the 32-slot draw loop.
- `src/game/entity.c` — `aabb_overlap_ee`, `aabb_overlap_player`,
  `entity_update_all`.

The Argon packet copies those functions and asks for a challenge to
this ordering. This document does not claim that review has happened.
