# Prism Toggle chamber guards

Date: 2026-11-17. Status: **implemented.**

## Problem

Carmelo (2026-11-17): "the puzzle where you have to hit a switch twice
to get to center, more monsters in that room I think, with a monster
inside the walls of the puzzle to add some flavor to it."

That room is the Prism Toggle chamber (Oracle / Link's Awakening
crystal-switch): the hero must strike a prism orb at least twice, then
step on the gold seal in the walled center pocket. It can appear as the
Trial or Waystone in Stages 1–2, and as the Waystone in Stages 3–6.

Procgen spawned the ordinary puzzle-room guard pack (Easy 3 / Normal 4,
plus one from Stage 4) *before* the chamber was carved over the compact
20×17 court. `prism_prepare` then cleared any body whose tile landed
inside the 12×11 fixture, often by zeroing `flags` without
`entity_kill`. Most of the intended pack disappeared, and the center
stayed empty.

## Behavior

- After the chamber is laid, accidental bodies inside it are removed
  with `entity_kill`. One grounded, stage-native melee inmate
  (Crawler, Skeleton, Orc, Rope, Shard Crab, Bog Toad, or Echo Guard;
  otherwise a Blue Crawler) is spawned on a 2×2 of non-seal floor in
  the goal pocket, or on the non-seal floor tile farthest from the
  gold plate in tight Stage 5+ chambers that only have an 8px apron.
- While the room is still locked the inmate is held on that stand so
  it cannot walk onto the gold plate or out a lowered gate. After the
  seal opens, the pen is released and the inmate is an ordinary fight
  in the open chamber.
- The open ring is topped up to Easy 4 / Normal 5, plus one more from
  Stage 4 (`bosses_beaten >= 3`). The inmate is extra and does not
  count against that band. Ring anchors stay off the fixture, the
  arrival door, and existing bodies.
- Visuals, orb strikes, barrier colours, and the gold-seal reward are
  unchanged. Puzzle rooms still do not combat-seal, so the inmate
  cannot lock the doors or the solve.
- Contact and shots already stop on walls and raised pillars. The
  inmate is melee-only so it cannot chip the hero through a closed
  wall. `test_performance` is the existing double-speed OAM/loop
  fence; this pack is much smaller than that dense-room budget.

## Tests

`scripts/test_prism_toggle.py` still checks Rust tile parity, melee
flips, and seal persistence on Stages 1/2/3/6, and now also asserts
the ring count, that the inmate stays in the goal pocket for 180
frames while locked, that a hero standing outside a pocket wall takes
no damage, and that teleporting onto the seal still unlocks the room.
