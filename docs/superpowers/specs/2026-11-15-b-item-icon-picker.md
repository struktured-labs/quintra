# B-item icon picker

Status: **spec only.** Issue #71. Carmelo could not discover how to equip
the Hookshot. This document proposes a Zelda-style icon picker and an
always-visible equipped-B HUD box. No gameplay code in this change; wait
for his approval before implementing.

## Current behavior

START opens the Pack. SELECT goes to the Aim page. Up and Down both call
`secondary_cycle()` in `hookshot.c`, which walks owned secondaries
*forward only* and falls back to the class power (`10 + class_id`). The
Aim page itself is `inventory_aim_enter()`: a text list, no frames, no
sprites (`HIDE_SPRITES`). The selected name is prefixed with `> ` and a
one-line tip such as `LATCH + PULL SELF`.

Three things hide the Hookshot in particular:

1. `grant_special_item()` puts the tool in `player.inventory` but does not
   change `player.active_item`. B stays the class power until the player
   finds this page and cycles to it.
2. The first-pickup HUD notice is the four-letter word `HOOK` for 45
   frames. It does not say how to equip the tool. There is no dialog, unlike
   Waygear or the Rift Sigil.
3. `font_min` has no `/`, `:`, `>`, or `+`. The live Aim page therefore
   renders `AIM  B WEAPON`, `UP DOWN  B WEAPON`, and `LATCH  PULL SELF`.
   The screenshot in `docs/previews/pr-b-picker/current-aim.png` is a
   headless PyBoy capture of main (`78eb8fd8`) with Hookshot already
   selected.

The Pack already draws an 8x8 OBJ icon next to the B name
(`inventory_prepare_sprites`). The Aim page is the one that does not.

`secondary_cycle()` order is class power, then Boomerang (45), Hookshot
(46), Morningstar (47), Bomb Bag (48).

## Proposal

Replace the Aim page's text cycle with a framed icon grid. Keep the page
in the same Pack SELECT chain (page 4). Cursor movement equips immediately,
the same as today's Up/Down cycle. A still toggles hold-aim vs classic.
START or B returns to play. SELECT continues to Gear.

### Layout (20 columns, 18 rows)

Reuse the Pack's carved frame tiles (`INV_FRAME_*` at `0xF6..0xFE`) and
the four Pack BG palettes (body, gold, magic, quest).

- Row 0: gold title ` B ITEMS ` in the top rail, Pack-style.
- Row 2: `PICK YOUR B ITEM`.
- Rows 4–6: five 3×3 wells (frame + centered 8x8 icon). Cols 2–16, one
  well per B item in this order: class power, Boomerang, Hookshot,
  Morningstar, Bomb Bag. The selected well uses the gold palette; owned
  unselected wells use the magic palette. Unowned wells are empty frames
  in the dim body palette so the player can see that more B items exist.
- Rows 8–10: gold name, green one-line use hint, and `B FIRES THIS ITEM`.
- Rows 12–14: aim-mode help, visually secondary. `MODE: HOLD AIM` (or
  `MODE: CLASSIC`), `A SWITCHES MODE`, `LEFT RIGHT TO PICK`. Up and Down
  are aliases for Left and Right so today's muscle memory still works.
- Row 16: `SEL GEAR  B PLAY`.

Tips must fit 18 columns and stay inside the side rails. `font_min` has
spaces, digits, and A–Z only; do not use `/`, `:`, `>`, or `+` until those
glyphs exist. The official Hookshot tip becomes `LATCH AND PULL` on this
page (the mechanic is unchanged).

Class-power icons stay the ones the Pack already uses: Swift Fang, Ward
Charm, Hunter Eye, Mana Gem, Thorn. Tool icons are `SPR_ITEM_BOOMERANG`,
`SPR_WAYGEAR_HOOK`, a new `SPR_ITEM_MORNINGSTAR`, and `SPR_ITEM_RIFT_BOMB`.

### HUD equipped-B box

Recommended: grow the window to two rows (`WY = 128`) and put a 16×16
gold-framed box in cols 10–11, replacing the room-depth digits. The 8x8
item tile sits centered in the frame. Hearts, MP, Will, and coins stay on
the bottom row. Room depth remains on the Pack. Costs the bottom 8 px of
playfield.

Notices already overwrite cols 10–15 for 45 frames; they will cover the B
box the same way they cover depth today, then the box returns.

Alternative, if the playfield cannot shrink: keep `WY = 136` and put a
gold `B` letter plus the 8x8 icon in the same two depth columns. It is
readable as "something is equipped" but the Hookshot tile is almost lost
at 8 px. Both mockups are in `docs/previews/pr-b-picker/`.

Upload the active icon into one reserved window tile (or park one OBJ
sprite on the window) whenever `player.active_item` changes.

### First-pickup notice

Replace the four-letter `HOOK` flash with a three-line dialog, in the same
style as Waygear and the Rift Sigil:

```
HOOKSHOT CLAIMED
START OPENS PACK
SEL PICKS THE B
```

Boomerang, Morningstar, and Bomb Bag get the same page with their own
names (`BOMB BAG CLAIMED`, and so on). 18 characters or fewer per line, no
punctuation `font_min` lacks.

Do not auto-equip the new tool. B stays the class power until the player
moves the picker cursor onto the icon. This is a design question; see
below.

## Input

- Left / Right: move the cursor across *owned* wells, wrapping. Equip on
  move (`player.active_item =` that item). Play `SFX_TICK`.
