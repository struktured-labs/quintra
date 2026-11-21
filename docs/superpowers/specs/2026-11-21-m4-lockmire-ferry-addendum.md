# M4 Lockmire Ferry — implementation addendum (2026-11-21)

Companion to `2026-11-19-ultima-puzzle-depth.md` (PR #149), milestone **M4: choice keys and
flip-conveyors** (§6.7 matching keys, §6.8 lure, §6.9 flip-conveyors). Stacked on PR #154
(`feat/m3-kite`). It reuses the shared pocket machinery (`rime_pick_cell`, `puzzle_pack_*`,
`puzzle_keep_*`), M2's region painter pattern (world arrays now, VRAM one region per frame,
off-camera cue + blink on arrival, re-dress on BG reload), M1's Stone Jagger art and plate, and
M3's cage bars.

## Placement
- **Toxic Mire** (stage 4, `bosses_beaten == 4`), the same optional pocket cell as M1–M3.
  One new verb per dungeon: Verdant freeze (M1), Ember rewrite (M2), Frost tool-beast (M3),
  Mire keys + ferry (M4). The spec names no dungeon for M4.
- 12x18 tiles at world x18–29, y11–28 of a wide room. West-wall entrance at local rows 6–7 with a
  corridor to the central trail. Never on the critical path. Self-contained: WRAM only, rebuilt
  on entry; the per-dungeon pocket bit only stops a second reward.

## Layout (introduce, then combine)
```
############
#......#...#   Heart key (2,1), Star key (5,1) | Moon nook (coin at 9,1)
#......#...#
#......##..#   Moon door (9..10,3)
#..........#   reset plate (1..2,4..5)
#..........#   lure pedestal (8..9,5..6)
...........#   entrance (rows 6..7), always open
...........#
#####SS#####   Star door
#........###   flip plate (7..8,9..10); fence over the Jagger
#........###
#WW>>>>>>JJ#   weight plate W | east belt lane | Jagger rest
#WW>>>>>>JJ#
#........<<#   fixed west-belt preview
#==##GG##==#   windows (closet, vault) | gate (bars)
#..H....H..#   closet + Moon key (1,15) | Heart door W | ante | Heart door E | vault
#..H....HGG#   vault goal (9..10,16)
############
```
1. **Keys (introduce).** Heart and Star sit in the entry hall. The Star door seals the ferry hall.
   A Heart key bumping the Star door is refused (`SFX_REFUSE`), not consumed; the Star key opens it.
2. **Lure (introduce).** Pick it up from its pedestal; drop it from the Pack (TOOL LURE). It may
   only be dropped on plain floor of the ferry hall rows 9–10, x1–6: never in the entry hall, on
   the entrance/reset path, the lane, or the plates (refused). It cannot be picked back up.
3. **Conveyor (introduce).** The lane is an east belt; a fixed west-belt strip under the vault
   window previews the other direction before any flip. Belts push bodies 2 px/frame (the hero
   1 px x2, stopped by walls and the Jagger).
4. **Combine.** The dropped lure wakes the Stone Jagger; it walks toward it but the east belt
   carries it back (it struggles). The flip plate turns the lane west: the belt ferries the
   Jagger onto the weight plate W, where it settles. W held down (Jagger, or the hero standing on
   it) opens the gate. The bars never close on the hero.
5. **Choice.** One Heart key, two Heart doors in the antechamber: west = closet with the Moon key
   (the Moon door up in the entry hall pays a 5-coin reward, once per room build, never after the
   solve); east = vault with the goal. Through the windows both rooms are visible before choosing.
   The vault is the only goal, the closet is optional treasure; Pack reset returns the Heart.

## No softlocks / reset / undo
- Pack **RESET ROOM**, the **entrance reset plate**, and **walking out** of the pocket all restore
  the entry state: keys back on their pedestals, held keys cleared, doors relocked, lure on its
  pedestal, belt east, gate shut, Jagger home. Pack and plate warp the hero to the entry hall
  first (never sealed behind a door), HP kept. The Moon coin never pays twice.
- Pack RESET works while pinned (on the belt against the Jagger) or boxed in.
- The Jagger is fenced to the lane rows 11–12 (it cannot reach the entrance, reset plate or
  ferry hall). Its touch shoves the hero back to the last safe spot, never damage; shots are
  absorbed. Belt tiles are walkable, so a flip under any body is always safe.
- Ordinary enemies are kept out (movement keep-out + eviction every 8 frames, and on the first
  pocket tick for spawns placed after the prepare pass).
- Every hero can solve it: everything is stepped or chosen in the Pack; nothing needs a shot.

## Deviations from the spec text
1. **Toxic Mire placement** (the spec gives no dungeon for M4).
2. **Cap tested, not staged:** with one key of each type on the floor, a second key of a held type
   never appears in play. The cap is enforced (refuse, stays on the pedestal) and the test proves
   it by poking a held Star.
3. **Held keys show as HUD pips above the hero**, not as a bow row inside the Pack screen. The Pack
   carries TOOL LURE / TOOL RESET ROOM.
4. **One symmetric door tile** (borrowed id 37) for all three types, with the type shown by an OBJ
   plaque (the key's bow icon, in the type's palette) on the door, visible before the key is held.
   Shapes read in monochrome (heart, six-point star, crescent).
5. **The flip uses M2's region painter pattern, not the M2 rewrite table code** (own 7-region table:
   lane, gate, four doors, W). Glyph (mirrored arrow), preview strip, SFX and blink as specified.
6. **Harmless Jagger:** M1's Jagger costs a heart on contact; here it only shoves (a ferry body).
7. **After the solve, a reset or walking out relocks the doors** (no spare per-dungeon bit to
   remember which Heart door was chosen). Nothing behind them is needed once solved.
8. **Coin caveat:** the Moon coin is once per room build before the solve; re-entering the room
   rebuilds it, so a player can earn 5 coins again only by re-doing the ferry and closet. Accepted.
9. Borrowed BG ids: 105/106 belts, 107/96 weight plate up/down (walkable), 37 door, 99 bars
   (solid). Their art is overridden while the pocket is live; the test asserts none appears
   elsewhere in the room.
10. Art via GPT Image 2 (gpt-image-2.6-sunburst) quantised by `scripts/gen_lock_art.py`
    (belt, door, weight plate, flip glyph, lure, Heart/Star/Moon bows, key shaft); M1's Jagger and
    plate grids and M3's bars are reused.

## Budgets
- Code split across cold banks: `lock_room.c` (bank 27, rules), `lock_room_view.c` (bank 23,
  setup + painting), `lock_room_draw.c` (bank 31, OBJ list, Pack line, guards); art in bank 24
  (`lock_art.c`). The hot `enemy_new_draw.c` only loops over a prebuilt OBJ list. Banks 8, 26 untouched.

## Test
`scripts/test_lock_room.py` (add to ci.yml; the bot token lacks `workflow` scope).
