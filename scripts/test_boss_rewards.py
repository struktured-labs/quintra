#!/usr/bin/env python3
"""Live-ROM regression: a saturated boss kill still pays every guaranteed reward."""
from test_boss_identity import EN, PL, enter_boss


ENTITY_SIZE = 28
ENT_PROJECTILE = 1
ENT_PICKUP = 3
EF_ACTIVE_ALIVE = 0x03
EF_PLAYER_PROJ = 0x10
PICKUP_HEART_HALF = 0
PICKUP_COIN_5 = 2
PICKUP_ITEM = 3


def setup_projectile(pb, address, x, y, player_owned=False):
    pb.memory[address] = ENT_PROJECTILE
    pb.memory[address + 1] = EF_ACTIVE_ALIVE | (EF_PLAYER_PROJ if player_owned else 0)
    pb.memory[address + 3] = x
    pb.memory[address + 7] = y
    pb.memory[address + 10] = 0
    pb.memory[address + 11] = 0
    pb.memory[address + 14] = 1
    pb.memory[address + 16] = 90  # survive entity_update until combat resolves
    pb.memory[address + 25] = 0x77
    pb.memory[address + 26] = 1


def main():
    pb, boss = enter_boss(0, keep_open=True)
    boss_x, boss_y = pb.memory[boss + 3], pb.memory[boss + 7]
    pb.memory[boss + 14] = 1
    # The post-fight recovery beat is distinct from physical floor hearts:
    # park the hero away from rewards and prove the clear itself restores one
    # heart, capped by normal max-HP rules.
    pb.memory[PL + 2] = 4

    # Fill every other slot with real hostile projectiles, then use one of
    # those slots as the lethal player shot. Before the regression fix, the
    # live boss and its full bullet storm left no room for its reward drops.
    shot = None
    for index in range(32):
        address = EN + index * ENTITY_SIZE
        if address == boss:
            continue
        setup_projectile(pb, address, 8, 8)
        if shot is None:
            shot = address
    assert shot is not None
    setup_projectile(pb, shot, boss_x, boss_y, player_owned=True)

    # Keep the hero away from the parked hostile shots. Let the cartridge
    # advance through any transition/hit-stop frames before the next combat
    # sweep; pickups remain fresh enough that their ordinary timers cannot
    # obscure the assertion.
    pb.memory[PL + 9] = 144
    pb.memory[PL + 11] = 112
    for _ in range(20):
        pb.tick()

    kinds = []
    hostile_shots = 0
    boss_active = False
    for index in range(32):
        address = EN + index * ENTITY_SIZE
        active = pb.memory[address + 1] & 1
        if active and pb.memory[address] == ENT_PICKUP:
            kinds.append(pb.memory[address + 17])
        if active and pb.memory[address] == ENT_PROJECTILE \
                and not (pb.memory[address + 1] & EF_PLAYER_PROJ):
            hostile_shots += 1
        if active and pb.memory[address] == 2 and pb.memory[address + 17] == 1:
            boss_active = True

    assert not boss_active, (
        "lethal shot did not retire the large boss "
        f"(hp={pb.memory[boss + 14]} type={pb.memory[boss]} "
        f"shot_type={pb.memory[shot]} shot_hp={pb.memory[shot + 14]} "
        f"shot_flags={pb.memory[shot + 1]:02x})"
    )
    assert hostile_shots == 0, "boss-death bullet clear left hostile shots alive"
    assert pb.memory[PL + 2] == 6, (
        f"boss clear did not grant its one-heart recovery: hp={pb.memory[PL + 2]}")
    assert kinds.count(PICKUP_HEART_HALF) >= 2, f"missing boss hearts: {kinds}"
    assert kinds.count(PICKUP_COIN_5) >= 2, f"missing boss coins: {kinds}"
    assert PICKUP_ITEM in kinds, f"missing guaranteed boss relic: {kinds}"
    pb.stop(save=False)
    print(f"[boss-rewards] PASS recovery heart + saturated hearts/coins/relic ({kinds})")


if __name__ == "__main__":
    main()
