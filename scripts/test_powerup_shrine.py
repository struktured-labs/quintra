#!/usr/bin/env python3
"""ROM contract: one-per-run power shrine flag + seed-stable placement hook."""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_class_select import downs_to_class

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()

ENT_PICKUP = 3
PICKUP_POWERUP, PICKUP_ROULETTE = 27, 28
# run_state.vignette_seen is at +60 (u16). #137 then appends secret_shop (+62),
# veil_charms (+63 u16) and rift_caves (+65 u32). powerup_shrines follows.
SHRINE_OFF = 69


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


def boot_class(class_id, screen, player):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    for _ in range(downs_to_class(class_id)):
        pb.button("down")
        for _ in range(16):
            pb.tick()
    pb.button("a")
    for _ in range(80):
        pb.tick()
    assert pb.memory[screen] == 5 and pb.memory[player] == class_id
    return pb


def poke_cmd(pb, cmd):
    pb.memory[addr("_powerup_world_live")] = 1
    pb.memory[addr("_powerup_test_cmd")] = cmd


def main():
    player, entities, screen = map(addr, ("_player", "_entities", "_loop_current_screen"))
    pb = boot_class(1, screen, player)
    for _ in range(2):
        for i in range(32 * 28):
            pb.memory[entities + i] = 0
        pb.tick()

    # Spawn a dungeon-shrine roulette beside the hero (test cmd 2).
    poke_cmd(pb, 2)
    for _ in range(6):
        pb.tick()
    slot = None
    for i in range(32):
        e = entities + i * 28
        if pb.memory[e] == ENT_PICKUP and pb.memory[e + 17] == PICKUP_ROULETTE:
            slot = e
            break
    assert slot, "shrine test hook did not spawn a roulette"
    # Overlap lock + 20-frame freeze awards the power-up.
    px = pb.memory[player + 9] | (pb.memory[player + 10] << 8)
    py = pb.memory[player + 11] | (pb.memory[player + 12] << 8)
    raw = (px + 4) << 8
    for i in range(4):
        pb.memory[slot + 2 + i] = (raw >> (i * 8)) & 0xFF
    raw = (py + 4) << 8
    for i in range(4):
        pb.memory[slot + 6 + i] = (raw >> (i * 8)) & 0xFF
    for _ in range(30):
        pb.tick()
    assert pb.memory[addr("_powerup_id")] in range(4, 9), (
        f"shrine roulette awarded {pb.memory[addr('_powerup_id')]}, want uncommon+")

    rs = addr("_run_state")
    assert pb.memory[rs + SHRINE_OFF] & 0x01, (
        f"dungeon shrine claim bit was not set on collect "
        f"(byte {pb.memory[rs + SHRINE_OFF]} at +{SHRINE_OFF})")

    # cmd 4 (place_room_shrine) must refuse once the dungeon bit is claimed.
    for i in range(32 * 28):
        if pb.memory[entities + i] == ENT_PICKUP:
            pb.memory[entities + i] = 0
    poke_cmd(pb, 4)
    for _ in range(4):
        pb.tick()
    leftover = [i for i in range(32)
                if pb.memory[entities + i * 28] == ENT_PICKUP]
    assert leftover == [], f"claimed shrine still placed a pickup: {leftover}"

    pb.stop(save=False)
    print("[powerup-shrine] PASS uncommon roulette, claim bit, no respawn")


if __name__ == "__main__":
    main()
