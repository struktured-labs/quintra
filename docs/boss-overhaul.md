# Boss overhaul — September 26

Original implementation pass accepted on ROM `da33fb7b`; see its
[requirement audit and limits](boss-overhaul-acceptance.md). Entries below are a
chronological working log and include superseded failures and incomplete states.
No automatic hardware reloads or deployment.

## September 28 — Mire Heart refinement

ROM `351dc43c717b41f7b42cbf154dfd75934e14220d6eb47c45a3b36ae2ec1e5c9e`:
redrawn central lobes with a deep cleft and pointed ventricle, small eye slits,
and branching vein. Two resident 24-tile poses produce a double contraction
(six updates on, six off, six on, then rest across a 64-update cycle). Roots
remain anchored; collision bounds and attack behavior are unchanged. The extra
pose uses bank-1 tiles 64–87, with no per-frame VRAM upload or extra OAM actors.

22 Rust tests pass, including core contraction/root invariance. Native three-phase
Mire focus and both-pose menu restoration pass; the immutable prior ROM fails
the contraction gate. Expanded collision and all nine defeat/menu cleanup tests
pass. Dense boss guard passes (Mire 952/1200 and 761/1200 updates with escorts).
The earlier ordinary/Serpent performance failures remain open; this is still an
art-review build, not a release qualification. No hardware reload or deployment.

Fresh 61-card gallery: `builds/boss-phases-351dc43c-97b05c62/`.
Matched comparison: `builds/boss-art-comparison-351dc43c-3dd451b2/`, against
the prior enlarged-art ROM `855d3d39`, not the much older small sprites.

## September 27 follow-up requests

### Native redraw follow-up — art-review build, not release-qualified

ROM `855d3d39c9209bd6866fd58f32e19ac6e1790e2225ae98a7f63d68d548960e03`.
Served review: `builds/boss-phases-855d3d39-97b05c62/`, with the matched
comparison at `artwork/artwork.html`. All 61 phase/mechanic cards were freshly
captured. No MiSTer reload, SD copy, itch deployment, or GitHub push.

Qualification: 21 Rust tests pass; expanded-edge shot tests pass all three
hits and three outside misses (the immutable `cc76729f` parent fails the new
edge-hit test). Full native suite passes 28/30 checks, including all six focus
tests, nine defeat/menu cleanup cases, dense boss tests and audio observer
neutrality. Evidence: `builds/boss-acceptance-855d3d39-1790554638635560445/`.
Two performance gates remain FAILED: Serpent 702/1200 updates versus older
20-segment reference 745 (5.8% slower, budget 5%); ordinary fixed-roster room
156/180 versus required 167. These are retained regressions, not waived gates.
The latter needs a pinned-layout diagnosis too: startup asset timing changes
the generated room. Do not call this ROM release-ready or deploy it as such.

Implemented a new Crystal bruiser at 32×32, Frost Spider and Blood Hydra at
48×32, and Mire Heart at 32×48. The three enlarged bosses use 24 OBJ tiles in
VRAM bank 1. Their expanded shot/contact bounds leave decorative extremities
less punitive. Large-body OAM writes are atomic: initial captures exposed a
partial old/new position during a blink. Their hostile projectile sprite budget
is 10 instead of 12 to account for the larger body; this is a gameplay/rendering
tradeoff, not a claim that all crowded scanlines can display everything.

The matched sanctuary-route capture exposed a second bug missed by direct-entry
tests: identity loading in an earlier room could cache “no large boss.” Boss
spawn now registers the large actor explicitly. The pre-fix comparison gate
fails with zero bank-1 body sprites on Spider. Old comparison PNGs under
`boss-art-comparison-d48e45b3-c58e8007` are rejected, not evidence of the redraw.

Defeat/menu testing now holds Start/B until the bounded screen transition and
records the input/screen timeline; a one-display-frame pulse could miss a game
update. No game input behavior was weakened to satisfy that test.

The chronology below describes earlier builds, not the current implementation.

User requested an even longer, more menacing Serpent tail, then clarified it
could be narrower. Current ROM `cc76729fd6e8234625a011ebdcd041311fc65e695447a45687affcaa8d46576f`
uses 48 segments instead of 28, an 8-pixel body instead of 16, and burgundy /
blood-red / scarlet colors. Contact bounds follow the narrower rendered cells.
Growth still has four meals and retains full length through recovery.

The initial wide 48-segment candidate failed performance (673/1200); subsequent
iterations measured 696, 702 and 705 before the final 714/1200, compared with
715 for the previous 28-segment build and the older 745 reference. Optimizations
use pointer-based history shifting and bounded unsigned contact comparisons.
Failed timing reports remain in tmp. The old 28-segment ROM fails the new length
gate. Current native body/palette/menu/OAM/contact/defeat checks pass; two unwind
cycles finish in 3997 display frames. A reactive Picsean controller defeats it
in 5442 frames with 11 HP, without runtime RAM writes after staged entry.

The current 61-card preview is `builds/boss-phases-cc76729f-97b05c62/`, served
on port 8919 and browser-verified. Rivalmage was not reloaded: it still has the
previous requested deployment, `da33fb7b`.

At that earlier build, additional requested work remained: enlarge and redraw Frost
Spider, Mire Heart and Blood Hydra; revisit the overall boss art direction,
especially Crystal Colossus. These three enlargements are NOT implemented in
`cc76729f`. Existing 32x32 art and the 40-object hardware budget were inspected;
do not merely scale existing sprites and make projectiles/escorts disappear.
A preview-only Crystal concept sheet (bruiser / crab / idol) was generated using
the built-in image tool. It exceeds actual cartridge resolution/color limits
and is not a ROM asset or proof that the native art has been redrawn.

## Required outcomes

- Quiet arena floors; recognizable, solid boss silhouettes instead of tiled terrain-like bodies.
- Boss-specific projectile colors, shapes and sizes with matching collision boxes.
- True nonlinear trajectories: arcs, waves, spirals and returning shots.
- Bounded recursive projectiles: warning before splitting, different child patterns,
  two or three generations, reserved escape lanes and entity/OAM budgets.
- Distinct boss movement and multiple meaningful phases across all nine bosses.
- More telegraphed area attacks and bounded, purposeful minion summons.
- Shadow Reaper damage-link mode with pose/tether/audio tell and grace for shots
  already airborne; both directions of damage linking, with safe dodge strategy.
- Larger and longer Serpent body, temporary arena partitioning, readable escape
  gaps, coils that unwind and no abrupt recovery shrink.
- Distinct boss voices for arrival, attacks, phase changes, pain and defeat;
  sparse muffled calls audible near the corresponding sealed boss door.
- Updated web collage: every phase gets its own labeled animated card; transition
  clips; native audio on the selected fight only; honest fixture disclosures.

## Verification

Pin ROM, symbols, scripts and emulator. Short fresh-boot traces must prove curved
paths, changed child trajectories, bounded generation/population, warning windows,
phase transitions, collision extents and safe gaps. Check actual native pictures
and audio, then regression/performance tests and browser playback. Old ROM must
fail new behavioral gates. Full scope remains incomplete until all requirements
above have evidence, not merely one successful boss or one projectile family.

Baseline: `builds/boss-overhaul-baseline/quintra.gbc`, SHA-256
`7623604d389ae49d8eaa885d7320191601660dcc898559411659b4f81cd1fe49`.

## Progress: projectile foundation

Implemented bank-15 Q4 subpixel arc/wave trajectories and a two-generation
binary split with a 16-update stationary flashing warning. Seeds produce waves;
waves produce arcs. Spawn budget: at most 12 hostile shots and six reserved
entity slots. Newborn children wait for the next update regardless of slot order.
Ordinary boss volleys use this path; signature/Cinder attacks still need migration.
Projectile flag bit 7 selects the custom updater; ai_data[6] is marker 0xD0.

`test_boss_projectiles.py` passes actual path deviation, warning, child rules and
bounded ancestry. The baseline fails the new trajectory gate. Raw traces are in
`tmp/boss-projectile-traces-<rom-hash>.json`, including failed iterations.
An SDCC zero-flag clobber in generation-based ternary selection was avoided with
a fixed pattern table. Generic projectile dispatch uses the cached flags byte;
the dense regression retains 135/180 updates, generated room 175/180 and fixed
roster 172/180. Existing enemy-pattern tests pass.

Not yet complete: full visual/size variety, expanded phase identities, area/summon
work, reflection, serpent enlargement, voice listening review, phase/audio webpage.
The existing 30-second review capture is a diagnostic, not the final phase gallery.

## Progress: shot sizes and voices

Boss-only OBJ atlas 208..223 replaces peaceful residents in boss rooms. Native
shots now have 4x4 pellets, 7x7 orbs and 16x16 splitting seeds (14x14 hitbox);
large seed warning retains all four OAM tiles. Bolt/crescent art is reserved but
not yet assigned to attacks. Spawn budget now counts hardware sprite cost.
`test_boss_projectile_art.py` checks actual atlas/OAM and menu restoration; native
screenshot `/tmp/quintra-boss-projectile-sizes.png` was inspected.

