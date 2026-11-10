#!/usr/bin/env python3
"""Headless title and class-select grabs. PyBoy only. No GUI.

Reads rom/working/quintra.gbc, which is gitignored, and writes native
160x144 PNGs. Not part of `make manual` and not run in CI.
"""

from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parents[3]
ROM = ROOT / "rom" / "working" / "quintra.gbc"
OUT = Path(__file__).resolve().parents[1] / "content" / "images"


def tap(pb, key, down=6, up=12):
    pb.button_press(key)
    pb.tick(down)
    pb.button_release(key)
    pb.tick(up)


def save(pb, name):
    pb.screen.image.save(OUT / name)
    print(name, pb.screen.image.size)


def main():
    if not ROM.is_file():
        raise SystemExit(f"missing {ROM}")
    OUT.mkdir(parents=True, exist_ok=True)
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    save(pb, "screen-title.png")
    tap(pb, "start", down=8, up=30)
    for _ in range(180):
        pb.tick()
    save(pb, "screen-classes.png")
    pb.stop()


if __name__ == "__main__":
    main()
