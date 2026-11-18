#!/usr/bin/env python3
"""WATCH INTRO on the records page (title SELECT): rewatch the lore intro.

* SELECT opens records; its tilemap gains the START WATCH INTRO row.
* START there plays the intro (SCREEN_INTRO), title music running.
* A, B and START skip it; SELECT and the D-pad do not.
* Skipped or played to the end, it hands back to the title, which reopens
  the records page (same tilemap as before the intro).
* It plays even with CUTSCENES OFF (asked for on demand).
* Afterwards B still backs out to the main title and START still starts a
  new game; title idle attract still runs.
"""
import io
import os
import re
import sys
from pathlib import Path

os.environ["QUINTRA_KEEP_INTRO"] = "1"
from pyboy import PyBoy  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ROM = Path(os.environ.get("QUINTRA_TEST_ROM", ROOT / "rom/working/quintra.gbc"))
NOI = ROM.with_suffix(".noi")
if not NOI.exists():
    NOI = ROOT / "rom/working/quintra.noi"
NOI = NOI.read_text()


def sym(name):
    return int(re.search(rf"DEF {name} 0x([0-9A-F]+)", NOI).group(1), 16)


SCR, DEMO, TRACK = sym("_loop_current_screen"), sym("_attract_demo"), sym("_music_track_id")
TITLE, CLASS_SELECT, INTRO = 1, 2, 4
SRAM_SIZE = 0x8000
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

    def bgmap(self):
        return bytes(self.m[0, 0x9800:0x9800 + 32 * 18])


def to_records(e):
    e.until(lambda: e.scr() == INTRO, 600)
    e.tick(30)
    e.tap("start")
    e.until(lambda: e.scr() == TITLE, 60)
    e.tick(30)
    title_map = e.bgmap()
    e.tap("select")
    e.tick(10)
    return title_map, e.bgmap()


def row(mp, r):
    return mp[r * 32:r * 32 + 20]


def watch_and_skip(button):
    e = Emu()
    title_map, rec = to_records(e)
    check(rec != title_map and e.scr() == TITLE, f"[{button}] SELECT opens the records page")
    check(any(row(rec, 16)), f"[{button}] records page has the WATCH INTRO row")
    e.tap("start")
    n = e.until(lambda: e.scr() == INTRO, 10)
    check(n >= 0, f"[{button}] START on records plays the intro")
    e.tick(200)
    check(e.scr() == INTRO, f"[{button}] intro still playing after 200 frames")
    for other in ("select", "left", "up"):
        e.tap(other)
        e.tick(4)
    check(e.scr() == INTRO, f"[{button}] SELECT / D-pad do not skip the watched intro")
    e.tap(button)
    n = e.until(lambda: e.scr() == TITLE, 30)
    check(n >= 0, f"[{button}] {button.upper()} skips back to the title")
    e.tick(20)
    check(e.bgmap() == rec, f"[{button}] the title reopens the records page")
    check(e.scr() == TITLE, f"[{button}] the skip press did not act on the records page")
    e.tap("b")
    e.tick(10)
    check(row(e.bgmap(), 16) == row(title_map, 16) and e.scr() == TITLE,
          f"[{button}] B backs out to the main title")
    e.tick(20)
    e.tap("start")
    n = e.until(lambda: e.scr() == CLASS_SELECT, 60)
    check(n >= 0, f"[{button}] START on the main title still starts a new game")
    e.pb.stop(save=False)


def watch_to_end(ram=None, label="played out"):
    e = Emu(ram)
    if ram is not None:
        e.until(lambda: e.scr() == TITLE, 200)
        e.tick(30)
        title_map = e.bgmap()
        e.tap("select")
        e.tick(10)
        rec = e.bgmap()
    else:
        title_map, rec = to_records(e)
    e.tap("start")
    check(e.until(lambda: e.scr() == INTRO, 10) >= 0, f"[{label}] START on records plays the intro")
    e.tick(60)
    check(e.m[TRACK] != 0xFF, f"[{label}] music plays during the intro (track {e.m[TRACK]})")
    n = e.until(lambda: e.scr() != INTRO, 1800)
    check(n > 1200 and e.scr() == TITLE, f"[{label}] full intro ({n} frames) hands back to the title")
    e.tick(20)
    check(e.bgmap() == rec, f"[{label}] the title reopens the records page")
    e.tap("b")
    e.tick(10)
    e.until(lambda: e.m[DEMO] == 1 or e.scr() == INTRO, 900)
    check(e.m[DEMO] == 1 or e.scr() == INTRO, f"[{label}] title idle attract still runs afterwards")
    e.pb.stop(save=False)


def cutscenes_off_ram():
    ram = bytearray(SRAM_SIZE)
    rec = [ord("Q"), ord("M"), 2, 0xD2, 0x04, 3, 0, 0, 0, 0xFF, 0xFF, 0x04]
    rec.append(sum(rec) & 0xFF)
    ram[0x2000:0x2000 + 13] = bytes(rec)
    return bytes(ram)


def main():
    for button in ("a", "b", "start"):
        watch_and_skip(button)
    watch_to_end()
    watch_to_end(cutscenes_off_ram(), "CUTSCENES OFF")
    if FAIL:
        print(f"{len(FAIL)} failure(s)")
        sys.exit(1)
    print("watch intro OK")


if __name__ == "__main__":
    main()
