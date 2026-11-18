#!/usr/bin/env python3
"""Lore intro and attract mode (spec 2026-11-17 attract addendum).

1. Power-on plays the intro; A, B and START skip it to the title at any
   point, and an unskipped intro hands to the title on its own.
2. CUTSCENES OFF (meta flag 0x04) skips the power-on intro.
3. Twelve idle seconds on the title start attract: demo after a boot intro,
   then the intro replay, then the next demo, back to the title each time.
4. Any button during a demo or an intro replay returns to the title, also
   a button the demo itself is holding at that moment.
5. A demo run leaves all cart RAM byte-identical (suspend save and trophies).
6. Demo playback follows its recording (deterministic seed and input).
7. Continue after a demo resumes the suspended run, not the demo's state.

The other PyBoy tests mute the intro through _attract_mute (sitecustomize);
this one opts out with QUINTRA_KEEP_INTRO=1.
"""
import io
import json
import os
import re
import sys
from pathlib import Path

os.environ["QUINTRA_KEEP_INTRO"] = "1"
from pyboy import PyBoy  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ROM = Path(os.environ.get("QUINTRA_TEST_ROM", ROOT / "rom/working/quintra.gbc"))
NOI = ROM.with_suffix(".noi").read_text()


def sym(name):
    return int(re.search(rf"DEF {name} 0x([0-9A-F]+)", NOI).group(1), 16)


SCR, CNT, MUTE = sym("_loop_current_screen"), sym("_loop_frame_counter"), sym("_attract_mute")
DEMO, PL = sym("_attract_demo"), sym("_player")
KEYS, RS = sym("_input_keys"), sym("_run_state")
TITLE, CLASS_SELECT, RUN_INIT, INTRO, ROOM, DIALOG = 1, 2, 3, 4, 5, 10
IDLE = 720                 # ATTRACT_TITLE_IDLE
DEMO_FRAMES = 900          # ATTRACT_DEMO_FRAMES (loop iterations)
DEMO_WALL = 3000           # PyBoy frames: busy rooms run below 60 Hz
DEMOS = ["assets/attract/demo_wolfkin_crystal.json", "assets/attract/demo_picsean_verdant.json"]
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
        self.frame = 0

    def scr(self):
        return self.m[SCR]

    def cnt(self):
        return self.m[CNT] | (self.m[CNT + 1] << 8)

    def tick(self, n=1):
        for _ in range(n):
            self.pb.tick()
            self.frame += 1

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

    def sram(self):
        """All four cart RAM banks, read straight from the cartridge."""
        out = bytearray()
        for bank in range(4):
            out += bytes(self.m[bank, 0xA000:0xBFFF]) + bytes([self.m[bank, 0xBFFF]])
        return bytes(out)

    def stop_ram(self):
        buf = io.BytesIO()
        self.pb.stop(save=True, ram_file=buf)
        return buf.getvalue()


def boot_to_intro(e):
    """Run the boot ROM until the game is ticking the intro."""
    return e.until(lambda: e.scr() == INTRO and e.cnt() > 4, 400)


def skip_boot(e):
    boot_to_intro(e)
    e.tap("start")
    return e.until(lambda: e.scr() == TITLE, 30)


def with_meta(ram, flags):
    """Valid v2 trophy record in SRAM bank 1: best 1234, 3 runs, no win."""
    ram = bytearray(ram.ljust(SRAM_SIZE, b"\0"))
    rec = [ord("Q"), ord("M"), 2, 0xD2, 0x04, 3, 0, 0, 0, 0xFF, 0xFF, flags]
    rec.append(sum(rec) & 0xFF)
    ram[0x2000:0x2000 + 13] = bytes(rec)
    return bytes(ram)


def make_save():
    """A real suspend save: start a Wolfkin run and let the first room save."""
    e = Emu()
    skip_boot(e)
    e.tick(30); e.tap("start")
    e.until(lambda: e.scr() == CLASS_SELECT, 120); e.tick(30)
    e.tap("a")
    e.until(lambda: e.scr() == ROOM, 600); e.tick(240)
    return with_meta(e.stop_ram(), 0)


def test_boot_intro():
    e = Emu()
    check(boot_to_intro(e) >= 0, "power-on lands on the intro")
    e.tick(300)
    check(e.scr() == INTRO, "intro still playing after 5 s with no input")
    n = e.until(lambda: e.scr() == TITLE, 1500)
    check(n >= 0, f"unskipped intro hands to the title ({e.frame} frames after power-on)")
    e.pb.stop(save=False)
    for button, at in (("start", 0), ("a", 20), ("b", 500), ("start", 900)):
        e = Emu()
        boot_to_intro(e)
        e.tick(at)
        was = e.scr()
        e.tap(button)
        n = e.until(lambda: e.scr() == TITLE, 30)
        check(was == INTRO and n >= 0, f"{button.upper()} at intro frame {at} skips to the title")
        e.tick(60)
        check(e.scr() == TITLE, f"title holds after the {button.upper()} skip")
        e.pb.stop(save=False)


def test_cutscenes_off(save):
    e = Emu(with_meta(save, 0x04))
    n = e.until(lambda: e.scr() == TITLE, 140)
    check(n >= 0, "CUTSCENES OFF skips the power-on intro")
    e.pb.stop(save=False)


