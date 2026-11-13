# Merchant counter reach

Date: 2026-11-12. Status: **implemented.**

## Problem
Carmelo: having to walk around the merchandise to talk to the merchant is
annoying. In a normal shop you talk across the aisle, desk, or booth.

Every shopkeeper stands behind its own shelf: the dungeon merchant (80,40)
over wares at y=64, the town merchant (80,40) over wares at y=72, the
village smith (40,48) over the forge at (40,80), the rune tender (120,96)
under its shelves at y=64, and the chartwright (48,64) over the chart at
(48,96). The ordinary talk box is 20px (see `2026-11-09-dialogue-radius.md`),
so the far side of the ware row (dy 40-48) was out of reach.

## Rule
- Counter keepers are the merchant, smith, rune tender (apothecary), and
  chartwright. Every other resident and wayfarer keeps the 20px box.
- A counter keeper also answers A from up to 56px away vertically and 24px
  sideways, but only when the player faces it vertically (north when it is
  above, south when it is below). Facing away or sideways at that range
  attacks. Beyond 56px, A attacks.
- Inside the 20px box nothing changes: 14px talks from any facing, 14-20px
  must not face away.
- Standing at a ware (within 12px of a shelf) never talks. A stays with the
  shelf, so walking into a ware still buys it, and an unaffordable ware
  still refuses instead of opening a conversation.
- The nearest speaker still wins. The merchant's overhead coin cue keeps
  its 20px box.

## Evidence
`scripts/test_merchant_counter.py`: in the dungeon merchant room and the
town market, A from the far side of the ware row (dy 40 / 48) facing the
merchant opens the merchant dialogue, also 16px off-center; facing away or
east attacks; 24px farther down the room attacks; standing on a ware with no
coins does not talk and keeps the ware; with coins the ware is bought. The
smith answers across the forge, the rune tender from the north side of its
shelf, and facing away from either attacks. The test fails on 7b1b1438.