`boss_voice.c` supplies nine distinct pulse/noise profiles. Hooks cover door,
arrival, ordinary volley, signature threshold, pain and defeat. Door volume is
reduced; repeated calls are rate-limited. Cinder's bespoke attack path and new
phases still need their own call sites. Sound quality is not yet listening-verified.

On ROM `0b7c269224aed73186d646141412ef348c52e691d6720f2493b9b07d78913c94`,
all nine generated sanctuary fixtures emitted their expected quiet call and
non-silent native PCM. WAVs and full traces: `builds/boss-voices-0b7c2692/`.
The hook-free counterpart verifies unchanged PCM. `test_boss_threshold.py` passes;
performance: generated 175/180, fixed roster 171/180, dense 135/180 updates.

## Progress: phase foundation and Reaper damage link

ROM `40e5d723681bf776b6171af24be604c04f56b8ae9e16d6c9af10fd01a03982c0`
adds monotonic half/quarter-health phases, a 40-update transition pause and
hostile-shot clearance. Later phases introduce committed cardinal charges,
strafing and orbit movement, locked-position blast warnings and limited summons.
Serpent and Cinder retain their bespoke movement; their expanded phase design
is not complete. Art and complete encounter balance remain unqualified.

Reaper alternates exposed/warning/linked intervals, with a tether and palette
change. New shots during the link hurt the player; pre-link shots are exempt;
boss-projectile damage also reduces Reaper HP (currently floored at one).
It continues attacking while linked. Legacy signature shots still need migration
to the new projectile path and damage attribution.

`test_boss_phases.py` fresh-boots all nine encounters and injects explicit HP
thresholds. It checks phase persistence, transition duration, link alternation
and isolated collisions for fresh/exempt/shared shots. Disabling the live link
deliberately fails the damage-direction assertion (player 15→15, boss 40→38).
This proves collision routing, not yet automatic pre-link marking or readability.
Raw traces: `tmp/boss-phases-<rom-sha>.json`; mutation has `-no-link` suffix.
Projectile and ordinary enemy-pattern regressions pass. Performance remains
175/180 generated, 171/180 fixed roster and 135/180 dense updates; these are
ordinary-room guards, not a boss-load performance qualification.

## Progress: calmer bodies and phase review page

ROM `23fa2c6a59938c6187311990042301f2684d2f8663f340cada9ca60a6538986e`
replaces repeating body-surface highlights with solid shading and removes
checkerboard rune placement. Reaper has a hand-authored hood/cloak map.
Native screenshots were inspected: clutter is reduced, but silhouettes and
focal detail are not finished art. Static projected bodies still need refinement.

`test_boss_body_art.py` checks actual loaded body-tile pixels for all nine bosses.
The unchanged baseline fails with 58 adjacent color changes in Crystal's body
tile; the new quiet surfaces pass without erasing the tile. Native screenshots
and tile data are in `builds/boss-body-art-23fa2c6a/`. All nine phase tests and
the ordinary-room performance guard also pass on this ROM.

`capture_boss_phase_review.py` produces 27 health-phase and 18 transition cards,
with retained native WAVs, browser MP4 audio, full per-frame traces and hashes.
Current output: `builds/boss-phases-23fa2c6a-1cdfa5c8/index.html`, served on port
8919. Fresh boot per boss, stationary HP-replenished player, explicit half/quarter
boss HP; these are previews, not difficulty acceptance. Bespoke encounter acts
still need coverage beyond the three generic health-phase cards.
Visible previews are muted; enlarging pauses previews and enables only selected
audio. Browser playback and audio decoding are checked, not listening quality.

## Progress: Serpent retains growth and unwinds

ROM `89a32fb98bb6bbe18d3cc241fcb7771de1e6a65a0dad76473c0981dedf5a0a17`
removes recovery contraction. After growing, Serpent retains 20 segments and
unwinds through four outer waypoints before charging again. Chase movement
advances every three/two/one updates across health phases. Attack entries use
its own boss voice; the end-of-charge blast now respects player invulnerability.

`test_serpent_unwind.py` fresh-boots and allows real feeding/attack cycles with
no boss-state injection. Two complete unwind cycles retain all 20 segments,
cover 553 distinct unwind positions, and complete in 3265 LCD frames. The old
baseline fails at frame 1177 when length drops from 20 to 19. Traces and diagnostic
screenshots: `builds/serpent-unwind-89a32fb9/`. The eastern-camera screenshot does
not establish full-body readability or safe escape routes; those remain pending.

Renderer inspection found 12 head objects plus up to 20 tail objects starting at
OAM slot 4, overlapping slots 32..35 reserved for other entities. Do not call the
Serpent enlargement complete by simply raising the count. A wider-body rendering
strategy with collision-matched art and a verified sprite budget is still needed.
The phase webpage remains pinned to ROM 23fa2c6a, preceding this motion change.

## Progress: broad moving Serpent body

ROM `5d96a15f2210c56bcaf307e6fa700fbfca2546416abdfd2b788a51e57bc737ec`
draws the tail as a moving background overlay: 16-pixel-wide occupied cells,
28 history segments and at least 224 pixels of sampled route. Only changed
cells are uploaded. The underlying terrain/collision map is not overwritten.
The physical head retains its 12 sprites; OAM 16..39 is now available for other
entities, eliminating the old tail/projectile overlap. Tail collision uses the
same snapped centers as the overlay, with a fixed combined half-width of 12.
The former invisible 14-pixel charged reach was removed.

`test_serpent_body.py` verifies native growth, connected route length, occupied
VRAM cells, menu restoration, head plus twelve projectile sprites, edge damage
(11 pixels hits; 12 is safe), and defeat cleanup. Native screenshots were
inspected. Previous ROM 89a32fb9 fails the 28-segment growth gate. `test_colossal_serpent.py`
now runs this contract and the natural two-cycle retained-growth test instead
of requiring the superseded shrinking OBJ-only behavior.

Full-growth 1200-frame comparison: parent 745 updates, candidate 755; both
traces retain every LCD frame. First 1000 natural-entry frames: parent 677,
candidate 661; the new body has additional growth, and startup cost is slightly
higher. `test_serpent_performance.py` records the explicit unequal body sizes
and enforces a 5% full-growth regression guard. Ordinary-room performance is
unchanged. All nine phase tests and projectile atlas/menu tests pass.

Evidence: `builds/serpent-body-5d96a15f/`, `builds/serpent-unwind-5d96a15f/`,
`tmp/serpent-performance-<rom-sha>.json`. Updated 45-card preview is
`builds/boss-phases-5d96a15f-1cdfa5c8/index.html`. Remaining Serpent qualification:
controller-driven escape routes through the evolving coil, later-phase fairness,
and encounter-specific gallery clips spanning growth/unwind rather than only HP.

Follow-up ROM `a3835c2f0a1317dfdf1f22701f2c67a238e7df8bb151253d92e63ec96c650edd`
also validates head identity when rewards reuse its entity slot and releases the
dedicated renderer after defeat. The body regression now uses a real lethal
player-projectile collision, retains each frame of the boss-death freeze, and
requires cleanup within 32 display frames. This supersedes the earlier isolated
entity-deactivation check. Updated evidence has the `a3835c2f` prefix.
The qualified full-growth comparison on this follow-up is 752/1200 updates
versus the parent's 745/1200. Body/unwind, all nine health-phase checks and the
ordinary-room performance guard pass. Port 8919 now serves
`builds/boss-phases-a3835c2f-1cdfa5c8/index.html`; browser checks confirm this ROM
binding, all 45 cards, Serpent playback and isolated selected audio decoding.

## Progress: spiral/return motion and a second recursive family

ROM `14ff1c12f241ab4f9ce48adafbd59adde19296ab1d069def01459526f9035dbc`
adds true expanding spiral motion around a retained launch origin and looping
crescents that pause visibly before returning to that origin. Bolts activate
the reserved 16x8 art; crescents use 16x16 art. Traveling shots now honor three
speed bands (0.5/1/1.5 pixels per update at cardinal angles), stored in entity
state rather than the ai_data[5] status-source byte. Spawn coordinates denote
centers; splits preserve the parent's center when changing child sizes.

Ordinary volleys change identity across HP phases. Late-phase splitting spirals
produce returning crescents, which finish their return before warning and
splitting into bolts. The earlier seed→wave→arc family remains. Recursion is
limited to two splits; OAM cost accounts for all five shapes, including bolts
and crescents. Arena-edge rejection now includes the complete hitbox extent.
Internal obstacle sampling still needs full large-projectile coverage.

