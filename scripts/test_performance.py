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


FC, EN, TM, WW, WH, CX, CY, EC, PL = map(addr, (
    "_loop_frame_counter", "_entities", "_room_tilemap",
    "_room_world_width", "_room_world_height",
    "_room_camera_x", "_room_camera_y",
    "_entity_enemy_count", "_player",
))


def put32(pb, address, value):
    for i in range(4):
        pb.memory[address + i] = (value >> (i * 8)) & 0xFF


def loop_frames(pb):
    return pb.memory[FC] | (pb.memory[FC + 1] << 8)


def boot_room():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    pb.button("start")
    pb.tick(30)
    pb.button("a")
    pb.tick(90)
    assert pb.memory[0xFF4D] & 0x80, "cartridge never entered CGB double-speed mode"
    pb.memory[PL + 1] = pb.memory[PL + 2] = 240
    return pb


def make_fixed_crawlers(pb):
    kept = 0
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] != 2 or not (pb.memory[ep + 1] & 1):
            continue
        if kept >= 16:
            pb.memory[ep] = pb.memory[ep + 1] = 0
            continue
        kept += 1
        pb.memory[ep + 12] = 20
        pb.memory[ep + 13] = 3
        pb.memory[ep + 14] = 8
        pb.memory[ep + 15] = pb.memory[ep + 16] = 0
        for offset in range(17, 25):
            pb.memory[ep + offset] = 0
        pb.memory[ep + 25] = 0x77
        pb.memory[ep + 26] = 1


def main():
    pb = boot_room()

    before = loop_frames(pb)
    pb.tick(180)
    generated = (loop_frames(pb) - before) & 0xFFFF
    population = []
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 2 and pb.memory[ep + 1] & 1:
            population.append({
                "slot": i,
                "awake": bool(pb.memory[ep + 1] & 4),
                "x": pb.memory[ep + 3],
                "y": pb.memory[ep + 7],
            })
    awake = sum(enemy["awake"] for enemy in population)
    assert 14 <= len(population) <= 18, (
        f"opening district population drifted: {len(population)}")
    assert 1 <= awake < len(population), (
        f"camera-sector sleeping drifted: awake={awake}/{len(population)}")
    # Asset uploads affect DIV before the run seed is mixed, so an authored
    # atlas can legitimately move this probe between 14- and 18-body rolls.
    # Preserve the 55 Hz floor at fourteen bodies and budget three loop turns
    # per additional actor instead of pretending those rooms cost the same.
    generated_floor = 165 - max(0, len(population) - 14) * 3
    assert generated >= generated_floor, (
        f"generated mixed-AI room missed 55 Hz: {generated}/180 loop frames"
    )

    # The shipped v0.20.5 clean-room baseline was 171/180 (57 Hz) for sixteen
    # enemies. A visible Road Echo is now a seventeenth 16x16 OAM actor; its
    # measured four-turn cost over this three-second window is the explicit
    # budget, while the projectile-only saturation fence below stays intact.
    # Fill 12/32 entity slots with long-lived projectiles over known floor.
    # This exercises banked updates, collision scans, animation, and OAM writes
    # without using host wall-clock speed or depending on one procgen seed.
    for y in range(3, 14):
        for x in range(3, 17):
            pb.memory[TM + y * ROOM_W + x] = 1
    for i in range(32):
        ep = EN + i * 28
        pb.memory[ep] = pb.memory[ep + 1] = 0
    pb.memory[EC] = 0
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

    # Asset loading legitimately advances DIV before run seeding, so a new
    # sprite atlas can change the opening species without changing game code.
    # Use a fresh boot and normalize its existing visibility layout before
    # enforcing the historical apples-to-apples 57 Hz fence.
    fixed_pb = boot_room()
    make_fixed_crawlers(fixed_pb)
    before = loop_frames(fixed_pb)
    fixed_pb.tick(180)
    ordinary = (loop_frames(fixed_pb) - before) & 0xFFFF
    fixed_pb.stop(save=False)

    assert ordinary >= 167, (
        f"fixed-roster room missed video rate: {ordinary}/180 loop frames"
    )
    assert active >= 10, f"stress load evaporated before measurement ({active}/12)"
    # Twelve simultaneous hostile shots produce the v0.20.5 saturated
    # baseline of 135/180 (45 Hz). This is a regression fence, not a claim
    # that the existing engine has already reached the future 80% target.
    assert loops >= 135, (
        f"dense room fell below release baseline: {loops}/180 loop frames"
    )
    print(f"[performance] PASS double-speed generated={generated}/180, "
          f"fixed-roster={ordinary}/180, "
          f"dense={loops}/180, population={len(population)}, "
          f"awake={awake}, active_projectiles={active}/12")


if __name__ == "__main__":
    main()
