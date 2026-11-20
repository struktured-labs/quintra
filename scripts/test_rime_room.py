#!/usr/bin/env python3
"""ROM regression: M1 Rime chamber (Rime Pipes + Stone Jagger).

Headless proof for the optional Verdant Hollow chamber that
  * it is generated with an always-open entrance reachable from the doors,
  * it can be solved from fresh by walking the intended route,
  * Pack RESET ROOM works while the hero is pinned against the Jagger,
  * the entrance plate resets the room, HP/charges spent are never refunded,
  * it can be solved again after a reset, and
  * the Jagger never leaves its lane (it can never rest on the entrance,
    the foyer, the plate, or the reset path) and is untouched by shots.
"""
import os
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from quintra_topology import rime_cell_candidates  # noqa: E402
import test_stage_archetypes as tsa  # noqa: E402

STAGE = 1
SEED = int(os.environ.get("RIME_SEED", "0xCAFE1234"), 16)
CAPTURE = os.environ.get("RIME_CAPTURE")  # directory for 4x PNG/GIF
PUZZLE_RIME_ROOM = 7
X0, Y0, W, H = 21, 15, 9, 14
BGT_FLOOR, BGT_WALL = 1, 2

A = tsa.addr
RS, PL, EN = tsa.RS, tsa.PL, tsa.EN
LIVE, CELL, CHARGE, FREEZE = (A(n) for n in (
    "_rime_live", "_rime_cell", "_rime_charge", "_room_freeze_beats"))
JX, JY, HOLD, RESETS = (A(n) for n in (
    "_rime_jx", "_rime_jy", "_rime_jagger_hold", "_rime_resets"))
KIND = A("_room_puzzle_kind")
SCREEN = A("_loop_current_screen")
FRAME = A("_loop_frame_counter")
SEL = A("_selected_tool")
TM, EXT, BOT = A("_room_tilemap"), A("_room_world_extension"), A("_room_world_bottom")
TOOL_PIPES, TOOL_RESET = 4, 5
LAYOUT = [
    "#########", "#.......#", "#....SS.#", "#.......#", "######..#",
    "#.......#", "#.......#", "#..######", "#.......#", "........#",
    "........#", "#.......#", "#.......#", "#########",
]


def PX(lx):
    return (X0 + lx) * 8


def PY(ly):
    return (Y0 + ly) * 8


LANE = (PX(1), PY(5), PX(6), PY(5))   # Jagger top-left legal rect


