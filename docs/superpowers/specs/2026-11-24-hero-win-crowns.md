# Hero-select win crowns

Status: **implemented.** Requested by struktured (#243, clarified in
t708u): a hero who has won the campaign wears a small crown on their
head on `CLASS_SELECT` in later playthroughs, with a visible win count.
The crown is more majestic if that hero's best win was on Normal rather
than Easy.

## Player-facing

On `CHOOSE YOUR HERO`, each of the five champions with at least one true
ninth-Colossus victory shows a 1–3 digit count at column 12 of their name
row. Heroes with zero wins are unchanged: no count and no crown. The name
list, live 16x16 preview, gold-star cursor, kit typography, and Easy/Normal
prompts are not moved or restyled.

When the cursor highlights a champion who has won, an 8x8 crown sprite
sits on that hero's preview head, aligned per vessel (ears, crests, and
antennae have different scalp heights). The preview sprites stay in front
of the crown band so tufts and antennae read as worn, not covered. The
preview is currently a still pose; crown placement is tied to the preview
origin so a later idle bob would carry the crown with it. Switching to a
hero with no wins hides the sprite.

The name row does not repeat a second crown — that cluttered the list.
Tier is still readable at a glance: Easy counts use the gold label
palette, Normal+ counts use the royal (gold-and-ruby) palette. The head
crown on the selected hero is the majestic/simple signal up close.

Crown tier is the **best** difficulty that hero has ever won:

- **Easy only** (`CROWN_TIER_EASY`): a simple three-point gold crown.
- **Normal**, and any future harder mode (`CROWN_TIER_NORMAL`): a more
  ornate jeweled crown (gold metal plus a ruby).

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
reference, quantized to native 8x8 4-color GBC tiles. They load into OBJ
VRAM at `SPR_CROWN_EASY` / `SPR_CROWN_NORMAL` (20 and 21; those indices
are the room enemy/boss atlas, overwritten only on this screen). The
head crown is sprite 5, leaving preview sprites 0–3 and the cursor star
at 4, and staying within the 10-sprite line budget (at most the cursor,
two preview tiles, and the crown share a scanline, and only when
Vespine is highlighted). OBJ palettes 3 (gold) and 4 (royal) are used
for the two tiers; color 0 is transparent. Preview sprites keep priority
over the crown so hair and antennae stay in front. Banks 3/4/15 stay
above the 256-byte emergency floor; the helper remains in bank 27.

## Acceptance

- Fresh cart: no counts, no head crown.
- A win as hero A shows `1` on A's name row; highlighting A places that
  hero's crown on the preview head; other heroes stay bare. A second win
  as A shows `2`.
- A win as B is counted only on B.
- Easy-only wins use the simple gold crown and a gold count; a Normal
  win upgrades that hero's crown and paints the count royal.
- Old meta SRAM still loads; per-hero counts start at zero there.
- `scripts/test_hero_win_crowns.py` covers recording, tiers, the head
  sprite, name-row counts, and save compatibility.
  `scripts/test_new_game_start.py` (including Continue) stays green.
