#!/usr/bin/env python3
"""Live-ROM regression: Spirit Convergence is capped below eight boss hits."""
from test_boss_identity import EN, PL, enter_boss


ENTITY_SIZE = 28
ENT_PROJECTILE = 1
EF_ACTIVE_ALIVE = 0x03
EF_PLAYER_PROJ = 0x10
PROJ_FLAG_CONVERGENCE = 0x01


def setup_shot(pb, address, x, y, *, convergence=False):
    pb.memory[address] = ENT_PROJECTILE
    pb.memory[address + 1] = EF_ACTIVE_ALIVE | EF_PLAYER_PROJ
    pb.memory[address + 3] = x
    pb.memory[address + 7] = y
    pb.memory[address + 10] = 0
    pb.memory[address + 11] = 0
    pb.memory[address + 14] = 1
    pb.memory[address + 16] = 90
    pb.memory[address + 20] = PROJ_FLAG_CONVERGENCE if convergence else 0
    pb.memory[address + 25] = 0x77
    pb.memory[address + 26] = 7


def hit_boss(*, convergence, stage=0):
    pb, boss = enter_boss(stage, keep_open=True)
    boss_x, boss_y = pb.memory[boss + 3], pb.memory[boss + 7]
    pb.memory[boss + 14] = 100
    # Keep the hero out of the constructed collision and above Last Stand's
    # bonus-damage threshold. Eight shots model the single A+B chord exactly.
    pb.memory[PL + 9] = 144
    pb.memory[PL + 11] = 112
    shot_count = 0
    for index in range(32):
        address = EN + index * ENTITY_SIZE
        if address == boss:
            continue
        setup_shot(pb, address, boss_x, boss_y, convergence=convergence)
        shot_count += 1
        if shot_count == 8:
            break
    before = pb.memory[boss + 14]
    # A boss-entry transition can hand control back during its final
    # presentation frame. Advance through that harmless handoff and any
    # hit-stop, then sample the completed collision sweep.
    for _ in range(20):
        pb.tick()
    after = pb.memory[boss + 14]
    pb.stop(save=False)
    return before - after


def main():
    chord_damage = hit_boss(convergence=True)
    ordinary_damage = hit_boss(convergence=False)
    void_damage = hit_boss(convergence=False, stage=8)
    assert chord_damage == 28, (
        f"Convergence chord landed {chord_damage} boss damage; expected four 7-damage hits"
    )
    assert ordinary_damage == 56, (
        f"ordinary projectiles changed unexpectedly ({ordinary_damage}, expected 56)"
    )
    assert void_damage == 56, (
        f"Void Lord should retain its positional burst fight ({void_damage}, expected 56)"
    )
    print("[convergence-cap] PASS chord=28; ordinary-eight=56; void-eight=56")


if __name__ == "__main__":
    main()
