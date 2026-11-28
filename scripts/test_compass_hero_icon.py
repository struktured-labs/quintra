#!/usr/bin/env python3
"""The Compass "you" mark is the current hero, and shared cells take turns (#264).

Hero icon, for each of the five classes:
  * the dungeon node under the hero is that class's real 16x16 sprite
    (BG tiles 110..113 hold the same bytes as the class's four OBJ tiles);
  * the one-tile mark (legend, Riftwild, town) is that class's 8x8 mini;
  * both use the hero's live OBJ palette on the map's dark ground;
  * all five classes are distinct.

Slideshow: a cell holding two or more icons shows each for half a second.
Standing in the room the GOAL points at, the node alternates hero and GOAL
every 30 frames on the right palettes, and a single-icon map never changes.

Pass --shots DIR to save one Compass screenshot per class.
"""
import sys
from pathlib import Path

import gen_map_hero_icons as icons
from quintra_topology import STAGE_START, dungeon_size, mission_graph
from test_compass_map import (
    BGT_MAP_BIG_GOAL, BGT_MAP_BIG_HERE, GX, GY, addr, close_compass,
    map_tile, node_tile, open_compass,
)
from test_convergence_transform import boot

CLASSES = ("wolfkin", "sauran", "corvin", "picsean", "vespine")
BGT_MAP_HERE = 50
MAP_GROUND = (0x61, 0x08)          # BGR555(1, 3, 2), little-endian bytes
SCREEN, RS, PLAYER = map(addr, ("_loop_current_screen", "_run_state",
                                "_player"))
SLIDE_N = addr("_map_slide_n")


def bg_tile(pb, tile):
    base = 0x9000 + tile * 16 if tile < 128 else 0x8000 + tile * 16
    return bytes(pb.memory[0, base + i] for i in range(16))


def obj_tile(pb, tile):
    return bytes(pb.memory[0, 0x8000 + tile * 16 + i] for i in range(16))


def palette(pb, index_reg, slot):
    out = []
    for offset in range(8):
        pb.memory[index_reg] = slot * 8 + offset
        out.append(pb.memory[index_reg + 1])
    return tuple(out)


def attr(pb, x, y):
    return pb.memory[1, 0x9800 + y * 32 + x] & 7


def node_attr(pb, cell):
    return {attr(pb, GX[cell] + dx, GY[cell] + dy)
            for dx in (0, 1) for dy in (0, 1)}


def hero_contract(class_id, shots):
    name = CLASSES[class_id]
    pb = boot(class_id)
    pb.tick(30)
    assert pb.memory[PLAYER] == class_id, f"did not enter as {name}"
    sprite = [obj_tile(pb, class_id * 4 + t) for t in range(4)]
    hero_pal = palette(pb, 0xFF6A, 1)
    here = pb.memory[RS + 1] - STAGE_START[0]
    open_compass(pb, SCREEN)

    assert node_tile(pb, here) == BGT_MAP_BIG_HERE
    assert node_attr(pb, here) == {7}
    big = [bg_tile(pb, BGT_MAP_BIG_HERE + t) for t in range(4)]
    assert big == sprite, f"{name}: the map node is not the hero's own sprite"
    mini = bytes(icons.encode(icons.mini(name)))
    assert bg_tile(pb, BGT_MAP_HERE) == mini, (
        f"{name}: the one-tile mark is not the {name} mini")
    assert map_tile(pb, 0, 17) == BGT_MAP_HERE and attr(pb, 0, 17) == 7, (
        f"{name}: the legend's YOU key is not the hero mark")
    map_pal = palette(pb, 0xFF68, 7)
    assert map_pal[2:] == hero_pal[2:], (
        f"{name}: map hero palette {map_pal} is not the hero's {hero_pal}")
    assert map_pal[:2] == MAP_GROUND, f"{name}: hero mark ground {map_pal[:2]}"

    if shots is not None:
        pb.screen.image.convert("RGB").resize((480, 432), 0).save(
            shots / f"compass-hero-{name}.png")
    # The run seed differs per boot, so the start room may or may not share
    # its cell with another mark. With one icon per cell, nothing may change
    # while the map is open.
    shared = pb.memory[SLIDE_N]
    before = [map_tile(pb, x, y) for y in range(18) for x in range(20)]
    for _ in range(70):
        pb.tick()
    after = [map_tile(pb, x, y) for y in range(18) for x in range(20)]
    assert shared or after == before, (
        f"{name}: the map changed with no shared cell")
    close_compass(pb, SCREEN, PLAYER)
    pb.stop(save=False)
    return tuple(big), mini, map_pal


def slideshow_contract(shots):
    pb = boot(0)
    pb.tick(30)
    seed = sum(pb.memory[RS + 2 + i] << (i * 8) for i in range(4))
    goal = mission_graph(dungeon_size(0), seed, 0)["trial"]
    # Stand in the room the GOAL points at: hero and GOAL share its node.
    pb.memory[RS + 1] = STAGE_START[0] + goal
    open_compass(pb, SCREEN)
    assert pb.memory[SLIDE_N] == 1, (
        f"hero on the GOAL room should arm one slideshow cell, got "
        f"{pb.memory[SLIDE_N]}")
    want = {BGT_MAP_BIG_HERE: {7}, BGT_MAP_BIG_GOAL: {2}}
    runs, last, length, torn = [], None, 0, 0
    for frame in range(200):
        # A turn is drawn at the top of VBlank, which is exactly where the
        # emulator hands back control, so the frame of a turn can be sampled
        # half written. It is never displayed that way. Skip that one frame.
        tile = pb.memory[0, 0x9800 + GY[goal] * 32 + GX[goal]]
        if tile not in want or node_attr(pb, goal) != want[tile]:
            torn += 1
            pb.tick()
            continue
        if tile == last:
            length += 1
        else:
            if last is not None:
                runs.append((last, length))
            last, length = tile, 1
        if shots is not None and frame in (5, 45):
            pb.screen.image.convert("RGB").resize((480, 432), 0).save(
                shots / f"compass-slideshow-{'hero' if frame == 5 else 'goal'}.png")
        pb.tick()
    order = [tile for tile, _n in runs]
    assert order[:4] == [BGT_MAP_BIG_HERE, BGT_MAP_BIG_GOAL,
                         BGT_MAP_BIG_HERE, BGT_MAP_BIG_GOAL], order
    assert torn <= len(runs) + 1, f"{torn} unreadable frames in {len(runs)} turns"
    # The first slide started before sampling did; the rest are whole.
    assert all(n in (29, 30) for _tile, n in runs[1:]), (
        f"slides are not half a second each: {runs}")
    close_compass(pb, SCREEN, PLAYER)
    pb.stop(save=False)
    return runs


def main():
    shots = None
    if "--shots" in sys.argv:
        shots = Path(sys.argv[sys.argv.index("--shots") + 1])
        shots.mkdir(parents=True, exist_ok=True)
    seen = [hero_contract(c, shots) for c in range(5)]
    assert len({big for big, _m, _p in seen}) == 5, "dungeon hero icons repeat"
    assert len({mini for _b, mini, _p in seen}) == 5, "mini hero icons repeat"
    assert len({pal for _b, _m, pal in seen}) == 5, "hero map palettes repeat"
    runs = slideshow_contract(shots)
    print(f"[compass-hero-icon] PASS five classes: node = own sprite, mini "
          f"and palette distinct; hero + GOAL cell alternates every 30 "
          f"frames ({len(runs)} slides watched)")


if __name__ == "__main__":
    main()
