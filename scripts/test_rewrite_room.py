#!/usr/bin/env python3
"""ROM regression: M2 Cairn Ford (material-rewrite switches).

Headless proof for the optional Ember Depths pocket that
  * it is generated with an always-open entrance reachable from the doors,
  * both rewrite previews (cairn, ford) are on screen before any switch use,
  * Switch B is a dud until Switch A has raised rock (refusal, no change),
  * stepping A from the foyer seals the alcove and stepping it again undoes it,
  * raising rock on the hero's own tiles is refused (never entombed),
  * the intended solve works: shoot A through the sill mouth from the alcove,
    step B, cross the fords to the vault goal,
  * an off-camera rewrite plays its cue once and blinks when it scrolls in,
  * Pack RESET ROOM works while sealed in, HP is never refunded,
  * the entrance plate resets the room, and it solves again after a reset,
  * no ordinary enemy is ever inside the pocket.
"""
import os
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from quintra_topology import rime_cell_candidates  # noqa: E402
import test_stage_archetypes as tsa  # noqa: E402

STAGE = 2
SEED = int(os.environ.get("RW_SEED", "0xCAFE1234"), 16)
CAPTURE = os.environ.get("RW_CAPTURE")
PUZZLE_REWRITE_ROOM = 8
X0, Y0, W, H = 18, 11, 12, 20
BGT_FLOOR, BGT_WALL = 1, 2
CAIRN = (98, 109, 110, 39)
FORD, CHASM, SILL = 107, 108, 105
SOLID = {2, 108} | set(CAIRN) | set(tsa.HARD_SCENERY)
REG = ((6, 4, SILL), (9, 10, CHASM), (5, 14, CHASM))

A = tsa.addr
RS, PL, EN = tsa.RS, tsa.PL, tsa.EN
LIVE, RA, RB, RESETS, BLINK, OFFCAM, REFUSE = (A(n) for n in (
    "_rw_live", "_rw_a", "_rw_b", "_rw_resets", "_rw_blink",
    "_rw_offcam_sfx", "_rw_refusals"))
CELL = A("_rime_cell")
KIND = A("_room_puzzle_kind")
SCREEN = A("_loop_current_screen")
FRAME = A("_loop_frame_counter")
SEL = A("_selected_tool")
CAMY = A("_room_camera_y")
TM, EXT, BOT = A("_room_tilemap"), A("_room_world_extension"), A("_room_world_bottom")
TOOL_RESET = 4
LAYOUT = [
    "############", "#.....##...#", "#.....##...#", "#.....##...#",
    "#.....FF...#", "#.....FF...#", "......##...#", "......##...#",
    "#R-.WW##...#", "#--.WW##...#", "#########CC#", "#########CC#",
    "#..........#", "#..........#", "#####CC#####", "#####CC#####",
    "#..........#", "#...GG.....#", "#..........#", "############",
]


def PX(lx):
    return (X0 + lx) * 8


def PY(ly):
    return (Y0 + ly) * 8


def foot(lx, ly):
    """Hero top-left that puts the foot point inside tile (lx, ly)."""
    return PX(lx) - 4, PY(ly) - 8


class Run:
    def __init__(self, pb):
        self.pb = pb
        self.frames = []
        self.intruders = 0
        self.hurts = 0

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

    def hp(self):
        return self.m(PL + 2)

    def tick(self, n=1):
        for _ in range(n):
            self.pb.tick()
            if self.m(SCREEN) == 5 and self.m(LIVE) and self.m(FRAME) % 8 == 4:
                if any(t == 2 and ex + 8 >= PX(-1) and ey + 8 >= PY(0)
                       for t, ex, ey in self.ents()):
                    self.intruders += 1
            if CAPTURE and self.m(FRAME) % 4 == 0 and len(self.frames) < 700:
                self.frames.append(self.pb.screen.image.copy())

    def walk(self, tx, ty, limit=400, axis_first="x", until=None):
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
                stall = stall + 1 if (x, y) == last else 0
                last = (x, y)
                if stall > 40:
                    break
        return self.pos()

    def go(self, lx, ly, axis_first="x"):
        """Walk until the foot point rests in tile (lx, ly); the hero keeps a
        little momentum after release, so re-aim a few times."""
        tx, ty = foot(lx, ly)
        for _ in range(5):
            self.walk(tx, ty, axis_first=axis_first)
            self.tick(6)
            x, y = self.pos()
            if (x + 8) // 8 == X0 + lx and (y + 12) // 8 == Y0 + ly:
                break
        return self.pos()

    def press(self, btn, held=5, rel=6):
        self.pb.button_press(btn)
        self.tick(held)
        self.pb.button_release(btn)
        self.tick(rel)

    def settle(self, n=30):
        self.tick(n)

    def fire_west(self):
        """Face west (one tap) and fire one shot."""
        self.pb.button_press("left")
        self.tick(1)
        self.pb.button_release("left")
        self.tick(1)
        self.press("a", held=3, rel=2)

    def pack(self, tool):
        self.pb.button_press("start")
        self.tick(5)
        self.pb.button_release("start")
        self.tick(6)
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


