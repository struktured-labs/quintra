#!/usr/bin/env python3
"""Capture the settled, live-ROM title image used by the README."""
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom" / "working" / "quintra.gbc"
OUT = ROOT / "docs" / "media" / "title.png"


def main() -> None:
    if not ROM.exists():
        raise SystemExit("[title-media] missing built ROM")
    pb = PyBoy(str(ROM), window="null", cgb=True)
    # Let the real title enter load its font, palette, hero procession, and
    # first lore beat. This is a cartridge capture, not a mock or hand crop.
    pb.tick(240)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pb.screen.image.save(OUT)
    pb.stop(save=False)
    print(f"[title-media] wrote {OUT}")


if __name__ == "__main__":
    main()
