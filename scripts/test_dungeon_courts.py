#!/usr/bin/env python3
"""Live-ROM contract for generated 224x200 dungeon turn courts."""
import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
ROOM_W, ROOM_H = 20, 17


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


RS, PL, EN, TM, EXT, BOTTOM, WORLD_W, WORLD_H, CAMERA_X, CAMERA_Y, LARGE = map(
    addr,
    (
        "_run_state", "_player", "_entities", "_room_tilemap",
        "_room_world_extension", "_room_world_bottom", "_room_world_width",
        "_room_world_height", "_room_camera_x", "_room_camera_y",
        "_procgen_current_room_is_large",
    ),
)


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = value >> 8


def clear_hostiles(pb):
    for slot in range(32):
        base = EN + slot * 28
        if pb.memory[base] == 2:
            pb.memory[base] = pb.memory[base + 1] = 0


def settle(pb, frames=100):
    for _ in range(frames):
        pb.memory[PL + 2] = pb.memory[PL + 1]
        pb.memory[PL + 15] = 120
        pb.tick()


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    try:
        settle(pb, 240)
        pb.button("start")
        settle(pb, 30)
        pb.button("a")
        settle(pb, 60)

        # Publish opening-dungeon local room 3, then cross its east threshold
        # into local room 4—the first dense scrolling approach expanse.
        pb.memory[RS + 1] = 3
        pb.memory[RS + 11] = 0
        pb.memory[RS + 13] = 0
        pb.memory[TM + 8 * ROOM_W + 19] = 3
        pb.memory[TM + 9 * ROOM_W + 19] = 3
        clear_hostiles(pb)
        put16(pb, PL + 9, 144)
        put16(pb, PL + 11, 60)
        settle(pb)

        assert pb.memory[RS + 1] == 4
        assert pb.memory[LARGE] == 1
        assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (224, 200)
        # The next graph edge is the true far east edge. Crossing it keeps
        # wide-world state and enters the paired lighter turn court.
        clear_hostiles(pb)
        put16(pb, PL + 9, 216)
        put16(pb, PL + 11, 60)
        settle(pb)

        assert pb.memory[RS + 1] == 5
        assert pb.memory[LARGE] == 1
        assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (224, 200)
        # Local 5 owns reciprocal west and south links. The old east/south
        # viewport edges are interior; only the true 28x25 perimeter closes.
        assert pb.memory[TM + 8 * ROOM_W] == 3
        assert pb.memory[TM + 9 * ROOM_W] == 3
        walkable = (1, 19, 20, 23, 31)
        assert pb.memory[TM + 8 * ROOM_W + 19] in walkable
        assert pb.memory[TM + 16 * ROOM_W + 10] in walkable
        assert pb.memory[EXT + 8 * 8 + 7] == 2
        assert pb.memory[EXT + 9 * 8 + 7] == 2
        assert pb.memory[BOTTOM + 7 * 28 + 9] == 3
        assert pb.memory[BOTTOM + 7 * 28 + 10] == 3
        assert not any(
            pb.memory[EXT + i] & 0x80 for i in range(ROOM_H * 8)
        )
        assert not any(
            pb.memory[BOTTOM + i] & 0x80 for i in range(8 * 28)
        )
        field = []
        for y in range(25):
            row = []
            for x in range(28):
                if y < 17 and x < 20:
                    row.append(pb.memory[TM + y * 20 + x] & 0x7F)
                elif y < 17:
                    row.append(pb.memory[EXT + y * 8 + x - 20] & 0x7F)
                else:
                    row.append(pb.memory[BOTTOM + (y - 17) * 28 + x] & 0x7F)
            field.append(row)
        passable = {1, 3, 19, 20, 23, 31}
        queue = [(1, 8)]
        seen = set(queue)
        while queue:
            x, y = queue.pop()
            for nx, ny in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
                if (
                    0 <= nx < 28
                    and 0 <= ny < 25
                    and (nx, ny) not in seen
                    and field[ny][nx] in passable
                ):
                    seen.add((nx, ny))
                    queue.append((nx, ny))
        assert {(0, 8), (0, 9), (9, 24), (10, 24)} <= seen
        assert sum(
            field[y][x] == 21
            for y in range(25)
            for x in range(28)
            if x >= 20 or y >= 17
        ) >= 24

        hostiles = [
            (
                pb.memory[EN + slot * 28 + 3]
                | pb.memory[EN + slot * 28 + 4] << 8,
                pb.memory[EN + slot * 28 + 7]
                | pb.memory[EN + slot * 28 + 8] << 8,
            )
            for slot in range(32)
            if pb.memory[EN + slot * 28] == 2
        ]
        assert any(x >= 160 and y >= 136 for x, y in hostiles), hostiles

        # Exercise both camera axes in the actual added combat terrain.
        clear_hostiles(pb)
        put16(pb, PL + 9, 192)
        put16(pb, PL + 11, 160)
        settle(pb, 40)
        assert (pb.memory[CAMERA_X], pb.memory[CAMERA_Y]) == (64, 64)
        assert (pb.memory[0xFF43], pb.memory[0xFF42]) == (64, 64)
        shot = ROOT / "tmp" / "dungeon-turn-court.png"
        shot.parent.mkdir(exist_ok=True)
        pb.screen.image.save(shot)

        # The true south door continues into local room 6 without collapsing
        # back to a one-screen field. A turn now reads as a scrolling district,
        # not one isolated large room.
        put16(pb, PL + 9, 72)
        put16(pb, PL + 11, 184)
        settle(pb)
        assert pb.memory[RS + 1] == 6
        assert pb.memory[LARGE] == 1
        assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (224, 200)

        # Re-enter local 5 from the scrolling south neighbour. The champion
        # belongs at the true lower edge and SCY=64 immediately, never hidden
        # below the LCD.
        clear_hostiles(pb)
        put16(pb, PL + 9, 72)
        put16(pb, PL + 11, 0)
        settle(pb)
        assert pb.memory[RS + 1] == 5
        assert pb.memory[LARGE] == 1
        assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (224, 200)
        player_y = pb.memory[PL + 11] | pb.memory[PL + 12] << 8
        assert player_y == 176, player_y
        assert pb.memory[CAMERA_Y] == 64 and pb.memory[0xFF42] == 64

        # Local 7 is the authored Waystone fixture and deliberately returns
        # to the compact presentation so its puzzle language remains legible.
        clear_hostiles(pb)
        put16(pb, PL + 9, 72)
        put16(pb, PL + 11, 184)
        settle(pb)
        assert pb.memory[RS + 1] == 6
        clear_hostiles(pb)
        put16(pb, PL + 9, 0)
        put16(pb, PL + 11, 60)
        settle(pb)
        assert pb.memory[RS + 1] == 7
        assert pb.memory[LARGE] == 0
        assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (160, 136)
        assert (pb.memory[CAMERA_X], pb.memory[CAMERA_Y]) == (0, 0)
    finally:
        pb.stop(save=False)

    print(
        "[dungeon-courts] PASS scrolling 224x200 districts + wide-to-wide "
        "turn + southeast camera + objective reset + reciprocal arrival"
    )


if __name__ == "__main__":
    main()
