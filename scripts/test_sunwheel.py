#!/usr/bin/env python3
"""ROM contract: Sunwheel is a readable Golden Temple lane-shaper."""

from test_enemy_identity import generated_sprite, wait_for_obj_tile
from spinner_contract import assert_told_spiral
from test_stage_archetypes import EN, PL, TM, generated_room


ENTITY_SIZE = 28
ENT_PROJECTILE, ENT_ENEMY = 1, 2
EF_ACTIVE, EF_PLAYER_PROJ = 0x01, 0x10
ENEMY_SUNWHEEL = 24


def active_sunwheel(pb):
    for i in range(32):
        ep = EN + i * ENTITY_SIZE
        if (pb.memory[ep] == ENT_ENEMY and pb.memory[ep + 1] & EF_ACTIVE
                and pb.memory[ep + 17] == ENEMY_SUNWHEEL):
            return ep
    return None


def main():
    seen = []

    def probe(pb, _tiles):
        wheel = active_sunwheel(pb)
        if wheel is None:
            return
        seen.append(1)

        # Golden Temple must install Sunwheel art into the phase-safe slot 79
        # before anything is drawn. This catches a loader regression where
        # the correct typed enemy could spawn with the late-game Midge art.
        expected = generated_sprite("sprite_enemy_sunwheel")
        actual = wait_for_obj_tile(pb, 79, expected)
        assert actual == expected, (
            "Golden Temple did not install Sunwheel art in OBJ slot 79")

        # Exercise the live generated entity on a clear board: one told
        # spiral, a shot per compass point (spinner contract since #3).
        assert_told_spiral(pb, wheel, EN, PL, TM, "Sunwheel")

    for seed in range(0x5A710000, 0x5A710010):
        generated_room(6, seed, probe=probe)
        if seen:
            break
    assert seen, "Sunwheel did not appear in 16 fixed Golden Temple procgen seeds"
    print("[sunwheel] PASS Golden Temple procgen spawn + live told spiral")


if __name__ == "__main__":
    main()
