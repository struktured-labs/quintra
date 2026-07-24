#!/usr/bin/env python3
"""Live-ROM contract: class select teaches menus and PACK names the next goal."""
import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom" / "working" / "quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
SCREEN_INVENTORY = 9


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


def font_tiles(text):
    # font_min uses blank=0, A..Z=11..36. These guidance strings deliberately
    # avoid punctuation so the test mirrors the cartridge's tiny font exactly.
    return bytes(0 if char == " " else ord(char) - ord("A") + 11
                 for char in text)


def row(pb, y, x, text):
    got = bytes(pb.memory[0x9800 + y * 32 + x:
                          0x9800 + y * 32 + x + len(text)])
    assert got == font_tiles(text), f"row {y} expected {text!r}, got {list(got)}"


def settle(pb, frames):
    for _ in range(frames):
        pb.tick()


def open_pack(pb):
    pb.button("start")
    settle(pb, 20)
    assert pb.memory[addr("_loop_current_screen")] == SCREEN_INVENTORY


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    try:
        settle(pb, 240)
        pb.button("start")
        settle(pb, 20)

        # Navigation help is visible before committing to a champion.
        row(pb, 9, 2, "SELECT OPENS MAP")
        row(pb, 10, 2, "START OPENS PACK")
        (ROOT / "tmp").mkdir(exist_ok=True)
        pb.screen.image.save(ROOT / "tmp" / "quest-controls.png")

        pb.button("a")
        settle(pb, 60)
        open_pack(pb)
        row(pb, 9, 0, "GOAL FIND SIGIL KEY")
        pb.screen.image.save(ROOT / "tmp" / "quest-sigil-key.png")

        # Return to the live room, then advance the exact persisted fixture
        # flags. Each Pack visit must name the next real sanctuary prerequisite.
        pb.button("b")
        settle(pb, 20)
        rs = addr("_run_state")

        pb.memory[rs + 23] |= 1  # stage-zero rift_sigils low byte
        open_pack(pb)
        row(pb, 9, 0, "GOAL CLEAR WARDEN")
        pb.button("b")
        settle(pb, 20)

        pb.memory[rs + 27] |= 1 << 3  # dungeon_puzzles Warden Boon
        open_pack(pb)
        row(pb, 9, 0, "GOAL WAKE WAYSTONE")
        pb.button("b")
        settle(pb, 20)

        pb.memory[rs + 27] |= 1 << 7  # Waystone
        open_pack(pb)
        row(pb, 9, 0, "GOAL CLEAR DEEP WARD")
        pb.button("b")
        settle(pb, 20)

        pb.memory[rs + 28] |= 1 << 7  # deep Warden
        open_pack(pb)
        row(pb, 9, 0, "GOAL SEEK SKULL GATE")
        pb.button("b")
        settle(pb, 20)

        # The same single line remains useful between dungeons and at the
        # actual commitment fight rather than leaking dungeon-only advice.
        pb.memory[rs + 17] = 1  # world_mode
        open_pack(pb)
        row(pb, 9, 0, "GOAL FIND DUNGEON")
        pb.button("b")
        settle(pb, 20)

        pb.memory[rs + 17] = 0
        pb.memory[rs + 1] = 63  # first village
        open_pack(pb)
        row(pb, 9, 0, "GOAL REST THEN NORTH")
        pb.button("b")
        settle(pb, 20)

        pb.memory[rs + 1] = 19  # opening Colossus arena
        open_pack(pb)
        row(pb, 9, 0, "GOAL BREAK COLOSSUS")
    finally:
        pb.stop(save=False)

    print(
        "[quest-guidance] PASS menu controls + Sigil key + ordered "
        "trials + skull gate + world/village/Colossus goals"
    )


if __name__ == "__main__":
    main()
