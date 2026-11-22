#!/usr/bin/env python3
"""ROM regression: M5a Ember Conduit (turret churn, stone lane, teleport skip).

Headless proof for the optional stage-5 showcase pocket that
  * it is generated with an always-open entrance, the side door and Star
    door shut, the stone lane laid, and its borrowed tile ids nowhere else;
  * turret churn, fuzzed over many RNG seeds with the hero wandering the
    side door and wing: a shut never lands on the hero, flips are at least
    the lockout apart, the door tiles always match the state, the hero is
    never trapped longer than a bounded wait, and Pack RESET always works
    (also while pinned inside the shut wing);
  * player shots hurt the turret but never flip the switch; turret death
    opens the side door for good (fail-safe); freeze holds the cadence;
  * the Star key is behind the churn; the Star door refuses without it;
    the Stone Jagger guards the lane; freeze + the rolling stone crushes it
    (reset brings it back); the spawn plate releases a pack, the teleport
    pad skips it; the vault goal solves; walking out resets.
Every hero can solve it: everything is stepped or chosen in the Pack.
"""
import os
import random
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from quintra_topology import rime_cell_candidates  # noqa: E402
import test_stage_archetypes as tsa  # noqa: E402

STAGE = 5
SEED = int(os.environ.get("CD_SEED", "0xCAFE1234"), 16)
CAPTURE = os.environ.get("CD_CAPTURE")
FUZZ = int(os.environ.get("CD_FUZZ", "48"))
PUZZLE_CONDUIT_ROOM = 11
X0, Y0, W, H = 18, 11, 12, 18
BGT_FLOOR, BGT_WALL = 1, 2
TRACK, TPAD, SWITCH, PLATE, DOOR, BARS = 105, 106, 107, 96, 37, 99
CAIRN, STREAM, LOCK, G_ROCK, G_STREAM = (98, 109, 110, 39), 108, 38, 35, 36
OURS = {TRACK, TPAD, SWITCH, PLATE, DOOR, BARS, STREAM, LOCK, G_ROCK, G_STREAM} | set(CAIRN)
SOLID = {2, DOOR, BARS, STREAM, LOCK} | set(CAIRN) | set(tsa.HARD_SCENERY)
CLASS = int(os.environ.get("CD_CLASS", "0"))
PICSEAN = 3
J_GUARD, J_DEAD = 0, 1
TOOL_FREEZE, TOOL_RESET = 4, 5
LANE = 10

A = tsa.addr
RS, PL, EN = tsa.RS, tsa.PL, tsa.EN
NAMES = ("ra", "rb", "kx", "kst", "lockup", "hkey", "hdoor", "coin_given", "rewrites",
         "live", "side", "key", "held", "open", "charge", "jx", "jy", "jst", "sst",
         "sx", "st", "thp", "tt", "tell", "thead", "lock", "armed", "pend", "frame",
         "resets", "refusals", "flips", "crushed", "shoves", "pack_id", "pack", "von")
S = {n: A("_cd_" + n) for n in NAMES}
CELL = A("_rime_cell")
KIND = A("_room_puzzle_kind")
SCREEN = A("_loop_current_screen")
FRAME = A("_loop_frame_counter")
SEL = A("_selected_tool")
FREEZE = A("_room_freeze_beats")
RNG = A("_rng_state")
TM, EXT, BOT = A("_room_tilemap"), A("_room_world_extension"), A("_room_world_bottom")
LAYOUT = [
    "############", "#11...#....#", "#11...#....#", "#.....#....#",
    "#33...#..22#", "#33.33#..22#", "....33#....#", "......#....#",
    "####33######", "#g..33....g#", "#==========#", "#==========#",
    "############", "#..HLL..H..#", "#GGHLLPPH..#", "#SSSSSSCCSS#",
    "#SSSSSSCCSS#", "############",
]
REGIONS = {(6, 3), (6, 4), (6, 12), (7, 12)}
K_HOME, K_FLY, K_BREATH, K_DONE = 0, 1, 2, 3


def PX(lx):
    return (X0 + lx) * 8


def PY(ly):
    return (Y0 + ly) * 8


