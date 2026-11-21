#!/usr/bin/env python3
"""ROM regression: M4 Lockmire Ferry (matching keys, flip-conveyor, lure).

Headless proof for the optional Toxic Mire pocket that
  * it is generated with an always-open entrance reachable from the doors,
    the ferry hall and vault sealed by locked doors, both belt directions
    visible before the first flip, and its borrowed tile ids nowhere else;
  * keys: a Heart key is refused (and kept) at the Star door, the Star key
    opens it; one of each type at a time (cap refusal); the single Heart key
    buys one of two Heart doors (closet with the Moon key, or the vault);
  * the lure: refused outside the ferry hall drop zone, dropped inside it
    wakes the Stone Jagger, which struggles on the east-running belt; the
    flip plate turns the belt west, the Jagger rides onto the weight plate,
    the gate opens (off camera: one cue, a blink on arrival);
  * the Moon door pays its coin once per build, never again after a reset;
  * Pack RESET ROOM (from the Moon nook, and while pinned on the belt), the
    entrance plate, and walking out all restore keys to their pedestals,
    relock doors, home the Jagger; HP kept; it solves after resets;
  * the Jagger never leaves its lane rows; no ordinary enemy is inside;
    the hero is never hurt.
Every hero can solve it: everything is stepped or chosen in the Pack.
"""
import os
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from quintra_topology import rime_cell_candidates  # noqa: E402
import test_stage_archetypes as tsa  # noqa: E402

STAGE = 4
SEED = int(os.environ.get("LK_SEED", "0xCAFE1234"), 16)
CAPTURE = os.environ.get("LK_CAPTURE")
PUZZLE_LOCK_ROOM = 10
X0, Y0, W, H = 18, 11, 12, 18
BGT_FLOOR, BGT_WALL = 1, 2
CONV_E, CONV_W, WPLATE, WPRESS, DOOR, BARS = 105, 106, 107, 96, 37, 99
OURS = {CONV_E, CONV_W, WPLATE, WPRESS, DOOR, BARS}
SOLID = {2, DOOR, BARS} | set(tsa.HARD_SCENERY)
HEART, STAR, MOON = 1, 2, 4
J_IDLE, J_SEEK, J_SETTLED = 0, 1, 2
TOOL_LURE, TOOL_RESET = 4, 5

A = tsa.addr
RS, PL, EN = tsa.RS, tsa.PL, tsa.EN
(LIVE, HELD, PED, OPEN, DIR, GATE, WP, LURE, LX, LY, JX, JY, JST, COOL,
 RESETS, REFUSE, COINS, BLINK, OFFCAM, DROPS) = (A("_lk_" + n) for n in (
    "live", "held", "ped", "open", "dir", "gate", "wpress", "lure", "lx", "ly",
    "jx", "jy", "jst", "cool", "resets", "refusals", "coins", "blink",
    "offcam_sfx", "drops"))
CELL = A("_rime_cell")
KIND = A("_room_puzzle_kind")
SCREEN = A("_loop_current_screen")
FRAME = A("_loop_frame_counter")
SEL = A("_selected_tool")
TM, EXT, BOT = A("_room_tilemap"), A("_room_world_extension"), A("_room_world_bottom")
LAYOUT = [
    "############", "#......#...#", "#......#...#", "#......##..#",
    "#..........#", "#..........#", "...........#", "...........#",
    "############", "#........###", "#........###", "#..........#",
    "#..........#", "#........pp#", "#==######==#", "#..........#",
    "#........GG#", "############",
]


def PX(lx):
    return (X0 + lx) * 8


def PY(ly):
    return (Y0 + ly) * 8


# Hero positions: feet centre tile (lx, ly) -> (PX(lx)-4, PY(ly)-8).
def fx(lx):
    return PX(lx) - 4


def fy(ly):
    return PY(ly) - 8


