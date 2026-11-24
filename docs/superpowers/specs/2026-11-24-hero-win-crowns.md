# Hero-select win crowns

Status: **implemented.** Requested by struktured (#243): a hero who has won
the campaign shows a small crown and a win count on `CLASS_SELECT` in later
playthroughs. The crown is more majestic if that hero's best win was on
Normal rather than Easy.

## Player-facing

On `CHOOSE YOUR HERO`, each of the five champions with at least one true
ninth-Colossus victory shows an 8x8 crown at column 12 of their name row
and a 1–3 digit count immediately to its right (columns 13+). Heroes with
zero wins are unchanged: no crown and no zero. The name list, live 16x16
preview, gold-star cursor, kit typography, and Easy/Normal prompts are
not moved or restyled.

Crown tier is the **best** difficulty that hero has ever won:

- **Easy only** (`CROWN_TIER_EASY`): a simple three-point gold crown,
  painted with the existing label-gold BG palette.
- **Normal**, and any future harder mode (`CROWN_TIER_NORMAL`): a more
  ornate jeweled crown on a royal palette (gold metal plus a ruby).

Winning Easy after a Normal win does not downgrade the crown. Winning
Normal after Easy upgrades it. The count increments once per campaign
victory for that run's hero and saturates at 255. Hexa Dragmar remains a
badge, not another win. Attract demos record nothing.

## Persistence

Lifetime trophies already live in SRAM bank 1 as a version-2 `QM` record
(best score, runs, wins, best time, flags, checksum at offset 12). This
feature appends a sealed extension; it does not bump the meta version and
does not touch the suspend slot in bank 0:

```
[13]     'C'
[14]     extension version 1
[15..19] hero_wins[5]     (u8, saturate at 255)
[20..21] best tier packed (2 bits per hero: 0 none, 1 Easy, 2 Normal+)
[22]     checksum of bytes [13..21]
```

A missing, truncated, or bad extension reads as all zeros and is not
treated as cart corruption: existing totals, flags, and best time stay.
Historical `sram_meta_wins` are not attributed to a hero. The first
hero-win write, or a fresh `meta_reset`, creates a zeroed extension.
Legacy v2 records (checksum of `[3..10]` at `[11]`) still migrate in
place as before.

## Art and budget

The two crown tiles were drawn from a GPT Image 2 (`gpt-image-2.6-sunburst`)
reference, quantized to native 8x8 4-color GBC tiles. They load at
`BGT_CROWN_EASY` / `BGT_CROWN_NORMAL` (0x70, 0x71), past `font_min`. They
are background tiles, so the five preview/cursor objects and the 10-sprite
line budget are unchanged. BG palette 4 is the royal jeweled slot; the
VBlank attribute and palette commit sequence is otherwise the same as the
class-select restyle.

## Acceptance

- Fresh cart: no crowns.
- A win as hero A shows that hero's crown and `1` on the next hero
  select; other heroes stay bare. A second win as A shows `2`.
- A win as B is counted only on B.
- Easy-only wins use the simple crown; a Normal win upgrades that hero.
- Old meta SRAM still loads; per-hero counts start at zero there.
- `scripts/test_hero_win_crowns.py` covers recording, tiers, and save
  compatibility. `scripts/test_new_game_start.py` (including Continue)
  stays green.