def demo_trace(e, rel, frames):
    """Follow one demo; compare the player position at every input_poll.

    The recorder samples at input_poll entry as well (PyBoy ticks and loop
    iterations do not line up one to one), so the traces match exactly as
    long as playback is deterministic.
    """
    want = [tuple(p[:2]) for p in json.loads((ROOT / rel).read_text())["trace"]]
    got = []
    state = {"started": False}

    def on_poll(_ctx):
        if e.m[DEMO] and e.scr() in (ROOM, DIALOG):
            state["started"] = True
        if state["started"] and e.m[DEMO]:
            got.append((e.s16(PL + 9), e.s16(PL + 11)))

    e.pb.hook_register(0, sym("_input_poll"), on_poll, None)
    for _ in range(frames):
        e.tick()
        if not e.m[DEMO]:
            break
    e.pb.hook_deregister(0, sym("_input_poll"))
    n = min(len(got), len(want))
    drift = next((i for i in range(n) if want[i] != got[i]), None)
    return n, drift


def test_demos(save):
    for k, rel in enumerate(DEMOS):
        e = Emu(save)
        skip_boot(e)
        if k == 1:      # demo 1 comes after demo 0 and the intro replay
            e.until(lambda: e.m[DEMO] == 1, IDLE + 120)
            e.until(lambda: e.m[DEMO] == 0, DEMO_WALL)
            e.until(lambda: e.scr() == INTRO, IDLE + 120)
            e.until(lambda: e.scr() == TITLE, 1700)
        else:
            e.tick(IDLE - 40)
            check(e.scr() == TITLE and not e.m[DEMO], "title holds before the idle timeout")
        sram0 = e.sram()
        n = e.until(lambda: e.m[DEMO] == 1, IDLE + 120)
        check(n >= 0, f"demo {k} starts from title idle")
        cnt, drift = demo_trace(e, rel, DEMO_WALL)
        check(cnt > DEMO_FRAMES - 20 and drift is None,
              f"demo {k} follows its recording ({cnt} frames compared, first drift {drift})")
        n = e.until(lambda: e.scr() == TITLE, 120)
        check(n >= 0 and not e.m[DEMO], f"demo {k} ends on the title by itself")
        check(e.sram() == sram0, f"demo {k} leaves cart RAM byte-identical")
        e.tick(30)
        ram = e.stop_ram()
        check(ram[:SRAM_SIZE] == sram0, f"demo {k}: battery file unchanged")


def test_exit_and_loop(save):
    e = Emu(save)
    skip_boot(e)
    sram0 = e.sram()
    order = []
    for cycle, button in enumerate(("a", "b", "start", "select", "left")):
        e.until(lambda: e.m[DEMO] == 1 or e.scr() == INTRO, IDLE + 120)
        kind = "demo" if e.m[DEMO] else "intro" if e.scr() == INTRO else None
        order.append(kind)
        check(kind is not None, f"cycle {cycle}: title idle starts attract ({kind})")
        e.tick(200 + 37 * cycle)
        # A busy room loop can take three frames between joypad polls; a
        # four-frame tap is the shortest press a player can rely on.
        e.tap(button, 4)
        n = e.until(lambda: e.scr() == TITLE and not e.m[DEMO], 30)
        check(n >= 0, f"cycle {cycle}: {button.upper()} during the {kind} returns to the title")
        e.tick(90)
        check(e.scr() == TITLE, f"cycle {cycle}: {button.upper()} did not start a game")
    check(order == ["demo", "intro", "demo", "intro", "demo"], f"attract alternates demo/intro: {order}")
    check(e.sram() == sram0, "cart RAM unchanged after five interrupted cycles")
    e.tick(20); e.tap("start")
    n = e.until(lambda: e.scr() != TITLE, 60)
    check(n >= 0 and e.scr() in (CLASS_SELECT, RUN_INIT, ROOM), f"START on the title still starts a game (screen {e.scr()})")
    e.pb.stop(save=False)


def test_held_key_exit(save):
    """A press of the key the demo is holding still ends the demo."""
    e = Emu(save)
    skip_boot(e)
    e.until(lambda: e.m[DEMO] == 1, IDLE + 120)
    e.until(lambda: e.scr() == ROOM, 300)
    n = e.until(lambda: e.m[KEYS] & 0x10, 600)
    check(n >= 0, "demo 0 holds A at some point")
    e.pb.button_press("a")
    n = e.until(lambda: e.scr() == TITLE and not e.m[DEMO], 6)
    e.tick(20)
    e.pb.button_release("a")
    check(n >= 0, "pressing A while the demo holds A returns to the title")
    e.tick(60)
    check(e.scr() == TITLE, "A held through the hand-back does not act on the title")
    e.pb.stop(save=False)


def continue_state(e):
    e.tap("a")
    e.until(lambda: e.scr() == ROOM, 600)
    e.tick(2)
    return bytes(e.m[PL:PL + 48]), bytes(e.m[RS:RS + 60])


def test_continue_after_demo(save):
    e = Emu(save)
    skip_boot(e)
    e.tick(30)
    want = continue_state(e)
    e.pb.stop(save=False)
    e = Emu(save)
    skip_boot(e)
    e.until(lambda: e.m[DEMO] == 1, IDLE + 120)
    e.until(lambda: e.m[DEMO] == 0, DEMO_WALL)
    e.until(lambda: e.scr() == TITLE, 120)
    e.tick(30)
    got = continue_state(e)
    check(got[0] == want[0], "Continue after a demo restores the saved hero")
    check(got[1] == want[1], "Continue after a demo restores the saved run state")
    e.pb.stop(save=False)


def main():
    test_boot_intro()
    save = make_save()
    check(save[:2] == b"QS", "fixture has a suspend save")
    test_cutscenes_off(save)
    test_exit_and_loop(save)
    test_demos(save)
    test_held_key_exit(save)
    test_continue_after_demo(save)
    if FAIL:
        print(f"{len(FAIL)} failure(s)")
        sys.exit(1)
    print("attract mode OK")


if __name__ == "__main__":
    main()
