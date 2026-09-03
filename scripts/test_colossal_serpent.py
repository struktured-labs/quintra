#!/usr/bin/env python3
"""Live-ROM contract for Verdant's articulated Snake boss."""
from pathlib import Path

from test_boss_identity import EN, ENEMY_STATUS, PL, TM, addr, enter_boss, put16


ROOT = Path(__file__).resolve().parent.parent
BODY_MIN, BODY_MAX = 55, 63
CAMERA_X = addr("_room_camera_x")
TAIL_X = addr("_serpent_tail_x")
TAIL_Y = addr("_serpent_tail_y")
TAIL_COUNT = addr("_serpent_tail_count")
TAIL_VISIBLE = addr("_serpent_tail_visible")
TAIL_ACTIVE = addr("_serpent_tail_active")
HEAD_INDEX = addr("_serpent_head_index")
ANIM_COUNTER = addr("_entity_anim_counter")
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
    food = ((60, 88), (76, 76), (92, 68), (100, 60))
    visible_targets = (6, 10, 14, 16)
    lengths = [pb.memory[TAIL_VISIBLE]]
    background_counts = [len(projected_body_tiles(pb))]
    for growth, (food_x, food_y) in enumerate(food):
        pb.memory[PL + 15] = 255
        put16(pb, boss + 3, food_x - 12)
        put16(pb, boss + 7, food_y - 12)
        pb.memory[boss + 15] = 0
        pb.memory[boss + 16] = 1
        pb.memory[boss + 21] = growth
        pb.memory[boss + 11] = 3  # fourth waypoint: the real growth mote
        for _ in range(30):
            pb.tick()
            if pb.memory[boss + 21] == growth + 1:
                break
        assert pb.memory[boss + 21] == growth + 1, (
            f"Serpent ignored storm mote {growth + 1}: "
            f"state={pb.memory[boss + 15]} timer={pb.memory[boss + 16]} "
            f"growth={pb.memory[boss + 21]} pos={position(pb, boss)}")
        for _ in range(320):
            pb.memory[PL + 15] = 255
            pb.tick()
            if pb.memory[TAIL_VISIBLE] == visible_targets[growth]:
                break
        assert pb.memory[TAIL_VISIBLE] == visible_targets[growth], (
            f"meal {growth + 1} did not grow smoothly to "
            f"{visible_targets[growth]} scales: visible="
            f"{pb.memory[TAIL_VISIBLE]} state={pb.memory[boss + 15]} "
            f"growth={pb.memory[boss + 21]}")
        lengths.append(pb.memory[TAIL_VISIBLE])
        background_counts.append(len(projected_body_tiles(pb)))
    assert lengths == [2, 6, 10, 14, 16], (
        f"meals did not expose the sixteen-scale body: {lengths}")
    assert background_counts == [0, 0, 0, 0, 0], (
        f"growth leaked back into detached BG tiles: {background_counts}")

    # Lay a synthetic L-shaped motion trace one legal eight-pixel sample at a
    # time. The runtime must preserve that route as a continuous edge-connected
    # tail instead of stretching a line between teleports or repainting a map.
    pb.memory[boss + 15] = 1
    pb.memory[boss + 10] = 220
    def record_trace_point(x, y):
        put16(pb, boss + 3, x)
        put16(pb, boss + 7, y)
        # This section proves the eight-pixel route sampler itself. Keep the
        # live chase from advancing far enough within one PyBoy observation
        # tick to overwrite the exact synthetic point before Python sees it;
        # pursuit is exercised independently by the movement suite below.
        put16(pb, PL + 9, x)
        put16(pb, PL + 11, y)
        for _ in range(8):
            pb.memory[PL + 15] = 255
            pb.memory[boss + 16] = 0
            pb.memory[ENEMY_STATUS + (boss - EN) // ENTITY_SIZE] = 0
            pb.tick()
            if (pb.memory[TAIL_X] == (x + 12) & 0xFF
                    and pb.memory[TAIL_Y] == (y + 12) & 0xFF):
                return
        raise AssertionError(
            f"tail sampler missed authored point {(x, y)}: "
            f"tail0={tail_points(pb)[:2]} head={position(pb, boss)}")

    for x in range(60, 133, 8):
        record_trace_point(x, 36)
    for y in range(44, 109, 8):
        record_trace_point(132, y)
    trail = tail_points(pb)[:17]
    assert len(trail) == 17 and pb.memory[TAIL_VISIBLE] == 16
    for previous, current in zip(trail, trail[1:]):
        gap_x = abs(previous[0] - current[0])
        gap_y = abs(previous[1] - current[1])
        assert 1 <= gap_x + gap_y and gap_x <= 8 and gap_y <= 8, (
            f"tail disconnected at {previous}->{current}")
    route_pixels = sum(abs(previous[0] - current[0])
                       + abs(previous[1] - current[1])
                       for previous, current in zip(trail, trail[1:]))
    assert route_pixels >= 120, (
        f"full tail no longer occupies an exaggerated route length: {route_pixels}px")
    assert max(y for _, y in trail) - min(y for _, y in trail) >= 35, (
        f"tail did not retain the head's route: {trail}")

    # The tail is a one-damage contact hazard, not just art. Its combined
    # scale/player ribbon is deliberately wider than point contact, but remains
    # passable so curling around the player cannot create a boss-room softlock.
    clear_hostile_projectiles(pb)
    touch_x, touch_y = trail[5]
    # Put the champion at the outer combined-hurtbox edge: center +9px from
    # the scale, outside the old narrow threshold but inside the visible-body
    # plus champion-width ribbon.
    put16(pb, PL + 9, touch_x + 1)
    put16(pb, PL + 11, touch_y - 12)
    pb.memory[PL + 2] = 10
    pb.memory[PL + 15] = pb.memory[PL + 20] = 0
    for _ in range(3):
        pb.tick()
        if pb.memory[PL + 2] < 10:
            break
    assert pb.memory[PL + 2] == 9, (
        f"visible tail did not deal its fair contact damage: hp={pb.memory[PL + 2]}")

    # The maximum-length body alternates between its ordinary ribbon and a
    # visibly pale storm charge. On the charged beat its aura reaches 13px
    # from a scale center, turning the whole second coil into moving territory.
    pb.memory[PL + 15] = pb.memory[PL + 20] = 0
    pb.memory[PL + 2] = 10
    put16(pb, PL + 9, touch_x + 5)  # champion center = scale center +13
    put16(pb, PL + 11, touch_y - 12)
    for _ in range(6):
        pb.memory[ANIM_COUNTER] = 0x10
        pb.tick()
        if pb.memory[PL + 2] < 10:
            break
    assert pb.memory[PL + 2] == 9, (
        "full-growth pale pulse did not widen the tail's charged danger field")

    # Signature warning used to return before tail collision. Pin the champion
    # on a visible scale while half health arms Coil Tempest: the body must hurt
    # on that same beat and the warned signature must still begin normally.
    pb.memory[PL + 15] = pb.memory[PL + 20] = 0
    pb.memory[PL + 2] = 10
    put16(pb, PL + 9, touch_x - 8)
    put16(pb, PL + 11, touch_y - 12)
    pb.memory[boss + 14] = pb.memory[boss + 23] // 2
    pb.memory[boss + 20] &= 0x3F
    for _ in range(6):
        pb.tick()
        if pb.memory[boss + 20] & 0x40:
            break
    assert pb.memory[boss + 20] & 0x40, "Coil Tempest warning did not arm"
    assert pb.memory[PL + 2] == 9, (
        "tail became harmless while the signature dispatcher owned the boss")
    pb.memory[boss + 14] = pb.memory[boss + 23]
    pb.memory[boss + 20] = (pb.memory[boss + 20] & 0x3F) | 0x81
    pb.memory[boss + 18] = 0

    # Full length still layers bullet hell over Snake movement. The head fires
    # an aimed three-lane fan while the tail sheds a mixed-speed tip pair plus
    # a midpoint shot: six hostile sprites, not stage one's generic full ring.
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
        if hostile >= 6:
            break
    assert hostile == 6, f"Serpent lost its head+tail bullet hell: {hostile} shots"
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
    # Isolate the hood's fixed AOE from the separately proven charged coil.
    for i in range(pb.memory[TAIL_COUNT]):
        pb.memory[TAIL_X + i] = pb.memory[TAIL_Y + i] = 0
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
        if pb.memory[TAIL_VISIBLE] != before_length:
            break
    assert pb.memory[boss + 21] == before_growth
    assert pb.memory[TAIL_VISIBLE] == before_length - 1, (
        "contraction did not retract exactly one rear scale")

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
    # Renderer contract: hit flashes may change the hood palette but may never
    # hide it again. This source guard accompanies the live cartridge checks.
    draw_source = (ROOT / "src/game/enemy_serpent_draw.c").read_text()
    head_loop = draw_source.split("// A broad cobra head", 1)[1].split(
        "// Overlapping, spiked scales", 1)[0]
    assert "move_sprite(oam, 0, 0)" not in head_loop
    assert "set_sprite_prop(oam, head_pal)" in head_loop
    print(f"[colossal-serpent] PASS connected tail lengths {lengths}, no BG body, "
          f"{route_pixels}px continuous charged body, stable palette-flash hood, "
          f"{hostile}-shot head+tail hell, rings, bounded hood, "
          "AOE + one-scale contraction")


if __name__ == "__main__":
    main()
