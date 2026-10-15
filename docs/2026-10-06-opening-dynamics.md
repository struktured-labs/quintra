# Opening dynamics pass

ROM: `0d1f3d3cf4ec25a1452b7b1bea981ee215cb6e00e157a8a564052ab53abc7c2d`.
Parent `a51e7e78` archived with symbols in `builds/dynamic-parent-a51e7e78`.

Normal level-1 WAVE encounters now begin a 36-update warning when two or fewer
enemies remain, then add their existing three reinforcements. Population across
the whole encounter, enemy HP, damage and loot rates are unchanged. New enemies
retain the existing 40-pixel exclusion around the hero. Easy keeps its previous
clear-first behavior. First three local rooms are excluded by existing director
eligibility, as are puzzles, services, bosses and Riftwild.

One seeded signature out of eight eligible level-1 courts now has a small
corner discovery. After enemies are cleared, approaching an outer corner gives
intermittent sparkle cues; investigating closely reveals five coins and one MP.
It fires once, resets on generation, and is armed only for an eligible first
visit. This is an optional supply bonus, not a new seal or permanent-stat reward.
It does not guarantee every corner has a prize or every generated corner is
accessible. Regular item placement safety remains authoritative.

`scripts/test_opening_dynamics.py` records the live warning/count sequence:
two enemies remain through the warning, then five are present at sample 36.
It checks spawn distance, final clear, no repeated wave, no center-path reward,
corner supplies, no repeated payout, and unchanged Easy behavior. Fixtures stage
enemy counts and positions; they do not measure human difficulty. Parent fails
both overlap and corner-reward gates. The first corner fixture used an obstructed
position; normal pickup safety relocated rewards. Corrected the fixture to a
walkable nearby position rather than weakening the safety code.

Existing trap/wave/elite/hold director tests, Bellwater discovery/cold resume,
and Riftwild polish tests pass. ROM layout and diff whitespace checks pass.
Native screenshots inspected in `builds/opening-dynamics-0d1f3d3c`; full trace
and source binding are in its `capture.json`. Build/replay completed locally;
no hardware, cross-hero balance or performance qualification is claimed.

Not deployed to SD or itch. Human testing should compare the pressure during
the tail of wave fights and whether corner hints encourage exploration without
making room-clearing feel like a mandatory corner sweep.
