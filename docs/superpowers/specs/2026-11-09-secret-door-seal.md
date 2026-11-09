# Opened secret doors stay enterable

Status: **implemented.** Owner decision on issue #19: an opened secret
doorway is enterable even while combat or a puzzle seals the ordinary exits,
and it never redraws as closed after the room is cleared. Art and movement
agree for the whole time the mouth is open.

## Rule

Shooting a cracked wall still writes `BGT_DOOR` for the 16px pair and records
`secret_door_x/y` and `secret_door_x2/y2`. Walking onto that pair enters the
vault overlay immediately. Puzzle locks and combat seals still hold every
other forward door.

A compact redraw and a wide-field stream never substitute `BGT_DOOR_LOCKED`
for those two coordinates. When the room later unseals, the same pair is
painted `BGT_DOOR` again so a seal-time redraw cannot leave a portcullis
behind. A new room clears the coordinates before its first paint.

## What does not change

Graph exits, return doors, boss thresholds, and hidden walk tiles keep their
existing seal rules. The vault is still an overlay on the parent cell.

## Evidence

`scripts/test_secret_door_seal.py` opens a cracked wall while a hostile is
alive, redraws the room, walks into the mouth, then clears the room and
redraws again. The tiles stay open doors, and the walk enters the vault.
