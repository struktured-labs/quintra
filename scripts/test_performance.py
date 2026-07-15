#!/usr/bin/env python3
"""ROM regression: CGB double-speed keeps a dense room near video rate."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
ROOM_W = 20


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


FC, EN, TM = map(addr, ("_loop_frame_counter", "_entities", "_room_tilemap"))


def put32(pb, address, value):
    for i in range(4):
        pb.memory[address + i] = (value >> (i * 8)) & 0xFF


def loop_frames(pb):
    return pb.memory[FC] | (pb.memory[FC + 1] << 8)


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    pb.button("start")
    pb.tick(30)
    pb.button("a")
    pb.tick(90)

    # KEY1 bit 7 is the hardware's current-speed flag, not a build marker.
    assert pb.memory[0xFF4D] & 0x80, "cartridge never entered CGB double-speed mode"

    before = loop_frames(pb)
    pb.tick(180)
    ordinary = (loop_frames(pb) - before) & 0xFFFF
    assert ordinary >= 178, (
        f"ordinary room missed video rate: {ordinary}/180 loop frames"
    )

    # Fill 12/32 entity slots with long-lived projectiles over known floor.
    # This exercises banked updates, collision scans, animation, and OAM writes
    # without using host wall-clock speed or depending on one procgen seed.
    for y in range(3, 14):
        for x in range(3, 17):
            pb.memory[TM + y * ROOM_W + x] = 1
    for i in range(32):
        ep = EN + i * 28
        pb.memory[ep] = pb.memory[ep + 1] = 0
    for i in range(12):
        ep = EN + i * 28
        x = 32 + (i % 7) * 16
        y = 24 + (i // 7) * 24
        pb.memory[ep] = 1          # ENT_PROJECTILE
        pb.memory[ep + 1] = 0x03  # active/alive hostile bullet-hell load
        put32(pb, ep + 2, x << 8)
        put32(pb, ep + 6, y << 8)
        pb.memory[ep + 10] = pb.memory[ep + 11] = 0
        pb.memory[ep + 12] = 28
        pb.memory[ep + 13] = 2
        pb.memory[ep + 14] = 1
        pb.memory[ep + 16] = 255
        pb.memory[ep + 25] = 0x77
        pb.memory[ep + 26] = 1

    before = loop_frames(pb)
    pb.tick(180)
    loops = (loop_frames(pb) - before) & 0xFFFF
    active = sum(pb.memory[EN + i * 28 + 1] & 1 for i in range(32))
    pb.stop(save=False)

    assert active >= 10, f"stress load evaporated before measurement ({active}/12)"
    assert loops >= 144, (
        f"dense room fell below 80% video rate: {loops}/180 loop frames"
    )
    print(f"[performance] PASS double-speed ordinary={ordinary}/180, "
          f"dense={loops}/180, active={active}/12")


if __name__ == "__main__":
    main()
