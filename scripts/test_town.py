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
    rs, pl, en = addr("_run_state"), addr("_player"), addr("_entities")
    pb = PyBoy(str(ROM), window="null", cgb=True)
    tick = lambda n: [pb.tick() for _ in range(n)]
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
    for i in range(32):
        ep = en + i * 28
        if pb.memory[ep] == 3 and pb.memory[ep + 17] == 7:
            elder = ep
        elif pb.memory[ep] == 3 and pb.memory[ep + 17] == 8:
            merchant = ep
        elif pb.memory[ep] == 3 and pb.memory[ep + 17] == 9:
            smith = ep
    assert elder is not None, "town has no PICKUP_VILLAGER resident"
    assert pb.memory[elder + 12] == 69, "resident is not using villager art"
    assert merchant is not None, "town has no PICKUP_MERCHANT resident"
    assert pb.memory[merchant + 12] == 70, "merchant is not using merchant art"
    assert pb.memory[merchant + 12] != pb.memory[elder + 12], (
        "elder and merchant must remain visually distinct"
    )
    assert smith is not None, "town has no PICKUP_SMITH forge keeper"
    assert pb.memory[smith + 12] == 71, "smith is not using forge-keeper art"
    assert len({pb.memory[elder + 12], pb.memory[merchant + 12], pb.memory[smith + 12]}) == 3, (
        "elder, merchant, and smith silhouettes must remain distinct"
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
    print("[town] PASS sanctuary + elder/merchant/smith art + forge + Sauran Iron Heart growth")

if __name__ == "__main__":
    main()
