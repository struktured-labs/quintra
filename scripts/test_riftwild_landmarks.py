#!/usr/bin/env python3
"""Live-ROM contract for seed-stable, recognizable Riftwild geography."""
from collections import Counter

from PIL import Image, ImageDraw
from pyboy import PyBoy

from test_overworld import (
    CAMERA_X, CAMERA_Y, EN, LARGE, ORIGIN_X, ORIGIN_Y, PL, ROM, ROOT, RS, TM,
    WORLD_BOTTOM, WORLD_EXT, WORLD_H, WORLD_W, addr, exit_at, put16,
)
from quintra_topology import STAGE_BOSS_ROOM


ROOM_W, ROOM_H = 20, 17
WIDE_W, WIDE_H = 31, 31
EXT_W, BOTTOM_H = WIDE_W - ROOM_W, WIDE_H - ROOM_H
CLIMATE = (105, 106, 107, 108, 109, 110)
WALKABLE = {1, 3, 8, *range(9, 21), 23, 24, *range(33, 37), 96,
            105, 106, 107}
# Depth-first walk of the authored reciprocal graph. Repeated cells are the
# backtracking steps; every one of the 36 fields is still inspected once.
ROUTE = (
    (1, 232, 60), (2, 232, 60), (3, 232, 60), (4, 232, 60),
    (5, 232, 60), (11, 72, 232), (17, 72, 232), (23, 72, 232),
    (29, 72, 232), (35, 72, 232), (34, 0, 60), (33, 0, 60),
    (27, 72, 0), (21, 72, 0), (20, 0, 60), (14, 72, 0),
    (8, 72, 0), (7, 0, 60), (6, 0, 60), (12, 72, 232),
    (18, 72, 232), (19, 232, 60), (13, 72, 0), (19, 72, 232),
    (25, 72, 232), (31, 72, 232), (32, 232, 60), (26, 72, 0),
    (32, 72, 232), (31, 0, 60), (30, 0, 60), (24, 72, 0),
    (30, 72, 232), (31, 232, 60), (25, 72, 0), (19, 72, 0),
    (18, 0, 60), (12, 72, 0), (6, 72, 0), (7, 232, 60),
    (8, 232, 60), (14, 72, 232), (15, 232, 60), (9, 72, 0),
    (10, 232, 60), (16, 72, 232), (22, 72, 232), (28, 72, 232),
    (22, 72, 0), (16, 72, 0), (10, 72, 0), (9, 0, 60),
    (15, 72, 232), (14, 0, 60), (20, 72, 232), (21, 232, 60),
    (27, 72, 232), (33, 72, 232), (34, 232, 60), (35, 232, 60),
    (29, 72, 0), (23, 72, 0), (17, 72, 0), (11, 72, 0),
    (5, 72, 0), (4, 0, 60), (3, 0, 60), (2, 0, 60),
    (1, 0, 60), (0, 0, 60),
)


def horizontal_open(row, col):
    return not ((row, col) in ((1, 2), (2, 0), (3, 3), (4, 1)))


def vertical_open(row, col):
    return not ((row, col) in ((0, 4), (1, 1), (2, 3), (3, 0), (4, 4)))


def field_edges(screen):
    row, col = divmod(screen, 6)
    edges = 0
    if row > 0 and vertical_open(row - 1, col):
        edges |= 1
    if col < 5 and horizontal_open(row, col):
        edges |= 2
    if row < 5 and vertical_open(row, col):
        edges |= 4
    if col > 0 and horizontal_open(row, col - 1):
        edges |= 8
    return edges


def wide_tiles(pb):
    compact = list(pb.memory[TM:TM + ROOM_W * ROOM_H])
    extension = list(pb.memory[
        WORLD_EXT:WORLD_EXT + EXT_W * ROOM_H])
    bottom = list(pb.memory[
        WORLD_BOTTOM:WORLD_BOTTOM + BOTTOM_H * WIDE_W])
    rows = []
    for y in range(ROOM_H):
        rows.append(compact[y * ROOM_W:(y + 1) * ROOM_W]
                    + extension[y * EXT_W:(y + 1) * EXT_W])
    for y in range(BOTTOM_H):
        rows.append(bottom[y * WIDE_W:(y + 1) * WIDE_W])
    return rows


