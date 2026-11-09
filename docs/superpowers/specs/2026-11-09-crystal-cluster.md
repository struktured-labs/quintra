# Crystal tiles read as terrain

Status: **implemented.** Issue #23. The level-1 southwest crystal is
shootable scenery, not a pendant pickup.

## Rule

`BGT_CRYSTAL` stays solid until a shot shatters it. Its silhouette is an
asymmetric cluster of spires rising from a wide base, so it does not read
as a necklace on a stand. Collision and `room_break_crystal` are unchanged.
The same tile is used for secret-vault rings.

## Evidence

`scripts/test_crystal_cluster.py` checks the generated tile is not the old
pendant bytes and that a shot still turns the tile into floor.
