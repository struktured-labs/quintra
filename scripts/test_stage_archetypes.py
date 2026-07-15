#!/usr/bin/env python3
"""ROM regression: stage identity changes generated traversal geometry."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
ROOM_W, ROOM_H = 20, 18
BGT_CRYSTAL, BGT_SPIKES = 22, 31


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


RS, PL, EN, TM = map(addr, ("_run_state", "_player", "_entities", "_room_tilemap"))


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def generated_room(stage, seed=0xCAFE1234):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(60):
        pb.tick()

    target = stage * 6 + 1
    # Enter through the authored Riftwild dungeon gate. This follows the
    # cartridge's real between-dungeon transition without fighting prior
    # bosses merely to inspect deterministic stage geometry.
    pb.memory[RS + 1] = target - 1
    for i, byte in enumerate(seed.to_bytes(4, "little")):
        pb.memory[RS + 2 + i] = byte
    pb.memory[RS + 11] = stage
    pb.memory[RS + 12] = 0
    pb.memory[RS + 13] = 0
    pb.memory[RS + 17] = 1
    pb.memory[RS + 18] = 6  # authored ZELDA_CELL_DUNGEON_ENTRANCE
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 2:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 60)
    pb.memory[TM + 9 * ROOM_W + 10] = 34  # BGT_PORTAL under feet center
    for _ in range(20):
        pb.tick()
        if pb.memory[RS + 1] == target:
            break
    assert pb.memory[RS + 1] == target, f"could not enter stage {stage} room"
    for _ in range(20):
        pb.tick()
    tiles = [pb.memory[TM + i] for i in range(ROOM_W * ROOM_H)]
    pb.stop(save=False)
    return tiles


def tile(tiles, x, y):
    return tiles[y * ROOM_W + x]


def reachable_exits(tiles, start):
    walkable = {1, 3, 7, 19, 20, 23, 31, 33, 34, *range(9, 19)}

    def body_ok(x, y):
        return (1 <= x <= 19 and 1 <= y <= 16
                and all(tile(tiles, tx, ty) in walkable
                        for tx, ty in ((x - 1, y - 1), (x, y - 1),
                                       (x - 1, y), (x, y))))

    seen, todo = {start}, [start]
    while todo:
        x, y = todo.pop()
        for nx, ny in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
            if (nx, ny) not in seen and body_ok(nx, ny):
                seen.add((nx, ny))
                todo.append((nx, ny))
    exits = {(10, 1), (19, 9), (10, 16), (1, 9)}
    return exits & seen


def main():
    grove = generated_room(1, 2064128938)  # controller-agent seed 1
    grove_sites = [(4, 4), (5, 4), (14, 4), (15, 4),
                   (4, 12), (5, 12), (14, 12), (15, 12)]
    grove_crystals = sum(tile(grove, x, y) == BGT_CRYSTAL for x, y in grove_sites)
    assert grove_crystals >= 4, f"Verdant grove silhouette missing ({grove_crystals}/8)"
    grove_exits = reachable_exits(grove, (18, 9))
    assert len(grove_exits) == 4, f"Verdant grove disconnected exits: {grove_exits}"

    ember = generated_room(2)
    seam_spikes = sum(
        tile(ember, x, y) == BGT_SPIKES
        for x in (5, 14) for y in range(3, 15)
    )
    assert seam_spikes >= 10, f"Ember hazard seams missing ({seam_spikes}/24)"
    # The two three-tile breathing gaps must survive, keeping the hazard a
    # routing choice rather than unavoidable chip damage.
    assert any(tile(ember, 5, y) != BGT_SPIKES for y in range(4, 14))
    assert any(tile(ember, 14, y) != BGT_SPIKES for y in range(4, 14))
    ember_exits = reachable_exits(ember, (18, 9))
    assert len(ember_exits) == 4, f"Ember gauntlet disconnected exits: {ember_exits}"
    print(f"[stage-types] PASS Verdant grove={grove_crystals}/8, "
          f"Ember seams={seam_spikes}/24, all exits reachable")


if __name__ == "__main__":
    main()
