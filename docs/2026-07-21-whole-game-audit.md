# Quintra whole-game audit — updated 2026-07-24

## v0.18.73 perceived-scale and arrival-pacing response

The latest attended report is correct: 20–30 logical rooms still feel compact
when physical scale occurs only at isolated row ends. Each snake turn now
forms a scrolling district. Its final two cells flow into the first two
ordinary cells of the next row as consecutive 224×200 worlds; authored
Waystones, Wardens, shops, sanctuaries, and Colossi retain compact role
language. The number of wide dungeon fields rises from 5 to 8 in stage one
and from 8 to 15 in the finale without adding room counters or weakening the
Compass graph.

The same pass addresses a concrete Normal outlier rather than globally
nerfing enemies. Stages two through nine cap only their first combat room at
four non-elite bodies; subsequent rooms retain the 2–7-body budget and elite
roll. Golden Temple's entry drops from seven bodies/154 HP to four bodies/84
HP. In matched stage 4/7/9 controller samples, deaths fall from 4/15 to 0/15
and resolved entries rise from 3/15 to 5/15.

Live-ROM coverage crosses three consecutive wide cells, reaches camera
(64,64), re-enters at the correct far bound, and confirms that the Waystone
returns to 160×136 with a zeroed camera. Transition music still advances
through a 21-frame slide inside a 42-frame total transaction. Twelve seeds per
later stage retain at least six procedural foyer rosters with no elite
promotion.

## v0.18.72 first-play quest-language response

The live visual audit found that the v0.18.67 pocket grid and v0.18.71
scrolling wings now communicate geography, but the game still used **Sigil**
as unexplained lore vocabulary. A player could see the cyan marker and skull
gate without being told that the Rift Sigil is the dungeon's key or which
required fixture followed it.

Champion selection now teaches `SELECT OPENS MAP` and `START OPENS PACK`
before committing to a run. The Pack's formerly empty ninth row now names the
next objective from authoritative persisted state: find the Sigil key, clear
the first Warden, wake the Waystone when the stage requires it, clear the Deep
Ward when present, then seek the skull gate. Riftwild, villages, and live
Colossus arenas instead say to find the dungeon, rest and leave north, or
break the Colossus.

This is passive, backtracking-safe guidance rather than a forced tutorial or
a duplicate quest tracker. A linked-ROM contract advances every exact fixture
bit and verifies all eight messages, plus both menu-control prompts, directly
from the native tilemap. It therefore explains the lore term without weakening
Normal, changing procgen, or interrupting repeat roguelike runs.

## v0.18.71 dungeon-scale response

The report that the stages still feel compact remains correct even after the
6×5 topology work. v0.18.71 therefore changes physical room scale: every
complete snake row ends in a two-room generated wing. Dense approach expanses
4/10/16/22 flow into lighter turn courts 5/11/17/23; all are true 224×200
fields with a 0–64px camera on both axes. Stage one therefore contains six
scrolling dungeon fields and late stages contain eight. Their former 160×136
edge is interior terrain; reciprocal graph doors live only on the 28×25
field's far perimeter. Authored objectives, shops, secrets, sanctuaries,
minibosses, and Colossi keep their own roles, producing a deliberate
compact-room / sustained broad-wing rhythm.

The halls are not empty overscan. Seed-shifted ruin rings, pillar clusters,
stage-colored accents, firing lanes, and encounters occupy the added eastern
and southern sectors. Player collision, enemy routing, projectiles, renderer,
doors, camera, and controller observation share the same world coordinates.
A live-ROM contract reaches camera (64,64), proves all real doors connected,
crosses both obsolete seams and a wide-to-wide graph threshold, exits to an
ordinary 160×136 room, and re-enters at the correct far camera bound.

One direct `court` checkpoint per stage, hero, and difficulty grows both
external curricula to 460 states. Every court restores as 224×200, all 230
Normal/Easy pairs retain identical generated geometry and encounters, and
native mGBA cold-loads all six checkpoint families. This is the first
spatially meaningful dungeon-wing milestone; continuous multi-node regions
remain the next larger engine boundary.

## v0.18.70 two-axis Riftwild response

Riftwild now grows vertically as well as horizontally. Every logical cell is
a real 224×200 world behind the 160×136 LCD viewport, with camera travel from
0–64px on both axes. The old y=136 edge is ordinary generated terrain; the
real south graph threshold is y=184. Entering from the south starts at SCY 64,
and entities, projectiles, collision, enemy routing, camera state, and
controller observation all remain in shared world coordinates.

Each cell now owns a third seed-stable landmark cluster in its southern strip,
plus an encounter in the southeast beyond both former viewport seams. The
complete 4×4 geography therefore covers 896×800 logical pixels before its
nonlinear Rift Wells. Live-ROM coverage visits all sixteen cells through real
reciprocal seams, reaches camera (64,64), checks the original/eastern/southern
landmarks and true boundaries, and completes the gate route.

This materially reduces the reported compactness outdoors. Ordinary dungeon
rooms remain single-screen 160×136 spaces, however, so larger uninterrupted
dungeon wings remain a separate structural milestone.

## v0.18.69 Riftwild scale response

The first reusable wide-world implementation now extends beyond its Crystal
boss proof. All sixteen Riftwild cells occupy a real 224×136 world behind the
160×136 LCD viewport. The old x=160 east boundary is traversable terrain; a
tracking camera reveals eight additional generated columns, and only the
x=216 threshold follows an eastern graph edge. Entering from the east starts
at SCX 64 so the champion is never hidden beyond the viewport.

