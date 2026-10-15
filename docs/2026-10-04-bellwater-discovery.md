# Bellwater first-visit discovery

Implemented one optional scene in Waking Riftwild region 0, field 0. A flower
trail leads to the Reed Singer and a restorative spring. A lake shrine is
visible across the main path, with a second conversation and a Mana Gem.
The main route and hidden-companion discovery remain unchanged.

The spring shares the existing regional one-use well flag. The island requires
the raft or Picsean's innate swimming; ownership works without equipment changes.
Its Mana Gem has no despawn timer, uses the existing held-up reward ceremony,
and records its claim in unused regional flag bit 0x20. No save-layout change.
Ordinary loot relocation stays intact; this intentionally gated reward restores
its authored island position after construction.

Native candidate: `17da78a800e511631787f326f4ff05ea12c96e9591b735523e34d4f985e874f9`.
`scripts/test_riftwild_discovery.py` checks the first-field encounter, dialogue,
700-frame wait, blocked shore approach, raft crossing, +2 max MP, ceremony,
real east-edge exit/return, cold SRAM resume, and innate swimming. Progression,
shore position, protection, and raft grant are test fixtures, not a full playthrough.
Parent 57321748 fails the encounter gate as expected. An intermediate candidate
failed because ordinary loot safety moved the island reward onto shore; fixed
without weakening safety for other drops.

Also removed Kilnback's residual right-extension mural. Actual VRAM test:
parent 63 mural cells; candidate zero across 1200 frames and menu resume.
All nine boss-defeat art checks pass. Prior performance qualification gaps
remain; this pass makes no hardware performance claim.

Evidence: http://100.120.23.124:8919/bellwater/
Local implementation only: no itch deployment or live hardware reload.