def reg_tiles(r, i):
    lx, ly, _ = REG[i]
    g = world_tiles(r.pb)
    return [g[Y0 + ly + dy][X0 + lx + dx] for dy in (0, 1) for dx in (0, 1)]


def check_layout(grid):
    for ly, row in enumerate(LAYOUT):
        for lx, c in enumerate(row):
            t = grid[Y0 + ly][X0 + lx]
            if c == "#":
                assert t == BGT_WALL, f"wall missing at {lx},{ly}: {t}"
            elif c == "C":
                assert t == CHASM, f"chasm bed missing at {lx},{ly}: {t}"
            elif c == "F":
                assert t == SILL, f"sill bed missing at {lx},{ly}: {t}"
    # Previews of both rewrite results, present before first use.
    prev_c = [grid[Y0 + 8][X0 + 1], grid[Y0 + 8][X0 + 2],
              grid[Y0 + 9][X0 + 1], grid[Y0 + 9][X0 + 2]]
    assert tuple(prev_c) == CAIRN, f"cairn preview missing {prev_c}"
    assert all(grid[Y0 + y][X0 + x] == FORD for x in (4, 5) for y in (8, 9))
    seen = {(X0 + 1, Y0 + 6)}
    q = deque(seen)
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < 31 and 0 <= ny < 31 and (nx, ny) not in seen \
                    and grid[ny][nx] not in SOLID:
                seen.add((nx, ny))
                q.append((nx, ny))
    edges = [p for p in seen if p[0] in (0, 30) or p[1] in (0, 30)]
    assert edges, "pocket entrance not reachable from any room edge"
    assert (X0 + 9, Y0 + 1) in seen, "alcove (Switch B) not reachable at rest"
    assert (X0 + 4, Y0 + 13) not in seen, "hall reachable before any rewrite"
    return len(edges)


def try_seed(seed):
    cands = rime_cell_candidates(seed, STAGE)
    if not cands:
        return None
    pb = tsa.generated_room(STAGE, seed, local_room=cands[0], keep_running=True)
    real = pb.memory[CELL]
    if real != cands[0] and real in cands:
        pb.stop(save=False)
        pb = tsa.generated_room(STAGE, seed, local_room=real, keep_running=True)
    if pb.memory[KIND] != PUZZLE_REWRITE_ROOM or pb.memory[LIVE] != 1:
        why = "altar owns the cell" if real == 0xFF else f"kind={pb.memory[KIND]}"
        print(f"  seed {seed:#x}: no pocket ({why})")
        pb.stop(save=False)
        return None
    return Run(pb), real


def open_room():
    """First seed (from RW_SEED) whose Ember floor hosts the pocket."""
    global SEED
    for k in range(12):
        seed = (SEED + k * 0x01010101) & 0xFFFFFFFF
        got = try_seed(seed)
        if got:
            SEED = seed
            return got
    raise AssertionError("no seed in 12 hosted Cairn Ford")


def wait(r, cond, n=90):
    for _ in range(n):
        if cond():
            return True
        r.tick()
    return cond()


def shot_at(r, lx, ly):
    """Drop one player projectile onto a plate (class-agnostic)."""
    free = next(i for i in range(32) if not r.m(EN + i * 28 + 1) & 1)
    e = EN + free * 28
    for k in range(28):
        r.pb.memory[e + k] = 0
    r.pb.memory[e] = 1                       # ENT_PROJECTILE
    tsa.put16(r.pb, e + 3, PX(lx) + 4)
    tsa.put16(r.pb, e + 7, PY(ly) + 4)
    r.pb.memory[e + 14] = 1
    r.pb.memory[e + 16] = 30
    r.pb.memory[e + 25] = 0x44
    r.pb.memory[e + 26] = 1
    r.pb.memory[e + 1] = 0x11                # ACTIVE | PLAYER_PROJ
    return e


