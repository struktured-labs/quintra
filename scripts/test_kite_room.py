#!/usr/bin/env python3
"""ROM regression: M3 Kite Kennel (tool-beast chain).

Headless proof for the optional Frost Vault pocket that
  * it is generated with an always-open entrance reachable from the doors,
    the vault sealed by the crystal lock, and both channel materials
    (cairn, rift-stream) visible before any plate is used;
  * the pocket's borrowed tile ids appear nowhere else in the room;
  * the lock ignores player shots (only the Kite's breath breaks it);
  * "Kite dead": released into a cairn it gutters out in the cold and
    re-forms in the kennel with the gate shut; refused presses while it
    sits on a linked region;
  * "stream half-built": released with segment A built it waits there, the
    linked plate lets it through, it breaks the lock and flies home;
  * the vault goal solves; "lock already broken" re-releases cleanly;
  * Pack RESET ROOM (from the vault, and while the Kite is dead) and the
    entrance plate (while the Kite is flying) restore the start state with
    HP kept, and it solves again after a reset;
  * the Kite never leaves its channel; no ordinary enemy is ever inside.
Every hero can solve it: all plates are stepped, nothing needs a shot.
"""
import os
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from quintra_topology import rime_cell_candidates  # noqa: E402
import test_stage_archetypes as tsa  # noqa: E402

STAGE = 3
SEED = int(os.environ.get("KT_SEED", "0xCAFE1234"), 16)
CAPTURE = os.environ.get("KT_CAPTURE")
PUZZLE_KITE_ROOM = 9
X0, Y0, W, H = 18, 11, 12, 18
BGT_FLOOR, BGT_WALL = 1, 2
CAIRN = (98, 109, 110, 39)
BARS, STREAM, LOCK_T, LOCK_B = 99, 108, 37, 38
OURS = set(CAIRN) | {BARS, STREAM, LOCK_T, LOCK_B}
SOLID = {2} | OURS | set(tsa.HARD_SCENERY)
KT_HOME, KT_DOWN, KT_BREATH, KT_RETURN, KT_DEAD = range(5)

A = tsa.addr
RS, PL, EN = tsa.RS, tsa.PL, tsa.EN
LIVE, S1, X, BROKEN, STATE, KY, COLD = (A(n) for n in (
    "_kt_live", "_kt_s1", "_kt_x", "_kt_broken", "_kt_state", "_kt_ky", "_kt_cold"))
RESETS, DEATHS, REFUSE, OFFCAM, BLINK = (A(n) for n in (
    "_kt_resets", "_kt_deaths", "_kt_refusals", "_kt_offcam_sfx", "_kt_blink"))
CELL = A("_rime_cell")
KIND = A("_room_puzzle_kind")
SCREEN = A("_loop_current_screen")
FRAME = A("_loop_frame_counter")
SEL = A("_selected_tool")
TM, EXT, BOT = A("_room_tilemap"), A("_room_world_extension"), A("_room_world_bottom")
TOOL_RESET = 4
LAYOUT = [
    "############", "#.......#KK#", "#.......#KK#", "#.......#gg#",
    "#.......#gg#", "#.......#aa#", "........#aa#", "........#bb#",
    "#.......#bb#", "#.......#ss#", "#.......#ss#", "######LL#ss#",
    "######LL#ss#", "#..........#", "#..........#", "#...GG.....#",
    "#..........#", "############",
]


def PX(lx):
    return (X0 + lx) * 8


def PY(ly):
    return (Y0 + ly) * 8