The extension is not panorama art. Each seed-stable cell owns a second
landmark, trees, paths, collision, and encounter placement in a 136-byte WRAM
terrain strip used by the renderer, collision system, projectiles, enemy AI,
and controller instrumentation. The 4×4 region therefore grows from a
640×544 arrangement of fixed playfields to 896×544 logical pixels with
horizontal camera travel, while nonlinear Rift Wells and the existing
learnable graph remain intact. Live-ROM coverage traverses all sixteen cells,
checks both landmark halves and the old seam, proves reciprocal arrivals at
both camera bounds, and follows the boss-to-world-to-next-dungeon route.

This directly answers the latest playtest report that stages still feel
compact, but it is not presented as the final open-field engine. Logical-cell
and north/south crossings still rebuild a generated field. The next structural
step is to join larger groups of cells—or an entire outdoor stratum—without a
load transition, then use that same world-space foundation for distinct,
spatially meaningful dungeon wings rather than inflating room counts.

## v0.18.68 perceived-scale response

The report that stages still feel compact is correct. A 20–30-node topology
does not feel large when every node is a fixed 160px box. This milestone
therefore changes the engine boundary rather than adding counters: Crystal's
arena is a real 224×136 world behind the 160×136 viewport. Player, entities,
projectiles, collision, drops, exits, and the input-only balance pilot all use
the wider coordinates; the camera travels 0–64px and every ordinary room
resets to 160px.

Crystal now telegraphs and jumps among three authored wells at x=24, 96, and
176. The former right wall is a traversable seam, while the combat boundary
and post-clear exit moved to BG column 27. Live-ROM coverage crosses the seam,
pins the far wall before the kill, verifies the distant warp and full camera
range, exits to Riftwild after unseal, and proves the next Colossus did not
inherit wide state. Dense performance remains 147/180 updates with 12/12
entities active, the complete checkpoint curriculum was regenerated, and the
input-only pilot collects far-side boss relics and leaves the arena.
Passive duplicates also coalesce their presence record while retaining stacked
stats, preventing a long-run inventory registry from dropping a later
guaranteed boss relic's lasting behavior.

This does not by itself make all stages spacious. It is the proving
implementation for continuous Riftwild fields and larger landmarked dungeon
wings. Those should now reuse a tested world/camera path instead of inventing
screen-specific scroll tricks.

## v0.18.67 pocket-grid response

The 16×16 Compass nodes were individually legible but made a 20–30-room
dungeon look like a few isolated boxes because only the explored frontier
appeared. SELECT now renders the complete active 6×5 footprint as one-tile
rooms and one-tile reciprocal corridors. Unknown geography is dim; visited
rooms and links brighten; objective identity remains earned. A permanent
right-hand `YOU / ROOM / SIGIL / TRIAL / BOSS / RIFT` key makes the abstract
language self-explanatory on the cartridge rather than in this audit.

The current Normal curriculum still supports the user's report that the run
can become difficult early, but not a global nerf. The same generic policy
clears 10/45 progression-matched Colossus checkpoints and survives 11; stage
five and the finale defeat all five policies. In ordinary entry rooms it
resolves 14/45, with four deaths concentrated in Golden Temple's seven-body
154-HP pack. Stage-three pressure ranges from no damage for Wolfkin to twelve
half-hearts for Vespine. These are targeting-policy diagnostics, not human
balance verdicts, but together with the attended stage-three feedback they
identify attrition and class readability as higher priorities than another
global enemy-HP increase. Every pre-boss sanctuary already restores full HP
and MP, so boss duration and dungeon attrition can be tuned independently.

Fresh attended feedback also confirms that the enlarged dungeons still
*feel compact*. The opening dungeon owns 20 screens but its direct route is
only 12 room visits; the 30-screen finale is 22 direct visits, or 29
transitions when sweeping the required Sigil, Wardens, and Waystone in order.
More room counters are therefore not the next scale fix. Continuous outdoor
fields, distinctive side-wing landmarks, and arenas with real camera travel
are the active structural gap.

## v0.18.60 wider-stage response

Human playtesting still found the 10–16-room campaign compact. The nine-stage
ramp is now 14, 15, 16, 16, 17, 18, 18, 19, and 20 rooms including each boss:
153 dungeon screens in a successful run. Dungeons use a reciprocal 5×4 graph,
and the Compass exposes all active nodes and possible cardinal links in dim
ink before visited rooms and traversed links brighten. Rooms 2 and 8 own the
farther nonlinear Rift Well pair.

All stages now carry the full Sigil → Warden Boon → Waystone → Deep Warden
fixture chain; the 19- and 20-room routes add a third miniboss. A west-entry
Rift Well regression exposed both a severed 12px-body route and stale
reachability metadata. Rift rooms now reserve a full central cross, rendered
tilemaps sanitize scratch bits after puzzle authoring, and authoritative
collision masks the same metadata. v0.18.58/v0.18.59 suspend saves migrate to
equivalent stages and thresholds rather than being invalidated.

Stage-authored terrain now also owns a dedicated local-room-four landmark.
This preserves full grove, gauntlet, vault, mire, keep, temple, blood-sigil,
and void silhouettes away from the safety apron carved around Rift Wells,
giving the wider routes another strong spatial identity instead of padding
their room count with only generic layouts.

## v0.18.58 dungeon-depth response

The nine-stage ramp remains 10, 11, 12, 12, 13, 14, 14, 15, and 16 rooms
including each boss arena: 117 dungeon screens in a successful run. Those
cells now form reciprocal 4×4 topology with loops, backtracking, and visible
missing exits instead of one disguised room-counter corridor. The Compass
persists all sixteen seen bits and reveals the next missing fixture rather
than flattening the route into a boss arrow.

