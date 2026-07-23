#!/usr/bin/env python3
"""Live-ROM regression for Hornet solo chase and procedural swarm slots."""
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


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def hornet(pb, address, x, y):
    pb.memory[address] = 2
    pb.memory[address + 1] = 3
    put_fix8(pb, address + 2, x)
    put_fix8(pb, address + 6, y)
    pb.memory[address + 14] = 7
    pb.memory[address + 16] = 1  # move on its next even cadence tick
    pb.memory[address + 17] = 2
    pb.memory[address + 25] = 0x66


def xy(pb, address):
    return pb.memory[address + 3], pb.memory[address + 7]


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
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    pb.memory[player + 2] = 20
    pb.memory[player + 15] = 255
    put16(pb, player + 9, 80)
    put16(pb, player + 11, 64)

    lead = entities
    wingmate = entities + 28
    hornet(pb, lead, 32, 64)
    hornet(pb, wingmate, 32, 80)
    for _ in range(6):
        pb.tick()
    lead_x, lead_y = xy(pb, lead)
    wing_x, wing_y = xy(pb, wingmate)
    assert lead_x > 32 and lead_y == 64, (
        f"Hornet swarm lead did not pressure the champion: {lead_x},{lead_y}")
    assert wing_x > 32 and wing_y < 80, (
        f"Hornet wingmate did not take its raised flank: {wing_x},{wing_y}")

    # Removing the companion must restore the original direct solo chase.
    pb.memory[wingmate] = pb.memory[wingmate + 1] = 0
    before_x, before_y = xy(pb, lead)
    for _ in range(6):
        pb.tick()
    solo_x, solo_y = xy(pb, lead)
    assert solo_x > before_x and solo_y == before_y, (
        f"Solo Hornet did not retain direct chase: {before_x},{before_y} -> {solo_x},{solo_y}")

    # A Hornet is a persistent chaser, not an intangible projectile. It must
    # not enter an 8px hallway that the 12px champion cannot later use to
    # finish a sealed encounter. Its visible 8px body still reads as agile;
    # this only gives its navigation the same clearance as the player.
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    for x in range(1, 19):
        pb.memory[tilemap + 7 * 20 + x] = 2
        pb.memory[tilemap + 9 * 20 + x] = 2
    hornet(pb, lead, 32, 64)
    put16(pb, player + 9, 80)
    put16(pb, player + 11, 64)
    for _ in range(8):
        pb.tick()
    corridor_x, corridor_y = xy(pb, lead)
    assert (corridor_x, corridor_y) == (32, 64), (
        "Hornet entered a one-tile corridor the champion cannot occupy: "
        f"{corridor_x},{corridor_y}")
    print("[hornet-swarm] PASS formation flanks, solo chase remains direct")


if __name__ == "__main__":
    main()
