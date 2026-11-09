#!/usr/bin/env python3
"""Late-phase locomotion stays with each boss, and Void's blast matches its marks.

The retired shared stepper is simulated here so the east-wall bias stays
visible. Live rooms then check Spider, Hydra, Crystal, Void anchors, the
Event Horizon boundary, Reaper's linked fan, and the warp-flash duty cycle.
"""
from test_boss_identity import EN, PL, addr, enter_boss, put16

ENTITY = 28
ENT_FX = 4
ENT_PROJECTILE = 1


def pos(pb, entity):
    return (pb.memory[entity + 3] | (pb.memory[entity + 4] << 8),
            pb.memory[entity + 7] | (pb.memory[entity + 8] << 8))


def retired_shared_drift(steps=256):
    """East steps minus west steps of the removed Spider/Hydra stepper."""
    x = 0
    clock = 0
    for _ in range(steps):
        clock = (clock + 1) & 255
        if 64 <= clock < 112:
            continue
        folded = clock & 127
        if folded & 1:
            continue
        x += 1 if folded < 64 else -1
    return x


def half_health(pb, boss):
    maximum = pb.memory[boss + 23] or pb.memory[boss + 14]
    pb.memory[boss + 14] = max(1, maximum // 2)
    pb.memory[boss + 2] = 1
    # Bits 7 and 5 mark both signature crises spent so the locomotion
    # sample is not frozen inside the warning countdown.
    pb.memory[boss + 20] = (pb.memory[boss + 20] | 0xA1) & 0xBF
    pb.memory[PL + 2] = pb.memory[PL + 1] = 200
    pb.memory[PL + 15] = 255


def track(stage, frames):
    pb, boss = enter_boss(stage, keep_open=True)
    half_health(pb, boss)
    put16(pb, PL + 9, 80)
    put16(pb, PL + 11, 64)
    samples = []
    for _ in range(frames):
        pb.tick()
        samples.append(pos(pb, boss))
    pb.stop(save=False)
    return samples


def flash_duty(start):
    """Hidden frames after the drawer's decrement-then-odd test."""
    hidden = shown = 0
    value = start
    while value:
        value -= 1
        if value & 1:
            hidden += 1
        else:
            shown += 1
    return hidden, shown


def main():
    drift = retired_shared_drift()
    assert drift >= 24, f"retired stepper no longer documents the east pin: {drift}"
    hidden12, shown12 = flash_duty(12)
    hidden4, shown4 = flash_duty(4)
    assert (hidden12, shown12) == (6, 6)
    assert (hidden4, shown4) == (2, 2)
    assert hidden12 / 36 < 0.2

    spider = track(3, 400)
    assert any(abs(b[0] - a[0]) + abs(b[1] - a[1]) > 16
               for a, b in zip(spider, spider[1:])), \
        f"Spider late phase never blinked: {spider[0]} -> {spider[-1]}"
    assert spider[-1][0] < 200, f"Spider pinned east: {spider[-1]}"
    hydra = track(7, 400)
    dx = [b[0] - a[0] for a, b in zip(hydra, hydra[1:])]
    assert any(step > 0 for step in dx) and any(step < 0 for step in dx), \
        f"Hydra late phase lost its bounce: {hydra[0]} -> {hydra[-1]}"
    assert hydra[-1][0] < 200, f"Hydra pinned east: {hydra[-1]}"
    crystal = track(0, 220)
    wells = {(24, 48), (96, 32), (176, 72)}
    assert wells.intersection(crystal), f"Crystal left its wells: {set(crystal)}"
    void = track(8, 120)
    anchors = {(40, 32), (104, 32), (160, 64), (104, 40)}
    assert len(anchors.intersection(void)) >= 2, f"Void left its anchors: {set(void)}"

    pb, boss = enter_boss(8, keep_open=True)
    half_health(pb, boss)
    center = pos(pb, boss)
    pb.memory[boss + 2] = 2
    pb.memory[boss + 5] = 0
    pb.memory[boss + 20] |= 0x40
    pb.memory[boss + 18] = 48
    marks = []
    for _ in range(40):
        pb.tick()
        for index in range(32):
            entity = EN + index * ENTITY
            if pb.memory[entity] != ENT_FX:
                continue
            fx = pos(pb, entity)
            marks.append((abs(fx[0] - (center[0] + 12)),
                          abs(fx[1] - (center[1] + 12))))
    assert any(max(dx, dy) >= 90 for dx, dy in marks), \
        f"Event Horizon marks stayed inside the old 50px tell: {marks[:12]}"
    put16(pb, PL + 9, center[0] + 64)
    put16(pb, PL + 11, center[1])
    pb.memory[PL + 2] = 80
    pb.memory[PL + 15] = 0
    pb.memory[boss + 20] |= 0x40
    pb.memory[boss + 18] = 2
    for _ in range(6):
        pb.tick()
    assert pb.memory[PL + 2] < 80, "64px inside Event Horizon was safe"
    put16(pb, PL + 9, center[0] + 110)
    put16(pb, PL + 11, center[1])
    pb.memory[PL + 2] = 80
    pb.memory[PL + 15] = 0
    pb.memory[boss + 20] |= 0x40
    pb.memory[boss + 18] = 2
    for _ in range(6):
        pb.tick()
    assert pb.memory[PL + 2] == 80, \
        f"110px outside Event Horizon still hurt: {pb.memory[PL + 2]}"
    pb.memory[boss + 24] = 4
    seen = []
    for _ in range(6):
        pb.tick()
        seen.append(pb.memory[boss + 24])
    assert seen[0] < 4 and seen[-1] == 0, seen
    assert all(seen[i] >= seen[i + 1] for i in range(len(seen) - 1))
    pb.stop(save=False)

    link = addr("_boss_link_active")
    pb, boss = enter_boss(5, keep_open=True)
    half_health(pb, boss)
    pb.memory[boss + 2] = 2
    pb.memory[boss + 6] = 127
    pb.memory[boss + 5] = 0
    angles = set()
    linked = False
    for _ in range(90):
        pb.tick()
        linked = linked or bool(pb.memory[link])
        if not pb.memory[link]:
            continue
        for index in range(32):
            entity = EN + index * ENTITY
            if pb.memory[entity] != ENT_PROJECTILE:
                continue
            if pb.memory[entity + 1] & 0x10:
                continue
            angles.add(pb.memory[entity + 17])
    assert linked, "Reaper never linked"
    assert len(angles) >= 3, f"linked Reaper did not fan: {sorted(angles)}"
    pb.stop(save=False)
    print(f"[late-motion] PASS retired drift +{drift}px/256, "
          f"flash 12->{hidden12} hidden/{shown12} shown, "
          f"flash 4->{hidden4} hidden/{shown4} shown")


if __name__ == "__main__":
    main()
