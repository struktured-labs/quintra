"""Shared PyBoy helpers for the Sun Lattice light puzzle (PUZZLE_SUN_LATTICE).

The tracer here mirrors sl_trace() in src/game/sun_lattice_gen.c with the
live room_tilemap, so a test can read the fixtures from WRAM, solve the room
with a breadth-first search over vane angles, and then turn the needed vanes
with ordinary controller strikes.
"""

import re
from collections import deque
from itertools import product

PUZZLE_SUN_LATTICE = 5
SLK_EMITTER, SLK_VANE, SLK_FIXED, SLK_BIFROST, SLK_OBELISK = 1, 2, 3, 4, 5
W, H = 20, 17
DX = (0, 1, 0, -1)
DY = (-1, 0, 1, 0)
PASSABLE = {1, 19, 20, 31, 33, 97, 101, 102, 103, 104, 108}
WALKABLE = {1, 3, 7, 19, 20, 23, 31, 33, 34, *range(9, 19)}
PILLAR = 21
PATH_CAP, QUEUE = 32, 5


def symbols(noi_text):
    def addr(name):
        m = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", noi_text)
        if not m:
            raise RuntimeError(name)
        return int(m.group(1), 16)
    names = ("_sl_n", "_sl_x", "_sl_y", "_sl_kind", "_sl_ang",
             "_sl_solved_ang", "_sl_lit", "_sl_beam_h", "_sl_beam_v",
             "_sl_crystal_x", "_sl_crystal_y", "_sl_attempts")
    return {n: addr(n) for n in names}


def read_state(pb, sym):
    n = pb.memory[sym["_sl_n"]]
    fx = []
    for i in range(n):
        fx.append(dict(
            x=pb.memory[sym["_sl_x"] + i], y=pb.memory[sym["_sl_y"] + i],
            kind=pb.memory[sym["_sl_kind"] + i],
            ang=pb.memory[sym["_sl_ang"] + i],
            solved=pb.memory[sym["_sl_solved_ang"] + i],
            lit=pb.memory[sym["_sl_lit"] + i]))
    return fx


def read_bits(pb, base):
    out = set()
    for c in range(W * H):
        if pb.memory[base + (c >> 3)] & (1 << (c & 7)):
            out.add((c % W, c // W))
    return out


def trace(fixtures, angles, tiles=None):
    """Return (horizontal cells, vertical cells, lit obelisk indices)."""
    at = {(f["x"], f["y"]): i for i, f in enumerate(fixtures)}
    hz, vt, lit = set(), set(), set()
    queue = [(f["x"], f["y"], angles[i]) for i, f in enumerate(fixtures)
             if f["kind"] == SLK_EMITTER][:QUEUE]
    qi = 0
    while qi < len(queue):
        x, y, d = queue[qi]
        qi += 1
        for _ in range(PATH_CAP):
            x, y = x + DX[d], y + DY[d]
            if not (0 <= x < W and 0 <= y < H):
                break
            if (x, y) in at:
                i = at[(x, y)]
                k = fixtures[i]["kind"]
                if k in (SLK_VANE, SLK_FIXED):
                    d = (3 - d) if angles[i] else (d ^ 1)
                    continue
                if k == SLK_BIFROST:
                    for nd in ((d + 1) & 3, (d + 3) & 3):
                        if len(queue) < QUEUE:
                            queue.append((x, y, nd))
                elif k == SLK_OBELISK:
                    lit.add(i)
                break
            if tiles is not None and tiles[y * W + x] not in PASSABLE:
                break
            (hz if d & 1 else vt).add((x, y))
    return hz, vt, lit


def obelisks(fixtures):
    return {i for i, f in enumerate(fixtures) if f["kind"] == SLK_OBELISK}


def solve(fixtures, tiles):
    """Fewest vane turns that light every Obelisk, as fixture indices."""
    vanes = [i for i, f in enumerate(fixtures) if f["kind"] == SLK_VANE]
    goal = obelisks(fixtures)
    start = tuple(f["ang"] for f in fixtures)
    seen = {start}
    pending = deque([(start, ())])
    while pending:
        angles, path = pending.popleft()
        if trace(fixtures, angles, tiles)[2] >= goal:
            return list(path)
        for i in vanes:
            nxt = list(angles)
            nxt[i] ^= 1
            nxt = tuple(nxt)
            if nxt not in seen:
                seen.add(nxt)
                pending.append((nxt, path + (i,)))
    return None


def body_component(tiles, start):
    def ok(x, y):
        return (1 <= x <= 19 and 1 <= y <= 16 and all(
            tiles[ty * W + tx] in WALKABLE
            for tx, ty in ((x - 1, y - 1), (x, y - 1), (x - 1, y), (x, y))))
    seen, todo = {start}, [start]
    while todo:
        x, y = todo.pop()
        for c in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
            if c not in seen and ok(*c):
                seen.add(c)
                todo.append(c)
    return seen


def melee_reachable(component, x, y):
    """A 2x2 body position in the component touches (x, y) on a side."""
    for bx, by in component:
        for tx, ty in ((bx - 1, by - 1), (bx, by - 1), (bx - 1, by), (bx, by)):
            if abs(tx - x) + abs(ty - y) == 1:
                return True
    return False


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def strike(pb, player, tilemap, x, y, changed, frames=40):
    """Stand beside cell (x, y) and fire the primary attack into it.

    changed() reports success. Sides are tried in turn; each side must give
    the 16x16 body four walkable tiles so the champion is never placed in
    scenery.
    """
    tiles = [pb.memory[tilemap + i] for i in range(W * H)]

    def free(tx, ty):
        return 0 <= tx < W and 0 <= ty < H and tiles[ty * W + tx] in WALKABLE

    sides = (
        ("right", x * 8 - 16, y * 8 - 4, ((x - 2, y), (x - 1, y), (x - 2, y - 1), (x - 1, y - 1))),
        ("left", x * 8 + 8, y * 8 - 4, ((x + 1, y), (x + 2, y), (x + 1, y - 1), (x + 2, y - 1))),
        ("down", x * 8 - 4, y * 8 - 16, ((x, y - 2), (x, y - 1), (x - 1, y - 2), (x - 1, y - 1))),
        ("up", x * 8 - 4, y * 8 + 8, ((x, y + 1), (x, y + 2), (x - 1, y + 1), (x - 1, y + 2))),
    )
    def splash(button):
        # Cells the melee arc can reach besides the target: the body is two
        # tiles wide, so its arc also covers the neighbour beside the target.
        if button in ("right", "left"):
            return ((x, y - 1),)
        return ((x - 1, y),)

    def clean(side):
        return not any(0 <= cx < W and 0 <= cy < H and tiles[cy * W + cx] == PILLAR
                       for cx, cy in splash(side[0]))

    for button, px, py, body in sorted(sides, key=lambda s: not clean(s)):
        if not all(free(*c) for c in body):
            continue
        put16(pb, player + 9, px)
        put16(pb, player + 11, py)
        pb.button_press(button)
        pb.tick()
        pb.button_release(button)
        put16(pb, player + 9, px)
        put16(pb, player + 11, py)
        for i in range(frames):
            if i % 10 == 0:
                pb.button_press("a")
            elif i % 10 == 3:
                pb.button_release("a")
            pb.tick()
            if changed():
                pb.button_release("a")
                return button
        pb.button_release("a")
    return None