SWX = {1: (X0 + 1) * 8 - 2, 10: (X0 + 10) * 8 - 7}   # hero x: feet centre on a dead-end switch, clear of the wall


def fx(lx):          # hero x whose feet centre is in column lx
    return PX(lx) - 4


def fy(ly):          # hero y whose feet are in row ly
    return PY(ly) - 8


class Run:
    def __init__(self, pb):
        self.pb = pb
        self.frames = []
        self.intruders = 0
        self.hurts = 0
        self.armed = False
        self.heal = True

    def m(self, a):
        return self.pb.memory[a]

    def c(self, n):
        return self.pb.memory[S[n]]

    def pos(self):
        mem = self.pb.memory
        return (mem[PL + 9] | mem[PL + 10] << 8, mem[PL + 11] | mem[PL + 12] << 8)

    def set_pos(self, x, y):
        tsa.put16(self.pb, PL + 9, x)
        tsa.put16(self.pb, PL + 11, y)

    def hp(self):
        return self.m(PL + 2)

    def tick(self, n=1):
        for _ in range(n):
            hp0 = self.hp()
            rw0 = (self.pb.memory[S["rewrites"]], self.pb.memory[S["ra"]], self.pb.memory[S["rb"]])
            self.pb.tick()
            if getattr(self, "trace", None) is not None:
                self.trace = (self.trace + [(self.pos()[0], self.pos()[1], self.c("rewrites"), self.c("ra"), self.c("rb"), self.c("von"), self.c("resets"), self.m(SCREEN))])[-40:]
            if (self.pb.memory[S["rewrites"]], self.pb.memory[S["ra"]], self.pb.memory[S["rb"]]) != rw0:
                self.rw_log = (getattr(self, "rw_log", []) + [(self.pos(), self.c("rewrites"), self.c("ra"), self.c("rb"), self.c("resets"))])[-10:]
            if self.m(SCREEN) == 5 and self.hp() < hp0:
                self.hurts += 1
                if self.heal:
                    self.pb.memory[PL + 2] = hp0      # turret shots sting; keep the run alive
            if self.armed and self.m(SCREEN) == 5 and self.c("live") and self.m(FRAME) % 8 == 4:
                packs = {self.m(S["pack"]), self.m(S["pack"] + 1)}
                for i in range(32):
                    e = EN + i * 28
                    if self.m(e + 1) & 1 and self.m(e) == 2 and i not in packs:
                        ex = self.m(e + 3) | self.m(e + 4) << 8
                        ey = self.m(e + 7) | self.m(e + 8) << 8
                        if ex + 8 >= PX(-1) and PY(0) <= ey + 8 < PY(H):
                            self.intruders += 1
                            if self.intruders == 1:
                                self.first_bad = (i, self.m(e + 17), ex - PX(0), ey - PY(0),
                                                  self.m(A("_puzzle_keep_on")), self.c("resets"),
                                                  self.c("armed"), packs)
                            break
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

    def wx(self, tx, **k):
        return self.walk(tx, self.pos()[1], axis_first="x", **k)

    def wy(self, ty, **k):
        return self.walk(self.pos()[0], ty, axis_first="y", **k)

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


