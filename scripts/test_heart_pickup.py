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


PL, EN, SCREEN, DIRECTOR_KIND = map(addr, (
    "_player", "_entities", "_loop_current_screen", "_room_encounter_kind"))


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


def tone(pb):
    return tuple(pb.memory[address] for address in (
        0xFF10, 0xFF11, 0xFF12, 0xFF13, 0xFF21, 0xFF22))


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
    # Finish any entry/secret melody before comparing isolated reward voices.
    # Dense cartridge frames can still be retiring after the visible tilemap
    # settles, and reward SFX correctly defer while that melody owns CH1.
    for _ in range(120):
        pb.memory[DIRECTOR_KIND] = 0
        pb.tick()
    # Use the last slot: PyBoy yields on VBlank, which can occur after the
    # resident entity loop has cached slot 0 but before combat. Injecting a
    # different type into that in-flight slot creates a debugger-only race.
    heart = EN + 31 * 28
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
    # Keep live wide-field terrain from turning this pickup-only contract into
    # a simultaneous spike-hit-and-heal transaction.
    pb.memory[PL + 15] = 120
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
    heart_tone = tone(pb)

    # MP wisps follow the same no-fake-pickup rule. Previously the orb
    # vanished and played a reward sound at full MP even though no HUD value
    # changed, which was indistinguishable from a failed collection.
    mp = EN + 31 * 28
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
    mp_tone = tone(pb)

    # Coins follow the same no-fake-pickup contract. At the 999 purse cap,
    # both ordinary and five-coin drops must remain visible rather than play a
    # pickup sound while producing no HUD change. A lower purse then collects
    # and clamps normally through the real collision path.
    coin = EN + 31 * 28
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
    coin_tone = tone(pb)
    assert heart_tone != coin_tone, (
        f"heart twinkle still aliases the coin chirp: {heart_tone}")

    # A harmless pickup touched by the visible shoulder must collect even if
    # terrain prevents the feet box from moving closer. This exact pose ends
    # at y+8, merely kissing (and therefore missing) the former feet-only box.
    shoulder = EN + 31 * 28
    pb.memory[shoulder] = 3
    pb.memory[shoulder + 1] = 3
    put16(pb, shoulder + 3, px + 5)
    put16(pb, shoulder + 7, py + 2)
    pb.memory[shoulder + 14] = 1
    pb.memory[shoulder + 16] = 240
    pb.memory[shoulder + 17] = 1  # PICKUP_COIN_1
    pb.memory[shoulder + 25] = 0x66
    pb.memory[PL + 16], pb.memory[PL + 17] = 0, 0
    for _ in range(3):
        pb.tick()
    assert pb.memory[shoulder] == 0 and pb.memory[PL + 16] == 1, (
        "visible shoulder overlap did not collect edge-adjacent loot"
    )

    coin5 = EN + 31 * 28
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

    # Permanent relics and temporary Surges have their own audio identities,
    # too. Run both through normal pickup collision and compare the complete
    # square/noise register signature with heart, coin, and magic recovery.
    relic = EN + 31 * 28
    pb.memory[relic] = 3
    pb.memory[relic + 1] = 3
    put16(pb, relic + 3, px + 4)
    put16(pb, relic + 7, py + 8)
    pb.memory[relic + 14] = 1
    pb.memory[relic + 16] = 240
    pb.memory[relic + 17] = 3   # PICKUP_ITEM
    pb.memory[relic + 18] = 10  # generated Iron Heart item index
    pb.memory[relic + 25] = 0x66
    for _ in range(3):
        pb.tick()
    assert pb.memory[relic] == 0, "permanent relic fixture did not collect"
    relic_tone = tone(pb)

    surge = EN + 31 * 28
    pb.memory[surge] = 3
    pb.memory[surge + 1] = 3
    put16(pb, surge + 3, px + 4)
    put16(pb, surge + 7, py + 8)
    pb.memory[surge + 14] = 1
    pb.memory[surge + 16] = 240
    pb.memory[surge + 17] = 14  # PICKUP_SURGE
    pb.memory[surge + 25] = 0x66
    for _ in range(3):
        pb.tick()
    assert pb.memory[surge] == 0, "temporary Surge fixture did not collect"
    surge_tone = tone(pb)

    pickup_tones = {
        "heart": heart_tone, "coin": coin_tone, "magic": mp_tone,
        "relic": relic_tone, "surge": surge_tone,
    }
    assert len(set(pickup_tones.values())) == len(pickup_tones), (
        f"pickup sound families alias one another: {pickup_tones}")
    pb.stop(save=False)
    print("[heart-pickup] PASS capped pickups wait; five distinct reward "
          f"voices {pickup_tones}")


if __name__ == "__main__":
    main()
