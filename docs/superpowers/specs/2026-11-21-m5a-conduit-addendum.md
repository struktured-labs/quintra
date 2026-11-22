# M5a Ember Conduit — implementation addendum (PR #149 spec, milestone M5)

Status: M5a (playable subset of the spec's showcase floor). Stacks on M4
(`feat/m4-keys`). Optional pocket, never sealed, rebuilt from WRAM on entry.

## What ships
A 12x18 pocket in one large room of **stage 5** (dungeon index 5), chosen by
`rime_pick_cell` like M1–M4 (`CD_STAGE = 5`, `PUZZLE_CONDUIT_ROOM` = 11).

```
############   0
#11...#....#   1  teleport pad | turret (OBJ) in the east wing
#11...#....#   2
#.....D....#   3  D = side door (6,3..4), bars <-> floor
#33...D..22#   4  reset plate | gold switch under the turret
#33.33#..22#   5  Rime (freeze) pedestal (4..5,5..6)
....33#....#   6  entrance rows 6..7 | Star key (8..9,6..7)
......#....#   7
####33######   8  spawn plate in the only walking gap
#...33.....#   9  hall landing (teleport arrives at (1,9))
#==========#  10  rolling-stone lane; Stone Jagger guards it
#==========#  11
#####SS#####  12  Star door
#..........#  13  vault
#....GG....#  15  goal
############  17
```

* **Turret churn.** Every 80–111 frames (Easy 104–135) the turret telegraphs
  24 (32) frames — body flash, aim spark, and a gold flash on the switch when
  the lane crosses it — then fires one enemy bolt W or S (70% aimed: S when
  the hero is below the turret's rows, else W; 30% random). A bolt striking
  the gold switch flips the side door. After each flip a 64 (80) frame
  lockout pauses the fire timer. A shut is deferred while the hero overlaps
  the door cells. Player bolts damage the turret (4 HP) and never flip the
  switch; turret death opens the side door for good (fail-safe).
* **Star key** sits in the wing behind the churned door; the **Star door**
  refuses without it (`SFX_REFUSE`), opens with it.
* **Rime pedestal** gives one FREEZE charge (re-arms whenever none is held and
  no freeze runs). Pack TOOL FREEZE stops monsters, the Jagger and the turret
  cadence for 45 beats (Easy 56).
* **Stone Jagger** shadows the hero's x along the lane in front of the Star
  door (clamped to cols 3..7); its touch shoves back, never damages. It steps
  out of the lane while a stone is coming.
* **Rolling stone** rumbles (40 f, shake) then rolls west at 2 px/f every
  ~140 f. It crushes a **frozen** Jagger (removed until reset), shatters on an
  awake one, kills pack monsters, and shoves the hero out of the lane (no
  damage, 20 iframes).
* **Spawn plate** in the gap releases two of an ordinary enemy already in the
  room (while they live the keep-out box shrinks to the upper pocket, so they roam only the lower hall); the **teleport pad** jumps to the
  hall landing past the plate.
* **Reset**: Pack RESET ROOM (anywhere, incl. pinned or shut in the wing),
  the reset plate, and walking out all restore everything.

## Deviations from the spec
* Placed on stage 5, not Ember (stage 2): Ember hosts M2's pocket and the
  solved bit (`RUN_RIME_SOLVED_BIT`) is per dungeon, one pocket per dungeon.
* ROM not grown to 1 MiB (Carbon suggested bank 32): `check_cartridge.py`
  enforces 512 KiB; code fit into banks 5/14/16/22/24 instead. Needs an owner
  decision before M5b.
* Jagger shoves instead of damaging; freeze alone can slip past it (lure it
  aside, freeze, walk round), the stone gives the permanent removal.
* No off-camera cue for the side door (it is always on screen with the wing).
* Doors relock after solve on reset (the goal stays pressed).
* Deferred to **M5b**: rewrite switches A/B, the Kite chain, the Heart
  two-door choice.

## M5b: the vault (stacked on M5a)

The Star door moves to cols 6..7 of row 12 and opens onto a vault, rows 13..16:

```
r12 ############   Star door (6..7)
r13 #..HLL..H..#   Heart door B (3) | crystal lock (4..5, holds the Heart key) | Heart door A (8) | closet (9..10)
r14 #GGHLLPPH..#   goal alcove (1..2) | release plate (6..7)
r15 #SSSSSSCCSS#   rift stream (Kite only, 1 px per tick): region B (5..6) starts as stream, region A (7..8) starts as cairn
r16 #SSSSSSCCSS#   Kite home (9..10), stops under the lock (4..5)
r9  #g..33....g#   rewrite switches at the hall dead ends: A (1) flips A and B, B (10) flips B
```

* **Rewrite switches.** The pair uses materials the player has already seen in M3: the cairn and the rift stream. A glyph on each switch shows the state of its region. Raising a cairn onto the flying or stopped Kite is refused with the dud clunk.
* **Kite chain.** Only the release plate wakes the Kite. It rides west at 1 px per tick and waits at any cairn in its path. Freeze holds it too. At the lock it breathes for 30 frames and shatters it, which frees the Heart key.
* **Heart two-door choice.** There is one Heart key and two doors. Door A opens the treasure closet, which spawns a 5-coin pickup once per visit. Door B opens the goal. Using a Pack reset returns the key, the lock, the Kite and the regions, so every choice can be retried and nothing softlocks.
* **Turret-death fail-safe** is proved in-ROM with a projectile hero (Picsean). The test shoots the turret dead and then checks that the side door stays open for 600 frames and that player bolts never flip it.

### Deviations

* There is no off-camera blink when a rewrite changes a region you can't see; instead every rewrite plays a distinct cue (`SFX_DISTRICT`).
* All art is reused from M2–M4 (originally GPT-derived): cairn, stream, lock, Kite and the Heart bow. The two glyphs are 8×8 downsamples of the M3 tiles. No new renders were made.
* The switches sit at the hall's dead ends rather than beside the Star door. A single-row hall otherwise forces the player across them.