Every stage now requires the room-two Rift Sigil and room-three Warden Boon.
Stages with at least twelve cells also require the room-seven Waystone puzzle;
stages with at least fourteen require the room-nine Deep Warden. The sanctuary
door checks that chain before admitting the boss. This turns later stages into
multi-leg expeditions across the existing footprint instead of letting a
fortunate diagonal collapse a 4×4 map into a handful of transitions. Towns
remain after stages three and six.

This pass also exposed a genuine traversal defect: one nonlinear Rift Well
landing could be visible but unreachable behind generated structure. Both the
C runtime and Rust reference now clear a champion-width route from the landing
to the central lane. Linked-ROM contracts cover all stage sizes, late puzzles,
both miniboss thresholds, the unsealed opening shop, dungeon/Riftwild maps,
Rift Well paths, villages, stage architecture, and all nine boss identities.
The controller-only whole-run proof now needs 89,900 frames (**24:58** at
60 Hz), up from 74,880 (**20:48**) before the fixture chain, and finishes all
nine bosses with 9 HP. The current ROM SHA-256 is
`da14ffddce2f3167d7945c421c48de08583c47be170fd960a9d07166ee527663`.

## v0.18.54 transition-latency finding

The reported room-change drag was measurable and was not caused by the
Zelda-style camera motion. A live cartridge trace measured 103 frames from
door acceptance through restored gameplay, while the actual camera slide
occupied only 17 frames. Most of the hidden time belonged to the generated
room's champion-body reachability flood: it repeatedly rescanned the full
20×17 tilemap and crossed from bank 2 into bank 1 four times per candidate
footprint.

v0.18.54 keeps the identical four-tile walkability predicate but executes it
locally and floods each cell once through a bounded WRAM queue in bank 6. The
complete transaction now measures 38 frames, including procgen, enemy safety,
progression and puzzle fixtures, an 18-frame slide, palette/HUD refresh, and
sprite restoration. The live-ROM gate rejects totals above 45 frames and
requires the music sequencer to advance during scrolling. Cardinal-door,
push/rune/phase-puzzle, and sixteen required-miniboss reachability contracts
still pass. The optimization restores bank-2 headroom from 1,070 to 1,615
bytes; bank 6 retains 10,031 bytes.

## Verdict

Quintra is already a credible public **alpha/beta ROM**, not a prototype. The
complete nine-stage run, five differentiated champions, procedural room
generation, Riftwild, three-screen villages, Sigil gating, merchants, relic
builds, secrets, selective combat seals, lore intro/ending, battery suspend,
and real-cartridge checks are all implemented. The largest remaining risks are
Normal-mode balance evidence, first-play communication, boss scale/presentation,
original music composition, and release hygiene around a very large shared
worktree.

It is close enough to show publicly with honest prerelease language. It is not
yet ready to call 1.0.

## Evidence snapshot

- The live cartridge is a valid 128 KiB CGB-only MBC5 image with 32 KiB battery
  RAM and valid checksums.
- Procgen variety is now measured at both seams. After normalizing decorative
  floor texture, the Rust reference produces 393 meaningful room silhouettes
  across 512 seeds, reaches secret cracks on all four walls, both premium shop
  forks, and all four Rift Well anchors. The linked cartridge then produces
  12/12 distinct entry geometries and 12/12 distinct encounter rosters in each
  of all nine stages across 108 samples; each stage exposes 5–7 enemy species,
  ordinary population varies from 2–7, and elites remain represented. This is
  evidence for gameplay-affecting cover/hazard/roster variation rather than
  floor-speckle randomness.
- Riftwild now has four seed-rotated geographic families—meadow, pond,
  standing stones, and old-growth stumps—distributed exactly four times each
  across its 4×4 world. A linked-ROM sweep crosses all fifteen connecting
  seams, verifies every family and the uninterrupted central trail cross, and
  captures all sixteen cells as one native-resolution atlas. The same landmark
  layout remains pinned across paired Normal/Easy states; this improves
  geographic memory without weakening or forking encounter balance.
- All used ROM banks have headroom; the tightest switchable bank retains 1,409
  bytes and the home bank ends at 0x3D21 (735 bytes free).
- Targeted live-ROM tests pass for all cardinal door transitions, the fixed
  lower-edge block collision, immediate heart HUD redraw, the 10-to-16-node
  4×4 Compass, the boss-threshold warning, all nine boss silhouettes, and the
  tested stage-specific boss movement. All nine encounters now use validated
  screen-scale BG bodies: the opening Crystal guardian is 112×72, Verdant's
  hollow Storm Serpent coil is 112×64, Cinder Maw's furnace face is 112×64,
  Frost's hollow web-spider is 112×64, Toxic Mire pulses between 64×48 and
  96×64, Shadow's tattered Reaper cloak spans 112×64, Golden Temple's awakened
  idol spans 112×72, Bloodmoon's three-headed Hydra spans 112×64, and Void
  Sanctum holds a 128×80 astral body.
- A deterministic controller-only Easy test run clears all nine bosses, then
  a fresh emulator reproduces the ending from its exact recorded inputs at
  frame 53,991 with 15 HP. Its seed, procgen, rooms, enemies, patterns, towns,
  and Riftwild are identical to Normal; only the documented player-side test
  assist differs. This proves the complete systemic route and replay chain.
  It deliberately does not claim that a heuristic bot has balanced Normal.
