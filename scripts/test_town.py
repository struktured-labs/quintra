#!/usr/bin/env python3
"""ROM contract: sanctuaries plus a real connected three-screen village."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    m = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not m:
        raise RuntimeError(f"missing symbol {name}")
    return int(m.group(1), 16)


def main():
    rs, pl, en, screen = map(addr, (
        "_run_state", "_player", "_entities", "_loop_current_screen"))
    pb = PyBoy(str(ROM), window="null", cgb=True)

    def tick(n):
        for _ in range(n):
            pb.tick()

    def entities(kind=None):
        out = []
        for i in range(32):
            ep = en + i * 28
            if pb.memory[ep] != 3:
                continue
            if kind is None or pb.memory[ep + 17] == kind:
                out.append(ep)
        return out

    def clear_hostiles():
        for i in range(32):
            ep = en + i * 28
            if pb.memory[ep] == 2:
                pb.memory[ep] = pb.memory[ep + 1] = 0

    def enter_from_previous(target):
        pb.memory[rs + 1] = target - 1
        clear_hostiles()
        for off, value in ((9, 72), (10, 0), (11, 120), (12, 0)):
            pb.memory[pl + off] = value
        tick(45)
        assert pb.memory[rs + 1] == target, f"could not enter room {target}"

    def leave(direction):
        positions = {
            "north": (72, 0), "east": (144, 60),
            "south": (72, 120), "west": (0, 60),
        }
        x, y = positions[direction]
        for off, value in ((9, x), (10, 0), (11, y), (12, 0)):
            pb.memory[pl + off] = value
        tick(45)

    tick(240)
    pb.button("start"); tick(30)
    pb.button("down"); tick(8)  # Sauran
    pb.button("a"); tick(60)
    assert pb.memory[screen] == 5 and pb.memory[pl] == 1

    # Every pre-boss sanctuary remains a guaranteed full reset.
    pb.memory[pl + 2] = 1
    pb.memory[pl + 4] = 0
    enter_from_previous(5)
    assert pb.memory[pl + 2] == pb.memory[pl + 1]
    assert pb.memory[pl + 4] == pb.memory[pl + 3]

    # Screen 0: named arrival square, elder/fountain, three authored exits.
    enter_from_previous(19)
    assert pb.memory[rs + 19] == 0, "town did not begin in arrival square"
    elder = entities(7)
    assert len(elder) == 1 and pb.memory[elder[0] + 12] == 69
    assert not entities(4), "arrival square still crams market stock into one room"
    arrival = bytes(pb.memory[addr("_room_tilemap"):addr("_room_tilemap") + 340])
    assert arrival.count(3) == 6, "arrival square does not expose N/E/W village gates"
    pb.screen.image.save(ROOT / "tmp" / "town-arrival.png")

    # Elder is a visible, permanent full blessing.
    pb.memory[pl + 2] = 1
    pb.memory[pl + 4] = 0
    ex, ey = pb.memory[elder[0] + 3], (pb.memory[elder[0] + 7] - 8) & 0xFF
    for off, value in ((9, ex), (10, 0), (11, ey), (12, 0)):
        pb.memory[pl + off] = value
    tick(5)
    assert pb.memory[pl + 2] == pb.memory[pl + 1]
    assert pb.memory[pl + 4] == pb.memory[pl + 3]
    assert pb.memory[elder[0]] == 3

    # East branch: dedicated market with merchant and three visually distinct
    # wares. Stock must retain its own heart/relic art rather than collapsing
    # into the old ambiguous orange tag sprite.
    leave("east")
    assert pb.memory[rs + 1] == 19 and pb.memory[rs + 19] == 1
    merchant, wares = entities(8), entities(4)
    assert len(merchant) == 1 and pb.memory[merchant[0] + 12] == 70
    assert len(wares) == 3
    assert {pb.memory[w + 18] for w in wares} == {0, 1, 2}
    tick(70)
    assert pb.memory[wares[0] + 12] == 30, "heart stock lost its heart art"
    assert all(pb.memory[w + 12] == 35 for w in wares[1:]), \
        "relic stock lost its orb art"
    # Approach a ware without touching it: the market announces its price
    # before a walk-into purchase. Leaving the stall clears the context hint.
    ware = wares[0]
    pb.memory[pl + 16] = pb.memory[pl + 17] = 0
    wx, wy = pb.memory[ware + 3], (pb.memory[ware + 7] - 8) & 0xFF
    for off, value in ((9, wx), (10, 0), (11, wy - 24), (12, 0)):
        pb.memory[pl + off] = value
    tick(6)
    pb.memory[0xFF4F] = 0
    assert pb.memory[0x9C00 + 12] == 7, "nearby market ware did not show price HUD"
    for off, value in ((9, 16), (10, 0), (11, 16), (12, 0)):
        pb.memory[pl + off] = value
    tick(6)
    pb.memory[0xFF4F] = 0
    assert pb.memory[0x9C00 + 12] == 8, "market price HUD stayed after leaving stall"

    # Touch one unaffordable offer: it survives and latches one reject buzz.
    for off, value in ((9, wx), (10, 0), (11, wy), (12, 0)):
        pb.memory[pl + off] = value
    tick(6)
    assert pb.memory[ware] == 3 and pb.memory[ware + 21] == 1
    pb.memory[0xFF4F] = 0
    assert pb.memory[0x9C00 + 12] == 7, "market contact did not show coin/price HUD"
    pb.screen.image.save(ROOT / "tmp" / "town-market.png")

    # West back to arrival, then west again: forge/apothecary quarter.
    leave("west")
    assert pb.memory[rs + 19] == 0
    leave("west")
    assert pb.memory[rs + 1] == 19 and pb.memory[rs + 19] == 2
    smith, apothecary, wares = entities(9), entities(10), entities(4)
    assert len(smith) == len(apothecary) == 1
    assert pb.memory[smith[0] + 12] == 71
    assert pb.memory[apothecary[0] + 12] == 79
    assert len(wares) == 2 and {pb.memory[w + 18] for w in wares} == {3, 4}
    assert len({69, 70, pb.memory[smith[0] + 12], pb.memory[apothecary[0] + 12]}) == 4
    pb.screen.image.save(ROOT / "tmp" / "town-quarter.png")

    # Return to arrival and leave north: only now does dungeon depth advance.
    leave("east")
    assert pb.memory[rs + 19] == 0 and pb.memory[rs + 1] == 19
    leave("north")
    assert pb.memory[rs + 1] == 20, "north village gate did not continue the run"
    assert pb.memory[rs + 19] == 0, "town-local screen leaked into dungeon state"

    pb.stop(save=False)
    print("[town] PASS connected arrival + market + forge quarter + north continuation")


if __name__ == "__main__":
    main()