def southeast_review_position(wide):
    # Dynamic terrain makes a blind (224,224) debugger teleport invalid: that
    # point can deliberately be a canyon or reed bed. Find a real 16px floor
    # patch far enough southeast to drive both camera axes to their bounds.
    for y in range(27, 22, -1):
        for x in range(27, 20, -1):
            if all(wide[ty][tx] in WALKABLE
                   for ty in range(y, y + 2)
                   for tx in range(x, x + 2)):
                return x * 8, y * 8
    raise AssertionError("Riftwild climate left no southeast review clearing")


def boot_world():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(60):
        pb.tick()
    pb.memory[RS + 1] = STAGE_BOSS_ROOM[0]
    pb.memory[RS + 11] = 1
    # This debugger fixture changes the logical room to the defeated compact
    # boss arena. Do not retain the real opening field's scrolling geometry.
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
    # The visible opening cell has no south maze edge; mirror the defeated
    # arena's all-cardinal unseal before taking its real Riftwild exit.
    pb.memory[TM + 16 * ROOM_W + 9] = 3
    pb.memory[TM + 16 * ROOM_W + 10] = 3
    exit_at(pb, 72, 120)
    assert pb.memory[RS + 17] == 1 and pb.memory[RS + 18] == 0
    assert pb.memory[addr("_music_track_id")] == 22, \
        "Riftwild did not start its dedicated title-linked theme"
    # An authored east connection is a walkable trail at both halves of the
    # true 248px field edge, never an indoor door tile.
    assert pb.memory[WORLD_EXT + 8 * EXT_W + 10] == 36
    assert pb.memory[WORLD_EXT + 9 * EXT_W + 10] == 36
    return pb


def inspect_cell(pb, screen, seed_low, seen_families, biome_counts, shots):
    assert pb.memory[RS + 18] == screen
    # The old four-part 2x2 landmark family is lifted on ordinary fields and
    # replaced by a set piece (test_riftwild_setpiece.py). This contract keeps
    # mouths, climates, and the camera bounds.
    assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (248, 248)
    wide = wide_tiles(pb)
    edges = field_edges(screen)
    assert not any(tile == 3 for row in wide for tile in row), (
        f"cell {screen} leaked an indoor doorway into Riftwild"
    )
    # Each authored edge is a six-tile outdoor opening. These are the actual
    # field thresholds used by the transition detector, not decorative gaps.
    if edges & 1:
        assert wide[0][7:13] == [36] * 6, \
            f"cell {screen} narrow north mouth: {wide[0][7:13]}"
    if edges & 2:
        mouth = [wide[y][30] for y in range(6, 12)]
        assert mouth == [36] * 6, f"cell {screen} narrow east mouth: {mouth}"
    if edges & 4:
        assert wide[30][7:13] == [36] * 6, \
            f"cell {screen} narrow south mouth: {wide[30][7:13]}"
    if edges & 8:
        mouth = [wide[y][0] for y in range(6, 12)]
        assert mouth == [36] * 6, f"cell {screen} narrow west mouth: {mouth}"
    biome_counts[screen // 6].update(
        tile for row in wide for tile in row if tile in CLIMATE
    )
    # The obsolete viewport seams are now allowed to carry real rivers and
    # ridges. The protected central trail crosses both, so these features no
    # longer need to expose an artificial full-height/full-width floor line.
    # Move the real camera into the added terrain before taking review media.
    # Geography is the subject of this sweep.  Remove the optional encounter
    # before sampling the camera so enemy knockback cannot make the expected
    # 248-136 bound vary from cell to cell.
    for slot in range(32):
        base = EN + slot * 28
        pb.memory[base] = pb.memory[base + 1] = 0
    review_x, review_y = southeast_review_position(wide)
    put16(pb, PL + 9, review_x); put16(pb, PL + 11, review_y)
    pb.memory[PL + 15] = 120
    for _ in range(64):
        pb.tick()
        if (pb.memory[CAMERA_X], pb.memory[CAMERA_Y]) == (88, 112):
            break
    assert (pb.memory[CAMERA_X], pb.memory[CAMERA_Y]) == (88, 112), (
        f"cell {screen} camera={pb.memory[CAMERA_X]},{pb.memory[CAMERA_Y]} "
        f"player={pb.memory[PL + 9] | pb.memory[PL + 10] << 8},"
        f"{pb.memory[PL + 11] | pb.memory[PL + 12] << 8}")
    assert (pb.memory[0xFF43], pb.memory[0xFF42]) == (
        ((pb.memory[ORIGIN_X] << 3) + 88) & 0xFF,
        ((pb.memory[ORIGIN_Y] << 3) + 112) & 0xFF)
    shots[screen] = pb.screen.image.copy()


