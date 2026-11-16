#!/usr/bin/env python3
"""Live-ROM contract: conditions are survivable, readable and curable.

- Poison, Burn and Bleed never take the last half-heart on their own: a
  champion at one half-heart rides out the full duration of each.
- Totals: Poison 8, Burn 5, Bleed at most 3 half-hearts (sprinting the
  whole time); Bleed costs nothing while standing still.
- Every drain tick re-names the condition, harm re-names itself while it
  lasts, and harm that wears off says CURED.
- The Antidote cures all three: automatically at the half-heart floor, from
  the Pack TOOL row (focused for Burn/Bleed too), and it still refuses on a
  healthy body.
"""
import os
from pathlib import Path

from test_will_max import (
    PLAYER, SCREEN, addr, boot, clear_arena, press, put16,
)

ROOT = Path(__file__).resolve().parent.parent
SHOTS = Path(os.environ.get("QUINTRA_SHOTS", ROOT / "tmp"))
SHOTS.mkdir(parents=True, exist_ok=True)

NONE, POISON, BURN, SLOW, BLEED = 0, 1, 2, 3, 9
NAMES = {POISON: "poison", BURN: "burn", BLEED: "bleed", SLOW: "slow"}
DURATION = {POISON: 120, BURN: 60, BLEED: 60}
ITEM_ID_ANTIDOTE = 49
SCREEN_ROOM = 5
HP_MAX, HP, X, Y, IFRAMES = (PLAYER + 1, PLAYER + 2, PLAYER + 9,
                             PLAYER + 11, PLAYER + 15)
INV = PLAYER + 24
STATUS = addr("_player_status_kind")
TICKS = addr("_player_status_ticks")
NOTICE = addr("_hud_notice_ticks")
# Window row 0, columns 10..15: the HUD notice lane.
CURED_TILES = (94, 65, 76, 86, 82)
T_E, T_D = 86, 82


def tick(pb, frames):
    for _ in range(frames):
        pb.tick()


def lane(pb):
    pb.memory[0xFF4F] = 0
    return tuple(pb.memory[0x9C00 + 10 + i] for i in range(6))


def wait_cured(pb, what, frames=150):
    """CURED may queue behind the final tick's own card; wait for it."""
    for _ in range(frames):
        if lane(pb)[:5] == CURED_TILES:
            return
        pb.tick()
    raise AssertionError(f"{what} did not show CURED: {lane(pb)}")


def set_inventory(pb, ids):
    for i in range(16):
        pb.memory[INV + i] = ids[i] if i < len(ids) else 0xFF


def antidotes(pb):
    return sum(1 for i in range(16) if pb.memory[INV + i] == ITEM_ID_ANTIDOTE)


def afflict(pb, kind, ticks):
    pb.memory[STATUS] = kind
    pb.memory[TICKS] = ticks


def calm(pb):
    """No contact damage, no hostiles, no stray notices."""
    clear_arena(pb)
    pb.memory[IFRAMES] = 0
    pb.memory[NOTICE] = 0
    tick(pb, 2)


def ride_out(pb, kind, hp, move, max_frames=1400):
    """Run one full condition; return (lowest hp seen, frames, notices)."""
    base_x = 80
    put16(pb, X, base_x)
    put16(pb, Y, 72)
    pb.memory[HP] = hp
    pb.memory[NOTICE] = 0
    afflict(pb, kind, DURATION[kind])
    low = hp
    shown = 0
    last_notice = 0
    for f in range(max_frames):
        if move:
            put16(pb, X, base_x + (f & 1))
        pb.memory[IFRAMES] = 0
        pb.tick()
        hp_now = pb.memory[HP]
        low = min(low, hp_now)
        n = pb.memory[NOTICE]
        if n > last_notice:
            shown += 1
        last_notice = n
        assert pb.memory[SCREEN] == SCREEN_ROOM, (
            f"{NAMES[kind]}: left the room (death?) at frame {f}, hp={hp_now}")
        if pb.memory[STATUS] == NONE:
            return low, f, shown
    raise AssertionError(f"{NAMES[kind]} never expired")


def test_no_dot_death():
    pb = boot(0)
    try:
        calm(pb)
        set_inventory(pb, [])
        for kind in (POISON, BURN, BLEED):
            low, frames, shown = ride_out(pb, kind, 1, move=True)
            assert low == 1 and pb.memory[HP] == 1, (
                f"{NAMES[kind]} took the last half-heart (low={low})")
            assert shown >= 2, f"{NAMES[kind]} at the floor stayed silent"
            # Expiry names itself: CURED.
            wait_cured(pb, f"{NAMES[kind]} expiry")
            assert pb.memory[HP] == 1
            tick(pb, 120)
        pb.screen.image.save(SHOTS / "status-floor-cured.png")
    finally:
        pb.stop(save=False)


