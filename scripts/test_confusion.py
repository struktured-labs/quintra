#!/usr/bin/env python3
"""Live-ROM contract: Confusion duration, shorten, and immunity.

Player Confusion rolls a triangular duration around 10 s, clamped to
[3.067 s, 20 s] (23..150 eight-frame beats at 60 Hz). Easy keeps the
same shape at 3/5 scale, still never below 3 s (cap 12 s). Standing
still still shortens the effect, and a 10 s immunity window after it
ends prevents back-to-back procs.
"""
from test_will_max import (
    PLAYER, SCREEN, addr, boot, clear_arena, put16,
)

NONE, CONFUSION = 0, 6
MIN_TICKS = 23
MEAN_TICKS = 75
MAX_TICKS = 150
EASY_MAX_TICKS = 90  # (150 * 3 + 2) // 5
IMMUNE_FRAMES = 600
SAMPLES = 256
DIFFICULTY_EASY = 1
RS = addr("_run_state")
DIFF = RS + 26
KIND = addr("_player_status_kind")
TICKS = addr("_player_status_ticks")
IMMUNE = addr("_confusion_immune")
APPLY = addr("_status_apply_req")


def u16(pb, at):
    return pb.memory[at] | (pb.memory[at + 1] << 8)


def poke_u16(pb, at, value):
    pb.memory[at] = value & 0xFF
    pb.memory[at + 1] = (value >> 8) & 0xFF


def calm(pb):
    clear_arena(pb)
    pb.memory[KIND] = NONE
    pb.memory[TICKS] = 0
    poke_u16(pb, IMMUNE, 0)
    put16(pb, PLAYER + 9, 80)
    put16(pb, PLAYER + 11, 72)
    for _ in range(2):
        pb.tick()


def roll_once(pb):
    """Force a live status_player_apply(CONFUSION) and return its ticks."""
    pb.memory[KIND] = NONE
    pb.memory[TICKS] = 0
    poke_u16(pb, IMMUNE, 0)
    pb.memory[APPLY] = CONFUSION
    for _ in range(8):
        pb.tick()
        if pb.memory[KIND] == CONFUSION and pb.memory[TICKS]:
            return pb.memory[TICKS]
    raise AssertionError("status_apply_req did not apply Confusion")


def sample_rolls(pb, n=SAMPLES):
    values = []
    for _ in range(n):
        values.append(roll_once(pb))
    return values


def check_dist(values, lo, hi, mean_lo, mean_hi, label):
    assert values, f"{label}: no samples"
    # The apply frame can also consume one 8-frame beat, so a 23-tick
    # roll is sometimes first observed as 22.
    assert min(values) >= lo - 1, f"{label}: min {min(values)} < {lo - 1}"
    assert max(values) <= hi, f"{label}: max {max(values)} > {hi}"
    mean = sum(values) / len(values)
    assert mean_lo <= mean <= mean_hi, (
        f"{label}: mean {mean:.2f} beats outside {mean_lo}..{mean_hi} "
        f"(n={len(values)}, min={min(values)}, max={max(values)})")
    print(f"[confusion] {label}: n={len(values)} min={min(values)} "
          f"max={max(values)} mean={mean:.2f} beats "
          f"({mean * 8 / 60:.2f}s at 60 Hz)")
    return mean


def test_duration_distribution():
    pb = boot(0)
    try:
        calm(pb)
        # Default boot is Normal.
        normal = sample_rolls(pb, SAMPLES)
        check_dist(normal, MIN_TICKS, MAX_TICKS, 65, 85, "Normal")
        # We should have actually seen a spread, not 256 copies of one value.
        assert len(set(normal)) >= 8, (
            f"Normal rolls were not spread out: {sorted(set(normal))}")

        pb.memory[DIFF] = DIFFICULTY_EASY
        easy = sample_rolls(pb, SAMPLES)
        check_dist(easy, MIN_TICKS, EASY_MAX_TICKS, 36, 56, "Easy")
        assert max(easy) <= EASY_MAX_TICKS
        assert sum(easy) / len(easy) < sum(normal) / len(normal), (
            "Easy mean was not shorter than Normal")
    finally:
        pb.stop(save=False)


def test_shorten_and_immunity():
    pb = boot(0)
    try:
        calm(pb)
        ticks = roll_once(pb)
        # Standing still for 1 s shortens by 8 beats (same rule as before).
        put16(pb, PLAYER + 9, 80)
        put16(pb, PLAYER + 11, 72)
        for _ in range(60):
            pb.tick()
        left = pb.memory[TICKS]
        # About 7 or 8 beats of wall time also elapse (60/8 = 7.5), plus
        # the stand-still shorten of 8, so we expect a drop around 15-16,
        # never an increase, and the status should still be live for a
        # typical mid roll.
        assert pb.memory[KIND] == CONFUSION, "Confusion ended during a 1 s stand"
        assert left < ticks, f"stand-still did not shorten ticks ({ticks} -> {left})"
        dropped = ticks - left
        assert 12 <= dropped <= 20, (
            f"stand-still drop {dropped} from {ticks} was not ~15-16 beats")

        # Expiry starts the 10 s immunity window, and a forced apply
        # is ignored while it lasts.
        pb.memory[TICKS] = 1
        for _ in range(16):
            pb.tick()
        assert pb.memory[KIND] == NONE
        immune = u16(pb, IMMUNE)
        assert immune >= IMMUNE_FRAMES - 16, (
            f"expiry immunity {immune} was not ~{IMMUNE_FRAMES}")
        pb.memory[APPLY] = CONFUSION
        for _ in range(8):
            pb.tick()
        assert pb.memory[KIND] == NONE, "Confusion applied during immunity"
        later = u16(pb, IMMUNE)
        assert later < immune, f"immunity did not tick ({immune} -> {later})"
    finally:
        pb.stop(save=False)


def main():
    test_duration_distribution()
    test_shorten_and_immunity()
    print("[confusion] PASS triangular 3-20s duration (Easy 3/5, floor 3s), "
          "stand-still shorten, 10s immunity")


if __name__ == "__main__":
    main()
