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

    # The selector uses gold labels, a compact stat row, and blank separators
    # at rows 13 and 15. Pin Wolfkin's complete initial page, including the
    # two-space ROLE alignment and the 20-column stat line.
    class_rows = {
        9: "ROLE  BLADE FIGHTER",
        10: "A STAB SLASH DASH",
        11: "B 8 SHOTS BRIEF WARD",
        12: "TRAIT FAST MOVEMENT",
        14: "HP14 MP4 AT2 DF1 SP6",
        16: "NORMAL  SEL FOR EASY",
        17: " A CHOOSE   B BACK",
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
    for row in (13, 15):
        assert all(pb.memory[0x9800 + row * 32 + col] == 0 for col in range(20)), (
            f"class-select row {row} should be a blank separator"
        )

    # Class select must own its attribute map: title gold, selected name
    # accent, ROLE label gold, role value accent, A/B/TRAIT labels gold.
    pb.memory[0xFF4F] = 1
    def attrs(row, start, width):
        return list(pb.memory[0x9800 + row * 32 + start:
                              0x9800 + row * 32 + start + width])
    title_attrs = attrs(1, 2, 16)
    assert title_attrs == [1] * 16, f"title not gold: {title_attrs}"
    name_attrs = attrs(3, 4, 7)
    assert name_attrs == [2] * 7, f"Wolfkin name not accent: {name_attrs}"
    assert attrs(9, 0, 4) == [1] * 4, "ROLE label not gold"
    assert attrs(9, 6, 13) == [2] * 13, "role value not accent"
    assert attrs(10, 0, 1) == [1] and attrs(11, 0, 1) == [1]
    assert attrs(12, 0, 5) == [1] * 5, "TRAIT label not gold"
    # HP/MP/AT/DF/SP letters gold, digits and spaces body white.
    stat = attrs(14, 0, 20)
    expected_stat = []
    for ch in "HP14 MP4 AT2 DF1 SP6":
        expected_stat.append(1 if "A" <= ch <= "Z" else 0)
    assert stat == expected_stat, f"stat attributes drifted: {stat}"
    assert attrs(16, 8, 12) == [3] * 12, "SEL FOR EASY not lavender"
    assert attrs(17, 1, 1) == [1] and attrs(17, 3, 6) == [3] * 6
    assert attrs(17, 12, 1) == [1] and attrs(17, 14, 4) == [3] * 4
    pb.memory[0xFF4F] = 0

    # Every hero page must fit the 20-column LCD, including the two
    # former overflows (Picsean trait, Vespine trait) and Corvin's B line
    # which can no longer rely on a missing '+' glyph.
    hero_pages = [
        {
            9: "ROLE  BLADE FIGHTER",
            10: "A STAB SLASH DASH",
            11: "B 8 SHOTS BRIEF WARD",
            12: "TRAIT FAST MOVEMENT",
            14: "HP14 MP4 AT2 DF1 SP6",
        },
        {
            9: "ROLE  ARMORED TANK",
            10: "A HEAVY TAIL STRIKE",
            11: "B BLOCKS ALL HITS",
            12: "TRAIT HEALTH REGEN",
            14: "HP16 MP3 AT2 DF2 SP5",
        },
        {
            9: "ROLE  RANGED HUNTER",
            10: "A RETURNING FEATHER",
            11: "B MARK RAVEN DIVES",
            12: "TRAIT SHOW ENEMY HP",
            14: "HP14 MP8 AT2 DF1 SP5",
        },
        {
            9: "ROLE  MAGIC CASTER",
            10: "A PIERCING BUBBLE",
            11: "B 3 BUBBLES AND WARD",
            12: "TRAIT FAST MP REGEN",
            14: "HP14MP10 AT1 DF1 SP5",
        },
        {
            9: "ROLE  FAST STRIKER",
            10: "A FAST STINGER",
            11: "B ROTATING STINGERS",
            12: "TRAIT ELEMENT POWER",
            14: "HP13 MP5 AT4 DF1 SP7",
        },
    ]
    for hero, page in enumerate(hero_pages):
        if hero:
            pb.button("down")
            pb.tick(8)
        for row, label in page.items():
            expected_row = font_tiles(label)
            rendered_row = list(pb.memory[
                0x9800 + row * 32:0x9800 + row * 32 + len(expected_row)
            ])
            assert rendered_row == expected_row, (
                f"hero {hero} row {row} clipped or drifted: {rendered_row}"
            )
            assert all(pb.memory[0x9800 + row * 32 + col] == 0
                       for col in range(len(expected_row), 20)), (
                f"hero {hero} row {row} left stale edge glyphs"
            )
    # Return to Wolfkin so the Easy-toggle asserts stay on a known page.
    pb.button("down")
    pb.tick(8)

    pb.button("select")
    pb.tick(8)
    easy_hint = font_tiles("EASY MORE HP FEW HEX")
    assert list(pb.memory[0x9800 + 16 * 32:
                          0x9800 + 16 * 32 + len(easy_hint)]) == easy_hint, (
        "class-select SELECT did not switch the current-mode label to EASY"
    )
    assert all(pb.memory[0x9800 + 13 * 32 + col] == 0 for col in range(20)), (
        "class-select Easy page overwrote the blank separator at row 13"
    )

    # A browser emulator may retain VRAM across cartridge reloads, and real
    # CGB power-on contents are not a title-screen contract. Poison the CGB
    # attribute map, return through the real screen transition, and require
    # title_enter to restore palette 0 / tile bank 0 / no flips explicitly.
    pb.memory[0xFF4F] = 1
    for row in range(18):
        for col in range(20):
            pb.memory[0x9800 + row * 32 + col] = 0x6F
    # Leave VBK on the attribute plane across the real B transition. Pocket
    # hardware can arrive here in that state after a warm Game Over restart;
    # title_enter must select tile-data bank 0 before loading or drawing.
    pb.button("b")
    pb.tick(20)
    pb.memory[0xFF4F] = 1
    stale_attrs = [pb.memory[0x9800 + row * 32 + col]
                   for row in range(18) for col in range(20)]
    pb.memory[0xFF4F] = 0
    assert not any(stale_attrs), (
        "title retained stale CGB attributes from the previous screen"
    )
    warm_title = font_tiles("QUINTRA")
    assert list(pb.memory[0x9800 + 4 * 32 + 6:
                          0x9800 + 4 * 32 + 6 + len(warm_title)]) == warm_title, (
        "title drew into CGB attribute memory after a warm restart"
    )
    pb.stop(save=False)
    print(
        f"[title-version] PASS rendered {version}, README, clean CGB attributes, "
        "and warm-VBK recovery"
    )


if __name__ == "__main__":
    main()