def test_totals():
    pb = boot(0)
    try:
        calm(pb)
        set_inventory(pb, [])
        pb.memory[HP_MAX] = 16
        expect = {POISON: 8, BURN: 5}
        for kind, loss in expect.items():
            low, _, shown = ride_out(pb, kind, 16, move=False)
            assert 16 - pb.memory[HP] == loss, (
                f"{NAMES[kind]} total {16 - pb.memory[HP]} != {loss}")
            assert shown >= loss, f"{NAMES[kind]} ticks did not re-name it"
            tick(pb, 120)
        # Bleed while sprinting the entire duration: at most three.
        _, _, _ = ride_out(pb, BLEED, 16, move=True)
        lost = 16 - pb.memory[HP]
        assert 1 <= lost <= 3, f"sprinting Bleed cost {lost} half-hearts"
        tick(pb, 120)
        # Bleed while standing still: free, but still announced.
        _, _, shown = ride_out(pb, BLEED, 16, move=False)
        assert pb.memory[HP] == 16, "standing Bleed drained HP"
        assert shown >= 2, "standing Bleed never re-named itself"
    finally:
        pb.stop(save=False)


def test_notices():
    pb = boot(0)
    try:
        calm(pb)
        # A drain tick names its condition: BLEED (B L E E D).
        pb.memory[HP] = 10
        put16(pb, X, 80)
        afflict(pb, BLEED, 60)
        for f in range(140):
            put16(pb, X, 80 + (f & 1))
            pb.tick()
            if pb.memory[HP] < 10:
                break
        assert pb.memory[HP] == 9, "Bleed never ticked"
        row = lane(pb)
        assert row[2] == row[3] == T_E and row[4] == T_D, (
            f"Bleed tick did not show BLEED: {row}")
        pb.screen.image.save(SHOTS / "status-bleed-notice.png")
        # Non-draining harm re-names itself while active (lane free).
        afflict(pb, SLOW, 40)
        pb.memory[NOTICE] = 0
        seen = 0
        for _ in range(8 * 20):
            pb.tick()
            if pb.memory[NOTICE]:
                seen = 1
                break
        assert seen, "Slow never re-named itself while active"
        # ... and says CURED when it wears off.
        afflict(pb, SLOW, 2)
        pb.memory[NOTICE] = 0
        tick(pb, 24)
        assert pb.memory[STATUS] == NONE
        wait_cured(pb, "Slow expiry")
    finally:
        pb.stop(save=False)


def test_antidote_cures_all():
    pb = boot(0)
    try:
        calm(pb)
        # Automatic: a Burn/Bleed tick at the floor breaks a carried vial.
        for kind in (BURN, BLEED):
            set_inventory(pb, [ITEM_ID_ANTIDOTE])
            put16(pb, X, 80)
            pb.memory[HP] = 1
            pb.memory[NOTICE] = 0
            afflict(pb, kind, DURATION[kind])
            for f in range(400):
                put16(pb, X, 80 + (f & 1))
                pb.tick()
                if pb.memory[STATUS] == NONE:
                    break
            assert pb.memory[STATUS] == NONE, f"{NAMES[kind]} rescue did not cure"
            assert antidotes(pb) == 0, f"{NAMES[kind]} rescue kept the vial"
            assert pb.memory[HP] == 1
            wait_cured(pb, f"{NAMES[kind]} rescue")
            tick(pb, 90)

        # Pack: Bleed focuses the TOOL row on the vial and A cures it.
        for kind in (BLEED, BURN):
            set_inventory(pb, [ITEM_ID_ANTIDOTE, ITEM_ID_ANTIDOTE])
            pb.memory[HP] = 8
            afflict(pb, kind, 50)
            press(pb, "start", held=4, released=40)
            assert pb.memory[SCREEN] != SCREEN_ROOM, "Pack did not open"
            if kind == BLEED:
                pb.screen.image.save(SHOTS / "status-pack-bleed.png")
            press(pb, "a", held=4, released=60)
            assert pb.memory[SCREEN] == SCREEN_ROOM, (
                f"{NAMES[kind]}: Antidote use did not resume")
            assert pb.memory[STATUS] == NONE, f"Pack did not cure {NAMES[kind]}"
            assert antidotes(pb) == 1
            tick(pb, 90)

        # Healthy: still refuses instead of wasting a vial.
        set_inventory(pb, [ITEM_ID_ANTIDOTE])
        press(pb, "start", held=4, released=40)
        press(pb, "a", held=4, released=30)
        assert pb.memory[SCREEN] != SCREEN_ROOM, "healthy A left the Pack"
        assert antidotes(pb) == 1, "healthy Pack A spent an Antidote"
        press(pb, "start", held=4, released=40)
    finally:
        pb.stop(save=False)


def main():
    test_no_dot_death()
    test_totals()
    test_notices()
    test_antidote_cures_all()
    print("[status] PASS no DoT death, poison 8 / burn 5 / bleed <=3, "
          "notices + CURED, Antidote cures poison/burn/bleed")


if __name__ == "__main__":
    main()
