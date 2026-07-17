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

    def entities_by_type(entity_type):
        return [en + i * 28 for i in range(32)
                if pb.memory[en + i * 28] == entity_type]

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

    # Screen 0: named arrival square, elder/fountain, chartwright, three
    # authored exits. The chartwright gives a small route-reading blessing,
    # so villages are useful between procgen dungeons rather than scenery.
    enter_from_previous(19)
    assert pb.memory[rs + 19] == 0, "town did not begin in arrival square"
    elder = entities(7)
    chartwright = entities(12)
    waykeeper = entities(15)
    assert len(elder) == 1 and pb.memory[elder[0] + 12] == 69
    assert len(chartwright) == 1 and pb.memory[chartwright[0] + 12] == 123
    assert len(waykeeper) == 1 and pb.memory[waykeeper[0] + 12] == 124, \
        "arrival square lacks its dedicated north-gate Waykeeper"
    # The Waykeeper safely borrows the Rune Lantern's 8x8 VRAM slot only in a
    # town. Keep the exact town bytes so the transition below proves a normal
    # dungeon entry restores combat art rather than merely despawning the NPC.
    pb.memory[0xFF4F] = 0
    waykeeper_tile = bytes(pb.memory[0x8000 + 124 * 16:0x8000 + 125 * 16])
    assert not entities(4), "arrival square still crams market stock into one room"
    arrival = bytes(pb.memory[addr("_room_tilemap"):addr("_room_tilemap") + 340])
    assert arrival.count(3) == 6, "arrival square does not expose N/E/W village gates"
    pb.screen.image.save(ROOT / "tmp" / "town-arrival.png")

    # SELECT stays a graphical compass in a village too. The old text-only
    # town report made a three-screen settlement read like one strange room;
    # this tile graph exposes its craft quarter, arrival square, market, and
    # onward north gate at a glance.
    pb.button("select"); tick(120)
    assert pb.memory[screen] == 8, "SELECT did not open town compass"
    pb.memory[0xFF4F] = 0
    bg = 0x9800
    assert pb.memory[bg + 9 * 32 + 9] == 33, \
        f"arrival square lacks current marker (got {pb.memory[bg + 9 * 32 + 9]})"
    assert pb.memory[bg + 9 * 32 + 3] == 37, "craft quarter lacks roof marker"
    assert pb.memory[bg + 9 * 32 + 15] == 22, "market lacks crystal marker"
    assert pb.memory[bg + 4 * 32 + 9] == 3, "town compass lacks north gate"
    pb.screen.image.save(ROOT / "tmp" / "town-tile-map.png")
    pb.button("b"); tick(30)
    assert pb.memory[screen] == 5, "town compass did not resume arrival square"

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

    # The Chartwright marks the first two rooms of the next route without
    # turning the procedural map into a fully revealed spoiler.
    pb.memory[rs + 20] = 0
    ex, ey = pb.memory[chartwright[0] + 3], (pb.memory[chartwright[0] + 7] - 8) & 0xFF
    for off, value in ((9, ex), (10, 0), (11, ey), (12, 0)):
        pb.memory[pl + off] = value
    tick(5)
    assert pb.memory[rs + 20] & 0x03 == 0x03, "Chartwright did not mark two route rooms"
    assert pb.memory[chartwright[0] + 15] == 1, "Chartwright blessing did not latch"

    # East branch: dedicated market with merchant and three visually distinct
    # wares. Stock must retain its own heart/relic art rather than collapsing
    # into the old ambiguous orange tag sprite.
    leave("east")
    assert pb.memory[rs + 1] == 19 and pb.memory[rs + 19] == 1
    merchant, wares, tags = entities(8), entities(4), entities(13)
    assert len(merchant) == 1 and pb.memory[merchant[0] + 12] == 70
    assert len(wares) == 3
    assert len(tags) == 3 and all(pb.memory[t + 12] == 81 for t in tags), \
        "market stock lacks persistent gold sale markers"
    assert {pb.memory[t + 18] for t in tags} == {
        (w - en) // 28 for w in wares
    }, "sale markers are not bound to their wares"
    assert {pb.memory[w + 18] for w in wares} == {0, 1, 2}
    tick(70)
    assert pb.memory[wares[0] + 12] == 30, "heart stock lost its heart art"
    assert all(pb.memory[w + 12] == 35 for w in wares[1:]), \
        "relic stock lost its orb art"
    # A nearby merchant speaks visually before the player risks walking into
    # stock: a coin speech bubble makes the NPC's purpose legible even on a
    # busy market screen.
    mx, my = pb.memory[merchant[0] + 3], (pb.memory[merchant[0] + 7] - 8) & 0xFF
    for off, value in ((9, mx), (10, 0), (11, my + 24), (12, 0)):
        pb.memory[pl + off] = value
    tick(3)
    assert any(pb.memory[fx + 12] == 125 for fx in entities_by_type(4)), \
        "nearby merchant did not show its trade callout"
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

    # A sold ware removes its own marker. Restore currency only for this
    # contract check; the purchase itself remains the game's normal walk-into
    # interaction, with no UI-only shortcut.
    pb.memory[pl + 16] = 99
    pb.memory[pl + 17] = 0
    tick(6)
    assert pb.memory[ware] == 0, "purchased market ware remained active"
    tick(2)
    assert len(entities(13)) == 2, "sale marker remained after its ware sold"

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
    pb.memory[0xFF4F] = 0
    lantern_tile = bytes(pb.memory[0x8000 + 124 * 16:0x8000 + 125 * 16])
    assert lantern_tile != waykeeper_tile, \
        "Waykeeper art leaked from town into the Rune Lantern combat slot"

    pb.stop(save=False)
    print("[town] PASS connected arrival + market + forge quarter + north continuation")


if __name__ == "__main__":
    main()