- Up / Down: same as Left / Right, so the old Aim-page habit still works.
  Unlike today, Down also moves backward.
- A: toggle `player_penta_aim`, redraw, `SFX_TICK`. Unchanged.
- START or B: resume the room.
- SELECT: Gear page, unchanged.
- Unowned wells are not selectable.

`secondary_cycle()` becomes a bidirectional owned-item walk used by the
picker, or is replaced by a small cursor index on this page. In-room B
still fires `player.active_item` through `secondary_fire()`.

## Palettes and tiles

Measured against a cold link of `78eb8fd8`:

```
[layout] OK: home ends 0x3F7C, banks 0-16;
bank 1 free 297, bank 8 free 604, bank 14 free 1579, bank 16 free 921
```

- Code stays in bank 14 (`inventory.c`, `hud_notice.c`, 1579 bytes free).
  HUD window changes stay in bank 8 (604 bytes free). Do not add code to
  bank 1 (297 bytes free, tightest). New gameplay files, if any, use
  `#pragma bank 255` + `BANKED`.
- BG palettes on this screen: reuse Pack slots 0–3. Gold cursor = slot 1,
  unselected wells = slot 2, name = slot 1, tip = slot 3. No new palette.
- OBJ palettes: the five icons use the Pack's existing gold (slot 2) and
  magic (slot 3) item palettes. Five icon sprites, OAM otherwise cleared.
  Optional cursor sprites are unnecessary if the well frames are BG.
- Tiles: 9 Pack frame tiles, `font_min`, and the existing item OBJ tiles.
  One new tile is required: Morningstar. Today's code uses bare slot 237
  (`inventory_visual.c`, `secondary_heavy.c`, `shop.c`), which sits inside
  `SPR_CLASS_ASCENDED_STEP_BASE` (232–241) and has no art of its own. Give
  it a named `SPR_ITEM_MORNINGSTAR` in a free OBJ slot and load it from
  `tiles_load_item_sprites()`. The preview uses a proposed 8x8 spiked-ball
  tile in that style; it is the only non-shipped tile in the mockup.
- HUD: one reserved window tile (or one window-layer OBJ) for the active
  B icon, plus the Pack frame tiles or a 1 px gold box for the 16×16 well.
- `SPR_WAYGEAR_HOOK` is the real Hookshot tile. At 8x8 it reads like a
  question mark, both on the live Pack and in the mockup. A clearer hook
  is a follow-up art pass, not a picker requirement.

## Headless test plan

Extend or add a PyBoy test next to `scripts/test_inventory_action_tip.py`
and `scripts/test_secondary_weapons.py`. Use poked inventory, not a full
merchant run, for the picker walk. Suggested cases:

1. Boot Wolfkin, open Pack, SELECT, assert the five wells, the gold cursor
   on the class power, and the Howl name plus tip.
2. Grant Hookshot only. Cursor Right from the class power lands on the
   Hookshot well (skips empty Boomerang), `player.active_item == 46`, and
   the name/tip are `HOOKSHOT` / `LATCH AND PULL`. A second Right wraps to
   the class power, not into an unowned well.
3. Grant all four tools. Left/Right and Up/Down walk the five owned items
   in both directions and wrap.
4. A still flips `player_penta_aim` and does not change `active_item`.
   START / B resume the room; SELECT reaches Gear.
5. Return to play with Hookshot equipped, press B, assert a hookshot
   projectile (`PROJ_AUX_HOOKSHOT`) fires. This reuses the existing
   `test_secondary_weapons` hook-wall check.
6. First pickup: grant Hookshot through the shop/pickup path, assert the
   three-line dialog (not a 4-letter `HOOK` notice) and that
   `player.active_item` is still the class power.
7. HUD: with Hookshot equipped, the window is at `WY == 128` (or 136 for
   the 1-row alternative) and cols 10–11 show the hook tile. After a
   notice expires, the box is restored.
8. Screenshot anchors: picker with Hookshot selected, and a room shot of
   the equipped-B box, compared to `docs/previews/pr-b-picker/`.

## Non-goals

No combat or hookshot physics changes. No itch or MiSTer deploy. No
manual update until the page is implemented. No font-wide glyph pass
beyond this screen avoiding missing punctuation, unless that is approved
with the picker.

## Design questions for Carmelo

1. HUD: 2-row window with a 16×16 framed B box (recommended, loses 8 px of
   playfield) or the 1-row alternative that keeps `WY = 136`?
2. First pickup: leave the class power equipped and teach with the dialog,
   or auto-equip the new tool?
3. Keep the aim-mode toggle on the bottom of this page (as mocked), or
   split it off?
4. Always show five wells with empty frames for unowned tools, or only
   show owned items?
5. Redraw the Hookshot 8x8? The current `SPR_WAYGEAR_HOOK` tile looks like
   a `?`, which is why the selected well and the HUD box show a question
   mark.

## Previews

Headless captures and composed mockups, all native 160×144 and 4×
nearest-neighbor, built from the live ROM plus the Pack's real frame,
font, and item tiles:

- `docs/previews/pr-b-picker/current-aim.png` — live Aim page
- `docs/previews/pr-b-picker/proposed-picker.png` — icon picker, Hookshot selected
- `docs/previews/pr-b-picker/current-hud.png` — live HUD, no B box
- `docs/previews/pr-b-picker/proposed-hud.png` — 2-row HUD with 16×16 B box
- `docs/previews/pr-b-picker/proposed-hud-1row.png` — 1-row alternative
- `docs/previews/pr-b-picker/combined-comparison.png` — before/after sheet