- The final 2026-07-22 `make verify` pass completed uninterrupted after the
  mandatory media/state regeneration. It covers the cartridge header and
  layout, Rust/linked-ROM procgen parity and variety, 460 hash-bound
  Normal/Easy checkpoints, all nine colossal encounters, all 32 enemy IDs,
  overworld/village/Sigil routes, HUD/pickups/shops, combat abilities, exact
  Easy victory replay, focused hard-Normal policies, and deterministic input
  replay. The verified ROM SHA-256 is
  `f9808a7c18bae41c242d0605a1058116286001b4b04e7f698ffbe3b3087326d7`.
- The ROM-bound README reel now shows the live tile Compass, screen-scale
  Crystal Colossus, Riftwild/vault traversal, a real labelled village arrival,
  and the full ending instead of skipping the civic cadence. Its eleven
  supporting stills are regenerated in the same transaction and covered by a
  combined hash, preventing the former small-boss, missing-village, and
  fake-room screenshots from silently surviving a release.
- A ROM-derived 3×3 boss gallery now places all nine Normal encounters side by
  side. Their maximum live BG footprints are 110/84/96/94/84/96/106/100/144
  tiles; Toxic Mire is sampled in its expanded phase rather than misleadingly
  shown only as the 36-tile clenched heart. Gallery and capture-script hashes
  are part of the media gate.
- The expanded-route controller initially produced false room-one stalls:
  the Lua file exceeded mGBA's 200-local compile limit, then its new cairn
  policy stopped two pixels before the hero's real leading-edge push probe.
  The corrected controller compiles, holds the required ten contact frames,
  and gives authored puzzle and exact Sigil routes priority over generic
  unstick nudges. A fresh three-world, five-champion Normal matrix records all
  15/15 rows with **zero route stalls**. Crystal is cleared in 14/15 runs;
  median first/second Colossus clear times are 676/1,475 frames
  (11.3/24.6 seconds). Median maximum rooms reached are Wolfkin 12, Sauran 21,
  Corvin 10, Picsean 27, and Vespine 20. Two runs die, no run finishes the
  campaign, and combat stalls remain concentrated in Wolfkin/Corvin rather
  than navigation. This replaces the stale pre-expansion 34-clear sample but
  remains controller evidence, not a human verdict.
- Human playtest evidence from the earlier small-boss build points in the
  opposite direction: bosses one through roughly four felt disposable in
  5–10 seconds, while
  ordinary rooms became punishing and navigation became confusing around
  stage three. That mismatch means global enemy or boss multipliers would be
  the wrong next move.
- The corrected first-three-stage room pilot now sidesteps blocked retreat
  lanes instead of walking into a wall. It resolves or exits 10/15 fixed entry
  matchups, but the stage-two fixture still strands all five champions against
  three Orcs and a Hornet: one Orc is an elite, producing 76 combined hostile
  HP. Because this is one deterministic world rather than human or multi-seed
  evidence, v0.18.48 keeps the elite's HP, damage, and odds intact. Its sure
  reward instead becomes a half-heart when the player is wounded (five coins
  at full health), converting that spike into recoverable risk/reward without
  globally lowering Normal.
- All 460 direct checkpoints and the six automatic 5/10/15/20/25/30-minute
  training checkpoints now name the same current ROM hash. The periodic set
  had still pointed at an older cartridge despite loading correctly when it
  was first created; it has been regenerated and fresh-emulator verified from
  stages five through eight.

## Difficulty contract

Normal is the canonical game and the only mode whose balance gates should
block a release. Enemy HP, encounter population, movement, projectile speeds,
boss patterns, procedural topology, shops, and relic rolls remain authored for
Normal.

Easy is currently an intentionally generous deep-testing aid. It gives every
champion eight fully visible hearts, +4 ATK, +2 DEF, caps each impact at one
half-heart, quadruples the post-hit repositioning window, and lengthens the Gloom
Leech drain interval. It deliberately
traverses the same generated game. Easy-mode tuning
should wait until Normal's target curve is stable; otherwise two moving targets
will hide whether encounter design or the assist layer caused a result.
The paired-state live-ROM contract checks all 230 Normal/Easy checkpoint pairs
and requires identical generated tiles, route/progression state, hostile
placement and HP, and boss-pattern identity. Easy may soften the hero-facing
numbers and timing allowances, but it may not author different content.
Both curriculum diagnostics accept `AUDIT_DIFFICULTY=easy`, providing a direct
same-checkpoint comparison against canonical Normal. These comparisons measure
whether the broad testing assist works; they are explicitly not Easy balance
gates and cannot justify weakening Normal content.

On the v0.18.52 deterministic curriculum, the same deliberately generic pilot
clears 12/45 Normal boss fixtures and 27/45 Easy fixtures; survival rises from
14/45 to 32/45. Ordinary-room deaths fall from 5/45 in Normal to 1/45 in Easy.
The final Void Lord still defeats the
generic pilot in either mode because World Collapse is an authored positional
check whose marked safe pocket needs a dedicated response; that is evidence
about the policy, not permission to erase the intended near-roomwide attack.
Easy therefore provides substantially more observation time without changing
the generated world, while Normal remains the only balance target.

## Human Normal acceptance queue

No interaction-bearing v0.18.52 human-session report exists yet. The current
stage-two probe observed zero input and is correctly excluded, so automated
completion and curriculum evidence still cannot prove that Normal is fun or
that the cues read correctly on first sight. The shortest high-information
pass is:

1. `make play-state STAGE=2 CHECKPOINT=entry HERO=wolfkin` — test the early
   76-HP pack that produces the first measured pressure spike.