def into_alcove(r):
    r.go(4, 6)
    r.go(4, 5, axis_first="y")
    r.go(9, 5)                               # through F1 (sill) into the alcove
    assert r.pos()[0] >= foot(9, 5)[0] - 1, f"sill mouth blocked pos={r.pos()}"


def twin_a(r):
    """Step the alcove twin of Switch A (9..10, 6..7)."""
    before = r.m(RA)
    r.go(9, 6, axis_first="y")
    return wait(r, lambda: r.m(RA) != before, 60)


def still(r, name):
    if CAPTURE and not (Path(CAPTURE) / f"{name}.png").exists():
        Path(CAPTURE).mkdir(parents=True, exist_ok=True)
        r.pb.screen.image.copy().resize((640, 576), 0).save(Path(CAPTURE) / f"{name}.png")


def solve_route(r):
    """Entrance -> sill mouth -> alcove -> twin A (seals) -> B -> fords -> goal."""
    into_alcove(r)
    still(r, "state0_beds")
    sfx0 = r.m(OFFCAM)
    assert twin_a(r), f"twin Switch A did not toggle pos={r.pos()}"
    assert r.m(RA) == 1 and r.m(RB) == 0
    r.settle(10)
    assert tuple(reg_tiles(r, 0)) == CAIRN, f"F1 not raised {reg_tiles(r, 0)}"
    assert tuple(reg_tiles(r, 1)) == CAIRN, f"C1 not raised {reg_tiles(r, 1)}"
    assert r.m(OFFCAM) == sfx0 + 1, f"off-camera cue count {sfx0}->{r.m(OFFCAM)} camy={r.m(CAMY)}"
    assert r.m(BLINK) & 4, f"C2 not pending a blink (blink={r.m(BLINK)}, camy={r.m(CAMY)})"
    r.settle(20)
    still(r, "state1_cairns")
    r.go(9, 1, axis_first="y")              # step Switch B: rock -> ford
    assert wait(r, lambda: r.m(RB) == 1), "Switch B did not toggle"
    r.settle(10)
    for i in (0, 1):
        assert reg_tiles(r, i) == [FORD] * 4, f"region {i} not ford {reg_tiles(r, i)}"
    r.settle(10)
    still(r, "state2_fords")
    ref0 = r.m(REFUSE)
    r.walk(PX(8) - 1, foot(9, 1)[1])         # west lane of the alcove, off the twin
    r.walk(PX(8) - 1, foot(9, 9)[1], axis_first="y")
    r.go(9, 9)
    r.walk(*foot(9, 12), axis_first="y")
    assert r.pos()[1] >= foot(9, 12)[1] - 1, f"C1 ford not walkable pos={r.pos()}"
    r.go(5, 13)
    blink_seen = not (r.m(BLINK) & 4)
    for _ in range(12):
        r.tick()
        if r.m(BLINK) & 4 == 0:
            still(r, "state3_blink"); break
    r.walk(*foot(5, 16), axis_first="y")
    r.tick(20)
    blink_seen = blink_seen or not (r.m(BLINK) & 4)
    assert reg_tiles(r, 2) == [FORD] * 4, f"C2 not ford {reg_tiles(r, 2)}"
    r.go(4, 17)
    r.tick(4)
    if not r.m(RS + 27) & 0x20:
        print(f"    goal miss pos={r.pos()} want={foot(4, 17)}")
    if r.m(REFUSE) != ref0:
        print(f"    note: {r.m(REFUSE) - ref0} refusals on the walk")
    return bool(r.m(RS + 27) & 0x20), blink_seen


