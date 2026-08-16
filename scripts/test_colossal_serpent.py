#!/usr/bin/env python3
"""Live-ROM contract for Verdant's articulated Snake boss."""
from pathlib import Path

from test_boss_identity import EN, PL, TM, addr, enter_boss, put16


ROOT = Path(__file__).resolve().parent.parent
BODY_MIN, BODY_MAX = 55, 63
CAMERA_X = addr("_room_camera_x")
TAIL_X = addr("_serpent_tail_x")
TAIL_Y = addr("_serpent_tail_y")
TAIL_COUNT = addr("_serpent_tail_count")
TAIL_VISIBLE = addr("_serpent_tail_visible")
TAIL_ACTIVE = addr("_serpent_tail_active")
HEAD_INDEX = addr("_serpent_head_index")
ENTITY_SIZE = 28
SPR_BOSS_BIG = 40
SPR_SHIELD_AURA = 127
WORLD_W = addr("_room_world_width")
WORLD_H = addr("_room_world_height")


def projected_body_tiles(pb):
    tiles = list(pb.memory[TM:TM + 20 * 17])
    return [(i % 20, i // 20, tile) for i, tile in enumerate(tiles)
            if BODY_MIN <= tile <= BODY_MAX]


def position(pb, entity):
    return (pb.memory[entity + 3] | pb.memory[entity + 4] << 8,
            pb.memory[entity + 7] | pb.memory[entity + 8] << 8)


def tail_points(pb):
    count = pb.memory[TAIL_COUNT]
    return [(pb.memory[TAIL_X + i], pb.memory[TAIL_Y + i])
            for i in range(count)]


def obj_tile_art(tile):
    pb, _ = enter_boss(1, keep_open=True)
    lcdc = pb.memory[0xFF40]
    pb.memory[0xFF40] = lcdc & 0x7F
    pb.memory[0xFF4F] = 0
    art = bytes(pb.memory[0x8000 + tile * 16:0x8000 + (tile + 1) * 16])
    pb.stop(save=False)
    return art


def clear_hostile_projectiles(pb):
    for i in range(32):
        ep = EN + i * ENTITY_SIZE
        if pb.memory[ep] == 1:
            pb.memory[ep] = pb.memory[ep + 1] = 0


def hostile_count(pb):
    return sum(pb.memory[EN + i * ENTITY_SIZE] == 1
               and pb.memory[EN + i * ENTITY_SIZE + 1] & 1
               and not pb.memory[EN + i * ENTITY_SIZE + 1] & 0x10
               for i in range(32))


def main():
    pb, boss = enter_boss(1, keep_open=True)
    assert pb.memory[TAIL_ACTIVE] == 1, "Serpent route body was not activated"
    assert pb.memory[HEAD_INDEX] == (boss - EN) // ENTITY_SIZE, (
        "dedicated head renderer is not bound to the live boss")
    assert pb.memory[boss + 15] == 0 and pb.memory[boss + 21] == 0, (
        "Serpent did not deterministically enter its feeding phase")
    assert not projected_body_tiles(pb), (
        "detached legacy background body still exists at encounter entry")

    # Resolve the four real storm-mote meals. Growth must change only the
    # route-following OBJ length; the background remains ordinary arena art.
    food = ((184, 24), (28, 92), (176, 96), (44, 28))
    lengths = [pb.memory[TAIL_VISIBLE]]
    background_counts = [len(projected_body_tiles(pb))]
    for growth, (food_x, food_y) in enumerate(food):
        pb.memory[PL + 15] = 255
        put16(pb, boss + 3, food_x - 12)
        put16(pb, boss + 7, food_y - 12)
        pb.memory[boss + 15] = 0
        pb.memory[boss + 16] = 1
        pb.memory[boss + 21] = growth
        for _ in range(30):
            pb.tick()
            if pb.memory[boss + 21] == growth + 1:
                break
        assert pb.memory[boss + 21] == growth + 1, (
            f"Serpent ignored storm mote {growth + 1}: "
            f"state={pb.memory[boss + 15]} timer={pb.memory[boss + 16]} "
            f"growth={pb.memory[boss + 21]} pos={position(pb, boss)}")
        lengths.append(pb.memory[TAIL_VISIBLE])
        background_counts.append(len(projected_body_tiles(pb)))
    assert lengths == [2, 5, 8, 11, 14], (
        f"meals did not expose three real tail scales each: {lengths}")
    assert background_counts == [0, 0, 0, 0, 0], (
        f"growth leaked back into detached BG tiles: {background_counts}")

    # Lay a synthetic L-shaped motion trace one legal five-pixel sample at a
    # time. The runtime must preserve that route as a continuous overlapping
    # tail instead of stretching a line between teleports or repainting a map.
    pb.memory[boss + 15] = 1
    pb.memory[boss + 10] = 220
    for x in range(60, 126, 5):
        put16(pb, boss + 3, x)
        put16(pb, boss + 7, 36)
        pb.memory[PL + 15] = 255
        pb.tick(2)
    for y in range(41, 102, 5):
        put16(pb, boss + 3, 125)
        put16(pb, boss + 7, y)
        pb.memory[PL + 15] = 255
        pb.tick(2)
    trail = tail_points(pb)[:15]
    assert len(trail) == 15 and pb.memory[TAIL_VISIBLE] == 14
    for previous, current in zip(trail, trail[1:]):
        gap_x = abs(previous[0] - current[0])
        gap_y = abs(previous[1] - current[1])
        assert 1 <= gap_x + gap_y and gap_x <= 5 and gap_y <= 5, (
            f"tail disconnected at {previous}->{current}")
    assert max(y for _, y in trail) - min(y for _, y in trail) >= 35, (
        f"tail did not retain the head's route: {trail}")

    # The tail is a fair one-damage contact hazard, not just art. It remains
    # passable so curling around the player cannot create a boss-room softlock.
    clear_hostile_projectiles(pb)
    touch_x, touch_y = trail[5]
    put16(pb, PL + 9, touch_x - 8)
    put16(pb, PL + 11, touch_y - 12)
    pb.memory[PL + 2] = 10
    pb.memory[PL + 15] = pb.memory[PL + 20] = 0
    for _ in range(3):
        pb.tick()
        if pb.memory[PL + 2] < 10:
            break
    assert pb.memory[PL + 2] == 9, (
        f"visible tail did not deal its fair contact damage: hp={pb.memory[PL + 2]}")

    # Full length still layers bullet hell over Snake movement. The head fires
    # an aimed three-lane fan while the visible tail tip sheds a mixed-speed
    # counter-pair: five hostile sprites, not stage one's generic full ring.
    clear_hostile_projectiles(pb)
    pb.memory[PL + 15] = 255
    pb.memory[boss + 15] = 1
    pb.memory[boss + 10] = 72
    pb.memory[boss + 11] = 0
    pb.memory[boss + 18] = 0
    pb.memory[boss + 21] = 4
    hostile = 0
    for _ in range(30):
        pb.tick()
        hostile = hostile_count(pb)
        if hostile:
            break
    assert hostile == 5, f"Serpent lost its head+tail bullet hell: {hostile} shots"
    assert any(pb.memory[EN + i * ENTITY_SIZE] == 4
               and pb.memory[EN + i * ENTITY_SIZE + 12] == SPR_SHIELD_AURA
               for i in range(32)), "full growth lost its traveling hollow ring"

    # The fair contact body is smaller than the art, so the dedicated chase
    # clamp must keep the entire 32x24 hood inside the scrolling world.
    put16(pb, boss + 3, 220)
    put16(pb, boss + 7, 110)
    pb.memory[boss + 15] = 1
    pb.memory[boss + 10] = 70
    pb.memory[PL + 15] = 255
    pb.tick(2)
    hood_x, hood_y = position(pb, boss)
    assert hood_x <= pb.memory[WORLD_W] - 32
    assert hood_y <= pb.memory[WORLD_H] - 24

    # Resolve the advertised square blast, then pin visible rear contraction.
    clear_hostile_projectiles(pb)
    put16(pb, boss + 3, 80)
    put16(pb, boss + 7, 48)
    put16(pb, PL + 9, 120)
    put16(pb, PL + 11, 48)
    pb.memory[PL + 2] = 10
    pb.memory[PL + 15] = pb.memory[PL + 20] = 0
    pb.memory[boss + 15] = 1
    pb.memory[boss + 10] = 1
    for _ in range(4):
        pb.tick()
        if pb.memory[boss + 15] == 2:
            break
    assert pb.memory[PL + 2] == 8, (
        f"Serpent AOE did not deal fixed two damage: hp={pb.memory[PL + 2]}")
    before_growth = pb.memory[boss + 21]
    before_length = pb.memory[TAIL_VISIBLE]
    pb.memory[boss + 10] = 1
    for _ in range(4):
        pb.tick()
        if pb.memory[boss + 21] != before_growth:
            break
    assert pb.memory[boss + 21] == before_growth - 1
    assert pb.memory[TAIL_VISIBLE] == before_length - 3, (
        "contraction did not remove three rear scales")

    put16(pb, PL + 9, 200)
    scx = []
    for _ in range(80):
        pb.memory[PL + 15] = 255
        pb.tick()
        scx.append(pb.memory[0xFF43])
    assert pb.memory[CAMERA_X] == 64 and 61 <= scx[-1] <= 67, (
        f"Serpent field did not reach eastern camera: "
        f"camera={pb.memory[CAMERA_X]} SCX={scx[-1]}")

    screenshot = ROOT / "tmp" / "serpent-articulated-arena.png"
    pb.screen.image.save(screenshot)
    pb.stop(save=False)

    segment_a = obj_tile_art(SPR_BOSS_BIG + 12)
    segment_b = obj_tile_art(SPR_BOSS_BIG + 13)
    assert segment_a != bytes(16) and segment_b != bytes(16)
    assert segment_a != segment_b, "tail scale animation frames are identical"
    print(f"[colossal-serpent] PASS connected tail lengths {lengths}, no BG body, "
          f"one-damage contact, {hostile}-shot head+tail hell, rings, bounded hood, "
          "AOE + contraction")


if __name__ == "__main__":
    main()