class Run:
    def __init__(self, pb):
        self.pb = pb
        self.frames = []
        self.lane_violations = 0
        self.hurts = 0
        self.intruders = 0

    # -- memory --------------------------------------------------------
    def m(self, a):
        return self.pb.memory[a]

    def pos(self):
        mem = self.pb.memory
        return (mem[PL + 9] | mem[PL + 10] << 8, mem[PL + 11] | mem[PL + 12] << 8)

    def set_pos(self, x, y):
        tsa.put16(self.pb, PL + 9, x)
        tsa.put16(self.pb, PL + 11, y)

    def ents(self):
        out = []
        for i in range(32):
            e = EN + i * 28
            if self.m(e + 1) & 1:
                out.append((self.m(e), self.m(e + 3) | self.m(e + 4) << 8,
                            self.m(e + 7) | self.m(e + 8) << 8))
        return out

    def near(self):
        px, py = self.pos()
        return [t for t in self.ents()
                if abs(t[1] - px) < 40 and abs(t[2] - py) < 40]

    def hp(self):
        return self.m(PL + 2)

    def tick(self, n=1):
        for _ in range(n):
            self.pb.tick()
            if self.m(SCREEN) == 5 and self.m(LIVE):
                jx, jy = self.m(JX), self.m(JY)
                if not (LANE[0] <= jx <= LANE[2] and jy == LANE[1]):
                    self.lane_violations += 1
                if self.m(FRAME) % 8 == 4 and any(
                        typ == 2 and ex + 8 >= PX(-1) and PY(0) <= ey + 8 < PY(H)
                        for typ, ex, ey in self.ents()):
                    self.intruders += 1
            if CAPTURE and self.m(FRAME) % 4 == 0 and len(self.frames) < 600:
                self.frames.append(self.pb.screen.image.copy())

    # -- movement --------------------------------------------------------
    def walk(self, tx, ty, limit=400, axis_first="x", until=None):
        """Hold the d-pad until the hero reaches (tx, ty) or stalls."""
        for axis in ((axis_first, "y" if axis_first == "x" else "x")):
            stall, last = 0, None
            for _ in range(limit):
                x, y = self.pos()
                cur, tgt = (x, tx) if axis == "x" else (y, ty)
                if cur == tgt or (until is not None and until()):
                    break
                btn = (("right" if tgt > cur else "left") if axis == "x"
                       else ("down" if tgt > cur else "up"))
                self.pb.button_press(btn)
                hp0 = self.hp()
                self.tick()
                self.pb.button_release(btn)
                if self.hp() < hp0:
                    self.hurts += 1
                    print(f"    hurt at {(x, y)} -> {(tx, ty)} freeze={self.m(FREEZE)} "
                          f"j=({self.m(JX)},{self.m(JY)}) hold={self.m(HOLD)} ents={self.near()}")
                stall = stall + 1 if (x, y) == last else 0
                last = (x, y)
                if stall > 40:
                    break
        return self.pos()

    # -- Pack ------------------------------------------------------------
    def press(self, btn, held=5, rel=6):
        self.pb.button_press(btn)
        self.tick(held)
        self.pb.button_release(btn)
        self.tick(rel)

    def pack(self, tool):
        trace = []
        self.pb.button_press("start")
        for _ in range(5):
            self.tick(); trace.append(self.m(SCREEN))
        self.pb.button_release("start")
        for _ in range(6):
            self.tick(); trace.append(self.m(SCREEN))
        if os.environ.get("RIME_TRACE"):
            print("pack trace", trace)
        assert self.m(SCREEN) == 9, "START did not open the Pack"
        f0 = self.m(FRAME)
        for _ in range(240):
            if self.m(FRAME) != f0:
                break
            self.tick()
        for _ in range(8):
            if self.m(SEL) == tool:
                break
            self.press("left")
        assert self.m(SEL) == tool, f"Pack focus {self.m(SEL)} != {tool}"
        assert self.m(SCREEN) == 9, f"Pack closed early {trace}"
        self.pb.button_press("a")
        self.tick(5)
        self.pb.button_release("a")
        resume = None
        for _ in range(300):
            self.tick()
            if self.m(SCREEN) == 5 and resume is None:
                resume = self.m(FRAME)
            elif resume is not None and self.m(FRAME) != resume \
                    and self.pb.memory[0xFF40] & 0x80:
                break
        self.tick(2)
        assert self.m(SCREEN) == 5, "Pack did not resume the room"


def world_tiles(pb):
    mem = pb.memory
    grid = [[0] * 31 for _ in range(31)]
    for y in range(31):
        for x in range(31):
            if y < 17:
                grid[y][x] = mem[TM + y * 20 + x] if x < 20 else mem[EXT + y * 11 + x - 20]
            else:
                grid[y][x] = mem[BOT + (y - 17) * 31 + x]
    return grid


def check_layout(grid):
    for ly, row in enumerate(LAYOUT):
        for lx, c in enumerate(row):
            t = grid[Y0 + ly][X0 + lx]
            if c == "#":
                assert t == BGT_WALL, f"chamber wall missing at {lx},{ly}: {t}"
            else:
                assert t != BGT_WALL, f"chamber floor blocked at {lx},{ly}"
    # Entrance reachable from every open room edge (BFS on walkable tiles).
    walk = lambda t: t not in tsa.HARD_SCENERY and t != BGT_WALL  # noqa: E731
    start = (X0 + 1, Y0 + 9)
    seen, q = {start}, deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < 31 and 0 <= ny < 31 and (nx, ny) not in seen \
                    and walk(grid[ny][nx]):
                seen.add((nx, ny))
                q.append((nx, ny))
    edges = [p for p in seen if p[0] in (0, 30) or p[1] in (0, 30)]
    if not edges and os.environ.get("RIME_DUMP"):
        with open(os.environ["RIME_DUMP"], "w") as fh:
            for y in range(31):
                fh.write(" ".join(("*" if (x, y) in seen else "") + f"{grid[y][x]:02x}"
                                  for x in range(31)) + "\n")
    assert edges, "chamber entrance not reachable from any room edge"
    for gx, gy in ((X0 + 5, Y0 + 2), (X0 + 1, Y0 + 11), (X0 + 5, Y0 + 8)):
        assert (gx, gy) in seen, f"chamber tile {gx},{gy} unreachable"
    return len(edges)