def check_layout(grid):
    for ly, row in enumerate(LAYOUT):
        for lx, c in enumerate(row):
            v = grid[Y0 + ly][X0 + lx]
            if (lx, ly) in REGIONS:
                continue
            if c == "#":
                assert v == BGT_WALL, f"wall missing at {lx},{ly}: {v}"
            elif c == "=":
                assert v == TRACK, f"lane missing at {lx},{ly}: {v}"
            elif c in ".123GPg":
                assert v not in SOLID, f"floor blocked at {lx},{ly}: {v}"
            elif c == "S":
                assert v == STREAM, f"rift-stream missing at {lx},{ly}: {v}"
            elif c == "C":
                assert v in CAIRN, f"cairn missing at {lx},{ly}: {v}"
            elif c == "L":
                assert v == LOCK, f"crystal lock missing at {lx},{ly}: {v}"
            elif c == "H":
                assert v == DOOR, f"Heart door missing at {lx},{ly}: {v}"
    assert grid[Y0 + 3][X0 + 6] == BARS and grid[Y0 + 4][X0 + 6] == BARS, "side door not shut"
    assert grid[Y0 + 12][X0 + 6] == DOOR and grid[Y0 + 12][X0 + 7] == DOOR, "Star door not shut"
    assert grid[Y0 + 9][X0 + 1] == G_ROCK and grid[Y0 + 9][X0 + 10] == G_STREAM, "switch glyphs wrong"
    seen = bfs(grid, (X0 + 1, Y0 + 6))
    edges = [p for p in seen if p[0] in (0, 30) or p[1] in (0, 30)]
    assert edges, "pocket entrance not reachable from any room edge"
    assert (X0 + 1, Y0 + 1) in seen and (X0 + 8, Y0 + 11) in seen
    assert (X0 + 8, Y0 + 6) not in seen, "wing reachable with the side door shut"
    assert (X0 + 6, Y0 + 13) not in seen, "vault reachable with the Star door shut"
    stray = [(x, y, grid[y][x]) for y in range(31) for x in range(31)
             if grid[y][x] in OURS and not (X0 <= x < X0 + W and Y0 <= y < Y0 + H)]
    assert not stray, f"pocket tile ids outside the pocket: {stray[:4]}"
    return len(edges)


def try_seed(seed):
    cands = rime_cell_candidates(seed, STAGE)
    if not cands:
        return None
    pb = tsa.generated_room(STAGE, seed, local_room=cands[0], keep_running=True,
                            class_id=CLASS)
    real = pb.memory[CELL]
    if real != cands[0] and real in cands:
        pb.stop(save=False)
        pb = tsa.generated_room(STAGE, seed, local_room=real, keep_running=True,
                                class_id=CLASS)
    if pb.memory[KIND] != PUZZLE_CONDUIT_ROOM or pb.memory[S["live"]] != 1:
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
    raise AssertionError("no seed in 12 hosted the Ember Conduit")


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


def side_tiles_ok(r):
    g = world_tiles(r.pb)
    want = BGT_FLOOR if r.c("side") else BARS
    return g[Y0 + 3][X0 + 6] == want and g[Y0 + 4][X0 + 6] == want


def hero_in_door(r):
    x, y = r.pos()
    return x + 13 >= PX(6) and x + 2 < PX(7) and y + 15 >= PY(3) and y + 8 < PY(5)


def in_wing(r):
    x, y = r.pos()
    return (x + 8) >> 3 >= X0 + 7 and (y + 12) >> 3 <= Y0 + 7


def lane_quiet(r, n=120):
    # Wait until the stone is idle with at least n frames left.
    return wait(r, lambda: r.c("sst") == 0 and r.c("st") >= n, 400)


# ---- routes ----
def enter(r):
    r.set_pos(PX(-3), PY(6) - 4)
    r.tick(2)
    r.armed = True
    r.wx(fx(3))
    r.wy(fy(3))


def through_side(r, east):
    """Cross the side door (row 3); waits for it to open. Returns frames waited."""
    waited = 0
    while not r.c("side"):
        r.tick()
        waited += 1
        assert waited < 900, "side door never reopened (trapped)"
    r.wx(fx(8) if east else fx(3), until=lambda: not r.c("side") and not hero_in_door(r))
    return waited


def take_key(r):
    r.wy(fy(3))
    r.wx(fx(4))
    for _ in range(6):
        through_side(r, True)
        if in_wing(r):
            break
        r.wx(fx(4))
    assert in_wing(r), f"could not enter the wing {r.pos()}"
    r.walk(fx(8), fy(7), axis_first="y")
    r.wx(fx(9))
    assert wait(r, lambda: r.c("held") == 1, 10), f"Star key not taken {r.pos()}"
    r.wx(fx(8))
    r.wy(fy(3))
    for _ in range(6):
        through_side(r, False)
        if not in_wing(r) and r.pos()[0] < PX(6):
            break
        r.wx(fx(8))
    assert r.pos()[0] < PX(6), f"could not leave the wing {r.pos()}"