ANTE_Y = PY(15) - 4          # body inside rows 15..16 (one-tile Heart doors)
GAP = PX(5)                  # body inside cols 5..6 (Star door, gate)


class Run:
    def __init__(self, pb):
        self.pb = pb
        self.frames = []
        self.intruders = 0
        self.lane_bad = 0
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
            hp0 = self.hp()
            self.pb.tick()
            if self.m(SCREEN) == 5 and self.hp() < hp0:
                self.hurts += 1
                self.hurt_at = getattr(self, "hurt_at", []) + [
                    (self.pos()[0] - PX(0), self.pos()[1] - PY(0), self.m(FRAME))]
            if self.m(SCREEN) == 5 and self.m(LIVE):
                if not (PY(11) - 8 <= self.m(JY) <= PY(11) and PX(1) <= self.m(JX) <= PX(9)):
                    self.lane_bad += 1
                cur = {}
                for i in range(32):
                    e = EN + i * 28
                    if self.m(e + 1) & 1 and self.m(e) == 2:
                        cur[i] = (self.m(e + 3) | self.m(e + 4) << 8,
                                  self.m(e + 7) | self.m(e + 8) << 8, self.m(e + 17), self.m(e + 15))
                prev = getattr(self, "prev", {})
                self.prev = cur
                raw = {i: (self.m(EN + i * 28), self.m(EN + i * 28 + 1), self.m(EN + i * 28 + 17),
                           (self.m(EN + i * 28 + 3) | self.m(EN + i * 28 + 4) << 8) - PX(0),
                           (self.m(EN + i * 28 + 7) | self.m(EN + i * 28 + 8) << 8) - PY(0))
                       for i in range(32)}
                rawprev = getattr(self, "rawprev", {})
                self.rawprev = raw
                bad = [(i, ex - PX(0), ey - PY(0), eid, st, prev.get(i), rawprev.get(i), self.m(RS + 27))
                       for i, (ex, ey, eid, st) in cur.items()
                       if ex + 8 >= PX(-1) and PY(0) <= ey + 8 < PY(H)]
                if self.m(FRAME) % 8 == 4 and bad and getattr(self, 'armed', False):
                    self.intruders += 1
                    if not hasattr(self, "first_bad"):
                        self.first_bad = (bad, (self.pos()[0] - PX(0), self.pos()[1] - PY(0)))
            if CAPTURE and self.m(FRAME) % 4 == 0 and len(self.frames) < 1400:
                self.frames.append(self.pb.screen.image.copy())

    def walk(self, tx, ty, limit=500, axis_first="x", until=None):
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
                self.tick()
                self.pb.button_release(btn)
                stall = stall + 1 if (x, y) == last else 0
                last = (x, y)
                if stall > 30:
                    break
        self.tick(2)
        return self.pos()

    def wx(self, tx):
        return self.walk(tx, self.pos()[1], axis_first="x")

    def wy(self, ty):
        return self.walk(self.pos()[0], ty, axis_first="y")

    def press(self, btn, held=5, rel=6):
        self.pb.button_press(btn)
        self.tick(held)
        self.pb.button_release(btn)
        self.tick(rel)

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
        for _ in range(10):
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


def t(r, lx, ly):
    return world_tiles(r.pb)[Y0 + ly][X0 + lx]


def bfs(grid, start):
    seen, q = {start}, deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < 31 and 0 <= ny < 31 and (nx, ny) not in seen \
                    and grid[ny][nx] not in SOLID:
                seen.add((nx, ny))
                q.append((nx, ny))
    return seen


def doors_locked(g):
    cells = [(5, 8), (6, 8), (9, 3), (10, 3), (3, 15), (3, 16), (8, 15), (8, 16)]
    return all(g[Y0 + y][X0 + x] == DOOR for x, y in cells)