2. `make play-state STAGE=4 CHECKPOINT=sanctuary HERO=sauran` — approach the
   amber skull gate, confirm the roar reads as a commitment warning, then test
   the Frost Spider with a defensive champion.
3. `make play-state STAGE=8 CHECKPOINT=entry HERO=vespine` — test the measured
   170-HP, seven-enemy bullet room with the melee/flail vessel before
   attributing controller deaths to global enemy health.
4. `make play-state STAGE=8 CHECKPOINT=boss HERO=picsean` — judge whether Blood
   Hydra's huge body and five mixed-speed streams feel demanding rather than
   merely lethal.
5. `make play-state STAGE=9 CHECKPOINT=boss HERO=wolfkin` — verify that the
   marked World Collapse pocket is readable under real input.
6. `make play-state STAGE=1 CHECKPOINT=riftwild HERO=corvin` — press Select
   after crossing cells and verify the compressed 4x4 graph, current node,
   gate, rift, boss, and legend are understandable without the README.

Each checkpoint opens host-paused. Focus its SDL2 window and press any game
control (or `P`); the cartridge and passive report both begin only then. The
launcher consumes that first game-control press as readiness, so it cannot
fire, move, or open a menu on the first live frame. This prevents live-room
damage while the tester is finding the new window from contaminating the
Normal-mode evidence.

Closing each window writes a ROM-hash-bound report under
`tmp/human-playtests/`. A session-unique atomic `active-*.json` refreshes every five seconds,
preserving partial evidence if the graphics window or host session dies before
the normal timestamped final report. This uniqueness is required in the shared
workspace: older idle emulator windows can remain alive for hours, and the
former checkpoint-only filename let them overwrite a new tester's evidence.
A durable final report removes only its own live snapshot. Post-poll joypad
frame/edge counters mark
whether interaction was actually observed; an idle hero losing HP is not human
balance evidence. Re-run any mechanically blocked fixture with
`DIFFICULTY=easy`; Easy is an observation assist, not a substitute acceptance
result. The first Normal tuning pass should respond to those reports and the
player's qualitative notes together.

## Inspiration audit

### Penta Dragon

Quintra already carries the useful combat DNA: dense but differentiated
projectiles, stage-colored large enemies, movement-specific bosses, hit
recovery, elemental/build variation, and an agile compact playfield.

Penta Dragon also makes its temporary dragon form a central reward: kills or
a dedicated pickup turn Sara into a stronger form, while plentiful healing,
shot upgrades, protection, and invincibility offset the moving-arena pressure.
Quintra's equivalent is the full-MP 18-second Spirit Convergence. The live
cartridge now makes that system discoverable rather than merely implemented:
the Pack says `FULL MP A B CHORD`, and full MP digits turn icy white until B or
Convergence spends the meter. This changes no combat values.

The major missing ingredient was **boss spectacle as moving arena**, not merely
more HP or more bullets. The checked Penta Dragon guide describes camera
movement as part of several encounters: Crystal Dragon warps between holes
while the camera follows; Ted rotates the camera around its body, adds
removable vines, and exposes its head; Faze occupies most of the screen and
compresses safe movement into the side lanes; and the final dragon's huge
body/camera can corner the player around a vulnerable belly. Cameo is likewise
called out as a very large chameleon, but the checked guide does not establish
the same rotating-camera behavior, so this audit does not attribute it. The
sprite archive independently lists eleven enemy/boss sheets, including the
named Crystal Dragon, Cameo, Ted, Faze, and Penta Dragon forms.
That confirms the remembered distinction: at least several Penta Dragon fights
move a camera over boss terrain rather than presenting a large sprite against a
completely fixed single screen. Quintra now borrows that scale and motion, but
its bounded sub-tile drift remains a one-room illusion; a genuinely scrolling
multi-screen Colossus arena is still future engine work, not a completed claim.

The opening Crystal guardian now makes that moving-arena influence visible
immediately instead of reserving it for Verdant and Void. Its 112×72 BG body
orbits by a bounded 0–3px horizontally and 0–1px vertically while the hero,
OBJ weak point, HUD, and collision grid stay fixed. All boss rooms prepare one
offscreen BG row and column, preventing the drift from exposing streamed-room
garbage. The motion changes no HP, damage, cadence, projectile, or Normal/Easy
value, and dense-combat performance remains 148/180 CGB loop frames.

Sources:

- <https://gamefaqs.gamespot.com/gameboy/569778-penta-dragon/faqs/68202>
- <https://www.spriters-resource.com/game_boy_gbc/pentadrag/>
- <https://longplays.org/infusions/longplays/longplays.php?longplay_id=15989>

| Penta Dragon encounter evidence | Quintra response | Fidelity boundary |
|---|---|---|
| Crystal Dragon camera-follows-hole warps | Frost Spider/Reaper warned flank warps; Void anchor jumps | One-room anchors, not world-camera pursuit |
| Ted rotating camera, removable vines, head weak point | Mire/Hydra arena breath; mobile OBJ weak points; destructible ordinary hazards | No full circular camera track inside a boss room |
| Faze occupies most of the screen and constrains side lanes | 112×64 Hydra plus five streams; 128×80 Void body and marked pocket | BG body remains walkable so its art never creates invisible contact |
| Final dragon camera/corner pressure and belly weak point | Void's room-scale body, moving core, and near-roomwide Collapse | Collapse is telegraphed; the intended safe pocket remains visible |