def take_charge(r):
    assert wait(r, lambda: r.m(FREEZE) == 0, 1200), "freeze never ended"   # pedestal refuses mid-freeze
    r.walk(fx(3), fy(4), axis_first="x")
    r.walk(fx(5), fy(6), axis_first="y", until=lambda: r.c("charge") == 1)
    if not r.c("charge"):
        r.walk(fx(5), fy(5) + 2, axis_first="y", until=lambda: r.c("charge") == 1)
    if not wait(r, lambda: r.c("charge") == 1, 10):
        r.pb.screen.image.save("/tmp/q-m5-logs/fail_charge.png")
        g = world_tiles(r.pb)
        raise AssertionError(f"Rime charge not taken {r.pos()} frz {r.m(FREEZE)} rows5-7 {[g[Y0 + y][X0 + 3:X0 + 7] for y in (5, 6, 7)]}")


def teleport(r):
    r.walk(fx(3), fy(3), axis_first="y")
    r.walk(fx(2), fy(2), axis_first="x", until=lambda: r.pos()[1] >= PY(8))
    assert wait(r, lambda: r.pos()[1] >= PY(8), 10), f"teleport did not fire {r.pos()}"
    assert r.c("armed") == 0, "teleport armed the spawn plate"


def to_door(r):
    """From the hall landing: lure the Jagger west, freeze it, slip to the Star door."""
    r.wy(PY(LANE) - 12)                 # feet row 10, above the Jagger's feet
    lane_quiet(r)
    r.wx(fx(2))
    assert wait(r, lambda: r.c("jx") == PX(3), 90), f"Jagger did not shadow the hero {r.c('jx')}"
    r.pack(TOOL_FREEZE)
    assert r.m(FREEZE) > 0 and r.c("charge") == 0
    r.wx(PX(6))
    r.wy(PY(LANE))


def switches(r):
    """Hall row 9 dead ends: A (col 1) flips A and B, B (col 10) flips B -> both streams."""
    r.wy(PY(LANE) - 12)
    lane_quiet(r)
    r.wy(fy(9))
    for col, want in ((1, (1, 0)), (10, (1, 1))):
        n = r.c("rewrites")
        r.trace = []
        r.wx(SWX[col])
        if r.c("rewrites") != n + 1:
            print("TRACE", r.trace)
        r.trace = None
        assert wait(r, lambda: r.c("rewrites") == n + 1, 10), f"switch at col {col} did nothing {r.pos()} ref {r.c('refusals')} von {r.c('von')} live {r.c('live')} ra/rb {r.c('ra')}{r.c('rb')} kx {r.c('kx') - PX(0)} kst {r.c('kst')} resets {r.c('resets')} rw {getattr(r, 'rw_log', None)} n {n} rewrites {r.c('rewrites')}"
        assert (r.c("ra"), r.c("rb")) == want, f"regions {(r.c('ra'), r.c('rb'))} != {want}"
    r.wx(PX(7))                          # step off B along the hall (no lane bounce)
    g = world_tiles(r.pb)
    assert all(g[Y0 + y][X0 + x] == STREAM for x in range(1, 11) for y in (15, 16)), \
        "stream not continuous after A, B"
    assert g[Y0 + 9][X0 + 1] == G_STREAM and g[Y0 + 9][X0 + 10] == G_STREAM, "glyphs not flipped"


def kite_chain(r):
    """In the vault: release plate wakes the Kite; it rides west and shatters the lock."""
    r.wy(fy(13))
    assert r.pos()[1] == fy(13), f"could not enter the vault {r.pos()}"
    r.wy(fy(14))
    assert wait(r, lambda: r.c("kst") != K_HOME, 10), "release plate did not wake the Kite"
    assert wait(r, lambda: r.c("lockup") == 0, 420), f"Kite never shattered the lock (kx {r.c('kx') - PX(0)} kst {r.c('kst')} ra {r.c('ra')} rb {r.c('rb')} frz {r.m(FREEZE)} pos {r.pos()} rw {getattr(r, 'rw_log', None)} X0 {PX(0)} {PY(0)})"
    still(r, "state7_shattered")
    r.wy(fy(13))
    r.wx(PX(4))
    assert wait(r, lambda: r.c("held") & 2, 10), f"Heart key not taken {r.pos()}"


