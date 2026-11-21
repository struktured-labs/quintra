# M2 Cairn Ford — implementation addendum (2026-11-21)

Companion to `2026-11-19-ultima-puzzle-depth.md` (PR #149), milestone **M2: rewrite switches**.
Stacked on PR #150 (`feat/m1-rime-jagger`): it reuses that branch's pocket-cell picker,
Pack RESET ROOM entry, entrance-plate reset and enemy keep-out guard, generalised here.

## Placement
- **Ember Depths** (stage 2, `bosses_beaten == 2`), one optional pocket per floor, in the same
  cell M1 uses on Verdant Hollow (`rime_pick_cell`, which now accepts stage 1 or 2). One new
  verb per dungeon: Verdant = freeze/hazard timing (M1), Ember = material rewrite (M2).
  M5 Conduit placement stays open (Frost Vault or deeper in Ember).
- 12x20 tile pocket at world x18–29, y11–30 of a wide room; west-wall entrance (local rows 6–7)
  with a corridor carved west to the central trail (x11). Never on the critical path.
- **Self-contained** per the §4 decision: all state is WRAM (`rw_a`, `rw_b`), reset on every
  room entry; nothing persists across rooms or floors except the shared per-dungeon
  "pocket solved" bit (bit 5 of `dungeon_puzzles`, reset per dungeon), which only suppresses a second reward.

## Rules as built
- **Switch A** (round glyph, arrow-up / arrow-down two-state): bed ⇄ **cairn** (solid rock) on all
  three regions. Two plates carry the same glyph and the same meaning: foyer and alcove twin.
- **Switch B** (square glyph, rock / wave two-state): **cairn ⇄ ford** (walkable water bridge).
  Dud with a refusal SFX until A has raised rock; A refuses while fords are down.
- A change that would make the hero's own tiles solid is refused (never entombed).
- Regions: F1 sill mouth to the alcove (walkable bed), C1 chasm to the hall, C2 chasm to the vault.
- **Preview before first use**: a static cairn and a static ford sit in the foyer from the start.
- **Off-camera changes**: one `SFX_DISTRICT` cue per press; each off-camera region keeps a pending
  blink and flashes (door palette, 16 frames) when it scrolls into view.
- **Palette = passability**: ford and sill use the floor ramp, cairn and chasm the wall ramp. The stage
  crystal ramp reads as lava in Ember and the amber ramp means "secret", so neither is used;
  BG slots 5–7 are HUD lanes, so no private slot is claimed.
- **Intended solve**: walk through the sill mouth into the alcove, step the twin A (seals F1 behind you,
  raises C1/C2), step B (all cairns become fords), cross C1 to the hall and C2 to the vault, stand on the goal.
  Stepping A from the foyer seals the empty alcove; stepping it again undoes it.
- **No softlocks**: B is only reachable inside the alcove, and the alcove always holds B and the twin A, so every
  sealed state can be undone from where the hero stands. The hall and vault cannot change state while you are in them.
  Pack RESET ROOM (always offered while the pocket is live) and the foyer reset plate both warp to the entrance
  and clear A/B. HP is never refunded.
- Plates also take a player projectile centred on them (ranged classes can press the foyer A from range).

## Deviations from the spec text
1. **Ford is walkable water** (the user's "rock to water bridge"), not the spec's dry catwalk line.
2. **Ember Depths** placement (spec left the dungeon open).
3. **Reused BG tile ids** (Riftwild-only ids 98/109/110/39 cairn, 107 ford, 108 chasm, 105 sill) whose VRAM art
   is overridden while the pocket is live. The pocket re-dresses on every dungeon BG reload (`tiles_bg_epoch`).
   Picsean water rides only use ids 97/101.
4. **Twin plate instead of a shot puzzle**: the first draft required shooting A through the sill from the alcove.
   Wolfkin has no travelling shot, so the solve is class-agnostic. Shots still press plates as a bonus.
5. Art via GPT Image 2 (gpt-image-2.6-sunburst), quantised by `scripts/gen_rewrite_art.py`.

## Budgets
- Code + art: bank 26 (`rewrite_room.c`, `rewrite_art.c`). Bank 30 holds M1 only.
- Integration edits (bank 8 `dungeon_tools.c`) are smaller than M1's (generic `puzzle_pack_*` dispatch).

## Test
`scripts/test_rewrite_room.py` (not yet in ci.yml: the bot token lacks `workflow` scope).
