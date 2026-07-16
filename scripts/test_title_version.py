#!/usr/bin/env python3
"""The rendered cartridge title and README expose the same release version."""

import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom" / "working" / "quintra.gbc"
HEADER = ROOT / "src" / "game" / "version.h"
README = ROOT / "README.md"


def main():
    match = re.search(r'#define QUINTRA_VERSION "([^"]+)"', HEADER.read_text())
    assert match, "missing QUINTRA_VERSION"
    version = match.group(1)
    assert len(version) == 8, f"title version must fill exactly 8 columns: {version}"
    assert version in README.read_text(), "README latest version drifted from cartridge"

    pb = PyBoy(str(ROM), window="null", cgb=True)
    # Give the LCD several complete frames after title VRAM/font setup so the
    # captured evidence reflects the settled hardware image.
    for _ in range(240):
        pb.tick()

    # font_min maps digits 0..9 to tiles 1..10, punctuation to blank tile 0,
    # and lowercase 'v' to its compact-font V glyph at tile 32.
    expected = [32 if char == "v" else 0 if char == "." else int(char) + 1
                for char in version]
    title_row = 0x9800 + 17 * 32
    # font_min uses a packed, non-alphabetic glyph table.
    prompt = [29, 15, 22, 0, 28, 15, 13, 25, 28, 14]  # "SEL RECORD"
    assert list(pb.memory[title_row:title_row + 10]) == prompt, (
        "title SELECT prompt drifted"
    )
    assert pb.memory[title_row + 10] == 0, "title footer lost its version gutter"
    rendered = list(pb.memory[title_row + 11:title_row + 19])
    assert rendered == expected, (
        f"rendered title version drifted: expected {expected}, got {rendered}"
    )
    assert pb.memory[title_row + 19] == 0, "title footer touched scrolling corner"

    # Cycle past the long beat "FIVE SEAL THE RIFT", whose final T occupies
    # column 19. The following beat must erase that edge cell completely.
    for _ in range(1500):
        pb.tick()
    assert pb.memory[0x9800 + 8 * 32 + 19] == 0, \
        "intro lore left a glyph at the upper right edge"
    assert pb.memory[0x9800 + 9 * 32 + 19] == 0, \
        "intro lore left the trailing T from FIVE SEAL THE RIFT"
    screenshot = ROOT / "tmp" / "title-current-version.png"
    screenshot.parent.mkdir(exist_ok=True)
    pb.screen.image.save(screenshot)
    pb.stop(save=False)
    print(f"[title-version] PASS rendered {version} and README agree")


if __name__ == "__main__":
    main()
