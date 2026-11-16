#!/usr/bin/env python3
"""Capture Riftwild den screenshots and GIFs.

  capture_riftwild_dens.py OUT_DIR                 # after: full den run
  capture_riftwild_dens.py OUT_DIR --before ROM    # before: same fields on ROM
"""
import os
import sys
from pathlib import Path

from pyboy import PyBoy

if len(sys.argv) > 3 and sys.argv[2] == "--before":
    os.environ["QUINTRA_DENS_ROM"] = str(Path(sys.argv[3]).resolve())
import test_riftwild_dens as dens  # noqa: E402


def save(frames, out, prefix):
    out.mkdir(parents=True, exist_ok=True)
    for key, value in frames.items():
        if isinstance(value, list):
            scaled = [f.convert("RGB").resize((480, 432), 0) for f in value]
            scaled[0].save(out / f"{prefix}{key}.gif", save_all=True,
                           append_images=scaled[1:], duration=350, loop=0)
        else:
            value.convert("RGB").resize((480, 432), 0).save(out / f"{prefix}{key}.png")


def before(out):
    pb = PyBoy(str(dens.ROM), window="null", cgb=True)
    dens.enter_riftwild(pb)
    frames = {}
    for field in (dens.CAIRN_FIELD, dens.DROWNED_FIELD, dens.SCAR_FIELD):
        dens.teleport_field(pb, field)
        dens.snap(pb, frames, f"field{field}")
    pb.stop(save=False)
    save(frames, out, "before_")


def main():
    out = Path(sys.argv[1])
    if len(sys.argv) > 3 and sys.argv[2] == "--before":
        before(out)
        return
    save(dens.main(), out, "after_")


if __name__ == "__main__":
    main()
