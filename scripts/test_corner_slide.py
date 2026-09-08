#!/usr/bin/env python3
"""Held cardinal input aligns through narrow gaps without crossing scenery."""
import io

from pyboy import PyBoy
from test_damage_hud import ROM, PL, TM, SCREEN, clear_entities, press


def position(pb):
    return tuple(pb.memory[PL + i] | pb.memory[PL + i + 1] << 8
                 for i in (9, 11))


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    press(pb, "start")
    pb.tick(30)
    press(pb, "a")
    pb.tick(120)
    assert pb.memory[SCREEN] == 5
    clear_entities(pb)
    for y in range(17):
        for x in range(20):
            pb.memory[TM + y * 20 + x] = 1
    baseline = io.BytesIO()
    pb.save_state(baseline)
    cases = 0
    try:
        for speed in (4, 6, 7, 13):
            for tile in (2, 21, 25):
                for direction in ("up", "down", "left", "right"):
                    for offset in (-3, -1, 0, 1, 3, 4):
                        baseline.seek(0)
                        pb.load_state(baseline)
                        vertical = direction in ("up", "down")
                        # A two-tile slit, flanked by solid scenery.
                        for k in range(3, 16):
                            if k in (9, 10):
                                continue
                            tx, ty = (k, 8) if vertical else (10, k)
                            pb.memory[TM + ty * 20 + tx] = tile
                        if vertical:
                            x = (70 if offset <= 0 else 74) + offset
                            y = (72 if tile != 2 else 64) if direction == "up" else 48
                        else:
                            x = 86 if direction == "left" else 66
                            # Feet fit walls at y=64..72; full body at y=72.
                            y = ((64 if offset <= 0 else 72) if tile == 2 else 72) + offset
                        for i, value in ((9, x), (11, y)):
                            pb.memory[PL + i] = value
                            pb.memory[PL + i + 1] = 0
                        pb.memory[PL + 7] = speed
                        pb.memory[PL + 24] = 0
                        pb.button_press(direction)
                        for _ in range(24):
                            pb.tick()
                            px, py = position(pb)
                            samples = [(px + xx, py + yy)
                                       for xx in (2, 8, 13) for yy in (8, 15)]
                            if tile != 2:
                                samples += [(px + xx, py + yy)
                                            for xx in (2, 8, 13) for yy in (0, 7)]
                            assert all(pb.memory[TM + sy // 8 * 20 + sx // 8] == 1
                                       for sx, sy in samples), (direction, tile, offset, "clipped")
                        px, py = position(pb)
                        pb.button_release(direction)
                        pb.tick()
                        label = (speed, tile, direction, offset, (x, y), (px, py))
                        if abs(offset) <= 3:
                            progress = (y - py if direction == "up" else py - y) if vertical else (
                                x - px if direction == "left" else px - x)
                            assert progress >= 5, label
                            assert abs((px - x) if vertical else (py - y)) <= 3, label
                        else:
                            if tile == 25:
                                assert (px == x if vertical else py == y), label
                            else:
                                assert (px, py) == (x, y), label
                        cases += 1
        print(f"[corner-slide] PASS {cases} gap approaches; speeds, walls, pillars, crates, reach limit")
    finally:
        pb.stop(save=False)


if __name__ == "__main__":
    main()
