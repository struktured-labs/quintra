# Quintra whole-game audit — updated 2026-07-25

## v0.18.90 True Footing

The attended Pocket report identified spaces that looked *almost* wide enough
for the champion even though the 12-pixel feet box correctly rejected them.
The fix preserves the readable 16×16 champion instead of shrinking collision:
generated colonnades now form paired piers with body-wide openings, 31×31
court clusters join into coherent architectural masses, and approach crests
use a two-solid/two-accent rhythm rather than alternating false slots.

A seed-pure finalization pass now closes only isolated 8-pixel walkable cells
between permanent walls, pillars, or crystals. It runs once after stage
silhouettes and again after every room-role overlay. The pass masks the
temporary reachability bit borrowed from the tilemap during encounter
placement; without that detail, deep Frost wings and eastern court acreage
could evade the check even though their rendered tiles looked ordinary.
Targeted live-ROM coverage samples every stage archetype, all authored graph
exits, and the complete 31×31 collision field.

The crystal tile also gained a full-width stone pedestal. It no longer reads
like a floating collectible with empty space beneath it, so the art and its
solid collision contract agree before the player touches it.

Release preflight exposed a separate wide-seam suspend hazard: the first
home-bank SRAM call after the long banked streaming path could save the new
room counter with stale pre-seam coins and score. An immediate idempotent
settled-state commit now makes the complete payload authoritative. The
battery test proves the distinctive room, run, and player values after a
separate emulator process cold-boots from the written 32 KiB save image.

The Spirit Compass remains a tile-native 6×5 grid rather than text art. It
already distinguishes unknown, visited, current, objective, cache, Rift, and
Colossus cells, while the amber 16×16 skull seal and threshold roar warn before
the boss gate. The nine Colossi continue to use BG-plane bodies ranging from
roughly 64×48 to 128×80 in scrolling arenas; their silhouettes and weak-point
contracts were re-audited against the giant-boss direction established by
Penta Dragon.

## v0.18.89 Living Bazaar and Colossus damage correction

The four-counter merchant retains its dependable recovery and class-attuned
relic anchors, but its build and tactical shelves now form a deterministic
6×6 catalog. Ricochet Rune, Thorn Crown, War Drum, and Moon Flask add wall
rebound, damage counterfire, fifth-kill signature recharge, and surplus-heart
MP conversion. Distinct HUD glyphs identify all four. Selection advances past
unique relics already carried, preventing later merchants from offering a
mechanically dead duplicate.

The complete live-ROM contract enumerates all 36 stock pairs, buys each new
relic through physical counter overlap, and observes its actual runtime effect.
The fixed controller also understands the four new ware IDs and uses exact
feet-over-counter routing instead of oscillating beside a valid purchase.
Ricochet ownership is cached at run reset, purchase, and suspend resume rather
than scanning eight inventory slots on every attack. Its projectile bit is
also distinct from the existing Spirit Convergence marker. Dense-room timing
therefore remains 147/180 loop frames, the fixed Normal Convergence policy
reaches the first Colossus again, and the controller-only Picsean Easy campaign
defeats all nine Colossi in 198,443 frames before its recorded-input replay
reproduces victory.

The v0.18.88 progression curriculum found zero deaths in ordinary entry and
court samples but only 9/45 Normal Colossus clears. Stage bonuses had raised
repeatable late giant shots to 5–7 half-hearts against a 16-HP cap; the Void
Lord killed all five baseline champions in roughly nine seconds. v0.18.89 caps
repeatable giant shots at three and makes a missed World Collapse cost four,
without changing HP, motion, cadence, projectile count, or mixed speeds.
The PyBoy curriculum now honors the same visible Collapse corner cue as the
full mGBA pilot. On the final v0.18.89 ROM, four of five baseline Normal
champions survive the full 3,600-frame Void Lord sample; fragile Vespine lasts
2,888 frames. The v0.18.88 matrix killed all five in roughly 513–557 frames.
The complete 45-match Normal matrix improves from 9 clears / 14 survivals to
13 clears / 21 survivals without making a starter-like checkpoint kit defeat
the final boss inside one minute.