def check_layout(grid):
    regions = {(5, 8), (6, 8), (9, 3), (10, 3), (3, 15), (3, 16), (8, 15), (8, 16),
               (5, 14), (6, 14)}
    for ly, row in enumerate(LAYOUT):
        for lx, c in enumerate(row):
            v = grid[Y0 + ly][X0 + lx]
            if (lx, ly) in regions:
                continue
            if c == "#":
                assert v == BGT_WALL, f"wall missing at {lx},{ly}: {v}"
            elif c == "=":
                assert v == BARS, f"window missing at {lx},{ly}: {v}"
            elif c == "p":
                assert v == CONV_W, f"fixed west belt missing at {lx},{ly}: {v}"
            elif c == ".":
                assert v not in SOLID, f"floor blocked at {lx},{ly}: {v}"
    assert doors_locked(grid), "doors not locked at entry"
    assert all(grid[Y0 + y][X0 + x] == CONV_E for x in range(3, 9) for y in (11, 12)), \
        "lane is not the east belt"
    assert grid[Y0 + 14][X0 + 5] == BARS and grid[Y0 + 14][X0 + 6] == BARS, "gate not shut"
    assert all(grid[Y0 + y][X0 + x] == WPLATE for x in (1, 2) for y in (11, 12))
    seen = bfs(grid, (X0 + 1, Y0 + 6))
    edges = [p for p in seen if p[0] in (0, 30) or p[1] in (0, 30)]
    assert edges, "pocket entrance not reachable from any room edge"
    assert (X0 + 4, Y0 + 1) in seen and (X0 + 8, Y0 + 5) in seen
    assert (X0 + 2, Y0 + 10) not in seen, "ferry hall reachable with the Star door shut"
    assert (X0 + 9, Y0 + 16) not in seen and (X0 + 9, Y0 + 1) not in seen
    stray = [(x, y, grid[y][x]) for y in range(31) for x in range(31)
             if grid[y][x] in OURS and not (X0 <= x < X0 + W and Y0 <= y < Y0 + H)]
    assert not stray, f"pocket tile ids outside the pocket: {stray[:4]}"
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
    if pb.memory[KIND] != PUZZLE_LOCK_ROOM or pb.memory[LIVE] != 1:
        why = "altar owns the cell" if real == 0xFF else f"kind={pb.memory[KIND]}"
        print(f"  seed {seed:#x}: no pocket ({why})")
        pb.stop(save=False)
        return None
    return Run(pb), real


def open_room():
    global SEED
    for k in range(12):
        seed = (SEED + k * 0x01010101) & 0xFFFFFFFF
        got = try_seed(seed)
        if got:
            SEED = seed
            return got
    raise AssertionError("no seed in 12 hosted the Lockmire Ferry")


def wait(r, cond, n=90):
    for _ in range(n):
        if cond():
            return True
        r.tick()
    return cond()


def still(r, name):
    if CAPTURE and not (Path(CAPTURE) / f"{name}.png").exists():
        Path(CAPTURE).mkdir(parents=True, exist_ok=True)
        r.pb.screen.image.copy().resize((640, 576), 0).save(Path(CAPTURE) / f"{name}.png")


# ---- routes (entry hall feet row 4 is the safe east-west street) ----
def heart_key(r):
    r.wy(fy(4))
    r.wx(fx(4))
    r.wy(fy(1))
    r.wx(fx(3))                                   # feet on the Heart pedestal
    r.tick(3)
    r.wy(fy(4))


def star_key(r):
    r.wy(fy(4))
    r.wx(GAP)
    r.wy(fy(1))                                   # feet (6,1): Star pedestal
    r.tick(3)
    r.wy(fy(4))


def lure_take(r):
    # Row 6 street: feet row 4 at col 8 would bump the Moon door.
    r.wy(fy(4))
    r.wx(fx(5))
    r.wy(fy(6))
    r.wx(fx(8))
    r.tick(3)
    r.wx(fx(5))
    r.wy(fy(4))


def star_door_down(r):
    r.wy(fy(4))
    r.wx(GAP)
    r.wy(PY(8) - 16)                              # touch the Star door
    r.tick(3)