def setup_run(r):
    take_key(r)
    take_charge(r)
    teleport(r)


def assert_restored(r, resets):
    r.tick(12)
    g = world_tiles(r.pb)
    assert r.c("resets") == resets, f"resets {r.c('resets')} != {resets}"
    assert r.c("key") == 1 and r.c("held") == 0 and r.c("charge") == 0
    assert r.c("side") == 0 and r.c("open") == 0 and r.c("armed") == 0
    assert g[Y0 + 3][X0 + 6] == BARS and g[Y0 + 12][X0 + 6] == DOOR
    assert (r.c("ra"), r.c("rb"), r.c("kst"), r.c("lockup"), r.c("hkey"), r.c("hdoor")) == \
        (0, 1, K_HOME, 1, 1, 0), "vault not restored"
    assert g[Y0 + 13][X0 + 4] == LOCK and g[Y0 + 13][X0 + 3] == DOOR and g[Y0 + 15][X0 + 7] in CAIRN
    assert r.c("jst") == J_GUARD and r.c("thp") == 4
    assert r.m(FREEZE) == 0


def kite_wait(r, snap):
    snap.seek(0)
    r.pb.load_state(snap)
    mem = r.pb.memory
    mem[S["kst"]], mem[S["kx"]] = K_FLY, PX(9)
    r.tick(60)
    assert r.c("kx") == PX(9), f"Kite flew through the A cairn ({r.c('kx') - PX(0)})"
    mem[S["ra"]] = 1                         # pretend A was raised to stream: B is stream too
    assert wait(r, lambda: r.c("kx") < PX(7), 120) and r.c("kst") == K_FLY, \
        f"Kite stuck kx {r.c('kx') - PX(0)} kst {r.c('kst')} ra {r.c('ra')} rb {r.c('rb')} live {r.c('live')}"
    ref, n = r.c("refusals"), r.c("rewrites")
    r.set_pos(PX(3), fy(9))
    r.tick(2)
    r.wx(SWX[1])
    assert wait(r, lambda: r.c("refusals") == ref + 1, 10) and r.c("rewrites") == n, \
        "switch A raised a cairn onto the Kite"
    print("  Kite waits at a cairn; switch A refuses to raise one onto it")


DBG_K = int(os.environ.get('CD_DBG_K', '-1'))


