#!/usr/bin/env python3
"""Live-ROM contract: Riftwild Pack goal and Compass point at the Warden, then the gate.

Region 1 (first Riftwild): return field 0, Warden field 3, gate field 8.
- Pack reads FIND THE WARDEN until a wayfarer names it or the field is seen,
  then WARDEN LIES <dir>; in the field, SLAY THE WARDEN.
- The Compass marks the Warden field with the red BOSS node once known,
  even through fog. Once the Warden falls the gate is marked instead and the
  Pack reads GATE OPEN <dir> / ENTER THE GATE.
- The gate wayfarer really names the Warden: talking to it sets the bit.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_overworld import EN, PL, RS, SCREEN, addr, put16  # noqa: E402
from test_riftwild_landmarks import ROUTE, boot_world, cross_to  # noqa: E402
from test_quest_guidance import open_pack, row, settle  # noqa: E402

SCREEN_ROOM, SCREEN_MAP, SCREEN_DIALOG = 5, 8, 10
FLAGS, WORLD_SCREEN, WORLD_SEEN_XXHI = 47, 18, 50
GUARD_1 = 0x04
NAMED = 0x80
BGT_PORTAL, BGT_MAP_BOSS, BGT_MAP_HERE, BGT_MAP_UNKNOWN = 34, 51, 50, 95


def node(pb, cell):
    r, c = divmod(cell, 6)
    return pb.memory[0x9800 + (2 + 2 * r) * 32 + (1 + 2 * c)]


def keep(pb, n):
    for _ in range(n):
        pb.memory[PL + 2] = pb.memory[PL + 1]
        pb.memory[PL + 15] = 90
        pb.tick()


OUT = Path("builds/riftwild-mission")


def compass(pb, shot=None):
    pb.button_press("select")
    for _ in range(180):
        pb.tick()
        if pb.memory[SCREEN] == SCREEN_MAP:
            break
    pb.button_release("select")
    assert pb.memory[SCREEN] == SCREEN_MAP, "SELECT did not open the Compass"
    settle(pb, 90)
    nodes = {c: node(pb, c) for c in range(36)}
    if shot:
        OUT.mkdir(parents=True, exist_ok=True)
        pb.screen.image.save(str(OUT / shot))
    pb.button_press("b")
    for _ in range(180):
        pb.tick()
        if pb.memory[SCREEN] == SCREEN_ROOM:
            break
    pb.button_release("b")
    keep(pb, 90)
    return nodes


def pack(pb, text, shot=None):
    open_pack(pb)
    row(pb, 14, 4, text)
    if shot:
        OUT.mkdir(parents=True, exist_ok=True)
        pb.screen.image.save(str(OUT / shot))
    pb.button("b")
    keep(pb, 40)


def main():
    pb = boot_world()
    try:
        assert pb.memory[RS + WORLD_SCREEN] == 0
        keep(pb, 30)
        pb.memory[RS + WORLD_SEEN_XXHI] &= 0x7F
        pack(pb, "FIND THE WARDEN", "pack-unknown.png")
        nodes = compass(pb, "compass-unknown.png")
        assert nodes[3] == BGT_MAP_UNKNOWN, f"Warden leaked before named: {nodes[3]}"
        assert nodes[0] == BGT_MAP_HERE

        pb.memory[RS + WORLD_SEEN_XXHI] |= NAMED
        pack(pb, "WARDEN LIES E", "pack-warden.png")
        nodes = compass(pb, "compass-warden.png")
        assert nodes[3] == BGT_MAP_BOSS, f"named Warden not marked: {nodes[3]}"

        # Directions are true compass bearings from the current field.
        for here, text in ((35, "WARDEN LIES N"), (13, "WARDEN LIES NE"),
                           (5, "WARDEN LIES W"), (3, "SLAY THE WARDEN")):
            pb.memory[RS + WORLD_SCREEN] = here
            pack(pb, text)
        pb.memory[RS + WORLD_SCREEN] = 0

        pb.memory[RS + FLAGS] |= GUARD_1
        pack(pb, "GATE OPEN E", "pack-gate.png")
        nodes = compass(pb, "compass-gate.png")
        assert nodes[8] == BGT_PORTAL, f"woken gate not marked: {nodes[8]}"
        assert nodes[3] != BGT_MAP_BOSS, "fallen Warden still marked"
        for here, text in ((35, "GATE OPEN NW"), (8, "ENTER THE GATE")):
            pb.memory[RS + WORLD_SCREEN] = here
            pack(pb, text)
        pb.memory[RS + WORLD_SCREEN] = 0
        pb.memory[RS + FLAGS] &= 0xFF ^ GUARD_1
        print("[riftwild-mission] PASS Pack goal + Compass Warden/gate marks")

        # The sealed gate's wayfarer names the Warden for real.
        pb.memory[RS + WORLD_SEEN_XXHI] &= 0x7F
        for screen, x, y in ROUTE:
            cross_to(pb, screen, x, y)
            if screen == 8:
                break
        assert pb.memory[RS + WORLD_SCREEN] == 8
        assert not pb.memory[RS + WORLD_SEEN_XXHI] & NAMED
        wayfarer = [EN + i * 28 for i in range(32)
                    if pb.memory[EN + i * 28] == 3
                    and pb.memory[EN + i * 28 + 1] & 1]
        assert wayfarer, "no gate wayfarer"
        w = wayfarer[0]
        put16(pb, PL + 9, pb.memory[w + 3] | pb.memory[w + 4] << 8)
        put16(pb, PL + 11, (pb.memory[w + 7] | pb.memory[w + 8] << 8))
        for _attempt in range(6):
            keep(pb, 20)
            put16(pb, PL + 9, pb.memory[w + 3] | pb.memory[w + 4] << 8)
            put16(pb, PL + 11, pb.memory[w + 7] | pb.memory[w + 8] << 8)
            pb.button_press("a")
            keep(pb, 12)
            pb.button_release("a")
            keep(pb, 30)
            if pb.memory[SCREEN] == SCREEN_DIALOG:
                break
        assert pb.memory[SCREEN] == SCREEN_DIALOG, "gate wayfarer did not talk"
        assert pb.memory[addr("_dialog_topic")] == 13
        out = OUT
        out.mkdir(parents=True, exist_ok=True)
        pb.screen.image.save(str(out / "gate-wayfarer.png"))
        assert pb.memory[RS + WORLD_SEEN_XXHI] & NAMED, "wayfarer did not name the Warden"
        pb.button_press("a")
        keep(pb, 12)
        pb.button_release("a")
        keep(pb, 30)
        pb.screen.image.save(str(out / "gate-wayfarer-advice.png"))
        pb.button_press("b")
        keep(pb, 12)
        pb.button_release("b")
        keep(pb, 60)
        pack(pb, "WARDEN LIES NE")
        nodes = compass(pb)
        assert nodes[3] == BGT_MAP_BOSS
        print("[riftwild-mission] PASS gate wayfarer names the Warden (SEEK NORTHEAST)")
    finally:
        pb.stop(save=False)


if __name__ == "__main__":
    main()