`test_boss_projectiles.py` passes actual curved paths, full spiral quadrants,
complete returns, stationary warnings, distinct speed bands, both recursive
families and size-dependent arena-edge rejection. Parent a3835c2f fails the
spiral-quadrant gate. `test_boss_volley_patterns.py` observes expected ordinary
attack identities in all three phases of the eight shared-driver bosses.
Cinder remains excluded because its bespoke attacks are not migrated yet.

The five native projectile silhouettes were inspected; atlas/OAM/menu checks
pass. All nine phase checks and ordinary-room performance guards pass. Full-grown
Serpent remains 752/1200 versus the original 745/1200 comparison fixture.
New preview: `builds/boss-phases-14ff1c12-1cdfa5c8/index.html`.
Still required: migrate signature/Cinder projectiles, complete large-shot
obstacle checks, qualify dense spiral load, and finish remaining encounter/art
and controller-driven fairness work. This is not full-overhaul acceptance.
Port 8919 serves this capture via transient user service
`quintra-boss-review.service` (the earlier terminal-hosted preview had stopped).
Browser checks confirm the new ROM binding, 45 cards, late-phase Golem video and
isolated selected audio decoding. No game deployment or hardware reload occurred.

## Follow-up: bounded recursive geometry and obstacle coverage

ROM `8aa1c8e16acc4b3bde6d627467edc38538505b984023b1ca15128ab03678af0e`
passes a fresh `test_boss_projectiles.py` run, including both recursive families,
curved trajectories and large-projectile obstacle coverage. Recursion remains
two splits deep, with warning intervals and a shared sprite budget. Different
generations change motion rather than merely repeating the same radial burst.

The full-footprint tile lookup costs performance: the fresh Serpent stress test
reports 711/1200 updates versus the immutable parent's 745/1200 (ratio 0.954).
This narrowly passes the existing 0.95 guard; it is not a performance improvement.
Earlier collision implementations failed that guard and were replaced, without
reducing collision coverage. The 61-card event-capture script is not yet qualified;
the served 45-card preview still represents the earlier ROM. Hardware fairness,
the expanded gallery and overall boss-overhaul acceptance remain outstanding.

## Progress: native mechanic-cycle review

The same `8aa1c8e1` ROM now has a complete 61-card capture at
`builds/boss-phases-8aa1c8e1-97b05c62/index.html`, served on port 8919.
The original 45 health-phase/transition cards are joined by three natural
Serpent growth/pursuit/unwind clips, ten Cinder formation/transformation/Rex/reprise
clips and three Reaper warning/linked/exposed clips. Every mechanic clip reaches
its actual event boundary; traces retain per-frame mechanic state and the first
frame of the next state. Explicit health cuts and stationary, replenished player
fixtures are disclosed on the page. These are not successful-dodging demonstrations.

Browser acceptance checks all 61 cards, ROM binding, playback, shortlist controls,
selected-only audio decoding and close cleanup. Visual inspection caught a modal
that did not enlarge video; the new width/aspect-ratio gate fails that old page
at 160x144 and passes the corrected page at 640x576. Native PCM is retained;
listening quality remains unqualified. `scripts/test_boss_review_page.py` retains
this browser regression gate. Selected and grid screenshots plus browser metadata
live alongside the new capture. Serpent body tiling still looks too repetitive
and needs visual refinement despite the mechanical improvement.

Fresh checks on this ROM also pass all nine signature attacks, Cinder's bespoke
formation/armor/transformation/attack suite, all nine HP phase windows and Reaper
collision checks, and five projectile silhouettes with menu restoration.
No Pocket/MiSTer reload, itch deployment or git push was performed.

## Progress: continuous Serpent scale fill

ROM `d939e85ea48045e809f1cac11038236c7fea7108e32c54186432c919b52862bc`
replaces the four hollow ring tiles with broad overlapping scales and a muted
violet palette closer to the head. Tile count, OAM use, occupancy, collision and
renderer instructions are unchanged. Native before/after frames are in
`builds/serpent-body-8aa1c8e1/full-body.png` and
`builds/serpent-body-d939e85e/full-body.png`. The parent ROM/symbols are retained
in `builds/serpent-art-parent-8aa1c8e1/`.

The native atlas now has no floor-colored holes and a majority base shade;
the old ring build fails that new gate. This is a structural art check, not proof
of aesthetic quality. Visual inspection confirms the repeating hollow-circle
appearance is gone, but the occupancy-based outer contour is still blocky and
needs a subsequent silhouette pass. Body/menu/12-projectile/defeat checks pass;
two natural unwind cycles retain all 28 segments across 554 distinct positions.
The stress replay is unchanged at 711/1200 updates versus the original 745/1200
parent. This improvement does not close the broader sprite-art requirement.
The regenerated 61-card preview is `builds/boss-phases-d939e85e-97b05c62/`,
now served on port 8919. Browser acceptance passes on this ROM, including
640x576 selected playback, all mechanic records and isolated audio decoding.

## Progress: Reaper direct-attack link consistency

ROM `e00d0790e622269afa5b820c5c9d196a3e12c79b4e9b382f0d58fc5bbd469728`
routes signature impact damage through the same damage-sharing hook as hostile
bullets. The warned Death Sweep previously cost the player four HP while leaving
the linked Reaper unchanged. `scripts/test_reaper_link.py` reproduces that failure
on the immutable `builds/reaper-link-parent-d939e85e/` ROM; the candidate shares
the four HP. The fixture explicitly aligns the armed sweep with a linked window
and clears disposable entities to isolate direct area damage.

Additional native checks verify exposed-mode damage does not share, shields and
invulnerability protect both sides, and a projectile already airborne at clock
120 is automatically marked at the actual clock-128 link boundary, then damages
the Reaper without reflecting into the player. This replaces the earlier
manually stamped grace test as evidence for automatic marking. Full frame traces
are in `tmp/reaper-link-<ROM SHA>.json`.

All nine health-phase/transition tests and signature tests pass. Serpent stress
remains 711/1200. Still incomplete: shared damage currently floors boss HP at one;
the killing blow must use the normal boss reward/unseal path before the trick
mechanic is considered finished. Clearer player-facing link instructions and
controller-driven fairness testing also remain open.
The fresh 61-card capture at `builds/boss-phases-e00d0790-97b05c62/`
is served on port 8919 and passes the browser acceptance script. No hardware
reload or deployment was performed.

## Progress: linked killing blows use normal victory handling

ROM `65c4928be7432c9fb431c1928db4f7bee2d8fff5c9e98b56d467d8b39dcdc39f`
removes the Reaper's one-HP floor. Fatal shared damage queues the boss slot until
the source hit finishes, then runs the extracted normal enemy-death handler.
This avoids releasing/reusing entity slots while signature or collision code is
still reading them. Normal giant kills also clear both active and pending link
state. A zero-HP player cannot be revived by the deferred victory recovery;
simultaneous fatal damage gives player death priority rather than awarding a win.

`test_reaper_link.py` now verifies projectile and direct-sweep killing blows,
full-entity-table reward survival, actual north-exit terrain becoming doorway
tiles, victory music, no remaining hostile shots, simultaneous-death priority,
and a lethal protected pre-link shot clearing the link state. Parent e00d0790
fails the lethal gate (Reaper remains at one HP). Intermediate 7b2cac1a fails the
normal-kill cleanup gate; both parent ROM/symbol pairs are retained in builds.
Native victory screenshot: `tmp/reaper-linked-victory-65c4928b.png`.
The snapshot also makes an existing visual gap evident: the static projected
Reaper body remains painted after defeat and needs a proper cleanup/defeat pass.

Ordinary saturated boss rewards and all five class-affinity pools pass. Ooze
split/scatter/recombine and lone-shard pursuit pass after the shared death-handler
extraction. Performance: generated 176/180, fixed roster 174/180, dense 137/180;
full-grown Serpent 713/1200 versus original parent's 745/1200 (ratio 0.957).
No hardware deployment occurred. Link readability and controller-driven fairness
remain separate open requirements despite completion of the lethal routing.
All nine HP phase checks and the Serpent body/menu/defeat regression also pass.
Port 8919 now serves `builds/boss-phases-65c4928b-97b05c62/`; all 61 cards
and the enlarged, selected-audio browser checks pass against the current ROM.

## Progress: explicit Reaper phase instructions

ROM `3dbac2afde4ba4e9e485c20202b95f2688752fd2d43aa35d0109249c8befa5b5`
adds gold LINK, violet NO ATK and green ATTACK cues to contextual HUD columns
10..15. The player-heart columns remain untouched. Warning/linked cues take
priority immediately rather than waiting behind pickup text; interrupted notices
are queued under the existing queue limit. Phase labels are cached, restored
after menu initialization, and cancelled when the boss dies. Exposed-mode text
is brief so the contextual bar and queued notices can return.

