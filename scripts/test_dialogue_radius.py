#!/usr/bin/env python3
"""Dialogue requires a close, not-facing-away stance."""
from test_dialogue import (
    EN, PL, SCREEN, SCREEN_DIALOG, SCREEN_ROOM,
    boot_waypoint, put16, tick,
)


FACE_E, FACE_W = 1, 3
ENT_PROJECTILE = 1


def speaker_xy(pb, speaker):
    return (pb.memory[speaker + 3] | (pb.memory[speaker + 4] << 8),
            pb.memory[speaker + 7] | (pb.memory[speaker + 8] << 8))


def place(pb, x, y, facing):
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, y)
    pb.memory[PL + 13] = facing
    pb.memory[PL + 22] = 0
    tick(pb, 2)


def press_a(pb):
    pb.button_press("a")
    saw_shot = False
    for _ in range(12):
        pb.tick()
        if projectile_live(pb):
            saw_shot = True
    pb.button_release("a")
    tick(pb, 4)
    return saw_shot


def projectile_live(pb):
    return any(pb.memory[EN + i * 28] == ENT_PROJECTILE
               and (pb.memory[EN + i * 28 + 1] & 0x11)
               for i in range(32))


def main():
    pb, speaker = boot_waypoint(0)
    try:
        x, y = speaker_xy(pb, speaker)
        place(pb, x - 26, y, FACE_E)
        assert press_a(pb), "far A did not attack"
        assert pb.memory[SCREEN] == SCREEN_ROOM, "far A opened dialogue"

        place(pb, x - 16, y, FACE_W)
        assert press_a(pb), "facing away did not attack"
        assert pb.memory[SCREEN] == SCREEN_ROOM, "facing away opened dialogue"

        place(pb, x - 16, y, FACE_E)
        press_a(pb)
        assert pb.memory[SCREEN] == SCREEN_DIALOG, "facing the speaker did not talk"
    finally:
        pb.stop(save=False)
    print("[dialogue-radius] PASS far and turned-away A attacks; close A talks")


if __name__ == "__main__":
    main()
