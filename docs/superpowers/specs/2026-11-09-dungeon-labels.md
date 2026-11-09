# Dungeon arrival signs

Status: **implemented.** Issue #21. `RIFTWILD` stays. Dungeon words no
longer collide on the same row or replace the overworld name.

## Rule

Rift Wild, including its Hollow face, is a standing sign. Entering it clears
any dungeon countdown so that countdown cannot erase the name, and it clears
the remembered district so the next GATE or LOWER card still plays. Town
signs (Village, Market, Forge) are standing signs too. A guard in Rift Wild
does not replace `RIFTWILD`.

In a dungeon, a new depth shows its district name. If that room also has a
directive, the district stays for a short beat and the directive follows.
The same district does not repeat its name; a new directive still does.
Kind 14 is the four-letter `RIFT` return card, not an accidental slice of
`RIFTWILD`.

## Evidence

`scripts/test_riftwild_label.py` forces the overworld sign after a live
district countdown and checks `RIFTWILD` is still there after 130 frames.
