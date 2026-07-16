# Quintra

**A procedural Zelda-like action roguelike for the Game Boy Color.**

Native CGB. Five monster-human classes, procgen dungeons every run, bullet-hell
bosses, and item-driven builds. Heavy [Penta Dragon](https://en.wikipedia.org/wiki/Penta_Dragon)
influence (dense projectile patterns) crossed with the maze-exploration feel of
Zelda: Link's Awakening / Final Fantasy Adventure / Ultima: Runes of Virtue.

Written in C with GBDK-2020 — the only thing that ships on cart. All content
authoring and dev tooling is a typed **Rust** workspace that generates the C
tables at build time.

[Download the latest ROM — v0.17.49: Ascendant](https://github.com/struktured-labs/quintra/releases/latest)

![Quintra gameplay](docs/media/gameplay.gif)

The v0.17 reel shows the animated five-spirit prologue, champion selection,
live dungeon combat, the Riftwild overworld, a nonlinear cave-to-vault
teleport, and the animated epilogue. The transitions shown are executed by
the cartridge runtime.

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
- **19 enemies across a size hierarchy** — small swarm critters (crawler,
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
  by a safe procedural town with four visually distinct residents: elder,
  merchant, masked smith, and apothecary. The smith staffs a 30-coin Power
  Stone forge; the apothecary's 30-coin Mana Gem permanently adds two maximum
  MP for the run, while dungeon shops retain their own broad-hatted merchant.
  Sanctuary blessing and seeded general stock round out the town economy.
  Stock holds a hanging price tag continuously so it cannot be mistaken for
  loose coins; contact prints the exact price in the HUD, and unaffordable
  wares buzz once instead of nagging while the hero stands over them.
  The Spirit Compass gives each regional settlement a fixed remembered name—
  Emberford, Gloamharbor, or Dawn's Verge—but chooses its local warning from
  the run seed, making the place persistent while its account of the Rift
  remains deliberately uncertain. Dawn's Verge waits beyond the optional
  post-victory descent through Riftwild, making it a discoverable epilogue
  settlement rather than an interruption before the ending.
  Cleared dungeons open into an authored 4x4
  nonlinear overworld graph with caves, vaults, champion encounters, and a discoverable
  gate to the next dungeon. Riftwild fights are optional and its exits remain
  fleeable, unlike sealed dungeon arenas. SELECT now draws a real linked 4×4
  Riftwild map and a 3×2 dungeon route: visited cells persist in battery SRAM,
  the current cell is marked `@`, and unseen cells remain `?`. In town, the Spirit Compass switches
  to sanctuary context: completed/next region, elder restoration, and seeded
  market guidance instead of contradictory dungeon/depth labels. Lore is a
  set of fuzzy generated fixtures—not a fixed campaign replacing the run.
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
make media      # recapture the README reel from the current ROM
make media-check # prove reel version/hash/frame budget match the ROM
make info       # print build summary
```

`make balance` runs the actual cartridge under mGBA with five heuristic
agents, one per champion. They may read combat state to aim, but they only
send controller input—unlike reachability smoke tests, they never refill HP,
delete enemies, alter currency, or alter progression. They make affordable,
health-aware purchases through real movement and report purchase counts, so
the endurance gate proves every sample exercises the procedural economy. A
live encounter bitmask also requires the complete generated roster (IDs 0–18)
to appear somewhere in the paired-seed matrix, preventing a valid but
procedurally unreachable monster from hiding behind green completion tests.
Treat their CSV as a repeatable balance
baseline, not a substitute for human playtests. The `quintra-mgba` host tool
parses that telemetry by named columns, prints per-class medians, and enforces
report-count and victory-floor gates; the runner contains no duplicate inline
report implementation. A controller-only Wolfkin
reference run completes all nine bosses and reaches the rendered ending in
20,686 gameplay frames (**5:45** at 60 Hz). Expect roughly **20–35 minutes**
for a first successful human run and **10–20 minutes** once practiced; deaths
and procedural seeds make total session length variable. `make verify` also
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
It enforces a
128 KiB ROM ceiling and at least 512 bytes of free always-mapped bank space;
v0.17.49 occupies 64 KiB with 632 bytes of bank-0 headroom. Gameplay files
use an explicit validated bank map and the source manifest is sorted; the
preflight clean-copy rebuild must match the working ROM byte-for-byte, avoiding
GBDK autobank assignments that otherwise vary with an absolute checkout path.
The layout gate rejects any fixed switchable bank with less than 1 KiB free,
well before GBDK's warning-only cross-bank overwrite could produce a corrupt
ROM.
Enemy OBJ tile and palette identity now comes directly from validated generated
content rather than duplicate runtime switches. Hardware-range validation pins
tiles to 0–127 and palettes to 0–7. Combat now shares bank 3 with projectiles
and pickups, while the dispatcher-owned Pack screen moved out of the crowded
room/procgen bank. Switchable headroom is now 1,042 bytes in bank 1, 1,043 in
bank 2, and 1,027 in bank 3. Ascended champion art is emitted into a separate
bank-3 translation unit so GBDK cannot silently pack it into constrained bank 2.
Sprite arrays and their C declarations are emitted together from the same
typed Rust asset lists. Golden tests pin both files and require exactly one
declaration per generated array, so adding art can no longer leave a stale
hand-maintained header that breaks only during the ROM build.

Before a show build, `make endurance` runs three long-form entropy samples for
every champion, with a practiced-run ceiling of 90,000 gameplay frames (25
minutes at 60 Hz). It requires at least two complete nine-boss victories and
rendered endings per champion, complete telemetry, and zero rooms that retain
combat or cleared-route control for more than 7,200 frames (two minutes). The
v0.17.46 records 14/15 full clears: 3/3 for Wolfkin, Sauran, Picsean, and
Vespine and 2/3 for Corvin, whose remaining failure is a real boss death rather
than a timeout. Every enemy ID 0–18 appears in live cartridge state; combat
and route stalls remain zero. Runs make 7–11 real purchases rather than
bypassing merchants, and no run exceeds 70 Riftwild transitions. The gate now
proves every class faces the same three
procedural worlds; its former fixed host-frame padding silently produced
different seeds after class-select redraws. Successful agents still fall as
low as one half-heart and vary from roughly 4:45 to 11:47 active play, so
the sample retains pressure and meaningful build/seed variance.

The agents use each champion's actual weapon range and B ability, collect
finite hearts/MP/relics after combat, and report combat stalls separately from
route stalls. Narrow a reproduction with `QUINTRA_BALANCE_CLASSES='3 4'` and
`QUINTRA_BALANCE_RUNS='2'`; no health, enemy, RNG, or progression writes are
used in balance runs. Telemetry retains the worst combat and route dwell from
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
`QUINTRA_BOT_DEBUG_SCREEN=/tmp/quintra-stall`, and the agent
also performs a real double-tap dash when a Gloom Leech attaches. Cleared
dungeon rooms that genuinely exceed that threshold switch to a pixel-exact
feet-box edge follow for one body width, escaping pillar corners that the
coarser tile route cannot represent; overworld routing remains authored.

Cart spec: **64 KiB ROM, MBC5 + 32 KiB RAM + battery, CGB-only**, with the
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
