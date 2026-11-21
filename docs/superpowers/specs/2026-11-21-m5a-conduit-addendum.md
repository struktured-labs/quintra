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
  room (keep-out lifts while they live); the **teleport pad** jumps to the
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
* Pack keep-out lifts while the pack lives; doors relock after solve on reset.
* Deferred to **M5b**: rewrite switches A/B, the Kite chain, the Heart
  two-door choice.
