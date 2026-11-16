#!/usr/bin/env python3
"""Mid-room BG palette writes must heal if the LCD drops some of them.

Carmelo (MiSTer, Stage 2): room colours "changed quickly to like a brown
colour while in the room", and opening the menu fixed them. The stage-entry
reveal (and the boss-arena pop, Blind, HUD pulses) call palette_bg_load from
room_tick with the LCD on. A CGB ignores BCPD writes in STAT mode 3, so on
hardware part of the pop can be lost and the room keeps a mix of dimmed and
full bytes -- Verdant green turns brown -- until a menu reloads the palettes.

PyBoy never drops those writes, so this test models the hardware: every
palette_bg_load of a room slot (0..4) made with the LCD on loses the high
byte of each colour (the old dimmed byte survives). The ROM must re-commit
the requested colours during VBlank within a few frames.
"""

import io
import os
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = Path(os.environ.get("QUINTRA_TEST_ROM", ROOT / "rom/working/quintra.gbc"))
NOI = ROM.with_suffix(".noi").read_text()
SHOTS = Path(os.environ.get("QUINTRA_PALETTE_SHOTS", ROOT / "tmp/palette-heal"))
BLANK_SRAM = bytes(32 * 1024)
CODE = ("up", "right", "down", "left", "right",
        "up", "left", "down", "b", "a")
HEAL_FRAMES = 6


def sym(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    assert match, f"missing linker symbol {name}"
    return int(match.group(1), 16)


SCREEN = sym("_loop_current_screen")
RUN_STATE = sym("_run_state")
PLAYER = sym("_player")
LOAD = sym("_palette_bg_load")


def press(pb, button, frames=4):
    pb.button(button)
    pb.tick(frames)


def bg_palette(pb):
    out = []
    for i in range(64):
        pb.memory[0xFF68] = i
        out.append(pb.memory[0xFF69])
    return out


def put_bg_bytes(pb, index, values):
    pb.memory[0xFF68] = 0x80 | index
    for value in values:
        pb.memory[0xFF69] = value


def warp_stage2(title_wait):
    """Rift Index -> Stage 2 (Verdant Hollow), Normal, first champion."""
    pb = PyBoy(str(ROM), window="null", cgb=True,
               ram_file=io.BytesIO(BLANK_SRAM))
    pb.tick(240 + title_wait)
    for button in CODE:
        press(pb, button)
    press(pb, "down")
    press(pb, "a", 20)
    press(pb, "a")
    return pb


def run_seed(title_wait, shot_name=None):
    pb = warp_stage2(title_wait)
    pending = []

    def on_load(_):
        slot = pb.register_file.A & 7
        if slot > 4 or not (pb.memory[0xFF40] & 0x80):
            return
        if pb.memory[SCREEN] != 5:
            return
        de = (pb.register_file.D << 8) | pb.register_file.E
        new = [pb.memory[de + i] for i in range(8)]
        old = bg_palette(pb)[slot * 8:slot * 8 + 8]
        pending.append((slot, old, new))

    pb.hook_register(0, LOAD, on_load, None)
    entered = None
    mid_room = 0
    worst = 0
    expected = {}
    corrupted_frames = 0
    for frame in range(900):
        pb.memory[PLAYER + 2] = pb.memory[PLAYER + 1]  # stay alive
        pb.tick()
        if pb.memory[SCREEN] == 5 and entered is None:
            entered = frame
            assert pb.memory[RUN_STATE + 11] == 1, "warp did not reach Stage 2"
        # Hardware model: the high byte of every mid-frame colour is lost.
        for slot, old, new in pending:
            mixed = [new[i] if i % 2 == 0 else old[i] for i in range(8)]
            put_bg_bytes(pb, slot * 8, mixed)
            expected[slot] = new
            mid_room += 1
            if shot_name and corrupted_frames == 0:
                corrupted_frames = 1
        pending.clear()
        if entered is not None and frame > entered + 120:
            break
        if shot_name and corrupted_frames:
            corrupted_frames += 1
            if corrupted_frames == 12:
                SHOTS.mkdir(parents=True, exist_ok=True)
                pb.screen.image.save(str(SHOTS / shot_name))
    assert entered is not None, "Stage 2 never reached gameplay"
    assert mid_room, "no mid-room room-palette write observed (stage reveal)"
    # Let any queued VBlank commit run, then demand the requested colours.
    pb.tick(HEAL_FRAMES)
    pal = bg_palette(pb)
    bad = {slot: (pal[slot * 8:slot * 8 + 8], want)
           for slot, want in expected.items()
           if pal[slot * 8:slot * 8 + 8] != want}
    seed = int.from_bytes(bytes(pb.memory[RUN_STATE + 2:RUN_STATE + 6]), "little")
    pb.stop(save=False)
    assert not bad, (
        f"seed {seed:#010x}: room palettes still corrupted "
        f"{HEAL_FRAMES} frames after a dropped mid-room write: {bad}")
    return seed, mid_room


def main():
    seeds = []
    for i, wait in enumerate((0, 37, 91, 143, 211)):
        seeds.append(run_seed(wait, "stage2-reveal.png" if i == 0 else None))
    assert len({s for s, _ in seeds}) >= 3, f"seeds did not vary: {seeds}"
    print(f"[palette-heal] PASS {len(seeds)} Stage 2 seeds heal dropped "
          f"mid-room palette writes: " + ", ".join(f"{s:#010x}" for s, _ in seeds))


if __name__ == "__main__":
    main()