def to_ferry(r):
    star_door_down(r)
    assert r.m(OPEN) & 1, f"Star door did not open (held={r.m(HELD)})"
    r.wy(fy(10))


def drop_lure(r):
    r.wx(fx(2))
    r.pack(TOOL_LURE)
    r.tick(3)
    assert r.m(LURE) == 2 and r.m(LX) == PX(2) and r.m(LY) == PY(9), \
        f"lure not dropped ({r.m(LURE)} {r.m(LX)},{r.m(LY)})"
    assert r.m(JST) == J_SEEK


def flip(r):
    d0 = r.m(DIR)
    r.wx(fx(7))
    r.tick(3)
    assert r.m(DIR) == d0 ^ 1, "flip plate did not flip the belt"


def settle(r):
    assert wait(r, lambda: r.m(JST) == J_SETTLED, 260), \
        f"Jagger never settled (jx={r.m(JX)} jst={r.m(JST)})"
    assert r.m(JX) == PX(1)
    assert wait(r, lambda: r.m(GATE) == 1 and r.m(WP) == 1, 10), "gate did not open"


def down_to_ante(r):
    r.wy(fy(13))                                  # across the lane (belt drags west)
    r.wx(GAP)
    r.wy(ANTE_Y)
    assert r.pos()[1] == ANTE_Y, f"gate blocked the way down {r.pos()}"


def ante_to_entry(r):
    r.wx(GAP)
    r.wy(fy(13))
    r.wy(fy(10))
    r.wx(GAP)
    r.wy(fy(4))
    assert r.pos()[1] == fy(4), f"could not climb back to the entry hall {r.pos()}"


def setup_run(r):
    heart_key(r)
    star_key(r)
    assert r.m(HELD) == HEART | STAR and r.m(PED) == MOON
    lure_take(r)
    assert r.m(LURE) == 1
    to_ferry(r)


def assert_restored(r, resets, coins):
    r.tick(12)
    g = world_tiles(r.pb)
    assert r.m(RESETS) == resets, f"resets {r.m(RESETS)} != {resets}"
    assert r.m(HELD) == 0 and r.m(PED) == 7, f"keys not back ({r.m(HELD)}, {r.m(PED)})"
    assert r.m(OPEN) == 0 and doors_locked(g), "doors not relocked"
    assert r.m(LURE) == 0 and r.m(DIR) == 0 and r.m(GATE) == 0
    assert r.m(JST) == J_IDLE and r.m(JX) == PX(9) and r.m(JY) == PY(11)
    assert g[Y0 + 14][X0 + 5] == BARS and g[Y0 + 11][X0 + 4] == CONV_E
    assert r.m(COINS) == coins
    assert r.m(BLINK) == 0, f"reset repaint left blinks pending ({r.m(BLINK)})"


