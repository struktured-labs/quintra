#!/usr/bin/env python3
"""Force a combat death and grab headless Game Over stills + a GIF.

usage: capture_gameover.py --rom PATH --noi PATH --out DIR [--label before]
"""
import argparse
import re
import shutil
import tempfile
from pathlib import Path

from PIL import Image
from pyboy import PyBoy

# Keep this in lockstep with scripts/test_gameover.py's death injection.


def font_tiles(text):
    return bytes(0 if char == " " else ord(char) - ord("A") + 11
                 for char in text)


def addr(noi, name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", noi)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


def press(pb, button, held=4, released=4):
    pb.button_press(button)
    for _ in range(held):
        pb.tick()
    pb.button_release(button)
    for _ in range(released):
        pb.tick()


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def boot_fresh_run(pb, screen):
    for _ in range(240):
        pb.tick()
    press(pb, "start")
    for _ in range(30):
        pb.tick()
    press(pb, "a")
    for _ in range(80):
        pb.tick()
    assert pb.memory[screen] == 5, "did not enter SCREEN_ROOM"


def scale(im, n=4):
    return im.resize((im.size[0] * n, im.size[1] * n), Image.NEAREST)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", required=True, type=Path)
    ap.add_argument("--noi", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--label", default="shot")
    args = ap.parse_args()
    noi_path = args.noi or args.rom.with_suffix(".noi")
    noi = noi_path.read_text()
    rs, pl, en, screen = map(
        lambda n: addr(noi, n),
        ("_run_state", "_player", "_entities", "_loop_current_screen"),
    )
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    label = args.label

    with tempfile.TemporaryDirectory(prefix="quintra-go-cap-") as td:
        cart = Path(td) / "quintra.gbc"
        shutil.copy2(args.rom, cart)
        pb = PyBoy(str(cart), window="null", cgb=True)
        boot_fresh_run(pb, screen)
        pb.memory[rs + 16] = 7
        pb.memory[pl + 2] = 1
        pb.memory[pl + 15] = 0
        px = pb.memory[pl + 9] | (pb.memory[pl + 10] << 8)
        py = pb.memory[pl + 11] | (pb.memory[pl + 12] << 8)
        projectile = next(
            en + i * 28 for i in range(32) if not (pb.memory[en + i * 28 + 1] & 1)
        )
        for i in range(28):
            pb.memory[projectile + i] = 0
        pb.memory[projectile] = 1
        pb.memory[projectile + 1] = 3
        put_fix8(pb, projectile + 2, px + 5)
        put_fix8(pb, projectile + 6, py + 9)
        pb.memory[projectile + 14] = 1
        pb.memory[projectile + 16] = 20
        pb.memory[projectile + 25] = 0x77
        pb.memory[projectile + 26] = 4

        frames = []
        entered = False
        go_off = 0
        stills = {0: "enter", 20: "lock-end", 50: "rise-mid",
                  80: "risen", 110: "shards", 130: "text", 180: "hold"}
        saved = set()
        for i in range(600):
            pb.tick()
            if not entered:
                if pb.memory[screen] == 11:
                    entered = True
                    go_off = 0
                continue
            img = pb.screen.image.copy()
            if go_off % 2 == 0:
                frames.append(img)
            if go_off in stills and go_off not in saved:
                scale(img).save(out / f"{label}-{stills[go_off]}-{go_off:03d}.png")
                saved.add(go_off)
            go_off += 1
            if go_off >= 200:
                break
        assert entered, "never reached SCREEN_GAMEOVER"
        if 200 - 1 not in saved:
            scale(pb.screen.image.copy()).save(out / f"{label}-final.png")
        gif_frames = [scale(f) for f in frames[::2][:80]]
        if gif_frames:
            gif_path = out / f"{label}-anim.gif"
            gif_frames[0].save(
                gif_path, save_all=True, append_images=gif_frames[1:],
                duration=50, loop=0, optimize=False,
            )
            print(f"gif {gif_path} frames={len(gif_frames)}")
        pb.stop(save=False)
        print(f"stills {out} count={len(list(out.glob(label + '*.png')))} entered_at_ok")


if __name__ == "__main__":
    main()
