#!/usr/bin/env python3
"""4x GIFs of the new specialists for /workspace/quintra-monsters/."""
import os
from pathlib import Path
from PIL import Image
from quintra_new_monsters import (
    boot, spawn_arena, poke_enemy, PLAYER,
    ENEMY_VEIL_MAGUS, ENEMY_VAULT_HAND, ENEMY_BANE_BRUTE, ENEMY_LEYBEAM,
    ENEMY_HEX_WALKER, ENEMY_ZAG_DART, ENEMY_FUSE_HURLER, OFF_AI2,
)
from test_will_max import put16

OUT = Path(os.environ.get("QUINTRA_GIF_OUT", "/tmp/quintra-monsters-gifs"))
OUT.mkdir(parents=True, exist_ok=True)


def grab(pb, scale=4):
    im = pb.screen.image.convert("RGB")
    if scale != 1:
        im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    return im


def save_gif(name, frames, duration=80):
    if not frames:
        raise SystemExit(f"no frames for {name}")
    path = OUT / name
    frames[0].save(path, save_all=True, append_images=frames[1:],
                   duration=duration, loop=0, optimize=False)
    print("wrote", path, "frames", len(frames), "bytes", path.stat().st_size)


def record(pb, n, every=2, scale=4):
    frames = []
    for i in range(n):
        pb.tick()
        if i % every == 0:
            frames.append(grab(pb, scale))
    return frames


def main():
    # --- Veil Magus: blink, tell, bolt ---
    pb = boot(0)
    spawn_arena(pb)
    poke_enemy(pb, ENEMY_VEIL_MAGUS, 48, 72, hp=12, damage=2)
    put16(pb, PLAYER + 9, 104)
    put16(pb, PLAYER + 11, 72)
    save_gif("veil-magus-4x.gif", record(pb, 180, every=2))
    pb.stop(save=False)

    # --- Vault Hand: shadow, drop, mash escape then a carry ---
    pb = boot(0)
    spawn_arena(pb)
    e = poke_enemy(pb, ENEMY_VAULT_HAND, 80, 40, hp=16, damage=1)
    put16(pb, PLAYER + 9, 80)
    put16(pb, PLAYER + 11, 80)
    frames = record(pb, 220, every=2)
    save_gif("vault-hand-4x.gif", frames)
    pb.stop(save=False)

    # --- Bane Brute shove ---
    pb = boot(0)
    spawn_arena(pb)
    poke_enemy(pb, ENEMY_BANE_BRUTE, 64, 72, hp=22, damage=2)
    put16(pb, PLAYER + 9, 88)
    put16(pb, PLAYER + 11, 72)
    pb.memory[PLAYER + 15] = 0
    save_gif("bane-brute-4x.gif", record(pb, 160, every=2))
    pb.stop(save=False)

    # --- Leybeam sidestep ---
    pb = boot(0)
    spawn_arena(pb)
    e = poke_enemy(pb, ENEMY_LEYBEAM, 40, 72, hp=14)
    put16(pb, PLAYER + 9, 96)
    put16(pb, PLAYER + 11, 72)
    frames = []
    for i in range(200):
        phase = pb.memory[e + OFF_AI2]
        if phase == 2 and i > 90:
            put16(pb, PLAYER + 9, 96)
            put16(pb, PLAYER + 11, 96)
            pb.memory[PLAYER + 15] = 120
        pb.tick()
        if i % 2 == 0:
            frames.append(grab(pb, 4))
    save_gif("leybeam-4x.gif", frames)
    pb.stop(save=False)

    # extras
    pb = boot(0)
    spawn_arena(pb)
    poke_enemy(pb, ENEMY_HEX_WALKER, 48, 80, hp=10)
    put16(pb, PLAYER + 9, 104)
    put16(pb, PLAYER + 11, 80)
    save_gif("hex-walker-4x.gif", record(pb, 160, every=2))
    pb.stop(save=False)

    pb = boot(0)
    spawn_arena(pb)
    poke_enemy(pb, ENEMY_ZAG_DART, 48, 72, hp=8, damage=2)
    put16(pb, PLAYER + 9, 104)
    put16(pb, PLAYER + 11, 72)
    save_gif("zag-dart-4x.gif", record(pb, 160, every=2))
    pb.stop(save=False)

    pb = boot(0)
    spawn_arena(pb)
    poke_enemy(pb, ENEMY_FUSE_HURLER, 48, 72, hp=12)
    put16(pb, PLAYER + 9, 100)
    put16(pb, PLAYER + 11, 72)
    save_gif("fuse-hurler-4x.gif", record(pb, 220, every=2))
    pb.stop(save=False)


if __name__ == "__main__":
    main()