def foot(lx, ly):
    return PX(lx) - 4, PY(ly) - 8


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
            self.pb.tick()
            if self.m(SCREEN) == 5 and self.m(LIVE):
                if self.m(STATE) != KT_DEAD and not (PY(1) <= self.m(KY) <= PY(11)):
                    self.lane_bad += 1
                if self.m(FRAME) % 8 == 4 and any(
                        t == 2 and ex + 8 >= PX(-1) and PY(0) <= ey + 8 < PY(H)
                        for t, ex, ey in self.ents()):
                    self.intruders += 1
            if CAPTURE and self.m(FRAME) % 4 == 0 and len(self.frames) < 900:
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

    # -- plates: walk the clear column x4, then step east onto the plate's
    #    lower row (overshoot east only meets the wall, never leaves it).
    def plate(self, ly, settle=25):
        self.go(4, ly + 1)
        self.go(6, ly + 1)
        self.tick(4)
        self.go(4, ly + 1)
        self.tick(settle)


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


def reg(r, lx, ly):
    g = world_tiles(r.pb)
    return [g[Y0 + ly + dy][X0 + lx + dx] for dy in (0, 1) for dx in (0, 1)]


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
            t = grid[Y0 + ly][X0 + lx]
            if c == "#":
                assert t == BGT_WALL, f"wall missing at {lx},{ly}: {t}"
            elif c in "Ks":
                assert t == STREAM, f"stream missing at {lx},{ly}: {t}"
            elif c == "g":
                assert t == BARS, f"gate bars missing at {lx},{ly}: {t}"
            elif c == ".":
                assert t not in SOLID, f"floor blocked at {lx},{ly}: {t}"
    assert tuple(g for g in [grid[Y0 + 5][X0 + 9], grid[Y0 + 5][X0 + 10],
                             grid[Y0 + 6][X0 + 9], grid[Y0 + 6][X0 + 10]]) == CAIRN
    assert all(grid[Y0 + 7 + dy][X0 + 9 + dx] == STREAM for dx in (0, 1) for dy in (0, 1))
    assert [grid[Y0 + 11][X0 + 6], grid[Y0 + 11][X0 + 7],
            grid[Y0 + 12][X0 + 6], grid[Y0 + 12][X0 + 7]] == [LOCK_T, LOCK_T, LOCK_B, LOCK_B]
    seen = bfs(grid, (X0 + 1, Y0 + 6))
    edges = [p for p in seen if p[0] in (0, 30) or p[1] in (0, 30)]
    assert edges, "pocket entrance not reachable from any room edge"
    assert (X0 + 6, Y0 + 4) in seen and (X0 + 1, Y0 + 2) in seen
    assert (X0 + 4, Y0 + 15) not in seen, "vault reachable with the lock intact"
    # Borrowed ids live only inside the pocket.
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
    if pb.memory[KIND] != PUZZLE_KITE_ROOM or pb.memory[LIVE] != 1:
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
    raise AssertionError("no seed in 12 hosted the Kite Kennel")


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


def shot_at(r, lx, ly):
    free = next(i for i in range(32) if not r.m(EN + i * 28 + 1) & 1)
    e = EN + free * 28
    for k in range(28):
        r.pb.memory[e + k] = 0
    r.pb.memory[e] = 1
    tsa.put16(r.pb, e + 3, PX(lx) + 4)
    tsa.put16(r.pb, e + 7, PY(ly) + 4)
    r.pb.memory[e + 14] = 1
    r.pb.memory[e + 16] = 30
    r.pb.memory[e + 25] = 0x44
    r.pb.memory[e + 26] = 4
    r.pb.memory[e + 1] = 0x11