def stand_at_mouth(pb, x, y):
    """Stand on a path mouth tile so climate jitter cannot park the hero
    in a lake or tree just inside the authored edge coordinate."""
    wide = wide_tiles(pb)
    if x == 232:
        cols, rows = (30, 29, 28), range(6, 12)
    elif x == 0:
        cols, rows = (0, 1, 2), range(6, 12)
    elif y == 232:
        cols, rows = range(7, 13), (30, 29, 28)
    else:
        cols, rows = range(7, 13), (0, 1, 2)
    for prefer in (36, None):
        for ty in rows:
            for tx in cols:
                tile = wide[ty][tx]
                if tile == prefer or (prefer is None and tile in WALKABLE):
                    if x == 232:
                        return tx * 8 + 7, ty * 8 + 4
                    if x == 0:
                        return tx * 8, ty * 8 + 4
                    if y == 232:
                        return tx * 8 + 4, ty * 8 + 7
                    return tx * 8 + 4, ty * 8

    return x, y


def cross_to(pb, target, x, y):
    for slot in range(32):
        base = EN + slot * 28
        pb.memory[base] = pb.memory[base + 1] = 0
    stand_x, stand_y = stand_at_mouth(pb, x, y)
    put16(pb, PL + 9, stand_x)
    put16(pb, PL + 11, stand_y)
    if x == 232:
        hold = "right"
    elif x == 0:
        hold = "left"
    elif y == 232:
        hold = "down"
    else:
        hold = "up"
    pb.button_press(hold)
    stable = 0
    held = True
    player_x = player_y = 0
    for _ in range(240):
        # Keep incidental fire from killing the geography walk.
        pb.memory[PL + 2] = pb.memory[PL + 1]
        pb.memory[PL + 15] = 120
        pb.tick()
        if held and pb.memory[RS + 18] == target:
            pb.button_release(hold)
            held = False
        tiles = pb.memory[TM:TM + ROOM_W * ROOM_H]
        player_x = pb.memory[PL + 9] | pb.memory[PL + 10] << 8
        player_y = pb.memory[PL + 11] | pb.memory[PL + 12] << 8
        reciprocal_arrival = ((x == 232 and player_x < 24)
                              or (x == 0 and player_x > 200)
                              or (y == 232 and player_y < 24)
                              or (y == 0 and player_y > 200))
        expected_x = ((pb.memory[ORIGIN_X] << 3) + pb.memory[CAMERA_X]) & 0xFF
        expected_y = ((pb.memory[ORIGIN_Y] << 3) + pb.memory[CAMERA_Y]) & 0xFF
        ready = (pb.memory[RS + 17] == 1
                 and pb.memory[RS + 18] == target
                 and reciprocal_arrival
                 and pb.memory[0xFF40] & 0x02
                 and (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (248, 248)
                 and (pb.memory[0xFF43], pb.memory[0xFF42]) == (expected_x, expected_y)
                 and not any(tile & 0x80 for tile in tiles))
        stable = stable + 1 if ready else 0
        if stable >= 10:
            if held:
                pb.button_release(hold)
            return
    if held:
        pb.button_release(hold)
    raise AssertionError(
        f"Riftwild seam did not settle at {target}: "
        f"cell={pb.memory[RS + 18]} screen={pb.memory[RS + 17]} "
        f"lcdc={pb.memory[0xFF40]:02x} scx={pb.memory[0xFF43]} "
        f"scy={pb.memory[0xFF42]} origin="
        f"{pb.memory[ORIGIN_X]},{pb.memory[ORIGIN_Y]} "
        f"cam={pb.memory[CAMERA_X]},{pb.memory[CAMERA_Y]} "
        f"player={player_x},{player_y} world="
        f"{pb.memory[WORLD_W]},{pb.memory[WORLD_H]}"
    )


def verify_broad_mire_thresholds():
    # A fresh real north->south seam into the densest climate is the specific
    # cartridge regression for six-tile mouths. The long atlas walk below is
    # concerned with reciprocal reachability and can revisit fields after
    # debugger camera teleports, so do not conflate that stress state with the
    # generation-time width invariant.
    pb = boot_world()
    try:
        pb.memory[RS + 18] = 19
        exit_at(pb, 72, 232)
        assert pb.memory[RS + 18] == 25
        wide = wide_tiles(pb)
        assert wide[0][7:13] == [36] * 6
        assert wide[30][7:13] == [36] * 6
        assert [wide[y][0] for y in range(6, 12)] == [36] * 6
    finally:
        pb.stop(save=False)


def main():
    pb = boot_world()
    seed_low = pb.memory[RS + 2]
    family_counts = Counter()  # unused; kept so inspect_cell signature stays
    biome_counts = [Counter() for _ in range(6)]
    shots = {}
    try:
        inspect_cell(pb, 0, seed_low, family_counts, biome_counts, shots)
        for screen, x, y in ROUTE:
            # This is a geography sweep, not a fifteen-room endurance policy.
            # Keep each real seam observable without letting accumulated
            # optional overworld fire turn a terrain contract into GAME OVER.
            pb.memory[PL + 2] = pb.memory[PL + 1]
            pb.memory[PL + 15] = 120
            cross_to(pb, screen, x, y)
            if screen not in shots:
                inspect_cell(pb, screen, seed_low, family_counts,
                             biome_counts, shots)
    finally:
        pb.stop(save=False)

    # Six horizontal climate belts must remain mechanically and visually
    # distinct after landmark, gate, encounter, and reward orchestration.
    required = (
        (107, 109),       # Frostfell: snow and mountain crown
        (),               # Lakewood uses the legacy water/tree vocabulary
        (108, 109),       # High ridge: chasms and mountains
        (),               # Riverplain uses broad legacy water
        (105, 108, 110),  # Mire: mud, sinkholes, reeds
        (106, 108, 109),  # Sunscar: sand, canyon, mountains
    )
    for zone, kinds in enumerate(required):
        for tile in kinds:
            assert biome_counts[zone][tile] > 0, (
                f"Riftwild zone {zone} missing climate tile {tile}: "
                f"{biome_counts[zone]}"
            )
    verify_broad_mire_thresholds()
    sheet = Image.new("RGB", (6 * 160, 6 * 144), (0, 0, 0))
    draw = ImageDraw.Draw(sheet)
    for screen in range(36):
        x, y = (screen % 6) * 160, (screen // 6) * 144
        sheet.paste(shots[screen].convert("RGB"), (x, y))
        draw.text((x + 2, y + 130), f"CELL {screen:02d}", fill=(255, 255, 255))
    out = ROOT / "tmp" / "riftwild-landmarks.png"
    out.parent.mkdir(exist_ok=True)
    sheet.save(out)
    print(
        "[riftwild-landmarks] PASS 36 scrolling 248x248 fields, "
        "six climates, broad outdoor thresholds"
    )


if __name__ == "__main__":
    main()
