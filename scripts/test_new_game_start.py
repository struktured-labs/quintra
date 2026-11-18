#!/usr/bin/env python3
"""New-game and Continue start contract, every hero, every boot path.

Regression gate for the 41a663ba bug: the Crystal Caverns foyer vignette
(#127) plays from RUN_INIT, before any room exists, and its exit took the
room *resume* path. The run started in an unbuilt room: hero at (0, 0) in
the top-left corner, a blank dark screen, and no stage music. The vignette
also mirrored the champion every 8 frames (side-facing heads swivelled).

For each of the five heroes and each way into a run:
  * intro skipped with START, A or B; intro played to the end; after an
    attract demo has run; and Continue from a suspend (intro skipped or
    played),
it checks that
  * a new game plays the Crystal Caverns vignette, then lands in a room,
  * power-off during the foyer vignette, then Continue, is also sane,
  * the vignette champion is never H-flipped and only uses that class's
    idle / stride tiles, whose VRAM matches the art the room loads,
  * the room renders (not one flat colour),
  * the hero spawns inside the room, not at the top-left corner,
  * the hero OAM uses that class's tiles,
  * stage 1 music is playing (track 0, sequencer advancing).

Runs the real intro and vignettes: QUINTRA_KEEP_INTRO=1 and
QUINTRA_KEEP_VIGNETTES=1 opt out of the sitecustomize mutes.
"""
import io
import os
import re
import sys
from collections import Counter
from pathlib import Path

os.environ["QUINTRA_KEEP_INTRO"] = "1"
os.environ["QUINTRA_KEEP_VIGNETTES"] = "1"
from pyboy import PyBoy  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ROM = Path(os.environ.get("QUINTRA_TEST_ROM", ROOT / "rom/working/quintra.gbc"))
NOI = ROM.with_suffix(".noi")
if not NOI.exists():
    NOI = ROOT / "rom/working/quintra.noi"
NOI = NOI.read_text()


def sym(name):
    return int(re.search(rf"DEF {name} 0x([0-9A-F]+)", NOI).group(1), 16)


SCR, PL, DEMO = sym("_loop_current_screen"), sym("_player"), sym("_attract_demo")
TRACK, ROW = sym("_music_track_id"), sym("_music_row")
TITLE, CLASS_SELECT, RUN_INIT, INTRO, ROOM, VIGNETTE = 1, 2, 3, 4, 5, 6
HEROES = ["Wolfkin", "Sauran", "Corvin", "Picsean", "Vespine"]
SPR_CLASS_BASE, SPR_CLASS_WALK_A_BASE, STRIDE = 0, 82, 4   # render/tiles.h
S_FLIPX = 0x20
STAGE1_TRACK = 0
FAIL = []


def check(ok, msg):
    print(("ok   " if ok else "FAIL ") + msg, flush=True)
    if not ok:
        FAIL.append(msg)


class Emu:
    def __init__(self, ram=None):
        kw = {"ram_file": io.BytesIO(ram)} if ram is not None else {}
        self.pb = PyBoy(str(ROM), window="null", sound_emulated=False, cgb=True, **kw)
        self.m = self.pb.memory

    def scr(self):
        return self.m[SCR]

    def tick(self, n=1):
        for _ in range(n):
            self.pb.tick()

    def until(self, pred, limit):
        for i in range(limit):
            if pred():
                return i
            self.tick()
        return limit if pred() else -1

    def tap(self, button, n=3):
        self.pb.button_press(button)
        self.tick(n)
        self.pb.button_release(button)
        self.tick(2)

    def s16(self, a):
        v = self.m[a] | (self.m[a + 1] << 8)
        return v - 65536 if v & 0x8000 else v

    def oam(self, i):
        b = 0xFE00 + 4 * i
        return self.m[b], self.m[b + 1], self.m[b + 2], self.m[b + 3]

    def tile(self, t):
        a = 0x8000 + 16 * t
        return bytes(self.m[0, a:a + 16])

    def stop_ram(self):
        buf = io.BytesIO()
        self.pb.stop(save=True, ram_file=buf)
        return buf.getvalue()


def to_title(e, path):
    """Power-on to the title by the given path."""
    n = e.until(lambda: e.scr() == INTRO, 600)
    if path in ("start", "a", "b"):
        e.tick(30)
        e.tap(path)
    n = e.until(lambda: e.scr() == TITLE, 2400)
    if path == "played" and n < 1200:
        return False    # the intro must really play out (~24 s)
    if path == "after_demo" and n >= 0:
        if e.until(lambda: e.m[DEMO] == 1, 900) < 0:
            return False
        e.until(lambda: e.m[DEMO] == 0, 3200)
        n = e.until(lambda: e.scr() == TITLE and not e.m[DEMO], 200)
    return n >= 0


def hero_tiles(cls):
    base = [SPR_CLASS_BASE + cls * STRIDE + k for k in range(4)]
    walk = [SPR_CLASS_WALK_A_BASE + cls * STRIDE + k for k in range(4)]
    return set(base + walk)


