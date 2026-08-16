#!/usr/bin/env python3
"""Live-ROM contract for the nine telegraphed Colossus signatures."""
from test_boss_identity import EN, PL, enter_boss


ENTITY_SIZE = 28
EXPECTED = (3, 8, 5, 8, 8, 5, 8, 5, 8)
NAMES = (
    "Prism Lance", "Coil Tempest", "Furnace Breath",
    "Web Crucifix", "Miasma Bloom", "Death Sweep",
    "Sunfall", "Threefold Deluge", "Event Horizon",
)


def clear_disposable(pb):
    for slot in range(32):
        entity = EN + slot * ENTITY_SIZE
        if pb.memory[entity] in (1, 4):
            pb.memory[entity] = pb.memory[entity + 1] = 0


def hostile_projectiles(pb):
    result = []
    for slot in range(32):
        entity = EN + slot * ENTITY_SIZE
        if (pb.memory[entity] == 1
                and pb.memory[entity + 1] & 1
                and not pb.memory[entity + 1] & 0x10):
            vx = pb.memory[entity + 10]
            vy = pb.memory[entity + 11]
            result.append((vx - 256 if vx >= 128 else vx,
                           vy - 256 if vy >= 128 else vy))
    return result


def main():
    report = []
    for stage, (name, expected) in enumerate(zip(NAMES, EXPECTED)):
        pb, boss = enter_boss(stage, keep_open=True)
        try:
            clear_disposable(pb)
            maximum = pb.memory[boss + 23]
            assert maximum > 1, f"stage {stage + 1} never captured max HP"
            pb.memory[boss + 14] = maximum // 2

            saw_warning = False
            initial_timer = 0
            shots = []
            for _ in range(320):
                pb.memory[PL + 15] = 255
                pb.memory[PL + 2] = 16
                pb.tick()
                flags = pb.memory[boss + 20]
                if flags & 0x40:
                    saw_warning = True
                    initial_timer = max(initial_timer, pb.memory[boss + 18])
                current = hostile_projectiles(pb)
                if (saw_warning and not (flags & 0x40)
                        and pb.memory[boss + 18] >= 30
                        and len(current) >= expected):
                    shots = current
                    break

            assert saw_warning and initial_timer >= 40, (
                f"stage {stage + 1} {name} lost its long warning: {initial_timer}")
            assert pb.memory[boss + 20] & 0x80, (
                f"stage {stage + 1} {name} did not latch as spent")
            assert pb.memory[boss + 18] >= 30, (
                f"stage {stage + 1} {name} lost its recovery window")
            assert len(shots) == expected, (
                f"stage {stage + 1} {name} emitted {len(shots)}, expected {expected}")

            if stage in (0, 2, 7):
                assert len(set(shots)) == 1, f"{name} lost its unified fat lane"
            elif stage == 5:
                assert all(vy == 0 and vx for vx, vy in shots), (
                    "Death Sweep no longer crosses one horizontal row")
            elif stage in (1, 4, 6, 8):
                assert len(set(shots)) == 8, f"{name} lost its complete radial bloom"
            else:
                assert len(set(shots)) == 4, (
                    "Web Crucifix lost one of its cardinal directions")
            report.append(f"{stage + 1}:{name}={len(shots)}")
        finally:
            pb.stop(save=False)

    print("[colossus-signatures] PASS " + "; ".join(report))


if __name__ == "__main__":
    main()