Quintra's original giants were nine distinct 32×32 OBJ metasprites. That was a
good silhouette system but only 6.3% of the 160×144 screen area, and each giant
already consumed 16 of the GBC's 40 hardware sprites. A naive 64×64 OBJ boss
would exceed the total OAM budget before player, bullets, or effects and would
run into the ten-sprites-per-scanline limit; the current ROM therefore uses the
BG-body/OBJ-weak-point architecture described below for every stage boss.

The practical architecture is a room-sized **BG body plus OBJ weak point and
effects**. Void Sanctum proves that architecture in the live ROM: a
144-tile, 128×80 astral body occupies most of the arena while the existing
32×32 OBJ core stays vulnerable, holds a readable 36-frame punish window, then
jumps among authored face/maw anchors. Paired BG eyes blink, SCX breathes by
0–3px, projection tiles remain traversable, and World Collapse flickers its
actual safe corner. Toxic Mire proves the architecture can express a
different mechanic rather than merely clone the finale: its live movement
phase expands a dedicated organic BG silhouette from 36 tiles/64×48 to 84
tiles/96×64, then contracts it again around the original vulnerable heart.
The opening Crystal Colossus brings that spectacle into the path every tester
actually sees: a 110-tile, 112×72 guardian surrounds its original pursuing
heart without changing its 200 HP, damage, ring/aimed pattern, or riftbreak.
Verdant follows with a different Penta-style idea: an 84-tile hollow storm
coil makes the boss body part of the arena, animated charge travels through
it, and a bounded 0–3px camera sway adds scale while the original 205-HP OBJ
head keeps its diagonal rebound and rotating four-lane cross unchanged.
Ember Depths now carries that scale into boss three without cloning Crystal:
its 96-tile, 112×64 furnace beast opens through breath and hard lunge, then
clenches during the existing recovery window around the original moving core.
Its 150 HP, damage, aimed three-shot breath, lunge, and cadence are unchanged.
Frost follows with a hollow 94-tile, 112×64 web-spider: paired eyes and charged
strands pulse while the original 150-HP weak point keeps its warned flank
blink, alternating four-lane web, and post-blink punish beat unchanged.
Shadow Keep adds a widening 96-tile, 112×64 spectral cloak with a tattered
hem: its face and void folds phase while the original 255-HP weak point keeps
the warned hunt, flank re-entry, and three-shot burst unchanged.
Bloodmoon's Hydra extends the same architecture into a different late-game
language: a 100-tile, 112×64 three-headed coil alternates its side heads and
central maw around the original moving weak point. A bounded 0–3px horizontal
camera weave now gives that late arena the same spatial pressure
the Penta Dragon guide attributes to Faze, while Toxic Mire's pulse receives a
slower camera breath. Golden Golem remains deliberately static, paralleling
Troop's documented role as the original game's camera-independent exception.
Hydra's window is now 150 HP,
while damage, slow weave, and five mixed-speed streams remain unchanged. Every projection
remains walkable. Golden Temple completes the set with a 106-tile, 112×72
carved idol whose paired eyes and sun seals alternate stone sleep and wake
around the original pursuing weak point and unchanged slow heavy ring. All nine
load distinct BG art through the same phase-safe slots. The current Normal
matrix reaches boss one in 14 of
15 runs and clears it in 12, at a 607.5-frame median; one run falls to the
required Sentinel and two to Crystal, with no route or combat stalls. The dense-projectile
performance fixture is 148/180 loop frames, above the 80% CGB target. All nine
forms are now technically validated; human Normal play still has to establish
that each body reads as one creature and that its pattern duration feels fair.
The ROM-bound README media now includes a 16-frame animated 3×3 atlas sampled
across the same two-second live window for all nine Normal fights, plus the
maximum-footprint still. This makes the movement comparison inspectable rather
than hiding later bosses behind unit-test output.

### Zelda 1

The dungeon loop now has the important vocabulary: a centered six-node
single-glyph room graph whose dim slots brighten and connect as explored,
fog-of-war Compass, objective gating, secret-wall and block puzzles, a
satisfying puzzle jingle, selective kill-to-unseal rooms, merchants,
sanctuaries, and streamed cardinal room slides. The new amber/roaring boss
threshold gives the equivalent of a boss-door warning without adding a modal
dialog. Native-resolution review exposed two presentation bugs in that
otherwise-correct logic: HERE/SIGIL/BOSS used different attribute slots but
identical loaded colors, and the amber threshold still shared ordinary door
art. The live ROM now uses cyan/violet/amber semantic nodes with a tile-native
`YOU / SIGIL / BOSS` key, plus a dedicated skull/barred boss gate backed by the
same proximity roar and tremor. The threshold art now assembles as one 16×16
amber skull seal across the door and its inner walkable cell in every cardinal
orientation; this replaces the former two tiny, identical-looking north-door
squares without changing collision or procgen. Rendered-color, tilemap, audio, cardinal-door,
procgen-parity, and smoke contracts cover the result.

The Compass now also owns the dungeon's actual nonlinear topology. In dungeon
two and later, discovering one rift-well room reveals one violet endpoint;
discovering its paired nonadjacent room completes a four-diamond diagonal edge
and a tile-native `RIFT` legend. This preserves the intentionally disorienting
teleport while preventing the map from lying that only the cardinal snake
exists. A tile-native `MAP` heading now identifies dungeon, village, and
Riftwild diagrams without returning to the old truncated font page. A live
rendered-color contract covers partial and complete discovery.

Native review found that Riftwild's taller 4×4 variant initially started on
the same row as that heading, overwriting `A/P` and leaving a stray `M`. Its
grid now starts two rows lower and ends exactly on LCD row 17; the live
overworld contract pins the intact heading and shifted visited/current/vault
cells.

