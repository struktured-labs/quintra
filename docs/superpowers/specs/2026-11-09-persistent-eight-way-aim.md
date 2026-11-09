# Persistent eight-way aim

Status: **implemented.** Owner request (issue #26). Hold Aim is the default
and matches the requested Penta-style rule. Classic stays the vertical-cardinal
fallback. No SRAM layout change.

## Rule

Directional input sets an 8-way aim (`player_aim_dir`, dir8 index 0 = north
through 7 = northwest). Releasing the D-pad stops movement and leaves that aim
in place, diagonals included. An attack with no direction held — A, B, Oath,
Will MAX — fires along `player_aim_dir` until a new direction replaces it.

Hold Up+Right, release, then press attack: the shot goes northeast, not north
or east. A later single direction, for example Down, replaces the aim; after
that release a stationary shot goes south.

`room_input_dir8` still prefers the live D-pad. The retained aim is the no-key
fallback, and only while Hold Aim is selected (`player_penta_aim`, default 1).
Classic mode keeps the old fallback: the cardinal `player.facing` byte, which
vertical input overwrites.

## What does not move

- The cardinal facing byte. An A-only diagonal that still includes the previous
  heading does not replace it. Shots do not read that byte in Hold Aim.
- Suspend save, player struct offsets, and room-entry facing (still south).
  A new champion resets aim to south (dir 4). Aim is session state, not save
  state, so it also survives an ordinary room change until the next direction.

## Evidence

`scripts/test_persistent_aim.py` boots a real cart, holds each of the eight
directions, releases, and checks the stationary projectile. It also checks
hold-up-right, a second shot with no new input, then a Down replacement.
