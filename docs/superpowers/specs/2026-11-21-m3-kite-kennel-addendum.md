# M3 Kite Kennel — implementation addendum (2026-11-21)

Companion to `2026-11-19-ultima-puzzle-depth.md` (PR #149), milestone **M3: tool-beast chain**.
Stacked on PR #152 (`feat/m2-rewrite`, itself on #150). It reuses M2's cairn graphic, rewrite
painter pattern (refuse-if-occupied, one region per frame, off-camera cue + blink, re-dress
on BG reload) and the shared pocket machinery (`rime_pick_cell`, `puzzle_pack_*`, `puzzle_keep_*`).

## Placement
- **Frost Vault** (stage 3, `bosses_beaten == 3`), one optional pocket per floor, in the same
  pocket cell M1/M2 use. One new verb per dungeon: Verdant = freeze (M1), Ember = rewrite (M2),
  Frost = tool-beast (M3). The fire creature melting a frost-crystal lock fits the dungeon.
- 12x18 tiles at world x18–29, y11–28 of a wide room. West-wall entrance at local rows 6–7, with a
  corridor carved to the central trail. Never on the critical path.
- **Self-contained** (§4): WRAM only, rebuilt on entry. The shared per-dungeon pocket bit only stops
  a second reward.

## Chain as built (spawn → transform → route → tool)
- **Kennel** (channel top) holds the **Cinder Kite**: a 16x16 puzzle-owned actor, not an entity.
  Weapons, Bombs and the companion pass through it, so it can never be killed by a hit.
- **Lever L** (round, cage shut/open glyph) opens the kennel **gate** (bars ⇄ rift-stream).
- **Stream plates** (diamond, rock/stream glyph) turn a channel **cairn** segment (M2's graphic and
  meaning) into **rift-stream**, a new graphic that is never hero-walkable.
- **The link (twist, from Gemini's design review):** L and S2 are one switch. The gate opens exactly
  when segment B closes, so the player builds A, releases the Kite, lets it wait on A, then flips S2.
  That shuts the gate behind it and opens B.
- The Kite moves 1 px/frame while the next pixel row is stream. It stops *before* a closed row.
- At the channel end it breathes for 24 frames on the **crystal lock** (2x2, door palette), which
  plugs the vault doorway. The lock becomes floor, and the Kite then flies home through the air,
  shutting the gate.
- **Kite dead:** blocked for 150 frames, it is doused by the Frost Vault cold (it flickers from
  90). 90 frames later it re-forms in the kennel with the gate shut.
- **Refusals:** a press whose region overlaps the Kite's 16x16 box is refused (dud SFX).
- **The lock breaks only to the Kite's breath.** Shots, melee and Bombs do nothing; Bombs only open
  amber cracks.
- **No softlocks:** channel tiles are solid to the hero in every state, so a rewrite can never trap
  the hero. The only doorway the machine controls opens one way until a reset.
  - Pack RESET ROOM and the foyer reset plate warp the hero out *before* re-locking.
  - The Kite only ever exists inside its channel, so it can never rest on the entrance or reset path.
- **Class fairness:** every plate is stepped; nothing needs a shot (Wolfkin has no travelling one).

## Deviations from the spec text
1. **Lure deferred to M4.** The spec allows "M3 or M4". It needs B-slot/drop plumbing and a body that
   paths to it, and M3 has no roaming body. M4's Jagger is the natural first lure target.
2. **No crate**, so the spec's "lock already broken, crate wedged" case becomes "lock already broken":
   re-releasing is clean, the breath is a no-op, and a reset restores the lock.
3. **Kite death is environmental (cold), not by weapon.** The spec wants a dead Kite to respawn and
   the companion never to kill it. Making the Kite immune to every hit and killing it only through the
   cold satisfies both and keeps the companion out of it.
4. **Frost Vault placement** (the spec gives no dungeon for M3).
5. Borrowed solid BG ids: 98/109/110/39 cairn, 99 bars, 108 stream, 37/38 lock with the right column
   X-flipped. Their art is overridden while the pocket is live. The test asserts none of them appears
   elsewhere in the room.
6. Art via GPT Image 2 (gpt-image-2.6-sunburst), quantised by `scripts/gen_kite_art.py`.
   The cairn grid is reused from M2.

## Budgets
- Code in bank 28 (`kite_room.c`), art in bank 31 (`kite_art.c`). Bank 8 is untouched.

## Test
`scripts/test_kite_room.py` (add to ci.yml; the bot token lacks `workflow` scope).