def enter(cell):
    pb = tsa.generated_room(STAGE, SEED, local_room=cell, keep_running=True)
    return pb


def open_room():
    cands = rime_cell_candidates(SEED, STAGE)
    assert cands, "no Rime candidate cell"
    pb = enter(cands[0])
    real = pb.memory[CELL]
    if real != cands[0]:
        assert real in cands, f"_rime_cell {real} not a mirrored candidate"
        pb.stop(save=False)
        pb = enter(real)
    assert pb.memory[KIND] == PUZZLE_RIME_ROOM, (
        f"room_puzzle_kind={pb.memory[KIND]} (cell {real})")
    assert pb.memory[LIVE] == 1
    return Run(pb), real


def to_entrance(r):
    """Stand on the open apron outside the west entrance (BFS-proven)."""
    r.set_pos(PX(-3), PY(9))
    r.tick(2)
    r.walk(PX(3), PY(9))
    assert r.m(CHARGE) == 0


def solve_route(r):
    """Foyer pedestal -> foyer gap -> Pipes -> lane -> vault gap -> goal."""
    r.walk(PX(4), PY(8))
    assert r.m(CHARGE) == 1, f"foyer pedestal gave no charge pos={r.pos()}"
    r.walk(PX(1), PY(7) - 1)
    r.pack(TOOL_PIPES)
    assert r.m(CHARGE) == 0 and r.m(FREEZE) > 0, f"Pipes did not freeze charge={r.m(CHARGE)} freeze={r.m(FREEZE)} sel={r.m(SEL)} live={r.m(LIVE)} resets={r.m(RESETS)} pos={r.pos()} hp={r.hp()}"
    jx0 = r.m(JX)
    r.walk(PX(1), PY(5) - 8, axis_first="y")
    r.walk(PX(6), PY(5) - 8)
    assert r.m(JX) == jx0, "frozen Jagger moved"
    r.walk(PX(6), PY(2) - 8, axis_first="y")
    r.walk(PX(5), PY(2) - 8)
    return bool(r.m(RS + 27) & 0x20)


def shot_absorbed(r):
    """A player shot that overlaps the Jagger is eaten: no flash, no HP."""
    free = next(i for i in range(32) if not r.m(EN + i * 28 + 1) & 1)
    e = EN + free * 28
    for k in range(28):
        r.pb.memory[e + k] = 0
    jx, jy = r.m(JX), r.m(JY)
    r.pb.memory[e] = 1                       # ENT_PROJECTILE
    tsa.put16(r.pb, e + 3, jx + 4)
    tsa.put16(r.pb, e + 7, jy + 4)
    r.pb.memory[e + 14] = 1                  # pierce
    r.pb.memory[e + 16] = 60                 # lifetime
    r.pb.memory[e + 25] = 0x44
    r.pb.memory[e + 26] = 4
    r.pb.memory[e + 1] = 0x11                # ACTIVE | PLAYER_PROJ
    r.tick(3)
    assert not r.m(e + 1) & 1, "shot passed through the Jagger"
    assert LANE[0] <= r.m(JX) <= LANE[2] and r.m(JY) == LANE[1]
    print("  Jagger absorbed a player shot")


