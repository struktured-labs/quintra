#!/usr/bin/env python3
"""Live-ROM contract for Ember's Kilnback pack -> Cinder Rex encounter."""
from pathlib import Path

from test_boss_identity import EN, PL, TM, addr, enter_boss, put16


ROOT = Path(__file__).resolve().parent.parent
ENTITY_SIZE = 28
OAM = 0xFE00
SPR_BOSS_BIG = 40
CINDER_ACTIVE = addr("_cinder_pack_active")
CINDER_DAMAGE_OPEN = addr("_cinder_damage_open")
CINDER_PHASE = addr("_cinder_phase")
CINDER_PATTERN = addr("_cinder_pattern")
CINDER_ALIVE = addr("_cinder_pack_alive")
CINDER_TIMER = addr("_cinder_timer")
CINDER_X = addr("_cinder_pack_x")
CINDER_Y = addr("_cinder_pack_y")
# The encounter's private WRAM block follows its exported globals: x[5],
# y[5], then hazard x/y/ttl/delay arrays. This live test intentionally checks
# the runtime hazard lifetime rather than an OAM snapshot that can land during
# the GBC's ten-sprites-per-scanline selection.
CINDER_HAZARD_TTL = CINDER_ACTIVE + 0x20


def hostile_count(pb):
    return sum(
        pb.memory[EN + i * ENTITY_SIZE] == 1
        and pb.memory[EN + i * ENTITY_SIZE + 1] & 1
        and not pb.memory[EN + i * ENTITY_SIZE + 1] & 0x10
        for i in range(32)
    )


def clear_hostiles(pb):
    for i in range(32):
        ep = EN + i * ENTITY_SIZE
        if (pb.memory[ep] == 1 and pb.memory[ep + 1] & 1
                and not pb.memory[ep + 1] & 0x10):
            pb.memory[ep] = pb.memory[ep + 1] = 0


def place_player_shot(pb, x, y):
    """Place one stationary live player projectile at an exact world pixel."""
    for i in range(31, -1, -1):
        ep = EN + i * ENTITY_SIZE
        if not (pb.memory[ep + 1] & 1):
            pb.memory[ep] = 1
            pb.memory[ep + 1] = 0x11
            put16(pb, ep + 3, x)
            put16(pb, ep + 7, y)
            pb.memory[ep + 10] = pb.memory[ep + 11] = 0
            pb.memory[ep + 14] = 1
            pb.memory[ep + 25] = 0x66
            pb.memory[ep + 26] = 1
            return ep
    raise AssertionError("no free entity slot for armor probe")


def oam_tiles(pb, start=4, end=22):
    return [pb.memory[OAM + i * 4 + 2] for i in range(start, end)
            if pb.memory[OAM + i * 4] and pb.memory[OAM + i * 4 + 1]]


def keep_alive(pb, frames):
    for _ in range(frames):
        pb.memory[PL + 15] = 255
        pb.tick()


