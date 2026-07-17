#!/usr/bin/env python3
"""ROM contract: each champion owns distinct idle/walk art and pose slots."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()

CLASS_STRIDE = 4
IDLE_BASE = 0
WALK_BASE = 82
OAM_TILE_0 = 0xFE02


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


PLAYER = addr("_player")
SCREEN = addr("_loop_current_screen")
ANIM_FRAME_OFFSET = 14
X_OFFSET = 9
Y_OFFSET = 11


def press(pb, button, held=4, released=4):
    pb.button_press(button)
    for _ in range(held):
        pb.tick()
    pb.button_release(button)
    for _ in range(released):
        pb.tick()


def boot(class_moves):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    press(pb, "start")
    for _ in range(30):
        pb.tick()
    for _ in range(class_moves):
        press(pb, "down", held=3, released=3)
    press(pb, "a")
    for _ in range(80):
        pb.tick()
    assert pb.memory[SCREEN] == 5, "class select did not enter a room"
    return pb


def tile_bytes(pb, tile):
    start = 0x8000 + tile * 16
    return bytes(pb.memory[start:start + 64])


def main():
    hero_art = []
    for class_id in range(5):
        pb = boot(class_id)
        assert pb.memory[PLAYER] == class_id, (
            f"selected class {class_id}, runtime has {pb.memory[PLAYER]}"
        )

        # The authored 16x16 idle and walk metasprites occupy their own four
        # tiles.  A visual identity regression must not collapse two heroes.
        idle = tile_bytes(pb, IDLE_BASE + class_id * CLASS_STRIDE)
        walk = tile_bytes(pb, WALK_BASE + class_id * CLASS_STRIDE)
        assert idle != walk, f"class {class_id} walk pose equals idle art"
        hero_art.append(idle)

        # The room entry frame is always the idle pose.
        assert pb.memory[OAM_TILE_0] == IDLE_BASE + class_id * CLASS_STRIDE, (
            f"class {class_id} idle OAM tile is {pb.memory[OAM_TILE_0]}"
        )

        # Use real controller movement—not a memory poke—to prove the live
        # renderer changes to the matching walk atlas.  One of four directions
        # must be open from the procgen spawn; sample every moving frame.
        walk_tile = WALK_BASE + class_id * CLASS_STRIDE
        moved = False
        walk_seen = False
        for direction in ("right", "left", "down", "up"):
            x0 = pb.memory[PLAYER + X_OFFSET] | (pb.memory[PLAYER + X_OFFSET + 1] << 8)
            y0 = pb.memory[PLAYER + Y_OFFSET] | (pb.memory[PLAYER + Y_OFFSET + 1] << 8)
            pb.button_press(direction)
            for _ in range(20):
                pb.tick()
                walk_seen |= pb.memory[OAM_TILE_0] == walk_tile
            pb.button_release(direction)
            for _ in range(2):
                pb.tick()
            x1 = pb.memory[PLAYER + X_OFFSET] | (pb.memory[PLAYER + X_OFFSET + 1] << 8)
            y1 = pb.memory[PLAYER + Y_OFFSET] | (pb.memory[PLAYER + Y_OFFSET + 1] << 8)
            if (x0, y0) != (x1, y1):
                moved = True
                break
        assert moved, f"class {class_id} had no open spawn direction"
        assert walk_seen, f"class {class_id} movement never selected walk tile {walk_tile}"
        pb.stop(save=False)

    assert len(set(hero_art)) == 5, "champion idle art is not distinct"
    print("[champion-animation] PASS five distinct idle/walk champions")


if __name__ == "__main__":
    main()