def run_chain(r, label, away=False):
    """S1 (build A) -> lever (release; B closes) -> wait on A -> S2 -> lock."""
    if not r.m(S1):
        r.plate(5)
        assert r.m(S1) == 1, f"{label}: S1 did not build segment A"
    r.plate(3)                                   # lever: release
    assert r.m(X) == 1, f"{label}: lever did not release"
    assert reg(r, 9, 3) == [STREAM] * 4 or wait(r, lambda: reg(r, 9, 3) == [STREAM] * 4, 10)
    assert wait(r, lambda: r.m(KY) == PY(5), 120), f"{label}: Kite not waiting on A (ky={r.m(KY)})"
    still(r, f"{label}_waiting")
    assert reg(r, 9, 7) == list(CAIRN) and r.m(STATE) == KT_DOWN
    r.plate(7, settle=0)                         # S2: B opens, gate shuts
    assert r.m(X) == 0, f"{label}: S2 refused (ref={r.m(REFUSE)} ky={r.m(KY)})"
    if away:                                     # watch from the top: lock off camera
        r.go(4, 1, axis_first="y")
    if not away:
        assert wait(r, lambda: r.m(STATE) == KT_BREATH, 200), f"{label}: Kite never reached the lock"
        still(r, f"{label}_breath")
    else:
        assert wait(r, lambda: r.m(BROKEN) == 1, 200), f"{label}: lock never broke"
    assert wait(r, lambda: r.m(STATE) == KT_HOME, 200), f"{label}: Kite did not fly home"
    r.tick(10)


