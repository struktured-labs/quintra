# Quintra

**A procedural Zelda-like action roguelike for the Game Boy Color.**

Native CGB. Five monster-human classes, procgen dungeons every run, bullet-hell
bosses, and item-driven builds. Heavy [Penta Dragon](https://en.wikipedia.org/wiki/Penta_Dragon)
influence (dense projectile patterns) crossed with the maze-exploration feel of
Zelda: Link's Awakening / Final Fantasy Adventure / Ultima: Runes of Virtue.

Written in C with GBDK-2020 — the only thing that ships on cart. All content
authoring and dev tooling is a typed **Rust** workspace that generates the C
tables at build time.

[Download the latest ROM — v0.18.7: Colossus Contact Fairness](https://github.com/struktured-labs/quintra/releases/latest)

![Quintra gameplay](docs/media/gameplay.gif)

The current reel shows the animated five-spirit prologue, champion selection,
live dungeon combat, the Riftwild overworld, a nonlinear cave-to-vault
teleport, and the animated epilogue. The transitions shown are executed by
the cartridge runtime.

v0.18.7 makes every giant boss's body contact grant **45 recovery frames**,
matching the final Void Lord. Boss HP, chase cadence, bullet density, and
patterns are unchanged: this only prevents a knockback from turning into an
immediate second unavoidable collision. Live-ROM coverage now tests both an
ordinary Colossus and the Void Lord. In a complete 15-run controller-only
matrix, Picsean rises from one to **two nine-boss endings** with zero combat or
route stalls, while every champion clears the first boss in at least two of
three entropy samples. The full all-class endurance bar is still deliberately
unmet, so this is an evidence-backed fairness release rather than a show-build
sign-off.

v0.18.6 retunes the first Colossus from **200 HP to 140 HP**. It remains a
real pattern fight—15 seconds minimum even in an uninterrupted starter lane—
but no longer asks an unbuilt run to survive a full attrition wall before its
first relic. Every later boss retains its existing HP, damage, and patterns.
Live-ROM and content contracts pin that opening health budget. In the first
controller seed, all four non-Picsean starters now clear the first boss; the
second seed remains intentionally variable, so this is onboarding tuning, not
a substitute for the full endurance delivery gate.

v0.18.5 fixes a real sealed-room fairness failure: **Skeletons can no longer
chase into one-tile lanes that the champion's 12px feet box cannot enter**.
That removes a potential melee softlock while retaining the authored agile
movement of other small monsters. The controller pilot also now checks the
actual projectile centerline before committing short weapons to wall seams.
Live-ROM regressions cover the inaccessible lane, score saturation, and
Vampiric Sigil kill timing after room-entry publication has settled.

v0.18.4 simplifies the persistent-town runtime: all six resident constructors
now share one internal spawn path while preserving their unique art, palettes,
and merchant callout repair. That recovers **211 bytes** in bank 5—space for
future conference polish without changing village behavior. Live-ROM town and
resident-art contracts cover the refactor.

v0.18.3 fixes a misleading pickup edge case: **MP wisps now remain on the
floor at full MP** instead of disappearing with a reward sound while changing
nothing. They collect normally as soon as one MP is missing, matching the
already-established full-health heart behavior. The live-ROM pickup contract
covers both capped resources, and the pre-show endurance gate now requires
every released enemy ID—including Prism Skitter—before it can pass.

v0.18.2 adds the **Prism Skitter**, a Shadow Keep positional caster. It
maintains a readable ring around the hero, reverses cleanly around procedural
cover, and sends a slow rotating opposite pair through the room—two changing
lanes rather than another fan or full-ring flood. Its faceted sprite reuses
the peaceful elder OBJ slot only during dungeon combat, and its compact
`AI_SPINNER` behavior lives in an uncongested switchable bank. A live-ROM
contract proves the loaded art, a tangential orbit step, and the exact
two-lane projectile pair. The cartridge remains 128 KiB with 1,463 bytes of
fixed-bank headroom and every switchable bank above the 1 KiB safety floor.

v0.18.1 adds the rare **Astral Spear** to the weapon-orb pool. It is a slow,
long, single-target physical thrust—the deliberate counterpoint to Rift
Flail's broad three-target sweep. It has its own pointed in-game sprite while
reusing the Cartographer's OBJ slot only in dungeon combat, so towns retain
their resident art and the 128 KiB cartridge budget stays intact. A live-ROM
contract collects it through normal pickup collision and verifies its swap,
art, reach, damage, and non-cleaving identity.

v0.18.0 fixes village route knowledge and makes it a visible, purchasable
choice. The free **Chartwright** now correctly scouts the first two rooms of
the *next* dungeon instead of losing that blessing at the north gate. A blue
**Cartographer's Chart** shelf in the arrival square costs 15 coins and reveals
all six rooms for that one following dungeon; its folded-map HUD glyph and
price appear before contact. The live-ROM town contract buys the Chart through
ordinary collision and proves the full compass arrives exactly once.

v0.17.99 makes the village **Apothecary** a real run-building stop. Alongside
its Mana Gem, the crimson **Vampiric Sigil** shelf is always purchasable for
35 coins. Its new fangs offer glyph distinguishes a fifth-kill half-heart
recovery build from generic relics before purchase; it also grants +1 ATK and
+1 max HP for the run. Live-ROM coverage walks into the actual town shelf,
checks its art, price, semantic HUD glyph, and permanent stats, then resolves
real enemy kills to prove healing occurs exactly on every fifth kill.

v0.17.98 turns the cyan **Surge Spark/Tonic** into a real class-shaped
temporary build choice. Its fifteen-second shared damage and cadence lift now
also makes Wolfkin claws cleave, lengthens Sauran's tail strike, opens a second
Corvin feather lane, broadens and deepens Picsean bubbles, and lets Vespine's
sting pierce. The shop/drop remains temporary and its price/stat rules do not
change. A live-ROM contract boots all five champions, collects a real Spark,
and proves every style plus expiry. The controller agent now uses exact
feet-box routes for every required Rift Sigil and stationary-Spore firing lane,
and aligns against wall-clinging Gloom Leeches rather than stalling on them;
the five-class paired balance gate again reports zero combat and route stalls.

v0.17.97 fixes a late-run progression bug: the guaranteed **Bellwarden** was
visually and mechanically a miniboss, but because it reuses the Dread Bell
enemy it missed the Sentinel-only weapon-orb reward. Bellwarden now carries an
explicit encounter tag and always pays that weapon choice on defeat; ordinary
late-roster Dread Bells retain their normal drops. A live-ROM regression
delivers a real lethal shot to the stage-6 Bellwarden and proves the weapon orb
appears.

v0.17.96 makes late-run pressure fair instead of brittle. **Golden Temple**
onward now has the guaranteed **Bellwarden** miniboss: one stage-tinted Dread
Bell and one Rift Warden in a reserved safe apron, rather than another random
Sentinel roll. A boss clear immediately restores one heart (while its two
physical hearts, coins, and relic still remain on the floor), and a hero hurt
by spikes stumbles one safe body-width away when an adjacent lane exists. The
Golden Temple colossus is capped at 230 HP and the armored **Void Lord** at
220 HP; their patterns, Rift Armor, World Collapse, and long fights remain.
Live-ROM contracts cover the encounters, reward recovery, hazard escape, and
the 30/60/45-frame dungeon/Riftwild/Void-contact recovery beats. Four
controller-only seeds (13–16) complete all nine bosses with no route or
combat stalls.

v0.17.95 removes the full formatted-I/O runtime from the cartridge and
replaces it with a tiny native text writer shared by title, records, class
select, Pack, game-over, and ending screens. The same words, live numbers,
and lore panels remain on screen, but bank-0 headroom rises from **540** to
**1,552 bytes**—enough room to keep adding World Retro-era encounters without
living one edit away from a banking failure. Live ROM contracts cover title,
game-over, ending, Pack, and the full gameplay smoke route.

v0.17.94 makes a village stop an active build decision: the market's new far
shelf always sells a **Surge Tonic** for 20 coins. Its cyan orb and lightning
offer glyph make the temporary faster, harder-hitting primary weapon legible
before purchase. The existing heart, relic, and Iron Heart stock remains;
the full controller-only nine-boss route still completes and replays cleanly.

v0.17.93 completes the late-game **Rift Armor** rule: the final **Void Lord**
also caps a single hit at three damage, so a powered-up run cannot erase its
World Collapse before the positional mechanic matters. The controller now
recognizes the long, visible safe-pocket telegraph through ordinary inputs;
the canonical nine-boss run still completes and replays from a clean emulator,
with the final fight lasting 1,265 frames rather than melting in seconds.

v0.17.92 makes the late-game bosses earn their screen time. **Golden Temple**
and **Bloodmoon** colossi now have Rift Armor that caps a single projectile at
three damage. The **Void Lord** retains its distinct World Collapse positional
test. Ordinary enemies, mini-bosses,
and the first six bosses retain full weapon/elemental damage. That is a
cartridge-sized answer to runaway late-run power: the same automated seed-15
run now clears bosses 7–8 in 1,080/970 frames (formerly 189/137), while the
full campaign remains completable with no combat stalls.

v0.17.91 fixes the **Frost Vault** roster gap: the stationary Sentry turret
now appears there as a rare, readable rotating-cross lane hazard among the
moving threats. It also makes the vault's authored crystal
ring authoritative over the shared room skeleton, while preserving the
nonlinear Rift Well's hero-footprint landing apron where the two fixtures
overlap. Typed content validation proves every registered non-boss enemy is
reachable from at least one stage pool; live-ROM stage tests prove Frost,
Temple, and Rift paths remain connected.

v0.17.90 fixes a real procedural soft-lock risk: every nonlinear **Rift Well**
now carves a small hero-footprint landing apron, so the glowing exit is always
physically reachable rather than only visible. The live ROM contract floods
the actual 2x2 feet-box path to the rift, and the controller’s deterministic
seed-14 endurance route now advances past it with zero route stalls.

v0.17.89 added the **Rift Warden** to Golden Temple, Bloodmoon, and Void
Sanctum pools. This cyan split-mask caster fires a deliberate five-way fan:
it closes the center and adjacent diagonal lanes while preserving readable
outer-diagonal escapes. Its authored combat-only sprite safely reuses the
merchant sale-tag VRAM slot only outside shops and towns. Typed content checks
prove it is in all three late pools without raising their total spawn weight;
live-ROM coverage proves its sprite handoff and five real projectile lanes.
A complete nine-boss controller replay still wins after the new threat.

v0.17.88 gives every dungeon merchant a seed-stable premium choice: some runs
offer the permanent **Iron Heart** as before, while others offer a cyan
**Surge Tonic** for 20 coins. It starts the visible 15-second primary-weapon
burst—faster shots and +1 damage—without permanently inflating a run. The
stock's unique orb, lightning HUD icon, exact price, floor label, purchase,
and timer are all live-ROM tested; Rust/C procgen parity covers both seeded
price variants. Village market stock remains fixed and unchanged.

v0.17.87 reserves every stage's **Rift Sigil** before dense procgen combat and
loot can fill the fixed entity table. A live reproduction of the formerly
crowded stage-three room proves its required objective always exists and can
be collected. It also prevents **Spirit Convergence** from applying all eight
overlapping arcs to a 32×32 colossus in one frame: the eight-way crowd burst
remains intact, but a boss receives at most four hits per chord. Live-ROM
coverage proves the 28-damage cap while ordinary eight-shot damage remains 56;
the controller still completes all nine bosses on the canonical seed.

v0.17.86 fixes a dense boss-kill reward loss. The giant and its hostile shots
now release their entity slots before visual effects, so the two recovery
hearts, two coins, and guaranteed relic remain physical pickups even when a
32-slot bullet storm is full. A live-ROM saturation test proves that exact
failure case; the controller certification uses four consecutive seeds (13–16)
that each complete the corrected nine-boss route.

v0.17.85 makes merchant stock readable before purchase. Approaching a ware
now replaces the generic price prompt with a semantic HUD icon plus its coin
cost: healing heart, relic, max-vitality, forge attack, or mana rune. It keeps
the physical item art, floor price, and walk-into buying intact—no modal shop
menu or accidental transaction. The town ROM contract checks both the healing
icon and `$5` price at proximity and at contact.

v0.17.84 fixes a Dread Bell transition bug: entering a merchant room after
combat could leave the shared OBJ tile showing the bell instead of the nearby
merchant's speech bubble. Room-role tile loading is now centralized, and a
merchant explicitly restores its own callout tile when spawned. A live
cartridge regression crosses that exact portal boundary, waits for the real
store to populate, and verifies its VRAM art before testing the rest of the
enemy roster.

v0.17.83 adds the **Dread Bell**, a late-game iron caster that tolls an
eight-way, fast projectile peal on a deliberately slow cadence. It enters
Golden Temple, Bloodmoon, and Void Sanctum pools without displacing each
stage's core threats. Its new authored silhouette shares the merchant's
speech-bubble VRAM slot only in non-merchant combat rooms, with live cartridge
coverage proving both the eight lanes and the tile boundary. This release also
removes dead class `sprite_set` data: five champion idle and walk atlases are
now protected by a runtime animation contract instead of a misleading field.

v0.17.82 makes dropped **hearts patient**: brushing a heart at full HP no
longer plays a pickup chime, removes the sprite, and leaves the HUD unchanged.
The heart stays on the floor until the champion has a missing half-heart, then
heals normally. This turns a confusing apparent failed pickup into a readable
choice to return for recovery. A live ROM regression covers both full-health
and damaged collection, alongside the immediate damage-HUD contract.

v0.17.81 centralizes the dungeon **Compass Contract**: map rendering and
fog-of-war now ask one run-state helper which of the six dungeon cells is
current. That removes duplicated stage-transition math that could drift as
the run crosses a boss, Riftwild, or town boundary. The boss-to-Riftwild
handoff, the sigil compass marker, and the connected town compass all pass
their live ROM contracts.

v0.17.80 makes ordinary dungeon rooms carry **Rift Pressure** from the start.
Combat rooms now place at least two real monsters, with bounded retries around
pillars and entrance lanes so the floor cannot silently collapse to one
crawler. The depth ramp and enemy HP stay intact: this is more positioning and
target-priority pressure, not a sponge-health increase. Procgen parity, all
stage-route contracts, and a four-seed early-room density contract pass.

v0.17.79 gives every large boss a readable **Riftbreak** at half health: a
bright flash, short room shake, and slow four-way warning burst before its
existing faster enrage cadence resumes. It is a real second phase rather than
an invisible HP sponge—boss health remains capped at 255 for the 128 KiB
cartridge. The nine-boss emulator contract proves the marker and exactly four
new warning shots; a three-seed Picsean controller sample increased completed
boss-fight time from roughly 20.5 to 27.3 seconds.

v0.17.78 makes every champion’s **B signature legible and truthful**. The
Pack now states the actual effect beneath the signature name—Howl’s eight-way
burst, Stoneskin’s shot/body guard, Murder’s three-way shard burst, Tidal
Wave’s bubble guard, and Swarm’s four-stinger fan. The generated content no
longer promises unused stuns, homing crows, or auto-aim drones. This also moves
the isolated Pack screen out of constrained bank 2, restoring over 2 KiB of
conference-development headroom there while keeping the 128 KiB ROM budget.

v0.17.77 gives every village arrival square a distinctive **Waykeeper** at
the north gate: a hooded lantern bearer who makes the onward route read as a
real inhabited threshold rather than an empty exit. The new sprite reuses a
combat-only VRAM slot only while a town is loaded; normal room entry restores
Rune Lantern art before enemies appear. Town and enemy-identity emulator
contracts prove both sides of that boundary.

v0.17.76 makes the **Spirit Compass** fully graphical in towns as well as
dungeons and the Riftwild. Select now shows the connected craft quarter,
arrival square, market, and northward gate as a tile-built civic map, with the
hero’s current plaza marked by the same bright cursor used everywhere else.
This replaces the misleading text-only town report, removes its font path from
the runtime, and saves bank space. A PyBoy contract verifies the four real map
nodes and returning to the live village.

v0.17.75 adds the **Rift Flail**, a rare A-weapon swap that can appear from
miniboss and vault weapon orbs. It is a slow, physical 3-pierce sweep: a
genuinely different melee build for any champion, rather than a starter-weapon
reskin. Weapon-orb selection now derives from generated content instead of a
hard-coded five-entry prefix, and the Pack screen correctly resolves a held
weapon by table index. An emulator contract covers real collection, swap,
physical art, reach, pierce, and damage.

v0.17.74 gives all nine dungeon biomes and all nine boss routes their own
compact musical phrases. The sequencer remains deliberately tiny—two voices
and a 128 KiB cartridge—but a move into Toxic Mire, Shadow Keep, Bloodmoon,
or the Void no longer just changes the tempo of an earlier loop. The music
regression now verifies both the live route IDs and all eighteen distinct
authored phrase pairs.

v0.17.73 makes Sauran's Stoneskin unmissable: four small ward shards orbit
the champion while the B shield is active. The existing body/projectile guard,
cooldown, and duration are unchanged; this is legibility for live play, backed
by an emulator test that proves the controller input, loaded art, spawned aura,
contact immunity, and expiry together.

v0.17.72 adds **Surge Sparks**, rare cyan lightning drops that give every
champion about fifteen seconds of a harder-hitting, faster-cycling primary
weapon. It is deliberately temporary—no permanent stat is changed, menus do
not consume its timer, and an emulator contract proves its unique sprite,
damage lift, and expiry. This release also removes a fragile pickup-magnet
routine that could move a reward away at contact; drops now stay put and use
the existing generous walk-over collection box.

v0.17.71 gives merchants a small gold trade speech bubble when the champion
steps close. The existing persistent sale markers and nearby HUD price then
answer what is for sale and how much it costs, without a modal dialogue or an
accidental purchase. The callout is generated from the same sprite source as
the rest of the cartridge art and has a live town regression check.

v0.17.70 fixes sale-marker cleanup: purchasing a ware now removes its exact
gold marker too, so a market never leaves a phantom price over an empty tile
or a later entity that happens to reuse the same slot.

v0.17.69 makes shops readable at a glance: every heart or relic ware now keeps
its own icon while a persistent gold sale marker floats above it. The normal
nearby-price HUD and walk-into purchase remain unchanged, so nothing that
looks like a loose pickup is silently a purchase.

v0.17.68 adds the **Rune Lantern** to Shadow Keep and Void Sanctum pools. It
drifts through cover and telegraphs slow four-way cardinal rings: the diagonals
remain deliberately open, but each volley makes the player choose a new lane.
Its generated content, unique runtime sprite, and exact four-lane output are
covered by the cartridge regression suite.

v0.17.67 is a measured melee hotfix: Tail Spike and Stinger keep their
established projectile origin and range while retaining their new physical arc
art. Controller-only replay on the same seeds restored Sauran's early-boss
progression, so the visual repair does not quietly change combat geometry.

v0.17.66 makes melee visually honest across weapon swaps: Wolfkin's claw,
Sauran's Tail Spike, and Vespine's Stinger now all render as physical sweep
arcs instead of ordinary bullets. Ranged weapons retain their distinct bullet
art.

v0.17.65 makes the opening run ask more of the player without changing its
controls: regular enemies survive one additional starter hit, while colossi no
longer receive the hidden all-elements vulnerability that shortened every boss
fight by a third. A controller-only, two-seed sample across all five champions
still progresses, visits shops, defeats early bosses, and records no combat or
route stalls.

v0.17.64 gives every village arrival square a distinct Chartwright resident.
Touching them marks the first two rooms of the route ahead on the tile-built
Spirit Compass: a small, deterministic scouting blessing that makes town stops
useful while leaving the rest of each procgen dungeon unknown.

v0.17.63 moves the live HUD code out of the always-mapped bank without changing
its gameplay behavior. This restores 1,547 bytes of bank-0 headroom (up from
569), keeping the 128 KiB cartridge comfortable for future stages, monsters,
and polish rather than making every feature a banking gamble.

v0.17.62 makes the tile-built Spirit Compass place the Rift Sigil icon inside
the exact room that contains it: cracked stone means it is still required and
a crystal means it was recovered. This replaces the old floating marker, which
could read as decoration rather than a clear route to an otherwise locked boss.

v0.17.61 raises Sauran's Tail Spike from three to four damage. Its deliberate
28-frame cadence, shield cooldown, and MP cost are unchanged; the tank now
has the heavy-hit throughput needed to earn its way through a first colossus.

v0.17.60 makes a colossus body collision one half-heart while leaving its
projectile damage, HP, patterns, and cadence unchanged. This gives melee
champions room to make a lunge without turning dense boss arenas into
contact-damage races.

v0.17.59 gives every stage colossus a short, audible opening telegraph before
its first volley. HP, damage, bullet patterns, and later cadence are unchanged:
the beat is there to make entry positioning readable rather than to flatten
bullet-hell pressure.

v0.17.58 fixes cartridge sprite-bank loading: all five champions, their
ascended forms, and every stage colossus now load their authored art from the
correct ROM bank. It also removes unnecessary merchant proximity scans from
combat rooms, restoring dense-room performance headroom.

v0.17.56 hardens seeded mini-boss rooms: escorts now choose the nearest clear,
champion-sized floor space after props are placed, so a crate can never create
an unreachable live enemy and seal progression.

## Screens

| Title | Class select | Dungeon | Pack / stats |
|:---:|:---:|:---:|:---:|
| ![title](docs/media/title.png) | ![class](docs/media/class.png) | ![dungeon](docs/media/dungeon.png) | ![pack](docs/media/pack.png) |

| Stage boss | Merchant | Sanctuary | Ember Depths |
|:---:|:---:|:---:|:---:|
| ![boss](docs/media/boss.png) | ![shop](docs/media/shop.png) | ![sanctuary](docs/media/sanctuary.png) | ![ember](docs/media/ember.png) |

## Features

- **5 monster-human classes** — Wolfkin, Sauran, Corvin, Picsean, Vespine — each
  with its own stats, primary weapon, signature move, and a live passive perk.
  Conference endurance floors give true-melee Wolfkin five hearts, ranged
  Corvin six, Picsean seven, and close-range Vespine five-and-a-half
  while preserving their low-DEF specialist identities; Picsean's Tidal Wave
  raises a brief water barrier while its three bubble lanes erupt, and its
  swim passive crosses Toxic Mire pools without damage.
- **9 distinct dungeon themes**, each with its own palette, numbered music variant, and enemy
  roster: Crystal Caverns → Verdant Hollow → Ember Depths → Frost Vault →
  Toxic Mire → Shadow Keep → Golden Temple → Bloodmoon → Void Sanctum — then
  the ninth colossus, animated ending, and permanent win record. Victors may
  retire to the title or choose an optional max-scaled endless descent.
- **Stage-specific traversal architecture** is content-authored alongside each
  theme: cavern layouts give way to Verdant crystal groves, Ember's broken
  hazard-seam gauntlets, Frost's four-entry crystalline arena rings, and Toxic
  Mire's four ragged poison-pool islands around a safe central cross. Shadow
  Keep then introduces mirrored, offset portcullises that force a three-court
  zig-zag through hard cover; Golden Temple opens into a broad processional
  aisle and transept framed by seeded colonnades and an inner crystal court;
  Bloodmoon carves four broken diagonal hazard cuts into a crimson ritual
  sigil; Void Sanctum closes the run with mirrored pillar-and-crystal arcs
  folding around an open event horizon. All exits remain preserved by
  construction across procedural variants.
- **Skippable cartridge storytelling**: the title animates the seven-beat Old
  Vow of the five champion spirits; victory resolves through three moving
  epilogue tableaux before revealing run statistics. START skips tableaux to
  results rather than past them; only the results page accepts A for endless
  descent or START to retire, preventing accidental choices during lore.
- **9 large-sprite bosses** (32×32 metasprites, distinct runtime silhouettes
  and bullet patterns, with a crowned final Void Lord and telegraphed volleys)
  plus **5 mini-boss types** (each its own sprite,
  colour, and attack), **merchants** with priced wares, and a **sanctuary**
  that fully restores HP/MP before every boss.
- **22 enemies across a size hierarchy** — small swarm critters (crawler,
  hornet, skeleton, wisp), player-sized 16×16 bruisers (orc, warlock),
  exploding **Bombers**, teleporting **Shades**, and **Ropes** (snakes that
  slither then bee-line at you), rotating Sentries, invulnerable-expanding
  **Folding Stars**, Keese-like **Flutterbats**, and life-draining
  **Gloom Leeches**, Ember's area-denial **Cinder Maws**, and late-stage
  **Rift Oozes** that split into two fragile crawler fragments when slain,
  and Frost Vault **Mirror Moths** that reverse the champion's last movement
  vector before firing a slow reflected bolt down the new lane. Toxic Mire's
  **Mire Spores** lie dormant until approached, flash through a 36-frame fuse,
  erupt across eight lanes, then expose a 90-frame melee punish window.
  Golden Temple's **Echo Guards** parry the first careless attack, rush the
  attacker, then turn pale and vulnerable until their shield recovers; poison
  remains a class-readable answer to their heavy armor.
  Shadow Keep and Void Sanctum add drifting **Rune Lanterns**, whose slow
  cardinal rings force readable lane changes while leaving diagonal exits.
  Golden Temple onward also fields **Dread Bells**: slow-moving iron casters
  with a visible long cadence and a fast eight-way peal that makes every lane
  a decision instead of simply inflating enemy health. Those same late pools
  add **Rift Wardens**, five-way fan casters that pressure the central route
  without erasing the far-diagonal dodge lanes.
  Verdant Hollow once again fields fast pursuing Hornets; typed content tests
  now reject any registered non-boss monster missing from every stage pool.
  Both fragments are guaranteed even when the fixed 32-entity table is full;
  a spent lethal projectile yields its slot before the split resolves.
  Folding Stars, Flutterbats, Gloom Leeches, Cinder Maws, Rift Oozes,
  Mirror Moths, and Mire Spores have dedicated silhouettes
  instead of borrowing older monsters' art, so movement and shape both
  communicate threat. Folding Stars remain invulnerable while expanded but
  now contract for a full one-second punish window, and pursuing monsters
  edge-follow around procgen pillars instead of wedging behind them forever.
  Flutterbat diagonals resolve by axis and use champion-sized navigation
  clearance, preventing an 8px flyer from entering geometry no 12px champion
  can reach and softlocking a sealed room.
- **Distinct champion combat + dodge dash**: Wolfkin is a true close-range
  melee fighter; `A` uses each class primary, `B` uses its signature, Sauran
  raises a projectile-breaking cooldown shield, and full-MP `A+B` unleashes
  **Spirit Convergence**: an opening eight-way burst followed by an 18-second
  class-specific full-sprite ascended form. Neutral and walk poses are now
  separately authored instead of mirroring whole sprite quadrants. Turbo fire
  remains hold-to-use but starts deliberately slower; run-earned SPD reduces
  the interval by two frames per point, making attack-speed growth visible.
  A double-tap **dodge-dash** grants i-frames for weaving through bullet hell.
- **RPG layer**: HP/MP/ATK/DEF/SPD/LCK, elemental weakness bonuses, crits,
  hit-flash / hit-stop / knockback / screen shake for weight.
- **Interactive dungeons**: shoot glowing cracked walls for treasure vaults,
  smash **pots** and shatter **crystals** for loot, kick apart rubble, shove
  crates onto rewarding **pressure plates**, and pick your way around **spike
  floors**. Seeded nonlinear **rift wells** disorientingly bounce between
  nonadjacent rooms within the same stage—all across 11 procgen room shapes.
- **Generated world cadence**: three six-room dungeons form a region, followed
  by a safe, connected three-screen village: an elder's fountain square, a
  dedicated market, and a forge/apothecary quarter. Its five visually distinct
  residents are the elder, Chartwright, merchant, masked smith, and apothecary.
  The Chartwright scouts the first two rooms of the *next* route once per town
  visit; a 15-coin Cartographer's Chart in the arrival square instead reveals
  all six rooms for that following dungeon. The smith staffs a 30-coin Power
  Stone forge; the apothecary's 30-coin Mana Gem permanently adds two maximum
  MP for the run, while dungeon shops retain their own broad-hatted merchant.
  Sanctuary blessing and seeded general stock round out the town economy.
  Stock holds a hanging price tag continuously so it cannot be mistaken for
  loose coins; approaching a ware previews its exact HUD price before contact,
  and unaffordable wares buzz once instead of nagging while the hero stands
  over them.
  The Spirit Compass gives each regional settlement a fixed remembered name—
  Emberford, Gloamharbor, or Dawn's Verge—but chooses its local warning from
  the run seed, making the place persistent while its account of the Rift
  remains deliberately uncertain. Dawn's Verge waits beyond the optional
  post-victory descent through Riftwild, making it a discoverable epilogue
  settlement rather than an interruption before the ending.
  Cleared dungeons open into the grassy, tree-lined **Riftwild**: an authored
  4×4 nonlinear overworld with trails, caves, vaults, champion encounters, and
  a discoverable gate to the next dungeon. Riftwild fights are optional and
  its exits remain fleeable, unlike selected sealed dungeon arenas. Every
  dungeon hides a recoverable **Rift Sigil** in its second room; its sanctuary
  threshold rejects forward progress until that stage's Sigil is claimed.
  SELECT draws tile-based linked 4×4 Riftwild and 3×2 dungeon maps: visited
  cells persist in battery SRAM, the current cell is a bright marker, and
  unseen cells remain blank. In town, the Spirit Compass switches
  to sanctuary context: completed/next region, elder restoration, and seeded
  market guidance instead of contradictory dungeon/depth labels. Lore is a
  set of fuzzy generated fixtures—not a fixed campaign replacing the run.
  Exploration music now continues through ordinary doorways instead of
  restarting every screen, and market stock keeps its actual heart/relic art
  while the HUD previews its semantic offer icon and price before contact.
  Wolfkin's close-range claw now
  renders as a distinct sweeping weapon arc instead of a generic bullet.
  Ordinary same-stage dungeon doors now stream the next room across the screen
  in all four cardinal directions; boss, town, and Riftwild boundaries retain
  their deliberate palette-safe transition.
- **Run-long relic builds**: permanent-for-the-run stat items appear in seeded
  vaults and shops. The Vampiric Sigil restores a half-heart every fifth kill;
  an eight-heart cap leaves upgrade room even for six-heart Sauran. All relic
  boosts saturate at their displayed stat caps, including multi-point luck
  relics near the cap.
- **Roguelike persistence done right**: battery **suspend save** resumes your
  run (and dies with you — permadeath holds), while best score / runs / wins
  persist forever. High and endless-run scores saturate at 65,535 instead of
  wrapping back through zero. The cartridge regression suite delivers a real
  fatal hostile shot, waits through the animated game-over entry, power-cycles
  SRAM, proves the dead run cannot resume, and starts a clean replacement run.
- **Full chiptune audio**: nine numbered exploration variants and nine
  dedicated boss variants, plus title / victory / gameover tracks and 10
  register-level SFX. Reprised melodic families change tempo and pacing, so
  every stage/boss pairing remains audibly distinct within the ROM budget.
- **Hardware-paced CGB performance**: the CGB-only cartridge uses double-speed
  CPU mode and does not discard a second VBlank after a busy frame. Ordinary
  rooms hold 60/60 simulation Hz; the verification gate keeps a synthetic
  12-projectile bullet-hell room above 80% video rate instead of collapsing
  from a tiny overrun directly to 30 Hz.
- **Honest active-play timing**: the run clock follows hardware VBlanks even
  in dense combat, pauses in PACK and the Spirit Compass, and retains the
  subsecond earned before opening either screen. Menu tapping therefore cannot
  erase fractions from a timed run. A cartridge regression enforces ordinary,
  overloaded, inventory, and compass timing paths.

## Controls

| Input | Action |
|---|---|
| **D-pad** | Move (8-way aim while firing); double-tap to dodge-dash and shake off attached Gloom Leeches |
| **A** | Primary weapon (Wolfkin: melee) · continue a suspended run (title) |
| **B** | Class signature move (2 MP; Sauran: shield) |
| **A+B** | Spirit Convergence when MP is full |
| **START** | Pack screen (stats, loadout, run clock) |
| **SELECT** | Spirit Compass (dungeon/town progress; Riftwild coordinates, exits, and landmark hint) |

Shoot the glowing amber wall tiles — they hide secret rooms.

## Build & run

Requires [GBDK-2020](https://github.com/gbdk-2020/gbdk-2020) v4.5.0 at `~/gbdk`
and a stable Rust toolchain (host-side only — Rust never ships in the ROM).

```bash
make            # cargo codegen + sprite pipeline → SDCC → rom/working/quintra.gbc
make play       # build + launch in mGBA
make verify     # ROM tests + procgen parity + deterministic input replay
make preflight  # cart header/checksums + real battery-SRAM power-cycle test
make repro-check # clean source copy must rebuild the exact same ROM bytes
make balance    # five controller-only ROM agents -> tmp/balance-runs.csv
make endurance  # 15 long controller-only runs -> tmp/endurance-runs.csv
make policy-sweep # compare Sauran/Corvin giant-fight input policies
make final-sigil-proof # seed-14 final-Sigil controller completion proof
make picsean-endurance # four completed multi-seed Picsean controller runs
make victory-proof # full nine-boss Picsean run + clean-emulator input replay
make media      # recapture the README reel from the current ROM
make media-check # prove reel version/hash/frame budget match the ROM
make info       # print build summary
```

`make balance` runs the actual cartridge under **mGBA headless** with five
heuristic
agents, one per champion. They may read combat state to aim, but they only
send controller input—unlike reachability smoke tests, they never refill HP,
delete enemies, alter currency, or alter progression. They make affordable,
health-aware purchases through real movement and report purchase counts, so
the endurance gate proves every sample exercises the procedural economy. A
live encounter bitmask requires every generated enemy (IDs 0–21) to appear
somewhere in the paired-seed endurance matrix, preventing a valid but
procedurally unreachable monster from hiding behind green completion tests.
Treat their CSV as a repeatable balance
baseline, not a substitute for human playtests. The `quintra-mgba` host tool
parses that telemetry by named columns, prints per-class medians, and enforces
report-count and victory-floor gates; the runner contains no duplicate inline
report implementation. An older controller-only Wolfkin reference run
completed all nine bosses in 20,686 gameplay frames (**5:45** at 60 Hz), but
it is historical data. The current deterministic proof is Picsean seed 13:
all nine bosses in 53,415 gameplay frames (**14:50** at 60 Hz), verified by
replaying the recorded controller trace in a fresh emulator with matching seed,
room, HP, and victory state. Run `make victory-proof` to reproduce that proof;
it is one certified seed. `make final-sigil-proof` additionally proves that
the formerly stalled seed-14 final Sigil reaches a nine-boss victory through
ordinary controller input. `make picsean-endurance` now completes all four
consecutive Picsean seeds (13–16) through all nine bosses in 44k–55k frames.
Its Riftwild policy keeps the real B shield for normal close passes but resumes
the authored exit input after repeated grass-screen body contact, preventing
an optional enemy from pinning the pilot at the border. The all-class `make
endurance` target remains the stricter conference soak floor.
Expect
roughly **20–35 minutes** for a first successful human run and **10–20
minutes** once practiced; deaths and procedural seeds make total session
length variable. `make verify` also
boots the ending, checks its battery-SRAM win record, and returns to the title.
Its smoke pass resolves WRAM symbols from the current linker output and asserts
rooms 0→1→2→3→4→6, defeats a live giant through real A-button shots, then
proves Pack-screen entry and room return; it does not trust fixed debug
addresses or screenshot appearance alone.
Set `QUINTRA_BALANCE_TRACE_DIR=tmp/traces` to retain RLE-compressed joypad
transitions for selected balance runs. `make verify` records a Corvin run,
boots a second untouched emulator, replays only those controller states, and
requires seed, room, clears, kills, bosses, HP, outcome, screen, and total host
frames to match exactly. This turns a reported death or stall into a portable,
frame-for-frame cartridge reproduction without RAM or RNG instrumentation.
The default headless backend keeps these controller-only checks fast and
display-independent; set `QUINTRA_MGBA_BIN` to another compatible mGBA binary
when diagnosing a frontend-specific issue.
It enforces a 128 KiB ROM ceiling and at least 512 bytes of free always-mapped
bank space; v0.18.2 occupies 128 KiB with 1,463 bytes of bank-0 headroom.
Gameplay files
use an explicit validated bank map and the source manifest is sorted; the
preflight clean-copy rebuild must match the working ROM byte-for-byte, avoiding
GBDK autobank assignments that otherwise vary with an absolute checkout path.
The layout gate rejects any fixed switchable bank with less than 1 KiB free,
well before GBDK's warning-only cross-bank overwrite could produce a corrupt
ROM. The v0.18.2 release has 3,602 bytes in bank 1, 1,582 in bank 2,
3,334 in bank 3, 7,041 in bank 4, 11,775 in bank 5, and 14,811 in bank 6;
the always-mapped bank retains 1,463 bytes of headroom.
Enemy OBJ tile and palette identity now comes directly from validated generated
content rather than duplicate runtime switches. Hardware-range validation pins
tiles to 0–127 and palettes to 0–7. Combat now shares bank 3 with projectiles
and pickups, while the dispatcher-owned Pack screen moved out of the crowded
room/procgen code now has a dedicated bank. `make verify` remains the
authoritative layout report; the figures above are the current release build.
Ascended champion art is emitted into a separate
bank-3 translation unit so GBDK cannot silently pack it into constrained bank 2.
Sprite arrays and their C declarations are emitted together from the same
typed Rust asset lists. Golden tests pin both files and require exactly one
declaration per generated array, so adding art can no longer leave a stale
hand-maintained header that breaks only during the ROM build.

Before a show build, `make endurance` runs three long-form entropy samples for
every champion, with a practiced-run ceiling of 90,000 gameplay frames (25
minutes at 60 Hz). It requires at least two complete nine-boss victories and
rendered endings per champion, complete telemetry, and zero rooms that retain
combat or cleared-route control for more than 7,200 frames (two minutes).
The freshly rerun v0.18.2 15/15 matrix has complete telemetry, encounters
every roster member, and has **zero** controller combat or route stalls, but
does **not** pass this gate yet. Picsean reaches two complete nine-boss
endings in three samples; Wolfkin clears its first boss in all three seeds but
remains 0/3 for endings; Sauran and Corvin clear a first boss in one sample
each; and Vespine does so in two. The old exact three-ending Picsean recheck
remains useful controller research, but it is not substituted for this fresh
all-class matrix. A future matrix must still reach the full per-class victory
floor to pass the delivery gate.
It is therefore not a show build. The v0.17.46 14/15 result remains a
historical benchmark only. The gate proves every class faces the same three
procedural worlds; its former fixed host-frame padding silently produced
different seeds after class-select redraws. Successful agents still fall as
low as one half-heart and vary from roughly 4:45 to 11:47 active play, so
the sample retains pressure and meaningful build/seed variance.

The agents read the held A-weapon every frame—not just the selected champion—so
a procedural Flail or Astral Spear swap changes its route/spacing policy to
the real build shape; starter lunge routes retain their separately measured
cover-safe behavior. They use each champion's B ability, collect
finite hearts/MP/relics after combat, and report combat stalls separately from
route stalls. Narrow a reproduction with `QUINTRA_BALANCE_CLASSES='3 4'` and
`QUINTRA_BALANCE_RUNS='2'`; no health, enemy, RNG, or progression writes are
used in balance runs. Each row reports accepted `b_uses` (the game entering a
class-signature cooldown after a B-only press), rather than merely button
requests. Set `QUINTRA_BOT_ABILITY_POLICY=off` for a no-signature control;
the default `smart` policy uses reactive shields and Corvin's close-pack
burst. Rows
also separate `boss_attempt_frames` from `boss_clear_frames`, so a failed
bullet-hell attempt cannot be mistaken for a slow successful fight. The
semicolon-separated `boss_clear_durations` field exposes every successful
boss individually, so stage-specific tuning is measurable instead of averaged
away. The typed balance report prints the per-stage clear medians directly.
Each
emulator attempt writes to its own CSV; a file-locked duplicate check commits
exactly one finished row to the matrix, so late or overlapping processes cannot
pollute an interrupted/resumed sample. `giant_overlap_damage` separately
records HP lost on frames where the actual giant hurtbox overlaps the hero;
this distinguishes boss body-pinning from projectile pressure without writing
to cartridge state.

`make policy-sweep` is the reproducible controller-search loop: it runs the
baseline, orbit, orbit-fire, and pulse-fire giant policies through ordinary
inputs and emits one CSV per class/policy under `tmp/policy-sweep/`, plus a
compact table of boss clears, wins, deepest room, minimum HP, and stalls. It
defaults to Sauran and Corvin; set `QUINTRA_POLICY_CLASSES`,
`QUINTRA_POLICY_POLICIES`, `QUINTRA_POLICY_REPS`, or
`QUINTRA_POLICY_FRAMES` to widen an experiment. It is deliberately a
read-only-ROM evaluator, so an apparent improvement must survive a fresh
input-only replay before becoming the default policy.

Giant spacing defaults to a measured classwise policy: Sauran, Corvin,
Picsean, and Vespine use `orbit_fire` for large bosses; Wolfkin uses
conservative pulses. On paired three-seed searches,
Picsean's policy raised its boss clears from two to six with no deaths, while
orbit-fire gained four Sauran and four Corvin clears where their prior policies
managed two and one. Override it with
`QUINTRA_BOT_GIANT_POLICY=baseline` when comparing a candidate.
Wolfkin's classwise giant-retreat buffer is 32px (the other baseline kits use
28px): its paired three-seed first-boss sample improved from one to two clears
at 32px. Set `QUINTRA_BOT_GIANT_RETREAT_RANGE` explicitly for a matched sweep.

Long-form routing treats the Riftwild dungeon gate and nonlinear cave vault
as their real central staircase nodes, visits both the market and the
forge/apothecary quarter before taking a town's north gate, and records
`town_market_visits` / `town_quarter_visits` separately so that choice is
verifiable. It mirrors the cartridge's feet-center spike test before allowing
a tactical dodge or attack movement, and creates space from ordinary bodies
before short-range champions are forced into repeated contact trades. These
are controller-only safety
rules: the agent still changes the run solely through normal button input.
If it reaches a Sigil-gated sanctuary without that stage's fixture, it now
backs through the local dungeon to recover the objective rather than treating
the deliberately locked forward door as a route stall; a deterministic Sauran
regression covers that return route.
Picsean also uses the actual Tidal Wave Undertow guard when a nearby Riftwild
body cannot be sidestepped in the authored exit lane; a paired live-ROM run
must cross that world passage, clear the second boss, and reach the next
dungeon without controller-only state edits.
The same long-form run must leave the three-screen town through its real north
gate and reach the next dungeon—its controller route centers on the civic lane
then presses through the door lip, rather than targeting a blocked point just
inside the gate.
Vespine's 48px Stinger receives the same six-tile Flutterbat pursuit lane as
the ranged champions; a three-seed live-ROM regression requires it to clear
that moving-target room and reach the first boss threshold without a stall.

Constrained hosts can split a matrix into seed batches
with `QUINTRA_BALANCE_APPEND=1` and `QUINTRA_BALANCE_SKIP_REPORT=1`, then run
one final report against the accumulated CSV; every class/seed row is still
required before that report succeeds. Shop reachability and purchases are separate telemetry:
a stocked merchant room counts as a visit even if the agent cannot afford—or
does not need—its wares. Telemetry retains the worst combat and route dwell from
the entire run—not merely its final room—and identifies the responsible room
and enemy for reproducible failures. Death attribution is inferred entirely by
the emulator observer, so it cannot perturb cartridge timing: values 0–17 name
the nearest hostile, 254 denotes floor hazards, and 253 is an unresolved hostile
hit. Two-frame press/release beats ensure real
cartridge polls observe dodge double-taps; stalled firing lanes use the same
collision-aware BFS as melee pursuit instead of orbiting outside U-shaped
cover forever. Its cleared-room recovery gives tile-path alignment more
time than combat pursuit, preventing collision nudges from defeating its own
shortest-path route. Short-range champions also path around cover to engage,
then line up their final few pixels on the target's cardinal axis before
striking. Ranged champions also step onto a close boss's row or column instead
of orbiting at a perfect diagonal and sending cardinal shots past its corner.
If cover absorbs four seconds of any weapon's attacks, they flank and
reacquire instead of attacking the wall forever. Debug runs can emit a
one-shot screenshot when a room exceeds the stall threshold by setting
`QUINTRA_BOT_DEBUG_SCREEN=/tmp/quintra-stall`; with `QUINTRA_BOT_DEBUG=1`,
active giant fights are also sampled once per second so a corner pin can be
reproduced from controller input rather than guessed from a final CSV row.
Set `QUINTRA_BALANCE_DEBUG=1 QUINTRA_BALANCE_DEBUG_DIR=tmp/agent-debug` on the
wrapper to retain per-trial `BOTROOM`, `BOTWEAPON`, `BOTHIT`, ability, and
position events after mGBA exits;
run `make agent-events AGENT_EVENTS_DIR=tmp/agent-debug` to summarize each
trial's early-room and boss damage by source. The ordinary CSV remains the
compact release metric. The agent
also performs a real double-tap dash when a Gloom Leech attaches. Cleared
dungeon rooms that genuinely exceed that threshold switch to a pixel-exact
feet-box edge follow for one body width, escaping pillar corners that the
coarser tile route cannot represent; overworld routing remains authored.

`scripts/search_boss_policy.sh` is the offline policy harness: it evaluates
`baseline`, `orbit`, `orbit_fire`, and `pulse_fire` button-only giant policies
over the same seed/class grid and compares boss clears, deaths, minimum giant
HP, and damage taken. It does not silently adopt a candidate; a policy earns
adoption only after it beats baseline on reproducible evidence. For a quick Sauran sample,
run `QUINTRA_BOSS_SEARCH_RUNS=1 QUINTRA_BOSS_SEARCH_CLASSES=1 bash
scripts/search_boss_policy.sh`. `QUINTRA_BOSS_SEARCH_RETREAT_RANGES` and
`QUINTRA_BOSS_SEARCH_FIRE_CADENCES` accept either spaces or commas (for
example, `20 28 36` or `20,28,36`) for a matched sweep. The latter compares
how often `orbit_fire` takes an aimed beat while otherwise preserving its
collision-safe orbit; it changes only controller input, never game state.

## World Retro delivery bar — September 12, 2026

The conference build is a deliberately bounded, cartridge-first target: one
complete nine-boss route, the five champions, villages/Riftwild between dungeon
regions, procedural rooms with authored lore fixtures, and a real ending. The
goal is a confident 20–30 minute first clear, not an endless pile of systems.

Every gameplay candidate must clear three gates before it earns a ROM release:

1. `make preflight` validates the mapper, checksums, SRAM suspend/resume, and
   ROM-bank headroom.
2. Targeted PyBoy contracts prove the new interaction in the live cartridge,
   not just in C source or a debug poke.
3. The isolated Picsean endurance gate runs seeds 13–16 using only controller
   input. A completed row is a real loss or win; a missing row retries once in
   isolation because headless mGBA can occasionally bus-error under parallel
   load. The current baseline clears all four seeds in 44k–55k frames.

### Current conference evidence (v0.18.7)

- Functional ROM contracts pass, including the first-Colossus health budget,
  giant body-contact recovery, Skeleton clearance, score/Sigil stability, and
  the full boss identity suite.
- Cartridge-header and cold-boot SRAM checks pass; the refreshed 174-frame
  reel is hash-checked against the release ROM in `docs/media/gameplay.json`.
- This is **not yet a show-build sign-off**: the all-class endurance delivery
  gate remains two nine-boss endings per champion over three entropy samples
  with zero combat/route stalls. Picsean now meets that floor (2/3 wins,
  zero stalls); the other four champions do not yet, which keeps the next
  balance work focused on their long-run survivability.

The final stretch prioritizes readability and playability: room-transition
feel, merchant/tutorial clarity, late-boss patterns that are harder without
turning early runs into a wall, and physical-cart smoke testing. New content
is welcome only when it fits that budget and keeps the reproducible route
healthy.

Cart spec: **128 KiB ROM, MBC5 + 32 KiB RAM + battery, CGB-only**, with the
validated cartridge title `QUINTRA`. `make preflight` checks the Nintendo logo,
mapper/size flags, header and global checksums, then writes a live suspend to
SRAM and resumes it in a fresh emulator instance—the software equivalent of a
power cycle. A GB Operator
can upload the `.gbc` through **Data → Upload Homebrew** to a compatible
rewritable MBC5 flash/reproduction cartridge. It cannot overwrite the mask ROM
inside a normal original retail cartridge. Verify suspend/resume on hardware:
some reproduction boards implement save RAM differently despite accepting the
ROM image. For an EverDrive, skip the Operator and copy `quintra.gbc` directly
to the cartridge's microSD card.

## Architecture

The C runtime under `src/` is the only thing on the cartridge. Content
(classes, items, enemies, biomes, rooms) is hand-authored as **typed Rust** in
`content/`; the `tools/` Rust workspace validates it and emits GBDK-compatible
C tables into `src/generated/` at build time. Invalid content — an orphan item
reference, an oversize table — fails `cargo build`, never the Game Boy.

```
src/       C runtime (core / render / audio / input / game / generated)
content/   typed Rust content (the source of truth)
tools/     Rust workspace — content codegen, asset pipeline, procgen, mGBA bridge
docs/      design specs + media
```

See `docs/superpowers/specs/` for the full engine design and audit.

## Why Rust tooling but a C runtime?

Rust can't target the GBC's Sharp SM83 CPU — no LLVM/GCC backend exists, so the
runtime *must* be C. But Rust shines on the host side: typed content schemas and
compile-time invariant checking mean bad content can't reach the cart.

## Legal

Quintra is wholly original. It contains **no** assets from Penta Dragon or any
other game — only its own art, audio, and code.