def fuzz(r, snap):
    """Turret churn over FUZZ RNG seeds with the hero loitering in the door."""
    rnd = random.Random(1234)
    first_bad = None
    worst, flips, shut_on_hero, gap_bad, tiles_bad, resets = 0, 0, 0, 0, 0, 0
    lock = 64
    for k in range(FUZZ):
        snap.seek(0)
        r.pb.load_state(snap)
        for i in range(4):
            r.pb.memory[RNG + i] = rnd.randrange(256)
        r.pb.memory[S["tt"]] = 1 + rnd.randrange(40)
        last_flip, trapped, flips0, odd = None, 0, r.c("flips"), 0
        moves = ["right", "left", "up", "down", None]
        btn = None
        for f in range(700):
            if f % 12 == 0:
                if btn:
                    r.pb.button_release(btn)
                btn = rnd.choice(moves if in_wing(r) else moves + ["right", "right"])
                x, y = r.pos()
                if x < PX(2):
                    btn = "right"
                elif y > PY(6):
                    btn = "up"
                if btn:
                    r.pb.button_press(btn)
            n0 = r.c("flips")
            r.tick()
            if r.c("flips") != n0:
                if last_flip is not None and f - last_flip < lock:
                    gap_bad += 1
                last_flip = f
                if not r.c("side") and hero_in_door(r):
                    shut_on_hero += 1
            # pyboy samples at frame ends, which can land mid-update: a
            # mismatch must persist to count.
            odd = 0 if side_tiles_ok(r) else odd + 1
            if DBG_K == k and 60 <= f <= 125:
                g = world_tiles(r.pb)
                print("dbg", f, r.c("side"), r.c("pend"), r.c("lock"), r.c("flips"), g[Y0 + 3][X0 + 6], g[Y0 + 4][X0 + 6], r.pos(), r.c("kst"), r.c("ra"), r.c("rb"))
            if odd >= 2:
                tiles_bad += 1
                if tiles_bad == 1:
                    g = world_tiles(r.pb)
                    first_bad = (k, f, r.c("side"), g[Y0 + 3][X0 + 6], g[Y0 + 4][X0 + 6],
                                 r.c("pend"), r.c("lock"), r.c("thp"), r.c("flips"), r.c("resets"),
                                 tuple(p - o for p, o in zip(r.pos(), (PX(0), PY(0)))))
            trapped = trapped + 1 if (in_wing(r) and not r.c("side")) else 0
            worst = max(worst, trapped)
        if btn:
            r.pb.button_release(btn)
        flips += r.c("flips") - flips0
        if k % 6 == 0:
            # Reset while (possibly) shut in the wing: always works.
            if k % 12 == 0:
                r.set_pos(fx(8), fy(6))      # inside the wing, door maybe shut
                r.tick(2)
            n = r.c("resets")
            r.pack(TOOL_RESET)
            assert r.c("resets") == n + 1 and r.pos() == (PX(3), PY(5)), "Pack reset failed"
            resets += 1
    assert shut_on_hero == 0, f"side door shut on the hero {shut_on_hero}x"
    assert gap_bad == 0, f"flips closer than the lockout {gap_bad}x"
    assert tiles_bad == 0, f"side door tiles out of sync {tiles_bad} frames {first_bad}"
    assert flips >= FUZZ, f"turret churn too quiet ({flips} flips over {FUZZ} seeds)"
    assert worst < 600, f"hero shut in the wing {worst} frames"
    return flips, worst, resets


def turret_death():
    """Picsean (projectile hero): bolts up through the switch kill the turret;
    the side door opens for good and no bolt ever flips the switch."""
    global CLASS
    CLASS = PICSEAN
    r, _cell = open_room()
    r.set_pos(PX(-3), PY(6) - 4)
    r.tick(4)
    r.pb.memory[S["charge"]] = 1
    r.set_pos(fx(9), fy(7))
    r.tick(2)
    r.pack(TOOL_FREEZE)
    r.press("up", 3, 2)
    n, side, hp0 = r.c("flips"), r.c("side"), r.c("thp")
    for _ in range(40):
        if r.c("thp") == 0:
            break
        r.pb.memory[S["charge"]] = 0
        if r.m(FREEZE) < 8:
            r.pb.memory[S["charge"]] = 1
            r.pack(TOOL_FREEZE)
            r.press("up", 3, 2)
        r.press("up", 2, 1)              # face north (the switch blocks the walk)
        r.press("a", 3, 2)
        if os.environ.get("CD_TDBG"):
            for _k in range(6):
                pr = [(r.m(EN + i * 28), (r.m(EN + i * 28 + 3) | r.m(EN + i * 28 + 4) << 8) - PX(0),
                       (r.m(EN + i * 28 + 7) | r.m(EN + i * 28 + 8) << 8) - PY(0))
                      for i in range(32) if r.m(EN + i * 28 + 1) & 0x11 == 0x11]
                print("proj", r.pos(), pr, r.c("thp"), r.m(FREEZE))
                r.tick(1)
        r.tick(4)
    assert r.c("thp") == 0, f"Picsean bolts did not kill the turret (hp {hp0} -> {r.c('thp')})"
    assert r.c("flips") <= n + 1, "player bolts flipped the switch"
    r.tick(6)
    assert r.c("side") == 1 and side_tiles_ok(r), "turret death did not open the side door"
    r.pb.memory[FREEZE] = 0
    r.tick(600)
    assert r.c("side") == 1 and r.c("thp") == 0, "side door shut again after the turret died"
    still(r, "state1_turret_down")
    r.pb.stop(save=False)
    CLASS = 0
    print(f"  Picsean: {hp0} bolts kill the turret; side door opens for good (600 f); no flips from bolts")