def main():
    r, cell = open_room()
    edges = check_layout(world_tiles(r.pb))
    hp0 = r.hp()
    r.set_pos(PX(-3), PY(6) - 4)
    r.tick(2)
    r.armed = True                    # entry spawns are evicted on the first tick
    r.wx(fx(4))
    r.tick(20)
    still(r, "state0_start")
    print(f"  layout OK (seed {SEED:#x}, cell {cell}, edges {edges}; doors locked, "
          f"both belt directions shown, ids only in the pocket)")

    # --- keys: wrong key refused and kept; cap; Star opens its door.
    heart_key(r)
    assert r.m(HELD) == HEART and r.m(PED) == STAR | MOON
    ref = r.m(REFUSE)
    star_door_down(r)
    assert r.m(REFUSE) == ref + 1 and r.m(HELD) == HEART and r.m(OPEN) == 0, \
        "Heart key at the Star door not refused"
    still(r, "state1_refused")
    r.pb.memory[HELD] = HEART | STAR                # pretend a Star is held: cap
    ref = r.m(REFUSE)
    star_key(r)
    assert r.m(REFUSE) == ref + 1 and r.m(PED) & STAR, "second Star not refused"
    r.pb.memory[HELD] = HEART
    star_key(r)
    assert r.m(HELD) == HEART | STAR and r.m(PED) == MOON
    print("  Heart refused (kept) at the Star door; one of each type (cap); Star taken")

    # --- lure: refused outside the drop zone.
    lure_take(r)
    assert r.m(LURE) == 1
    ref = r.m(REFUSE)
    r.pack(TOOL_LURE)
    r.tick(3)
    assert r.m(LURE) == 1 and r.m(REFUSE) == ref + 1, f"lure drop in the entry hall not refused (lure={r.m(LURE)} ref {ref}->{r.m(REFUSE)} pos={r.pos()} sel={r.m(SEL)})"
    to_ferry(r)
    assert r.m(HELD) == HEART, "Star key not spent on the Star door"
    r.wx(fx(6))
    ref = r.m(REFUSE)
    r.pack(TOOL_LURE)
    r.tick(3)
    assert r.m(LURE) == 1 and r.m(REFUSE) == ref + 1, "drop by the flip plate not refused"
    drop_lure(r)
    still(r, "state2_lure")
    lo = 255
    for _ in range(140):
        r.tick()
        lo = min(lo, r.m(JX))
    assert r.m(JST) == J_SEEK and lo > PX(6) and r.m(GATE) == 0, \
        f"Jagger not held back by the east belt (min jx {lo})"
    still(r, "state3_struggle")
    print(f"  lure refused in the entry hall and off the zone; dropped, the Jagger "
          f"struggles on the east belt (min x {lo - PX(0)})")

    # --- flip: the belt ferries the Jagger onto the weight plate; gate opens.
    flip(r)
    settle(r)
    still(r, "state4_settled")
    print("  flip -> west belt ferries the Jagger onto W, gate open")

    # --- Heart on the closet door: Moon key, Moon door, coin once.
    down_to_ante(r)
    r.wx(PX(4) - 2)
    r.tick(3)
    assert r.m(OPEN) & 4 and r.m(HELD) == 0, "Heart key did not open the closet door"
    assert t(r, 8, 15) == DOOR, "vault door opened too"
    r.wx(PX(1) - 2)
    r.tick(3)
    assert r.m(HELD) == MOON, "Moon key not taken"
    still(r, "state5_moon_key")
    ante_to_entry(r)
    r.wx(PX(9))
    r.tick(4)
    assert r.m(OPEN) & 2 and r.m(HELD) == 0 and r.m(COINS) == 1, "Moon door/coin failed"
    r.wy(fy(1))
    r.tick(10)
    still(r, "state6_moon_nook")
    print("  Heart spent on the closet: Moon key -> Moon door -> coin (once)")

    # --- Pack RESET from the Moon nook.
    hp1 = r.hp()
    r.pack(TOOL_RESET)
    assert r.pos() == (PX(3), PY(5)), f"reset did not warp the hero {r.pos()}"
    assert_restored(r, 1, 1)
    assert r.hp() == hp1
    print("  Pack reset OK (from the nook: keys back, doors relocked, Jagger home, hp kept)")

    # --- run 2: off-camera gate (cue once, blink on arrival); reset while pinned.
    setup_run(r)
    flip(r)                                       # Jagger idle: belt flips, it stays
    assert r.m(JST) == J_IDLE
    r.wx(GAP)
    r.wy(fy(4))
    r.wx(fx(4))
    r.wy(fy(1))
    cues0 = r.m(OFFCAM)
    mem = r.pb.memory
    mem[LX], mem[LY], mem[LURE], mem[JST] = PX(2), PY(9), 2, J_SEEK   # lure "down"
    settle(r)
    r.tick(4)
    assert r.m(OFFCAM) == cues0 + 1, f"no single off-camera cue ({cues0}->{r.m(OFFCAM)})"
    assert r.m(BLINK) & 2, f"gate not pending a blink ({r.m(BLINK)})"
    r.wy(fy(4))
    r.wx(GAP)
    r.wy(fy(10))
    assert wait(r, lambda: not r.m(BLINK) & 2, 40), "gate never blinked on arrival"
    r.wy(fy(12))                                  # onto the west belt: pinned at the Jagger
    r.tick(40)
    x, _ = r.pos()
    assert x <= PX(3), f"belt did not carry the hero to the Jagger ({x - PX(0)})"
    still(r, "state7_pinned")
    r.pack(TOOL_RESET)
    assert r.pos() == (PX(3), PY(5))
    assert_restored(r, 2, 1)
    print("  off-camera gate: one cue, blink on arrival; Pack reset while pinned OK")

    # --- run 3: closet again: no second coin; entrance plate reset.
    setup_run(r)
    drop_lure(r)
    flip(r)
    settle(r)
    down_to_ante(r)
    r.wx(PX(4) - 2)
    r.wx(PX(1) - 2)
    r.tick(3)
    ante_to_entry(r)
    r.wx(PX(9))
    r.tick(4)
    n_ent = len(r.ents())
    r.tick(10)
    assert r.m(OPEN) & 2 and r.m(COINS) == 1 and len(r.ents()) <= n_ent, "coin paid twice"
    r.walk(fx(2), fy(4), axis_first="x", until=lambda: r.m(RESETS) == 3)
    assert wait(r, lambda: r.m(RESETS) == 3, 20), "entrance plate did not reset"
    assert_restored(r, 3, 1)
    print("  closet again: Moon door pays nothing; entrance plate reset OK")

    # --- run 4: Heart on the vault door, solve; walking out resets.
    setup_run(r)
    drop_lure(r)
    flip(r)
    settle(r)
    down_to_ante(r)
    r.wx(PX(8) - 14)
    r.tick(3)
    assert r.m(OPEN) & 8 and r.m(HELD) == 0, "Heart key did not open the vault door"
    assert t(r, 3, 15) == DOOR
    r.wx(fx(9))
    r.tick(4)
    assert r.m(RS + 27) & 0x20, f"goal not solved pos={r.pos()}"
    still(r, "state8_solved")
    r.wx(GAP)
    ante_to_entry(r)
    r.wx(fx(4))
    r.wy(PY(6) - 4)
    r.wx(PX(-3))
    r.tick(6)
    assert r.m(OPEN) == 0 and r.m(PED) == 7 and r.m(JST) == J_IDLE, "walking out did not reset"
    assert r.intruders == 0, f"enemies inside the pocket {r.intruders}x {getattr(r, 'first_bad', None)}"
    assert r.lane_bad == 0, f"Jagger left its lane {r.lane_bad}x"
    # Pocket mechanics never hurt (the Jagger only shoves). Room monsters at
    # the open entrance may (bats cast through the doorway): only there.
    deep = [h for h in getattr(r, "hurt_at", []) if h[1] >= 8 * 8 or h[0] >= 8 * 8]
    assert not deep, f"hero hurt inside the pocket at {deep}"
    print(f"  vault solved; walking out resets; Jagger stayed in its lane; no intruders; "
          f"never hurt past the entry hall (doorway hits by room monsters: {r.hurts}); refusals {r.m(REFUSE)} drops {r.m(DROPS)}")

    if CAPTURE:
        out = Path(CAPTURE)
        out.mkdir(parents=True, exist_ok=True)
        fr = [f.resize((480, 432), 0) for f in r.frames[::3]]
        if fr:
            fr[0].save(out / "lock_room_3x.gif", save_all=True,
                       append_images=fr[1:], duration=100, loop=0)
        print(f"  capture: {len(fr)} frames -> {out}")
    r.pb.stop(save=False)
    print("test_lock_room OK")


if __name__ == "__main__":
    main()
