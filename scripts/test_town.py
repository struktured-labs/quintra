#!/usr/bin/env python3
"""ROM-level sanctuary and town healing contracts."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi")

def addr(name):
    m = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI.read_text())
    if not m:
        raise SystemExit(f"missing symbol {name}")
    return int(m.group(1), 16)

def main():
    from pyboy import PyBoy
    rs, pl, en, screen = (
        addr("_run_state"), addr("_player"), addr("_entities"),
        addr("_loop_current_screen")
    )
    pb = PyBoy(str(ROM), window="null", cgb=True)
    tick = lambda n: [pb.tick() for _ in range(n)]
    def press(button):
        pb.button_press(button)
        tick(4)
        pb.button_release(button)
        tick(4)
    tick(240); pb.button("start"); tick(30)
    pb.button("down"); tick(8)  # Sauran: six-heart melee tank
    pb.button("a"); tick(60)
    assert pb.memory[pl] == 1, "class select did not choose Sauran"
    assert pb.memory[pl + 1] == 12, "Sauran starting HP contract drifted"

    def enter_from_previous(target):
        pb.memory[rs + 1] = target - 1
        for i in range(32):
            ep = en + i * 28
            if pb.memory[ep] == 2:
                pb.memory[ep] = pb.memory[ep + 1] = 0
        for off, value in ((9, 72), (10, 0), (11, 120), (12, 0)):
            pb.memory[pl + off] = value
        tick(45)
        assert pb.memory[rs + 1] == target, f"could not enter room {target}"

    # Every pre-boss sanctuary is a guaranteed full reset, not two optional
    # half-heart drops. This keeps deep bosses fair for fragile champions.
    pb.memory[pl + 2] = 1
    pb.memory[pl + 4] = 0
    enter_from_previous(5)
    assert pb.memory[pl + 2] == pb.memory[pl + 1], "sanctuary did not restore HP"
    assert pb.memory[pl + 4] == pb.memory[pl + 3], "sanctuary did not restore MP"

    # Enter the first post-region town and verify its resident blessing too.
    enter_from_previous(19)
    assert pb.memory[rs + 1] == 19, "could not enter first town"

    elder = None
    merchant = None
    smith = None
    apothecary = None
    for i in range(32):
        ep = en + i * 28
        if pb.memory[ep] == 3 and pb.memory[ep + 17] == 7:
            elder = ep
        elif pb.memory[ep] == 3 and pb.memory[ep + 17] == 8:
            merchant = ep
        elif pb.memory[ep] == 3 and pb.memory[ep + 17] == 9:
            smith = ep
        elif pb.memory[ep] == 3 and pb.memory[ep + 17] == 10:
            apothecary = ep
    assert elder is not None, "town has no PICKUP_VILLAGER resident"
    assert pb.memory[elder + 12] == 69, "resident is not using villager art"
    assert merchant is not None, "town has no PICKUP_MERCHANT resident"
    assert pb.memory[merchant + 12] == 70, "merchant is not using merchant art"
    assert pb.memory[merchant + 12] != pb.memory[elder + 12], (
        "elder and merchant must remain visually distinct"
    )
    assert smith is not None, "town has no PICKUP_SMITH forge keeper"
    assert pb.memory[smith + 12] == 71, "smith is not using forge-keeper art"
    assert apothecary is not None, "town has no PICKUP_APOTHECARY rune keeper"
    assert pb.memory[apothecary + 12] == 79, "rune keeper is not using apothecary art"
    assert len({pb.memory[elder + 12], pb.memory[merchant + 12],
                pb.memory[smith + 12], pb.memory[apothecary + 12]}) == 4, (
        "all four village roles must retain distinct silhouettes"
    )

    # SELECT in a town must show town context, not the mathematically wrapped
    # "Dungeon 1 / Depth 2" labels that used to contradict YOU ARE HERE.
    press("select")
    tick(60)
    assert pb.memory[screen] == 8, "town SELECT did not open Spirit Compass"
    compass_shot = ROOT / "tmp" / "town-compass.png"
    pb.screen.image.save(compass_shot)
    press("b")
    tick(8)
    assert pb.memory[screen] == 5 and pb.memory[rs + 1] == 19, (
        "town compass did not resume the same town"
    )

    # Merchants are permanent scenery/NPCs rather than collectible pickups.
    mx = pb.memory[merchant + 3]
    my = (pb.memory[merchant + 7] - 8) & 0xFF
    for off, value in ((9, mx), (10, 0), (11, my), (12, 0)):
        pb.memory[pl + off] = value
    tick(4)
    assert pb.memory[merchant] == 3 and pb.memory[merchant + 17] == 8, (
        "merchant disappeared when touched"
    )

    # The smith is also permanent; the adjacent forge ware owns the purchase.
    sx = pb.memory[smith + 3]
    sy = (pb.memory[smith + 7] - 8) & 0xFF
    for off, value in ((9, sx), (10, 0), (11, sy), (12, 0)):
        pb.memory[pl + off] = value
    tick(4)
    assert pb.memory[smith] == 3 and pb.memory[smith + 17] == 9, (
        "smith disappeared when touched"
    )

    ax = pb.memory[apothecary + 3]
    ay = (pb.memory[apothecary + 7] - 8) & 0xFF
    for off, value in ((9, ax), (10, 0), (11, ay), (12, 0)):
        pb.memory[pl + off] = value
    tick(4)
    assert pb.memory[apothecary] == 3 and pb.memory[apothecary + 17] == 10, (
        "apothecary disappeared when touched"
    )

    shot = ROOT / "tmp" / "town-merchant.png"
    shot.parent.mkdir(exist_ok=True)
    pb.screen.image.save(shot)

    pb.memory[pl + 2] = 1       # wounded, empty magic
    pb.memory[pl + 4] = 0
    # Player collision is feet-anchored (y+8), so y=40 meets elder y=48.
    for off, value in ((9, 80), (10, 0), (11, 40), (12, 0)):
        pb.memory[pl + off] = value
    tick(4)
    assert pb.memory[pl + 2] == pb.memory[pl + 1], "elder did not restore HP"
    assert pb.memory[pl + 4] == pb.memory[pl + 3], "elder did not restore MP"
    assert pb.memory[elder + 15] == 1, "elder blessing did not latch"

    # The guaranteed Iron Heart stall must remain useful even to Sauran,
    # whose six-heart start formerly collided with the global HP cap.
    iron_heart = None
    for i in range(32):
        ep = en + i * 28
        if (pb.memory[ep] == 3 and pb.memory[ep + 17] == 4
                and pb.memory[ep + 18] == 2):
            iron_heart = ep
            break
    assert iron_heart is not None, "town has no WARE_BIG Iron Heart stall"
    price = pb.memory[iron_heart + 19]
    pb.memory[pl + 16] = price
    pb.memory[pl + 17] = 0
    # Entity fix8 integer bytes are x+3/y+7; player pickup collision is
    # feet-anchored, so stand eight pixels above the ware.
    px = pb.memory[iron_heart + 3]
    py = (pb.memory[iron_heart + 7] - 8) & 0xFF
    for off, value in ((9, px), (10, 0), (11, py), (12, 0)):
        pb.memory[pl + off] = value
    tick(4)
    assert pb.memory[pl + 1] == 14, (
        f"Iron Heart did not raise Sauran to seven hearts "
        f"(hpmax={pb.memory[pl + 1]}, coins={pb.memory[pl + 16]}, "
        f"ware_type={pb.memory[iron_heart]}, pos={pb.memory[pl + 9]},{pb.memory[pl + 11]})"
    )
    assert pb.memory[pl + 2] == 14, "Iron Heart did not fill the new heart"
    assert pb.memory[pl + 16] == 0 and pb.memory[pl + 17] == 0, "purchase did not deduct coins"

    forge = None
    for i in range(32):
        ep = en + i * 28
        if (pb.memory[ep] == 3 and pb.memory[ep + 17] == 4
                and pb.memory[ep + 18] == 3):
            forge = ep
            break
    assert forge is not None, "town has no WARE_FORGE Power Stone stall"
    old_atk = pb.memory[pl + 5]
    price = pb.memory[forge + 19]
    pb.memory[pl + 16] = price
    pb.memory[pl + 17] = 0
    px = pb.memory[forge + 3]
    py = (pb.memory[forge + 7] - 8) & 0xFF
    for off, value in ((9, px), (10, 0), (11, py), (12, 0)):
        pb.memory[pl + off] = value
    tick(4)
    assert pb.memory[pl + 5] == old_atk + 1, "forge did not grant +1 ATK"
    assert pb.memory[pl + 16] == 0 and pb.memory[pl + 17] == 0, "forge did not deduct coins"

    rune = None
    for i in range(32):
        ep = en + i * 28
        if (pb.memory[ep] == 3 and pb.memory[ep + 17] == 4
                and pb.memory[ep + 18] == 4):
            rune = ep
            break
    assert rune is not None, "town has no WARE_RUNE Mana Gem counter"
    old_mp_max = pb.memory[pl + 3]
    price = pb.memory[rune + 19]
    pb.memory[pl + 16] = price
    pb.memory[pl + 17] = 0
    px = pb.memory[rune + 3]
    py = (pb.memory[rune + 7] - 8) & 0xFF
    for off, value in ((9, px), (10, 0), (11, py), (12, 0)):
        pb.memory[pl + off] = value
    tick(4)
    assert pb.memory[pl + 3] == old_mp_max + 2, "rune shop did not grant +2 max MP"
    assert pb.memory[pl + 4] == pb.memory[pl + 3], "Mana Gem did not fill new MP"
    assert pb.memory[pl + 16] == 0 and pb.memory[pl + 17] == 0, "rune shop did not deduct coins"

    # Multi-point relic boosts must saturate at their advertised runtime cap.
    # Hunter's Eye is generated item index 18 and grants +3 LCK; the former
    # check-before-add implementation allowed 9 + 3 to leak through as 12.
    relic = next(en + i * 28 for i in range(32) if pb.memory[en + i * 28] == 0)
    for off in range(28):
        pb.memory[relic + off] = 0
    pb.memory[relic] = 3             # ENT_PICKUP
    pb.memory[relic + 1] = 3         # EF_ACTIVE | EF_ALIVE
    pb.memory[relic + 3] = 80        # fix8 x integer byte
    pb.memory[relic + 7] = 48        # fix8 y integer byte
    pb.memory[relic + 16] = 255      # linger
    pb.memory[relic + 17] = 3        # PICKUP_ITEM
    pb.memory[relic + 18] = 18       # Hunter's Eye array index
    pb.memory[relic + 25] = 0x66     # pickup hitbox
    pb.memory[pl + 8] = 9
    for off, value in ((9, 80), (10, 0), (11, 40), (12, 0)):
        pb.memory[pl + off] = value
    relic_lck_trace = []
    for _ in range(4):
        pb.tick()
        relic_lck_trace.append(pb.memory[pl + 8])
    assert pb.memory[pl + 8] == 10, (
        f"Hunter's Eye cap/pickup failed (lck={pb.memory[pl + 8]}, "
        f"entity={pb.memory[relic]}/{pb.memory[relic + 1]}, "
        f"kind={pb.memory[relic + 17]}, item={pb.memory[relic + 18]}, "
        f"epos={pb.memory[relic + 3]},{pb.memory[relic + 7]}, "
        f"ppos={pb.memory[pl + 9]},{pb.memory[pl + 11]}, "
        f"trace={relic_lck_trace})"
    )

    # Ordinary dungeon shops are staffed too, not only the larger town hubs.
    enter_from_previous(22)
    shop_merchant = None
    for i in range(32):
        ep = en + i * 28
        if pb.memory[ep] == 3 and pb.memory[ep + 17] == 8:
            shop_merchant = ep
            break
    assert shop_merchant is not None, "ordinary shop has no merchant"
    assert pb.memory[shop_merchant + 12] == 70, "shop merchant art drifted"
    pb.stop(save=False)
    print("[town] PASS sanctuary + market/forge/rune shops + four distinct residents")

if __name__ == "__main__":
    main()
