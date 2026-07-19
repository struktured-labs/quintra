#!/usr/bin/env python3
"""Live-ROM contract for the one-use Riftwild restoration landmark."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()

ENTITY_SIZE = 28
ENT_PICKUP = 3
PICKUP_RIFTWELL = 16
# run_state_t is packed by SDCC: the persisted landmark flag follows
# next_dungeon_reveal at byte 25 (room_tilemap begins at byte 26).
# In Riftwild the one-use bit occupies the existing cave-return anchor's high
# bit, keeping the run-state ABI/SRAM footprint unchanged.
WORLD_RETURN_OFFSET = 19
RIFTWELL_USED_FLAG = 0x80


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


RS, PL, EN = map(addr, ("_run_state", "_player", "_entities"))


def put16(pb, where, value):
    pb.memory[where] = value & 255
    pb.memory[where + 1] = (value >> 8) & 255


def tick(pb, frames=90):
    for _ in range(frames):
        pb.tick()


def riftwell(pb):
    for index in range(32):
        entity = EN + index * ENTITY_SIZE
        if (pb.memory[entity] == ENT_PICKUP and pb.memory[entity + 1] & 1
                and pb.memory[entity + 17] == PICKUP_RIFTWELL):
            return entity
    return None


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    tick(pb, 240)
    pb.button("start"); tick(pb, 30)
    pb.button("a"); tick(pb, 90)

    # Simulate the real post-boss handoff, then cross authored 0 -> 1.
    pb.memory[RS + 1] = 6
    pb.memory[RS + 11] = 1
    put16(pb, PL + 9, 72); put16(pb, PL + 11, 120)
    tick(pb)
    assert pb.memory[RS + 17] == 1 and pb.memory[RS + 18] == 0
    put16(pb, PL + 9, 144); put16(pb, PL + 11, 60)
    tick(pb)
    assert pb.memory[RS + 18] == 1, "did not reach the Riftwell screen"

    well = riftwell(pb)
    assert well is not None, "Riftwell was not spawned on the first Riftwild fork"
    # It restores both resource types, bounded by their normal caps.
    pb.memory[PL + 1] = 8; pb.memory[PL + 2] = 5
    pb.memory[PL + 3] = 6; pb.memory[PL + 4] = 5
    put16(pb, PL + 9, pb.memory[well + 3])
    # Player y is the sprite top while pickup collision uses feet at y+8.
    put16(pb, PL + 11, pb.memory[well + 7] - 8)
    tick(pb, 4)
    assert pb.memory[PL + 2] == 8 and pb.memory[PL + 4] == 6, (
        f"Riftwell recovery wrong hp/mp={pb.memory[PL + 2]}/{pb.memory[PL + 4]}"
    )
    assert pb.memory[RS + WORLD_RETURN_OFFSET] & RIFTWELL_USED_FLAG, \
        "Riftwell use was not persisted"
    assert riftwell(pb) is None, "spent Riftwell entity did not disappear"

    # Rebuild the room through real adjacent transitions; the well must stay
    # spent instead of returning from procedural regeneration.
    put16(pb, PL + 9, 0); put16(pb, PL + 11, 60); tick(pb)
    assert pb.memory[RS + 18] == 0
    put16(pb, PL + 9, 144); put16(pb, PL + 11, 60); tick(pb)
    assert pb.memory[RS + 18] == 1 and riftwell(pb) is None, \
        "spent Riftwell respawned after backtracking"
    pb.stop(save=False)
    print("[riftwell] PASS one-use HP/MP recovery persists across Riftwild backtracking")


if __name__ == "__main__":
    main()