`test_reaper_cues.py` checks native tile IDs, CGB palette colors, intact heart
columns, the phase/clock correspondence and menu resume. Parent 65c4928b fails
because it never displays the instructions. Inspected native images and complete
traces: `builds/reaper-cues-3dbac2af-c743fa43/`. Earlier capture variants exposed
video-memory/LCD timing differences, including the menu's white fade; the final
capture waits for stable tiles and a nonblank post-fade frame. Those earlier
variants do not qualify the visible menu restoration.

Reaper collision/grace/lethal/reward tests, ordinary pickup/status feedback and
performance tests pass. Generated/fixed/dense counts remain 176/174/137 per 180
frames; Serpent remains 713/1200 versus the original 745/1200 parent. The full
61-card capture is `builds/boss-phases-3dbac2af-97b05c62/`. This improves explicit
instructions but does not complete the pose/silhouette, defeat-art or safe-dodge
requirements. No hardware deployment occurred.
Port 8919 serves this capture; the browser gate passes all 61 cards, enlarged
aspect ratio, shortlist controls and selected-only audio decoding.

## Progress: remove defeated boss projections

ROM `5c97183bcf753478170eeca23479869923fa4f196d0d8f8049ee68f90b3e0884`
clears projected body tiles from stored arena terrain and native BG VRAM during
victory unsealing. The far-chamber renderer now checks the cleared-boss state,
so a menu redraw cannot repaint the defeated body. Floor inlays outside the body,
arena walls, rewards and exit behavior are retained. This is defeat cleanup,
not a new authored collapse animation or completion of the living boss art.

`test_boss_defeat_art.py` fresh-boots all nine bosses, explicitly stages a one-HP
lethal player collision with the AI held, and records every LCD frame until
both the stored and visible projections disappear. All nine clear within 5–6
display frames from the staged hit. The eight non-final arenas stay clear after
menu resume, with victory music and an open north exit. Final-boss acceptance
stops at the cleanup boundary before the victory screen replaces arena VRAM.
Unrelated interior terrain is compared against its original tile values.

Native before/after/menu images and full traces:
`builds/boss-defeat-5c97183b-67977921/`. Reaper and Crystal images were inspected;
rewards remain visible on quiet floor instead of over the lingering body.
Parent `builds/boss-defeat-parent-3dbac2af/` fails the new gate, retaining 181
visible projection tiles and 118 stored body cells after the first boss's death.
Boss reward, Reaper linked-kill, and Serpent body/menu/defeat regressions pass.
Ordinary performance remains generated 176/180, fixed 174/180, dense 137/180.
No hardware deployment occurred.
Serpent stress remains 713/1200 versus the original 745/1200. The regenerated
61-card preview at `builds/boss-phases-5c97183b-97b05c62/` is served on port 8919
and passes the current-ROM browser checks.

## Progress: Crystal's moving body becomes the visual focus

ROM `1adba15e9bff4ba30d3a425d5b9587a6f7f38ae739c02a077497dfd417aafd23`
removes Crystal's detached western and far-chamber murals. Its existing 32x32
moving OBJ and collision behavior remain; this removes decorative duplicates,
not a physical boss body. The Rust-authored atlas now has broader crystal light
and shadow planes and a wider armored torso, retaining the crown, reactor and
split feet. Generated assets and all 18 Rust asset tests pass.

`test_crystal_focus.py` verifies the loaded atlas's broader highlights, no mural
tiles, 16-tile moving OAM output across three HP phases, and art/menu restoration.
The first phase deliberately visits three teleport wells; its movement gate
checks those distant positions rather than incorrectly requiring continuous
motion. Full unselected traces are retained, while still posters explicitly
record selected on-camera frames after three stable OAM draws. Native battle
posters in `builds/crystal-focus-1adba15e-ff670038/` were inspected. The previous
ROM in `builds/crystal-art-parent-5c97183b/` fails the new native-highlight gate.

The wide arena still permits the boss to teleport outside a stationary player's
camera; the replay does not hide that or pretend the whole arena fits one screen.
Further pose work and controller-driven encounter readability remain open.
Crystal's defeat test now requires no live mural and all 16 moving OBJ tiles,
instead of treating its removed decoration as a required living body. The other
eight bosses retain their existing projection/body cleanup gates. This is the
first focused living-silhouette pass, not completion of all nine boss sprites.
All nine defeat-cleanup checks, ordinary boss rewards and performance guards
pass on this ROM. Generated/fixed/dense counts remain 176/174/137 per 180 frames;
Serpent remains 713/1200. The current 61-card page at
`builds/boss-phases-1adba15e-97b05c62/` is served on port 8919 and passes browser
acceptance. No hardware deployment occurred.

## Progress: movement uses each boss's voice

ROM `0e54e32fdb240c4c0822513269da920085a2461d25b5f67f83675022505e831d`
routes the five remaining shared movement roars in `enemy_boss_motion.c` through
the existing stage-specific attack voice and its cooldown. Telegraph ticks stay
unchanged. This covers Crystal, Spider, Reaper, Void, and the legacy Cinder lunge;
the active bespoke Cinder and Serpent drivers already use individual voices.

`test_boss_motion_voices.py` captures 720 native LCD frames and untrimmed stereo
PCM in four naturally updating phase-zero encounters, with a stationary player
whose health is replenished. All four show movement, their own attack envelope
and noise profile, and no shared roar calls. Hook-free replays produce identical
PCM and recorded state/register timelines. The immutable `1adba15e` parent fails
on Crystal's five shared roars at frames 70, 229, 386, 542, and 706. Spider can
alternate two valid positions around the stationary player, so the movement
guard requires two distinct positions rather than an invented three-position
requirement. This is routing evidence, not a subjective audio-quality judgment.

All nine native door-voice tests still pass. The Serpent performance guard is
unchanged at 713/1200 versus the qualified original 745/1200. No hardware was
reloaded; listening review and the remaining visual/encounter work stay open.
The refreshed 61-card preview at `builds/boss-phases-0e54e32f-97b05c62/`
is served on port 8919 and passes browser acceptance. The first browser check
correctly rejected the still-served parent ROM; after switching the preview
service to this capture, the current-ROM hash and all browser checks pass.
Hook-free door replays also match all nine observed native PCM captures exactly.

## Progress: Reaper's link has a body pose, not only a HUD label

ROM `d18803ccec80c1433de9f8de434ad439e4b2997258fb7c5cc4420adcb58ee6bf`
adds three authored Reaper poses through the existing Rust asset pipeline:
open cloak/scythe and exposed chest, raised-arm link warning, and crossed bone
arms while linked. The skull and tattered cloak persist across poses. The
16-tile atlas changes only when the pose changes; room/menu loading invalidates
the cache, and resumed phase updates restore the active pose. Collision size,
link timing, existing airborne-shot grace, and OAM usage are unchanged.

Both static Reaper projections are removed, leaving the actual moving 32x32
boss as the target on the quiet arena floor. Crystal and Reaper therefore have
no living mural in the defeat-art check; the other bosses retain their own
existing body checks. This is a focused Reaper art/tell pass, not a declaration
that the remaining seven bosses' silhouettes or encounter fairness are done.

All 19 Rust asset tests pass, including generated-pose equality and substantial
pairwise pose differences. Native `test_reaper_cues.py` verifies distinct loaded
atlases in all three states, matching HUD text/palettes, and linked-pose menu
restoration. Its stills wait for three fully visible 16-tile OAM frames; the full
unselected trace retains off-camera and incomplete draws. Native stills in
`builds/reaper-cues-d18803cc-3c8e5ae4/` were visually inspected. The immutable
`0e54e32f` parent fails the unchanged-pose gate. Earlier still selection captured
an off-camera boss; those earlier artifacts remain, but are not the selected
visual evidence for this pass.

Native Reaper damage/grace/lethal rewards and all nine boss defeat cleanup tests
pass. `test_reaper_performance.py` compares fresh half-health encounters against
the immutable parent over all 1200 LCD frames: both deliver 1173 game updates.
Serpent remains 713/1200 against its qualified original 745/1200. These are
offline measured guards, not hardware acceptance. No hardware was reloaded.
The 61-card preview is regenerated at `builds/boss-phases-d18803cc-97b05c62/`.

## Progress: advance summon tells and distinct escorts

ROM `117fdf8ddc6bc876f96c2fad3c065b494c286f8dbc46b8cf5b50f940bd8ebe8a`
marks up to two visible, clear arena sites at boss clock 160 and resolves those
same sites at 192. A site is only armed if its warning FX allocation succeeds.
Resolution rechecks all four terrain corners, player distance, and nearby enemy
bodies; it never silently relocates an invalidated warning to an unmarked spot.
Phase transitions clear the pending sites. Existing escorts still count toward
the two-minion cap, so successive calls cannot build an unlimited crowd.

