# Earned Spirit Compass map

Date: 2026-11-12

## Decision
The SELECT / Spirit Compass dungeon map was too revealing: from the first
press it drew the whole 6x5 footprint as dim ghost rooms, faint corridors,
and the optional cache. The full map must be earned.

## Behavior
- Unvisited rooms and their corridors are blank (`BGT_VOID`).
- Drawn: the current room, rooms actually entered (or charted), the one
  earned next GOAL, and the boss node once the sanctuary has been entered.
- The corridor to the boss waits until the boss room is entered.
- The cache (LOOT) node appears only after its room is visited or charted.
- Depth-band numbers appear only for rows with an entered room.
- A corridor appears only after both of its rooms are entered or charted;
  the GOAL marker does not reveal the path to it.
- A Cartographer's Chart (`WARE_CHART`) bought in a dungeon already sets
  every `dungeon_seen` bit, so it fills in the full current layout. Town
  charts queue the same reveal for the next dungeon; fog resets per stage.

## Scope
Only `draw_dungeon_grid` changes. Town and Riftwild maps are unchanged.
Ported from the map half of unmerged commit ebfd6cce
(`feat/dungeon-variety`); that branch's route-variety, skull-door, and
procgen changes are deliberately not included.
