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
WALK_A_BASE = 82
WALK_B_BASE = 160
HURT_BASE = 180
OAM_TILE_0 = 0xFE02


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


PLAYER = addr("_player")
SCREEN = addr("_loop_current_screen")
HURT_TICKS = addr("_room_hurt_pose_ticks")
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
        walk_a = tile_bytes(pb, WALK_A_BASE + class_id * CLASS_STRIDE)
        walk_b = tile_bytes(pb, WALK_B_BASE + class_id * CLASS_STRIDE)
        hurt = tile_bytes(pb, HURT_BASE + class_id * CLASS_STRIDE)
        assert len({idle, walk_a, walk_b, hurt}) == 4, \
            f"class {class_id} collapsed an authored motion pose"
        hero_art.append(idle)

        # The room entry frame is always the idle pose.
        assert pb.memory[OAM_TILE_0] == IDLE_BASE + class_id * CLASS_STRIDE, (
            f"class {class_id} idle OAM tile is {pb.memory[OAM_TILE_0]}"
        )

        # Use real controller movement—not a memory poke—to prove the live
        # renderer changes to the matching walk atlas.  One of four directions
        # must be open from the procgen spawn; sample every moving frame.
        walk_a_tile = WALK_A_BASE + class_id * CLASS_STRIDE
        walk_b_tile = WALK_B_BASE + class_id * CLASS_STRIDE
        moved = False
        walk_seen = set()
        for direction in ("right", "left", "down", "up"):
            x0 = pb.memory[PLAYER + X_OFFSET] | (pb.memory[PLAYER + X_OFFSET + 1] << 8)
            y0 = pb.memory[PLAYER + Y_OFFSET] | (pb.memory[PLAYER + Y_OFFSET + 1] << 8)
            pb.button_press(direction)
            for _ in range(28):
                pb.tick()
                if pb.memory[OAM_TILE_0] in (walk_a_tile, walk_b_tile):
                    walk_seen.add(pb.memory[OAM_TILE_0])
            pb.button_release(direction)
            # Passive ally shots can legitimately land during this exact
            # release window and briefly hold the last pose in hit-stop.
            # Require a prompt idle settle, not one particular two-frame beat.
            for _ in range(20):
                pb.tick()
                if pb.memory[OAM_TILE_0] == IDLE_BASE + class_id * CLASS_STRIDE:
                    break
            x1 = pb.memory[PLAYER + X_OFFSET] | (pb.memory[PLAYER + X_OFFSET + 1] << 8)
            y1 = pb.memory[PLAYER + Y_OFFSET] | (pb.memory[PLAYER + Y_OFFSET + 1] << 8)
            if (x0, y0) != (x1, y1):
                moved = True
                break
        assert moved, f"class {class_id} had no open spawn direction"
        assert walk_seen == {walk_a_tile, walk_b_tile}, (
            f"class {class_id} did not cycle both strides: {walk_seen}"
        )
        assert pb.memory[OAM_TILE_0] == IDLE_BASE + class_id * CLASS_STRIDE, \
            f"class {class_id} did not settle back to idle: " \
            f"tile={pb.memory[OAM_TILE_0]} expected={IDLE_BASE + class_id * CLASS_STRIDE}"

        # A real hostile projectile must select the class-specific recoil art,
        # not merely flash the idle sprite or change the HP number.
        for i in range(32 * 28):
            pb.memory[addr("_entities") + i] = 0
        e = addr("_entities")
        x = pb.memory[PLAYER + X_OFFSET] | pb.memory[PLAYER + X_OFFSET + 1] << 8
        y = pb.memory[PLAYER + Y_OFFSET] | pb.memory[PLAYER + Y_OFFSET + 1] << 8
        pb.memory[e] = 1
        pb.memory[e + 1] = 0x03
        pb.memory[e + 3], pb.memory[e + 4] = (x + 5) & 0xFF, (x + 5) >> 8
        pb.memory[e + 7], pb.memory[e + 8] = (y + 9) & 0xFF, (y + 9) >> 8
        pb.memory[e + 14] = 1
        pb.memory[e + 16] = 20
        pb.memory[e + 25] = 0x66
        pb.memory[e + 26] = 1
        pb.memory[PLAYER + 15] = 0
        hp_before = pb.memory[PLAYER + 2]
        hurt_seen = False
        for _ in range(24):
            pb.tick()
            hurt_seen |= pb.memory[OAM_TILE_0] == HURT_BASE + class_id * CLASS_STRIDE
        assert pb.memory[PLAYER + 2] < hp_before, f"class {class_id} took no damage"
        assert pb.memory[HURT_TICKS] > 0 or hurt_seen, \
            f"class {class_id} never entered recoil timing"
        assert hurt_seen, f"class {class_id} recoil art never reached OAM"
        pb.stop(save=False)

    assert len(set(hero_art)) == 5, "champion idle art is not distinct"
    print("[champion-animation] PASS five idle + two-stride + recoil champions")


if __name__ == "__main__":
    main()
