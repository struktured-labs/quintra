#!/usr/bin/env python3
"""Live-ROM proof for Blast Seed, fractal Echo Prism, and Rift Lens."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


PL, EN, TM, TRAITS = map(addr, (
    "_player", "_entities", "_room_tilemap", "_g_player_attack_traits",
))


def put16(pb, where, value):
    pb.memory[where] = value & 0xFF
    pb.memory[where + 1] = value >> 8


def boot():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    pb.button("start")
    pb.tick(30)
    pb.button("a")
    pb.tick(80)
    for i in range(20 * 17):
        pb.memory[TM + i] = 1
    return pb


def clear_entities(pb):
    for i in range(32 * 28):
        pb.memory[EN + i] = 0


def projectiles(pb):
    return [EN + i * 28 for i in range(32)
            if pb.memory[EN + i * 28] == 1
            and pb.memory[EN + i * 28 + 1] & 0x10]


def fire(pb):
    pb.memory[PL + 22] = 0
    pb.memory[PL + 42] = 0
    before = set(projectiles(pb))
    pb.button_press("right")
    pb.button_press("a")
    pb.tick()
    pb.button_release("a")
    pb.button_release("right")
    pb.tick(2)
    made = [shot for shot in projectiles(pb) if shot not in before]
    assert made, "primary attack failed to spawn"
    return made[0]


def place_enemy(pb, slot, x, y, hp=10):
    e = EN + slot * 28
    pb.memory[e] = 2
    pb.memory[e + 1] = 0x07
    put16(pb, e + 3, x)
    put16(pb, e + 7, y)
    pb.memory[e + 14] = hp
    pb.memory[e + 17] = 0
    pb.memory[e + 25] = 0x88
    return e


def main():
    # Blast Seed: the spawned primary carries the one-use marker, then its
    # direct hit damages a second nearby body through a real area burst.
    blast = boot()
    clear_entities(blast)
    blast.memory[TRAITS] = 0x08
    shot = fire(blast)
    assert blast.memory[shot + 20] & 0x08, "Blast Seed did not mark primary"
    put16(blast, shot + 3, 80)
    put16(blast, shot + 7, 64)
    blast.memory[shot + 10] = blast.memory[shot + 11] = 0
    direct = place_enemy(blast, 4, 80, 64)
    splash = place_enemy(blast, 5, 90, 64)
    blast.tick(4)
    assert blast.memory[direct + 14] < 10, "direct Blast Seed hit missed"
    blast.tick()
    assert blast.memory[splash + 14] < 10, "Blast Seed area hit was cosmetic"
    blast.stop(save=False)

    # Echo Prism: every fourth deliberate A makes two children; each splits
    # once after travel into four smaller lanes and then stops fractal growth.
    echo = boot()
    clear_entities(echo)
    put16(echo, PL + 9, 80)
    put16(echo, PL + 11, 64)
    echo.memory[PL + 24] = 34
    for attack in range(4):
        try:
            fire(echo)
        except AssertionError as error:
            raise AssertionError(f"Echo primary {attack + 1} failed") from error
    first = [p for p in projectiles(echo) if echo.memory[p + 20] & 0x10]
    assert len(first) == 2, f"Echo first generation drifted: {len(first)}"
    echo.tick(20)
    children = [p for p in projectiles(echo) if echo.memory[p + 25] == 0x55]
    assert len(children) >= 4, f"Echo did not fractal into four lanes: {len(children)}"
    echo.tick(20)
    assert len(projectiles(echo)) <= 10, "Echo Prism recursed without a bound"
    echo.stop(save=False)

    # Rift Lens: the third primary becomes a broad, durable, two-OBJ beam.
    beam = boot()
    clear_entities(beam)
    put16(beam, PL + 9, 80)
    put16(beam, PL + 11, 64)
    beam.memory[PL + 24] = 44
    fire(beam)
    fire(beam)
    third = fire(beam)
    assert beam.memory[third + 20] & 0x20, "Rift Lens cadence did not mark beam"
    assert beam.memory[third + 12] == 158 and beam.memory[third + 25] == 0xDD
    assert beam.memory[third + 14] >= 6, "fat beam lost its heavy pierce body"
    beam.tick(2)
    oam_tiles = [beam.memory[0xFE02 + i * 4] for i in range(4, 40)]
    assert 158 in oam_tiles and 159 in oam_tiles, \
        f"fat beam was not rendered as two sprites: {oam_tiles}"
    beam.stop(save=False)
    print("[attack-physics] PASS splash AOE + bounded 2->4 fractal + fat beam")


if __name__ == "__main__":
    main()
