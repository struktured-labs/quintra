# Quintra World Cadence and Lore Contract

## Core promise

Quintra is a procedural action adventure, not a sequence of anonymous combat
boxes. Its world should feel like the first Zelda: dangerous spaces invite
wandering, routes loop and reconnect, landmarks create memory, and knowledge
from failed runs makes the next expedition smarter.

## World rhythm

- One dungeon is six major rooms ending in a champion-scale boss.
- Three dungeons form a region.
- A procedural town follows each region (rooms 19, 37, 55...).
- Towns fully restore HP/MP, offer a market, and act as emotional punctuation.
- Most rooms, routes, puzzles, towns, and encounters derive from the run seed.
- Lore fixtures occupy deterministic landmark slots, but the run interprets
  them. Symbols and dramatic roles persist; names, order, location, witnesses,
  local geometry, and sometimes the truth of an account are seed-fuzzy.

The next world-generation milestone replaces the one-dimensional room counter
with a compact region graph: a 4x4 screen overworld containing a town, dungeon
entrances, secrets, loops, and one locked story landmark. The existing counter
remains the stable seed/index and save migration bridge until that graph ships.

## Founding myth

When the world split open, five champion spirits accepted one shared charge:
carry the five living sparks into the world below, bind the devouring Rift,
and rekindle dawn before every road and name is forgotten.

- Wolfkin — Fang of Flame: courage and direct action.
- Sauran — Scale of Stone: endurance and guardianship.
- Corvin — Wing of Shadow: truth, foresight, and forbidden paths.
- Picsean — Fin of Tide: memory, change, and restoration.
- Vespine — Sting of Bloom: sacrifice, decay, and renewal.

The player chooses the vessel, not the only hero. The other four spirits still
exist in the world and can become rivals, rescuers, ghosts, or lore anchors.

## Procedural versus authored

Procedural by default: routes, room geometry, enemy ecology, treasure, shops,
ordinary towns, puzzles, and optional secrets.

Lore fixtures: variations of the opening myth, five spirit revelations,
regional town identities, competing causes of the Rift, and the final choice.
Fixtures specify a symbolic role and generation constraints, never an entire
map. No run is required to present every fixture, or present it the same way.
