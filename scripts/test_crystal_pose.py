#!/usr/bin/env python3
"""Crystal Colossus alternates a bank-1 refraction pose on the same 16 sprites."""
from pathlib import Path

from PIL import Image

from test_boss_identity import (
    CAMERA_X, CAMERA_Y, EN, LARGE, PL, ROOM_W, RS, TM, WORLD_H, WORLD_W,
    enter_boss, put16,
)
from quintra_topology import STAGE_BOSS_ROOM, STAGE_START, dungeon_direction

ART = Path("/opt/cursor/artifacts")


def crystal_sprites(pb):
    found = []
    for i in range(4, 40):
        base = 0xFE00 + i * 4
        y, x, tile, prop = (pb.memory[base + k] for k in range(4))
        if not (y and x):
            continue
        bank = prop & 0x08
        if bank == 0 and 40 <= tile <= 55:
            found.append((tile, 0))
        elif bank and 128 <= tile <= 143:
            found.append((tile, 8))
    return found


def bank1_tiles(pb, tile, count):
    pb.memory[0xFF40] &= 0x7F
    pb.memory[0xFF4F] = 1
    data = bytes(pb.memory[0x8000 + tile * 16:0x8000 + (tile + count) * 16])
    pb.memory[0xFF4F] = 0
    pb.memory[0xFF40] |= 0x80
    return data


def enter_loaded(pb, stage):
    """Cross into another stage's boss room on an already-running ROM."""
    target = STAGE_BOSS_ROOM[stage]
    pb.memory[RS + 1] = target - 1
    pb.memory[RS + 11] = stage
    pb.memory[RS + 6] = 0xFF
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
    put16(pb, RS + 23, 1 << stage)
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 2:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    source_local = target - 1 - STAGE_START[stage]
    target_local = target - STAGE_START[stage]
    direction = dungeon_direction(source_local, target_local)
    for tx, ty in {
        0: ((9, 0), (10, 0)), 1: ((19, 8), (19, 9)),
        2: ((9, 16), (10, 16)), 3: ((0, 8), (0, 9)),
    }[direction]:
        pb.memory[TM + ty * ROOM_W + tx] = 3
    x, y = {0: (72, 0), 1: (144, 60), 2: (72, 120), 3: (0, 60)}[direction]
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, y)
    for _ in range(80):
        pb.tick()
        if pb.memory[RS + 1] == target:
            break
    assert pb.memory[RS + 1] == target, f"could not enter boss stage {stage}"
    for _ in range(60):
        pb.tick()


def main():
    pb, _boss = enter_boss(0, keep_open=True)
    bits = set()
    counts = set()
    saved = set()
    for _ in range(96):
        pb.tick(1, render=True, sound=False)
        sprites = crystal_sprites(pb)
        if len(sprites) != 16:
            if sprites:
                counts.add(len(sprites))
            continue
        counts.add(16)
        bit = sprites[0][1]
        bits.add(bit)
        if bit not in saved and ART.is_dir():
            image = pb.screen.image
            if image.convert("L").getextrema()[0] > 40:
                continue
            image.resize(
                (image.width * 4, image.height * 4),
                Image.Resampling.NEAREST).save(
                ART / ("after-crystal-refract.png" if bit else "after-crystal-idle.png"))
            saved.add(bit)
    assert 16 in counts, f"crystal body is not 16 sprites: {sorted(counts)}"
    assert bits == {0, 8}, f"both poses must appear, saw {sorted(bits)}"

    pb.memory[0xFF40] &= 0x7F
    pb.memory[0xFF4F] = 0
    idle = bytes(pb.memory[0x8000 + 40 * 16:0x8000 + 56 * 16])
    pb.memory[0xFF4F] = 1
    bent = bytes(pb.memory[0x8000 + 128 * 16:0x8000 + 144 * 16])
    forbidden = bytes(pb.memory[0x8000 + 40 * 16:0x8000 + 56 * 16])
    differ = sum(a != b for a, b in zip(idle, bent))
    assert differ > 32, f"bank-1 refraction matches the idle upload ({differ} bytes)"
    assert forbidden != bent, "refraction was uploaded over bank-1 tiles 40..55"
    assert any(bent[128:]), "crystal pose left tiles 136..143 empty"

    # The Rex pose also starts at bank-1 tile 128. Entering its room must
    # wipe Crystal's tail and replace the shared head of the window.
    enter_loaded(pb, 2)
    rex = bank1_tiles(pb, 128, 8)
    tail = bank1_tiles(pb, 136, 8)
    pb.stop(save=False)
    assert tail == bytes(128), "crystal tiles lingered in the Rex room"
    assert rex != bent[:128], "Rex room kept the Crystal pose"
    print(f"crystal poses ok, vram bytes differ {differ}; rex room cleared the window")


if __name__ == "__main__":
    main()
