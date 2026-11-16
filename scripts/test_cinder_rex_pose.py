#!/usr/bin/env python3
"""Cinder Rex (48x32) opens its jaw on the wind-up and strides on the lunge."""
from test_boss_identity import enter_boss
from test_colossal_cinder import CINDER_PHASE, keep_alive

BANK = 0x08


def rex_rows(pb):
    """(screen y, pose bit) for each visible Rex tile (OAM 16..39, bank 1:
    idle 64..87, roar/stride 88..111)."""
    rows = []
    for i in range(16, 40):
        base = 0xFE00 + i * 4
        y, x, tile, prop = (pb.memory[base + k] for k in range(4))
        if y and x and (prop & BANK) and 64 <= tile < 112:
            rows.append((y, BANK if tile >= 88 else 0))
    return rows


def main():
    pb, boss = enter_boss(2, keep_open=True)
    # Unfold the Rex the real way (the metamorphosis places the 48x32 body).
    pb.memory[boss + 14] = 120
    for _ in range(400):
        keep_alive(pb, 1)
        if pb.memory[CINDER_PHASE] == 2:
            break
    assert pb.memory[CINDER_PHASE] == 2, "Rex never unfolded"
    seen = set()
    for _ in range(240):
        pb.memory[boss + 14] = 110
        keep_alive(pb, 1)
        rows = rex_rows(pb)
        if len(rows) < 24:
            continue
        top = min(y for y, _ in rows)
        for y, bit in rows:
            seen.add((0 if y < top + 16 else 1, bit))
    assert (0, BANK) in seen, f"roar never showed: {sorted(seen)}"
    assert (1, BANK) in seen, f"stride never showed: {sorted(seen)}"
    assert (0, 0) in seen and (1, 0) in seen, f"idle rows vanished: {sorted(seen)}"

    pb.memory[0xFF40] &= 0x7F
    pb.memory[0xFF4F] = 1
    idle = bytes(pb.memory[0x8000 + 64 * 16:0x8000 + 88 * 16])
    pose = bytes(pb.memory[0x8000 + 88 * 16:0x8000 + 112 * 16])
    differ = sum(a != b for a, b in zip(idle, pose))
    pb.stop(save=False)
    assert any(idle) and any(pose), "rex bank-1 tiles were never uploaded"
    assert differ > 64, f"roar/stride matches the idle upload ({differ} bytes)"
    print(f"cinder rex poses ok, vram bytes differ {differ}")


if __name__ == "__main__":
    main()
