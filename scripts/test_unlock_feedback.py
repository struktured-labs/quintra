#!/usr/bin/env python3
"""Live-ROM contract: the final mandatory kill sounds the door latch."""
import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom" / "working" / "quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


PL, EN, SEALED, KIND, PHASE, COMPLETE, SCREEN = map(addr, (
    "_player", "_entities", "_room_combat_sealed",
    "_room_encounter_kind", "_room_encounter_phase",
    "_room_encounter_complete", "_loop_current_screen"))


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start"); pb.tick(30)
    pb.button("a"); pb.tick(120)
    assert pb.memory[SCREEN] == 5, "fixture did not enter gameplay"

    for i in range(32 * 28):
        pb.memory[EN + i] = 0
    pb.memory[KIND] = 0       # ordinary mandatory SKIRMISH
    pb.memory[PHASE] = 0
    pb.memory[COMPLETE] = 0
    pb.memory[SEALED] = 1
    pb.memory[PL + 15] = 120  # isolate the kill from body-contact damage

    px = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
    py = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
    enemy = EN + 30 * 28
    pb.memory[enemy] = 2
    pb.memory[enemy + 1] = 7
    put16(pb, enemy + 3, px + 16)
    put16(pb, enemy + 7, py)
    pb.memory[enemy + 14] = 1
    pb.memory[enemy + 17] = 0  # ordinary Crawler
    pb.memory[enemy + 25] = 0x88
    pb.tick()
    assert pb.memory[SEALED] == 1, "mandatory room opened while hostile lived"

    # Resolve the final enemy with a genuine player-owned projectile. Enemy
    # death may emit its own hit/death voice first; the room-clear boundary
    # must finish on the dedicated latch signature and release the seal.
    shot = EN + 31 * 28
    ex = pb.memory[enemy + 3] | (pb.memory[enemy + 4] << 8)
    ey = pb.memory[enemy + 7] | (pb.memory[enemy + 8] << 8)
    pb.memory[shot] = 1
    pb.memory[shot + 1] = 0x13  # active/alive/player projectile
    put16(pb, shot + 3, ex)
    put16(pb, shot + 7, ey)
    pb.memory[shot + 14] = 1
    pb.memory[shot + 16] = 30
    pb.memory[shot + 25] = 0x77
    pb.memory[shot + 26] = 20
    for _ in range(8):
        pb.tick()
        if pb.memory[enemy] == 0 and pb.memory[SEALED] == 0:
            break
    assert pb.memory[enemy] == 0, "final projectile did not defeat the Crawler"
    assert pb.memory[SEALED] == 0, "final mandatory kill did not unseal room"

    # room_unseal_doors waits for the VBlank on which its tile swap becomes
    # visible. PyBoy can return at that boundary just before the following
    # banked sound call executes, so finish the release frame before sampling.
    pb.tick()
    signature = tuple(pb.memory[address] for address in (
        0xFF10, 0xFF11, 0xFF12, 0xFF21, 0xFF22))
    assert (signature[0] & 0x7F) == 0x26 and signature[2:] == (
        0xC4, 0xB3, 0x5A), (
        f"mandatory clear did not finish on latch voice: {signature}")
    pb.stop(save=False)
    print(f"[unlock-feedback] PASS final real kill released seal with latch "
          f"signature {signature}")


if __name__ == "__main__":
    main()