The graphical village variant now labels its left, centre, and right nodes
`FORGE`, `VILLAGE`, and `MARKET` using the same tile-native alphabet as the
live civic landmarks. This keeps the three-node diagram compact while removing
the earlier requirement to decode roof/crystal shorthand from documentation.

Riftwild now uses that same compressed graph language. Its former sixteen
3×3 terrain thumbnails filled almost the whole LCD but left the current,
gate, cave/rift, and boss colors unexplained. The live cartridge instead draws
the visited 4×4 topology as one-glyph nodes and two-tile links, with a right-
hand `YOU / GATE / RIFT / BOSS` legend. All sixteen dim hollow slots establish
the square grid on first sight, while unseen identities and links remain
fogged; a discovered vault retains the familiar violet objective diamond.
This makes the outdoor route materially easier to parse without revealing the
whole authored graph or changing any Riftwild encounter/progression state.

The live playfield now adds amber tile-native `RIFTWILD`, `VILLAGE`, `MARKET`,
and `FORGE` landmarks without replacing the walkable generated terrain below
them. Together with the graphical town Compass, that removes the specific
failure where a working overworld or three-screen village looked like another
dungeon room. The remaining Zelda-like problem is fresh-player communication:
room graph, Sigil objective, merchant offer, movable-landscape cairn, and the
meaning of each outdoor landmark still need validation through recordings
rather than more explanatory README text.

### Final Fantasy Adventure

The strongest match is now Wolfkin's input-shaped melee kit and the run's RPG
stats/relic curve. The broader weapon set—flail and spear in addition to class
starters—helps, but weapon identity should continue to come from geometry and
commitment rather than from recolored ranged shots. Full-power sword beams are
appropriate as an earned exception, not Wolfkin's default attack.

### Ultima: Runes of Virtue

Riftwild's nonlinear traversal, cave/vault links, town cadence, compact
portable-room exploration, and explicit in-play area identity are on target.
The former geographic-continuity risk is materially reduced: every run now
rotates four unmistakable landmark families across the 4×4 graph, while the
fixed Riftwell, cave/vault, boss, and dungeon-gate cells retain lore identity.
The remaining question is human, not structural—whether the ponds, meadows,
stones, and stumps are memorable enough during combat without reading the
Compass. Quiet landmark cells already include the Riftwell, gate, and vault;
do not enlarge or depopulate the world until a fresh player tests this rhythm.

## Priority order

1. **Normal first-three-dungeon human balance pass.** Capture class, seed,
   room, death source, boss fight duration, build, and whether the player knew
   the objective. Tune ordinary-room survival and giant duration separately.
   Initial targets: a practiced early giant should survive long enough to show
   at least two full pattern cycles; an ordinary mandatory room should threaten
   without consuming most of a seven-heart bar.
2. **Release correctness.** Finish the full verification stack, regenerate
   media from the final ROM, confirm reproducibility, and separate/attribute
   all shared-agent edits before any commit or release. Never force-push over
   unreviewed work.
3. **Human-test the nine colossal forms.** Crystal's 112×72 guardian/pursuing
   heart, Verdant's 112×64 charged coil/mobile head/sub-tile sway, Cinder's
   112×64 breath/lunge/recovery furnace, Frost's 112×64 hollow web/blinking
   weak point, Shadow's 112×64 tattered phased cloak/mobile core, Void's fixed
   128×80 body/mobile weak point, Mire's 64×48↔96×64 pulse, Golden Temple's
   112×72 awakened idol/pursuing heart, and Hydra's 112×64 alternating
   three-head coil pass footprint, collision, art-identity,
   pattern, and video-rate contracts.
   Verify that each reads as one creature during real Normal play before
   selecting another giant for large-form treatment.
4. **Fresh-player readability.** Test the Compass/Sigil, shops, village,
   Riftwild, push-block secret, A/B descriptions, cooldown bar, and Easy toggle
   with someone who has not read the README.
5. **Music composition pass.** Keep nine exploration/boss track identities,
   but replace or revise phrases through the documented composer workflow so
   the music can honestly be credited as player-composed rather than merely
   generated variants.
6. **Easy balance later.** Once Normal's curve is stable, tune the assist from
   observed tester friction. Prefer a few legible modifiers over a second set
   of enemy/content tables.

## Checkpoint/testing workflow

