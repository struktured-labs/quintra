#!/usr/bin/env python3
"""4x GIFs: each basilisk tier charging and firing, and a Fuse Hurler blast.

  PYTHONPATH=scripts/quintra_sitecustomize:scripts python3 scripts/record_basilisk_gifs.py
Writes to $QUINTRA_GIF_OUT (default /tmp/quintra-basilisk-gifs).
"""
import os
from pathlib import Path
from quintra_new_monsters import (
    boot, spawn_arena, poke_enemy, PLAYER,
    ENEMY_LEYBEAM, ENEMY_SUN_BASILISK, ENEMY_NOX_BASILISK, ENEMY_FUSE_HURLER,
    OFF_AI2,
)
from record_new_monster_gifs import grab
from test_will_max import put16

OUT = Path(os.environ.get("QUINTRA_GIF_OUT", "/tmp/quintra-basilisk-gifs"))
OUT.mkdir(parents=True, exist_ok=True)


def save_gif(name, frames, duration=40):
    path = OUT / name
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=duration, loop=0, optimize=False)
    print("wrote", path, "frames", len(frames), "bytes", path.stat().st_size)
VOID_OBJ6 = [(0, 0, 0), (13, 6, 20), (3, 1, 7), (20, 31, 18)]


def obj_palette(pb, n, colours):
    """The arena boots in Crystal Caverns; show pal 6 as the Void Sanctum sets it."""
    pb.memory[0xFF6A] = 0x80 | (n * 8)
    for r, g, b in colours:
        v = r | (g << 5) | (b << 10)
        pb.memory[0xFF6B] = v & 0xFF
        pb.memory[0xFF6B] = v >> 8


def tier_gif(enemy_id, cool, name, frames_n=150):
    pb = boot(0)
    spawn_arena(pb)
    e = poke_enemy(pb, enemy_id, 32, 72, hp=30, timer=cool - 20)
    frames, done = [], 0
    for i in range(frames_n):
        put16(pb, PLAYER + 9, 112)
        put16(pb, PLAYER + 11, 92)
        pb.memory[PLAYER + 15] = 0
        if enemy_id == ENEMY_NOX_BASILISK:
            obj_palette(pb, 6, VOID_OBJ6)
        pb.tick()
        if i % 2 == 0:
            frames.append(grab(pb, 4))
        if pb.memory[e + OFF_AI2] == 2:
            done = 1
        elif done and pb.memory[e + OFF_AI2] == 0:
            done += 1
            if done > 12:
                break
    save_gif(name, frames, duration=40)
    pb.stop(save=False)


def blast_gif():
    pb = boot(0)
    spawn_arena(pb)
    e = poke_enemy(pb, ENEMY_FUSE_HURLER, 40, 72, hp=12)
    pb.memory[e + 18] = 46  # about to wind up the lob
    frames = []
    for i in range(130):
        put16(pb, PLAYER + 9, 112)
        put16(pb, PLAYER + 11, 72)
        pb.memory[PLAYER + 15] = 0
        pb.tick()
        frames.append(grab(pb, 4))
    save_gif("fuse-blast-4x.gif", frames, duration=20)
    pb.stop(save=False)


def main():
    tier_gif(ENEMY_LEYBEAM, 100, "basilisk-ley-16px-4x.gif")
    tier_gif(ENEMY_SUN_BASILISK, 96, "basilisk-sun-24px-4x.gif")
    tier_gif(ENEMY_NOX_BASILISK, 90, "basilisk-nox-32px-4x.gif")
    blast_gif()


if __name__ == "__main__":
    main()