The latest attended Pocket note sharpens the champion/tile concern: several
sub-body-width gaps between scenery pieces look *almost* traversable even
though the 12-pixel feet box correctly rejects them. The next terrain
readability pass should preserve the legible 16×16 champions, widen intended
routes to genuinely body-clear lanes, and overlap rubble or trim across every
intentionally blocked 8–11-pixel seam so collision is obvious before contact.

## v0.18.88 merchant choice and Compass legibility

The attended request that merchants sell more interesting things is now a
mechanical change, not a larger list of stat names. Dungeon shops keep healing
and a class-attuned sealed relic, then independently roll one build shelf and
one tactical shelf. Build stock can be vampirism, a Flail/Spear trade, Glass
Fang (one max heart for +2 ATK/+1 SPD), or Echo Prism (every fourth A attack
forks into two half-damage lanes). Tactical stock can be Surge, a full-dungeon
Chart, Phoenix Cord (one lethal-hit revival at half health), or Spirit Draught
(full MP plus Surge, making the A+B form immediately available). All sixteen
pairings are seed-stable and consume no combat RNG.

This makes coin decisions situational: low-health runs may save for Phoenix,
strong defensive builds can accept Glass, a crowd-control build can take
Echo, and a player preparing for the skull gate can buy an immediate Spirit
Convergence opportunity. The sealed relic no longer hides a purchase-time
random stat; its champion-attuned payload is fixed when the counter spawns.
Live-ROM tests buy and exercise every new mechanic, including a real lethal
hostile projectile for Phoenix and exact one/one/one/three projectile counts
for Echo.

The Compass audit also found two presentation failures. Its purple objective
rune resembled a stray `P`, so the 16×16 node now contains a centered `!`.
More seriously, the Riftwild legend's `R` and `F` tile slots were overwritten
by in-play district letters, visibly spelling `PNIHT`. Reversing atlas load
priority restores `RIFT`, and rendered-pixel coverage distinguishes the fixed
R/F strokes from the old P/H corruption. A carried two-second dungeon label
timer could likewise erase a persistent village `MARKET` sign after entry;
town and Riftwild generation now cancel that dungeon-only timer.

The v0.18.88 native training ladder contains six ROM-bound mGBA states at
five-minute intervals, and every state cold-loads through mGBA's `-t` path.
This particular Picsean Easy controller run reaches stage two by minute five,
then remains alive with 15 HP in room 38 through minute thirty. That is useful
deep-test access, but not progression evidence: the stage-two route stall is
retained as an open controller-policy/procgen audit item.

## v0.18.87 attended geography, scale, and merchant findings

Attended Pocket play likes the new larger rooms. The five Compass rows now
correspond to five physical 248×248 depth dialects—Gate, Lower, Deep, Inner,
and Heart—rather than one repeated court grammar. Each owns a distant
multi-tile silhouette, connected encounter aprons, and a restrained boundary
bell. The first presentation pass left names such as `LOWER` permanently over
black/floor tiles, which made them look like unexplained terrain. They are now
two-second Zelda-style arrival callouts. Exact rotated-VRAM coverage proves
that the generated row returns afterward and that a same-district seamless
crossing cannot carry stale letters into its neighbour.

The same session repeated the long-standing bottom-centre block-clipping
report. The root was broader than walking: damage knockback checked four
corners while walking checked six feet/body probes, so a hit could embed the
hero on the centre of a one-tile pillar. A permissive recovery route could
then model the scenery as a tunnel. Walking, dashes, and knockback now share
the complete collision contract and ordinary input has no embedded-scenery
exception. Live-ROM coverage pins crate/pillar contact from below, dash
contact, an impossible embedded fixture, and x/y=232 world bounds. A fresh
button-only campaign crosses the formerly permanent room-72 stall, defeats all
nine Colossi, and reaches room 220 victory. Its cold recorded-input replay
passes in 158,896 frames with 16 HP remaining.

