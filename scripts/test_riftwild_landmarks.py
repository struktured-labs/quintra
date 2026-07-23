#!/usr/bin/env python3
"""Live-ROM contract for seed-stable, recognizable Riftwild geography."""
from collections import Counter

from PIL import Image, ImageDraw
from pyboy import PyBoy

from test_overworld import EN, PL, ROM, ROOT, RS, TM, exit_at, put16
from quintra_topology import STAGE_BOSS_ROOM


ROOM_W, ROOM_H = 20, 17
LANDMARKS = (96, 97, 98, 99)
# Visit all sixteen cells through real reciprocal seams in a compact snake.
ROUTE = (
    (1, 144, 60), (2, 144, 60), (3, 144, 60),
    (7, 72, 120), (6, 0, 60), (5, 0, 60), (4, 0, 60),
    (8, 72, 120), (9, 144, 60), (10, 144, 60), (11, 144, 60),
    (15, 72, 120), (14, 0, 60), (13, 0, 60), (12, 0, 60),
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
    expected = LANDMARKS[(seed_low + screen) & 3]
    assert counts == Counter({expected: 8}), (
        f"Riftwild cell {screen} expected landmark {expected}, got {counts}"
    )
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
    for _ in range(180):
        pb.tick()
        tiles = pb.memory[TM:TM + ROOM_W * ROOM_H]
        ready = (pb.memory[RS + 17] == 1
                 and pb.memory[RS + 18] == target
                 and pb.memory[0xFF40] & 0x02
                 and pb.memory[0xFF43] == 0
                 and pb.memory[0xFF42] == 0
                 and sum(tile == expected for tile in tiles) == 8
                 and not any(tile & 0x80 for tile in tiles))
        stable = stable + 1 if ready else 0
        if stable >= 10:
            return
    raise AssertionError(
        f"Riftwild seam did not settle at {target}: "
        f"cell={pb.memory[RS + 18]} screen={pb.memory[RS + 17]} "
        f"lcdc={pb.memory[0xFF40]:02x} scx={pb.memory[0xFF43]} "
        f"scy={pb.memory[0xFF42]}"
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
            inspect_cell(pb, screen, seed_low, family_counts, shots)
    finally:
        pb.stop(save=False)

    assert family_counts == Counter({tile: 4 for tile in LANDMARKS}), family_counts
    sheet = Image.new("RGB", (4 * 160, 4 * 144), (0, 0, 0))
    draw = ImageDraw.Draw(sheet)
    for screen in range(16):
        x, y = (screen & 3) * 160, (screen >> 2) * 144
        sheet.paste(shots[screen].convert("RGB"), (x, y))
        draw.text((x + 2, y + 130), f"CELL {screen:02d}", fill=(255, 255, 255))
    out = ROOT / "tmp" / "riftwild-landmarks.png"
    out.parent.mkdir(exist_ok=True)
    sheet.save(out)
    print(
        "[riftwild-landmarks] PASS four seed-rotated families x4, "
        "16/16 real seams, central trails clear"
    )


if __name__ == "__main__":
    main()
