#!/usr/bin/env python3
"""The rendered cartridge title and README expose the same release version."""

import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom" / "working" / "quintra.gbc"
HEADER = ROOT / "src" / "game" / "version.h"
README = ROOT / "README.md"


def font_tiles(text):
    """Encode the uppercase/digit subset exposed by GBDK's compact font."""
    result = []
    for char in text:
        if "A" <= char <= "Z":
            result.append(11 + ord(char) - ord("A"))
        elif "0" <= char <= "9":
            result.append(1 + ord(char) - ord("0"))
        else:
            result.append(0)
    return result


def main():
    match = re.search(r'#define QUINTRA_VERSION "([^"]+)"', HEADER.read_text())
    assert match, "missing QUINTRA_VERSION"
    version = match.group(1)
    assert len(version) <= 8, f"title version exceeds title-footer space: {version}"
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
    records_row = 0x9800 + 16 * 32
    title_row = 0x9800 + 17 * 32
    prompt = font_tiles("SELECT RECORDS HELP")
    assert list(pb.memory[records_row + 1:records_row + 20]) == prompt, (
        "title SELECT prompt drifted"
    )
    assert pb.memory[records_row] == 0, "title records prompt lost its left gutter"
    rendered = list(pb.memory[title_row + 6:title_row + 6 + len(version)])
    assert rendered == expected, (
        f"rendered title version drifted: expected {expected}, got {rendered}"
    )
    assert all(pb.memory[title_row + col] == 0
               for col in (*range(6), *range(6 + len(version), 20))), \
        "title footer left stale version glyphs in its gutter"
    assert pb.memory[title_row + 19] == 0, "title footer touched scrolling corner"

    # Best score belongs to the SELECT → Records screen. The title used to
    # leave a bare number (for example "831") on row 15, which read as a
    # broken glyph in the lore tableau. Prove the live cartridge has an empty
    # row there rather than merely trusting the C source.
    title_score_row = 0x9800 + 15 * 32
    assert all(pb.memory[title_score_row + col] == 0 for col in range(20)), \
        "title retained a stray best-score number; it belongs in Records"

    # The lore is now a real procession: five existing champion metasprites
    # line up above the logo, each in either its idle or walk pose. Checking
    # OAM rather than a screenshot makes this a cartridge contract even when
    # a host's palette conversion differs.
    class_base, walk_base, stride = 0, 82, 4
    for champion in range(5):
        oam = 0xFE00 + champion * 4 * 4
        top_left = pb.memory[oam + 2]
        expected_idle = class_base + champion * stride
        expected_walk = walk_base + champion * stride
        assert top_left in (expected_idle, expected_walk), (
            f"title champion {champion} missing from spirit procession: tile={top_left}"
        )
        assert pb.memory[oam] >= 31 and pb.memory[oam + 1] >= 24, (
            f"title champion {champion} was parked instead of displayed"
        )

    # SELECT replaces the lore tableau with a full records page. No title
    # sprite may survive beneath those statistics; SELECT again must restore
    # the same five-spirit presentation before START reaches class select.
    pb.button("select")
    pb.tick(20)
    for sprite in range(20):
        oam = 0xFE00 + sprite * 4
        assert pb.memory[oam] == 0 and pb.memory[oam + 1] == 0, (
            f"title spirit OAM {sprite} leaked into records"
        )
    pb.button("select")
    pb.tick(20)
    assert pb.memory[0xFE00 + 2] in (class_base, walk_base), \
        "records exit did not restore the spirit procession"

    # Observe the long beat "FIVE SEAL THE RIFT", whose final T occupies
    # column 19, then prove its successor clears that exact edge. This is
    # intentionally event-based: menu round trips should not make a fixed
    # frame-count assertion accidentally sample the long beat itself.
    lore_edge = 0x9800 + 9 * 32 + 19
    for _ in range(2000):
        pb.tick()
        if pb.memory[lore_edge] != 0:
            break
    else:
        raise AssertionError("intro lore never rendered FIVE SEAL THE RIFT")
    for _ in range(400):
        pb.tick()
        if pb.memory[lore_edge] == 0:
            break
    else:
        raise AssertionError("intro lore left the trailing T from FIVE SEAL THE RIFT")
    assert pb.memory[0x9800 + 8 * 32 + 19] == 0, \
        "intro lore left a glyph at the upper right edge"
    screenshot = ROOT / "tmp" / "title-current-version.png"
    screenshot.parent.mkdir(exist_ok=True)
    pb.screen.image.save(screenshot)

    # The title owns OAM 0..19, whereas class select owns only 0..4. Leaving
    # the remaining procession sprites live would make ghost heroes appear on
    # the selection screen, so the real START transition must park them.
    pb.button("start")
    pb.tick(20)
    for sprite in range(5, 20):
        oam = 0xFE00 + sprite * 4
        assert pb.memory[oam] == 0 and pb.memory[oam + 1] == 0, (
            f"title spirit OAM {sprite} leaked into class select"
        )

    # The selector uses one plain-language row for each concept: role, A, B,
    # trait, then fully named stats. Pin Wolfkin's complete initial page on the
    # rendered 20-column cartridge screen rather than accepting abbreviations.
    class_rows = {
        9: "ROLE BLADE FIGHTER",
        10: "A STAB SLASH DASH",
        11: "B 8 SHOTS BRIEF WARD",
        12: "TRAIT FAST MOVEMENT",
        14: "HEALTH 14 MAGIC 4",
        15: "ATTACK 2 ARMOR 1",
        16: "SPEED 6 SEL>EASY",
    }
    for row, label in class_rows.items():
        expected_row = font_tiles(label)
        rendered_row = list(pb.memory[
            0x9800 + row * 32:0x9800 + row * 32 + len(expected_row)
        ])
        assert rendered_row == expected_row, (
            f"class-select row {row} is ambiguous or clipped: {rendered_row}"
        )
        assert all(pb.memory[0x9800 + row * 32 + col] == 0
                   for col in range(len(expected_row), 20)), (
            f"class-select row {row} left stale edge glyphs"
        )
    pb.button("select")
    pb.tick(8)
    easy_mode = font_tiles("SPEED 6 SEL>NORMAL")
    assert list(pb.memory[0x9800 + 16 * 32:
                          0x9800 + 16 * 32 + len(easy_mode)]) == easy_mode, (
        "class-select SELECT did not expose Easy as an explicit mode"
    )

    # A browser emulator may retain VRAM across cartridge reloads, and real
    # CGB power-on contents are not a title-screen contract. Poison the CGB
    # attribute map, return through the real screen transition, and require
    # title_enter to restore palette 0 / tile bank 0 / no flips explicitly.
    pb.memory[0xFF4F] = 1
    for row in range(18):
        for col in range(20):
            pb.memory[0x9800 + row * 32 + col] = 0x6F
    pb.memory[0xFF4F] = 0
    pb.button("b")
    pb.tick(20)
    pb.memory[0xFF4F] = 1
    stale_attrs = [pb.memory[0x9800 + row * 32 + col]
                   for row in range(18) for col in range(20)]
    pb.memory[0xFF4F] = 0
    assert not any(stale_attrs), (
        "title retained stale CGB attributes from the previous screen"
    )
    pb.stop(save=False)
    print(f"[title-version] PASS rendered {version}, README, and clean CGB attributes")


if __name__ == "__main__":
    main()