def main():
    r, cell = open_room()
    edges = check_layout(world_tiles(r.pb))
    hp0 = r.hp()
    r.set_pos(PX(-3), foot(0, 6)[1])
    r.tick(2)
    r.go(2, 6)
    r.tick(20)
    still(r, "state0_start")
    print(f"  layout + previews OK (seed {SEED:#x}, cell {cell}, edges {edges}; "
          f"ids only in the pocket; vault sealed)")

    # --- the lock ignores shots.
    shot_at(r, 6, 11)
    shot_at(r, 7, 12)
    r.tick(20)
    assert r.m(BROKEN) == 0 and reg(r, 6, 11) == [LOCK_T, LOCK_T, LOCK_B, LOCK_B]
    print("  crystal lock ignores player shots")

    # --- Kite dead: release with A still cairn; it waits in the gate.
    r.plate(3)
    assert r.m(X) == 1
    assert wait(r, lambda: r.m(KY) == PY(3), 90), f"Kite not in the gate ky={r.m(KY)}"
    ref0 = r.m(REFUSE)
    r.plate(7, settle=0)                         # linked plate while it sits in the gate
    assert r.m(X) == 1 and r.m(REFUSE) == ref0 + 1, "linked press under the Kite not refused"
    assert wait(r, lambda: r.m(STATE) == KT_DEAD, 220), f"Kite never guttered (cold={r.m(COLD)})"
    assert r.m(DEATHS) == 1
    assert wait(r, lambda: r.m(STATE) == KT_HOME, 120), "dead Kite did not re-form"
    r.tick(10)
    assert r.m(X) == 0 and reg(r, 9, 3) == [BARS] * 4, "gate not shut after respawn"
    print("  Kite dead -> re-forms in the kennel, gate shut; refusal under the Kite")

    # --- stream half-built -> chain -> lock broken.
    cues0 = r.m(OFFCAM)
    run_chain(r, "chain1", away=True)
    assert r.m(OFFCAM) == cues0 + 1, f"no off-camera cue for the lock ({cues0}->{r.m(OFFCAM)})"
    assert r.m(BLINK) & 8, f"lock not pending a blink ({r.m(BLINK)})"
    assert r.m(BROKEN) == 1 and reg(r, 6, 11) == [BGT_FLOOR] * 4, "lock not broken"
    assert r.m(X) == 0 and reg(r, 9, 3) == [BARS] * 4
    print(f"  half-built stream -> Kite waits on A, linked plate lets it through, "
          f"lock shattered off camera (cue once, blink pending), Kite home")

    # --- through the doorway to the goal.
    r.go(4, 9)
    assert wait(r, lambda: not r.m(BLINK) & 8, 30), "lock never blinked on arrival"
    still(r, "state_lock_blink")
    r.walk(PX(6), foot(4, 9)[1])
    r.walk(PX(6), foot(6, 13)[1], axis_first="y")
    assert r.pos()[1] >= foot(6, 13)[1] - 2, f"doorway blocked pos={r.pos()}"
    r.go(4, 15)
    r.tick(4)
    assert r.m(RS + 27) & 0x20, f"goal not solved pos={r.pos()}"
    still(r, "state1_solved")
    print("  lock blinked when it scrolled into view")
    print(f"  vault goal solved (hurts {r.hurts}, hp {hp0}->{r.hp()})")

    # --- lock already broken: release again; breath is a no-op.
    r.go(4, 13)
    r.walk(PX(6), foot(4, 13)[1])
    r.walk(PX(6), foot(6, 9)[1], axis_first="y")
    r.go(4, 9)
    run_chain(r, "chain2")
    assert r.m(BROKEN) == 1
    print("  lock already broken: re-release runs clean, Kite home")

    # --- Pack reset from the vault.
    r.go(4, 9)
    r.walk(PX(6), foot(4, 9)[1])
    r.walk(PX(6), foot(6, 14)[1], axis_first="y")
    hp1 = r.hp()
    r.pack(TOOL_RESET)
    assert r.pos() == (PX(1), PY(5)), f"reset did not warp hero {r.pos()}"
    r.tick(10)
    assert r.m(RESETS) == 1 and r.m(BROKEN) == 0 and r.m(S1) == 0 and r.m(X) == 0
    assert reg(r, 6, 11) == [LOCK_T, LOCK_T, LOCK_B, LOCK_B], "lock not restored"
    assert reg(r, 9, 5) == list(CAIRN) and r.hp() == hp1
    # --- Pack reset while the Kite is dead.
    r.plate(3)
    assert wait(r, lambda: r.m(STATE) == KT_DEAD, 320)
    r.pack(TOOL_RESET)
    r.tick(4)
    assert r.m(RESETS) == 2 and r.m(STATE) == KT_HOME and r.m(KY) == PY(1)
    print("  Pack reset OK (from the vault; while the Kite is dead; hp kept)")

    # --- entrance plate while the Kite is flying.
    r.plate(5)
    r.plate(3, settle=0)
    assert wait(r, lambda: r.m(STATE) == KT_DOWN, 30)
    r.go(4, 2)
    r.walk(*foot(2, 2), until=lambda: r.m(RESETS) != 2)
    assert wait(r, lambda: r.m(RESETS) == 3, 30), f"entrance plate no reset ({r.m(RESETS)})"
    r.tick(6)
    assert r.m(STATE) == KT_HOME and r.m(X) == 0 and r.m(S1) == 0
    print("  entrance plate reset OK (mid-flight)")

    # --- solve again after reset.
    r.pb.memory[RS + 27] &= ~0x20 & 0xFF
    r.tick(25)
    run_chain(r, "chain3")
    r.go(4, 9)
    r.walk(PX(6), foot(4, 9)[1])
    r.walk(PX(6), foot(6, 13)[1], axis_first="y")
    r.go(4, 15)
    r.tick(4)
    assert r.m(RS + 27) & 0x20, "solve after reset failed"
    assert r.intruders == 0, f"enemies inside the pocket {r.intruders}x"
    assert r.lane_bad == 0, f"Kite left its channel {r.lane_bad}x"
    assert r.hp() >= 1
    print(f"  solve after reset OK; Kite stayed in its channel; no intruders; hp {r.hp()}")

    if CAPTURE:
        out = Path(CAPTURE)
        out.mkdir(parents=True, exist_ok=True)
        fr = [f.resize((640, 576), 0) for f in r.frames[::2]]
        if fr:
            fr[0].save(out / "kite_room_4x.gif", save_all=True,
                       append_images=fr[1:], duration=66, loop=0)
            fr[len(fr) // 2].save(out / "kite_room_4x.png")
        print(f"  capture: {len(fr)} frames -> {out}")
    r.pb.stop(save=False)
    print("test_kite_room OK")


if __name__ == "__main__":
    main()
