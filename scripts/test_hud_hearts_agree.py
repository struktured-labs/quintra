#!/usr/bin/env python3
"""The HUD hearts and the heart pickup's HP FULL check always agree (#255).

A Vespine run showed a missing heart while a heart pickup refused with
HP FULL. Vespine starts on 13 half-hearts, an odd maximum, and the HUD
never drew a half heart: SDCC folded the half threshold "1 + i * 2" into
"(2 + i * 2) + 1", so any odd HP showed one half-heart less than the hero
had, and a full 13/13 looked like 12.

For every class, and for odd and even maxima up to the 16 half-heart cap:

  * walking over a heart at every HP below the maximum heals one
    half-heart, and the HUD then shows exactly that HP, half hearts
    included;
  * at the maximum the pickup refuses with HP FULL, the heart stays, and
    the HUD shows no empty or half heart;
  * below the maximum the HUD always shows at least one heart that is not
    full, so "missing a heart" on the HUD means a pickup will heal.
"""
from test_convergence_transform import PLAYER as PL, boot
from test_heart_hud import (
    HPFULL, HUD_HEART_EMPTY, HUD_HEART_FULL, HUD_HEART_HALF, hearts, notice,
    spawn_heart,
)

HUD_BLANK = 8
HP_CAP = 16
CLASSES = ("wolfkin", "sauran", "corvin", "picsean", "vespine")
BASE_MAX = (14, 16, 14, 14, 13)


def expected(hp, hp_max):
    """Eight HUD cells for hp of hp_max half-hearts."""
    row = []
    for slot in range(8):
        below = slot * 2
        if below >= hp_max:
            row.append(HUD_BLANK)
        elif hp >= hp_max or hp - below >= 2:
            row.append(HUD_HEART_FULL)
        elif hp - below == 1:
            row.append(HUD_HEART_HALF)
        else:
            row.append(HUD_HEART_EMPTY)
    return tuple(row)


def calm(pb):
    pb.memory[PL + 46] = pb.memory[PL + 47] = 0   # no hunger/heal-block curse
    pb.memory[PL + 15] = 0


def check_max(pb, name, hp_max):
    pb.memory[PL + 1] = hp_max
    for hp in range(2, hp_max + 1):
        calm(pb)
        pb.memory[PL + 2] = hp - 1
        heart = spawn_heart(pb)
        pb.tick()
        where = f"{name} max {hp_max}, heart taken at {hp - 1}"
        assert pb.memory[PL + 2] == hp, (
            f"{where}: pickup did not heal (hp {pb.memory[PL + 2]})")
        assert not pb.memory[heart + 1] & 1, f"{where}: heart stayed"
        row = hearts(pb)
        assert row == expected(hp, hp_max), (
            f"{where}: HUD shows {row}, want {expected(hp, hp_max)}")
        short = any(t in (HUD_HEART_EMPTY, HUD_HEART_HALF) for t in row)
        assert short == (hp < hp_max), (
            f"{where}: HUD {'shows' if short else 'hides'} a missing heart "
            f"at hp {hp}/{hp_max}")

    # At the maximum: refused, named, and the HUD agrees that it is full.
    calm(pb)
    where = f"{name} at full {hp_max}/{hp_max}"
    heart = spawn_heart(pb)
    pb.tick()
    assert pb.memory[heart + 1] & 1, f"{where}: a full hero consumed the heart"
    seen = False
    # The HEAL+1 notice from the last heal holds its lane for 105 frames,
    # and a floor heart times out, so keep one under the hero meanwhile.
    for frame in range(160):
        calm(pb)
        if frame % 16 == 0:
            spawn_heart(pb)
        pb.tick()
        if notice(pb) == HPFULL:
            seen = True
            break
    assert pb.memory[PL + 2] == hp_max, f"{where}: HP changed"
    assert seen, f"{where}: refusal did not say HP FULL: {notice(pb)}"
    row = hearts(pb)
    slots = (hp_max + 1) // 2
    assert row == (HUD_HEART_FULL,) * slots + (HUD_BLANK,) * (8 - slots), (
        f"{where}: the pickup says HP FULL but the HUD shows {row}")


def main():
    checked = 0
    for class_id, name in enumerate(CLASSES):
        pb = boot(class_id)
        pb.tick(30)
        assert pb.memory[PL] == class_id, f"did not enter as {name}"
        base = pb.memory[PL + 1]
        assert base == BASE_MAX[class_id], f"{name} starts on {base} half-hearts"
        assert pb.memory[PL + 2] == base
        row = hearts(pb)
        assert row == expected(base, base), (
            f"{name} starts at full {base}/{base} but the HUD shows {row}")
        # The class's own maximum, plus the next odd and even maxima a
        # Vitality relic can reach.
        for hp_max in sorted({base, min(base + 1, HP_CAP),
                              min(base + 2, HP_CAP), 3}):
            check_max(pb, name, hp_max)
            checked += 1
        pb.stop(save=False)
    print(f"[hud-hearts-agree] PASS {checked} class/max-HP combinations: "
          f"HUD hearts match HP at every value, half hearts included, and "
          f"HP FULL appears exactly when no heart is missing")


if __name__ == "__main__":
    main()
