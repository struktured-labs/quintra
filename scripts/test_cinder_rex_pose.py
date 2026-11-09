#!/usr/bin/env python3
"""Cinder Rex opens its jaw on the wind-up and strides on the lunge."""
from test_boss_identity import enter_boss
from test_colossal_cinder import CINDER_PHASE, keep_alive

BANK = 0x08


def rex_rows(pb):
    """(screen y, bank bit) for each visible Rex tile."""
    rows = []
    for i in range(4, 22):
        base = 0xFE00 + i * 4
        y, x, tile, prop = (pb.memory[base + k] for k in range(4))
        if y and x and ((48 <= tile <= 55 and not (prop & BANK))
                        or (128 <= tile <= 135 and (prop & BANK))):
            rows.append((y, prop & BANK))
    return rows


def main():
    pb, boss = enter_boss(2, keep_open=True)
    pb.memory[boss + 14] = 180
    pb.memory[CINDER_PHASE] = 2
    seen = set()
    for _ in range(240):
        pb.memory[boss + 14] = 180
        pb.memory[CINDER_PHASE] = 2
        keep_alive(pb, 1)
        rows = rex_rows(pb)
        if len(rows) < 8:
            continue
        top = min(y for y, _ in rows)
        for y, bit in rows:
            seen.add((0 if y == top else 1, bit))
    assert (0, BANK) in seen, f"roar never showed: {sorted(seen)}"
    assert (1, BANK) in seen, f"stride never showed: {sorted(seen)}"
    assert (0, 0) in seen and (1, 0) in seen, f"idle rows vanished: {sorted(seen)}"

    pb.memory[0xFF40] &= 0x7F
    pb.memory[0xFF4F] = 0
    idle = bytes(pb.memory[0x8000 + 48 * 16:0x8000 + 56 * 16])
    pb.memory[0xFF4F] = 1
    pose = bytes(pb.memory[0x8000 + 128 * 16:0x8000 + 136 * 16])
    forbidden = bytes(pb.memory[0x8000 + 48 * 16:0x8000 + 56 * 16])
    differ = sum(a != b for a, b in zip(idle, pose))
    pb.stop(save=False)
    assert differ > 16, f"bank-1 rex matches the idle upload ({differ} bytes)"
    assert forbidden != pose, "rex pose was uploaded over bank-1 tiles 48..55"
    print(f"cinder rex poses ok, vram bytes differ {differ}")


if __name__ == "__main__":
    main()