Removed the ineffective `ai_data[1]=60` assignment: neither Hornet nor Crawler
uses that byte as a generic spawn grace timer. Fairness now comes from a real
advance tell plus placement revalidation, not an imaginary immunity period.
Frost Spider calls chasing Hornets; Mire's Crawlers use the sweeping cast, while
Void's use the warned radial burst. Crawler cast clocks start at zero instead of
the ordinary position/slot-dependent initial offset. No general enemy AI changes.

`test_boss_summons.py` checks the three bosses at half and quarter HP through
two summon opportunities, including the cap, at least 30 elapsed game updates
between markers and birth, matching marked coordinates, and authored cast IDs.
Additional fixtures deliberately move the player onto a marked location or
insert a pillar at its previously unchecked top-right terrain corner; both
cancel that spawn. These are disclosed synthetic safety cases, not claimed
controller playthroughs. The immutable `d18803cc` parent fails the missing
advance-warning gate. Source-bound traces and native stills are in
`builds/boss-summons-117fdf8d-c1aebf10/`; earlier first-cycle captures were visually
inspected and retained at the same ROM's `6c01f45b` variant.

All nine phase-transition tests pass. Ordinary generated/fixed/dense performance
remains 176/174/137 updates per 180 LCD frames; Serpent remains 713/1200 versus
745/1200 in its original control. These do not replace a dedicated dense
summoning-boss controller/performance qualification, which remains open.
No hardware reload or deployment occurred.
The refreshed `builds/boss-phases-117fdf8d-97b05c62/` preview is served on port
8919 and passes all 61-card browser checks.

## Progress: a third recursive family, Golem's forked lightning

ROM `66890286f113ff1f37d6cdf65b5c300e51da7e3b631926bdcfa3fa9975b3a39d`
adds a third ancestry: broad gold bolt → two perpendicular violet curved sparks
→ narrower pairs of weaving orbs. The first fork uses ±8 of 32 angle steps;
the second uses ±3. Each branching generation still pauses and flashes for 16
updates before splitting. Gold-based patterns now alternate gold/violet rather
than the old gold/gold palette toggle. Existing seed/wave/arc and
spiral/crescent/bolt families, two-generation limit, and shared spawn budgets
remain intact.

Golem emits its branching root before the rest of its budgeted ring; previously
the earlier wide bolts could consume all 12 projectile OAM units before the
special root's turn. The root aims horizontally toward the arena interior.
An initial fixed-left implementation passed the isolated trajectory test but
failed the phase-one encounter: after a wallward charge the root died against
the wall before splitting. The final natural encounter test observes all three
generations in each HP phase, not merely injected projectiles in an empty room.

The isolated native test verifies changed movement/angles, two warning palette
states, violet middle-generation identity, and a maximum four descendants within
the unchanged sprite budget. The immutable `117fdf8d` parent fails the warning
gate. `test_boss_volley_patterns.py` now saves source-bound encounter traces and
native Golem family stills at `builds/boss-volley-patterns-66890286-34f0085e/`.
Native first/middle/final-generation stills were inspected, including the final
violet-spark revision. The Golem's gold background projection still competes
with its moving body; this projectile pass does not resolve that art debt.

A loop assigning child colors inside the update path regressed the Serpent
stress run to 653/1200; extracting a split helper recovered only 672/1200. Both
failed variants' traces remain (`e3dd3e6d` and `fe04aabf`). The accepted version
assigns the new color once at spawn and retains the cheaper split call shape:
713/1200, unchanged from the qualified parent, against original 745/1200.
The five native projectile shapes/menu restoration and ordinary performance
guards also pass (176/174/137 updates per 180 frames). An intermediate preview
capture terminated with exit 143 and remains incomplete; it was not served as
a completed review. No hardware was reloaded or deployed.
The completed final 61-card capture, `builds/boss-phases-66890286-97b05c62/`,
is served on port 8919 and passes the current-ROM browser acceptance checks.

## Progress: Golem's actual body owns the arena

ROM `483efac31eebddcab7e22f59e214c9a53c60512717087566b523ee8788688173`
removes the two detached gold Golem background projections. Its actual moving
32x32 sprite now uses the full width for shoulders and fists, broad light/shadow
armor planes, separated limbs, a dark mouth slit and inset sun-heart. Sprite
size, collision size and OAM allocation are unchanged; this is a clearer and
heavier silhouette, not a claim to have enlarged its collision body.

The expanded native focus check exposed a real later-phase movement issue:
after chasing a stationary player to the wall, Golem repeatedly aimed its
charge into that wall and could remain at one position for all 480 frames.
It now backs toward the arena center during recovery beats 48–63 and 112–127
of its movement cycle. Charge warnings, AOE timing and faster last-phase rushes
remain. The first art-only candidate's failed movement trace is retained under
`builds/golem-focus-6ca211df-79bb6b3b/`.

`test_crystal_focus.py --stage 6` checks broad loaded highlights, no murals,
moving OAM output across three phases and menu atlas restoration. The immutable
`66890286` parent fails the native-highlight gate (28 versus required 100).
Final native phase stills in `builds/golem-focus-483efac3-79bb6b3b/` were inspected,
as were old/new native phase-one review posters. Crystal's existing focus check
also passes, and all 19 Rust asset tests pass.

All nine defeat cleanup and phase-transition checks pass; Golem's branching
lightning still produces all three generations in every phase. Defeat evidence
now waits for three full OAM draws before its staged lethal hit: the first
attempt sampled Golem during an entry flash, not a missing atlas. Its full entry
OAM/flash trace is retained, rather than hiding that temporary absence. General
performance stays 176/174/137 per 180 frames; Serpent stays 713/1200 against its
original 745/1200 control. No hardware reload or deployment occurred.
The regenerated 61-card review is `builds/boss-phases-483efac3-97b05c62/`.

## Progress: Mire's hollow-ring AOE

ROM `dc688a59f676c7e2e5acee00a1fe3bc95f7a6b6ba30c8e8ff5e8bf619512ab0b`
gives Mire a different spatial decision from the other bosses' filled blasts:
an eight-point violet ring locks onto the player's location, warns for 32 game
updates, then damages the 16–30px radial band. Staying within its center or
moving beyond its outer edge avoids this attack; unrelated enemies and shots
are still dangerous. Its four follow-up waves originate on the perimeter and
travel outward, rather than spawning a bullet on the supposedly safe center.
If any warning pulse cannot allocate all its markers, this cast fizzles instead
of dealing untelegraphed damage. Other bosses' area patterns remain unchanged.

`test_mire_ring.py` retains native traces/stills at
`builds/mire-ring-dc688a59-62f43763/`. It checks the eight distinct locked marker
coordinates, safe center/inner region, cardinal and diagonal damaging band,
safe cardinal/diagonal exterior, no early warning damage, and a saturated-table
fizzle. Its escape case starts at the center and uses a held Right input from
the warning onward, clearing the band without damage. Initial encounter setup
and the other geometry probes use explicit fixture positions, half HP/clock,
and suppression of unrelated attacks; this is not whole-encounter controller
acceptance. The immutable `483efac3` parent fails the distinct-ring-warning gate
and previously recorded damage to the new safe-center case. Warning, center
resolution and held-input escape native frames were visually inspected.

Both later-phase summon suites and all nine phase-transition checks pass.
General performance remains 176/174/137 updates per 180 LCD frames; Serpent
remains 713/1200 versus its qualified original 745/1200. Mire's remaining large
static projection still needs a living-body art pass. No hardware was reloaded
or deployed.
The fresh 61-card capture at `builds/boss-phases-dc688a59-97b05c62/` is served
on port 8919 and passes current-ROM browser acceptance.

## Progress: Mire's living eye and curled roots

ROM `b6e6ed0464c76892575078650898edd170d63ea9d9b644babca7491e97055bf2`
replaces Mire's scattered oval accents with a broad bright eye, dark offset
pupil, glint and four connected curled root-tendrils. Its existing 32x32 moving
body, collision and OAM size remain. Both detached background projections are
removed, including the per-frame `room_draw` path that repainted the western
organism after its removal at entry. The first native check caught that redraw;
removing only the entry painting was insufficient. The room rebuild completed
normally and the hot bank gains 108 bytes of headroom.

All 19 Rust asset tests pass, including specific eye/root landmarks.
`test_crystal_focus.py --stage 4` checks broad loaded highlights, three-phase
movement/drawing, absence of murals and menu restoration. The immutable
`dc688a59` parent fails the highlight gate (73 versus required 100). Native phase
stills were inspected in `builds/mire-focus-b6e6ed04-469a4daf/` and the preceding
same-art `46d6d603` revision. Menu probes now hold Start/B until their screen
transition, with a bounded trace: the former one-LCD-frame tap could fall entirely
between input polls during combat, leaving the game running rather than opening
the menu. Failed traces remain alongside the qualified run.