The champion/tile proportion is not conclusively wrong, but the mixed feeling
has a concrete source. The logical champion and collision footprint are
16×16—two 8×8 tiles, the conventional top-down Game Boy ratio—while much of
the opaque character art reads closer to one tile and several environmental
objects remain literal one-tile marks. Shrinking the champion would reduce
directional animation and handheld readability without fixing that mismatch.
The next art pass should keep the 16×16 metasprite/collision contract and make
important architecture and props read as deliberate multi-tile forms; attended
Pocket play should decide whether the opaque hero silhouette itself then needs
one or two more pixels of mass.

Merchants sell nine semantic ware families: healing, procedural
relics, max HP, attack, mana, vampirism, a one-dungeon chart, alternate
weapons, and a fifteen-second class-shaped Surge. Village shelves include
Flail/Spear trades, Vampiric Sigils, mapping, and permanent build stats.
Nevertheless, attended play still reads the offers as uninteresting. The
visual audit explains why: all but hearts and Surge collapse into essentially
the same generic orb/diamond silhouette, while the meaningful description
appears only near the shelf. This is both a communication and variety problem.

The first response shipped in v0.18.87. A dungeon merchant's featured shelf is
seed-stable but can be an Iron Heart, Surge, Vampiric Sigil, Power Stone, Mana
Gem, full dungeon Chart, or alternate A-weapon instead of alternating between
only vitality and Surge. Approaching it already replaces the physical orb
with the exact heart/forge/rune/lightning/fangs/chart/weapon glyph and price in
the HUD; the shelf palette now also groups steel/weapon, crimson sustain, and
cyan magic/information. v0.18.88 completes the next mechanical step with two
specialty shelves, risk/reward, revival, attack-fork, and transformation-ready
offers. Dedicated physical silhouettes and longer pre-purchase names remain a
future presentation opportunity.

