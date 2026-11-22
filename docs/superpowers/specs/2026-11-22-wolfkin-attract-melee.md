# Wolfkin attract-mode melee reach

Date: 2026-11-22

## Problem

In attract mode, Wolfkin's melee looks like he is throwing a sword only
half an inch from himself. The range is too short to read as a wielded
blade.

## Cause

PR #158 (feat/wolfkin-longsword, Longblade slash/stab) is not on main.
Attract demos feed recorded joypad bytes through the same room attack path
as live play; they do not use a stale attract-only offset. The live kit
is still Fang Claw: an 8x8 `SPR_FX_SWING` shot that starts ~10 px from
the body center and slides for 6 frames, so the sprite barely clears the
body. That is what the attract demo shows.

## Fix

Stack this branch on #158 so attract (and live play) use the wielded
Longblade: parented segments with no travel, slash 22 px past the body
edge, stab 32 px, distinct sword tiles. Add a headless contract that the
sword sprite itself reaches those distances, in a clean room and during
the Wolfkin attract demo.

No attract-only input bypass. If the recorded demo trace drifts after
the kit change, re-record `demo_wolfkin_crystal` with the same seed.

## Bank

`wolfkin_sword.c` and `wolfkin_sword_art.c` used fixed bank 23 on #158.
Current main has filled that bank; stacking them there left 61 bytes free,
under the 256-byte layout floor. Both files now use `#pragma bank 255`.