The broader focus check found Crystal at 359 complete draws in 480 frames,
just below its unchanged 360-frame visibility requirement. Its post-teleport
blink is shortened from 12 to 6 updates; the advance warning stays unchanged.
Crystal, Mire and Golem now pass all three phases and menu return on this ROM.

The summon test also encountered a frame boundary inside `enemy_spawn`, after
the slot was marked active but before its position/cast fields were initialized.
Its raw timeline still retains those partial rows; birth-position assertions now
sample at phase clock 193, after the clock-192 spawning call finishes. This
avoids treating the temporary zeroed struct as an actual monster at (0,0).
All half/quarter-HP summon and placement-safety cases pass on the final ROM.

Native ring geometry/held-input escape/crowding safeguards and all nine defeat
cleanup cases pass. General performance remains 176/174/137 per 180 frames;
Serpent is 715/1200 (previous 713), against its original 745/1200 control. This
does not close the broader controller-fairness or voice-listening work. No
hardware was reloaded or deployed.
The completed 61-card preview `builds/boss-phases-b6e6ed04-97b05c62/` is served
on port 8919 and passes the current-ROM browser checks.

## Progress: Spider silhouette and refreshed review

ROM `ce30c201441f402f677b7e7d759ba5ee814ebf03e4e5efadfa63acd39f3e89d7`
gives Spider brighter articulated leg segments and a larger shaded carapace
within its existing 32x32 body. Its detached arena murals are removed. Unused
Spider, Reaper and Golem background animation calls and the stale Mire projection
state are removed; the hot bank has 644 bytes free. Sprite/OAM dimensions are
unchanged. The 19 Rust asset tests pass.

Spider's native focus test checks loaded leg highlights, full-body drawing,
three phases and menu restoration. Its first-phase movement check follows its
authored blink between separated positions, rather than requiring continuous
travel. The immutable `b6e6ed04` parent fails the new highlight gate. Native
stills are in `builds/spider-focus-ce30c201-13db57a5/`; the phase-1 image was
visually inspected again during handoff. Crystal and Mire also freshly pass
their three-phase focus/menu checks on this ROM.

The defeat fixture initially failed Cinder: a display-frame boundary can fall
inside an already-running armor update, so setting a freeze and immediately
inserting a shot does not freeze that in-flight call. The trace showed the
anchor moving and its hitbox changing while that shot was consumed. The fixture
now advances four display frames after setting the freeze, records the settled
anchor, then exposes the collision target and inserts the lethal shot. All nine
defeat/menu cleanup cases pass in `builds/boss-defeat-ce30c201-70ef2c99/`.
This is a synthetic cleanup probe, not proof of armor fairness; the separate
real Cinder armor, formation, transformation and reprise test also freshly passes.

Serpent performance is 719/1200 updates versus the immutable original 745/1200
(96.5%, within the unchanged 95% gate). No runtime code changed during these
qualification checks. The complete 61-card native capture at
`builds/boss-phases-ce30c201-97b05c62/` now serves on port 8919. Browser acceptance
passes video playback, individual event traces, enlargement/aspect ratio,
shortlisting, isolated audio decoding and closing cleanup. Audio is not
listening-qualified. No hardware reload or deployment was performed.

The full overhaul remains open: Hydra/Void living-body art, Serpent contour,
broader controller-driven encounter fairness and dense-fight performance, and
voice listening still need acceptance. The preview is for review, not a claim
that every requested boss improvement is finished.

## Progress: Hydra's moving three-headed silhouette

ROM `9c24a892624f062e973db4fc3e889026a70bad015d0aa2d29ab17c547f43e47e`
thickens Hydra's three necks with lit and shadowed planes, defines three jaws
and fangs, and adds a broad belly highlight. Its 32x32 moving body and collision
dimensions stay unchanged. Both detached background murals and their unused
per-frame animation are removed. The room rebuild took approximately three
minutes and completed normally; bank 1 now has 694 bytes free.

All 19 Rust asset checks pass. Native loaded bright pixels increase from 16
to 136. The immutable `builds/hydra-focus-parent-ce30c201/` control fails the
new focus gate; the new ROM passes three-phase movement/drawing, absence of
murals and menu restoration. Evidence is in
`builds/hydra-focus-9c24a892-c68c1c16/`; its first-phase native frame was visually
inspected. All nine actual-collision defeat/cleanup fixtures pass.

General performance remains 176/175/137 updates per 180 LCD frames; Serpent
records 721/1200 against the immutable original 745/1200 (96.8%). These focused
offline checks do not close the outstanding whole-encounter fairness, Void art,
Serpent contour or voice-listening work. No hardware was reloaded or deployed.
The three recursive projectile families and all nine phase-transition tests
also freshly pass. The completed 61-card capture at
`builds/boss-phases-9c24a892-97b05c62/` is now served on port 8919 and passes
current-ROM browser acceptance, including selected-only audio decoding (not
subjective listening qualification).

## Progress: Void Lord's hollow mantle

ROM `7fcb0bcdbbfb0ede667136dc6bbd2b0b914d8a200fffcb402349f20c9a38b201`
replaces Void's inherited Crystal torso with a crowned hollow mantle, lit
shoulder planes and hanging folds. Its continuous bright horizontal mask stays.
The moving body remains 32x32 with unchanged collision/OAM allocation. Both
detached background projections and their unused room animation call are gone.
The room rebuild completed in approximately three minutes; hot-bank headroom
increases to 745 bytes. All 19 Rust asset checks pass.

`test_crystal_focus.py --stage 8` verifies the loaded native mantle gap and mask,
145 bright pixels, all four opening warp anchors, later-phase movement, body
visibility, absence of murals and menu restoration. The immutable
`builds/void-focus-parent-9c24a892/` ROM fails the hollow-mantle gate (and its
earlier probe also failed mural absence). Native evidence is retained at
`builds/void-focus-7fcb0bcd-a607389c/`; the phase-0 image was visually inspected.

All nine defeat-cleanup cases pass in
`builds/boss-defeat-7fcb0bcd-c4fd7d5a/`. All eight summon warning/cap/placement
cases and the eight shared bosses' three-phase volley-identity checks pass.
General performance remains 176/175/137 updates per 180 display frames; Serpent
records 722/1200 versus the immutable original 745/1200 (96.9%).

This finishes the detached-mural removal for the seven ordinary moving bosses;
Serpent and Cinder keep their bespoke body renderers. It does not finish the
full objective: Serpent contour/escape acceptance, broader controller-driven
encounter fairness and dense-fight checks, and voice listening remain open.
No hardware was reloaded or deployed.
The completed 61-card capture at `builds/boss-phases-7fcb0bcd-97b05c62/` is
served on port 8919 and passes current-ROM browser acceptance. Selected audio
decodes correctly; this is still not a listening-quality claim.

## Progress: connected Serpent outline

ROM `45a42b94dbe7018ad2ba1f737d66dfbf5ee7457c60a034a168c186f4df7cbc69`
replaces Serpent's repeating four-tile scale blocks with nine adjacency-selected
body/edge/corner tiles. A continuous broad violet fill has a lit top/left edge,
dark lower/right edge and rounded exterior corners. Joined segments no longer
draw internal tile borders. Length, occupied cells, collision and OAM allocation
remain unchanged. Dirty cells also invalidate their four neighbors so moving
edges cannot leave stale interior seams.

The first version recomputed adjacency-change masks for every bitmap byte and
cost 701/1200 updates against the original 745/1200. Mask-based lookup reached
704; avoiding redundant palette writes reached only 702. Those failed timing
traces remain under their ROM hashes in `tmp/serpent-performance-*.json`.
The accepted version propagates dirty edges only from changed bytes: 712/1200
(95.6%, within the unchanged 95% limit), versus 722 for the previous flat-tile
candidate. It uses 68 additional WRAM bytes and 565 bytes of bank-15 headroom;
5531 bytes remain free there. The rendering change does not claim free speed.

`test_serpent_body.py` now checks nine loaded tiles, rounded corners without
interior holes, actual selected contour tiles after menu/settlement, the full
28-point body, twelve concurrent projectile sprites, unchanged contact edges
and actual lethal-hit cleanup. Evidence:
`builds/serpent-body-45a42b94-b7189c3e/`. The immutable pre-contour ROM at
`builds/serpent-contour-parent-7fcb0bcd/` fails the new atlas gate. The earlier
702-update variant's collision fixture missed its fixed three-display-frame
window; that failure remains preserved, and the accepted ROM passes without
loosening the probe. Native contour and full-length unwind frames were inspected.

Two complete unwind cycles pass over 3712 display frames with 554 distinct
unwind positions and all 28 segments retained. General room performance remains
176/175/137 updates per 180 display frames. Whole-encounter controller escape
acceptance is still separate and open; geometry/length checks do not prove it.
No hardware was reloaded or deployed.
All nine defeat-cleanup cases and the combined Serpent regression pass. The
fresh 61-card capture `builds/boss-phases-45a42b94-97b05c62/` is served on port
8919 and passes browser acceptance, including selected-only audio decoding.

