#!/usr/bin/env python3
"""Live-ROM invariant: final terrain never embeds a generated monster."""

from quintra_topology import dungeon_size
from test_pickup_reachability import world_tiles
from test_stage_archetypes import EN, generated_room


ENTITY_SIZE = 28
ENT_ENEMY = 2
EF_ACTIVE = 0x01
WALKABLE = {1, 3, 7, *range(9, 21), 23, 31, 33, 34,
            *range(55, 64)}
FULL_BODY_SOLID = {21, 25, 28, 29, 30}


def i16(pb, where):
    value = pb.memory[where] | pb.memory[where + 1] << 8
    return value - 0x10000 if value & 0x8000 else value


def terrain_clear(tiles, x, y):
    width, height = len(tiles[0]), len(tiles)
    if x < 0 or y < 0 or x > width * 8 - 16 or y > height * 8 - 16:
        return False

    def tile(px, py):
        return tiles[py // 8][px // 8] & 0x7F

    feet = ((x + 2, y + 8), (x + 8, y + 8), (x + 13, y + 8),
            (x + 2, y + 15), (x + 8, y + 15), (x + 13, y + 15))
    body = ((x + 2, y), (x + 8, y), (x + 13, y),
            (x + 2, y + 7), (x + 8, y + 7), (x + 13, y + 7))
    return (all(tile(px, py) in WALKABLE for px, py in feet)
            and all(tile(px, py) not in FULL_BODY_SOLID for px, py in body))


def flutterbat_clear(tiles, x, y):
    """Mirror the bat's intentional square-corner flight collision contract."""
    width, height = len(tiles[0]), len(tiles)
    if x < 0 or y < 0 or x > width * 8 - 16 or y > height * 8 - 16:
        return False

    def tile(px, py):
        return tiles[py // 8][px // 8] & 0x7F

    corners = ((x + 1, y + 1), (x + 14, y + 1),
               (x + 1, y + 14), (x + 14, y + 14))
    return all(tile(px, py) in WALKABLE for px, py in corners)


def enemy_clear(tiles, x, y, enemy_id, hitbox):
    """Mirror the live navigation envelope after the room settles."""
    if enemy_id == 12:
        return flutterbat_clear(tiles, x, y)
    if enemy_id in {0, 2, 3, 13, 32} or enemy_id >= 33:
        return terrain_clear(tiles, x, y)

    width, height = len(tiles[0]), len(tiles)
    ext_x = 14 if hitbox >> 4 >= 10 else 6
    ext_y = 14 if hitbox & 0x0F >= 10 else 6
    if (x < 8 or y < 8 or x + ext_x >= width * 8
            or y + ext_y >= height * 8):
        return False

    def tile(px, py):
        return tiles[py // 8][px // 8] & 0x7F

    return all(tile(px, py) in WALKABLE for px, py in (
        (x + 1, y + 1), (x + ext_x, y + 1),
        (x + 1, y + ext_y), (x + ext_x, y + ext_y)))


def main():
    checked = 0
    fields = 0

    def inspect(label):
        def probe(pb, _compact):
            nonlocal checked, fields
            fields += 1
            tiles = world_tiles(pb)
            for slot in range(32):
                base = EN + slot * ENTITY_SIZE
                if (pb.memory[base] != ENT_ENEMY
                        or not pb.memory[base + 1] & EF_ACTIVE):
                    continue
                x, y = i16(pb, base + 3), i16(pb, base + 7)
                enemy_id = pb.memory[base + 17]
                clear = enemy_clear(
                    tiles, x, y, enemy_id, pb.memory[base + 26])
                corner_tiles = ()
                if (0 <= x <= len(tiles[0]) * 8 - 16
                        and 0 <= y <= len(tiles) * 8 - 16):
                    corner_tiles = tuple(
                        tiles[py // 8][px // 8] & 0x7F
                        for px, py in ((x + 1, y + 1), (x + 14, y + 1),
                                       (x + 1, y + 14), (x + 14, y + 14)))
                assert clear, (
                    f"{label}: enemy {enemy_id} slot {slot} embedded at "
                    f"{(x, y)} corners={corner_tiles}")
                checked += 1
        return probe

    seed = 0x51A7B10C
    for stage in range(9):
        # The final two graph cells are the authored sanctuary and Colossus,
        # not generated monster fields; the live boss gate also correctly
        # refuses this synthetic sweep before its required Sigil is earned.
        for local in range(dungeon_size(stage) - 2):
            generated_room(stage, seed, local_room=local,
                           probe=inspect(f"stage {stage + 1} room {local}"))

    assert checked > 1500, f"enemy terrain sweep was unexpectedly sparse: {checked}"
    print(f"[enemy-spawn-terrain] PASS {checked} monsters across "
          f"{fields} generated fields remain clear after final terrain repair")


if __name__ == "__main__":
    main()
