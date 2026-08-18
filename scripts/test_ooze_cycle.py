#!/usr/bin/env python3
"""Live-ROM regression for Rift Ooze split, scatter, and recombination."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def read_fix8(pb, address):
    raw = sum(pb.memory[address + i] << (i * 8) for i in range(4))
    return raw >> 8


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(240):
        pb.tick()

    entities = addr("_entities")
    tilemap = addr("_room_tilemap")
    player = addr("_player")
    hitstop = addr("_g_hitstop")
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    # Keep the player clear and invulnerable: this is a movement-cycle test,
    # not an endurance test against the two intentionally live shards.
    pb.memory[player + 2] = 20
    pb.memory[player + 15] = 255
    put16(pb, player + 9, 24)
    put16(pb, player + 11, 24)
    # PyBoy can return from a nested transition VBlank while the cartridge
    # still holds a pointer to an entity from the old room. Let that frame
    # retire before constructing the capacity fixture, then publish the clean
    # table once more at the ordinary game-loop boundary.
    for _ in range(4):
        pb.tick()
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    pb.memory[player + 2] = 20
    pb.memory[player + 15] = 255
    put16(pb, player + 9, 24)
    put16(pb, player + 11, 24)

    ooze = entities
    shot = entities + 28
    # Saturate the remaining slots. The death handler must recycle the killed
    # projectile slot, proving the split remains safe at the entity cap.
    for i in range(2, 32):
        filler = entities + i * 28
        pb.memory[filler] = 4
        pb.memory[filler + 1] = 3
        pb.memory[filler + 16] = 100
    pb.memory[ooze] = 2
    pb.memory[ooze + 1] = 7
    put_fix8(pb, ooze + 2, 80)
    put_fix8(pb, ooze + 6, 72)
    pb.memory[ooze + 14] = 1
    pb.memory[ooze + 16] = 30
    pb.memory[ooze + 17] = 15
    pb.memory[ooze + 25] = 0x66
    pb.memory[ooze + 27] = 1
    pb.memory[shot] = 1
    pb.memory[shot + 1] = 0x13
    put_fix8(pb, shot + 2, 80)
    put_fix8(pb, shot + 6, 72)
    pb.memory[shot + 14] = 1
    pb.memory[shot + 16] = 10
    pb.memory[shot + 25] = 0x77
    pb.memory[shot + 27] = 1
    pb.memory[hitstop] = 0
    for _ in range(4):
        pb.tick()
    fragments = [entities + i * 28 for i in range(32)
                 if pb.memory[entities + i * 28] == 2
                 and pb.memory[entities + i * 28 + 1] & 1]
    assert len(fragments) == 2 and all(
        pb.memory[e + 17] == 0 and pb.memory[e + 14] == 2 for e in fragments
    ), (
        f"Rift Ooze did not split into two crawler shards: {fragments}; "
        f"ooze={list(pb.memory[ooze:ooze + 28])}; "
        f"shot={list(pb.memory[shot:shot + 28])}; "
        f"active={[(i, pb.memory[entities + i * 28], pb.memory[entities + i * 28 + 1], pb.memory[entities + i * 28 + 14], pb.memory[entities + i * 28 + 17], pb.memory[entities + i * 28 + 19]) for i in range(32) if pb.memory[entities + i * 28 + 1] & 1]}"
    )
    # Direct WRAM construction bypasses entity_spawn's population counter and
    # its first-sector refresh. The two fragments are visibly in the current
    # camera, so publish that normal runtime fact before testing recombination.
    for fragment in fragments:
        pb.memory[fragment + 1] |= 4

    for i in range(2, 32):
        filler = entities + i * 28
        pb.memory[filler] = pb.memory[filler + 1] = 0
    pb.memory[hitstop] = 0
    for _ in range(180):
        pb.tick()
    reformed = [entities + i * 28 for i in range(32)
                if pb.memory[entities + i * 28] == 2
                and pb.memory[entities + i * 28 + 1] & 1
                and pb.memory[entities + i * 28 + 17] == 15]
    assert len(reformed) == 1 and pb.memory[reformed[0] + 14] == 8, (
        f"Rift Ooze shards did not reform into one weakened body: {reformed}")

    # A lone shard becomes an active hunter. At the north boundary, its old
    # direction-only walk could roam behind generated cover indefinitely while
    # holding a room seal. Put the player southwest and require the shard to
    # leave that wall and close real distance without any controller input.
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for x in range(20):
        pb.memory[tilemap + x] = 2
    shard = entities
    pb.memory[shard] = 2
    pb.memory[shard + 1] = 7
    put_fix8(pb, shard + 2, 80)
    put_fix8(pb, shard + 6, 8)
    pb.memory[shard + 14] = 2
    pb.memory[shard + 16] = 0
    pb.memory[shard + 17] = 0
    pb.memory[shard + 19] = 0x4F
    pb.memory[shard + 25] = 0
    start_x = read_fix8(pb, shard + 2)
    start_y = read_fix8(pb, shard + 6)
    player_x = pb.memory[player + 9] | pb.memory[player + 10] << 8
    player_y = pb.memory[player + 11] | pb.memory[player + 12] << 8
    start_dist = abs(player_x - start_x) + abs(player_y - start_y)
    for _ in range(140):
        pb.tick()
    end_x = read_fix8(pb, shard + 2)
    end_y = read_fix8(pb, shard + 6)
    end_dist = abs(player_x - end_x) + abs(player_y - end_y)
    assert end_y > start_y and end_dist < start_dist, (
        "lone north-wall Ooze shard did not hunt the player: "
        f"player=({player_x},{player_y}) start=({start_x},{start_y}) "
        f"end=({end_x},{end_y}) flags={pb.memory[shard + 1]} "
        f"timer={pb.memory[shard + 16]}")
    print("[ooze-cycle] PASS split -> scatter -> recombine; lone shard hunts")


if __name__ == "__main__":
    main()