The goal-facing Compass and Colossus contracts remain materially present.
SELECT is a tile-native 6×5 abstract graph with dim unknown nodes, bright
visited links, current-room arrow, Sigil/trial/rift/loot/boss semantics, and
stage context. The boss threshold has a 16×16 amber skull seal plus a
one-shot roar and tremor before entry. All nine Colossi are BG-plane bodies
roughly 64×48 through 128×80 around mobile weak points; the 224×136 arenas
scroll and their gallery shows bodies occupying most of the viewport across
multiple camera positions. This aligns with the reference direction: the
[Penta Dragon asset index](https://www.spriters-resource.com/game_boy_gbc/pentadrag/)
catalogues eleven separate enemy/boss sheets, and its documented play loop
also ties kill-earned transformation power to boss pacing. Human validation
still outranks screenshots: later Normal Colossi, merchant readability, and
the current Compass should be tested directly from the refreshed deep states.

## v0.18.84 whole-world trainer correction

The latest attended report remains authoritative: the stages feel compact.
Their nominal 20–30-cell footprints and 31×31 ordinary fields do not override
that experience. The graph explains part of the mismatch. Depending on the
seed-selected fold, the direct entrance-to-boss distance is only 9–21 edges;
the required Sigil, Warden, Waystone, Deep Warden, and boss expedition spans
19–31. Future scale work must make those required miles read as distinct,
memorable subregions and add meaningful optional depth instead of merely
adding counters or repeating generated floor.

The audit used to understate that physical acreage. The framework-neutral
PyBoy environment clipped enemies, hostile projectiles, and pickups to the old
160×136 viewport and exposed only its 20×17 collision tilemap. Ordinary
dungeon fields are now 248×248 and every Colossus arena is 224×136, so the
trainer could mistake an internal camera seam for a room exit or lose a live
boss when it crossed x=160. The latter produced false zero-HP endpoints after
Game Over replaced the entity table.

Observation now publishes the cartridge's live world width, height, camera,
and complete collision field. Exit, hostile, pickup, firing-lane, and body
routing use the full grid while compact recorded fixtures remain compatible.
A live stage-four regression moves its real Colossus to x=184, verifies the
eastern chamber geometry, and proves that the controller still aims and fires
across the former seam.

The corrected Normal boss matrix sees each giant for 100% of every sampled
fight, including legal positions through x=201. It clears 8/45 rather than the
clipped observer's 4/45 and survives 13/45. Remaining HP is now the last live
boss observation, never a synthetic zero caused by death-screen replacement.
This remains a policy diagnostic, not a balance vote: stages five through nine
are the highest-value attended Normal checks.

The corrected thirty-second ordinary-room matrices resolve 18/45 stage-entry
fixtures and 30/45 mid-stage courts, both with zero deaths. The previous
39/45 and 44/45 results were inflated by compact-grid navigation. The new
result shows sustained encounters that a small pilot often cannot finish in
thirty seconds, but does not show globally lethal ordinary rooms. Human
reports of both difficulty and compactness therefore remain compatible and
remain the design authority.

## v0.18.80 sustained-acreage response

Attended play found the stages compact despite their 20–30-cell Compass
footprints. The report matches the cartridge structure: v0.18.79 had only 119
wide dungeon cells across the campaign, grouped into runs no longer than five.
Nominal route distance therefore kept collapsing back into one-screen
objective and Warden thresholds.

Every non-service dungeon node is now a 31×31 scrolling field. The final
merchant, sanctuary, and authored Colossus arena remain the deliberate compact
destination cadence. This raises wide dungeon coverage from 119/219 to
192/219 cells. Stage one is a continuous seventeen-field expedition before
its destination; the Void route is twenty-seven. Room counts, topology,
encounter draws, enemy HP, projectiles, bosses, heroes, and difficulty values
are unchanged.

The objective roles remain legible rather than drifting into distant random
corners. Rift Sigils, Waystones, and Wardens occupy the familiar western entry
sector inside the wider field. The nonlinear room-2/room-8 Rift needs an
explicit post-layer restamp because a generated court replaces the compact
base map. Its seed-derived position and body-wide central route are restored
after stage silhouettes, without consuming RNG. Moving that restoration into
the world-generation bank leaves procgen with 1,097 bytes free and preserves
the 1 KiB development floor.

The live-ROM geography contract traverses all seventeen opening fields through
their real snake edges, including objective/miniboss roles, and asserts every
destination remains 248×248. Separate coverage proves the Rift fixture and its
hero-width path, Waystone/deep-Warden gates, puzzle persistence, reciprocal
arrivals, collision, distributed encounters, rotated Compass resume, and exact
31×31 VRAM publication. A complete wide transition settles in 55 frames,
keeps the LCD and champion visible, and advances four music rows.

The full route audit exposed a mandatory-fixture failure hidden by direct room
probes. Entering local room 9 from the west places the hero at x=224 in the
extension strip; the compact spawn-component marker had treated that
coordinate as though it belonged to the 20×17 base array. The Sentinel spawn
was therefore suppressed while the sanctuary still required its deep-Warden
bit. Wide arrivals are now projected onto the guaranteed central seam before
the compact component flood. Both required Warden rooms spawn one reachable
Sentinel across 32 seeded layouts, and the exact formerly stuck controller
seed advances beyond room 9 with zero route stalls.

The same campaign exposed stale controller bounds at the first post-village
Mirror Moth field and at a far-sector Crystal reward. The verifier's small-
enemy edge guard used y=116 as a literal bottom edge, forcing the pilot north
at what is now only an internal seam. It now reads the cartridge's live arena
dimensions, commits cross-sector pursuits to the guaranteed court axes, and
uses exact feet-box firing lanes through lower-ruin gaps. Boss-relic goals use
the same live bounds rather than clamping at x=146. The final controller-only
campaign defeats all nine Colossi and reaches the ending at frame 154,986 on
seed 2064128163 with 11 HP, collects every observed intermediate relic, and
replays to the same victory in a cold emulator inside the unchanged
210,000-frame budget.

The release-hash external curriculum is current as well. All 460 native mGBA
entry, court, sanctuary, boss, Riftwild, and village checkpoints regenerate
after the sustained-acreage change and representative files from all six
families cold-load through `-t`. The continuous Easy Picsean training route
publishes verified native states at 5/10/15/20/25/30 minutes; its final state
has reached stage 7, room 158, with six Colossi defeated and 15 HP.

## v0.18.79 checkpoint and difficulty-response audit

The post-v0.18.78 audit found a concrete stale-artifact gap: all 460 PyBoy
curriculum fixtures matched the continuous-district ROM, but the native mGBA
curriculum and five-minute training set still named the preceding cartridge
hash. The complete five-hero, two-difficulty native curriculum is regenerated
against v0.18.79 and representative entry, court, sanctuary, boss, Riftwild,
and village files cold-load through mGBA's independent `-t` startup path. The
continuous Easy Picsean route publishes six more native states at 5, 10, 15,
20, 25, and 30 minutes. Its final checkpoint is stage 6, room counter 118,
with five Colossi down and 16 HP.

The periodic native generator also had an interruption hazard. It removed the
last manifest and root states before the replacement controller route had
finished; a host SIGTERM correctly prevented a false manifest but unnecessarily
left the tester with no usable complete set. It now writes into an unreferenced
generation, cold-loads every due checkpoint, publishes that directory, and
atomically replaces the manifest last. Only after readers can resolve the new
hashes does it retire old files. A failed or killed run therefore preserves the
last complete generation rather than exposing partial progress.
An intentional invalid-emulator run against the populated output fails before
publication while preserving the prior manifest byte-for-byte, leaves its
single referenced generation intact, and cleans the abandoned staging
directory.

The exact release candidate also completes the controller-only campaign with
all nine Colossi and all eight intermediate boss relics at frame 192,530. A
fresh emulator replays its recorded button stream to victory at frame 193,716
with 15 HP. That gate exposed and fixed one host-side portability issue: its
multi-line `awk` condition now ends continued lines with `||`, which both mawk
and gawk accept. The cartridge result was already valid; only the audit parser
had rejected it.

The attended statement that the last played build felt difficult remains valid
human evidence, but does not by itself justify weakening every Normal room.
Normal remains the authored target. The live Game Over screen now closes the
discoverability gap by rendering `SELECT EASY AT HERO` after a real Normal
combat death; Easy deaths instead suggest another hero. A fatal-combat,
permadeath, SRAM, rendered-text, and clean-restart contract owns that prompt,
while the paired difficulty contract confirms all 230 Normal/Easy curriculum
pairs still share generated tiles, routes, shared-hostile identity, and
boss-pattern identity around the documented one-foe Easy court and
Warden-health/escort reductions.

The current controller diagnostics make the intended distinction visible.
The Normal stage-entry pilot resolves 39/45 generated fixtures with zero
deaths, so ordinary arrival pressure is not globally lethal. Its generic
one-minute Colossus policy clears 9/45 and survives 12/45; the matching Easy
policy clears and survives 40/45. These scripts are policy diagnostics rather
than balance authority, but they support keeping demanding Normal encounters
while making the existing inspection mode discoverable.

Attended feedback also confirms that nominal topology is not the same thing as
perceived scale. Even with 20–30 Compass cells and continuous seams between
selected 31×31 fields, the stages still feel compact. The next geography pass
must expand sustained scrolling acreage and meaningful branches rather than
padding the campaign with tiny room counters.

Native visual review confirms the other two goal-facing systems already meet
their current cartridge contracts. SELECT renders a complete faint 6×5
one-tile dungeon graph beside a permanent `YOU / ROOM / SIGIL / TRIAL / BOSS /
RIFT` legend, with explored nodes and corridors brightened. Every actual
boss-adjacent edge uses a 16×16 amber skull seal and triggers a one-shot roar
and tremor in its approach band. The nine-boss gallery remains a set of
64×48–128×80 background bodies around mobile weak points; Crystal retains the
true 224×136 scrolling arena and Void occupies four fifths of screen width.

## v0.18.78 continuous-district response

The 31×31 scale pass increased real terrain but consecutive procedural nodes
still announced themselves as separate rooms by rebuilding the screen at every
edge. Wide-to-wide dungeon and Riftwild crossings now use the hardware 32×32
background map as a rotating ring. The next 31×31 field streams a row or
column per VBlank behind the moving viewport; the LCD stays enabled, the
champion's four OAM pieces stay visible, and the music sequencer advances
throughout. Compact authored puzzle rooms retain their shorter Zelda-style
slide, and palette/role changes still take the deliberately blanked path.

The logical graph has not been flattened. Each generated field retains its
own seed-stable collision map, encounter, objective role, visited Compass
node, and reciprocal entrance. The rotated origin is published only once all
961 destination tiles are resident, making the seam atomic to gameplay,
Compass/Pack resume, and external checkpoints. Live writes for pushed blocks,
revealed puzzles, door seals, and area labels map through the current origin.

The cartridge contract crosses a wide dungeon pair west/east and another
south/north, samples every transition frame for an enabled LCD and visible
hero, confirms music-row movement, and compares the entire destination
tilemap with physical VRAM. It also opens and closes the Spirit Compass at a
nonzero origin. A separate authored-world sweep traverses all sixteen
Riftwild cells through real reciprocal seams.

The controller-only Picsean proof now wins at frame 193,716 with 15 HP,
remaining inside its 210,000-frame cartridge budget. It observes and collects
all eight post-boss relics before the ending. A short relic policy owns the
first pickup; repeated collection is asserted by this campaign-wide proof.

The hot camera path initially cost one stress frame. Its final form keeps both
rotated scroll additions inline, removes an unnecessary champion-renderer
wrapper and a topology-redundant stage comparison, and holds 180/180 ordinary
frames plus 144/180 under twelve persistent projectiles. Bank 1 retains 1,038
bytes of development headroom.

## v0.18.77 attended scale response

The latest attended report still finds the stages compact after the 31×31
field expansion. That is accepted as the governing evidence: increasing the
area of fields hidden several rooms into a route did not establish scale soon
enough. Every dungeon foyer is now a 248×248 scrolling field, and local
approach fourteen supplies another broad beat in the graph's compact middle
row. Stage one rises from eight to ten wide districts and the finale from
fifteen to seventeen, while the room budgets, objectives, and Compass topology
remain unchanged.

The audit also found that generated wide-room enemies were not using the
space honestly. The first body occupied one eastern point and nearly every
subsequent body was overwritten onto the same southeast point. Four
deterministic, guaranteed-open sectors now distribute the encounter across the
near hall, southeast apron, eastern ruin, and southern approach without
consuming RNG or changing which enemies rolled. Live-ROM coverage enters the
wide opening foyer, crosses consecutive 31×31 courts, confirms distinct near
and far bodies, returns to a compact Waystone, and enters the new central
approach. Deep-state generation now treats a live scrolling foyer camera as
valid and explicitly normalizes only its synthetic defeated-boss source.

Moving-camera work is consolidated into one banked camera/entity projection
pass; a settled camera returns to resident rendering. Measured performance is
179/180 ordinary frames and 144/180 dense frames, with 1,034 bytes free in
bank 1.

The attended route trace also exposed a legacy boundary inside later
stage-archetype courts: the camera could show the southern field while the old
160×136 edge still behaved like a wall. Wide generation now reopens the entire
obsolete row and column after stage decoration. A Stage 3 checkpoint verifies
both seams as passable, and the controller reaches room 54 by frame 35,000
instead of stalling against the room-41 Fold Star.

The end-to-end Picsean proof reaches the ending at frame 158,466 after all
nine bosses with 16 HP remaining. All 460 native mGBA champion/difficulty/
checkpoint fixtures cold-load, and a separate periodic set supplies native
snapshots at five-minute intervals for attended deep testing. Longer host
watchdogs in a few input-controller fixtures accommodate route analysis over
31×31 collision fields; no cartridge frame budget, deterministic seed,
assertion, combat value, or difficulty rule changed with them.

## v0.18.76 physical-scale response

The repeated report that stages still feel compact is accepted as physical
evidence, not contradicted by the nominal 20–30-room count. The old scrolling
district was 28×25 tiles (224×200 pixels, 44,800 generated pixels) behind a
160×136 viewport. Every ordinary wide dungeon role and every Riftwild cell is
now 31×31 tiles (248×248 pixels, 61,504 generated pixels): 37.3% more actual
collision terrain. Camera range grows from 0..64 on both axes to 0..88
horizontally and 0..112 vertically. The 32nd hardware BG row and column remain
deterministic wall/tree overscan, so shake never exposes stale VRAM.

This is not empty perimeter inflation. Dungeon districts extend the upper and
lower ruin halls, add a distant encounter apron and southeast landmark, keep
stage-colored cover, and carve their two-tile cardinal hall last. Riftwild
adds a third eastern landmark block and a second southern block per cell; all
four landmark families still rotate exactly four times over the 4×4 graph.
Far-field enemies now occupy the new southeast space. Stage one retains eight
wide districts and the finale fifteen, so the campaign becomes physically
larger without adding filler counters or changing the compact Compass graph.

The first live south-door check exposed an SDCC 4.4 optimizer failure in the
banked collision query: after the 31×31 index arithmetic, the combined
`height > view && row >= 17` expression reused a corrupted temporary and read
every lower row as a wall. The equivalent nested comparison now compiles into
independent checks. Live-ROM coverage crosses a southern dungeon seam,
re-enters at y=224 with SCY=112, sweeps all sixteen Riftwild cells, reaches
camera (88,112), and follows the ending route through the expanded world.

The external mGBA pilot now recognizes the generated field's visible
body-wide cardinal hall rather than flood-filling as many as 61,504 pixel
positions merely to rediscover it. It still uses ordinary D-pad input and the
ROM's real collision map. Sauran clears the covered Frost Sentinel route,
Corvin crosses Riftwild, Vespine escapes the deterministic Rope pin, and the
short five-champion sample records no deaths. Crystal remains its audited
224×136 scrolling Colossus arena; boss scale, enemy stats, hero stats, and
Normal/Easy rules are unchanged.

## v0.18.75 Compass context and corrected room evidence

The dungeon Compass remains the requested compressed abstract grid rather
than a text status page: one tile per room, one tile per link, the complete
6×5 active footprint, bright explored routes, dim unknown routes, semantic
colors, a staged objective, nonlinear rift edge, and an amber pre-entry boss
hint. Its heading now adds the missing run context as `S1 MAP` through
`S9 MAP`. This keeps screenshots and native deep-test states self-identifying
without displacing the graph or its permanent legend.

The earlier Golden Temple warning was partly a controller artifact. Corvin
and Picsean's PyBoy training policy retreated whenever a contact pack entered
preferred range, even when it already owned a clear cardinal firing lane.
Four chasers could therefore make the pilot deal zero damage and scrape the
room edge until death. The policy now spends one beat in four on an honestly
aligned shot and the other three preserving space; no ROM values, hidden aim,
or future state are used.

The corrected 30-second Normal room matrix resolves 29/45 fixtures, with 17
exits and zero deaths. Golden Temple Picsean reaches the open exit in 692
frames at 15/16 HP and Corvin exits in 570 frames untouched. Sauran remains
the useful pressure lead: at 60 seconds he has removed 52/84 hostile HP,
defeated two enemies, regenerated once, and survives at 4/18 HP. That is
productive late-game combat pressure, not evidence for a global Normal nerf.

## v0.18.74 Easy deep-boss response

The first current-ROM paired curriculum refresh separates dungeon attrition
from boss inspection more cleanly. On Normal, every one of the 45
progression-matched stage-entry fixtures survives its 30-second sample; 20
resolve by clearing or exiting and 25 remain under pressure. The old five
entry deaths are gone. Golden Temple remains the attended-test lead: its
Picsean fixture survives at 1/16 HP after losing fifteen half-hearts, while the
other four survive or resolve. That is a reason to watch one specific late
foyer, not to reduce every Normal enemy.

The paired boss diagnostic exposes a different Easy-mode gap. Before this
pass, the generic pilot cleared 34/45 Easy Colossi, but Sauran and Vespine
still died with only 19 and 37 HP left on Void Lord. Easy now lets player hits
deal up to five damage through Ember-and-later Rift Armor; Normal retains its
three-damage cap. Boss HP, generated arenas, movement, projectile patterns,
incoming damage behavior, and World Collapse are identical between modes.
The matched rerun clears 42/45, leaves the other three alive at timeout, and
clears Void Lord with all five champions. This makes Easy a more useful
mechanic-inspection mode without presenting its input policy as human balance
evidence.

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

## Penta Dragon boss-scale reference check

The original game supports the requested direction more specifically than
"make the boss sprite bigger." The [complete boss and enemy sheet
index](https://www.spriters-resource.com/game_boy_gbc/pentadrag/) shows a
campaign built around unusually large silhouettes, while the surviving
160×144 fight captures make their screen share measurable. Faze occupies
roughly four fifths of the LCD width and more than half of the active
playfield; Penta Dragon has a similarly dominant, tall silhouette rather than
a 32×32 body floating in an ordinary room.

The [contemporary walkthrough
description](https://gamefaqs.gamespot.com/gameboy/569778-penta-dragon/faqs/68202)
also resolves the camera question. Crystal Dragon enters and exits distant
holes and the camera follows it; Faze combines sheer size with a moving camera;
Penta Dragon's size and camera movement can pin the player in a corner. The
important reference behavior is therefore a large readable creature, a mobile
target or weak point, and selective arena/camera choreography—not mandatory
full scrolling on every fight.

The current cartridge is already close to that presentation target. Void
Lord's authored BG body is 128×80 pixels (the same four-fifths screen width);
Crystal is 112×72 plus a mobile 32×32 heart in a true 224×136 arena with
64 pixels of camera travel; Golden Temple is 112×72; and the other projected
forms range from 64×48 to 112×64 while retaining independently moving weak
points. Native gallery review confirms all nine read as creatures rather than
decorative backdrops. Expanding every arena would currently make several weak
points detach from their projected bodies and create empty safe acreage, so it
would reduce reference fidelity. Keep Crystal as the explicit scrolling-warp
fight, the late Hydra/Void camera drift as moving-arena language, and require
attended Normal testing before choosing another form for true world-space
expansion.

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
Normal/Easy pairs retain identical generated geometry and routes; Easy turn
courts deliberately retain one member of Normal's generated pair. Native mGBA
cold-loads all six checkpoint families. This is the first
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
and requires identical generated tiles, route/progression state, shared
hostile identity, and boss-pattern identity. It explicitly owns the two
documented content assists: required Wardens have half HP and one escort, and
turn courts retain one member of Normal's generated pair. No other checkpoint
family may author different content.
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

With continuous-district timing, this fixed controller spends about 27,000
frames resolving its stage-two room-20 Skeleton lane before continuing and
still completes all nine bosses in the separate 210,000-frame victory proof.
The town fixture therefore receives 90,000 frames to reach its actual subject;
its north-gate stall limit remains the same strict 3,600 frames.

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