def main():
    r, cell = open_room()
    edges = check_layout(world_tiles(r.pb))
    hp0 = r.hp()
    r.set_pos(PX(-3), foot(0, 6)[1])
    r.tick(2)
    print(f"  layout + previews OK (seed {SEED:#x}, cell {cell}, edges reachable {edges})")

    # --- Switch B is a dud before A: walk round via the sill and step it.
    r.go(4, 6)
    r.go(4, 5, axis_first="y")
    r.go(9, 5)
    r.go(9, 1, axis_first="y")
    r.tick(4)
    assert r.m(RB) == 0 and r.m(REFUSE) == 1, f"B not a dud (b={r.m(RB)} ref={r.m(REFUSE)})"
    print("  Switch B dud before A OK")

    # --- refuse-if-occupied: stand on the sill bed, shoot A.
    r.go(9, 5, axis_first="y")
    r.go(7, 5)
    r.settle(25)
    shot_at(r, 1, 4)                        # a player shot onto Switch A
    r.tick(30)
    assert r.m(RA) == 0, (f"A raised rock onto the hero pos={r.pos()} "
                          f"want={foot(7, 5)} ref={r.m(REFUSE)} f1={reg_tiles(r, 0)}")
    assert r.m(REFUSE) == 2, f"no refusal while occupied ({r.m(REFUSE)})"
    print("  raise-onto-hero refused OK")

    # --- seal from the foyer, then undo by stepping A again.
    r.go(4, 5)
    r.settle(25)
    r.go(2, 5)                              # onto Switch A (1..2, 4..5)
    assert wait(r, lambda: r.m(RA) == 1), "foyer step did not raise A"
    r.settle(40)
    assert tuple(reg_tiles(r, 0)) == CAIRN
    r.go(4, 5)
    r.settle(25)
    r.go(2, 5)
    assert wait(r, lambda: r.m(RA) == 0), "second step did not undo A"
    r.settle(30)
    assert reg_tiles(r, 0) == [SILL] * 4, f"undo left {reg_tiles(r, 0)}"
    print("  foyer seal + undo OK (no softlock)")

    ok, blink = solve_route(r)
    assert ok, f"fresh solve failed pos={r.pos()} hp={r.hp()}"
    assert blink, "off-camera region never blinked on arrival"
    print(f"  fresh solve OK (twin A seals the alcove, step B, fords; offcam cues {r.m(OFFCAM)}, "
          f"blink on arrival; hurts {r.hurts}, hp {hp0}->{r.hp()})")

    # --- Pack reset from the vault.
    hp1 = r.hp()
    r.pack(TOOL_RESET)
    assert r.pos() == (PX(1), PY(5)), f"reset did not warp hero {r.pos()}"
    assert r.m(RESETS) == 1 and r.m(RA) == 0 and r.m(RB) == 0
    assert r.hp() == hp1, "reset refunded HP"
    r.settle(10)
    for i in range(3):
        assert reg_tiles(r, i) == [REG[i][2]] * 4, f"reset left region {i} {reg_tiles(r, i)}"
    # --- sealed in the alcove by the twin A, then Pack reset.
    into_alcove(r)
    assert twin_a(r) and r.m(RA) == 1
    r.settle(20)
    assert tuple(reg_tiles(r, 0)) == CAIRN
    hp2 = r.hp()
    r.pack(TOOL_RESET)
    assert r.m(RESETS) == 2 and r.m(RA) == 0 and r.m(RB) == 0
    assert r.pos() == (PX(1), PY(5)), f"sealed reset pos {r.pos()}"
    assert r.hp() == hp2, "sealed reset refunded HP"
    print("  Pack reset OK (from vault and sealed alcove; hp kept)")

    # --- entrance plate reset (raise A first so there is state to undo).
    r.settle(25)
    r.go(4, 6)
    r.go(4, 5, axis_first="y")
    r.settle(25)
    r.go(2, 5)
    assert wait(r, lambda: r.m(RA) == 1), "A did not raise before plate test"
    r.settle(30)
    r.go(4, 5)
    r.walk(*foot(4, 2), axis_first="y",     # onto the reset plate (3..4, 1..2)
           until=lambda: r.m(RESETS) != 2)
    assert wait(r, lambda: r.m(RESETS) == 3, 30), f"entrance plate no reset ({r.m(RESETS)})"
    assert r.m(RA) == 0
    print("  entrance plate reset OK")

    # --- solvable again after reset (re-arm the goal for the walk check).
    r.pb.memory[RS + 27] &= ~0x20 & 0xFF
    r.settle(30)
    ok2, _ = solve_route(r)
    assert ok2, f"solve after reset failed pos={r.pos()}"
    assert r.intruders == 0, f"enemies inside the pocket {r.intruders}x"
    assert r.hp() >= 1
    print(f"  solve after reset OK; no intruders; final hp {r.hp()}")

    if CAPTURE:
        out = Path(CAPTURE)
        out.mkdir(parents=True, exist_ok=True)
        fr = [f.resize((640, 576), 0) for f in r.frames[::2]]
        if fr:
            fr[0].save(out / "rewrite_room_4x.gif", save_all=True,
                       append_images=fr[1:], duration=66, loop=0)
            fr[len(fr) // 2].save(out / "rewrite_room_4x.png")
        print(f"  capture: {len(fr)} frames -> {out}")
    r.pb.stop(save=False)
    print("test_rewrite_room OK")


if __name__ == "__main__":
    main()
