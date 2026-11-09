# Companion greeting beat

Status: **implemented.** Issue #25. The first secret vault is visible,
with the reveal sound and the companion's flash, before the greeting box.

## Rule

Discovering the Road Echo still marks it found and saves that on room
entry. The greeting does not open on the arrival frame. For 36 frames the
champion is held, the vault and the spirit at the crystal ring are on
screen, and the secret-revealed sound plays. Then the greeting dialogue
opens. A later secret does not greet again. The vault loot timer does not
run during the beat.

## Evidence

`scripts/test_companion_greeting.py` opens a first secret. The room stays
up with the companion present, then the dialogue opens.