def assert_room(e, label, cls, art=None):
    """Room built, hero inside it, class art on OAM, stage music running."""
    e.tick(120)
    img = e.pb.screen.image.convert("RGB")
    px = list(img.crop((0, 0, 160, 128)).getdata())   # above the HUD
    top = Counter(px).most_common(1)[0][1] / len(px)
    colours = len(set(px))
    check(colours >= 8 and top < 0.85,
          f"{label}: room renders ({colours} colours, top colour {top:.0%})")
    x, y = e.s16(PL + 9), e.s16(PL + 11)
    check(x >= 16 and y >= 16, f"{label}: hero spawns inside the room at ({x},{y})")
    oy, ox = e.oam(0)[0], e.oam(0)[1]
    check(oy > 24 + 16 or ox > 24 + 8, f"{label}: hero OAM not in the top-left corner ({ox},{oy})")
    tiles = {e.oam(i)[2] for i in range(4)}
    check(e.m[PL] == cls, f"{label}: player class is {HEROES[cls]}")
    room_art = {t: e.tile(t) for t in hero_tiles(cls)}
    if art is not None:
        bad = [t for t, b in art.items() if room_art.get(t) != b]
        check(not bad, f"{label}: vignette champion VRAM matched room art (tiles differing: {bad})")
    r0 = e.m[ROW]
    e.tick(120)
    check(e.m[TRACK] == STAGE1_TRACK and e.m[ROW] != r0,
          f"{label}: stage 1 music playing (track {e.m[TRACK]}, row {r0}->{e.m[ROW]})")
    check(tiles <= hero_tiles(cls) | {b + cls * STRIDE + k for b in (160, 180) for k in range(4)},
          f"{label}: hero OAM tiles {sorted(tiles)}")


def new_game(path, cls):
    label = f"{HEROES[cls]} new game, intro {path}"
    e = Emu()
    check(to_title(e, path), f"{label}: reached the title")
    e.tick(30)
    e.tap("start")
    check(e.until(lambda: e.scr() == CLASS_SELECT, 200) >= 0, f"{label}: class select")
    e.tick(30)
    for _ in range(cls):
        e.tap("down")
        e.tick(6)
    e.tap("a")
    check(e.until(lambda: e.scr() == VIGNETTE, 120) >= 0, f"{label}: Crystal Caverns vignette plays")
    flips, foreign, art = 0, set(), {}
    allowed = hero_tiles(cls)
    for _ in range(600):
        e.tick()
        if e.scr() != VIGNETTE:
            break
        for i in range(4):
            y, x, t, a = e.oam(i)
            if y == 0 or y >= 160:
                continue
            if a & S_FLIPX:
                flips += 1
            if t not in allowed:
                foreign.add(t)
            elif t not in art:
                art[t] = e.tile(t)
    check(flips == 0, f"{label}: vignette champion never mirrored ({flips} flipped OAM samples)")
    check(not foreign and art, f"{label}: vignette champion uses {HEROES[cls]} tiles (foreign {sorted(foreign)})")
    n = e.until(lambda: e.scr() == ROOM, 300)
    check(n >= 0, f"{label}: vignette hands to the room")
    assert_room(e, label, cls, art)
    e.tick(240)   # first room writes the suspend save
    return e.stop_ram()


def continue_run(ram, path, cls):
    label = f"{HEROES[cls]} Continue, intro {path}"
    e = Emu(ram)
    check(to_title(e, path), f"{label}: reached the title")
    e.tick(30)
    e.tap("a")
    check(e.until(lambda: e.scr() == ROOM, 600) >= 0, f"{label}: Continue lands in the room")
    assert_room(e, label, cls)
    e.pb.stop(save=False)


def power_cycle_mid_foyer(cls):
    """Power off during the foyer vignette: Continue (if offered) is sane."""
    label = f"{HEROES[cls]} power-cycle mid-foyer vignette"
    e = Emu()
    to_title(e, "start")
    e.tick(30)
    e.tap("start")
    e.until(lambda: e.scr() == CLASS_SELECT, 200)
    e.tick(30)
    for _ in range(cls):
        e.tap("down")
        e.tick(6)
    e.tap("a")
    e.until(lambda: e.scr() == VIGNETTE, 120)
    e.tick(60)
    ram = e.stop_ram()
    e = Emu(ram)
    to_title(e, "start")
    e.tick(30)
    e.tap("a")
    if e.until(lambda: e.scr() == ROOM, 600) >= 0:
        assert_room(e, label + ", Continue", cls)
    else:
        check(e.scr() == TITLE, f"{label}: no Continue offered, title holds ({e.scr()})")
    e.pb.stop(save=False)


def main():
    paths = os.environ.get("QUINTRA_NEW_GAME_PATHS", "start,a,b,played,after_demo").split(",")
    for cls in range(len(HEROES)):
        ram = None
        for path in paths:
            r = new_game(path, cls)
            ram = ram or r
        for path in ("start", "played"):
            continue_run(ram, path, cls)
        power_cycle_mid_foyer(cls)
    if FAIL:
        print(f"{len(FAIL)} failure(s)")
        sys.exit(1)
    print("new game start OK")


if __name__ == "__main__":
    main()
