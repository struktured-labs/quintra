#!/usr/bin/env python3
"""Capture 4x GIFs of every hero's tap spell, hold ward and Wolfkin's claw."""
import sys
from pathlib import Path
sys.path.insert(0, 'scripts')
from test_magic import *   # noqa

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "tmp/magic_gifs")
OUT.mkdir(parents=True, exist_ok=True)
NAMES = ("moonfire", "flame_ward", "thunder", "stoneskin", "hex",
         "shadow_veil", "blizzard", "cure", "bramble", "thorn_mirror")


def grab(pb, frames, every=2, on_frame=None):
    out = []
    for f in range(frames):
        if on_frame:
            on_frame(f)
        pb.tick()
        if f % every == 0:
            out.append(pb.screen.image.convert("RGB").resize((640, 576), 0))
    return out


def save(frames, name):
    frames[0].save(OUT / f"{name}.gif", save_all=True, append_images=frames[1:],
                   duration=33, loop=0, optimize=True)
    print("wrote", OUT / f"{name}.gif")


def foes(pb, c):
    if c == 0:
        entity(pb, 0, 2, 124, 30, enemy_id=3); entity(pb, 1, 2, 130, 96, enemy_id=3)
    elif c == 1:
        entity(pb, 0, 2, 120, 64); entity(pb, 1, 2, 136, 84)
    elif c == 3:
        entity(pb, 0, 2, 120, 40, enemy_id=3)
    else:
        entity(pb, 0, 2, 104, 64); entity(pb, 1, 2, 126, 64); entity(pb, 2, 2, 116, 78)


for c in range(5):
    pb = boot(c)
    m = pb.memory
    # Tap spell.
    arena(pb); foes(pb, c)
    def tap_frame(f):
        if f == 0: pb.button_press("right")
        if f == 2: pb.button_press("b")
        if f == 5: pb.button_release("b")
        if f == 6: pb.button_release("right")
        if c == 3 and 10 <= f < 40: pb.button_press("up")
        if c == 3 and f == 40: pb.button_release("up")
    save(grab(pb, 90, on_frame=tap_frame), f"{c}_{HEROES[c].lower()}_tap_{NAMES[c*2]}")
    # Hold ward, with shots for wards that answer them.
    arena(pb)
    m[PLAYER + PL_HP] = m[PLAYER + PL_HP_MAX] - 3
    if c in (0, 4):
        entity(pb, 0, 1, 150, 64, hp=1, vx=-1); entity(pb, 1, 1, 72, 10, hp=1, vy=1)
    if c == 1:
        entity(pb, 0, 2, 96, 64)
    def hold_frame(f):
        if f == 0: pb.button_press("b")
        if f == 32: pb.button_release("b")
    save(grab(pb, 120, on_frame=hold_frame), f"{c}_{HEROES[c].lower()}_hold_{NAMES[c*2+1]}")
    if c == 0:
        arena(pb)
        entity(pb, 0, 2, 92, 64, enemy_id=3); entity(pb, 1, 2, 88, 80, enemy_id=3)
        def claw_frame(f):
            if f == 0: pb.button_press("right"); pb.button_press("a")
            if f == 50: pb.button_release("a"); pb.button_release("right")
        save(grab(pb, 70, on_frame=claw_frame), "0_wolfkin_a_fang_claw")
    pb.stop(save=False)
