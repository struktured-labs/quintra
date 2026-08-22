#!/usr/bin/env python3
"""Live-ROM contract for seed-stable, recognizable Riftwild geography."""
from collections import Counter

from PIL import Image, ImageDraw
from pyboy import PyBoy

from test_overworld import (
    CAMERA_X, CAMERA_Y, EN, LARGE, ORIGIN_X, ORIGIN_Y, PL, ROM, ROOT, RS, TM,
    WORLD_BOTTOM, WORLD_EXT, WORLD_H, WORLD_W, exit_at, put16,
)
from quintra_topology import STAGE_BOSS_ROOM


ROOM_W, ROOM_H = 20, 17
WIDE_W, WIDE_H = 31, 31
EXT_W, BOTTOM_H = WIDE_W - ROOM_W, WIDE_H - ROOM_H
LANDMARKS = (96, 97, 98, 99)
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
    return pb


def inspect_cell(pb, screen, seed_low, seen_families, shots):
    assert pb.memory[RS + 18] == screen
    tiles = list(pb.memory[TM:TM + ROOM_W * ROOM_H])
    counts = Counter(tile for tile in tiles if tile in LANDMARKS)
    extension = list(pb.memory[
        WORLD_EXT:WORLD_EXT + EXT_W * ROOM_H])
    extension_counts = Counter(tile for tile in extension if tile in LANDMARKS)
    bottom = list(pb.memory[
        WORLD_BOTTOM:WORLD_BOTTOM + BOTTOM_H * WIDE_W])
    bottom_counts = Counter(tile for tile in bottom if tile in LANDMARKS)
    expected = LANDMARKS[(seed_low + screen) & 3]
    assert counts[expected] == 8, (
        f"Riftwild cell {screen} expected landmark {expected}, got {counts}"
    )
    extra = counts.copy()
    del extra[expected]
    assert extra == (Counter({96: 1}) if screen == 3 else Counter()), (
        f"Riftwild cell {screen} gained unintended landmark tiles: {extra}"
    )
    assert extension_counts == Counter({expected: 12}), (
        f"Riftwild far field {screen} expected landmark {expected}, "
        f"got {extension_counts}"
    )
    assert bottom_counts == Counter({expected: 8}), (
        f"Riftwild south field {screen} expected landmark {expected}, "
        f"got {bottom_counts}"
    )
    assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (248, 248)
    # Every solid family stays outside the broad trail cross. The center and
    # all four arms therefore remain visibly connected even when a route does
    # not expose every cardinal graph edge.
    assert all(tiles[y * ROOM_W + x] in (35, 34, 36)
               for x in (9, 10) for y in range(1, ROOM_H - 1)), (
        f"cell {screen} landmark interrupted north/south trail"
    )
    assert all(tiles[y * ROOM_W + x] in (35, 34, 36)
               for y in (8, 9) for x in range(1, ROOM_W - 1)), (
        f"cell {screen} landmark interrupted east/west trail"
    )
    assert all(tiles[y * ROOM_W + 19] in (35, 36)
               for y in range(1, ROOM_H - 1)), (
        f"cell {screen} retained a wall at the old viewport seam"
    )
    # Move the real camera into the added terrain before taking review media.
    # Geography is the subject of this sweep.  Remove the optional encounter
    # before sampling the camera so enemy knockback cannot make the expected
    # 248-136 bound vary from cell to cell.
    for slot in range(32):
        base = EN + slot * 28
        pb.memory[base] = pb.memory[base + 1] = 0
    put16(pb, PL + 9, 224); put16(pb, PL + 11, 224)
    pb.memory[PL + 15] = 120
    for _ in range(64):
        pb.tick()
    assert (pb.memory[CAMERA_X], pb.memory[CAMERA_Y]) == (88, 112), (
        f"cell {screen} camera={pb.memory[CAMERA_X]},{pb.memory[CAMERA_Y]} "
        f"player={pb.memory[PL + 9] | pb.memory[PL + 10] << 8},"
        f"{pb.memory[PL + 11] | pb.memory[PL + 12] << 8}")
    assert (pb.memory[0xFF43], pb.memory[0xFF42]) == (
        ((pb.memory[ORIGIN_X] << 3) + 88) & 0xFF,
        ((pb.memory[ORIGIN_Y] << 3) + 112) & 0xFF)
    seen_families[expected] += 1
    shots[screen] = pb.screen.image.copy()


def cross_to(pb, target, x, y):
    for slot in range(32):
        base = EN + slot * 28
        pb.memory[base] = pb.memory[base + 1] = 0
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, y)
    stable = 0
    expected = LANDMARKS[(pb.memory[RS + 2] + target) & 3]
    expected_camera_x = 88 if x == 0 else 0
    expected_camera_y = 112 if y == 0 else 0
    for _ in range(180):
        pb.tick()
        tiles = pb.memory[TM:TM + ROOM_W * ROOM_H]
        ready = (pb.memory[RS + 17] == 1
                 and pb.memory[RS + 18] == target
                 and pb.memory[0xFF40] & 0x02
                 and pb.memory[0xFF43]
                    == (((pb.memory[ORIGIN_X] << 3)
                         + expected_camera_x) & 0xFF)
                 and pb.memory[0xFF42]
                    == (((pb.memory[ORIGIN_Y] << 3)
                         + expected_camera_y) & 0xFF)
                 and sum(tile == expected for tile in tiles) == 8
                 and not any(tile & 0x80 for tile in tiles))
        stable = stable + 1 if ready else 0
        if stable >= 10:
            return
    raise AssertionError(
        f"Riftwild seam did not settle at {target}: "
        f"cell={pb.memory[RS + 18]} screen={pb.memory[RS + 17]} "
        f"lcdc={pb.memory[0xFF40]:02x} scx={pb.memory[0xFF43]} "
        f"scy={pb.memory[0xFF42]} origin="
        f"{pb.memory[ORIGIN_X]},{pb.memory[ORIGIN_Y]} "
        f"expected_camera={expected_camera_x},{expected_camera_y}"
    )


def main():
    pb = boot_world()
    seed_low = pb.memory[RS + 2]
    family_counts = Counter()
    shots = {}
    try:
        inspect_cell(pb, 0, seed_low, family_counts, shots)
        for screen, x, y in ROUTE:
            # This is a geography sweep, not a fifteen-room endurance policy.
            # Keep each real seam observable without letting accumulated
            # optional overworld fire turn a terrain contract into GAME OVER.
            pb.memory[PL + 2] = pb.memory[PL + 1]
            pb.memory[PL + 15] = 120
            cross_to(pb, screen, x, y)
            if screen not in shots:
                inspect_cell(pb, screen, seed_low, family_counts, shots)
    finally:
        pb.stop(save=False)

    assert family_counts == Counter({tile: 9 for tile in LANDMARKS}), family_counts
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
        "[riftwild-landmarks] PASS 36 scrolling 248x248 fields, four-part "
        "seed-rotated landmarks, real seams, central trails clear"
    )


if __name__ == "__main__":
    main()
