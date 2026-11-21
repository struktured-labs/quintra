#!/usr/bin/env python3
"""Per-hero ailment resistance: 50% shrug, -25% duration, never immunity."""
from test_will_max import PLAYER, boot, clear_arena, addr

# kind ids must match status.h
KIND = {
    "poison": 1, "burn": 2, "slow": 3, "stop": 4, "blind": 5,
    "confusion": 6, "mute": 7, "brittle": 8, "bleed": 9, "curse": 10,
}
TABLE = [
    (0, "Wolfkin", "bleed", 9, 45, "burn", 2, 60),
    (1, "Sauran", "brittle", 8, 56, "bleed", 9, 60),
    (2, "Corvin", "blind", 5, 56, "bleed", 9, 60),
    (3, "Picsean", "burn", 2, 45, "bleed", 9, 60),
    (4, "Vespine", "poison", 1, 90, "bleed", 9, 60),
]
# 75% of 75 = 56.25; we use ticks - (ticks>>2) = 75-18 = 57? 
# 75 >> 2 = 18, 75-18 = 57. I used 56 in the spec (floor of 75*0.75).
# Need to match the C: ticks - (ticks >> 2).
# 60 - 15 = 45 (bleed/burn) OK
# 75 - 18 = 57 (blind/brittle), not 56!
# 120 - 30 = 90 (poison) OK
# Fix expected brittle/blind to 57.


def apply_once(pb, kind):
    req = addr("_status_apply_req")
    st = addr("_player_status_kind")
    ticks = addr("_player_status_ticks")
    # Clear first so a prior status does not confuse the read
    pb.memory[st] = 0
    pb.memory[ticks] = 0
    pb.memory[req] = kind
    # Gate + tick must run; a handful of frames is enough
    pb.tick(4)
    return pb.memory[st], pb.memory[ticks]


def test_hero(class_id, name, resist_name, resist_kind, resist_ticks,
              other_name, other_kind, other_ticks):
    pb = boot(class_id)
    try:
        clear_arena(pb)
        # Normal difficulty: Easy would halve durations.
        shrugged = 0
        landed = 0
        landed_ticks = []
        for _ in range(40):
            kind, ticks = apply_once(pb, resist_kind)
            if kind == 0:
                shrugged += 1
            elif kind == resist_kind:
                landed += 1
                landed_ticks.append(ticks)
            else:
                raise AssertionError(f"{name}: unexpected kind {kind}")
        assert 12 <= shrugged <= 28, (
            f"{name} shrug rate off: {shrugged}/40 (want ~20)")
        assert landed >= 8, f"{name} never landed {resist_name}"
        # Duration is counted down every 8 frames; 4 ticks of apply may have
        # burned 0 of the status tick (status_clock & 7). Allow 2 ticks slack.
        for t in landed_ticks:
            assert abs(t - resist_ticks) <= 2, (
                f"{name} landed {resist_name} at {t}, want ~{resist_ticks}")
        # A non-resisted ailment always applies at full duration.
        hits = 0
        for _ in range(8):
            kind, ticks = apply_once(pb, other_kind)
            if kind == other_kind:
                hits += 1
                assert abs(ticks - other_ticks) <= 2, (
                    f"{name} {other_name} duration {ticks}, want ~{other_ticks}")
            else:
                raise AssertionError(
                    f"{name} shrugged non-resisted {other_name} (kind {kind})")
        assert hits == 8, f"{name} failed to apply non-resisted {other_name}"
        print(f"  {name}: {resist_name} shrug {shrugged}/40, "
              f"landed ticks {landed_ticks[:3]}..., {other_name} full")
    finally:
        pb.stop(save=False)


def main():
    # Match C: ticks - (ticks >> 2)
    rows = [
        (0, "Wolfkin", "bleed", 9, 45, "burn", 2, 60),
        (1, "Sauran", "brittle", 8, 57, "bleed", 9, 60),
        (2, "Corvin", "blind", 5, 57, "bleed", 9, 60),
        (3, "Picsean", "burn", 2, 45, "bleed", 9, 60),
        (4, "Vespine", "poison", 1, 90, "bleed", 9, 60),
    ]
    for row in rows:
        test_hero(*row)
    print("[class-status-resist] PASS 5 heroes, shrug + duration + no cross-resist")


if __name__ == "__main__":
    main()