## Progress: controller-only Serpent survival probes

No ROM changes: candidate remains `45a42b94`. New diagnostic
`scripts/test_serpent_escape.py` (source hash `8c48282a`) enters the authored
encounter using the disclosed stage/sanctuary fixture, then performs no RAM
writes. No health refills, shields, attack suppression or boss-state injection
occur during the measured fight. All display frames, directions, player HP and
positions, boss states, body length and update clocks are retained. Native
stills are taken periodically and on state changes.

Blind perimeter circuits fail: Wolfkin dies after 1278 frames and Sauran after
3257; periodic double-tap dodges alone extend Wolfkin to 3054 frames but still
do not finish two unwind cycles. These are failed control strategies, not proof
of unavoidable damage. The stationary Wolfkin control dies after 2261 frames.

The reactive controller resamples current head, body and projectile positions
every 12 display frames, selects a short safe-looking movement step, and uses
no future emulator-state lookahead. It can read off-camera world positions,
so this is automated feasibility evidence, not human-visible-tell acceptance.
Its optional dash uses actual press/release double taps on a fixed 96-frame
schedule, not a RAM-granted invulnerability timer. Runs do not attack the boss,
so they exercise the natural growth/charge/unwind cycle at opening HP, not
half/quarter-HP encounter acceptance.

Fresh results in `builds/serpent-escape-45a42b94-8c48282a/`:

| Class / control | Completed cycles | Final HP | Display frames |
| --- | ---: | ---: | ---: |
| Wolfkin / reactive + dash | 2 | 6 | 3648 |
| Sauran / reactive, no dash | 2 | 6 | 3567 |
| Corvin / reactive + dash | 2 | 4 | 3650 |
| Picsean / reactive + dash | 1 | 0 | 2430 |
| Vespine / reactive + dash | 2 | 1 | 3840 |
| Wolfkin / reactive, no dash | 0 | 0 | 2080 |
| Wolfkin / stationary | 0 | 0 | 2261 |

Wolfkin's late second-cycle native frame was inspected. Four successful
controller-only runs establish that the moving partitions are not universally
inescapable, but do not close fairness: Picsean's failure, Vespine's thin margin,
off-camera knowledge and untested later HP phases remain explicit. Next work
should distinguish route quality from unavoidable damage and exercise attacks
and class abilities; do not nerf the boss merely to make this bot green. The
existing gallery and all hardware remain untouched.

## Progress: Serpent combat with class signatures

The ROM is unchanged (`45a42b94`). The controller probe now supports real B
presses and aimed A bursts. Its signature-only comparison changes Picsean's
two-cycle result from death to 10 HP remaining: Undertow's native guard is a
material part of the class. Vespine still finishes that survival probe at 1 HP.
These runs are retained under probe hash `0f927e13`.

With A and B enabled, Picsean defeats the full 240-HP Serpent in 4590 display
frames with 5 HP remaining. Boss HP phases 1, 2 and 3 occur through actual
projectile collisions, with no WRAM writes after fixture entry. Sauran's tested
combat policy dies after 9893 frames with 10 boss HP remaining; Vespine dies
after 5544 with 85 remaining. Thus this closes neither all-class combat balance
nor human-controller fairness. Failed runs remain under probe hash `f3cc79c0`.

The final probe `41f663cb` captures optional silent video at half native display
rate. Picsean's recorded and unrecorded runs have identical complete 4590-row
input/state traces. The replay contains 2295 native 160x144 frames over 76.849
seconds, with no speed adjustment or hidden damage suppression. Evidence:
`builds/serpent-escape-45a42b94-41f663cb/`. The controller still reads off-camera
world coordinates and replans every 12 display frames; this is automated
feasibility, not evidence that all warnings are readable by a human.

The existing preview now has a separate `serpent-controller.html` page with the
silent fight, trace download, fixture disclosure and the two failed-class
results. The 61-card phase gallery remains intact. No hardware or ROM deployment
occurred. Next combat work should assess those remaining class routes and the
other bosses' hardest phases, not infer universal fairness from this one win.

## Progress: shared AOE warnings fail safely under crowding

The scope audit found a real gap outside the Serpent controller work: Mire
already cancelled an unwarned ring under allocation pressure, but the other
shared blasts still dealt damage if their warning FX could not be allocated.
An immutable `45a42b94` control reproduces this: full FX occupancy hides the
four warning markers yet Crystal removes two HP at resolution.

ROM `0378df0313298779fb97a8bb8b99e47270e9e3c57280161094d31ed0408361f8`
shares an armed flag across the mutually exclusive ring/blast drivers. Any
failed warning-marker allocation cancels this cast's damage and follow-up
projectiles. New encounters and HP transitions clear the flag. Normal casts
retain their warning duration, radius and damage. This guards allocation
failure; it does not prove every hardware scanline can display all warnings.

`test_boss_area_warning.py` (`c7a7ea2e`) passes 24 native cases across Crystal,
Cinder, Spider, Golem, Hydra and Void: standing inside a complete warning takes
damage; held Right escapes; initial full occupancy cancels the attack; occupancy
introduced partway through the warning also cancels it. Initial positions,
half HP/clock and suppression of unrelated attacks are explicit fixture setup,
not whole-encounter acceptance. Native warning and crowded-resolution frames
were inspected. Evidence: `builds/boss-area-warning-0378df03-c7a7ea2e/`.
The same final test fails the immutable parent with HP 14 -> 12 under crowding.

Mire's eight ring cases and all nine HP transition checks freshly pass. General
performance remains 176/175/137 updates per 180 display frames; Serpent remains
712/1200 against its original 745/1200. The short bank-15 rebuild completed in
seconds and leaves 5506 bytes free. No hardware was reloaded or deployed.
Reaper damage-link and all eight summon cases also freshly pass. The complete
61-card capture `builds/boss-phases-0378df03-97b05c62/` is served on port 8919.
The earlier controller replay remains accessible and is explicitly labeled as
archived `45a42b94` evidence, not a new capture.

## Progress: summoned shots share the boss budget

The dense-encounter audit found that ordinary enemy-shot constructors bypassed
the boss's hostile sprite budget. Natural Spider escorts reached 15 hostile
shots, and Void escorts reached 24, despite the boss constructor's cap of 12.
The immutable `builds/dense-budget-parent-0378df03/` control fails the new native
budget assertion at Spider frame 790 with 13 hostile sprite slots.

ROM `8a3c409b6d784082ee3e526a28733d3fcc4fbece9fc86c62a2d1bc09bdb3cfa8`
centralizes the existing capacity check in `boss_projectile_has_room`. Boss
shots and ordinary monster shots in boss rooms now share the same hostile-count,
sprite-cost and six-free-entity reserve. Normal dungeon enemy constructors are
unchanged. The header change required a full rebuild, which completed normally;
bank 7 has 1783 bytes free and bank 15 has 5490.

`test_boss_dense_performance.py` (`133fe168`) retains every display frame during
1200-frame half/quarter-HP encounters, with natural summons and volleys. It
asserts at least 300 frames containing two escorts, at least six simultaneous
shots, and at most 12 hostile sprite slots. Its 600/1200 update floor is an
explicit engineering guard, not a hardware-framerate promise. Player health is
replenished in these load fixtures; they are not survival tests.

| Boss / HP phase | Before updates | After updates | Peak hostile shots after |
| --- | ---: | ---: | ---: |
| Spider / half | 757 | 757 | 12 |
| Spider / quarter | 706 | 682 | 12 |
| Mire / half | 949 | 951 | 12 |
| Mire / quarter | 702 | 705 | 12 |
| Void / half | 932 | 959 | 12 |
| Void / quarter | 788 | 826 | 12 |

All counts use the full 1200 display frames, including stalls. Encounter
composition changes when shots are refused, so this is not an identical-scene
microbenchmark or a uniform speedup claim. Longest unchanged-update streaks are
two frames except Mire quarter (three). Spider quarter remains the slowest
case. Native Void-with-escorts imagery was inspected. Evidence:
`builds/boss-dense-performance-8a3c409b-133fe168/`.

All three recursive families, eight shared bosses' three-phase volley identities,
eight summon safety cases, 24 area-warning cases and ordinary enemy-pattern
regressions pass. Serpent performance is 715/1200 against the original 745/1200,
within its unchanged 95% guard. This closes the discovered budget bypass, not
every possible crowded scanline or player-attack load. No hardware deployment.

The wider regression run exposed two synthetic-fixture hazards. Reaper's old
link probe cleared/reused a slot while a pre-existing update was still running;
the trace showed the newly placed shot at (80,60) overwritten to (110,-4) and
retired before contact. The fixture now freezes, clears, settles four display
frames, then chooses and initializes an inactive slot. `test_boss_phases.py`
(`fa3d315a`) preserves per-collision traces and uses source-hashed reports. All
nine phase checks pass; the deliberate no-link mutation still fails by damaging
the boss instead of reflecting damage to the player. The dedicated Reaper
grace/sharing/lethal-reward test also passes unchanged.

