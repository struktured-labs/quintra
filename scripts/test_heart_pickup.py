#!/usr/bin/env python3
"""ROM contract: capped heart/MP pickups remain available until useful."""
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


PL, EN, SCREEN = map(addr, ("_player", "_entities", "_loop_current_screen"))


def press(pb, button, held=4, released=4):
    pb.button_press(button)
    for _ in range(held):
        pb.tick()
    pb.button_release(button)
    for _ in range(released):
        pb.tick()


def put16(pb, address, pixels):
    pb.memory[address] = pixels & 0xFF
    pb.memory[address + 1] = (pixels >> 8) & 0xFF


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    press(pb, "start")
    for _ in range(30):
        pb.tick()
    press(pb, "a")
    for _ in range(80):
        pb.tick()
    assert pb.memory[SCREEN] == 5
    # Let the opening room settle its entry placement before sampling a
    # collision point; the room transition may still publish the centered
    # spawn during its first visible frames.
    for _ in range(60):
        pb.tick()

    # Isolate a real pickup entity directly under the player's normal
    # collision box. The test writes setup state only; both outcomes run
    # through combat_resolve -> pickup_check_player_collision in the ROM.
    for i in range(32 * 28):
        pb.memory[EN + i] = 0
    heart = EN
    px = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
    py = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
    pb.memory[heart] = 3
    pb.memory[heart + 1] = 3
    put16(pb, heart + 3, px + 4)
    put16(pb, heart + 7, py + 8)
    pb.memory[heart + 14] = 1
    pb.memory[heart + 16] = 240
    pb.memory[heart + 17] = 0  # PICKUP_HEART_HALF
    pb.memory[heart + 25] = 0x66

    pb.memory[PL + 1] = 8
    pb.memory[PL + 2] = 8
    for _ in range(3):
        pb.tick()
    assert pb.memory[heart] == 3 and pb.memory[PL + 2] == 8, \
        ("full-health heart was consumed without healing "
         f"(entity={pb.memory[heart]}/{pb.memory[heart + 1]} "
         f"hp={pb.memory[PL + 2]}/{pb.memory[PL + 1]})")

    pb.memory[PL + 2] = 7
    for _ in range(3):
        pb.tick()
    assert pb.memory[heart] == 0 and pb.memory[PL + 2] == 8, \
        ("heart did not heal and consume once health was missing "
         f"(entity={pb.memory[heart]}/{pb.memory[heart + 1]} "
         f"hp={pb.memory[PL + 2]}/{pb.memory[PL + 1]} "
         f"player={list(pb.memory[PL + 9:PL + 13])} "
         f"heart={list(pb.memory[heart + 2:heart + 18])})")

    # MP wisps follow the same no-fake-pickup rule. Previously the orb
    # vanished and played a reward sound at full MP even though no HUD value
    # changed, which was indistinguishable from a failed collection.
    mp = EN
    pb.memory[mp] = 3
    pb.memory[mp + 1] = 3
    put16(pb, mp + 3, px + 4)
    put16(pb, mp + 7, py + 8)
    pb.memory[mp + 14] = 1
    pb.memory[mp + 16] = 240
    pb.memory[mp + 17] = 6  # PICKUP_MP
    pb.memory[mp + 25] = 0x66
    pb.memory[PL + 3] = 4
    pb.memory[PL + 4] = 4
    for _ in range(3):
        pb.tick()
    assert pb.memory[mp] == 3 and pb.memory[PL + 4] == 4, \
        "full-MP wisp was consumed without restoring a point"

    pb.memory[PL + 4] = 3
    for _ in range(3):
        pb.tick()
    assert pb.memory[mp] == 0 and pb.memory[PL + 4] == 4, \
        "MP wisp did not restore and consume once MP was missing"

    # Coins follow the same no-fake-pickup contract. At the 999 purse cap,
    # both ordinary and five-coin drops must remain visible rather than play a
    # pickup sound while producing no HUD change. A lower purse then collects
    # and clamps normally through the real collision path.
    coin = EN
    pb.memory[coin] = 3
    pb.memory[coin + 1] = 3
    put16(pb, coin + 3, px + 4)
    put16(pb, coin + 7, py + 8)
    pb.memory[coin + 14] = 1
    pb.memory[coin + 16] = 240
    pb.memory[coin + 17] = 1  # PICKUP_COIN_1
    pb.memory[coin + 25] = 0x66
    pb.memory[PL + 16], pb.memory[PL + 17] = 0xE7, 0x03  # 999
    for _ in range(3):
        pb.tick()
    assert pb.memory[coin] == 3 and (pb.memory[PL + 16] | (pb.memory[PL + 17] << 8)) == 999, \
        "full-purse coin was consumed without a visible gain"
    pb.memory[PL + 16], pb.memory[PL + 17] = 0xE6, 0x03  # 998
    for _ in range(3):
        pb.tick()
    assert pb.memory[coin] == 0 and (pb.memory[PL + 16] | (pb.memory[PL + 17] << 8)) == 999, \
        "ordinary coin did not collect to the purse cap"

    coin5 = EN
    pb.memory[coin5] = 3
    pb.memory[coin5 + 1] = 3
    put16(pb, coin5 + 3, px + 4)
    put16(pb, coin5 + 7, py + 8)
    pb.memory[coin5 + 14] = 1
    pb.memory[coin5 + 16] = 240
    pb.memory[coin5 + 17] = 2  # PICKUP_COIN_5
    pb.memory[coin5 + 25] = 0x66
    pb.memory[PL + 16], pb.memory[PL + 17] = 0xE7, 0x03
    for _ in range(3):
        pb.tick()
    assert pb.memory[coin5] == 3, "full-purse five-coin drop was consumed"
    pb.memory[PL + 16], pb.memory[PL + 17] = 0xE4, 0x03  # 996
    for _ in range(3):
        pb.tick()
    assert pb.memory[coin5] == 0 and (pb.memory[PL + 16] | (pb.memory[PL + 17] << 8)) == 999, \
        "five-coin drop did not clamp and collect correctly"
    pb.stop(save=False)
    print("[heart-pickup] PASS capped heart/MP/coins wait, missing stats restore")


if __name__ == "__main__":
    main()