Every build produces 460 manifest-bound PyBoy states: all five champions in
Normal and Easy at entry, scrolling-court, pre-boss sanctuary, and live-boss checkpoints for
all nine stages, fresh Riftwild arrivals after stages one through eight, plus
the village arrivals after stages three and six. The
sanctuary fixture settles the entire streamed room slide, arrives before the
proximity roar, carries the recovered Sigil, and exposes the marked forward
gate; it therefore tests warning and fight as one sequence instead of skipping
the requested cue. Late states carry a deterministic prior-boss relic curve.
Use `make play-state STAGE=7 CHECKPOINT=sanctuary HERO=sauran` to exercise the
warning before Golden Temple's Colossus. Use
`make play-state STAGE=1 CHECKPOINT=riftwild DIFFICULTY=easy` to enter a fresh
post-boss Riftwild and test its compact Compass without replaying a dungeon;
here `STAGE` is the dungeon just cleared and may be 1 through 8. Use
`make play-state STAGE=3 CHECKPOINT=village DIFFICULTY=easy` to enter the first
village directly; for a village checkpoint, `STAGE` names the dungeon just
cleared and may be 3 or 6. The interactive launcher now writes a passive,
ROM-hash-labelled JSON report when its window closes. It records room
transitions, unique dungeon/Riftwild locations, HP loss and recovery,
Compass/Pack opens, peak hostile/projectile counts, and every giant attempt's
duration and remaining HP. It never supplies controller input or edits WRAM;
this closes the evidence gap between autonomous route proofs and the required
human Normal pass without pretending either is the other. `make timed-states`
runs controller-driven Easy segments from stage four for 30 emulated minutes
and atomically captures a new state every five minutes; duration is overridable
with `TIMED_MINUTES`. If a whole interval has no forward room/world/boss
progress, the external trainer loads the next matching stage entry and records
that curriculum advance. With the corrected cardinal-fire/orbit policy, the
current six checkpoints span stages five through eight instead of cloning
one stuck room; the direct curriculum still covers every stage and champion.
`make play-timed-state TIMED_CHECKPOINT=25` opens any periodic state under the
same controller-friendly readiness pause and passive ROM-bound reporting used
by direct checkpoints, so a deep manual session cannot begin or lose evidence
while the tester is finding the window.
Their manifest pins the
ROM, source state, policy, PyBoy version, and every state hash. These are
external emulator fixtures, never an in-ROM save-state feature, and PyBoy
states are not interchangeable with mGBA, MiSTer, or EverDrive state formats.

`make boss-curriculum-audit` runs the small framework-neutral PyBoy pilot from
every Normal live-boss state. It is an observation/policy diagnostic, not a
balance gate: its early results remain far below the independent mGBA matrix
and the assisted nine-boss systemic replay. That contradiction has exposed trainer
bugs rather than justified ROM nerfs: walkable 55–63 colossal projections were
treated as walls, held A+B activated neither signature nor Convergence, a
valid firing lane still returned “walk into the boss,” neutral turbo fire kept
the previous dodge-facing, and 48px physical attacks were held just outside
their real collision lane. The latest controller also rejects diagonal rays as
four-way attacks, separates approach/retreat from firing, makes one decision
per emulated frame, and orbits colossal bodies instead of backing blindly into
an arena wall. On v0.18.52 the current one-minute matrix clears 12/45
progression-matched fights and survives 14/45.
Picsean owns six clears, Wolfkin three, Corvin two, Sauran one, and Vespine
none. The pilot clears two of five Crystal, three of five Storm and Cinder
fixtures, clears two and times out alive in two Frost fixtures, and has no generic
clear against Blood Hydra or the marked World Collapse. That remaining class
and mechanic skew is a useful human-test lead,
not permission to nerf Normal around a small heuristic policy. The exact
assisted Picsean replay remains the systemic completion proof; attended Normal
play remains the balance authority.

`make room-curriculum-audit` complements that boss-only sample with every
progression-matched Normal stage-entry room and champion. It records starting
body/HP burden, peak projectile count, cumulative HP loss, death, hostile
clear, and room exit independently. Entry exits can be open and the same small
pilot has strong class-specific targeting bias, so this is a pressure trace,
not a pass-rate balance gate. The v0.18.52 sample resolves 21/45 fixtures:
19 exits, two hostile clears, five deaths, and 19 unresolved survivals.
Stage two causes two deaths and 9.8 HP average loss against its 76-HP pack;
stage eight causes the other three deaths and averages 11.8 HP loss against a
170-HP seven-enemy room, while stages one, three, four, and nine permit every
pilot to resolve or exit.
That evidence does not justify a global Normal nerf; it gives later human tests
exact late-stage rooms to compare against the earlier stage-three difficulty
report.

# Non-gating Normal policy research

The historical Sauran right-edge lane replay is no longer a correctness gate.
With the Penta-scale boss campaign, that controller dies at the fourth boss
before it can reach the room-31 Skeleton fixture even in Easy. Keep the replay
as a standalone policy experiment; do not weaken Normal or claim the lane was
tested from an earlier death. The assisted Picsean nine-boss replay is the
end-to-end system proof, not a Normal balance substitute.

The historical Vespine Mirror Moth route is likewise standalone policy
research: its fixed controller now dies at an earlier colossal boss before the
stage-six fixture, even with the coarse tester assist. The live Mirror Moth AI
and art remain covered by the enemy-identity contract; a future checkpoint-
started input policy should replace this unreachable full-run prerequisite.

The town-continuation controller is deliberately an Easy route fixture: it
checks the market, civic quarter, north gate, and next-dungeon transition, not
combat balance. Normal remains canonical through the dedicated boss policies,
curriculum audits, and attended playtests.

That assisted replay now pins class-select frame 1040 / run seed 2064129883. In
its final Sigil room a 2-HP crawler legitimately hugs the one-tile top edge,
where the pilot's cardinal BubbleBolt route cannot acquire a pixel lane. The
controller closes toward a reachable same-row proxy and uses Picsean's real
three-lane Tidal Wave; it then clears the ninth boss and replays the exact
input trace from a fresh emulator. No ROM enemy position, HP, damage, RNG, or
Normal-mode value is changed to make the proof pass.

Wolfkin's fixed sealed-Leech lane is also an Easy route fixture. The live-ROM
Leech test separately owns latch release, the post-dash lockout, and legal
edge placement; the controller replay only checks the clear Fang-lane choice.

Wolfkin's unsealed-edge replay uses Easy for the same reason: surviving its
two-giant setup must not obscure the actual assertion that an optional border
enemy cannot prevent taking an already-open forward exit.

The guaranteed boss-relic pickup replay uses Easy as well. It verifies that
every observed post-colossus relic is collected; Normal giant survival is
covered elsewhere and is not part of that pickup contract.
