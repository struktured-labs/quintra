#!/usr/bin/env python3
"""Live-ROM contract: a real double-tap dash shakes off a latched Gloom Leech."""
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


PL, EN, TM = map(addr, ("_player", "_entities", "_room_tilemap"))


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def press(pb, button, held=2, released=2):
    pb.button_press(button)
    for _ in range(held):
        pb.tick()
    pb.button_release(button)
    for _ in range(released):
        pb.tick()


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")  # Wolfkin
    for _ in range(120):
        pb.tick()

    for i in range(32 * 28):
        pb.memory[EN + i] = 0
    for i in range(20 * 17):
        pb.memory[TM + i] = 1  # clear, dashable floor
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 72)
    pb.memory[PL + 15] = 0  # no inherited room-entry recovery

    leech = EN
    pb.memory[leech] = 2       # ENT_ENEMY
    pb.memory[leech + 1] = 3   # active + alive
    put_fix8(pb, leech + 2, 76)
    put_fix8(pb, leech + 6, 73)
    pb.memory[leech + 14] = 10
    pb.memory[leech + 17] = 13  # ENEMY_GLOAM_LEECH
    pb.memory[leech + 23] = 1   # ai_data[6]: already attached
    pb.memory[leech + 25] = 0x66

    # The same right/right controller sequence a player uses to dash. The
    # engine—not this fixture—must create the dash recovery window, which the
    # Leech AI then observes and uses to release the latch.
    press(pb, "right")
    pb.button_press("right")
    pb.tick()
    dash_iframes = pb.memory[PL + 15]
    for _ in range(5):
        pb.tick()
    pb.button_release("right")
    for _ in range(4):
        pb.tick()
    for _ in range(8):
        pb.tick()

    assert pb.memory[leech + 23] == 0, "Gloom Leech stayed attached after dash"
    assert dash_iframes >= 12, "double-tap did not produce dash recovery"
    hero_x = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
    assert hero_x > 72, f"dash did not carry champion out of latch: x={hero_x}"

    # A latch can be shaken loose while the champion is riding the north
    # door edge. The old release preserved the attached y=2 sprite there,
    # outside the enemy navigation band: it could neither chase nor be hit
    # and therefore softlocked a sealed room. The release must rehome it on
    # a legal, player-reachable floor position.
    put16(pb, PL + 11, 1)
    put_fix8(pb, leech + 2, 76)
    put_fix8(pb, leech + 6, 2)
    pb.memory[leech + 1] = 3
    pb.memory[leech + 17] = 13
    pb.memory[leech + 23] = 1
    # The first half of this regression already proves that a real double-tap
    # supplies this recovery window. Inject just that established engine
    # condition here so the second fixture tests edge placement rather than
    # coupling itself to the first dash's cooldown timer.
    pb.memory[PL + 15] = 16
    for _ in range(4):
        pb.tick()
    leech_y = pb.memory[leech + 7]
    assert pb.memory[leech + 23] == 0, (
        "edge Leech stayed attached after dash: "
        f"type={pb.memory[leech]} flags={pb.memory[leech + 1]} "
        f"iframes={pb.memory[PL + 15]} y={pb.memory[leech + 7]}"
    )
    assert leech_y >= 8, f"edge Leech released outside legal floor: y={leech_y}"
    pb.stop(save=False)
    print(f"[leech-detach] PASS released latch; dash reached x={hero_x}; edge y={leech_y}")


if __name__ == "__main__":
    main()