def main():
    pb, boss = enter_boss(2, keep_open=True)
    assert pb.memory[boss + 14] == 240, (
        f"two-act Ember HP drifted: {pb.memory[boss + 14]}")
    assert pb.memory[CINDER_ACTIVE] == 1
    assert pb.memory[CINDER_PHASE] == 0
    assert pb.memory[CINDER_ALIVE] == 5
    assert not (pb.memory[boss + 1] & 0x04), (
        "closed Kilnback armor remained targetable")

    # All five rendered bodies are physical armor, even though only the final
    # vent is combat's logical weak point. A shot into the first shell must
    # burst visibly instead of passing through a creature the player can see.
    armor_shot = place_player_shot(
        pb, pb.memory[CINDER_X] + 5, pb.memory[CINDER_Y] + 1)
    keep_alive(pb, 2)
    assert not (pb.memory[armor_shot + 1] & 1), (
        "closed non-anchor Kilnback body let a player shot pass through")

    # The discarded Infernal Maw painted 96 projection tiles over the floor.
    # This arena must be genuinely occupied by moving pack bodies instead.
    projected = sum(55 <= pb.memory[TM + i] <= 63 for i in range(20 * 17))
    assert projected == 0, f"legacy furnace projection survived: {projected} tiles"

    pack_tiles = oam_tiles(pb)
    assert len([t for t in pack_tiles if 40 <= t <= 47]) >= 6, (
        f"five-body Kilnback renderer absent from OAM: {pack_tiles}")
    before = tuple(pb.memory[CINDER_X + i] for i in range(5)) + tuple(
        pb.memory[CINDER_Y + i] for i in range(5))
    keep_alive(pb, 36)
    after = tuple(pb.memory[CINDER_X + i] for i in range(5)) + tuple(
        pb.memory[CINDER_Y + i] for i in range(5))
    assert before != after, "Crucible Wheel bodies did not independently move"

    # The three follow-up formations are physical movement grammars, not
    # names attached to the same orbit. Exercise each directly while keeping
    # all five bodies alive.
    clear_hostiles(pb)
    pb.memory[CINDER_PATTERN] = 1
    pb.memory[CINDER_TIMER] = 0
    press_y = tuple(pb.memory[CINDER_Y + i] for i in range(5))
    keep_alive(pb, 102)
    pressed_y = tuple(pb.memory[CINDER_Y + i] for i in range(5))
    assert sum(pressed_y) > sum(press_y) and hostile_count(pb) >= 5, (
        "Kiln Press lost its descending phalanx or upward backdraft")

    clear_hostiles(pb)
    pb.memory[CINDER_PATTERN] = 2
    pb.memory[CINDER_TIMER] = 0
    keep_alive(pb, 42)
    assert any(pb.memory[CINDER_HAZARD_TTL + i] for i in range(8)), (
        "Brandwalk stopped leaving warned burning nodes")

    pb.memory[CINDER_PATTERN] = 3
    pb.memory[CINDER_TIMER] = 35
    broken_before = tuple(pb.memory[CINDER_X + i] for i in range(5))
    keep_alive(pb, 48)
    broken_after = tuple(pb.memory[CINDER_X + i] for i in range(5))
    assert broken_before != broken_after, (
        "Broken Cadence did not split the fake Wheel into zigzag groups")

    # Force one complete formation's punish window. It exposes exactly the
    # logical vent anchor to the ordinary combat system.
    pb.memory[CINDER_PATTERN] = 0
    pb.memory[CINDER_TIMER] = 119
    keep_alive(pb, 27)
    assert pb.memory[CINDER_DAMAGE_OPEN] == 1
    assert pb.memory[boss + 1] & 0x04, "open furnace vent is not targetable"
    vent_x, vent_y = pb.memory[CINDER_X + 4], pb.memory[CINDER_Y + 4]
    player_x, player_y = pb.memory[PL + 9], pb.memory[PL + 11]
    assert abs(vent_y - player_y) <= 4 and abs(vent_x - player_x) >= 32, (
        "Crucible Wheel recovery vent did not peel into a cardinal weapon lane: "
        f"vent={(vent_x, vent_y)} player={(player_x, player_y)}")
    vent_tiles = oam_tiles(pb)
    assert any(t in (44, 45) for t in vent_tiles), (
        f"open vent pose did not reach OAM: {vent_tiles}; "
        f"pack={[(pb.memory[CINDER_X+i], pb.memory[CINDER_Y+i]) for i in range(5)]}; "
        f"player={(pb.memory[PL+9], pb.memory[PL+11])}")

    # Each 24-HP band removes one animal. Crossing the 120-HP midpoint begins
    # the visible five-husk metamorphosis, then produces a ten-sprite 40x16 Rex.
    pb.memory[boss + 14] = 216
    keep_alive(pb, 2)
    assert pb.memory[CINDER_ALIVE] == 4, "first Kilnback segment did not break"
    pb.memory[boss + 14] = 120
    keep_alive(pb, 2)
    assert pb.memory[CINDER_PHASE] == 1, "pack did not begin metamorphosis"
    transform_shot = ROOT / "tmp" / "cinder-transform-live.png"
    pb.screen.image.save(transform_shot)
    keep_alive(pb, 66)
    assert pb.memory[CINDER_PHASE] == 2, "Cinder Rex did not unfold"
    rex_tiles = oam_tiles(pb)
    assert len([t for t in rex_tiles if 48 <= t <= 55]) == 10, (
        f"40x16 Cinder Rex lost its stretched ten-sprite body: {rex_tiles}")

    # Furnace Breath is a broad wall with one traversable gap, followed later
    # by a reverse wall. Seven projectiles prove this is arena geometry, not
    # the former generic aimed triple shot.
    clear_hostiles(pb)
    pb.memory[CINDER_PATTERN] = 0
    pb.memory[CINDER_TIMER] = 35
    keep_alive(pb, 3)
    assert hostile_count(pb) == 7, (
        f"Furnace Breath lost its seven-lane wall: {hostile_count(pb)}")

    clear_hostiles(pb)
    pb.memory[CINDER_PATTERN] = 1
    pb.memory[CINDER_TIMER] = 27
    keep_alive(pb, 3)
    assert hostile_count(pb) == 2, "Slag Spit lost its mixed-speed paired globs"

    clear_hostiles(pb)
    pb.memory[CINDER_PATTERN] = 2
    pb.memory[CINDER_TIMER] = 19
    keep_alive(pb, 3)
    assert sum(bool(pb.memory[CINDER_HAZARD_TTL + i]) for i in range(8)) >= 5, (
        "Kiln Stomp lost its five delayed footprint tells")

    clear_hostiles(pb)
    pb.memory[CINDER_PATTERN] = 3
    pb.memory[CINDER_TIMER] = 15
    rex_before = (pb.memory[boss + 3] | pb.memory[boss + 4] << 8,
                  pb.memory[boss + 7] | pb.memory[boss + 8] << 8)
    keep_alive(pb, 65)
    rex_after = (pb.memory[boss + 3] | pb.memory[boss + 4] << 8,
                 pb.memory[boss + 7] | pb.memory[boss + 8] << 8)
    assert rex_before != rex_after, f"Rex Charge did not cross the arena: {rex_before}"

    # At critical HP, Rex explodes into five fast Brandwalk silhouettes, then
    # recombines instead of simply gaining projectile speed.
    clear_hostiles(pb)
    pb.memory[boss + 14] = 40
    keep_alive(pb, 2)
    assert pb.memory[CINDER_PHASE] == 3 and pb.memory[CINDER_ALIVE] == 5, (
        "critical Rex did not split into five fire silhouettes")
    keep_alive(pb, 98)
    assert pb.memory[CINDER_PHASE] == 2, "fire pack did not recombine into Rex"

    final_shot = ROOT / "tmp" / "cinder-rex-live.png"
    pb.screen.image.save(final_shot)
    pb.stop(save=False)
    print("[colossal-cinder] PASS five legal 16x8 Kilnbacks; Wheel, Press, "
          "Brandwalk, Broken Cadence; armored/open vent; 5->Rex metamorphosis; "
          "40x16 Rex; Furnace, Slag, Stomp, Charge; critical Brandwalk reprise")


if __name__ == "__main__":
    main()