def main():
    r, cell = open_room()
    if os.environ.get("RIME_TRACE"):
        for name in ("_rime_use_pipes", "_dungeon_tools_apply_pending", "_rime_pack_a", "_rime_reset"):
            ad = A(name)
            bank = ad >> 16
            r.pb.hook_register(bank, ad & 0xFFFF, lambda ctx: print("HOOK", ctx, "charge", r.m(CHARGE)), name)
    edges = check_layout(world_tiles(r.pb))
    hp0 = r.hp()
    to_entrance(r)
    assert r.m(JX) in range(LANE[0], LANE[2] + 1)
    shot_absorbed(r)
    ok1 = solve_route(r)
    assert ok1, f"fresh solve failed pos={r.pos()} hp={r.hp()}"
    hp_solved = r.hp()
    print(f"  fresh solve OK (cell {cell}, edges reachable {edges}, "
          f"hurts {r.hurts}, hp {hp0}->{hp_solved})")

    # --- pinned reset: spent charge, standing in the lane on the Jagger.
    while r.m(FREEZE):
        r.tick()
    r.set_pos(PX(3), PY(5) - 8)
    r.pb.memory[PL + 15] = 200          # i-frames: stays pinned, no shove
    r.tick(60)
    hp_pin = r.hp()
    r.pack(TOOL_RESET)
    x, y = r.pos()
    assert (x, y) == (PX(1), PY(9)), f"reset did not warp hero: {(x, y)}"
    assert r.m(RESETS) == 1 and r.m(CHARGE) == 0 and r.m(FREEZE) == 0
    assert r.m(JX) == PX(4) and r.m(JY) == PY(5)
    assert r.hp() == hp_pin, "reset refunded HP"
    print(f"  pinned Pack reset OK (hp kept {hp_pin})")

    # --- spend a charge, strand it mid-lane, then the entrance plate.
    r.walk(PX(4), PY(8))
    r.walk(PX(1), PY(7) - 1)
    r.pack(TOOL_PIPES)
    while r.m(FREEZE):
        r.tick()
    hp_before = r.hp()
    r.walk(PX(1), PY(11), axis_first="y",       # onto the reset plate
           until=lambda: r.m(RESETS) != 1)
    r.tick(4)
    assert r.m(RESETS) == 2, f"entrance plate did not reset ({r.m(RESETS)})"
    assert r.hp() <= hp_before, "plate reset refunded HP"
    print(f"  entrance plate reset OK")

    # --- after reset: solvable again (re-arm the goal for the walk check).
    r.pb.memory[RS + 27] &= ~0x20 & 0xFF
    r.walk(PX(3), PY(10))
    r.tick(35)                                  # Jagger hold elapses
    ok2 = solve_route(r)
    assert ok2, f"solve after reset failed pos={r.pos()}"
    print(f"  solve after reset OK (hurts {r.hurts})")

    # --- return trip: vault pedestal always re-arms, so the vault is no trap.
    while r.m(FREEZE):
        r.tick()
    r.walk(PX(1), PY(2) - 8)
    assert r.m(CHARGE) == 1, "vault pedestal gave no return charge"
    r.pack(TOOL_PIPES)
    r.walk(PX(6), PY(5) - 8, axis_first="x")
    r.walk(PX(1), PY(5) - 8)
    r.walk(PX(1), PY(9), axis_first="y")
    r.walk(PX(-2), PY(9))
    assert r.pos()[0] < PX(0), f"could not walk back out pos={r.pos()}"
    assert r.m(CHARGE) == 0, "charge survived leaving the chamber"
    assert r.intruders == 0, f"enemies inside the chamber {r.intruders}x"
    assert r.lane_violations == 0, f"Jagger left its lane {r.lane_violations}x"
    assert r.hp() >= 1
    print(f"  return trip OK; Jagger stayed in lane; final hp {r.hp()}")

    if CAPTURE:
        out = Path(CAPTURE)
        out.mkdir(parents=True, exist_ok=True)
        fr = [f.resize((640, 576), 0) for f in r.frames[::2]]
        if fr:
            fr[0].save(out / "rime_room_4x.gif", save_all=True,
                       append_images=fr[1:], duration=66, loop=0)
            fr[len(fr) // 3].save(out / "rime_room_4x.png")
        print(f"  capture: {len(fr)} frames -> {out}")
    r.pb.stop(save=False)
    print("test_rime_room OK")


if __name__ == "__main__":
    main()
