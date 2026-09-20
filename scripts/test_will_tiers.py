#!/usr/bin/env python3
"""Tier timing, stat scaling, controls, and all champion attack shapes."""

from test_will_max import (
    PLAYER, ENTITIES, ENTITY_SIZE, WILL_OFFSET, LEVEL_OFFSET,
    addr, boot, clear_arena, fire_right, player_shots, press,
)


def main():
    pb = boot(0)
    clear_arena(pb)
    counter = [0]
    symbol = addr("_will_charge_tick")
    pb.hook_register(symbol >> 16, symbol & 0xFFFF,
                     lambda counts: counts.__setitem__(0, counts[0] + 1), counter)
    for speed in (0, 3, 5, 10, 30):
        pb.memory[PLAYER + 7] = speed
        pb.memory[PLAYER + 44] = 7
        pb.memory[PLAYER + LEVEL_OFFSET] = 0
        pb.memory[PLAYER + WILL_OFFSET] = 0
        pb.memory[addr("_will_charge_fraction")] = 0
        previous = 0
        start = counter[0]
        for level in range(1, 5):
            for _ in range(1600):
                pb.memory[PLAYER + 15] = 120
                pb.tick()
                if pb.memory[PLAYER + LEVEL_OFFSET] == level:
                    break
            else:
                raise AssertionError(("tier never filled", speed, level))
            duration = counter[0] - start
            expected = (90 + 30 * (level - 1)) * 40 / (15 + min(speed, 10))
            assert abs(duration - expected) <= 2, (speed, level, duration, expected)
            assert duration > previous, ("higher tier not slower", speed, level)
            previous, start = duration, counter[0]
        pb.tick(30)
        assert pb.memory[PLAYER + LEVEL_OFFSET] == 4
    pb.stop(save=False)

    pb = boot(0)
    clear_arena(pb)
    pb.memory[PLAYER + 44] = 7
    pb.memory[PLAYER + LEVEL_OFFSET] = 2
    pb.memory[PLAYER + WILL_OFFSET] = 45
    pb.memory[addr("_player_status_kind")] = 7
    pb.memory[addr("_player_status_ticks")] = 255
    pb.tick(30)
    assert pb.memory[PLAYER + WILL_OFFSET] == 45, "Mute charged Will"
    press(pb, "a")
    assert pb.memory[PLAYER + LEVEL_OFFSET] == 2, "Mute stole stored tiers"
    pb.memory[addr("_player_status_kind")] = 0
    pb.memory[addr("_player_status_ticks")] = 0
    press(pb, "start")
    frozen = (pb.memory[PLAYER + LEVEL_OFFSET], pb.memory[PLAYER + WILL_OFFSET])
    pb.tick(120)
    assert frozen == (pb.memory[PLAYER + LEVEL_OFFSET], pb.memory[PLAYER + WILL_OFFSET]), \
        "Pack charged Will"
    press(pb, "b")
    assert pb.memory[PLAYER + LEVEL_OFFSET] == 2, "Pack resume lost tiers"
    pb.stop(save=False)

    pb = boot(0)
    for owned, cap in ((0, 1), (1, 2), (2, 2), (3, 3), (7, 4), (8, 1)):
        clear_arena(pb)
        pb.memory[PLAYER + 44] = owned
        pb.memory[PLAYER + 7] = 5
        pb.memory[PLAYER + LEVEL_OFFSET] = 0
        pb.memory[PLAYER + WILL_OFFSET] = 0
        for _ in range(1300):
            pb.memory[PLAYER + 15] = 120
            pb.tick()
        assert pb.memory[PLAYER + LEVEL_OFFSET] == cap, (owned, cap)
        if cap == 4:
            pb.screen.image.save('/tmp/quintra-will-tier4.png')
    pb.stop(save=False)

    for hero in range(5):
        pb = boot(hero)
        previous = 0
        expected_shots = ((3, 5, 7, 8), (1, 3, 5, 7), (5, 6, 7, 8),
                          (5, 6, 7, 8), (3, 5, 7, 8))[hero]
        for level in range(1, 5):
            clear_arena(pb)
            pb.memory[PLAYER + 44] = 7
            pb.memory[PLAYER + LEVEL_OFFSET] = level
            pb.memory[PLAYER + WILL_OFFSET] = 20
            mp = pb.memory[PLAYER + 4]
            fire_right(pb)
            shots = player_shots(pb)
            assert len(shots) > previous, (hero, level, len(shots), previous)
            assert len(shots) == expected_shots[level - 1], (hero, level, len(shots))
            previous = len(shots)
            assert pb.memory[PLAYER + LEVEL_OFFSET] == 0, (hero, level)
            assert pb.memory[PLAYER + 4] == mp, "Will spent MP"
        clear_arena(pb)
        pb.memory[PLAYER + LEVEL_OFFSET] = 2
        pb.memory[PLAYER + WILL_OFFSET] = 20
        pb.memory[PLAYER + 19] = 0
        pb.memory[PLAYER + 4] = pb.memory[PLAYER + 3]
        pb.button_press("a")
        pb.button_press("b")
        pb.tick(12)
        pb.button_release("a")
        pb.button_release("b")
        assert pb.memory[PLAYER + 4] == 0, "A+B lost Convergence"
        assert pb.memory[PLAYER + LEVEL_OFFSET] == 2, "A+B spent Will"
        pb.stop(save=False)

    pb = boot(0)
    clear_arena(pb)
    pb.memory[PLAYER + LEVEL_OFFSET] = 1
    pb.memory[PLAYER + WILL_OFFSET] = 90
    for slot in range(32):
        base = ENTITIES + slot * ENTITY_SIZE
        pb.memory[base] = 4
        pb.memory[base + 1] = 1
        pb.memory[base + 16] = 255
    press(pb, "a", held=2, released=1)
    assert pb.memory[PLAYER + LEVEL_OFFSET] == 1, "full entity table stole Will"
    pb.stop(save=False)
    print("[will-tiers] PASS timing, SPD cap, five heroes x four tiers, A+B, capacity")


if __name__ == "__main__":
    main()