Serpent's twelve-shot fixture had left the hero wherever prior damage displaced
it. On this ROM that position was (60,76), overlapping the test shot at (64,88),
which ordinary combat correctly consumed. The fixture now explicitly places
the hero clear of the grid before measuring twelve-shot/head OAM coexistence.
`test_serpent_body.py` (`0ad8b214`) records the prior player state and passes;
both full-length unwind cycles pass over 3698 frames. Cinder's pack, armor,
transformation, Rex attacks and reprise checks pass too. Failed fixture traces
remain preserved; no runtime behavior was changed to accommodate them.

On this final ROM, all nine door calls and the four shared movement-voice cases
freshly produce their expected profiles and non-silent native PCM. Hook-free
runs reproduce the complete WAVs byte-for-byte; movement traces match too.
This verifies output/observer neutrality, not subjective listening quality.
General performance stays 176/175/137 per 180 display frames. The completed
61-card preview `builds/boss-phases-8a3c409b-97b05c62/` is served on port 8919
and passes browser acceptance; the archived controller replay keeps its original
ROM label. Listening feedback has been requested separately.

## Rejected optimization: early budget rejection

Candidate `bdd65c24` returned immediately when a partial entity scan already
exceeded the requested hostile sprite budget. It preserved all six budget
gates but did not improve the slowest scene: Spider quarter remained 682/1200.
The other dense results were 756/951/706/958/825, effectively unchanged from
757/951/705/959/826; Serpent remained 715/1200. The extra per-projectile branch
does not earn its complexity here. It was removed, leaving the shared-budget
implementation unchanged. Source-bound candidate traces remain in
`builds/boss-dense-performance-bdd65c24-133fe168/` and the Serpent timing report.

## Spiral arithmetic optimization

Candidate `4ee2b65481bce1e5d83f56bebb8064ad717e565ad0fcc1ea2d007bf6c432696d`
replaces two per-update spiral multiplies with an 800-byte signed lookup.
Radius, angle, timing and negative-value rounding are unchanged. The new
`test_spiral_table.py` checks all 800 values against floor(sine * radius / 16),
finds the exact bytes in compiled bank 15, and rejects a deliberately corrupted
copy. This is exhaustive arithmetic evidence, not a full parent/candidate
native timeline comparison. Native projectile trajectories, all three recursive
families and all eight shared bosses' three-phase volley checks pass freshly.

Dense fixture updates per 1200 display frames are Spider 757/703, Mire 958/735,
and Void 964/847 (half/quarter HP), compared with 757/682, 951/705, 959/826 in
the qualified parent. Every case stays within 12 hostile sprite units.
Serpent remains 715/1200 versus the original 745/1200. The table costs 777 net
bank bytes, leaving 4713 in bank 15. These are emulator fixture measurements,
not hardware speed guarantees or identical full encounter timelines.

At this checkpoint the served preview remained `8a3c409b`; qualification and
the subsequent preview refresh are recorded below. No hardware deployment.

## Current-build phase gallery refresh

Fresh native captures for `4ee2b654` are now served from
`builds/boss-phases-4ee2b654-97b05c62/` on port 8919. All 61 cards completed,
including explicit Serpent, Cinder and Reaper mechanic cycles. Browser acceptance
passes card count, ROM binding, complete event traces, playback, enlargement,
160:144 aspect ratio, selected-only audio decoding, shortlist and modal cleanup.
The selected Serpent screenshot was inspected: the floor is subdued and the
head/body contrast is clear, but a tight coil still merges into a broad flat
purple mass. This remains an art limitation, not a newly solved silhouette.

Fresh current-ROM checks pass all nine phase thresholds/transitions, Reaper
airborne grace/sharing/lethal outcomes, Cinder pack/transformation/Rex/reprise,
24 general AOE warning/escape/allocation cases and eight summon safety cases.
The archived Serpent controller replay remains available at
`/serpent-controller.html`, explicitly labeled with its original `45a42b94`
ROM. It is not evidence of a fresh current-build controller playthrough.
Audio decoding is verified; subjective listening and hardware playability
remain unqualified. This refresh does not deploy to Pocket, MiSTer or itch.

## Serpent dorsal-scale shading

ROM `1c1ed362d322c87d931f24501769d7e3f4b330fc6f6c06323e7028955f35f68e`
changes only six body-atlas bytes and the two global-checksum bytes compared
with `4ee2b654` (full ROM byte comparison). The interior tile gains four lit
pixels and four shadow pixels, retaining 56 base-shade pixels. No code, collision,
palette, tile selection, body length or timing changes. Native before/after
captures show small dorsal scales instead of an entirely flat interior; they
do not resolve merged silhouettes where the body overlaps itself.

`test_serpent_body.py` (`5b82423d`) checks these native atlas pixels alongside
the existing body/contour/menu/OAM/contact/defeat gates. The immutable parent
in `builds/serpent-scales-parent-4ee2b654/` fails specifically on the missing
scales; the candidate passes. Performance remains 715/1200 updates, versus
745/1200 for the original smaller body. Both full-length unwind cycles pass
over 3698 display frames with 554 unwind positions. Native contour screenshots
were inspected; texture is a modest art refinement, not an escape-route fix.

The fresh 61-card capture is served from
`builds/boss-phases-1c1ed362-97b05c62/`; browser playback, binding, event traces,
aspect ratio, audio decoding and controls pass. Archived controller footage
retains its older ROM label. No hardware or public deployment.

## Serpent final growth sweep

The full-grown blob was partly a route problem: the last meal's narrow turns
packed a 16-pixel-wide body into overlapping lanes. Candidate `bfce94ac` widened
all four growth legs, but its opening was unnecessarily long: the unchanged
4200-display-frame cycle test reached only one completed unwind. That failed
trace is retained; the test deadline was not relaxed.

ROM `da33fb7b5b23b0ba5b4e110edd7270dae630967a7368e1f80bb0e05b7fa9b69a`
instead changes only the final four growth waypoints. The early tightening coil
remains; the final meal opens into a broad outer sweep before pursuit. At first
maximum length, the same 28 segments now occupy 56 native background cells
instead of 43. The strengthened body gate requires at least 52 and rejects the
immutable `1c1ed362` parent specifically for folded coverage. Native captures
show a long partitioning body instead of the previous compact filled patch.
Later overlap is still possible during pursuit; this is not a general
self-avoidance algorithm or a claim that every coil always stays separate.

Body continuity, contact edges, twelve-shot/head coexistence, menu restoration
and defeat cleanup pass. Both full-length unwind cycles finish within the
unchanged deadline (4109 frames, 464 unwind positions). The isolated performance
fixture remains 715/1200. A current-ROM reactive Picsean A/B/dash controller
defeats the boss in 6399 display frames with 12 HP, using no runtime RAM writes
after developer entry. Its off-camera state access remains disclosed: this is
an achievable-controller-path check, not human difficulty qualification.

All nine phase checks pass freshly on this ROM. The completed 61-card capture
`builds/boss-phases-da33fb7b-97b05c62/` is now served on port 8919 and passes
browser acceptance. The archived controller video still carries its older
ROM label; the new successful controller run is recorded separately above.

## Continuous Reaper link strategy

On unchanged ROM `da33fb7b`, `test_reaper_controller.py` (`66edaf0d`) enters
stage 6 as Picsean, heals at sanctuary, then sets Reaper to half health once.
There are no subsequent RAM writes. It samples current world threats and the
warning/link state every 12 LCD frames, moves/dashes, and aims A during exposed
intervals. Full LCD/input/HP/phase traces and periodic/state-change native stills
are retained. It has off-camera state access and a staged half-health boss;
this is not a full-run or human-reaction qualification.

Without B shielding, respecting warning/link survives three complete link
intervals in 1951 display frames with 13/15 HP; boss HP falls from 127 to 37
through normal combat. The deliberately reckless `--ignore-link` variant dies
at frame 2058, during the third link (two completed cycles), with boss HP 34.
That variant fails the unchanged survival gate and its failed trace is retained.
The separate fresh native collision test still passes pre-link shot grace,
damage sharing, lethal rewards/unseal and mutual-death ordering. Diverging
controller routes mean the aggregate health difference is not attributed solely
to reflection; the collision test supplies that narrower causal evidence.

An earlier shield-enabled probe (`3d6dfb32`) kept both strategies at full HP;
this did not demonstrate the intended strategic difference, so it is preserved
but not used as the decisive test. The final probe makes B optional, and uses
the unshielded comparison. Native linked-state imagery was inspected. No game
code, balance, ROM, served preview or hardware state changed in this pass.