def main():
    if os.environ.get("CD_ONLY_TURRET"):
        turret_death()
        print("test_conduit_room OK")
        return
    r, cell = open_room()
    edges = check_layout(world_tiles(r.pb))
    pid = r.c("pack_id")
    enter(r)
    r.tick(20)
    still(r, "state0_start")
    print(f"  layout OK (seed {SEED:#x}, cell {cell}, edges {edges}; doors shut, lane laid, "
          f"ids only in the pocket; pack id {pid})")

    # --- turret churn fuzz (snapshot inside the west hall, door shut).
    import io
    snap = io.BytesIO()
    r.pb.save_state(snap)
    if os.environ.get("CD_ONLY_KITE"):
        kite_wait(r, snap)
        return
    if os.environ.get("CD_ONLY_SOLVE"):
        flips = worst = resets = 0
    else:
        flips, worst, resets = fuzz(r, snap)
    if os.environ.get("CD_ONLY_SOLVE"):
        pass
    else:
        if os.environ.get("CD_ONLY_FUZZ"):
            print(f"  fuzz only: {flips} flips, worst {worst}")
            return
        print(f"  turret fuzz: {FUZZ} RNG seeds, {flips} flips, never shut on the hero, "
              f"lockout held, tiles in sync, longest wing wait {worst} f, {resets} Pack resets")
        snap.seek(0)
        r.pb.load_state(snap)

        # --- freeze holds the cadence; player shots never flip; turret death opens.
        r.pb.memory[S["charge"]] = 1
        r.set_pos(fx(9), fy(7))             # in the wing, under the switch
        r.tick(2)
        side = r.c("side")
        r.pack(TOOL_FREEZE)
        tt2, tl2, n, hp0 = r.c("tt"), r.c("tell"), r.c("flips"), r.c("thp")
        r.press("up", 3, 2)
        for _ in range(10):                  # fire north through the switch at the turret
            r.press("a", 3, 6)
        assert r.m(FREEZE) > 0, "freeze ran out during the volley"
        assert r.c("tt") == tt2 and r.c("tell") == tl2, "freeze did not hold the turret"
        assert r.c("flips") == n and r.c("side") == side, "a player shot flipped the switch"
        hits = hp0 - r.c("thp")
        if hits:
            r.pb.memory[S["thp"]] = 1
            for _ in range(20):
                r.press("a", 3, 6)
                if r.c("thp") == 0:
                    break
            r.tick(4)
            assert r.c("thp") == 0 and r.c("side") == 1 and side_tiles_ok(r), "turret death did not open"
            r.tick(400)
            assert r.c("side") == 1, "side door shut after the turret died"
            still(r, "state1_turret_down")
        print(f"  freeze held the turret; player shots: {hits} hits, no flip"
              + ("; turret death opens the side door for good" if hits else " (melee hero)"))

        # --- Star door refused without the key (Jagger frozen aside).
        snap.seek(0)
        r.pb.load_state(snap)
        take_charge(r)
        teleport(r)
        to_door(r)
        assert r.c("open") == 0 and r.c("refusals") >= 1, \
            f"Star door not refused without the key ({r.c('refusals')}, pos {r.pos()})"
        still(r, "state2_refused")
        r.pack(TOOL_RESET)
        assert_restored(r, 1)
        print("  Star door refused without the Star key; Pack reset restores")

        # --- spawn plate releases the pack; the teleport skipped it above.
        r.walk(PX(4), fy(7), axis_first="x")
        r.wy(fy(9), until=lambda: r.c("armed"))
        assert wait(r, lambda: r.c("armed") == 1, 20), f"spawn plate did not arm {r.pos()}"
        packs = [p for p in (r.m(S["pack"]), r.m(S["pack"] + 1)) if p != 0xFF]
        assert (pid == 0xFF) or len(packs) == 2, f"pack not released ({packs}, id {pid})"
        still(r, "state3_pack")
        r.pack(TOOL_RESET)
        assert_restored(r, 2)
        assert r.m(S["pack"]) == 0xFF and r.m(S["pack"] + 1) == 0xFF, "reset left the pack"
        print(f"  spawn plate released {len(packs)} x id {pid}; teleport skips it; reset clears it")

        # --- stone crushes a frozen Jagger; reset brings it back.
        r.pb.memory[S["charge"]] = 1
        teleport(r)
        r.wy(PY(LANE) - 12)
        r.wx(fx(3))
        assert wait(r, lambda: r.c("sst") == 0 and r.c("st") < 30 and r.c("jy") == PY(LANE), 600)
        r.pack(TOOL_FREEZE)
        r.wy(fy(9))
        assert wait(r, lambda: r.c("jst") == J_DEAD, 260), "stone did not crush the frozen Jagger"
        still(r, "state4_crushed")
        r.pack(TOOL_RESET)
        assert_restored(r, 3)
        print("  rolling stone crushed the frozen Jagger; reset restored it")

        kite_wait(r, snap)

    # --- full solve, closet first: Star key, switches, Kite chain, Heart key on
    # door A (treasure); door B refused; reset returns the key; then door B, goal.
    snap.seek(0)
    r.pb.load_state(snap)
    setup_run(r)
    switches(r)
    to_door(r)
    assert wait(r, lambda: r.c("open") == 1, 20), f"Star key did not open the door {r.pos()}"
    still(r, "state5_open")
    kite_chain(r)
    r.wx(fx(9))
    assert wait(r, lambda: r.c("hdoor") == 1, 20), f"Heart door A did not open {r.pos()} {r.c('hdoor')}"
    assert not (r.c("held") & 2) and r.c("coin_given") == 1, "closet: key not spent / no treasure"
    still(r, "state8_closet")
    ref = r.c("refusals")
    r.wx(PX(4))
    r.wx(PX(3) - 2)
    assert r.c("refusals") == ref + 1 and r.c("hdoor") == 1, "Heart door B opened with no key"
    r.pack(TOOL_RESET)
    assert r.c("hkey") == 1 and r.c("hdoor") == 0 and r.c("lockup") == 1, "reset did not return the Heart key"
    assert (r.c("ra"), r.c("rb"), r.c("kst"), r.c("kx")) == (0, 1, K_HOME, PX(9)), \
        f"reset left the vault {(r.c('ra'), r.c('rb'), r.c('kst'), r.c('kx') - PX(0))} rw {getattr(r, 'rw_log', None)}"
    print("  Heart key spent on door A (treasure); door B refused; reset returns the key")
    setup_run(r)
    switches(r)
    to_door(r)
    assert wait(r, lambda: r.c("open") == 1, 20)
    kite_chain(r)
    r.wx(PX(3) - 2)
    assert wait(r, lambda: r.c("hdoor") == 2, 20), f"Heart door B did not open {r.pos()}"
    r.wy(fy(14))
    r.wx(fx(2))
    assert wait(r, lambda: r.m(RS + 27) & 0x20, 30), f"goal not solved pos={r.pos()}"
    still(r, "state6_solved")
    r.pack(TOOL_RESET)
    r.tick(8)
    r.wy(PY(6) - 4)
    r.wx(PX(-3))
    r.tick(6)
    assert r.c("open") == 0 and r.c("key") == 1 and r.c("jst") == J_GUARD, "walk-out reset failed"
    assert r.intruders == 0, f"room enemies inside the pocket {r.intruders}x {getattr(r, 'first_bad', None)}"
    print(f"  solved (Star key behind churn, switches A/B, freeze, Star door, Kite chain, Heart door B, goal); walking out resets; "
          f"no intruders; turret stings {r.hurts}; shoves {r.c('shoves')} refusals {r.c('refusals')}")

    if CAPTURE:
        out = Path(CAPTURE)
        fr = [f.resize((480, 432), 0) for f in r.frames[::3]]
        if fr:
            fr[0].save(out / "conduit_room_3x.gif", save_all=True,
                       append_images=fr[1:], duration=100, loop=0)
        print(f"  capture: {len(fr)} frames -> {out}")
    r.pb.stop(save=False)
    turret_death()
    print("test_conduit_room OK")


if __name__ == "__main__":
    main()
